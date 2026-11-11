"""Fake D-Bus services on a private bus, for every test of the service layer and the modules built
on it (M5 Brief, G10).

The real session and system buses are never touched: the daemon is ``dbus-daemon`` on a socket of
its own, and a fake service has a connection of its own on a thread of its own (never the layer's
connection), so a name that moves away, a service that restarts and a daemon that dies behave as
they do on a desktop.

``PrivateDaemon`` starts, stops and restarts the daemon on one address. ``FakeService`` owns a
well-known name and exports objects: each ``FakeObject`` has settable properties (a change emits
``PropertiesChanged``), methods with a handler, and signals. ``Monitor`` counts what clients send
the daemon (the match rules of a connection). ``FakeBus`` bundles a daemon, the thread the fakes
run on and the services made on it.
"""

from __future__ import annotations

import asyncio
import inspect
import shutil
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Coroutine, Iterator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from dbus_fast import Message, MessageType
from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, dbus_method, dbus_property, dbus_signal

HAVE_DAEMON = shutil.which("dbus-daemon") is not None

# No service directories: the daemon must never start a real service by activation, or a test of
# "no service" would find one.
_CONFIG = """<!DOCTYPE busconfig PUBLIC "-//freedesktop//DTD D-Bus Bus Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/dbus/1.0/busconfig.dtd">
<busconfig>
  <type>session</type>
  <listen>unix:path={socket}</listen>
  <auth>EXTERNAL</auth>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""


def wait_for(predicate: Callable[[], object], timeout: float = 3.0) -> bool:
    """Poll ``predicate`` until it is true or ``timeout`` seconds pass (never a fixed sleep)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return bool(predicate())


class PrivateDaemon:
    """A ``dbus-daemon`` on its own socket. ``restart`` brings it back on the same address."""

    def __init__(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="tess-bus-")
        self._socket = Path(self._tmp.name) / "bus.sock"
        self._config = Path(self._tmp.name) / "bus.conf"
        self._config.write_text(_CONFIG.format(socket=self._socket))
        self._process: subprocess.Popen[str] | None = None
        self.address = f"unix:path={self._socket}"

    def start(self) -> None:
        assert self._process is None, "already running"
        self._socket.unlink(missing_ok=True)
        self._process = subprocess.Popen(
            ["dbus-daemon", f"--config-file={self._config}", "--nofork", "--print-address=1"],
            stdout=subprocess.PIPE,
            text=True,
        )
        assert self._process.stdout is not None
        assert self._process.stdout.readline().strip(), "dbus-daemon printed no address"

    def stop(self) -> None:
        """Kill the daemon: every connection to it drops."""
        process, self._process = self._process, None
        if process is not None:
            process.kill()
            process.wait(5)

    def restart(self, pause: float = 0.0) -> None:
        self.stop()
        if pause:
            time.sleep(pause)
        self.start()

    def close(self) -> None:
        self.stop()
        self._tmp.cleanup()


class FakeThread:
    """The thread the fake services run on (an asyncio loop of its own)."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="fake-dbus", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def run[T](self, coro: Coroutine[Any, Any, T], timeout: float = 5.0) -> T:
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result(timeout)

    def close(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)
        self._thread.join(5)
        self.loop.close()


def _reap(bus: MessageBus) -> None:
    """Retrieve the disconnect future of a fake's connection, so a daemon that dies does not leave
    an "exception was never retrieved" at exit."""

    async def wait() -> None:
        try:
            await bus.wait_for_disconnect()
        except Exception:
            pass

    asyncio.ensure_future(wait())


def _method(name: str, ins: Sequence[str], out: str, fn: Callable[..., Any]) -> Any:
    impl: Callable[..., Any]
    if inspect.iscoroutinefunction(fn):

        async def impl_async(self: Any, *args: Any) -> Any:
            return await fn(*args)

        impl = impl_async
    else:

        def impl_sync(self: Any, *args: Any) -> Any:
            return fn(*args)

        impl = impl_sync
    params = [inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD)]
    params += [
        inspect.Parameter(f"a{i}", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=sig)
        for i, sig in enumerate(ins)
    ]
    impl.__signature__ = inspect.Signature(params, return_annotation=out or None)  # type: ignore[attr-defined]
    impl.__name__ = name
    return dbus_method(name=name)(impl)


def _signal(name: str, sig: str) -> Any:
    def impl(self: Any, *args: Any) -> Any:
        return list(args) if len(args) != 1 else args[0]

    params = [inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD)]
    params += [
        inspect.Parameter(f"a{i}", inspect.Parameter.POSITIONAL_OR_KEYWORD)
        for i in range(_count(sig))
    ]
    impl.__signature__ = inspect.Signature(params, return_annotation=sig)  # type: ignore[attr-defined]
    impl.__name__ = name
    return dbus_signal(name=name)(impl)


def _count(signature: str) -> int:
    """How many complete types a signature holds."""
    from dbus_fast import SignatureTree

    return len(SignatureTree(signature).types)


def _property(name: str, sig: str, writable: bool) -> Any:
    from dbus_fast import PropertyAccess

    def getter(self: Any) -> Any:
        return self._values[name]

    getter.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        [inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD)],
        return_annotation=sig,
    )
    getter.__name__ = name
    prop = dbus_property(
        access=PropertyAccess.READWRITE if writable else PropertyAccess.READ, name=name
    )(getter)
    if writable:

        def setter(self: Any, value: Any) -> None:
            self._values[name] = value

        setter.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
            [
                inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD),
                inspect.Parameter("value", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=sig),
            ]
        )
        setter.__name__ = name
        prop = prop.setter(setter)
    return prop


class FakeObject:
    """One interface at one path of a fake service.

    ``properties`` maps a name to ``(signature, value)``; ``methods`` a name to ``(in signatures,
    out signature, handler)`` (the handler gets the arguments and returns the reply; it may raise
    ``dbus_fast.DBusError``); ``signals`` a name to its signature. ``calls`` records
    ``(method, args)``.
    """

    def __init__(
        self,
        service: FakeService,
        path: str,
        interface: str,
        properties: Mapping[str, tuple[str, Any]] | None = None,
        methods: Mapping[str, tuple[Sequence[str], str, Callable[..., Any]]] | None = None,
        signals: Mapping[str, str] | None = None,
    ) -> None:
        self.service = service
        self.path = path
        self.interface = interface
        self.signatures = {k: v[0] for k, v in (properties or {}).items()}
        self.values: dict[str, Any] = {k: v[1] for k, v in (properties or {}).items()}
        self.calls: list[tuple[str, tuple[Any, ...]]] = []
        self._methods = dict(methods or {})
        self._signals = dict(signals or {})
        self._iface: ServiceInterface | None = None

    def _build(self) -> ServiceInterface:
        """A fresh interface object (one per connection: the old one belonged to a bus that is
        gone)."""
        ns: dict[str, Any] = {}
        for name, sig in self.signatures.items():
            ns[name] = _property(name, sig, writable=False)
        for name, (ins, out, handler) in self._methods.items():
            ns[name] = _method(name, ins, out, self._recorded(name, handler))
        for name, sig in self._signals.items():
            ns[name] = _signal(name, sig)
        cls = type("Fake_" + self.interface.replace(".", "_"), (ServiceInterface,), ns)
        iface = cls(self.interface)
        iface._values = self.values  # type: ignore[attr-defined]
        self._iface = iface
        return iface

    def _recorded(self, name: str, handler: Callable[..., Any]) -> Callable[..., Any]:
        if inspect.iscoroutinefunction(handler):

            async def run_async(*args: Any) -> Any:
                self.calls.append((name, args))
                return await handler(*args)

            return run_async

        def run(*args: Any) -> Any:
            self.calls.append((name, args))
            return handler(*args)

        return run

    def set(self, prop: str, value: Any, *, invalidate: bool = False) -> None:
        """Change a property and emit ``PropertiesChanged`` (``invalidate``: send the name in the
        invalidated list instead of the value)."""

        async def emit() -> None:
            self.values[prop] = value
            if self._iface is not None:
                if invalidate:
                    self._iface.emit_properties_changed({}, [prop])
                else:
                    self._iface.emit_properties_changed({prop: value})

        self.service.thread.run(emit())

    def silent_set(self, prop: str, value: Any) -> None:
        """Change a property without any signal (a service that does not emit changes)."""
        self.values[prop] = value

    def emit(self, signal: str, *args: Any) -> None:
        async def go() -> None:
            assert self._iface is not None, "the service is not up"
            getattr(self._iface, signal)(*args)

        self.service.thread.run(go())


class FakeService:
    """A well-known name with objects. ``up`` connects, exports and takes the name; ``down``
    gives the name up (it moves away); ``restart`` drops the connection and comes back (a service
    that crashed and started again); after a daemon restart, ``up`` makes it come back."""

    def __init__(self, daemon: PrivateDaemon, thread: FakeThread, name: str) -> None:
        self.daemon = daemon
        self.thread = thread
        self.name = name
        self.objects: list[FakeObject] = []
        self._bus: MessageBus | None = None

    def add(
        self,
        path: str,
        interface: str,
        properties: Mapping[str, tuple[str, Any]] | None = None,
        methods: Mapping[str, tuple[Sequence[str], str, Callable[..., Any]]] | None = None,
        signals: Mapping[str, str] | None = None,
    ) -> FakeObject:
        obj = FakeObject(self, path, interface, properties, methods, signals)
        self.objects.append(obj)
        return obj

    @property
    def unique_name(self) -> str | None:
        return self._bus.unique_name if self._bus is not None else None

    async def _up(self) -> None:
        if self._bus is None or not self._bus.connected:
            bus = MessageBus(bus_address=self.daemon.address)
            self._bus = await bus.connect()
            _reap(self._bus)
            for obj in self.objects:
                self._bus.export(obj.path, obj._build())
        await self._bus.request_name(self.name)

    def up(self) -> None:
        self.thread.run(self._up())

    async def _down(self) -> None:
        if self._bus is not None and self._bus.connected:
            await self._bus.release_name(self.name)

    def down(self) -> None:
        """Give the name up; the connection stays."""
        self.thread.run(self._down())

    async def _drop(self) -> None:
        bus, self._bus = self._bus, None
        if bus is not None:
            bus.disconnect()
            await asyncio.sleep(0)

    def drop(self) -> None:
        """Close the connection: the name goes with it."""
        self.thread.run(self._drop())

    def restart(self) -> None:
        self.drop()
        self.up()


class Monitor:
    """A monitor connection on the private bus: it records the method calls clients make to the
    bus daemon itself (``AddMatch``, ``RemoveMatch``), to count the rules a client holds."""

    def __init__(self, daemon: PrivateDaemon, thread: FakeThread) -> None:
        self.thread = thread
        self.daemon = daemon
        self.seen: list[tuple[str, str, str]] = []  # (sender, member, rule)
        self._bus: MessageBus | None = None

    async def _start(self) -> None:
        bus = await MessageBus(bus_address=self.daemon.address).connect()
        _reap(bus)
        rules = ["type='method_call',destination='org.freedesktop.DBus'"]
        reply = await bus.call(
            Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus.Monitoring",
                member="BecomeMonitor",
                signature="asu",
                body=[rules, 0],
            )
        )
        assert reply is not None and reply.message_type == MessageType.METHOD_RETURN, reply
        bus.add_message_handler(self._on_message)
        self._bus = bus

    def _on_message(self, message: Message) -> bool:
        if message.member in ("AddMatch", "RemoveMatch") and message.body:
            self.seen.append((message.sender or "", message.member, str(message.body[0])))
        # a monitor must not send anything: a truthy result means "handled", so dbus-fast does
        # not answer the calls it sees (the daemon would drop the monitor)
        return message.message_type == MessageType.METHOD_CALL

    def start(self) -> None:
        self.thread.run(self._start())

    def stop(self) -> None:
        if self._bus is not None:
            self._bus.disconnect()
            self._bus = None

    def added(self, sender: str | None, contains: str = "") -> list[str]:
        """The rules ``sender`` added and has not removed, that contain ``contains``."""
        held: list[str] = []
        for who, member, rule in list(self.seen):
            if who != sender:
                continue
            if member == "AddMatch":
                held.append(rule)
            elif rule in held:
                held.remove(rule)
        return [r for r in held if contains in r]


class FakeBus:
    """A private daemon, the thread the fake services run on, and the services made on it."""

    def __init__(self) -> None:
        self.daemon = PrivateDaemon()
        self.daemon.start()
        self.thread = FakeThread()
        self.services: list[FakeService] = []

    @property
    def address(self) -> str:
        return self.daemon.address

    def service(self, name: str) -> FakeService:
        service = FakeService(self.daemon, self.thread, name)
        self.services.append(service)
        return service

    def monitor(self) -> Monitor:
        monitor = Monitor(self.daemon, self.thread)
        monitor.start()
        return monitor

    def close(self) -> None:
        for service in self.services:
            try:
                service.drop()
            except Exception:
                pass
        self.thread.close()
        self.daemon.close()


@contextmanager
def fake_bus() -> Iterator[FakeBus]:
    bus = FakeBus()
    try:
        yield bus
    finally:
        bus.close()
