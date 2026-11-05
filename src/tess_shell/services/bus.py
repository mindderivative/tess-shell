"""The D-Bus service thread (D-Bus Service Layer > The Service Thread).

One thread named ``dbus`` runs one asyncio loop and owns the session-bus connection, opened on
first use. Nothing here touches a node: a callback on this thread hands its result to the loop
thread with ``call_soon`` (Process Model and Threading). No call is made from the loop thread.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from collections.abc import Coroutine
from typing import Any

from dbus_fast import BusType
from dbus_fast.aio import MessageBus
from loguru import logger

CALL_TIMEOUT = 5.0  # seconds; every call has one


class ServiceThread:
    def __init__(self, address: str | None = None) -> None:
        """``address`` is a bus address for tests; ``None`` is the session bus as the
        environment gives it (``DBUS_SESSION_BUS_ADDRESS``)."""
        self._address = address
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self._bus: MessageBus | None = None
        self._lock: asyncio.Lock | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="dbus", daemon=True)
        self._thread.start()
        self._ready.wait()

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._lock = asyncio.Lock()
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            tasks = asyncio.all_tasks(loop)
            for task in tasks:
                task.cancel()
            loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
            if self._bus is not None:
                self._bus.disconnect()
            loop.close()

    def submit[T](self, coro: Coroutine[Any, Any, T]) -> concurrent.futures.Future[T]:
        """Run ``coro`` on the service thread; the future is for the caller's thread."""
        assert self._loop is not None, "the service thread is not started"
        return asyncio.run_coroutine_threadsafe(coro, self._loop)

    async def session(self) -> MessageBus:
        """The session-bus connection (call this from a coroutine on the service thread)."""
        assert self._lock is not None
        async with self._lock:
            if self._bus is None or not self._bus.connected:
                bus = (
                    MessageBus(bus_address=self._address)
                    if self._address
                    else MessageBus(bus_type=BusType.SESSION)
                )
                self._bus = await asyncio.wait_for(bus.connect(), CALL_TIMEOUT)
                logger.debug("dbus: connected to the session bus")
            return self._bus

    def stop(self) -> None:
        loop, thread = self._loop, self._thread
        if loop is None or thread is None:
            return
        loop.call_soon_threadsafe(loop.stop)
        thread.join(timeout=5)
        self._thread = None
        self._loop = None
