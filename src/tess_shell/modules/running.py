"""The running-callback record (Security Model, control 5).

The loop runs one module callback at a time. :class:`CallbackRecord` keeps which one: the module,
the entry point and the monotonic time it started, so a watchdog on another thread can name a
module whose callback does not return (Crash Recovery and Watchdog), and so a callback over its
budget is logged and a module that is over it again and again is named in a warning.

Reading, from any thread (the watchdog's)::

    running = record.running()      # RunningCallback or None: None means no callback is running
    if running is not None:
        age = time.monotonic() - running.started    # seconds it has been running
        print(running.module, running.entry, age)

``running()`` is one attribute read of an immutable tuple, so it needs no lock and never blocks the
loop; what it returns is a consistent snapshot of one moment. Writing is for the loop thread only:
``enter`` and ``leave``, or ``run`` for a call that returns. The cost of a callback is two stores
(the record, and its undoing) and two clock reads; the second read is what the budget needs.
"""

from __future__ import annotations

import time
from collections import Counter, deque
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from typing import Any

from loguru import logger

BUDGET = 0.004  # seconds: a module callback on the loop (Performance Budgets)
WINDOW = 60.0  # seconds
SLOW_MORE_THAN = 100  # callbacks over the budget in WINDOW that earn the warning

_Current = tuple[str, str, float]


@dataclass(frozen=True, slots=True)
class RunningCallback:
    """The callback that is running: ``module`` is the module's name, ``entry`` the entry point (an
    action, ``start``, a tick callback's name, ...) and ``started`` the ``time.monotonic()`` at
    which it began."""

    module: str
    entry: str
    started: float


def entry_name(fn: Callable[..., Any]) -> str:
    """The name a callback is recorded under: its qualified name (``Greeting.tick``), looking
    through ``functools.partial``."""
    while isinstance(fn, partial):
        fn = fn.func
    return getattr(fn, "__qualname__", None) or type(fn).__name__


class CallbackRecord:
    """Which module callback is running on the loop; see the module's docstring.

    ``warn(module, rule, message)`` is told ``slow-module`` once a minute for a module that ran
    more than 100 callbacks over ``budget`` in the last minute. ``periodic`` is called on the
    loop thread at the end of the first callback after each minute: a check that needs no timer of
    its own, and costs no wake-up when nothing runs. ``clock`` is injectable."""

    __slots__ = (
        "_budget",
        "_clock",
        "_current",
        "_last_warned",
        "_next_check",
        "_periodic",
        "_slow",
        "_warn",
    )

    def __init__(
        self,
        warn: Callable[[str, str, str], None],
        *,
        clock: Callable[[], float] = time.monotonic,
        budget: float = BUDGET,
        periodic: Callable[[], None] | None = None,
    ) -> None:
        self._periodic = periodic
        self._next_check = 0.0
        self._warn = warn
        self._clock = clock
        self._budget = budget
        self._current: _Current | None = None
        self._slow: dict[str, deque[tuple[float, str]]] = {}
        self._last_warned: dict[str, float] = {}

    # -- any thread ------------------------------------------------------------------------------

    def running(self) -> RunningCallback | None:
        """The callback that is running now, or ``None``. Safe from any thread."""
        current = self._current
        return None if current is None else RunningCallback(*current)

    # -- the loop thread -------------------------------------------------------------------------

    def enter(self, module: str, entry: str) -> _Current | None:
        """A callback of ``module`` begins. Returns what was running (a callback that calls
        another one), which :meth:`leave` puts back."""
        previous = self._current
        self._current = (module, entry, self._clock())
        return previous

    def leave(self, previous: _Current | None) -> None:
        """The callback that began last has ended; ``previous`` is what :meth:`enter` returned."""
        current = self._current
        self._current = previous
        if current is not None:
            now = self._clock()
            if now - current[2] > self._budget:
                self._over(current[0], current[1], now - current[2], now)
            if now >= self._next_check and previous is None:
                self._next_check = now + WINDOW
                if self._periodic is not None:
                    self._periodic()

    def run(self, module: str, entry: str, fn: Callable[..., Any], *args: Any) -> Any:
        """Call ``fn(*args)`` as a callback of ``module``; an exception goes on to the caller."""
        previous = self.enter(module, entry)
        try:
            return fn(*args)
        finally:
            self.leave(previous)

    def _over(self, module: str, entry: str, took: float, now: float) -> None:
        logger.debug(
            f"module {module}: {entry} took {took * 1000:.1f} ms on the loop "
            f"(budget {self._budget * 1000:.0f} ms)"
        )
        seen = self._slow.get(module)
        if seen is None:
            seen = self._slow[module] = deque(maxlen=SLOW_MORE_THAN + 1)
        seen.append((now, entry))
        if len(seen) <= SLOW_MORE_THAN or now - seen[0][0] > WINDOW:
            return  # not more than 100 over the budget in the last minute
        last = self._last_warned.get(module)
        if last is not None and now - last < WINDOW:
            return
        self._last_warned[module] = now
        worst = Counter(e for _, e in seen).most_common(1)[0][0]
        self._warn(
            module,
            "slow-module",
            f"{module}: more than {SLOW_MORE_THAN} callbacks ran over {self._budget * 1000:.0f} ms "
            f"on the loop in a minute; the entry point most often over it is {worst}",
        )

    def forget(self, module: str) -> None:
        """A module was replaced or removed: its count of slow callbacks starts again."""
        self._slow.pop(module, None)
