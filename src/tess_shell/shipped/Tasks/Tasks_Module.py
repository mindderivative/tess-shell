"""The Tasks: the open windows as a row of buttons (Tasks Module). KWin has no call that lists
windows, so the list comes from the shell's own KWin script through ``ctx.windows``; this module
turns it into a row for each use and acts on a click with a one-shot script (``ctx.windows.
activate``, ``minimize`` and ``close_window``).

It subscribes to ``ctx.windows`` while it has a use (that is what turns the script's list on: with
no Tasks module the script sends no title, class or id) and to the current virtual desktop of
``/VirtualDesktopManager`` for ``desktop: CURRENT``. No timer, no thread of its own beyond one
worker that reads icon files (never the loop thread).

Keys sent, for each use and filtered for it (its ``monitor`` and ``desktop``): ``ready`` (the first
list has arrived and the script is answering), ``windows`` (a record per shown window, in the order
the windows were opened: ``id``, ``title``, ``app``, ``name`` (the application's ``Name`` from its
desktop entry, the desktop file name until it is read), ``icon``, ``active``, ``minimized``,
``attention``, ``label``) and ``has_windows``. A use with ``announce`` has the module say, politely,
with ``ctx.announce``, a window opened, closed or wanting attention. ``available`` is the
layer's: KWin is on the session bus. The icons and names come from ``ctx.icons`` on the worker and
are made again when the desktop's icon theme changes; until an icon is read a button shows the
shipped ``application-outline``.
"""

from __future__ import annotations

from collections.abc import Mapping
from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from tess_shell import Module, action

if TYPE_CHECKING:
    from tess_shell.module import Event
    from tess_shell.modules.context import UseRecord
    from tess_shell.services.api import Subscription, WindowInfo

KWIN = "org.kde.KWin"
PATH = "/VirtualDesktopManager"
INTERFACE = "org.kde.KWin.VirtualDesktopManager"
FALLBACK_ICON = "mdi:application-outline"
MONITORS = ("THIS", "ALL")
DESKTOPS = ("CURRENT", "ALL")


def label_of(window: WindowInfo, name: str = "") -> str:
    """The button's accessible name: the title and the application's name (``name``, from its
    desktop entry; the desktop file name when it is not known), the state in words."""
    app = name or window.app
    first = window.title or app
    text = f"{first}, {app}" if window.title and app else first
    for flag, words in (
        (window.active, "active"),
        (window.minimized, "minimised"),
        (window.attention, "wants attention"),
    ):
        if flag:
            text += f", {words}"
    return text


class Tasks(Module):
    def __init__(self) -> None:
        self.subs: list[Subscription] = []
        self.windows_sub: Subscription | None = None
        self.pool: ThreadPoolExecutor | None = None
        self.current = ""  # the current virtual desktop (an id), "" until it was read
        self.icons: dict[tuple[str, int], str] = {}  # (application, size) -> a reference
        self.pending: set[tuple[str, int]] = set()  # icons a worker is making
        self.generation = 0  # counts icon-theme changes: a result of an older one is dropped
        self.sent: dict[tuple[str, str], Any] = {}  # (use key, key) -> the last value sent
        self.shown: dict[str, list[str]] = {}  # use key -> the ids of its row, in order
        self.names: dict[str, str] = {}  # application -> its desktop entry's Name
        self.naming: set[str] = set()  # names the worker is reading
        self.all_ids: set[str] = set()  # every window of the last list, whatever its row

    # -- start and stop -------------------------------------------------------------------------

    def start(self) -> None:
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="tasks-icons")
        desktops = self.ctx.dbus.session().proxy(KWIN, PATH, INTERFACE)
        self.subs = [
            desktops.on_property_changed(self.desktop_changed),
            self.ctx.icons.on_theme_changed(self.theme_changed),
        ]
        if self.ctx.uses:
            self.subscribe()
        self.refresh()  # every use has a value before the first list

    def stop(self) -> None:
        for sub in self.subs:
            sub.cancel()
        self.subs = []
        self.unsubscribe()
        if self.pool is not None:
            self.pool.shutdown(wait=False, cancel_futures=True)
            self.pool = None

    def validate_use(self, use: UseRecord) -> None:
        if use.params.get("monitor") not in MONITORS:
            raise ValueError(f"monitor must be one of {', '.join(MONITORS)}")
        if use.params.get("desktop") not in DESKTOPS:
            raise ValueError(f"desktop must be one of {', '.join(DESKTOPS)}")

    def use_added(self, use: UseRecord) -> None:
        self.subscribe()
        self.refresh()

    def use_removed(self, use: UseRecord) -> None:
        for pair in [p for p in self.sent if p[0] == use.key]:
            del self.sent[pair]
        self.shown.pop(use.key, None)
        if not self.ctx.uses:
            self.unsubscribe()  # the last use is gone: the script's list is turned off

    def subscribe(self) -> None:
        """Ask for the window list (the first subscriber turns the script's list on)."""
        if self.windows_sub is None:
            self.windows_sub = self.ctx.windows.on_changed(self.refresh)

    def unsubscribe(self) -> None:
        if self.windows_sub is not None:
            self.windows_sub.cancel()
            self.windows_sub = None

    # -- what changed ---------------------------------------------------------------------------

    def desktop_changed(self, values: Mapping[str, Any]) -> None:
        """The virtual desktop manager's properties (dbus thread)."""
        current = values.get("current")
        if isinstance(current, str) and current != self.current:
            self.current = current
            self.ctx.call_soon(self.refresh)

    def theme_changed(self) -> None:
        """The desktop's icon theme changed: every icon made before it came from the old one."""
        self.ctx.call_soon(self.theme_changed_on_loop)

    def theme_changed_on_loop(self) -> None:
        self.generation += 1
        self.icons.clear()
        self.names.clear()
        self.refresh()

    # -- icons (a worker thread) ----------------------------------------------------------------

    def icon(self, app: str, size: int) -> str:
        """The icon of an application, or the fallback while a worker is reading it."""
        key = (app, size)
        found = self.icons.get(key)
        if found is not None:
            return found
        if key not in self.pending and self.pool is not None:
            self.pending.add(key)
            try:
                self.pool.submit(self.resolve, key, self.generation)
            except RuntimeError:  # the pool was shut down: the module stopped
                self.pending.discard(key)
        return FALLBACK_ICON

    def resolve(self, key: tuple[str, int], generation: int) -> None:
        try:
            ref = self.ctx.icons.app_icon(key[0], key[1])
        except Exception:
            self.ctx.log.opt(exception=True).error(f"the icon of {key[0]} failed")
            ref = FALLBACK_ICON
        self.ctx.call_soon(lambda: self.resolved(key, generation, ref))

    def resolved(self, key: tuple[str, int], generation: int, ref: str) -> None:
        self.pending.discard(key)
        if generation == self.generation:
            self.icons[key] = ref
        self.refresh()

    def name(self, app: str) -> str:
        """What a person calls an application: the ``Name`` of its desktop entry, read on the
        worker with the icons; the desktop file name until it is read (or when it has no entry)."""
        found = self.names.get(app)
        if found is not None:
            return found
        if app and app not in self.naming and self.pool is not None:
            self.naming.add(app)
            try:
                self.pool.submit(self.resolve_name, app, self.generation)
            except RuntimeError:  # the pool was shut down: the module stopped
                self.naming.discard(app)
        return app

    def resolve_name(self, app: str, generation: int) -> None:
        try:
            name = self.ctx.icons.app_name(app)
        except Exception:
            self.ctx.log.opt(exception=True).error(f"the name of {app} failed")
            name = app
        self.ctx.call_soon(lambda: self.named(app, generation, name))

    def named(self, app: str, generation: int, name: str) -> None:
        self.naming.discard(app)
        if generation == self.generation:
            self.names[app] = name
        if name != app:
            self.refresh()

    # -- what is shown (loop thread) ------------------------------------------------------------

    def rows(self, use: UseRecord, windows: tuple[WindowInfo, ...]) -> list[dict[str, Any]]:
        params = use.params
        on_this_monitor = params.get("monitor") == "THIS"
        on_this_desktop = params.get("desktop") == "CURRENT"
        size = int(params.get("icon_size") or 18)
        out: list[dict[str, Any]] = []
        for window in windows:
            if on_this_monitor and window.output and window.output != use.monitor:
                continue
            if (
                on_this_desktop
                and self.current
                and window.desktops  # empty: on all desktops
                and self.current not in window.desktops
            ):
                continue
            name = self.name(window.app)
            out.append(
                {
                    "id": window.id,
                    "title": window.title,
                    "app": window.app,
                    "name": name,
                    "icon": self.icon(window.app, size),
                    "active": window.active,
                    "minimized": window.minimized,
                    "attention": window.attention,
                    "label": label_of(window, name),
                }
            )
        return out

    def refresh(self) -> None:
        """Send each use what changed for it; a list that changes nothing sends nothing."""
        service = self.ctx.windows if self.windows_sub is not None else None
        windows = service.list() if service is not None else ()
        ready = service is not None and service.ready and service.available
        for use in list(self.ctx.uses.values()):
            rows = self.rows(use, windows)
            self.shown[use.key] = [row["id"] for row in rows]
            values: dict[str, Any] = {"ready": ready, "windows": rows, "has_windows": bool(rows)}
            asked = bool(use.params.get("announce"))
            said = self.announcement(use, ready, rows, windows) if asked else ""
            for key, value in values.items():
                if self.sent.get((use.key, key)) != value or (use.key, key) not in self.sent:
                    self.sent[(use.key, key)] = value
                    self.ctx.send(key, value, use=use)
            if said:
                self.ctx.announce(said, use=use)
        self.all_ids = {window.id for window in windows}

    def announcement(
        self,
        use: UseRecord,
        ready: bool,
        rows: list[dict[str, Any]],
        windows: tuple[WindowInfo, ...],
    ) -> str:
        """What a use says aloud (Accessibility, rule 6, ``POLITE``): a window of its row that
        opened, closed or came to want attention, in one message (the first three events, then a
        count). Nothing for the first list, for a change of the active window (the desktop says
        that itself) or for a window that only left the row (another desktop or monitor):
        ``all_ids`` is the list of the whole shell before this one. It is said through the surface's
        window, not through a block, so the last window's closing is heard although the row is
        then hidden."""
        if not self.sent.get((use.key, "ready")) or not ready:
            return ""
        before = {row["id"]: row for row in self.sent.get((use.key, "windows"), [])}
        now = {row["id"]: row for row in rows}
        here = {window.id for window in windows}
        events: list[str] = []
        for window_id, row in now.items():
            if window_id not in before and window_id not in self.all_ids:
                events.append(f"{row['title'] or row['name']} opened")
            elif window_id in before and row["attention"] and not before[window_id]["attention"]:
                events.append(f"{row['title'] or row['name']} wants attention")
        for window_id, row in before.items():
            if window_id not in now and window_id not in here:
                events.append(f"{row['title'] or row['name']} closed")
        if len(events) > 3:
            events = [*events[:3], f"and {len(events) - 3} more"]
        return ", ".join(events)

    # -- the clicks (loop thread) ---------------------------------------------------------------

    def window(self, window_id: object) -> WindowInfo | None:
        for window in self.ctx.windows.list():
            if window.id == window_id:
                return window
        return None

    @action
    def activate(self, event: Event, id: str) -> None:
        """A click on a button: the active window is minimised, any other is activated
        (un-minimising it). The row changes when KWin has acted and the script reports."""
        window = self.window(id)
        if window is None:
            return
        if window.active and not window.minimized:
            self.ctx.windows.minimize(id)
        else:
            self.ctx.windows.activate(id)

    @action
    def key(self, event: Event, id: str) -> None:
        """A key on a focused task: Delete closes its window (the middle click's keyboard twin)."""
        if event.key == "delete" and not (event.shift or event.ctrl or event.alt or event.meta):
            self.close(event, id)

    @action
    def close(self, event: Event, id: str) -> None:
        """A middle click: ask the window to close."""
        if self.window(id) is not None:
            self.ctx.windows.close_window(id)

    @action
    def cycle(self, event: Event, delta: float = 0) -> None:
        """The wheel over a row: activate the next (``delta`` > 0, a step down) or the previous
        window of that row, wrapping round."""
        row = self.shown.get(event.use, [])
        if not row or not delta:
            return
        active = next(
            (i for i, window_id in enumerate(row) if (w := self.window(window_id)) and w.active),
            None,
        )
        step = 1 if delta > 0 else -1
        target = (0 if step > 0 else len(row) - 1) if active is None else (active + step) % len(row)
        self.ctx.windows.activate(row[target])
