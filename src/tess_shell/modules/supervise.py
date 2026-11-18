"""Faults are per module (Security Model, control 6): when a failed module may be started again, and
which threads are a module's own.

Standard library only; no clock and no timer of its own: the host passes the clock and drives
:meth:`Restarts.due` from the shared time source while a restart is waiting.
"""

from __future__ import annotations

import sys
import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

FIRST_DELAY = 1.0  # seconds before the first restart; each next one waits twice as long
MAX_DELAY = 60.0
MAX_TRIES = 5  # restarts of one failure run; then the module stays failed until a reload
STABLE_AFTER = 60.0  # a restart that has run this long without failing starts the count again
MANY_THREADS = 16  # more live threads than this gives the warning ``many-threads``


def delay_before(attempt: int) -> float:
    """Seconds to wait before restart number ``attempt`` (1 for the first): 1, 2, 4, ... at most
    60."""
    return min(MAX_DELAY, FIRST_DELAY * 2.0 ** (attempt - 1))


@dataclass(slots=True)
class _Retry:
    tries: int = 0  # restarts started in this run of failures
    due: float | None = None  # when the next one may start; None when none is waiting
    ok_since: float | None = None  # when the last restart came up running


class Restarts:
    """The back-off of every failed module. ``clock`` is injectable (monotonic seconds)."""

    def __init__(self, clock: Callable[[], float]) -> None:
        self._clock = clock
        self._by_module: dict[str, _Retry] = {}

    def failed(self, module: str) -> float | None:
        """``module`` failed now. Returns the seconds until its next restart, or ``None`` when the
        tries are used up and it stays failed until a reload."""
        now = self._clock()
        retry = self._by_module.setdefault(module, _Retry())
        if retry.ok_since is not None and now - retry.ok_since >= STABLE_AFTER:
            retry.tries = 0  # it ran well for a minute: this is a new failure
        retry.ok_since = None
        if retry.tries >= MAX_TRIES:
            retry.due = None
            return None
        retry.tries += 1
        wait = delay_before(retry.tries)
        retry.due = now + wait
        return wait

    def started(self, module: str) -> None:
        """A restart of ``module`` is running."""
        retry = self._by_module.get(module)
        if retry is not None:
            retry.due = None
            retry.ok_since = self._clock()

    def tries(self, module: str) -> int:
        retry = self._by_module.get(module)
        return 0 if retry is None else retry.tries

    def due(self) -> list[str]:
        """The modules whose restart may begin now; each is handed out once."""
        now = self._clock()
        out = [m for m, r in self._by_module.items() if r.due is not None and r.due <= now]
        for module in out:
            self._by_module[module].due = None
        return out

    def waiting(self) -> bool:
        """Is any restart waiting for its time?"""
        return any(r.due is not None for r in self._by_module.values())

    def reset(self, module: str) -> None:
        """A reload (or the end of the module): the count starts again and nothing waits."""
        self._by_module.pop(module, None)

    def clear(self) -> None:
        self._by_module.clear()


def thread_counts(own: Mapping[str, tuple[Path, bool]]) -> dict[str, int]:
    """The live threads each module owns now. A thread is a module's when a frame of its stack
    runs code from the module's Python file, or from a file of its own folder when that folder is
    the module's (``Modules/<Name>/``, the ``bool``): that is what a thread a module started and
    that is still in the module's code looks like, whatever it was started with. A thread that
    runs the shell's or the standard library's code only (a pool worker waiting for work, the
    shell's own threads) belongs to no module. ``own`` maps a module's name to its Python file and
    whether its folder is its own."""
    files = {str(py): name for name, (py, _) in own.items()}
    folders = [(str(py.parent) + "/", name) for name, (py, dedicated) in own.items() if dedicated]
    me = threading.get_ident()
    counts: dict[str, int] = {}
    for ident, frame in sys._current_frames().items():
        if ident == me:
            continue
        found: str | None = None
        current = frame
        while current is not None:  # from the innermost frame out; the outermost match wins
            filename = current.f_code.co_filename
            name = files.get(filename)
            if name is None:
                name = next((n for prefix, n in folders if filename.startswith(prefix)), None)
            if name is not None:
                found = name
            current = current.f_back  # type: ignore[assignment]
        if found is not None:
            counts[found] = counts.get(found, 0) + 1
    return counts
