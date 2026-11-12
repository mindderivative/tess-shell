"""The shipped Network module (Network Module): the derivations, then the module on a fake
NetworkManager on a private system bus (``tests/fake_nm.py``), drawn by the real binder in a
headless Bar."""

from __future__ import annotations

import importlib.util
import time
from types import ModuleType
from typing import Any

import pytest

from tess_shell.files.icons import IconSets
from tests.fake_dbus import HAVE_DAEMON, wait_for
from tests.fake_nm import AC, AP, DEV, MANAGER_PATH, NO_OBJECT
from tests.modules_rig import desk, shell
from tests.widgets_live import SHIPPED, Widgets

needs_daemon = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")

TEXT = (228, 234, 241)  # $color.on_surface of the Default theme
WARNING = (230, 187, 106)  # $color.warning
MUTED = (159, 174, 191)  # $color.on_surface_muted


def load() -> ModuleType:
    path = SHIPPED / "Network" / "Network_Module.py"
    spec = importlib.util.spec_from_file_location("shipped_network", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


N = load()
SETS = IconSets([SHIPPED / "Icons"])


# -- the derivations ----------------------------------------------------------------------------


def test_every_icon_the_python_can_send_and_the_vpn_icon_are_in_the_shipped_mdi_set() -> None:
    missing = sorted(name for name in N.ICONS if SETS.lookup(f"mdi:{name}") is None)
    assert missing == [], f"not in the mdi set: {missing}"
    assert SETS.lookup("mdi:vpn") is not None
    assert len(N.ICONS) == 15


STATES = ("CONNECTED", "LIMITED", "PORTAL", "CONNECTING", "DISCONNECTED", "DISABLED", "UNKNOWN")
KINDS = ("ETHERNET", "WIFI", "MOBILE", "BLUETOOTH", "OTHER", "NONE")


def test_icon_names_the_table_gives_never_leave_the_set() -> None:
    seen = set()
    for kind in KINDS:
        for state in STATES:
            for strength in (-1, 0, 24, 25, 49, 50, 74, 75, 100):
                name = N.icon_name(kind, state, strength)
                assert name in N.ICONS, (kind, state, strength, name)
                seen.add(name)
    assert seen == set(N.ICONS)  # every name is reachable


@pytest.mark.parametrize(
    ("kind", "state", "strength", "icon"),
    [
        ("WIFI", "CONNECTED", 0, "wifi-strength-1"),
        ("WIFI", "CONNECTED", 24, "wifi-strength-1"),
        ("WIFI", "CONNECTED", 25, "wifi-strength-2"),
        ("WIFI", "CONNECTED", 49, "wifi-strength-2"),
        ("WIFI", "CONNECTED", 50, "wifi-strength-3"),
        ("WIFI", "CONNECTED", 74, "wifi-strength-3"),
        ("WIFI", "CONNECTED", 75, "wifi-strength-4"),
        ("WIFI", "CONNECTED", 100, "wifi-strength-4"),
        ("WIFI", "LIMITED", 80, "wifi-alert"),
        ("WIFI", "PORTAL", 80, "wifi-alert"),
        ("WIFI", "CONNECTING", -1, "wifi-sync"),
        ("ETHERNET", "CONNECTED", -1, "ethernet"),
        ("ETHERNET", "LIMITED", -1, "lan-disconnect"),
        ("ETHERNET", "PORTAL", -1, "lan-disconnect"),
        ("ETHERNET", "CONNECTING", -1, "lan-pending"),
        ("MOBILE", "CONNECTING", -1, "lan-pending"),
        ("BLUETOOTH", "CONNECTING", -1, "lan-pending"),
        ("OTHER", "CONNECTING", -1, "lan-pending"),
        ("MOBILE", "CONNECTED", -1, "cellphone-wireless"),
        ("MOBILE", "LIMITED", -1, "cellphone-wireless"),
        ("BLUETOOTH", "PORTAL", -1, "bluetooth"),
        ("OTHER", "CONNECTED", -1, "network"),
        ("NONE", "DISCONNECTED", -1, "network-off"),
        ("NONE", "DISABLED", -1, "wifi-off"),
        ("ETHERNET", "UNKNOWN", -1, "network-outline"),
        ("NONE", "UNKNOWN", -1, "network-outline"),
    ],
)
def test_the_icon_table(kind: str, state: str, strength: int, icon: str) -> None:
    assert N.icon_name(kind, state, strength) == icon


@pytest.mark.parametrize(
    ("manager", "connecting", "state"),
    [
        ({"State": 70, "Connectivity": 4}, False, "CONNECTED"),
        ({"State": 70, "Connectivity": 0}, False, "CONNECTED"),
        ({"State": 70, "Connectivity": 1}, False, "CONNECTED"),
        ({"State": 70, "Connectivity": 3}, False, "LIMITED"),
        ({"State": 60, "Connectivity": 4}, False, "LIMITED"),
        ({"State": 50, "Connectivity": 3}, False, "LIMITED"),
        ({"State": 50}, False, "LIMITED"),
        ({"State": 70, "Connectivity": 2}, False, "PORTAL"),
        ({"State": 60, "Connectivity": 2}, False, "PORTAL"),
        ({"State": 40}, False, "CONNECTING"),
        ({"State": 70, "Connectivity": 4}, True, "CONNECTING"),  # the connection is activating
        ({"State": 20}, False, "DISCONNECTED"),
        ({"State": 30}, False, "DISCONNECTED"),
        ({"State": 20, "Connectivity": 2}, False, "DISCONNECTED"),  # no portal without a link
        ({"State": 10}, False, "DISABLED"),
        ({"State": 70, "NetworkingEnabled": False}, False, "DISABLED"),
        ({"State": 20, "WirelessEnabled": False}, False, "DISCONNECTED"),  # wifi off is not off
        ({"State": 0}, False, "UNKNOWN"),
        ({}, False, "UNKNOWN"),
        ({"State": 33}, False, "UNKNOWN"),
    ],
)
def test_the_state_follows_the_manager_and_the_portal_case_the_connectivity(
    manager: dict[str, Any], connecting: bool, state: str
) -> None:
    assert N.state_name(manager, connecting) == state


def test_the_four_wifi_steps_are_equal_quarters_and_the_tooltip_percent_is_in_fives() -> None:
    assert [N.step_of(p) for p in (0, 24, 25, 49, 50, 74, 75, 99, 100)] == [
        0,
        0,
        1,
        1,
        2,
        2,
        3,
        3,
        3,
    ]
    assert [N.shown_strength(p) for p in (0, 4, 5, 72, 73, 74, 75, 99, 100)] == [
        0,
        0,
        5,
        70,
        70,
        70,
        75,
        95,
        100,
    ]
    # a boundary of a step is a multiple of 5: the shown percent never crosses a step
    for p in range(101):
        assert N.step_of(N.shown_strength(p)) == N.step_of(p)


def test_the_tooltip_says_the_name_the_kind_and_the_state() -> None:
    t = N.tooltip_text
    assert t("ETHERNET", "CONNECTED", "Wired connection 1", -1, None) == (
        "Wired connection 1, ethernet, connected"
    )
    assert t("WIFI", "CONNECTED", "Home-WiFi", 72, None) == "Home-WiFi, Wi-Fi 70 %, connected"
    assert t("WIFI", "LIMITED", "Home-WiFi", 72, None) == (
        "Home-WiFi, Wi-Fi 70 %, limited connectivity"
    )
    assert t("WIFI", "PORTAL", "Cafe", 40, None) == "Cafe, Wi-Fi 40 %, sign-in required"
    assert t("WIFI", "CONNECTING", "Home-WiFi", -1, None) == "Home-WiFi, Wi-Fi, connecting"
    assert t("WIFI", "CONNECTED", "", 55, None) == "Wi-Fi 55 %, connected"
    assert t("MOBILE", "CONNECTED", "Plan", -1, None) == "Plan, mobile, connected"
    assert t("NONE", "DISCONNECTED", "", -1, None) == "Disconnected"
    assert t("NONE", "DISABLED", "", -1, None) == "Networking off"
    assert t("ETHERNET", "CONNECTED", "Wired", -1, "Work") == "Wired, ethernet, connected, VPN Work"
    assert t("ETHERNET", "CONNECTED", "Wired", -1, "") == "Wired, ethernet, connected, VPN"
    assert N.label_text("WIFI", "CONNECTED", "Home-WiFi", 72, None) == (
        "Network, Wi-Fi Home-WiFi, 70 percent, connected"
    )
    assert N.label_text("NONE", "DISCONNECTED", "", -1, None) == "Network, disconnected"


def test_an_ssid_is_decoded_with_replacement_characters_for_what_is_not_utf8() -> None:
    assert N.ssid_text(b"Home-WiFi") == "Home-WiFi"
    assert N.ssid_text([72, 105]) == "Hi"
    assert N.ssid_text(b"caf\xe9") == "caf\ufffd"
    assert N.ssid_text(b"a\x00b") == "ab"
    assert N.ssid_text(None) == ""


# -- the module on a fake NetworkManager --------------------------------------------------------


def shown(w: Widgets) -> bool:
    """Is the module's root visible (it takes space in the Bar)?"""
    (root,) = [n for k, n in w.view.nodes.items() if k.endswith("/Root")]
    return bool(root.get("visible"))


def level(w: Widgets) -> Any:
    """The box of the look that shows (normal, warning or muted), or ``None`` when hidden."""
    if not shown(w):
        return None
    found = [
        n
        for k, n in w.view.nodes.items()
        if k.split("/")[-1].startswith("Level") and n.get("visible")
    ]
    assert len(found) == 1, f"{len(found)} looks shown"
    return found[0]


def icons(w: Widgets) -> list[Any]:
    box = level(w)
    assert box is not None
    return [c for c in box.children() if c.get("kind") == "svg"]


def glyph(w: Widgets) -> Any:
    return icons(w)[0]


def vpn_shown(w: Widgets) -> bool:
    """Does the second icon show?"""
    box = level(w)
    return box is not None and bool(icons(w)[1].get("visible"))


def icon_of(w: Widgets) -> str | None:
    """The name of the icon the Bar shows (the module's first SVG), or ``None``."""
    if not shown(w):
        return None
    doc = glyph(w).get("svg")
    (name,) = [n for n in N.ICONS if SETS.lookup(f"mdi:{n}") == doc] or [None]
    return name  # type: ignore[no-any-return]


def values(w: Widgets) -> dict[str, Any]:
    (use,) = w.uses
    return dict(w.store.values[use])


def quiet(w: Widgets) -> list[str]:
    """Every INFO, WARNING and ERROR line (but the Bar's own): what a quiet module logs."""
    return [
        x
        for x in w.lines
        if ("| INFO " in x or "| WARNING " in x or "| ERROR " in x) and "Bar Top_Bar" not in x
    ]


def sent(w: Widgets) -> dict[str, Any]:
    return dict(w.host.loaded["Network"].instance.sent)


def counting(w: Widgets) -> list[str]:
    """Record every key the module sends from now on."""
    instance = w.host.loaded["Network"].instance
    calls: list[str] = []
    real = instance.ctx.send

    def spy(key: str, value: Any, use: Any = None) -> None:
        calls.append(key)
        real(key, value) if use is None else real(key, value, use=use)

    instance.ctx.send = spy
    return calls


@needs_daemon
def test_the_maintainers_desktop_shows_ethernet_with_no_second_icon_and_the_tooltip() -> None:
    with desk() as d:
        fake, _ = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "ethernet"), (w.log(), values(w))
            v = values(w)
            assert v["tooltip"] == "Wired connection 1, ethernet, connected"
            assert v["label"] == "Network, ethernet Wired connection 1, connected"
            assert (v["available"], v["ready"], v["vpn"], v["strength"]) == (True, True, False, -1)
            assert not vpn_shown(w) and len(icons(w)) == 2
            (root,) = [n for k, n in w.view.nodes.items() if k.endswith("/Root")]
            assert root.get("role") == "group" and root.get("label") == v["label"]
            assert quiet(w) == [] and w.warnings() == []


@needs_daemon
def test_unplugging_the_cable_shows_network_off_and_disconnected_in_one_loop_turn() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "ethernet")
            instance = w.host.loaded["Network"].instance
            net.nothing()
            # the callback on the dbus thread has sent; no wait for anything else
            assert wait_for(lambda: instance.sent["icon"] == "network-off")
            w.flush()  # one loop turn: the store applies what was sent
            w.advance(16)
            assert icon_of(w) == "network-off" and shown(w)  # a disconnected machine stays visible
            assert values(w)["tooltip"] == "Disconnected" and values(w)["state"] == "DISCONNECTED"
            assert (values(w)["kind"], values(w)["name"]) == ("NONE", "")
            net.wired()  # plugged in again
            assert d.settle(w, lambda: icon_of(w) == "ethernet")
            assert values(w)["tooltip"] == "Wired connection 1, ethernet, connected"
            assert quiet(w) == []


@needs_daemon
def test_wifi_shows_its_strength_in_four_steps_and_the_tooltip_in_fives() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "ethernet")
            net.wifi(72)
            assert d.settle(w, lambda: icon_of(w) == "wifi-strength-3")
            v = values(w)
            assert v["tooltip"] == "Home-WiFi, Wi-Fi 70 %, connected" and v["strength"] == 72
            assert v["kind"] == "WIFI" and v["name"] == "Home-WiFi"
            assert v["label"] == "Network, Wi-Fi Home-WiFi, 70 percent, connected"
            net.ap["one"].set("Strength", 80)
            assert d.settle(w, lambda: icon_of(w) == "wifi-strength-4")
            assert values(w)["tooltip"] == "Home-WiFi, Wi-Fi 80 %, connected"
            for strength, icon in (
                (0, "wifi-strength-1"),
                (24, "wifi-strength-1"),
                (25, "wifi-strength-2"),
                (49, "wifi-strength-2"),
                (50, "wifi-strength-3"),
                (74, "wifi-strength-3"),
                (75, "wifi-strength-4"),
                (100, "wifi-strength-4"),
            ):
                net.ap["one"].set("Strength", strength)
                assert d.settle(
                    w, lambda i=icon, s=strength: icon_of(w) == i and values(w)["strength"] == s
                ), (
                    strength,
                    icon_of(w),
                )
            assert quiet(w) == []


@needs_daemon
def test_a_strength_that_moves_inside_the_tooltips_five_sends_nothing() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            net.wifi(72)
            assert d.settle(w, lambda: icon_of(w) == "wifi-strength-3")
            calls = counting(w)
            net.ap["one"].set("Strength", 73)  # 72 to 73: the same icon, the same 70 %
            net.ap["one"].set("Strength", 71)
            net.ap["one"].set("Strength", 74)
            d.settle(w, lambda: False, 0.4)
            assert calls == [], calls
            net.ap["one"].set("Strength", 75)  # the step and the 5 change
            assert wait_for(lambda: calls)
            assert sorted(set(calls)) == ["icon", "label", "strength", "tooltip"]
            assert icon_of(w) == "wifi-strength-4" or d.settle(
                w, lambda: icon_of(w) == "wifi-strength-4"
            )


@needs_daemon
def test_a_value_is_sent_only_when_it_changed() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "ethernet")
            calls = counting(w)
            net.manager.set("State", 70)  # the same
            net.manager.set("Connectivity", 4)  # the same
            net.manager.set("WirelessEnabled", True)  # a property nothing reads
            net.dev["eth"].set("Interface", "eth9")
            net.dev["eth"].set("State", 100)
            d.settle(w, lambda: False, 0.4)
            assert calls == []
            net.manager.set("Connectivity", 3)
            assert wait_for(lambda: calls)
            assert "state" in calls and "kind" not in calls and "name" not in calls


@needs_daemon
def test_a_portal_and_a_limited_connection_show_the_alert_icons_in_the_warning_colour() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "ethernet")
            net.manager.set("Connectivity", 2)
            assert d.settle(w, lambda: icon_of(w) == "lan-disconnect")
            assert values(w)["state"] == "PORTAL" and "sign-in required" in values(w)["tooltip"]
            assert glyph(w).get("svg_color") == (*WARNING, 255)
            net.wifi(60)
            net.manager.set("Connectivity", 2)  # the helper says 4: the portal again
            assert d.settle(w, lambda: icon_of(w) == "wifi-alert")
            assert values(w)["state"] == "PORTAL"
            net.manager.set("Connectivity", 3)  # no internet
            assert d.settle(w, lambda: values(w)["state"] == "LIMITED")
            assert icon_of(w) == "wifi-alert" and "limited connectivity" in values(w)["tooltip"]
            net.manager.set("Connectivity", 4)
            net.manager.set("State", 50)  # local only
            assert d.settle(w, lambda: values(w)["state"] == "LIMITED")
            net.manager.set("State", 60)
            net.manager.set("State", 70)
            assert d.settle(w, lambda: icon_of(w) == "wifi-strength-3")
            assert glyph(w).get("svg_color") == (*TEXT, 255)  # back to the text colour


@needs_daemon
def test_connecting_shows_the_pending_icons() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "ethernet")
            net.manager.set("State", 40)
            assert d.settle(w, lambda: icon_of(w) == "lan-pending")
            net.wifi(60)
            net.manager.set("State", 40)
            assert d.settle(w, lambda: icon_of(w) == "wifi-sync")
            assert values(w)["tooltip"] == "Home-WiFi, Wi-Fi 60 %, connecting"
            net.manager.set("State", 70)
            net.conn["wifi"].set("State", 1)  # the connection itself is activating
            assert d.settle(w, lambda: icon_of(w) == "wifi-sync")
            net.conn["wifi"].set("State", 2)
            assert d.settle(w, lambda: icon_of(w) == "wifi-strength-3")


@needs_daemon
def test_wifi_switched_off_is_network_off_unless_the_manager_says_disabled() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            net.nothing()
            assert d.settle(w, lambda: icon_of(w) == "network-off")
            net.manager.set("WirelessEnabled", False)
            d.settle(w, lambda: False, 0.3)
            assert icon_of(w) == "network-off"  # Wi-Fi off alone says nothing
            net.manager.set("State", 10)  # NetworkManager says the network is off
            assert d.settle(w, lambda: icon_of(w) == "wifi-off")
            assert values(w)["state"] == "DISABLED" and values(w)["tooltip"] == "Networking off"
            net.manager.set("State", 20)
            net.manager.set("NetworkingEnabled", False)
            d.settle(w, lambda: False, 0.1)
            assert d.settle(w, lambda: icon_of(w) == "wifi-off")
            net.manager.set("NetworkingEnabled", True)
            assert d.settle(w, lambda: icon_of(w) == "network-off")
            assert glyph(w).get("svg_color") == (*MUTED, 255)


@needs_daemon
def test_a_vpn_shows_a_second_icon_over_the_kind_and_show_vpn_false_hides_it() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }\nNetwork { show_vpn: false }") as w:
            first, second = w.uses

            def both(shown_first: bool, shown_second: bool) -> bool:
                def vpn(use_index: int) -> bool:
                    names = [
                        n
                        for k, n in w.view.nodes.items()
                        if f"Network_{use_index + 1}/Vpn" in k and n.get("visible")
                    ]
                    return any(n.get("visible") for n in names)

                return vpn(0) is shown_first and vpn(1) is shown_second

            assert d.settle(w, lambda: w.store.values[first].get("icon") == "ethernet")
            assert both(False, False)
            net.with_vpn(True)
            assert d.settle(w, lambda: w.store.values[first].get("vpn") is True)
            assert w.store.values[first]["icon"] == "ethernet"  # a VPN is never the kind
            assert (
                w.store.values[first]["tooltip"]
                == "Wired connection 1, ethernet, connected, VPN Work VPN"
            )
            assert d.settle(w, lambda: both(True, False))  # shown by the first, not the second
            net.with_vpn(False)
            assert d.settle(w, lambda: both(False, False))
            assert w.store.values[first]["vpn"] is False


@needs_daemon
def test_a_vpn_over_wifi_still_shows_the_wifi_and_a_vpn_that_is_primary_does_not_replace_it() -> (
    None
):
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            net.wifi(60)
            net.with_vpn(True, base="wifi")
            assert d.settle(w, lambda: icon_of(w) == "wifi-strength-3" and vpn_shown(w))
            # the VPN takes over as the primary connection: the link under it is still described
            net.manager.set("ActiveConnections", [AC["vpn"], AC["wifi"]])
            net.manager.set("PrimaryConnection", AC["vpn"])
            d.settle(w, lambda: False, 0.4)
            assert icon_of(w) == "wifi-strength-3" and vpn_shown(w)
            assert values(w)["kind"] == "WIFI" and values(w)["name"] == "Home-WiFi"
            assert quiet(w) == []


@needs_daemon
def test_roaming_replaces_the_access_point_and_the_old_one_is_no_longer_heard() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        monitor = d.system.monitor()
        try:
            with shell(d, "Network { }") as w:
                net.wifi(72, "one")
                assert d.settle(w, lambda: icon_of(w) == "wifi-strength-3")
                me = d.service.system._conn.unique_name  # type: ignore[attr-defined]
                assert wait_for(lambda: monitor.added(me, f"path='{AP['one']}'"))
                net.wifi(30, "two")  # roams to another access point
                assert d.settle(w, lambda: values(w)["name"] == "Cafe-Mesh")
                assert icon_of(w) == "wifi-strength-2" and values(w)["strength"] == 30
                assert wait_for(lambda: not monitor.added(me, f"path='{AP['one']}'"))
                assert monitor.added(me, f"path='{AP['two']}'")
                calls = counting(w)
                net.ap["one"].set("Strength", 100)  # the one it left
                d.settle(w, lambda: False, 0.4)
                assert calls == [] and icon_of(w) == "wifi-strength-2"
                net.ap["two"].set("Strength", 90)
                assert d.settle(w, lambda: icon_of(w) == "wifi-strength-4")
        finally:
            monitor.stop()


@needs_daemon
def test_a_change_of_the_primary_connection_replaces_the_subscriptions_on_its_objects() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        monitor = d.system.monitor()
        try:
            with shell(d, "Network { }") as w:
                assert d.settle(w, lambda: icon_of(w) == "ethernet")
                me = d.service.system._conn.unique_name  # type: ignore[attr-defined]
                assert wait_for(lambda: monitor.added(me, f"path='{DEV['eth']}'"))
                one_rule_each = [
                    monitor.added(me, f"path='{AC['wired']}'"),
                    monitor.added(me, f"path='{DEV['eth']}'"),
                ]
                assert all(len(r) == 1 for r in one_rule_each), one_rule_each
                assert monitor.added(me, f"path='{MANAGER_PATH}'")
                net.wifi(60)
                assert d.settle(w, lambda: icon_of(w) == "wifi-strength-3")
                assert wait_for(lambda: not monitor.added(me, f"path='{AC['wired']}'"))
                assert wait_for(lambda: not monitor.added(me, f"path='{DEV['eth']}'"))
                for path in (AC["wifi"], DEV["wlan"], AP["one"]):
                    assert monitor.added(me, f"path='{path}'"), path
                # the Device and the Device.Wireless interface are two rules on one path
                assert len(monitor.added(me, f"path='{DEV['wlan']}'")) == 2
                calls = counting(w)
                net.dev["eth"].set("DeviceType", 8)  # the old device changes: nobody is listening
                net.conn["wired"].set("Id", "other")
                d.settle(w, lambda: False, 0.4)
                assert calls == []
                net.nothing()
                assert d.settle(w, lambda: icon_of(w) == "network-off")
                assert wait_for(lambda: not monitor.added(me, f"path='{DEV['wlan']}'"))
                assert not monitor.added(me, f"path='{AP['one']}'")
        finally:
            monitor.stop()


@needs_daemon
def test_a_device_type_gives_the_kind() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "ethernet")
            for code, kind, icon in (
                (8, "MOBILE", "cellphone-wireless"),
                (5, "BLUETOOTH", "bluetooth"),
                (29, "OTHER", "network"),
                (1, "ETHERNET", "ethernet"),
            ):
                net.dev["eth"].set("DeviceType", code)
                assert d.settle(w, lambda i=icon: icon_of(w) == i), (code, icon_of(w))
                assert values(w)["kind"] == kind


@needs_daemon
def test_an_ssid_that_is_not_utf8_or_empty_still_gives_a_name() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            net.ap["one"].set("Ssid", b"caf\xe9")
            net.wifi(60)
            assert d.settle(w, lambda: values(w)["name"] == "caf\ufffd")
            net.ap["one"].set("Ssid", b"")
            assert d.settle(w, lambda: values(w)["name"] == "Home-WiFi")  # the connection's Id


@needs_daemon
def test_a_wifi_device_with_no_access_point_shows_the_wifi_icon_and_no_percent() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            net.wireless.set("ActiveAccessPoint", NO_OBJECT)  # type: ignore[union-attr]
            net.manager.set("ActiveConnections", [AC["wifi"]])
            net.manager.set("PrimaryConnection", AC["wifi"])
            assert d.settle(w, lambda: values(w)["kind"] == "WIFI")
            assert values(w)["strength"] == -1 and values(w)["tooltip"] == "Wi-Fi, connected"
            assert icon_of(w) == "wifi-strength-1" and quiet(w) == []


@needs_daemon
def test_show_name_puts_the_connection_name_next_to_the_icon() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { show_name: true }") as w:
            net.wifi(60)
            assert d.settle(w, lambda: icon_of(w) == "wifi-strength-3")
            box = level(w)
            assert [c.get("text") for c in box.children() if c.get("kind") == "text"] == [
                "Home-WiFi"
            ]
    with desk() as d:
        fake, _ = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "ethernet")
            assert [c for c in level(w).children() if c.get("kind") == "text"] == []


# -- NetworkManager leaves and returns ----------------------------------------------------------


@needs_daemon
def test_no_networkmanager_at_all_is_hidden_without_a_crash_and_shows_when_it_appears() -> None:
    with desk() as d:  # no fake NetworkManager on the system bus
        with shell(d, "Network { }") as w:
            d.settle(w, lambda: False, 0.5)
            assert values(w)["available"] is False and level(w) is None
            assert [x for x in w.lines if "| ERROR " in x] == []
            fake, _ = d.network()
            fake.up()
            assert d.settle(w, lambda: icon_of(w) == "ethernet")


@needs_daemon
def test_networkmanager_leaving_hides_the_module_with_one_warning_and_returning_shows_it() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "ethernet")
            fake.down()
            assert d.settle(w, lambda: level(w) is None)
            assert values(w)["available"] is False
            warned = [x for x in w.lines if "| WARNING " in x]
            assert len(warned) == 1
            assert "org.freedesktop.NetworkManager left the system bus" in warned[0]
            # it comes back with another primary connection: the module follows the new objects
            net.manager.silent_set("PrimaryConnection", AC["wifi"])
            net.manager.silent_set("ActiveConnections", [AC["wifi"]])
            net.wireless.silent_set("ActiveAccessPoint", AP["two"])  # type: ignore[union-attr]
            fake.up()
            assert d.settle(w, lambda: icon_of(w) == "wifi-strength-2"), (icon_of(w), values(w))
            assert values(w)["available"] is True and values(w)["name"] == "Cafe-Mesh"
            net.ap["two"].set("Strength", 90)  # and hears the new access point
            assert d.settle(w, lambda: icon_of(w) == "wifi-strength-4")
            assert [x for x in w.lines if "| ERROR " in x] == []


@needs_daemon
def test_networkmanager_restarting_gives_new_objects_and_the_module_follows_them() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            net.wifi(60)
            assert d.settle(w, lambda: icon_of(w) == "wifi-strength-3")
            fake.restart()  # the process goes away and comes back (new connection, same objects)
            assert d.settle(w, lambda: icon_of(w) == "wifi-strength-3")
            net.ap["one"].set("Strength", 90)
            assert d.settle(w, lambda: icon_of(w) == "wifi-strength-4")


@needs_daemon
def test_a_module_used_twice_shares_one_follow_and_a_use_added_later_gets_the_values() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        monitor = d.system.monitor()
        try:
            with shell(d, "Network { }\nNetwork { show_name: true }") as w:
                first, second = w.uses
                assert d.settle(
                    w,
                    lambda: all(
                        w.store.values[u].get("icon") == "ethernet" for u in (first, second)
                    ),
                )
                me = d.service.system._conn.unique_name  # type: ignore[attr-defined]
                assert len(monitor.added(me, f"path='{DEV['eth']}'")) == 1  # one rule, two uses
        finally:
            monitor.stop()


# -- what it draws ------------------------------------------------------------------------------


def near(px: tuple[int, ...], want: tuple[int, ...], tol: int = 40) -> bool:
    return all(abs(a - b) <= tol for a, b in zip(px[:3], want[:3], strict=True))


def glyph_pixels(w: Widgets, want: tuple[int, ...], which: int = 0) -> int:
    """How many pixels of the colour ``want`` the Bar's drawing has inside the shown icon's box."""
    node = icons(w)[which]
    x, y, gw, gh = (
        int(node.get(k)) for k in ("layout_x", "layout_y", "layout_width", "layout_height")
    )
    assert (gw, gh) == (16, 16)
    rgba, width, _ = w.window.snapshot()
    return sum(
        near(tuple(rgba[(row * width + col) * 4 : (row * width + col) * 4 + 4]), want)
        for row in range(y, y + gh)
        for col in range(x, x + gw)
    )


@needs_daemon
def test_the_icon_is_drawn_in_each_state_in_its_colour_and_no_node_is_made_or_lost() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "ethernet")
            names = set(w.view.nodes)
            looks = {k: n for k, n in w.view.nodes.items() if "/Glyph" in k}
            assert len(looks) == 3
            assert glyph_pixels(w, TEXT) > 20
            before = len([x for x in w.lines if "rebuilt" in x])
            steps: list[tuple[str, Any, tuple[int, ...]]] = [
                ("limited", lambda: net.manager.set("Connectivity", 3), WARNING),
                ("disconnected", net.nothing, MUTED),
                ("wifi", lambda: net.wifi(80), TEXT),
                ("disabled", lambda: net.manager.set("State", 10), MUTED),
                ("wired", net.wired, TEXT),
            ]
            for label, act, want in steps:
                act()
                assert d.settle(w, lambda: True, 0.05)
                d.settle(w, lambda: False, 0.35)
                w.advance(16)
                assert set(w.view.nodes) == names, label  # nothing created, nothing removed
                assert all(w.view.nodes[k] == n for k, n in looks.items())
                assert glyph_pixels(w, want) > 20, f"{label}: the icon is not drawn in {want}"
                for other in (TEXT, WARNING, MUTED):
                    if other != want:
                        assert glyph_pixels(w, other) < 8, (label, other)
            rebuilt = [x for x in w.lines if "rebuilt" in x][before:]
            assert rebuilt == [] or all("0 created, 0 removed" in x for x in rebuilt), rebuilt


@needs_daemon
def test_the_vpn_icon_is_drawn_when_shown_and_no_node_is_made_for_it() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "ethernet")
            names = set(w.view.nodes)
            assert not vpn_shown(w)
            net.with_vpn(True)
            assert d.settle(w, lambda: vpn_shown(w))
            w.advance(16)
            assert glyph_pixels(w, TEXT, which=1) > 20  # the second icon is drawn
            assert set(w.view.nodes) == names


@needs_daemon
def test_the_icon_only_module_keeps_its_size_at_every_state_so_its_tooltip_area_stays() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "ethernet")
            (root,) = [n for k, n in w.view.nodes.items() if k.endswith("/Root")]
            sizes = []
            for act in (
                net.wired,
                lambda: net.manager.set("Connectivity", 3),
                net.nothing,
                lambda: net.wifi(60),
            ):
                act()
                d.settle(w, lambda: False, 0.35)
                w.advance(16)
                sizes.append((root.get("layout_width"), root.get("layout_height")))
            assert all(w_ >= 16 and h_ >= 16 for w_, h_ in sizes), sizes
            assert len({s for s in sizes}) == 1  # the same box for every icon


# -- no thread, no timer, the work per signal ---------------------------------------------------


@needs_daemon
def test_the_module_starts_no_thread_and_calls_nothing_blocking() -> None:
    import threading

    with desk() as d:
        fake, _ = d.network()
        fake.up()
        before = {t.name for t in threading.enumerate()}
        with shell(d, "Network { }") as w:
            assert d.settle(w, lambda: icon_of(w) == "ethernet")
            assert {t.name for t in threading.enumerate()} - before == set()
    source = (SHIPPED / "Network" / "Network_Module.py").read_text()
    for word in (
        "threading",
        "Thread(",
        "run_blocking",
        "every(",
        "on_tick",
        "sleep",
        "subprocess",
    ):
        assert word not in source, word
    assert "CheckConnectivity" not in source and ".set(" not in source  # read-only, no calls


@needs_daemon
def test_the_module_never_writes_to_networkmanager() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            net.wifi(60)
            assert d.settle(w, lambda: icon_of(w) == "wifi-strength-3")
            net.nothing()
            assert d.settle(w, lambda: icon_of(w) == "network-off")
        everything = [net.manager, *net.conn.values(), *net.dev.values(), *net.ap.values()]
        assert net.wireless is not None
        assert [o.calls for o in [*everything, net.wireless]] == [[]] * (len(everything) + 1)


@needs_daemon
def test_per_signal_module_work_is_far_under_a_millisecond(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            net.wifi(50)
            assert d.settle(w, lambda: icon_of(w) == "wifi-strength-3")
            start = len(d.layer.callback_times.get("Network", ()))
            for i in range(150):
                net.ap["one"].set("Strength", i % 100)
                net.manager.set("Connectivity", 3 + (i % 2))
            assert d.settle(w, lambda: len(d.layer.callback_times["Network"]) - start >= 300, 10)
            count, p50, p99, worst = d.layer.callback_summary("Network")
            with capsys.disabled():
                print(
                    f"\nNetwork callback: n={count} p50={p50 * 1e6:.1f} us "
                    f"p99={p99 * 1e6:.1f} us max={worst * 1e6:.1f} us"
                )
            assert p99 < 0.001


@needs_daemon
def test_a_burst_of_strength_signals_changes_the_bar_only_at_a_step_or_a_five() -> None:
    with desk() as d:
        fake, net = d.network()
        fake.up()
        with shell(d, "Network { }") as w:
            net.wifi(50)
            assert d.settle(w, lambda: icon_of(w) == "wifi-strength-3")
            calls = counting(w)
            wobble = [50, 51, 49, 52, 50, 53, 51, 54, 50]  # 50 to 54 shows 50 %, 49 shows 45
            for strength in wobble:
                net.ap["one"].set("Strength", strength)
            time.sleep(0.2)
            d.settle(w, lambda: False, 0.4)
            # only the 49 (step 2 and 45 %) and its way back are changes
            assert calls.count("tooltip") == 2 and calls.count("icon") == 2, calls


# -- a hidden module takes no Bar space ---------------------------------------------------------


@needs_daemon
def test_a_network_with_no_networkmanager_takes_no_space_and_a_disconnected_one_does() -> None:
    from tests.test_hidden_module import gap, row

    with desk() as d, shell(d, row("Network { }", "Network { show_name: true }")) as w:
        d.settle(w, lambda: False, 0.3)
        assert gap(w) == 8  # hidden: no second gap, no zero-size box
        fake, net = d.network()
        fake.up()  # NetworkManager appears: both show
        assert d.settle(w, lambda: gap(w) > 8 + 8)
        (root,) = [n for k, n in w.view.nodes.items() if k.endswith("/Root") and "Network_1" in k]
        width = float(root.get("layout_width"))
        assert width >= 16
        net.nothing()  # a disconnected machine is not hidden: it shows `network-off`
        d.settle(w, lambda: False, 0.4)
        assert gap(w) > 8 + 8
        fake.down()  # NetworkManager leaves: the space goes
        assert d.settle(w, lambda: gap(w) == 8)
