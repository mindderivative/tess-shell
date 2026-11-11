"""The Frame's ring in one fill shader that blends in linear light (``Debug { Frame_Blend:
LINEAR }``).

tre blends the anti-aliased edge of a path in sRGB: a half-covered pixel of a light line on a dark
ground has about 0.31 of the light's brightness in linear light, not 0.5, so a 2 px band that is
whole pixels on a straight is thinner to the eye on a curve (TRE-REQ-015,
``tests/kwin/repro_srgb_edge_blend.py``). A shader's output is stored as the encoded bytes it
returns, so a shader that mixes the colours itself in linear light and returns the encoded result
puts the right pixels on screen, with no engine change.

One ``box`` node, the painter's size and below everything else, is painted by a fill shader that
draws the three bands of the ring (outer border, fill, inner border; ``ring.py``) as signed
distance fields and composites them in linear light:

* the outer contours are rounded rectangles (``rrect``, per-corner radii) from ``Ring.contours``,
  the numbers the path build draws from, so both builds have the same positions, margins,
  thicknesses and radii;
* with melded bodies the opening is a distance field of its own: the outside of the opening's
  rounded rectangle, with each body joined to it by ``sd_round_union`` (an exact circular fillet at
  the body's joins and, where it runs to the opening's corner, between its far edge and the side).
  The inner border and the seal under it are offsets of that field. A body is five uniforms: its
  place and sides, its depth and radii at the start and at the end of its slide, and ``s``, how
  far along it is, which tre animates with ``Shader.animate`` (no Python per frame; PARAM's contour
  has the same shape at every ``s``, and the same easing);
* ``hit_path`` is the painted contour, so a click in the opening goes through.

The colours are given as linear-light uniforms (``linear``) and the result is encoded once, so the
shader does a handful of ``pow`` for each pixel and a window that is still draws nothing. A change
of uniforms alone draws no frame in such a window (seen on a compositor): the ring writes to its
node after a ``set``, and a uniform that must change while another body slides is moved with an
``animate`` of 1 ms (``set`` would stop that slide, and an ``animate`` of no duration is applied
but wakes nothing); a slide starts from a value put at once.

Only an edge between two colours the shader paints itself is blended in linear light. The border's
outer edge (against the fill) is; its inner edge (against the opening, where the desktop is) is
blended by the compositor in sRGB as always, and so is the ring's own outer edge against whatever
is outside it. The colours are opaque (a translucent one, or an ``Opacity`` below 1, keeps the
path build: see ``Frames._blend_reason``) and the shader paints no text, which stays as it was.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Sequence
from typing import TYPE_CHECKING, Any, ClassVar

from tess_shell.surfaces.join import Easing, JoinRun
from tess_shell.surfaces.ring import BodyGeo, Corners, Rect4, Ring

if TYPE_CHECKING:
    from tess_re import LayerWindow, Shader
    from tess_re import Node as TreNode

RGBA = tuple[int, int, int, int]
Uniform = float | tuple[float, ...]
MAX_BODIES = 8  # melded bodies one shader draws (each is five uniforms and one call)
MAX_PIXELS = 8192  # tre paints a shader node larger than this (physical px) without its shader
_SIDE = {"left": 0.0, "top": 1.0, "right": 2.0, "bottom": 3.0}
_EMPTY = "M0,0 L0,0 Z"
# the corner of the opening (top-left, top-right, bottom-right, bottom-left) at each end of a body
# (``lo`` first: left on top and bottom, top on the left and right)
_CORNER = {"top": (0, 1), "right": (1, 2), "bottom": (3, 2), "left": (0, 3)}

_HEAD = """
const BIG: f32 = 4096.0;

fn to_srgb(c: vec3<f32>) -> vec3<f32> {
    let l = clamp(c, vec3<f32>(0.0), vec3<f32>(1.0));
    return select(1.055 * pow(l, vec3<f32>(1.0 / 2.4)) - 0.055, l * 12.92,
                  l <= vec3<f32>(0.0031308));
}

// a rectangle (x0, y0, x1, y1) with its corner radii (top-left, top-right, bottom-right,
// bottom-left): negative inside
fn rrect(q: vec2<f32>, r: vec4<f32>, rad: vec4<f32>) -> f32 {
    let h = (r.zw - r.xy) * 0.5;
    let p = q - (r.xy + r.zw) * 0.5;
    var rr = select(select(rad.z, rad.y, p.y < 0.0), select(rad.w, rad.x, p.y < 0.0), p.x < 0.0);
    rr = min(rr, min(h.x, h.y));
    let w = abs(p) - h + vec2<f32>(rr, rr);
    return min(max(w.x, w.y), 0.0) + length(max(w, vec2<f32>(0.0, 0.0))) - rr;
}

fn cover(d: f32) -> f32 {
    return sd_coverage(d * frame.scale);
}

// a body that grows out of the band edge: a box from the edge (t = 0) to its far edge, with its far
// corners rounded; a flush end runs on to the opening's side
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

// the distance field of the ring (negative inside it) with one body joined to it. A free end of
// the body has a fillet with the band edge (the plane t = 0). A flush end runs on to the opening's
// side: the opening's own corner there is the body's, so the field it comes in has a sharp corner
// (the caller took the radius off it) and the fillet is the one between the body's far edge and
// the side plane, which are at a right angle (two parallel edges closer than the radius would
// bulge, so a fillet is never taken between the band edge and the far edge of a body)
fn body_union(q: vec2<f32>, d_in: f32, g: vec4<f32>, dd: vec4<f32>, fo: vec4<f32>,
              fj: vec4<f32>, s: f32) -> f32 {
    var dep = vec2<f32>(0.0, 1.0);
    if (g.w < 0.5) {
        dep = vec2<f32>(1.0, 0.0);
    } else if (g.w > 2.5) {
        dep = vec2<f32>(0.0, -1.0);
    } else if (g.w > 1.5) {
        dep = vec2<f32>(-1.0, 0.0);
    }
    let axs = vec2<f32>(abs(dep.y), abs(dep.x));
    let a = dot(q, axs);
    let t = dot(q, dep) - g.z;
    let depth = mix(dd.x, dd.y, s);
    let flo = dd.z > 0.5;
    let fhi = dd.w > 0.5;
    let far_lo = mix(fo.x, fo.z, s);
    let far_hi = mix(fo.y, fo.w, s);
    let body = body_box(vec2<f32>(a, t), select(g.x, -BIG, flo), select(g.y, BIG, fhi), depth,
                        select(far_lo, 0.0, flo), select(far_hi, 0.0, fhi));
    let j_lo = select(mix(fj.x, fj.z, s), 0.0, flo);
    let j_hi = select(mix(fj.y, fj.w, s), 0.0, fhi);
    let rj = min(select(j_hi, j_lo, a < (g.x + g.y) * 0.5), depth);
    var x = min(t, body);
    if (rj > 0.01) {
        x = sd_round_union(t, body, rj);
    }
    var d = min(d_in, x);
    if (flo && far_lo > 0.01) {
        d = min(d, sd_round_union(a - g.x, body, far_lo));
    }
    if (fhi && far_hi > 0.01) {
        d = min(d, sd_round_union(g.y - a, body, far_hi));
    }
    return d;
}
"""

_SHADE = """
fn shade(p: Pixel) -> vec4<f32> {
    let q = p.px / frame.scale;
    var o2 = rrect(q, u.open_x, u.open_c);
    var o3 = rrect(q, u.ins_x, u.ins_c);
    var os = rrect(q, u.hole_x, u.hole_c);
@BODIES@
    let a_o = cover(max(rrect(q, u.out_x, u.out_c), -rrect(q, u.outh_x, u.outh_c))) * u.col_out.a;
    let a_f = cover(max(rrect(q, u.fill_x, u.fill_c), -os)) * u.col_fill.a;
    let a_b = cover(max(o2, -o3)) * u.col_in.a;
    let a_u = a_f + a_o * (1.0 - a_f);
    let a = a_b + a_u * (1.0 - a_b);
    if (a <= 0.0) {
        return vec4<f32>(0.0, 0.0, 0.0, 0.0);
    }
    let pm = u.col_in.rgb * a_b
        + (u.col_fill.rgb * a_f + u.col_out.rgb * a_o * (1.0 - a_f)) * (1.0 - a_b);
    return vec4<f32>(to_srgb(pm / a), a);
}
"""

_BODIES = """    if (u.mode > 0.5) {
        var d = -rrect(q, u.open_x, u.base_c);
@CALLS@
        o2 = -d;
        o3 = o2 + u.iw;
        os = o2 + u.iv;
    }
"""


def source(bodies: int) -> str:
    """The WGSL of a shader that draws up to ``bodies`` melded bodies."""
    if bodies:
        calls = "\n".join(
            f"        d = body_union(q, d, u.bg{k}, u.bd{k}, u.bo{k}, u.bj{k}, u.bs{k});"
            for k in range(bodies)
        )
        union = _BODIES.replace("@CALLS@", calls)
    else:
        union = ""
    return _HEAD + _SHADE.replace("@BODIES@", union)


def _lin(v: float) -> float:
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def linear(colour: RGBA | None) -> tuple[float, float, float, float]:
    """An sRGB colour as the shader takes it: linear-light channels and alpha; none is not drawn."""
    if colour is None:
        return (0.0, 0.0, 0.0, 0.0)
    r, g, b = (_lin(v / 255) for v in colour[:3])
    return (r, g, b, colour[3] / 255)


def _rect(r: Rect4) -> tuple[float, float, float, float]:
    return (r.x0, r.y0, r.x1, r.y1)


def _corners(c: Corners) -> tuple[float, float, float, float]:
    return (float(c[0]), float(c[1]), float(c[2]), float(c[3]))


def body_reason(geo: BodyGeo | None, low: BodyGeo | None = None) -> str | None:
    """Why the shader cannot draw this body, or ``None``. A body as deep as the opening has no far
    corners, and a tab has to be the same shape as its body (the two are blended)."""
    if geo is None:
        return "a melded body reaches the opposite side of the opening, so it has no far corners"
    if low is not None and (low.flush != geo.flush or low.side != geo.side or low.span != geo.span):
        return "a melded body and its tab are not the same shape"
    return None


class RingShader:
    """The ring's node, its shader and the bodies' uniforms. ``bodies`` is how many melded bodies
    the Frame can have (a slot each, in the order of its plan)."""

    def __init__(self, painter: LayerWindow, bodies: Sequence[str], z_index: int = 0) -> None:
        self._painter = painter
        self.node: TreNode | None = None
        self._z = z_index
        self._slots: list[str] = list(bodies)
        self._shader: Shader | None = None
        self._sent: dict[str, Uniform] = {}
        self._fresh = True  # the shader has not been given uniforms since it was made
        self._lows: dict[str, BodyGeo | None] = {}  # bodies that animate and where they start
        self._s: dict[str, float] = {}  # how far out each body is (the last value Python set)
        self._animating: set[str] = set()
        self._ctx: tuple[Any, ...] | None = None
        self._shape: tuple[Any, ...] | None = None
        self.active = False  # the node draws the ring now (the state fits and it is visible)
        self._make()

    # -- the node and its shader -----------------------------------------------------------------

    def _uniforms(self) -> dict[str, Uniform]:
        zero4 = (0.0, 0.0, 0.0, 0.0)
        base: dict[str, Uniform] = {"mode": 0.0, "iw": 0.0, "iv": 0.0, "base_c": zero4}
        for name in ("out", "outh", "fill", "open", "hole", "ins"):
            base[f"{name}_x"] = zero4
            base[f"{name}_c"] = zero4
        for name in ("col_out", "col_fill", "col_in"):
            base[name] = zero4
        for k in range(len(self._slots)):
            base.update({f"bg{k}": zero4, f"bd{k}": zero4, f"bo{k}": zero4, f"bj{k}": zero4})
            base[f"bs{k}"] = 0.0
        return base

    def _make(self) -> None:
        import tess_re

        self._shader = tess_re.Shader(source(len(self._slots)), uniforms=self._uniforms())
        self._sent = {}
        self._fresh = True
        if self.node is None:
            self.node = self._painter.create(
                "box",
                position="absolute",
                left=0,
                top=0,
                width=1,
                height=1,
                visible=False,
                a11y_hidden=True,
                z_index=self._z,
                shader=self._shader,
            )
            self._painter.root.add_child(self.node)
        else:
            self.node.set(shader=self._shader)

    def configure(self, bodies: Sequence[str]) -> None:
        """The bodies the plan has now; a different count makes the shader again."""
        if len(bodies) != len(self._slots):
            self._slots = list(bodies)
            self._animating.clear()
            self._make()
            self._shape = None
        else:
            self._slots = list(bodies)

    def destroy(self) -> None:
        self.active = False
        if self.node is not None:
            self.node.destroy()
            self.node = None

    def hide(self) -> None:
        self.active = False
        if self.node is not None and self._shape is not None:
            self.node.set(visible=False)
            self._shape = None

    # -- what the ring needs, and what it cannot draw ---------------------------------------------

    def reason(self, ring: Ring, names: Sequence[str]) -> str | None:
        """Why the shader cannot draw ``ring`` (its placed bodies are ``names``' slots), else
        ``None``."""
        if ring.contours is None:
            return "the ring has no contours"
        placed = [
            (n, g)
            for n, b, g in zip(names, ring.bodies, _padded(ring.geometry, len(names)), strict=False)
            if b is not None
        ]
        for name, geo in placed:
            if name not in self._slots:
                return f"the melded body {name} has no place in the shader"
            why = body_reason(geo, self._lows.get(name))
            if why is not None:
                return why
        return None

    # -- drawing -----------------------------------------------------------------------------------

    def draw(
        self,
        size: tuple[float, float],
        ring: Ring,
        names: Sequence[str],
        moving: Collection[str],
        colours: tuple[RGBA | None, RGBA | None, RGBA | None],
    ) -> None:
        """Paint ``ring`` (the bodies of ``names`` in it, those in ``moving`` at their full size
        and animated by their joins) in ``colours``: outer border, fill, inner border."""
        self._ctx = (size, ring, tuple(names), frozenset(moving), colours)
        self._paint()

    def _paint(self) -> None:
        assert self._ctx is not None and self.node is not None
        size, ring, names, moving, colours = self._ctx
        con = ring.contours
        outer, fill, inner = colours
        values: dict[str, Uniform] = {
            "mode": 1.0 if self._slots and any(b is not None for b in ring.bodies) else 0.0,
            "iw": con.inner_width,
            "iv": con.inner_seal,
            "col_out": linear(outer if con.outer_drawn else None),
            "col_fill": linear(fill),
            "col_in": linear(inner if con.inner_drawn else None),
        }
        for key, (rect, radii) in (
            ("out", con.outer),
            ("outh", con.outer_hole),
            ("fill", con.fill),
            ("open", con.opening),
            ("hole", con.hole),
            ("ins", con.inside),
        ):
            values[f"{key}_x"] = _rect(rect)
            values[f"{key}_c"] = _corners(radii)
        geometry = _padded(ring.geometry, len(names))
        base = list(con.opening[1])  # a corner a flush body runs into is the body's: no radius
        for k, slot in enumerate(self._slots):
            geo: BodyGeo | None = None
            if slot in names:
                i = names.index(slot)
                geo = geometry[i] if i < len(ring.bodies) and ring.bodies[i] is not None else None
            animating = slot in moving or slot in self._lows
            if geo is None:
                values.update(self._off(k))
                self._s.pop(slot, None)
                continue
            low = self._lows.get(slot) if animating else geo
            values.update(self._body(k, geo, low))
            for end in (0, 1):
                if geo.flush[end]:
                    base[_CORNER[geo.side][end]] = 0.0
            if not animating:
                self._s[slot] = 1.0
            values[f"bs{k}"] = self._s.get(slot, 0.0)
        values["base_c"] = _corners((base[0], base[1], base[2], base[3]))
        self._apply(values)
        shape = (size, self._hit(ring, colours))
        if shape != self._shape or not self.active:
            self.node.set(width=size[0], height=size[1], hit_path=shape[1], visible=True)
            self._shape = shape
        self.active = True

    @staticmethod
    def _off(k: int) -> dict[str, Uniform]:
        zero4 = (0.0, 0.0, 0.0, 0.0)
        return {f"bg{k}": zero4, f"bd{k}": zero4, f"bo{k}": zero4, f"bj{k}": zero4, f"bs{k}": 0.0}

    @staticmethod
    def _body(k: int, geo: BodyGeo, low: BodyGeo | None) -> dict[str, Uniform]:
        """The uniforms of body ``k``: its place and sides, and its depth and radii at the start
        (``low``: its tab, else collapsed onto the band edge) and at the end of its slide."""
        lo, hi = geo.span
        dx, dy = geo.toward
        ex, ey = geo.at(0.0, 0.0)
        if low is None:  # a flush end's fillet does not grow, a join's and a corner's do
            far0 = (
                geo.far[0] if geo.flush[0] else 0.0,
                geo.far[1] if geo.flush[1] else 0.0,
            )
            depth0, join0 = 0.0, (0.0, 0.0)
        else:
            far0, depth0, join0 = low.far, low.depth, low.join
        return {
            f"bg{k}": (lo, hi, dx * ex + dy * ey, _SIDE[geo.side]),
            f"bd{k}": (depth0, geo.depth, float(geo.flush[0]), float(geo.flush[1])),
            f"bo{k}": (far0[0], far0[1], geo.far[0], geo.far[1]),
            f"bj{k}": (join0[0], join0[1], geo.join[0], geo.join[1]),
        }

    @staticmethod
    def _hit(ring: Ring, colours: tuple[RGBA | None, RGBA | None, RGBA | None]) -> str:
        """The painted contour: the bands that are drawn, as one path (each band is its outer
        contour clockwise and its inner one the other way, so the union of their windings is
        the union of the bands)."""
        outer, fill, inner = colours
        parts = [
            data
            for data, colour in (
                (ring.outer_border, outer),
                (ring.fill, fill),
                (ring.inner_border, inner),
            )
            if data and colour is not None
        ]
        return " ".join(parts) or _EMPTY

    def _apply(self, values: dict[str, Uniform]) -> None:
        """Give the shader ``values``. While a body animates only what changed is sent, each as an
        ``animate`` of 1 ms (``set`` would stop the animations that are running; an ``animate`` of
        no duration is applied at once but does not wake a window that is still, and one of 1 ms
        does). With nothing animating ``set`` takes them all, and a write to the node wakes the
        window: a change of uniforms alone draws no frame."""
        assert self._shader is not None and self.node is not None
        if self._fresh or not self._animating:
            if self._fresh or values != self._sent:
                self._shader.set(uniforms=values)
                self.node.set(shader=self._shader)
            self._fresh = False
        else:
            for key, value in values.items():
                if self._sent.get(key) != value:
                    self._shader.animate(key, value, 1)
        self._sent = dict(values)

    # -- the animation of one body ----------------------------------------------------------------

    def progress(self, name: str) -> float | None:
        """How far out ``name`` is now, as the engine has it (an animation's current value), or
        ``None`` when the shader has no such body."""
        if self._shader is None or name not in self._slots:
            return None
        value = self._shader.uniforms[f"bs{self._slots.index(name)}"]
        return float(value)  # type: ignore[arg-type]

    def begin_body(self, name: str, low: BodyGeo | None, start: float) -> bool:
        """Start drawing ``name`` at ``start`` (0 collapsed or at its tab, 1 fully out)."""
        if not self.active or self._ctx is None or name not in self._slots:
            return False
        self._lows[name] = low
        self._s[name] = start
        self._paint()
        self._move(name, start, 0)  # at once: the slide that follows starts from here
        return True

    def _move(self, name: str, value: float, ms: int) -> None:
        """Put ``name``'s ``s`` at ``value``: at once (a window that is still stays so until
        something else draws) or in ``ms``."""
        assert self._shader is not None
        key = f"bs{self._slots.index(name)}"
        self._shader.animate(key, value, ms)
        self._sent[key] = value
        self._s[name] = value

    def play_body(self, name: str, target: float, ms: int, easing: Easing) -> None:
        """Move ``name`` to ``target`` on tre's clock, from where it is."""
        assert self._shader is not None
        key = f"bs{self._slots.index(name)}"
        self._animating.add(name)
        self._shader.animate(key, target, ms, easing)
        self._sent[key] = target
        self._s[name] = target

    def seek_body(self, name: str, p: float) -> None:
        if name in self._slots and name in self._lows:
            self._move(name, p, 1)

    def end_body(self, name: str) -> None:
        """``name`` is at rest (or gone): an animation that is still running jumps to where it was
        heading and the ring is drawn again with the body as the ring has it now."""
        was = name in self._animating or name in self._lows
        if name in self._animating and name in self._s:
            self._move(name, self._s[name], 1)
        self._animating.discard(name)
        self._lows.pop(name, None)
        if was and self.active and self._ctx is not None:
            self._paint()


def _padded(geometry: Sequence[BodyGeo | None], n: int) -> list[BodyGeo | None]:
    return [*geometry, *([None] * max(n - len(geometry), 0))]


def too_large(size: tuple[float, float], scale: float) -> bool:
    """Whether the painter is too big in physical pixels for a shader node."""
    return max(size) * scale > MAX_PIXELS


class LinearJoin:
    """The join of one melded body when the ring is the shader: the body's ``s`` uniform. It has no
    nodes; the Frame draws the ring (the body at its full size) and the join animates ``s``."""

    ghost: ClassVar[bool] = False

    def __init__(self, painter: LayerWindow, ring: RingShader, name: str) -> None:
        self._painter = painter
        self._ring = ring
        self._name = name
        self._timer: Any = None

    def begin(self, run: JoinRun) -> bool:
        if run.kind != "SLIDE":
            return False
        geo = run.ring.geometry[run.index] if run.index < len(run.ring.geometry) else None
        if body_reason(geo, run.low_geo) is not None:
            return False
        return self._ring.begin_body(self._name, run.low_geo, 0.0 if run.show else 1.0)

    def play(self, show: bool, ms: int, easing: Easing, done: Callable[[], None]) -> None:
        if self._timer is not None:
            self._timer.cancel()
        self._ring.play_body(self._name, 1.0 if show else 0.0, ms, easing)
        self._timer = self._painter.after(ms, done)

    def seek(self, p: float) -> None:
        self._ring.seek_body(self._name, p)

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        self._ring.end_body(self._name)

    def destroy(self) -> None:
        self.stop()
