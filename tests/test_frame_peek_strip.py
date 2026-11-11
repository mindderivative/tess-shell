"""A strip with ``Peek``: at rest the side holds (and reserves) only a sliver of ``Size`` pixels and
its children are not shown; the pointer on the sliver for ``Enter_Delay`` pushes the strip out over
the windows to its whole ``Thickness`` (the reserved space does not change); leaving for
``Exit_Delay`` sends it back. The ring's contour follows (the body of the strip is a melded body
that runs the whole side). Headless like ``test_frame_peek``. The geometry: a 400 x 300 output, a
Frame 20 thick with a 2 px green border, a top strip 34 thick that rests as a 6 px sliver."""

from __future__ import annotations

from typing import Any

import pytest

from tess_shell.binder.model import Handler
from tess_shell.model.store import ValueStore
from tess_shell.surfaces.join import JOINS
from tess_shell.surfaces.manager import SurfaceManager
from tests.test_frame import StubApp, look, only
from tests.test_frame_strips import BG, BLUE, GREEN, NONE, RED, module, shell_of

DOT = 'Rectangle { Name: Dot, Width: 50, Height: 10, Fill: "#ff0000" }'
PEEK = "Peek { Size: 6, Enter_Delay: 100, Exit_Delay: 200 }"


def frame(side: str = "Top", peek: str = PEEK, name: str = "Name: Strip, ") -> str:
    thick = 34 if side in ("Top", "Bottom") else 40
    return (
        "Frame { Name: F, Thickness: 20, Inner_Radius: 8, "
        f'Inner_Border {{ Width: 2, Color: "#00ff00" }}, {BG}, Edges {{ {side} {{ '
        f"Thickness: {thick}, {name}Padding: [10, 8, 10, 8], Children {{ {DOT} }}"
        f"{', ' + peek if peek else ''} }} }} }}"
    )


def started(text: str | None = None, join: str = "PARAM") -> SurfaceManager:
    app, store = StubApp(), ValueStore()
    manager = SurfaceManager(
        app,
        module(),
        lambda key: key[-1],
        store,
        look(),
        join_mode=join,  # type: ignore[arg-type],
        blend_mode="SRGB",
    )
    manager.sink = lambda handler, key, raw: manager.run_builtin(handler)
    manager.plan(shell_of(text or frame()))
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


def act(manager: SurfaceManager, action: str, target: str = "Strip") -> None:
    manager.run_builtin(Handler(action, {"Target": target}, builtin=True))


def host(manager: SurfaceManager) -> Any:
    (h,) = only(manager).hosts.values()
    return h


def advance(manager: SurfaceManager, ms: int) -> None:
    only(manager).painter.advance(ms)


def point(manager: SurfaceManager, x: int, y: int) -> None:
    only(manager).painter.simulate("pointer_move", x=x, y=y)


def at_rest(manager: SurfaceManager) -> bool:
    return host(manager).anim is None and "Strip" in only(manager).hidden_melds


def is_out(manager: SurfaceManager) -> bool:
    return host(manager).anim is None and "Strip" not in only(manager).hidden_melds


def no_red(manager: SurfaceManager) -> bool:
    rgba, _, _ = only(manager).painter.snapshot()
    return all(tuple(rgba[i : i + 4]) != RED for i in range(0, len(rgba), 4))


def test_at_rest_only_the_sliver_shows_and_the_children_are_not_drawn() -> None:
    m = started()
    at = px(m)
    assert at(200, 5) == BLUE and at(200, 7) == GREEN and at(200, 12) == NONE  # 6 px, border
    assert no_red(m) and host(m).container.get("visible") is False
    assert at_rest(m)


def test_the_side_reserves_the_sliver_and_the_zones_never_change() -> None:
    m = started()
    st = only(m)
    zones = dict(st.zones)
    assert zones == {"left": 22, "top": 8, "right": 22, "bottom": 22}  # 6 + the 2 px border
    act(m, "Show")
    for ms in (1, 50, 50, 200):
        advance(m, ms)
        assert st.zones == zones
    act(m, "Hide")
    for ms in (1, 100, 300):
        advance(m, ms)
        assert st.zones == zones
    assert st.plan.ring.totals == (22, 8, 22, 22)


def test_the_pointer_on_the_sliver_pushes_the_strip_out_over_the_opening() -> None:
    m = started()
    point(m, 200, 3)
    advance(m, 99)
    assert at_rest(m)
    advance(m, 2)
    assert host(m).anim == "in"
    advance(m, 450)
    assert is_out(m)
    at = px(m)
    assert (
        at(200, 33) == BLUE and at(200, 35) == GREEN and at(200, 40) == NONE
    )  # 34, over the opening
    assert at(30, 12) == RED  # the strip's child, now shown
    assert at(200, 20) == BLUE  # where a window would be: the strip is drawn over it
    assert host(m).container.get("visible") is True


def test_leaving_sends_it_back_after_exit_delay_and_a_quick_in_out_does_nothing() -> None:
    m = started()
    point(m, 200, 3)
    advance(m, 50)
    point(m, 200, 150)
    advance(m, 1000)
    assert at_rest(m) and host(m).surface.generation == 0
    point(m, 200, 3)
    advance(m, 600)
    assert is_out(m)
    point(m, 200, 150)
    advance(m, 199)
    assert is_out(m)
    advance(m, 2)
    assert host(m).anim == "out"
    advance(m, 450)
    assert at_rest(m) and no_red(m) and px(m)(200, 20) == NONE


def test_moving_down_the_out_strip_to_its_lower_edge_is_not_leaving() -> None:
    m = started()
    point(m, 200, 3)
    advance(m, 600)
    point(m, 200, 20)  # over the body of the strip, below the sliver
    point(m, 200, 30)
    advance(m, 1000)
    assert is_out(m)


def test_the_strip_has_no_content_between_the_sliver_and_its_full_thickness_at_rest() -> None:
    m = started()
    assert px(m)(30, 12) == NONE  # at rest the opening is open: a window would show here
    h = host(m)
    got: list[Any] = []
    h.clip.on("pointer_down", lambda e: got.append(e.target))
    only(m).painter.simulate("pointer_down", x=200, y=20)  # not on the sliver
    assert got == []
    only(m).painter.simulate("pointer_down", x=200, y=3)
    assert len(got) == 1


def test_show_hide_and_toggle_by_the_strips_name() -> None:
    m = started()
    act(m, "Show")
    advance(m, 1)
    assert host(m).anim == "in"
    advance(m, 300)
    assert is_out(m)
    act(m, "Hide")
    advance(m, 300)
    assert at_rest(m)
    act(m, "Toggle")
    advance(m, 300)
    assert is_out(m)
    act(m, "Toggle")
    advance(m, 300)
    assert at_rest(m)
    assert "Strip" in m.frames.names()


def test_a_show_during_the_hide_turns_round() -> None:
    m = started()
    act(m, "Show")
    advance(m, 120)
    act(m, "Hide")
    assert host(m).anim == "out"
    advance(m, 10)
    act(m, "Show")
    assert host(m).anim == "in"
    advance(m, 400)
    assert is_out(m)


@pytest.mark.parametrize("side", ["Bottom", "Left", "Right"])
def test_a_strip_peeks_out_of_each_side(side: str) -> None:
    m = started(frame(side))
    rest = {"Bottom": (200, 297), "Left": (3, 150), "Right": (397, 150)}[side]
    inside = {"Bottom": (200, 280), "Left": (30, 150), "Right": (370, 150)}[side]
    assert px(m)(*rest) == BLUE and px(m)(*inside) == NONE
    point(m, *rest)
    advance(m, 101)
    advance(m, 450)
    assert is_out(m)
    assert px(m)(*inside) == BLUE
    point(m, 200, 150) if side != "Bottom" else point(m, 100, 100)
    advance(m, 201)
    advance(m, 450)
    assert at_rest(m) and px(m)(*inside) == NONE


def test_reduced_motion_switches_at_once() -> None:
    app, store = StubApp(), ValueStore()
    from tess_shell.appearance import Appearance

    quiet = look().with_appearance(Appearance(scheme="dark", reduced_motion=True))
    m = SurfaceManager(app, module(), lambda key: key[-1], store, quiet, blend_mode="SRGB")  # type: ignore[arg-type]
    m.sink = lambda handler, key, raw: m.run_builtin(handler)
    m.plan(shell_of(frame()))
    m.build()
    only(m).painter.resize(*app.size)
    point(m, 200, 3)
    advance(m, 101)
    assert is_out(m) and px(m)(30, 12) == RED
    point(m, 200, 150)
    advance(m, 201)
    assert at_rest(m) and no_red(m)


@pytest.mark.parametrize("join", JOINS)
def test_every_join_option_ends_the_strip_in_the_same_pixels(join: str) -> None:
    m = started(join=join)
    act(m, "Show")
    advance(m, 1)
    advance(m, 450)
    at = px(m)
    assert is_out(m) and at(200, 33) == BLUE and at(200, 35) == GREEN and at(30, 12) == RED
    act(m, "Hide")
    advance(m, 1)
    advance(m, 450)
    assert at_rest(m) and px(m)(200, 12) == NONE and no_red(m)


def test_a_strip_without_a_peek_is_unchanged_and_has_no_hover_box() -> None:
    m = started(frame(peek="", name=""))
    assert host(m).clip is None
    assert px(m)(30, 12) == RED and px(m)(200, 33) == BLUE and px(m)(200, 36) == NONE


def reload_to(m: SurfaceManager, text: str) -> None:
    checked = m.check(shell_of(text), module())
    assert checked is not None
    m.apply(checked[0], module(), checked[1])


def test_a_reload_keeps_the_strip_out_or_in() -> None:
    m = started()
    act(m, "Show")
    advance(m, 450)
    reload_to(m, frame().replace("Exit_Delay: 200", "Exit_Delay: 250"))
    assert is_out(m) and px(m)(30, 12) == RED
    act(m, "Hide")
    advance(m, 450)
    reload_to(m, frame())
    assert at_rest(m)


def test_a_reload_adds_or_removes_the_peek() -> None:
    m = started(frame(peek="", name=""))
    assert px(m)(200, 33) == BLUE  # a strip 34 thick
    reload_to(m, frame())
    assert at_rest(m) and px(m)(200, 12) == NONE and only(m).zones["top"] == 8
    reload_to(m, frame(peek="", name=""))
    assert host(m).clip is None and px(m)(200, 33) == BLUE and only(m).zones["top"] == 36


def test_a_peeking_strip_and_a_melded_panel_on_the_same_side_warn() -> None:
    from loguru import logger

    seen: list[str] = []
    sink = logger.add(lambda message: seen.append(str(message)), level="WARNING")
    try:
        panel = (
            "Panel { Name: Tab, Meld: true, Attach_To: F, Attach: TOP, Alignment: START, "
            "Length: 60, Depth: 20, Children { Spacer { } } }"
        )
        app, store = StubApp(), ValueStore()
        m = SurfaceManager(app, module(), lambda key: key[-1], store, look(), blend_mode="SRGB")  # type: ignore[arg-type]
        m.plan(shell_of(frame(), panel))
        m.build()
    finally:
        logger.remove(sink)
    assert any("Panel Tab melds into the top side" in s for s in seen)
