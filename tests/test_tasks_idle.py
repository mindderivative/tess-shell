"""The Tasks module's idle cost (Tasks Module > Performance Budget): with the script loaded, a row
of windows and no window change, the ``dbus`` thread does not wake and the time source has no
subscriber. Counted as in ``tests/test_dbus_idle.py``: the iterations of the service thread's
asyncio loop, the kernel timeslices of the thread and its voluntary context switches. A 5 second
run is in the suite; the 60 seconds of the spec are marked ``perf`` (``pytest -m perf
tests/test_tasks_idle.py``). Then the cost of a list of 50 windows on the loop."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from tests.fake_dbus import HAVE_DAEMON
from tests.fake_kwin import uuid, window
from tests.tasks_rig import tasks_desk, tasks_shell
from tests.test_dbus_idle import ThreadCounters, _native_id, check, read_counters, report
from tests.test_tasks import ids, start

pytestmark = [
    pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed"),
    pytest.mark.skipif(not Path("/proc/self/task").is_dir(), reason="needs /proc"),
]


def measure(
    tmp_path: Path, seconds: float
) -> tuple[ThreadCounters, ThreadCounters, float, Any, int]:
    with tasks_desk(tmp_path) as t, tasks_shell(t) as w:
        t.fake.script.windows = [window(uuid(n), f"W{n}", output="HDMI-A-1") for n in (1, 2, 3)]
        start(t, w)
        assert t.settle(w, lambda: len(ids(w)) == 3)
        wakes: list[int] = []

        def wake(callback: Any) -> None:
            wakes.append(1)
            t.d.pump.call_soon(callback)

        w.host.ticks.start(wake)  # the real time source, as the app starts it
        try:
            t.settle(w, lambda: False, 0.5)
            iterations = [0]
            loop: Any = t.d.service._loop
            original = loop._run_once

            def counting() -> None:
                iterations[0] += 1
                original()

            loop._run_once = counting
            tid = t.d.service.submit(_native_id()).result(5)
            time.sleep(0.5)
            before = read_counters(tid, iterations)
            wakes.clear()
            started = time.monotonic()
            time.sleep(seconds)
            after = read_counters(tid, iterations)
            window_s = time.monotonic() - started
            ticks = len(wakes)
            t.d.service.post(lambda: None)  # the control: one wake-up the counters must see
            time.sleep(0.2)
            return before, after, window_s, read_counters(tid, iterations), ticks
        finally:
            w.host.ticks.close()


def test_no_wakeups_in_5_s_with_the_script_loaded_and_no_window_change(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before, after, window_s, control, ticks = measure(tmp_path, 5.0)
    with capsys.disabled():
        print("\nTasks " + report(before, after, window_s) + f", time source {ticks}")
    check(before, after, control)
    assert ticks == 0  # no timer: the time source had nobody to wake for


@pytest.mark.perf
def test_wakeups_in_60_s(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    before, after, window_s, control, ticks = measure(tmp_path, 60.0)
    with capsys.disabled():
        print("\nTasks " + report(before, after, window_s) + f", time source {ticks}")
    check(before, after, control)
    assert ticks == 0


def test_a_list_of_50_windows_reaches_the_row_in_well_under_16_ms_of_the_shells_work(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Tasks Module > Performance Budget: a ``WindowsState`` of 50 windows to the row updated under
    16 ms of the shell's work: the parse and the filter and send of the module, not the drawing."""
    import json

    from tess_shell.services.kwin import parse_windows

    raw = json.dumps(
        [
            window(uuid(n), f"Window title number {n}", f"org.example.app{n % 7}", output="DP-1")
            for n in range(1, 51)
        ]
    )
    started = time.perf_counter()
    for _ in range(20):
        parsed = parse_windows(raw)
    parse_ms = (time.perf_counter() - started) / 20 * 1000
    assert parsed is not None and len(parsed) == 50
    with tasks_desk(tmp_path) as t, tasks_shell(t) as w:
        start(t, w)
        tasks = w.host.loaded["Tasks"].instance
        use = next(iter(w.host.loaded["Tasks"].ctx.uses.values()))
        for window_info in parsed:
            tasks.icon(window_info.app, 18)  # the icons were read before: the budget is the row's
        t.settle(w, lambda: False, 0.5)
        started = time.perf_counter()
        for _ in range(20):
            tasks.rows(use, parsed)
        rows_ms = (time.perf_counter() - started) / 20 * 1000
    with capsys.disabled():
        print(f"\n50 windows: parse {parse_ms:.2f} ms, the row's records {rows_ms:.2f} ms")
    assert parse_ms + rows_ms < 16
