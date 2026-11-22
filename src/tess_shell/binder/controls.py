"""Controls: what a module's block does with the pointer so that a Toggle, a Checkbox, a Slider and
a List keep their own state (Standard Modules > Toggle, Checkbox, Slider, List).

A control is a behaviour of one built block, chosen by a key of the module's layout that gives tre
nothing (``Toggles``, ``Slides``, ``Selection_Mode``). The value comes in from outside through the
tre property the block already has for it (``checked``, ``value``) or ``Chosen``; the user's edits
go out through ``On_Changed`` and the block's flag states (``:checked``, ``:selected``) and its
accessibility state. Data in, edits out (R6): a value that the module sets moves the control and
raises nothing; a value the user sets stays until the module sets a different one. Nothing here
runs in Python while the pointer does nothing: a slider drag is pointer events, the engine draws
the result and an idle control draws no frame.

The keys of a control (Standard Modules > Keyboard Operation) are its ``key_down`` listener: a node
with a ``key_down`` listener keeps every key, so a focused Toggle, Slider or List does not scroll a
scroll view around it with the arrow keys (tre's rule), and a handled key does not bubble. tre fires
``click`` for Enter and Space on a focused node itself (``Activated``, after the ``key_down``); a
click that came from the keyboard has no pointer position and no button (:func:`from_keyboard`).
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from tess_shell.binder.model import Enum, Text

if TYPE_CHECKING:
    from tess_re import Node as TreNode

    from tess_shell.binder.build import Entry, View, Wire


def _word(entry: Entry, key: str) -> str:
    value = entry.typed.props.get(key)
    return value.name if isinstance(value, Enum) else ""


def _flag(entry: Entry, key: str) -> bool:
    value = entry.typed.props.get(key)
    return bool(getattr(value, "value", False))


def _holds_focus(node: TreNode) -> bool:
    """Whether ``node`` or a node under it has keyboard focus."""
    return bool(node.get("focused")) or any(_holds_focus(c) for c in node.children())


def from_keyboard(event: Any) -> bool:
    """Whether a ``click`` was made by Enter or Space on a focused block (tre's ``Activated``): it
    has no pointer position and no button, a click of the pointer has both."""
    return getattr(event, "button", None) is None and getattr(event, "x", None) is None


def plain(event: Any) -> bool:
    """A key with no Ctrl, Alt or Meta held: those are the user's shortcuts, not the widget's."""
    return not any(getattr(event, name, False) for name in ("ctrl", "alt", "meta"))


_KEYS = frozenset({"Toggles", "Selection_Mode", "Slides", "Menu_Item", "Reveals"})
# the blocks the engine's container selection takes (tre 0.6.13: a box, container or scroll view)
_CONTAINERS = frozenset({"ScrollBox", "FlexBox", "Box"})


def kind_of(entry: Entry) -> str:
    """The control this block is: ``toggle``, ``select``, ``slide``, ``item``, ``expand`` or
    empty."""
    if _KEYS.isdisjoint(entry.typed.props):  # most blocks: no control key written
        return ""
    if _flag(entry, "Toggles"):
        return "toggle"
    mode = _word(entry, "Selection_Mode")
    if mode == "SINGLE":
        return "select"
    if mode == "MULTIPLE" and entry.typed.kind in _CONTAINERS:
        return "multiselect"
    if _word(entry, "Slides") in ("HORIZONTAL", "VERTICAL"):
        return "slide"
    if _flag(entry, "Menu_Item"):
        return "item"
    if _word(entry, "Reveals") in ("OPEN", "CLOSED"):
        return "expand"
    return ""


class Control:
    """Base: the block, its wire and where ``On_Changed`` goes."""

    takes_keys = False  # the control has keys: its block listens for ``key_down``

    def __init__(self, view: View, entry: Entry) -> None:
        self.view = view
        self.entry = entry
        assert entry.tre is not None
        self.tre: TreNode = entry.tre
        self.wired = False
        self.key_wired = False

    @property
    def wire(self) -> Wire | None:
        return self.entry.wire

    def configure(self, entry: Entry) -> None:
        """The block was built or rebuilt (``entry`` is its current entry): read what the module
        gives and adopt a new outside value; keep the user's edit when the outside value is the
        one it already was."""
        self.entry = entry

    def sync(self) -> None:
        """A property of the block changed (a slot of the module)."""
        self.configure(self.entry)

    def changed(self, old: object, new: object) -> None:
        """Raise ``On_Changed``, if the call wrote one."""
        wire = self.wire
        handler = wire.handlers.get("On_Changed") if wire is not None else None
        if handler is None or self.view.sink is None:
            return
        raw = SimpleNamespace(old_value=old, new_value=new, value=new)
        self.view.sink(handler, "On_Changed", raw)

    def released(self, old: object, new: object) -> None:
        """Raise ``On_Released``, if the call wrote one: the press that moved a slider ended."""
        wire = self.wire
        handler = wire.handlers.get("On_Released") if wire is not None else None
        if handler is None or self.view.sink is None:
            return
        raw = SimpleNamespace(old_value=old, new_value=new, value=new)
        self.view.sink(handler, "On_Released", raw)

    def listen_keys(self) -> None:
        """Listen for the control's keys, once (a node takes one ``key_down`` listener)."""
        if self.takes_keys and not self.key_wired:
            self.key_wired = True
            self.tre.on("key_down", self._key_down)

    def _key_down(self, event: Any) -> None:
        wire = self.wire
        if wire is not None and wire.blocked:  # a disabled block takes no key
            return
        if self.key(event):
            event.stop()  # the key was the control's: nothing above it hears it

    def key(self, event: Any) -> bool:
        """A key went down on the focused block (or one under it); whether the control used it."""
        return False

    def accepts(self, event: Any) -> bool:
        """Whether a ``click`` that reached the block does anything: the block's ``On_Click`` and
        :meth:`clicked` run only when it does."""
        return True

    def clicked(self, event: Any) -> None:  # noqa: B027 - most controls do not take a click
        """The block's ``click`` (not blocked, not stopped by an entry's own handler)."""

    def stop(self) -> None:
        """The block is gone."""


class Toggle(Control):
    """``Toggles: true``: a click flips ``Checked`` (tre's ``checked``). Space flips it too and
    Enter does nothing (Standard Modules > Keyboard Operation): tre clicks the focused block for
    both keys, so the block remembers an Enter (and a repeat of a held Space) from the
    ``key_down`` that comes first and does not take the click that follows."""

    takes_keys = True

    def __init__(self, view: View, entry: Entry) -> None:
        super().__init__(view, entry)
        self.state = False
        self.base: bool | None = None
        self.mute = False  # the next click from the keyboard is not a flip

    def key(self, event: Any) -> bool:
        key = getattr(event, "key", None)
        self.mute = key == "enter" or (key == "space" and bool(getattr(event, "repeat", False)))
        return False

    def accepts(self, event: Any) -> bool:
        mute, self.mute = self.mute, False
        return not (mute and from_keyboard(event))

    def configure(self, entry: Entry) -> None:
        super().configure(entry)
        wire = entry.wire
        if wire is not None:
            wire.owned = True
        param = bool(entry.props.get("checked", False))
        if self.base is None or param != self.base:
            self.base = param
            self.state = param
        self.apply()

    def apply(self) -> None:
        if self.tre.get("checked") != self.state:
            self.tre.set(checked=self.state)
        if self.wire is not None:
            self.wire.set_flags(checked=self.state)

    def clicked(self, event: Any) -> None:
        old = self.state
        self.state = not old
        self.apply()
        self.view.resync()  # the parts of the module show the new state too
        self.changed(old, self.state)


TYPE_AHEAD_MS = 1000  # the letters typed in a list make one search until this long after the last


class Select(Control):
    """``Selection_Mode: SINGLE``: the block's children are the entries of a list; a click on one
    chooses it (an entry has a ``Key``, a ``For`` entry the key of the repeater).

    The keys (Standard Modules > Keyboard Operation): Up and Down move the chosen entry (the
    first Down chooses the first entry and the first Up the last), Page Up and Page Down by a
    page, Home and End to the ends, Enter and Space choose the first entry when none is chosen,
    and a letter typed jumps to the next entry whose text starts with the letters typed in the
    last second. Every move is a choice: ``On_Changed`` with the old and the new key, and the
    entry scrolls into view. An entry that is disabled is passed over."""

    takes_keys = True

    def __init__(self, view: View, entry: Entry) -> None:
        super().__init__(view, entry)
        self.chosen = ""
        self.base: str | None = None
        self.typed = ""  # the letters of the search in progress
        self.forget: Any = None  # the timer that ends it

    def keys(self) -> list[tuple[str, Entry]]:
        """The entries and their keys: the children of the block, or, when the block is a
        ScrollBox (a list that scrolls), the children of the one child it scrolls."""
        out: list[tuple[str, Entry]] = []
        holder = self.entry
        if holder.typed.kind == "ScrollBox" and holder.children:
            holder = holder.children[0]
        for child in holder.children:
            key = child.typed.props.get("Key")
            if isinstance(key, Text) and child.tre is not None:
                out.append((key.value, child))
        return out

    def configure(self, entry: Entry) -> None:
        super().configure(entry)
        value = self.view.dynamic.get(entry.typed.name or "", {}).get("Chosen")
        value = value if value is not None else entry.typed.props.get("Chosen")
        param = value.value if isinstance(value, Text) else ""
        if self.base is None or param != self.base:
            self.base = param
            self.chosen = param
        self.apply()

    def apply(self) -> None:
        for key, child in self.keys():
            on = key == self.chosen
            if child.wire is not None:
                child.wire.owned = True
                child.wire.set_flags(selected=on)
            if child.tre is not None:
                if child.tre.get("selected") != on:
                    child.tre.set(selected=on)
                if "role" not in child.props and child.tre.get("role") != "listitem":
                    child.tre.set(role="listitem")
        self.view.point_fields(self)

    def choose(self, key: str, child: Entry) -> None:
        """The user chose the entry ``key`` (``child``): it takes the state, ``On_Changed`` says
        so, and it scrolls into view."""
        if key != self.chosen:
            old = self.chosen
            self.chosen = key
            self.apply()
            self.view.resync()
            self.changed(old, key)
        if child.tre is not None:
            child.tre.scroll_into_view()

    def clicked(self, event: Any) -> None:
        target = getattr(event, "target", None)
        by_node = {child.tre: key for key, child in self.keys()}
        node = target
        while node is not None and node not in by_node:
            node = node.parent()
        if node is None:
            return
        key = by_node[node]
        child = next(c for k, c in self.keys() if k == key)
        if child.wire is not None and child.wire.blocked:
            return
        if key == self.chosen:
            return
        old = self.chosen
        self.chosen = key
        self.apply()
        self.view.resync()
        self.changed(old, key)

    # -- the keys -----------------------------------------------------------------------------

    def enabled(self) -> list[tuple[str, Entry]]:
        return [(k, c) for k, c in self.keys() if c.wire is None or not c.wire.blocked]

    def page(self) -> int:
        """How many entries fit in the list: the step of Page Up and Page Down."""
        rows = self.keys()
        if not rows or rows[0][1].tre is None:
            return 1
        row = float(rows[0][1].tre.get("layout_height") or 0)
        shown = float(self.tre.get("layout_height") or 0)
        return max(int(shown // row), 1) if row > 0 else 1

    @staticmethod
    def text_of(entry: Entry) -> str:
        """What an entry says, for a search by typing: its ``Label``, else the text of the
        ``Text`` blocks in it."""
        label = entry.tre.get("label") if entry.tre is not None else None
        if label:
            return str(label)
        parts: list[str] = []

        def walk(e: Entry) -> None:
            if e.tre is not None and e.typed.kind == "Text":
                parts.append(str(e.tre.get("text") or ""))
            for c in e.children:
                walk(c)

        walk(entry)
        return " ".join(p for p in parts if p)

    def search(self, letter: str, rows: list[tuple[str, Entry]], at: int | None) -> int | None:
        """The entry a typed ``letter`` jumps to: the next one whose text starts with the letters
        typed in the last second (the same letter again goes round the entries that start with
        it), or ``None``."""
        self.typed += letter.lower()
        if self.forget is not None:
            self.forget.cancel()
        self.forget = self.view.window.after(TYPE_AHEAD_MS, self._forget)
        needle = self.typed
        again = len(set(needle)) == 1  # "aa": the next entry that starts with "a"
        if again:
            needle = needle[0]
        first = 0 if at is None else (at + 1 if again or len(needle) == 1 else at)
        count = len(rows)
        for i in range(count):
            at_i = (first + i) % count
            if self.text_of(rows[at_i][1]).lower().startswith(needle):
                return at_i
        return None

    def _forget(self) -> None:
        self.typed = ""
        self.forget = None

    def key(self, event: Any) -> bool:
        key = getattr(event, "key", None)
        if not isinstance(key, str) or not plain(event):
            return False
        rows = self.enabled()
        if not rows:
            return False
        names = [k for k, _ in rows]
        at = names.index(self.chosen) if self.chosen in names else None
        last = len(rows) - 1
        if key == "arrow_down":
            to = 0 if at is None else min(at + 1, last)
        elif key == "arrow_up":
            to = last if at is None else max(at - 1, 0)
        elif key == "page_down":
            to = 0 if at is None else min(at + self.page(), last)
        elif key == "page_up":
            to = last if at is None else max(at - self.page(), 0)
        elif key == "home":
            to = 0
        elif key == "end":
            to = last
        elif key == "space" and self.typed:  # a space in the middle of a search is a letter of it
            found = self.search(" ", rows, at)
            if found is None:
                return True
            to = found
        elif key in ("enter", "space"):
            to = 0 if at is None else at
        elif len(key) == 1 and key.isprintable():
            found = self.search(key, rows, at)
            if found is None:
                return True  # nothing starts with it: the key was a search all the same
            to = found
        else:
            return False
        self.choose(*rows[to])
        return True

    def stop(self) -> None:
        if self.forget is not None:
            self.forget.cancel()
            self.forget = None


class MultiSelect(Control):
    """``Selection_Mode: MULTIPLE``: the same entries as :class:`Select`, chosen as a set by the
    engine's own container selection (tre 0.6.13: ``selection_mode`` ``"multiple"`` on the
    ScrollBox, whose items are the children of the one child it scrolls). The engine has the
    rules (Selection pattern: click, Shift+click a range, Ctrl+click a toggle, Shift+Up and Down,
    Ctrl+Space, Ctrl+A, a disabled entry is skipped, the anchor), says ``selected`` and
    ``multiselectable`` to assistive technology and announces the count once, debounced; the shell
    keeps the ``:selected`` look, ``Selected`` from outside and ``On_Changed``. The keys of the
    chosen entries are joined by a comma (``old``, ``new`` and ``value`` of the event; the same
    text is what ``Selected`` takes), in the order of the entries."""

    ANNOUNCE = "{count} selected"

    def __init__(self, view: View, entry: Entry) -> None:
        super().__init__(view, entry)
        self.chosen: frozenset[str] = frozenset()
        self.base: str | None = None
        self.listening = False

    def entries(self) -> list[tuple[str, Entry]]:
        """The keyed entries, as :meth:`Select.keys` finds them."""
        out: list[tuple[str, Entry]] = []
        holder = self.entry
        if holder.typed.kind == "ScrollBox" and holder.children:
            holder = holder.children[0]
        for child in holder.children:
            key = child.typed.props.get("Key")
            if isinstance(key, Text) and child.tre is not None:
                out.append((key.value, child))
        return out

    def items(self) -> list[Entry]:
        holder = self.entry.children[0] if self.entry.children else self.entry
        return list(holder.children)

    def text(self, keys: frozenset[str]) -> str:
        return ",".join(k for k, _ in self.entries() if k in keys)

    def configure(self, entry: Entry) -> None:
        super().configure(entry)
        tre = self.tre
        if tre.get("selection_mode") != "multiple":
            tre.set(selection_mode="multiple", select_all_key=True)
        if tre.get("selection_announce") != self.ANNOUNCE:
            tre.set(selection_announce=self.ANNOUNCE)
        # a child that is not an entry, or is disabled, is not chosen by a range or a key
        keyed = {id(child) for _, child in self.entries()}
        for child in self.items():
            if child.tre is None:
                continue
            can = id(child) in keyed and not child.tre.get("disabled")
            if child.tre.get("item_selectable") != can:
                child.tre.set(item_selectable=can)
        value = self.view.dynamic.get(entry.typed.name or "", {}).get("Chosen")
        value = value if value is not None else entry.typed.props.get("Chosen")
        param = value.value if isinstance(value, Text) else ""
        if self.base is None or param != self.base:
            self.base = param
            wanted = frozenset(k for k in param.split(",") if k)
            self.chosen = wanted
            nodes = [c.tre for k, c in self.entries() if k in wanted and c.tre is not None]
            tre.set(selection=nodes)
        self.apply()
        if not self.listening:
            self.listening = True
            tre.on("selection_change", self.moved)

    def apply(self) -> None:
        for key, child in self.entries():
            on = key in self.chosen
            if child.wire is not None:
                child.wire.owned = True
                child.wire.set_flags(selected=on)
            if child.tre is not None and child.tre.get("selected") != on:
                child.tre.set(selected=on)  # what the engine says to assistive technology
            if child.tre is not None and "role" not in child.props:
                if child.tre.get("role") != "listitem":
                    child.tre.set(role="listitem")

    def moved(self, event: Any) -> None:
        """The engine changed the set (a click, a key, Ctrl+A, or a set from outside)."""
        nodes = list(getattr(event, "selection", None) or [])
        by_node = {child.tre: key for key, child in self.entries()}
        new = frozenset(by_node[n] for n in nodes if n in by_node)
        if new == self.chosen:
            return
        old = self.chosen
        self.chosen = new
        self.apply()
        self.view.resync()
        self.changed(self.text(old), self.text(new))


class Slide(Control):
    """``Slides: HORIZONTAL | VERTICAL``: a press on the block, and a drag with the pointer
    captured, set ``value`` between ``value_min`` and ``value_max`` in steps of ``value_step``.
    The block's parts ``fill`` and ``handle`` follow it. The keys are at :meth:`key`."""

    takes_keys = True

    def __init__(self, view: View, entry: Entry) -> None:
        super().__init__(view, entry)
        self.value = 0.0
        self.base: float | None = None
        self.low, self.high, self.step = 0.0, 100.0, 1.0
        self.vertical = False
        self.dragging = False
        self.pressed_at: int | float = 0  # the value when the press began
        self.size = (0.0, 0.0)
        self.fill: Entry | None = None
        self.handle: Entry | None = None

    def configure(self, entry: Entry) -> None:
        super().configure(entry)
        self.vertical = _word(entry, "Slides") == "VERTICAL"
        props = entry.props
        self.low = float(props.get("value_min", 0))
        self.high = float(props.get("value_max", 100))
        self.step = float(props.get("value_step", 1))
        self.fill = self._part(entry, "fill")
        self.handle = self._part(entry, "handle")
        param = self.clamp(float(props.get("value", self.low)))
        if self.base is None or param != self.base:
            self.base = param
            self.value = param
        if not self.wired:
            self.wired = True
            self._listen()
        self.apply()

    @staticmethod
    def _part(entry: Entry, name: str) -> Entry | None:
        for child in entry.children:
            if child.typed.part == name:
                return child
            found = Slide._part(child, name)
            if found is not None:
                return found
        return None

    def _listen(self) -> None:
        wire = self.wire
        if wire is None:
            return
        wire.add_hook("down", self.down)
        wire.add_hook("up", self.up)
        self.tre.on("pointer_move", self.move)
        self.tre.on("layout", self.laid_out)

    # -- the value ----------------------------------------------------------------------------

    def clamp(self, value: float) -> float:
        value = min(max(value, self.low), self.high)
        if self.step > 0:
            value = self.low + round((value - self.low) / self.step) * self.step
            value = min(max(value, self.low), self.high)
        value = round(value, 9)
        return float(int(value)) if value == int(value) else value

    def number(self, value: float) -> int | float:
        return int(value) if value == int(value) else value

    def fraction(self, value: float | None = None) -> float:
        span = self.high - self.low
        if span <= 0:
            return 0.0
        return min(max(((self.value if value is None else value) - self.low) / span, 0.0), 1.0)

    # -- the keys -----------------------------------------------------------------------------

    def key(self, event: Any) -> bool:
        """Left and Down take a step off, Right and Up put a step on, Page Up and Page Down ten,
        Home and End go to the ends (Standard Modules > Keyboard Operation, in both
        orientations). Each key that moves the value raises ``On_Changed`` and then, at once,
        ``On_Released``, both with the value before the step as ``old``; one that cannot move it
        (at an end) raises nothing."""
        key = getattr(event, "key", None)
        if self.dragging or not plain(event):
            return False
        step = self.step if self.step > 0 else 1.0
        if key in ("arrow_right", "arrow_up"):
            target = self.value + step
        elif key in ("arrow_left", "arrow_down"):
            target = self.value - step
        elif key == "page_up":
            target = self.value + 10 * step
        elif key == "page_down":
            target = self.value - 10 * step
        elif key == "home":
            target = self.low
        elif key == "end":
            target = self.high
        else:
            return False
        new = self.clamp(target)
        if new != self.value:
            old = self.value
            self.value = new
            self.apply()
            self.changed(self.number(old), self.number(new))
            self.released(self.number(old), self.number(new))
        return True

    # -- geometry -----------------------------------------------------------------------------

    def laid_out(self, event: Any) -> None:
        self.size = (float(event.width or 0), float(event.height or 0))
        self.apply()

    def _handle_size(self) -> float:
        node = self.handle.tre if self.handle is not None else None
        if node is None:
            return 0.0
        return float(node.get("layout_height" if self.vertical else "layout_width") or 0)

    def apply(self) -> None:
        """Put the handle and the fill where the value is, and the value in the accessibility
        state."""
        number = self.number(self.value)
        if self.tre.get("value") != number:
            self.tre.set(value=number)
        length = self.size[1] if self.vertical else self.size[0]
        if length <= 0:
            length = float(self.tre.get("layout_height" if self.vertical else "layout_width") or 0)
        if length <= 0:
            return
        hs = self._handle_size() or 0.0
        travel = max(length - hs, 0.0)
        f = self.fraction()
        if self.handle is not None and self.handle.tre is not None:
            if self.vertical:
                self.handle.tre.set(translate_y=(1 - f) * travel)
            else:
                self.handle.tre.set(translate_x=f * travel)
        if self.fill is not None and self.fill.tre is not None:
            reach = f * travel + hs / 2
            if self.vertical:
                self.fill.tre.set(height=reach, translate_y=length - reach)
            else:
                self.fill.tre.set(width=reach)

    # -- the pointer --------------------------------------------------------------------------

    def _from(self, event: Any) -> float | None:
        x, y = getattr(event, "x", None), getattr(event, "y", None)
        pos = y if self.vertical else x
        length = self.size[1] if self.vertical else self.size[0]
        if length <= 0:
            length = float(self.tre.get("layout_height" if self.vertical else "layout_width") or 0)
        if pos is None or length <= 0:
            return None
        hs = self._handle_size()
        travel = max(length - hs, 1.0)
        f = min(max((float(pos) - hs / 2) / travel, 0.0), 1.0)
        if self.vertical:
            f = 1.0 - f
        return self.low + f * (self.high - self.low)

    def to(self, event: Any) -> None:
        raw = self._from(event)
        if raw is None:
            return
        new = self.clamp(raw)
        if new == self.value:
            return
        old = self.value
        self.value = new
        self.apply()
        self.changed(self.number(old), self.number(new))

    def down(self) -> None:
        wire = self.wire
        event = getattr(wire, "event", None)
        if event is None or getattr(event, "button", "primary") not in (None, "primary"):
            return
        self.dragging = True
        self.pressed_at = self.number(self.value)
        self.tre.capture_pointer()
        if self.handle is not None and self.handle.wire is not None:
            self.handle.wire.down()  # the handle shows pressed whatever part was pressed
        self.to(event)

    def move(self, event: Any) -> None:
        if self.dragging:
            self.to(event)

    def up(self) -> None:
        if not self.dragging:
            return
        self.dragging = False
        wire = self.wire
        event = getattr(wire, "event", None)
        if self.handle is not None and self.handle.wire is not None:
            self.handle.wire.up()  # the capture took the release from the handle
            if event is not None and not self._over_handle(event):
                self.handle.wire.leave()
        # once per press, however it ended: the button went up (the capture delivers it outside
        # the slider too), the press was taken for a window move, or the slider was disabled
        self.released(self.pressed_at, self.number(self.value))

    def _over_handle(self, event: Any) -> bool:
        x, y = getattr(event, "x", None), getattr(event, "y", None)
        node = self.handle.tre if self.handle is not None else None
        if x is None or y is None or node is None:
            return False
        length = self.size[1] if self.vertical else self.size[0]
        hs = self._handle_size()
        travel = max(length - hs, 0.0)
        f = self.fraction()
        w, h = float(node.get("layout_width") or 0), float(node.get("layout_height") or 0)
        left = 0.0 if self.vertical else f * travel
        top = (1 - f) * travel if self.vertical else 0.0
        return bool(left <= x <= left + w and top <= y <= top + h)

    def stop(self) -> None:
        self.dragging = False


class Item(Control):
    """``Menu_Item: true``: a row of a menu. The Popup that holds it hears the pointer enter and
    leave and a click (``View.menu_sink``): it opens the submenu the row names (``Opens``) after
    the pointer rests on it or at a click, closes the one that is open when the pointer rests on
    another row, and closes the menu after a click on a row that opens nothing."""

    def __init__(self, view: View, entry: Entry) -> None:
        super().__init__(view, entry)
        self.opens = ""

    def configure(self, entry: Entry) -> None:
        super().configure(entry)
        value = entry.typed.props.get("Opens")
        self.opens = value.value if isinstance(value, Text) else ""
        if not self.wired and entry.wire is not None:
            self.wired = True
            entry.wire.add_hook("enter", lambda: self.say("enter"))
            entry.wire.add_hook("leave", lambda: self.say("leave"))

    def say(self, event: str) -> None:
        sink = self.view.menu_sink
        if sink is not None and self.entry.typed.name is not None:
            sink(event, self.entry.typed.name, self.opens)

    def clicked(self, event: Any) -> None:
        self.say("click")


class Expand(Control):
    """``Reveals: OPEN | CLOSED``: an Expander's root. The module sets the state it wants (a slot
    of its ``Expanded`` param); the size and the content's opacity ease there (``binder.motion``)
    and, when the size has arrived, ``On_Changed`` is raised with ``event.value`` the new state.
    A change with nothing to ease (reduced motion, a ``Duration`` of 0, a content with no size)
    raises it at once; an opening reversed half-way raises nothing for the opening that did not
    finish, and one event for the closing that did."""

    def __init__(self, view: View, entry: Entry) -> None:
        super().__init__(view, entry)
        self.open: bool | None = None  # the state the block was last told
        self.pending = False  # a size animation is on its way to the state
        self.tre.on("animation_end", self._ended)

    def _wanted(self, entry: Entry) -> bool:
        value = self.view.dynamic.get(entry.typed.name or "", {}).get("Reveals")
        value = value if value is not None else entry.typed.props.get("Reveals")
        return isinstance(value, Enum) and value.name == "OPEN"

    @property
    def axis(self) -> str:
        """The size that eases: the width of a row (LEFT, RIGHT), else the height."""
        return "width" if self.tre.get("flex_direction") == "horizontal" else "height"

    def configure(self, entry: Entry) -> None:
        super().configure(entry)
        now = self._wanted(entry)
        if self.open is None:  # the first state is what the block starts in
            self.open = now
        elif now != self.open:
            self.open = now
            axis = self.axis
            if self.tre.get_target(axis) != self.tre.get(axis):  # the size is on its way
                self.pending = True
            else:
                self.pending = False
                self.changed(not now, now)
        self._content()

    def _content(self) -> None:
        """The content of a closed Expander is not on screen and takes no Tab stop (Standard
        Modules > Keyboard Operation: a disabled or hidden widget takes no focus): it is hidden
        while the Expander is closed, shown the moment it opens and until a closing has finished.
        Done for every block the Expander holds, so a rebuild that made a new one hides it too.
        Focus that was inside when the content hid is parked on the Expander's own block, so no
        key reaches a hidden block (a text field is not typed into unseen)."""
        show = bool(self.open) or self.pending
        for child in self.tre.children():
            if child.get("visible") != show:
                if not show and _holds_focus(child):
                    self._park_focus()
                child.set(visible=show)

    def _park_focus(self) -> None:
        """tre drops focus only by giving it to another node: the Expander's block takes it (it
        is no Tab stop, so the next Tab starts again at the first stop)."""
        was = self.tre.get("focusable")
        self.tre.set(focusable=True)
        self.tre.focus()
        self.tre.set(focusable=was)

    def _ended(self, event: Any) -> None:
        if self.pending and event.property == self.axis and event.finished:
            self.pending = False
            assert self.open is not None
            self._content()
            self.changed(not self.open, self.open)

    def stop(self) -> None:
        try:
            self.tre.off("animation_end")
        except ValueError:  # the node is gone
            pass


def make(view: View, entry: Entry) -> Control | None:
    kind = kind_of(entry)
    if entry.tre is None or not kind:
        return None
    makers = {
        "toggle": Toggle,
        "select": Select,
        "multiselect": MultiSelect,
        "slide": Slide,
        "item": Item,
        "expand": Expand,
    }
    return makers[kind](view, entry)


__all__ = [
    "Control",
    "Expand",
    "Item",
    "MultiSelect",
    "Select",
    "Slide",
    "Toggle",
    "kind_of",
    "make",
]
