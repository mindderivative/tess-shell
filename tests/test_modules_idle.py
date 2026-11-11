"""With a Battery and a Workspaces shown and no signal traffic, the ``dbus`` thread does not wake
(Battery Module and Workspaces Module > Performance Budget; M5 Brief, B3).

Counted as in ``tests/test_dbus_idle.py``: the iterations of the service thread's asyncio loop, the
kernel timeslices of the thread (``schedstat``) and its voluntary context switches. A 5 second run
is in the suite; the 60 seconds of the Brief are marked ``perf``
(``pytest -m perf tests/test_modules_idle.py``)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from tests.fake_dbus import HAVE_DAEMON
from tests.modules_rig import desk, shell
from tests.test_dbus_idle import ThreadCounters, _native_id, check, read_counters, report
from tests.test_workspaces import faces

pytestmark = [
    pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed"),
    pytest.mark.skipif(not Path("/proc/self/task").is_dir(), reason="needs /proc"),
]


def measure(seconds: float) -> tuple[ThreadCounters, ThreadCounters, float, ThreadCounters]:
    with desk() as d:
        battery, _ = d.battery()
        battery.up()
        profiles, _ = d.profiles()
        profiles.up()
        kwin, _, _ = d.kwin(("A", "B", "C"))
        kwin.up()
        with shell(d, "Battery { }\nWorkspaces { }") as w:
            assert d.settle(w, lambda: len(faces(w, w.uses[1])) == 3)
            assert d.settle(w, lambda: w.store.values[w.uses[0]].get("icon") == "battery-80")
            d.settle(w, lambda: False, 0.5)
            iterations = [0]
            loop: Any = d.service._loop
            original = loop._run_once

            def counting() -> None:
                iterations[0] += 1
                original()

            loop._run_once = counting
            tid = d.service.submit(_native_id()).result(5)
            time.sleep(0.5)
            before = read_counters(tid, iterations)
            started = time.monotonic()
            time.sleep(seconds)
            after = read_counters(tid, iterations)
            window = time.monotonic() - started
            d.service.post(lambda: None)  # the control: one wake-up the counters must see
            time.sleep(0.2)
            return before, after, window, read_counters(tid, iterations)


def test_no_wakeups_in_5_s_with_both_modules_shown(capsys: pytest.CaptureFixture[str]) -> None:
    before, after, window, control = measure(5.0)
    with capsys.disabled():
        print("\nBattery + Workspaces " + report(before, after, window))
    check(before, after, control)


@pytest.mark.perf
def test_no_wakeups_in_60_s_with_both_modules_shown(capsys: pytest.CaptureFixture[str]) -> None:
    before, after, window, control = measure(60.0)
    with capsys.disabled():
        print("\nBattery + Workspaces " + report(before, after, window))
    check(before, after, control)
