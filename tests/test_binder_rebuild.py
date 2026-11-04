"""``View.rebuild``: the keyed diff keeps what is the same and changes only what differs."""

from __future__ import annotations

from typing import Any

import pytest
from tess_re import Window

from tess_shell.binder.build import View, build
from tess_shell.binder.model import (
    BindFailed,
    Color,
    Length,
    Node,
    Number,
    Origin,
    Text,
)


class Spy:
    def __init__(self, window: Window) -> None:
        self.window = window
        self.applies: list[int] = []
        self.builds = 0

    @property
    def root(self) -> Any:
        return self.window.root

    def apply(self, changes: Any) -> None:
        self.applies.append(len(changes))
        self.window.apply(changes)

    def build(self, spec: Any) -> Any:
        self.builds += 1
        return self.window.build(spec)


def text(value: str, name: str | None = None, **style: Any) -> Node:
    return Node("Text", name=name, props={"Text": Text(value)}, style=style)


def row(*children: Node, name: str | None = "Row") -> Node:
    return Node("FlexBox", name=name, children=children)


def make(*children: Node) -> tuple[View, Spy]:
    window = Window(300, 40)
    view = build([row(*children)], window)
    spy = Spy(window)
    view.window = spy  # type: ignore[assignment]
    return view, spy


def kids(view: View) -> list[Any]:
    return view.nodes["Row"].children()


def test_the_same_tree_changes_nothing() -> None:
    view, spy = make(text("a", "A"), text("b", "B"))
    before = list(kids(view))
    view.rebuild([row(text("a", "A"), text("b", "B"))])
    assert spy.applies == [] and spy.builds == 0
    assert kids(view) == before


def test_a_changed_property_is_one_apply_and_the_node_is_kept() -> None:
    view, spy = make(text("a", "A"), text("b", "B"))
    a, b = kids(view)
    view.rebuild([row(text("a2", "A"), text("b", "B"))])
    assert spy.applies == [1] and spy.builds == 0
    assert kids(view) == [a, b] and a.get("text") == "a2"


def test_several_changes_across_the_tree_are_still_one_apply() -> None:
    view, spy = make(text("a", "A"), text("b", "B"))
    view.rebuild(
        [
            Node(
                "FlexBox",
                name="Row",
                props={"Spacing": Number(6)},
                children=(text("a2", "A"), text("b2", "B", Foreground=Color(1, 2, 3))),
            )
        ]
    )
    assert spy.applies == [3]  # the row's gap, and the two texts


def test_a_child_added_removed_and_moved_keeps_the_others() -> None:
    view, spy = make(text("a", "A"), text("b", "B"), text("c", "C"))
    a, b, c = kids(view)
    view.rebuild([row(text("c", "C"), text("new", "N"), text("a", "A"))])
    out = kids(view)
    assert out[0] == c and out[2] == a  # kept, in the new order
    assert out[1].get("text") == "new" and spy.builds == 1
    with pytest.raises(ValueError):
        b.get("text")  # removed nodes are freed
    assert set(view.nodes) == {"Row", "C", "N", "A"}


def test_a_changed_block_word_under_one_name_is_a_replacement() -> None:
    view, _ = make(text("a", "A"))
    (old,) = kids(view)
    view.rebuild([row(Node("Spacer", name="A"))])
    (new,) = kids(view)
    assert new != old and view.kinds["A"] == "Spacer"
    with pytest.raises(ValueError):
        old.get("text")


def test_a_property_the_new_tree_no_longer_sets_makes_a_replacement() -> None:
    view, _ = make(text("a", "A", Foreground=Color(1, 2, 3)))
    (old,) = kids(view)
    view.rebuild([row(text("a", "A"))])
    (new,) = kids(view)
    assert new != old and new.get("fill") != (1, 2, 3, 255)


def test_unnamed_siblings_are_matched_by_block_word_and_position() -> None:
    view, spy = make(text("one"), Node("Spacer"), text("two"))
    one, spacer, two = kids(view)
    view.rebuild([row(text("one"), Node("Spacer"), text("two!"))])
    assert kids(view) == [one, spacer, two] and spy.applies == [1]
    assert two.get("text") == "two!"
    # dropping the first Text makes the second one the first: it is matched to it
    view.rebuild([row(text("two!"), Node("Spacer"))])
    out = kids(view)
    assert out[0] == one and one.get("text") == "two!" and len(out) == 2


def test_a_bad_value_leaves_the_old_tree_whole_and_names_the_key() -> None:
    view, spy = make(text("a", "A"), text("b", "B"))
    before = list(kids(view))
    bad = Node(
        "Text", name="B", props={"Text": Text("x"), "Width": Text("wide", origin=Origin("f", 7, 9))}
    )
    with pytest.raises(BindFailed) as info:
        view.rebuild([row(text("changed", "A"), bad)])
    assert info.value.errors[0].origin.line == 7
    assert kids(view) == before and view.nodes["A"].get("text") == "a"
    assert spy.applies == [] and spy.builds == 0


def test_updates_still_work_after_a_rebuild() -> None:
    view, spy = make(text("a", "A"))
    view.rebuild([row(text("a", "A"), text("b", "B"))])
    assert view.update([("B", "Text", Text("b2")), ("A", "Text", Text("a2"))]) == []
    assert view.nodes["B"].get("text") == "b2" and view.nodes["A"].get("text") == "a2"
    assert spy.applies[-1] == 2


def test_a_new_subtree_is_built_whole_with_its_ids() -> None:
    view, spy = make(text("a", "A"))
    view.rebuild([row(text("a", "A"), Node("Box", name="Box", children=(text("in", "Inner"),)))])
    assert spy.builds == 1 and "Inner" in view.nodes
    assert view.nodes["Inner"].parent() == view.nodes["Box"]
    view.rebuild([row(text("a", "A"), Node("Box", name="Box", children=(text("in2", "Inner"),)))])
    assert view.nodes["Inner"].get("text") == "in2" and spy.builds == 1


def test_the_top_level_may_change_too() -> None:
    window = Window(100, 40)
    view = build([text("a", "A")], window)
    first = view.nodes["A"]
    view.rebuild([text("a", "A"), Node("Spacer", name="S")])
    assert view.nodes["A"] == first and len(window.root.children()) == 2
    view.rebuild([Node("Spacer", name="S")])
    assert len(window.root.children()) == 1 and "A" not in view.nodes


def test_a_length_property_diff_compares_converted_values() -> None:
    view, spy = make(Node("Spacer", name="S", props={"Width": Length(5)}))
    view.rebuild([row(Node("Spacer", name="S", props={"Width": Length(5)}))])
    assert spy.applies == []
    view.rebuild([row(Node("Spacer", name="S", props={"Width": Length(6)}))])
    assert spy.applies == [1] and view.nodes["S"].get("width") == 6
