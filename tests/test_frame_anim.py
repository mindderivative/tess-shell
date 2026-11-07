"""A melded Panel's show and hide: SLIDE, FADE, events, Hide_After and turning round, run
headless with ``Window.advance`` (the animation is tre's, in the engine). Every test runs once
for each way of drawing the join (``Debug { Frame_Join }``): they must all do the same."""

from __future__ import annotations

from typing import Any

import pytest

from tess_shell.appearance import Appearance
from tess_shell.binder.model import Handler
from tess_shell.model.store import ValueStore
from tess_shell.surfaces.join import JOINS, nodes_of
from tess_shell.surfaces.manager import SurfaceManager
from tests.test_frame import StubApp, look, only
from tests.test_frame_strips import BG, BLUE, NONE, module, shell_of

RING = (
    "Frame { Name: F, Thickness: 20, Inner_Radius: 8, "
    f'Inner_Border {{ Width: 2, Color: "#00ff00" }}, {BG} }}'
)
GREEN = (0, 255, 0, 255)
CURRENT = {"join": "SMIL"}  # the join option the running test draws with


@pytest.fixture(autouse=True, params=JOINS)
def join_option(request: pytest.FixtureRequest) -> Any:
    CURRENT["join"] = request.param
    yield request.param
    CURRENT["join"] = "SMIL"


def drawn(h: Any) -> bool:
    """Whether the host's join still has a node on show."""
    return any(n.get("visible") for n in nodes_of(h.join))


def tab(extra: str = "", animation: str = "Animation { Type: SLIDE, Duration: 400 }") -> str:
    keys = ", ".join(k for k in (extra.strip(), animation) if k)
    return (
        "Panel { Name: Tab, Meld: true, Attach_To: F, Attach: TOP, Alignment: START, "
        f"Length: 120, Depth: 40, {keys}, "
        'Children { Rectangle { Name: Dot, Width: 20, Height: 20, Fill: "#ff0000" } } }'
    )


def started(
    extra: str = "",
    animation: str = "Animation { Type: SLIDE, Duration: 400 }",
    visible: str = "",
    reduced: bool = False,
    join: str | None = None,
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
        join_mode=join or CURRENT["join"],  # type: ignore[arg-type]
    )
    manager.sink = lambda handler, key, raw: manager.run_builtin(handler)
    manager.plan(shell_of(RING, tab(f"{visible} {extra}", animation)))
    manager.build()
    st = only(manager)
    st.painter.resize(*app.size)
    st.painter.snapshot()
    return manager


def px(manager: SurfaceManager) -> Any:
    st = only(manager)
    rgba, w, _ = st.painter.snapshot()

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


# the ring is 20 thick: the body is 120 x 40 against the top, x 20..140, y 20..60


def test_a_shown_body_slides_out_from_the_edge_and_reaches_the_ring_contour() -> None:
    m = started()
    # at rest it is part of the ring's one contour
    assert px(m)(60, 50) == BLUE and not drawn(host(m))
    act(m, "Hide")
    advance(m, 1)
    at = px(m)
    assert at(60, 50) == BLUE  # no pop at the start: it is still where it was
    advance(m, 200)
    at = px(m)
    assert at(60, 59) == NONE and at(60, 25) == BLUE  # half way: the bottom has come up
    advance(m, 400)
    at = px(m)
    assert at(60, 50) == NONE and at(60, 25) == NONE and at(60, 10) == BLUE
    assert host(m).anim is None and "Tab" in only(m).hidden_melds
    assert not drawn(host(m))


def test_showing_slides_the_body_out_and_ends_in_the_single_contour() -> None:
    m = started(visible="Visible: false")
    assert px(m)(60, 50) == NONE
    act(m, "Show")
    advance(m, 1)
    assert px(m)(60, 50) == NONE  # starts hidden behind the band: no pop
    advance(m, 200)
    mid = px(m)
    assert mid(60, 25) == BLUE and mid(60, 59) == NONE  # the body is half out
    advance(m, 400)
    end = px(m)
    assert end(60, 59) == BLUE and end(60, 61) == GREEN and end(60, 63) == NONE
    assert host(m).anim is None and "Tab" not in only(m).hidden_melds
    assert only(m).shape.bodies[0] is not None  # the ring's contour has the body again


def test_the_last_frame_of_the_slide_matches_the_ring_after_the_swap() -> None:
    m = started(visible="Visible: false")
    act(m, "Show")
    advance(m, 1)
    advance(m, 399)  # the last tick
    rgba_a, w, h = only(m).painter.snapshot()
    advance(m, 50)
    rgba_b, _, _ = only(m).painter.snapshot()
    diff = sum(1 for i in range(0, len(rgba_a), 4) if rgba_a[i : i + 4] != rgba_b[i : i + 4])
    assert diff <= 40, f"{diff} pixels changed at the swap"


def test_a_hide_during_a_show_turns_round_from_where_it_is() -> None:
    m = started(visible="Visible: false")
    act(m, "Show")
    advance(m, 200)
    travelled = host(m).mover.get("translate_y")
    act(m, "Hide")
    assert host(m).anim == "out"
    advance(m, 1)
    now = host(m).mover.get("translate_y")
    assert abs(now - travelled) < 4  # it did not jump
    advance(m, 400)
    assert host(m).anim is None and "Tab" in only(m).hidden_melds
    assert px(m)(60, 40) == NONE
    act(m, "Show")  # and shown again from hidden
    advance(m, 450)
    assert px(m)(60, 50) == BLUE


def test_show_and_hide_are_idempotent() -> None:
    m = started()
    act(m, "Show")  # already shown: nothing happens
    assert host(m).anim is None
    act(m, "Hide")
    gen = host(m).surface.generation
    act(m, "Hide")  # already hiding
    assert host(m).surface.generation == gen
    advance(m, 450)
    act(m, "Hide")
    assert host(m).anim is None


def test_fade_changes_opacity_and_the_ring_has_no_body_while_it_runs() -> None:
    m = started(animation="Animation { Type: FADE, Duration: 400 }", visible="Visible: false")
    act(m, "Show")
    advance(m, 1)
    assert px(m)(60, 50)[3] < 20  # starts transparent: no pop
    advance(m, 200)
    alpha = px(m)(60, 50)[3]
    assert 60 < alpha < 250 and px(m)(60, 50)[2] > 0  # half way: translucent
    advance(m, 400)
    assert px(m)(60, 50) == BLUE


@pytest.mark.parametrize("animation", ["", "Animation { Type: NONE }"])
def test_without_an_animation_it_is_instant(animation: str) -> None:
    m = started(animation=animation or "Animation { Type: NONE }")
    act(m, "Hide")
    assert px(m)(60, 50) == NONE and host(m).anim is None
    act(m, "Show")
    assert px(m)(60, 50) == BLUE


def test_reduced_motion_makes_it_instant() -> None:
    m = started(reduced=True)
    act(m, "Hide")
    assert px(m)(60, 50) == NONE and host(m).anim is None
    act(m, "Show")
    assert px(m)(60, 50) == BLUE


@pytest.mark.parametrize("side", ["bottom", "left", "right"])
def test_a_body_slides_out_of_each_edge(side: str) -> None:
    app, store = StubApp(), ValueStore()
    manager = SurfaceManager(app, module(), lambda key: key[-1], store, look())  # type: ignore[arg-type]
    panel = tab("Visible: false").replace("Attach: TOP", f"Attach: {side.upper()}")
    manager.plan(shell_of(RING, panel))
    manager.build()
    st = only(manager)
    st.painter.resize(*app.size)
    st.painter.snapshot()
    probe = {"bottom": (60, 260, 60, 235), "left": (30, 60, 55, 60), "right": (370, 60, 345, 60)}
    act(manager, "Show")
    advance(manager, 1)
    start = px(manager)
    x, y = probe[side][:2]
    assert start(x, y) == NONE
    advance(manager, 500)
    assert px(manager)(x, y) == BLUE
    assert host(manager).anim is None


def test_events_fire_in_order_and_after_the_animation() -> None:
    log: list[str] = []
    m = started()
    real = m._fire
    m._fire = lambda s, key: (log.append(key), real(s, key))[1]  # type: ignore[method-assign]
    act(m, "Hide")
    assert log == ["On_Close", "On_Anim_Start"]
    advance(m, 450)
    assert log == ["On_Close", "On_Anim_Start", "On_Anim_End", "On_Hidden"]
    log.clear()
    m.run_builtin(Handler("Toggle", {"Target": "Tab"}, builtin=True))
    assert log[:3] == ["On_Toggle", "On_Open", "On_Anim_Start"]
    advance(m, 450)
    assert log[-2:] == ["On_Anim_End", "On_Visible"]


def test_a_panels_own_event_handler_runs_the_shells_action() -> None:
    other = (
        "Panel { Name: Other, Meld: true, Attach_To: F, Attach: BOTTOM, Alignment: END,"
        " Length: 80, Depth: 30, Visible: false, Animation { Type: NONE } }"
    )
    app, store = StubApp(), ValueStore()
    manager = SurfaceManager(app, module(), lambda key: key[-1], store, look())  # type: ignore[arg-type]
    manager.sink = lambda handler, key, raw: manager.run_builtin(handler)
    manager.plan(shell_of(RING, tab("On_Hidden { Action: Show, Target: Other }") + other))
    manager.build()
    st = only(manager)
    st.painter.resize(*app.size)
    assert "Other" in st.hidden_melds
    act(manager, "Hide")
    advance(manager, 450)
    assert "Other" not in st.hidden_melds and "Tab" in st.hidden_melds


def test_hide_after_hides_the_body_by_a_timer_of_the_painter() -> None:
    m = started("Hide_After: 300", animation="Animation { Type: NONE }")
    st = only(m)
    assert "Tab" not in st.hidden_melds
    advance(m, 350)
    assert "Tab" in st.hidden_melds and px(m)(60, 50) == NONE
    act(m, "Show")
    advance(m, 200)
    act(m, "Show")  # shown again: the timer starts over
    advance(m, 200)
    assert "Tab" not in st.hidden_melds
    advance(m, 150)
    assert "Tab" in st.hidden_melds


def test_closing_the_frame_during_an_animation_stops_cleanly() -> None:
    m = started()
    act(m, "Hide")
    advance(m, 100)
    m.run_builtin(Handler("Hide", {"Target": "F"}, builtin=True))
    assert only(m).hosts == {}
    m.run_builtin(Handler("Show", {"Target": "F"}, builtin=True))
    assert host(m).anim is None


def test_a_click_cannot_reach_the_body_while_it_slides() -> None:
    m = started(visible="Visible: false")
    act(m, "Show")
    advance(m, 200)
    h = host(m)
    if CURRENT["join"] == "SMIL":
        assert h.join.svg.get("hit_testable") is False
    advance(m, 400)
    st = only(m)
    hits: list[str] = []
    h.clip.on("pointer_down", lambda e: hits.append("body"))
    st.painter.simulate("pointer_down", x=60, y=50)
    assert hits == ["body"]  # at rest the body takes the click: the Panel's box under it


def test_a_strips_blocks_are_never_drawn_over_by_a_body_that_animates_beneath() -> None:
    """Variant B of the KWin demo: the Dock grows out of the right band at its top end, under the
    top strip's rightmost block. The ring and the morph are drawn below the strips."""
    frame = (
        "Frame { Name: F, Thickness: [20, 30, 24, 20], Inner_Radius: 14,"
        ' Style { Background: "#0000ff" },'
        ' Inner_Border { Width: 2, Color: "#00ff00" }, Edges { Top { Children { FlexBox {'
        " Width: 100%, Justify_Content: END, Children { Rectangle { Name: Edge, Width: 40,"
        ' Height: 20, Fill: "#ff0000" } } } } } } }'
    )
    dock = (
        "Panel { Name: Tab, Meld: true, Attach_To: F, Attach: RIGHT, Alignment: START, Length: 120,"
        " Depth: 60, Animation { Type: SLIDE, Duration: 400 }, Visible: false,"
        " Style { Corner_Radius: 10 },"
        ' Children { Rectangle { Name: Dot, Width: 20, Height: 20, Fill: "#ffff00" } } }'
    )
    app, store = StubApp(), ValueStore()
    manager = SurfaceManager(app, module(), lambda key: key[-1], store, look())  # type: ignore[arg-type]
    manager.plan(shell_of(frame, dock))
    manager.build()
    st = only(manager)
    st.painter.resize(*app.size)
    act(manager, "Show")
    block = [
        (x, y) for x in range(362, 398) for y in range(2, 18)
    ]  # inside the 40 x 20 block at the right end
    for step in (1, 60, 60, 60, 60, 60, 60, 60):
        advance(manager, step)
        at = px(manager)
        assert all(at(x, y) == (255, 0, 0, 255) for x, y in block), "the strip block was drawn over"
    assert host(manager).anim is None


def test_the_ring_and_the_morph_are_below_the_strips_and_the_content_above_both() -> None:
    m = started(visible="Visible: false")
    h = host(m)
    st = only(m)
    act(m, "Show")
    advance(m, 50)
    assert st.nodes[1].get("z_index") < nodes_of(h.join)[0].get("z_index") < h.clip.get("z_index")


def test_while_sliding_the_ring_nodes_keep_the_shape_that_takes_clicks_at_alpha_one() -> None:
    m = started(visible="Visible: false")
    st = only(m)
    act(m, "Show")
    advance(m, 100)
    ghosted = host(m).join.ghost  # only the join that cannot take clicks needs it
    assert st.nodes[1].get("fill")[3] == (1 if ghosted else 255)
    assert st.nodes[2].get("fill")[3] == (1 if ghosted else 255)
    advance(m, 400)
    assert st.nodes[1].get("fill")[3] == 255 and not drawn(host(m))


def test_a_turn_round_retargets_the_svg_clock_from_where_it_is() -> None:
    m = started(visible="Visible: false")
    act(m, "Show")
    advance(m, 200)
    if CURRENT["join"] == "SMIL":
        mid = host(m).join.svg.get("svg_time")
    act(m, "Hide")
    advance(m, 1)
    if CURRENT["join"] == "SMIL":
        assert abs(host(m).join.svg.get("svg_time") - mid) < 0.05  # no jump
    advance(m, 450)
    assert host(m).anim is None and "Tab" in only(m).hidden_melds


def test_the_rest_contour_and_the_last_morph_frame_agree_at_a_fractional_scale() -> None:
    m = started(visible="Visible: false")
    act(m, "Show")
    advance(m, 1)  # a shader's animation starts on the frame after the request
    advance(m, 398)
    st = only(m)
    before, w, _ = st.painter.snapshot(scale=1.5)
    advance(m, 50)
    after, _, _ = st.painter.snapshot(scale=1.5)
    # a pixel that changes by more than 40 levels is a pop; the edge anti-aliasing of a shader
    # or of boxes differs a little from the path's, which stays under that
    differing = sum(
        1
        for i in range(0, len(before), 4)
        if max(abs(before[i + k] - after[i + k]) for k in range(4)) > 40
    )
    assert differing <= 30, f"{differing} device pixels changed at the swap"
