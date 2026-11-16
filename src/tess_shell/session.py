"""``tesserae-shell install-session``: the two files the desktop session needs (Packaging and
Session Start).

* the desktop file ``io.github.mindderivative.TesseraeShell.desktop``, which gives the shell its
  application id (the Settings portal's ``Register`` wants it), in ``$XDG_DATA_HOME/applications``;
* the systemd user unit ``tesserae-shell.service`` (``Type=notify``), in
  ``$XDG_CONFIG_HOME/systemd/user``.

Both are templates inside the wheel (``tess_shell/data``); the command writes them with the
absolute path of the running command. Standard library only: ``tess_shell.client`` imports this
module for the ``status`` warning, so it must stay as cheap to import as the client is.

Safety. Every path the module writes or removes goes through :func:`guard`, which refuses the
real ``~/.config/systemd/user`` and ``~/.local/share/applications`` while ``PYTEST_CURRENT_TEST``
is set; the default runner (the one that would run ``systemctl --user ...``) refuses under a test
too. A test passes temporary folders in :class:`Targets` and a recording runner.
"""

from __future__ import annotations

import json
import os
import pwd
import re
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tess_shell.exit_codes import ExitCode

APP_ID = "io.github.mindderivative.TesseraeShell"
DESKTOP_NAME = f"{APP_ID}.desktop"
UNIT_NAME = "tesserae-shell.service"
COMMAND_NAME = "tesserae-shell"
WANTED_BY = "graphical-session.target"

SYSTEMCTL_TIMEOUT = 30.0  # seconds a systemctl call may take


# -- where the files go ------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Targets:
    """The two folders the files go to. Built from the environment by default; a test passes
    temporary ones."""

    applications: Path  # $XDG_DATA_HOME/applications
    units: Path  # $XDG_CONFIG_HOME/systemd/user

    @classmethod
    def from_environ(cls, environ: Mapping[str, str] | None = None) -> Targets:
        env = os.environ if environ is None else environ
        home = Path(env.get("HOME") or Path.home())
        data = env.get("XDG_DATA_HOME", "")
        config = env.get("XDG_CONFIG_HOME", "")
        data_home = Path(data) if data and os.path.isabs(data) else home / ".local" / "share"
        config_home = Path(config) if config and os.path.isabs(config) else home / ".config"
        return cls(data_home / "applications", config_home / "systemd" / "user")

    @property
    def desktop_file(self) -> Path:
        return self.applications / DESKTOP_NAME

    @property
    def unit_file(self) -> Path:
        return self.units / UNIT_NAME

    @property
    def wants_link(self) -> Path:
        """The symlink ``systemctl --user enable`` makes for ``WantedBy=`` the session target."""
        return self.units / f"{WANTED_BY}.wants" / UNIT_NAME

    @property
    def enabled(self) -> bool:
        return os.path.lexists(self.wants_link)


class Refused(Exception):
    """An action the safety guard stopped (a test about to touch the real session)."""


class Conflict(Exception):
    """An existing file differs from what the command would write, and ``--force`` was not given."""

    def __init__(self, paths: Sequence[Path]) -> None:
        self.paths = list(paths)
        names = ", ".join(str(p) for p in self.paths)
        super().__init__(
            f"{names} exists and differs from what install-session writes; nothing was changed "
            "(add --force to replace it)"
        )


class WriteFailure(Exception):
    """A folder or file that cannot be written or removed."""

    def __init__(self, path: Path, error: OSError) -> None:
        self.path = path
        super().__init__(f"cannot write {path}: {error.strerror or error}")


class SystemdFailure(Exception):
    """``systemctl --user`` is missing or refused. ``outcome`` is what was done before it (the
    files an ``--enable`` had written), if anything."""

    def __init__(self, message: str, outcome: Outcome | None = None) -> None:
        super().__init__(message)
        self.outcome = outcome


def _failed(verb: str, ran: Ran) -> str:
    return f"{' '.join(systemctl(verb, UNIT_NAME))} failed with {ran.returncode}" + (
        f" ({ran.output})" if ran.output else ""
    )


def real_homes() -> set[Path]:
    """The home directory of the user running the process by the password database, not
    ``$HOME`` (a test sets that to a temporary folder, which is then safe to write to)."""
    try:
        return {Path(pwd.getpwuid(os.getuid()).pw_dir)}
    except KeyError:  # no entry for this user: the environment's home is all there is
        return {Path.home()}


def guard(path: Path, environ: Mapping[str, str] | None = None) -> None:
    """Refuse to touch the real folders of the session while a test runs. ``path`` is a folder
    or a file the caller is about to write or remove."""
    env = os.environ if environ is None else environ
    if "PYTEST_CURRENT_TEST" not in env:
        return
    resolved = Path(os.path.realpath(path))
    for home in real_homes():
        for relative in (".config/systemd/user", ".local/share/applications"):
            real = Path(os.path.realpath(home / relative))
            if resolved == real or real in resolved.parents:
                raise Refused(f"a test may not touch {real}; use a temporary folder")


# -- the command line the files start ---------------------------------------------------------


def current_command(argv0: str | None = None, executable: str | None = None) -> list[str]:
    """The absolute command that starts this install of the shell, without its arguments: the
    ``tesserae-shell`` script that was run, else the one beside the interpreter (a virtual
    environment run as ``python -m tess_shell``), else ``<interpreter> -m tess_shell``. Symbolic
    links are kept, not followed: ``~/.local/bin/tesserae-shell`` survives an upgrade of the tool
    environment it points into."""
    argv0 = sys.argv[0] if argv0 is None else argv0
    executable = sys.executable if executable is None else executable
    if argv0 and os.path.basename(argv0) == COMMAND_NAME:
        script = argv0 if os.sep in argv0 else _on_path(argv0)
        if script and _is_executable(os.path.abspath(script)):
            return [os.path.abspath(script)]
    if not executable:
        raise ValueError("cannot tell which Python runs the shell (sys.executable is empty)")
    beside = os.path.join(os.path.dirname(os.path.abspath(executable)), COMMAND_NAME)
    if _is_executable(beside):
        return [beside]
    return [os.path.abspath(executable), "-m", "tess_shell"]


def _on_path(name: str) -> str | None:
    import shutil

    return shutil.which(name)


def _is_executable(path: str) -> bool:
    return os.path.isfile(path) and os.access(path, os.X_OK)


def _check_plain(arg: str) -> None:
    if any(c in arg for c in "\0\n\r"):
        raise ValueError(f"cannot write {arg!r} into a unit or desktop file: it holds a line break")


_SYSTEMD_SAFE = re.compile(r"[A-Za-z0-9_+=:,./@-]+")


def systemd_quote(arg: str, *, executable: bool = False) -> str:
    """One word of an ``ExecStart=`` line (systemd.syntax: ``%`` is doubled, and ``$`` in an
    argument; a word with anything else than plain characters goes in double quotes with ``\\``
    and ``"`` escaped). ``executable``: the first word, the program: systemd takes it as it
    stands, so a ``$`` in it is not doubled (``systemd-analyze verify`` looks for a path with
    the two dollars otherwise)."""
    _check_plain(arg)
    escaped = arg.replace("%", "%%")
    if not executable:
        escaped = escaped.replace("$", "$$")
    if _SYSTEMD_SAFE.fullmatch(escaped):
        return escaped
    return '"' + escaped.replace("\\", "\\\\").replace('"', '\\"') + '"'


_SYSTEMD_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "s": " ", "\\": "\\", '"': '"', "'": "'"}


def systemd_split(text: str) -> list[str]:
    """The words of an ``ExecStart=`` value (quotes, backslash escapes, ``%%`` and ``$$``)."""
    words: list[str] = []
    current: list[str] = []
    started = False
    quote = ""
    i = 0
    while i < len(text):
        c = text[i]
        if c == "\\" and i + 1 < len(text):
            i += 1
            current.append(_SYSTEMD_ESCAPES.get(text[i], "\\" + text[i]))
            started = True
        elif quote:
            if c == quote:
                quote = ""
            else:
                current.append(c)
        elif c in "\"'":
            quote = c
            started = True
        elif c.isspace():
            if started:
                words.append("".join(current))
                current, started = [], False
        else:
            current.append(c)
            started = True
        i += 1
    if started:
        words.append("".join(current))
    # `$$` is a literal `$` in an argument; the program (the first word) is taken as it stands
    return [(w if i == 0 else w.replace("$$", "$")).replace("%%", "%") for i, w in enumerate(words)]


_DESKTOP_RESERVED = frozenset(" \t\n\"'\\><~|&;$*?#()`")


def desktop_quote(arg: str) -> str:
    """One argument of a desktop file's ``Exec=`` line (Desktop Entry Specification, The Exec key:
    ``%`` is doubled; an argument with a reserved character goes in double quotes, ``"``, backquote,
    ``$`` and ``\\`` escaped, and each backslash is doubled again for the file's string layer)."""
    _check_plain(arg)
    arg = arg.replace("%", "%%")
    if not any(c in _DESKTOP_RESERVED for c in arg):
        return arg
    escaped = re.sub(r'(["`$\\])', r"\\\1", arg).replace("\\", "\\\\")
    return f'"{escaped}"'


# -- the two files ----------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class SessionFile:
    kind: str  # "desktop" or "unit"
    path: Path
    content: str

    @property
    def state(self) -> str:
        """``absent``, ``same`` (the file already holds this content) or ``differs``."""
        try:
            return "same" if self.path.read_text(encoding="utf-8") == self.content else "differs"
        except FileNotFoundError:
            return "absent"
        except OSError, UnicodeDecodeError:
            return "differs"


def read_template(name: str) -> str:
    """A file of ``tess_shell/data`` (package data: a pure wheel carries it)."""
    from importlib.resources import files

    return (files("tess_shell") / "data" / name).read_text(encoding="utf-8")


def set_key(text: str, key: str, value: str) -> str:
    """``text`` with the one ``key=...`` line given ``value``."""
    lines = text.split("\n")
    hits = [i for i, line in enumerate(lines) if line.startswith(f"{key}=")]
    if len(hits) != 1:
        raise ValueError(f"the template has {len(hits)} lines '{key}=', not one")
    lines[hits[0]] = f"{key}={value}"
    return "\n".join(lines)


def exec_arguments(command: Sequence[str], config_dir: Path | None = None) -> list[str]:
    """The words that start the shell: the command, ``run`` and, when ``--config-dir`` was given
    to ``install-session``, that folder (absolute)."""
    words = [*command, "run"]
    if config_dir is not None:
        words += ["--config-dir", os.path.abspath(config_dir)]
    return words


def render_files(
    command: Sequence[str], targets: Targets, config_dir: Path | None = None
) -> list[SessionFile]:
    """The desktop file and the unit, with ``command`` in their ``Exec`` lines."""
    words = exec_arguments(command, config_dir)
    desktop = set_key(
        read_template(DESKTOP_NAME), "Exec", " ".join(desktop_quote(w) for w in words)
    )
    unit = set_key(
        read_template(UNIT_NAME),
        "ExecStart",
        " ".join(systemd_quote(w, executable=i == 0) for i, w in enumerate(words)),
    )
    return [
        SessionFile("desktop", targets.desktop_file, desktop),
        SessionFile("unit", targets.unit_file, unit),
    ]


# -- systemctl --------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Ran:
    """What a runner reports for one command: its exit code and its output."""

    returncode: int
    output: str = ""


Runner = Callable[[Sequence[str]], Ran]


def systemctl(*args: str) -> list[str]:
    return ["systemctl", "--user", *args]


def systemctl_runner(argv: Sequence[str]) -> Ran:
    """The real runner: runs ``argv`` (``systemctl --user ...``). Refused while a test runs; a test
    passes a recording runner instead."""
    if "PYTEST_CURRENT_TEST" in os.environ:
        raise Refused(f"a test may not run {' '.join(argv)}; pass a runner")
    import subprocess

    try:
        done = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            timeout=SYSTEMCTL_TIMEOUT,
            stdin=subprocess.DEVNULL,
            check=False,
        )
    except FileNotFoundError:
        return Ran(127, f"{argv[0]} was not found")
    except subprocess.TimeoutExpired:
        return Ran(124, f"{argv[0]} did not answer within {SYSTEMCTL_TIMEOUT:g} s")
    return Ran(done.returncode, (done.stderr or done.stdout).strip())


def _run(runner: Runner, *args: str) -> Ran:
    return runner(systemctl(*args))


# -- the actions ------------------------------------------------------------------------------


@dataclass(slots=True)
class Outcome:
    action: str  # "install", "remove" or "print"
    files: list[dict[str, Any]]
    enabled: bool
    notes: list[str]
    exec_start: list[str]


def _write_all(files: Sequence[SessionFile], environ: Mapping[str, str] | None) -> list[str]:
    """Write each file to a temporary name in its own folder, then rename them all into place, so a
    failure leaves no half-written file. The results, in order."""
    for f in files:
        guard(f.path, environ)
    results: list[str] = []
    pending: list[tuple[Path, Path]] = []
    try:
        for f in files:
            before = f.state
            if before == "same":
                results.append("unchanged")
                continue
            try:
                f.path.parent.mkdir(parents=True, exist_ok=True)
                import tempfile

                fd, name = tempfile.mkstemp(
                    dir=f.path.parent, prefix=f".{f.path.name}.", suffix=".tmp"
                )
            except OSError as exc:
                raise WriteFailure(f.path, exc) from exc
            pending.append((Path(name), f.path))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as handle:
                    handle.write(f.content)
                os.chmod(name, 0o644)
            except OSError as exc:
                raise WriteFailure(f.path, exc) from exc
            results.append("written" if before == "absent" else "replaced")
        for temporary, final in pending:
            try:
                os.replace(temporary, final)
            except OSError as exc:
                raise WriteFailure(final, exc) from exc
        pending = []
    finally:
        for temporary, _ in pending:
            temporary.unlink(missing_ok=True)
    return results


def install(
    files: Sequence[SessionFile],
    targets: Targets,
    *,
    force: bool,
    enable: bool,
    runner: Runner,
    command: Sequence[str],
    environ: Mapping[str, str] | None = None,
) -> Outcome:
    """Write both files (a differing one only with ``force``), then enable the unit when asked."""
    for f in files:
        guard(f.path, environ)
    differing = [f.path for f in files if f.state == "differs"]
    if differing and not force:
        raise Conflict(differing)
    results = _write_all(files, environ)
    notes: list[str] = []
    out = Outcome(
        "install",
        [
            {"kind": f.kind, "path": str(f.path), "result": r}
            for f, r in zip(files, results, strict=True)
        ],
        targets.enabled,
        notes,
        list(command),
    )
    if enable:
        ran = _run(runner, "enable", UNIT_NAME)
        if ran.returncode != 0:
            raise SystemdFailure(
                f"the files are written, but {UNIT_NAME} cannot be enabled: "
                + _failed("enable", ran),
                out,
            )
        out.enabled = True
    elif not out.enabled:
        notes.append(
            f"not enabled: run `{COMMAND_NAME} install-session --enable` to start it with the "
            "session"
        )
    return out


def remove(
    targets: Targets, *, runner: Runner, environ: Mapping[str, str] | None = None
) -> Outcome:
    """Disable the unit when it is enabled, then remove both files. The configuration folder is
    not touched."""
    paths = [("unit", targets.unit_file), ("desktop", targets.desktop_file)]
    for _, path in paths:
        guard(path, environ)
    guard(targets.wants_link, environ)
    was_enabled = targets.enabled
    notes: list[str] = []
    if was_enabled:
        ran = _run(runner, "disable", UNIT_NAME)
        if ran.returncode != 0:
            raise SystemdFailure(
                f"cannot disable {UNIT_NAME}: " + _failed("disable", ran) + "; nothing was removed"
            )
    results: list[dict[str, Any]] = []
    for kind, path in paths:
        try:
            path.unlink()
            result = "removed"
        except FileNotFoundError:
            result = "absent"
        except OSError as exc:
            raise WriteFailure(path, exc) from exc
        results.append({"kind": kind, "path": str(path), "result": result})
    if was_enabled:
        ran = _run(runner, "daemon-reload")
        if ran.returncode != 0:
            notes.append("systemctl --user daemon-reload failed; the manager still lists the unit")
        notes.append("a running shell is not stopped: run `tesserae-shell quit`")
    return Outcome("remove", results, targets.enabled, notes, [])


def preview(files: Sequence[SessionFile], targets: Targets, command: Sequence[str]) -> Outcome:
    """What ``install`` would write; writes nothing."""
    return Outcome(
        "print",
        [
            {"kind": f.kind, "path": str(f.path), "state": f.state, "content": f.content}
            for f in files
        ],
        targets.enabled,
        [],
        list(command),
    )


# -- the status warning -----------------------------------------------------------------------


def unit_exec_start(text: str) -> list[str] | None:
    """The words of the last non-empty ``ExecStart=`` of the ``[Service]`` section, systemd's
    prefix characters (``@ - : + !``) cut from the first; ``None`` when there is none."""
    section = ""
    value: str | None = None
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("[") and line.endswith("]"):
            section = line
        elif section == "[Service]" and line.startswith("ExecStart="):
            value = line[len("ExecStart=") :].strip() or None  # an empty one resets the list
    if value is None:
        return None
    words = systemd_split(value)
    if words:
        words[0] = words[0].lstrip("@-:+!")
    return words or None


def _shebang_interpreter(path: str) -> str | None:
    try:
        with open(path, "rb") as handle:
            head = handle.readline(512)
    except OSError:
        return None
    if not head.startswith(b"#!"):
        return None
    parts = head[2:].decode("utf-8", "replace").split()
    return parts[0] if parts else None


def _same_file(a: str, b: str) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def stale_warnings(unit: Path, current: Sequence[str] | None = None) -> list[str]:
    """What is wrong with the installed unit's ``ExecStart``: a command that is gone, one that is
    not executable, a script whose interpreter is gone, or a command other than the one running
    (``current``, from :func:`current_command`). Empty when no unit is installed, or it is fine."""
    try:
        text = unit.read_text(encoding="utf-8")
    except OSError, UnicodeDecodeError:
        return []
    fix = f"run `{COMMAND_NAME} install-session --force` to point it at this install"
    words = unit_exec_start(text)
    if words is None:
        return [f"the unit {unit} has no ExecStart; {fix}"]
    exe = words[0]
    if not os.path.isabs(exe):
        return [f"the unit {unit} starts {exe}, which is not an absolute path; {fix}"]
    if not os.path.exists(exe):
        return [f"the unit {unit} starts {exe}, which does not exist; {fix}"]
    if not _is_executable(exe):
        return [f"the unit {unit} starts {exe}, which is not an executable file; {fix}"]
    interpreter = _shebang_interpreter(exe)
    if interpreter and os.path.isabs(interpreter) and not os.path.exists(interpreter):
        return [
            f"the unit {unit} starts {exe}, whose interpreter {interpreter} does not exist; {fix}"
        ]
    if current:
        same = _same_file(exe, current[0]) and list(words[1 : len(current)]) == list(current[1:])
        if not same:
            return [
                f"the unit {unit} starts {exe}, but this command is {current[0]}: a different "
                f"install; if the shell moved or was reinstalled, {fix}"
            ]
    return []


def installed_warnings(environ: Mapping[str, str] | None = None) -> list[str]:
    """The warnings for the unit in the user's folder; never raises (a check must not break the
    command that asks for it)."""
    try:
        return stale_warnings(Targets.from_environ(environ).unit_file, current_command())
    except Exception:
        return []


# -- the command ------------------------------------------------------------------------------


def _text(outcome: Outcome) -> str:
    lines: list[str] = []
    if outcome.action == "print":
        for f in outcome.files:
            lines.append(f"# {f['path']} ({f['state']})")
            lines.append(f["content"].rstrip("\n"))
            lines.append("")
        return "\n".join(lines).rstrip("\n")
    for f in outcome.files:
        lines.append(f"{f['result']} {f['path']}")
    if outcome.action == "install" and outcome.enabled:
        lines.append(f"enabled {UNIT_NAME} (systemctl --user enable {UNIT_NAME})")
    lines.extend(outcome.notes)
    return "\n".join(lines)


def _fail(
    message: str, code: ExitCode, *, json_out: bool, extra: dict[str, Any] | None = None
) -> int:
    if json_out:
        print(json.dumps({"ok": False, "error": message, "exit": int(code), **(extra or {})}))
    else:
        print(f"tesserae-shell: {message}", file=sys.stderr)
    return int(code)


def run_command(
    *,
    print_only: bool = False,
    enable: bool = False,
    remove_files: bool = False,
    force: bool = False,
    json_out: bool = False,
    config_dir: Path | None = None,
    runner: Runner | None = None,
    targets: Targets | None = None,
    command: Sequence[str] | None = None,
    environ: Mapping[str, str] | None = None,
) -> int:
    """``tesserae-shell install-session``; the exit code. 0 done; 1 a differing file kept (no
    ``--force``) or a file that cannot be written; 2 systemd refused, the safety guard stopped it,
    or the command cannot be named."""
    env = os.environ if environ is None else environ
    where = Targets.from_environ(env) if targets is None else targets
    run = systemctl_runner if runner is None else runner
    try:
        if remove_files:
            outcome = remove(where, runner=run, environ=env)
        else:
            words = list(current_command() if command is None else command)
            files = render_files(words, where, config_dir)
            if print_only:
                outcome = preview(files, where, exec_arguments(words, config_dir))
            else:
                outcome = install(
                    files,
                    where,
                    force=force,
                    enable=enable,
                    runner=run,
                    command=exec_arguments(words, config_dir),
                    environ=env,
                )
    except Conflict as exc:
        return _fail(
            str(exc),
            ExitCode.CONFIG,
            json_out=json_out,
            extra={"conflicts": [str(p) for p in exc.paths]},
        )
    except WriteFailure as exc:
        return _fail(str(exc), ExitCode.CONFIG, json_out=json_out)
    except SystemdFailure as exc:
        done = exc.outcome
        if done is not None and not json_out:
            print(_text(done))
        return _fail(
            str(exc),
            ExitCode.ENVIRONMENT,
            json_out=json_out,
            extra={"files": done.files} if done is not None else None,
        )
    except (Refused, ValueError) as exc:
        return _fail(str(exc), ExitCode.ENVIRONMENT, json_out=json_out)
    if json_out:
        print(
            json.dumps(
                {
                    "ok": True,
                    "action": outcome.action,
                    "files": outcome.files,
                    "enabled": outcome.enabled,
                    "exec_start": outcome.exec_start,
                    "notes": outcome.notes,
                }
            )
        )
    else:
        print(_text(outcome))
    return int(ExitCode.OK)
