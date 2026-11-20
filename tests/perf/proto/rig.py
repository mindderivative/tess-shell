"""The sandbox the module process test runs the shell in, and the shell's configurations.

Never the user's session: a private headless sway (``tests.sway.PrivateSway``), a private session bus
with the fakes of ``fake_session.py``, a private system bus with the fake NetworkManager and UPower
of ``tests/kwin/fake_hardware.py``, and a fake PulseAudio server (``tests/kwin/fake_pulse_server.py``).
The shell gets exactly those addresses; ``kitlib.refuse_real`` refuses to go on when the environment
it is about to hand over names the real bus or runtime directory. Not collected by pytest.
"""

from __future__ import annotations

import contextlib
import os
import queue
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

REPO = Path(__file__).resolve().parents[3]
MODULES = Path(__file__).resolve().parent / "modules"

HEADER = "---\nTDL: 0.2\nName: Main_Shell\n---\n"
SETTINGS = (
    "---\nTDL: 0.2\nName: S\n---\n"
    "Settings { Appearance { Stylesheets: [Default], Follow_Desktop: false } "
    "KWin { Script: OFF } }\n"
)

# the default shell: the eight modules and the Launcher (a Panel the Applications module serves)
DEFAULT_BAR = (
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


def private_data(root: Path) -> dict[str, str]:
    """The shell's view of the desktop's data, all private: ``HOME``, ``XDG_DATA_HOME`` (with an
    ``applications`` folder of ten made-up desktop entries), ``XDG_CONFIG_HOME`` and ``XDG_DATA_DIRS``,
    a folder of links to everything the real ``XDG_DATA_DIRS`` hold EXCEPT ``applications`` and
    ``icons`` (as ``share_without_applications`` of ``tests/kwin/prepare_m7g_hardware.py``: the graphics
    stack finds its drivers through ``XDG_DATA_DIRS``, ``vulkan/icd.d``). So the Launcher lists only
    the made-up applications and no icon theme is found: the shell falls back to its own icon
    (``mdi:application-outline``) for them, and the tray and task icons its own set. The one file read
    outside is ``/usr/share/pixmaps``, a path the icon lookup hard-codes (system, not the user's)."""
    home, data, config, share = (root / n for n in ("home", "data", "config", "share"))
    apps = data / "applications"
    for folder in (home, config, apps):
        folder.mkdir(parents=True, exist_ok=True)
    for name in APPLICATIONS:
        (apps / f"{name.lower().replace(' ', '-')}.desktop").write_text(
            f"[Desktop Entry]\nType=Application\nName={name}\nExec=true\nComment=made up for the test\n"
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


USER_THREE = {"Pomodoro", "DiskUse", "DeskName"}


def shell_text(extra_bar: str = "", launcher: bool = True) -> str:
    from tess_shell.schema.default_panels import PANELS

    panel = PANELS["Launcher"][1] if launcher else ""
    return (
        HEADER
        + "Shell { Monitor { Name: Main, Index: 0, Children {\n"
        + f"  {panel}\n"
        + "  Bar { Name: Top_Bar, Edge: TOP, Width: EXPAND, Height: 34, Style { Background: "
        + "$color.surface }, Children { FlexBox { Width: EXPAND, Flex: HORIZONTAL, Spacing: 12, "
        + f"Padding: 4, Align_Items: CENTER, Children {{ {DEFAULT_BAR} {extra_bar} }} }} }} }}\n"
        + "} } }\n"
    )


def write_config(root: Path, kind: str, in_process: bool = True) -> Path:
    """``root/cfg``: the shell of ``kind``. ``in_process``: ``Debug { User_Modules_In_Process: true
    }``, the user modules stay in the shell and the posture of the prototype (or posture A) decides
    where they run; false is the product's own posture C (cell ``P`` of ``measure.py``).

    * ``default``: the eight modules and the Launcher;
    * ``plus3``: that and three user modules (Pomodoro, DiskUse, DeskName);
    * ``probe``: that and the latency probe;
    * ``contain``: that, the victim (hang, crash and reload) and a scrolling Marquee_Text as the test
      node whose painting is watched.
    """
    cfg = root / "cfg"
    (cfg / "Shells").mkdir(parents=True)
    (cfg / "settings.tdl").write_text(
        SETTINGS.replace(
            "KWin { Script: OFF } }",
            "KWin { Script: OFF } Debug { User_Modules_In_Process: true } }",
        )
        if in_process
        else SETTINGS
    )
    users: list[str] = []
    extra = ""
    if kind == "plus3":
        users = sorted(USER_THREE)
        extra = "Pomodoro { } DiskUse { } DeskName { }"
    elif kind == "probe":
        users = ["Probe"]
        extra = "Probe { }"
    elif kind == "contain":
        users = ["Victim"]
        extra = (
            'Victim { } Marquee_Text { Text: "a long text that keeps scrolling across its box so '
            'the engine paints it all the time", Width: 200, Speed: 90, Pause: 0, Loop: RESTART }'
        )
    elif kind != "default":
        raise ValueError(f"unknown configuration {kind!r}")
    (cfg / "Shells" / "Main_Shell.tdl").write_text(shell_text(extra))
    for name in users:
        folder = cfg / "Modules" / name
        folder.mkdir(parents=True)
        for suffix in ("py", "tdl"):
            (folder / f"{name}_Module.{suffix}").write_text(
                (MODULES / name / f"{name}_Module.{suffix}").read_text()
            )
    return cfg


# -- the sandbox ---------------------------------------------------------------------------------


@dataclass
class Rig:
    """A private sway and the fakes; :meth:`env` is what a shell started in it gets."""

    sway: PrivateSway = field(default_factory=PrivateSway)
    root: Path = field(default_factory=lambda: Path(tempfile.mkdtemp(prefix="tmp-proc-")))
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
            "session": [sys.executable, "-m", "tests.perf.proto.fake_session"],
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
            **more,
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


# -- a running shell -------------------------------------------------------------------------------


class Shell:
    """``python -m tess_shell run`` (posture A, no probe) or ``tests.perf.proto.run_shell`` as a
    process of its own, with its stderr and its ``NOTIFY_SOCKET`` read by threads. Times are
    ``time.monotonic()`` of this process (``CLOCK_MONOTONIC``, the same clock the shell and its
    children read)."""

    def __init__(
        self,
        rig: Rig,
        cfg: Path,
        *,
        posture: str = "A",
        services: str = "B1",
        wrapper: bool = False,
        probe_out: Path | None = None,
        probe_dir: Path | None = None,
        decisions: Path | None = None,
        watch: float | None = None,
        stall: float | None = None,
        kill: float | None = None,
    ) -> None:
        self.cfg = cfg
        self.lines: list[tuple[float, str]] = []
        self.notified: queue.Queue[tuple[float, str]] = queue.Queue()
        self._notify_path = str(cfg.parent / f"notify-{time.monotonic_ns()}.sock")
        self._notify = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self._notify.bind(self._notify_path)
        more = {"NOTIFY_SOCKET": self._notify_path}
        if probe_dir is not None:
            more["TESS_PROBE_DIR"] = str(probe_dir)
        proto = wrapper or posture != "A" or probe_out is not None
        if proto:
            more["TESS_PROTO_POSTURE"] = posture
            more["TESS_PROTO_SERVICES"] = services
            if probe_out is not None:
                more["TESS_PROTO_PROBE_OUT"] = str(probe_out)
            if decisions is not None:
                more["TESS_PROTO_DECISIONS"] = str(decisions)
            if "TESS_PROTO_LEAN_RULE" in os.environ:  # the lean B's rule (the harness sets it)
                more["TESS_PROTO_LEAN_RULE"] = os.environ["TESS_PROTO_LEAN_RULE"]
            if watch is not None:
                more["TESS_PROTO_WATCH"] = str(watch)
            if stall is not None:
                more["TESS_PROTO_STALL"] = str(stall)
            if kill is not None:
                more["TESS_PROTO_KILL"] = str(kill)
                if posture == "P":  # the product's own times (2 s and 5 s), scaled to the kill time
                    more["TESS_SHELL_TEST_WATCHDOG_SCALE"] = str(kill / 5.0)
        module = "tests.perf.proto.run_shell" if proto else "tess_shell"
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
        threading.Thread(target=self._notifications, daemon=True).start()

    def _pump(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self.lines.append((time.monotonic(), line))

    def _notifications(self) -> None:
        while True:
            try:
                data = self._notify.recv(256)
            except OSError:
                return
            self.notified.put((time.monotonic(), data.decode(errors="replace")))

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
        return "".join(line for _, line in self.lines)

    def find(self, text: str, after: float = 0.0) -> float | None:
        """The time of the first stderr line containing ``text`` after ``after``."""
        for when, line in list(self.lines):
            if when >= after and text in line:
                return when
        return None

    @property
    def pid(self) -> int:
        return self.process.pid

    def stop(self) -> None:
        if self.process.poll() is None:
            with contextlib.suppress(OSError):
                self.process.terminate()  # the shell, which stops its modules; then the group
            try:
                self.process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                with contextlib.suppress(OSError):
                    os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()
        with contextlib.suppress(OSError):
            os.killpg(self.process.pid, signal.SIGKILL)  # whatever else stayed in the group
        self._notify.close()


# -- the process tree ------------------------------------------------------------------------------


def children_map() -> dict[int, list[int]]:
    tree: dict[int, list[int]] = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        try:
            with open(f"/proc/{entry}/stat") as handle:
                fields = handle.read().rsplit(")", 1)[1].split()
        except OSError:
            continue
        tree.setdefault(int(fields[1]), []).append(int(entry))
    return tree


def tree_pids(root: int) -> list[int]:
    """``root`` and every descendant."""
    tree = children_map()
    found = [root]
    for pid in found:
        found.extend(tree.get(pid, ()))
    return found


def child_names(root: int) -> list[str]:
    """The modules of the module processes below ``root`` (the ``--name`` of their command line),
    sorted."""
    names: list[str] = []
    for pid in tree_pids(root):
        try:
            argv = Path(f"/proc/{pid}/cmdline").read_bytes().split(b"\0")
        except OSError:
            continue
        if b"tests.perf.proto.child" in argv and b"--name" in argv:
            names.append(argv[argv.index(b"--name") + 1].decode())
    return sorted(names)


def read_env(pid: int) -> Mapping[str, str]:
    try:
        raw = Path(f"/proc/{pid}/environ").read_bytes()
    except OSError:
        return {}
    return dict(
        item.split("=", 1) for item in raw.decode(errors="replace").split("\0") if "=" in item
    )
