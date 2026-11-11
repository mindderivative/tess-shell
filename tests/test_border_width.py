"""The inner border has the same width on a curve as on a straight, at rest, at every display scale.

A KWin review saw the border "slightly thinner during the rounding than the straight portions".
The measurements (``/tmp/frame-review/FOLLOWUP.md``) showed the geometry and the coverage that tre
rasterises are exact on curves; what is thinner is the *look* of a one-pixel anti-aliased edge of
a light line on a dark ground, because tre blends the edge in sRGB (see
``tests/kwin/repro_srgb_edge_blend.py``). These tests pin what is exact so it cannot regress:

* the band's inner contour lies ``Inner_Border.Width`` from its outer contour all the way round,
  joins, the Frame's opening corners and a melded body's corners included;
* the border coverage tre draws in a window round each kind of curve (``sum of coverage``, not a
  threshold) equals that of the exact band, to 3 %, at scale 1.0, 1.25 and 1.5.
"""

from __future__ import annotations

import math
import re
import time
from pathlib import Path

import pytest
import tess_re

from tess_shell.surfaces.ring import MeldSpec, RingSpec, ring
from tests.sway import PrivateSway

W, H = 400, 300
IW = 2
SPEC = RingSpec(
    thickness=(24, 24, 24, 24),
    inner_radius=(14, 14, 14, 14),
    inner_border=IW,
    seal_inner=True,
    melds=(MeldSpec("top", 120, 40, "CENTER", (8, 8, 8, 8)),),
)
# (name, x0, y0, x1, y1) in logical pixels: a window round each kind of curve
WINDOWS = [
    ("opening corner", 22, 22, 44, 44),
    ("join of the body", 120, 22, 142, 46),
    ("far corner of the body", 138, 52, 160, 68),
    ("straight (left side)", 22, 100, 30, 200),
]
Point = tuple[float, float]


def flatten(data: str, steps: int = 24) -> list[list[Point]]:
    """The closed polylines of path data made of M, L, C, circular A and Z."""
    tokens = re.findall(r"[MLCAZ]|-?\d+\.?\d*", data)
    contours: list[list[Point]] = []
    here: Point = (0.0, 0.0)
    i = 0
    while i < len(tokens):
        t = tokens[i]
        if t in "ML":
            here = (float(tokens[i + 1]), float(tokens[i + 2]))
            if t == "M":
                contours.append([])
            contours[-1].append(here)
            i += 3
        elif t == "C":
            p1, p2, p3 = ((float(tokens[i + k]), float(tokens[i + k + 1])) for k in (1, 3, 5))
            for k in range(1, steps + 1):
                u = k / steps
                a, b, c, d = (1 - u) ** 3, 3 * (1 - u) ** 2 * u, 3 * (1 - u) * u * u, u**3
                contours[-1].append(
                    (
                        a * here[0] + b * p1[0] + c * p2[0] + d * p3[0],
                        a * here[1] + b * p1[1] + c * p2[1] + d * p3[1],
                    )
                )
            here = p3
            i += 7
        elif t == "A":
            r, sweep = float(tokens[i + 1]), int(tokens[i + 5])
            end = (float(tokens[i + 6]), float(tokens[i + 7]))
            mx, my = (here[0] + end[0]) / 2, (here[1] + end[1]) / 2
            chord = math.dist(here, end)
            h = math.sqrt(max(r * r - chord * chord / 4, 0.0))
            nx, ny = -(end[1] - here[1]) / chord, (end[0] - here[0]) / chord
            for sign in (1, -1):  # the centre whose short arc turns the way ``sweep`` says
                cx, cy = mx - sign * h * nx, my - sign * h * ny
                a0 = math.atan2(here[1] - cy, here[0] - cx)
                a1 = math.atan2(end[1] - cy, end[0] - cx)
                delta = (a1 - a0) % (2 * math.pi) if sweep == 1 else -((a0 - a1) % (2 * math.pi))
                if abs(delta) <= math.pi + 1e-9:
                    break
            for k in range(1, steps + 1):
                a = a0 + delta * k / steps
                contours[-1].append((cx + r * math.cos(a), cy + r * math.sin(a)))
            here = end
            i += 8
        else:
            i += 1
    return contours


def distance(p: Point, poly: list[Point]) -> float:
    best = math.inf
    for k, a in enumerate(poly):
        b = poly[(k + 1) % len(poly)]
        dx, dy = b[0] - a[0], b[1] - a[1]
        length = dx * dx + dy * dy
        along = (p[0] - a[0]) * dx + (p[1] - a[1]) * dy
        t = 0.0 if length == 0 else max(0.0, min(1.0, along / length))
        best = min(best, math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy))
    return best


def area(poly: list[Point]) -> float:
    return abs(
        sum(
            poly[k][0] * poly[(k + 1) % len(poly)][1] - poly[(k + 1) % len(poly)][0] * poly[k][1]
            for k in range(len(poly))
        )
        / 2
    )


def inside(p: Point, polys: list[list[Point]]) -> bool:
    """Even-odd: the band is between the outer contour and the inner one."""
    n = 0
    for poly in polys:
        for k, a in enumerate(poly):
            b = poly[(k + 1) % len(poly)]
            if (a[1] > p[1]) != (b[1] > p[1]):
                x = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                n += p[0] < x
    return n % 2 == 1


def band() -> list[list[Point]]:
    shaped = ring(SPEC, (W, H))
    contours = flatten(shaped.inner_border)
    assert len(contours) == 2
    return sorted(contours, key=lambda p: -area(p))


def test_the_borders_inner_contour_is_the_width_from_its_outer_contour_all_the_way_round() -> None:
    outer, inner = band()
    for contour, other in ((inner, outer), (outer, inner)):
        widths = [distance(p, other) for p in contour]
        assert max(abs(w - IW) for w in widths) < 0.005, (min(widths), max(widths))


def drawn(scale: float) -> list[list[float]]:
    """tre's coverage of the border alone (white on transparent), per pixel, rows of floats."""
    shaped = ring(SPEC, (W, H))
    window = tess_re.LayerWindow(
        "test.border",
        layer="top",
        anchor=("top", "right", "bottom", "left"),
        size=(0, 0),
        exclusive_zone=-1,
        input_region=[],
    )
    window.resize(W, H)
    node = window.create(
        "path",
        data=shaped.inner_border,
        fill=(255, 255, 255, 255),
        position="absolute",
        left=0,
        top=0,
        width=W,
        height=H,
    )
    window.root.add_child(node)
    rgba, w, h = window.snapshot(scale=scale)
    return [[rgba[(y * w + x) * 4 + 3] / 255 for x in range(w)] for y in range(h)]


@pytest.mark.parametrize("scale", [1.0, 1.25, 1.5])
def test_the_border_coverage_round_every_kind_of_curve_is_that_of_the_exact_band(
    scale: float,
) -> None:
    coverage = drawn(scale)
    polys = band()
    sub = 4  # samples per device pixel and axis for the exact coverage
    for name, x0, y0, x1, y1 in WINDOWS:
        px0, py0, px1, py1 = (round(v * scale) for v in (x0, y0, x1, y1))
        got = sum(coverage[y][x] for y in range(py0, py1) for x in range(px0, px1))
        want = 0.0
        for y in range(py0, py1):
            for x in range(px0, px1):
                hits = sum(
                    inside(((x + (i + 0.5) / sub) / scale, (y + (j + 0.5) / sub) / scale), polys)
                    for i in range(sub)
                    for j in range(sub)
                )
                want += hits / (sub * sub)
        assert want > 10, name
        assert abs(got - want) / want < 0.03, f"{name} at {scale}: tre {got:.2f}, exact {want:.2f}"


@pytest.mark.tre
def test_the_live_border_on_a_private_sway_has_the_exact_coverage_round_the_corner(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    """What the compositor shows (grim) at an opening corner: the green of the border, summed
    over a window, is that of the exact band (the live renderer agrees with the snapshots)."""
    from tests.test_frame_live import BEHIND, OUT, run_shell, screenshot, stop, usable

    frame = (
        "Frame { Name: F, Thickness: 24, Inner_Radius: 14, "
        'Inner_Border { Width: 2, Color: "#00ff00" }, Style { Background: "#0000ff" } }'
    )
    shell = run_shell(private_sway, tmp_path, f"{BEHIND}\n{frame}", blend="SRGB")
    try:
        usable(private_sway, 26, 26, 26, 26)
        time.sleep(0.6)
        width, _, pixels = screenshot(private_sway)
        spec = RingSpec(thickness=(24,) * 4, inner_radius=(14,) * 4, inner_border=2)  # type: ignore[arg-type]
        outer, inner = sorted(flatten(ring(spec, OUT).inner_border), key=lambda poly: -area(poly))
        x0, y0, x1, y1 = 22, 22, 44, 44
        got = sum(
            pixels[(y * width + x) * 3 + 1] / 255 for y in range(y0, y1) for x in range(x0, x1)
        )
        want = sum(
            sum(
                inside(((x + (i + 0.5) / 4), (y + (j + 0.5) / 4)), [outer, inner])
                for i in range(4)
                for j in range(4)
            )
            / 16
            for y in range(y0, y1)
            for x in range(x0, x1)
        )
        assert abs(got - want) / want < 0.03, f"live {got:.2f}, exact {want:.2f}"
        stop(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
