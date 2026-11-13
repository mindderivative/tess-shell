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


def kind_of(entry: Entry) -> str:
    """The control this block is: ``toggle``, ``select``, ``slide``, ``item``, ``expand`` or
    empty."""
    if _flag(entry, "Toggles"):
        return "toggle"
    if _word(entry, "Selection_Mode") == "SINGLE":
        return "select"
    if _word(entry, "Slides") in ("HORIZONTAL", "VERTICAL"):
        return "slide"
    if _flag(entry, "Menu_Item"):
        return "item"
    if _word(entry, "Reveals") in ("OPEN", "CLOSED"):
        return "expand"
    return ""


class Control:
    """Base: the block, its wire and where ``On_Changed`` goes."""

    def __init__(self, view: View, entry: Entry) -> None:
        self.view = view
        self.entry = entry
        assert entry.tre is not None
        self.tre: TreNode = entry.tre
        self.wired = False

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

    def clicked(self, event: Any) -> None:  # noqa: B027 - most controls do not take a click
        """The block's ``click`` (not blocked, not stopped by an entry's own handler)."""

    def stop(self) -> None:
        """The block is gone."""


class Toggle(Control):
    """``Toggles: true``: a click flips ``Checked`` (tre's ``checked``)."""

    def __init__(self, view: View, entry: Entry) -> None:
        super().__init__(view, entry)
        self.state = False
        self.base: bool | None = None

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


class Select(Control):
    """``Selection_Mode: SINGLE``: the block's children are the entries of a list; a click on one
    chooses it (an entry has a ``Key``, a ``For`` entry the key of the repeater)."""

    def __init__(self, view: View, entry: Entry) -> None:
        super().__init__(view, entry)
        self.chosen = ""
        self.base: str | None = None

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


class Slide(Control):
    """``Slides: HORIZONTAL | VERTICAL``: a press on the block, and a drag with the pointer
    captured, set ``value`` between ``value_min`` and ``value_max`` in steps of ``value_step``.
    The block's parts ``fill`` and ``handle`` follow it."""

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
            return
        if now == self.open:
            return
        self.open = now
        axis = self.axis
        if self.tre.get_target(axis) != self.tre.get(axis):  # the size is on its way
            self.pending = True
        else:
            self.pending = False
            self.changed(not now, now)

    def _ended(self, event: Any) -> None:
        if self.pending and event.property == self.axis and event.finished:
            self.pending = False
            assert self.open is not None
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
    makers = {"toggle": Toggle, "select": Select, "slide": Slide, "item": Item, "expand": Expand}
    return makers[kind](view, entry)


__all__ = ["Control", "Expand", "Item", "Select", "Slide", "Toggle", "kind_of", "make"]
