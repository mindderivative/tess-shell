"""The Frame's ring drawn in linear light (``Debug { Frame_Blend: LINEAR }``), headless: tre
blends a path's anti-aliased edge in sRGB, so a light 2 px border on a dark ring is thinner to the
eye on a curve than on a straight (``tests/kwin/repro_srgb_edge_blend.py``, TRE-REQ-015); the
shader build (``surfaces/frame_shader.py``) blends in linear light itself.

What it can fix, measured here: the border's outer edge (against the fill, which the shader
paints too) is right to 1 %. Its inner edge is against the opening, where the desktop is, and the
compositor blends that in sRGB whatever the shader writes, so a ring over a dark desktop keeps part
of the deficit (the ``test_over_a_dark_desktop`` numbers).
"""

from __future__ import annotations

import math
from typing import Any

import pytest
from loguru import logger

from tess_shell.appearance import Appearance
from tess_shell.binder.model import Handler
from tess_shell.model.store import ValueStore
from tess_shell.surfaces.manager import SurfaceManager
from tests.test_frame import StubApp, look, only
from tests.test_frame_strips import module, shell_of

LIGHT, DARK = (0x89, 0xB4, 0xFA), (0x1E, 0x1E, 0x2E)
FRAME = (
    "Frame { Name: F, Thickness: 24, Inner_Radius: 14, "
    'Inner_Border { Width: 2, Color: "#89b4fa" }, Style { Background: "#1e1e2e" } }'
)


def started(
    frame: str = FRAME,
    extra: str = "",
    blend: str = "LINEAR",
    join: str = "PARAM",
    size: tuple[int, int] = (400, 300),
) -> SurfaceManager:
    app, store = StubApp(), ValueStore()
    app.size = size
    manager = SurfaceManager(
        app,  # type: ignore[arg-type]
        module(),
        lambda key: key[-1],
        store,
        look(),
        join_mode=join,
        blend_mode=blend,
    )
    manager.sink = lambda handler, key, raw: manager.run_builtin(handler)
    manager.plan(shell_of(frame, extra))
    manager.build()
    st = only(manager)
    st.painter.resize(*app.size)
    st.painter.advance(1)
    st.painter.snapshot()
    return manager


def snap(manager: SurfaceManager, scale: float = 1.0) -> tuple[bytes, int, int]:
    shot: tuple[bytes, int, int] = only(manager).painter.snapshot(scale=scale)
    return shot


def pixel(shot: tuple[bytes, int, int], x: int, y: int) -> tuple[int, ...]:
    rgba, w, _ = shot
    i = (y * w + x) * 4
    return tuple(rgba[i : i + 4])


def lin(v: float) -> float:
    v /= 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def luminance(c: tuple[float, ...]) -> float:
    return 0.2126 * lin(c[0]) + 0.7152 * lin(c[1]) + 0.0722 * lin(c[2])


def over(shot: tuple[bytes, int, int], backdrop: tuple[int, int, int]) -> list[tuple[float, ...]]:
    """The snapshot over ``backdrop`` the way a compositor puts it there: straight alpha, in the
    encoded values."""
    rgba, w, h = shot
    out = []
    for i in range(0, w * h * 4, 4):
        a = rgba[i + 3] / 255
        out.append(tuple(rgba[i + k] * a + backdrop[k] * (1 - a) for k in range(3)))
    return out


def lit(c: tuple[float, ...], base: tuple[int, int, int], top: tuple[int, int, int]) -> float:
    """How far from ``base`` to ``top`` a pixel is, in linear-light luminance (0 to 1)."""
    return (luminance(c) - luminance(base)) / (luminance(top) - luminance(base))


def quarter(
    flat: list[tuple[float, ...]],
    width: int,
    scale: float,
    box: tuple[int, int],
    base: tuple[int, int, int],
) -> float:
    """The sum of ``lit`` over the corner square of logical px ``box`` (x0, x1), in logical px
    squared."""
    lo, hi = box
    total = 0.0
    for y in range(round(lo * scale), round(hi * scale)):
        for x in range(round(lo * scale), round(hi * scale)):
            total += lit(flat[y * width + x], base, LIGHT)
    return total / scale**2


RING_AREA = math.pi / 4 * (16**2 - 14**2)  # the border at the Frame's opening corner, in px^2
DISC_AREA = math.pi / 4 * 16**2  # what the opening corner holds of the lit region, in px^2
ARC = math.pi / 2 * 16  # the length of that corner's outer edge, in px


@pytest.mark.parametrize("scale", [1.0, 1.5])
def test_the_borders_outer_edge_loses_no_brightness_on_a_curve_where_the_paths_lose_it(
    scale: float,
) -> None:
    """Over a desktop that is the border's own colour the border's inner edge cannot show, so the
    corner's brightness (the sum of linear light over the corner square, in px^2) is the exact
    area of the lit disc less what the fill/border edge loses; divided by the edge's length that
    is the width the edge lost, in px: a few hundredths for the shader, more than a tenth for tre's
    paths."""
    lost = {}
    for blend in ("SRGB", "LINEAR"):
        shot = snap(started(blend=blend), scale)
        got = quarter(over(shot, LIGHT), shot[1], scale, (24, 40), DARK)
        lost[blend] = (DISC_AREA - got) / ARC
    assert abs(lost["LINEAR"]) < 0.02, lost
    assert lost["SRGB"] > 0.08, lost


@pytest.mark.parametrize(("scale", "paths", "shader"), [(1.0, 1.72, 1.86), (1.5, 1.82, 1.92)])
def test_over_a_dark_desktop_the_border_is_wider_on_a_curve_but_not_the_width_of_a_straight(
    scale: float, paths: float, shader: float
) -> None:
    """The real Frame: the border's inner edge is against the opening, which the compositor blends
    in sRGB however the pixel is written. A 2 px border measured as the sum of linear light over
    the opening corner (the desktop the ring's own dark): the paths give about 1.69 (1x) and
    1.79 (1.5x), the shader 1.88 and 1.93, a straight 2.00 in both."""
    width = {}
    for blend in ("SRGB", "LINEAR"):
        manager = started(blend=blend)
        shot = snap(manager, scale)
        flat = over(shot, DARK)
        width[blend] = 2 * quarter(flat, shot[1], scale, (24, 40), DARK) / RING_AREA
        straight = sum(
            lit(flat[y * shot[1] + x], DARK, LIGHT)
            for y in range(round(100 * scale), round(200 * scale))
            for x in range(round(24 * scale), round(26 * scale))
        ) / (100 * scale**2)
        assert straight == pytest.approx(2.0, abs=0.01), (blend, straight)
    assert width["SRGB"] < paths, width
    assert width["LINEAR"] > shader, width
    assert width["LINEAR"] < 2.02, width


def zones(manager: SurfaceManager, margin: float = 3.0) -> list[tuple[float, float, float, float]]:
    """Squares round every rounded corner of the ring's rectangles (logical px): where the two
    builds blend an edge differently."""
    con = only(manager).shape.contours
    boxes = []
    for rect, radii in (con.outer, con.fill, con.opening, con.inside):
        for (cx, cy), r in zip(
            ((rect.x0, rect.y0), (rect.x1, rect.y0), (rect.x1, rect.y1), (rect.x0, rect.y1)),
            radii,
            strict=True,
        ):
            if r > 0:
                reach = r + margin
                boxes.append((cx - reach, cy - reach, cx + reach, cy + reach))
    return boxes


def mismatches(
    a: tuple[bytes, int, int],
    b: tuple[bytes, int, int],
    scale: float,
    skip: list[tuple[float, float, float, float]],
    tolerance: int = 3,
) -> list[tuple[int, int, tuple[int, ...], tuple[int, ...]]]:
    out = []
    for y in range(a[2]):
        for x in range(a[1]):
            lx, ly = (x + 0.5) / scale, (y + 0.5) / scale
            if any(x0 <= lx <= x1 and y0 <= ly <= y1 for x0, y0, x1, y1 in skip):
                continue
            pa, pb = pixel(a, x, y), pixel(b, x, y)
            if max(abs(u - v) for u, v in zip(pa, pb, strict=True)) > tolerance:
                out.append((x, y, pa, pb))
    return out


ALL = (
    "Frame { Name: F, Thickness: [10, 20, 30, 40], Margin: 4, Corner_Radius: 12, "
    'Inner_Radius: 10, Outer_Border { Width: 2, Color: "#ff0000" }, '
    'Inner_Border { Width: 2, Color: "#00ff00" }, Style { Background: "#0000ff" } }'
)
OPEN = (
    "Frame { Name: F, Thickness: [10, 20, 0, 40], Margin: 4, Corner_Radius: 12, "
    'Inner_Radius: 10, Outer_Border { Width: 2, Color: "#ff0000" }, '
    'Inner_Border { Width: 2, Color: "#00ff00" }, Style { Background: "#0000ff" } }'
)
BARE = 'Frame { Name: F, Thickness: 12, Style { Background: "#336699" } }'


@pytest.mark.parametrize("scale", [1.0, 1.5])
@pytest.mark.parametrize(
    ("frame", "curved"),
    [(ALL, True), (OPEN, True), (BARE, False)],
    ids=["all", "open side", "fill"],
)
def test_at_rest_the_ring_is_the_path_ring_everywhere_but_at_the_curves(
    frame: str, curved: bool, scale: float
) -> None:
    """Colours, positions, margins, thicknesses and seams: every pixel that is not within 3 px of
    a rounded corner is the one the paths draw (to 3 levels; the edges of a straight run on the
    pixel grid are whole pixels)."""
    paths, shader = started(frame, blend="SRGB"), started(frame, blend="LINEAR")
    assert only(shader).linear is not None and only(paths).linear is None
    a, b = snap(paths, scale), snap(shader, scale)
    assert (a[1], a[2]) == (b[1], b[2])
    bad = mismatches(a, b, scale, zones(paths))
    assert not bad, f"{len(bad)} pixels differ, the first: {bad[:3]}"
    if curved:  # and the shader has the curves: a corner pixel is part way between
        assert any(0 < pixel(b, x, y)[3] < 255 for x in range(0, 20) for y in range(0, 20))


def test_the_reserved_zones_are_the_same_in_both_builds() -> None:
    paths, shader = started(ALL, blend="SRGB"), started(ALL, blend="LINEAR")
    want = {"left": 18, "top": 28, "right": 38, "bottom": 48}  # thickness, borders and margin
    assert only(paths).zones == only(shader).zones == want
    assert only(paths).plan.ring.totals == only(shader).plan.ring.totals
    assert set(only(paths).reservers) == set(only(shader).reservers)


# -- melded Panels: the body is a uniform of the shader --------------------------------------------

RING = (
    "Frame { Name: F, Thickness: 20, Inner_Radius: 8, "
    'Inner_Border { Width: 2, Color: "#00ff00" }, Style { Background: "#0000ff" } }'
)


def tab(
    alignment: str = "START",
    visible: bool = True,
    peek: str = "",
    animation: str = "Animation { Type: SLIDE, Duration: 400 }",
    depth: int = 40,
    name: str = "Tab",
) -> str:
    keys = ", ".join(k for k in (peek, animation, "" if visible else "Visible: false") if k)
    return (
        f"Panel {{ Name: {name}, Meld: true, Attach_To: F, Attach: TOP, Alignment: {alignment}, "
        f"Length: 120, Depth: {depth}, {keys}, Children {{ Rectangle {{ Name: {name}_Dot, "
        'Width: 20, Height: 20, Fill: "#ff0000" } } }'
    )


def act(manager: SurfaceManager, action: str, target: str = "Tab") -> None:
    manager.run_builtin(Handler(action, {"Target": target}, builtin=True))


def host(manager: SurfaceManager) -> Any:
    return next(h for h in only(manager).hosts.values() if h.plan.name == "Tab")


def advance(manager: SurfaceManager, ms: int) -> None:
    only(manager).painter.advance(ms)


def differing(a: tuple[bytes, int, int], b: tuple[bytes, int, int], levels: int = 60) -> int:
    """How many pixels differ by more than ``levels`` over a grey desktop (a nearly transparent
    pixel has a colour that does not show)."""
    count = 0
    for i in range(0, len(a[0]), 4):
        wa, wb = a[0][i + 3] / 255, b[0][i + 3] / 255
        if any(
            abs((a[0][i + k] * wa + 128 * (1 - wa)) - (b[0][i + k] * wb + 128 * (1 - wb))) > levels
            for k in range(3)
        ):
            count += 1
    return count


def far_edge(shot: tuple[bytes, int, int], scale: float, x: float) -> float:
    """The row (logical px) where the ring ends going down the column at ``x``: the first
    transparent pixel after the band."""
    for y in range(shot[2]):
        if pixel(shot, round(x * scale), y)[3] < 128 and y > 4 * scale:
            return y / scale
    return -1.0


def slide(
    blend: str, alignment: str, show: bool, scale: float, depth: int = 40, lag: int = 0
) -> list[tuple[bytes, int, int]]:
    """The painter at 0, 25, 50, 75 and 100 % of a 400 ms slide (and a little after), ``lag`` ms
    late."""
    manager = started(RING, tab(alignment, visible=not show, depth=depth), blend=blend)
    act(manager, "Show" if show else "Hide")
    frames = [snap(manager, scale)]
    advance(manager, 1)  # an animation of the engine starts on the frame after the request
    done = 1
    for at in (101, 201, 301, 460):
        advance(manager, at + lag - done)
        done = at + lag
        frames.append(snap(manager, scale))
    return frames


@pytest.mark.parametrize("scale", [1.0, 1.5])
@pytest.mark.parametrize("alignment", ["START", "CENTER"])
@pytest.mark.parametrize("show", [True, False])
def test_the_body_slides_as_the_param_contour_does(
    show: bool, alignment: str, scale: float
) -> None:
    """The shader's ``s`` follows the same curve as PARAM's parameters: at each quarter of the
    slide the same pixels bar the anti-aliased edges (the paths' and the shader's differ there at
    every curve: 100 levels is more than they ever differ), and the body's far edge is on the same
    row. A uniform of a shader starts moving one tick after the request, as a parameter of a path
    does not, so the shader is looked at 1 ms late (at the steepest part of the easing the lag is
    0.4 px, which at 120 px of edge is 150 to 400 pixels over the threshold)."""
    paths = slide("SRGB", alignment, show, scale)
    shader = slide("LINEAR", alignment, show, scale, lag=1)
    for i, (a, b) in enumerate(zip(paths, shader, strict=True)):
        assert differing(a, b, 100) <= 90, (i, differing(a, b, 100))
        assert abs(far_edge(a, scale, 80) - far_edge(b, scale, 80)) <= 0.7, i


def test_the_shader_uniform_animates_and_the_ring_nodes_and_join_draw_nothing() -> None:
    m = started(RING, tab(visible=False))
    st, h = only(m), host(m)
    assert type(h.join).__name__ == "LinearJoin" and st.drawn == "linear"
    assert not any(n.get("visible") for n in st.nodes)
    assert st.linear.progress("Tab") == 0.0
    act(m, "Show")
    advance(m, 1)
    seen = []
    for _ in range(4):
        advance(m, 100)
        seen.append(st.linear.progress("Tab"))
    assert 0.0 < seen[0] < seen[1] < seen[2] <= 1.0, seen
    advance(m, 100)
    assert st.linear.progress("Tab") == 1.0 and h.anim is None
    assert not any(n.get("visible") for n in st.nodes)  # the ring is still the shader's


def test_the_last_frame_is_the_rest_ring_and_a_hidden_body_leaves_no_trace() -> None:
    for show in (True, False):
        m = started(RING, tab(visible=not show))
        act(m, "Show" if show else "Hide")
        advance(m, 1)
        advance(m, 500)
        rest = started(RING, tab(visible=show))
        assert differing(snap(m), snap(rest), 3) == 0, show
        assert only(m).linear.progress("Tab") == (1.0 if show else 0.0)


# -- clicks follow the painted contour -------------------------------------------------------------


def clicker(manager: SurfaceManager) -> Any:
    st = only(manager)
    taken: list[str] = []
    st.linear.node.on("pointer_down", lambda e: taken.append("ring"))
    host(manager).clip.on("pointer_down", lambda e: taken.append("body"))

    def click(x: int, y: int) -> list[str]:
        taken.clear()
        st.painter.simulate("pointer_down", x=x, y=y)
        return list(taken)

    return click


def test_clicks_follow_the_painted_contour_at_rest_and_while_it_moves() -> None:
    m = started(RING, tab(visible=False))
    click = clicker(m)
    act(m, "Show")
    advance(m, 1)
    advance(m, 450)
    # the body is 120 x 40 at x 20..140, y 20..60; its join on the right has radius 10: the notch
    # at (149, 29) is the opening's
    assert click(80, 40) == ["body"]
    assert click(10, 100) == ["ring"]
    assert click(100, 150) == []  # the opening
    assert click(149, 29) == []  # in the notch of the join: the click falls through
    assert click(141, 21) == ["ring"]  # in the join's corner
    advance(m, 1)
    act(m, "Hide")
    advance(m, 1)
    advance(m, 150)
    assert click(149, 29) == [] and click(300, 150) == []  # nor while it is moving
    assert click(10, 100) == ["ring"]


def hit_map(manager: SurfaceManager, step: int = 3) -> dict[tuple[int, int], str]:
    """What takes a click at each point of a grid: the ring (its path nodes, or the shader's),
    the melded body, or nothing."""
    st = only(manager)
    taken: list[str] = []
    for node in [st.linear.node] if st.linear is not None else st.nodes:
        node.on("pointer_down", lambda e: taken.append("ring"))
    host(manager).clip.on("pointer_down", lambda e: taken.append("body"))
    out = {}
    for y in range(0, 300, step):
        for x in range(0, 400, step):
            taken.clear()
            st.painter.simulate("pointer_down", x=x + 0.5, y=y + 0.5)
            out[(x, y)] = taken[0] if taken else "-"
    return out


@pytest.mark.parametrize("visible", [True, False], ids=["body out", "body hidden"])
def test_the_hit_shape_is_the_painted_shape_of_the_path_build_all_over_the_painter(
    visible: bool,
) -> None:
    frame = (
        "Frame { Name: F, Thickness: [10, 20, 30, 40], Margin: 4, Corner_Radius: 12, "
        'Inner_Radius: 10, Outer_Border { Width: 2, Color: "#ff0000" }, '
        'Inner_Border { Width: 2, Color: "#00ff00" }, Style { Background: "#0000ff" } }'
    )
    panel = tab("CENTER", visible=visible)
    paths = hit_map(started(frame, panel, blend="SRGB"))
    shader = hit_map(started(frame, panel, blend="LINEAR"))
    assert (
        set(paths.values())
        == set(shader.values())
        == ({"ring", "body", "-"} if visible else {"ring", "-"})
    )
    assert [k for k in paths if paths[k] != shader[k]] == []


def test_the_hit_path_is_set_for_the_body_at_its_full_size_while_it_comes_out() -> None:
    m = started(RING, tab(visible=False))
    st = only(m)
    hidden = st.linear.node.get("hit_path")
    act(m, "Show")
    advance(m, 1)
    advance(m, 100)
    with_body = st.linear.node.get("hit_path")
    assert with_body != hidden  # the contour it ends with, not the moving one
    advance(m, 400)
    assert st.linear.node.get("hit_path") == with_body


# -- every place a body can have ----------------------------------------------------------------


def region(shot: tuple[bytes, int, int]) -> bytes:
    """Each pixel as nothing (alpha under half), the border (green), the ring (blue) or other (the
    content of a body): what is where, with none of the anti-aliasing."""
    rgba, w, h = shot
    out = bytearray(w * h)
    for i in range(w * h):
        r, g, b, a = rgba[i * 4 : i * 4 + 4]
        out[i] = 0 if a < 128 else 2 if g > r and g > b and g > 128 else 1 if b > 128 else 3
    return bytes(out)


def moved(a: tuple[bytes, int, int], b: tuple[bytes, int, int]) -> int:
    return sum(1 for x, y in zip(region(a), region(b), strict=True) if x != y)


def melded(side: str, alignment: str, radius: int, length: int, depth: int) -> str:
    return (
        f"Panel {{ Name: Tab, Meld: true, Attach_To: F, Attach: {side}, Alignment: {alignment}, "
        f"Length: {length}, Depth: {depth}, Style {{ Corner_Radius: {radius} }}, "
        'Children { Rectangle { Name: Dot, Width: 10, Height: 10, Fill: "#ff0000" } } }'
    )


OPEN_TOP = RING.replace("Thickness: 20", "Thickness: [20, 20, 0, 20]")
ROUND = RING.replace("Inner_Radius: 8", "Inner_Radius: 30")
PLACES = (
    [(RING, "TOP", a, r, 120, 40, 1.0) for a in ("START", "CENTER", "END") for r in (0, 12)]
    + [
        (RING, "TOP", a, 12, n, d, 1.0)
        for a in ("START", "CENTER")
        for n, d in ((60, 20), (120, 6))
    ]
    + [(RING, "TOP", "START", 12, 500, 40, 1.0)]  # the whole side: both ends flush
    + [
        (RING, s, a, 12, 120, 40, 1.0)
        for s in ("LEFT", "RIGHT", "BOTTOM")
        for a in ("START", "END")
    ]
    + [(RING, "BOTTOM", "CENTER", 12, 120, 40, 1.0), (RING, "LEFT", "CENTER", 12, 120, 40, 1.0)]
    + [(RING, "TOP", a, 12, 120, 40, 1.5) for a in ("START", "CENTER")]
    + [(OPEN_TOP, "TOP", a, 12, 120, 40, 1.0) for a in ("START", "CENTER")]
    + [(ROUND, "TOP", a, 12, 120, 40, 1.0) for a in ("START", "CENTER")]
    + [(ROUND, "TOP", "START", 0, 120, 6, 1.0)]
)


@pytest.mark.parametrize(
    ("frame", "side", "alignment", "radius", "length", "depth", "scale"),
    PLACES,
    ids=[f"{p[1]}-{p[2]}-r{p[3]}-{p[4]}x{p[5]}-{p[6]:g}x-{i}" for i, p in enumerate(PLACES)],
)
def test_a_body_in_every_place_is_the_contour_the_paths_draw(
    frame: str, side: str, alignment: str, radius: int, length: int, depth: int, scale: float
) -> None:
    """The distance field has the contour of the path build wherever the body is: against any of
    the four sides, at either end or in the middle, the whole side (both ends flush) or a sliver of
    10 px, with square corners or rounded ones, with a side that is open or an opening whose
    corners are large. What is where (nothing, border, ring) differs only by anti-aliasing: the
    number of pixels that change class beyond what the ring has without any body is at most 110
    (the slowest case is a curve of radius 32, with 50 px of edge)."""
    paths, shader = (
        started(frame, melded(side, alignment, radius, length, depth), blend="SRGB"),
        started(frame, melded(side, alignment, radius, length, depth), blend="LINEAR"),
    )
    assert only(shader).linear.active
    plain = started(frame, "", blend="SRGB"), started(frame, "", blend="LINEAR")
    extra = moved(snap(paths, scale), snap(shader, scale)) - moved(
        snap(plain[0], scale), snap(plain[1], scale)
    )
    assert extra <= 110, extra


# -- a peek: the tab at rest, the strip's sliver ---------------------------------------------------

PEEK = "Peek { Size: 12, Enter_Delay: 150, Exit_Delay: 300 }"
STRIP = (
    "Frame { Name: F, Thickness: 20, Inner_Radius: 8, "
    'Inner_Border { Width: 2, Color: "#00ff00" }, Style { Background: "#0000ff" }, '
    "Edges { Top { Thickness: 34, Name: Strip, Padding: [10, 8, 10, 8], "
    'Children { Rectangle { Name: Dot, Width: 50, Height: 10, Fill: "#ff0000" } }, '
    "Peek { Size: 6, Enter_Delay: 100, Exit_Delay: 200 } } } }"
)


def peek_run(
    blend: str, scale: float, frame: str, extra: str, where: tuple[int, int], delay: int, lag: int
) -> tuple[list[tuple[bytes, int, int]], SurfaceManager]:
    """Rest, then the pointer on the tab or the sliver, then the slide at about 25, 50, 75 and 100
    % (``lag`` ms late) and a while after."""
    m = started(frame, extra, blend=blend)
    frames = [snap(m, scale)]
    only(m).painter.simulate("pointer_move", x=where[0], y=where[1])
    advance(m, delay + 1)  # the delay runs out and the slide starts
    done = 0
    for at in (101, 201, 301, 600):
        advance(m, at + lag - done)
        done = at + lag
        frames.append(snap(m, scale))
    return frames, m


@pytest.mark.parametrize("scale", [1.0, 1.5])
@pytest.mark.parametrize(
    ("frame", "extra", "where", "delay", "name"),
    [
        (RING, tab(peek=PEEK), (60, 26), 150, "Tab"),
        (STRIP, "", (200, 3), 100, "Strip"),
    ],
    ids=["a Panel's tab", "a strip's sliver"],
)
def test_a_peek_is_the_same_slide_from_its_tab_or_sliver_to_the_whole_body(
    frame: str, extra: str, where: tuple[int, int], delay: int, name: str, scale: float
) -> None:
    paths, _ = peek_run("SRGB", scale, frame, extra, where, delay, 0)
    shader, m = peek_run("LINEAR", scale, frame, extra, where, delay, 1)
    assert only(m).linear is not None and only(m).linear.active
    for i, (a, b) in enumerate(zip(paths, shader, strict=True)):
        assert differing(a, b, 100) <= 90, (i, differing(a, b, 100))
    assert only(m).linear.progress(name) == 1.0  # out, and still the shader's
    assert not any(n.get("visible") for n in only(m).nodes)


def test_a_tab_at_rest_is_a_body_of_size_pixels_and_leaving_goes_back_to_it() -> None:
    m = started(RING, tab(peek=PEEK), blend="LINEAR")
    st = only(m)
    assert st.linear.progress("Tab") == 1.0  # a tab is the body at its (shallow) rest depth
    assert pixel(snap(m), 60, 31) == (0, 0, 255, 255)  # 12 px of ring below the band, then...
    assert pixel(snap(m), 60, 33) == (0, 255, 0, 255)  # ... the border
    st.painter.simulate("pointer_move", x=60, y=26)
    advance(m, 151)
    advance(m, 450)
    assert pixel(snap(m), 60, 50) == (0, 0, 255, 255)  # out: 40 deep
    st.painter.simulate("pointer_move", x=300, y=200)
    advance(m, 301)
    advance(m, 450)
    assert pixel(snap(m), 60, 31) == (0, 0, 255, 255) and pixel(snap(m), 60, 45)[3] == 0
    assert host(m).anim is None and "Tab" in st.tab_melds


# -- a new look, a reload, and what it cannot draw -------------------------------------------------


def themed(blend: str) -> SurfaceManager:
    frame = (
        "Frame { Name: F, Thickness: 20, Inner_Radius: 8, "
        "Inner_Border { Width: 2, Color: $color.on_surface }, "
        "Style { Background: $color.surface } }"
    )
    return started(frame, tab(visible=True), blend=blend)


def test_a_new_desktop_look_repaints_the_ring_and_a_slide_in_flight_arrives_first() -> None:
    for moving in (False, True):
        shader, paths = themed("LINEAR"), themed("SRGB")
        before = [pixel(snap(m), 5, 100) for m in (shader, paths)]
        assert before[0] == before[1]
        if moving:
            act(shader, "Hide")
            advance(shader, 1)
            advance(shader, 100)
            assert host(shader).anim == "out"
        for m in (shader, paths):
            m.set_look(m.look.with_appearance(Appearance(scheme="light")))  # type: ignore[arg-type]
        assert host(shader).anim is None  # settled: where it was heading
        advance(shader, 1)
        after = [pixel(snap(m), 5, 100) for m in (shader, paths)]
        assert after[0] == after[1] != before[0], (moving, before, after)
        if not moving:
            assert differing(snap(shader), snap(paths), 100) <= 60


def reload(manager: SurfaceManager, frame: str, extra: str = "") -> None:
    checked = manager.check(shell_of(frame, extra), module())
    assert checked is not None
    manager.apply(checked[0], module(), checked[1])


def test_a_reload_changes_the_ring_in_place_and_a_new_body_gets_a_slot() -> None:
    m = started(RING, tab(visible=True))
    st, node = only(m), only(m).linear.node
    before = snap(m)
    reload(m, RING.replace("Thickness: 20", "Thickness: 30"), tab(visible=True))
    advance(m, 1)
    assert only(m) is st and st.linear.node is node  # the same painter and node
    assert pixel(before, 25, 100)[3] == 0 and pixel(snap(m), 25, 100) == (0, 0, 255, 255)
    reload(m, RING, tab(visible=True) + tab("END", name="Tab2"))
    advance(m, 1)
    assert only(m).linear is not None and only(m).linear.progress("Tab2") == 1.0
    ring = snap(m)
    assert pixel(ring, 60, 50) == (0, 0, 255, 255) and pixel(ring, 330, 50) == (0, 0, 255, 255)


def warnings(run: Any) -> list[str]:
    seen: list[str] = []
    sink = logger.add(lambda message: seen.append(str(message)), level="WARNING")
    try:
        run()
    finally:
        logger.remove(sink)
    return [line for line in seen if "Frame_Blend" in line or "cannot draw" in line]


def far_row(manager: SurfaceManager, x: int = 60) -> int:
    """The first transparent row below the band at column ``x``: the far edge and its border."""
    shot = snap(manager)
    return next(y for y in range(21, 90) if pixel(shot, x, y)[3] == 0)


def test_a_drag_follows_the_pointer_with_the_shader_and_a_release_past_half_opens_it() -> None:
    m = started(RING, tab(peek="Peek { Size: 12, Trigger: DRAG }"))
    st = only(m)

    def pointer(event: str, y: int) -> None:
        st.painter.simulate(event, x=60, y=y)
        advance(m, 1)  # a uniform that is moved to a value takes 1 ms and starts on a tick
        advance(m, 2)

    pointer("pointer_down", 26)
    pointer("pointer_move", 32)
    pointer("pointer_move", 34)
    a = far_row(m)
    pointer("pointer_move", 40)
    b = far_row(m)
    assert b - a == 6  # the far edge moved as far as the pointer
    assert host(m).anim == "in" and 0.2 < st.linear.progress("Tab") < 0.7
    pointer("pointer_up", 46)  # 20 of 28 px: past half
    advance(m, 500)
    assert host(m).anim is None and "Tab" not in st.tab_melds and st.linear.progress("Tab") == 1.0
    assert far_row(m) == 62
    assert not any(n.get("visible") for n in st.nodes)


def test_a_frame_that_cannot_be_drawn_for_a_moment_gets_its_join_back_and_then_the_shader() -> None:
    m = started(RING, tab())
    st = only(m)
    assert type(host(m).join).__name__ == "LinearJoin"
    translucent = st.plan.paint.__class__(fill=(0, 0, 255, 128), inner=(0, 255, 0, 255))
    solid = st.plan.paint

    def make_translucent() -> None:
        st.plan.paint = translucent
        m.frames._blend(st)

    seen = warnings(make_translucent)
    assert st.linear is None and type(host(m).join).__name__ == "ParamJoin"
    assert len(seen) == 1 and "translucent" in seen[0]
    m.frames._draw(st)
    assert [n.get("visible") for n in st.nodes][1:] == [True, True]
    st.plan.paint = solid  # and when it can, the shader again, and the body still animates
    m.frames._blend(st)
    m.frames._draw(st)
    assert st.linear is not None and type(host(m).join).__name__ == "LinearJoin"
    assert not any(n.get("visible") for n in st.nodes)
    act(m, "Hide")
    advance(m, 1)
    advance(m, 200)
    assert 0.0 < st.linear.progress("Tab") < 1.0
    advance(m, 300)
    assert st.linear.progress("Tab") == 0.0 and host(m).anim is None


FALLBACKS = {
    "a translucent Background": (
        RING.replace('"#0000ff"', '"#0000ff80"'),
        tab(),
        "PARAM",
        "its Background colour is translucent",
    ),
    "a translucent border": (
        RING.replace('"#00ff00"', '"#00ff0080"'),
        tab(),
        "PARAM",
        "its Inner_Border colour is translucent",
    ),
    "an Opacity below 1": (
        RING.replace(
            'Style { Background: "#0000ff" }', 'Style { Background: "#0000ff", Opacity: 0.5 }'
        ),
        tab(),
        "PARAM",
        "its Opacity is 0.5",
    ),
    "Animation: FADE": (
        RING,
        tab(animation="Animation { Type: FADE }"),
        "PARAM",
        "Animation: FADE",
    ),
    "a join that is not PARAM": (RING, tab(), "SMIL", "Frame_Join: SMIL"),
}


@pytest.mark.parametrize("name", list(FALLBACKS))
def test_a_frame_the_shader_cannot_draw_keeps_the_paths_and_says_why_once(name: str) -> None:
    frame, panel, join, why = FALLBACKS[name]
    holder: list[SurfaceManager] = []
    seen = warnings(lambda: holder.append(started(frame, panel, join=join)))
    (m,) = holder
    st = only(m)
    assert st.linear is None and st.drawn != "linear"
    assert [n.get("visible") for n in st.nodes][1:] == [True, True]  # the fill and the border
    assert len(seen) == 1 and why in seen[0], seen
    # drawing again, reloading and a new look do not say it again

    def redo() -> None:
        m.frames._draw(st)
        reload(m, frame, panel)
        m.set_look(m.look)

    again = warnings(redo)
    assert again == []
    assert pixel(snap(m), 5, 100)[3] > 0  # and the ring is drawn


def test_a_frame_with_more_bodies_than_the_shader_has_slots_keeps_the_paths() -> None:
    panels = "".join(tab(name=f"Tab{i}") for i in range(9))
    holder: list[SurfaceManager] = []
    seen = warnings(lambda: holder.append(started(RING, panels)))
    assert only(holder[0]).linear is None
    assert len(seen) == 1 and "9 melded bodies" in seen[0], seen


def test_a_body_as_deep_as_the_opening_cannot_be_drawn_so_the_paths_draw_that_state() -> None:
    """The field has no far corners for it: the state it is in is drawn with paths (and said),
    the others with the shader."""
    m = started(RING, tab(depth=300, visible=False))
    st = only(m)
    assert st.linear.active  # hidden: nothing the shader cannot draw

    def run(action: str) -> None:
        act(m, action)
        advance(m, 1)
        advance(m, 500)

    seen = warnings(lambda: run("Show"))
    assert host(m).anim is None and "Tab" not in st.hidden_melds
    assert not st.linear.active and [n.get("visible") for n in st.nodes][1:] == [True, True]
    assert any("opposite side" in line for line in seen), seen
    assert len([line for line in seen if "opposite side" in line]) == 1
    assert pixel(snap(m), 5, 100)[3] > 0
    warnings(lambda: run("Hide"))
    assert st.linear.active and not any(n.get("visible") for n in st.nodes)


def test_the_default_is_the_path_ring() -> None:
    from tests.test_frame import started as default_started

    m, _ = default_started('Frame { Name: F, Thickness: 12, Style { Background: "#336699" } }')
    st = only(m)
    assert m.blend_mode == "SRGB" and st.linear is None
    assert [n.get("visible") for n in st.nodes] == [False, True, False]
