"""``Bus.watch_prefix`` and ``Bus.forget`` (D-Bus Service Layer additions of M5d, Media Module >
Needs from the Layer): every well-known name under a prefix found by one ``ListNames`` and
followed by one ``NameOwnerChanged`` rule; the callbacks on the ``dbus`` thread; ``available`` is
the bus being reachable, not the players; an optional proxy of a player that leaves does not make
the module unavailable."""

from __future__ import annotations

import threading
import time

import pytest

from tests.fake_dbus import HAVE_DAEMON, FakeBus, fake_bus, wait_for
from tests.test_dbus_layer import Rig

pytestmark = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")

PREFIX = "org.mpris.MediaPlayer2."


class Watcher:
    def __init__(self) -> None:
        self.added: list[tuple[str, int]] = []
        self.removed: list[tuple[str, int]] = []

    def on_added(self, name: str) -> None:
        self.added.append((name, threading.get_ident()))

    def on_removed(self, name: str) -> None:
        self.removed.append((name, threading.get_ident()))

    @property
    def names(self) -> list[str]:
        return [n for n, _ in self.added]

    @property
    def gone(self) -> list[str]:
        return [n for n, _ in self.removed]


def make_rig(bus: FakeBus) -> Rig:
    fake = bus.service("org.test.Other")  # the Rig wants a service; this one is not used
    obj = fake.add("/o", "org.test.Other", properties={"A": ("i", 1)})
    return Rig(bus, fake, obj)


def player(bus: FakeBus, suffix: str, up: bool = True) -> object:
    service = bus.service(PREFIX + suffix)
    service.add(
        "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2", properties={"Identity": ("s", suffix)}
    )
    if up:
        service.up()
    return service


def test_the_names_that_exist_are_announced_and_later_ones_follow_on_the_dbus_thread() -> None:
    with fake_bus() as bus:
        player(bus, "vlc")
        player(bus, "mpv")
        stranger = bus.service("org.other.Thing")
        stranger.add("/x", "org.other.Thing", properties={"A": ("i", 1)})
        stranger.up()
        rig = make_rig(bus)
        try:
            mod, watcher = rig.module("Media"), Watcher()
            mod.dbus.session().watch_prefix(PREFIX, watcher.on_added, watcher.on_removed)
            assert wait_for(lambda: len(watcher.names) == 2)
            assert sorted(watcher.names) == [PREFIX + "mpv", PREFIX + "vlc"]
            assert {t for _, t in watcher.added} == {rig.service.thread_id}  # the dbus thread
            late = player(bus, "late", up=False)
            late.up()  # type: ignore[attr-defined]
            assert wait_for(lambda: PREFIX + "late" in watcher.names)
            assert len(watcher.names) == 3  # nothing twice, and the stranger never
            late.down()  # type: ignore[attr-defined]
            assert wait_for(lambda: watcher.gone == [PREFIX + "late"])
            assert {t for _, t in watcher.removed} == {rig.service.thread_id}
        finally:
            rig.close()


def test_the_prefix_is_a_namespace_not_a_text_prefix() -> None:
    with fake_bus() as bus:
        rig = make_rig(bus)
        try:
            mod, watcher = rig.module("Media"), Watcher()
            mod.dbus.session().watch_prefix(PREFIX, watcher.on_added, watcher.on_removed)
            wait_for(lambda: mod.available())
            near = bus.service("org.mpris.MediaPlayer2x")  # shares the text, not the namespace
            near.add("/x", "org.x", properties={"A": ("i", 1)})
            near.up()
            player(bus, "real")
            assert wait_for(lambda: watcher.names == [PREFIX + "real"])
            time.sleep(0.2)
            assert watcher.names == [PREFIX + "real"]
        finally:
            rig.close()


def test_one_name_owner_rule_for_two_modules_and_it_goes_with_the_last() -> None:
    with fake_bus() as bus:
        rig = make_rig(bus)
        monitor = bus.monitor()
        try:
            a, b = rig.module("A"), rig.module("B")
            wa, wb = Watcher(), Watcher()
            sa = a.dbus.session().watch_prefix(PREFIX, wa.on_added, wa.on_removed)
            sb = b.dbus.session().watch_prefix(PREFIX, wb.on_added, wb.on_removed)
            player(bus, "vlc")
            assert wait_for(lambda: wa.names and wb.names)  # both hear it
            me = rig.unique_name()
            rules = monitor.added(me, "arg0namespace='org.mpris.MediaPlayer2'")
            assert len(rules) == 1, rules
            sa.cancel()
            time.sleep(0.15)
            assert len(monitor.added(me, "arg0namespace=")) == 1  # b still listens
            player(bus, "mpv")
            assert wait_for(lambda: PREFIX + "mpv" in wb.names)
            assert PREFIX + "mpv" not in wa.names  # a stopped
            sb.cancel()
            assert wait_for(lambda: monitor.added(me, "arg0namespace=") == [])
        finally:
            monitor.stop()
            rig.close()


def test_available_is_the_bus_being_reachable_and_not_the_players() -> None:
    with fake_bus() as bus:
        rig = make_rig(bus)
        try:
            mod, watcher = rig.module("Media"), Watcher()
            sub = mod.dbus.session()
            sub.watch_prefix(PREFIX, watcher.on_added, watcher.on_removed)
            assert rig.pump.wait(lambda: mod.available() and mod.available()[-1] is True)
            assert mod.dbus.available is True  # with no player at all
            p = player(bus, "vlc")
            assert wait_for(lambda: watcher.names)
            # an optional proxy of the player: its leaving does not make the module unavailable
            sub.proxy(
                PREFIX + "vlc", "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2", optional=True
            )
            time.sleep(0.2)
            p.down()  # type: ignore[attr-defined]
            assert wait_for(lambda: watcher.gone)
            time.sleep(0.2)
            assert mod.dbus.available is True and mod.available()[-1] is True
            assert [w for w in rig.warnings if "left" in w] == []  # an optional service: no warning
        finally:
            rig.close()


def test_forget_lets_go_of_a_name_its_watch_and_its_cache() -> None:
    with fake_bus() as bus:
        rig = make_rig(bus)
        monitor = bus.monitor()
        try:
            mod = rig.module("Media")
            session = mod.dbus.session()
            p = player(bus, "vlc")
            proxy = session.proxy(
                PREFIX + "vlc", "/org/mpris/MediaPlayer2", "org.mpris.MediaPlayer2", optional=True
            )
            got: list[object] = []
            sub = proxy.on_property_changed(got.append)
            assert wait_for(lambda: got)
            me = rig.unique_name()
            assert monitor.added(me, "PropertiesChanged")
            sub.cancel()
            session.forget(PREFIX + "vlc")
            assert wait_for(lambda: monitor.added(me, "PropertiesChanged") == [])
            assert wait_for(lambda: monitor.added(me, "NameOwnerChanged") == [])
            assert ("session", PREFIX + "vlc") not in rig.layer._services
            assert not rig.layer._caches
            p.down()  # type: ignore[attr-defined]
            time.sleep(0.2)
            assert [w for w in rig.warnings if "vlc" in w] == []
        finally:
            monitor.stop()
            rig.close()


def test_the_daemon_restarting_lists_the_names_again_and_tells_what_went() -> None:
    with fake_bus() as bus:
        rig = make_rig(bus)
        try:
            mod, watcher = rig.module("Media"), Watcher()
            mod.dbus.session().watch_prefix(PREFIX, watcher.on_added, watcher.on_removed)
            a = player(bus, "gone_after")
            player(bus, "stays")
            assert wait_for(lambda: len(watcher.names) == 2)
            bus.daemon.stop()
            assert wait_for(
                lambda: sorted(watcher.gone) == sorted(watcher.names)
            )  # every name went
            assert wait_for(lambda: mod.available() and mod.available()[-1] is False)
            bus.daemon.restart()
            bus.services[-1].up()  # only "stays" comes back (the last service made)
            assert a is not None
            assert wait_for(lambda: len(watcher.names) >= 3, 15)
            assert watcher.names[-1] == PREFIX + "stays"
            assert wait_for(lambda: mod.available()[-1] is True, 15)
        finally:
            rig.close()
