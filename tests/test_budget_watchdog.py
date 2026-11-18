"""The heartbeat and the watchdog thread cost about two wake-ups a second (Crash Recovery and
Watchdog > Performance budget: "one timer at most once a second and one store; the watchdog thread
wakes once a second"; the idle budget of the whole shell is 5 a second, Performance Budgets).

Counted on the real :class:`Watchdog` thread with its default times: how many times it queues a
beat on the loop in 4.5 s, how many times the kernel switched the thread (voluntary context
switches, ``/proc``), and, under a supervisor, how many ``WATCHDOG=1`` datagrams it sent. A
heartbeat that runs ten times as often (a ``tick`` of 0.1 s) or a ping at every look shows at once.
The limits are the design's rates with a margin of one beat. The test takes 4.5 s.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from tess_shell.watchdog import Heartbeat, Watchdog

pytestmark = pytest.mark.skipif(not Path("/proc/self/task").is_dir(), reason="needs /proc")

WINDOW = 4.5  # seconds: four to five looks at one a second


def voluntary_switches(watchdog: Watchdog) -> int:
    assert watchdog._thread is not None
    task = Path(f"/proc/{os.getpid()}/task/{watchdog._thread.native_id}/status")
    for line in task.read_text().splitlines():
        if line.startswith("voluntary_ctxt_switches"):
            return int(line.split()[1])
    raise AssertionError("no voluntary_ctxt_switches in " + str(task))


class Loop:
    """A stand-in for ``LoopHandle.call_soon`` that runs the beat at once and counts."""

    def __init__(self) -> None:
        self.queued = 0

    def call_soon(self, fn: Callable[[], None]) -> None:
        self.queued += 1
        fn()


def test_budgets_watchdog_one_beat_and_one_look_a_second_and_a_ping_every_half_interval() -> None:
    loop = Loop()
    plain = Watchdog(Heartbeat(), lambda: None, loop.call_soon)
    sent: list[str] = []
    supervised = Watchdog(
        Heartbeat(),
        lambda: None,
        Loop().call_soon,
        interval=15.0,
        supervised=True,
        send=lambda state: sent.append(state),
    )
    plain.start()
    supervised.start()
    try:
        before = voluntary_switches(plain)
        time.sleep(WINDOW)
        switches = voluntary_switches(plain) - before
    finally:
        plain.stop()
        supervised.stop()
    # one beat queued per look, the first look at 1 s: four or five in 4.5 s, never ten
    assert 3 <= loop.queued - 1 <= 6, loop.queued  # begin() beats once without queueing
    # the thread wakes at its look and nowhere else
    assert switches <= 7, switches
    # systemd's pace is WatchdogSec / 2 = 7.5 s: the first ping at the start, no second in 4.5 s
    assert sent == ["WATCHDOG=1"], sent
