"""A fake StatusNotifierWatcher, fake StatusNotifierItems and a fake ``com.canonical.dbusmenu`` on a
private session bus (Tray Module; D-019, D-025: nothing here touches the real bus, the real watcher
or a real item).

``add_watcher`` is ``org.kde.StatusNotifierWatcher`` with the members the specification gives and
the ones read on the maintainer's machine; ``register`` and ``unregister`` list an item and emit
the signal as the real watcher does. ``add_item`` is one item with the properties, the four methods
(which only record their calls) and the six ``New*`` signals; ``add_menu`` gives it a dbusmenu with
a tree made of :class:`Node`. Calls are in ``item.calls`` and ``menu.calls``; a test changes a
property with ``item.object.set`` and then emits the signal itself, as an application does.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from dbus_fast import Variant

from tests.fake_dbus import FakeBus, FakeObject, FakeService

WATCHER = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"
ITEM = "org.kde.StatusNotifierItem"
ITEM_PATH = "/StatusNotifierItem"
MENU = "com.canonical.dbusmenu"
MENU_PATH = "/MenuBar"
SIGNALS = {
    "NewIcon": "",
    "NewAttentionIcon": "",
    "NewOverlayIcon": "",
    "NewTitle": "",
    "NewToolTip": "",
    "NewStatus": "s",
}
PIXMAP = "a(iiay)"
NO_PIXMAPS: list[Any] = []


@dataclass
class Watcher:
    service: FakeService
    object: FakeObject
    hosts: list[str] = field(default_factory=list)  # RegisterStatusNotifierHost arguments

    def up(self) -> None:
        self.service.up()

    def down(self) -> None:
        self.service.down()

    def restart(self) -> None:
        """The watcher process restarts: the name goes and comes back (with the same items it was
        told of; a real one starts empty and its items register again: use ``clear``)."""
        self.service.restart()

    def register(self, item: Item) -> None:
        listed = [*self.object.values["RegisteredStatusNotifierItems"], item.registered]
        self.object.set("RegisteredStatusNotifierItems", listed)
        self.object.emit("StatusNotifierItemRegistered", item.registered)

    def unregister(self, item: Item) -> None:
        was = self.object.values["RegisteredStatusNotifierItems"]
        listed = [s for s in was if s != item.registered]
        self.object.set("RegisteredStatusNotifierItems", listed)
        self.object.emit("StatusNotifierItemUnregistered", item.registered)

    def clear(self) -> None:
        self.object.silent_set("RegisteredStatusNotifierItems", [])


def add_watcher(bus: FakeBus, items: Sequence[Item] = ()) -> Watcher:
    """A fake watcher listing ``items`` (not up yet)."""
    service = bus.service(WATCHER)
    hosts: list[str] = []

    def register_host(name: str) -> None:
        hosts.append(name)

    obj = service.add(
        WATCHER_PATH,
        WATCHER,
        properties={
            "RegisteredStatusNotifierItems": ("as", [i.registered for i in items]),
            "IsStatusNotifierHostRegistered": ("b", True),
            "ProtocolVersion": ("i", 0),
        },
        methods={
            "RegisterStatusNotifierHost": (["s"], "", register_host),
            "RegisterStatusNotifierItem": (["s"], "", lambda s: None),
        },
        signals={
            "StatusNotifierItemRegistered": "s",
            "StatusNotifierItemUnregistered": "s",
            "StatusNotifierHostRegistered": "",
        },
    )
    return Watcher(service, obj, hosts)


@dataclass
class Node:
    """One entry of a menu tree: ``props`` are the dbusmenu properties as plain values."""

    id: int
    props: dict[str, Any] = field(default_factory=dict)
    children: list[Node] = field(default_factory=list)


PROP_TYPES = {
    "label": "s",
    "enabled": "b",
    "visible": "b",
    "type": "s",
    "toggle-type": "s",
    "toggle-state": "i",
    "icon-name": "s",
    "icon-data": "ay",
    "shortcut": "aas",
    "children-display": "s",
}


def wire(node: Node) -> list[Any]:
    """``(ia{sv}av)``: the id, the properties as variants and the children as variants."""
    props = {k: Variant(PROP_TYPES[k], v) for k, v in node.props.items()}
    return [node.id, props, [Variant("(ia{sv}av)", wire(c)) for c in node.children]]


@dataclass
class Menu:
    object: FakeObject
    root: Node
    revision: int = 1

    @property
    def calls(self) -> list[tuple[str, tuple[Any, ...]]]:
        return self.object.calls

    def clicked(self) -> list[int]:
        """The ids of the ``Event`` calls with ``clicked``."""
        return [int(a[0]) for m, a in self.calls if m == "Event" and a[1] == "clicked"]

    def updated(self) -> None:
        """The application changed the tree (``root`` first): ``LayoutUpdated``."""
        self.revision += 1
        self.object.emit("LayoutUpdated", self.revision, 0)


def sample_tree() -> Node:
    """A menu with a label, a separator, a disabled entry, a checked checkmark, a radio pair, an
    entry with a shortcut and an icon name, and a submenu of two (one of them with a submenu)."""
    return Node(
        0,
        {"children-display": "submenu"},
        [
            Node(1, {"label": "Open _Window"}),
            Node(2, {"type": "separator"}),
            Node(3, {"label": "Disabled", "enabled": False}),
            Node(4, {"label": "Checked", "toggle-type": "checkmark", "toggle-state": 1}),
            Node(5, {"label": "Radio on", "toggle-type": "radio", "toggle-state": 1}),
            Node(6, {"label": "Radio off", "toggle-type": "radio", "toggle-state": 0}),
            Node(7, {"label": "Quit", "shortcut": [["Control", "Q"]], "icon-name": "app-quit"}),
            Node(8, {"label": "Hidden", "visible": False}),
            Node(
                9,
                {"label": "More", "children-display": "submenu"},
                [
                    Node(10, {"label": "First"}),
                    Node(
                        11,
                        {"label": "Deeper", "children-display": "submenu"},
                        [
                            Node(
                                12,
                                {"label": "Level three", "children-display": "submenu"},
                                [Node(13, {"label": "Level four"})],
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


@dataclass
class Item:
    service: FakeService
    object: FakeObject
    menu: Menu | None = None

    @property
    def name(self) -> str:
        return self.service.name

    @property
    def registered(self) -> str:
        """What the watcher lists: the bus name and the path."""
        return self.service.name + ITEM_PATH

    @property
    def calls(self) -> list[tuple[str, tuple[Any, ...]]]:
        return self.object.calls

    def up(self) -> None:
        self.service.up()

    def down(self) -> None:
        self.service.down()

    def drop(self) -> None:
        """The application dies: its connection closes and the name goes."""
        self.service.drop()

    def changed(self, signal: str, **props: Any) -> None:
        """What an application does: set properties, then emit the ``New*`` signal (``NewStatus``
        carries the status). The properties do not emit ``PropertiesChanged``."""
        for key, value in props.items():
            self.object.silent_set(key, value)
        if signal == "NewStatus":
            self.object.emit(signal, props.get("Status", ""))
        else:
            self.object.emit(signal)


def add_item(
    bus: FakeBus,
    suffix: str = "1-1",
    *,
    title: str = "Fake App",
    status: str = "Active",
    icon: str = "fake-icon",
    pixmap: list[Any] | None = None,
    theme_path: str = "",
    attention_icon: str = "",
    attention_pixmap: list[Any] | None = None,
    tooltip: tuple[str, list[Any], str, str] = ("", NO_PIXMAPS, "Fake App", "Fake text"),
    menu: Node | None = None,
    item_is_menu: bool = False,
) -> Item:
    """A fake item ``org.kde.StatusNotifierItem-<suffix>`` (not up yet); ``menu`` is its tree, if
    it has a menu (``Menu`` is ``/MenuBar``, else ``/NO_DBUSMENU``)."""
    service = bus.service(f"{ITEM}-{suffix}")
    obj = service.add(
        ITEM_PATH,
        ITEM,
        properties={
            "Category": ("s", "ApplicationStatus"),
            "Id": ("s", f"fake-{suffix}"),
            "Title": ("s", title),
            "Status": ("s", status),
            "WindowId": ("u", 0),
            "IconThemePath": ("s", theme_path),
            "IconName": ("s", icon),
            "IconPixmap": (PIXMAP, pixmap or NO_PIXMAPS),
            "OverlayIconName": ("s", ""),
            "OverlayIconPixmap": (PIXMAP, NO_PIXMAPS),
            "AttentionIconName": ("s", attention_icon),
            "AttentionIconPixmap": (PIXMAP, attention_pixmap or NO_PIXMAPS),
            "AttentionMovieName": ("s", ""),
            "ToolTip": ("(sa(iiay)ss)", list(tooltip)),
            "ItemIsMenu": ("b", item_is_menu),
            "Menu": ("o", MENU_PATH if menu is not None else "/NO_DBUSMENU"),
        },
        methods={
            "Activate": (["i", "i"], "", lambda x, y: None),
            "SecondaryActivate": (["i", "i"], "", lambda x, y: None),
            "ContextMenu": (["i", "i"], "", lambda x, y: None),
            "Scroll": (["i", "s"], "", lambda delta, orientation: None),
        },
        signals=SIGNALS,
    )
    item = Item(service, obj)
    if menu is not None:
        item.menu = add_menu(service, menu)
    return item


def add_menu(service: FakeService, root: Node) -> Menu:
    menu: Menu

    def get_layout(parent: int, depth: int, names: list[str]) -> list[Any]:
        return [menu.revision, wire(menu.root)]

    obj = service.add(
        MENU_PATH,
        MENU,
        properties={
            "Version": ("u", 3),
            "TextDirection": ("s", "ltr"),
            "Status": ("s", "normal"),
            "IconThemePath": ("as", []),
        },
        methods={
            "GetLayout": (["i", "i", "as"], "u(ia{sv}av)", get_layout),
            "AboutToShow": (["i"], "b", lambda ident: False),
            "Event": (["i", "s", "v", "u"], "", lambda ident, kind, data, stamp: None),
        },
        signals={"LayoutUpdated": "ui", "ItemsPropertiesUpdated": "a(ia{sv})a(ias)"},
    )
    menu = Menu(obj, root)
    return menu
