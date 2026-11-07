"""Rounded rectilinear outlines: the opening of a Frame with melded Panels grown into it.

A pure module (no engine). An outline is a closed polygon whose edges are axis-aligned, walked
clockwise on the screen (y down), so the region is always on the right of the direction of travel.
Each vertex has a fillet radius. A vertex where the walk turns right (clockwise) is *convex* for the
region (an inner corner of the opening); a vertex where it turns left is *reflex* (the corner of
a melded body that points into the opening).

:func:`simplify` drops vertices that lie on a straight run or on a spike (so a body flush with a
corner removes that corner), :func:`clamp` keeps neighbouring fillets from overlapping,
:func:`erode` moves every edge inward (the Frame's inner border follows a meld), and :func:`path`
writes SVG path data, clockwise or the other way round (the hole of a non-zero fill).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Point = tuple[float, float]


@dataclass(frozen=True, slots=True)
class Vertex:
    x: float
    y: float
    radius: float = 0.0
    tag: float | None = None  # the radius to use when this vertex turns out reflex

    @property
    def at(self) -> Point:
        return self.x, self.y


def _num(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def _turn(a: Point, b: Point, c: Point) -> float:
    """Cross product of ``ab`` and ``bc``: positive when the walk turns right (clockwise on a
    y-down screen)."""
    return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])


def simplify(vertices: list[Vertex]) -> list[Vertex]:
    """Remove repeated points and every vertex with no turn (a straight run or a spike)."""
    pts = list(vertices)
    changed = True
    while changed and len(pts) >= 3:
        changed = False
        pts = [v for i, v in enumerate(pts) if v.at != pts[i - 1].at]
        for i in range(len(pts)):
            a, b, c = pts[i - 1], pts[i], pts[(i + 1) % len(pts)]
            if abs(_turn(a.at, b.at, c.at)) < 1e-9:
                del pts[i]
                changed = True
                break
    return pts


def is_convex(vertices: list[Vertex], i: int) -> bool:
    n = len(vertices)
    return _turn(vertices[i - 1].at, vertices[i].at, vertices[(i + 1) % n].at) > 0


def clamp(vertices: list[Vertex]) -> list[Vertex]:
    """Radii reduced so that the two fillets on one edge do not overlap and none passes the
    middle of its shorter edge."""
    r = [v.radius for v in vertices]
    n = len(vertices)
    for _ in range(4):
        for i in range(n):
            j = (i + 1) % n
            length = math.dist(vertices[i].at, vertices[j].at)
            total = r[i] + r[j]
            if total > length > 0:
                scale = length / total
                r[i] *= scale
                r[j] *= scale
            elif length == 0:
                r[i] = r[j] = 0
    return [Vertex(v.x, v.y, r[i], v.tag) for i, v in enumerate(vertices)]


def erode(vertices: list[Vertex], d: float) -> list[Vertex] | None:
    """The outline moved ``d`` pixels inward. A convex fillet shrinks by ``d`` (to a sharp corner
    at 0) and a rounded reflex one grows by ``d``. ``None`` when an edge would vanish or turn
    round (the border does not fit)."""
    n = len(vertices)
    out: list[Vertex] = []
    for i, v in enumerate(vertices):
        a, c = vertices[i - 1], vertices[(i + 1) % n]
        dx_in, dy_in = _unit(a.at, v.at)
        dx_out, dy_out = _unit(v.at, c.at)
        # right normal of (dx, dy) on a y-down screen is (-dy, dx)
        x = v.x + d * (-dy_in - dy_out)
        y = v.y + d * (dx_in + dx_out)
        if is_convex(vertices, i):
            radius = max(v.radius - d, 0.0)
        else:
            radius = v.radius + d if v.radius > 0 else 0.0
        out.append(Vertex(x, y, radius, v.tag))
    for i in range(n):
        j = (i + 1) % n
        before = _unit(vertices[i].at, vertices[j].at)
        after = _unit(out[i].at, out[j].at)
        if before != after:
            return None
    return out


def _unit(a: Point, b: Point) -> Point:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length == 0:
        return (0.0, 0.0)
    return (round(dx / length, 6), round(dy / length, 6))


def path(vertices: list[Vertex], clockwise: bool = True) -> str:
    """SVG path data of the outline with its fillets. ``clockwise=False`` walks it the other
    way (the hole of a non-zero fill)."""
    pts = list(vertices) if clockwise else list(reversed(vertices))
    n = len(pts)
    if n < 3:
        return ""
    # the walk's turn is judged on the order given: reversing flips it
    corners: list[tuple[Point, Point, int]] = []  # (arc start, arc end, sweep)
    for i, v in enumerate(pts):
        a, c = pts[i - 1], pts[(i + 1) % n]
        r = v.radius
        ux, uy = _unit(a.at, v.at)
        wx, wy = _unit(v.at, c.at)
        start = (v.x - ux * r, v.y - uy * r)
        end = (v.x + wx * r, v.y + wy * r)
        sweep = 1 if _turn(a.at, v.at, c.at) > 0 else 0
        corners.append((start, end, sweep))
    first = corners[0]
    d = f"M{_num(first[1][0])},{_num(first[1][1])}"
    for i in range(1, n + 1):
        start, end, sweep = corners[i % n]
        r = pts[i % n].radius
        d += f" L{_num(start[0])},{_num(start[1])}"
        if r > 0:
            d += f" A{_num(r)},{_num(r)} 0 0 {sweep} {_num(end[0])},{_num(end[1])}"
    return d + " Z"
