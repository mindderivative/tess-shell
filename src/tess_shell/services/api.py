"""What a module sees of the D-Bus service layer (D-Bus Service Layer > Python Contract).

Standard library only: the module host and a module author import these names, and neither may
import ``dbus_fast``. The implementation is ``tess_shell.services.layer``.

Threads. ``Bus.proxy``, ``Proxy.on_property_changed`` and ``Proxy.on_signal`` are plain functions
for the loop thread (they return at once; the work happens on the ``dbus`` service thread).
``Proxy.get`` and ``Proxy.call`` are coroutines that run on the service thread: start one with
``Bus.run`` (a future, any thread, never blocks) or ``Bus.run_blocking`` (any thread except the loop
thread and the service thread, where it raises :class:`BlockingCallError`). A callback given to
``on_property_changed`` or ``on_signal`` runs on the service thread: short, never blocking; it
calls ``ctx.send``, which crosses to the loop.
"""

from __future__ import annotations

import concurrent.futures
import enum
from collections.abc import Callable, Coroutine, Mapping, Sequence
from typing import Any, Protocol

CALL_TIMEOUT = 5.0  # seconds; every call has one


class ServiceState(enum.Enum):
    """What the layer knows of a service. ``UNAVAILABLE``: the well-known name has no owner (or
    the bus is not reachable)."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ServiceError(Exception):
    """A call failed. ``service`` is the bus name; ``name`` the D-Bus error name, if the service
    sent one."""

    def __init__(self, service: str, message: str, name: str = "") -> None:
        super().__init__(f"{service}: {message}")
        self.service = service
        self.detail = message  # without the service's name in front
        self.name = name


class ServiceTimeout(ServiceError):
    """The call did not finish within its timeout (default 5 s)."""


class ServiceUnavailable(ServiceError):
    """The service has no owner on the bus (``ServiceUnknown``, ``NameHasNoOwner``, ``NoReply``) or
    the bus is not reachable. The layer has set the service's state to ``UNAVAILABLE``."""

    state = ServiceState.UNAVAILABLE


class BlockingCallError(RuntimeError):
    """A blocking form was used on the loop thread (or on the service thread, where it would wait
    for itself)."""


PropertyCallback = Callable[[Mapping[str, Any]], None]
SignalCallback = Callable[..., None]


class Subscription(Protocol):
    def cancel(self) -> None:
        """Stop the callback. The match rule goes with the last subscriber. The shell also cancels
        every subscription of a module when the module stops."""


class Proxy(Protocol):
    """One object on a service: a bus name and a path, with an optional default interface."""

    async def get(self, prop: str, *, interface: str | None = None, fresh: bool = False) -> Any:
        """The value of a property. Read from the cache the layer keeps for the interface (filled
        by one ``GetAll`` when the interface is first used, kept current from
        ``PropertiesChanged``); ``fresh=True`` asks the service (for a property that does not emit
        changes). Plain Python values: a ``Variant`` is unwrapped."""
        ...

    async def call(
        self,
        method: str,
        args: Sequence[Any] = (),
        signature: str = "",
        *,
        interface: str | None = None,
        timeout: float = CALL_TIMEOUT,
    ) -> Any:
        """Call a method. ``signature`` is the D-Bus type string of ``args``. The result is the
        reply's one value, ``None`` for no value, or a tuple for several. Raises
        :class:`ServiceTimeout`, :class:`ServiceUnavailable` or :class:`ServiceError`."""
        ...

    async def set(
        self,
        prop: str,
        value: Any,
        signature: str,
        *,
        interface: str | None = None,
        timeout: float = CALL_TIMEOUT,
    ) -> None:
        """Write a property (``org.freedesktop.DBus.Properties.Set``); ``signature`` is the D-Bus
        type of the value. The cache follows from the service's ``PropertiesChanged``, not from
        this call. Raises as :meth:`call` does."""
        ...

    def on_property_changed(
        self, callback: PropertyCallback, *, interface: str | None = None, initial: bool = True
    ) -> Subscription:
        """``callback(changed)`` with a mapping of property name to value, on the service thread.
        The first call (unless ``initial=False``) holds every property, once the layer has read
        them; later calls hold what ``PropertiesChanged`` reports. When the service returns after
        it left the bus, the callback gets every property again (before ``on_service_found``)."""
        ...

    def on_signal(
        self, member: str, callback: SignalCallback, *, interface: str | None = None
    ) -> Subscription:
        """``callback(*body)`` for each signal of ``member`` from this object, on the service
        thread."""
        ...


class Bus(Protocol):
    def proxy(
        self, name: str, path: str, interface: str | None = None, *, optional: bool = False
    ) -> Proxy:
        """A proxy for the object ``path`` of the service ``name``. The layer watches ``name`` from
        now on (a well-known name): when its owner goes away the module gets
        ``on_service_lost(name)`` and ``available`` false, and ``on_service_found(name)`` with
        ``available`` true when an owner returns. An ``optional`` service (a value the module can
        do without) still gets the hooks, but does not count in ``available``, and its absence is
        only a debug line in the log."""
        ...

    def watch_prefix(
        self, prefix: str, on_added: Callable[[str], None], on_removed: Callable[[str], None]
    ) -> Subscription:
        """Follow every well-known name that starts with ``prefix`` (``org.mpris.MediaPlayer2.``):
        ``on_added(name)`` for each that has an owner now and for each that appears later,
        ``on_removed(name)`` when one goes. One ``ListNames`` at the start and one
        ``NameOwnerChanged`` rule, no polling; the callbacks run on the service thread. The names
        are not made services of the module: make a proxy for each with ``optional=True`` (a
        player may leave at any time without the module being unavailable). ``available`` stays
        true while the bus can be reached."""
        ...

    def forget(self, name: str) -> None:
        """Let go of a name the module made a proxy for (a player that left): its watch and its
        cached properties. Cancel the subscriptions on it first."""
        ...

    def state(self, name: str) -> ServiceState:
        """The state of a service this module has made a proxy for (any thread)."""
        ...

    def run[T](self, coro: Coroutine[Any, Any, T]) -> concurrent.futures.Future[T]:
        """Run ``coro`` on the service thread. Never blocks; any thread. An exception that nobody
        reads from the future is logged with the module's name."""
        ...

    def run_blocking[T](self, coro: Coroutine[Any, Any, T], timeout: float | None = None) -> T:
        """Run ``coro`` on the service thread and wait for it. Raises :class:`BlockingCallError`
        on the loop thread and on the service thread. ``timeout`` is for the whole wait; the
        calls inside have their own."""
        ...


class ModuleDBus(Protocol):
    """``ctx.dbus``. Nothing connects until a proxy is used; the system bus opens on the first
    use that needs it."""

    @property
    def available(self) -> bool:
        """True while every service this module made a proxy for has an owner (any thread). A
        service that is not read yet counts as absent, so this is false right after ``proxy()``;
        the layer sends ``available`` with ``ctx.send`` each time this value changes (the
        empty-state convention: ``Children`` wrap in ``If: available``). A module that also
        needs a condition of its own (a battery that is not present) sends a key of its own and
        combines the two in its layout; it does not send ``available`` itself."""
        ...

    def session(self) -> Bus: ...

    def system(self) -> Bus: ...

    def close(self) -> None:
        """End every subscription and watch of the module (the shell calls it when the module
        stops)."""
        ...


class ServiceHooks(Protocol):
    """The module's hooks, called on the loop thread."""

    def lost(self, name: str) -> None: ...

    def found(self, name: str) -> None: ...


class DBusPort(Protocol):
    """What the module host needs of the layer: one helper per module."""

    def for_module(
        self,
        module: str,
        send: Callable[[str, object], None],
        hooks: ServiceHooks,
    ) -> ModuleDBus: ...
