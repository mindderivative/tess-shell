"""The Applications module: the launcher (Applications Module). A text field over a list of the
installed applications; the list comes from ``ctx.apps`` (the shell's index of desktop entries,
built on a worker thread), the keys of the list reach this module from the field (``On_Key_Down``),
and a start goes through ``ctx.apps.launch``, which asks the Panel's window for an activation token
first.

Keys sent, for each use: ``ready``, ``query``, ``results`` (a record per row: ``id``, ``name``,
``comment``, ``icon``), ``selected`` (the selected row's index, 0 when the list changes),
``selected_id``, ``has_results``, ``list_height`` and ``message`` (the layout's comment says what
each is). Each use has its own query and selection: two Panels on two outputs do not share them.
The icons come from ``ctx.icons.app_icon`` on one worker (never the loop thread) and are made again
when the desktop's icon theme changes; until one is read a row shows the shipped
``application-outline``. No timer.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING, Any

from tess_shell import Module, action

if TYPE_CHECKING:
    from tess_shell.module import Event
    from tess_shell.modules.context import UseRecord
    from tess_shell.modules.ticks import Subscription as TickSubscription
    from tess_shell.services.api import AppInfo, LaunchResult, Subscription

FALLBACK_ICON = "mdi:application-outline"
ROW_HEIGHT = 40  # pixels: the layout's ``Height`` of a row
FIELD = "query"  # the ``Name`` of the text field in the layout
MODIFIERS = ("ctrl", "alt", "meta")


class State:
    """What one use shows."""

    __slots__ = (
        "heard",
        "heard_message",
        "last",
        "message",
        "pending",
        "query",
        "results",
        "selected",
        "sent",
        "zero_width",
    )

    def __init__(self) -> None:
        self.query = ""
        self.results: list[AppInfo] = []
        self.selected = 0  # the index of the selected row
        self.message = ""  # "Could not start <name>"
        self.sent: dict[str, Any] = {}  # the last value sent, by key
        self.heard: str | None = None  # the id of the row last said (None: no row chosen yet)
        self.heard_message = ""  # the message last said (or there when the Panel was shown)
        self.last = ""  # the words last put in the live region, without the mark
        self.zero_width = False  # the mark is on them (see :meth:`Applications.words`)
        self.pending = False  # a narrowed list's row waits for the next second to be said


class Applications(Module):
    def __init__(self) -> None:
        self.states: dict[str, State] = {}
        self.subs: list[Subscription] = []
        self.pool: ThreadPoolExecutor | None = None
        self.icons: dict[tuple[str, int], str] = {}  # (application, size) -> a reference
        self.pending: set[tuple[str, int]] = set()  # icons the worker is making
        self.generation = 0  # counts icon-theme changes: a result of an older one is dropped
        self.tick_sub: TickSubscription | None = None  # the second that says a narrowed list's row

    # -- start and stop -------------------------------------------------------------------------

    def start(self) -> None:
        self.pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="applications-icons")
        self.subs = [
            self.ctx.apps.on_changed(self.list_changed),
            self.ctx.surface.on_shown(self.shown),
            self.ctx.icons.on_theme_changed(self.theme_changed),
        ]
        for use in self.ctx.uses.values():
            self.use_added(use)

    def stop(self) -> None:
        for sub in self.subs:
            sub.cancel()
        self.subs = []
        if self.pool is not None:
            self.pool.shutdown(wait=False, cancel_futures=True)
            self.pool = None
        if self.tick_sub is not None:
            self.tick_sub.cancel()
            self.tick_sub = None

    def validate_use(self, use: UseRecord) -> None:
        rows = use.params.get("max_results")
        if isinstance(rows, bool) or not isinstance(rows, int | float) or rows < 1:
            raise ValueError(f"max_results is a number of rows, 1 or more, not {rows!r}")
        size = use.params.get("icon_size")
        if isinstance(size, bool) or not isinstance(size, int | float) or size <= 0:
            raise ValueError(f"icon_size is a size in pixels, above 0, not {size!r}")

    def use_added(self, use: UseRecord) -> None:
        self.states.setdefault(use.key, State())
        self.refresh(use)

    def use_removed(self, use: UseRecord) -> None:
        self.states.pop(use.key, None)

    # -- what changed ---------------------------------------------------------------------------

    def list_changed(self) -> None:
        """The index was built or built again, or a start changed the order."""
        for use in list(self.ctx.uses.values()):
            self.refresh(use)

    def shown(self, use: UseRecord) -> None:
        """The Panel was shown: the list is made again if the folders are not watched, and the
        field takes the focus with its text selected, so typing starts a new search. Nothing said
        before is said again: the announcement is cleared (the live region is in the tree only
        while the Panel is shown) and the row and the message that are there now count as heard."""
        self.ctx.apps.refresh()
        state = self.states.get(use.key)
        if state is not None and state.message:
            state.message = ""
            self.send(use, "message", "")
        if state is not None:
            state.heard = state.results[state.selected].id if state.results else None
            state.heard_message = self.empty_text(state)
            state.last, state.zero_width, state.pending = "", False, False
            self.send(use, "announcement", "")
        self.ctx.surface.focus(FIELD, select_all=True, use=use)

    def theme_changed(self) -> None:
        """The desktop's icon theme changed (any thread): earlier icons are the old theme's."""
        self.ctx.call_soon(self.theme_changed_on_loop)

    def theme_changed_on_loop(self) -> None:
        self.generation += 1
        self.icons.clear()
        self.list_changed()

    # -- icons (a worker thread) ----------------------------------------------------------------

    def icon(self, app: str, size: int) -> str:
        """The icon of an application, or the fallback while the worker is reading it."""
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
        self.list_changed()

    # -- what is shown (loop thread) ------------------------------------------------------------

    def rows(self, use: UseRecord) -> int:
        return max(int(use.params.get("max_results") or 8), 1)

    def compute(self, use: UseRecord, state: State, keep: str | None = None) -> None:
        """Make the results of the use's query; ``keep`` is the id that stays selected if it is
        still there (the list changed under the user), else the first row is."""
        state.results = self.ctx.apps.search(state.query, self.rows(use))
        index = 0
        if keep is not None:
            index = next((i for i, a in enumerate(state.results) if a.id == keep), 0)
        state.selected = index

    def send(self, use: UseRecord, key: str, value: Any) -> None:
        state = self.states[use.key]
        if key not in state.sent or state.sent[key] != value:
            state.sent[key] = value
            self.ctx.send(key, value, use=use)

    def empty_text(self, state: State) -> str:
        if not self.ctx.apps.ready:
            return ""
        if state.message:
            return state.message
        if state.results:
            return ""
        return "No results" if state.query.strip() else "No applications found"

    def refresh(self, use: UseRecord, settle: bool = False) -> None:
        """Send the use every value that differs from what it has (the first call sends all)."""
        state = self.states.get(use.key)
        if state is None:
            return
        keep = state.results[state.selected].id if state.results else None
        self.compute(use, state, keep)
        size = int(use.params.get("icon_size") or 24)
        rows = [
            {
                "id": a.id,
                "name": a.name,
                "comment": a.generic_name or a.comment,
                "icon": self.icon(a.id, size),
            }
            for a in state.results
        ]
        chosen = state.results[state.selected].id if state.results else ""
        message = self.empty_text(state)
        values: dict[str, Any] = {
            "ready": self.ctx.apps.ready,
            "query": state.query,
            "results": rows,
            "selected": state.selected,
            "selected_id": chosen,
            "has_results": bool(rows),
            "list_height": len(rows) * ROW_HEIGHT,
            "message": message,
        }
        if "announcement" not in state.sent:
            values["announcement"] = ""  # a value before the first announcement
        said = self.announcement(state, rows, chosen, message, settle)
        if said:
            values["announcement"] = said
        for key, value in values.items():
            self.send(use, key, value)

    def announcement(
        self, state: State, rows: list[dict[str, Any]], chosen: str, message: str, settle: bool
    ) -> str:
        """The words this refresh says aloud (Accessibility, rule 6, ``POLITE``), or ``""``: a new
        message ("No results", "Could not start <name>") at once; a selected row that is not the
        one last said, as ``Name, 2 of 8``: at once when the user moved the selection, and when the
        list narrowed under typing (``settle``) at the next second, so typing is not one
        announcement a key. The first row of a list nobody has heard is not said (``heard`` is
        ``None`` until one is chosen)."""
        if message != state.heard_message:
            state.heard_message = message
            if message:
                return self.words(state, message)
        if not chosen:
            return ""
        if state.heard is None:
            state.heard = chosen
            return ""
        if chosen == state.heard:
            return ""
        if settle:
            state.pending = True
            if self.tick_sub is None:
                self.tick_sub = self.ctx.on_tick("second", self.settled)
            return ""
        state.heard, state.pending = chosen, False
        name = rows[state.selected]["name"]
        return self.words(state, f"{name}, {state.selected + 1} of {len(rows)}")

    @staticmethod
    def words(state: State, text: str) -> str:
        """``text`` for the live region; the same words twice in a row get an invisible mark added
        and taken off in turn, because only a change of the label is announced."""
        if text == state.last:
            state.zero_width = not state.zero_width
        else:
            state.last, state.zero_width = text, False
        return text + ("\u200b" if state.zero_width else "")

    def settled(self) -> None:
        """Loop thread, the second after the list narrowed under typing: say the row now chosen
        if it is not the one last said, and stop the tick."""
        if self.tick_sub is not None:
            self.tick_sub.cancel()
            self.tick_sub = None
        for key, state in list(self.states.items()):
            use = self.ctx.uses.get(key)
            if state.pending and use is not None:
                state.pending = False
                self.refresh(use)

    def use_of(self, event: Event) -> tuple[UseRecord, State] | None:
        use = self.ctx.uses.get(event.use)
        state = self.states.get(event.use)
        return (use, state) if use is not None and state is not None else None

    # -- the field and the list (loop thread) ---------------------------------------------------

    @action
    def search(self, event: Event, text: str = "") -> None:
        """Typing in the field: the list narrows and the first row is selected."""
        found = self.use_of(event)
        if found is None:
            return
        use, state = found
        state.query, state.message = text, ""
        self.compute(use, state)
        self.refresh(use, settle=True)
        self.ctx.log.debug(f"search {text!r}: {len(state.results)} results")

    def move(self, use: UseRecord, state: State, step: int, wrap: bool) -> None:
        """Move the selection by ``step`` rows; a single step wraps round the ends, a page stops
        at them."""
        count = len(state.results)
        if not count:
            return
        target = state.selected + step
        state.selected = target % count if wrap else min(max(target, 0), count - 1)
        self.refresh(use)
        self.ctx.log.debug(f"selected {state.results[state.selected].name}")

    @action
    def key(self, event: Event) -> None:
        """``On_Key_Down`` of the field (it comes before the field acts, which it does whatever
        this does): the list's keys are moved from it, and Escape is the module's (clear, then
        hide). A key this module uses goes no further, so the Panel's own Escape does not also
        hide a Panel that was only cleared."""
        found = self.use_of(event)
        if found is None or event.key is None:
            return
        use, state = found
        self.ctx.log.debug(f"key {event.key}")  # what tells a log that the keys arrive at all
        if any(getattr(event, name) for name in MODIFIERS):
            return  # Ctrl, Alt or Meta with a key is the user's shortcut, not the list's
        page = self.rows(use)
        if event.key == "arrow_down":
            self.move(use, state, 1, True)
        elif event.key == "arrow_up":
            self.move(use, state, -1, True)
        elif event.key == "page_down":
            self.move(use, state, page, False)
        elif event.key == "page_up":
            self.move(use, state, -page, False)
        elif event.key == "escape":
            if state.query:
                state.query, state.message = "", ""
                self.compute(use, state)
                self.refresh(use, settle=True)
                self.ctx.log.debug("escape: the field is cleared")
            else:
                self.ctx.log.debug("escape: the panel hides")
                self.ctx.surface.hide(use)
        else:
            return
        event.stop()

    @action
    def launch_selected(self, event: Event) -> None:
        """Enter in the field: start the selected row."""
        found = self.use_of(event)
        if found is None:
            return
        use, state = found
        if state.results:
            self.start_app(use, state.results[state.selected])

    @action
    def launch(self, event: Event, id: str) -> None:
        """A click on a row: start that application."""
        found = self.use_of(event)
        if found is None:
            return
        use, state = found
        app = next((a for a in state.results if a.id == id), None)
        if app is not None:
            self.start_app(use, app)

    def start_app(self, use: UseRecord, app: AppInfo) -> None:
        """Start ``app``. The token is asked for now (inside the key or click that starts it); when
        the start is made the field is cleared and the Panel hides, and when it failed the Panel
        stays open and says so."""
        self.ctx.apps.launch(
            app.id, use=use.key, on_done=lambda result: self.started(use, app, result)
        )

    def started(self, use: UseRecord, app: AppInfo, result: LaunchResult) -> None:
        state = self.states.get(use.key)
        if state is None:
            return
        if result.ok:
            state.query, state.message = "", ""
            self.compute(use, state)
            self.refresh(use)
            self.ctx.surface.hide(use)
        else:
            self.ctx.log.warning(f"could not start {app.name}: {result.error}")
            state.message = f"Could not start {app.name}"
            state.heard_message = ""  # a second failure of the same one is said again
            self.refresh(use)
