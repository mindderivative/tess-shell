"""The Frame's ring: side totals and the contours of its bands (Frame > The Ring and Its Corners).

A pure function: no engine, no I/O. From the thickness, margin, borders and corner radii of a
Frame and the output's logical size it gives the space each side reserves and the SVG path data
of three bands, each an outer contour wound one way and an inner contour wound the other, so
that tre's non-zero fill rule leaves the inside open:

* the outer border, between the margin and the fill band,
* the fill band, ``Thickness`` wide on each side,
* the inner border, between the fill band and the opening.

The borders are bands, not strokes: a tre stroke has round joins that would round a square outer
corner. The contours are rounded rectangles (circular arcs), so a corner's radius is one number.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

Sides = tuple[float, float, float, float]  # left, top, right, bottom
Corners = tuple[float, float, float, float]  # top-left, top-right, bottom-right, bottom-left


@dataclass(frozen=True, slots=True)
class RingSpec:
    """What a Frame asks for, in logical pixels. ``thickness`` is the fill band of each side;
    a side of 0 is open: no band, no border, no margin and no reserver."""

    thickness: Sides = (0, 0, 0, 0)
    margin: Sides = (0, 0, 0, 0)
    outer_radius: Corners = (0, 0, 0, 0)
    inner_radius: Corners = (0, 0, 0, 0)
    outer_border: float = 0
    inner_border: float = 0


@dataclass(frozen=True, slots=True)
class Rect4:
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


@dataclass(frozen=True, slots=True)
class Ring:
    """The result: what each side reserves, the three bands, and what had to be reduced."""

    totals: tuple[int, int, int, int]  # left, top, right, bottom: each reserver's zone
    outer_border: str  # SVG path data; empty when the band is not drawn
    fill: str
    inner_border: str
    warnings: tuple[str, ...] = ()


def _whole(values: Sides) -> tuple[int, int, int, int]:
    """Pixels are whole: round half up, and no side is negative."""
    a, b, c, d = (max(math.floor(v + 0.5), 0) for v in values)
    return a, b, c, d


def totals(spec: RingSpec) -> tuple[int, int, int, int]:
    """The space each side reserves: thickness, both borders and margin; 0 for an open side."""
    thick = _whole(spec.thickness)
    margin = _whole(spec.margin)
    ow = max(math.floor(spec.outer_border + 0.5), 0)
    iw = max(math.floor(spec.inner_border + 0.5), 0)
    t = tuple(0 if th == 0 else th + m + ow + iw for th, m in zip(thick, margin, strict=True))
    return t  # type: ignore[return-value]


def _scale(radii: Corners, rect: Rect4) -> tuple[Corners, bool]:
    """Radii that fit ``rect``: scaled together so no two on one edge exceed its length (the CSS
    rule). Also returns whether anything was reduced."""
    tl, tr, br, bl = (max(r, 0.0) for r in radii)
    w, h = max(rect.width, 0.0), max(rect.height, 0.0)
    factor = 1.0
    for total, length in ((tl + tr, w), (bl + br, w), (tl + bl, h), (tr + br, h)):
        if total > length:
            factor = min(factor, length / total if total else 1.0)
    if factor >= 1.0:
        return (tl, tr, br, bl), False
    return (tl * factor, tr * factor, br * factor, bl * factor), True


def _corner_points(rect: Rect4, radii: Corners) -> list[tuple[int, tuple[float, float]]]:
    """Points along each corner arc of a rounded rectangle: ``(corner index, (x, y))``."""
    points: list[tuple[int, tuple[float, float]]] = []
    # centre, start angle (degrees; 0 is +x, 90 is +y in screen space), per corner
    corners = (
        (rect.x0 + radii[0], rect.y0 + radii[0], 180.0),
        (rect.x1 - radii[1], rect.y0 + radii[1], 270.0),
        (rect.x1 - radii[2], rect.y1 - radii[2], 0.0),
        (rect.x0 + radii[3], rect.y1 - radii[3], 90.0),
    )
    radius = radii
    for i, (cx, cy, start) in enumerate(corners):
        for step in range(0, 91, 15):
            angle = math.radians(start + step)
            points.append((i, (cx + radius[i] * math.cos(angle), cy + radius[i] * math.sin(angle))))
    return points


def _inside(outer: Rect4, radii: Corners, point: tuple[float, float], corner: int) -> bool:
    """Whether ``point`` is within ``outer``'s rounded rectangle, judged at ``corner``."""
    eps = 1e-6
    x, y = point
    if x < outer.x0 - eps or x > outer.x1 + eps or y < outer.y0 - eps or y > outer.y1 + eps:
        return False
    r = radii[corner]
    if r <= 0:
        return True
    u = x - outer.x0 if corner in (0, 3) else outer.x1 - x
    v = y - outer.y0 if corner in (0, 1) else outer.y1 - y
    if u >= r or v >= r:
        return True
    return (r - u) ** 2 + (r - v) ** 2 <= r * r + eps


def _fit(outer: Rect4, radii: Corners, inner: Rect4, inner_radii: Corners) -> Corners:
    """``radii`` of ``outer`` reduced, corner by corner, until ``inner`` lies inside it: where
    the inner contour would poke through, the band would be pinched and the opposite winding
    would fill the gap."""
    points = _corner_points(inner, inner_radii)
    result = list(radii)
    for corner in range(4):
        mine = [p for i, p in points if i == corner]
        low, high = 0.0, result[corner]

        def ok(r: float, corner: int = corner, mine: list[tuple[float, float]] = mine) -> bool:
            trial = list(result)
            trial[corner] = r
            return all(_inside(outer, tuple(trial), p, corner) for p in mine)  # type: ignore[arg-type]

        if ok(high):
            continue
        for _ in range(24):
            mid = (low + high) / 2
            if ok(mid):
                low = mid
            else:
                high = mid
        result[corner] = low
    return result[0], result[1], result[2], result[3]


def _num(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def contour(rect: Rect4, radii: Corners, clockwise: bool) -> str:
    """The closed path of a rounded rectangle, wound clockwise or counter-clockwise on screen."""
    tl, tr, br, bl = radii
    x0, y0, x1, y1 = rect.x0, rect.y0, rect.x1, rect.y1
    n = _num

    def arc(r: float, x: float, y: float, sweep: int) -> str:
        return f" A{n(r)},{n(r)} 0 0 {sweep} {n(x)},{n(y)}" if r > 0 else f" L{n(x)},{n(y)}"

    if clockwise:
        d = f"M{n(x0 + tl)},{n(y0)} L{n(x1 - tr)},{n(y0)}"
        d += arc(tr, x1, y0 + tr, 1) + f" L{n(x1)},{n(y1 - br)}"
        d += arc(br, x1 - br, y1, 1) + f" L{n(x0 + bl)},{n(y1)}"
        d += arc(bl, x0, y1 - bl, 1) + f" L{n(x0)},{n(y0 + tl)}"
        d += arc(tl, x0 + tl, y0, 1)
    else:
        d = f"M{n(x0 + tl)},{n(y0)}"
        d += arc(tl, x0, y0 + tl, 0) + f" L{n(x0)},{n(y1 - bl)}"
        d += arc(bl, x0 + bl, y1, 0) + f" L{n(x1 - br)},{n(y1)}"
        d += arc(br, x1, y1 - br, 0) + f" L{n(x1)},{n(y0 + tr)}"
        d += arc(tr, x1 - tr, y0, 0) + f" L{n(x0 + tl)},{n(y0)}"
    return d + " Z"


def _band(outer: Rect4, outer_radii: Corners, inner: Rect4 | None, inner_radii: Corners) -> str:
    """A band: ``outer`` clockwise and, when there is an opening, ``inner`` the other way."""
    data = contour(outer, outer_radii, True)
    if inner is not None and inner.width > 0 and inner.height > 0:
        data += " " + contour(inner, inner_radii, False)
    return data


def _inset(rect: Rect4, left: float, top: float, right: float, bottom: float) -> Rect4:
    x0, y0 = rect.x0 + left, rect.y0 + top
    x1, y1 = rect.x1 - right, rect.y1 - bottom
    return Rect4(x0, y0, max(x1, x0), max(y1, y0))


def ring(spec: RingSpec, size: tuple[float, float]) -> Ring:
    """The ring of ``spec`` on a surface of ``size`` logical pixels.

    A radius larger than its contour allows is reduced, and a warning names the key
    (``Corner_Radius`` or ``Inner_Radius``).
    """
    width, height = size
    thick = _whole(spec.thickness)
    closed = tuple(t > 0 for t in thick)
    margin = tuple(m if c else 0 for m, c in zip(_whole(spec.margin), closed, strict=True))
    ow = max(math.floor(spec.outer_border + 0.5), 0)
    iw = max(math.floor(spec.inner_border + 0.5), 0)

    def edge(c: bool, amount: float) -> float:
        return amount if c else 0

    left, top, right, bottom = closed
    c0 = _inset(Rect4(0, 0, width, height), *margin)
    c1 = _inset(c0, edge(left, ow), edge(top, ow), edge(right, ow), edge(bottom, ow))
    c2 = _inset(c1, *thick)
    c3 = _inset(c2, edge(left, iw), edge(top, iw), edge(right, iw), edge(bottom, iw))
    opening = c2.width > 0 and c2.height > 0

    warnings: list[str] = []
    want_inner = _grow(spec.inner_radius, 0)
    want_outer = _grow(spec.outer_radius, 0)
    r3, _ = _scale(want_inner, c3) if opening else ((0.0, 0.0, 0.0, 0.0), False)
    r2, _ = _scale(_grow(r3, iw), c2)
    r1, _ = _scale(_grow(want_outer, -ow), c1)
    if opening:
        r1 = _fit(c1, r1, c2, r2)
    r0, _ = _scale(want_outer, c0)
    r0 = _fit(c0, r0, c1, r1)
    if any(abs(a - b) > 0.01 for a, b in zip(r0, want_outer, strict=True)):
        warnings.append(
            f"Corner_Radius {_list(want_outer)} is larger than the ring allows; "
            f"it was reduced to {_list(r0)}"
        )
    if opening and any(abs(a - b) > 0.01 for a, b in zip(r3, want_inner, strict=True)):
        warnings.append(
            f"Inner_Radius {_list(want_inner)} is larger than the opening allows; "
            f"it was reduced to {_list(r3)}"
        )
    return Ring(
        totals=totals(spec),
        outer_border=_band(c0, r0, c1, r1) if ow and any(closed) else "",
        fill=_band(c1, r1, c2 if opening else None, r2),
        inner_border=_band(c2, r2, c3, r3) if iw and opening and any(closed) else "",
        warnings=tuple(warnings),
    )


def _grow(radii: Corners, by: float) -> Corners:
    """``radii`` grown by ``by`` (shrunk when negative), none below 0."""
    a, b, c, d = (max(float(r) + by, 0.0) for r in radii)
    return a, b, c, d


def _list(values: Corners) -> str:
    return "[" + ", ".join(_num(v) for v in values) + "]"
