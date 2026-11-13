"""With the control interface exported and no command, the ``dbus`` thread does not wake (IPC and
CLI > Performance; the instruments and the method are those of ``test_dbus_idle``): the loop
iterations of the service thread, the timeslices the kernel gave it and its voluntary context
switches stay at zero. ``test_idle_wakeups_5_s`` runs with the suite; the 60 second run is marked
``perf`` (``pytest -m perf tests/test_control_idle.py``)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from tess_shell.services.bus import ServiceThread
from tess_shell.services.control import ControlService
from tests.fake_dbus import HAVE_DAEMON, fake_bus
from tests.test_control import Client, FakeCommands, FakeLoop
from tests.test_dbus_idle import ThreadCounters, _native_id, check, read_counters, report

pytestmark = [
    pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed"),
    pytest.mark.skipif(not Path("/proc/self/task").is_dir(), reason="needs /proc"),
]


def measure_idle(
    seconds: float,
) -> tuple[ThreadCounters, ThreadCounters, float, ThreadCounters]:
    """Export the interface, answer a few commands (the traffic is over), let it settle, then count
    what the service thread does for ``seconds`` seconds; and the counters after one deliberate
    wake-up (a control)."""
    with fake_bus() as bus:
        service = ServiceThread(bus.address)
        service.start()
        loop = FakeLoop()
        control = ControlService(service, loop.call_soon, FakeCommands(), "1")
        try:
            assert service.submit(control.start()).result(8)
            control.set_state("running")
            client = Client(bus)
            for _ in range(5):
                client.ok("Status")
            assert client.prop("State") == "running"
            iterations = [0]
            event_loop: Any = service._loop
            original = event_loop._run_once

            def counting() -> None:
                iterations[0] += 1
                original()

            event_loop._run_once = counting
            tid = service.submit(_native_id()).result(5)
            time.sleep(0.5)  # whatever the last reply left behind has run by now
            before = read_counters(tid, iterations)
            started = time.monotonic()
            time.sleep(seconds)
            after = read_counters(tid, iterations)
            window = time.monotonic() - started
            service.post(lambda: None)  # a control: one wake-up, which the counters must see
            time.sleep(0.2)
            return before, after, window, read_counters(tid, iterations)
        finally:
            service.stop()
            loop.close()


def test_idle_wakeups_5_s(capsys: pytest.CaptureFixture[str]) -> None:
    before, after, window, control = measure_idle(5.0)
    with capsys.disabled():
        print("\ncontrol interface " + report(before, after, window))
    check(before, after, control)


@pytest.mark.perf
def test_idle_wakeups_60_s(capsys: pytest.CaptureFixture[str]) -> None:
    before, after, window, control = measure_idle(60.0)
    with capsys.disabled():
        print("\ncontrol interface " + report(before, after, window))
    check(before, after, control)
