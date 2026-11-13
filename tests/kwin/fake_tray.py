"""A fake StatusNotifierWatcher and five fake StatusNotifierItems on a PRIVATE session bus, for the
maintainer's KWin check of the Tray module (``tests/kwin/prepare_m5f_gallery.py``; not collected by
pytest).

``python fake_tray.py --root DIR`` starts a private ``dbus-daemon`` and, on it, the watcher
``org.kde.StatusNotifierWatcher`` and the items ``mail`` (a theme icon, a menu with every kind of
entry), ``chat`` (a pixmap only, no menu: ``ContextMenu`` is its secondary click), ``sync`` (its own
icon folder through ``IconThemePath``, an attention icon, ``ItemIsMenu``), ``update`` (a menu with a
submenu of 95 entries, as the maintainer's Cachy-Update) and ``ghost`` (``Passive``). It writes the
bus address to ``DIR/bus-address`` and its pid to ``DIR/fake.pid``, and every call the shell makes on
a fake (``Activate``, ``SecondaryActivate``, ``Scroll``, ``ContextMenu``, the menu's ``AboutToShow``,
``GetLayout`` and ``Event``, and the host the shell registers) to ``DIR/fake.log``. ``tray-set.sh``
changes the fakes with ``busctl`` through one extra object, ``org.tess.FakeTray``, on the same
private bus.

It never connects to the real session bus or the real system bus: the daemon is its own, on a socket
in a temporary directory. ``SIGTERM`` / ``SIGINT`` end the daemon and this process.
"""

from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.fake_dbus import FakeBus  # noqa: E402
from tests.fake_sni import Item, Menu, Node, Watcher, add_item, add_watcher, sample_tree  # noqa: E402

CONTROL = "org.tess.FakeTray"
CONTROL_PATH = "/org/tess/Fake"
CONTROL_INTERFACE = "org.tess.FakeTray.Control"
ROLES = ("mail", "chat", "sync", "update", "ghost")
SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" width="24" height="24">'
    '<circle cx="12" cy="12" r="10" fill="{fill}"/><text x="12" y="17" font-size="14" '
    'text-anchor="middle" fill="white">{mark}</text></svg>'
)
ICONS = {
    "tess-sync": ("#3a7bd5", "S"),
    "tess-sync-attention": ("#e0701a", "!"),
    "tess-swap-a": ("#2e9e5b", "A"),
    "tess-swap-b": ("#9b3fc0", "B"),
}


def write_icons(folder: Path) -> None:
    """The kit's own icon folder (an item's ``IconThemePath``): four SVGs."""
    folder.mkdir(parents=True, exist_ok=True)
    for name, (fill, mark) in ICONS.items():
        (folder / f"{name}.svg").write_text(SVG.format(fill=fill, mark=mark))


def gradient() -> bytes:
    """A 22 by 22 ARGB32 pixmap (network byte order): opaque red to blue, with a clear corner."""
    out = bytearray()
    for y in range(22):
        for x in range(22):
            alpha = 0 if x + y < 4 else 255
            out += bytes((alpha, 255 - 11 * x, 40, 20 + 10 * y))
    return bytes(out)


def big_tree() -> Node:
    """What the maintainer's Cachy-Update gives: an entry, and a submenu of 95 entries."""
    return Node(
        0,
        {"children-display": "submenu"},
        [
            Node(1, {"label": "95 updates available"}),
            Node(
                2,
                {"label": "All (95)", "children-display": "submenu"},
                [Node(10 + i, {"label": f"package-{i + 1:02d}"}) for i in range(95)],
            ),
        ],
    )


def small_tree() -> Node:
    return Node(
        0,
        {"children-display": "submenu"},
        [
            Node(1, {"label": "Sync now"}),
            Node(2, {"label": "Pause", "toggle-type": "checkmark", "toggle-state": 0}),
        ],
    )


class Live:
    """One fake item, its log and what a control call does to it."""

    def __init__(self, bus: FakeBus, root: Path, role: str, number: int, log: Any) -> None:
        self.role = role
        self.log = log
        kw: dict[str, Any] = {"title": role.capitalize(), "icon": "dialog-information"}
        menu: Node | None = None
        if role == "mail":
            kw.update(icon="mail-unread", tooltip=("", [], "Mail", "3 unread messages"))
            menu = sample_tree()
        elif role == "chat":
            kw.update(icon="", pixmap=[[22, 22, gradient()]], tooltip=("", [], "Chat", "pixmap"))
        elif role == "sync":
            kw.update(
                icon="tess-sync",
                theme_path=str(root / "icons"),
                attention_icon="tess-sync-attention",
                item_is_menu=True,
                tooltip=("", [], "Sync", "Up to date"),
            )
            menu = small_tree()
        elif role == "update":
            kw.update(icon="system-software-update", tooltip=("", [], "Update", "95 updates"))
            menu = big_tree()
        else:
            kw.update(status="Passive", tooltip=("", [], "Ghost", "passive"))
        self.item: Item = add_item(bus, f"{number}-1", menu=menu, **kw)
        self.log_calls()

    def log_calls(self) -> None:
        for name, signature in (
            ("Activate", ["i", "i"]),
            ("SecondaryActivate", ["i", "i"]),
            ("ContextMenu", ["i", "i"]),
            ("Scroll", ["i", "s"]),
        ):

            def record(*args: Any, name: str = name) -> None:
                self.log(f"{self.role} {name} {' '.join(str(a) for a in args)}")

            self.item.object._methods[name] = (signature, "", record)
        menu = self.item.menu
        if menu is not None:

            def about(ident: int) -> bool:
                self.log(f"{self.role} menu AboutToShow {ident}")
                return False

            def layout(parent: int, depth: int, names: list[str]) -> list[Any]:
                from tests.fake_sni import wire

                self.log(f"{self.role} menu GetLayout {parent} {depth}")
                return [menu.revision, wire(menu.root)]

            def event(ident: int, kind: str, data: Any, stamp: int) -> None:
                self.log(f"{self.role} menu Event {ident} {kind}")

            methods = menu.object._methods
            methods["AboutToShow"] = (["i"], "b", about)
            methods["GetLayout"] = (["i", "i", "as"], "u(ia{sv}av)", layout)
            methods["Event"] = (["i", "s", "v", "u"], "", event)

    @property
    def menu(self) -> Menu | None:
        return self.item.menu


async def emit(obj: Any, signal_name: str, *args: Any) -> None:
    """A signal from inside the fake's own loop."""
    if obj._iface is not None:
        getattr(obj._iface, signal_name)(*args)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    write_icons(args.root / "icons")
    log_path = args.root / "fake.log"
    log_path.write_text("")

    def log(line: str) -> None:
        with log_path.open("a") as out:
            out.write(f"{time.strftime('%H:%M:%S')} {line}\n")

    bus = FakeBus()  # a private daemon, and the thread the fakes run on
    live = {role: Live(bus, args.root, role, n + 1, log) for n, role in enumerate(ROLES)}
    watcher: Watcher = add_watcher(bus, [live[r].item for r in ROLES])

    def host(name: str) -> None:
        log(f"watcher RegisterStatusNotifierHost {name}")
        watcher.hosts.append(name)

    watcher.object._methods["RegisterStatusNotifierHost"] = (["s"], "", host)
    control = bus.service(CONTROL)

    async def w_list(item: Item, present: bool) -> None:
        listed = [
            s
            for s in watcher.object.values["RegisteredStatusNotifierItems"]
            if s != item.registered
        ]
        if present:
            listed.append(item.registered)
        watcher.object.values["RegisteredStatusNotifierItems"] = listed
        if watcher.object._iface is not None:
            watcher.object._iface.emit_properties_changed({"RegisteredStatusNotifierItems": listed})
            signal_name = (
                "StatusNotifierItemRegistered" if present else "StatusNotifierItemUnregistered"
            )
            await emit(watcher.object, signal_name, item.registered)

    async def c_item(role: str, word: str) -> None:
        item = live[role].item
        if word == "away":
            await item.service._drop()  # leaves the bus without unregistering
        elif word == "back":
            await item.service._up()
            await w_list(item, True)
        elif word == "unregister":
            await w_list(item, False)
        elif word == "register":
            await w_list(item, True)

    async def c_state(role: str, status: str) -> None:
        item = live[role].item
        item.object.values["Status"] = status
        await emit(item.object, "NewStatus", status)

    async def c_text(role: str, kind: str, text: str) -> None:
        item = live[role].item
        if kind == "title":
            item.object.values["Title"] = text
            await emit(item.object, "NewTitle")
        else:
            item.object.values["ToolTip"] = ["", [], text, f"{text}: changed"]
            await emit(item.object, "NewToolTip")

    async def c_swap(role: str) -> None:
        item = live[role].item
        pair = ("tess-swap-a", "tess-swap-b")
        item.object.values["IconThemePath"] = str(args.root / "icons")
        now = item.object.values["IconName"]
        item.object.values["IconName"] = pair[1] if now == pair[0] else pair[0]
        await emit(item.object, "NewIcon")

    async def c_relabel(role: str) -> None:
        menu = live[role].menu
        if menu is None:
            return
        first = menu.root.children[0]
        first.props["label"] = (
            "Changed label" if first.props["label"] != "Changed label" else "Back"
        )
        menu.revision += 1
        await emit(menu.object, "LayoutUpdated", menu.revision, 0)

    async def c_watcher(word: str) -> None:
        if word == "away":
            await watcher.service._down()
        elif word == "back":
            await watcher.service._up()
        else:  # restart
            await watcher.service._drop()
            await watcher.service._up()

    control.add(
        CONTROL_PATH,
        CONTROL_INTERFACE,
        methods={
            "Item": (["s", "s"], "", c_item),
            "State": (["s", "s"], "", c_state),
            "Text": (["s", "s", "s"], "", c_text),
            "Swap": (["s"], "", c_swap),
            "Relabel": (["s"], "", c_relabel),
            "Watcher": (["s"], "", c_watcher),
        },
    )
    control.up()
    watcher.up()
    for role in ROLES:
        live[role].item.up()
    (args.root / "fake.pid").write_text(str(os.getpid()))
    (args.root / "bus-address").write_text(bus.address)
    print(f"fake tray on {bus.address}", flush=True)
    stop = {"now": False}

    def on_term(*_: object) -> None:
        stop["now"] = True

    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)
    try:
        while not stop["now"]:
            time.sleep(0.2)
    finally:
        bus.close()
        (args.root / "bus-address").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
