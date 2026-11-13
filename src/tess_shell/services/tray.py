"""The shell as a StatusNotifier host (Tray Module > The Host, Plasma Coexistence > Tray).

A second host next to Plasma's: the shell owns ``org.kde.StatusNotifierHost-<pid>`` on the session
bus and calls ``RegisterStatusNotifierHost`` on ``org.kde.StatusNotifierWatcher``. It starts a
watcher of its own never (Plasma Coexistence): with none on the bus it logs one warning and waits
for one. The name is taken through ``Bus.own_name``, which is the shell's alone: a module sees only
``ModuleTray.on_host`` and cannot own any name.

Everything runs on the ``dbus`` service thread. The host starts with the first subscription of a
module and ends (gives the name up) with the last. It registers again each time the watcher comes
(it started late or restarted) and after a reconnect to the bus; the name itself is asked for again
by the bus after a reconnect (``Bus.on_reconnect``). A name that is taken is tried again as
``-<pid>-<n>`` for the next ``n``; after three tries there is one error and the host is not
registered (``on_host(False)``).
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable

from loguru import logger

from tess_shell.services.api import (
    HostCallback,
    ModuleTray,
    ServiceError,
    Subscription,
)
from tess_shell.services.bus import Bus, ServiceThread, Unsubscribe

WATCHER = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"
WATCHER_INTERFACE = "org.kde.StatusNotifierWatcher"
HOST_PREFIX = "org.kde.StatusNotifierHost-"
TRIES = 3  # names tried before giving up: -<pid>, -<pid>-1, -<pid>-2


class TrayService:
    """One per shell. ``pid`` is for the tests (the host name carries it)."""

    def __init__(self, service: ServiceThread, pid: int | None = None) -> None:
        self._service = service
        self._pid = pid if pid is not None else os.getpid()
        self._callbacks: list[HostCallback] = []
        self._hosted: bool | None = None  # what the callbacks were last told
        self._name: str | None = None  # the host name the shell owns
        self._unwatch: Unsubscribe | None = None
        self._started = False
        self._lock: asyncio.Lock | None = None
        self.registered = 0  # RegisterStatusNotifierHost calls that went through (tests)

    @property
    def bus(self) -> Bus:
        return self._service.session

    def for_module(self, module: str) -> ModuleTray:
        """The helper for one module (``ctx.tray``)."""
        return _ModuleTray(self, module)

    # -- subscriptions (any thread: the work is posted to the service thread) -------------------

    def subscribe(self, callback: HostCallback) -> Subscription:
        sub = _Sub(self, callback)
        self._service.post(lambda: self._add(sub))
        return sub

    def _add(self, sub: _Sub) -> None:
        if sub.cancelled:
            return
        self._callbacks.append(sub.callback)
        if self._hosted is not None:
            self._call(sub.callback, self._hosted)
        if not self._started:
            self._started = True
            task = asyncio.ensure_future(self._start())
            task.add_done_callback(self._done)

    def _remove(self, sub: _Sub) -> None:
        if sub.callback in self._callbacks:
            self._callbacks.remove(sub.callback)
        if not self._callbacks and self._started:
            self._started = False
            asyncio.ensure_future(self._stop()).add_done_callback(self._done)

    @staticmethod
    def _done(task: asyncio.Future[None]) -> None:
        if not task.cancelled() and task.exception() is not None:
            logger.opt(exception=task.exception()).error("tray host: a task failed")

    # -- the host (service thread) --------------------------------------------------------------

    async def _start(self) -> None:
        self._lock = asyncio.Lock()
        try:
            self._unwatch = await self.bus.watch(WATCHER, self._owner_changed)
        except ServiceError as exc:
            logger.debug(f"tray host: the session bus is not reachable yet ({exc})")
            self._set(False)
            return
        if self.bus.owner(WATCHER) is None:
            logger.warning(
                f"no {WATCHER} on the session bus: the tray stays empty until one appears (the "
                "shell does not start one; Plasma's kded6 provides it)"
            )
            self._set(False)
            return
        await self._register()

    async def _stop(self) -> None:
        if self._unwatch is not None:
            self._unwatch()
            self._unwatch = None
        name, self._name = self._name, None
        self._hosted = None
        if name is not None:
            await self.bus.release_name(name)

    def _owner_changed(self, old: str | None, new: str | None) -> None:
        if not self._started:
            return
        if new is None:
            logger.info(f"tray host: {WATCHER} left the session bus")
            self._set(False)
        else:
            task = asyncio.ensure_future(self._register())
            task.add_done_callback(self._done)

    async def _register(self) -> None:
        """Own the host name and tell the watcher; the watcher that came after a restart gets it
        again. One at a time: a restart can raise the owner change twice."""
        assert self._lock is not None
        async with self._lock:
            if not self._started:
                return
            try:
                name = await self._own()
                if name is None:
                    self._set(False)
                    return
                await self.bus.call(
                    WATCHER,
                    WATCHER_PATH,
                    WATCHER_INTERFACE,
                    "RegisterStatusNotifierHost",
                    "s",
                    [name],
                )
            except ServiceError as exc:
                logger.warning(f"tray host: could not register with {WATCHER} ({exc})")
                self._set(False)
                return
            self.registered += 1
            logger.info(f"tray host: registered as {name} with {WATCHER}")
            self._set(True)

    async def _own(self) -> str | None:
        """The host name this shell owns: the one it has, or the first of the three it can get."""
        if self._name is not None and await self.bus.own_name(self._name):
            return self._name
        self._name = None
        for n in range(TRIES):
            name = f"{HOST_PREFIX}{self._pid}" + (f"-{n}" if n else "")
            if await self.bus.own_name(name):
                self._name = name
                return name
        logger.error(
            f"tray host: the names {HOST_PREFIX}{self._pid}, -{self._pid}-1 and -{self._pid}-2 are "
            "all taken: the tray shows nothing"
        )
        return None

    def _set(self, hosted: bool) -> None:
        if hosted == self._hosted:
            return
        self._hosted = hosted
        for callback in list(self._callbacks):
            self._call(callback, hosted)

    @staticmethod
    def _call(callback: Callable[[bool], None], hosted: bool) -> None:
        try:
            callback(hosted)
        except Exception:
            logger.opt(exception=True).error("tray host: a callback raised")


class _Sub:
    def __init__(self, service: TrayService, callback: HostCallback) -> None:
        self._service = service
        self.callback = callback
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True
        self._service._service.post(lambda: self._service._remove(self))


class _ModuleTray:
    """``ctx.tray`` of one module: ``on_host`` and nothing else."""

    def __init__(self, service: TrayService, module: str) -> None:
        self._service = service
        self._module = module
        self._subs: list[Subscription] = []

    def on_host(self, callback: HostCallback) -> Subscription:
        sub = self._service.subscribe(callback)
        self._subs.append(sub)
        return sub

    def close(self) -> None:
        for sub in self._subs:
            sub.cancel()
        self._subs.clear()
