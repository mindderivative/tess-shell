"""The hand-check kit framework: steps a session can run unattended, in private sandboxes.

THE RULE (the maintainer, 2026-11-16): a kit never asks a person to copy terminal output. Every step
that a session can do runs by itself and writes its result to a file; ``checklist.txt`` keeps only
what no session can do, each line saying why.

This file is standard library only on purpose: a generator (``tests/kwin/prepare_*.py``) imports it
to describe a kit, and :func:`write_kit` copies it into the kit folder as ``kit_runner.py``, so the
kit runs with only its own files and the interpreter that generated it. ``run-all.sh`` calls
``kit_runner.py``, which reads ``steps.json``, runs the ``auto`` steps in order, each in the sandbox
the step names, writes ``results/<id>.txt`` and ``results.txt``, prints one PASS/FAIL/SKIP line per
step and exits non-zero when any step failed (D-019, D-025, D-026: a session never touches the real
session, bus, systemd, KWin, kglobalaccel, portal, audio or files).

The sandboxes (:func:`private_bus`, :func:`private_systemd`, :func:`private_kwin`,
:func:`private_sway`) nest: the compositor, the systemd user
manager live inside a private ``dbus-run-session`` with a private
``XDG_RUNTIME_DIR``. Each one REFUSES to go on when, after its setup, the bus or the runtime
directory is the real one, and each one is killed and removed at the end, also on failure
(:func:`kill_strays` looks for any process that still carries the private runtime directory in its
environment).
"""

from __future__ import annotations

import contextlib
import dataclasses
import json
import os
import re
import select
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SYSTEMD = "/usr/lib/systemd/systemd"

#: variables a sandbox never inherits: they name the real session, bus, compositor or sound server
SCRUBBED = (
    "DBUS_SESSION_BUS_ADDRESS",
    "DBUS_STARTER_ADDRESS",
    "DBUS_STARTER_BUS_TYPE",
    "WAYLAND_DISPLAY",
    "WAYLAND_SOCKET",
    "DISPLAY",
    "SWAYSOCK",
    "I3SOCK",
    "NOTIFY_SOCKET",
    "XDG_RUNTIME_DIR",
    "XDG_SESSION_ID",
    "XDG_SESSION_PATH",
    "XDG_ACTIVATION_TOKEN",
    "DESKTOP_STARTUP_ID",
    "JOURNAL_STREAM",
    "INVOCATION_ID",
    "MANAGERPID",
    "SYSTEMD_EXEC_PID",
    "PULSE_SERVER",
    "PULSE_RUNTIME_PATH",
    "PULSE_COOKIE",
    "PULSE_SINK",
    "PULSE_SOURCE",
    "PIPEWIRE_REMOTE",
    "PIPEWIRE_RUNTIME_DIR",
    "XDG_STATE_HOME",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
    "TESS_SHELL_BIN",
    # a kit that a test runs is not "a test": the guards of install-session name the real folders,
    # and the sandbox's folders are private
    "PYTEST_CURRENT_TEST",
)

VERDICTS = ("PASS", "FAIL", "SKIP")


class SandboxUnavailable(RuntimeError):
    """A tool the sandbox needs is not installed: the steps that need it are skipped."""


class SandboxError(RuntimeError):
    """A sandbox that could not be started or did not answer: the steps that need it fail."""


class SandboxRefused(RuntimeError):
    """The environment after the setup names the REAL bus or runtime directory: nothing runs."""


# -- the environment -------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class RealSession:
    """What the real session looks like, read from the environment of the process that made the
    sandbox (the process is never changed by a sandbox)."""

    bus: str
    runtime: str
    uid_runtime: str

    @classmethod
    def current(cls) -> RealSession:
        return cls(
            bus=os.environ.get("DBUS_SESSION_BUS_ADDRESS", ""),
            runtime=os.environ.get("XDG_RUNTIME_DIR", ""),
            uid_runtime=f"/run/user/{os.getuid()}",
        )


def scrubbed_environ(base: Mapping[str, str] | None = None) -> dict[str, str]:
    """``base`` (default: this process) without the variables that name the real session."""
    env = dict(os.environ if base is None else base)
    for name in SCRUBBED:
        env.pop(name, None)
    return env


def refuse_real(
    env: Mapping[str, str], real: RealSession | None = None, *, need_bus: bool = True
) -> None:
    """Raise :class:`SandboxRefused` when ``env`` holds the real bus or runtime directory, or when
    the bus or the runtime directory is missing or outside the temporary folder."""
    real = RealSession.current() if real is None else real
    runtime = env.get("XDG_RUNTIME_DIR", "")
    bus = env.get("DBUS_SESSION_BUS_ADDRESS", "")
    real_runtimes = {os.path.realpath(p) for p in (real.runtime, real.uid_runtime) if p}
    if not runtime or not os.path.isabs(runtime):
        raise SandboxRefused(f"XDG_RUNTIME_DIR is not a private absolute path: {runtime!r}")
    resolved = os.path.realpath(runtime)
    tmp = os.path.realpath(tempfile.gettempdir())
    if resolved in real_runtimes or any(resolved.startswith(r + os.sep) for r in real_runtimes):
        raise SandboxRefused(f"XDG_RUNTIME_DIR {runtime} is the real runtime directory")
    if not resolved.startswith(tmp + os.sep):
        raise SandboxRefused(f"XDG_RUNTIME_DIR {runtime} is not under {tmp}")
    if need_bus:
        if not bus:
            raise SandboxRefused("DBUS_SESSION_BUS_ADDRESS is not set")
        if real.bus and bus == real.bus:
            raise SandboxRefused(f"the bus {bus} is the real session bus")
        if real.uid_runtime in bus or (real.runtime and real.runtime in bus):
            raise SandboxRefused(f"the bus {bus} lives in the real runtime directory")
        match = re.search(r"unix:path=([^,;]+)", bus)
        if match and not os.path.realpath(match.group(1)).startswith(tmp + os.sep):
            raise SandboxRefused(f"the bus {bus} is not a socket under {tmp}")
    for name in ("WAYLAND_DISPLAY", "SWAYSOCK"):
        value = env.get(name, "")
        if value.startswith("/") and not os.path.realpath(value).startswith(resolved + os.sep):
            raise SandboxRefused(f"{name}={value} is outside {runtime}")


def force_remove(path: Path) -> None:
    """``rm -rf`` that first makes every folder writable (a systemd user manager leaves
    ``systemd/inaccessible/*`` with no permissions)."""
    if not path.exists() and not path.is_symlink():
        return
    for root, dirs, files in os.walk(path):
        for name in (*dirs, *files):
            full = os.path.join(root, name)
            with contextlib.suppress(OSError):
                if not os.path.islink(full):
                    os.chmod(
                        full, stat.S_IRWXU if os.path.isdir(full) else stat.S_IRUSR | stat.S_IWUSR
                    )
    with contextlib.suppress(OSError):
        os.chmod(path, stat.S_IRWXU)
    shutil.rmtree(path, ignore_errors=True)


def unmount_under(path: Path) -> list[str]:
    """Lazily unmount every mount below ``path`` (the gvfs FUSE daemon that a private bus may
    start mounts ``$XDG_RUNTIME_DIR/gvfs``; when it is killed the mount stays and nothing can
    remove the folder). Returns the mount points handled."""
    prefix = str(path) + "/"
    done: list[str] = []
    try:
        with open("/proc/self/mountinfo") as handle:
            lines = handle.read().splitlines()
    except OSError:
        return done
    points = [line.split()[4] for line in lines if len(line.split()) > 4]
    for point in sorted((p for p in points if p.startswith(prefix)), reverse=True):
        for tool in ("fusermount3", "fusermount"):
            if shutil.which(tool):
                subprocess.run(
                    [tool, "-u", "-z", point], capture_output=True, check=False, timeout=15
                )
                break
        else:
            subprocess.run(["umount", "-l", point], capture_output=True, check=False, timeout=15)
        done.append(point)
    return done


def environ_names_runtime(environ: bytes, runtime: Path | str) -> bool:
    """Whether the ``/proc/<pid>/environ`` bytes hold the entry ``XDG_RUNTIME_DIR=<runtime>``: one
    whole entry (entries are NUL separated), never a longer name that ends with it
    (``FOO_XDG_RUNTIME_DIR=...``) or a longer path that starts with it."""
    wanted = f"XDG_RUNTIME_DIR={runtime}".encode()
    return any(entry == wanted for entry in environ.split(b"\0"))


def processes_with_runtime(runtime: Path) -> list[int]:
    """Pids (other than this one) whose environment names ``runtime`` as ``XDG_RUNTIME_DIR``.
    Refuses a runtime that is not a private folder under the temporary directory (the real one
    would match every process of the session)."""
    refuse_real({"XDG_RUNTIME_DIR": str(runtime)}, need_bus=False)
    found: list[int] = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit() or int(entry) == os.getpid():
            continue
        try:
            with open(f"/proc/{entry}/environ", "rb") as handle:
                data = handle.read()
        except OSError:
            continue
        if environ_names_runtime(data, runtime):
            found.append(int(entry))
    return found


def kill_strays(runtime: Path, *, grace: float = 3.0) -> list[int]:
    """Kill every process that still carries ``runtime`` in its environment (TERM, then KILL).
    Returns the pids that had to be killed."""
    found = pids = processes_with_runtime(runtime)
    for sig in (signal.SIGTERM, signal.SIGKILL):
        for pid in pids:
            with contextlib.suppress(OSError):
                os.kill(pid, sig)
        deadline = time.monotonic() + grace
        while time.monotonic() < deadline and processes_with_runtime(runtime):
            time.sleep(0.05)
        pids = processes_with_runtime(runtime)
        if not pids:
            break
    return found


def wait_until(
    predicate: Callable[[], bool], timeout: float, what: str, *, interval: float = 0.05
) -> None:
    """Poll ``predicate`` until it is true (no fixed sleeps); :class:`SandboxError` on timeout."""
    deadline = time.monotonic() + timeout
    while True:
        if predicate():
            return
        if time.monotonic() > deadline:
            raise SandboxError(f"timed out after {timeout:g} s waiting for {what}")
        time.sleep(interval)


def need(*tools: str) -> None:
    missing = [t for t in tools if not (shutil.which(t) or os.path.exists(t))]
    if missing:
        raise SandboxUnavailable(f"not installed: {', '.join(missing)}")


def stop_group(process: subprocess.Popen[Any], *, timeout: float = 5.0) -> None:
    """Terminate a process started with ``start_new_session=True`` and its whole group."""
    with contextlib.suppress(OSError):
        os.killpg(process.pid, signal.SIGTERM)
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(OSError):
            os.killpg(process.pid, signal.SIGKILL)
        process.wait()
    with contextlib.suppress(OSError):
        os.killpg(process.pid, signal.SIGKILL)  # whatever else stayed in the group


# -- the sandboxes ---------------------------------------------------------------------------


@dataclass(slots=True)
class Bus:
    """A private session bus with its own runtime and XDG folders. ``env`` is the environment for
    any child that should live in it."""

    runtime: Path
    root: Path
    env: dict[str, str]
    process: subprocess.Popen[str]
    real: RealSession
    leftovers: list[int] = field(default_factory=list)  # pids still alive at the end (a leak)

    @property
    def address(self) -> str:
        return self.env["DBUS_SESSION_BUS_ADDRESS"]

    def run(
        self, argv: Sequence[str], timeout: float = 60, **kw: Any
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(argv),
            env={**self.env, **kw.pop("env", {})},
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            check=False,
            **kw,
        )

    def name_owned(self, name: str) -> bool:
        done = self.run(
            [
                "dbus-send",
                "--session",
                "--dest=org.freedesktop.DBus",
                "--print-reply",
                "/org/freedesktop/DBus",
                "org.freedesktop.DBus.NameHasOwner",
                f"string:{name}",
            ],
            timeout=10,
        )
        return done.returncode == 0 and "boolean true" in done.stdout


SESSION_CONF = Path("/usr/share/dbus-1/session.conf")
MINIMAL_CONF = (
    "<!DOCTYPE busconfig PUBLIC "
    '"-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN" '
    '"http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">\n'
    "<busconfig><type>session</type><listen>unix:tmpdir=/tmp</listen><auth>EXTERNAL</auth>"
    "<standard_session_servicedirs/>"
    '<policy context="default"><allow send_destination="*" eavesdrop="true"/>'
    '<allow eavesdrop="true"/><allow own="*"/></policy></busconfig>\n'
)


def session_conf(runtime: Path) -> str:
    """The distribution's session bus configuration, listening on ``runtime/bus`` (where a
    systemd user manager puts ``DBUS_SESSION_BUS_ADDRESS`` for its services, so a unit started by
    the private manager finds the same bus)."""
    text = SESSION_CONF.read_text() if SESSION_CONF.exists() else MINIMAL_CONF
    text = re.sub(r"<listen>.*?</listen>", f"<listen>unix:path={runtime}/bus</listen>", text)
    return text.replace(
        "<includedir>session.d</includedir>",
        f"<includedir>{SESSION_CONF.parent}/session.d</includedir>",
    )


@contextlib.contextmanager
def private_bus(real: RealSession | None = None) -> Iterator[Bus]:
    """A private ``dbus-run-session`` with a fresh ``XDG_RUNTIME_DIR`` (mode 700 under the temporary
    folder) and ``XDG_CONFIG_HOME``, ``XDG_DATA_HOME``, ``XDG_CACHE_HOME``, ``XDG_STATE_HOME`` and
    ``HOME`` below a private root. Refuses when the bus or the runtime directory is the real one."""
    need("dbus-run-session", "dbus-send")
    real = RealSession.current() if real is None else real
    root = Path(tempfile.mkdtemp(prefix="tk-", dir=tempfile.gettempdir()))
    runtime = root / "run"
    runtime.mkdir(mode=0o700)
    os.chmod(runtime, 0o700)
    env = scrubbed_environ()
    env["XDG_RUNTIME_DIR"] = str(runtime)
    for name, sub in (
        ("XDG_CONFIG_HOME", "config"),
        ("XDG_DATA_HOME", "data"),
        ("XDG_CACHE_HOME", "cache"),
        ("XDG_STATE_HOME", "state"),
        ("HOME", "home"),
    ):
        (root / sub).mkdir()
        env[name] = str(root / sub)
    # no system bus either: UPower and NetworkManager are the real ones
    env["DBUS_SYSTEM_BUS_ADDRESS"] = f"unix:path={root}/no-system-bus"
    conf = root / "session.conf"
    conf.write_text(session_conf(runtime))
    process: subprocess.Popen[str] | None = None
    bus: Bus | None = None
    try:
        process = subprocess.Popen(
            [
                "dbus-run-session",
                f"--config-file={conf}",
                "--",
                "sh",
                "-c",
                'echo "$DBUS_SESSION_BUS_ADDRESS"; exec cat',
            ],
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            start_new_session=True,
        )
        assert process.stdout is not None
        ready, _, _ = select.select([process.stdout], [], [], 20)
        line = process.stdout.readline().strip() if ready else ""
        if not line:
            raise SandboxError("dbus-run-session printed no bus address")
        env["DBUS_SESSION_BUS_ADDRESS"] = line
        refuse_real(env, real)
        bus = Bus(runtime, root, env, process, real)
        wait_until(lambda: bus.name_owned("org.freedesktop.DBus"), 20, "the private bus")
        yield bus
    finally:
        if process is not None:
            with contextlib.suppress(OSError):
                if process.stdin is not None:
                    process.stdin.close()
            stop_group(process)
        leftovers = kill_strays(runtime)
        if bus is not None:
            bus.leftovers = leftovers
        unmount_under(runtime)
        force_remove(root)


@dataclass(slots=True)
class Systemd:
    """A private ``systemd --user`` manager; ``systemctl --user`` in ``env`` talks to it."""

    bus: Bus
    process: subprocess.Popen[bytes]
    log: Path

    @property
    def env(self) -> dict[str, str]:
        return self.bus.env

    def ctl(self, *args: str, timeout: float = 90) -> subprocess.CompletedProcess[str]:
        return self.bus.run(["systemctl", "--user", *args], timeout=timeout)

    def set_environment(self, **variables: str) -> None:
        done = self.ctl("set-environment", *(f"{k}={v}" for k, v in variables.items()))
        if done.returncode != 0:
            raise SandboxError(f"set-environment failed: {done.stderr.strip()}")

    def active_units(self) -> list[str]:
        done = self.ctl(
            "list-units", "--no-legend", "--plain", "--state=active,activating", "--type=service"
        )
        return [line.split()[0] for line in done.stdout.splitlines() if line.split()]


_SYSTEMD_WORKS: list[bool] = []


def systemd_works() -> bool:
    """Whether a private ``systemd --user`` manager can be started on this machine (asked once).
    The binary can be there while the manager cannot run: a CI runner has systemd but is not a
    login session, and the manager exits at once. A test or a step then skips with that reason
    instead of failing."""
    if not _SYSTEMD_WORKS:
        try:
            with private_bus() as bus, private_systemd(bus):
                _SYSTEMD_WORKS.append(True)
        except SandboxError, OSError:
            _SYSTEMD_WORKS.append(False)
    return _SYSTEMD_WORKS[0]


@contextlib.contextmanager
def private_systemd(bus: Bus) -> Iterator[Systemd]:
    """A ``systemd --user`` manager inside ``bus`` (its own runtime, so its units, its
    ``systemctl --user`` and its sockets are private). Every unit is stopped at the end; the
    leftovers of the manager (``systemd/inaccessible``) are made removable."""
    need(SYSTEMD, "systemctl")
    refuse_real(bus.env, bus.real)
    log = bus.root / "systemd.log"
    # An empty target of its own: default.target would pull in the socket units of the desktop
    # (the bus, pipewire, pulse, gpg-agent), and a connection would start real daemons.
    transient = bus.runtime / "systemd" / "user"
    transient.mkdir(parents=True, exist_ok=True)
    (transient / "kit.target").write_text(
        "[Unit]\nDescription=Kit sandbox\nDefaultDependencies=no\n"
    )
    handle = open(log, "wb")  # noqa: SIM115 - lives as long as the manager
    process = subprocess.Popen(
        [SYSTEMD, "--user", "--unit=kit.target"],
        env=bus.env,
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=handle,
        start_new_session=True,
    )
    manager = Systemd(bus, process, log)
    try:
        private = bus.runtime / "systemd" / "private"

        def up() -> bool:
            if process.poll() is not None:
                raise SandboxError(f"systemd --user exited early: {log.read_text()[-400:]}")
            if not private.exists():
                return False
            done = manager.ctl("is-system-running", timeout=20)
            return done.stdout.strip() in ("running", "degraded")

        wait_until(up, 30, "the private systemd manager")
        # the manager names its own bus socket; the units must see the sandbox bus (KWin, the shell)
        manager.set_environment(DBUS_SESSION_BUS_ADDRESS=bus.address)
        yield manager
    finally:
        with contextlib.suppress(Exception):
            for unit in manager.active_units():
                manager.ctl("stop", unit, timeout=30)
        stop_group(process)
        handle.close()


@dataclass(slots=True)
class Compositor:
    """A private Wayland compositor (KWin or sway) in a private bus. ``env`` is the bus environment
    plus ``WAYLAND_DISPLAY``."""

    name: str
    bus: Bus
    process: subprocess.Popen[bytes]
    display: str
    log: Path
    env: dict[str, str]

    def run(
        self, argv: Sequence[str], timeout: float = 60, **kw: Any
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            list(argv),
            env={**self.env, **kw.pop("env", {})},
            capture_output=True,
            text=True,
            timeout=timeout,
            stdin=subprocess.DEVNULL,
            check=False,
            **kw,
        )


@contextlib.contextmanager
def private_kwin(
    bus: Bus, *, width: int = 1280, height: int = 720, global_shortcuts: bool = True
) -> Iterator[Compositor]:
    """A real ``kwin_wayland --virtual`` on socket ``pkwin`` in ``bus`` (its own kwinrc and
    kwinrulesrc under the private ``XDG_CONFIG_HOME``); waits until ``org.kde.KWin`` is on the
    private bus. KWin 6.8 hosts the ``org.kde.kglobalaccel`` service itself, so a key chord sent
    through its fake input (``tests/kitdrive.py``) reaches a shortcut a client registered; with
    ``global_shortcuts=False`` (``--no-global-shortcuts``) it would not."""
    need("kwin_wayland")
    refuse_real(bus.env, bus.real)
    log = bus.root / "kwin.log"
    handle = open(log, "wb")  # noqa: SIM115
    env = dict(bus.env)
    # what a KWin script prints (print(), console.log) goes to kwin.log: a step reads it there
    process = subprocess.Popen(
        [
            "kwin_wayland",
            "--virtual",
            "--socket",
            "pkwin",
            "--no-lockscreen",
            *([] if global_shortcuts else ["--no-global-shortcuts"]),
            "--width",
            str(width),
            "--height",
            str(height),
        ],
        env={
            **env,
            "QT_LOGGING_RULES": "kwin_scripting.debug=true;js.debug=true",
            "QT_FORCE_STDERR_LOGGING": "1",
        },
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=handle,
        start_new_session=True,
    )
    try:

        def up() -> bool:
            if process.poll() is not None:
                raise SandboxError(f"kwin_wayland exited early: {log.read_text()[-400:]}")
            return (bus.runtime / "pkwin").exists() and bus.name_owned("org.kde.KWin")

        wait_until(up, 40, "the private KWin")
        env["WAYLAND_DISPLAY"] = "pkwin"
        refuse_real(env, bus.real)
        yield Compositor("kwin", bus, process, "pkwin", log, env)
    finally:
        stop_group(process)
        handle.close()


@contextlib.contextmanager
def private_sway(bus: Bus) -> Iterator[Compositor]:
    """A headless sway (pixman) in ``bus``; ``wtype`` and ``swaymsg`` work against it
    (``SWAYSOCK`` is in ``env``)."""
    need("sway", "swaymsg")
    refuse_real(bus.env, bus.real)
    display_file = bus.root / "sway-display"
    config = bus.root / "sway-config"
    config.write_text(f"exec sh -c 'echo $WAYLAND_DISPLAY > {display_file}'\n")
    log = bus.root / "sway.log"
    handle = open(log, "wb")  # noqa: SIM115
    env = dict(bus.env)
    env.update(WLR_BACKENDS="headless", WLR_LIBINPUT_NO_DEVICES="1", WLR_RENDERER="pixman")
    process = subprocess.Popen(
        ["sway", "-c", str(config)],
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=handle,
        stderr=handle,
        start_new_session=True,
    )
    try:
        sock = bus.runtime / f"sway-ipc.{os.getuid()}.{process.pid}.sock"
        child_env = {**bus.env, "SWAYSOCK": str(sock)}

        def up() -> bool:
            if process.poll() is not None:
                raise SandboxError(f"sway exited early: {log.read_text()[-400:]}")
            if not (display_file.exists() and display_file.read_text().strip() and sock.exists()):
                return False
            done = subprocess.run(
                ["swaymsg", "-t", "get_version"], env=child_env, capture_output=True, check=False
            )
            return done.returncode == 0

        wait_until(up, 30, "the private sway")
        display = display_file.read_text().strip()
        child_env["WAYLAND_DISPLAY"] = display
        refuse_real(child_env, bus.real)
        yield Compositor("sway", bus, process, display, log, child_env)
    finally:
        stop_group(process)
        handle.close()


# -- the steps -------------------------------------------------------------------------------


KINDS = ("auto", "manual", "real-session")
SANDBOXES = ("none", "bus", "systemd", "kwin", "sway")


@dataclass(slots=True)
class Result:
    """What a step printed and returned (what a ``check`` sees)."""

    returncode: int
    stdout: str
    stderr: str
    seconds: float
    env: dict[str, str] = field(default_factory=dict)
    kit: Path | None = None
    step_dir: Path | None = None

    @property
    def output(self) -> str:
        return self.stdout + self.stderr


Check = Callable[[Result], "str | None"]


@dataclass(frozen=True, slots=True)
class Step:
    """One line of a kit.

    ``kind``: ``auto`` runs by itself; ``manual`` is something no session can do (``reason`` says
    why) and goes to ``checklist.txt``; ``real-session`` needs the maintainer's real session
    (``action`` is the exact thing to ask permission for, ``reason`` why no sandbox will do).

    ``command`` is an argv list, or a script text run by ``bash -c``. ``sandbox`` names the
    sandboxes the command runs in, joined with ``+`` (``bus``, ``systemd`` (implies a bus),
    ``kwin``, ``sway``, ``none``); sandboxes are started when first needed and
    kept until the end of the run, so steps that share one see each other's results. ``tools`` are
    programs the step needs: missing, it is skipped.

    The expectation: the exit code (``None``: not checked), ``expect`` regexes that must match the
    output (stdout then stderr), ``forbid`` regexes that must not, and ``check``, a callable
    ``(Result) -> str | None`` returning a failure text, or (for a kit file, which cannot hold a
    function) the source text of a ``def check(result): ...``.
    """

    id: str
    title: str
    kind: str = "auto"
    command: tuple[str, ...] | str = ()
    sandbox: str = "none"
    exit_code: int | None = 0
    expect: tuple[str, ...] = ()
    forbid: tuple[str, ...] = ()
    check: Check | str | None = None
    reason: str = ""
    action: str = ""
    tools: tuple[str, ...] = ()
    timeout: float = 120.0

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"step {self.id}: kind {self.kind!r} is not one of {KINDS}")
        for part in self.sandbox.split("+"):
            if part not in SANDBOXES:
                raise ValueError(f"step {self.id}: sandbox {part!r} is not one of {SANDBOXES}")
        if self.kind != "auto" and not self.reason:
            raise ValueError(f"step {self.id}: a {self.kind} step needs a reason")
        if self.kind == "real-session" and not self.action:
            raise ValueError(f"step {self.id}: a real-session step needs the exact action")
        if self.kind == "auto" and not self.command:
            raise ValueError(f"step {self.id}: an auto step needs a command")

    @property
    def needs(self) -> list[str]:
        """The sandboxes of ``sandbox``, in the order they are started."""
        wanted = {p for p in self.sandbox.split("+") if p != "none"}
        if wanted - {"bus"}:
            wanted.add("bus")
        order = ("bus", "kwin", "sway", "systemd")
        return [n for n in order if n in wanted]

    def command_text(self) -> str:
        if isinstance(self.command, str):
            return self.command.rstrip("\n")
        return " ".join(_shell_quote(w) for w in self.command)

    def argv(self) -> list[str]:
        if isinstance(self.command, str):
            return ["bash", "-c", self.command]
        return list(self.command)

    def expectation_text(self) -> str:
        parts = ["exit code " + ("not checked" if self.exit_code is None else str(self.exit_code))]
        parts += [f"output must match /{p}/" for p in self.expect]
        parts += [f"output must not match /{p}/" for p in self.forbid]
        if self.check is not None:
            parts.append("and its own check (" + (_check_summary(self.check)) + ")")
        return "; ".join(parts)

    def to_json(self) -> dict[str, Any]:
        if callable(self.check):
            raise ValueError(
                f"step {self.id}: a kit file holds a check as source text, not a function"
            )
        data = dataclasses.asdict(self)
        data["command"] = self.command if isinstance(self.command, str) else list(self.command)
        for key in ("expect", "forbid", "tools"):
            data[key] = list(data[key])
        return data

    @classmethod
    def from_json(cls, data: Mapping[str, Any]) -> Step:
        data = dict(data)
        cmd = data.get("command", ())
        data["command"] = cmd if isinstance(cmd, str) else tuple(cmd)
        for key in ("expect", "forbid", "tools"):
            data[key] = tuple(data.get(key, ()))
        return cls(**data)


def _shell_quote(word: str) -> str:
    import shlex

    return shlex.quote(word)


def _check_summary(check: Check | str) -> str:
    if isinstance(check, str):
        first = next((ln.strip() for ln in check.splitlines() if ln.strip()), "check")
        return first
    return getattr(check, "__name__", "a python check")


def compile_check(check: Check | str) -> Check:
    if callable(check):
        return check
    namespace: dict[str, Any] = {"re": re, "json": json, "os": os, "Path": Path}
    exec(compile(check, "<check>", "exec"), namespace)
    function = namespace.get("check")
    if not callable(function):
        raise ValueError("a check source must define check(result)")
    return function  # type: ignore[no-any-return]


def evaluate(step: Step, result: Result) -> list[str]:
    """The reasons a step failed its expectation (empty: it passed)."""
    reasons: list[str] = []
    if step.exit_code is not None and result.returncode != step.exit_code:
        reasons.append(f"exit code {result.returncode}, expected {step.exit_code}")
    for pattern in step.expect:
        if not re.search(pattern, result.output, re.MULTILINE | re.DOTALL):
            reasons.append(f"output does not match /{pattern}/")
    for pattern in step.forbid:
        found = re.search(pattern, result.output, re.MULTILINE)
        if found:
            line = result.output[found.start() :].split("\n", 1)[0]
            reasons.append(f"output matches /{pattern}/: {line[:160]!r}")
    if step.check is not None:
        try:
            message = compile_check(step.check)(result)
        except Exception as exc:  # a broken check is a failure of the step, with the reason
            message = f"the check raised {type(exc).__name__}: {exc}"
        if message:
            reasons.append(message)
    return reasons


@dataclass(slots=True)
class Outcome:
    step: Step
    verdict: str
    reason: str
    file: str


# -- the sandboxes of one run ----------------------------------------------------------------


class Sandboxes:
    """The sandboxes a run has started so far. They are started when a step first needs them, in a
    fixed order, and closed together at the end."""

    def __init__(self) -> None:
        self.stack = contextlib.ExitStack()
        self.bus: Bus | None = None
        self.systemd: Systemd | None = None
        self.compositors: dict[str, Compositor] = {}

    def ensure(self, names: Sequence[str]) -> None:
        for name in names:
            if name == "bus" and self.bus is None:
                self.bus = self.stack.enter_context(private_bus())
            elif name in ("kwin", "sway") and name not in self.compositors:
                assert self.bus is not None
                opener = private_kwin if name == "kwin" else private_sway
                comp = self.stack.enter_context(opener(self.bus))
                self.compositors[name] = comp
                if self.systemd is not None:
                    self.systemd.set_environment(WAYLAND_DISPLAY=comp.display)
            elif name == "systemd" and self.systemd is None:
                assert self.bus is not None
                self.systemd = self.stack.enter_context(private_systemd(self.bus))
                for comp in self.compositors.values():
                    self.systemd.set_environment(WAYLAND_DISPLAY=comp.display)

    def env_for(self, names: Sequence[str]) -> dict[str, str]:
        """The environment of a command in these sandboxes (the compositor named last wins)."""
        if not names:
            return scrubbed_environ()
        assert self.bus is not None
        env = dict(self.bus.env)
        for comp in ("kwin", "sway"):
            if comp in names and comp in self.compositors:
                env = dict(self.compositors[comp].env)
        env["SANDBOX"] = str(self.bus.root)
        return env

    def save_logs(self, dest: Path) -> None:
        """Copy the logs of the compositor, the manager and the daemons (and any ``*.out`` a step
        wrote into ``$SANDBOX``) into ``dest``."""
        if self.bus is None:
            return
        dest.mkdir(parents=True, exist_ok=True)
        for pattern in ("*.log", "*.out"):
            for path in self.bus.root.glob(pattern):
                with contextlib.suppress(OSError):
                    shutil.copyfile(path, dest / path.name)

    def close(self) -> None:
        self.stack.close()


# -- the runner ------------------------------------------------------------------------------


def run_step(step: Step, kit: Path, sandboxes: Sandboxes, variables: Mapping[str, str]) -> Outcome:
    results = kit / "results"
    out_file = f"results/{step.id}.txt"
    step_dir = results / f"{step.id}.d"
    step_dir.mkdir(parents=True, exist_ok=True)
    header = [
        f"step: {step.id}",
        f"title: {step.title}",
        f"kind: {step.kind}",
        f"sandbox: {step.sandbox}",
        "command:",
        *("  " + ln for ln in step.command_text().splitlines()),
        f"expectation: {step.expectation_text()}",
    ]

    def finish(verdict: str, reason: str, body: Sequence[str] = ()) -> Outcome:
        text = "\n".join([*header, f"verdict: {verdict}", f"reason: {reason}", *body]) + "\n"
        (kit / out_file).write_text(text)
        return Outcome(step, verdict, reason, out_file)

    missing = [t for t in step.tools if not (shutil.which(t) or os.path.exists(t))]
    if missing:
        return finish("SKIP", f"not installed: {', '.join(missing)}")
    try:
        sandboxes.ensure(step.needs)
    except SandboxUnavailable as exc:
        return finish("SKIP", f"sandbox unavailable ({exc})")
    except SandboxError as exc:
        return finish("FAIL", f"sandbox did not start: {exc}")
    env = sandboxes.env_for(step.needs)
    env.update(variables)
    env.update(KIT=str(kit), RESULTS=str(results), STEP_DIR=str(step_dir), STEP=step.id)
    started = time.monotonic()
    process = subprocess.Popen(
        step.argv(),
        env=env,
        cwd=kit,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        errors="replace",
        start_new_session=True,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=step.timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        with contextlib.suppress(OSError):
            os.killpg(process.pid, signal.SIGKILL)
        stdout, stderr = process.communicate()
    except FileNotFoundError as exc:  # pragma: no cover - Popen raises at construction
        stdout, stderr = "", str(exc)
    with contextlib.suppress(OSError):
        os.killpg(process.pid, signal.SIGKILL)  # anything the step left in its group
    result = Result(
        returncode=process.returncode,
        stdout=stdout,
        stderr=stderr,
        seconds=time.monotonic() - started,
        env=env,
        kit=kit,
        step_dir=step_dir,
    )
    reasons = [f"timed out after {step.timeout:g} s"] if timed_out else evaluate(step, result)
    with contextlib.suppress(OSError):
        step_dir.rmdir()  # only when the step wrote nothing there
    verdict = "FAIL" if reasons else "PASS"
    reason = "; ".join(reasons) if reasons else "expectation met"
    return finish(
        verdict,
        reason,
        [
            f"exit code: {result.returncode}",
            f"seconds: {result.seconds:.1f}",
            "--- stdout ---",
            stdout.rstrip("\n"),
            "--- stderr ---",
            stderr.rstrip("\n"),
        ],
    )


def skipped(step: Step, kit: Path) -> Outcome:
    """A manual or real-session step: it is never run; the line says where it is listed."""
    out_file = f"results/{step.id}.txt"
    reason = f"{step.kind}, see checklist.txt: {step.reason}"
    text = "\n".join(
        [
            f"step: {step.id}",
            f"title: {step.title}",
            f"kind: {step.kind}",
            "verdict: SKIP",
            f"reason: {reason}",
        ]
    )
    (kit / out_file).write_text(text + "\n")
    return Outcome(step, "SKIP", reason, out_file)


@dataclass(slots=True)
class Run:
    outcomes: list[Outcome]
    strays: list[int]  # processes the sandboxes left behind (killed at the end; a leak)

    @property
    def failed(self) -> bool:
        return bool(self.strays) or any(o.verdict == "FAIL" for o in self.outcomes)

    def verdict(self, step_id: str) -> str:
        return next(o.verdict for o in self.outcomes if o.step.id == step_id)


def run_kit(
    steps: Sequence[Step],
    kit: Path,
    *,
    variables: Mapping[str, str] | None = None,
    only: Sequence[str] = (),
    echo: Callable[[str], None] = print,
) -> Run:
    """Run every ``auto`` step of ``steps`` in order, write ``results/`` and ``results.txt`` under
    ``kit``, echo one line per step. A manual or real-session step is listed as SKIP and never
    runs."""
    kit = Path(kit)
    results = kit / "results"
    force_remove(results)
    results.mkdir(parents=True)
    outcomes: list[Outcome] = []
    sandboxes = Sandboxes()
    bus: Bus | None = None
    try:
        for step in steps:
            if only and step.id not in only:
                continue
            if step.kind != "auto":
                outcome = skipped(step, kit)
            else:
                outcome = run_step(step, kit, sandboxes, variables or {})
            outcomes.append(outcome)
            echo(f"{outcome.verdict}  {step.id}  {step.title}: {outcome.reason}")
        bus = sandboxes.bus
    finally:
        sandboxes.save_logs(kit / "results" / "sandbox")
        sandboxes.close()
    strays = list(bus.leftovers) if bus is not None else []
    write_results(kit, outcomes, strays)
    echo(summary_line(outcomes, strays))
    return Run(outcomes, strays)


def summary_line(outcomes: Sequence[Outcome], strays: Sequence[int] = ()) -> str:
    counts = {v: sum(1 for o in outcomes if o.verdict == v) for v in VERDICTS}
    tail = f"; {len(strays)} stray process(es) killed after the run" if strays else ""
    return f"{counts['PASS']} PASS, {counts['FAIL']} FAIL, {counts['SKIP']} SKIP{tail}"


def write_results(kit: Path, outcomes: Sequence[Outcome], strays: Sequence[int] = ()) -> None:
    lines = [f"{o.verdict}  {o.step.id}  {o.reason}  [{o.file}]" for o in outcomes]
    lines.append(
        f"{'FAIL' if strays else 'PASS'}  cleanup  "
        + (
            f"processes left in the sandbox: {list(strays)}"
            if strays
            else "no process left in the sandbox"
        )
        + "  [-]"
    )
    lines.append(summary_line(outcomes, strays))
    (kit / "results.txt").write_text("\n".join(lines) + "\n")


# -- the checklist and the kit folder --------------------------------------------------------


def checklist_text(title: str, steps: Sequence[Step], intro: str = "") -> str:
    """``checklist.txt``: a pointer to ``results.txt`` and the count of unattended steps, then ONLY
    the manual and real-session steps, each with its reason (and the exact action to ask for)."""
    auto = [s for s in steps if s.kind == "auto"]
    human = [s for s in steps if s.kind != "auto"]
    lines = [
        title,
        "",
        f"{len(auto)} steps run unattended in private sandboxes: run ./run-all.sh, then read",
        "results.txt (one PASS/FAIL/SKIP line each; the full output of every step is in",
        "results/<id>.txt). You do not copy any output anywhere. What is left is below: only",
        "what no session can do.",
    ]
    if intro:
        lines += ["", intro.strip()]
    if not human:
        lines += ["", "Nothing is left for you: every step is unattended."]
    for step in human:
        lines += [
            "",
            f"{step.id}  [{step.kind}]  {step.title}",
            f"    why a session cannot: {step.reason}",
        ]
        if step.action:
            lines.append(f"    exact action (ask permission first): {step.action}")
        if step.expect:
            lines.append("    expected: " + "; ".join(step.expect))
    return "\n".join(lines) + "\n"


def write_kit(
    root: Path,
    steps: Sequence[Step],
    *,
    title: str,
    intro: str = "",
    files: Mapping[str, str] | None = None,
    executable: Sequence[str] = (),
    variables: Mapping[str, str] | None = None,
    python: str | None = None,
    obsolete: Sequence[str] = (),
    support: Sequence[str] = (),
) -> None:
    """Write a kit folder: ``kit_runner.py`` (this file), ``steps.json``, ``run-all.sh``,
    ``checklist.txt``, any extra ``files`` (name -> text; ``executable`` names get mode 755) and
    the ``support`` files (paths below ``tests/``, copied under their base name).
    A folder that holds a ``backup`` directory keeps it; everything else the generator writes is
    replaced."""
    root.mkdir(parents=True, exist_ok=True)
    python = python or sys.executable
    for name in obsolete:  # files of an older version of the kit (never a backup folder)
        (root / name).unlink(missing_ok=True)
    for name in ("results", "results.txt"):
        target = root / name
        if target.is_dir():
            force_remove(target)
        elif target.exists():
            target.unlink()
    shutil.copyfile(Path(__file__).resolve(), root / "kit_runner.py")
    for name in support:  # helpers and drivers, named relative to this folder (tests/)
        shutil.copyfile(Path(__file__).resolve().parent / name, root / Path(name).name)
    data = {
        "title": title,
        "variables": dict(variables or {}),
        "steps": [s.to_json() for s in steps],
    }
    (root / "steps.json").write_text(json.dumps(data, indent=2) + "\n")
    for name, text in (files or {}).items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        if name in executable:
            path.chmod(0o755)
    run_all = root / "run-all.sh"
    run_all.write_text(
        "#!/bin/sh\n"
        "# Runs every unattended step in private sandboxes; writes results.txt and results/.\n"
        'cd "$(dirname "$0")" || exit 1\n'
        f'exec env -u WAYLAND_DISPLAY -u DISPLAY {_shell_quote(python)} kit_runner.py "$@"\n'
    )
    run_all.chmod(0o755)
    (root / "checklist.txt").write_text(checklist_text(title, steps, intro))


def load_kit(kit: Path) -> tuple[list[Step], dict[str, str], str]:
    data = json.loads((kit / "steps.json").read_text())
    return (
        [Step.from_json(s) for s in data["steps"]],
        dict(data.get("variables", {})),
        str(data.get("title", "")),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """``kit_runner.py [step id ...]``: run the kit that sits beside this file."""
    kit = Path(__file__).resolve().parent
    steps, variables, _ = load_kit(kit)
    only = list(sys.argv[1:] if argv is None else argv)

    def stop(signum: int, _frame: object) -> None:
        raise SystemExit(128 + signum)

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGHUP, stop)
    return 1 if run_kit(steps, kit, variables=variables, only=only).failed else 0


if __name__ == "__main__":
    sys.exit(main())
