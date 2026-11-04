"""``binder.build`` on a headless ``tess_re`` window: the M1 example, read back from the nodes."""

from __future__ import annotations

import pytest
from tess_re import Window

from tess_shell.binder.build import View, build
from tess_shell.binder.model import (
    Auto,
    BindFailed,
    Color,
    Enum,
    Expand,
    ForNode,
    IfNode,
    Length,
    Node,
    Number,
    Origin,
    Text,
)


def at(line: int, column: int = 5) -> Origin:
    return Origin("Shells/Main_Shell.tdl", line, column)


def example() -> Node:
    """The Bar's contents in the M1 Brief: a FlexBox of a Text, a Spacer and a Rectangle."""
    return Node(
        "FlexBox",
        name="Row",
        props={
            "Width": Expand(),
            "Flex": Enum("HORIZONTAL"),
            "Spacing": Number(8),
            "Padding": Length(4),
        },
        children=(
            Node(
                "Text",
                name="Clock",
                props={"Text": Text("14:05")},
                style={"Font_Size": Number(14), "Foreground": Color(255, 255, 255)},
            ),
            Node("Spacer"),
            Node(
                "Rectangle",
                props={
                    "Width": Length(12),
                    "Height": Length(12),
                    "Fill": Color(0x89, 0xB4, 0xFA),
                    "Corner_Radius": Length(6),
                },
            ),
        ),
    )


def test_the_example_reads_back_from_the_nodes() -> None:
    window = Window(200, 40)
    view = build([example()], window)
    (row,) = view.roots
    assert row.get("flex_direction") == "horizontal"
    assert row.get("gap") == 8
    clock = view.nodes["Clock"]
    assert clock.get("text") == "14:05"
    assert clock.get("font_size") == 14
    assert clock.get("fill") == (255, 255, 255, 255)
    text, spacer, rect = row.children()
    assert spacer.get("flex_grow") == 1
    assert (rect.get("width"), rect.get("height"), rect.get("corner_radius")) == (12, 12, 6)
    assert rect.get("fill") == (0x89, 0xB4, 0xFA, 255)
    assert text == clock and window.root.children() == [row]


def test_the_example_draws_the_circle_where_the_spacer_pushes_it() -> None:
    window = Window(200, 40, decorations=False)
    window.root.set(fill=(0, 0, 0, 255), padding=0)
    build([example()], window)
    rgba, width, height = window.snapshot()
    blue = [i // 4 % width for i in range(0, len(rgba), 4) if rgba[i + 2] > 200 and rgba[i] < 200]
    assert blue, "the rectangle was not drawn"
    assert min(blue) > width // 2  # at the right end of the row, after the spacer


def test_a_wrong_value_gives_the_position_of_its_key_and_builds_nothing() -> None:
    window = Window(200, 40)
    bad = Node(
        "Text",
        props={"Text": Text("x"), "Width": Text("wide", origin=at(7))},
        style={"Font_Size": Number(-1, origin=at(9, 13))},
        origin=at(5, 1),
    )
    with pytest.raises(BindFailed) as info:
        build([bad], window)
    errors = info.value.errors
    assert [(e.origin.line, e.origin.column) for e in errors] == [(7, 5), (9, 13)]
    assert "Width" in errors[0].message
    assert window.root.children() == []


def test_every_error_is_reported_not_only_the_first() -> None:
    window = Window(200, 40)
    nodes = [
        Node("Text", props={"Bogus": Number(1, origin=at(3))}, origin=at(2)),
        Node("Gadget", origin=at(10)),
        Node("Box", children=(IfNode(origin=at(13)),), origin=at(12)),
        Node("SVG", origin=at(20)),
    ]
    with pytest.raises(BindFailed) as info:
        build(nodes, window)
    assert [e.origin.line for e in info.value.errors] == [3, 10, 13, 20]


def test_unknown_key_and_block_suggest_the_nearest_name() -> None:
    window = Window(200, 40)
    with pytest.raises(BindFailed) as info:
        build(
            [Node("FlexBox", props={"Justify_Contnt": Enum("START", origin=at(3))}, origin=at(1))],
            window,
        )
    assert "Justify_Content" in info.value.errors[0].hint
    with pytest.raises(BindFailed) as info:
        build([Node("Flexbox", origin=at(1))], window)
    assert "FlexBox" in info.value.errors[0].hint


@pytest.mark.parametrize("repeater", [IfNode(origin=at(4)), ForNode(origin=at(4))])
def test_if_and_for_are_refused_with_a_clear_message(repeater: IfNode | ForNode) -> None:
    with pytest.raises(BindFailed) as info:
        build([Node("Box", children=(repeater,))], Window(50, 50))
    (error,) = info.value.errors
    assert "not supported yet" in error.message and error.origin.line == 4


def test_a_key_written_in_the_block_and_in_its_style_is_an_error_naming_both() -> None:
    node = Node(
        "Box",
        props={"Padding": Length(1, origin=at(3))},
        style={"Padding": Length(9, origin=at(6, 9))},
    )
    with pytest.raises(BindFailed) as info:
        build([node], Window(50, 50))
    (error,) = info.value.errors
    assert (error.origin.line, error.origin.column) == (6, 9)
    assert "Main_Shell.tdl:3:5" in error.hint


def test_a_box_puts_every_child_in_the_same_cell() -> None:
    node = Node("Box", children=(Node("Spacer"), Node("Spacer")))
    view = build([node], Window(50, 50))
    (root,) = view.roots
    assert [(c.get("grid_column"), c.get("grid_row")) for c in root.children()] == [("1", "1")] * 2


def test_expand_and_auto_sizes() -> None:
    node = Node("Box", props={"Width": Expand(), "Height": Auto()})
    (root,) = build([node], Window(50, 50)).roots
    assert (root.get("flex_grow"), root.get("align_self"), root.get("height")) == (
        1,
        "stretch",
        "auto",
    )


def test_tre_errors_are_translated_to_the_key_position() -> None:
    # Two siblings with one Name: tre refuses the second id; the position is that node's.
    window = Window(50, 50)
    node = Node(
        "Box",
        children=(
            Node("Spacer", name="A", origin=at(3)),
            Node("Spacer", name="A", origin=at(4)),
        ),
        origin=at(1),
    )
    with pytest.raises(BindFailed) as info:
        build([node], window)
    (error,) = info.value.errors
    assert error.origin.line == 4 and "used twice" in error.message
    assert window.root.children() == []


def test_names_must_be_unique_across_top_level_nodes() -> None:
    with pytest.raises(BindFailed) as info:
        build(
            [Node("Spacer", name="A", origin=at(1)), Node("Spacer", name="A", origin=at(2))],
            Window(50, 50),
        )
    assert info.value.errors[0].origin.line == 2


def test_svg_needs_a_source_and_rejects_a_malformed_document_at_its_key() -> None:
    window = Window(50, 50)
    with pytest.raises(BindFailed) as info:
        build([Node("SVG", props={"Source": Text("not svg", origin=at(6))}, origin=at(5))], window)
    (error,) = info.value.errors
    assert error.origin.line == 6 and "valid SVG" in error.message


def test_dispose_removes_and_frees_the_subtree_and_is_idempotent() -> None:
    window = Window(100, 40)
    view: View = build([example()], window)
    (row,) = view.roots
    view.dispose()
    assert window.root.children() == []
    with pytest.raises(ValueError):
        row.get("gap")
    view.dispose()
    assert view.nodes == {}
