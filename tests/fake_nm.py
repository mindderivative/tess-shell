"""A fake NetworkManager on a private system bus (M5c): the manager, three active connections
(wired, Wi-Fi, VPN), two devices (an ethernet port and a Wi-Fi device with the ``Device.Wireless``
interface) and two access points, with the properties and types of the real service (Network
Module > What It Reads). Every property is writable by a client of the private bus, so the KWin
kit's ``busctl set-property`` and the tests change them the way NetworkManager would. Never
touches the real buses. Used by ``tests/test_network*.py`` and ``tests/kwin/fake_nm.py``."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tests.fake_dbus import FakeObject, FakeService

NM = "org.freedesktop.NetworkManager"
MANAGER_PATH = "/org/freedesktop/NetworkManager"
ACTIVE = "org.freedesktop.NetworkManager.Connection.Active"
DEVICE = "org.freedesktop.NetworkManager.Device"
WIRELESS = "org.freedesktop.NetworkManager.Device.Wireless"
ACCESS_POINT = "org.freedesktop.NetworkManager.AccessPoint"

AC = {
    "wired": "/org/freedesktop/NetworkManager/ActiveConnection/1",
    "wifi": "/org/freedesktop/NetworkManager/ActiveConnection/2",
    "vpn": "/org/freedesktop/NetworkManager/ActiveConnection/3",
}
DEV = {
    "eth": "/org/freedesktop/NetworkManager/Devices/2",
    "wlan": "/org/freedesktop/NetworkManager/Devices/3",
}
AP = {
    "one": "/org/freedesktop/NetworkManager/AccessPoint/1",
    "two": "/org/freedesktop/NetworkManager/AccessPoint/2",
}
NO_OBJECT = "/"


def ssid(text: str) -> bytes:
    return text.encode()


@dataclass
class Net:
    """The fake NetworkManager's objects, by role, and the scenarios the tests and the kit use."""

    service: FakeService
    manager: FakeObject
    conn: dict[str, FakeObject] = field(default_factory=dict)
    dev: dict[str, FakeObject] = field(default_factory=dict)
    wireless: FakeObject | None = None
    ap: dict[str, FakeObject] = field(default_factory=dict)

    # -- scenarios: the objects first, the manager's pointers last, as the real one orders it -----

    def wired(self) -> None:
        """Cable plugged in: the wired connection is primary, ``State`` 70, ``Connectivity`` 4."""
        m = self.manager
        m.set("ActiveConnections", self._active("wired"))
        m.set("PrimaryConnection", AC["wired"])
        m.set("Connectivity", 4)
        m.set("State", 70)

    def wifi(self, strength: int = 72, access_point: str = "one") -> None:
        """Wi-Fi is primary, on the access point ``access_point`` at ``strength`` percent."""
        assert self.wireless is not None
        self.ap[access_point].set("Strength", strength)
        self.wireless.set("ActiveAccessPoint", AP[access_point])
        m = self.manager
        m.set("ActiveConnections", self._active("wifi"))
        m.set("PrimaryConnection", AC["wifi"])
        m.set("Connectivity", 4)
        m.set("State", 70)

    def nothing(self) -> None:
        """No primary connection: ``State`` 20, ``Connectivity`` 1 (the cable is unplugged)."""
        m = self.manager
        m.set("PrimaryConnection", NO_OBJECT)
        m.set("ActiveConnections", [])
        m.set("Connectivity", 1)
        m.set("State", 20)

    def with_vpn(self, on: bool, base: str = "wired") -> None:
        """A VPN active connection joins (or leaves) the list; the primary one stays."""
        names = [base, "vpn"] if on else [base]
        self.manager.set("ActiveConnections", self._active(*names))

    def _active(self, *names: str) -> list[str]:
        return [AC[n] for n in names]


def add_network(service: FakeService) -> Net:
    """Add the objects to ``service`` (not up yet). The initial scenario is the maintainer's
    desktop: wired, ``State`` 70, ``Connectivity`` 4, Wi-Fi switched off."""

    def add(path: str, interface: str, props: dict[str, tuple[str, Any]]) -> FakeObject:
        return service.add(path, interface, properties=props, writable=list(props))

    manager = add(
        MANAGER_PATH,
        NM,
        {
            "State": ("u", 70),
            "Connectivity": ("u", 4),
            "PrimaryConnection": ("o", AC["wired"]),
            "ActiveConnections": ("ao", [AC["wired"]]),
            "WirelessEnabled": ("b", False),
            "WirelessHardwareEnabled": ("b", True),
            "NetworkingEnabled": ("b", True),
        },
    )
    net = Net(service, manager)
    net.conn["wired"] = add(
        AC["wired"],
        ACTIVE,
        {
            "Id": ("s", "Wired connection 1"),
            "Type": ("s", "802-3-ethernet"),
            "State": ("u", 2),
            "Vpn": ("b", False),
            "Default": ("b", True),
            "Devices": ("ao", [DEV["eth"]]),
        },
    )
    net.conn["wifi"] = add(
        AC["wifi"],
        ACTIVE,
        {
            "Id": ("s", "Home-WiFi"),
            "Type": ("s", "802-11-wireless"),
            "State": ("u", 2),
            "Vpn": ("b", False),
            "Default": ("b", True),
            "Devices": ("ao", [DEV["wlan"]]),
        },
    )
    net.conn["vpn"] = add(
        AC["vpn"],
        ACTIVE,
        {
            "Id": ("s", "Work VPN"),
            "Type": ("s", "vpn"),
            "State": ("u", 2),
            "Vpn": ("b", True),
            "Default": ("b", False),
            "Devices": ("ao", [DEV["eth"]]),
        },
    )
    net.dev["eth"] = add(
        DEV["eth"],
        DEVICE,
        {"DeviceType": ("u", 1), "Interface": ("s", "enp195s0"), "State": ("u", 100)},
    )
    net.dev["wlan"] = add(
        DEV["wlan"],
        DEVICE,
        {"DeviceType": ("u", 2), "Interface": ("s", "wlan0"), "State": ("u", 100)},
    )
    net.wireless = add(DEV["wlan"], WIRELESS, {"ActiveAccessPoint": ("o", NO_OBJECT)})
    net.ap["one"] = add(
        AP["one"], ACCESS_POINT, {"Ssid": ("ay", ssid("Home-WiFi")), "Strength": ("y", 72)}
    )
    net.ap["two"] = add(
        AP["two"], ACCESS_POINT, {"Ssid": ("ay", ssid("Cafe-Mesh")), "Strength": ("y", 40)}
    )
    return net
