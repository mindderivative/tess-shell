"""The context (``self.ctx``): a module's whole view of the shell (Module Context).

M2 offers ``name``, ``uid``, ``config``, ``log``, ``uses``, ``send`` and ``on_tick``; the rest of
the member list waits for a module that needs it.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from loguru import logger

from tess_shell.modules.ticks import Subscription, TimeSource
from tess_shell.services.api import DBusPort, ModuleDBus


@dataclass(frozen=True, slots=True)
class UseRecord:
    """A place where the module is used."""

    key: str  # <Module>@<uid>
    name: str
    uid: str
    monitor: str
    params: Mapping[str, Any]


class PopupPort(Protocol):
    """What the shell offers a module for its Popups (the surface manager's ``Popups``)."""

    def call(
        self, module: str, use: str | None, name: str, data: Mapping[str, Any] | None
    ) -> None: ...

    def close_named(self, name: str | None = None) -> None: ...


class ModuleContext:
    def __init__(
        self,
        name: str,
        uid: str,
        config: Mapping[str, Any],
        uses: Mapping[str, UseRecord],
        send: Callable[[str | None, str, object], None],
        ticks: TimeSource,
        popups: Callable[[], PopupPort | None] | None = None,
        dbus: Callable[[], DBusPort | None] | None = None,
    ) -> None:
        self.name = name
        self.caller: UseRecord | None = None  # the use whose block raised the event being handled
        self._popups = popups
        self._dbus_port = dbus
        self._dbus: ModuleDBus | None = None
        self._on_lost: Callable[[str], None] | None = None
        self._on_found: Callable[[str], None] | None = None
        self._closed = False
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

    def popup(
        self,
        name: str,
        data: Mapping[str, Any] | None = None,
        use: UseRecord | str | None = None,
    ) -> None:
        """Open the Popup ``name`` beside the use that called (``ctx.caller``, set while an
        ``@action`` runs; or ``use``), or close it when it is the open one. Loop thread only. A
        Popup that does not exist, or a use on no open surface, is logged with the module and
        the name; nothing is raised."""
        key = use.key if isinstance(use, UseRecord) else use
        if key is None and self.caller is not None:
            key = self.caller.key
        if key is None:
            self.log.error(
                f"ctx.popup({name!r}) needs the use that calls it: call it from an @action, "
                "or pass use="
            )
            return
        port = self._popups() if self._popups else None
        if port is None:
            self.log.error(f"ctx.popup({name!r}): the shell has no surfaces to open it on")
            return
        port.call(self.name, key, name, data)

    def close_popup(self, name: str | None = None) -> None:
        """Close the open Popup (the one called ``name``, if given). Loop thread only."""
        port = self._popups() if self._popups else None
        if port is not None:
            port.close_named(name)

    @property
    def dbus(self) -> ModuleDBus:
        """The D-Bus helper (D-Bus Service Layer): ``ctx.dbus.session()`` and ``.system()`` give a
        bus with ``proxy(name, path)``. Nothing connects until a proxy is used."""
        if self._dbus is None:
            port = self._dbus_port() if self._dbus_port else None
            if port is None:
                raise RuntimeError("the shell has no D-Bus service layer")
            self._dbus = port.for_module(self.name, lambda key, value: self.send(key, value), self)
        return self._dbus

    def set_service_hooks(self, lost: Callable[[str], None], found: Callable[[str], None]) -> None:
        """The module's ``on_service_lost`` and ``on_service_found`` (set by the host)."""
        self._on_lost, self._on_found = lost, found

    def lost(self, name: str) -> None:  # ServiceHooks: the layer calls it on the loop thread
        self._service_hook("on_service_lost", self._on_lost, name)

    def found(self, name: str) -> None:
        self._service_hook("on_service_found", self._on_found, name)

    def _service_hook(self, what: str, fn: Callable[[str], None] | None, name: str) -> None:
        if self._closed or fn is None:
            return
        try:
            fn(name)
        except Exception:
            self.log.opt(exception=True).error(f"{what}({name!r}) raised")

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
        self._closed = True
        if self._dbus is not None:
            self._dbus.close()
            self._dbus = None
