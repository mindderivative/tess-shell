"""Option d: the join as one shader, with an exact circular fillet (``sd_round_union``) and a
uniform that tre animates (``Shader.animate``, tre 0.6.4).

A shader node covers the neighbourhood of the body (a box that holds its fillets and border) and
draws, for each pixel, the signed distance to the union of the band edge and the body: a half
plane for the band, a box whose far corners are rounded for the body, and ``sd_round_union``
between them for the join. Fill is where the distance is negative, the border where it is within
the border's width, both anti-aliased analytically at any display scale (``frame.scale``). One
uniform, ``s`` (how far out the body is, 0 to 1), is animated by the engine and the rest is
computed from it in the shader: the body's far edge, its corners' radius and the fillets' radius
all grow with ``s``. A body flush with the opening's corner has no join; its far corner gets the
fillet of the band's side instead (a second round union with a half plane).

The ring is not ghosted (it draws the ring without the body and the shader draws over it), so use
opaque colours: a translucent fill or border shows where the two overlap. ``hit_path`` is set,
not animated: it is the final shape of the body and its fillets, so a click on the part that has
not grown yet is taken by the shader node. ``Shader.animate`` has no completion callback, so the
end of the animation is a timer of the painter. An idle painter draws nothing: the animation is
not ``animated=True`` (which would redraw every frame), only a uniform that moves.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar

from tess_shell.surfaces import outline
from tess_shell.surfaces.join import Easing, JoinRun
from tess_shell.surfaces.outline import Vertex
from tess_shell.surfaces.ring import BodyGeo

if TYPE_CHECKING:
    from tess_re import LayerWindow
    from tess_re import Node as TreNode

WGSL = """
const BIG: f32 = 4096.0;

fn body_box(p: vec2<f32>, lo: f32, hi: f32, far: f32, rlo: f32, rhi: f32) -> f32 {
    let c = vec2<f32>((lo + hi) * 0.5, far * 0.5);
    let b = vec2<f32>((hi - lo) * 0.5, far * 0.5);
    let q = p - c;
    var r = 0.0;
    if (q.y > 0.0) {
        r = select(rlo, rhi, q.x > 0.0);
    }
    r = min(r, min(b.x, b.y));
    let w = abs(q) - b + vec2<f32>(r, r);
    return min(max(w.x, w.y), 0.0) + length(max(w, vec2<f32>(0.0, 0.0))) - r;
}

fn shade(p: Pixel) -> vec4<f32> {
    let q = p.px / frame.scale + u.o;
    let a = dot(q, u.axs);
    let t = dot(q, u.dep) - u.edge;
    let s = u.s;
    let far = s * u.dpt;
    let flo = u.fl.x > 0.5;
    let fhi = u.fl.y > 0.5;
    let lo = select(u.spn.x, -BIG, flo);
    let hi = select(u.spn.y, BIG, fhi);
    let body = body_box(vec2<f32>(a, t), lo, hi, far,
                        select(u.rf.x * s, 0.0, flo), select(u.rf.y * s, 0.0, fhi));
    let band = t;
    let rj = select(u.rj.y, u.rj.x, a < (u.spn.x + u.spn.y) * 0.5) * s;
    var d = min(band, body);
    if (rj > 0.01) {
        d = sd_round_union(band, body, rj);
    }
    if (flo) {
        let side = a - u.spn.x;
        d = select(min(d, side), sd_round_union(d, side, u.rf.x), u.rf.x > 0.01);
    }
    if (fhi) {
        let side = u.spn.y - a;
        d = select(min(d, side), sd_round_union(d, side, u.rf.y), u.rf.y > 0.01);
    }
    let fa = sd_coverage((d - u.iv) * frame.scale) * u.col_fill.a;
    let ba = clamp(sd_coverage((d - u.iw) * frame.scale) - sd_coverage(d * frame.scale), 0.0, 1.0)
        * u.col_line.a;
    let alpha = ba + fa * (1.0 - ba);
    let rgb = (u.col_line.rgb * ba + u.col_fill.rgb * fa * (1.0 - ba)) / max(alpha, 0.00001);
    return vec4<f32>(rgb, alpha);
}
"""

_REST = 2.0  # pixels of margin around the shapes the shader draws


def _unit(colour: tuple[int, int, int, int]) -> tuple[float, float, float, float]:
    return colour[0] / 255, colour[1] / 255, colour[2] / 255, colour[3] / 255


class ShaderJoin:
    ghost: ClassVar[bool] = False

    def __init__(self, painter: LayerWindow, z_index: int) -> None:
        import tess_re

        self._painter = painter
        self._shader = tess_re.Shader(WGSL, uniforms=self._uniforms_of(None))
        self.node: TreNode = painter.create(
            "box",
            position="absolute",
            left=0,
            top=0,
            width=1,
            height=1,
            visible=False,
            a11y_hidden=True,
            z_index=z_index,
            shader=self._shader,
        )
        painter.root.add_child(self.node)
        self.nodes = [self.node]
        self._kind = "SLIDE"
        self._opacity = 1.0
        self._timer: Any = None

    @staticmethod
    def _uniforms_of(
        values: dict[str, float | tuple[float, ...]] | None,
    ) -> dict[str, float | tuple[float, ...]]:
        base: dict[str, float | tuple[float, ...]] = {
            "o": (0.0, 0.0),
            "dep": (0.0, 1.0),
            "axs": (1.0, 0.0),
            "edge": 0.0,
            "spn": (0.0, 0.0),
            "dpt": 0.0,
            "s": 0.0,
            "rj": (0.0, 0.0),
            "rf": (0.0, 0.0),
            "fl": (0.0, 0.0),
            "iw": 0.0,
            "iv": 0.0,
            "col_fill": (0.0, 0.0, 0.0, 0.0),
            "col_line": (0.0, 0.0, 0.0, 0.0),
        }
        return {**base, **(values or {})}

    @staticmethod
    def _extent(geo: BodyGeo, iw: float) -> tuple[float, float, float]:
        """What the shader node covers, as ``a0``, ``a1`` along the side and ``t1`` away from the
        band edge (it starts at the edge): the body, its fillets and its border."""
        lo, hi = geo.span
        reach = max(*geo.join, *geo.far)
        a0 = lo - (_REST if geo.flush[0] else geo.join[0] + iw + _REST)
        a1 = hi + (_REST if geo.flush[1] else geo.join[1] + iw + _REST)
        return a0, a1, geo.depth + reach + iw + _REST

    def _hit_path(
        self, geo: BodyGeo, a0: float, a1: float, t1: float, origin: tuple[float, float]
    ) -> str:
        """The body and its fillets at full size, with a strip of the band, in the node's pixels."""
        lo, hi = geo.span
        depth, pad = geo.depth, 1.0
        pts: list[tuple[float, float, float]] = [(a0, -pad, 0.0), (a1, -pad, 0.0)]
        if geo.flush[1]:
            pts += [(a1, t1, 0.0), (hi, t1, 0.0), (hi, depth, geo.far[1])]
        else:
            pts += [(a1, 0.0, 0.0), (hi, 0.0, geo.join[1]), (hi, depth, geo.far[1])]
        if geo.flush[0]:
            pts += [(lo, depth, geo.far[0]), (lo, t1, 0.0), (a0, t1, 0.0)]
        else:
            pts += [(lo, depth, geo.far[0]), (lo, 0.0, geo.join[0]), (a0, 0.0, 0.0)]
        vertices = []
        for a, t, r in pts:
            x, y = geo.at(a, t)
            vertices.append(Vertex(x - origin[0], y - origin[1], r))
        return outline.path(outline.clamp(vertices))

    def begin(self, run: JoinRun) -> bool:
        geo = run.ring.geometry[run.index]
        if geo is None or run.fill is None:
            return False
        self._kind, self._opacity = run.kind, run.opacity
        iw = geo.border if run.border is not None else 0.0
        a0, a1, t1 = self._extent(geo, iw)
        (x0, y0), (x1, y1) = geo.at(a0, 0.0), geo.at(a1, t1)
        left, top = min(x0, x1), min(y0, y1)
        width, height = abs(x1 - x0), abs(y1 - y0)
        dx, dy = geo.toward
        line = run.border or run.fill
        edge_x, edge_y = geo.at(0.0, 0.0)
        start = 0.0 if (run.show and run.kind == "SLIDE") else 1.0
        self._shader.set(
            uniforms=self._uniforms_of(
                {
                    "o": (left, top),
                    "dep": (dx, dy),
                    "axs": (abs(dy), abs(dx)),
                    "edge": dx * edge_x + dy * edge_y,
                    "spn": geo.span,
                    "dpt": geo.depth,
                    "s": start,
                    "rj": geo.join,
                    "rf": geo.far,
                    "fl": (float(geo.flush[0]), float(geo.flush[1])),
                    "iw": iw,
                    "iv": geo.seal if iw else 0.0,
                    "col_fill": _unit(run.fill),
                    "col_line": _unit(line),
                }
            )
        )
        self.node.set(
            left=left,
            top=top,
            width=width,
            height=height,
            visible=True,
            opacity=(0.0 if run.show else run.opacity) if run.kind == "FADE" else run.opacity,
            hit_path=self._hit_path(geo, a0, a1, t1, (left, top)),
        )
        return True

    def play(self, show: bool, ms: int, easing: Easing, done: Callable[[], None]) -> None:
        if self._timer is not None:
            self._timer.cancel()
        if self._kind == "SLIDE":
            self._shader.animate("s", 1.0 if show else 0.0, ms, easing)
            self._timer = self._painter.after(ms, done)
        else:
            self.node.animate("opacity", self._opacity if show else 0.0, ms, easing, done)

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self.node.set(visible=False, opacity=1.0)

    def destroy(self) -> None:
        self.stop()
        self.node.destroy()
