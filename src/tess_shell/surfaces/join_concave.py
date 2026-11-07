"""Option c: the join as boxes with concave corners, moved by ``scale``, ``translate`` and
``corner_radius`` (tre 0.6.4: ``transform_origin`` and ``corner_style="concave"``).

The body is a rounded box that slides out from behind the band edge inside a clip box, its far
corners' radius growing with it. Each join fillet is a small box whose corner nearest the body
curves inward (``corner_style="concave"``): it is scaled from 0 to 1 about the corner it touches
(``transform_origin``), so it grows out of the band edge as the body comes out. Where the body is
flush with the opening's corner there is no join: a fillet of constant size at the body's far
corner travels with the far edge. The border is a second set of the same boxes in the border
colour, one size larger, under the fill boxes. All of it is animated by tre's clock, no Python
per frame, and takes clicks by its box and notch shapes.

Limits: the ring is *not* ghosted (it draws the ring without the body and the pieces draw over
it), so a translucent fill or border shows where they overlap: use opaque colours. The border's
thickness along a fillet grows with it (the two boxes are scaled together). The opening's own
rounded corner shows until a flush body has covered it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar

from tess_shell.surfaces.join import Easing, JoinRun
from tess_shell.surfaces.ring import BodyGeo

if TYPE_CHECKING:
    from tess_re import LayerWindow
    from tess_re import Node as TreNode

RGBA = tuple[int, int, int, int]
Box = tuple[float, float, float, float]  # x, y, width, height in the painter's logical pixels
Radii = tuple[float, float, float, float]  # top left, top right, bottom right, bottom left
_ZERO: Radii = (0.0, 0.0, 0.0, 0.0)


def _box(geo: BodyGeo, a0: float, t0: float, a1: float, t1: float) -> Box:
    """The painter's rectangle between two points given along the side and away from the edge."""
    (x0, y0), (x1, y1) = geo.at(a0, t0), geo.at(a1, t1)
    return min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)


def _corner(box: Box, point: tuple[float, float]) -> int:
    """Which corner of ``box`` ``point`` is: 0 top left, 1 top right, 2 bottom right, 3 bottom
    left."""
    x, y, w, h = box
    right, bottom = abs(point[0] - (x + w)) < 1e-6, abs(point[1] - (y + h)) < 1e-6
    return (2 if right else 3) if bottom else (1 if right else 0)


def _radii(index: int, radius: float) -> Radii:
    values = [0.0, 0.0, 0.0, 0.0]
    values[index] = radius
    return values[0], values[1], values[2], values[3]


class ConcaveJoin:
    ghost: ClassVar[bool] = False

    def __init__(self, painter: LayerWindow, z_index: int) -> None:
        self._painter = painter
        self._z = z_index
        self.nodes: list[TreNode] = []
        self._group: TreNode | None = None
        self._kind = "SLIDE"
        self._opacity = 1.0
        # what play() animates: (node, property, value while out of the way, value at rest)
        self._moves: list[tuple[TreNode, str, Any, Any]] = []

    def _make(self, parent: TreNode, **props: Any) -> TreNode:
        node = self._painter.create("box", position="absolute", a11y_hidden=True, **props)
        parent.add_child(node)
        self.nodes.append(node)
        return node

    def _fillet(
        self,
        parent: TreNode,
        geo: BodyGeo,
        a: tuple[float, float],
        t: tuple[float, float],
        centre: tuple[float, float],
        attach: tuple[float, float],
        radius: float,
        colour: RGBA,
    ) -> TreNode:
        """A box over ``a`` by ``t`` whose corner at ``centre`` is concave with ``radius``;
        ``attach`` is the corner it grows from."""
        box = _box(geo, a[0], t[0], a[1], t[1])
        index = _corner(box, geo.at(*centre))
        ax, ay = geo.at(*attach)
        origin = ((ax - box[0]) / box[2], (ay - box[1]) / box[3])
        styles = ["round"] * 4
        styles[index] = "concave"
        return self._make(
            parent,
            left=box[0],
            top=box[1],
            width=box[2],
            height=box[3],
            fill=colour,
            corner_radius=_radii(index, radius),
            corner_style=tuple(styles),
            transform_origin=origin,
        )

    def begin(self, run: JoinRun) -> bool:
        geo = run.ring.geometry[run.index]
        if geo is None or run.fill is None:
            return False
        self.stop()
        self._kind, self._opacity = run.kind, run.opacity
        slide, show = run.kind == "SLIDE", run.show
        iw = geo.border if run.border is not None else 0.0
        fill, line = run.fill, run.border or run.fill
        lo, hi = geo.span
        depth = geo.depth
        dx, dy = geo.toward
        translate = "translate_y" if geo.side in ("top", "bottom") else "translate_x"
        away = -depth * (dy if translate == "translate_y" else dx)
        group = self._painter.create(
            "box",
            position="absolute",
            left=0,
            top=0,
            width=run.size[0],
            height=run.size[1],
            z_index=self._z,
            a11y_hidden=True,
            hit_testable=False,
        )
        self._painter.root.add_child(group)
        self.nodes, self._group, self._moves = [group], group, []

        # the body: the border box (larger) under the fill box, both in a mover in a clip box
        a_lo = lo - (0 if geo.flush[0] else iw)
        a_hi = hi + (0 if geo.flush[1] else iw)
        outer = _box(geo, a_lo, 0, a_hi, depth + iw)
        clip = self._make(
            group,
            left=outer[0],
            top=outer[1],
            width=outer[2],
            height=outer[3],
            clip_children=True,
            hit_testable=False,
        )
        mover = self._make(clip, left=0, top=0, width=outer[2], height=outer[3], hit_testable=False)
        self._moves.append((mover, translate, away, 0.0))

        def body(box: Box, colour: RGBA, grow: float) -> None:
            """A box of the body's shape, its far corners' radii growing from 0."""
            final = [0.0, 0.0, 0.0, 0.0]
            for end, radius, flush, sign in (
                (lo, geo.far[0], geo.flush[0], -1.0),
                (hi, geo.far[1], geo.flush[1], 1.0),
            ):
                if not flush and radius > 0:
                    final[_corner(box, geo.at(end + sign * grow, depth + grow))] = radius + grow
            node = self._make(
                mover,
                left=box[0] - outer[0],
                top=box[1] - outer[1],
                width=box[2],
                height=box[3],
                fill=colour,
                corner_radius=(final[0], final[1], final[2], final[3]),
            )
            self._moves.append((node, "corner_radius", _ZERO, node.get("corner_radius")))

        if iw:
            body(outer, line, iw)
        body(_box(geo, lo, 0, hi, depth), fill, 0.0)
        # the far-corner fillets of a flush end travel with the far edge: they are in a drift box
        drift = self._make(
            group, left=0, top=0, width=run.size[0], height=run.size[1], hit_testable=False
        )
        self._moves.append((drift, translate, away, 0.0))
        for end, sign, join, flush, far in (
            (lo, -1.0, geo.join[0], geo.flush[0], geo.far[0]),
            (hi, 1.0, geo.join[1], geo.flush[1], geo.far[1]),
        ):
            r = far if flush else join
            if r <= 0:
                continue
            if flush:  # the fillet under the body's far edge, beside the band's side
                parent, t = drift, (depth, depth + r)
                a, centre, attach = (end, end - sign * r), (end - sign * r, depth + r), (end, depth)
            else:  # the join: on the band edge, beside the body
                parent, t = group, (0.0, r)
                a, centre, attach = (end, end + sign * r), (end + sign * r, r), (end, 0.0)
            layers = ([(max(r - iw, 0.0), line)] if iw else []) + [(r, fill)]
            for radius, colour in layers:
                node = self._fillet(parent, geo, a, t, centre, attach, radius, colour)
                if not flush:
                    self._moves.append((node, "scale", 0.0, 1.0))
        for node, prop, out, rest in self._moves:
            node.set(**{prop: out if slide and show else rest})
        group.set(opacity=0.0 if not slide and show else run.opacity)
        return True

    def play(self, show: bool, ms: int, easing: Easing, done: Callable[[], None]) -> None:
        if self._group is None:
            return
        if self._kind != "SLIDE":
            self._group.animate("opacity", self._opacity if show else 0.0, ms, easing, done)
            return
        for i, (node, prop, out, rest) in enumerate(self._moves):
            node.animate(prop, rest if show else out, ms, easing, done if i == 0 else None)

    def stop(self) -> None:
        group, self._group = self._group, None
        self.nodes, self._moves = [], []
        if group is not None:
            group.destroy()

    def destroy(self) -> None:
        self.stop()
