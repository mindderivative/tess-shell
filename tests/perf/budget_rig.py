"""The sandbox the budget harness runs the shell in, and the readers of ``/proc`` it uses.

Never the user's session: a private headless sway (``tests.sway.PrivateSway``), a private session
bus with the fakes of ``budget_session.py`` (KWin's virtual desktops, an MPRIS player, a tray), a
private system bus with the fake NetworkManager and UPower of ``tests/kwin/fake_hardware.py`` and a
fake PulseAudio server (``tests/kwin/fake_pulse_server.py``). The shell gets exactly those
addresses and nothing else of this process's environment that names a session;
``kitlib.refuse_real`` refuses to go on when the environment it is about to hand over names the real
bus or runtime directory. Not collected by pytest.
"""

from __future__ import annotations

import contextlib
import os
import platform
import queue
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path

from tests import kitlib
from tests.sway import PrivateSway

REPO = Path(__file__).resolve().parents[2]

HEADER = "---\nTDL: 0.2\nName: Main_Shell\n---\n"
SETTINGS = (
    "---\nTDL: 0.2\nName: S\n---\n"
    "Settings { Appearance { Stylesheets: [Default], Follow_Desktop: false } "
    "KWin { Script: OFF } }\n"
)
BAR_STYLE = "Style { Background: $color.surface }"

# the default shell: the eight modules in one Bar and the Launcher (a Panel the Applications
# module serves); the Clock shows the minute
DEFAULT_MODULES = (
    "Workspaces { } Tasks { show_title: true, max_width: 180 } Spacer { } "
    "Media { show_title: true, show_controls: true } Tray { } Audio { show_percent: true } "
    'Network { } Battery { } Clock { format: "%H:%M" }'
)
APPLICATIONS = (
    "Alacritty Terminal",
    "Blender Modeller",
    "Calculator",
    "Dolphin Files",
    "Firefox Browser",
    "GIMP Image Editor",
    "Kate Text Editor",
    "LibreOffice Writer",
    "Mpv Player",
    "Okular Reader",
)


# -- the machine -----------------------------------------------------------------------------------


def load_average() -> tuple[float, float, float]:
    return os.getloadavg()


def _read(path: str) -> str:
    try:
        return Path(path).read_text().strip()
    except OSError:
        return "?"


def _run(argv: list[str]) -> str:
    try:
        out = subprocess.run(argv, capture_output=True, text=True, timeout=10).stdout
    except OSError, subprocess.SubprocessError:
        return "?"
    return out.strip()


def busiest_processes(count: int = 6) -> list[str]:
    """The processes using the most CPU right now (``ps``: average since each started), so a loaded
    reading can say what was running."""
    out = _run(["ps", "-eo", "pcpu,rss,comm", "--sort=-pcpu"])
    return [" ".join(line.split()) for line in out.splitlines()[1 : count + 1]]


def machine_facts() -> list[tuple[str, str]]:
    """Facts about the machine and the software for the report header."""
    uname = platform.uname()
    cpu = "?"
    for line in _read("/proc/cpuinfo").splitlines():
        if line.startswith("model name"):
            cpu = line.split(":", 1)[1].strip()
            break
    mem = "?"
    for line in _read("/proc/meminfo").splitlines():
        if line.startswith("MemTotal"):
            mem = f"{int(line.split()[1]) / 1048576:.1f} GiB"
            break
    from importlib import metadata

    def version(name: str) -> str:
        try:
            return metadata.version(name)
        except metadata.PackageNotFoundError:
            return "?"

    gil = "with the GIL" if getattr(sys, "_is_gil_enabled", lambda: True)() else "free-threaded"
    sway = _run(["sway", "--version"]) if shutil.which("sway") else "not installed"
    governor = _read("/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor")
    head = _run(["git", "-C", str(REPO), "rev-parse", "--short", "HEAD"])
    dirty = _run(["git", "-C", str(REPO), "status", "--porcelain", "--untracked-files=no"])
    return [
        ("Machine", f"{uname.system} {uname.release} {uname.machine}"),
        ("CPU", f"{cpu}, {os.cpu_count()} threads, governor {governor}"),
        ("Memory", mem),
        ("Python", f"{platform.python_version()} ({gil})"),
        ("tess_re (tesserae-engine)", version("tesserae-engine")),
        ("tess_dl / tess_el", f"{version('tesserae-dl')} / {version('tesserae-el')}"),
        (
            "tess-shell",
            f"{version('tesserae-shell')} at {head}{' plus local changes' if dirty else ''}",
        ),
        ("Compositor", f"private headless sway ({sway}), pixman renderer, no GPU"),
    ]


# -- the sandbox -----------------------------------------------------------------------------------


def private_data(root: Path) -> dict[str, str]:
    """The shell's view of the desktop's data, all private: ``HOME``, ``XDG_DATA_HOME`` (with an
    ``applications`` folder of ten made-up desktop entries), ``XDG_CONFIG_HOME`` and
    ``XDG_DATA_DIRS``: a folder of links to everything the real ``XDG_DATA_DIRS`` hold EXCEPT
    ``applications`` and ``icons`` (the graphics stack finds its drivers through
    ``XDG_DATA_DIRS``, ``vulkan/icd.d``). So the Launcher lists only the made-up applications."""
    home, data, config, share = (root / n for n in ("home", "data", "config", "share"))
    apps = data / "applications"
    for folder in (home, config, apps):
        folder.mkdir(parents=True, exist_ok=True)
    for name in APPLICATIONS:
        (apps / f"{name.lower().replace(' ', '-')}.desktop").write_text(
            f"[Desktop Entry]\nType=Application\nName={name}\nExec=true\nComment=made up\n"
        )
    real = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    share.mkdir(parents=True, exist_ok=True)
    for directory in (Path(d) for d in real.split(":") if d and Path(d).is_dir()):
        for entry in directory.iterdir():
            link = share / entry.name
            if entry.name not in ("applications", "icons") and not link.is_symlink():
                link.symlink_to(entry)
    return {
        "HOME": str(home),
        "XDG_DATA_HOME": str(data),
        "XDG_CONFIG_HOME": str(config),
        "XDG_DATA_DIRS": f"{data}:{share}",
    }


@dataclass
class Rig:
    """A private sway and the fakes; :meth:`env` is what a shell started in it gets."""

    sway: PrivateSway = field(default_factory=PrivateSway)
    root: Path = field(default_factory=lambda: Path(tempfile.mkdtemp(prefix="tmp-budget-")))
    procs: list[subprocess.Popen[bytes]] = field(default_factory=list)
    session_bus: str = ""
    system_bus: str = ""
    pulse: str = ""

    def start(self) -> Rig:
        self.sway.start()
        base = kitlib.scrubbed_environ()
        for name in ("session", "hardware", "pulse"):
            (self.root / name).mkdir()
        specs = {
            "session": [sys.executable, "-m", "tests.perf.budget_session"],
            "hardware": [sys.executable, str(REPO / "tests" / "kwin" / "fake_hardware.py")],
            "pulse": [sys.executable, str(REPO / "tests" / "kwin" / "fake_pulse_server.py")],
        }
        for name, argv in specs.items():
            log = open(self.root / f"{name}.log", "wb")  # noqa: SIM115 - lives as long as the fake
            self.procs.append(
                subprocess.Popen(
                    [*argv, "--root", str(self.root / name)],
                    env=base,
                    cwd=REPO,
                    stdout=log,
                    stderr=log,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                )
            )

        def read(path: Path) -> str:
            kitlib.wait_until(path.exists, 30, f"{path.name} of a fake")
            return path.read_text().strip()

        self.session_bus = read(self.root / "session" / "bus-address")
        self.system_bus = read(self.root / "hardware" / "bus-address")
        self.pulse = "unix:" + read(self.root / "pulse" / "server-socket")
        return self

    def env(self, **more: str) -> dict[str, str]:
        env = {
            **self.sway.env,
            "DBUS_SESSION_BUS_ADDRESS": self.session_bus,
            "DBUS_SYSTEM_BUS_ADDRESS": self.system_bus,
            "PULSE_SERVER": self.pulse,
            **private_data(self.root),
        }
        for name in ("PULSE_RUNTIME_PATH", "PULSE_COOKIE", "PIPEWIRE_REMOTE", "NOTIFY_SOCKET"):
            env.pop(name, None)
        env.update(more)
        kitlib.refuse_real(env, need_bus=True)
        return env

    def stop(self) -> None:
        for proc in self.procs:
            with contextlib.suppress(OSError):
                os.killpg(proc.pid, signal.SIGTERM)
        for proc in self.procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(OSError):
                    os.killpg(proc.pid, signal.SIGKILL)
        self.procs.clear()
        runtime = self.sway.runtime
        self.sway.stop()
        kitlib.kill_strays(runtime)
        kitlib.force_remove(self.root)


@contextlib.contextmanager
def rig() -> Iterator[Rig]:
    r = Rig()
    try:
        yield r.start()
    finally:
        r.stop()


# -- the configurations ----------------------------------------------------------------------------


def shell_text(bar: str, panels: str = "", extra: str = "") -> str:
    """A main shell: one Monitor with a Bar that holds ``bar`` (shell file text), ``panels`` beside
    it and ``extra`` after it."""
    return (
        HEADER
        + "Shell { Monitor { Name: Main, Index: 0, Children {\n"
        + f"  {panels}\n"
        + f"  Bar {{ Name: Top_Bar, Edge: TOP, Width: EXPAND, Height: 34, {BAR_STYLE}, "
        + "Children { FlexBox { Width: EXPAND, Flex: HORIZONTAL, Spacing: 12, Padding: 4, "
        + f"Align_Items: CENTER, Children {{ {bar} }} }} }} }}\n  {extra}\n"
        + "} } }\n"
    )


def launcher_panel() -> str:
    from tess_shell.schema.default_panels import PANELS

    return PANELS["Launcher"][1]


def surfaces_panels(count: int) -> str:
    """``count`` floating, shown Panels, each with a Text (with the Bar: ``count + 1`` surfaces)."""
    return " ".join(
        f"Panel {{ Name: P{n}, Layer: TOP, Width: 120, Height: 40, Visible: true, "
        f'Children {{ Text {{ Text: "panel {n}", Font_Size: 12 }} }} }}'
        for n in range(count)
    )


KINDS = {
    "none": "no Main_Shell: no surface at all",
    "bar": "one Bar with a Clock (minute) and a Text",
    "default": "the eight default modules in one Bar and the Launcher",
    "seconds": "the default shell with the Clock showing seconds",
    "ten": "a shell of 10 surfaces: a Bar and 9 shown Panels",
}


def write_config(root: Path, kind: str, *, folder: str = "cfg") -> Path:
    """``root/<folder>``: the configuration of ``kind`` (see ``KINDS``)."""
    cfg = root / folder
    (cfg / "Shells").mkdir(parents=True)
    (cfg / "settings.tdl").write_text(SETTINGS)
    if kind == "none":
        return cfg
    if kind == "bar":
        text = shell_text(
            'Text { Text: "Tesserae", Font_Size: 14 } Spacer { } Clock { format: "%H:%M" }'
        )
    elif kind == "default":
        text = shell_text(DEFAULT_MODULES, panels=launcher_panel())
    elif kind == "seconds":
        text = shell_text(
            DEFAULT_MODULES.replace('format: "%H:%M"', 'format: "%H:%M:%S"'),
            panels=launcher_panel(),
        )
    elif kind == "ten":
        text = shell_text('Text { Text: "Tesserae", Font_Size: 14 }', panels=surfaces_panels(9))
    else:
        raise ValueError(f"unknown configuration {kind!r}")
    (cfg / "Shells" / "Main_Shell.tdl").write_text(text)
    return cfg


# -- a running shell -------------------------------------------------------------------------------


class Shell:
    """``python -m tess_shell run`` (or ``module``) as a process of its own, with its stderr and its
    ``NOTIFY_SOCKET`` read by threads. Times are ``time.monotonic()`` of this process
    (``CLOCK_MONOTONIC``), taken when a line or a datagram arrives."""

    def __init__(
        self,
        rig: Rig,
        cfg: Path,
        *,
        module: str = "tess_shell",
        env: Mapping[str, str] | None = None,
        notify: bool = True,
    ) -> None:
        self.cfg = cfg
        self.lines: list[tuple[float, str]] = []
        self.notified: queue.Queue[tuple[float, str]] = queue.Queue()
        self.notifications: list[tuple[float, str]] = []
        more = dict(env or {})
        more.setdefault("XDG_STATE_HOME", str(cfg.parent / f"state-{time.monotonic_ns()}"))
        self._notify: socket.socket | None = None
        if notify:
            path = str(cfg.parent / f"notify-{time.monotonic_ns()}.sock")
            self._notify = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            self._notify.bind(path)
            more["NOTIFY_SOCKET"] = path
        self.started = time.monotonic()
        self.process = subprocess.Popen(
            [sys.executable, "-m", module, "run", "--config-dir", str(cfg)],
            env=rig.env(**more),
            cwd=REPO,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
        )
        threading.Thread(target=self._pump, daemon=True).start()
        if self._notify is not None:
            threading.Thread(target=self._notifications, daemon=True).start()

    def _pump(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self.lines.append((time.monotonic(), line))

    def _notifications(self) -> None:
        assert self._notify is not None
        while True:
            try:
                data = self._notify.recv(256)
            except OSError:
                return
            item = (time.monotonic(), data.decode(errors="replace"))
            self.notifications.append(item)
            self.notified.put(item)

    def wait_ready(self, timeout: float = 60.0) -> float:
        """Seconds from the start of the process to ``READY=1``."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                when, text = self.notified.get(timeout=0.2)
            except queue.Empty:
                if self.process.poll() is not None:
                    raise RuntimeError(
                        f"the shell exited early:\n{self.stderr()[-2000:]}"
                    ) from None
                continue
            if "READY=1" in text:
                return when - self.started
        raise TimeoutError(f"no READY=1 in {timeout:g} s:\n{self.stderr()[-2000:]}")

    def stderr(self) -> str:
        return "".join(line for _, line in list(self.lines))

    def find(self, text: str, after: float = 0.0) -> float | None:
        """The time of the first stderr line containing ``text`` at or after ``after``."""
        for when, line in list(self.lines):
            if when >= after and text in line:
                return when
        return None

    def count(self, text: str, after: float = 0.0) -> int:
        return sum(1 for when, line in list(self.lines) if when >= after and text in line)

    def wait_line(self, text: str, timeout: float = 30.0, after: float = 0.0) -> float:
        """The time of the first line containing ``text`` (wait for it)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            found = self.find(text, after)
            if found is not None:
                return found
            if self.process.poll() is not None and self.find(text, after) is None:
                time.sleep(0.2)  # the pump may still hold the last lines
                found = self.find(text, after)
                if found is not None:
                    return found
                raise RuntimeError(f"the shell ended before {text!r}:\n{self.stderr()[-2000:]}")
            time.sleep(0.01)
        raise TimeoutError(f"never saw {text!r} in {timeout:g} s:\n{self.stderr()[-2000:]}")

    @property
    def pid(self) -> int:
        return self.process.pid

    def terminate(self, timeout: float = 15.0) -> tuple[float, int | None]:
        """SIGTERM and wait: the seconds it took and the exit code (None: it had to be killed)."""
        begun = time.monotonic()
        self.process.send_signal(signal.SIGTERM)
        try:
            code: int | None = self.process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            code = None
        took = time.monotonic() - begun
        if code is None:
            self.stop()
        return took, code

    def stop(self) -> None:
        if self.process.poll() is None:
            with contextlib.suppress(OSError):
                self.process.terminate()
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(OSError):
                    os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()
        with contextlib.suppress(OSError):
            os.killpg(self.process.pid, signal.SIGKILL)  # whatever else stayed in the group
        if self._notify is not None:
            self._notify.close()


@contextlib.contextmanager
def running(rig: Rig, cfg: Path, **kwargs: object) -> Iterator[Shell]:
    shell = Shell(rig, cfg, **kwargs)  # type: ignore[arg-type]
    try:
        yield shell
    finally:
        shell.stop()


# -- /proc -----------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ThreadCount:
    name: str
    voluntary: int
    involuntary: int
    ticks: int  # utime + stime of the thread, in clock ticks

    @property
    def switches(self) -> int:
        return self.voluntary + self.involuntary


def thread_counts(pid: int) -> dict[int, ThreadCount]:
    """Every thread of ``pid``: its name, context switches and CPU ticks."""
    found: dict[int, ThreadCount] = {}
    try:
        tasks = list(Path(f"/proc/{pid}/task").iterdir())
    except OSError:
        return found
    for task in tasks:
        try:
            name = (task / "comm").read_text().strip()
            status = (task / "status").read_text().splitlines()
            stat = (task / "stat").read_text().rsplit(")", 1)[1].split()
        except OSError:
            continue  # the thread ended
        voluntary = involuntary = 0
        for line in status:
            if line.startswith("voluntary_ctxt_switches"):
                voluntary = int(line.split()[1])
            elif line.startswith("nonvoluntary_ctxt_switches"):
                involuntary = int(line.split()[1])
        found[int(task.name)] = ThreadCount(
            name, voluntary, involuntary, int(stat[11]) + int(stat[12])
        )
    return found


def cpu_ticks(pid: int) -> int:
    """utime + stime of the whole process (every thread), in clock ticks."""
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return int(fields[11]) + int(fields[12])


CLOCK_TICKS = os.sysconf("SC_CLK_TCK")


def memory_kib(pid: int) -> tuple[int, int]:
    """``(RSS, PSS)`` of a process in KiB (``smaps_rollup``)."""
    rss = pss = 0
    for line in Path(f"/proc/{pid}/smaps_rollup").read_text().splitlines():
        if line.startswith("Rss:"):
            rss = int(line.split()[1])
        elif line.startswith("Pss:"):
            pss = int(line.split()[1])
    return rss, pss


def process_children(pid: int) -> list[int]:
    out: list[int] = []
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            fields = Path(f"/proc/{entry}/stat").read_text().rsplit(")", 1)[1].split()
        except OSError:
            continue
        if int(fields[1]) == pid:
            out.append(int(entry))
    return out
