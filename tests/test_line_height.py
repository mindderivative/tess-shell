"""``Line_Height`` is a height in pixels (Style Schema); tre's ``line_height`` is a multiple of the
font size, so the binder divides."""

from __future__ import annotations

import pytest
from tess_re import Window

from tess_shell.binder import model as m
from tess_shell.binder.build import build, convert_states

DEFAULT = 16.0  # the size tre sets text in when none is given


def text(style: dict[str, m.Value], states: dict[str, dict[str, m.Value]] | None = None) -> m.Node:
    return m.Node("Text", name="T", props={"Text": m.Text("x")}, style=style, states=states or {})


def view(node: m.Node):  # type: ignore[no-untyped-def]
    return build([node], Window(width=100, height=100))


def test_a_line_height_in_pixels_is_a_multiple_of_the_font_size() -> None:
    v = view(text({"Font_Size": m.Number(14), "Line_Height": m.Number(21)}))
    assert v.nodes["T"].get("line_height") == pytest.approx(1.5)


def test_with_no_font_size_it_is_a_multiple_of_tres_own() -> None:
    v = view(text({"Line_Height": m.Number(24)}))
    assert v.nodes["T"].get("line_height") == pytest.approx(24 / DEFAULT)


def test_a_state_that_sets_only_the_line_height_uses_the_blocks_font_size() -> None:
    node = text({"Font_Size": m.Number(10)}, {"hovered": {"Line_Height": m.Number(15)}})
    assert convert_states(node, [])["hovered"]["line_height"] == pytest.approx(1.5)


def test_a_slot_that_changes_the_line_height_or_the_font_size_keeps_the_pixels() -> None:
    v = view(text({"Font_Size": m.Number(14), "Line_Height": m.Number(21)}))
    assert v.update([("T", "Line_Height", m.Number(28))]) == []
    assert v.nodes["T"].get("line_height") == pytest.approx(2.0)
    assert v.update([("T", "Font_Size", m.Number(28))]) == []
    assert v.nodes["T"].get("line_height") == pytest.approx(1.0)  # still 28 px


def test_a_line_height_of_the_stylesheets_body_type_is_one_line_high() -> None:
    v = view(text({"Font_Size": m.Number(14), "Line_Height": m.Number(20)}))
    assert v.nodes["T"].get("line_height") * 14 == pytest.approx(20)
