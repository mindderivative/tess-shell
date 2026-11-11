"""The D-Bus service layer a module uses through ``ctx.dbus`` (D-Bus Service Layer).

Everything here that touches a bus runs on the ``dbus`` service thread; the functions a module
calls from the loop thread only post work to it. What the layer adds to :class:`Bus`:

* a state per service (``AVAILABLE`` or ``UNAVAILABLE``), from ``NameOwnerChanged`` and from the
  calls that fail: a service that leaves gives its modules ``available`` false and
  ``on_service_lost``, one that returns gives them their properties again, ``available`` true and
  ``on_service_found`` (both hooks are handed to the loop with ``call_soon``);
* a cache of the properties of each (bus, service, path, interface) that is read once (``GetAll``)
  and kept current from ``PropertiesChanged``;
* a timeout on every call, the rate-limited warnings and the callback-time guard.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
import time
from collections import deque
from collections.abc import Callable, Coroutine, Mapping, Sequence
from typing import Any

from loguru import logger

from tess_shell.services.api import (
    CALL_TIMEOUT,
    BlockingCallError,
    ModuleDBus,
    PropertyCallback,
    ServiceError,
    ServiceHooks,
    ServiceState,
    ServiceTimeout,
    ServiceUnavailable,
    SignalCallback,
)
from tess_shell.services.bus import (
    BusKind,
    MatchKey,
    ServiceThread,
    Unsubscribe,
    unwrap,
)

PROPERTIES = "org.freedesktop.DBus.Properties"
SLOW_CALLBACK = 0.05  # seconds of its own work; a callback over this is logged with the module
WARN_EVERY = 60.0  # seconds; one warning per service and kind of trouble in this time
_STATS_KEPT = 4096  # callback times kept per module, for the measurements

CallSoon = Callable[[Callable[[], None]], None]


def percentile(values: Sequence[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    return ordered[min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))]


class Layer:
    """One per shell. ``call_soon`` runs a function on the loop thread (``LoopHandle.call_soon``);
    ``loop_thread`` is that thread's ident (default: the thread that makes the layer)."""

    def __init__(
        self,
        service: ServiceThread,
        call_soon: CallSoon,
        *,
        loop_thread: int | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.service = service
        self.call_soon = call_soon
        self.loop_thread = loop_thread if loop_thread is not None else threading.get_ident()
        self._clock = clock
        self._services: dict[tuple[BusKind, str], _Service] = {}
        self._caches: dict[tuple[BusKind, str, str, str], _Cache] = {}
        self._warned: dict[tuple[str, str, str], float] = {}
        self._tasks: set[asyncio.Future[Any]] = set()
        self.callback_times: dict[str, deque[float]] = {}  # module -> seconds of each callback

    def for_module(
        self, module: str, send: Callable[[str, object], None], hooks: ServiceHooks
    ) -> ModuleDBus:
        """The helper for one module (``ctx.dbus``)."""
        return _ModuleDBus(self, module, send, hooks)

    # -- measurement and warnings ---------------------------------------------------------------

    def callback_summary(self, module: str | None = None) -> tuple[int, float, float, float]:
        """``(count, p50, p99, max)`` in seconds of the callbacks run on the service thread, of one
        module or of all of them."""
        pool = (
            list(self.callback_times.get(module, ()))
            if module is not None
            else [t for times in self.callback_times.values() for t in times]
        )
        return (len(pool), percentile(pool, 0.5), percentile(pool, 0.99), max(pool, default=0.0))

    def warn_limited(self, key: tuple[str, str, str], message: str) -> None:
        """A warning, at most one per ``key`` in :data:`WARN_EVERY` seconds; the rest are debug."""
        now = self._clock()
        last = self._warned.get(key)
        if last is None or now - last >= WARN_EVERY:
            self._warned[key] = now
            logger.warning(message)
        else:
            logger.debug(message)

    def timed(self, helper: _ModuleDBus, fn: Callable[..., None], *args: object) -> None:
        """Run a module's callback on the service thread: an exception is logged with the module's
        name, and a callback over :data:`SLOW_CALLBACK` is a warning naming it."""
        start = time.perf_counter()
        try:
            fn(*args)
        except Exception:
            helper.log.opt(exception=True).error("a D-Bus callback raised")
        took = time.perf_counter() - start
        self.callback_times.setdefault(helper.module, deque(maxlen=_STATS_KEPT)).append(took)
        if took > SLOW_CALLBACK:
            logger.warning(
                f"module {helper.module}: a D-Bus callback took {took * 1000:.0f} ms on the "
                f"service thread (over {SLOW_CALLBACK * 1000:.0f} ms); hand slow work to a thread"
            )

    # -- on the service thread ------------------------------------------------------------------

    def spawn(self, coro: Coroutine[Any, Any, Any]) -> None:
        task = asyncio.ensure_future(coro)
        self._tasks.add(task)
        task.add_done_callback(self._done)

    def _done(self, task: asyncio.Future[Any]) -> None:
        self._tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            logger.opt(exception=task.exception()).error("dbus: a layer task failed")

    async def attach(self, helper: _ModuleDBus, kind: BusKind, name: str) -> _Service:
        """``helper`` uses the service ``name``: watch its owner (the first user does) and give
        the module its state."""
        service = self._services.get((kind, name))
        if service is None:
            service = self._services[(kind, name)] = _Service(self, kind, name)
        await service.attach(helper)
        return service

    def cache(self, helper: _ModuleDBus, service: _Service, path: str, interface: str) -> _Cache:
        key = (service.kind, service.name, path, interface)
        cache = self._caches.get(key)
        if cache is None:
            cache = self._caches[key] = _Cache(self, service, path, interface)
        cache.users.add(helper)
        return cache

    def drop_cache(self, cache: _Cache) -> None:
        key = (cache.service.kind, cache.service.name, cache.path, cache.interface)
        if self._caches.get(key) is cache:
            del self._caches[key]
        cache.close()

    async def call(
        self,
        service: _Service,
        path: str,
        interface: str,
        member: str,
        signature: str,
        args: Sequence[Any],
        timeout: float,
    ) -> list[Any]:
        """A call on behalf of a module: the failures set the service's state and are warned
        about at a limited rate (one per service a minute for each kind)."""
        bus = self.service.bus(service.kind)
        try:
            reply = await bus.call(
                service.name, path, interface, member, signature, args, timeout=timeout
            )
        except ServiceUnavailable as exc:
            self.warn_limited(
                (service.kind, service.name, "unavailable"),
                f"dbus: {exc} ({service.kind} bus); its modules show their empty state",
            )
            service.mark_unavailable()
            raise
        except ServiceTimeout as exc:
            self.warn_limited(
                (service.kind, service.name, "timeout"), f"dbus: {exc} ({service.kind} bus)"
            )
            raise
        service.mark_ok()
        return reply


class _Service:
    """One well-known name on one bus, shared by every module that uses it."""

    def __init__(self, layer: Layer, kind: BusKind, name: str) -> None:
        self.layer = layer
        self.kind: BusKind = kind
        self.name = name
        self.state = ServiceState.UNAVAILABLE
        self.listeners: list[_ModuleDBus] = []
        self._unwatch: Unsubscribe | None = None
        self._starting = False
        self._finding = False
        self._ready = asyncio.Event()

    @property
    def key(self) -> tuple[BusKind, str]:
        return (self.kind, self.name)

    async def attach(self, helper: _ModuleDBus) -> None:
        if helper not in self.listeners:
            self.listeners.append(helper)
        if not self._starting:
            self._starting = True
            bus = self.layer.service.bus(self.kind)
            try:
                self._unwatch = await bus.watch(self.name, self._owner_changed)
            except BaseException:
                self._starting = False
                raise
            self.state = (
                ServiceState.AVAILABLE if bus.owner(self.name) else ServiceState.UNAVAILABLE
            )
            self._ready.set()
        else:
            await self._ready.wait()
        helper.service_state(self, self.state, None)

    def detach(self, helper: _ModuleDBus) -> None:
        if helper in self.listeners:
            self.listeners.remove(helper)
        if not self.listeners:
            if self._unwatch is not None:
                self._unwatch()
                self._unwatch = None
            if self.layer._services.get(self.key) is self:
                del self.layer._services[self.key]

    def _owner_changed(self, old: str | None, new: str | None) -> None:
        if new is None:
            logger.info(f"dbus: {self.name} left the {self.kind} bus")
            for cache in self._caches():
                cache.loaded = False
            self._set(ServiceState.UNAVAILABLE, "lost")
        else:
            logger.info(f"dbus: {self.name} is on the {self.kind} bus ({new})")
            self.layer.spawn(self._found())

    def _caches(self) -> list[_Cache]:
        return [c for c in self.layer._caches.values() if c.service is self]

    async def _found(self) -> None:
        """The service has an owner: read its properties again, then tell the modules."""
        if self._finding:  # the reads below are calls too: each would start another round
            return
        self._finding = True
        try:
            for cache in self._caches():
                await cache.refresh()
        finally:
            self._finding = False
        bus = self.layer.service.bus(self.kind)
        if bus.owner(self.name) is None:  # it left again while we read
            return
        self._set(ServiceState.AVAILABLE, "found")

    def _set(self, state: ServiceState, hook: str) -> None:
        changed = state is not self.state
        self.state = state
        for helper in list(self.listeners):
            helper.service_state(self, state, hook if (changed or hook == "found") else None)

    def mark_unavailable(self) -> None:
        if self.state is ServiceState.AVAILABLE:
            for cache in self._caches():
                cache.loaded = False
            self._set(ServiceState.UNAVAILABLE, "lost")

    def mark_ok(self) -> None:
        if self.state is ServiceState.UNAVAILABLE and not self._finding:
            self.layer.spawn(self._found())  # a call went through: it is there


class _PropSub:
    __slots__ = ("callback", "delivered", "helper", "initial")

    def __init__(self, helper: _ModuleDBus, callback: PropertyCallback, initial: bool) -> None:
        self.helper = helper
        self.callback = callback
        self.initial = initial
        self.delivered = False  # has it had its first set of values


class _Cache:
    """The properties of one interface of one object, and who listens to their changes."""

    def __init__(self, layer: Layer, service: _Service, path: str, interface: str) -> None:
        self.layer = layer
        self.service = service
        self.path = path
        self.interface = interface
        self.values: dict[str, Any] = {}
        self.loaded = False
        self.users: set[_ModuleDBus] = set()
        self.subs: list[_PropSub] = []
        self._unsubscribe: Unsubscribe | None = None
        self._lock = asyncio.Lock()
        self.reads = 0  # GetAll calls made (tests)

    async def ensure(self) -> None:
        """Subscribe to ``PropertiesChanged`` (before the read, so no change is missed) and read
        every property once."""
        async with self._lock:
            if self._unsubscribe is None:
                key = MatchKey(
                    self.service.name, self.path, PROPERTIES, "PropertiesChanged", self.interface
                )
                bus = self.layer.service.bus(self.service.kind)
                self._unsubscribe = await bus.subscribe(key, self._on_signal)
            if not self.loaded:
                await self._load()

    async def _load(self) -> None:
        self.reads += 1
        reply = await self.layer.call(
            self.service, self.path, PROPERTIES, "GetAll", "s", [self.interface], CALL_TIMEOUT
        )
        self.values = dict(reply[0]) if reply else {}
        self.loaded = True

    async def refresh(self) -> None:
        """Read everything again (the service came back, or a property was invalidated) and give
        every listener the whole set."""
        try:
            async with self._lock:
                await self._load()
        except ServiceError:
            return  # warned and counted by Layer.call; the next owner change tries again
        self._deliver_all()

    def _on_signal(self, message: Any) -> None:
        _, changed, invalidated = message.body
        changed = unwrap(changed)
        self.values.update(changed)
        if invalidated:
            for prop in invalidated:
                self.values.pop(prop, None)
            self.layer.spawn(self.refresh())
        if changed:
            self._deliver(dict(changed))

    def _deliver(self, values: Mapping[str, Any]) -> None:
        """``PropertiesChanged``: the changes, to the listeners that already have their first
        set (the others get everything when their first read is done)."""
        for sub in list(self.subs):
            if sub.delivered:
                self.layer.timed(sub.helper, sub.callback, dict(values))

    def _deliver_all(self) -> None:
        """After a re-read: every property, to every listener (a first set for one that had none
        yet: nothing, if it asked for ``initial=False``)."""
        for sub in list(self.subs):
            first = not sub.delivered
            sub.delivered = True
            if first and not sub.initial:
                continue
            self.layer.timed(sub.helper, sub.callback, dict(self.values))

    def deliver_first(self, sub: _PropSub) -> None:
        sub.delivered = True
        if sub.initial:
            self.layer.timed(sub.helper, sub.callback, dict(self.values))

    def close(self) -> None:
        if self._unsubscribe is not None:
            self._unsubscribe()
            self._unsubscribe = None

    def release(self, helper: _ModuleDBus, sub: _PropSub | None) -> None:
        if sub is not None and sub in self.subs:
            self.subs.remove(sub)
        if not any(s.helper is helper for s in self.subs):
            self.users.discard(helper)
        if not self.users:
            self.layer.drop_cache(self)


class _Subscription:
    """What ``on_property_changed`` and ``on_signal`` return. The work happens on the service thread
    some time after the call, so a cancel before that is remembered."""

    def __init__(self, helper: _ModuleDBus) -> None:
        self._helper = helper
        self._undo: Callable[[], None] | None = None
        self._cancelled = False

    def attach(self, undo: Callable[[], None]) -> None:  # service thread
        if self._cancelled:
            undo()
        else:
            self._undo = undo

    def cancel(self) -> None:
        self._cancelled = True
        self._helper.layer.service.post(self._run)

    def _run(self) -> None:  # service thread
        undo, self._undo = self._undo, None
        if undo is not None:
            undo()


class _Proxy:
    def __init__(self, bus: _Bus, name: str, path: str, interface: str | None) -> None:
        self._bus = bus
        self.name = name
        self.path = path
        self.interface = interface

    def _interface(self, interface: str | None) -> str:
        found = interface or self.interface
        if not found:
            raise ValueError("give an interface: to proxy() or to this call")
        return found

    async def get(self, prop: str, *, interface: str | None = None, fresh: bool = False) -> Any:
        helper, kind, layer = self._bus.helper, self._bus.kind, self._bus.helper.layer
        iface = self._interface(interface)
        service = await layer.attach(helper, kind, self.name)
        if fresh:
            reply = await layer.call(
                service, self.path, PROPERTIES, "Get", "ss", [iface, prop], CALL_TIMEOUT
            )
            value = reply[0]
            cache = layer._caches.get((kind, self.name, self.path, iface))
            if cache is not None and cache.loaded:
                cache.values[prop] = value
            return value
        cache = layer.cache(helper, service, self.path, iface)
        await cache.ensure()
        try:
            return cache.values[prop]
        except KeyError:
            raise ServiceError(self.name, f"{self.path} has no property {iface}.{prop}") from None

    async def call(
        self,
        method: str,
        args: Sequence[Any] = (),
        signature: str = "",
        *,
        interface: str | None = None,
        timeout: float = CALL_TIMEOUT,
    ) -> Any:
        if args and not signature:
            raise ValueError("arguments need their D-Bus signature")
        iface = self._interface(interface)
        helper, kind, layer = self._bus.helper, self._bus.kind, self._bus.helper.layer
        service = await layer.attach(helper, kind, self.name)
        reply = await layer.call(service, self.path, iface, method, signature, args, timeout)
        if not reply:
            return None
        return reply[0] if len(reply) == 1 else tuple(reply)

    def on_property_changed(
        self, callback: PropertyCallback, *, interface: str | None = None, initial: bool = True
    ) -> _Subscription:
        iface = self._interface(interface)
        helper, kind, layer = self._bus.helper, self._bus.kind, self._bus.helper.layer
        subscription = helper.subscription()

        async def watch() -> None:
            service = await layer.attach(helper, kind, self.name)
            cache = layer.cache(helper, service, self.path, iface)
            sub = _PropSub(helper, callback, initial)
            cache.subs.append(sub)
            subscription.attach(lambda: cache.release(helper, sub))
            try:
                await cache.ensure()
            except ServiceError:
                return  # the service is not there: the first values come when it is
            cache.deliver_first(sub)

        layer.service.post(lambda: layer.spawn(watch()))
        return subscription

    def on_signal(
        self, member: str, callback: SignalCallback, *, interface: str | None = None
    ) -> _Subscription:
        iface = self._interface(interface)
        helper, kind, layer = self._bus.helper, self._bus.kind, self._bus.helper.layer
        subscription = helper.subscription()

        async def watch() -> None:
            service = await layer.attach(helper, kind, self.name)
            key = MatchKey(service.name, self.path, iface, member)

            def received(message: Any) -> None:
                layer.timed(helper, callback, *unwrap(message.body))

            subscription.attach(await layer.service.bus(kind).subscribe(key, received))

        layer.service.post(lambda: layer.spawn(watch()))
        return subscription


class _Bus:
    def __init__(self, helper: _ModuleDBus, kind: BusKind) -> None:
        self.helper = helper
        self.kind: BusKind = kind

    def proxy(self, name: str, path: str, interface: str | None = None) -> _Proxy:
        self.helper.use(self.kind, name)
        return _Proxy(self, name, path, interface)

    def state(self, name: str) -> ServiceState:
        return self.helper.states.get((self.kind, name), ServiceState.UNAVAILABLE)

    def run[T](self, coro: Coroutine[Any, Any, T]) -> concurrent.futures.Future[T]:
        return self.helper.layer.service.submit(coro)

    def run_blocking[T](self, coro: Coroutine[Any, Any, T], timeout: float | None = None) -> T:
        layer = self.helper.layer
        ident = threading.get_ident()
        if ident == layer.loop_thread or ident == layer.service.thread_id:
            coro.close()
            where = "the loop thread" if ident == layer.loop_thread else "the dbus thread"
            raise BlockingCallError(
                f"module {self.helper.module}: a blocking D-Bus call on {where}; use Bus.run() "
                "or call it from a worker thread"
            )
        return self.run(coro).result(timeout)


class _ModuleDBus:
    """``ctx.dbus`` of one module."""

    def __init__(
        self,
        layer: Layer,
        module: str,
        send: Callable[[str, object], None],
        hooks: ServiceHooks,
    ) -> None:
        self.layer = layer
        self.module = module
        self.log = logger.bind(source=f"module:{module}")
        self._send = send
        self._hooks = hooks
        self.states: dict[tuple[BusKind, str], ServiceState] = {}
        self._buses = {"session": _Bus(self, "session"), "system": _Bus(self, "system")}
        self._used: set[tuple[BusKind, str]] = set()
        self._published: bool | None = None
        self._subscriptions: list[_Subscription] = []
        self._closed = False

    # -- what the module sees -------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return all(s is ServiceState.AVAILABLE for s in list(self.states.values()))

    def session(self) -> _Bus:
        return self._buses["session"]

    def system(self) -> _Bus:
        return self._buses["system"]

    # -- loop thread ----------------------------------------------------------------------------

    def use(self, kind: BusKind, name: str) -> None:
        """The module made a proxy: watch the name (once per module)."""
        if (kind, name) in self._used or self._closed:
            return
        self._used.add((kind, name))
        self.states.setdefault((kind, name), ServiceState.UNAVAILABLE)  # until it is read

        async def attach() -> None:
            await self.layer.attach(self, kind, name)

        self.layer.service.post(lambda: self.layer.spawn(attach()))

    def close(self) -> None:
        """The module stopped: every subscription and watch of it ends."""
        if self._closed:
            return
        self._closed = True
        self.layer.service.post(self._close_on_thread)

    # -- service thread -------------------------------------------------------------------------

    def subscription(self) -> _Subscription:
        sub = _Subscription(self)
        self._subscriptions.append(sub)
        return sub

    def service_state(self, service: _Service, state: ServiceState, hook: str | None) -> None:
        """The service's state, as this module sees it; ``available`` is sent when it changes."""
        if self._closed:
            return
        self.states[service.key] = state
        value = self.available
        if value != self._published:
            self._published = value
            self._send("available", value)
        if hook is not None:
            name = service.name
            self.layer.call_soon(lambda: self._run_hook(hook, name))

    def _run_hook(self, hook: str, name: str) -> None:  # loop thread
        if self._closed:
            return
        try:
            getattr(self._hooks, hook)(name)
        except Exception:
            self.log.opt(exception=True).error(f"on_service_{hook}({name!r}) raised")

    def _close_on_thread(self) -> None:
        for sub in self._subscriptions:
            sub._run()
        self._subscriptions.clear()
        for cache in [c for c in self.layer._caches.values() if self in c.users]:
            cache.release(self, None)
        for service in [s for s in self.layer._services.values() if self in s.listeners]:
            service.detach(self)
