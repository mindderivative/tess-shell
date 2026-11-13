"""The Tray_Menu: the menu of a tray item (Tray Module > The Menu), the content of the Popups
``Tray_Menu``, ``Tray_Menu_2`` and ``Tray_Menu_3``. The Tray fetched the tree and opened the
Popup with it in ``caller.data`` (``menus``: the entries under each parent; ``service`` and
``path``: where a click goes). This module draws one level (``Level``: 1 is the root's children, 2
and 3 the children of the row that opened the submenu) and turns a click on a row into
``com.canonical.dbusmenu.Event(id, "clicked", <empty variant>, timestamp)``. A click closes the
whole menu (the Popup does that); a failed call is one warning a minute per service."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from tess_shell import Module, action

if TYPE_CHECKING:
    from tess_shell.module import Event
    from tess_shell.services.api import Bus, Proxy

MENU_INTERFACE = "com.canonical.dbusmenu"
WARN_EVERY = 60.0  # seconds between two warnings about the same service


class Tray_Menu(Module):
    def __init__(self) -> None:
        self.failed: dict[str, float] = {}
        self.monotonic = time.monotonic  # a test swaps it

    def start(self) -> None:
        self.bus: Bus = self.ctx.dbus.session()

    @action
    def pick(self, event: Event, id: str, service: str, path: str, submenu: str = "") -> None:
        """A row was clicked: tell the application (``Event`` with ``clicked``); the menu closes.
        A row that opens a submenu (``submenu`` is its Popup) is only opened by the click."""
        if submenu:
            return
        stamp = int(time.time()) & 0xFFFFFFFF
        proxy = self.bus.proxy(service, path, MENU_INTERFACE, optional=True)
        self.bus.run(self.send(proxy, service, int(id), stamp))

    async def send(self, proxy: Proxy, service: str, ident: int, stamp: int) -> None:
        try:
            # the data of a ``clicked`` event is an empty variant: ("s", "")
            await proxy.call("Event", [ident, "clicked", ("s", ""), stamp], "isvu")
        except Exception as exc:
            now = self.monotonic()
            if now - self.failed.get(service, float("-inf")) >= WARN_EVERY:
                self.failed[service] = now
                self.ctx.log.warning(f"Event {ident} of {service} failed ({exc})")
            else:
                self.ctx.log.debug(f"Event {ident} of {service} failed ({exc})")
