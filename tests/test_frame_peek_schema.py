"""``Peek { Size, Enter_Delay, Exit_Delay }`` on a melded Panel and on an ``Edges`` entry, and
``Name`` on a strip: what it takes and what it refuses."""

from __future__ import annotations

import pytest

from tess_shell.schema.model import EdgeDef, PanelDef, PeekDef
from tests.test_frame_schema import MELD, problems, with_frame
from tests.test_schema_shell import read


def melded(peek: str) -> PanelDef:
    panel = MELD.replace("Style {", f"{peek}, Style {{") if peek else MELD
    shell, findings = read(with_frame("Frame { Name: F, Thickness: 12 }\n" + panel))
    assert shell is not None and [f for f in findings if f.severity == "error"] == [], findings
    return shell.monitors[0].frames[0].melds[0]


def strip(text: str, frame: str = "Frame { Name: F, Thickness: 6, ") -> EdgeDef:
    shell, findings = read(with_frame(frame + f"Edges {{ Top {{ {text} }} }} }}"))
    assert shell is not None and [f for f in findings if f.severity == "error"] == [], findings
    return shell.monitors[0].frames[0].edges["top"]


KID = 'Children { Rectangle { Name: Dot, Width: 5, Height: 5, Fill: "#ff0000" } }'


def test_a_peek_is_a_block_with_the_defaults_24_150_and_300() -> None:
    assert melded("").peek is None
    peek = melded("Peek { }").peek
    assert isinstance(peek, PeekDef)
    assert (peek.size, peek.enter_delay, peek.exit_delay) == (24, 150, 300)
    peek = melded("Peek { Size: 10, Enter_Delay: 0, Exit_Delay: 50 }").peek
    assert peek is not None and (peek.size, peek.enter_delay, peek.exit_delay) == (10, 0, 50)


@pytest.mark.parametrize(
    ("written", "message"),
    [
        ("Peek { Size: 0 }", "Size is 1 or more pixels"),
        ("Peek { Size: -3 }", "Size is 1 or more pixels"),
        ("Peek { Enter_Delay: -1 }", "Enter_Delay is 0 or more"),
        ("Peek { Exit_Delay: -1 }", "Exit_Delay is 0 or more"),
    ],
)
def test_a_peek_size_below_1_px_or_a_negative_delay_is_an_error(written: str, message: str) -> None:
    body = "Frame { Name: F, Thickness: 12 }\n" + MELD.replace("Style {", f"{written}, Style {{")
    assert message in {f.message for f in problems(body)}


def test_an_unknown_key_in_a_peek_names_the_nearest_ones() -> None:
    body = "Frame { Name: F, Thickness: 12 }\n" + MELD.replace(
        "Style {", "Peek { Sise: 10 }, Style {"
    )
    (f,) = problems(body)
    assert "Sise" in f.message and "Size" in f.hint


def test_a_peek_is_a_block_not_a_value() -> None:
    body = "Frame { Name: F, Thickness: 12 }\n" + MELD.replace("Style {", "Peek: 10, Style {")
    assert "bad-value" in {f.rule for f in problems(body)}


def test_a_peek_larger_than_the_depth_is_an_error() -> None:
    body = "Frame { Name: F, Thickness: 12 }\n" + MELD.replace(
        "Style {", "Peek { Size: 40 }, Style {"
    )  # the Depth is 40: the tab would be the whole body
    (f,) = problems(body)
    assert f.rule == "peek-size" and "Depth" in f.message


def test_a_panel_in_a_window_of_its_own_has_no_peek() -> None:
    plain = (
        "Panel { Name: P, Layer: OVERLAY, Width: 100, Height: 50, Anchor: [TOP], Peek { Size: 5 } }"
    )
    (f,) = problems(plain)
    assert f.rule == "peek-window" and "Meld: true" in f.hint


def test_a_strip_takes_a_peek_and_a_name() -> None:
    edge = strip(f"Thickness: 34, Name: Top_Strip, {KID}, Peek {{ Size: 6, Exit_Delay: 100 }}")
    assert edge.name == "Top_Strip" and edge.thickness == 34
    assert edge.peek is not None and (edge.peek.size, edge.peek.exit_delay) == (6, 100)
    plain = strip(f"Thickness: 34, {KID}")
    assert plain.peek is None and plain.name is None


def test_a_strip_peek_needs_children_and_a_thickness_above_its_size() -> None:
    body = with_frame(
        "Frame { Name: F, Thickness: 6, Edges { Top { Thickness: 34, Peek { Size: 6 } } } }"
    )
    assert "peek-empty" in {f.rule for f in problems_of(body)}
    body = with_frame(
        f"Frame {{ Name: F, Thickness: 6, Edges {{ Top {{ Thickness: 20, {KID}, "
        "Peek { Size: 24 } } } }"
    )
    assert "peek-size" in {f.rule for f in problems_of(body)}


def problems_of(body: str):  # type: ignore[no-untyped-def]
    shell, findings = read(body)
    assert shell is None, "expected an error"
    return [f for f in findings if f.severity == "error"]


def test_a_name_on_a_strip_without_a_peek_is_not_built() -> None:
    body = with_frame(f"Frame {{ Name: F, Thickness: 6, Edges {{ Top {{ Name: S, {KID} }} }} }}")
    (f,) = problems_of(body)
    assert f.rule == "not-built" and "Peek" in f.hint


def test_a_strips_name_is_unique_among_the_shells_names() -> None:
    body = with_frame(
        f"Frame {{ Name: F, Thickness: 6, Edges {{ Top {{ Name: F, Thickness: 30, {KID}, "
        "Peek { Size: 6 } } } }"
    )
    assert problems_of(body)


def test_an_unknown_key_in_a_strip_lists_name_and_peek() -> None:
    body = with_frame(f"Frame {{ Name: F, Thickness: 6, Edges {{ Top {{ Peak: 6, {KID} }} }} }}")
    (f,) = problems_of(body)
    assert "Peak" in f.message and "Peek" in f.hint


# -- Trigger, Handle, Slide_From ------------------------------------------------------------------


def corner_panel(peek: str, attach: str = "TOP", alignment: str = "END") -> str:
    return (
        f"Panel {{ Name: Tab, Meld: true, Attach_To: F, Attach: {attach}, "
        f"Alignment: {alignment}, Length: 120, Depth: 40, {peek} }}"
    )


def read_corner(peek: str, attach: str = "TOP", alignment: str = "END") -> PanelDef:
    body = with_frame("Frame { Name: F, Thickness: 12 }\n" + corner_panel(peek, attach, alignment))
    shell, findings = read(body)
    assert shell is not None and [f for f in findings if f.severity == "error"] == [], findings
    return shell.monitors[0].frames[0].melds[0]


def test_trigger_handle_and_slide_from_default_to_hover_auto_and_the_attached_edge() -> None:
    peek = read_corner("Peek { }").peek
    assert peek is not None
    assert (peek.trigger, peek.handle, peek.slide_from) == ("HOVER", "AUTO", None)
    peek = read_corner("Peek { Trigger: DRAG, Handle: CHEVRON, Slide_From: RIGHT, Size: 10 }").peek
    assert peek is not None
    assert (peek.trigger, peek.handle, peek.slide_from) == ("DRAG", "CHEVRON", "RIGHT")


@pytest.mark.parametrize("trigger", ["HOVER", "CLICK", "DRAG"])
@pytest.mark.parametrize("handle", ["AUTO", "NONE", "DOTS", "BAR", "CHEVRON"])
def test_every_trigger_and_handle_word_is_taken(trigger: str, handle: str) -> None:
    peek = read_corner(f"Peek {{ Trigger: {trigger}, Handle: {handle} }}").peek
    assert peek is not None and (peek.trigger, peek.handle) == (trigger, handle)


def test_a_list_of_triggers_is_a_clear_not_built_error_with_the_one_value_form() -> None:
    body = "Frame { Name: F, Thickness: 12 }\n" + corner_panel("Peek { Trigger: [HOVER, DRAG] }")
    (f,) = problems(body)
    assert f.rule == "not-built" and "list" in f.message and "Trigger: HOVER" in f.hint


def test_a_bad_trigger_or_handle_word_names_the_choices() -> None:
    for written in ("Trigger: TAP", "Handle: ARROW"):
        (f,) = problems(
            "Frame { Name: F, Thickness: 12 }\n" + corner_panel(f"Peek {{ {written} }}")
        )
        assert f.rule == "bad-value" and ("HOVER" in f.message or "DOTS" in f.message)


@pytest.mark.parametrize(
    ("attach", "alignment", "ok", "bad"),
    [
        ("TOP", "END", ("TOP", "RIGHT"), ("LEFT", "BOTTOM")),
        ("TOP", "START", ("TOP", "LEFT"), ("RIGHT", "BOTTOM")),
        ("BOTTOM", "END", ("BOTTOM", "RIGHT"), ("LEFT", "TOP")),
        ("LEFT", "START", ("LEFT", "TOP"), ("RIGHT", "BOTTOM")),
        ("RIGHT", "END", ("RIGHT", "BOTTOM"), ("LEFT", "TOP")),
    ],
)
def test_slide_from_is_the_attached_edge_or_the_other_edge_of_the_corner(
    attach: str, alignment: str, ok: tuple[str, ...], bad: tuple[str, ...]
) -> None:
    for edge in ok:
        assert read_corner(f"Peek {{ Slide_From: {edge} }}", attach, alignment).peek is not None
    for edge in bad:
        body = "Frame { Name: F, Thickness: 12 }\n" + corner_panel(
            f"Peek {{ Slide_From: {edge} }}", attach, alignment
        )
        (f,) = problems(body)
        assert f.rule == "peek-slide-from" and edge in f.message


def test_a_centred_panel_touches_one_edge_so_slide_from_must_be_it() -> None:
    assert read_corner("Peek { Slide_From: TOP }", "TOP", "CENTER").peek is not None
    body = "Frame { Name: F, Thickness: 12 }\n" + corner_panel(
        "Peek { Slide_From: RIGHT }", "TOP", "CENTER"
    )
    (f,) = problems(body)
    assert f.rule == "peek-slide-from" and "CENTER" in f.hint


def test_with_slide_from_the_size_is_checked_against_the_extent_it_slides_along() -> None:
    assert read_corner("Peek { Size: 60, Slide_From: RIGHT }").peek is not None  # Length 120
    body = "Frame { Name: F, Thickness: 12 }\n" + corner_panel("Peek { Size: 60 }")
    assert "peek-size" in {f.rule for f in problems(body)}  # the Depth is 40
    body = "Frame { Name: F, Thickness: 12 }\n" + corner_panel(
        "Peek { Size: 130, Slide_From: RIGHT }"
    )
    (f,) = problems(body)
    assert f.rule == "peek-size" and "Length" in f.message


def test_a_strip_has_no_slide_from_it_runs_the_whole_side() -> None:
    body = with_frame(
        f"Frame {{ Name: F, Thickness: 6, Edges {{ Top {{ Thickness: 34, {KID}, "
        "Peek { Slide_From: TOP } } } }"
    )
    (f,) = problems_of(body)
    assert f.rule == "peek-slide-from" and "strip" in f.message
    edge = strip(f"Thickness: 34, {KID}, Peek {{ Trigger: DRAG, Handle: BAR }}")
    assert edge.peek is not None and (edge.peek.trigger, edge.peek.handle) == ("DRAG", "BAR")


def test_enter_and_exit_delay_with_click_or_drag_are_a_warning_not_an_error() -> None:
    def written(trigger: str) -> str:
        return with_frame(
            "Frame { Name: F, Thickness: 12 }\n"
            + corner_panel(f"Peek {{ Trigger: {trigger}, Exit_Delay: 100 }}")
        )

    for trigger in ("CLICK", "DRAG"):
        shell, findings = read(written(trigger))
        assert shell is not None
        assert any(f.severity == "warning" and "Exit_Delay" in f.message for f in findings)
    assert not [f for f in read(written("HOVER"))[1] if f.severity == "warning"]


def test_size_is_not_a_hover_delay_and_never_warns() -> None:
    for trigger in ("CLICK", "DRAG"):
        body = with_frame(
            "Frame { Name: F, Thickness: 12 }\n"
            + corner_panel(f"Peek {{ Trigger: {trigger}, Size: 10 }}")
        )
        shell, findings = read(body)
        assert shell is not None and not [f for f in findings if f.severity == "warning"]


# -- Handle_Opacity, Content_Fade -----------------------------------------------------------------


def test_handle_opacity_defaults_to_0_6_and_takes_0_to_1() -> None:
    peek = read_corner("Peek { }").peek
    assert peek is not None and peek.handle_opacity == 0.6
    for value, want in (("0", 0.0), ("1", 1.0), ("0.25", 0.25)):
        peek = read_corner(f"Peek {{ Handle_Opacity: {value} }}").peek
        assert peek is not None and peek.handle_opacity == want
    edge = strip(f"Thickness: 34, {KID}, Peek {{ Handle_Opacity: 0.3 }}")
    assert edge.peek is not None and edge.peek.handle_opacity == 0.3


@pytest.mark.parametrize("value", ["1.5", "-0.1"])
def test_a_handle_opacity_outside_0_to_1_is_an_error(value: str) -> None:
    body = "Frame { Name: F, Thickness: 12 }\n" + corner_panel(
        f"Peek {{ Handle_Opacity: {value} }}"
    )
    (f,) = problems(body)
    assert f.rule == "bad-value" and "0 to 1" in f.message


def test_handle_opacity_never_warns_with_click_or_drag() -> None:
    body = with_frame(
        "Frame { Name: F, Thickness: 12 }\n"
        + corner_panel("Peek { Trigger: CLICK, Handle_Opacity: 0.2 }")
    )
    shell, findings = read(body)
    assert shell is not None and not [f for f in findings if f.severity == "warning"]


def test_content_fade_is_on_by_default_and_false_opts_out_on_a_panel_and_a_strip() -> None:
    assert read_corner("Peek { }").content_fade is True
    body = with_frame(
        "Frame { Name: F, Thickness: 12 }\n"
        + corner_panel("Peek { }").replace("Depth: 40,", "Depth: 40, Content_Fade: false,")
    )
    shell, findings = read(body)
    assert shell is not None and not findings
    assert shell.monitors[0].frames[0].melds[0].content_fade is False
    assert strip(f"Thickness: 34, {KID}, Peek {{ }}").content_fade is True
    assert strip(f"Thickness: 34, Content_Fade: false, {KID}, Peek {{ }}").content_fade is False


def test_content_fade_must_be_a_boolean_and_a_window_panel_is_warned_it_has_none() -> None:
    body = "Frame { Name: F, Thickness: 12 }\n" + corner_panel("Peek { }").replace(
        "Depth: 40,", "Depth: 40, Content_Fade: 3,"
    )
    assert problems(body)
    window = (
        "Panel { Name: P, Layer: OVERLAY, Width: 100, Height: 50, Anchor: [TOP], "
        "Content_Fade: false }"
    )
    shell, findings = read(with_frame(window))
    assert shell is not None
    warned = [f for f in findings if f.severity == "warning"]
    assert warned and "Content_Fade" in warned[0].message and "Meld" in warned[0].hint
