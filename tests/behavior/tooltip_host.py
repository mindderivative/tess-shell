"""tess-shell as a host of the behavior standard's ``tooltip``: a module whose root is a button with
a ``Tooltip: "Save the file"``, in the surface manager's headless Bar (``tests/test_popup.py``'s
rig), driven through ``window.simulate`` and ``window.advance`` (the fake clock: the shell's delays
are tre window timers) and read back from the shell's own nodes and popup manager.

What the shell reports is read, not invented: the open state is whether a tooltip popup is open; the
tree is the nodes' role, label and description; ``TooltipManager.tooltip_log`` says each open and
close with its why. What the shell does NOT have is a cancelable change request (``before_change``):
the adapter never emits one, so a case that expects it fails, and ``KNOWN_GAPS`` says so."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from tess_behavior import (
    AdvanceInput,
    Event,
    FocusInput,
    Input,
    KeyInput,
    NotRun,
    Outcome,
    PointerInput,
    PressInput,
    ScrollInput,
    SetOptionInput,
    Spec,
    TextInput,
    WindowInput,
)

from tests.test_popup import Rig, rig

BTN = (
    "Module { FlexBox { Name: Root, Role: BUTTON, Label: Save, Focusable: true, Width: 60, "
    'Height: 20, Tooltip: "Save the file" } }'
)
#: The tooltip's delay and grace are the shell's own (500 and 150 ms): other values cannot run.
DEFAULTS = {"label": "Save", "text": "Save the file", "open_delay": 500, "grace": 150}
#: The reason of a change by its why: a timer's change has the reason of the input that armed it.
API = {"a scroll", "window"}


class TooltipHost:
    """A button with a tooltip on the shell's headless Bar, as a host of ``tooltip``."""

    def __init__(
        self, spec: Spec, options: dict[str, Any] | None, controlled: bool, responses: list[str]
    ) -> None:
        given = {**DEFAULTS, **(options or {})}
        if controlled:
            raise NotRun("a tooltip has no controlled value")
        for name, default in DEFAULTS.items():
            if given[name] != default:
                raise NotRun(f"the shell's tooltip {name} is fixed ({default!r})")
        self._rig: Iterator[Rig] = rig("", btn=BTN)
        self.r = next(self._rig)
        self.window = self.r.bar.window
        self.window.advance(16)
        self._seen = len(self.r.popups.tooltip_log)
        self._armed_by = "pointer"

    def close(self) -> None:
        self._rig.close()

    # -- observing ------------------------------------------------------------------------------

    @property
    def _node(self) -> Any:
        return self.r.root_of()

    @property
    def state(self) -> dict[str, Any]:
        cur = self.r.popups.current
        return {"open": cur is not None and cur.block is not None and not cur.closing}

    @property
    def focus(self) -> str | None:
        return "trigger" if self._node.get("focused") else None

    def present(self, name: str) -> bool:
        return name == "trigger" or (name == "tip" and bool(self.state["open"]))

    def tree(self) -> list[dict[str, Any]]:
        node = self._node
        nodes = [
            {
                "role": node.get("role"),
                "name": node.get("label"),
                "props": {"description": node.get("description")},
                "children": [],
            }
        ]
        cur = self.r.popups.current
        if self.state["open"] and cur is not None:
            root = cur.window.root
            nodes.append(
                {
                    "role": "tooltip",
                    "name": next(
                        (n.get("text") for n in _walk(root) if n.get("kind") == "text"), None
                    ),
                    "props": {"hidden": bool(root.get("a11y_hidden"))},
                    "children": [],
                }
            )
        return nodes

    # -- input ----------------------------------------------------------------------------------

    def dispatch(self, event: Input) -> Outcome:
        before = self.focus
        w = self.window
        match event:
            case PointerInput(part, kind):
                if part != "trigger":
                    raise NotRun(f"the part {part!r} cannot be pointed at")
                self._armed_by = "pointer"
                if kind == "enter":
                    w.simulate("pointer_enter", node=self._node)
                elif kind == "leave":
                    w.simulate("pointer_leave", node=self._node)
                elif kind == "down":
                    w.simulate("pointer_down", node=self._node)
                else:
                    raise NotRun(f"pointer {kind} is not driven")
            case FocusInput(part, via):
                if part == "trigger" and via == "keyboard":
                    self._armed_by = "keyboard"
                    w.simulate(
                        "key_down", key="shift"
                    )  # the keyboard was the last input: focus shows
                    self._node.focus()
                elif part is None and self.focus == "trigger":
                    self._armed_by = "keyboard"
                    w.simulate("key_down", key="tab")
                else:
                    raise NotRun("a focus by pointer without a press cannot be driven")
            case KeyInput(_, key):
                self._armed_by = "keyboard"
                w.simulate("key_down", key=key.lower())
            case ScrollInput():
                w.simulate("wheel", node=self._node, delta_x=0.0, delta_y=40.0)
            case WindowInput(kind):
                if kind != "focus_lost":
                    raise NotRun(f"window {kind} is not driven")
                w.simulate("active", active=True)
                w.simulate("active", active=False)
            case AdvanceInput(ms):
                w.advance(ms)
            case TextInput() | PressInput() | SetOptionInput():
                raise NotRun("not an input of a tooltip")
        w.advance(0)
        events: list[Event] = []
        log = self.r.popups.tooltip_log
        for opened, why in list(log)[self._seen :]:
            events.append(Event("change", self._fields(opened, why)))
        self._seen = len(log)
        if self.focus != before:
            moved = Event(
                "focus_move", {"from": before, "to": self.focus, "reason": self._armed_by}
            )
            events = [moved, *events] if isinstance(event, FocusInput) else [*events, moved]
        return Outcome(events, consumed=False)

    def _fields(self, opened: bool, why: str) -> dict[str, Any]:
        reason = "api" if why in API else self._armed_by
        return {
            "reason": reason,
            "detail": _DETAIL.get(why, why),
            "previous": not opened,
            "value": opened,
        }


#: The shell's close reasons in the standard's words.
_DETAIL = {
    "hover": "hover",
    "focus": "focus",
    "the pointer left": "grace",
    "escape": "escape",
    "a press": "press",
    "a scroll": "scroll",
}


def _walk(node: Any) -> Iterator[Any]:
    yield node
    for child in node.children():
        yield from _walk(child)
