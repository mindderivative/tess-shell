"""The Media module's idle cost (Media Module > Performance Budget; M5 Brief, D2): with no player,
with a paused player, and with a playing one that nobody shows the position of, the ``dbus`` thread
does not wake and the time source has no subscriber (no wake-up at all); with a playing player and a
position shown there is exactly one wake-up a second on the loop side and still none on the
``dbus`` thread.

Counted as in ``tests/test_dbus_idle.py``: the iterations of the service thread's asyncio loop, the
kernel timeslices of the thread (``schedstat``) and its voluntary context switches; the time
source's wake-ups through the ``wake`` function it is started with. A 5 second run is in the suite;
the 60 seconds of the Brief are marked ``perf`` (``pytest -m perf tests/test_media_idle.py``)."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pytest

from tests.fake_dbus import HAVE_DAEMON
from tests.modules_rig import desk, shell
from tests.test_dbus_idle import ThreadCounters, _native_id, check, read_counters, report

pytestmark = [
    pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed"),
    pytest.mark.skipif(not Path("/proc/self/task").is_dir(), reason="needs /proc"),
]

ABSENT, PAUSED, PLAYING_HIDDEN, PLAYING_SHOWN = "absent", "paused", "playing", "playing+position"


def measure(
    scenario: str, seconds: float
) -> tuple[ThreadCounters, ThreadCounters, float, ThreadCounters, int]:
    with desk() as d:
        if scenario != ABSENT:
            player = d.player("vlc", status="Paused" if scenario == PAUSED else "Playing")
            player.up()
        uses = "Media { show_position: true }" if scenario != PLAYING_HIDDEN else "Media { }"
        with shell(d, uses) as w:
            wakes: list[int] = []

            def wake(callback: Any) -> None:
                wakes.append(1)
                d.pump.call_soon(callback)

            w.host.ticks.start(wake)  # the real time source, as the app starts it
            try:
                media = [u for u in w.uses if u.startswith("Media@")][0]
                want = "available" if scenario == ABSENT else "status"
                assert d.settle(w, lambda: w.store.values[media].get(want) not in (None, False))
                d.settle(w, lambda: False, 0.5)
                wakes.clear()
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
                wakes.clear()
                started = time.monotonic()
                time.sleep(seconds)
                after = read_counters(tid, iterations)
                window = time.monotonic() - started
                ticks = len(wakes)
                d.service.post(lambda: None)  # the control: one wake-up the counters must see
                time.sleep(0.2)
                return before, after, window, read_counters(tid, iterations), ticks
            finally:
                w.host.ticks.close()


@pytest.mark.parametrize("scenario", [ABSENT, PAUSED, PLAYING_HIDDEN])
def test_no_wakeups_in_5_s_with_no_player_a_paused_one_or_a_playing_one_unshown(
    scenario: str, capsys: pytest.CaptureFixture[str]
) -> None:
    before, after, window, control, ticks = measure(scenario, 5.0)
    with capsys.disabled():
        print(f"\nMedia {scenario} " + report(before, after, window) + f", time source {ticks}")
    check(before, after, control)
    assert ticks == 0  # no timer: the time source had nobody to wake for


def test_one_wakeup_a_second_while_playing_with_the_position_shown(
    capsys: pytest.CaptureFixture[str],
) -> None:
    before, after, window, control, ticks = measure(PLAYING_SHOWN, 5.0)
    with capsys.disabled():
        print(
            "\nMedia playing+position " + report(before, after, window) + f", time source {ticks}"
        )
    check(before, after, control)  # the dbus thread still sleeps
    assert 4 <= ticks <= 6, ticks  # one a second for 5 s


@pytest.mark.perf
@pytest.mark.parametrize("scenario", [ABSENT, PAUSED, PLAYING_HIDDEN, PLAYING_SHOWN])
def test_wakeups_in_60_s(scenario: str, capsys: pytest.CaptureFixture[str]) -> None:
    before, after, window, control, ticks = measure(scenario, 60.0)
    with capsys.disabled():
        print(f"\nMedia {scenario} " + report(before, after, window) + f", time source {ticks}")
    check(before, after, control)
    if scenario == PLAYING_SHOWN:
        assert 58 <= ticks <= 62, ticks
    else:
        assert ticks == 0
