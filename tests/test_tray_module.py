"""The shipped Tray (Tray Module): the derivations, then the module on a fake watcher, fake
StatusNotifierItems and a fake ``com.canonical.dbusmenu`` on a private session bus, drawn by the
real binder in a headless Bar, with the real icon service on a temporary theme folder and the real
tray host service. Every acceptance bullet of the spec is a test here; nothing touches the real
session bus, the real watcher or a real item."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tess_shell.files.icons import IconSets
from tests.fake_dbus import HAVE_DAEMON, wait_for
from tests.fake_sni import Item, Node, sample_tree
from tests.icon_theme import Dir, png_bytes, svg, write_theme
from tests.test_dbus_own_name import owner_of
from tests.tray_rig import HOST_NAME, TrayDesk, tray_desk, tray_shell
from tests.widgets_live import SHIPPED, Widgets, running

needs_daemon = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")


def load() -> ModuleType:
    path = SHIPPED / "Tray" / "Tray_Module.py"
    spec = importlib.util.spec_from_file_location("shipped_tray", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


T = load()
SETS = IconSets([SHIPPED / "Icons"])


# -- the derivations ----------------------------------------------------------------------------


def test_an_item_is_a_bus_name_and_a_path_and_a_bare_name_has_the_default_path() -> None:
    assert T.parse_service("org.kde.StatusNotifierItem-927553-1/StatusNotifierItem") == (
        "org.kde.StatusNotifierItem-927553-1",
        "/StatusNotifierItem",
    )
    assert T.parse_service(":1.55") == (":1.55", "/StatusNotifierItem")
    assert T.parse_service(":1.55/org/ayatana/Item") == (":1.55", "/org/ayatana/Item")


def test_a_tooltip_loses_its_markup_and_the_label_says_attention() -> None:
    assert T.tooltip_of(["", [], "Cachy-Update", "95 updates <b>available</b> &amp; more"]) == (
        "Cachy-Update",
        "95 updates available & more",
    )
    assert T.tooltip_of(None) == ("", "")
    assert T.label_of("Chat", True) == "Chat, needs attention"
    assert T.label_of("Chat", False) == "Chat"


def test_a_mnemonic_is_taken_out_and_two_underscores_are_one() -> None:
    assert T.mnemonic("Open _Window") == "Open Window"
    assert T.mnemonic("a__b") == "a_b"
    assert T.mnemonic("plain") == "plain"
    assert T.shortcut([["Control", "Shift", "Q"]]) == "Ctrl+Shift+Q"
    assert T.shortcut([]) == "" and T.shortcut(None) == ""


def test_the_fallback_icon_is_in_the_shipped_mdi_set() -> None:
    assert SETS.lookup(T.FALLBACK_ICON) is not None
    assert SETS.lookup("mdi:check") and SETS.lookup("mdi:radiobox-marked")
    assert SETS.lookup("mdi:radiobox-blank")


# -- helpers ------------------------------------------------------------------------------------


def tray_uses(w: Widgets) -> list[str]:
    return [u for u in w.uses if u.startswith("Tray@")]


def values(w: Widgets, index: int = 0) -> dict[str, Any]:
    return dict(w.store.values[tray_uses(w)[index]])


def ids(w: Widgets) -> list[str]:
    return [i["id"] for i in values(w).get("items", [])]


def root(w: Widgets) -> Any:
    return w.of_use("Tray", "Root")


def shown(w: Widgets) -> bool:
    return bool(root(w).get("visible"))


def item_node(w: Widgets, index: int = 0) -> Any:
    """The Root of the ``index``-th Tray_Item (in the order of the keys)."""
    keys = sorted(k for k in w.view.nodes if "/Tray_Item@" in k and k.endswith("/Root"))
    return w.view.nodes[keys[index]]


def settle(t: TrayDesk, w: Widgets, predicate: Any, timeout: float = 5.0) -> bool:
    return t.d.settle(w, predicate, timeout)


def up(t: TrayDesk, *items: Item) -> None:
    for item in items:
        item.up()
        t.watcher.register(item)


# -- the module on fakes ------------------------------------------------------------------------


@needs_daemon
def test_with_no_watcher_the_module_is_empty_and_takes_no_space_and_a_watcher_shows_the_items(
    tmp_path: Path,
) -> None:
    with tray_desk(tmp_path, watcher_up=False) as t:
        item = t.item()
        item.up()
        t.watcher.object.silent_set("RegisteredStatusNotifierItems", [item.registered])
        with tray_shell(t) as w:
            assert settle(t, w, lambda: values(w).get("available") is False)
            settle(t, w, lambda: False, 0.3)
            assert not shown(w) and values(w)["has_items"] is False and values(w)["items"] == []
            assert float(root(w).get("layout_width") or 0) == 0  # no space on the Bar
            warned = [x for x in w.warnings() if "StatusNotifierWatcher" in x]
            assert len(warned) == 1, w.warnings()
            t.watcher.up()  # no shell restart
            assert settle(t, w, lambda: shown(w) and ids(w) == [item.registered])
            assert float(root(w).get("layout_width") or 0) > 0
            assert len([x for x in w.warnings() if "StatusNotifierWatcher" in x]) == 1


@needs_daemon
def test_a_registered_item_appears_with_its_texts_and_an_unregistered_one_disappears(
    tmp_path: Path,
) -> None:
    with tray_desk(tmp_path) as t:
        first = t.item("1-1", title="Chat", tooltip=("", [], "Chat", "3 unread"))
        with tray_shell(t) as w:
            assert settle(t, w, lambda: values(w).get("available") is True)
            assert not shown(w)  # nothing registered yet
            up(t, first)
            assert settle(t, w, lambda: shown(w) and ids(w) == [first.registered])
            (entry,) = values(w)["items"]
            assert (entry["title"], entry["status"], entry["attention"]) == (
                "Chat",
                "Active",
                False,
            )
            assert (entry["tooltip_title"], entry["tooltip_text"]) == ("Chat", "3 unread")
            assert entry["label"] == "Chat" and entry["description"] == "3 unread"
            assert entry["icon"].startswith("<svg") and "#ff0000" in entry["icon"]
            second = t.item("2-1", title="Sync")
            up(t, second)
            assert settle(t, w, lambda: ids(w) == [first.registered, second.registered])
            t.watcher.unregister(first)
            assert settle(t, w, lambda: ids(w) == [second.registered])
            assert w.warnings() == [], w.warnings()


@needs_daemon
def test_an_item_that_leaves_the_bus_without_unregistering_is_removed(tmp_path: Path) -> None:
    with tray_desk(tmp_path) as t:
        a, b = t.item("1-1"), t.item("2-1")
        up(t, a, b)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: len(ids(w)) == 2)
            a.drop()  # the application died: its name has no owner
            assert settle(t, w, lambda: ids(w) == [b.registered])
            b.drop()
            assert settle(t, w, lambda: ids(w) == [] and not shown(w))


@needs_daemon
def test_the_shell_owns_the_host_name_registers_once_and_again_after_the_watcher_restarts(
    tmp_path: Path,
) -> None:
    with tray_desk(tmp_path) as t:
        item = t.item()
        up(t, item)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: ids(w) == [item.registered])
            assert t.watcher.hosts == [HOST_NAME]  # RegisterStatusNotifierHost, once
            assert owner_of(t.d.session, HOST_NAME) is not None
            t.watcher.restart()  # the fake watcher process restarts; its list survives in the fake
            assert wait_for(lambda: t.watcher.hosts == [HOST_NAME, HOST_NAME], 5), t.watcher.hosts
            assert settle(t, w, lambda: ids(w) == [item.registered] and shown(w))


@needs_daemon
def test_each_new_signal_changes_its_value_after_one_fresh_read(tmp_path: Path) -> None:
    with tray_desk(tmp_path) as t:
        item = t.item(title="Old", tooltip=("", [], "Old", "old text"), attention_icon="hi-icon")
        up(t, item)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: ids(w) == [item.registered])
            first = values(w)["items"][0]["icon"]
            write_theme(
                t.theme,
                "Fake",
                [Dir("scalable/apps", 48, "Scalable", {"other.svg": svg("#123456")})],
                inherits=["hicolor"],
            )
            t.icons.invalidate()
            before = len(item.calls)
            item.changed("NewIcon", IconName="other")
            assert settle(t, w, lambda: "#123456" in values(w)["items"][0]["icon"])
            assert values(w)["items"][0]["icon"] != first
            item.changed("NewTitle", Title="New")
            assert settle(t, w, lambda: values(w)["items"][0]["title"] == "New")
            item.changed("NewToolTip", ToolTip=("", [], "New tip", "new text"))
            assert settle(t, w, lambda: values(w)["items"][0]["tooltip_text"] == "new text")
            assert values(w)["items"][0]["tooltip_title"] == "New tip"
            item.changed("NewStatus", Status="NeedsAttention")
            assert settle(t, w, lambda: values(w)["items"][0]["attention"] is True)
            assert "#00ffff" in values(w)["items"][0]["icon"]  # the attention icon replaces it
            assert values(w)["items"][0]["label"] == "New, needs attention"
            item.changed("NewStatus", Status="Active")
            assert settle(t, w, lambda: values(w)["items"][0]["attention"] is False)
            assert "#123456" in values(w)["items"][0]["icon"]
            item.changed("NewOverlayIcon", OverlayIconName="x")  # read, not drawn
            settle(t, w, lambda: False, 0.2)
            assert len(item.calls) == before  # reading is not a click: no method was called
            assert w.warnings() == [], w.warnings()


@needs_daemon
def test_a_passive_item_is_hidden_unless_show_passive_and_the_module_hides_with_none(
    tmp_path: Path,
) -> None:
    with tray_desk(tmp_path) as t:
        item = t.item(status="Passive")
        up(t, item)
        with tray_shell(t, "Tray { } Tray { show_passive: true }") as w:
            assert settle(t, w, lambda: ids(w) == [] and ids_of(w, 1) == [item.registered])
            assert values(w)["has_items"] is False and values(w, 1)["has_items"] is True
            item.changed("NewStatus", Status="Active")
            assert settle(t, w, lambda: ids(w) == [item.registered])
            item.changed("NewStatus", Status="Passive")
            assert settle(t, w, lambda: ids(w) == [])
            assert ids_of(w, 1) == [item.registered]


def ids_of(w: Widgets, index: int) -> list[str]:
    return [i["id"] for i in values(w, index).get("items", [])]


@needs_daemon
def test_a_status_or_text_change_replaces_no_node_and_an_attention_icon_swap_keeps_the_svg(
    tmp_path: Path,
) -> None:
    with tray_desk(tmp_path) as t:
        item = t.item(attention_icon="hi-icon")
        up(t, item)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: ids(w) == [item.registered])
            nodes = dict(w.view.nodes)
            item.changed("NewTitle", Title="Another")
            item.changed("NewToolTip", ToolTip=("", [], "T", "x"))
            item.changed("NewStatus", Status="NeedsAttention")
            assert settle(t, w, lambda: values(w)["items"][0]["attention"] is True)
            settle(t, w, lambda: False, 0.2)
            assert {k: n for k, n in w.view.nodes.items() if k in nodes} == nodes
            assert set(w.view.nodes) == set(nodes)  # none created, none removed
            node = item_node(w)
            assert node.get("label") == "Another, needs attention"


def centre(node: Any) -> tuple[int, int]:
    x, y, wd, ht = (
        float(node.get(k)) for k in ("layout_x", "layout_y", "layout_width", "layout_height")
    )
    return round(x + wd / 2), round(y + ht / 2)


def calls(item: Item, name: str) -> list[tuple[Any, ...]]:
    return [a for m, a in item.calls if m == name]


@needs_daemon
def test_the_clicks_call_activate_secondary_activate_and_scroll_with_the_items_centre(
    tmp_path: Path,
) -> None:
    with tray_desk(tmp_path) as t:
        a, b = t.item("1-1"), t.item("2-1")
        up(t, a, b)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: len(ids(w)) == 2)
            second = item_node(w, 1)
            w.window.simulate("click", node=second)
            assert wait_for(lambda: len(calls(b, "Activate")) == 1)
            assert calls(b, "Activate") == [centre(second)]  # once, at the item's centre
            w.window.simulate("pointer_down", node=second, button="middle")
            w.window.simulate("pointer_up", node=second, button="middle")
            assert wait_for(lambda: len(calls(b, "SecondaryActivate")) == 1)
            assert calls(b, "SecondaryActivate") == [centre(second)]
            w.window.simulate("wheel", node=second, delta_y=40.0)  # one step down
            w.window.simulate("wheel", node=second, delta_y=-40.0)  # one step up
            assert wait_for(lambda: len(calls(b, "Scroll")) == 2)
            assert calls(b, "Scroll") == [(-120, "vertical"), (120, "vertical")]
            settle(t, w, lambda: False, 0.2)
            assert calls(a, "Activate") == [] and calls(b, "Activate") == [centre(second)]
            assert calls(b, "ContextMenu") == []  # an item with a menu: the shell's menu
            assert w.warnings() == [], w.warnings()


@needs_daemon
def test_a_primary_click_on_an_item_that_is_a_menu_opens_the_menu_instead(tmp_path: Path) -> None:
    with tray_desk(tmp_path) as t:
        item = t.item(menu=sample_tree(), item_is_menu=True)
        up(t, item)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: ids(w) == [item.registered])
            w.window.simulate("click", node=item_node(w))
            assert settle(t, w, lambda: w.manager.popups.current is not None)
            assert calls(item, "Activate") == []
            assert item.menu is not None
            assert [m for m, _ in item.menu.calls if m in ("AboutToShow", "GetLayout")] == [
                "AboutToShow",
                "GetLayout",
            ]


@needs_daemon
def test_a_secondary_click_on_an_item_without_a_menu_calls_context_menu(tmp_path: Path) -> None:
    with tray_desk(tmp_path) as t:
        item = t.item()  # Menu is /NO_DBUSMENU
        up(t, item)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: ids(w) == [item.registered])
            node = item_node(w)
            w.window.simulate("secondary_click", node=node)
            assert wait_for(lambda: len(calls(item, "ContextMenu")) == 1)
            assert calls(item, "ContextMenu") == [centre(node)]
            settle(t, w, lambda: False, 0.2)
            assert w.manager.popups.current is None


def labels(op: Any) -> list[str]:
    return [
        str(n.get("label"))
        for k, n in op.view.nodes.items()
        if k.endswith("/Root") and n.get("role") == "menuitem"
    ]


def row(op: Any, label: str) -> Any:
    (found,) = [n for n in op.view.nodes.values() if n.get("label") == label]
    return found


@needs_daemon
def test_a_secondary_click_opens_the_menu_from_the_tree_and_a_click_sends_event_once(
    tmp_path: Path,
) -> None:
    with tray_desk(tmp_path) as t:
        item = t.item(menu=sample_tree())
        up(t, item)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: ids(w) == [item.registered])
            w.window.simulate("secondary_click", node=item_node(w))
            assert settle(t, w, lambda: w.manager.popups.current is not None), w.log()[-3000:]
            op = w.manager.popups.current
            assert item.menu is not None
            sent = [(m, a) for m, a in item.menu.calls if m in ("AboutToShow", "GetLayout")]
            assert sent == [("AboutToShow", (0,)), ("GetLayout", (0, -1, []))]  # before the draw
            assert labels(op) == [
                "Open Window",  # the mnemonic is gone
                "Disabled, disabled",
                "Checked, checked",
                "Radio on, checked",
                "Radio off, not checked",
                "Quit",
                "More",
            ]
            roles = [n.get("role") for k, n in op.view.nodes.items() if k.endswith("/Root")]
            assert roles.count("separator") == 1  # a rule
            assert row(op, "Disabled, disabled").get("disabled") is True
            assert row(op, "Quit").get("disabled") is not True
            assert not [x for x in labels(op) if x == "Hidden"]  # visible: false
            data = op.caller.data["menus"]["0"]
            assert [e["shortcut"] for e in data if e["text"] == "Quit"] == ["Ctrl+Q"]
            assert [e["icon"] for e in data if e["text"] == "Checked"] == ["mdi:check"]
            assert [e["icon"] for e in data if e["text"] == "Radio on"] == ["mdi:radiobox-marked"]
            assert [e["icon"] for e in data if e["text"] == "Radio off"] == ["mdi:radiobox-blank"]
            quit_icon = [e["icon"] for e in data if e["text"] == "Quit"][0]
            assert (
                quit_icon.startswith("<svg") and "#0000ff" in quit_icon
            )  # icon-name from the theme
            op.window.simulate("click", node=row(op, "Quit"))
            assert wait_for(lambda: item.menu.clicked() == [7])  # Event(7, "clicked", ...), once
            op.window.advance(50)
            assert w.manager.popups.current is None  # the menu closed
            settle(t, w, lambda: False, 0.2)
            assert item.menu.clicked() == [7]
            (event,) = [a for m, a in item.menu.calls if m == "Event"]
            assert event[1] == "clicked" and isinstance(event[3], int)
            assert w.warnings() == [], w.warnings()


@needs_daemon
def test_a_disabled_entry_sends_nothing_and_a_submenu_opens_to_three_levels(
    tmp_path: Path,
) -> None:
    with tray_desk(tmp_path) as t:
        item = t.item(menu=sample_tree())
        up(t, item)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: ids(w) == [item.registered])
            w.window.simulate("secondary_click", node=item_node(w))
            assert settle(t, w, lambda: w.manager.popups.current is not None)
            op = w.manager.popups.current
            assert item.menu is not None
            op.window.simulate("click", node=row(op, "Disabled, disabled"))
            settle(t, w, lambda: False, 0.2)
            assert item.menu.clicked() == []
            op.window.simulate("click", node=row(op, "More"))  # a click opens the submenu
            assert settle(t, w, lambda: op.sub is not None)
            assert labels(op.sub) == ["First", "Deeper"]
            op.sub.window.simulate("click", node=row(op.sub, "Deeper"))
            assert settle(t, w, lambda: op.sub.sub is not None)
            assert labels(op.sub.sub) == ["Level three"]  # level four is not shown
            third = op.sub.sub
            third.window.simulate("click", node=row(third, "Level three"))
            assert wait_for(
                lambda: item.menu.clicked() == [12]
            )  # the rows with a submenu sent none
            third.window.advance(50)  # the click closes every level once its action has run
            assert w.manager.popups.current is None  # the click closed the whole menu


def open_menu(t: TrayDesk, w: Widgets, item: Item) -> Any:
    w.window.simulate("secondary_click", node=item_node(w))
    assert settle(t, w, lambda: w.manager.popups.current is not None), w.log()[-3000:]
    return w.manager.popups.current


@needs_daemon
def test_layout_updated_while_the_menu_is_open_rebuilds_its_entries(tmp_path: Path) -> None:
    with tray_desk(tmp_path) as t:
        item = t.item(menu=sample_tree())
        up(t, item)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: ids(w) == [item.registered])
            op = open_menu(t, w, item)
            assert "Quit" in labels(op)
            assert item.menu is not None
            quit_node = item.menu.root.children[6]
            quit_node.props["label"] = "Exit now"
            item.menu.root.children.append(Node(14, {"label": "Added"}))
            item.menu.updated()
            assert settle(
                t,
                w,
                lambda: (
                    w.manager.popups.current is not None
                    and "Exit now" in labels(w.manager.popups.current)
                ),
            ), w.log()[-3000:]
            fresh = w.manager.popups.current
            assert "Quit" not in labels(fresh) and labels(fresh)[-2:] == ["More", "Added"]
            # the new entries are live: a click on one sends its id
            fresh.window.simulate("click", node=row(fresh, "Added"))
            assert wait_for(lambda: item.menu.clicked() == [14])
            assert w.warnings() == [], w.warnings()
            # a change while the menu is closed opens nothing
            fresh.window.advance(50)
            settle(t, w, lambda: w.manager.popups.current is None)
            item.menu.updated()
            settle(t, w, lambda: False, 0.4)
            assert w.manager.popups.current is None


@needs_daemon
def test_an_item_that_leaves_while_its_menu_is_open_closes_the_menu(tmp_path: Path) -> None:
    with tray_desk(tmp_path) as t:
        item = t.item(menu=sample_tree())
        other = t.item("2-1")
        up(t, item, other)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: len(ids(w)) == 2)
            op = open_menu(t, w, item)
            assert op is not None
            t.watcher.unregister(item)
            assert settle(t, w, lambda: w.manager.popups.current is None), w.log()[-2000:]
            assert ids(w) == [other.registered]


@needs_daemon
def test_a_get_layout_that_fails_is_one_warning_and_no_menu_opens(tmp_path: Path) -> None:
    with tray_desk(tmp_path) as t:
        item = t.item(menu=sample_tree())
        assert item.menu is not None

        def broken(parent: int, depth: int, names: list[str]) -> Any:
            from dbus_fast import DBusError

            raise DBusError("org.test.Failed", "no layout today")

        item.menu.object._methods["GetLayout"] = (["i", "i", "as"], "u(ia{sv}av)", broken)
        up(t, item)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: ids(w) == [item.registered])
            for _ in range(2):
                w.window.simulate("secondary_click", node=item_node(w))
                settle(t, w, lambda: False, 0.3)
            assert w.manager.popups.current is None
            failed = [x for x in w.warnings() if "GetLayout" in x]
            assert len(failed) == 1, w.warnings()  # one a minute for the item


@needs_daemon
def test_an_event_call_that_fails_is_logged_once_a_minute_and_the_menu_closes(
    tmp_path: Path,
) -> None:
    with tray_desk(tmp_path) as t:
        item = t.item(menu=sample_tree())
        assert item.menu is not None

        def broken(ident: int, kind: str, data: Any, stamp: int) -> None:
            from dbus_fast import DBusError

            raise DBusError("org.test.Failed", "no event today")

        item.menu.object._methods["Event"] = (["i", "s", "v", "u"], "", broken)
        up(t, item)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: ids(w) == [item.registered])
            op = open_menu(t, w, item)
            op.window.simulate("click", node=row(op, "Quit"))
            op.window.advance(50)
            assert settle(t, w, lambda: w.manager.popups.current is None)
            assert settle(t, w, lambda: len([x for x in w.warnings() if "Event" in x]) == 1)
            op = open_menu(t, w, item)
            op.window.simulate("click", node=row(op, "Open Window"))
            op.window.advance(50)
            settle(t, w, lambda: False, 0.3)
            assert len([x for x in w.warnings() if "Event" in x]) == 1  # the second is debug


@needs_daemon
def test_with_no_popups_written_the_shipped_ones_open_the_menu_and_its_submenus(
    tmp_path: Path,
) -> None:
    with tray_desk(tmp_path) as t:
        item = t.item(menu=sample_tree())
        up(t, item)
        with tray_shell(t, popups="") as w:  # the shell file writes no Popup at all
            assert settle(t, w, lambda: ids(w) == [item.registered])
            plans = {name for _, name in w.manager.popups.plans}
            assert plans == {"Tray_Menu", "Tray_Menu_2", "Tray_Menu_3"}
            op = open_menu(t, w, item)
            assert "Quit" in labels(op)
            planned = w.bar.planned
            assert planned is not None
            popup = op.plan.popup
            assert (popup.max_height_percent, popup.attach) == (60.0, "BOTTOM")
            op.window.simulate("click", node=row(op, "More"))
            assert settle(t, w, lambda: op.sub is not None)
            assert labels(op.sub) == ["First", "Deeper"]
            op.window.simulate("click", node=row(op, "Open Window"))
            assert item.menu is not None
            assert wait_for(lambda: item.menu.clicked() == [1])
            assert w.warnings() == [], w.warnings()


@needs_daemon
def test_a_popup_of_the_same_name_in_the_shell_file_overrides_the_shipped_one(
    tmp_path: Path,
) -> None:
    mine = (
        "Popup { Name: Tray_Menu, Attach: TOP, Max_Height: 120, "
        "Style { Background: $color.surface_raised }, Children { Tray_Menu { Level: 1 } } }"
    )
    with tray_desk(tmp_path) as t:
        item = t.item(menu=sample_tree())
        up(t, item)
        with tray_shell(t, popups=mine) as w:
            assert settle(t, w, lambda: ids(w) == [item.registered])
            plans = {name: p for (_, name), p in w.manager.popups.plans.items()}
            assert set(plans) == {"Tray_Menu", "Tray_Menu_2", "Tray_Menu_3"}
            assert (plans["Tray_Menu"].popup.attach, plans["Tray_Menu"].popup.max_height) == (
                "TOP",
                120,
            )  # the user's, whole: not merged with the shipped one
            assert plans["Tray_Menu"].popup.max_height_percent is None
            assert plans["Tray_Menu_2"].popup.max_height_percent == 60.0  # the others stay shipped
            assert plans["Tray_Menu_2"].popup.attach == "BOTTOM"


def test_a_shell_that_shows_neither_the_tray_nor_audio_gets_no_shipped_popup() -> None:
    with running("Label { Text: x }") as w:
        assert w.manager.popups.plans == {}
    with running("Audio { }") as w:  # no sound service here: the module fails, the plan stays
        assert {name for _, name in w.manager.popups.plans} == {"Audio_Outputs"}
    with running("Audio { }", popups="Popup { Name: Audio_Outputs, Attach: TOP }") as w:
        (plan,) = w.manager.popups.plans.values()
        assert plan.popup.attach == "TOP"


def pixel_at(w: Widgets, x: float, y: float) -> tuple[int, ...]:
    rgba, width, _ = w.window.snapshot()
    i = (round(y) * width + round(x)) * 4
    return tuple(rgba[i : i + 4])


def argb(a: int, r: int, g: int, b: int) -> bytes:
    """One ARGB32 pixel in network byte order."""
    return bytes([a, r, g, b])


def near(px: tuple[int, ...], want: tuple[int, ...], tol: int = 48) -> bool:
    return all(abs(a - b) <= tol for a, b in zip(px[:3], want[:3], strict=True))


@needs_daemon
def test_a_pixmap_only_item_shows_its_pixmap_with_the_right_colours(tmp_path: Path) -> None:
    # a 2x2 pixmap: red, green / blue, white (alpha first, as the specification sends them)
    quad = (
        argb(255, 255, 0, 0)
        + argb(255, 0, 255, 0)
        + argb(255, 0, 0, 255)
        + argb(255, 255, 255, 255)
    )
    with tray_desk(tmp_path) as t:
        item = t.item(icon="", pixmap=[[2, 2, quad]])
        up(t, item)
        with tray_shell(t, "Tray { icon_size: 20 }") as w:
            assert settle(t, w, lambda: ids(w) == [item.registered])
            icon = values(w)["items"][0]["icon"]
            assert icon.startswith("pixels:")  # decoded pixels, never a path
            settle(t, w, lambda: False, 0.2)
            node = item_node(w)
            cx, cy = centre(node)
            # the icon is 20 px square in the middle of the item: one quadrant is 10 px
            assert near(pixel_at(w, cx - 5, cy - 5), (255, 0, 0))
            assert near(pixel_at(w, cx + 5, cy - 5), (0, 255, 0))
            assert near(pixel_at(w, cx - 5, cy + 5), (0, 0, 255))
            assert near(pixel_at(w, cx + 5, cy + 5), (255, 255, 255))
            assert w.warnings() == [], w.warnings()


@needs_daemon
def test_the_pixmap_nearest_above_the_wanted_size_is_the_one_shown(tmp_path: Path) -> None:
    small = [1, 1, argb(255, 255, 0, 0)]
    large = [4, 4, argb(255, 0, 0, 255) * 16]
    with tray_desk(tmp_path) as t:
        item = t.item(icon="", pixmap=[small, large])
        up(t, item)
        with tray_shell(t, "Tray { icon_size: 3 }") as w:  # 3 px: the 4x4 is the first above
            assert settle(t, w, lambda: ids(w) == [item.registered])
            settle(t, w, lambda: False, 0.2)
            cx, cy = centre(item_node(w))
            assert near(pixel_at(w, cx, cy), (0, 0, 255))


@needs_daemon
def test_a_pixmap_of_the_wrong_length_is_ignored_with_one_warning_naming_the_item(
    tmp_path: Path,
) -> None:
    with tray_desk(tmp_path) as t:
        item = t.item(icon="", pixmap=[[8, 8, b"\x00" * 12]])
        up(t, item)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: ids(w) == [item.registered])
            assert values(w)["items"][0]["icon"] == T.FALLBACK_ICON  # nothing else to show
            item.changed("NewTitle", Title="Again")  # read again: still one warning
            settle(t, w, lambda: values(w)["items"][0]["title"] == "Again")
            warned = [x for x in w.warnings() if "8x8" in x]
            assert len(warned) == 1 and item.registered in warned[0], w.warnings()


@needs_daemon
def test_neither_a_name_nor_a_pixmap_shows_the_fallback_icon_without_a_warning(
    tmp_path: Path,
) -> None:
    with tray_desk(tmp_path) as t:
        nothing = t.item("1-1", icon="no-such-icon-anywhere")
        up(t, nothing)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: ids(w) == [nothing.registered])
            assert values(w)["items"][0]["icon"] == "mdi:application-outline"
            assert shown(w) and float(item_node(w).get("layout_width")) > 0
            assert w.warnings() == [], w.warnings()


@needs_daemon
def test_an_icon_theme_path_of_the_item_is_looked_in_first(tmp_path: Path) -> None:
    own = tmp_path / "own"
    own.mkdir()
    (own / "special.svg").write_text(svg("#abcdef"))
    with tray_desk(tmp_path) as t:
        item = t.item(icon="special", theme_path=str(own))
        up(t, item)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: ids(w) == [item.registered])
            assert "#abcdef" in values(w)["items"][0]["icon"]


@needs_daemon
def test_an_icon_name_is_found_through_inherits_and_hicolor_preferring_the_svg(
    tmp_path: Path,
) -> None:
    with tray_desk(tmp_path) as t:
        write_theme(
            t.theme,
            "Fake",
            [
                Dir("22x22/apps", 22, "Fixed", {"both.png": png_bytes(22, 22, (9, 9, 9, 255))}),
                Dir("scalable/apps", 48, "Scalable", {"both.svg": svg("#101010")}),
            ],
            inherits=["Parent"],
        )
        write_theme(
            t.theme, "Parent", [Dir("scalable/apps", 48, "Scalable", {"up.svg": svg("#202020")})]
        )
        t.icons.invalidate()
        item = t.item("1-1", icon="both")
        parent = t.item("2-1", icon="up")
        hicolor = t.item("3-1", icon="hi-icon")
        up(t, item, parent, hicolor)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: len(ids(w)) == 3)
            got = {i["id"]: i["icon"] for i in values(w)["items"]}
            assert "#101010" in got[item.registered]  # the svg, though the png is exact
            assert "#202020" in got[parent.registered]  # one theme up
            assert "#00ffff" in got[hicolor.registered]  # hicolor


@needs_daemon
def test_a_theme_svg_is_drawn_in_the_bar_and_a_change_of_icon_keeps_the_node(
    tmp_path: Path,
) -> None:
    with tray_desk(tmp_path) as t:
        item = t.item()  # fake-icon.svg of the temporary theme: a red square
        up(t, item)
        with tray_shell(t, "Tray { icon_size: 20 }") as w:
            assert settle(t, w, lambda: ids(w) == [item.registered])
            settle(t, w, lambda: False, 0.2)
            cx, cy = centre(item_node(w))
            assert near(pixel_at(w, cx, cy), (255, 0, 0))
            nodes = set(w.view.nodes)
            item.changed("NewIcon", IconName="hi-icon")  # the cyan square of hicolor
            assert settle(t, w, lambda: "#00ffff" in values(w)["items"][0]["icon"])
            settle(t, w, lambda: False, 0.2)
            assert near(pixel_at(w, cx, cy), (0, 255, 255))
            assert set(w.view.nodes) == nodes  # the SVG node stays: its document changed


def timed_opens(t: TrayDesk, w: Widgets, count: int) -> tuple[list[float], list[float]]:
    """``count`` openings of a menu: the click to the Popup shown (what a person waits), and the
    shell's own work in it (the time ``show_menu`` runs on the loop thread)."""
    import time

    tray = w.host.loaded["Tray"].instance
    inside: list[float] = []
    real = tray.show_menu

    def timed(*args: Any) -> None:
        started = time.perf_counter()
        real(*args)
        inside.append((time.perf_counter() - started) * 1000)

    tray.show_menu = timed
    waits: list[float] = []
    for _ in range(count):
        started = time.perf_counter()
        w.window.simulate("secondary_click", node=item_node(w))
        assert settle(t, w, lambda: w.manager.popups.current is not None)
        waits.append((time.perf_counter() - started) * 1000)
        w.manager.popups.close_current("test")
        settle(t, w, lambda: w.manager.popups.current is None)
    return waits, inside


def hundred_entries() -> Node:
    return Node(0, {}, [Node(i + 1, {"label": f"Entry {i + 1}"}) for i in range(100)])


@needs_daemon
def test_a_menu_of_100_entries_is_built_and_shown_in_a_reasonable_time(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Tray Module > Performance Budget: the Popup shows within 100 ms of the click. The suite's
    bound is generous (a loaded machine); ``-m perf`` holds the 100 ms."""
    with tray_desk(tmp_path) as t:
        item = t.item(menu=hundred_entries())
        up(t, item)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: ids(w) == [item.registered])
            waits, inside = timed_opens(t, w, 5)
            with capsys.disabled():
                print(
                    f"\nTray menu of 100 entries: click to shown {min(waits):.0f} ms best of "
                    f"{len(waits)}, the shell's own work {min(inside):.0f} ms"
                )
            assert min(inside) < 150, inside


@pytest.mark.perf
@needs_daemon
def test_a_menu_of_100_entries_shows_within_100_ms_of_the_click(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with tray_desk(tmp_path) as t:
        item = t.item(menu=hundred_entries())
        up(t, item)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: ids(w) == [item.registered])
            waits, inside = timed_opens(t, w, 20)
            ordered = sorted(waits)
            with capsys.disabled():
                print(
                    f"\nTray menu of 100 entries, click to shown: best {ordered[0]:.0f} ms, "
                    f"median {ordered[len(ordered) // 2]:.0f} ms; the shell's own work "
                    f"{min(inside):.0f} ms best"
                )
            assert ordered[len(ordered) // 2] < 100, ordered
