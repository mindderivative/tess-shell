"""The Network: how the machine is connected, as NetworkManager reports it (Network Module). It
reads the manager once, then follows ``PropertiesChanged`` on the manager, on every active
connection, on the primary connection's device and on that device's access point: no timer, no
thread, no polling. The callbacks run on the ``dbus`` thread, derive the values and send only the
ones that changed. One instance serves every use.

Keys sent: ``ready`` (the manager, the primary connection, its device and access point were
read), ``state`` (``CONNECTED``, ``LIMITED``, ``PORTAL``, ``CONNECTING``, ``DISCONNECTED``,
``DISABLED`` or ``UNKNOWN``), ``kind`` (``ETHERNET``, ``WIFI``, ``MOBILE``, ``BLUETOOTH``,
``OTHER`` or ``NONE``), ``name``, ``strength`` (percent, -1 when the connection is not Wi-Fi; sent
only when the icon step or the tooltip's value changes), ``vpn``, ``icon``, ``tooltip`` and
``label`` (the accessible name). ``available`` is the layer's: true while NetworkManager is on the
system bus. A layout shows itself with ``Visible: {{ available and ready }}``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from functools import partial
from typing import TYPE_CHECKING, Any

from tess_shell import Module

if TYPE_CHECKING:
    from tess_shell.modules.context import UseRecord
    from tess_shell.services.api import Bus, Proxy, Subscription

NM = "org.freedesktop.NetworkManager"
NM_PATH = "/org/freedesktop/NetworkManager"
ACTIVE = "org.freedesktop.NetworkManager.Connection.Active"
DEVICE = "org.freedesktop.NetworkManager.Device"
WIRELESS = "org.freedesktop.NetworkManager.Device.Wireless"
ACCESS_POINT = "org.freedesktop.NetworkManager.AccessPoint"
NONE_PATH = "/"
# the manager's properties the module reads: a callback with all of them is a whole read
FULL = frozenset(
    {"State", "Connectivity", "PrimaryConnection", "ActiveConnections", "NetworkingEnabled"}
)

# NetworkManager's ``State``: 0 unknown, 10 disabled, 20 disconnected, 30 disconnecting,
# 40 connecting, 50 connected local, 60 connected site, 70 connected global
# ``Connectivity``: 0 unknown, 1 none, 2 portal, 3 limited, 4 full
# ``DeviceType``: 1 ethernet, 2 Wi-Fi, 5 Bluetooth, 8 modem
KINDS = {1: "ETHERNET", 2: "WIFI", 5: "BLUETOOTH", 8: "MOBILE"}
VPN_TYPES = ("vpn", "wireguard")

# the one place the tooltip's wording lives (Network Module, open question 4)
STATE_WORDS = {
    "CONNECTED": "connected",
    "LIMITED": "limited connectivity",
    "PORTAL": "sign-in required",
    "CONNECTING": "connecting",
    "DISCONNECTED": "disconnected",
    "DISABLED": "networking off",
    "UNKNOWN": "state unknown",
}
KIND_WORDS = {
    "ETHERNET": "ethernet",
    "WIFI": "Wi-Fi",
    "MOBILE": "mobile",
    "BLUETOOTH": "Bluetooth",
    "OTHER": "network",
}

FALLBACK_ICON = "network-outline"
WIFI_STEPS = ("wifi-strength-1", "wifi-strength-2", "wifi-strength-3", "wifi-strength-4")
# every icon the module can send; a test checks each against the shipped ``mdi`` set
ICONS = frozenset(
    {
        *WIFI_STEPS,
        "wifi-alert",
        "wifi-sync",
        "ethernet",
        "lan-disconnect",
        "lan-pending",
        "cellphone-wireless",
        "bluetooth",
        "network",
        "network-off",
        "wifi-off",
        FALLBACK_ICON,
    }
)


def number(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def text(value: object) -> str:
    return value if isinstance(value, str) else ""


def ssid_text(raw: object) -> str:
    """An access point's ``Ssid`` (an array of bytes): UTF-8, with replacement characters."""
    if isinstance(raw, bytes | bytearray):
        data = bytes(raw)
    elif isinstance(raw, Sequence) and not isinstance(raw, str):
        data = bytes(b for b in raw if isinstance(b, int) and 0 <= b < 256)
    else:
        return ""
    return data.decode("utf-8", "replace").replace("\x00", "")


def step_of(strength: int) -> int:
    """The Wi-Fi step 0 to 3 of a percent: four equal quarters (0 to 24, 25 to 49, 50 to 74,
    75 to 100)."""
    return min(max(strength, 0), 99) // 25


def shown_strength(strength: int) -> int:
    """The percent the tooltip shows: in steps of 5 (72 and 73 show 70), so it does not change on
    every wobble of the signal."""
    return min(max(strength, 0), 100) // 5 * 5


def state_name(manager: Mapping[str, Any], connecting: bool) -> str:
    """``state`` from the manager's ``State``, ``Connectivity`` and ``NetworkingEnabled`` and
    whether the primary connection is activating (Network Module > State and Kind)."""
    code = number(manager.get("State"))
    if manager.get("NetworkingEnabled") is False or code == 10:
        return "DISABLED"
    if code is None or code == 0:
        return "UNKNOWN"
    if code in (20, 30):
        return "DISCONNECTED"
    if code == 40 or connecting:
        return "CONNECTING"
    connectivity = number(manager.get("Connectivity"))
    if connectivity == 2:
        return "PORTAL"
    if code == 70 and connectivity != 3:
        return "CONNECTED"
    if code in (50, 60, 70):
        return "LIMITED"
    return "UNKNOWN"


def icon_name(kind: str, state: str, strength: int) -> str:
    """The ``mdi`` icon for a kind, a state and a Wi-Fi strength (Network Module > Icon). The rows
    the table does not give: any kind that is disconnected is ``network-off``, a disabled one
    ``wifi-off``, a connecting one ``lan-pending`` and a connected one of no kind ``network``."""
    if state == "UNKNOWN":
        return FALLBACK_ICON
    if state == "DISABLED":
        return "wifi-off"
    if state == "DISCONNECTED":
        return "network-off"
    if kind == "WIFI":
        if state == "CONNECTING":
            return "wifi-sync"
        if state in ("LIMITED", "PORTAL"):
            return "wifi-alert"
        return WIFI_STEPS[step_of(strength)] if strength >= 0 else WIFI_STEPS[0]
    if state == "CONNECTING":
        return "lan-pending"
    if kind == "ETHERNET":
        return "ethernet" if state == "CONNECTED" else "lan-disconnect"
    if kind == "MOBILE":
        return "cellphone-wireless"
    if kind == "BLUETOOTH":
        return "bluetooth"
    return "network"


def tooltip_text(kind: str, state: str, name: str, strength: int, vpn_name: str | None) -> str:
    """``Home-WiFi, Wi-Fi 70 %, connected``; ``Wired connection 1, ethernet, connected``;
    ``Disconnected``. A VPN adds ``VPN`` and its name."""
    if kind == "NONE":
        parts = [STATE_WORDS[state].capitalize()]
    else:
        parts = [name] if name else []
        word = KIND_WORDS[kind]
        if kind == "WIFI" and strength >= 0:
            word += f" {shown_strength(strength)} %"
        parts += [word, STATE_WORDS[state]]
    if vpn_name is not None:
        parts.append(f"VPN {vpn_name}" if vpn_name else "VPN")
    return ", ".join(parts)


def label_text(kind: str, state: str, name: str, strength: int, vpn_name: str | None) -> str:
    """The accessible name: ``Network, Wi-Fi Home-WiFi, 70 percent, connected``."""
    parts = ["Network"]
    if kind != "NONE":
        parts.append(f"{KIND_WORDS[kind]} {name}" if name else KIND_WORDS[kind])
        if kind == "WIFI" and strength >= 0:
            parts.append(f"{shown_strength(strength)} percent")
    parts.append(STATE_WORDS[state])
    if vpn_name is not None:
        parts.append(f"VPN {vpn_name}" if vpn_name else "VPN")
    return ", ".join(parts)


class Link:
    """One object the module follows with the properties of one interface: the path it is on now,
    its subscription and the last properties it gave. ``follow`` replaces the path; ``changed`` is
    called after properties of the followed path arrived."""

    def __init__(self, bus: Bus, interface: str, changed: Callable[[], None]) -> None:
        self.bus = bus
        self.interface = interface
        self.changed = changed
        self.path = ""
        self.props: dict[str, Any] = {}
        self.sub: Subscription | None = None

    def follow(self, path: str) -> None:
        """Follow ``path`` (``""`` or ``/``: nothing); a change of path drops the old one."""
        path = "" if path == NONE_PATH else path
        if path == self.path:
            return
        self.drop()
        self.path = path
        if path:
            proxy: Proxy = self.bus.proxy(NM, path, self.interface)
            self.sub = proxy.on_property_changed(partial(self.arrived, path))

    def drop(self) -> None:
        if self.sub is not None:
            self.sub.cancel()
            self.sub = None
        self.path = ""
        self.props = {}

    def arrived(self, path: str, values: Mapping[str, Any]) -> None:
        """Properties of ``path``: kept, if it is still the one followed (a callback that was on
        its way when the path changed is dropped)."""
        if path == self.path:
            self.props.update(values)
            self.changed()


class Network(Module):
    def __init__(self) -> None:
        self.manager: dict[str, Any] = {}
        self.sent: dict[str, Any] = {}
        self.warned: set[str] = set()
        self.basis: tuple[int, int] | None = None  # the Wi-Fi step and shown percent sent
        self.conns: dict[str, dict[str, Any]] = {}  # every active connection's properties
        self.conn_subs: dict[str, Subscription] = {}

    def start(self) -> None:
        # defaults, so a layout reading any key has a value before NetworkManager has answered
        self.publish(
            {
                "ready": False,
                "state": "UNKNOWN",
                "kind": "NONE",
                "name": "",
                "strength": -1,
                "vpn": False,
                "icon": FALLBACK_ICON,
                "tooltip": "",
                "label": "Network",
            }
        )
        self.bus = self.ctx.dbus.system()
        self.device = Link(self.bus, DEVICE, self.update)
        self.wireless = Link(self.bus, WIRELESS, self.update)
        self.point = Link(self.bus, ACCESS_POINT, self.update)
        self.proxy = self.bus.proxy(NM, NM_PATH, NM)
        self.proxy.on_property_changed(self.manager_changed)

    def use_added(self, use: UseRecord) -> None:
        for key, value in list(self.sent.items()):
            self.ctx.send(key, value, use=use)

    # -- on the dbus thread -------------------------------------------------------------------

    def manager_changed(self, values: Mapping[str, Any]) -> None:
        if FULL <= values.keys():
            # every property: the first read, or a read after the service came back (the layer
            # gives the whole set again). Its objects may be other ones, so what was followed is
            # let go and followed again from this set. (Not ``on_service_lost``: that hook runs on
            # the loop thread, and the layer's new set may arrive here before it does.)
            self.reset()
            self.manager = dict(values)
        else:
            self.manager.update(values)
        self.update()

    def reset(self) -> None:
        for sub in self.conn_subs.values():
            sub.cancel()
        self.conn_subs.clear()
        self.conns.clear()
        for link in (self.device, self.wireless, self.point):
            link.drop()

    def connection_changed(self, path: str, values: Mapping[str, Any]) -> None:
        """The properties of an active connection that is in the manager's list."""
        if path in self.conn_subs:
            self.conns.setdefault(path, {}).update(values)
            self.update()

    def watch_connections(self) -> None:
        """One subscription for each active connection (its type, VPN flag, name and devices),
        replaced as the manager's list changes."""
        listed = self.manager.get("ActiveConnections")
        paths = [p for p in listed if isinstance(p, str)] if isinstance(listed, list) else []
        for path in list(self.conn_subs):
            if path not in paths:
                self.conn_subs.pop(path).cancel()
                self.conns.pop(path, None)
        for path in paths:
            if path not in self.conn_subs:
                proxy = self.bus.proxy(NM, path, ACTIVE)
                self.conn_subs[path] = proxy.on_property_changed(
                    partial(self.connection_changed, path)
                )

    def update(self) -> None:
        if "State" not in self.manager:
            return
        self.watch_connections()
        link = self.link_connection()
        devices = link.get("Devices") if link else None
        first = devices[0] if isinstance(devices, list) and devices else ""
        self.device.follow(first if isinstance(first, str) else "")
        wifi = number(self.device.props.get("DeviceType")) == 2
        self.wireless.follow(self.device.path if wifi else "")
        ap = text(self.wireless.props.get("ActiveAccessPoint")) if wifi else ""
        self.point.follow(ap)
        if not self.complete(link, wifi):
            return
        self.derive(link, wifi)

    def link_connection(self) -> dict[str, Any] | None:
        """The connection the icon describes: the primary one, or, when that is a VPN, the
        connection it runs over (a VPN is never the kind), or ``None``."""
        primary = text(self.manager.get("PrimaryConnection"))
        found = self.conns.get(primary) if primary != NONE_PATH else None
        if found is not None and not self.is_vpn(found):
            return found
        if found is None and primary not in ("", NONE_PATH):
            return None  # the primary connection has not been read yet
        for props in self.conns.values():
            if not self.is_vpn(props) and (props.get("Default") is True or found is not None):
                return props
        return None

    @staticmethod
    def is_vpn(props: Mapping[str, Any]) -> bool:
        return props.get("Vpn") is True or text(props.get("Type")) in VPN_TYPES

    def complete(self, link: dict[str, Any] | None, wifi: bool) -> bool:
        """Everything the values need has been read: the manager, and, with a primary connection,
        its properties, its device and (Wi-Fi) the device's access point."""
        primary = text(self.manager.get("PrimaryConnection"))
        if primary not in ("", NONE_PATH) and link is None:
            return False
        if link is None:
            return True
        if not self.device.path or "DeviceType" not in self.device.props:
            return not self.device.path and not link.get("Devices")
        if wifi:
            if "ActiveAccessPoint" not in self.wireless.props:
                return False
            if self.point.path and "Strength" not in self.point.props:
                return False
        return True

    def derive(self, link: dict[str, Any] | None, wifi: bool) -> None:
        kind = "NONE"
        name = ""
        strength = -1
        if link is not None:
            device_type = number(self.device.props.get("DeviceType"))
            kind = KINDS.get(device_type, "OTHER") if device_type is not None else "OTHER"
            name = text(link.get("Id"))
            if wifi:
                if self.point.path:
                    strength = self.byte(self.point.props.get("Strength"))
                    name = ssid_text(self.point.props.get("Ssid")) or name
                else:
                    name = ""
        connecting = link is not None and number(link.get("State")) == 1
        state = state_name(self.manager, connecting)
        vpns = [p for p in self.conns.values() if self.is_vpn(p)]
        vpn_name = text(vpns[0].get("Id")) if vpns else None
        basis = (step_of(strength), shown_strength(strength)) if strength >= 0 else None
        values: dict[str, Any] = {
            "state": state,
            "kind": kind,
            "name": name,
            "vpn": bool(vpns),
            "icon": icon_name(kind, state, shown_strength(strength) if strength >= 0 else -1),
            "tooltip": tooltip_text(kind, state, name, strength, vpn_name),
            "label": label_text(kind, state, name, strength, vpn_name),
        }
        # a signal that moves the percent inside a step and a tooltip's 5 changes nothing sent
        if basis != self.basis or "strength" not in self.sent:
            self.basis = basis
            values["strength"] = strength
        values["ready"] = True
        self.publish(values)

    def byte(self, value: object) -> int:
        percent = number(value)
        if percent is None:
            self.warn_once("an access point's Strength is not a whole number; ignored")
            return -1
        return min(max(percent, 0), 100)

    def publish(self, values: Mapping[str, Any]) -> None:
        """Send what changed since the last send: a refresh that changes nothing sends nothing."""
        for key, value in values.items():
            if key not in self.sent or self.sent[key] != value:
                self.sent[key] = value
                self.ctx.send(key, value)

    def warn_once(self, message: str) -> None:
        if message not in self.warned:
            self.warned.add(message)
            self.ctx.log.warning(message)
