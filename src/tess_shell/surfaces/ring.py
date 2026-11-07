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

import dataclasses
import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from tess_shell.surfaces import outline
from tess_shell.surfaces.outline import Vertex

Sides = tuple[float, float, float, float]  # left, top, right, bottom
Corners = tuple[float, float, float, float]  # top-left, top-right, bottom-right, bottom-left


@dataclass(frozen=True, slots=True)
class MeldSpec:
    """A Panel hosted in the Frame's surface (Frame > Hosted Melding): a body of ``width`` by
    ``height`` pixels that grows from the inner edge of ``side`` into the opening, ``alignment``
    START, CENTER or END along that side. ``radius`` rounds the body's corners (top-left,
    top-right, bottom-right, bottom-left); the two on the Frame's side are not rounded, the join
    uses the Frame's inner radius."""

    side: str  # left, top, right, bottom
    width: float
    height: float
    alignment: str = "CENTER"
    radius: Corners = (0, 0, 0, 0)

    @property
    def depth(self) -> float:
        """How far the body reaches from the Frame's edge."""
        return self.width if self.side in ("left", "right") else self.height

    def shallow(self, depth: float) -> MeldSpec:
        """The same body ``depth`` pixels deep (the tab of a peeking Panel)."""
        if self.side in ("left", "right"):
            return dataclasses.replace(self, width=depth)
        return dataclasses.replace(self, height=depth)


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
    melds: tuple[MeldSpec, ...] = ()
    # Seal a border to the fill beside it: the fill runs under the border, so the two anti-aliased
    # edges that would meet on one line (and let the desktop through as a hairline) do not. Only
    # for an opaque border: a translucent one would show the fill under half of itself.
    seal_inner: bool = False
    seal_outer: bool = False


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


class Morph(Protocol):
    """The contour with each melded body part of the way out: ``morph({body: s})`` gives
    ``(fill, inner_border)`` path data with the same commands for every ``s``; ``radius`` is the
    fraction the fillets have reached where it differs from ``s`` (the default is the same)."""

    def __call__(
        self, s: Mapping[int, float], radius: Mapping[int, float] | None = None
    ) -> tuple[str, str]: ...


@dataclass(frozen=True, slots=True)
class BodyGeo:
    """One melded body as pieces: where it grows from and how its two ends are shaped, in the
    painter's logical pixels (what the joins built of boxes or of a shader need).

    ``rect`` is the body at full depth and ``edge`` the coordinate of the band edge it grows from
    (``rect.y0`` on top, ``rect.y1`` at the bottom, ``rect.x0`` on the left, ``rect.x1`` on the
    right). The ends are ``lo`` and ``hi`` along the side (left to right, or top to bottom). A
    *free* end has a ``join`` fillet where the body meets the band, which grows with the body, and
    a ``far`` corner of the body's own that grows with it. A *flush* end is against the opening's
    own corner: no join, and ``far`` is the constant radius of the fillet where the body's far
    edge meets the band's side, which travels with the far edge."""

    side: str
    rect: Rect4
    edge: float
    far: tuple[float, float]
    join: tuple[float, float]
    flush: tuple[bool, bool]
    border: float = 0.0  # the inner border's width where it is drawn, else 0
    seal: float = 0.0  # how far the fill runs under an opaque border

    @property
    def span(self) -> tuple[float, float]:
        """The body's ends along the side: ``lo`` and ``hi`` in the painter's x (top and bottom)
        or y (left and right)."""
        r = self.rect
        return (r.x0, r.x1) if self.side in ("top", "bottom") else (r.y0, r.y1)

    @property
    def depth(self) -> float:
        """How far the body reaches from the band edge at full size."""
        r = self.rect
        return r.height if self.side in ("top", "bottom") else r.width

    @property
    def toward(self) -> tuple[float, float]:
        """The unit vector from the band edge into the opening, in the painter's pixels."""
        return {"top": (0.0, 1.0), "bottom": (0.0, -1.0), "left": (1.0, 0.0), "right": (-1.0, 0.0)}[
            self.side
        ]

    def at(self, a: float, t: float) -> tuple[float, float]:
        """The painter's point at ``a`` along the side and ``t`` away from the band edge."""
        dx, dy = self.toward
        if self.side in ("top", "bottom"):
            return a, self.edge + t * dy
        return self.edge + t * dx, a


@dataclass(frozen=True, slots=True)
class Ring:
    """The result: what each side reserves, the three bands, and what had to be reduced."""

    totals: tuple[int, int, int, int]  # left, top, right, bottom: each reserver's zone
    outer_border: str  # SVG path data; empty when the band is not drawn
    fill: str
    inner_border: str
    warnings: tuple[str, ...] = ()
    outer: Rect4 = None  # type: ignore[assignment]  # the fill band's outside (inside the margin)
    opening: Rect4 = None  # type: ignore[assignment]  # the fill band's inside (before the border)
    bodies: tuple[Rect4 | None, ...] = ()  # each meld's body, or None when it was not placed
    # how the contour looks with each melded body at a fraction of its depth: ``morph({body: s})``
    # gives ``(fill, inner_border)`` path data with the same commands for every ``s`` (None when no
    # body is placed); the bodies not named are at 1
    morph: Morph | None = None
    geometry: tuple[BodyGeo | None, ...] = ()  # each body as pieces; None where it is not placed
    bands: tuple[Rect4, Rect4, Rect4, Rect4] = None  # type: ignore[assignment]
    # the fill band of each side (left, top, right, bottom). The top and bottom bands own the
    # corner squares and run the width of the ring; the left and right bands run between them


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
    iv = min(iw / 2, 1.0) if spec.seal_inner and iw else 0.0  # the fill under the inner border
    ov = min(ow / 2, 1.0) if spec.seal_outer and ow else 0.0  # the outer border under the fill
    hole = c2
    r_hole = r2
    if iv and opening:
        hole = _inset(c2, *(iv if c else 0 for c in closed))
        r_hole = _grow(r2, -iv)
    fill = _band(c1, r1, hole if opening else None, r_hole)
    inner = _band(c2, r2, c3, r3) if iw and opening and any(closed) else ""
    bodies: tuple[Rect4 | None, ...] = ()
    morph: Morph | None = None
    geometry: tuple[BodyGeo | None, ...] = ()
    if spec.melds:
        bodies = _place_melds(spec.melds, c2, closed, warnings)
        if opening and any(b is not None for b in bodies):
            morph, geometry = _melded(c1, r1, c2, r2, iw, iv, bodies, spec.melds, warnings)
            fill, inner = morph({})
    outer_hole = c1
    r_outer_hole = r1
    if ov:
        outer_hole = _inset(c1, *(ov if c else 0 for c in closed))
        r_outer_hole = _grow(r1, -ov)
    return Ring(
        totals=totals(spec),
        outer_border=_band(c0, r0, outer_hole, r_outer_hole) if ow and any(closed) else "",
        fill=fill,
        inner_border=inner,
        warnings=tuple(warnings),
        outer=c1,
        opening=c2,
        bodies=bodies,
        morph=morph,
        geometry=geometry,
        bands=(
            Rect4(c1.x0, c1.y0 + thick[1], c1.x0 + thick[0], max(c1.y1 - thick[3], c1.y0)),
            Rect4(c1.x0, c1.y0, c1.x1, min(c1.y0 + thick[1], c1.y1)),
            Rect4(c1.x1 - thick[2], c1.y0 + thick[1], c1.x1, max(c1.y1 - thick[3], c1.y0)),
            Rect4(c1.x0, max(c1.y1 - thick[3], c1.y0), c1.x1, c1.y1),
        ),
    )


_SIDES = ("left", "top", "right", "bottom")


def _body_rect(spec: MeldSpec, c2: Rect4) -> Rect4:
    """Where a meld's body sits: against ``spec.side`` of the opening ``c2``, clamped to it."""
    across = spec.side in ("left", "right")  # the side runs along y
    along = min(spec.height if across else spec.width, c2.height if across else c2.width)
    depth = min(spec.width if across else spec.height, c2.width if across else c2.height)
    lo, hi = (c2.y0, c2.y1) if across else (c2.x0, c2.x1)
    start = {"START": lo, "CENTER": (lo + hi - along) / 2, "END": hi - along}[spec.alignment]
    if spec.side == "top":
        return Rect4(start, c2.y0, start + along, c2.y0 + depth)
    if spec.side == "bottom":
        return Rect4(start, c2.y1 - depth, start + along, c2.y1)
    if spec.side == "left":
        return Rect4(c2.x0, start, c2.x0 + depth, start + along)
    return Rect4(c2.x1 - depth, start, c2.x1, start + along)


def _overlap(a: Rect4, b: Rect4) -> bool:
    return a.x0 < b.x1 - 1e-6 and b.x0 < a.x1 - 1e-6 and a.y0 < b.y1 - 1e-6 and b.y0 < a.y1 - 1e-6


def _place_melds(
    melds: tuple[MeldSpec, ...], c2: Rect4, closed: tuple[bool, ...], warnings: list[str]
) -> tuple[Rect4 | None, ...]:
    """The body of each meld, or ``None`` when its side is open or it would overlap one placed
    before it. Sizes are whole pixels."""
    placed: list[Rect4 | None] = []
    for i, spec in enumerate(melds):
        if not closed[_SIDES.index(spec.side)]:
            warnings.append(
                f"meld {i}: the {spec.side} side has no thickness, so nothing is melded"
            )
            placed.append(None)
            continue
        body = _body_rect(spec, c2)
        body = Rect4(*(math.floor(v + 0.5) for v in (body.x0, body.y0, body.x1, body.y1)))
        if body.width <= 0 or body.height <= 0:
            warnings.append(f"meld {i}: nothing is left of the opening to meld into")
            placed.append(None)
        elif any(o is not None and _overlap(o, body) for o in placed):
            warnings.append(f"meld {i}: it overlaps another meld and is not drawn")
            placed.append(None)
        else:
            placed.append(body)
    return tuple(placed)


def _quadrant_radius(c2: Rect4, radii: Corners, x: float, y: float) -> float:
    left = x <= (c2.x0 + c2.x1) / 2
    top = y <= (c2.y0 + c2.y1) / 2
    return radii[0] if left and top else radii[1] if top else radii[3] if left else radii[2]


def _opening_outline(
    c2: Rect4,
    r2: Corners,
    iw: float,
    bodies: tuple[Rect4 | None, ...],
    melds: tuple[MeldSpec, ...],
) -> list[Vertex]:
    """The fill band's inner contour: the opening ``c2`` with each body cut out of it, clockwise.
    A vertex that turns out convex takes the inner radius of its quadrant (the join of a meld uses
    the Frame's inner radius); a reflex one, a body's own corner, takes its radius less the
    border (the border band follows the contour, so the visible corner has the body's radius)."""
    by_side: dict[str, list[tuple[Rect4, MeldSpec, int]]] = {s: [] for s in _SIDES}
    for i, (body, spec) in enumerate(zip(bodies, melds, strict=True)):
        if body is not None:
            by_side[spec.side].append((body, spec, i))

    def own(spec: MeldSpec, corner: int) -> float:
        return max(float(spec.radius[corner]) - iw, 0.0)

    pts: list[Vertex] = [Vertex(c2.x0, c2.y0)]
    for b, sp, k in sorted(by_side["top"], key=lambda t: t[0].x0):
        pts += [
            Vertex(b.x0, b.y0, body=k),
            Vertex(b.x0, b.y1, tag=own(sp, 3), body=k),
            Vertex(b.x1, b.y1, tag=own(sp, 2), body=k),
            Vertex(b.x1, b.y0, body=k),
        ]
    pts.append(Vertex(c2.x1, c2.y0))
    for b, sp, k in sorted(by_side["right"], key=lambda t: t[0].y0):
        pts += [
            Vertex(b.x1, b.y0, body=k),
            Vertex(b.x0, b.y0, tag=own(sp, 0), body=k),
            Vertex(b.x0, b.y1, tag=own(sp, 3), body=k),
            Vertex(b.x1, b.y1, body=k),
        ]
    pts.append(Vertex(c2.x1, c2.y1))
    for b, sp, k in sorted(by_side["bottom"], key=lambda t: -t[0].x0):
        pts += [
            Vertex(b.x1, b.y1, body=k),
            Vertex(b.x1, b.y0, tag=own(sp, 1), body=k),
            Vertex(b.x0, b.y0, tag=own(sp, 0), body=k),
            Vertex(b.x0, b.y1, body=k),
        ]
    pts.append(Vertex(c2.x0, c2.y1))
    for b, sp, k in sorted(by_side["left"], key=lambda t: -t[0].y0):
        pts += [
            Vertex(b.x0, b.y1, body=k),
            Vertex(b.x1, b.y1, tag=own(sp, 2), body=k),
            Vertex(b.x1, b.y0, tag=own(sp, 1), body=k),
            Vertex(b.x0, b.y0, body=k),
        ]
    pts = outline.simplify(pts)
    sized: list[Vertex] = []
    for i, v in enumerate(pts):
        if outline.is_convex(pts, i):
            r = _quadrant_radius(c2, r2, v.x, v.y)
        else:
            r = v.tag or 0.0
        sized.append(Vertex(v.x, v.y, r, v.tag, v.body))
    return outline.clamp(sized)


def _rect_vertices(rect: Rect4, radii: Corners) -> list[Vertex]:
    return [
        Vertex(rect.x0, rect.y0, radii[0]),
        Vertex(rect.x1, rect.y0, radii[1]),
        Vertex(rect.x1, rect.y1, radii[2]),
        Vertex(rect.x0, rect.y1, radii[3]),
    ]


def _edge_of(body: Rect4, side: str) -> float:
    """The coordinate of the band edge a body grows from."""
    return {"top": body.y0, "bottom": body.y1, "left": body.x0, "right": body.x1}[side]


def _melded(
    c1: Rect4,
    r1: Corners,
    c2: Rect4,
    r2: Corners,
    iw: float,
    iv: float,
    bodies: tuple[Rect4 | None, ...],
    melds: tuple[MeldSpec, ...],
    warnings: list[str],
) -> tuple[Morph, tuple[BodyGeo | None, ...]]:
    """The fill band and the inner border band when bodies are melded into the opening, as a
    function of how far each body has grown (see :mod:`tess_shell.surfaces.outline`), and each
    body as pieces. The fill runs ``iv`` under the border."""
    shape = _opening_outline(c2, r2, iw, bodies, melds)
    dirs = outline.directions(shape)
    convex = outline.convex_flags(shape)
    edges = {
        i: (m.side, _edge_of(b, m.side))
        for i, (b, m) in enumerate(zip(bodies, melds, strict=True))
        if b is not None
    }
    inward = {"top": 1.0, "left": 1.0, "bottom": -1.0, "right": -1.0}
    sealed = outline.erode(shape, iv) if iv else None
    inside = outline.erode(shape, iw) if iw else None
    if iw and inside is None:
        warnings.append("a melded body is too narrow for the inner border: the border is left out")
    outer_rect = _rect_vertices(c1, r1)
    outer_dirs = outline.directions(outer_rect)
    outer = outline.cubic_path(outer_rect, outer_dirs, True)

    def at(s: Mapping[int, float], radius: Mapping[int, float] | None = None) -> tuple[str, str]:
        f = dict(s)
        g = None if radius is None else dict(radius)

        def shifted(d: float) -> dict[int, float]:
            return {i: d * inward[side] for i, (side, _) in edges.items()}

        now = outline.collapse(shape, convex, edges, f, grow=g)
        hole = (
            outline.collapse(sealed, convex, edges, f, shifted(iv), g)
            if sealed is not None
            else now
        )
        fill = outer + " " + outline.cubic_path(hole, dirs, clockwise=False)
        if inside is None:
            return fill, ""
        eroded = outline.collapse(inside, convex, edges, f, shifted(iw), g)
        return fill, (
            outline.cubic_path(now, dirs, True) + " " + outline.cubic_path(eroded, dirs, False)
        )

    pieces = tuple(
        _geometry(shape, convex, k, b, edges[k], iw if inside is not None else 0.0, iv)
        if b is not None
        else None
        for k, b in enumerate(bodies)
    )
    return at, pieces


def _geometry(
    shape: list[Vertex],
    convex: list[bool],
    k: int,
    body: Rect4,
    edge: tuple[str, float],
    border: float,
    seal: float,
) -> BodyGeo | None:
    """Body ``k`` as pieces, from its vertices in the full outline; ``None`` when it does not have
    the two far corners (a body as deep as the opening)."""
    side, e = edge
    along = 0 if side in ("top", "bottom") else 1
    mine = [(v, cx) for v, cx in zip(shape, convex, strict=True) if v.body == k]
    far = sorted((v for v, _ in mine if v.tag is not None), key=lambda v: v.at[along])
    joins = [v for v, _ in mine if v.tag is None]
    if len(far) != 2:
        return None
    radii: list[float] = []
    flush: list[bool] = []
    fillets: list[float] = []
    for v in far:
        match = [j for j in joins if abs(j.at[along] - v.at[along]) < 1e-6]
        flush.append(not match)
        fillets.append(match[0].radius if match else 0.0)
        radii.append(v.radius)
    return BodyGeo(
        side,
        body,
        e,
        (radii[0], radii[1]),
        (fillets[0], fillets[1]),
        (flush[0], flush[1]),
        border,
        seal,
    )


def padded(band: Rect4, padding: Sides) -> Rect4:
    """The content area of a strip: its band less the padding (left, top, right, bottom), never
    negative."""
    return _inset(band, *padding)


def _grow(radii: Corners, by: float) -> Corners:
    """``radii`` grown by ``by`` (shrunk when negative), none below 0."""
    a, b, c, d = (max(float(r) + by, 0.0) for r in radii)
    return a, b, c, d


def _list(values: Corners) -> str:
    return "[" + ", ".join(_num(v) for v in values) + "]"
