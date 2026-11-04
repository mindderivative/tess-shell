from typing import Any

import pytest

from tess_shell.binder import convert
from tess_shell.binder.model import (
    Auto,
    BindError,
    Bool,
    Color,
    Enum,
    Expand,
    Length,
    Number,
    Origin,
    Percent,
    Seq,
    Sides,
    Text,
    Value,
)

AT = Origin("x.tdl", 4, 7)
FOUR = ("padding_top", "padding_right", "padding_bottom", "padding_left")

GOOD: list[tuple[str, Value, tuple[str, ...], tuple[str, ...], dict[str, Any]]] = [
    ("length", Length(16), ("width",), (), {"width": 16}),
    ("length", Length(2.5), ("width",), (), {"width": 2.5}),
    ("length", Percent(50), ("height",), (), {"height": "50%"}),
    ("length", Auto(), ("width",), (), {"width": "auto"}),
    ("length", Expand(), ("width",), (), {"flex_grow": 1, "align_self": "stretch"}),
    ("text_length", Auto(), ("width",), (), {"width": "fit-content"}),
    ("text_length", Length(9), ("width",), (), {"width": 9}),
    ("bound", Length(5), ("min_width",), (), {"min_width": 5}),
    ("bound", Percent(10), ("max_height",), (), {"max_height": "10%"}),
    ("number", Number(0.5), ("opacity",), (), {"opacity": 0.5}),
    ("number", Length(8), ("gap",), (), {"gap": 8}),
    ("whole", Number(3), ("z_index",), (), {"z_index": 3}),
    ("positive", Number(14), ("font_size",), (), {"font_size": 14}),
    ("bool", Bool(False), ("visible",), (), {"visible": False}),
    ("text", Text("14:05"), ("text",), (), {"text": "14:05"}),
    ("color", Color(31, 31, 31), ("fill",), (), {"fill": (31, 31, 31, 255)}),
    ("color", Color(1, 2, 3, 4), ("fill",), (), {"fill": (1, 2, 3, 4)}),
    (
        "enum",
        Enum("SPACE_BETWEEN"),
        ("justify_content",),
        ("SPACE_BETWEEN",),
        {"justify_content": "space_between"},
    ),
    ("wrap_flag", Bool(True), ("flex_wrap",), (), {"flex_wrap": "wrap"}),
    ("wrap_flag", Bool(False), ("flex_wrap",), (), {"flex_wrap": "no_wrap"}),
    ("sides", Length(4), FOUR, (), dict(zip(FOUR, (4, 4, 4, 4), strict=True))),
    # TDL order is left, top, right, bottom; tre's is top, right, bottom, left
    ("sides", Sides(1, 2, 3, 4), FOUR, (), dict(zip(FOUR, (2, 3, 4, 1), strict=True))),
    ("radius", Length(6), ("corner_radius",), (), {"corner_radius": 6}),
    (
        "radius",
        Seq((Length(1), Length(2), Length(3), Length(4))),
        ("corner_radius",),
        (),
        {"corner_radius": (1, 2, 3, 4)},
    ),
    ("font_family", Text("Inter"), ("font_family",), (), {"font_family": "Inter"}),
    (
        "font_family",
        Seq((Text("Inter"), Text("Noto"))),
        ("font_family",),
        (),
        {"font_family": "Inter, Noto"},
    ),
]


@pytest.mark.parametrize(("name", "value", "names", "choices", "expected"), GOOD)
def test_converts(
    name: str,
    value: Value,
    names: tuple[str, ...],
    choices: tuple[str, ...],
    expected: dict[str, Any],
) -> None:
    assert convert.CONVERTERS[name](value, names, choices) == expected


BAD: list[tuple[str, Value, tuple[str, ...], tuple[str, ...], str]] = [
    ("length", Text("16"), ("width",), (), "found text"),
    ("length", Length(-1), ("width",), (), "negative"),
    ("length", Percent(-5), ("width",), (), "negative"),
    ("length", Expand(), ("min_width",), (), "only allowed for Width and Height"),
    ("bound", Auto(), ("min_width",), (), "found auto"),
    ("number", Text("1"), ("opacity",), (), "found text"),
    ("number", Bool(True), ("opacity",), (), "found bool"),
    ("whole", Number(1.5), ("z_index",), (), "whole number"),
    ("positive", Number(0), ("font_size",), (), "greater than 0"),
    ("bool", Number(1), ("visible",), (), "true or false"),
    ("text", Number(1), ("text",), (), "a string"),
    ("color", Text("#fff"), ("fill",), (), "found text"),
    ("color", Color(256, 0, 0), ("fill",), (), "0 to 255"),
    ("enum", Enum("SIDEWAYS"), ("flex_direction",), ("HORIZONTAL", "VERTICAL"), "SIDEWAYS"),
    ("enum", Text("HORIZONTAL"), ("flex_direction",), ("HORIZONTAL",), "found text"),
    ("wrap_flag", Enum("WORD"), ("flex_wrap",), (), "true or false"),
    ("sides", Text("1"), FOUR, (), "a number or four sides"),
    ("sides", Length(-1), FOUR, (), "negative"),
    ("radius", Seq((Length(1), Length(2))), ("corner_radius",), (), "one number or four"),
    ("radius", Length(-2), ("corner_radius",), (), "negative"),
    ("font_family", Number(1), ("font_family",), (), "font family"),
]


@pytest.mark.parametrize(("name", "value", "names", "choices", "message"), BAD)
def test_bad_values_raise_at_their_position(
    name: str, value: Value, names: tuple[str, ...], choices: tuple[str, ...], message: str
) -> None:
    located = _at(value)
    with pytest.raises(BindError, match=message) as info:
        convert.CONVERTERS[name](located, names, choices)
    assert info.value.origin == AT


def _at(value: Value) -> Value:
    import dataclasses

    return dataclasses.replace(value, origin=AT)


def test_enum_error_suggests_the_nearest_word() -> None:
    with pytest.raises(BindError) as info:
        convert.enum(Enum("HORIZONTL", origin=AT), ("flex_direction",), ("HORIZONTAL", "VERTICAL"))
    assert "HORIZONTAL" in info.value.hint


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("#1f1f1f", (31, 31, 31, 255)),
        ("#89B4FA", (137, 180, 250, 255)),
        ("#00000040", (0, 0, 0, 64)),
        ("#fff", (255, 255, 255, 255)),
        ("#f008", (255, 0, 0, 136)),
        ("rgba(10 20 30 0.5)", (10, 20, 30, 128)),
        ("rgba(10, 20, 30, 1.0)", (10, 20, 30, 255)),
        ("rgb(1 2 3)", (1, 2, 3, 255)),
    ],
)
def test_parse_color(written: str, expected: tuple[int, int, int, int]) -> None:
    c = convert.parse_color(written, AT)
    assert (c.r, c.g, c.b, c.a) == expected and c.origin == AT


@pytest.mark.parametrize(
    "written",
    ["red", "#12", "#1234567", "#gggggg", "rgba(1 2)", "rgba(300 0 0 1)", "rgba(0 0 0 2)", ""],
)
def test_parse_color_errors_name_the_position(written: str) -> None:
    with pytest.raises(BindError) as info:
        convert.parse_color(written, AT)
    assert info.value.origin == AT
