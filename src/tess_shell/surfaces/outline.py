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
    body: int = -1  # the melded body this vertex belongs to, -1 for the opening's own corners

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
    return [Vertex(v.x, v.y, r[i], v.tag, v.body) for i, v in enumerate(vertices)]


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
        out.append(Vertex(x, y, radius, v.tag, v.body))
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


# -- a family of contours with one command structure (the morph of a melded body) -----------------
#
# A body that grows out of the Frame's edge is a parameter ``s`` from 0 (collapsed onto the band
# edge, every fillet radius 0) to 1 (full size). Every coordinate of the contour is *linear* in
# ``s``: the body's far corners move along the depth axis by ``s`` times their depth, the radii of
# the joins and of the body's own corners are ``s`` times theirs, and the directions of the edges
# (which fix where a fillet's control points lie) never change. So the contour at s = 0 and at
# s = 1, written with the same commands (``L`` then a cubic ``C`` per vertex, a degenerate cubic
# where the radius is 0), has every intermediate contour as the linear blend of the two, which is
# what an SVG ``<animate attributeName="d">`` computes. Arcs are cubic Beziers with the standard
# quarter-circle constant, so nothing is flattened.

KAPPA = 0.5522847498307936  # the control length of a quarter circle, in radii

Edge = tuple[str, float]  # (side the body grows from, the coordinate of the band edge)


def directions(vertices: list[Vertex]) -> list[tuple[Point, Point]]:
    """The unit direction each vertex is reached in and left in, from the full outline."""
    n = len(vertices)
    return [
        (_unit(vertices[i - 1].at, v.at), _unit(v.at, vertices[(i + 1) % n].at))
        for i, v in enumerate(vertices)
    ]


def convex_flags(vertices: list[Vertex]) -> list[bool]:
    return [is_convex(vertices, i) for i in range(len(vertices))]


def collapse(
    vertices: list[Vertex],
    convex: list[bool],
    edges: dict[int, Edge],
    s: dict[int, float],
    shift: dict[int, float] | None = None,
    grow: dict[int, float] | None = None,
) -> list[Vertex]:
    """The outline with each melded body at ``s[body]`` (1 for a body not named). ``shift`` moves
    a body's edge coordinate (an eroded outline's band edge is the border's width away). ``grow``
    is the fraction the radii have reached where it differs from the depth's (the parametric
    path keeps the two apart); by default it is ``s``."""
    out: list[Vertex] = []
    for v, cx in zip(vertices, convex, strict=True):
        f = s.get(v.body, 1.0)
        g = (s if grow is None else grow).get(v.body, 1.0)
        if v.body < 0 or (f == 1.0 and g == 1.0):
            out.append(v)
            continue
        side, e = edges[v.body]
        e += (shift or {}).get(v.body, 0.0)
        x, y, r = v.x, v.y, v.radius
        if v.tag is not None:  # a corner of the body that is away from the Frame's edge
            if side in ("top", "bottom"):
                y = e + f * (y - e)
            else:
                x = e + f * (x - e)
            r = r if cx else g * r  # a convex one is the opening's own corner (a flush body)
        else:  # a join on the band edge: its fillet grows with the body
            r = g * r
        out.append(Vertex(x, y, r, v.tag, v.body))
    return out


def cubic_path(
    vertices: list[Vertex], dirs: list[tuple[Point, Point]], clockwise: bool = True
) -> str:
    """Path data of the outline: for each vertex ``L`` to where its fillet starts and one ``C``
    round it (a degenerate one for radius 0), so every outline of one family has the same
    commands. ``dirs`` are the directions of the *full* outline, in the order of ``vertices``."""
    n = len(vertices)
    if n < 3:
        return ""
    order = list(range(n)) if clockwise else list(reversed(range(n)))
    out: list[str] = []
    for k, i in enumerate(order):
        v = vertices[i]
        (ux, uy), (wx, wy) = dirs[i]
        if not clockwise:  # walked backwards: arrive where it left, leave where it arrived
            (ux, uy), (wx, wy) = (-wx, -wy), (-ux, -uy)
        r = v.radius
        a = (v.x - ux * r, v.y - uy * r)
        b = (v.x + wx * r, v.y + wy * r)
        c1 = (v.x - ux * r * (1 - KAPPA), v.y - uy * r * (1 - KAPPA))
        c2 = (v.x + wx * r * (1 - KAPPA), v.y + wy * r * (1 - KAPPA))
        out.append(f"{'M' if k == 0 else 'L'}{_num(a[0])},{_num(a[1])}")
        out.append(
            f"C{_num(c1[0])},{_num(c1[1])} {_num(c2[0])},{_num(c2[1])} {_num(b[0])},{_num(b[1])}"
        )
    return " ".join(out) + " Z"
