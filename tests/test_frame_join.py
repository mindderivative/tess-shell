"""The ways of drawing a melded Panel's join (``Debug { Frame_Join }``) against one another: every
option starts where the ring is, ends in the ring's single contour, follows the same frames as the
SMIL morph, turns round without a jump, takes clicks by the contour (not through the body, not in
a notch) and draws nothing once it is done. Headless, with ``Window.advance``."""

from __future__ import annotations

import pytest
from loguru import logger

from tess_shell.model.store import ValueStore
from tess_shell.surfaces.join import JOINS, nodes_of
from tess_shell.surfaces.manager import SurfaceManager
from tests.test_frame import StubApp, look, only
from tests.test_frame_anim import BLUE, NONE, RING, act, advance, host, started
from tests.test_frame_strips import module, shell_of

OTHERS = [j for j in JOINS if j != "SMIL"]


def popped(a: bytes, b: bytes, levels: int = 40) -> int:
    """How many pixels differ between two snapshots by more than ``levels`` in some channel."""
    return sum(
        1 for i in range(0, len(a), 4) if max(abs(a[i + k] - b[i + k]) for k in range(4)) > levels
    )


def shot(m: SurfaceManager, scale: float = 1.0) -> bytes:
    return only(m).painter.snapshot(scale=scale)[0]  # type: ignore[no-any-return]


def scene(
    join: str, side: str = "TOP", alignment: str = "START", depth: int = 40
) -> SurfaceManager:
    """A hidden body of 120 x ``depth`` on ``side`` of the 400 x 300 ring."""
    app, store = StubApp(), ValueStore()
    manager = SurfaceManager(
        app,  # type: ignore[arg-type]
        module(),
        lambda key: key[-1],
        store,
        look(),
        join_mode=join,
        blend_mode="SRGB",
    )
    manager.sink = lambda handler, key, raw: manager.run_builtin(handler)
    panel = (
        f"Panel {{ Name: Tab, Meld: true, Attach_To: F, Attach: {side}, Alignment: {alignment}, "
        f"Length: 120, Depth: {depth}, Visible: false, Style {{ Corner_Radius: 8 }}, "
        "Animation { Type: SLIDE, Duration: 400 }, "
        'Children { Rectangle { Name: Dot, Width: 20, Height: 20, Fill: "#ff0000" } } }'
    )
    manager.plan(shell_of(RING, panel))
    manager.build()
    st = only(manager)
    st.painter.resize(*app.size)
    st.painter.snapshot()
    return manager


@pytest.mark.parametrize("scale", [1.0, 1.5])
@pytest.mark.parametrize("show", [True, False])
@pytest.mark.parametrize("join", JOINS)
def test_every_join_starts_where_the_ring_is_and_ends_in_its_contour(
    join: str, show: bool, scale: float
) -> None:
    m = started(visible="Visible: false" if show else "", join=join)
    at_rest = shot(m, scale)
    act(m, "Show" if show else "Hide")
    assert popped(at_rest, shot(m, scale)) <= 30, "the first frame is not the ring"
    advance(m, 1)  # a shader's animation starts on the frame after the request
    advance(m, 398)
    last = shot(m, scale)
    advance(m, 60)
    assert popped(last, shot(m, scale)) <= 30, "the swap to the ring's contour pops"
    assert host(m).anim is None and not any(n.get("visible") for n in nodes_of(host(m).join))


@pytest.mark.parametrize("join", JOINS)
def test_a_turn_round_does_not_jump_and_ends_hidden(join: str) -> None:
    m = started(visible="Visible: false", join=join)
    act(m, "Show")
    advance(m, 1)
    advance(m, 150)
    before = shot(m)
    act(m, "Hide")
    assert popped(before, shot(m)) <= 30, "the turn-round jumped"
    advance(m, 1)
    advance(m, 20)
    mid = shot(m)
    act(m, "Show")  # and round again
    assert popped(mid, shot(m)) <= 30
    advance(m, 1)
    advance(m, 450)
    assert px_at(m, 60, 50) == BLUE and host(m).anim is None
    act(m, "Hide")
    advance(m, 1)
    advance(m, 450)
    assert px_at(m, 60, 50) == NONE and "Tab" in only(m).hidden_melds


def px_at(m: SurfaceManager, x: int, y: int) -> tuple[int, ...]:
    rgba, w, _ = only(m).painter.snapshot()
    i = (y * w + x) * 4
    return tuple(rgba[i : i + 4])


CASES = [
    ("TOP", "CENTER"),
    ("TOP", "START"),
    ("TOP", "END"),
    ("BOTTOM", "CENTER"),
    ("LEFT", "END"),
    ("RIGHT", "START"),
]


@pytest.mark.parametrize("show", [True, False])
@pytest.mark.parametrize(("side", "alignment"), CASES)
@pytest.mark.parametrize("join", OTHERS)
def test_every_join_draws_the_frames_of_the_smil_morph(
    join: str, side: str, alignment: str, show: bool
) -> None:
    """The reference is the SMIL build; the others differ only by the anti-aliasing of the edge
    (a few hundred pixels of 120 000 differ by more than 60 levels, thousands would be a shape)."""
    frames: dict[str, list[bytes]] = {}
    for name in ("SMIL", join):
        m = scene(name, side, alignment)
        if not show:
            act(m, "Show")
            advance(m, 1)
            advance(m, 450)
        act(m, "Show" if show else "Hide")
        advance(m, 1)
        taken = []
        for ms in (99, 100, 100):  # 25, 50 and 75 % of 400 ms
            advance(m, ms)
            taken.append(shot(m))
        frames[name] = taken
    for ref, got in zip(frames["SMIL"], frames[join], strict=True):
        assert popped(ref, got, 60) <= 450


@pytest.mark.parametrize("join", JOINS)
def test_clicks_follow_the_contour_at_the_end_and_never_go_through_a_notch(join: str) -> None:
    m = started(visible="Visible: false", join=join)
    st = only(m)
    taken: list[str] = []
    for name, node in [("ring", n) for n in st.nodes] + [("body", host(m).clip)]:
        node.on("pointer_down", lambda e, name=name: taken.append(name))
    act(m, "Show")
    advance(m, 1)
    advance(m, 450)

    def click(x: int, y: int) -> list[str]:
        taken.clear()
        st.painter.simulate("pointer_down", x=x, y=y)
        return list(taken)

    # body 120 x 40 at x 20..140, y 20..60, join radius 10 on its right: the notch at (149, 29)
    assert click(80, 40) == ["body"]
    assert click(10, 100) == ["ring"]
    assert click(100, 150) == []  # the opening
    assert click(149, 29) == []  # in the notch of the join: the click falls through
    assert click(141, 21) != []  # in the join's corner: the ring
    advance(m, 1)
    act(m, "Hide")
    advance(m, 1)
    advance(m, 150)
    assert click(149, 29) == [] and click(300, 150) == []  # nor while it is moving


@pytest.mark.parametrize("join", JOINS)
def test_a_join_is_made_by_name(join: str) -> None:
    kinds = {
        "SMIL": "SmilJoin",
        "CONCAVE": "ConcaveJoin",
        "SHADER": "ShaderJoin",
        "STRUCTURE": "StructureJoin",
        "PARAM": "ParamJoin",
    }
    assert type(host(started(join=join)).join).__name__ == kinds[join]


@pytest.mark.parametrize("join", ["CONCAVE", "SHADER"])
def test_a_body_as_deep_as_the_opening_is_shown_at_once_with_a_warning(join: str) -> None:
    """The boxes and the shader need the body's two far corners; a body that reaches the other
    band has none, so the Frame shows it without animating (and says so)."""
    m = scene(join, depth=300)
    seen: list[str] = []
    sink = logger.add(lambda message: seen.append(str(message)), level="WARNING")
    try:
        act(m, "Show")
    finally:
        logger.remove(sink)
    assert host(m).anim is None and "Tab" not in only(m).hidden_melds
    assert any("cannot draw this body" in line for line in seen)


@pytest.mark.parametrize("join", JOINS)
def test_a_body_across_the_whole_opening_has_two_flush_ends(join: str) -> None:
    app, store = StubApp(), ValueStore()
    m = SurfaceManager(
        app,  # type: ignore[arg-type]
        module(),
        lambda key: key[-1],
        store,
        look(),
        join_mode=join,
        blend_mode="SRGB",
    )
    panel = (
        "Panel { Name: Tab, Meld: true, Attach_To: F, Attach: TOP, Alignment: START, "
        "Length: 400, Depth: 40, Visible: false, Animation { Type: SLIDE, Duration: 400 }, "
        'Children { Rectangle { Name: Dot, Width: 20, Height: 20, Fill: "#ff0000" } } }'
    )
    m.sink = lambda handler, key, raw: m.run_builtin(handler)
    m.plan(shell_of(RING, panel))
    m.build()
    only(m).painter.resize(*app.size)
    act(m, "Show")
    advance(m, 1)
    advance(m, 200)
    assert px_at(m, 200, 40) == BLUE
    advance(m, 300)
    assert px_at(m, 200, 58) == BLUE and host(m).anim is None
