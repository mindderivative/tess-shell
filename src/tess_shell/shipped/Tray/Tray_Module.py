"""The Tray: the system tray, one icon per application that registers a StatusNotifierItem (Tray
Module). The shell is a second tray host next to Plasma's: ``ctx.tray`` owns the host name and
registers it with ``org.kde.StatusNotifierWatcher`` (the shell never starts a watcher). This module
follows the watcher's ``StatusNotifierItemRegistered`` and ``-Unregistered`` signals, each item's
properties and its ``NewIcon``, ``NewAttentionIcon``, ``NewOverlayIcon``, ``NewTitle``,
``NewToolTip`` and ``NewStatus`` signals (a signal is followed by a fresh read of the matching
properties), and the loss of an item's bus name. No timer: it wakes on those signals only.

Keys sent (to each use, for its own ``show_passive`` and ``icon_size``): ``has_items`` (the shell is
registered as a host and an item is shown) and ``items``, a list in the order of registration with
``id`` (the bus name and the object path), ``title``, ``status``, ``icon`` (a reference an ``Icon:``
shows: an SVG document or ``pixels:...``; the attention icon while the status is ``NeedsAttention``
and the item has one), ``tooltip_title``, ``tooltip_text``, ``attention``, ``label`` (the accessible
name: the title, and "needs attention") and ``description`` (the tooltip's text). ``available`` is
the layer's: the watcher is on the session bus. A layout shows itself with
``Visible: {{ available and has_items }}``.

The clicks are actions on the loop thread: ``activate``, ``secondary``, ``scroll`` and ``menu``. The
item's menu is the shell's own: ``AboutToShow`` and ``GetLayout`` of its ``com.canonical.dbusmenu``,
then the Popup ``Tray_Menu`` opens beside the tray with the tree in ``caller.data`` (the module
``Tray_Menu`` draws it, and sends the click back). While it is open a ``LayoutUpdated`` or
``ItemsPropertiesUpdated`` of that menu closes and opens it again with the new tree; an item that
leaves while its menu is open closes it. Icon files are read on a worker thread, never on the loop
or the ``dbus`` thread.
"""

from __future__ import annotations

import asyncio
import html
import re
import threading
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import TYPE_CHECKING, Any

from tess_shell import Module, action

if TYPE_CHECKING:
    from tess_shell.module import Event
    from tess_shell.modules.context import UseRecord
    from tess_shell.services.api import Bus, Proxy, Subscription

WATCHER = "org.kde.StatusNotifierWatcher"
WATCHER_PATH = "/StatusNotifierWatcher"
WATCHER_INTERFACE = "org.kde.StatusNotifierWatcher"
ITEM_INTERFACE = "org.kde.StatusNotifierItem"
MENU_INTERFACE = "com.canonical.dbusmenu"
DEFAULT_PATH = "/StatusNotifierItem"
NO_MENU = ("", "/", "/NO_DBUSMENU")
POPUP = "Tray_Menu"
LEVELS = 3  # a menu shows its first three levels (Events and Actions)
FALLBACK_ICON = "mdi:application-outline"
WARN_EVERY = 60.0  # seconds between two warnings about a failed call to one item
WHEEL = 120  # one wheel step in the units of Qt's angle delta (up is positive)

# the properties each ``New*`` signal makes the module read again
SIGNALS: dict[str, tuple[str, ...]] = {
    "NewIcon": ("IconName", "IconPixmap", "IconThemePath"),
    "NewAttentionIcon": ("AttentionIconName", "AttentionIconPixmap"),
    "NewOverlayIcon": ("OverlayIconName", "OverlayIconPixmap"),
    "NewTitle": ("Title",),
    "NewToolTip": ("ToolTip",),
    "NewStatus": ("Status",),
}
KEYS = ("items", "has_items")
TAGS = re.compile(r"<[^>]*>")


def parse_service(service: str) -> tuple[str, str]:
    """``<bus name><object path>`` as the watcher lists an item; a bare bus name (an item that
    registered with its name only) has the specification's default path."""
    index = service.find("/")
    if index < 0:
        return service, DEFAULT_PATH
    return service[:index], service[index:]


def plain(text: object) -> str:
    """A tooltip's text with its markup (it may be rich text) taken out."""
    return html.unescape(TAGS.sub("", text)).strip() if isinstance(text, str) else ""


def tooltip_of(value: object) -> tuple[str, str]:
    """``ToolTip`` is ``(icon name, icon pixmaps, title, text)``."""
    if isinstance(value, Sequence) and not isinstance(value, str) and len(value) >= 4:
        return plain(value[2]), plain(value[3])
    return "", ""


def label_of(title: str, attention: bool) -> str:
    return f"{title}, needs attention" if attention else title


def string(value: object) -> str:
    return value if isinstance(value, str) else ""


class Item:
    """One item on the bus: what it said last and the icons made for it."""

    def __init__(self, name: str, path: str) -> None:
        self.name = name
        self.path = path
        self.id = name + path
        self.props: dict[str, Any] = {}
        self.loaded = False  # its properties were read: not shown before
        self.proxy: Proxy | None = None
        self.subs: list[Subscription] = []
        self.icon_key: object = None  # what ``icons`` were made from
        self.icons: dict[tuple[int, bool], str] = {}  # (size, attention) -> reference
        self.failed = float("-inf")  # the monotonic time of the last warning about a call

    @property
    def status(self) -> str:
        return string(self.props.get("Status")) or "Active"

    @property
    def attention(self) -> bool:
        return self.status == "NeedsAttention"

    @property
    def menu_path(self) -> str | None:
        path = self.props.get("Menu")
        return path if isinstance(path, str) and path not in NO_MENU else None

    @property
    def title(self) -> str:
        return string(self.props.get("Title")) or string(self.props.get("Id")) or self.name


class Tray(Module):
    def __init__(self) -> None:
        self.lock = threading.RLock()  # the table of items: the dbus thread, a worker, the loop
        self.send_lock = threading.Lock()
        self.items: dict[str, Item] = {}
        self.hosted = False
        self.sent: dict[tuple[str, str], Any] = {}  # (use key, key) -> the last value sent
        self.pool: ThreadPoolExecutor | None = None
        self.subs: list[Subscription] = []
        self.menu_item: tuple[str, str] | None = None  # (item id, use key) of the open menu
        self.menu_anchor: tuple[float, float, float, float] | None = None  # the icon's rect
        self.menu_subs: list[Subscription] = []
        self.menu_opening = False  # the first tree is on its way
        self.menu_busy = False  # a refresh of the open menu is under way
        self.menu_dirty = False  # it changed while a read was under way
        self.monotonic = time.monotonic  # a test swaps it

    # -- start and stop -------------------------------------------------------------------------

    def start(self) -> None:
        self.publish()  # defaults, so a layout reading any key has a value before the watcher
        self.bus: Bus = self.ctx.dbus.session()
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tray-icons")
        watcher = self.bus.proxy(WATCHER, WATCHER_PATH, WATCHER_INTERFACE)
        self.subs = [
            watcher.on_property_changed(self.watcher_changed),
            watcher.on_signal("StatusNotifierItemRegistered", self.registered),
            watcher.on_signal("StatusNotifierItemUnregistered", self.unregistered),
            self.ctx.tray.on_host(self.host_changed),
        ]

    def stop(self) -> None:
        for sub in [*self.subs, *self.menu_subs]:
            sub.cancel()
        self.subs, self.menu_subs = [], []
        with self.lock:
            for item in self.items.values():
                for sub in item.subs:
                    sub.cancel()
            self.items.clear()
        if self.pool is not None:
            self.pool.shutdown(wait=False, cancel_futures=True)
            self.pool = None

    def use_added(self, use: UseRecord) -> None:
        self.resolve_all()  # a size nobody asked for before
        self.publish()

    def use_removed(self, use: UseRecord) -> None:
        with self.send_lock:
            for pair in [p for p in self.sent if p[0] == use.key]:
                del self.sent[pair]

    def on_service_lost(self, name: str) -> None:
        """An item's bus name lost its owner (it left without unregistering)."""
        for item in [i for i in list(self.items.values()) if i.name == name]:
            self.remove_item(item.id)

    # -- the watcher and the host (dbus thread) -------------------------------------------------

    def host_changed(self, hosted: bool) -> None:
        self.hosted = hosted
        self.publish()

    def watcher_changed(self, values: Mapping[str, Any]) -> None:
        """The watcher's properties (all of them when it was read, or came back): add the items it
        lists. Items that left are removed by their own signal or by the loss of their name."""
        listed = values.get("RegisteredStatusNotifierItems")
        if isinstance(listed, list):
            for service in listed:
                if isinstance(service, str):
                    self.add_item(*parse_service(service))

    def registered(self, service: str) -> None:
        self.add_item(*parse_service(service))

    def unregistered(self, service: str) -> None:
        name, path = parse_service(service)
        self.remove_item(name + path)

    def add_item(self, name: str, path: str) -> None:
        item = Item(name, path)
        with self.lock:
            if item.id in self.items:
                return
            self.items[item.id] = item
        proxy = item.proxy = self.bus.proxy(name, path, ITEM_INTERFACE, optional=True)
        item.subs = [
            proxy.on_property_changed(partial(self.props_changed, item.id)),
            *(proxy.on_signal(sig, partial(self.signalled, item.id, sig)) for sig in SIGNALS),
        ]

    def remove_item(self, item_id: str) -> None:
        with self.lock:
            item = self.items.pop(item_id, None)
            shared = item is not None and any(i.name == item.name for i in self.items.values())
        if item is None:
            return
        for sub in item.subs:
            sub.cancel()
        if not shared:
            self.bus.forget(item.name)
        if self.menu_item is not None and self.menu_item[0] == item_id:
            self.ctx.call_soon(self.close_menu)
        self.publish()

    def props_changed(self, item_id: str, values: Mapping[str, Any]) -> None:
        item = self.items.get(item_id)
        if item is None:
            return
        item.props.update(values)
        item.loaded = True
        self.resolve(item)
        self.publish()

    def signalled(self, item_id: str, signal: str, *body: object) -> None:
        """A ``New*`` signal: read the matching properties again (one read each, on the ``dbus``
        thread's loop)."""
        self.bus.run(self.reread(item_id, signal))

    async def reread(self, item_id: str, signal: str) -> None:
        item = self.items.get(item_id)
        if item is None or item.proxy is None:
            return
        for prop in SIGNALS[signal]:
            try:
                item.props[prop] = await item.proxy.get(prop, fresh=True)
            except Exception as exc:  # a property the item does not have, or it left
                self.ctx.log.debug(f"could not read {prop} of {item_id} ({exc})")
        self.resolve(item)
        self.publish()

    # -- icons (a worker thread) ----------------------------------------------------------------

    def sizes(self) -> set[int]:
        sizes = {int(u.params.get("icon_size") or 18) for u in list(self.ctx.uses.values())}
        return sizes or {18}

    def resolve_all(self) -> None:
        for item in list(self.items.values()):
            item.icon_key = None
            self.resolve(item)

    def resolve(self, item: Item) -> None:
        """Make the item's icons again when what they are made from changed."""
        p = item.props
        key = (
            tuple(string(p.get(k)) for k in ("IconName", "IconThemePath", "AttentionIconName")),
            pixmap_signature(p.get("IconPixmap")),
            pixmap_signature(p.get("AttentionIconPixmap")),
            frozenset(self.sizes()),
        )
        if key == item.icon_key or self.pool is None:
            return
        item.icon_key = key
        snapshot = dict(p)
        sizes = sorted(self.sizes())
        try:
            self.pool.submit(self.make_icons, item, key, snapshot, sizes)
        except RuntimeError:  # the pool was shut down: the module stopped
            pass

    def make_icons(self, item: Item, key: object, props: dict[str, Any], sizes: list[int]) -> None:
        try:
            made: dict[tuple[int, bool], str] = {}
            for size in sizes:
                normal = self.icon_for(item, props, size, "")
                made[(size, False)] = normal
                made[(size, True)] = self.icon_for(item, props, size, "Attention") or normal
        except Exception:
            self.ctx.log.opt(exception=True).error(f"icons of {item.id} failed")
            made = {(s, a): FALLBACK_ICON for s in sizes for a in (False, True)}
        with self.lock:
            if item.icon_key != key:  # a newer reading is on its way
                return
            item.icons = made
        self.publish()

    def icon_for(self, item: Item, props: Mapping[str, Any], size: int, which: str) -> str:
        """``IconName`` (or ``AttentionIconName``) from the item's theme path and the desktop's
        theme, else its pixmap, else the fallback. For the attention icon, an empty string when the
        item has none."""
        name = string(props.get(f"{which}IconName"))
        pixmaps = props.get(f"{which}IconPixmap")
        icons = self.ctx.icons
        theme_path = string(props.get("IconThemePath")) or None
        ref = icons.theme_icon(name, size, theme_path) if name else None
        if ref is None and isinstance(pixmaps, list) and pixmaps:
            ref = icons.pixmap_icon(pixmaps, size, item.id)
        if ref is None:
            return "" if which else FALLBACK_ICON
        return ref

    # -- what is shown --------------------------------------------------------------------------

    def entries(self, show_passive: bool, size: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        with self.lock:
            for item in self.items.values():
                icon = item.icons.get((size, item.attention))
                if not item.loaded or icon is None:
                    continue
                if item.status == "Passive" and not show_passive:
                    continue
                tip_title, tip_text = tooltip_of(item.props.get("ToolTip"))
                out.append(
                    {
                        "id": item.id,
                        "title": item.title,
                        "status": item.status,
                        "icon": icon,
                        "tooltip_title": tip_title or item.title,
                        "tooltip_text": tip_text,
                        "attention": item.attention,
                        "label": label_of(item.title, item.attention),
                        "description": tip_text,
                    }
                )
        return out

    def values(self, use: UseRecord) -> dict[str, Any]:
        params = use.params
        entries = self.entries(bool(params.get("show_passive")), int(params.get("icon_size") or 18))
        return {"items": entries, "has_items": self.hosted and bool(entries)}

    def publish(self) -> None:
        """Send each use what changed for it: a refresh that changes nothing sends nothing."""
        with self.send_lock:
            for use in list(self.ctx.uses.values()):
                for key, value in self.values(use).items():
                    if (use.key, key) not in self.sent or self.sent[(use.key, key)] != value:
                        self.sent[(use.key, key)] = value
                        self.ctx.send(key, value, use=use)

    # -- the clicks (loop thread) ---------------------------------------------------------------

    def item_of(self, item_id: str) -> Item | None:
        return self.items.get(item_id)

    @staticmethod
    def where(event: Event) -> list[int]:
        """The centre of the icon that was clicked, in the output's coordinates (the specification
        says so; ``Event.rect`` is the block's rectangle there). Without a rectangle (the shell
        could not place the block) the pointer's position in its window is the nearest it has."""
        if event.rect is not None:
            x, y, width, height = event.rect
            return [round(x + width / 2), round(y + height / 2)]
        return [round(event.x or 0), round(event.y or 0)]

    @action
    def activate(self, event: Event, id: str) -> None:
        item = self.item_of(id)
        if item is None:
            return
        if item.props.get("ItemIsMenu") is True and item.menu_path is not None:
            self.open_menu(item, event)
        else:
            self.call(item, "Activate", self.where(event), "ii")

    @action
    def secondary(self, event: Event, id: str) -> None:
        item = self.item_of(id)
        if item is not None:
            self.call(item, "SecondaryActivate", self.where(event), "ii")

    @action
    def scroll(self, event: Event, id: str, delta: float = 0) -> None:
        """One wheel step (``delta`` +1 for a step down): ``Scroll(delta, "vertical")`` in Qt's
        units, up positive."""
        item = self.item_of(id)
        if item is not None and delta:
            self.call(item, "Scroll", [-round(delta) * WHEEL, "vertical"], "is")

    @action
    def menu(self, event: Event, id: str) -> None:
        """The item's menu, drawn by the shell; ``ContextMenu`` when the item has none."""
        item = self.item_of(id)
        if item is None:
            return
        if item.menu_path is None:
            self.call(item, "ContextMenu", self.where(event), "ii")
        else:
            self.open_menu(item, event)

    def call(self, item: Item, method: str, args: list[Any], signature: str) -> None:
        self.bus.run(self.call_item(item, method, args, signature))

    async def call_item(self, item: Item, method: str, args: list[Any], signature: str) -> None:
        if item.proxy is None:
            return
        try:
            await item.proxy.call(method, args, signature)
        except Exception as exc:
            self.warn(item, f"{method} of {item.id} failed ({exc})")

    def warn(self, item: Item, message: str) -> None:
        """One warning a minute for each item; the rest are debug lines."""
        now = self.monotonic()
        if now - item.failed >= WARN_EVERY:
            item.failed = now
            self.ctx.log.warning(message)
        else:
            self.ctx.log.debug(message)

    # -- the menu -------------------------------------------------------------------------------

    def open_menu(self, item: Item, event: Event) -> None:
        # listen first: a change between the read and the Popup opening is read once more
        self.watch_menu(item, event.use)
        self.menu_opening, self.menu_dirty = True, False
        self.menu_anchor = event.rect  # the menu opens beside the icon that was clicked
        self.bus.run(self.fetch_menu(item, event.use, False))

    async def fetch_menu(self, item: Item, use_key: str, refresh: bool) -> None:
        """``AboutToShow(0)``, ``GetLayout(0, -1, [])`` and the entries (icons on the worker), then
        the Popup opens on the loop thread."""
        path = item.menu_path
        if path is None:
            return self.menu_failed(refresh)
        proxy = self.bus.proxy(item.name, path, MENU_INTERFACE, optional=True)
        try:
            await proxy.call("AboutToShow", [0], "i")
        except Exception as exc:  # the call is advice: the layout is read anyway
            self.ctx.log.debug(f"AboutToShow of {item.id} failed ({exc})")
        try:
            reply = await proxy.call("GetLayout", [0, -1, []], "iias")
        except Exception as exc:
            self.warn(item, f"GetLayout of {item.id} failed ({exc}); no menu opens")
            return self.menu_failed(refresh)
        layout = reply[1] if isinstance(reply, tuple) and len(reply) == 2 else None
        if not isinstance(layout, list) or len(layout) < 3:
            self.warn(item, f"GetLayout of {item.id} gave no tree; no menu opens")
            return self.menu_failed(refresh)
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(self.pool, self.build_menu, item, path, layout)
        self.ctx.call_soon(partial(self.show_menu, item.id, use_key, data, refresh))

    def menu_failed(self, refresh: bool) -> None:
        """No tree: nothing opens; an open menu that could not be refreshed stays as it is."""
        self.menu_busy = self.menu_opening = False
        if not refresh:
            self.ctx.call_soon(self.forget_menu)

    def show_menu(self, item_id: str, use_key: str, data: dict[str, Any], refresh: bool) -> None:
        """Loop thread: open the Popup (again, when the menu changed while it was open)."""
        self.menu_busy = False
        item = self.items.get(item_id)
        if item is None:
            self.menu_opening = False
            return
        if refresh and not (self.ctx.is_popup_open(POPUP) and self.menu_item == (item_id, use_key)):
            return  # it was closed while the new tree was on its way
        if refresh:
            self.ctx.close_popup(POPUP)
        self.ctx.popup(POPUP, data=data, use=use_key, anchor=self.menu_anchor)
        self.menu_opening = False
        if self.menu_dirty:  # it changed again while this tree was on its way
            self.menu_dirty = False
            self.refresh_menu(item_id)

    def watch_menu(self, item: Item, use_key: str) -> None:
        """Listen to the menu's ``LayoutUpdated`` and ``ItemsPropertiesUpdated`` until it is
        closed (a change found after that ends the listening)."""
        for sub in self.menu_subs:
            sub.cancel()
        self.menu_item = (item.id, use_key)
        path = item.menu_path
        if path is None:
            self.menu_subs = []
            return
        proxy = self.bus.proxy(item.name, path, MENU_INTERFACE, optional=True)
        self.menu_subs = [
            proxy.on_signal(sig, partial(self.menu_changed, item.id), interface=MENU_INTERFACE)
            for sig in ("LayoutUpdated", "ItemsPropertiesUpdated")
        ]

    def menu_changed(self, item_id: str, *body: object) -> None:
        """The open menu's tree changed (dbus thread): read it again, once at a time."""
        opened = self.menu_item
        if opened is None or opened[0] != item_id or item_id not in self.items:
            return
        if self.menu_opening or self.menu_busy:  # a read is under way: read once more after it
            self.menu_dirty = True
            return
        self.menu_busy = True
        self.ctx.call_soon(partial(self.refresh_menu, item_id))

    def refresh_menu(self, item_id: str) -> None:
        """Loop thread: only while the menu is open does the new tree matter."""
        item, opened = self.items.get(item_id), self.menu_item
        if item is None or opened is None:
            self.menu_busy = False
            return
        if not self.ctx.is_popup_open(POPUP):
            self.menu_busy = False
            if not self.menu_opening:
                self.forget_menu()  # it was closed: stop listening to its menu
            return
        self.menu_busy = True
        self.bus.run(self.fetch_menu(item, opened[1], True))

    def close_menu(self) -> None:
        self.ctx.close_popup(POPUP)
        self.forget_menu()

    def forget_menu(self) -> None:
        self.menu_item = None
        self.menu_anchor = None
        self.menu_opening = self.menu_busy = self.menu_dirty = False
        for sub in self.menu_subs:
            sub.cancel()
        self.menu_subs = []

    def build_menu(self, item: Item, path: str, layout: list[Any]) -> dict[str, Any]:
        """The tree as the data of the Popup (worker thread): ``menus`` maps a parent's id to the
        entries under it (``"0"`` is the root); ``service`` and ``path`` say where a click goes."""
        menus: dict[str, list[dict[str, Any]]] = {}

        def entries(node: list[Any], level: int) -> list[dict[str, Any]]:
            out: list[dict[str, Any]] = []
            for child in node[2]:
                entry = self.menu_entry(item, child, level, menus)
                if entry is not None:
                    out.append(entry)
            return out

        menus["0"] = entries(layout, 1)
        return {"service": item.name, "path": path, "title": item.title, "menus": menus}

    def menu_entry(
        self, item: Item, node: Any, level: int, menus: dict[str, list[dict[str, Any]]]
    ) -> dict[str, Any] | None:
        if not isinstance(node, list) or len(node) < 3 or not isinstance(node[1], dict):
            return None
        ident, props, kids = node[0], node[1], node[2]
        if props.get("visible", True) is False:
            return None
        if props.get("type") == "separator":
            return {**blank_entry(ident), "separator": True}
        text = mnemonic(string(props.get("label")))
        enabled = props.get("enabled", True) is not False
        kind, state = string(props.get("toggle-type")), props.get("toggle-state")
        checked = kind in ("checkmark", "radio") and state == 1
        submenu = ""
        if level < LEVELS and kids:
            below = [
                e
                for e in (self.menu_entry(item, k, level + 1, menus) for k in kids)
                if e is not None
            ]
            if below:
                menus[str(ident)] = below
                submenu = f"{POPUP}_{level + 1}"
        label = text
        if kind in ("checkmark", "radio"):
            label += ", checked" if checked else ", not checked"
        if not enabled:
            label += ", disabled"
        return {
            **blank_entry(ident),
            "text": text,
            "enabled": enabled,
            "icon": self.menu_icon(item, props, kind, checked),
            "shortcut": shortcut(props.get("shortcut")),
            "submenu": submenu,
            "label": label,
        }

    def menu_icon(self, item: Item, props: Mapping[str, Any], kind: str, checked: bool) -> str:
        """The glyph before a row: the mark of a toggle entry, else its icon (a theme name or png
        data), else none."""
        if kind == "checkmark":
            return "mdi:check" if checked else ""
        if kind == "radio":
            return "mdi:radiobox-marked" if checked else "mdi:radiobox-blank"
        name = string(props.get("icon-name"))
        icons = self.ctx.icons
        if name:
            ref = icons.theme_icon(name, 16)
            if ref is not None:
                return ref
        data = props.get("icon-data")
        if isinstance(data, bytes) and data:
            return icons.png_icon(data, item.id) or ""
        return ""


def pixmap_signature(value: object) -> tuple[tuple[int, int, int], ...]:
    """What decides whether a pixmap list changed: each entry's size and a hash of its bytes."""
    if not isinstance(value, list):
        return ()
    return tuple(
        (int(p[0]), int(p[1]), hash(bytes(p[2])))
        for p in value
        if isinstance(p, list) and len(p) >= 3 and isinstance(p[0], int) and isinstance(p[1], int)
    )


def blank_entry(ident: object) -> dict[str, Any]:
    return {
        "id": str(ident),
        "text": "",
        "enabled": True,
        "icon": "",
        "shortcut": "",
        "separator": False,
        "submenu": "",
        "label": "",
    }


def mnemonic(label: str) -> str:
    """An underscore marks the mnemonic and is removed; two are one underscore."""
    return re.sub(r"_(.?)", r"\1", label)


def shortcut(value: object) -> str:
    """``[["Control", "Q"]]`` as ``Ctrl+Q`` (the first alternative)."""
    if isinstance(value, list) and value and isinstance(value[0], list):
        return "+".join("Ctrl" if k == "Control" else str(k) for k in value[0])
    return ""
