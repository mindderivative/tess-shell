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


def test_class_and_a_padding_with_no_strip_are_warnings() -> None:
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


# -- strips (Edges) -------------------------------------------------------------------------------

STRIP = (
    "Frame { Name: F, Thickness: 8, Padding: [2, 3, 4, 5], Edges { Top { Thickness: 32,"
    " Children { Spacer { Name: S } } }, Left { Thickness: 24, Padding: 1,"
    " Children { Spacer { Name: L } } }, Bottom { Thickness: 12 } } }"
)


def test_edges_hold_a_thickness_a_padding_and_the_strips_children() -> None:
    f = frame_of(STRIP)
    assert f.padding == (2, 3, 4, 5)
    assert set(f.edges) == {"top", "left", "bottom"}
    top, left, bottom = f.edges["top"], f.edges["left"], f.edges["bottom"]
    assert top.thickness == 32 and top.padding is None and len(top.children) == 1
    assert left.thickness == 24 and left.padding == (1, 1, 1, 1)
    assert bottom.thickness == 12 and bottom.children == ()  # an override with no strip


def test_a_strip_takes_the_frames_thickness_when_it_has_none_of_its_own() -> None:
    f = frame_of("Frame { Name: F, Thickness: 8, Edges { Top { Children { Spacer { } } } } }")
    assert f.edges["top"].thickness is None


def test_a_strip_on_a_side_with_no_thickness_is_an_error() -> None:
    (f,) = problems(
        "Frame { Name: F, Thickness { Left: 8 }, Edges { Top { Children { Spacer { } } } } }"
    )
    assert f.rule == "frame-strip-thickness" and "top strip" in f.message
    frame_of(
        "Frame { Name: F, Thickness { Left: 8 }, Edges { Top { Thickness: 20,"
        " Children { Spacer { } } } } }"
    )


@pytest.mark.parametrize(
    "edges",
    [
        "Edges { Middle { } }",
        "Edges { Top { Thickness: -1 } }",
        "Edges { Top { Colour: 3 } }",
        "Edges { Top { Thickness: 4 }, Top { Thickness: 5 } }",
        "Edges { Top { Padding: [1, 2] } }",
        "Edges { Top { Children { Nope { } } } }",
        "Edges: 3",
    ],
)
def test_a_wrong_edges_block_is_an_error(edges: str) -> None:
    assert problems(f"Frame {{ Name: F, Thickness: 8, {edges} }}")


# -- melded Panels --------------------------------------------------------------------------------

MELD = (
    "Panel { Name: Tab, Meld: true, Attach_To: F, Attach: TOP, Alignment: START, Width: 120,"
    " Height: 40, Style { Corner_Radius: 8 }, Children { Spacer { Name: T } } }"
)


def test_a_panel_with_meld_moves_into_its_frame_and_leaves_the_monitors_surfaces() -> None:
    shell, findings = read(with_frame("Frame { Name: F, Thickness: 12 }\n" + MELD))
    assert shell is not None and [f for f in findings if f.severity == "error"] == []
    (monitor,) = shell.monitors
    assert [s.name for s in monitor.surfaces] == ["Top_Bar"]
    (frame,) = monitor.frames
    (tab,) = frame.melds
    assert tab.name == "Tab" and tab.meld and tab.attach == "TOP" and tab.attach_to == "F"


@pytest.mark.parametrize(
    ("change", "rule"),
    [
        ("Margin: 4", "meld-margin"),
        ("Hide_After: 100", "not-built"),
        ("Movable: true", "not-built"),
        ("Keyboard: ON_DEMAND", "not-built"),
        ("Input_Region: AUTO", "not-built"),
        ("Animation { Type: SLIDE }", "not-built"),
        ("On_Open { Action: Hide, Target: Tab }", "not-built"),
    ],
)
def test_what_a_melded_panel_cannot_do_is_refused(change: str, rule: str) -> None:
    body = with_frame(
        "Frame { Name: F, Thickness: 12 }\n"
        + MELD.replace(" Width: 120,", f" {change}, Width: 120,")
    )
    shell, findings = read(body)
    errors = [f for f in findings if f.severity == "error"]
    assert shell is None and errors and rule in {f.rule for f in errors}


def test_meld_needs_an_attach_target_and_a_frame_of_the_same_monitor() -> None:
    bare = MELD.replace("Attach_To: F, ", "")
    assert "meld-target" in {f.rule for f in problems("Frame { Name: F, Thickness: 12 }\n" + bare)}
    assert "meld-target" in {
        f.rule for f in problems("Frame { Name: F, Thickness: 12 }\n" + MELD.replace("F,", "G,"))
    }


def test_a_melded_panels_own_colour_and_border_are_ignored_with_a_warning() -> None:
    panel = MELD.replace("Corner_Radius: 8", 'Corner_Radius: 8, Fill: "#ff0000", Border_Width: 2')
    shell, findings = read(with_frame("Frame { Name: F, Thickness: 12 }\n" + panel))
    assert shell is not None
    warned = [f for f in findings if f.severity == "warning"]
    assert {f.message.split(" ")[0] for f in warned} == {"Fill", "Border_Width"}


def test_a_panel_attached_to_a_frame_without_meld_is_still_not_built() -> None:
    plain = MELD.replace("Meld: true, ", "")
    (f,) = problems("Frame { Name: F, Thickness: 12 }\n" + plain)
    assert f.rule == "not-built" and "Frame F" in f.message


def test_a_melded_panel_attached_to_a_bar_is_refused() -> None:
    body = MELD.replace("Attach_To: F", "Attach_To: Top_Bar")
    assert "meld-target" in {f.rule for f in problems("Frame { Name: F, Thickness: 12 }\n" + body)}
