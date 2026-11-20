"""A block that listens for nothing gets no ``Wire`` (``binder.build._inert``): what still gets
one, and that a reload which gives a plain block a handler, a state style or a name wires it then
(Performance Budgets B18)."""

from __future__ import annotations

from typing import Any

import pytest
from tess_re import Window

from tess_shell.binder.build import View, build
from tess_shell.binder.model import (
    BindFailed,
    Bool,
    Color,
    Enum,
    Handler,
    Length,
    Node,
    Origin,
    Text,
)

CLICK = Handler("pressed")


def text(name: str | None = None, **extra: Any) -> Node:
    return Node("Text", name=name, props={"Text": Text("x")}, **extra)


def box(name: str | None = None, **extra: Any) -> Node:
    return Node("FlexBox", name=name, props={"Width": Length(20), "Height": Length(20)}, **extra)


def with_row(*children: Node) -> tuple[View, Window]:
    window = Window(200, 40)
    view = build([Node("FlexBox", name="Row", children=children)], window)
    return view, window


def wires(view: View) -> list[bool]:
    """Whether each node under the row has a wire."""
    return [e.wire is not None for e in view.entries[0].children]


def test_what_listens_for_something_gets_a_wire_and_the_rest_does_not() -> None:
    hot = {"hovered": {"Background": Color(1, 2, 3, 255)}}
    view, _ = with_row(
        text(),  # plain
        text("Named"),  # a tooltip or a slot finds it by name
        box(handlers={"On_Click": CLICK}),
        box(states=hot),
        Node("FlexBox", props={"Enabled": Bool(False)}),  # disabled: swallows the click
        Node("FlexBox", props={"Role": Enum("BUTTON")}),  # a Tab stop with keys
        Node("FlexBox", props={"Checked": Bool(True)}),
        Node("FlexBox", props={"Toggles": Bool(False)}),  # a control key, written
    )
    assert wires(view) == [False, True, True, True, True, True, True, True]


def test_a_reload_that_gives_a_plain_block_a_handler_wires_it() -> None:
    clicks: list[Any] = []
    view, window = with_row(box(), box())
    view.sink = lambda handler, key, raw: clicks.append((handler.action, key))
    first = view.entries[0].children[0].tre
    window.simulate("click", node=first)
    assert clicks == []  # nobody listens
    clickable = box(handlers={"On_Click": CLICK})
    view.rebuild([Node("FlexBox", name="Row", children=(clickable, box()))])
    assert wires(view) == [True, False]
    assert view.entries[0].children[0].tre == first  # kept, not rebuilt
    window.simulate("click", node=first)
    assert clicks == [("pressed", "On_Click")]


def test_a_reload_that_takes_the_handler_away_stops_the_handler_hearing_clicks() -> None:
    clicks: list[Any] = []
    view, window = with_row(box(handlers={"On_Click": CLICK}))
    view.sink = lambda handler, key, raw: clicks.append(key)
    node = view.entries[0].children[0].tre
    window.simulate("click", node=node)
    view.rebuild([Node("FlexBox", name="Row", children=(box(),))])
    window.simulate("click", node=node)
    assert clicks == ["On_Click"]


def test_a_tre_error_deep_in_the_tree_is_reported_at_the_key_that_caused_it() -> None:
    """The index of positions is made only when tre refuses a tree: it must still name the key."""
    deep = Node(
        "SVG",
        props={"Source": Text("not svg", origin=Origin("f.tdl", 9, 7))},
        origin=Origin("f.tdl", 8, 5),
    )
    tree = Node(
        "FlexBox",
        origin=Origin("f.tdl", 1, 1),
        children=(
            Node("Spacer", origin=Origin("f.tdl", 2, 5)),
            Node("FlexBox", origin=Origin("f.tdl", 3, 5), children=(Node("Spacer"), deep)),
        ),
    )
    window = Window(50, 50)
    with pytest.raises(BindFailed) as info:
        build([tree], window)
    (error,) = info.value.errors
    assert (error.origin.line, error.origin.column) == (9, 7)
    assert window.root.children() == []
