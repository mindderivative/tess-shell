"""``View.update``: new typed values reach named nodes through one ``Window.apply``."""

from __future__ import annotations

from typing import Any

from tess_re import Window

from tess_shell.binder.build import View, build
from tess_shell.binder.model import (
    Color,
    Length,
    Node,
    Number,
    Origin,
    SlotPart,
    SlotValue,
    Text,
)


class Spy:
    """Stands in for the window after the build and counts ``apply`` calls."""

    def __init__(self, window: Window) -> None:
        self.window = window
        self.calls: list[int] = []

    def apply(self, changes: Any) -> None:
        self.calls.append(len(changes))
        self.window.apply(changes)


def make() -> tuple[View, Spy]:
    window = Window(200, 40)
    tree = [
        Node(
            "FlexBox",
            children=(
                Node("Text", name="A", props={"Text": Text("one")}),
                Node("Text", name="B", props={"Text": Text("two")}),
                Node("Spacer", name="S"),
            ),
        )
    ]
    view = build(tree, window)
    spy = Spy(window)
    view.window = spy  # type: ignore[assignment]
    return view, spy


def test_changes_to_several_nodes_are_one_apply_call() -> None:
    view, spy = make()
    errors = view.update(
        [
            ("A", "Text", Text("uno")),
            ("B", "Text", Text("dos")),
            ("B", "Foreground", Color(1, 2, 3)),
        ]
    )
    assert errors == [] and spy.calls == [2]
    assert view.nodes["A"].get("text") == "uno" and view.nodes["B"].get("text") == "dos"
    assert view.nodes["B"].get("fill") == (1, 2, 3, 255)


def test_a_value_the_node_already_has_makes_no_call() -> None:
    view, spy = make()
    assert view.update([("A", "Text", Text("one"))]) == []
    assert spy.calls == []
    view.update([("A", "Text", Text("uno"))])
    view.update([("A", "Text", Text("uno"))])
    assert spy.calls == [1]


def test_a_bad_value_is_reported_and_the_property_keeps_its_last_value() -> None:
    view, spy = make()
    bad = Number(3, origin=Origin("f.tdl", 7, 9))
    (error,) = view.update([("A", "Text", bad)])
    assert "Text" in error.message and error.origin.line == 7
    assert view.nodes["A"].get("text") == "one" and spy.calls == []


def test_an_unevaluated_slot_is_refused() -> None:
    view, _ = make()
    slot = SlotValue((SlotPart("time"),), origin=Origin("f.tdl", 3, 3))
    (error,) = view.update([("A", "Text", slot)])
    assert "slot" in error.message


def test_an_unknown_node_or_key_is_an_error_not_an_exception() -> None:
    view, spy = make()
    errors = view.update([("Nope", "Text", Text("x")), ("S", "Bogus", Length(1))])
    assert len(errors) == 2 and spy.calls == []
