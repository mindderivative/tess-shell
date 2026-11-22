"""The scrollbar of the spec (Scrollbar and Scroll Container): a ScrollBox takes its sizes and
opacities from the theme's ``Scrollbar`` group and the thumb in the muted ink; a block's own key
wins; a Popup's own scroll view gets the same."""

from __future__ import annotations

import pytest

from tests.widgets_live import running

BODY = (
    "Shell { Monitor { Name: Main, Index: 0, Children { Bar { Name: Top_Bar, Edge: TOP, "
    "Width: EXPAND, Height: 120, Children { %s } } } } }"
)


def scroll_node(w):  # type: ignore[no-untyped-def]
    return next(n for k, n in w.view.nodes.items() if k.endswith("S"))


def test_a_scrollbox_takes_the_specs_scrollbar_from_the_theme() -> None:
    box = "ScrollBox { Name: S, Width: 100, Height: 60, Children { FlexBox { Height: 400 } } }"
    with running("", body=BODY % box) as w:
        n = scroll_node(w)
        assert (n.get("scrollbar_width"), n.get("scrollbar_hit_width")) == (8, 12)
        assert (n.get("scrollbar_margin"), n.get("scrollbar_min_length")) == (2, 32)
        assert n.get("scrollbar_gutter") == 12 and n.get("scrollbar_radius") == 4
        assert [round(n.get(k), 2) for k in ("scrollbar_opacity", "scrollbar_opacity_hover")] == [
            0.7,
            0.8,
        ]
        assert n.get("scrollbar_opacity_drag") == 1.0
        assert (n.get("wheel_notch"), n.get("key_line")) == (40, 40)
        assert n.get("page_fraction") == pytest.approx(0.9)
        thumb = n.get("scrollbar_fill")
        assert thumb == n.get("scrollbar_fill_hover") == n.get("scrollbar_fill_drag")


def test_a_key_written_on_the_block_or_in_a_rule_replaces_the_themes() -> None:
    box = (
        "ScrollBox { Name: S, Width: 100, Height: 60, Style { Scrollbar_Width: 5, "
        "Scrollbar_Show: ALWAYS }, Children { FlexBox { Height: 400 } } }"
    )
    with running("", body=BODY % box) as w:
        n = scroll_node(w)
        assert n.get("scrollbar_width") == 5 and n.get("scrollbar_show") == "always"
        assert n.get("scrollbar_hit_width") == 12  # the rest stays the theme's


def test_a_scrollbar_key_that_is_no_choice_is_refused_at_load() -> None:
    from tests.test_focus import bar, read

    shell, findings = read(bar("ScrollBox { Name: S, Style { Scrollbar_Show: SOMETIMES } }"))
    assert shell is None
    (f,) = [f for f in findings if f.severity == "error"]
    assert f.rule == "bad-value" and "OVERFLOW, ALWAYS, AUTO_HIDE, NEVER" in f.message
