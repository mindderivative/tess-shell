"""A real shell (a private headless sway, a private session bus) with a user module in a process:
the surfaces do not wait for the module, ``READY=1`` does (without holding the loop), a value the
module sends reaches the screen, and a module that hangs is contained. Nothing touches a session."""

from __future__ import annotations

import datetime
import os
import re
import socket
import subprocess
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.fake_dbus import HAVE_DAEMON, FakeBus
from tests.sway import PrivateSway
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed"),
]

SETTINGS = (
    "---\nTDL: 0.2\nName: S\n---\n"
    "Settings { Appearance { Stylesheets: [Default], Follow_Desktop: false }\n"
    "    KWin { Script: OFF } }\n"
)
SHELL = """---
TDL: 0.2
Shell: 0.1
Name: Main_Shell
---
Shell { Monitor { Name: Main, Index: 0, Children {
    Bar { Name: Top_Bar, Edge: TOP, Width: EXPAND, Height: 34,
          Style { Background: "#101010" },
          Children { FlexBox { Width: EXPAND, Flex: HORIZONTAL, Padding: 4, Children {
              Lag { }
          } } } }
} } }
"""
LAYOUT = """---
TDL: 0.2
Shell: 0.1
Name: Lag
---
Module {
    Rectangle { Width: 80, Height: 24, Fill: <| color |> }
}
"""
STAMP = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3})")


def stamp(line: str) -> float:
    match = STAMP.match(line)
    assert match, line
    return datetime.datetime.fromisoformat(match.group(1)).timestamp()


def config(tmp_path: Path, code: str) -> Path:
    cfg = tmp_path / "cfg"
    (cfg / "Shells").mkdir(parents=True)
    (cfg / "settings.tdl").write_text(SETTINGS)
    (cfg / "Shells" / "Main_Shell.tdl").write_text(SHELL)
    folder = cfg / "Modules" / "Lag"
    folder.mkdir(parents=True)
    (folder / "Lag_Module.tdl").write_text(LAYOUT)
    (folder / "Lag_Module.py").write_text(code)
    folder.chmod(0o700)
    for path in (cfg, cfg / "Modules", folder, folder / "Lag_Module.py"):
        path.chmod(0o700 if path.is_dir() else 0o600)
    return cfg


class Notify:
    """The ``NOTIFY_SOCKET`` of a private service manager: what the shell tells systemd, with the
    time each message came."""

    def __init__(self, root: Path) -> None:
        self.path = str(root / "notify.sock")
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.sock.bind(self.path)
        self.sock.settimeout(0.1)
        self.got: list[tuple[float, str]] = []

    def poll(self) -> None:
        try:
            data = self.sock.recv(4096)
        except TimeoutError:
            return
        self.got.append((time.time(), data.decode()))

    def wait(self, text: str, timeout: float) -> float:
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            self.poll()
            for when, msg in self.got:
                if text in msg:
                    return when
        raise AssertionError(f"never got {text!r}; got {self.got}")

    def close(self) -> None:
        self.sock.close()


class Run:
    def __init__(self, tmp_path: Path, sway: PrivateSway, code: str, **env: str) -> None:
        self.bus = FakeBus()
        self.notify = Notify(tmp_path)
        self.spawned = time.time()
        self.shell = Shell(
            config(tmp_path, code),
            {
                **sway.env,
                "DBUS_SESSION_BUS_ADDRESS": self.bus.address,
                "NOTIFY_SOCKET": self.notify.path,
                **env,
            },
        )
        self.sway = sway

    def stop(self) -> int:
        self.shell.process.terminate()
        return self.shell.finish(timeout=20)

    def close(self) -> None:
        if self.shell.process.poll() is None:
            self.shell.process.kill()
            self.shell.process.wait(10)
        self.bus.close()
        self.notify.close()

    def logged(self, text: str) -> float:
        lines = self.shell.stderr.splitlines(keepends=True)
        for line in lines:
            if text in line and STAMP.match(line):
                return stamp(line)
        raise AssertionError(f"no line with {text!r}:\n" + "".join(lines))

    def grim(self) -> bytes:
        return subprocess.run(
            ["grim", "-t", "ppm", "-"], env=self.sway.env, capture_output=True, check=True
        ).stdout


def count(ppm: bytes, red: int, green: int, blue: int) -> int:
    """The pixels of one colour in a binary PPM (P6)."""
    parts = ppm.split(b"\n", 3)
    assert parts[0] == b"P6"
    body = parts[3]
    pixel = bytes((red, green, blue))
    return sum(1 for i in range(0, len(body) - 2, 3) if body[i : i + 3] == pixel)


@pytest.fixture
def run(private_sway: PrivateSway, tmp_path: Path) -> Iterator[type[Run]]:
    runs: list[Run] = []

    class Made(Run):
        def __init__(self, code: str, **env: str) -> None:
            super().__init__(tmp_path, private_sway, code, **env)
            runs.append(self)

    try:
        yield Made
    finally:
        for r in runs:
            r.close()


SLOW_IMPORT = """
import time
from tess_shell import Module

time.sleep(2.0)

class Lag(Module):
    def start(self):
        self.ctx.send("color", "#ff0000")
"""

RED_DOT = """
from tess_shell import Module

class Lag(Module):
    def start(self):
        self.ctx.send("color", "#ff0000")
"""


def test_the_surfaces_do_not_wait_for_a_slow_module_and_ready_does(run: type[Run]) -> None:
    r = run(SLOW_IMPORT)
    ready = r.notify.wait("READY=1", 20)
    r.shell.wait_for("configured")
    r.shell.wait_for("running")
    assert r.shell.process.poll() is None
    configured, running = r.logged("configured"), r.logged("running")
    assert configured < running - 1.0, "the first surface came while the module was still importing"
    assert ready - r.spawned >= 2.0, "READY=1 waited for the module"
    assert abs(ready - running) < 1.0
    assert r.stop() == 0
    assert "STOPPING=1" in "".join(m for _, m in r.notify.got) or r.notify.poll() is None


def test_a_value_a_user_module_sends_reaches_the_screen(run: type[Run]) -> None:
    r = run(RED_DOT)
    r.notify.wait("READY=1", 20)
    end = time.monotonic() + 15
    seen = 0
    while time.monotonic() < end and not seen:
        seen = count(r.grim(), 255, 0, 0)
        time.sleep(0.2)
    assert seen >= 80 * 24 // 2, f"the module's red rectangle was not drawn ({seen} red pixels)"
    assert r.stop() == 0
    assert "Traceback" not in r.shell.stderr, r.shell.stderr[-1500:]


HANG_IN_START = """
import time
from tess_shell import Module

class Lag(Module):
    def start(self):
        time.sleep(600)
"""


def test_a_module_that_hangs_in_start_neither_holds_ready_forever_nor_stops_the_surfaces(
    run: type[Run],
) -> None:
    r = run(HANG_IN_START, TESS_SHELL_TEST_WATCHDOG_SCALE="0.2")
    ready = r.notify.wait("READY=1", 20)
    assert ready - r.spawned < 10
    r.shell.wait_for("configured")
    r.shell.wait_for("did not return in 1 s; killing the module process")
    r.shell.wait_for("module Lag")
    assert r.shell.process.poll() is None, "the shell runs on"
    assert r.stop() == 0, r.shell.stderr[-2000:]
    assert os.path.exists(r.notify.path)


GREEN_DOT = RED_DOT.replace("#ff0000", "#00ff00")


def test_saving_a_user_modules_python_replaces_its_process_and_the_screen_follows(
    run: type[Run], tmp_path: Path
) -> None:
    r = run(RED_DOT)
    r.notify.wait("READY=1", 20)
    end = time.monotonic() + 15
    while time.monotonic() < end and not count(r.grim(), 255, 0, 0):
        time.sleep(0.2)
    assert count(r.grim(), 255, 0, 0)
    (tmp_path / "cfg" / "Modules" / "Lag" / "Lag_Module.py").write_text(GREEN_DOT)
    end = time.monotonic() + 15
    seen = 0
    while time.monotonic() < end and not seen:
        seen = count(r.grim(), 0, 255, 0)
        time.sleep(0.2)
    assert seen >= 80 * 24 // 2, "the new module's value reached the screen"
    r.shell.wait_for("the code was replaced")
    assert r.stop() == 0
