"""The application service: the launcher's view of the desktop-entry index (Applications Module).

``ctx.apps`` is :class:`AppService` seen by one module (``_ModuleApps``). What it adds to the index
of ``services.desktop_entries`` (one parser, shared with the icon lookup):

* the **search** of the spec: a query is folded (case and accents), an entry matches when every word
  of it matches, and the best rank of a word (start of the name, start of a word of the name,
  anywhere in the name, start of a word of the generic name or a keyword, anywhere in the generic
  name, a keyword or the comment) orders the results; equal ranks by how often the user started the
  application, then by name; an empty query lists the most started first;
* the **start** (:func:`build_command`, :func:`parse_exec`): the ``Exec`` value split by the Desktop
  Entry Specification's quoting rules with its field codes expanded, ``Terminal=true`` through
  ``xdg-terminal-exec``, ``Path=`` as the working folder, the shell's own variables left out of the
  environment, ``XDG_ACTIVATION_TOKEN`` set when the caller has a token, and a transient user scope
  (``systemd-run --user --scope``) when systemd can make one;
* the **count** of starts per application (a JSON file in the state folder, written with a
  temporary file and a rename by the worker).

Threads. The index is built on a worker thread on the first use and again after the folders changed
(the index debounces them); ``search`` reads that list from memory and is cheap, so it runs on the
loop thread; ``launch`` hands the start to the worker and calls back on the loop thread.

Safety. Nothing here starts a process but through a :class:`Runner`. The real one (``SystemRunner``)
refuses while ``PYTEST_CURRENT_TEST`` is set (a test that forgot to inject a fake must not start an
application): it appends the command to the file named by ``TESS_SHELL_LAUNCH_RECORD`` when there is
one (the live tests, which run the shell as a process they cannot inject into) and raises
:class:`SpawnRefused` otherwise.
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import re
import secrets
import shutil
import subprocess
import threading
import unicodedata
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from loguru import logger

from tess_shell.services.api import AppInfo, LaunchResult, Subscription
from tess_shell.services.desktop_entries import ApplicationIndex, DesktopEntry

RECORD_VARIABLE = "TESS_SHELL_LAUNCH_RECORD"  # the guard's recorder (see the module docstring)
TOKEN_VARIABLE = "XDG_ACTIVATION_TOKEN"
SYSTEMD_RUN = "systemd-run"
TERMINAL_LAUNCHER = "xdg-terminal-exec"
# what a started application does not inherit: the variables that belong to the shell's own
# process (systemd's service protocol, the journal) and the shell's own
_OWN_NAMES = frozenset(
    {
        "NOTIFY_SOCKET",
        "LISTEN_PID",
        "LISTEN_FDS",
        "LISTEN_FDNAMES",
        "WATCHDOG_PID",
        "WATCHDOG_USEC",
        "MAINPID",
        "MANAGERPID",
        "INVOCATION_ID",
        "JOURNAL_STREAM",
        "SYSTEMD_EXEC_PID",
        "SYSLOG_IDENTIFIER",
        "DESKTOP_STARTUP_ID",
        TOKEN_VARIABLE,
    }
)
_OWN_PREFIXES = ("TESS_SHELL_", "TESSERAE_SHELL_")
_RESERVED = set(" \t\n\"'\\><~|&;$*?#()`")
_QUOTED_ESCAPES = '"`$\\'


# -- search -------------------------------------------------------------------------------------


def fold(text: str) -> str:
    """``text`` without case and without accents (``Écran`` -> ``ecran``)."""
    plain = unicodedata.normalize("NFKD", text)
    return "".join(c for c in plain if not unicodedata.combining(c)).casefold()


def _word_starts(folded: str, word: str) -> bool:
    """Does a word of ``folded`` (text between non-letters and non-digits) start with ``word``?"""
    at = folded.find(word)
    while at >= 0:
        if at == 0 or not folded[at - 1].isalnum():
            return True
        at = folded.find(word, at + 1)
    return False


@dataclass(frozen=True, slots=True)
class _Row:
    """One application as the search reads it: the text of each field, folded once."""

    entry: DesktopEntry
    name: str
    generic: str
    keywords: tuple[str, ...]
    comment: str

    def rank(self, word: str) -> int:
        """The rank of one word, 1 (best) to 5, or 0 when it does not match."""
        if self.name.startswith(word):
            return 1
        if _word_starts(self.name, word):
            return 2
        if word in self.name:
            return 3
        if _word_starts(self.generic, word) or any(_word_starts(k, word) for k in self.keywords):
            return 4
        if word in self.generic or word in self.comment or any(word in k for k in self.keywords):
            return 5
        return 0


def _row(entry: DesktopEntry) -> _Row:
    return _Row(
        entry,
        fold(entry.name),
        fold(entry.generic_name),
        tuple(fold(k) for k in entry.keywords),
        fold(entry.comment),
    )


def _info(entry: DesktopEntry) -> AppInfo:
    return AppInfo(
        entry.id,
        entry.name,
        entry.generic_name,
        entry.comment,
        entry.icon,
        entry.keywords,
        entry.terminal,
        str(entry.path),
    )


# -- the Exec key -------------------------------------------------------------------------------


class ExecError(ValueError):
    """An ``Exec`` value that cannot be split (an unclosed quote)."""


def split_exec(value: str) -> list[tuple[str, bool]]:
    """``value`` split into arguments by the Desktop Entry Specification's quoting rules: an
    argument is quoted in whole with double quotes, inside which a backslash makes the next
    ``"``, backtick, ``$`` or backslash literal; the specification's own escape rule (``\\\\``) was
    applied when the file was read. Returns ``(argument, was_quoted)``. Arguments are separated by
    spaces (a tab or a newline counts as one)."""
    args: list[tuple[str, bool]] = []
    current: list[str] = []
    quoted = False  # inside double quotes
    was_quoted = False
    started = False  # an argument is open (a quoted empty one counts)
    i = 0
    while i < len(value):
        char = value[i]
        if quoted:
            if char == "\\" and i + 1 < len(value) and value[i + 1] in _QUOTED_ESCAPES:
                current.append(value[i + 1])
                i += 2
                continue
            if char == '"':
                quoted = False
            else:
                current.append(char)
        elif char == '"':
            quoted = started = was_quoted = True
        elif char in " \t\n":
            if started:
                args.append(("".join(current), was_quoted))
                current, started, was_quoted = [], False, False
        else:
            current.append(char)
            started = True
        i += 1
    if quoted:
        raise ExecError("a double quote is not closed")
    if started:
        args.append(("".join(current), was_quoted))
    return args


_CODE = re.compile(r"%(.)", re.DOTALL)
_DROPPED = set("fFuUdDnNvm")  # the file and URL codes (nothing is passed) and the deprecated ones


def parse_exec(entry: DesktopEntry) -> list[str]:
    """The program and arguments of ``entry``'s ``Exec``: split (:func:`split_exec`), then each
    field code: ``%f %F %u %U`` (nothing is passed) and the deprecated ``%d %D %n %N %v %m`` are
    removed,
    ``%i`` becomes ``--icon`` and the ``Icon`` when it is an argument of its own and the entry has
    an icon (removed otherwise), ``%c`` the name, ``%k`` the file's path, ``%%`` a percent sign. An
    argument that was only a removed code goes away; one that holds more keeps the rest. Raises
    :class:`ExecError` for an empty ``Exec`` or an unclosed quote."""
    if not entry.exec.strip():
        raise ExecError("the entry has no Exec")
    out: list[str] = []
    for argument, was_quoted in split_exec(entry.exec):
        if argument == "%i" and not was_quoted:
            if entry.icon:
                out.extend(["--icon", entry.icon])
            continue

        def code(match: re.Match[str], entry: DesktopEntry = entry) -> str:
            char = match.group(1)
            if char == "%":
                return "%"
            if char == "c":
                return entry.name
            if char == "k":
                return str(entry.path)
            if char in _DROPPED or char == "i":
                return ""
            logger.debug(f"applications: {entry.id}: the field code %{char} is not known: removed")
            return ""

        expanded = _CODE.sub(code, argument)
        if expanded or was_quoted or "%" not in argument:
            out.append(expanded)
    if not out:
        raise ExecError("the Exec has no program")
    return out


# -- the start ----------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StartSpec:
    """What a start would run: the command line (with ``systemd-run`` in front of it when it is
    started in a scope), the environment, the working folder and the scope's name (``None`` for a
    plain start)."""

    argv: tuple[str, ...]
    env: Mapping[str, str]
    cwd: str
    scope: str | None = None


class SpawnRefused(RuntimeError):
    """The real runner was asked to start something while a test runs."""


class Runner(Protocol):
    """What starts a process (injected: a test gives a recorder; nothing in a test starts one)."""

    def which(self, program: str) -> str | None:
        """The path of ``program`` on the path, or ``None``."""
        ...

    def scope_available(self) -> bool:
        """Whether an application can be started in a transient user scope."""
        ...

    def spawn(self, spec: StartSpec) -> None:
        """Start ``spec`` detached from the shell (its own session, no inherited descriptors).
        Raises :class:`OSError` when the program could not be started."""
        ...


class SystemRunner:
    """The real runner. The command is run by ``sh`` as a background job (``"$@" &``) with its own
    session and no standard streams: ``sh`` ends at once, so the application is a child of init (or
    of the user manager's subreaper) and the shell never has a zombie to wait for."""

    def __init__(self, env: Mapping[str, str] | None = None) -> None:
        self._env = os.environ if env is None else env
        self._scope: bool | None = None
        self._lock = threading.Lock()

    def which(self, program: str) -> str | None:
        return shutil.which(program, path=self._env.get("PATH"))

    def scope_available(self) -> bool:
        """``systemd-run`` is on the path and a user manager answers (one probe, kept). Under a test
        the presence of the program is all that is asked (a probe would start a process)."""
        if self.which(SYSTEMD_RUN) is None:
            return False
        if os.environ.get("PYTEST_CURRENT_TEST"):
            return True
        with self._lock:
            if self._scope is None:
                try:
                    done = subprocess.run(
                        [SYSTEMD_RUN, "--user", "--scope", "--quiet", "true"],
                        stdin=subprocess.DEVNULL,
                        capture_output=True,
                        timeout=10,
                        check=False,
                    )
                    self._scope = done.returncode == 0
                except (OSError, subprocess.SubprocessError) as exc:
                    logger.debug(f"applications: systemd-run could not be probed: {exc}")
                    self._scope = False
                if not self._scope:
                    logger.debug(
                        "applications: no user scope: applications start as plain processes"
                    )
            return self._scope

    def spawn(self, spec: StartSpec) -> None:
        if os.environ.get("PYTEST_CURRENT_TEST"):
            record = os.environ.get(RECORD_VARIABLE)
            if not record:
                raise SpawnRefused(f"a test must not start {spec.argv[0]}: inject a Runner")
            with open(record, "a", encoding="utf-8") as out:
                out.write(
                    json.dumps(
                        {
                            "argv": list(spec.argv),
                            "cwd": spec.cwd,
                            "scope": spec.scope,
                            "token": spec.env.get(TOKEN_VARIABLE),
                            "env": dict(spec.env),
                        }
                    )
                    + "\n"
                )
            return
        shell = shutil.which("sh") or "/bin/sh"
        child = subprocess.Popen(
            [shell, "-c", '"$@" &', "sh", *spec.argv],
            env=dict(spec.env),
            cwd=spec.cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
        child.wait()  # ``sh`` returns as soon as the job is started


def clean_environment(env: Mapping[str, str]) -> dict[str, str]:
    """``env`` without the variables that belong to the shell's own process."""
    return {k: v for k, v in env.items() if k not in _OWN_NAMES and not k.startswith(_OWN_PREFIXES)}


def scope_name(entry: DesktopEntry) -> str:
    """``app-<id>-<random>.scope``: the id without ``.desktop``, with what a unit name does not
    allow replaced by ``_``."""
    safe = re.sub(r"[^A-Za-z0-9:_.\\-]", "_", entry.app) or "application"
    return f"app-{safe}-{secrets.token_hex(4)}.scope"


class LaunchError(Exception):
    """An application that cannot be started; the text is the reason."""


def build_command(
    entry: DesktopEntry,
    runner: Runner,
    env: Mapping[str, str],
    home: str,
    token: str | None,
    scope: bool,
) -> StartSpec:
    """The start of ``entry``: its command line (``parse_exec``, behind ``xdg-terminal-exec`` for
    ``Terminal=true``), the program checked on the path, the working folder (``Path`` when it is a
    folder, else the user's home), the cleaned environment with the activation token, and, with
    ``scope``, ``systemd-run --user --scope`` in front. Raises :class:`LaunchError`."""
    try:
        argv = parse_exec(entry)
    except ExecError as exc:
        raise LaunchError(f"{entry.name}: {exc}") from exc
    if entry.terminal:
        if runner.which(TERMINAL_LAUNCHER) is None:
            raise LaunchError(
                f"{entry.name} needs a terminal: {TERMINAL_LAUNCHER} is not on the path"
            )
        argv = [TERMINAL_LAUNCHER, *argv]
    program = argv[0]
    if "/" in program:
        if not (os.path.isfile(program) and os.access(program, os.X_OK)):
            raise LaunchError(f"{entry.name}: {program} is not an executable file")
    elif runner.which(program) is None:
        raise LaunchError(f"{entry.name}: {program} is not on the path")
    cwd = home
    if entry.working_dir:
        if os.path.isdir(entry.working_dir):
            cwd = entry.working_dir
        else:
            logger.debug(f"applications: {entry.id}: Path={entry.working_dir} is no folder")
    child_env = clean_environment(env)
    if token:
        child_env[TOKEN_VARIABLE] = token
    name = None
    if scope:
        name = scope_name(entry)
        argv = [
            SYSTEMD_RUN,
            "--user",
            "--scope",
            "--quiet",
            "--collect",
            f"--unit={name}",
            f"--description={entry.name}",
            "--",
            *argv,
        ]
    return StartSpec(tuple(argv), child_env, cwd, name)


# -- the count ----------------------------------------------------------------------------------


class Counts:
    """How often each application was started: a JSON object in one file, written with a
    temporary file and a rename. A file that cannot be read starts empty; one that cannot be
    written is one warning and the counts stay in memory."""

    def __init__(self, path: Path | None) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._counts: dict[str, int] = {}
        self._warned = False
        self._load()

    def _load(self) -> None:
        if self._path is None:
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError) as exc:
            logger.warning(f"applications: {self._path} is not readable ({exc}): counting anew")
            return
        if isinstance(data, dict):
            self._counts = {str(k): int(v) for k, v in data.items() if isinstance(v, int) and v > 0}

    def get(self, entry_id: str) -> int:
        with self._lock:
            return self._counts.get(entry_id, 0)

    def raise_(self, entry_id: str) -> None:
        with self._lock:
            self._counts[entry_id] = self._counts.get(entry_id, 0) + 1
            snapshot = dict(self._counts)
        self._write(snapshot)

    def _write(self, snapshot: Mapping[str, int]) -> None:
        if self._path is None:
            return
        temp = self._path.with_name(self._path.name + ".tmp")
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp.write_text(json.dumps(snapshot, sort_keys=True), encoding="utf-8")
            os.replace(temp, self._path)
        except OSError as exc:
            if not self._warned:
                self._warned = True
                logger.warning(f"applications: cannot write {self._path}: {exc.strerror}")


# -- the service --------------------------------------------------------------------------------


class _Listener:
    """The subscription ``AppService.on_changed`` returns."""

    __slots__ = ("_callback", "_service")

    def __init__(self, service: AppService, callback: Callable[[], None]) -> None:
        self._service = service
        self._callback = callback

    def cancel(self) -> None:
        service = self._service
        with service._lock:
            if self._callback in service._listeners:
                service._listeners.remove(self._callback)


@dataclass(slots=True)
class Stats:
    builds: int = 0  # how many times the list was built (the tests, the measurements)
    build_ms: list[float] = field(default_factory=list)


class AppService:
    """The application service (``ctx.apps`` is one per module over this). ``index`` is the shared
    desktop-entry index; ``runner`` starts processes; ``counts`` is the file of start counts
    (``None`` keeps them in memory); ``call_soon`` runs a function on the loop thread."""

    def __init__(
        self,
        index: ApplicationIndex,
        *,
        runner: Runner | None = None,
        counts: Path | None = None,
        call_soon: Callable[[Callable[[], None]], None] | None = None,
        env: Mapping[str, str] | None = None,
        home: str | None = None,
    ) -> None:
        self.index = index
        self._runner = runner if runner is not None else SystemRunner(env)
        self._counts = Counts(counts)
        self._call_soon = call_soon
        self._env = dict(os.environ if env is None else env)
        self._home = home or str(Path(self._env.get("HOME") or "~").expanduser())
        self._lock = threading.RLock()
        self._rows: list[_Row] = []
        self._ready = False
        self._pool: concurrent.futures.ThreadPoolExecutor | None = None
        self._building = False
        self._again = False  # the folders changed while the list was being built
        self._listeners: list[Callable[[], None]] = []
        self._unlisten: Callable[[], None] | None = None
        self.stats = Stats()

    # -- the list -------------------------------------------------------------------------------

    @property
    def ready(self) -> bool:
        """The list is built (any thread)."""
        with self._lock:
            return self._ready

    @property
    def watching(self) -> bool:
        """The folders are followed with inotify (else the list is rebuilt when the Panel opens)."""
        return self.index.watching

    def start(self) -> None:
        """Build the list on the worker thread (the first use) and follow the index. Safe to call
        again."""
        with self._lock:
            if self._pool is None:
                self._pool = concurrent.futures.ThreadPoolExecutor(
                    max_workers=1, thread_name_prefix="apps"
                )
            if self._unlisten is None:
                self._unlisten = self.index.on_changed(self.refresh)
        self.refresh()

    def stop(self) -> None:
        with self._lock:
            pool, self._pool = self._pool, None
            unlisten, self._unlisten = self._unlisten, None
        if unlisten is not None:
            unlisten()
        if pool is not None:
            pool.shutdown(wait=False, cancel_futures=True)

    def refresh(self) -> None:
        """Build the list again (the index reads the folders again when they changed). One build at
        a time; a request that comes during one makes one more after it."""
        with self._lock:
            pool = self._pool
            if pool is None:
                return
            if self._building:
                self._again = True
                return
            self._building = True
        try:
            pool.submit(self._build)
        except RuntimeError:  # the pool was shut down: the shell is stopping
            with self._lock:
                self._building = False

    def _build(self) -> None:
        import time

        started = time.monotonic()
        try:
            rows = [_row(e) for e in self.index.applications()]
        except Exception:
            logger.opt(exception=True).error("applications: the index could not be built")
            rows = []
        took = (time.monotonic() - started) * 1000
        with self._lock:
            self._rows = rows
            self._ready = True
            self._building = False
            again, self._again = self._again, False
            self.stats.builds += 1
            self.stats.build_ms.append(took)
        logger.debug(f"applications: {len(rows)} applications listed in {took:.0f} ms")
        self._notify()
        if again:
            self.refresh()

    def _notify(self) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            self._to_loop(listener)

    def _to_loop(self, fn: Callable[[], None]) -> None:
        if self._call_soon is not None:
            self._call_soon(fn)
        else:
            fn()

    def on_changed(self, callback: Callable[[], None]) -> Subscription:
        """``callback()`` on the loop thread when the list was built or built again."""
        with self._lock:
            self._listeners.append(callback)

        return _Listener(self, callback)

    # -- asking ---------------------------------------------------------------------------------

    def search(self, query: str, limit: int = 8) -> list[AppInfo]:
        """The applications that match ``query``, best first, at most ``limit`` (see the module's
        docstring). An empty query lists the most started first, then the rest by name."""
        with self._lock:
            rows = self._rows
        words = fold(query).split()
        ranked: list[tuple[int, int, str, _Row]] = []
        for row in rows:
            rank = 0
            for word in words:
                got = row.rank(word)
                if got == 0:
                    break
                rank = max(rank, got)
            else:
                ranked.append((rank, -self._counts.get(row.entry.id), row.name, row))
        ranked.sort(key=lambda r: r[:3])
        return [_info(r[3].entry) for r in ranked[: max(limit, 0)]]

    def get(self, entry_id: str) -> AppInfo | None:
        """The application with this id (with or without ``.desktop``), or ``None``."""
        with self._lock:
            rows = self._rows
        wanted = entry_id if entry_id.endswith(".desktop") else f"{entry_id}.desktop"
        for row in rows:
            if row.entry.id == wanted:
                return _info(row.entry)
        return None

    def count(self, entry_id: str) -> int:
        return self._counts.get(entry_id)

    # -- starting -------------------------------------------------------------------------------

    def launch(
        self,
        entry_id: str,
        token: str | None = None,
        on_done: Callable[[LaunchResult], None] | None = None,
    ) -> None:
        """Start the application ``entry_id`` on the worker: ``on_done(result)`` is called on the
        loop thread. ``token`` is an activation token, or ``None``."""
        with self._lock:
            pool = self._pool
        if pool is None:
            self._finish(on_done, LaunchResult(False, "the application service is not running", ""))
            return
        try:
            pool.submit(self._launch, entry_id, token, on_done)
        except RuntimeError:
            self._finish(on_done, LaunchResult(False, "the shell is stopping", ""))

    def _finish(self, on_done: Callable[[LaunchResult], None] | None, result: LaunchResult) -> None:
        if on_done is not None:
            self._to_loop(lambda: on_done(result))

    def _launch(
        self,
        entry_id: str,
        token: str | None,
        on_done: Callable[[LaunchResult], None] | None,
    ) -> None:
        entry = self.index.get(entry_id)
        if entry is None:
            logger.warning(f"applications: no application {entry_id}")
            self._finish(on_done, LaunchResult(False, f"no application {entry_id}", entry_id))
            return
        try:
            self._start(entry, token)
        except (LaunchError, OSError, SpawnRefused) as exc:
            logger.warning(f"applications: {entry.id}: {exc}")
            self._finish(on_done, LaunchResult(False, str(exc), entry.name))
            return
        except Exception as exc:
            logger.opt(exception=True).error(f"applications: starting {entry.id} raised")
            self._finish(on_done, LaunchResult(False, str(exc), entry.name))
            return
        self._counts.raise_(entry.id)
        self._finish(on_done, LaunchResult(True, "", entry.name))
        self._notify()  # the counts changed the order

    def _start(self, entry: DesktopEntry, token: str | None) -> None:
        scope = self._runner.scope_available()
        spec = build_command(entry, self._runner, self._env, self._home, token, scope)
        if scope:
            try:
                self._runner.spawn(spec)
                logger.info(f"applications: started {entry.id} in {spec.scope}")
                return
            except SpawnRefused:
                raise
            except OSError as exc:
                logger.debug(f"applications: systemd-run failed ({exc}): a plain start instead")
                spec = build_command(entry, self._runner, self._env, self._home, token, False)
        self._runner.spawn(spec)
        logger.info(f"applications: started {entry.id}")
