"""The shell as a StatusNotifier host (Tray Module > The Host; Plasma Coexistence > Tray) against a
fake watcher on a private bus: the name, the registration, the restarts and the names that are
taken. Nothing here reaches the real session bus or the real watcher."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass

import pytest
from loguru import logger

from tess_shell.services.bus import ServiceThread
from tess_shell.services.tray import HOST_PREFIX, TrayService
from tests.fake_dbus import HAVE_DAEMON, FakeBus, fake_bus, wait_for
from tests.fake_sni import Watcher, add_watcher
from tests.test_dbus_own_name import owner_of

pytestmark = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")

PID = 4242
HOST = f"{HOST_PREFIX}{PID}"


@dataclass
class Rig:
    bus: FakeBus
    service: ServiceThread
    tray: TrayService
    watcher: Watcher
    states: list[bool]
    lines: list[str]


@contextmanager
def rig(*, watcher_up: bool = True) -> Iterator[Rig]:
    with fake_bus() as bus:
        service = ServiceThread(bus.address)
        service.start()

        async def sleep(seconds: float) -> None:
            await asyncio.sleep(0.02)

        service.session._sleep = sleep
        watcher = add_watcher(bus)
        if watcher_up:
            watcher.up()
        tray = TrayService(service, pid=PID)
        lines: list[str] = []
        sink = logger.add(lines.append, level="DEBUG", format="{level} {message}")
        try:
            yield Rig(bus, service, tray, watcher, [], lines)
        finally:
            logger.remove(sink)
            service.stop()


def subscribe(r: Rig) -> None:
    r.tray.for_module("Tray").on_host(r.states.append)


def test_the_shell_owns_the_host_name_and_registers_it_once() -> None:
    with rig() as r:
        subscribe(r)
        assert wait_for(lambda: r.states == [True])
        assert r.watcher.hosts == [HOST]  # RegisterStatusNotifierHost, once, with the name
        assert owner_of(r.bus, HOST) is not None
        assert r.tray.registered == 1


def test_two_modules_share_one_host() -> None:
    with rig() as r:
        subscribe(r)
        assert wait_for(lambda: r.states == [True])
        second: list[bool] = []
        r.tray.for_module("Tray2").on_host(second.append)
        assert wait_for(lambda: second == [True])  # told at once, nothing registered again
        assert r.watcher.hosts == [HOST]


def test_with_no_watcher_there_is_one_warning_and_the_host_waits_for_one() -> None:
    with rig(watcher_up=False) as r:
        subscribe(r)
        assert wait_for(lambda: r.states == [False])
        assert owner_of(r.bus, HOST) is None  # no name is taken for nobody
        warned = [x for x in r.lines if x.startswith("WARNING")]
        assert len(warned) == 1 and "StatusNotifierWatcher" in warned[0]
        assert "does not start one" in warned[0]  # the shell never starts a watcher
        r.watcher.up()  # one appears: no restart of anything
        assert wait_for(lambda: r.states == [False, True])
        assert r.watcher.hosts == [HOST]
        assert [x for x in r.lines if x.startswith("WARNING")] == warned


def test_after_the_watcher_restarts_the_shell_registers_again() -> None:
    with rig() as r:
        subscribe(r)
        assert wait_for(lambda: r.states == [True])
        r.watcher.restart()
        assert wait_for(lambda: r.states == [True, False, True])
        assert r.watcher.hosts == [HOST, HOST]
        assert r.tray.registered == 2


def test_after_the_bus_comes_back_the_name_and_the_registration_return() -> None:
    with rig() as r:
        subscribe(r)
        assert wait_for(lambda: r.states == [True])
        r.bus.daemon.restart()
        assert wait_for(lambda: r.states[-1:] == [False])
        r.watcher.up()  # the fake watcher reconnects to the new daemon
        assert wait_for(lambda: r.states[-1:] == [True], 10)
        assert owner_of(r.bus, HOST) is not None
        assert r.watcher.hosts.count(HOST) == 2


def test_a_taken_name_is_replaced_by_the_next_of_three() -> None:
    with rig() as r:
        r.bus.service(HOST).up()
        subscribe(r)
        assert wait_for(lambda: r.states == [True])
        assert r.watcher.hosts == [f"{HOST}-1"]
    with rig() as r:
        r.bus.service(HOST).up()
        r.bus.service(f"{HOST}-1").up()
        subscribe(r)
        assert wait_for(lambda: r.states == [True])
        assert r.watcher.hosts == [f"{HOST}-2"]


def test_after_three_tries_there_is_one_error_and_nothing_is_registered() -> None:
    with rig() as r:
        for n in (HOST, f"{HOST}-1", f"{HOST}-2"):
            r.bus.service(n).up()
        subscribe(r)
        assert wait_for(lambda: r.states == [False])
        assert r.watcher.hosts == []
        errors = [x for x in r.lines if x.startswith("ERROR")]
        assert len(errors) == 1 and "taken" in errors[0]


def test_the_last_subscription_to_go_gives_the_name_up() -> None:
    with rig() as r:
        sub = r.tray.for_module("Tray").on_host(r.states.append)
        assert wait_for(lambda: r.states == [True])
        sub.cancel()
        assert wait_for(lambda: owner_of(r.bus, HOST) is None)
        again = r.tray.for_module("Tray").on_host(r.states.append)  # a code reload
        assert wait_for(lambda: owner_of(r.bus, HOST) is not None)
        again.cancel()


def test_a_module_gets_on_host_and_nothing_that_owns_a_name() -> None:
    with rig() as r:
        helper = r.tray.for_module("Tray")
        assert {n for n in dir(helper) if not n.startswith("_")} == {"on_host", "close"}
