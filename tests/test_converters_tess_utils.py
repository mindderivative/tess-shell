"""The shell's converters over ``tess_utils`` (the ``tesserae-utils`` package from PyPI): colours,
sides, radius and enum words take tre's forms, and a bad value is a bind error at its position."""

from __future__ import annotations

import pytest

from tess_shell.binder import convert
from tess_shell.binder.model import (
    BindError,
    Enum,
    Length,
    Number,
    Origin,
    Seq,
    Sides,
)

AT = Origin("t.tdl", 3, 5)


@pytest.mark.parametrize(
    ("written", "expected"),
    [
        ("#102030", (16, 32, 48, 255)),
        ("#10203040", (16, 32, 48, 64)),
        ("#fa0", (255, 170, 0, 255)),
        ("rgba(0 0 0 0.5)", (0, 0, 0, 128)),
        ("rgb(1, 2, 3)", (1, 2, 3, 255)),
        ("transparent", (0, 0, 0, 0)),
    ],
)
def test_the_shell_reads_colours_through_tess_utils(
    written: str, expected: tuple[int, int, int, int]
) -> None:
    c = convert.parse_color(written, AT)
    assert (c.r, c.g, c.b, c.a) == expected and c.origin == AT


def test_a_bad_colour_is_a_bind_error_at_the_written_position() -> None:
    with pytest.raises(BindError) as exc:
        convert.parse_color("#12", AT)
    assert exc.value.origin == AT and "'#12'" in exc.value.message and exc.value.hint


def test_sides_radius_and_enum_words_take_tres_forms() -> None:
    assert convert.sides(Sides(1, 2, 3, 4, origin=AT), ("t", "r", "b", "l")) == {
        "t": 2,
        "r": 3,
        "b": 4,
        "l": 1,
    }
    assert convert.sides(Number(5, origin=AT), ("t", "r", "b", "l")) == {
        "t": 5,
        "r": 5,
        "b": 5,
        "l": 5,
    }
    items = tuple(Length(n, origin=AT) for n in (1, 2, 3, 4))
    assert convert.radius(Seq(items, origin=AT), ("corner_radius",)) == {
        "corner_radius": (1, 2, 3, 4)
    }
    assert convert.enum(Enum("SPACE_BETWEEN", origin=AT), ("justify",), ("SPACE_BETWEEN",)) == {
        "justify": "space_between"
    }
    with pytest.raises(BindError, match="negative"):
        convert.sides(Sides(1, -2, 3, 4, origin=AT), ("t", "r", "b", "l"))
