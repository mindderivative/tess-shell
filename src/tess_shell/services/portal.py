"""Follow the desktop's appearance through the Settings portal (Portals > The Settings Portal).

One ``ReadAll`` of ``org.freedesktop.appearance`` at start, then ``SettingChanged`` only: no
polling. Everything runs on the D-Bus service thread; ``on_change`` is called there and its
caller crosses to the loop thread with ``call_soon``. A missing portal, a failed read or an odd
value gives the defaults and one warning; the reader tries again when the portal service
reappears on the bus.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from collections.abc import Callable, Mapping
from dataclasses import replace
from typing import Any

from dbus_fast import DBusError, Variant
from dbus_fast.aio import MessageBus
from loguru import logger

from tess_shell.appearance import Appearance, Scheme
from tess_shell.services.bus import CALL_TIMEOUT, ServiceThread

APP_ID = "io.github.mindderivative.TesseraeShell"
PORTAL = "org.freedesktop.portal.Desktop"
PATH = "/org/freedesktop/portal/desktop"
NAMESPACE = "org.freedesktop.appearance"

_SCHEMES: dict[int, Scheme] = {0: "default", 1: "dark", 2: "light"}


def _unwrap(value: Any) -> Any:
    return value.value if isinstance(value, Variant) else value


def _accent(raw: Any) -> tuple[int, int, int] | None:
    """``(ddd)`` with each channel 0 to 1; out of range means unset."""
    try:
        r, g, b = (float(c) for c in _unwrap(raw))
    except TypeError, ValueError:
        return None
    if not all(0.0 <= c <= 1.0 for c in (r, g, b)):
        return None
    return (round(r * 255), round(g * 255), round(b * 255))


def apply_key(current: Appearance, key: str, raw: Any) -> Appearance:
    """``current`` with one portal key applied; a key it does not know leaves it as it is, and an
    unknown value of a ``u`` key counts as 0 (the portal documentation)."""
    value = _unwrap(raw)
    match key:
        case "color-scheme":
            return replace(current, scheme=_SCHEMES.get(value, "default"))
        case "accent-color":
            return replace(current, accent=_accent(value))
        case "contrast":
            return replace(current, high_contrast=value == 1)
        case "reduced-motion":
            return replace(current, reduced_motion=value == 1)
    return current


def parse(values: Mapping[str, Any]) -> Appearance:
    result = Appearance()
    for key, raw in values.items():
        result = apply_key(result, key, raw)
    return result


class PortalReader:
    def __init__(
        self,
        service: ServiceThread,
        on_change: Callable[[Appearance], None],
        app_id: str = APP_ID,
    ) -> None:
        self._service = service
        self._on_change = on_change
        self._app_id = app_id
        self.current = Appearance()
        self._known = Appearance()  # what the consumer has been told: the defaults, until told more
        self._known_lock = threading.Lock()
        self._gave_up = False  # ``first`` timed out: the consumer runs on the defaults
        self._first: concurrent.futures.Future[Appearance] | None = None
        self._task: concurrent.futures.Future[None] | None = None
        self._warned = False

    def start(self) -> None:
        """Begin on the service thread: register, read once, then listen."""
        self._first = concurrent.futures.Future()
        self._task = self._service.submit(self._run())

    def first(self, timeout: float = 0.2) -> Appearance:
        """The first answer, or the defaults after ``timeout`` seconds (a slow portal never delays
        the surfaces; the answer then arrives through ``on_change``)."""
        assert self._first is not None, "start() first"
        try:
            return self._first.result(timeout)
        except concurrent.futures.TimeoutError:
            with self._known_lock:
                if self._first.done():  # it arrived in the gap
                    return self._first.result()
                self._gave_up = True
            return Appearance()

    def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()

    # -- on the service thread ----------------------------------------------------------------

    def _warn(self, message: str) -> None:
        """One warning for all the trouble with the portal; the rest is debug (no retry loop)."""
        if not self._warned:
            self._warned = True
            logger.warning(f"portal: {message}")
        else:
            logger.debug(f"portal: {message}")

    def _settle(self, appearance: Appearance, *, initial: bool) -> None:
        if appearance != self.current or initial:
            logger.debug(f"portal: appearance {appearance}")
        self.current = appearance
        call = False
        with self._known_lock:
            first = self._first
            if first is not None and not first.done() and not self._gave_up:
                # a caller is waiting in ``first``: it gets this answer, not ``on_change``
                self._known = appearance
                first.set_result(appearance)
            elif appearance != self._known:
                self._known = appearance
                if first is not None and not first.done():
                    first.set_result(appearance)
                call = True
        if call:
            self._on_change(appearance)

    async def _run(self) -> None:
        try:
            bus = await self._service.session()
        except Exception as exc:
            self._warn(f"the session bus is not reachable ({exc}); using the default appearance")
            self._settle(Appearance(), initial=True)
            return
        await self._watch_owner(bus)
        await self._read(bus, first=True)
        await asyncio.Event().wait()  # signals do the rest

    async def _proxy(self, bus: MessageBus, interface: str) -> Any:
        intro = await asyncio.wait_for(bus.introspect(PORTAL, PATH), CALL_TIMEOUT)
        return bus.get_proxy_object(PORTAL, PATH, intro).get_interface(interface)

    async def _read(self, bus: MessageBus, *, first: bool) -> None:
        try:
            await self._register(bus)
            settings = await self._proxy(bus, "org.freedesktop.portal.Settings")
            reply = await asyncio.wait_for(settings.call_read_all([NAMESPACE]), CALL_TIMEOUT)
            if not self._subscribed:
                settings.on_setting_changed(self._setting_changed)
                self._subscribed = True
            self._settle(parse(reply.get(NAMESPACE, {})), initial=first)
        except (DBusError, TimeoutError, OSError, AttributeError) as exc:
            self._warn(
                f"the Settings portal is not available ({exc}); using the default appearance"
            )
            self._settle(Appearance(), initial=first)

    _subscribed = False
    _registered = False

    async def _register(self, bus: MessageBus) -> None:
        """An unsandboxed app registers its id once, before any other portal call."""
        if self._registered:
            return
        self._registered = True
        try:
            intro = await asyncio.wait_for(bus.introspect(PORTAL, PATH), CALL_TIMEOUT)
            registry: Any = bus.get_proxy_object(PORTAL, PATH, intro).get_interface(
                "org.freedesktop.host.portal.Registry"
            )
            await asyncio.wait_for(registry.call_register(self._app_id, {}), CALL_TIMEOUT)
        except Exception as exc:  # the reads continue without it
            self._warn(f"Register failed ({exc}); reading the settings anyway")

    def _setting_changed(self, namespace: str, key: str, value: Any) -> None:
        if namespace == NAMESPACE:
            self._settle(apply_key(self.current, key, value), initial=False)

    async def _watch_owner(self, bus: MessageBus) -> None:
        """The portal service came back (or a new one took the name): register and read again."""
        try:
            intro = await asyncio.wait_for(
                bus.introspect("org.freedesktop.DBus", "/org/freedesktop/DBus"), CALL_TIMEOUT
            )
            dbus: Any = bus.get_proxy_object(
                "org.freedesktop.DBus", "/org/freedesktop/DBus", intro
            ).get_interface("org.freedesktop.DBus")
        except Exception as exc:
            logger.debug(f"portal: cannot watch the bus names ({exc})")
            return

        def owner_changed(name: str, old: str, new: str) -> None:
            if name == PORTAL and new:
                self._registered = False
                self._subscribed = False
                asyncio.ensure_future(self._read(bus, first=False))

        dbus.on_name_owner_changed(owner_changed)
