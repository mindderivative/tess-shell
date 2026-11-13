"""The content fade (Frame > Peek Triggers and Handles): the content of a melded Panel or a strip
fades with its slide, its opacity the slide's progress (0 collapsed or at the tab, 1 fully out) on
the slide's clock and easing, set in the same call as the contour while a drag follows the pointer.
``Content_Fade: false`` and reduced motion leave it opaque. ``Peek { Handle_Opacity }`` is the
handle's brightness at rest. Headless like ``test_frame_peek``: ``advance`` and ``simulate``, with
the ring drawn as paths (``SRGB``) and as one shader (``LINEAR``)."""

from __future__ import annotations

from typing import Any

import pytest

from tess_shell.appearance import Appearance
from tess_shell.binder.model import Handler
from tess_shell.model.store import ValueStore
from tess_shell.surfaces.manager import SurfaceManager
from tests.test_frame import StubApp, look, only
from tests.test_frame_peek import PEEK, RING, panel
from tests.test_frame_strips import BG, module, shell_of

ON_TAB = (60, 26)
CLICK = "Peek { Size: 12, Trigger: CLICK }"
BLENDS = ["SRGB", "LINEAR"]


def started(
    extra: str = CLICK,
    animation: str = "Animation { Type: SLIDE, Duration: 400 }",
    more: str = "",
    blend: str = "SRGB",
    reduced: bool = False,
    frame: str = RING,
) -> SurfaceManager:
    app, store = StubApp(), ValueStore()
    theme_look = look()
    if reduced:
        theme_look = theme_look.with_appearance(Appearance(scheme="dark", reduced_motion=True))
    m = SurfaceManager(
        app,  # type: ignore[arg-type]
        module(),
        lambda key: key[-1],
        store,
        theme_look,
        blend_mode=blend,
    )
    m.sink = lambda handler, key, raw: m.run_builtin(handler)
    m.plan(shell_of(frame, panel(extra, animation, more=more)))
    m.build()
    st = only(m)
    st.painter.resize(*app.size)
    st.painter.advance(1)
    st.painter.snapshot()
    return m


def host(m: SurfaceManager, name: str = "Tab") -> Any:
    return next(h for h in only(m).hosts.values() if h.plan.name == name)


def advance(m: SurfaceManager, ms: int) -> None:
    only(m).painter.advance(ms)


def sim(m: SurfaceManager, event: str, where: tuple[int, int], **kw: Any) -> None:
    only(m).painter.simulate(event, x=where[0], y=where[1], **kw)


def act(m: SurfaceManager, action: str, target: str = "Tab") -> None:
    m.run_builtin(Handler(action, {"Target": target}, builtin=True))


def opacity(m: SurfaceManager, name: str = "Tab") -> float:
    return float(host(m, name).mover.get("opacity"))


def progress(m: SurfaceManager) -> float:
    """How far the content has slid in: 1 - translate / away (the Panel is on the top side)."""
    h = host(m)
    away = h.away[1]
    return 1.0 - float(h.mover.get(h.away[0])) / away


# -- an animated slide ----------------------------------------------------------------------------


@pytest.mark.parametrize("blend", BLENDS)
def test_the_content_opacity_is_the_slides_progress_on_every_frame_of_a_show(blend: str) -> None:
    m = started(blend=blend)
    assert (only(m).linear is not None) == (blend == "LINEAR")  # the ring is the shader or paths
    act(m, "Show")
    advance(m, 1)
    seen = [opacity(m)]
    for _ in range(8):
        advance(m, 50)
        seen.append(opacity(m))
        assert abs(opacity(m) - progress(m)) < 0.03, (opacity(m), progress(m))
    assert seen[0] < 0.05 and seen == sorted(seen) and 0.2 < seen[3] < 0.95
    advance(m, 100)
    assert host(m).anim is None and opacity(m) == 1.0


@pytest.mark.parametrize("blend", BLENDS)
def test_a_hide_fades_the_content_out_with_the_slide_and_it_stays_hidden_in_the_tab(
    blend: str,
) -> None:
    m = started(blend=blend)
    act(m, "Show")
    advance(m, 450)
    act(m, "Hide")
    advance(m, 1)
    values = []
    for _ in range(7):
        advance(m, 50)
        values.append(opacity(m))
        assert abs(opacity(m) - progress(m)) < 0.03
    assert values == sorted(values, reverse=True) and values[0] > 0.5
    advance(m, 200)
    assert host(m).anim is None
    assert host(m).container.get("visible") is False  # nothing of it is shown in the tab


@pytest.mark.parametrize("blend", BLENDS)
def test_a_turn_round_keeps_the_content_with_the_contour(blend: str) -> None:
    m = started(blend=blend)
    act(m, "Show")
    advance(m, 1)
    advance(m, 150)
    at = opacity(m)
    act(m, "Hide")
    advance(m, 1)
    assert abs(opacity(m) - at) < 0.1  # it did not jump
    assert abs(opacity(m) - progress(m)) < 0.03
    advance(m, 500)
    assert host(m).anim is None


def test_a_plain_show_and_hide_of_a_panel_without_a_peek_fades_too() -> None:
    m = started(extra="", more="Visible: false")
    act(m, "Show")
    advance(m, 1)
    advance(m, 150)
    assert 0.05 < opacity(m) < 0.95 and abs(opacity(m) - progress(m)) < 0.03
    advance(m, 400)
    assert opacity(m) == 1.0
    act(m, "Hide")
    advance(m, 1)
    advance(m, 150)
    assert 0.05 < opacity(m) < 0.95


def test_a_fade_animation_still_fades_the_whole_body_as_before() -> None:
    m = started(
        extra="", more="Visible: false", animation="Animation { Type: FADE, Duration: 400 }"
    )
    act(m, "Show")
    advance(m, 1)
    advance(m, 200)
    assert 0.05 < opacity(m) < 0.95 and host(m).mover.get("translate_y") == 0


# -- a drag ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("blend", BLENDS)
def test_a_drag_sets_the_opacity_to_the_progress_in_the_same_call_as_the_contour(
    blend: str,
) -> None:
    m = started(extra="Peek { Size: 12, Trigger: DRAG }", blend=blend)
    sim(m, "pointer_down", ON_TAB)
    sim(m, "pointer_move", (60, 30))
    for y, p in ((30, 4 / 28), (40, 14 / 28), (54, 1.0), (33, 7 / 28)):
        sim(m, "pointer_move", (60, y))
        assert abs(opacity(m) - p) < 1e-6, (y, opacity(m), p)
        assert abs(progress(m) - p) < 1e-6  # the place and the opacity come from one value
    sim(m, "pointer_move", (60, 5))
    assert opacity(m) == 0.0
    sim(m, "pointer_up", (60, 5))
    advance(m, 500)
    assert host(m).container.get("visible") is False


@pytest.mark.parametrize("blend", BLENDS)
def test_a_released_drag_finishes_the_fade_with_the_contour(blend: str) -> None:
    m = started(extra="Peek { Size: 12, Trigger: DRAG }", blend=blend)
    sim(m, "pointer_down", ON_TAB)
    sim(m, "pointer_move", (60, 30))
    sim(m, "pointer_move", (60, 44))  # 18 of 28 px: past half
    sim(m, "pointer_up", (60, 44))
    start = opacity(m)
    advance(m, 1)
    advance(m, 60)
    assert start < opacity(m) < 1.0 and abs(opacity(m) - progress(m)) < 0.04
    advance(m, 400)
    assert opacity(m) == 1.0 and host(m).anim is None


# -- a strip --------------------------------------------------------------------------------------


STRIP = (
    "Frame { Name: F, Thickness: 20, Inner_Radius: 8, "
    f'Inner_Border {{ Width: 2, Color: "#00ff00" }}, {BG}, Edges {{ Top {{ Thickness: 34, '
    "Name: Strip, Padding: [10, 8, 10, 8], @FADE@Children { Rectangle { Name: Dot, Width: 50, "
    'Height: 10, Fill: "#ff0000" } }, Peek { Size: 6, Trigger: @TRIGGER@ } } } }'
)


def strip_started(fade: str = "", blend: str = "SRGB", trigger: str = "CLICK") -> SurfaceManager:
    app, store = StubApp(), ValueStore()
    m = SurfaceManager(
        app,  # type: ignore[arg-type]
        module(),
        lambda key: key[-1],
        store,
        look(),
        blend_mode=blend,
    )
    m.sink = lambda handler, key, raw: m.run_builtin(handler)
    m.plan(shell_of(STRIP.replace("@FADE@", fade).replace("@TRIGGER@", trigger)))
    m.build()
    only(m).painter.resize(*app.size)
    only(m).painter.advance(1)
    return m


@pytest.mark.parametrize("blend", BLENDS)
def test_a_strips_children_fade_with_their_strip(blend: str) -> None:
    m = strip_started(blend=blend)
    h = next(iter(only(m).hosts.values()))
    assert h.container.get("visible") is False  # collapsed: the children are not shown
    act(m, "Show", "Strip")
    advance(m, 1)
    values = []
    for _ in range(4):
        advance(m, 50)
        values.append(float(h.mover.get("opacity")))
    assert values == sorted(values) and 0.05 < values[1] < 0.95
    advance(m, 200)
    assert h.mover.get("opacity") == 1.0 and h.anim is None
    act(m, "Hide", "Strip")
    advance(m, 1)
    advance(m, 80)
    assert 0.05 < float(h.mover.get("opacity")) < 0.95


def test_a_strips_drag_fades_the_children_with_the_pointer() -> None:
    m = strip_started(trigger="DRAG")
    h = next(iter(only(m).hosts.values()))
    sim(m, "pointer_down", (200, 3))
    sim(m, "pointer_move", (200, 8))
    sim(m, "pointer_move", (200, 20))  # 17 of 28 px from the press
    assert abs(float(h.mover.get("opacity")) - 17 / 28) < 1e-6
    sim(m, "pointer_up", (200, 20))


# -- the opt-out, reduced motion -------------------------------------------------------------------


@pytest.mark.parametrize("blend", BLENDS)
def test_content_fade_false_keeps_the_content_opaque_through_a_slide_and_a_drag(
    blend: str,
) -> None:
    m = started(more="Content_Fade: false", blend=blend)
    act(m, "Show")
    advance(m, 1)
    for _ in range(4):
        advance(m, 60)
        assert opacity(m) == 1.0
        assert 0.0 < progress(m) < 1.0 or host(m).anim is None
    advance(m, 300)
    d = started(extra="Peek { Size: 12, Trigger: DRAG }", more="Content_Fade: false", blend=blend)
    sim(d, "pointer_down", ON_TAB)
    sim(d, "pointer_move", (60, 30))
    sim(d, "pointer_move", (60, 40))
    assert opacity(d) == 1.0 and 0.4 < progress(d) < 0.6
    sim(d, "pointer_up", (60, 40))


def test_a_strips_content_fade_false_keeps_its_children_opaque() -> None:
    m = strip_started(fade="Content_Fade: false, ")
    h = next(iter(only(m).hosts.values()))
    act(m, "Show", "Strip")
    advance(m, 1)
    advance(m, 80)
    assert h.mover.get("opacity") == 1.0


def test_reduced_motion_has_no_fade_a_slide_or_a_drag_switches_with_the_state() -> None:
    m = started(reduced=True)
    act(m, "Show")
    assert host(m).anim is None and opacity(m) == 1.0
    d = started(extra="Peek { Size: 12, Trigger: DRAG }", reduced=True)
    sim(d, "pointer_down", ON_TAB)
    sim(d, "pointer_move", (60, 30))
    sim(d, "pointer_move", (60, 40))
    assert opacity(d) == 1.0  # the body still follows the pointer, the content does not fade
    sim(d, "pointer_up", (60, 40))
    assert opacity(d) == 1.0


def test_animation_none_is_instant_with_no_fade() -> None:
    m = started(animation="Animation { Type: NONE }")
    act(m, "Show")
    assert host(m).anim is None and opacity(m) == 1.0


# -- input, idle ----------------------------------------------------------------------------------


def test_collapsed_content_is_not_shown_and_takes_no_input() -> None:
    m = started()
    h = host(m)
    got: list[Any] = []
    h.surface.view.nodes["Dot"].on("pointer_down", lambda e: got.append("dot"))
    sim(m, "pointer_down", ON_TAB)
    sim(m, "pointer_down", (30, 24))
    assert got == [] and h.container.get("visible") is False
    act(m, "Show")
    advance(m, 450)
    sim(m, "pointer_down", (30, 30))  # the Dot, 20 x 20 at the body's origin (20, 20)
    assert got == ["dot"]


@pytest.mark.parametrize("blend", BLENDS)
def test_nothing_is_animating_once_the_slide_is_over(blend: str) -> None:
    m = started(blend=blend)
    act(m, "Show")
    advance(m, 1)
    advance(m, 450)
    h = host(m)
    assert h.mover.get_target("opacity") == h.mover.get("opacity") == 1.0
    painter = only(m).painter
    before = painter.frame_stats()["frames"]
    advance(m, 2000)
    assert painter.frame_stats()["frames"] == before  # idle draws nothing


# -- Handle_Opacity -------------------------------------------------------------------------------


def test_handle_opacity_is_the_handles_rest_brightness_and_hover_raises_it() -> None:
    default = started()
    assert host(default).handle.holder.get("opacity") == pytest.approx(0.6)
    m = started(extra="Peek { Size: 12, Trigger: CLICK, Handle_Opacity: 0.25 }")
    h = host(m).handle
    assert h.holder.get("opacity") == pytest.approx(0.25) and h.rest == 0.25
    sim(m, "pointer_move", ON_TAB)
    advance(m, 200)
    assert h.holder.get("opacity") == pytest.approx(1.0)
    sim(m, "pointer_move", (300, 200))
    advance(m, 200)
    assert h.holder.get("opacity") == pytest.approx(0.25)


def test_handle_opacity_zero_and_one_are_taken_and_a_reload_changes_it() -> None:
    from tests.test_frame_peek import apply

    m = started(extra="Peek { Size: 12, Trigger: CLICK, Handle_Opacity: 1 }")
    assert host(m).handle.holder.get("opacity") == 1.0
    apply(m, RING, panel("Peek { Size: 12, Trigger: CLICK, Handle_Opacity: 0 }"))
    assert host(m).handle.holder.get("opacity") == 0.0
    apply(m, RING, panel(CLICK))
    assert host(m).handle.holder.get("opacity") == pytest.approx(0.6)


def test_the_handle_opacity_default_is_the_old_constant() -> None:
    from tess_shell.surfaces import handle

    assert handle.REST_OPACITY == 0.6 and PEEK  # PEEK: the file imports it for its parity check
