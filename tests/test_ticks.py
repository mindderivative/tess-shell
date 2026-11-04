"""The shared time source: boundaries from the wall clock, wake-ups only at ticks."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator

import pytest

from tess_shell.modules.ticks import TimeSource, next_boundary


def test_boundaries_are_whole_seconds_and_minutes_after_now() -> None:
    assert next_boundary("second", 100.2) == 101.0
    assert next_boundary("second", 101.0) == 102.0  # a boundary is the next one, not this one
    assert next_boundary("minute", 100.2) == 120.0
    assert next_boundary("minute", 120.0) == 180.0


class Fake:
    """A source with a clock the test moves, and a loop that runs callbacks at once."""

    def __init__(self, now: float) -> None:
        self.now = now
        self.source = TimeSource(clock=lambda: self.now)
        self.ran: list[str] = []
        self.event = threading.Event()
        self.source.start(lambda callback: callback())
        time.sleep(0.1)  # let the thread read its first boundary from the clock at `now`

    def sub(self, unit: str) -> None:
        def fire() -> None:
            self.ran.append(unit)
            self.event.set()

        self.source.subscribe(unit, fire)
        time.sleep(0.1)  # the thread takes its first boundary from the clock as it is now

    def move(self, now: float) -> None:
        self.now = now
        with self.source._cond:
            self.source._cond.notify_all()

    def wait(self, timeout: float = 3.0) -> bool:
        ok = self.event.wait(timeout)
        self.event.clear()
        return ok

    def close(self) -> None:
        self.source.close()


@pytest.fixture
def fake() -> Iterator[Fake]:
    f = Fake(100.5)
    yield f
    f.close()


def test_a_minute_subscriber_is_not_woken_by_the_next_second(fake: Fake) -> None:
    fake.sub("minute")
    fake.move(101.2)
    assert not fake.wait(0.3) and fake.ran == []
    fake.move(120.01)
    assert fake.wait() and fake.ran == ["minute"]


def test_a_second_subscriber_ticks_each_second_and_only_its_unit(fake: Fake) -> None:
    fake.sub("second")
    fake.move(101.01)
    assert fake.wait() and fake.ran == ["second"]
    fake.move(101.5)
    assert not fake.wait(0.3)
    fake.move(102.01)
    assert fake.wait() and fake.ran == ["second", "second"]


def test_both_units_due_at_the_minute_start(fake: Fake) -> None:
    fake.sub("second")
    fake.sub("minute")
    fake.move(120.01)
    assert fake.wait()
    time.sleep(0.1)
    assert sorted(fake.ran) == ["minute", "second"]


def test_a_clock_moved_back_does_not_leave_the_next_tick_hours_away(fake: Fake) -> None:
    fake.sub("second")
    fake.move(100_000.0)
    fake.wait(0.5)
    fake.ran.clear()
    fake.move(50.0)  # a day backwards
    time.sleep(0.1)  # the thread takes its next boundary from the new time
    fake.move(51.01)
    assert fake.wait() and fake.ran == ["second"]


def test_a_cancelled_subscription_stops_ticking(fake: Fake) -> None:
    calls: list[int] = []
    sub = fake.source.subscribe("second", lambda: calls.append(1))
    sub.cancel()
    fake.move(101.1)
    time.sleep(0.3)
    assert calls == []


def test_with_no_subscriber_the_thread_is_asleep(fake: Fake) -> None:
    fake.move(500.0)
    time.sleep(0.3)
    assert fake.ran == []


def test_an_unknown_unit_is_refused() -> None:
    with pytest.raises(ValueError, match="second"):
        TimeSource().subscribe("hour", lambda: None)


def test_with_the_real_clock_a_second_tick_lands_just_after_the_second() -> None:
    stamps: list[float] = []
    done = threading.Event()

    def fire() -> None:
        stamps.append(time.time())
        if len(stamps) == 3:
            done.set()

    source = TimeSource()
    source.subscribe("second", fire)
    source.start(lambda callback: callback())
    try:
        assert done.wait(5)
    finally:
        source.close()
    assert all(0.0 <= s % 1 < 0.15 for s in stamps), stamps
    assert 0.9 < stamps[1] - stamps[0] < 1.1 and 0.9 < stamps[2] - stamps[1] < 1.1
