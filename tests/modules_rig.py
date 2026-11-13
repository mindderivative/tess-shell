"""A shell with the shipped Battery and Workspaces on private buses (M5b): a private session bus and
a private system bus (two ``dbus-daemon``s, never the real ones), the ``dbus`` service thread and
the layer on them, and the headless Bar of ``tests/widgets_live.py`` with a real module host. The
test thread is the loop thread: ``settle`` drains what the layer handed over with ``call_soon``,
flushes the value store and lets the surface draw, until a condition holds."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from tess_shell.services.bus import ServiceThread
from tess_shell.services.layer import Layer
from tests.fake_dbus import FakeBus, FakeObject, FakeService, fake_bus
from tests.fake_mpris import Fake, add_player
from tests.fake_nm import NM, Net, add_network
from tests.test_dbus_layer import Pump
from tests.widgets_live import Widgets, running

UPOWER = "org.freedesktop.UPower"
DEVICE = "/org/freedesktop/UPower/devices/DisplayDevice"
DEVICE_INTERFACE = "org.freedesktop.UPower.Device"
PROFILES = "org.freedesktop.UPower.PowerProfiles"
PROFILES_PATH = "/org/freedesktop/UPower/PowerProfiles"
KWIN = "org.kde.KWin"
VDM = "/VirtualDesktopManager"
VDM_INTERFACE = "org.kde.KWin.VirtualDesktopManager"


@dataclass
class Desk:
    session: FakeBus
    system: FakeBus
    service: ServiceThread
    layer: Layer
    pump: Pump

    def battery(
        self, *, present: bool = True, percentage: float = 82.0, state: int = 2, **more: Any
    ) -> tuple[FakeService, FakeObject]:
        """A fake UPower on the system bus (not up yet)."""
        fake = self.system.service(UPOWER)
        props: dict[str, tuple[str, Any]] = {
            "IsPresent": ("b", present),
            "Type": ("u", 2 if present else 0),
            "Percentage": ("d", percentage),
            "State": ("u", state),
            "TimeToEmpty": ("x", 8040),
            "TimeToFull": ("x", 0),
            "WarningLevel": ("u", 1),
            "IconName": ("s", "battery-good-symbolic"),
        }
        props.update({k: v for k, v in more.items()})
        return fake, fake.add(DEVICE, DEVICE_INTERFACE, properties=props)

    def network(self) -> tuple[FakeService, Net]:
        """A fake NetworkManager on the system bus (not up yet): the maintainer's desktop, wired
        and online."""
        fake = self.system.service(NM)
        return fake, add_network(fake)

    def player(self, suffix: str = "fake", **kwargs: Any) -> Fake:
        """A fake MPRIS player on the session bus (not up yet)."""
        return add_player(self.session, suffix, **kwargs)

    def profiles(self, active: str = "balanced") -> tuple[FakeService, FakeObject]:
        fake = self.system.service(PROFILES)
        obj = fake.add(
            PROFILES_PATH,
            PROFILES,
            properties={"ActiveProfile": ("s", active)},
            writable=["ActiveProfile"],
        )
        return fake, obj

    def kwin(
        self, names: tuple[str, ...] = ("Main", "Code"), signature: str = "a(uss)"
    ) -> tuple[FakeService, FakeObject, list[str]]:
        """A fake KWin virtual desktop manager; returns the ids too."""
        ids = [f"id-{i}" for i in range(len(names))]
        fake = self.session.service(KWIN)
        obj = fake.add(
            VDM,
            VDM_INTERFACE,
            properties={
                "desktops": (signature, [[i, ids[i], names[i]] for i in range(len(names))]),
                "current": ("s", ids[0]),
            },
            signals={
                "desktopCreated": "sus",
                "desktopRemoved": "s",
                "desktopDataChanged": "s",
                "currentChanged": "s",
                "countChanged": "u",
            },
            writable=["current"],
        )
        return fake, obj, ids

    def settle(
        self, w: Widgets | None, predicate: Callable[[], object], timeout: float = 5.0
    ) -> bool:
        """Be the loop until ``predicate`` holds (or ``timeout``): run the layer's hooks, flush the
        value store and draw a frame."""
        deadline = time.monotonic() + timeout
        while True:
            self.pump.drain()
            if w is not None:
                w.flush()
                w.advance(16)
            if predicate():
                return True
            if time.monotonic() > deadline:
                return False
            time.sleep(0.004)


@contextmanager
def desk() -> Iterator[Desk]:
    with fake_bus() as session, fake_bus() as system:
        service = ServiceThread(session.address, system.address)
        service.start()
        pump = Pump()
        layer = Layer(service, pump.call_soon)
        try:
            yield Desk(session, system, service, layer, pump)
        finally:
            service.stop()


@contextmanager
def shell(d: Desk, children: str, **kwargs: Any) -> Iterator[Widgets]:
    with running(children, dbus=d.layer, **kwargs) as w:
        try:
            yield w
        finally:
            w.host.stop_all()
