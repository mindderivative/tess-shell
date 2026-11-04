"""The shared time source (Module Context > A shared time source): one thread, woken only at the
start of a second or a minute that someone subscribed to.

Boundaries come from the wall clock each time, so a pause, a resume or a manual time change
corrects itself within one tick and nothing drifts. With no second subscriber the thread sleeps
until the next minute; with none at all it sleeps until woken.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field

from loguru import logger

UNITS = ("second", "minute")
_SLACK = 0.005  # wake just after the boundary, so the clock reads the new second


@dataclass(slots=True)
class Subscription:
    unit: str
    fn: Callable[[], None]
    _source: TimeSource
    active: bool = True

    def cancel(self) -> None:
        self._source._cancel(self)


def next_boundary(unit: str, now: float) -> float:
    step = 1.0 if unit == "second" else 60.0
    return (now // step + 1) * step


@dataclass(slots=True)
class TimeSource:
    clock: Callable[[], float] = time.time
    _subs: list[Subscription] = field(default_factory=list)
    _cond: threading.Condition = field(default_factory=threading.Condition)
    _wake: Callable[[Callable[[], None]], None] | None = None
    _thread: threading.Thread | None = None
    _closed: bool = False

    def subscribe(self, unit: str, fn: Callable[[], None]) -> Subscription:
        if unit not in UNITS:
            raise ValueError(f"a tick unit is 'second' or 'minute', not {unit!r}")
        sub = Subscription(unit, fn, self)
        with self._cond:
            self._subs.append(sub)
            self._cond.notify_all()
        return sub

    def _cancel(self, sub: Subscription) -> None:
        with self._cond:
            sub.active = False
            if sub in self._subs:
                self._subs.remove(sub)
            self._cond.notify_all()

    def start(self, wake: Callable[[Callable[[], None]], None]) -> None:
        """Begin ticking; ``wake(callback)`` runs ``callback`` on the loop (``call_soon``)."""
        self._wake = wake
        self._thread = threading.Thread(target=self._run, name="time-source", daemon=True)
        self._thread.start()

    def close(self) -> None:
        with self._cond:
            self._closed = True
            self._cond.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=2)

    def _due(self, now: float, last: dict[str, float]) -> list[str]:
        return [u for u in UNITS if now >= last[u] and any(s.unit == u for s in self._subs)]

    def _run(self) -> None:
        wake = self._wake
        assert wake is not None
        target = {u: next_boundary(u, self.clock()) for u in UNITS}
        while True:
            with self._cond:
                while not self._closed:
                    now = self.clock()
                    # a clock moved back leaves a boundary far ahead: take the next one from now
                    for unit in UNITS:
                        if target[unit] - now > (1.0 if unit == "second" else 60.0) + 1:
                            target[unit] = next_boundary(unit, now)
                    units = {s.unit for s in self._subs}
                    if not units:
                        self._cond.wait()
                        target = {u: next_boundary(u, self.clock()) for u in UNITS}
                        continue
                    if any(now >= target[u] for u in units):
                        break
                    # never sleep past a boundary a changed clock could have moved
                    until = min(target[u] for u in units) - now + _SLACK
                    self._cond.wait(timeout=max(0.0, min(until, 60.0)))
                if self._closed:
                    return
                now = self.clock()
                due = self._due(now, target)
                for unit in due:
                    target[unit] = next_boundary(unit, now)
                callbacks = [s.fn for s in self._subs if s.unit in due]
            if callbacks:
                wake(lambda cbs=tuple(callbacks): self._dispatch(cbs))  # type: ignore[misc]

    @staticmethod
    def _dispatch(callbacks: tuple[Callable[[], None], ...]) -> None:
        for fn in callbacks:
            try:
                fn()
            except Exception:
                logger.opt(exception=True).error("a tick callback raised")
