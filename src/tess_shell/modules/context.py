"""The context (``self.ctx``): a module's whole view of the shell (Module Context).

M2 offers ``name``, ``uid``, ``config``, ``log``, ``uses``, ``send`` and ``on_tick``; the rest of
the member list waits for a module that needs it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from loguru import logger

from tess_shell.modules.ticks import Subscription, TimeSource


@dataclass(frozen=True, slots=True)
class UseRecord:
    """A place where the module is used."""

    key: str  # <Module>@<uid>
    name: str
    uid: str
    monitor: str
    params: Mapping[str, Any]


class ModuleContext:
    def __init__(
        self,
        name: str,
        uid: str,
        config: Mapping[str, Any],
        uses: Mapping[str, UseRecord],
        send: Callable[[str | None, str, object], None],
        ticks: TimeSource,
    ) -> None:
        self.name = name
        self.uid = uid
        self.config = config
        self.uses = uses
        self.log = logger.bind(source=f"module:{name}")
        self._send = send
        self._ticks = ticks
        self._subscriptions: list[Subscription] = []

    def send(self, key: str, value: object, use: UseRecord | str | None = None) -> None:
        """Send one value, for one use or (with no ``use``) for every use of this module. Thread
        safe, coalesced, never blocks."""
        use_key = use.key if isinstance(use, UseRecord) else use
        self._send(use_key, key, value)

    def on_tick(self, unit: str, fn: Callable[[], None]) -> Subscription:
        """Call ``fn`` at the start of each ``"second"`` or ``"minute"``, on the loop thread."""
        guarded = self._guard(fn)
        sub = self._ticks.subscribe(unit, guarded)
        self._subscriptions.append(sub)
        return sub

    def _guard(self, fn: Callable[[], None]) -> Callable[[], None]:
        def run() -> None:
            try:
                fn()
            except Exception:
                self.log.opt(exception=True).error("a tick callback raised")

        return run

    def close(self) -> None:
        for sub in self._subscriptions:
            sub.cancel()
        self._subscriptions.clear()
