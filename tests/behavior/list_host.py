"""tess-shell as a host of the behavior standard's ``list`` (the Selection behavior): the shell's
``List`` module on the headless Bar of ``tests/widgets_live.py``, driven through ``window.simulate``
and read back from its nodes.

What the shell has: ``Selection: MULTIPLE`` is the engine's own container selection (TSH-082), so
the set, the anchor, the Shift and Ctrl rules, Ctrl+A and the skipped disabled entry are the
engine's. ``Selection: SINGLE`` is the shell's own chooser (arrows choose, Space chooses). What it
does not: an ``unselectable`` row, ``select_on_focus``, a ``select_all_key`` option, a report of
a change with its count, anchor, reason and detail (``On_Changed`` says the keys), a role
``listbox``/``option`` (``list``/``listitem``), names on the rows, and an announcement readable
headless (the engine's ``selection_announce`` is read from a real AT-SPI bus in
``tests/test_multiselect_atspi.py``). The adapter emits only the ``focus_move`` it can see;
``consumed`` is inferred: the set, the anchor or the focus changed."""

from __future__ import annotations

from contextlib import ExitStack
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
    SetOptionInput,
    Spec,
)

from tests.widgets_live import Widgets, running

#: The standard's key names -> the engine's.
KEYS = {
    "arrowdown": "arrow_down",
    "arrowup": "arrow_up",
    "space": "space",
    "escape": "escape",
    "enter": "enter",
    "home": "home",
    "end": "end",
}
MODIFIERS = ("ctrl", "shift")
DRIVER = (
    "from tess_shell import Module\n"
    "class Driver(Module):\n"
    "    def start(self):\n"
    "        self.ctx.send('pick', INITIAL)\n"
)
LAYOUT = (
    "Module {{ FlexBox {{ Children {{ List {{ Name: L, Label: Items, Selection: {mode}, "
    "Height: 400, Selected: <| pick |>, Children {{ {entries} }} }} }} }} }}"
)


def _held(modifiers: tuple[str, ...]) -> dict[str, bool]:
    return {m: True for m in modifiers if m in MODIFIERS}


class ListHost:
    """A ``List`` in a headless shell, as a host of ``list``."""

    def __init__(
        self, spec: Spec, options: dict[str, Any] | None, controlled: bool, responses: list[str]
    ) -> None:
        given = {
            "items": [],
            "selection": [],
            "selection_mode": "multiple",
            "select_all_key": True,
            "select_on_focus": False,
            **(options or {}),
        }
        if controlled:
            raise NotRun("the List's selection is not controlled by the host")
        if any(entry.get("unselectable") for entry in given["items"]):
            raise NotRun("a List entry has no unselectable state (only disabled, or no Key)")
        if given["select_on_focus"]:
            raise NotRun("a List never selects on focus")
        if given["select_all_key"] is not True:
            raise NotRun("a List always has Ctrl+A")
        self.single = given["selection_mode"] == "single"
        self.ids: list[str] = [entry["id"] for entry in given["items"]]
        entries = " ".join(
            f'FlexBox {{ Class: list_item, Key: "{e["id"]}", Label: "{e["label"]}", Height: 30, '
            f"{'Enabled: false, ' if e.get('disabled') else ''}"
            f'Children {{ Text {{ Text: "{e["label"]}", Width: AUTO, Height: AUTO }} }} }}'
            for e in given["items"]
        )
        layout = LAYOUT.format(mode="SINGLE" if self.single else "MULTIPLE", entries=entries)
        initial = ",".join(given["selection"])
        self._stack = ExitStack()
        self.w: Widgets = self._stack.enter_context(
            running("Driver { }", driver=layout, driver_py=DRIVER.replace("INITIAL", repr(initial)))
        )
        self.w.advance(16)
        self.root = self._root()
        self.rows = [n for k, n in self.w.view.nodes.items() if k.endswith("/Items")][0].children()
        self._focused = self.focus

    def close(self) -> None:
        self._stack.close()

    def _root(self) -> Any:
        return next(
            n for k, n in self.w.view.nodes.items() if k.startswith("List@") and k.endswith("/Root")
        )

    # -- observing ------------------------------------------------------------------------------

    def _row(self, item: Any) -> Any:
        if item not in self.ids:
            raise NotRun(f"no row {item!r}")
        return self.rows[self.ids.index(item)]

    def _chosen(self) -> list[str]:
        return [i for i, row in zip(self.ids, self.rows, strict=True) if row.get("selected")]

    def _anchor(self) -> str | None:
        if self.single:
            return None  # the shell's single chooser keeps no anchor
        held = self.root.get("selection_anchor")
        if held is None:
            return None
        return next((i for i, row in zip(self.ids, self.rows, strict=True) if row == held), None)

    @property
    def state(self) -> dict[str, Any]:
        return {"selection": self._chosen(), "anchor": self._anchor()}

    @property
    def focus(self) -> str | None:
        return next(
            (f"option#{i}" for i, r in zip(self.ids, self.rows, strict=True) if r.get("focused")),
            None,
        )

    def present(self, name: str) -> bool:
        part, _, ident = name.partition("#")
        return part == "listbox" or (part == "option" and ident in self.ids)

    def tree(self) -> list[dict[str, Any]]:
        chosen = self._chosen()
        options = [
            {
                "role": row.get("role"),
                "name": row.get("label") or "",
                "props": {"selected": i in chosen, "disabled": bool(row.get("disabled"))},
                "children": [],
            }
            for i, row in zip(self.ids, self.rows, strict=True)
        ]
        return [
            {
                "role": self.root.get("role"),
                "name": self.root.get("label") or "",
                "props": {"multiselectable": not self.single},
                "children": options,
            }
        ]

    # -- driving --------------------------------------------------------------------------------

    def dispatch(self, event: Input) -> Outcome:
        window = self.w.window
        before = (self._chosen(), self._anchor(), self.focus)
        reason = "keyboard"
        match event:
            case PressInput(_, via, item, modifiers):
                reason = via
                if via != "pointer":
                    raise NotRun("a keyboard press on a row is a key: the case sends it")
                if item is None:
                    window.simulate("click", node=self.root, x=10.0, y=300.0, **_held(modifiers))
                else:
                    window.simulate("click", node=self._row(item), **_held(modifiers))
            case PointerInput(_, kind, item, modifiers):
                reason = "pointer"
                if item is None or kind not in ("down", "up"):
                    raise NotRun("only a pointer press or release on a row can be driven")
                window.simulate(f"pointer_{kind}", node=self._row(item), **_held(modifiers))
            case KeyInput(_, key, modifiers, _):
                if key.lower() not in KEYS and len(key) != 1:
                    raise NotRun(f"no engine key for {key!r}")
                window.simulate(
                    "key_down", key=KEYS.get(key.lower(), key.lower()), **_held(modifiers)
                )
            case FocusInput(_, via, item):
                reason = via
                if item is None:
                    raise NotRun("focus on the list itself")
                if via == "pointer":
                    raise NotRun("a pointer focus without a press cannot be driven")
                self._row(item).focus()
            case AdvanceInput(ms):
                window.advance(ms)
                raise NotRun("the announcement cannot be read back from a headless window")
            case SetOptionInput(option, value):
                if option != "selection":
                    raise NotRun(f"there is no option {option!r} to change")
                reason = "api"
                self.w.send("pick", ",".join(i for i in self.ids if i in value))
            case _:
                raise NotRun("an input this widget does not take")
        for _ in range(3):
            window.advance(16)
        events: list[Event] = []
        now = self.focus
        if now != before[2] and now is not None:
            events.append(Event("focus_move", {"from": before[2], "to": now, "reason": reason}))
        consumed = (self._chosen(), self._anchor(), now) != before
        return Outcome(events, consumed=consumed)
