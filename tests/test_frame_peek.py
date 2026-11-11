"""A melded Panel that peeks: at rest only a tab of ``Size`` pixels is out of the Frame's edge (part
of the ring's one contour, with its fillets); the pointer staying on it for ``Enter_Delay`` brings
the whole body out, leaving for ``Exit_Delay`` sends it back. Headless: tre's own clock through
``Window.advance`` and the pointer through ``Window.simulate``. The geometry: a 400 x 300 output, a
Frame 20 thick with a 2 px green border, the body 120 x 40 against the top at x 20..140 and its
tab 12 px of it (so the tab ends at y 32 and the body at y 60)."""

from __future__ import annotations

from typing import Any

import pytest
from loguru import logger

from tess_shell.appearance import Appearance
from tess_shell.binder.model import Handler
from tess_shell.model.store import ValueStore
from tess_shell.surfaces.join import JOINS, nodes_of
from tess_shell.surfaces.manager import SurfaceManager
from tests.test_frame import StubApp, look, only
from tests.test_frame_strips import BG, BLUE, GREEN, NONE, module, shell_of

RING = (
    "Frame { Name: F, Thickness: 20, Inner_Radius: 8, "
    f'Inner_Border {{ Width: 2, Color: "#00ff00" }}, {BG} }}'
)
PEEK = "Peek { Size: 12, Enter_Delay: 150, Exit_Delay: 300 }"
ON_TAB = (60, 26)  # on the tab (y 20..32)
BELOW = (60, 45)  # where the body is when it is out, and nothing is at rest
AWAY = (300, 200)  # in the opening, far from the Panel


def panel(
    extra: str = PEEK, animation: str = "Animation { Type: SLIDE, Duration: 400 }", **kw: str
) -> str:
    keys = ", ".join(k for k in (extra.strip(), animation, kw.get("more", "")) if k)
    return (
        "Panel { Name: Tab, Meld: true, Attach_To: F, Attach: TOP, Alignment: START, "
        f"Length: 120, Depth: 40, {keys}, "
        'Children { Rectangle { Name: Dot, Width: 20, Height: 20, Fill: "#ff0000" } } }'
    )


def started(
    extra: str = PEEK,
    animation: str = "Animation { Type: SLIDE, Duration: 400 }",
    more: str = "",
    reduced: bool = False,
    join: str = "PARAM",
    frame: str = RING,
) -> SurfaceManager:
    app, store = StubApp(), ValueStore()
    theme_look = look()
    if reduced:
        theme_look = theme_look.with_appearance(Appearance(scheme="dark", reduced_motion=True))
    manager = SurfaceManager(
        app,
        module(),
        lambda key: key[-1],
        store,
        theme_look,
        join_mode=join,  # type: ignore[arg-type],
        blend_mode="SRGB",
    )
    manager.sink = lambda handler, key, raw: manager.run_builtin(handler)
    manager.plan(shell_of(frame, panel(extra, animation, more=more)))
    manager.build()
    st = only(manager)
    st.painter.resize(*app.size)
    st.painter.snapshot()
    return manager


def px(manager: SurfaceManager) -> Any:
    rgba, w, _ = only(manager).painter.snapshot()

    def at(x: int, y: int) -> tuple[int, ...]:
        i = (y * w + x) * 4
        return tuple(rgba[i : i + 4])

    return at


def act(manager: SurfaceManager, action: str) -> None:
    manager.run_builtin(Handler(action, {"Target": "Tab"}, builtin=True))


def host(manager: SurfaceManager) -> Any:
    return next(h for h in only(manager).hosts.values() if h.plan.name == "Tab")


def advance(manager: SurfaceManager, ms: int) -> None:
    only(manager).painter.advance(ms)


def point(manager: SurfaceManager, where: tuple[int, int]) -> None:
    """Move the pointer to ``where`` (the painter's own hit test says what it is over)."""
    only(manager).painter.simulate("pointer_move", x=where[0], y=where[1])


def at_rest(manager: SurfaceManager) -> bool:
    st = only(manager)
    return host(manager).anim is None and "Tab" in st.tab_melds


def is_out(manager: SurfaceManager) -> bool:
    st = only(manager)
    return host(manager).anim is None and not (st.tab_melds | st.hidden_melds)


# -- at rest ---------------------------------------------------------------------------------------


def test_at_rest_a_tab_of_size_pixels_is_part_of_the_ring_with_its_fillet_and_border() -> None:
    m = started()
    at = px(m)
    assert at(60, 31) == BLUE and at(60, 33) == GREEN and at(60, 36) == NONE  # 12 px, then border
    assert (
        at(60, 19) == BLUE and at(200, 21) == GREEN
    )  # the band; beside the tab, the border at y 20
    assert at_rest(m) and only(m).hidden_melds == set()
    st = only(m)
    body = st.shape.bodies[0]
    assert (body.x0, body.y0, body.x1, body.y1) == (20, 20, 140, 32)
    # the fillet (radius 8) where the tab meets the band: the corner is round, not square
    assert at(141, 22) == BLUE and at(141, 31) != BLUE  # filled in the corner, not above the tab


def test_the_tab_shows_no_content_and_the_hover_box_is_the_tab() -> None:
    m = started()
    h = host(m)
    assert h.container.get("visible") is False and h.surface.hidden
    assert (h.clip.get("left"), h.clip.get("top"), h.clip.get("width"), h.clip.get("height")) == (
        20,
        20,
        120,
        12,
    )


def test_the_fillets_of_the_tab_follow_the_dock_corner_radius_clamped_to_the_tab() -> None:
    """Inner_Radius 14 and the body's own Corner_Radius 12 do not fit a 24 px tab together
    (14 + 12 > 24): the tab has smaller radii and they grow as it comes out."""
    frame = RING.replace("Inner_Radius: 8", "Inner_Radius: 14")
    m = started(
        extra="Peek { Size: 24 }",
        more="Style { Corner_Radius: 12 }",
        frame=frame,
    )
    st = only(m)
    full = st.plan.ring_for(st.size, frozenset(), frozenset())
    tab = st.plan.ring_for(st.size, frozenset(), frozenset({"Tab"}))
    assert full.fill != tab.fill and tab.bodies[0].height == 24 and full.bodies[0].height == 40


def test_reserved_space_is_the_same_in_every_state() -> None:
    m = started()
    st = only(m)
    zones = dict(st.zones)
    totals = st.plan.ring.totals
    assert zones and sorted(zones.values()) == [22, 22, 22, 22] and totals == (22, 22, 22, 22)
    act(m, "Show")
    for ms in (1, 100, 100, 300):
        advance(m, ms)
        assert st.zones == zones
    act(m, "Hide")
    for ms in (1, 200, 300):
        advance(m, ms)
        assert st.zones == zones
    assert st.plan.ring.totals == totals and at_rest(m)


# -- hover -----------------------------------------------------------------------------------------


def test_the_pointer_on_the_tab_brings_the_body_out_after_enter_delay() -> None:
    m = started()
    point(m, ON_TAB)
    advance(m, 149)
    assert at_rest(m) and px(m)(60, 45) == NONE  # not yet
    advance(m, 2)
    assert host(m).anim == "in"
    advance(m, 450)
    assert is_out(m)
    at = px(m)
    assert at(60, 59) == BLUE and at(60, 61) == GREEN and at(60, 64) == NONE
    assert host(m).container.get("visible") is True and not host(m).surface.hidden


def test_the_body_comes_out_by_the_joins_contour_not_a_box_growing() -> None:
    """Half way the tab's bottom edge is between the two depths and the content is part way in."""
    m = started()
    point(m, ON_TAB)
    advance(m, 151)
    advance(m, 200)  # half of 400 ms (the easing is not linear: look at the middle only)
    at = px(m)
    edge = next(y for y in range(21, 70) if at(60, y) == NONE)
    assert 33 < edge < 62, edge
    assert host(m).anim == "in"
    assert any(n.get("visible") for n in nodes_of(host(m).join))


def test_leaving_sends_it_back_after_exit_delay() -> None:
    m = started()
    point(m, ON_TAB)
    advance(m, 600)
    assert is_out(m)
    point(m, AWAY)
    advance(m, 299)
    assert is_out(m)
    advance(m, 2)
    assert host(m).anim == "out"
    advance(m, 450)
    assert at_rest(m)
    assert px(m)(60, 45) == NONE and px(m)(60, 33) == GREEN


def test_a_quick_in_and_out_does_nothing() -> None:
    m = started()
    point(m, ON_TAB)
    advance(m, 100)
    point(m, AWAY)  # left before Enter_Delay ran out
    advance(m, 1000)
    assert at_rest(m)
    assert host(m).surface.generation == 0


def test_a_quick_out_and_in_keeps_it_out() -> None:
    m = started()
    point(m, ON_TAB)
    advance(m, 600)
    point(m, AWAY)
    advance(m, 200)
    point(m, BELOW)  # back on the body before Exit_Delay ran out
    advance(m, 1000)
    assert is_out(m)


def test_moving_from_the_tab_into_the_body_does_not_count_as_leaving() -> None:
    m = started(extra="Peek { Size: 12, Enter_Delay: 150, Exit_Delay: 0 }")
    point(m, ON_TAB)
    advance(m, 600)
    assert is_out(m)
    point(m, (60, 30))
    point(m, BELOW)
    point(m, ON_TAB)
    advance(m, 50)
    assert is_out(m)  # with an Exit_Delay of 0 a flicker of leave and enter would show here


def test_leaving_while_it_comes_out_turns_round_from_where_it_is() -> None:
    m = started(extra="Peek { Size: 12, Enter_Delay: 50, Exit_Delay: 100 }")
    point(m, ON_TAB)
    advance(m, 51)
    advance(m, 150)
    h = host(m)
    assert h.anim == "in"
    point(m, AWAY)
    advance(m, 98)  # still coming out: the delay has not run out
    assert h.anim == "in"
    travelled = h.mover.get("translate_y")
    advance(m, 3)
    assert h.anim == "out"
    assert abs(h.mover.get("translate_y") - travelled) < 4  # it did not jump
    advance(m, 500)
    assert at_rest(m)


def test_coming_back_while_it_goes_back_turns_round_after_enter_delay() -> None:
    m = started()
    act(m, "Show")
    advance(m, 450)
    act(m, "Hide")
    advance(m, 100)
    assert host(m).anim == "out"
    point(m, ON_TAB)
    advance(m, 151)
    assert host(m).anim == "in"
    advance(m, 500)
    assert is_out(m)


def test_hover_does_nothing_for_a_panel_that_is_fully_hidden() -> None:
    m = started(more="Visible: false")
    st = only(m)
    assert st.hidden_melds == {"Tab"} and st.tab_melds == set()
    assert host(m).clip.get("visible") is False  # nothing to hover: it takes no pointer
    assert px(m)(60, 26)[3] == 0 or px(m)(60, 26) == GREEN  # only the border of the opening
    point(m, ON_TAB)
    advance(m, 1000)
    assert only(m).hidden_melds == {"Tab"} and host(m).anim is None


# -- show, hide, toggle, events ------------------------------------------------------------------


def test_show_brings_it_fully_out_and_hide_back_to_the_tab() -> None:
    m = started()
    act(m, "Show")
    advance(m, 1)
    assert host(m).anim == "in"
    advance(m, 450)
    assert is_out(m) and px(m)(60, 59) == BLUE
    act(m, "Hide")
    advance(m, 450)
    assert at_rest(m) and px(m)(60, 31) == BLUE and px(m)(60, 45) == NONE


def test_show_and_hide_are_idempotent_and_toggle_flips() -> None:
    m = started()
    act(m, "Hide")  # already at the tab
    assert host(m).anim is None and host(m).surface.generation == 0
    act(m, "Toggle")
    advance(m, 450)
    assert is_out(m)
    act(m, "Show")
    assert host(m).anim is None
    act(m, "Toggle")
    advance(m, 450)
    assert at_rest(m)


def test_events_fire_in_order_for_a_hover_out_and_back() -> None:
    log: list[str] = []
    m = started()
    real = m._fire
    m._fire = lambda s, key: (log.append(key), real(s, key))[1]  # type: ignore[method-assign]
    point(m, ON_TAB)
    advance(m, 151)
    assert log == ["On_Open", "On_Anim_Start"]
    advance(m, 450)
    assert log == ["On_Open", "On_Anim_Start", "On_Anim_End", "On_Visible"]
    log.clear()
    point(m, AWAY)
    advance(m, 301)
    assert log == ["On_Close", "On_Anim_Start"]
    advance(m, 450)
    assert log == ["On_Close", "On_Anim_Start", "On_Anim_End", "On_Hidden"]


def test_hide_after_sends_the_body_back_to_the_tab_not_away() -> None:
    m = started(more="Hide_After: 500", animation="Animation { Type: NONE }")
    st = only(m)
    assert st.tab_melds == {"Tab"}  # a tab at start: no timer runs
    act(m, "Show")
    assert is_out(m)
    advance(m, 450)
    assert is_out(m)
    advance(m, 100)
    assert st.tab_melds == {"Tab"} and px(m)(60, 31) == BLUE and px(m)(60, 45) == NONE


def test_hide_after_waits_while_the_pointer_is_on_the_body() -> None:
    m = started(more="Hide_After: 500")
    act(m, "Show")
    advance(m, 450)
    point(m, BELOW)
    advance(m, 900)
    assert is_out(m)  # the timer ran out with the pointer on it
    point(m, AWAY)
    advance(m, 301)
    advance(m, 450)
    assert at_rest(m)


def test_with_visible_false_hide_goes_back_to_nothing_not_to_the_tab() -> None:
    m = started(more="Visible: false")
    st = only(m)
    act(m, "Show")
    advance(m, 450)
    assert is_out(m)
    act(m, "Hide")
    advance(m, 450)
    assert st.hidden_melds == {"Tab"} and st.tab_melds == set()
    assert px(m)(60, 26) == NONE and px(m)(60, 45) == NONE


def test_a_panel_without_a_peek_is_unchanged() -> None:
    m = started(extra="")
    st = only(m)
    assert st.tab_melds == set() and st.hidden_melds == set()
    act(m, "Hide")
    advance(m, 450)
    assert st.hidden_melds == {"Tab"} and px(m)(60, 45) == NONE and px(m)(60, 31) == NONE


# -- reduced motion, no animation -------------------------------------------------------------


def test_reduced_motion_switches_at_once_after_the_delays() -> None:
    m = started(reduced=True)
    point(m, ON_TAB)
    advance(m, 149)
    assert at_rest(m)
    advance(m, 2)
    assert is_out(m) and host(m).anim is None and px(m)(60, 59) == BLUE
    point(m, AWAY)
    advance(m, 301)
    assert at_rest(m) and px(m)(60, 45) == NONE


@pytest.mark.parametrize("animation", ["Animation { Type: NONE }", "Animation { Duration: 0 }"])
def test_without_an_animation_it_switches_at_once(animation: str) -> None:
    m = started(animation=animation)
    act(m, "Show")
    assert is_out(m) and px(m)(60, 59) == BLUE
    act(m, "Hide")
    assert at_rest(m) and px(m)(60, 45) == NONE


def test_fade_peeks_by_the_contour_like_slide() -> None:
    m = started(animation="Animation { Type: FADE, Duration: 400 }")
    act(m, "Show")
    advance(m, 1)
    assert host(m).kind == "SLIDE"
    advance(m, 450)
    assert is_out(m)


# -- hit shape -------------------------------------------------------------------------------------


def hits(m: SurfaceManager, where: tuple[int, int]) -> list[Any]:
    seen: list[Any] = []
    root = only(m).painter.root
    root.on("pointer_down", lambda e: seen.append(e.target))
    only(m).painter.simulate("pointer_down", x=where[0], y=where[1])
    root.off("pointer_down")
    return seen


def test_a_click_on_the_tab_reaches_the_panel_and_beside_it_does_not() -> None:
    m = started()
    h = host(m)
    on_clip: list[Any] = []
    h.clip.on("pointer_down", lambda e: on_clip.append(e.target))
    only(m).painter.simulate("pointer_down", x=ON_TAB[0], y=ON_TAB[1])
    assert len(on_clip) == 1
    only(m).painter.simulate("pointer_down", x=BELOW[0], y=BELOW[1])  # under the tab: nothing
    assert len(on_clip) == 1
    only(m).painter.simulate("pointer_down", x=200, y=26)  # beside the tab, in the opening
    assert len(on_clip) == 1


def test_clicks_reach_the_body_when_it_is_out_and_the_tab_content_takes_none() -> None:
    m = started()
    act(m, "Show")
    advance(m, 450)
    h = host(m)
    got: list[Any] = []
    h.clip.on("pointer_down", lambda e: got.append(e.target))
    only(m).painter.simulate("pointer_down", x=BELOW[0], y=BELOW[1])
    assert len(got) == 1


# -- the join options ------------------------------------------------------------------------------


@pytest.mark.parametrize("join", JOINS)
def test_every_join_option_draws_the_peek_and_ends_in_the_same_pixels(join: str) -> None:
    m = started(join=join)
    point(m, ON_TAB)
    advance(m, 151)
    advance(m, 1)
    assert host(m).anim == "in"
    advance(m, 80)
    assert any(px(m)(60, y) == NONE for y in range(33, 70))
    advance(m, 500)
    end = px(m)
    assert end(60, 59) == BLUE and end(60, 61) == GREEN and end(60, 64) == NONE
    assert is_out(m)


@pytest.mark.parametrize("join", ["SHADER", "CONCAVE"])
def test_a_join_that_cannot_start_from_a_tab_warns_once_and_draws_with_param(join: str) -> None:
    seen: list[str] = []
    sink = logger.add(lambda message: seen.append(str(message)), level="WARNING")
    try:
        m = started(join=join)
        n = [s for s in seen if "cannot draw a Panel that peeks" in s]
        assert len(n) == 1 and join in n[0] and "PARAM" in n[0]
        assert type(host(m).join).__name__ == "ParamJoin"
        # a second Frame with a peek (a second manager) in one run warns once per option
    finally:
        logger.remove(sink)


def test_a_peek_less_panel_keeps_its_own_join_option() -> None:
    m = started(extra="", join="SHADER")
    assert type(host(m).join).__name__ == "ShaderJoin"


@pytest.mark.parametrize("join", JOINS)
def test_the_last_frame_of_the_peek_matches_the_ring_after_the_swap(join: str) -> None:
    m = started(join=join)
    act(m, "Show")
    advance(m, 1)
    advance(m, 399)
    st = only(m)
    before, _, _ = st.painter.snapshot()
    advance(m, 50)
    after, _, _ = st.painter.snapshot()
    diff = sum(1 for i in range(0, len(before), 4) if before[i : i + 4] != after[i : i + 4])
    assert diff <= 60, f"{diff} pixels changed at the swap"


# -- reload and size ------------------------------------------------------------------------------


def apply(manager: SurfaceManager, frame: str, panel_text: str) -> None:
    checked = manager.check(shell_of(frame, panel_text), module())
    assert checked is not None
    manager.apply(checked[0], module(), checked[1])


def test_a_reload_keeps_the_state_out_or_tab() -> None:
    m = started()
    act(m, "Show")
    advance(m, 450)
    apply(m, RING.replace("Width: 2", "Width: 2, "), panel())
    assert is_out(m)
    act(m, "Hide")
    advance(m, 450)
    apply(m, RING, panel())
    assert at_rest(m) and px(m)(60, 31) == BLUE


def test_a_reload_that_changes_the_size_redraws_the_tab() -> None:
    m = started()
    apply(m, RING, panel("Peek { Size: 20 }"))
    assert at_rest(m) and px(m)(60, 39) == BLUE and px(m)(60, 41) == GREEN


def test_a_reload_that_removes_the_peek_shows_the_panel_and_one_that_adds_it_keeps_it_shown() -> (
    None
):
    m = started()
    apply(m, RING, panel(""))
    st = only(m)
    assert st.tab_melds == set() and st.hidden_melds == set() and px(m)(60, 59) == BLUE
    apply(m, RING, panel(PEEK))
    assert st.tab_melds == set() and px(m)(60, 59) == BLUE  # as the run left it
    act(m, "Hide")
    advance(m, 450)
    assert at_rest(m)


def test_a_reload_that_flips_visible_is_decided_by_the_file() -> None:
    m = started()
    apply(m, RING, panel(more="Visible: false"))
    assert only(m).hidden_melds == {"Tab"} and only(m).tab_melds == set()
    assert px(m)(60, 26) == NONE
    apply(m, RING, panel())
    assert at_rest(m)


def test_a_new_output_size_keeps_the_state_and_redraws() -> None:
    app, store = StubApp(), ValueStore()
    manager = SurfaceManager(app, module(), lambda key: key[-1], store, look(), blend_mode="SRGB")  # type: ignore[arg-type]
    manager.sink = lambda handler, key, raw: manager.run_builtin(handler)
    manager.plan(shell_of(RING, panel()))
    manager.build()
    st = only(manager)
    st.painter.resize(*app.size)
    act(manager, "Show")
    advance(manager, 450)
    app.size = (500, 320)
    plans = manager._frame_plans
    assert plans  # the stub app owns the size; a sync with the same plans keeps everything
    manager.frames.sync(plans)
    assert is_out(manager)


def test_the_frame_hidden_and_shown_again_keeps_the_panels_rest_state() -> None:
    m = started()
    m.run_builtin(Handler("Hide", {"Target": "F"}, builtin=True))
    assert only(m).hosts == {}
    act(m, "Show")  # no window: the state is set for when the Frame is back
    m.run_builtin(Handler("Show", {"Target": "F"}, builtin=True))
    assert is_out(m)
    m.run_builtin(Handler("Hide", {"Target": "F"}, builtin=True))
    act(m, "Hide")
    m.run_builtin(Handler("Show", {"Target": "F"}, builtin=True))
    assert at_rest(m)


def test_hot_plug_keeps_the_other_monitors_peek_and_a_returning_monitor_starts_at_the_tab() -> None:
    from tests.test_hotplug import Out, make

    def side(name: str, ring: str) -> str:
        return (
            f"Frame {{ Name: {ring}, Thickness: [20, 20, 20, 20] }}\n"
            f"Panel {{ Name: {name}, Meld: true, Attach_To: {ring}, Attach: TOP, "
            "Alignment: START, Length: 80, Depth: 40, Peek { Size: 10 }, "
            "Animation { Type: NONE }, Children { FlexBox { } } }\n"
        )

    text = (
        "Shell {\n"
        "Monitor { Name: Main, Connector: HDMI-A-1, Children { "
        f"{side('Dock_A', 'Ring_A')} }} }}\n"
        f"Monitor {{ Name: Side, Index: 1, Children {{ {side('Dock_B', 'Ring_B')} }} }}\n"
        "}\n"
    )
    r = make(text)
    frames = r.manager.frames
    a, b = frames.states["Main_Shell.Main.Ring_A"], frames.states["Main_Shell.Side.Ring_B"]
    assert a.tab_melds == {"Dock_A"} and b.tab_melds == {"Dock_B"}
    frames.run("Show", "Dock_A")
    frames.run("Show", "Dock_B")
    assert a.tab_melds == set() and b.tab_melds == set()
    r.app.unplug("DP-1")
    assert frames.states["Main_Shell.Main.Ring_A"] is a and a.tab_melds == set()  # untouched
    r.app.plug(Out("DP-1", 600, 400, 0, 800))
    back = frames.states["Main_Shell.Side.Ring_B"]
    assert back.tab_melds == {"Dock_B"} and back.hidden_melds == set()  # a new one: at its tab
    host = next(iter(back.hosts.values()))
    assert host.surface.hidden and host.container.get("visible") is False


@pytest.mark.parametrize("join", JOINS)
def test_the_fillets_stay_round_at_every_frame_of_a_peek(join: str) -> None:
    """The join where the body meets the band keeps a fillet from the tab to the whole body (a
    blend of the tab's contour and the body's, not a body that grows from nothing): count the
    painted pixels in the corner a round fillet fills and a square one leaves empty."""
    frame = RING.replace("Inner_Radius: 8", "Inner_Radius: 14")
    m = started(
        extra="Peek { Size: 24, Enter_Delay: 50, Exit_Delay: 100 }",
        more="Style { Corner_Radius: 12 }",
        frame=frame,
        join=join,
    )

    def corner() -> int:
        at = px(m)
        return sum(at(x, y) != NONE for x in range(143, 154) for y in range(23, 34))

    rest = corner()
    point(m, (60, 26))
    advance(m, 51)
    seen = []
    for _ in range(8):
        advance(m, 30)
        seen.append(corner())
    advance(m, 300)
    whole = corner()
    assert whole >= 20 and rest >= 20, (rest, whole)  # a square corner leaves none of them
    assert all(n >= 20 for n in seen), seen


@pytest.mark.parametrize(
    ("side", "tab", "body_only", "leave"),
    [
        ("BOTTOM", (60, 274), (60, 255), (300, 100)),
        ("LEFT", (26, 60), (45, 60), (300, 200)),
        ("RIGHT", (374, 60), (355, 60), (100, 200)),
    ],
)
def test_a_tab_peeks_out_of_each_side(
    side: str, tab: tuple[int, int], body_only: tuple[int, int], leave: tuple[int, int]
) -> None:
    app, store = StubApp(), ValueStore()
    m = SurfaceManager(app, module(), lambda key: key[-1], store, look(), blend_mode="SRGB")  # type: ignore[arg-type]
    m.sink = lambda handler, key, raw: m.run_builtin(handler)
    m.plan(shell_of(RING, panel().replace("Attach: TOP", f"Attach: {side}")))
    m.build()
    only(m).painter.resize(*app.size)
    assert px(m)(*tab) == BLUE and px(m)(*body_only) == NONE  # the tab: 12 px of the body
    point(m, tab)
    advance(m, 151)
    advance(m, 450)
    assert is_out(m) and px(m)(*body_only) == BLUE
    point(m, leave)
    advance(m, 301)
    advance(m, 450)
    assert at_rest(m) and px(m)(*body_only) == NONE and px(m)(*tab) == BLUE


def test_the_body_stays_out_while_a_popup_hanging_off_it_is_open() -> None:
    """The pointer in a Popup has left the painter; going back would close the Popup."""
    m = started()
    point(m, ON_TAB)
    advance(m, 600)
    assert is_out(m)
    point(m, AWAY)
    h = host(m)

    class Open:
        parent = h.surface

    m.popups.current = Open()  # type: ignore[assignment]
    advance(m, 301)
    advance(m, 1000)
    assert is_out(m)  # it waits as long as the Popup is open
    m.popups.current = None
    advance(m, 301)
    assert h.anim == "out"
    advance(m, 450)
    assert at_rest(m)
