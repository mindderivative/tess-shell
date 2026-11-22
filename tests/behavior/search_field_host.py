"""tess-shell as a host of the behavior standard's ``search_field``: the Launcher's query field
(the ``TextInput`` of the Applications module in the Launcher Panel), driven through the desk of
``tests/launcher_rig.py`` and read back from its nodes.

What the shell has: an input (a text box) whose text is the value, Escape that clears it (and, with
the field already empty, hides the Panel). What it does not: a clear button, a controlled value, a
``disabled`` option, and any report of a change with its reason and detail: the adapter emits none
of those events, only the ``focus_move`` it can see."""

from __future__ import annotations

import tempfile
from contextlib import ExitStack
from pathlib import Path
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

from tests.launcher_rig import Desk, launcher_desk

#: What a corpus option is, in the Launcher: the placeholder is its name; the rest is not there.
DEFAULTS = {"clear_label": "Clear", "clear_on_escape": True}
KEYS = {"escape": "escape", "enter": "enter", "space": "space"}


class SearchFieldHost:
    """The Launcher's query field as a host of ``search_field``."""

    def __init__(
        self, spec: Spec, options: dict[str, Any] | None, controlled: bool, responses: list[str]
    ) -> None:
        given = {"value": "", "disabled": False, **DEFAULTS, **(options or {})}
        if controlled:
            raise NotRun("the Launcher's query is not a controlled value")
        if given["disabled"]:
            raise NotRun("the Launcher's field has no disabled option")
        for name, default in DEFAULTS.items():
            if given[name] != default:
                raise NotRun(f"the option {name} does not exist in the Launcher")
        self._stack = ExitStack()
        folder = Path(self._stack.enter_context(tempfile.TemporaryDirectory(prefix="bh-")))
        self.desk: Desk = self._stack.enter_context(launcher_desk(folder, {"Firefox": {}}))
        self.desk.toggle()
        self._focused = False
        if given["value"]:
            self.desk.type(str(given["value"]))

    def close(self) -> None:
        self._stack.close()

    # -- observing ------------------------------------------------------------------------------

    @property
    def _field(self) -> Any:
        return self.desk.field()

    @property
    def state(self) -> dict[str, Any]:
        return {"value": str(self._field.get("text"))}

    @property
    def focus(self) -> str | None:
        return "input" if self._field.get("focused") else None

    def present(self, name: str) -> bool:
        return name == "input"  # there is no clear button

    def tree(self) -> list[dict[str, Any]]:
        field = self._field
        return [
            {
                "role": field.get("role"),
                "name": field.get("label"),
                "props": {"value": str(field.get("text")), "disabled": False},
                "children": [],
            }
        ]

    # -- input ----------------------------------------------------------------------------------

    def dispatch(self, event: Input) -> Outcome:
        before, value = self.focus, self.state["value"]
        consumed = False
        match event:
            case TextInput(part, text):
                self._need_input(part)
                # the standard's `text` is the field's new text: select what is there, then type
                self.desk.press("a", ctrl=True)
                self.desk.type(text)
                consumed = True  # the text box took it
            case KeyInput(part, key, _):
                self._need_input(part)
                was_hidden = self.desk.hidden
                self.desk.press(KEYS.get(key.lower(), key.lower()))
                # a key the module used is stopped (Escape that cleared the field): the Panel's own
                # Escape did not also hide it. A key that changed nothing is not consumed
                consumed = self.state["value"] != value and self.desk.hidden == was_hidden
            case FocusInput(part, _):
                if part == "input":
                    self._field.focus()
                    self.desk.press("shift")
                elif part is None:
                    self.desk.press("tab")
                else:
                    raise NotRun(f"the part {part!r} does not exist in the Launcher")
            case PressInput(part, _):
                raise NotRun(f"the part {part!r} does not exist in the Launcher (no clear button)")
            case SetOptionInput():
                raise NotRun("an option cannot be changed on the Launcher's field")
            case PointerInput() | ScrollInput() | WindowInput() | AdvanceInput():
                raise NotRun("not driven on the Launcher's field")
        events: list[Event] = []
        if self.focus != before:
            reason = event.via if isinstance(event, FocusInput) else "keyboard"
            events.append(Event("focus_move", {"from": before, "to": self.focus, "reason": reason}))
        return Outcome(events, consumed=consumed)

    @staticmethod
    def _need_input(part: str) -> None:
        if part != "input":
            raise NotRun(f"the part {part!r} does not exist in the Launcher")
