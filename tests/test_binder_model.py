import pytest

from tess_shell.binder.model import (
    NO_ORIGIN,
    Auto,
    BindError,
    BindFailed,
    Color,
    Length,
    Node,
    Origin,
    Text,
)


def test_origin_never_takes_part_in_equality() -> None:
    a = Length(12, origin=Origin("a.tdl", 3, 5))
    b = Length(12, origin=Origin("b.tdl", 9, 1))
    assert a == b
    assert Length(12) != Length(13)
    assert Length(12) != Auto()


def test_a_tree_from_a_file_equals_the_same_tree_built_in_code() -> None:
    def tree(origin: Origin) -> Node:
        return Node(
            "FlexBox",
            name="Row",
            props={"Width": Length(100, origin=origin)},
            style={"Background": Color(1, 2, 3, origin=origin)},
            children=(Node("Text", props={"Text": Text("x", origin=origin)}, origin=origin),),
            origin=origin,
        )

    assert tree(Origin("f.tdl", 4, 2)) == tree(NO_ORIGIN)


def test_nodes_are_immutable() -> None:
    node = Node("Spacer")
    with pytest.raises(AttributeError):
        node.kind = "Box"


def test_bind_error_names_its_position_and_bind_failed_lists_every_error() -> None:
    first = BindError("bad", Origin("m.tdl", 7, 9), hint="fix it")
    second = BindError("worse", Origin("m.tdl", 8, 1))
    assert str(first) == "m.tdl:7:9: bad"
    failed = BindFailed([first, second])
    assert failed.errors == [first, second]
    assert "worse" in str(failed)
