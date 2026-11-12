"""The D-Bus service layer against fake services on a private bus (D-Bus Service Layer; M5 Brief,
A1 to A6).

Every bus here is a private ``dbus-daemon`` (tests/fake_dbus.py); the fake services have their own
connections and thread. The test thread plays the loop thread: the layer's ``call_soon`` queues a
function that the test runs when it drains the pump, so a hook that runs on the wrong thread shows.
"""

from __future__ import annotations

import asyncio
import queue
import threading
import time
from collections.abc import Callable, Iterator, Mapping
from typing import Any

import pytest
from dbus_fast import DBusError
from loguru import logger

from tess_shell.services.api import (
    BlockingCallError,
    ServiceError,
    ServiceState,
    ServiceTimeout,
    ServiceUnavailable,
)
from tess_shell.services.bus import BACKOFF, MatchKey, ServiceThread
from tess_shell.services.layer import SLOW_CALLBACK, Layer
from tests.fake_dbus import HAVE_DAEMON, FakeBus, FakeObject, FakeService, fake_bus, wait_for

pytestmark = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")

NAME = "org.test.Battery"
PATH = "/org/test/Battery"
IFACE = "org.test.Battery"


class Pump:
    """The loop thread: ``call_soon`` queues, the test thread runs the queue."""

    def __init__(self) -> None:
        self._queue: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()

    def call_soon(self, fn: Callable[[], None]) -> None:
        self._queue.put(fn)

    def drain(self) -> None:
        while True:
            try:
                fn = self._queue.get_nowait()
            except queue.Empty:
                return
            fn()

    def wait(self, predicate: Callable[[], object], timeout: float = 5.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.drain()
            if predicate():
                return True
            time.sleep(0.005)
        self.drain()
        return bool(predicate())


class Hooks:
    def __init__(self) -> None:
        self.lost: list[tuple[str, int]] = []
        self.found: list[tuple[str, int]] = []

    def lost_(self, name: str) -> None:
        self.lost.append((name, threading.get_ident()))

    def found_(self, name: str) -> None:
        self.found.append((name, threading.get_ident()))


class _HookPort:
    def __init__(self, hooks: Hooks) -> None:
        self._hooks = hooks

    def lost(self, name: str) -> None:
        self._hooks.lost_(name)

    def found(self, name: str) -> None:
        self._hooks.found_(name)


class Mod:
    """A module: what it sent, what its hooks saw, what its property callback got."""

    def __init__(self, rig: Rig, name: str) -> None:
        self.name = name
        self.sent: list[tuple[str, object]] = []
        self.hooks = Hooks()
        self.changes: list[Mapping[str, Any]] = []
        self.dbus = rig.layer.for_module(
            name, lambda k, v: self.sent.append((k, v)), _HookPort(self.hooks)
        )

    def available(self) -> list[object]:
        return [v for k, v in self.sent if k == "available"]


class Rig:
    def __init__(self, bus: FakeBus, service: FakeService, obj: FakeObject) -> None:
        self.bus, self.fake, self.obj = bus, service, obj
        self.service = ServiceThread(bus.address)
        self.service.start()
        self.pump = Pump()
        self.now = 1000.0  # the layer's clock, for the once-a-minute warnings
        self.layer = Layer(self.service, self.pump.call_soon, clock=lambda: self.now)
        self.mods: list[Mod] = []
        self.warnings: list[str] = []
        self._sink = logger.add(lambda m: self.warnings.append(str(m)), level="WARNING")

    def module(self, name: str = "Battery") -> Mod:
        mod = Mod(self, name)
        self.mods.append(mod)
        return mod

    def unique_name(self) -> str:
        conn = self.service.session._conn
        assert conn is not None and conn.unique_name is not None
        return conn.unique_name

    def close(self) -> None:
        for mod in self.mods:
            mod.dbus.close()
        logger.remove(self._sink)
        self.service.stop()


async def _slow() -> None:
    await asyncio.sleep(1.0)


def _boom() -> None:
    raise DBusError("org.test.Error.Boom", "it broke")


@pytest.fixture
def rig() -> Iterator[Rig]:
    with fake_bus() as bus:
        fake = bus.service(NAME)
        obj = fake.add(
            PATH,
            IFACE,
            properties={"Percentage": ("d", 50.0), "State": ("u", 1)},
            methods={
                "Echo": (["s"], "s", lambda s: s),
                "Slow": ([], "", _slow),
                "Boom": ([], "", _boom),
                "Two": ([], "su", lambda: ["a", 2]),
                "Nothing": ([], "", lambda: None),
            },
            signals={"Ping": "s"},
        )
        fake.up()
        r = Rig(bus, fake, obj)
        try:
            yield r
        finally:
            r.close()


def run(rig: Rig, coro: Any, timeout: float = 5.0) -> Any:
    return rig.service.submit(coro).result(timeout)


# -- the thread, calls and errors ---------------------------------------------------------------


def test_the_service_thread_is_called_dbus(rig: Rig) -> None:
    async def name() -> str:
        return threading.current_thread().name

    assert run(rig, name()) == "dbus"
    assert rig.service.thread_id != threading.get_ident()


def test_a_call_runs_on_the_service_thread_and_returns_plain_values(rig: Rig) -> None:
    bus = rig.module().dbus.session()
    proxy = bus.proxy(NAME, PATH, IFACE)
    assert run(rig, proxy.call("Echo", ["hi"], "s")) == "hi"
    assert run(rig, proxy.call("Two")) == ("a", 2)
    assert run(rig, proxy.call("Nothing")) is None
    with pytest.raises(ServiceError) as caught:
        run(rig, proxy.call("Boom"))
    assert caught.value.name == "org.test.Error.Boom" and not isinstance(
        caught.value, ServiceUnavailable
    )


def test_arguments_need_a_signature(rig: Rig) -> None:
    proxy = rig.module().dbus.session().proxy(NAME, PATH, IFACE)
    with pytest.raises(ValueError, match="signature"):
        run(rig, proxy.call("Echo", ["hi"]))
    with pytest.raises(ValueError, match="interface"):
        run(rig, rig.module("B").dbus.session().proxy(NAME, PATH).call("Echo", ["x"], "s"))


def test_a_call_to_a_name_with_no_owner_is_unavailable_with_one_warning(rig: Rig) -> None:
    mod = rig.module()
    bus = mod.dbus.session()
    proxy = bus.proxy("org.test.Nobody", PATH, IFACE)
    started = time.monotonic()
    with pytest.raises(ServiceUnavailable) as caught:
        run(rig, proxy.call("Echo", ["x"], "s"))
    assert time.monotonic() - started < 5.0  # within the call timeout, not after it
    assert caught.value.state is ServiceState.UNAVAILABLE
    with pytest.raises(ServiceUnavailable):
        run(rig, proxy.call("Echo", ["x"], "s"))
    assert wait_for(lambda: bus.state("org.test.Nobody") is ServiceState.UNAVAILABLE)
    assert sum("org.test.Nobody" in w for w in rig.warnings) == 1  # one warning a minute
    assert mod.available() == [False]
    assert not mod.dbus.available
    rig.now += 61  # a minute later it may warn again
    with pytest.raises(ServiceUnavailable):
        run(rig, proxy.call("Echo", ["x"], "s"))
    assert sum("org.test.Nobody" in w for w in rig.warnings) == 2


def test_a_timeout_raises_service_timeout_and_warns_once_a_minute(rig: Rig) -> None:
    mod = rig.module()
    proxy = mod.dbus.session().proxy(NAME, PATH, IFACE)
    for _ in range(2):
        started = time.monotonic()
        with pytest.raises(ServiceTimeout):
            run(rig, proxy.call("Slow", timeout=0.2))
        assert 0.15 < time.monotonic() - started < 0.9
    assert sum("no reply" in w for w in rig.warnings) == 1
    rig.now += 61
    with pytest.raises(ServiceTimeout):
        run(rig, proxy.call("Slow", timeout=0.2))
    assert sum("no reply" in w for w in rig.warnings) == 2
    assert proxy.interface == IFACE and mod.dbus.available  # a timeout is not "gone"


def test_the_default_timeout_is_five_seconds() -> None:
    import inspect

    from tess_shell.services.api import CALL_TIMEOUT
    from tess_shell.services.layer import _Proxy

    assert CALL_TIMEOUT == 5.0
    assert inspect.signature(_Proxy.call).parameters["timeout"].default == CALL_TIMEOUT


# -- the blocking guard -------------------------------------------------------------------------


def test_a_blocking_call_on_the_loop_thread_raises(rig: Rig) -> None:
    bus = rig.module().dbus.session()
    proxy = bus.proxy(NAME, PATH, IFACE)
    with _no_unawaited_warning(), pytest.raises(BlockingCallError, match="loop thread"):
        bus.run_blocking(proxy.call("Echo", ["x"], "s"))


class _no_unawaited_warning:
    """The guard closes the coroutine it refuses, so Python has nothing to complain about."""

    def __enter__(self) -> None:
        import warnings

        self._ctx = warnings.catch_warnings()
        self._ctx.__enter__()
        warnings.simplefilter("error", RuntimeWarning)

    def __exit__(self, *exc: Any) -> None:
        self._ctx.__exit__(*exc)


def test_a_blocking_call_on_a_worker_thread_works(rig: Rig) -> None:
    bus = rig.module().dbus.session()
    proxy = bus.proxy(NAME, PATH, IFACE)
    out: list[Any] = []

    def worker() -> None:
        out.append(bus.run_blocking(proxy.call("Echo", ["w"], "s"), timeout=5))

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join(10)
    assert out == ["w"]


def test_a_blocking_call_on_the_service_thread_raises_instead_of_waiting_for_itself(
    rig: Rig,
) -> None:
    bus = rig.module().dbus.session()
    proxy = bus.proxy(NAME, PATH, IFACE)

    async def inside() -> None:
        bus.run_blocking(proxy.call("Echo", ["x"], "s"))

    with pytest.raises(BlockingCallError, match="dbus thread"):
        run(rig, inside())


def test_run_gives_a_future_and_never_blocks(rig: Rig) -> None:
    bus = rig.module().dbus.session()
    proxy = bus.proxy(NAME, PATH, IFACE)
    future = bus.run(proxy.call("Echo", ["f"], "s"))
    assert future.result(5) == "f"


# -- properties, the cache and the match rules --------------------------------------------------


def test_properties_are_read_once_and_follow_the_signals(rig: Rig) -> None:
    mod = rig.module()
    proxy = mod.dbus.session().proxy(NAME, PATH, IFACE)
    sub = proxy.on_property_changed(mod.changes.append)
    assert wait_for(lambda: len(mod.changes) == 1)
    assert mod.changes[0] == {"Percentage": 50.0, "State": 1}  # the first set: everything
    cache = rig.layer._caches[("session", NAME, PATH, IFACE)]
    assert cache.reads == 1
    rig.obj.set("Percentage", 70.0)
    assert wait_for(lambda: len(mod.changes) == 2)
    assert mod.changes[1] == {"Percentage": 70.0}  # then what changed
    assert run(rig, proxy.get("Percentage")) == 70.0  # from the cache
    assert cache.reads == 1  # signals only: no second GetAll
    rig.obj.silent_set("State", 4)  # a service that sends no signal for it
    assert run(rig, proxy.get("State")) == 1
    assert run(rig, proxy.get("State", fresh=True)) == 4
    assert run(rig, proxy.get("State")) == 4  # a fresh read refreshes the cache
    with pytest.raises(ServiceError, match="no property"):
        run(rig, proxy.get("Nope"))
    sub.cancel()


def test_an_invalidated_property_is_read_again(rig: Rig) -> None:
    mod = rig.module()
    proxy = mod.dbus.session().proxy(NAME, PATH, IFACE)
    proxy.on_property_changed(mod.changes.append)
    assert wait_for(lambda: len(mod.changes) == 1)
    rig.obj.silent_set("Percentage", 33.0)
    rig.obj.set("Percentage", 33.0, invalidate=True)
    assert wait_for(lambda: len(mod.changes) >= 2)
    assert mod.changes[-1]["Percentage"] == 33.0
    assert rig.layer._caches[("session", NAME, PATH, IFACE)].reads == 2


def test_initial_false_skips_the_first_set(rig: Rig) -> None:
    mod = rig.module()
    proxy = mod.dbus.session().proxy(NAME, PATH, IFACE)
    proxy.on_property_changed(mod.changes.append, initial=False)
    assert wait_for(lambda: ("session", NAME, PATH, IFACE) in rig.layer._caches)
    assert wait_for(lambda: rig.layer._caches[("session", NAME, PATH, IFACE)].loaded)
    time.sleep(0.05)
    assert mod.changes == []
    rig.obj.set("State", 2)
    assert wait_for(lambda: mod.changes == [{"State": 2}])


def test_a_signal_reaches_the_callback_with_plain_values(rig: Rig) -> None:
    mod = rig.module()
    got: list[tuple[Any, ...]] = []
    sub = mod.dbus.session().proxy(NAME, PATH, IFACE).on_signal("Ping", lambda *a: got.append(a))
    assert wait_for(lambda: rig.service.session.rules)
    assert wait_for(lambda: any("Ping" in r for r in rig.service.session.rules))
    rig.obj.emit("Ping", "hello")
    assert wait_for(lambda: got == [("hello",)])
    sub.cancel()
    assert wait_for(lambda: not any("Ping" in r for r in rig.service.session.rules))
    rig.obj.emit("Ping", "again")
    time.sleep(0.1)
    assert got == [("hello",)]


def test_two_modules_subscribing_to_the_same_signal_add_one_match_rule(rig: Rig) -> None:
    monitor = rig.bus.monitor()
    try:
        a, b = rig.module("A"), rig.module("B")
        got_a: list[Any] = []
        got_b: list[Any] = []
        sub_a = a.dbus.session().proxy(NAME, PATH, IFACE).on_signal("Ping", got_a.append)
        sub_b = b.dbus.session().proxy(NAME, PATH, IFACE).on_signal("Ping", got_b.append)
        pa = a.dbus.session().proxy(NAME, PATH, IFACE)
        pb = b.dbus.session().proxy(NAME, PATH, IFACE)
        pa.on_property_changed(a.changes.append)
        pb.on_property_changed(b.changes.append)
        assert wait_for(lambda: a.changes and b.changes)
        # on the daemon: what this client asked it to match
        me = rig.unique_name()
        assert wait_for(lambda: len(monitor.added(me, "member='Ping'")) >= 1)
        time.sleep(0.1)  # a second AddMatch would be here by now
        assert len(monitor.added(me, "member='Ping'")) == 1
        assert len(monitor.added(me, "member='PropertiesChanged'")) == 1
        assert len(monitor.added(me, "member='NameOwnerChanged'")) == 1  # one per watched name
        # on the connection: the layer's own table says the same
        rules = rig.service.session.rules
        assert sum("member='Ping'" in r for r in rules) == 1
        assert sum("member='PropertiesChanged'" in r for r in rules) == 1
        rig.obj.emit("Ping", "x")
        assert wait_for(lambda: got_a == ["x"] and got_b == ["x"])  # both modules hear it
        sub_a.cancel()
        time.sleep(0.1)
        assert len(monitor.added(me, "member='Ping'")) == 1  # b still listens: the rule stays
        sub_b.cancel()
        assert wait_for(lambda: monitor.added(me, "member='Ping'") == [])  # the last one goes
    finally:
        monitor.stop()


def test_a_module_that_stops_drops_its_rules_and_watch(rig: Rig) -> None:
    monitor = rig.bus.monitor()
    try:
        mod = rig.module()
        mod.dbus.session().proxy(NAME, PATH, IFACE).on_property_changed(mod.changes.append)
        me_ready = wait_for(lambda: mod.changes)
        assert me_ready
        me = rig.unique_name()
        assert len(monitor.added(me)) == 2  # NameOwnerChanged and PropertiesChanged
        mod.dbus.close()
        assert wait_for(lambda: monitor.added(me) == [])
        assert not rig.layer._services and not rig.layer._caches
        rig.obj.set("Percentage", 1.0)
        time.sleep(0.1)
        assert len(mod.changes) == 1
    finally:
        monitor.stop()


def test_no_module_can_request_a_bus_name_through_the_helper(rig: Rig) -> None:
    from typing import get_protocol_members

    from tess_shell.services import api

    # what a module is promised: no call that takes a name, exports an object or owns anything
    assert get_protocol_members(api.ModuleDBus) == {"available", "close", "session", "system"}
    assert get_protocol_members(api.Bus) == {"proxy", "run", "run_blocking", "state"}
    assert get_protocol_members(api.Proxy) == {
        "call",
        "get",
        "on_property_changed",
        "on_signal",
        "set",
    }
    # and what it gets is no more than that: no attribute that reaches the connection
    mod = rig.module()
    bus = mod.dbus.session()
    proxy = bus.proxy(NAME, PATH, IFACE)
    for thing in (mod.dbus, bus, proxy):
        names = {n.lower() for n in dir(thing)}
        assert not any(
            word in n for n in names for word in ("request_name", "release_name", "export", "conn")
        )


# -- the system bus is lazy ---------------------------------------------------------------------


def test_the_system_bus_opens_on_first_use_only() -> None:
    with fake_bus() as session, fake_bus() as system:
        fake = system.service("org.test.Sys")
        fake.add("/s", "org.test.Sys", properties={"V": ("i", 7)})
        fake.up()
        service = ServiceThread(session.address, system.address)
        service.start()
        layer = Layer(service, Pump().call_soon)
        try:
            mod = layer.for_module("M", lambda k, v: None, _HookPort(Hooks()))
            mod.session()  # asking for a bus object connects nothing
            mod.system().proxy("org.test.Sys", "/s", "org.test.Sys")
            assert wait_for(lambda: service.system.connects == 1)
            assert service.session.connects == 0  # and the session bus stays closed too
            assert service.session.connected is False
            value = service.submit(
                mod.system().proxy("org.test.Sys", "/s", "org.test.Sys").get("V")
            )
            assert value.result(5) == 7
        finally:
            service.stop()


def test_an_unreachable_system_bus_is_a_state_not_a_crash() -> None:
    with fake_bus() as session:
        service = ServiceThread(session.address, "unix:path=/nonexistent/system.sock")
        service.start()
        pump = Pump()
        layer = Layer(service, pump.call_soon)
        sent: list[tuple[str, object]] = []
        try:
            mod = layer.for_module("M", lambda k, v: sent.append((k, v)), _HookPort(Hooks()))
            proxy = mod.system().proxy("org.test.Sys", "/s", "org.test.Sys")
            with pytest.raises(ServiceUnavailable):
                service.submit(proxy.call("X")).result(5)
            assert wait_for(lambda: ("available", False) in sent)
            assert not mod.available
        finally:
            service.stop()


# -- a service that leaves and returns ----------------------------------------------------------


def test_a_service_that_leaves_gives_lost_and_unavailable_and_returns_found(rig: Rig) -> None:
    mod = rig.module()
    bus = mod.dbus.session()
    proxy = bus.proxy(NAME, PATH, IFACE)
    proxy.on_property_changed(mod.changes.append)
    assert wait_for(lambda: mod.changes and mod.available() == [True])
    assert bus.state(NAME) is ServiceState.AVAILABLE and mod.dbus.available
    rig.fake.down()  # the name moves away
    assert rig.pump.wait(lambda: mod.hooks.lost)
    assert mod.hooks.lost == [(NAME, threading.get_ident())]  # on the loop thread
    assert mod.available() == [True, False]
    assert bus.state(NAME) is ServiceState.UNAVAILABLE and not mod.dbus.available
    with pytest.raises(ServiceUnavailable):  # a read does not return the stale value
        run(rig, proxy.get("Percentage"))
    rig.obj.silent_set("Percentage", 99.0)  # it changed while it was away
    rig.fake.up()  # and comes back
    assert rig.pump.wait(lambda: mod.hooks.found)
    assert mod.hooks.found == [(NAME, threading.get_ident())]
    assert mod.available() == [True, False, True]
    assert mod.changes[-1] == {"Percentage": 99.0, "State": 1}  # everything again, before the hook
    assert run(rig, proxy.get("Percentage")) == 99.0
    rig.obj.set("Percentage", 98.0)  # and the signals work again
    assert wait_for(lambda: mod.changes[-1] == {"Percentage": 98.0})
    assert mod.hooks.lost.__len__() == 1 and mod.hooks.found.__len__() == 1


def test_a_service_that_restarts_recovers_through_the_hooks(rig: Rig) -> None:
    mod = rig.module()
    proxy = mod.dbus.session().proxy(NAME, PATH, IFACE)
    proxy.on_property_changed(mod.changes.append)
    assert wait_for(lambda: mod.changes)
    rig.fake.drop()  # the process died: its connection closed
    assert rig.pump.wait(lambda: mod.hooks.lost)
    rig.obj.silent_set("Percentage", 12.0)
    rig.fake.up()
    assert rig.pump.wait(lambda: mod.hooks.found)
    assert mod.changes[-1]["Percentage"] == 12.0
    assert mod.dbus.available


def test_a_module_with_two_services_is_available_only_while_both_are(rig: Rig) -> None:
    other = rig.bus.service("org.test.Other")
    other.add("/o", "org.test.Other", properties={"V": ("i", 1)})
    other.up()
    mod = rig.module()
    bus = mod.dbus.session()
    bus.proxy(NAME, PATH, IFACE).on_property_changed(mod.changes.append)
    bus.proxy("org.test.Other", "/o", "org.test.Other").on_property_changed(mod.changes.append)
    # a service that is not read yet counts as absent: the module is available when both are there
    assert wait_for(lambda: mod.available()[-1:] == [True])
    sent = len(mod.available())
    other.down()
    assert wait_for(lambda: mod.available()[sent:] == [False])
    other.up()
    assert wait_for(lambda: mod.available()[sent:] == [False, True])


def test_a_service_missing_at_start_gives_its_first_values_when_it_appears() -> None:
    with fake_bus() as bus:
        fake = bus.service(NAME)
        obj = fake.add(PATH, IFACE, properties={"Percentage": ("d", 5.0)})
        service = ServiceThread(bus.address)
        service.start()
        pump = Pump()
        layer = Layer(service, pump.call_soon)
        hooks, changes = Hooks(), []
        sent: list[tuple[str, object]] = []
        try:
            mod = layer.for_module("M", lambda k, v: sent.append((k, v)), _HookPort(hooks))
            mod.session().proxy(NAME, PATH, IFACE).on_property_changed(changes.append)
            assert wait_for(lambda: ("available", False) in sent)
            assert changes == [] and hooks.lost == []  # absent from the start is not a "loss"
            fake.up()
            assert pump.wait(lambda: hooks.found)
            assert changes == [{"Percentage": 5.0}] and sent[-1] == ("available", True)
            obj.set("Percentage", 6.0)
            assert wait_for(lambda: changes[-1] == {"Percentage": 6.0})
        finally:
            service.stop()


# -- the bus daemon restarts --------------------------------------------------------------------


def fast_sleep(service: ServiceThread, delays: list[float]) -> None:
    async def sleep(seconds: float) -> None:
        delays.append(seconds)
        await asyncio.sleep(0.02)

    service.session._sleep = sleep


def test_killing_and_restarting_the_bus_daemon_brings_the_layer_back(rig: Rig) -> None:
    delays: list[float] = []
    fast_sleep(rig.service, delays)
    mod = rig.module()
    proxy = mod.dbus.session().proxy(NAME, PATH, IFACE)
    got: list[tuple[Any, ...]] = []
    proxy.on_signal("Ping", lambda *a: got.append(a))
    proxy.on_property_changed(mod.changes.append)
    assert wait_for(lambda: mod.changes)
    reconnected: list[str] = []

    async def hook(conn: Any) -> None:  # where the owner of the shell's own name asks for it again
        reconnected.append(conn.unique_name)

    rig.service.submit(_register(rig, hook)).result(5)
    first = rig.service.session.connects
    rig.bus.daemon.restart()
    assert rig.pump.wait(lambda: mod.hooks.lost)  # the connection dropped: the services are gone
    rig.obj.silent_set("Percentage", 21.0)
    rig.fake.up()  # the fake service reconnects to the new daemon
    assert rig.pump.wait(lambda: mod.hooks.found, 10)
    assert rig.service.session.connects == first + 1
    assert reconnected and delays[0] == BACKOFF[0]
    assert mod.changes[-1]["Percentage"] == 21.0  # read again on the new connection
    rig.obj.set("Percentage", 22.0)  # the rules were put back: signals arrive again
    assert wait_for(lambda: mod.changes[-1] == {"Percentage": 22.0})
    rig.obj.emit("Ping", "back")
    assert wait_for(lambda: got == [("back",)])
    assert run(rig, proxy.call("Echo", ["ok"], "s")) == "ok"
    assert mod.dbus.available and mod.available()[-1] is True


async def _register(rig: Rig, hook: Any) -> None:
    rig.service.session.on_reconnect(hook)


def test_the_reconnect_back_off_is_1_2_4_8_16_then_30_seconds(rig: Rig) -> None:
    assert BACKOFF == (1.0, 2.0, 4.0, 8.0, 16.0, 30.0)
    delays: list[float] = []
    fast_sleep(rig.service, delays)
    mod = rig.module()
    mod.dbus.session().proxy(NAME, PATH, IFACE).on_property_changed(mod.changes.append)
    assert wait_for(lambda: mod.changes)
    rig.bus.daemon.stop()  # the bus stays away
    assert wait_for(lambda: len(delays) >= 8, 10)
    assert delays[:8] == [1.0, 2.0, 4.0, 8.0, 16.0, 30.0, 30.0, 30.0]
    assert not rig.service.session.connected
    rig.bus.daemon.start()  # it comes back: the next attempt takes it
    assert wait_for(lambda: rig.service.session.connected, 10)
    rig.fake.up()
    assert rig.pump.wait(lambda: mod.hooks.found, 10)


def test_a_bus_that_was_never_reachable_is_retried_when_something_depends_on_it() -> None:
    with fake_bus() as bus:
        bus.daemon.stop()
        service = ServiceThread(bus.address)
        service.start()
        delays: list[float] = []
        fast_sleep(service, delays)
        pump = Pump()
        layer = Layer(service, pump.call_soon)
        hooks = Hooks()
        try:
            mod = layer.for_module("M", lambda k, v: None, _HookPort(hooks))
            mod.session().proxy(NAME, PATH, IFACE)
            assert wait_for(lambda: len(delays) >= 2)
            bus.daemon.start()
            fake = bus.service(NAME)
            fake.add(PATH, IFACE, properties={"Percentage": ("d", 1.0)})
            fake.up()
            assert pump.wait(lambda: hooks.found, 10)
        finally:
            service.stop()


# -- callbacks: exceptions, the guard and the measured times ------------------------------------


def test_a_callback_that_raises_is_logged_with_the_module_and_the_layer_goes_on(rig: Rig) -> None:
    mod = rig.module("Greedy")
    errors: list[str] = []
    sources: list[str] = []

    def collect(message: Any) -> None:
        errors.append(message.record["message"])
        sources.append(message.record["extra"].get("source", "").removeprefix("module:"))

    sink = logger.add(collect, level="ERROR")

    def bad(values: dict[str, Any]) -> None:
        raise RuntimeError("oops")

    try:
        mod.dbus.session().proxy(NAME, PATH, IFACE).on_property_changed(bad)
        assert wait_for(lambda: any("a D-Bus callback raised" in e for e in errors))
        assert "Greedy" in sources
        other = rig.module("Fine")
        other.dbus.session().proxy(NAME, PATH, IFACE).on_property_changed(other.changes.append)
        assert wait_for(lambda: other.changes)
    finally:
        logger.remove(sink)


def test_a_callback_over_50_ms_is_logged_with_the_module_name(rig: Rig) -> None:
    assert SLOW_CALLBACK == 0.05
    mod = rig.module("Slowpoke")

    def slow(values: dict[str, Any]) -> None:
        time.sleep(0.08)

    mod.dbus.session().proxy(NAME, PATH, IFACE).on_property_changed(slow)
    assert wait_for(lambda: any("Slowpoke" in w and "took" in w for w in rig.warnings))
    count, p50, p99, worst = rig.layer.callback_summary("Slowpoke")
    assert count >= 1 and worst >= 0.08


def test_measured_callback_times(rig: Rig, capsys: pytest.CaptureFixture[str]) -> None:
    """Real callback times on the service thread: a callback that only copies a value to a list
    (what ``ctx.send`` costs the module besides the queue)."""
    mod = rig.module("Meter")
    sent: list[Any] = []
    mod.dbus.session().proxy(NAME, PATH, IFACE).on_property_changed(
        lambda values: sent.append(dict(values))
    )
    assert wait_for(lambda: sent)
    n = 300
    for i in range(n):
        rig.obj.set("Percentage", float(i))
    assert wait_for(lambda: len(sent) >= n, 10)
    count, p50, p99, worst = rig.layer.callback_summary("Meter")
    with capsys.disabled():
        print(
            f"\ncallback times: n={count} p50={p50 * 1e6:.1f} us p99={p99 * 1e6:.1f} us "
            f"max={worst * 1e6:.1f} us"
        )
    assert count >= n and p99 < 0.001  # the 1 ms budget of a callback's own work


def test_match_key_rules() -> None:
    key = MatchKey("org.x", "/p", "org.x.I", "Sig", "arg")
    assert key.rule() == (
        "type='signal',sender='org.x',path='/p',interface='org.x.I',member='Sig',arg0='arg'"
    )
    assert MatchKey(None, None, "i", "m").rule() == "type='signal',interface='i',member='m'"


# -- M5b additions: set, optional services, the log level of an absent service ------------------


def test_set_writes_a_property_and_the_cache_follows_the_services_signal(rig: Rig) -> None:
    other = rig.bus.service("org.test.Writable")
    obj = other.add("/w", "org.test.Writable", properties={"Level": ("i", 1)}, writable=["Level"])
    other.up()
    mod = rig.module()
    proxy = mod.dbus.session().proxy("org.test.Writable", "/w", "org.test.Writable")
    proxy.on_property_changed(mod.changes.append)
    assert wait_for(lambda: mod.changes == [{"Level": 1}])
    run(rig, proxy.set("Level", 7, "i"))
    assert obj.sets == [("Level", 7)]
    assert wait_for(lambda: mod.changes[-1] == {"Level": 7})
    assert run(rig, proxy.get("Level")) == 7
    # a property the service does not let a client write is an error, not a crash
    ro = rig.module("Other").dbus.session().proxy(NAME, PATH, IFACE)
    with pytest.raises(ServiceError):
        run(rig, ro.set("Percentage", 1.0, "d"))


def test_an_optional_service_is_left_out_of_available_and_logs_at_debug(rig: Rig) -> None:
    mod = rig.module()
    bus = mod.dbus.session()
    bus.proxy(NAME, PATH, IFACE).on_property_changed(mod.changes.append)
    bus.proxy("org.test.Optional", "/o", "org.test.Optional", optional=True).on_property_changed(
        mod.changes.append
    )
    assert wait_for(
        lambda: mod.available()[-1:] == [True]
    )  # the absent optional one does not count
    assert mod.dbus.available
    assert bus.state("org.test.Optional") is ServiceState.UNAVAILABLE
    assert rig.warnings == []
    other = rig.bus.service("org.test.Optional")
    other.add("/o", "org.test.Optional", properties={"V": ("i", 1)})
    other.up()
    assert rig.pump.wait(lambda: mod.hooks.found)  # the hooks still come for it
    assert mod.hooks.found[-1][0] == "org.test.Optional"
    other.down()
    assert rig.pump.wait(lambda: mod.hooks.lost)
    assert mod.dbus.available  # the optional service leaving changes nothing for the module
    assert rig.warnings == []  # and it is an info line, not a warning


def test_a_required_service_that_leaves_is_one_warning_and_one_that_is_absent_is_info(
    rig: Rig,
) -> None:
    mod = rig.module()
    bus = mod.dbus.session()
    bus.proxy(NAME, PATH, IFACE).on_property_changed(mod.changes.append)
    bus.proxy("org.test.Nobody", "/n", "org.test.Nobody").on_property_changed(mod.changes.append)
    assert wait_for(lambda: bus.state(NAME) is ServiceState.AVAILABLE)
    assert wait_for(lambda: bus.state("org.test.Nobody") is ServiceState.UNAVAILABLE)
    time.sleep(0.1)
    assert rig.warnings == []  # absent at the start: not a warning (the first read says so at info)
    rig.fake.down()
    assert rig.pump.wait(lambda: mod.hooks.lost)
    assert wait_for(lambda: sum("left the session bus" in w for w in rig.warnings) == 1)
    rig.fake.up()
    assert rig.pump.wait(lambda: mod.hooks.found)
    rig.fake.down()  # again within the minute: the rate limit holds
    assert rig.pump.wait(lambda: len(mod.hooks.lost) >= 2)
    assert sum("left the session bus" in w for w in rig.warnings) == 1


def test_a_new_use_gets_the_current_available_from_the_context() -> None:
    from tess_shell.modules.context import ModuleContext, UseRecord
    from tess_shell.modules.ticks import TimeSource

    with fake_bus() as bus:
        fake = bus.service(NAME)
        fake.add(PATH, IFACE, properties={"Percentage": ("d", 5.0)})
        fake.up()
        service = ServiceThread(bus.address)
        service.start()
        layer = Layer(service, Pump().call_soon)
        sent: list[tuple[str | None, str, object]] = []
        ctx = ModuleContext(
            "M",
            "uid",
            {},
            {},
            lambda use, key, value: sent.append((use, key, value)),
            TimeSource(),
            dbus=lambda: layer,
        )
        try:
            ctx.dbus.session().proxy(NAME, PATH, IFACE)
            assert sent[0] == (None, "available", False)  # a layout can read it from the start
            assert wait_for(lambda: ctx.dbus.available)
            record = UseRecord("M@u2", "S.M.B.M_2", "u2", "Main", {})
            ctx.send_available(record)
            assert sent[-1] == ("M@u2", "available", True)
        finally:
            ctx.close()
            service.stop()


def test_a_change_that_arrives_while_the_first_read_is_in_flight_is_not_lost() -> None:
    """The layer subscribes before it reads, and a ``PropertiesChanged`` can be handled before the
    coroutine that awaits the ``GetAll`` reply resumes: the reply, read before that change, must
    not wipe it out (found on the Network module, where a change right after the start left the
    module with half of an update). Modelled directly: the reply is the old state and the change
    is handled first."""
    from dbus_fast import Variant

    from tess_shell.services.layer import _Cache

    class Message:
        body = ["iface", {"Primary": Variant("o", "/new")}, []]

    class Stub:
        async def call(self, *args: Any, **kwargs: Any) -> list[dict[str, Any]]:
            cache._on_signal(Message())  # handled before ``_load`` resumes
            return [{"Primary": "/old", "State": 70}]

        def timed(self, helper: Any, fn: Any, *args: Any) -> None:
            fn(*args)

        def spawn(self, coro: Any) -> None:  # pragma: no cover - nothing is invalidated here
            coro.close()

    class Service:
        kind = "system"
        name = "org.x"

    cache = _Cache(Stub(), Service(), "/p", "iface")  # type: ignore[arg-type]

    async def go() -> None:
        await cache._load()

    asyncio.run(go())
    assert cache.values == {"Primary": "/new", "State": 70}, cache.values
    assert cache.loaded and cache._pending is None
