"""The Tray's idle cost (Tray Module > Performance Budget; M5 Brief, D2): with no watcher, and with
a watcher and items and no signal traffic, the ``dbus`` thread does not wake and the time source has
no subscriber (no wake-up at all). Counted as in ``tests/test_dbus_idle.py``: the iterations of the
service thread's asyncio loop, the kernel timeslices of the thread (``schedstat``) and its voluntary
context switches. A 5 second run is in the suite; the 60 seconds of the Brief are marked ``perf``
(``pytest -m perf tests/test_tray_idle.py``). Then the cost of each signal: the module's own
callback on the ``dbus`` thread, p50 and p99."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from tests.fake_dbus import HAVE_DAEMON
from tests.test_dbus_idle import ThreadCounters, _native_id, check, read_counters, report
from tests.test_tray_module import ids, settle, up, values
from tests.tray_rig import tray_desk, tray_shell

pytestmark = [
    pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed"),
    pytest.mark.skipif(not Path("/proc/self/task").is_dir(), reason="needs /proc"),
]

ABSENT, ITEMS = "no watcher", "items"


def measure(
    tmp_path: Path, scenario: str, seconds: float
) -> tuple[ThreadCounters, ThreadCounters, float, ThreadCounters, int]:
    with tray_desk(tmp_path, watcher_up=scenario != ABSENT) as t:
        if scenario == ITEMS:
            up(t, t.item("1-1"), t.item("2-1"))
        with tray_shell(t) as w:
            wakes: list[int] = []

            def wake(callback: Any) -> None:
                wakes.append(1)
                t.d.pump.call_soon(callback)

            w.host.ticks.start(wake)  # the real time source, as the app starts it
            try:
                if scenario == ITEMS:
                    assert settle(t, w, lambda: len(ids(w)) == 2)
                else:
                    assert settle(t, w, lambda: values(w).get("available") is False)
                settle(t, w, lambda: False, 0.5)
                wakes.clear()
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
                window = time.monotonic() - started
                ticks = len(wakes)
                t.d.service.post(lambda: None)  # the control: one wake-up the counters must see
                time.sleep(0.2)
                return before, after, window, read_counters(tid, iterations), ticks
            finally:
                w.host.ticks.close()


@pytest.mark.parametrize("scenario", [ABSENT, ITEMS])
def test_no_wakeups_in_5_s_with_no_watcher_or_with_items_and_no_traffic(
    scenario: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before, after, window, control, ticks = measure(tmp_path, scenario, 5.0)
    with capsys.disabled():
        print(f"\nTray {scenario} " + report(before, after, window) + f", time source {ticks}")
    check(before, after, control)
    assert ticks == 0  # no timer: the time source had nobody to wake for


@pytest.mark.perf
@pytest.mark.parametrize("scenario", [ABSENT, ITEMS])
def test_wakeups_in_60_s(scenario: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    before, after, window, control, ticks = measure(tmp_path, scenario, 60.0)
    with capsys.disabled():
        print(f"\nTray {scenario} " + report(before, after, window) + f", time source {ticks}")
    check(before, after, control)
    assert ticks == 0


def test_the_callback_of_each_signal_costs_well_under_a_millisecond(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with tray_desk(tmp_path) as t:
        item = t.item(menu=None)
        up(t, item)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: len(ids(w)) == 1)
            for i in range(30):
                item.changed("NewTitle", Title=f"Title {i}")
                assert settle(t, w, lambda i=i: values(w)["items"][0]["title"] == f"Title {i}")
            for i in range(30):
                item.changed("NewToolTip", ToolTip=("", [], f"T{i}", f"text {i}"))
                assert settle(
                    t, w, lambda i=i: values(w)["items"][0]["tooltip_text"] == f"text {i}"
                )
            count, p50, p99, worst = t.d.layer.callback_summary("Tray")
            with capsys.disabled():
                print(
                    f"\nTray callbacks on the dbus thread: n={count} p50={p50 * 1e6:.0f} us "
                    f"p99={p99 * 1e6:.0f} us max={worst * 1e6:.0f} us"
                )
            assert count >= 60  # each signal is one callback of the module's own
            assert p50 < 0.001 and p99 < 0.005, (p50, p99, worst)
