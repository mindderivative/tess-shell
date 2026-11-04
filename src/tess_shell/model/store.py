"""The value store (TEL Integration > The Value Store).

``ctx.send`` may be called from any thread. The pair is queued; the loop collects the queue once
per turn, keeps the latest value of each key per use (coalescing), checks the type and returns what
changed. Only the loop thread reads or writes ``values``.
"""

from __future__ import annotations

import threading
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from loguru import logger

Wake = Callable[[Callable[[], None]], None]
Listener = Callable[[list["Change"]], None]

_SCALARS = (str, int, float, bool)


@dataclass(frozen=True, slots=True)
class Change:
    use: str
    key: str


def plain(value: object, depth: int = 0) -> bool:
    """Strings, numbers, booleans, and lists and dicts of those (Value Types, M2)."""
    if depth > 8:
        return False
    if isinstance(value, _SCALARS):
        return True
    if isinstance(value, list | tuple):
        return all(plain(v, depth + 1) for v in value)
    if isinstance(value, dict):
        return all(isinstance(k, str) and plain(v, depth + 1) for k, v in value.items())
    return False


def freeze(value: Any) -> Any:
    """A copy the sender cannot change later."""
    if isinstance(value, list | tuple):
        return [freeze(v) for v in value]
    if isinstance(value, dict):
        return {k: freeze(v) for k, v in value.items()}
    return value


@dataclass(slots=True)
class ValueStore:
    """``use`` is the instance key ``<Module>@<uid>``; a send with ``use=None`` reaches every use of
    the sending module."""

    on_change: Listener | None = None
    values: dict[str, dict[str, Any]] = field(default_factory=dict)
    _uses: dict[str, list[str]] = field(default_factory=dict)  # module -> use keys
    _queue: list[tuple[str, str | None, str, Any]] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _wake: Wake | None = None
    _scheduled: bool = False

    def add_use(self, module: str, use: str) -> None:
        self._uses.setdefault(module, []).append(use)
        self.values.setdefault(use, {})

    def remove_use(self, use: str) -> None:
        for uses in self._uses.values():
            if use in uses:
                uses.remove(use)
        self.values.pop(use, None)

    def drop_module(self, module: str) -> None:
        """Forget the values of a module whose instance was replaced (Module Contract)."""
        for use in self._uses.get(module, ()):
            self.values[use] = {}

    def attach_loop(self, wake: Wake) -> None:
        """From now on a send wakes the loop with ``wake(callback)`` (``LoopHandle.call_soon``).
        Before this, sends wait for an explicit :meth:`flush`."""
        with self._lock:
            self._wake = wake
            pending = bool(self._queue)
            self._scheduled = pending
        if pending:
            wake(self._turn)

    def send(self, module: str, use: str | None, key: str, value: object) -> None:
        """Queue one value. Thread-safe; never blocks."""
        if not isinstance(key, str) or not key:
            logger.error(f"module {module}: a send needs a key")
            return
        if not plain(value):
            logger.error(
                f"module {module}: the value for '{key}' is a {type(value).__name__}, "
                "not a string, number, boolean, list or dict; the last value stays"
            )
            return
        frozen = freeze(value)
        with self._lock:
            self._queue.append((module, use, key, frozen))
            wake = self._wake
            if wake is None or self._scheduled:
                return
            self._scheduled = True
        wake(self._turn)

    def _turn(self) -> None:
        changes = self.flush()
        if changes and self.on_change is not None:
            self.on_change(changes)

    def flush(self) -> list[Change]:
        """Loop thread: apply the queue, keeping the latest value per use and key."""
        with self._lock:
            queue, self._queue = self._queue, []
            self._scheduled = False
        before: dict[tuple[str, str], Any] = {}
        missing = object()
        for module, use, key, value in queue:
            targets = [use] if use is not None else list(self._uses.get(module, ()))
            for target in targets:
                if target not in self.values:
                    logger.error(f"module {module}: unknown use {target}")
                    continue
                before.setdefault((target, key), self.values[target].get(key, missing))
                self.values[target][key] = value
        # a value sent and then sent back inside one turn is not a change
        return [
            Change(use, key)
            for (use, key), old in before.items()
            if old is missing or self.values[use][key] != old
        ]

    def snapshot(self, use: str) -> Mapping[str, Any]:
        return self.values.get(use, {})
