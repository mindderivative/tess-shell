"""A real shell on a private headless sway and a private session bus: the watchdog, the crash
record, safe start and a lost compositor (Crash Recovery and Watchdog, Acceptance criteria).

The watchdog times are scaled by ``TESS_SHELL_TEST_WATCHDOG_SCALE`` (a setting for these tests
only) so that no test waits 10 s for the decision. ``NOTIFY_SOCKET`` is always a datagram socket of
the test, never a real one."""

from __future__ import annotations

import json
import signal
import socket
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

from tess_shell.watchdog import SCALE_VARIABLE
from tests import kitlib
from tests.fake_dbus import HAVE_DAEMON, FakeBus
from tests.shell_samples import BODY, HEADER, write_example
from tests.sway import PrivateSway
from tests.test_notify_live import drain, notify_socket  # noqa: F401  (a fixture)
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed"),
]

TEXT_LINE = 'Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }'
MODULE_TDL = 'Module { Text { Text: "x" } }\n'

# sleeps in a tick callback once the test says go, until the test says stop
HANG_PY = """
import os, time
from pathlib import Path
from tess_shell import Module


class Hang(Module):
    def start(self):
        self.ctx.on_tick("second", self.sleepy)

    def sleepy(self):
        if not Path(os.environ["HANG_GO"]).exists():
            return
        while not Path(os.environ["HANG_STOP"]).exists():
            time.sleep(0.05)
"""

# its file is written when the module's Python is imported: it proves whether the Python ran
RAN_PY = """
import os
from pathlib import Path
from tess_shell import Module

Path(os.environ["RAN_FILE"]).write_text("ran")


class Ran(Module):
    def start(self):
        pass
"""


def write_config(cfg: Path, modules: dict[str, str], in_process: bool = False) -> None:
    """``in_process``: the user modules stay in the shell (``Debug { User_Modules_In_Process }``):
    the shell-wide watchdog watches the loop, and only a module that runs on it can hang it (a
    user module is in a process of its own otherwise: ``tests/test_modproc_failures.py``)."""
    uses = "\n".join(f"{name} {{ }}" for name in modules)
    write_example(cfg, BODY.replace(TEXT_LINE, uses))
    debug = " Debug { User_Modules_In_Process: true }" if in_process else ""
    (cfg / "settings.tdl").write_text(
        f"---\nTDL: 0.2\nName: S\n---\nSettings {{ Logging {{ Level: DEBUG }}{debug} }}\n"
    )
    for name, python in modules.items():
        folder = cfg / "Modules" / name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{name}_Module.tdl").write_text(HEADER.replace("Main_Shell", name) + MODULE_TDL)
        (folder / f"{name}_Module.py").write_text(python)


class Rig:
    """A private sway, a private bus, a config folder and the ways to start shells on them."""

    def __init__(self, sway: PrivateSway, bus: FakeBus, tmp: Path) -> None:
        self.sway, self.bus, self.tmp = sway, bus, tmp
        self.cfg = tmp / "cfg"
        self.state = Path(sway.env["XDG_STATE_HOME"]) / "tesserae-shell"
        self.env = {**sway.env, "DBUS_SESSION_BUS_ADDRESS": bus.address}
        self.shells: list[Shell] = []

    def start(self, **extra: str) -> Shell:
        shell = Shell(self.cfg, {**self.env, **extra})
        self.shells.append(shell)
        shell.wait_for("running")
        return shell

    def command(self, *argv: str, **extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "tess_shell", *argv],
            env={**self.env, **extra},
            capture_output=True,
            text=True,
            timeout=30,
        )

    def kill(self, shell: Shell) -> None:
        shell.process.kill()
        shell.process.wait()


@pytest.fixture
def rig(private_sway: PrivateSway, tmp_path: Path) -> Iterator[Rig]:
    bus = FakeBus()
    made = Rig(private_sway, bus, tmp_path)
    yield made
    for shell in made.shells:
        if shell.process.poll() is None:
            shell.process.kill()
            shell.process.wait()
    bus.close()


# -- a hung module: the stall, the tracebacks, the trigger, the pings ----------------------------


def hang_env(tmp: Path, **extra: str) -> dict[str, str]:
    return {
        "HANG_GO": str(tmp / "go"),
        "HANG_STOP": str(tmp / "stop"),
        SCALE_VARIABLE: "0.25",  # 0.5 s to the warning, 2.5 s to the decision, 1.25 s fresh
        **extra,
    }


def test_a_hung_module_is_named_with_tracebacks_then_systemd_is_asked_and_pings_stop(
    rig: Rig,
    notify_socket: tuple[socket.socket, str],  # noqa: F811
) -> None:
    sock, path = notify_socket
    write_config(rig.cfg, {"Hang": HANG_PY}, in_process=True)
    shell = rig.start(NOTIFY_SOCKET=path, WATCHDOG_USEC="2000000", **hang_env(rig.tmp))
    sock.settimeout(30)
    assert sock.recv(256) == b"READY=1"
    assert sock.recv(256) == b"WATCHDOG=1"  # the loop's first turn
    (rig.tmp / "go").touch()  # the next tick callback sleeps
    shell.wait_for("loop stalled")
    shell.wait_for("asking systemd to restart the shell")
    shell.wait_for("the traceback of every thread")

    warning = next(line for line in shell.seen if "loop stalled" in line)
    assert "module Hang" in warning and "entry point Hang.sleepy" in warning, warning
    assert "WARNING" in warning

    # the trigger arrives, and after it nothing more: the heartbeat is old, so the pings stopped
    received: list[bytes] = []
    while True:
        received.append(sock.recv(256))
        if received[-1] == b"WATCHDOG=trigger":
            break
        assert received[-1] == b"WATCHDOG=1", received
    assert received.count(b"WATCHDOG=trigger") == 1
    assert drain(sock) == []
    sock.settimeout(1.5)
    with pytest.raises(TimeoutError):
        sock.recv(256)

    dump = "".join(shell.seen)
    assert "in sleepy" in dump  # the traceback of the loop thread shows where it is stuck

    # the module lets go: the loop runs again and the pings come back
    (rig.tmp / "stop").touch()
    shell.wait_for("loop is running again")
    sock.settimeout(15)
    assert sock.recv(256) == b"WATCHDOG=1"
    shell.process.send_signal(signal.SIGTERM)
    while (got := sock.recv(256)) != b"STOPPING=1":
        assert got == b"WATCHDOG=1"  # a ping or two while it stops, nothing else
    assert shell.finish() == 0


def test_with_no_watchdog_the_same_hang_is_logged_and_nothing_is_sent(
    rig: Rig,
    notify_socket: tuple[socket.socket, str],  # noqa: F811
) -> None:
    sock, path = notify_socket
    write_config(rig.cfg, {"Hang": HANG_PY}, in_process=True)
    env = {k: v for k, v in rig.env.items() if k != "WATCHDOG_USEC"}
    rig.env = env
    shell = rig.start(NOTIFY_SOCKET=path, **hang_env(rig.tmp))
    sock.settimeout(30)
    assert sock.recv(256) == b"READY=1"
    (rig.tmp / "go").touch()
    shell.wait_for("loop stalled for")
    shell.wait_for("no supervisor can restart it")
    shell.wait_for("the traceback of every thread")
    assert "module Hang" in next(line for line in shell.seen if "loop stalled" in line)
    assert drain(sock) == []  # no ping, no trigger: nothing at all
    (rig.tmp / "stop").touch()
    shell.wait_for("loop is running again")
    shell.process.send_signal(signal.SIGTERM)
    assert sock.recv(256) == b"STOPPING=1"
    assert shell.finish() == 0
    assert drain(sock) == []


# -- the crash record -----------------------------------------------------------------------------


def test_a_sigabrt_leaves_its_tracebacks_in_crash_log_and_the_next_start_keeps_them(
    rig: Rig,
) -> None:
    write_config(rig.cfg, {})
    first = rig.start()
    first.process.send_signal(signal.SIGABRT)  # what systemd's watchdog sends
    assert first.process.wait(timeout=15) == -signal.SIGABRT
    crash = (rig.state / "crash.log").read_text()
    assert "Fatal Python error: Aborted" in crash
    assert "Thread 0x" in crash or "Current thread" in crash  # every thread, not only the main one
    assert (rig.state / "running").exists()  # it did not stop cleanly

    second = rig.start()
    assert (rig.state / "crash.log.1").read_text() == crash  # the previous file is kept
    assert (rig.state / "crash.log").read_text() == ""  # a new one for this run
    second.process.send_signal(signal.SIGTERM)
    assert second.finish() == 0
    assert not (rig.state / "crash.log").exists()  # a clean run leaves none
    assert (rig.state / "crash.log.1").read_text() == crash


def test_after_sigkill_the_next_start_logs_and_counts_it_and_status_shows_the_count(
    rig: Rig,
) -> None:
    write_config(rig.cfg, {})
    shell = rig.start()
    rig.kill(shell)
    assert (rig.state / "running").exists()

    # no shell is running; status still says what the state folder knows
    done = rig.command("status")
    assert done.returncode == 3 and "no shell is running" in done.stderr
    assert "unclean starts since the last clean stop: 1" in done.stderr
    as_json = json.loads(rig.command("--json", "status").stdout)
    assert as_json["exit"] == 3 and as_json["recovery"]["unclean_starts"] == 1

    again = rig.start()
    warning = next(line for line in again.seen if "previous run ended uncleanly" in line)
    assert "WARNING" in warning and "unclean starts since the last clean stop: 1" in warning
    status = json.loads(rig.command("--json", "status").stdout)
    assert status["recovery"]["unclean_starts"] == 1
    assert status["recovery"]["safe_start"] is False
    assert status["recovery"]["last_crash"] is not None
    text = rig.command("status").stdout
    assert "unclean starts since the last clean stop: 1" in text and "last crash: 20" in text

    again.process.send_signal(signal.SIGTERM)
    assert again.finish() == 0
    clean = rig.start()  # a clean stop reset the count
    assert not any("previous run ended uncleanly" in line for line in clean.seen)
    assert json.loads(rig.command("--json", "status").stdout)["recovery"]["unclean_starts"] == 0
    clean.process.send_signal(signal.SIGTERM)
    assert clean.finish() == 0


# -- safe start -----------------------------------------------------------------------------------


def test_three_unclean_starts_in_a_row_start_without_user_modules_and_a_reload_ends_it(
    rig: Rig, tmp_path: Path
) -> None:
    ran = tmp_path / "ran"
    write_config(rig.cfg, {"Ran": RAN_PY})
    env = {"RAN_FILE": str(ran)}

    first = rig.start(**env)
    assert ran.exists()  # the module's Python runs in a normal start
    rig.kill(first)  # unclean 1 will be counted by the next start
    rig.kill(rig.start(**env))  # counts 1
    rig.kill(rig.start(**env))  # counts 2
    ran.unlink()

    safe = rig.start(**env)  # counts 3: three runs ended uncleanly
    assert not ran.exists(), "the user module's Python ran in a safe start"
    warning = next(line for line in safe.seen if "safe start:" in line)
    assert "WARNING" in warning and "Ran (" in warning and "Ran_Module.tdl" in warning
    assert "3 unclean starts" in warning and "untouched" in warning
    status = json.loads(rig.command("--json", "status", **env).stdout)
    assert status["recovery"] == {
        "unclean_starts": 3,
        "last_crash": status["recovery"]["last_crash"],
        "safe_start": True,
        "skipped_modules": ["Ran"],
    }
    assert "safe start: user modules were not loaded (Ran)" in rig.command("status").stdout
    assert (rig.cfg / "Modules" / "Ran" / "Ran_Module.py").read_text() == RAN_PY  # untouched

    # the user fixed the module and asks for a reload: user modules load, the safe start ends
    assert rig.command("reload", **env).returncode == 0
    # the module's process imports it a moment after the reload has answered
    kitlib.wait_until(ran.exists, 15, "the module's Python to run after the reload")
    after = json.loads(rig.command("--json", "status", **env).stdout)
    assert after["recovery"]["safe_start"] is False
    safe.process.send_signal(signal.SIGTERM)
    assert safe.finish() == 0

    ran.unlink()
    normal = rig.start(**env)  # the clean stop reset the count
    assert ran.exists()
    assert not any("safe start" in line for line in normal.seen)
    normal.process.send_signal(signal.SIGTERM)
    assert normal.finish() == 0


# -- a lost compositor --------------------------------------------------------------------------


def test_a_lost_compositor_stops_the_shell_and_exits_with_a_code_that_restarts_it(
    rig: Rig, private_sway: PrivateSway
) -> None:
    write_config(rig.cfg, {})
    shell = rig.start()
    assert private_sway.process is not None
    private_sway.process.kill()  # the compositor goes away
    code = shell.process.wait(timeout=20)
    shell.finish()
    assert code == 69
    unit = (Path(__file__).parents[1] / "src/tess_shell/data/tesserae-shell.service").read_text()
    never_restarted = [
        int(n)
        for line in unit.splitlines()
        if line.startswith("RestartPreventExitStatus=")
        for n in line.split("=", 1)[1].split()
    ]
    assert code not in (0, *never_restarted)  # Restart=on-failure brings the shell back
    assert "the Wayland connection was lost" in shell.stderr
    log = shell.log_text()
    assert "stopping" in log and "stopped" in log  # the modules and the registry were looked after
    assert not (rig.state / "running").exists()  # a controlled exit is not an unclean one
    assert json.loads((rig.state / "recovery.json").read_text())["unclean"] == []
