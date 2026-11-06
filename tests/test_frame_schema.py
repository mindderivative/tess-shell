"""The ``Frame`` block of a shell file: its forms, its tokens and what it refuses."""

from __future__ import annotations

import pytest

from tess_shell.binder.model import Color, TokenRef
from tess_shell.schema.findings import Finding
from tess_shell.schema.model import FrameDef
from tests.shell_samples import BODY
from tests.test_schema_shell import read


def with_frame(frame: str) -> str:
    return BODY.replace("            Bar {", f"            {frame}\n            Bar {{", 1)


def frame_of(frame: str) -> FrameDef:
    shell, findings = read(with_frame(frame))
    assert [f for f in findings if f.severity == "error"] == [], findings
    assert shell is not None
    (found,) = shell.monitors[0].frames
    return found


def problems(frame: str, extra: str = "") -> list[Finding]:
    shell, findings = read(with_frame(frame) + extra)
    assert shell is None, "expected an error"
    return [f for f in findings if f.severity == "error"]


@pytest.mark.parametrize(
    ("written", "sides"),
    [
        ("Thickness: 8", (8, 8, 8, 8)),
        ("Thickness: [1, 2, 3, 4]", (1, 2, 3, 4)),
        ("Thickness { Top: 8, Left: 24 }", (24, 8, 0, 0)),
        ("Thickness { Bottom: 5 }", (0, 0, 0, 5)),
    ],
)
def test_thickness_is_a_number_four_sides_or_named_sides(
    written: str, sides: tuple[float, ...]
) -> None:
    assert frame_of(f"Frame {{ Name: F, {written} }}").thickness == sides


@pytest.mark.parametrize(
    ("written", "sides"),
    [
        ("Margin: 5", (5, 5, 5, 5)),
        ("Margin: [5, 6, 7, 8]", (5, 6, 7, 8)),
        ("Margin { Right: 9 }", (0, 0, 9, 0)),
    ],
)
def test_margin_takes_the_same_forms(written: str, sides: tuple[float, ...]) -> None:
    assert frame_of(f"Frame {{ Name: F, Thickness: 8, {written} }}").margin == sides


def test_radii_are_one_number_or_four_corners_clockwise_from_the_top_left() -> None:
    f = frame_of("Frame { Name: F, Thickness: 8, Corner_Radius: 12, Inner_Radius: [1, 2, 3, 4] }")
    assert f.outer_radius == (12, 12, 12, 12) and f.inner_radius == (1, 2, 3, 4)
    f = frame_of("Frame { Name: F, Thickness: 8 }")
    assert f.outer_radius == (0, 0, 0, 0) and f.inner_radius == (0, 0, 0, 0)  # square outside


def test_borders_are_blocks_with_a_width_and_a_colour_or_token() -> None:
    f = frame_of(
        'Frame { Name: F, Thickness: 8, Inner_Border { Width: 2, Color: "#ffffff22" },'
        " Outer_Border { Width: 1, Color: $color.outline } }"
    )
    assert f.inner_border is not None and f.inner_border.width == 2
    assert f.inner_border.color == Color(255, 255, 255, 0x22)
    assert f.outer_border is not None and isinstance(f.outer_border.color, TokenRef)
    assert f.outer_border.color.path == "color.outline"


def test_the_background_is_a_colour_or_a_token_and_a_style_border_is_the_inner_border() -> None:
    f = frame_of(
        'Frame { Name: F, Thickness: 8, Style { Background: "#0b0c0d", Border_Width: 1,'
        ' Border_Color: "#ff0000", Opacity: 0.5 } }'
    )
    assert f.style["Background"] == Color(0x0B, 0x0C, 0x0D, 255)
    assert f.inner_border is not None and f.inner_border.width == 1
    f = frame_of(
        "Frame { Name: F, Thickness: 8, Style { Background: $color.surface,"
        ' Border { Width: 3, Color: "#00ff00" } } }'
    )
    assert isinstance(f.style["Background"], TokenRef)
    assert f.inner_border is not None and f.inner_border.width == 3


def test_visible_and_layer() -> None:
    assert frame_of("Frame { Name: F, Thickness: 8 }").visible is True
    assert frame_of("Frame { Name: F, Thickness: 8, Visible: false, Layer: TOP }").visible is False


def test_a_frame_needs_a_name_and_a_thickness() -> None:
    assert {f.rule for f in problems("Frame { Thickness: 8 }")} == {"missing-key"}
    (f,) = problems("Frame { Name: F }")
    assert f.rule == "missing-key" and "Thickness" in f.message


def test_a_monitor_has_one_frame() -> None:
    (f,) = problems("Frame { Name: A, Thickness: 8 }\nFrame { Name: B, Thickness: 8 }")
    assert f.rule == "frame-duplicate" and "A" in f.message


@pytest.mark.parametrize(
    "written",
    [
        "Thickness: [1, 2, 3]",
        "Thickness: -1",
        "Thickness { Top: -2 }",
        "Thickness: big",
        "Thickness: 8, Margin: [1, 2]",
        "Thickness: 8, Corner_Radius: [1, 2]",
        "Thickness: 8, Corner_Radius: -4",
        "Thickness: 8, Layer: BOTTOM",
        "Thickness: 8, Visible: yes",
        "Thickness: 8, Inner_Border: 3",
        "Thickness: 8, Inner_Border { Width: 1 }",
        'Thickness: 8, Inner_Border { Color: "#ffffff" }',
        'Thickness: 8, Inner_Border { Width: -1, Color: "#ffffff" }',
        'Thickness: 8, Inner_Border { Width: 1, Colour: "#ffffff" }',
        "Thickness: 8, Style { Background: 3 }",
        "Thickness: 8, Style { Border_Width: 2 }",
        'Thickness: 8, Style { Border_Color: "#ff0000" }',
        'Thickness: 8, Style { Colour: "#ff0000" }',
        "Thickness: 8, Colour: 3",
    ],
)
def test_a_wrong_value_or_key_is_an_error_at_its_position(written: str) -> None:
    fs = problems(f"Frame {{ Name: F, {written} }}")
    assert fs and all(f.line > 0 for f in fs)


def test_an_unknown_key_suggests_the_nearest() -> None:
    (f,) = problems("Frame { Name: F, Thickness: 8, Inner_Radus: 4 }")
    assert f.rule == "unknown-key" and "Inner_Radius" in f.hint


def test_a_second_inner_border_is_refused() -> None:
    (f,) = problems(
        'Frame { Name: F, Thickness: 8, Inner_Border { Width: 1, Color: "#fff" },'
        ' Style { Border_Width: 2, Border_Color: "#000" } }'
    )
    assert f.rule == "frame-border-twice"


@pytest.mark.parametrize(
    "written",
    [
        "Edges { Top { Thickness: 32 } }",
        "Children { Spacer { } }",
        "Border_Tile: true",
        "Meld: true",
        "Exclusive_Zone: 4",
        "Keyboard: ON_DEMAND",
        "Input_Region: AUTO",
        "Style { Elevation: 20% }",
        'Style { Shadows { Shadow { Color: "#000" } } }',
    ],
)
def test_what_is_not_built_is_an_error_not_a_silent_no_op(written: str) -> None:
    (f,) = problems(f"Frame {{ Name: F, Thickness: 8, {written} }}")
    assert f.rule == "not-built"


def test_padding_and_class_are_warnings() -> None:
    shell, findings = read(with_frame("Frame { Name: F, Thickness: 8, Padding: 4, Class: x }"))
    assert shell is not None
    assert [(f.rule, f.severity) for f in findings] == [("not-built", "warning")] * 2


def test_a_panel_attached_to_a_frame_is_not_built() -> None:
    panel = (
        "Panel { Name: P, Layer: OVERLAY, Width: 100, Height: 50, Attach_To: F, Attach: BOTTOM }"
    )
    (f,) = problems("Frame { Name: F, Thickness: 8 }\n" + panel)
    assert f.rule == "not-built" and "Frame F" in f.message


def test_the_frame_name_is_unique_across_the_shell() -> None:
    (f,) = problems("Frame { Name: Top_Bar, Thickness: 8 }")
    assert f.rule == "name-duplicate"
