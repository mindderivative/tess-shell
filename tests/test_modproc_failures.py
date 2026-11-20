"""What happens when a module process fails: it exits, hangs, floods, misbehaves, or the shell
goes away. Each fault stops only that module, the shell's loop never waits for it, and the module
comes back with the M7a back-off. Real processes; the main thread is the shell's loop."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from loguru import logger

from tess_shell.binder.model import Handler
from tess_shell.logging import finding_sinks
from tess_shell.modules import supervise
from tess_shell.schema.findings import Finding
from tests.modproc_rig import ProcRig, new_rig

REPO = Path(__file__).resolve().parents[1]

HEAD = "import os, time, threading\nfrom tess_shell import Module, action\n"

STEADY = (
    HEAD
    + """
class Steady(Module):
    def start(self):
        self.ctx.send("pid", os.getpid())
        self.ctx.send("mode", "isolated" if __import__("sys").flags.isolated else "open")
        env = os.environ
        self.ctx.send("env", [str(env.get("NOTIFY_SOCKET")), str(env.get("WATCHDOG_USEC"))])
        self.ctx.send("path_has_folder", os.path.dirname(__file__) in __import__("sys").path)
"""
)

# a process whose GIL is held in C code: it cannot read its pipe, so only the kernel can end it
FREEZE = """
    @action
    def freeze(self, event):
        import ctypes
        ctypes.PyDLL(None).sleep(100)
"""

HANGING = (
    HEAD
    + """
class Hg(Module):
    def start(self):
        self.ctx.send("pid", os.getpid())

    @action
    def hang(self, event):
        time.sleep(60)
"""
)


@pytest.fixture(name="rig")
def rig_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[ProcRig]:
    monkeypatch.setattr(supervise, "FIRST_DELAY", 0.02)
    yield from new_rig(tmp_path)


@pytest.fixture
def lines() -> Iterator[list[tuple[str, str, str]]]:
    seen: list[tuple[str, str, str]] = []

    def sink(message: Any) -> None:
        r = message.record
        seen.append((r["level"].name, str(r["extra"].get("source", "")), r["message"]))

    sink_id = logger.add(sink, level="DEBUG")
    try:
        yield seen
    finally:
        logger.remove(sink_id)


@pytest.fixture
def findings() -> Iterator[list[Finding]]:
    seen: list[Finding] = []
    finding_sinks.append(seen.append)
    try:
        yield seen
    finally:
        finding_sinks.remove(seen.append)


def run(rig: ProcRig, name: str, code: str) -> Any:
    loaded, problems = rig.load(name, code)
    assert loaded is not None and problems == [], problems
    assert rig.host.start(loaded) == []
    return loaded


def said(lines: list[tuple[str, str, str]], *parts: str) -> bool:
    return any(all(p in m for p in parts) for _, _, m in lines)


# -- the process ends ---------------------------------------------------------------------------


def test_a_killed_process_fails_only_its_module_keeps_its_values_and_restarts(
    rig: ProcRig, lines: list[tuple[str, str, str]]
) -> None:
    other = run(rig, "Steady", STEADY)
    victim = run(rig, "Hg", HANGING)
    old = rig.wait_value("Hg@u1", "pid")
    rig.wait_value("Steady@u1", "pid")
    os.kill(old, signal.SIGKILL)
    rig.pump(lambda: victim.state == "failed")
    assert other.state == "running", "the other module does not notice"
    assert rig.value("Hg@u1", "pid") == old, "the surfaces keep the last values"
    assert said(lines, "module Hg", f"(pid {old}) ended: exit code -9 (killed by SIGKILL)")
    assert said(lines, "its surfaces keep their last values")
    rig.pump(lambda: rig.value("Hg@u1", "pid") not in (None, old), restarts=True)
    assert rig.host.loaded["Hg"].state == "running"


def test_a_callback_that_hangs_is_named_then_killed_and_the_module_restarts(
    rig: ProcRig, lines: list[tuple[str, str, str]], capfd: pytest.CaptureFixture[str]
) -> None:
    run(rig, "Steady", STEADY)
    run(rig, "Hg", HANGING)
    old = rig.wait_value("Hg@u1", "pid")
    began = time.monotonic()
    rig.host.dispatch(Handler("hang", use="Hg@u1"), "On_Click", None)
    rig.pump(lambda: said(lines, "the callback hang has run for", "stalled"))
    stalled = time.monotonic() - began
    rig.pump(lambda: said(lines, "did not return in 1.2 s; killing the module process"))
    killed = time.monotonic() - began
    assert 0.3 < stalled < killed < 5, (stalled, killed)
    rig.pump(lambda: rig.value("Hg@u1", "pid") not in (None, old), restarts=True)
    assert rig.value("Steady@u1", "pid") is not None
    assert said(lines, "module Hg", "ended: killed: the callback hang did not return")
    err = capfd.readouterr().err
    assert "Hg_Module.py" in err and "in hang" in err, err[-800:]


def test_a_module_that_keeps_failing_stays_failed_after_five_tries_and_a_reload_gives_five_more(
    rig: ProcRig, lines: list[tuple[str, str, str]]
) -> None:
    code = HEAD + "class Bad(Module):\n    def start(self):\n        raise RuntimeError('always')\n"
    loaded = run(rig, "Bad", code)
    rig.pump(lambda: said(lines, "failed again after 5 restarts; it stays failed"), restarts=True)
    assert rig.host.loaded["Bad"].state == "failed"
    assert sum("restarting" in m for _, _, m in lines) == 5
    assert loaded is not rig.host.loaded["Bad"] or loaded.state == "failed"
    rig.host.restarts.reset("Bad")  # what a reload does (``_replace``)
    assert rig.host.restarts.tries("Bad") == 0


def test_a_restart_counts_as_up_only_when_the_module_says_it_started(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lines: list[tuple[str, str, str]]
) -> None:
    """The back-off forgets a restart that ran for a minute. A module whose process starts and then
    fails in ``start()`` has not run: with a clock that jumps 100 s on each reading, a restart
    counted as up when it was only sent would never use up its five tries."""
    monkeypatch.setattr(supervise, "FIRST_DELAY", 0.02)
    ticks = iter(range(0, 10**9, 100))
    rig = ProcRig(tmp_path, clock=lambda: float(next(ticks)))
    try:
        code = HEAD + "class Bad(Module):\n    def start(self):\n        raise RuntimeError('x')\n"
        run(rig, "Bad", code)
        rig.pump(lambda: said(lines, "stays failed"), restarts=True)
    finally:
        rig.close()


def test_a_process_that_cannot_be_started_is_a_finding_and_the_shell_goes_on(
    rig: ProcRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*args: Any, **kw: Any) -> Any:
        raise OSError(12, "Cannot allocate memory")

    monkeypatch.setattr("tess_shell.modproc.supervisor.subprocess.Popen", refuse)
    loaded, problems = rig.load("Steady", STEADY)
    assert loaded is None and [f.rule for f in problems] == ["module-init"]
    assert "Cannot allocate memory" in problems[0].message
    assert not rig.processes.handles, "nothing is left of a start that failed"


GARBAGE = (
    HEAD
    + """
class Gb(Module):
    def start(self):
        self.ctx.send("pid", os.getpid())

    @action
    def spam(self, event):
        import gc
        channel = next(o for o in gc.get_objects() if type(o).__name__ == "Channel")
        channel._sock.sendall(b"not json\\n" * 3)
        time.sleep(30)
"""
)


def test_three_bad_lines_in_a_row_get_the_process_killed(
    rig: ProcRig, lines: list[tuple[str, str, str]]
) -> None:
    loaded = run(rig, "Gb", GARBAGE)
    old = rig.wait_value("Gb@u1", "pid")
    rig.host.dispatch(Handler("spam", use="Gb@u1"), "On_Click", None)
    rig.pump(lambda: loaded.state == "failed")
    assert said(lines, "module Gb", "sent bad lines three times in a row; killed")
    rig.pump(lambda: rig.value("Gb@u1", "pid") not in (None, old), restarts=True)


def test_a_process_that_stops_reading_is_killed_when_the_queue_to_it_is_full(
    rig: ProcRig, lines: list[tuple[str, str, str]]
) -> None:
    loaded = run(rig, "Hg", HANGING)
    rig.wait_value("Hg@u1", "pid")
    handle = loaded.remote
    handle.channel._queue_cap = 200_000  # type: ignore[attr-defined]
    rig.host.dispatch(Handler("hang", use="Hg@u1"), "On_Click", None)
    time.sleep(0.2)
    for _ in range(100):
        handle.send({"t": "level", "level": "INFO", "pad": "p" * 50_000})  # type: ignore[attr-defined]
        if handle.channel.closed:  # type: ignore[attr-defined]
            break
    rig.pump(lambda: loaded.state == "failed")
    assert said(lines, "did not read (hung); killed")


# -- the shell ends -----------------------------------------------------------------------------

ORPHAN = f"""
import pathlib, sys, time
sys.path.insert(0, {str(REPO)!r})
from tess_shell.binder.model import Handler
from tess_shell.modproc.supervisor import Timing
from tests.modproc_rig import ProcRig
CODE = {STEADY + FREEZE!r}
rig = ProcRig(pathlib.Path(sys.argv[1]), Timing(stall=900, kill=1000, poll=1, gate=1000, stop=5))
loaded, _ = rig.load("Steady", CODE)
rig.host.start(loaded)
rig.pump(lambda: rig.value("Steady@u1", "pid") is not None)
if sys.argv[2] == "freeze":
    rig.host.dispatch(Handler("freeze", use="Steady@u1"), "On_Click", None)
    time.sleep(0.5)
print(rig.value("Steady@u1", "pid"), flush=True)
time.sleep(120)
"""


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    try:  # a zombie is gone as far as a module is concerned
        return Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0] != "Z"
    except OSError:
        return False


@pytest.mark.parametrize("how", ["idle", "freeze"])
def test_a_module_process_does_not_outlive_a_shell_that_is_killed(tmp_path: Path, how: str) -> None:
    """An idle process notices the end of its pipe; one that holds the GIL in C code cannot, and
    ``PR_SET_PDEATHSIG`` takes it down."""
    shell = subprocess.Popen(
        [sys.executable, "-c", ORPHAN, str(tmp_path), how], stdout=subprocess.PIPE, text=True
    )
    try:
        assert shell.stdout is not None
        pid = int(shell.stdout.readline())
        assert alive(pid)
        shell.kill()
        shell.wait(10)
        end = time.monotonic() + 5
        while alive(pid) and time.monotonic() < end:
            time.sleep(0.05)
        assert not alive(pid), f"a {how} module process outlived the shell"
    finally:
        shell.kill()


def test_sigterm_does_not_end_a_module_process_the_shells_stop_does(rig: ProcRig) -> None:
    """systemd's stop signals the whole control group; the module's ``stop()`` must still run."""
    loaded = run(rig, "Hg", HANGING)
    pid = rig.wait_value("Hg@u1", "pid")
    for number in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        os.kill(pid, number)
    time.sleep(0.4)
    assert alive(pid) and loaded.state == "running"
    rig.host.stop_all()
    assert not alive(pid)


def test_a_stop_that_does_not_return_is_killed_at_the_stop_time(rig: ProcRig) -> None:
    code = (
        HEAD
        + "class St(Module):\n    def start(self):\n        self.ctx.send('pid', os.getpid())\n"
        + "    def stop(self):\n        time.sleep(60)\n"
    )
    loaded = run(rig, "St", code)
    pid = rig.wait_value("St@u1", "pid")
    began = time.monotonic()
    rig.host.stop_all()
    took = time.monotonic() - began
    assert not alive(pid) and loaded.state == "stopped"
    assert rig.processes.timing.stop <= took < rig.processes.timing.stop + 3, took


# -- what a process may and may not inherit ------------------------------------------------------


def test_a_process_is_isolated_and_has_no_systemd_variables(
    rig: ProcRig, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NOTIFY_SOCKET", "/run/systemd/notify")
    monkeypatch.setenv("WATCHDOG_USEC", "15000000")
    run(rig, "Steady", STEADY)
    assert rig.wait_value("Steady@u1", "mode") == "isolated"
    assert rig.wait_value("Steady@u1", "env") == ["None", "None"]
    assert rig.value("Steady@u1", "path_has_folder") is False, (
        "the module's folder is not on sys.path"
    )


# -- the controls of M7a, in the process ----------------------------------------------------------

SLOW = (
    HEAD
    + """
class Sl(Module):
    @action
    def burn(self, event):
        time.sleep(0.006)
"""
)

THREADS = (
    HEAD
    + """
class Th(Module):
    def start(self):
        self.entered = []
        self.release = threading.Event()
        for _ in range(17):
            threading.Thread(target=self.worker, daemon=True).start()
        end = time.monotonic() + 5
        while len(self.entered) < 17 and time.monotonic() < end:
            time.sleep(0.01)

    def worker(self):
        self.entered.append(1)
        self.release.wait()

    @action
    def tick(self, event):
        pass
"""
)


def test_slow_module_comes_through_with_its_code_and_the_modules_name(
    rig: ProcRig, findings: list[Finding]
) -> None:
    run(rig, "Sl", SLOW)
    for _ in range(105):
        rig.host.dispatch(Handler("burn", use="Sl@u1"), "On_Click", None)
    rig.pump(lambda: any(f.rule == "slow-module" for f in findings))
    (found,) = [f for f in findings if f.rule == "slow-module"]
    assert (
        found.severity == "warning" and "Sl: more than 100 callbacks ran over 4 ms" in found.message
    )
    assert "Sl.burn" in found.message or "burn" in found.message


def test_many_threads_comes_through_once_with_its_code(
    rig: ProcRig, findings: list[Finding], monkeypatch: pytest.MonkeyPatch
) -> None:
    # the check runs at the end of the first callback after a minute: scaled to 0.6 s here
    monkeypatch.setenv("TESS_SHELL_TEST_WATCHDOG_SCALE", "0.01")
    run(rig, "Th", THREADS)
    time.sleep(0.8)
    rig.host.dispatch(Handler("tick", use="Th@u1"), "On_Click", None)
    rig.pump(lambda: any(f.rule == "many-threads" for f in findings))
    (found,) = [f for f in findings if f.rule == "many-threads"]
    assert (
        found.message.startswith("Th: ")
        and "live threads of its own (more than 16)" in found.message
    )


def test_a_module_that_logs_in_a_loop_cannot_flood_the_shells_log(
    rig: ProcRig, lines: list[tuple[str, str, str]]
) -> None:
    code = (
        HEAD
        + """
class Fl(Module):
    @action
    def flood(self, event):
        for i in range(1000):
            self.ctx.log.info(f"line {i}")
        time.sleep(1.1)
        self.ctx.log.info("after")
"""
    )
    run(rig, "Fl", code)
    rig.host.dispatch(Handler("flood", use="Fl@u1"), "On_Click", None)
    rig.pump(lambda: said(lines, "after") and said(lines, "log lines were dropped"))
    got = sum(1 for _, src, m in lines if src == "module:Fl" and m.startswith("line "))
    assert 200 <= got <= 400, got
