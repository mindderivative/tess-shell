"""Peek triggers and handles: ``Trigger`` CLICK and DRAG, the icon on the tab (dots, a bar, a
chevron that turns with the slide), the minimum sizes, and ``Slide_From`` of a corner Panel.
Headless like ``test_frame_peek``: tre's clock (``advance``) and tre's hit test (``simulate``).
The geometry is that file's: a 400 x 300 output, a Frame 20 thick with a 2 px green border (the
handle's colour), a Panel 120 x 40 against the top at x 20..140 whose tab is 12 px (y 20..32), so
a handle sits at (80, 26) at rest and 28 px lower (80, 54) when the body is out."""

from __future__ import annotations

from typing import Any

import pytest
from loguru import logger

from tess_shell.surfaces import handle as handles
from tess_shell.surfaces.join import JOINS
from tests.test_frame import only
from tests.test_frame_peek import (
    BELOW,
    BLUE,
    NONE,
    RING,
    act,
    advance,
    at_rest,
    host,
    is_out,
    point,
    px,
    started,
)

ON_TAB = (60, 26)
FAR = (60, 58)  # the far strip of the body when it is out (depth 38 of 40, 12 px of it)
AWAY = (300, 200)


def peek(trigger: str = "HOVER", handle: str = "AUTO", size: int = 12, more: str = "") -> str:
    parts = [f"Size: {size}", f"Trigger: {trigger}", f"Handle: {handle}"]
    return f"Peek {{ {', '.join(parts)}{more} }}"


def sim(m: Any, event: str, where: tuple[int, int], **fields: Any) -> None:
    only(m).painter.simulate(event, x=where[0], y=where[1], **fields)


def click(m: Any, where: tuple[int, int]) -> None:
    """A press and a release on one node: tre makes the ``click``."""
    sim(m, "pointer_down", where)
    sim(m, "pointer_up", where)


def ink(m: Any, x0: int = 62, y0: int = 21, x1: int = 98, y1: int = 31) -> list[tuple[int, int]]:
    """The pixels of the handle: those in the box that are not the Frame's blue, above the
    contour's border (the first transparent row at x = 60, less its 2 px, bounds the box)."""
    at = px(m)
    edge = next(y for y in range(21, 90) if at(60, y) == NONE)
    return [(x, y) for x in range(x0, x1) for y in range(y0, min(y1, edge - 2)) if at(x, y) != BLUE]


def centre_y(points: list[tuple[int, int]], x0: int, x1: int) -> float:
    ys = [y for x, y in points if x0 <= x < x1]
    assert ys, "no handle pixels there"
    return sum(ys) / len(ys)


# -- what is drawn ------------------------------------------------------------------------------


def test_auto_picks_dots_for_hover_a_bar_for_drag_and_a_chevron_for_click() -> None:
    kinds = {}
    for trigger in ("HOVER", "DRAG", "CLICK"):
        m = started(extra=peek(trigger))
        kinds[trigger] = host(m).handle.kind
    assert kinds == {"HOVER": "DOTS", "DRAG": "BAR", "CLICK": "CHEVRON"}
    assert host(started(extra=peek("CLICK", "DOTS"))).handle.kind == "DOTS"  # named: forced
    assert host(started(extra=peek("HOVER", "NONE"))).handle is None


def test_the_dots_are_three_dots_side_by_side_on_the_middle_of_the_tab() -> None:
    m = started(extra=peek("HOVER"))
    pts = ink(m)
    assert pts, "nothing was drawn"
    xs = sorted({x for x, _ in pts})
    # three separate groups of columns (a dot is 3 px wide, the gap 3 px), centred on x = 80
    groups = [g for g in _runs(xs)]
    assert len(groups) == 3, groups
    assert (
        70 <= groups[0][0]
        and groups[2][-1] <= 90
        and abs((groups[0][0] + groups[2][-1]) / 2 - 80) <= 1.5
    )
    ys = [y for _, y in pts]
    assert 23 <= min(ys) and max(ys) <= 29 and abs((min(ys) + max(ys)) / 2 - 26) <= 1.5


def _runs(values: list[int]) -> list[list[int]]:
    out: list[list[int]] = []
    for v in values:
        if out and v == out[-1][-1] + 1:
            out[-1].append(v)
        else:
            out.append([v])
    return out


def test_the_bar_is_one_short_bar_and_a_hover_icon_is_not_a_bar() -> None:
    m = started(extra=peek("DRAG"))
    pts = ink(m)
    xs = sorted({x for x, _ in pts})
    assert len(_runs(xs)) == 1 and 20 <= xs[-1] - xs[0] + 1 <= 26  # one run, about 24 px
    assert max(y for _, y in pts) - min(y for _, y in pts) <= 4  # 3 px thick


def test_the_handle_has_the_colour_of_the_frames_border_dimmed_until_the_pointer_is_on_it() -> None:
    m = started(extra=peek("DRAG"))
    at = px(m)
    r, g, b, _ = at(80, 26)
    assert g > 100 and r < 40  # green on blue: the border's colour, 60 % of it
    full = g
    point(m, ON_TAB)
    advance(m, 200)  # the icon brightens while the pointer is on the tab
    assert px(m)(80, 26)[1] > full
    point(m, AWAY)
    advance(m, 200)
    assert px(m)(80, 26)[1] == full


@pytest.mark.parametrize("scale", [1.0, 1.5])
def test_the_icons_are_drawn_at_a_fractional_scale_too(scale: float) -> None:
    m = started(extra=peek("CLICK"))
    rgba, w, _ = only(m).painter.snapshot(scale=scale)
    xs = range(int(62 * scale), int(98 * scale))
    ys = range(int(21 * scale), int(31 * scale))
    drawn = [
        1 for x in xs for y in ys if tuple(rgba[(y * w + x) * 4 : (y * w + x) * 4 + 4]) != BLUE
    ]
    assert len(drawn) > 10


def test_a_handle_does_not_take_clicks_the_tab_does() -> None:
    m = started(extra=peek("CLICK"))
    h = host(m)
    seen: list[Any] = []
    h.clip.on("pointer_down", lambda e: seen.append(e.target))
    sim(m, "pointer_down", (80, 26))  # on the icon
    assert len(seen) == 1 and seen[0] != h.handle.holder
    assert h.handle.holder.get("hit_testable") is False
    assert all(n.get("hit_testable") is False for n in h.handle.parts)


# -- minimum sizes -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("trigger", "size", "drawn"),
    [
        ("HOVER", 7, False),
        ("HOVER", 8, True),
        ("DRAG", 7, False),
        ("DRAG", 8, True),
        ("CLICK", 11, False),
        ("CLICK", 12, True),
    ],
)
def test_a_handle_is_drawn_only_on_a_tab_at_least_as_thick_as_its_minimum(
    trigger: str, size: int, drawn: bool
) -> None:
    seen: list[str] = []
    sink = logger.add(lambda message: seen.append(str(message)), level="DEBUG")
    try:
        m = started(extra=peek(trigger, size=size))
    finally:
        logger.remove(sink)
    assert (host(m).handle is not None) is drawn
    said = [s for s in seen if "handle: its tab" in s]
    assert len(said) == (0 if drawn else 1)
    if not drawn:
        assert "thinner than" in said[0] and "WARNING" not in said[0] and "INFO" not in said[0]


def test_a_side_thinner_than_the_handle_draws_none() -> None:
    thin = RING.replace("Thickness: 20", "Thickness: 6")
    m = started(extra=peek("HOVER", size=12), frame=thin)
    assert host(m).handle is None  # the 12 px tab is thick enough: the Frame's side is not


def test_the_minimums_are_named_constants() -> None:
    assert handles.MIN_THICKNESS == {"DOTS": 8.0, "BAR": 8.0, "CHEVRON": 12.0}


# -- the chevron turns with the slide ------------------------------------------------------------


def test_the_chevron_points_away_from_the_frame_at_rest_and_towards_it_when_out() -> None:
    m = started(extra=peek("CLICK"))
    rest = ink(m)
    # the top Frame: away is down. The apex is the middle column, the ends the outer ones
    assert centre_y(rest, 79, 82) > centre_y(rest, 72, 75) + 2
    click(m, ON_TAB)
    advance(m, 450)
    assert is_out(m)
    out = ink(m, 62, 47, 98, 61)
    assert centre_y(out, 79, 82) < centre_y(out, 72, 75) - 2  # towards the Frame: up
    assert 50 <= centre_y(out, 62, 98) <= 56  # on the far strip of the body, 12 px of it
    click(m, FAR)
    advance(m, 450)
    assert at_rest(m)
    back = ink(m)
    assert centre_y(back, 79, 82) > centre_y(back, 72, 75) + 2


def test_the_chevron_changes_during_the_slide_not_before_and_not_after() -> None:
    m = started(extra=peek("CLICK"))
    click(m, ON_TAB)
    advance(m, 1)
    seen = []
    for _ in range(14):
        advance(m, 25)
        pts = ink(m, 62, 21, 98, 61)
        seen.append(centre_y(pts, 79, 82) - centre_y(pts, 72, 75))
    assert seen[0] > 0 > seen[-1], seen  # away, then towards
    assert all(b <= a + 0.5 for a, b in zip(seen, seen[1:], strict=False))  # one way only
    advance(m, 100)
    assert host(m).anim is None


def test_the_handle_travels_with_the_far_edge_and_does_not_jump_at_the_end() -> None:
    m = started(extra=peek("CLICK"))
    click(m, ON_TAB)
    advance(m, 1)
    ys = []
    for _ in range(7):
        advance(m, 50)
        ys.append(centre_y(ink(m, 62, 21, 98, 61), 62, 98))
    assert ys == sorted(ys) and ys[0] > 24  # it only goes down
    advance(m, 100)
    before = centre_y(ink(m, 62, 21, 98, 61), 62, 98)
    advance(m, 100)
    assert host(m).anim is None
    after = centre_y(ink(m, 62, 21, 98, 61), 62, 98)
    assert abs(before - after) < 1.0, (before, after)


def test_the_chevron_at_the_middle_of_a_drag_is_between_the_two() -> None:
    m = started(extra=peek("DRAG", "CHEVRON"))
    sim(m, "pointer_down", ON_TAB)
    sim(m, "pointer_move", (60, 40))  # 14 of 28 px: half way
    pts = ink(m, 62, 21, 98, 61)
    assert abs(centre_y(pts, 79, 82) - centre_y(pts, 72, 75)) < 1.5  # a flat chevron
    assert abs(centre_y(pts, 62, 98) - 40) <= 2.5  # at the middle of the way


def test_reduced_motion_flips_the_chevron_at_once_with_the_state() -> None:
    m = started(extra=peek("CLICK"), reduced=True)
    click(m, ON_TAB)
    assert is_out(m) and host(m).anim is None
    out = ink(m, 62, 47, 98, 61)
    assert centre_y(out, 79, 82) < centre_y(out, 72, 75) - 2
    click(m, FAR)
    assert at_rest(m)
    back = ink(m)
    assert centre_y(back, 79, 82) > centre_y(back, 72, 75) + 2


# -- CLICK ---------------------------------------------------------------------------------------


def test_a_click_on_the_tab_opens_it_and_a_click_on_the_handle_closes_it() -> None:
    m = started(extra=peek("CLICK"))
    click(m, ON_TAB)
    assert host(m).anim == "in"
    advance(m, 450)
    assert is_out(m) and px(m)(60, 59) == BLUE
    click(m, FAR)
    advance(m, 450)
    assert at_rest(m) and px(m)(*BELOW) == NONE


def test_with_click_hovering_does_nothing_and_leaving_does_not_close_it() -> None:
    m = started(extra=peek("CLICK"))
    point(m, ON_TAB)
    advance(m, 2000)
    assert at_rest(m)
    click(m, ON_TAB)
    advance(m, 450)
    point(m, AWAY)
    advance(m, 2000)
    assert is_out(m)


def test_a_click_on_the_open_body_beside_the_handle_is_not_a_trigger() -> None:
    m = started(extra=peek("CLICK"))
    click(m, ON_TAB)
    advance(m, 450)
    click(m, (60, 40))  # the content area: its own clicks are the Panel's
    advance(m, 450)
    assert is_out(m)


def test_a_second_click_while_it_slides_turns_it_round() -> None:
    m = started(extra=peek("CLICK"))
    click(m, ON_TAB)
    advance(m, 150)
    assert host(m).anim == "in"
    click(m, (60, 30))  # during the slide the tab zone and the far zone both take it
    assert host(m).anim == "out"
    advance(m, 500)
    assert at_rest(m)


def test_a_secondary_button_does_not_trigger() -> None:
    m = started(extra=peek("CLICK"))
    sim(m, "pointer_down", ON_TAB, button="secondary")
    sim(m, "pointer_up", ON_TAB, button="secondary")
    advance(m, 500)
    assert at_rest(m)


def test_click_events_and_hide_after() -> None:
    log: list[str] = []
    m = started(extra=peek("CLICK"), more="Hide_After: 800")
    real = m._fire
    m._fire = lambda s, key: (log.append(key), real(s, key))[1]  # type: ignore[method-assign]
    click(m, ON_TAB)
    advance(m, 450)
    assert log == ["On_Open", "On_Anim_Start", "On_Anim_End", "On_Visible"]
    point(m, BELOW)
    advance(m, 2000)
    assert is_out(m)  # the timer ran out with the pointer on the body: it waits
    point(m, AWAY)
    advance(m, 900)
    advance(m, 450)
    assert at_rest(m)  # then it went back to the tab, not away
    assert log[-4:] == ["On_Close", "On_Anim_Start", "On_Anim_End", "On_Hidden"]


def test_enter_and_exit_delay_are_ignored_with_click_and_say_so_at_load() -> None:
    from tests.test_frame_peek_schema import MELD, with_frame
    from tests.test_schema_shell import read

    body = with_frame(
        "Frame { Name: F, Thickness: 12 }\n"
        + MELD.replace("Style {", "Peek { Trigger: CLICK, Enter_Delay: 50 }, Style {")
    )
    shell, findings = read(body)
    assert shell is not None
    warned = [f for f in findings if f.severity == "warning"]
    assert warned and "Enter_Delay" in warned[0].message and "CLICK" in warned[0].message


# -- DRAG ----------------------------------------------------------------------------------------


def contour_edge(m: Any, x: int = 60) -> int:
    """The first transparent pixel below the band at column ``x`` (the far edge plus its border)."""
    at = px(m)
    return next(y for y in range(21, 90) if at(x, y) == NONE)


def test_a_drag_pulls_the_body_out_following_the_pointer_and_a_release_past_half_opens_it() -> None:
    m = started(extra=peek("DRAG"))
    sim(m, "pointer_down", ON_TAB)
    sim(m, "pointer_move", (60, 32))
    sim(m, "pointer_move", (60, 34))
    a = contour_edge(m)
    sim(m, "pointer_move", (60, 40))
    b = contour_edge(m)
    assert b - a == 6  # the far edge moved as far as the pointer: 40 - 34
    sim(m, "pointer_move", (60, 46))
    assert contour_edge(m) - b == 6
    assert host(m).anim == "in" and host(m).drag is not None
    sim(m, "pointer_up", (60, 46))  # 20 of 28 px: past half
    assert host(m).drag is None
    advance(m, 500)
    assert is_out(m) and px(m)(60, 59) == BLUE


def test_a_release_below_half_sends_it_back_to_the_tab() -> None:
    m = started(extra=peek("DRAG"))
    sim(m, "pointer_down", ON_TAB)
    sim(m, "pointer_move", (60, 34))  # 8 of 28 px
    sim(m, "pointer_up", (60, 34))
    advance(m, 500)
    assert at_rest(m) and px(m)(*BELOW) == NONE and px(m)(60, 31) == BLUE


def test_exactly_half_opens_it() -> None:
    m = started(extra=peek("DRAG"))
    sim(m, "pointer_down", ON_TAB)
    sim(m, "pointer_move", (60, 40))  # 14 of 28 px
    sim(m, "pointer_up", (60, 40))
    advance(m, 500)
    assert is_out(m)


def test_the_body_does_not_go_past_the_ends_whatever_the_pointer_does() -> None:
    m = started(extra=peek("DRAG"))
    sim(m, "pointer_down", ON_TAB)
    sim(m, "pointer_move", (60, 200))  # far past the full depth
    assert host(m).drag.p == 1.0 and contour_edge(m) == 62
    sim(m, "pointer_move", (60, 5))  # and back past the top
    assert host(m).drag.p == 0.0
    sim(m, "pointer_up", (60, 5))
    advance(m, 500)
    assert at_rest(m)


def test_a_press_that_moves_under_four_pixels_is_a_click_and_toggles_it() -> None:
    m = started(extra=peek("DRAG"))
    sim(m, "pointer_down", ON_TAB)
    sim(m, "pointer_move", (60, 29))  # 3 px
    sim(m, "pointer_up", (60, 29))
    assert host(m).anim == "in"
    advance(m, 450)
    assert is_out(m)
    sim(m, "pointer_down", FAR)
    sim(m, "pointer_up", FAR)  # a click on the handle strip closes it again
    advance(m, 450)
    assert at_rest(m)


def test_a_drag_back_from_out_follows_the_pointer_and_a_release_below_half_closes_it() -> None:
    m = started(extra=peek("DRAG"))
    act(m, "Show")
    advance(m, 450)
    assert is_out(m)
    sim(m, "pointer_down", FAR)
    sim(m, "pointer_move", (60, 50))
    sim(m, "pointer_move", (60, 38))  # 20 px up: p = 1 - 20 / 28
    assert 0.2 < host(m).drag.p < 0.35 and host(m).anim == "out"
    sim(m, "pointer_up", (60, 38))
    advance(m, 500)
    assert at_rest(m)


def test_a_drag_back_released_past_half_leaves_it_out_with_no_events() -> None:
    log: list[str] = []
    m = started(extra=peek("DRAG"))
    act(m, "Show")
    advance(m, 450)
    real = m._fire
    m._fire = lambda s, key: (log.append(key), real(s, key))[1]  # type: ignore[method-assign]
    sim(m, "pointer_down", FAR)
    sim(m, "pointer_move", (60, 52))
    sim(m, "pointer_up", (60, 52))
    advance(m, 500)
    assert is_out(m) and log == []


def test_a_press_on_the_open_bodys_content_does_not_start_a_drag() -> None:
    m = started(extra=peek("DRAG"))
    act(m, "Show")
    advance(m, 450)
    sim(m, "pointer_down", (60, 40))
    sim(m, "pointer_move", (60, 70))
    assert host(m).drag is None and is_out(m)


def test_the_pointer_is_captured_so_a_move_off_the_tab_keeps_dragging() -> None:
    m = started(extra=peek("DRAG"))
    sim(m, "pointer_down", ON_TAB)
    sim(m, "pointer_move", (300, 45))  # far outside the Panel, along the slide by 19 px
    assert host(m).drag is not None and 0.6 < host(m).drag.p < 0.7
    sim(m, "pointer_up", (300, 45))
    advance(m, 500)
    assert is_out(m)


def test_a_drag_does_not_use_the_hover_delays_and_events_fire_once_at_the_release() -> None:
    log: list[str] = []
    m = started(extra=peek("DRAG"))
    real = m._fire
    m._fire = lambda s, key: (log.append(key), real(s, key))[1]  # type: ignore[method-assign]
    sim(m, "pointer_down", ON_TAB)
    sim(m, "pointer_move", (60, 40))
    sim(m, "pointer_move", (60, 44))
    assert log == []
    sim(m, "pointer_up", (60, 44))
    advance(m, 500)
    assert log == ["On_Open", "On_Anim_Start", "On_Anim_End", "On_Visible"]
    log.clear()
    sim(m, "pointer_down", FAR)
    sim(m, "pointer_move", (60, 30))
    sim(m, "pointer_up", (60, 30))
    advance(m, 500)
    assert log == ["On_Close", "On_Anim_Start", "On_Anim_End", "On_Hidden"]


def test_a_released_drag_takes_time_in_proportion_to_what_is_left() -> None:
    m = started(extra=peek("DRAG"))  # 400 ms
    sim(m, "pointer_down", ON_TAB)
    sim(m, "pointer_move", (60, 50))  # 24 of 28 px: 4 px left, 57 ms
    sim(m, "pointer_up", (60, 50))
    advance(m, 150)
    assert is_out(m)


def test_reduced_motion_settles_a_released_drag_at_once() -> None:
    m = started(extra=peek("DRAG"), reduced=True)
    sim(m, "pointer_down", ON_TAB)
    sim(m, "pointer_move", (60, 44))
    sim(m, "pointer_up", (60, 44))
    assert is_out(m) and host(m).anim is None
    assert px(m)(60, 59) == BLUE


def test_the_zones_are_unchanged_by_a_drag() -> None:
    m = started(extra=peek("DRAG"))
    st = only(m)
    zones = dict(st.zones)
    sim(m, "pointer_down", ON_TAB)
    for y in (30, 36, 44):
        sim(m, "pointer_move", (60, y))
        assert st.zones == zones
    sim(m, "pointer_up", (60, 44))
    advance(m, 500)
    assert st.zones == zones


@pytest.mark.parametrize("join", JOINS)
def test_a_drag_works_with_every_join_option(join: str) -> None:
    m = started(extra=peek("DRAG"), join=join)
    sim(m, "pointer_down", ON_TAB)
    sim(m, "pointer_move", (60, 34))
    sim(m, "pointer_move", (60, 40))
    assert abs(contour_edge(m) - 48) <= 1, contour_edge(m)  # 32 + 14 and the 2 px border
    sim(m, "pointer_up", (60, 40))
    advance(m, 500)
    assert is_out(m) and px(m)(60, 59) == BLUE and px(m)(60, 61) != BLUE


def test_a_join_that_cannot_follow_a_drag_warns_once_and_takes_param_for_a_strip() -> None:
    from tests.test_frame_peek_strip import started as strip_started

    seen: list[str] = []
    sink = logger.add(lambda message: seen.append(str(message)), level="WARNING")
    try:
        text = (
            'Frame { Name: F, Thickness: 20, Style { Background: "#0000ff" }, Edges { Top { '
            "Thickness: 34, Children { Rectangle { Name: Dot, Width: 50, Height: 10 } }, "
            "Peek { Size: 8, Trigger: DRAG } } } }"
        )
        m = strip_started(text, join="SHADER")
    finally:
        logger.remove(sink)
    assert type(next(iter(only(m).hosts.values())).join).__name__ == "ParamJoin"
    assert len([s for s in seen if "cannot follow a drag" in s]) == 1


# -- corner Panels: Slide_From -------------------------------------------------------------------


def corner_started(attach: str, alignment: str, peek_text: str, join: str = "PARAM") -> Any:
    """A Panel 120 x 40 in a corner of the 400 x 300 Frame (20 thick, 2 px border)."""
    from tess_shell.model.store import ValueStore
    from tess_shell.surfaces.manager import SurfaceManager
    from tests.test_frame import StubApp, look
    from tests.test_frame_strips import module, shell_of

    text = (
        f"Panel {{ Name: Tab, Meld: true, Attach_To: F, Attach: {attach}, Alignment: {alignment}, "
        f"Length: 120, Depth: 40, {peek_text}, Animation {{ Type: SLIDE, Duration: 400 }}, "
        'Children { Rectangle { Name: Dot, Width: 20, Height: 20, Fill: "#ff0000" } } }'
    )
    app = StubApp()
    m = SurfaceManager(app, module(), lambda key: key[-1], ValueStore(), look(), join_mode=join)  # type: ignore[arg-type]
    m.sink = lambda handler, key, raw: m.run_builtin(handler)
    m.plan(shell_of(RING, text))
    m.build()
    only(m).painter.resize(*app.size)
    only(m).painter.snapshot()
    return m


def test_a_top_right_panel_slides_out_of_the_right_edge_with_its_handle_on_it() -> None:
    m = corner_started("TOP", "END", "Peek { Size: 12, Slide_From: RIGHT, Trigger: CLICK }")
    h = host(m)
    assert h.plan.side == "right" and h.handle.side == "right"
    at = px(m)
    # the tab is 12 px wide against the right band, at the top end of it: x 368..380, y 20..60
    assert at(374, 24) == BLUE and at(363, 40) == NONE and at(300, 24) == NONE
    assert at(374, 62) != BLUE  # below the tab, the opening
    chevron = [(x, y) for x in range(368, 380) for y in range(30, 51) if at(x, y) != BLUE]
    assert chevron  # the handle is on the right edge's tab, at its middle (y = 40)
    assert abs(sum(y for _, y in chevron) / len(chevron) - 40) <= 2
    click(m, (374, 40))
    advance(m, 450)
    assert is_out(m)
    at = px(m)
    assert at(300, 24) == BLUE and at(250, 40) == NONE and at(300, 65) == NONE
    # the chevron points towards the right edge now, at the far (left) strip of the body
    moved = [(x, y) for x in range(260, 272) for y in range(30, 51) if at(x, y) != BLUE]
    assert moved and abs(sum(x for x, _ in moved) / len(moved) - 266) <= 3


def test_a_top_left_panel_can_slide_from_the_left_and_the_default_is_the_attached_edge() -> None:
    m = corner_started("TOP", "START", "Peek { Size: 12, Slide_From: LEFT }")
    assert host(m).plan.side == "left"
    at = px(m)
    assert at(25, 24) == BLUE and at(35, 24) != BLUE and at(25, 62) != BLUE
    point(m, (26, 40))
    advance(m, 151)
    advance(m, 450)
    assert is_out(m) and px(m)(100, 40) == BLUE and px(m)(100, 62) == NONE
    same = corner_started("TOP", "START", "Peek { Size: 12, Slide_From: TOP }")
    assert host(same).plan.side == "top" and px(same)(60, 26) == BLUE
    default = corner_started("TOP", "START", "Peek { Size: 12 }")
    assert host(default).plan.side == "top"


def test_the_dots_of_a_left_edge_tab_stand_in_a_column() -> None:
    m = corner_started("TOP", "START", "Peek { Size: 12, Slide_From: LEFT }")
    at = px(m)
    pts = [(x, y) for x in range(21, 31) for y in range(28, 52) if at(x, y) != BLUE]
    assert len(_runs(sorted({y for _, y in pts}))) == 3  # three dots one above the other
    assert max(x for x, _ in pts) - min(x for x, _ in pts) <= 4


@pytest.mark.parametrize(
    ("attach", "alignment", "edge", "tab", "inside"),
    [
        ("BOTTOM", "END", "RIGHT", (372, 244), (300, 244)),
        ("LEFT", "START", "TOP", (25, 25), (25, 100)),
        ("RIGHT", "END", "BOTTOM", (345, 276), (345, 200)),
    ],
)
def test_the_other_corners_slide_from_their_other_edge_too(
    attach: str, alignment: str, edge: str, tab: tuple[int, int], inside: tuple[int, int]
) -> None:
    m = corner_started(
        attach, alignment, f"Peek {{ Size: 12, Slide_From: {edge}, Trigger: CLICK }}"
    )
    assert host(m).plan.side == edge.lower()
    assert px(m)(*tab) == BLUE and px(m)(*inside) == NONE
    click(m, tab)
    advance(m, 450)
    assert is_out(m) and px(m)(*inside) == BLUE


def test_slide_from_does_not_change_what_the_frame_reserves() -> None:
    plain = corner_started("TOP", "END", "Peek { Size: 12 }")
    slid = corner_started("TOP", "END", "Peek { Size: 12, Slide_From: RIGHT }")
    assert only(plain).zones == only(slid).zones


# -- strips --------------------------------------------------------------------------------------


def strip_started(trigger: str, handle: str = "AUTO", size: int = 12, join: str = "PARAM") -> Any:
    from tests.test_frame_peek_strip import DOT
    from tests.test_frame_peek_strip import started as base

    text = (
        "Frame { Name: F, Thickness: 20, Inner_Radius: 8, "
        'Inner_Border { Width: 2, Color: "#00ff00" }, Style { Background: "#0000ff" }, '
        "Edges { Top { Thickness: 34, Name: Strip, Padding: [10, 8, 10, 8], "
        f"Children {{ {DOT} }}, "
        f"Peek {{ Size: {size}, Trigger: {trigger}, Handle: {handle} }} }} }} }}"
    )
    return base(text, join=join)


def test_a_strip_can_peek_by_click_with_a_chevron_on_its_sliver() -> None:
    m = strip_started("CLICK")
    h = next(iter(only(m).hosts.values()))
    assert h.handle.kind == "CHEVRON"
    at = px(m)
    chevron = [(x, y) for x in range(180, 220) for y in range(1, 11) if at(x, y) != BLUE]
    assert chevron and 3 <= sum(y for _, y in chevron) / len(chevron) <= 8
    click(m, (200, 6))
    advance(m, 300)
    assert next(iter(only(m).hosts.values())).anim is None
    assert "Strip" not in only(m).hidden_melds and px(m)(30, 12) == (255, 0, 0, 255)
    click(m, (200, 28))  # the far strip of the band: where the handle went
    advance(m, 300)
    assert "Strip" in only(m).hidden_melds


def test_a_strip_can_peek_by_drag_with_a_bar() -> None:
    m = strip_started("DRAG")
    h = next(iter(only(m).hosts.values()))
    assert h.handle.kind == "BAR"
    sim(m, "pointer_down", (200, 6))
    sim(m, "pointer_move", (200, 20))  # 14 of the 22 px: past half
    assert only(m).zones["top"] == 14
    at = px(m)
    assert at(200, 20) == BLUE and at(200, 28) != BLUE or at(200, 26) != BLUE
    sim(m, "pointer_up", (200, 20))
    advance(m, 300)
    assert "Strip" not in only(m).hidden_melds and px(m)(200, 33) == BLUE


def test_a_strips_sliver_thinner_than_the_handle_draws_none() -> None:
    m = strip_started("CLICK", size=8)
    assert next(iter(only(m).hosts.values())).handle is None  # 8 px: no chevron (12)
    assert next(iter(only(strip_started("HOVER", size=8)).hosts.values())).handle is not None


# -- reload --------------------------------------------------------------------------------------


def test_a_reload_changes_the_trigger_and_the_handle_and_keeps_the_state() -> None:
    from tests.test_frame_peek import RING as ring_text
    from tests.test_frame_peek import apply, panel

    m = started(extra=peek("HOVER"))
    assert host(m).handle.kind == "DOTS"
    act(m, "Show")
    advance(m, 450)
    apply(m, ring_text, panel(peek("CLICK")))
    assert host(m).handle.kind == "CHEVRON" and host(m).plan.peek.trigger == "CLICK"
    assert is_out(m)
    out = ink(m, 62, 47, 98, 61)
    assert out and centre_y(out, 79, 82) < centre_y(out, 72, 75) - 2  # towards the Frame
    apply(m, ring_text, panel(peek("CLICK", "NONE")))
    assert host(m).handle is None and is_out(m)
    assert not ink(m, 62, 47, 98, 61)


def test_a_new_theme_recolours_the_handle() -> None:
    m = started(extra=peek("DRAG"))
    colour = host(m).handle.colour
    assert colour == (0, 255, 0, 255)


def test_the_handle_goes_with_the_panel_when_it_is_fully_hidden() -> None:
    m = started(extra=peek("CLICK"), more="Visible: false")
    assert host(m).handle is not None and host(m).handle.holder.get("visible") is False
    act(m, "Show")
    advance(m, 450)
    assert host(m).handle.holder.get("visible") is True
    act(m, "Hide")
    advance(m, 450)
    assert host(m).handle.holder.get("visible") is False
