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
the windows were opened: ``id``, ``title``, ``app``, ``icon``, ``active``, ``minimized``,
``attention``, ``label``) and ``has_windows``. ``available`` is the layer's: KWin is on the session
bus. The icons come from ``ctx.icons.app_icon`` on the worker and are made again when the desktop's
icon theme changes; until one is read a button shows the shipped ``application-outline``.
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


def label_of(window: WindowInfo) -> str:
    """The button's accessible name: the title and the application, the state in words."""
    name = window.title or window.app
    text = f"{name}, {window.app}" if window.title and window.app else name
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
            out.append(
                {
                    "id": window.id,
                    "title": window.title,
                    "app": window.app,
                    "icon": self.icon(window.app, size),
                    "active": window.active,
                    "minimized": window.minimized,
                    "attention": window.attention,
                    "label": label_of(window),
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
            values = {"ready": ready, "windows": rows, "has_windows": bool(rows)}
            for key, value in values.items():
                if self.sent.get((use.key, key)) != value or (use.key, key) not in self.sent:
                    self.sent[(use.key, key)] = value
                    self.ctx.send(key, value, use=use)

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
