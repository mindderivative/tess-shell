"""Owning a bus name (Tray Module > Needs from the Shell; D-Bus Service Layer > Own Names and
Objects): ``Bus.own_name`` is the shell's own, asks again after a reconnect through
``Bus.on_reconnect``, and no module can take a name through ``ctx.dbus``. Private buses only."""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from dbus_fast import Message, MessageType
from dbus_fast.aio import MessageBus

from tess_shell.services import api
from tess_shell.services.api import ServiceUnavailable
from tess_shell.services.bus import ServiceThread
from tests.fake_dbus import HAVE_DAEMON, FakeBus, fake_bus, wait_for

pytestmark = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")

NAME = "org.kde.StatusNotifierHost-4242"


def owner_of(bus: FakeBus, name: str) -> str | None:
    """Who owns ``name`` on the private bus, asked from a connection of the test's own."""

    async def ask() -> str | None:
        conn = await MessageBus(bus_address=bus.address).connect()
        try:
            reply = await conn.call(
                Message(
                    destination="org.freedesktop.DBus",
                    path="/org/freedesktop/DBus",
                    interface="org.freedesktop.DBus",
                    member="GetNameOwner",
                    signature="s",
                    body=[name],
                )
            )
            if reply is not None and reply.message_type == MessageType.METHOD_RETURN:
                return str(reply.body[0])
            return None
        finally:
            conn.disconnect()

    return bus.thread.run(ask())


def test_the_shell_owns_the_name_and_asking_again_changes_nothing() -> None:
    with fake_bus() as bus:
        service = ServiceThread(bus.address)
        service.start()
        try:
            assert service.submit(service.session.own_name(NAME)).result(5) is True
            first = owner_of(bus, NAME)
            assert first is not None
            assert service.submit(service.session.own_name(NAME)).result(5) is True
            assert owner_of(bus, NAME) == first
            assert len(service.session._hooks) == 1  # one hook to ask again, not two
            service.submit(service.session.release_name(NAME)).result(5)
            assert owner_of(bus, NAME) is None
            assert service.session._hooks == []
        finally:
            service.stop()


def test_a_name_somebody_else_owns_is_not_waited_for() -> None:
    with fake_bus() as bus:
        other = bus.service(NAME)
        other.up()
        service = ServiceThread(bus.address)
        service.start()
        try:
            assert service.submit(service.session.own_name(NAME)).result(5) is False
            assert service.session._hooks == []  # nothing to ask again for
            assert owner_of(bus, NAME) == other.unique_name
        finally:
            service.stop()


def test_the_name_is_asked_for_again_after_the_bus_comes_back() -> None:
    with fake_bus() as bus:
        service = ServiceThread(bus.address)
        service.start()

        async def sleep(seconds: float) -> None:
            await asyncio.sleep(0.02)

        service.session._sleep = sleep
        try:
            assert service.submit(service.session.own_name(NAME)).result(5) is True
            first = service.session.connects
            bus.daemon.restart()
            assert wait_for(lambda: service.session.connects == first + 1, 10)
            assert wait_for(lambda: owner_of(bus, NAME) is not None, 5)
            assert owner_of(bus, NAME) == service.session._conn.unique_name  # type: ignore[union-attr]
        finally:
            service.stop()


def test_an_unreachable_bus_raises_unavailable() -> None:
    with fake_bus() as bus:
        bus.daemon.stop()
        service = ServiceThread(bus.address)
        service.start()
        try:
            with pytest.raises(ServiceUnavailable):
                service.submit(service.session.own_name(NAME)).result(5)
        finally:
            service.stop()


def test_a_module_cannot_take_a_name_through_ctx_dbus() -> None:
    """Nothing the module sees can own a name: the protocols, and the objects behind them."""
    from tess_shell.services.layer import Layer
    from tests.test_dbus_layer import Pump

    for protocol in (api.ModuleDBus, api.Bus, api.Proxy):
        members = {n for n in dir(protocol) if not n.startswith("_")}
        assert not members & {"own_name", "request_name", "release_name"}
    with fake_bus() as bus:
        service = ServiceThread(bus.address)
        service.start()
        try:
            layer = Layer(service, Pump().call_soon)
            sent: list[Any] = []
            helper = layer.for_module("M", lambda k, v: sent.append((k, v)), _Hooks())
            session = helper.session()
            proxy = session.proxy("org.test.X", "/x", "org.test.X")
            for thing in (helper, session, proxy):
                names = {n.lower() for n in dir(thing)}
                assert not any(w in n for n in names for w in ("own_name", "request_name"))
                assert not any(w in n for n in names for w in ("release_name", "export", "conn"))
            assert not hasattr(session, "own_name")
        finally:
            service.stop()


class _Hooks:
    def lost(self, name: str) -> None: ...

    def found(self, name: str) -> None: ...
