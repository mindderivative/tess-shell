"""The Frame: a ring around an output that reserves its sides (Frame > Parts on Tre).

Per Frame and output there are up to five windows, all on the ``top`` layer:

* one *painter*: all four anchors, size (0, 0), ``exclusive_zone`` -1 and ``input_region="auto"``.
  It draws the ring as three ``path`` nodes (outer border, fill, inner border; see
  :mod:`tess_shell.surfaces.ring`) with ``hit_shape="painted"``, so a click lands only on what is
  painted and the opening passes it on;
* up to four *reservers*, one per side with a thickness: anchored to that edge and both edges
  across it, 1 px thick, transparent, taking no input, with the side's total (thickness, borders
  and margin) as ``exclusive_zone``. They push maximised windows inside the ring.

The painter also *hosts* content (Frame > What a Frame Holds, Option A): a **strip** is a side's
``Children`` laid out in a box in that side's band (top and bottom strips own the corner squares
and run the full width, left and right strips run between them and lay their children out
vertically), and a **melded Panel** (``Meld: true``, ``Attach_To`` the Frame) is a body grown from
a side into the opening, drawn as part of the ring's one contour with a fillet at each join. Each
hosted box is bound like a Bar's tree and is a :class:`~tess_shell.surfaces.manager.Surface`
whose window is the painter, so module uses get live values, the manager's change, reload and
look paths reach it, and popups and tooltips can hang off it.

:class:`Frames` keeps them keyed like the other surfaces; :meth:`Frames.sync` brings the open
windows to a plan (start, reload, hot-plug) and changes a zone, a radius, a colour or a strip
live, without making the painter again.
"""

from __future__ import annotations

import dataclasses
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loguru import logger

from tess_shell.binder import convert
from tess_shell.binder.build import build
from tess_shell.binder.model import (
    BindError,
    BindFailed,
    Color,
    Expand,
    Length,
    Number,
    Seq,
    Value,
)
from tess_shell.model.expand import Expanded
from tess_shell.model.live import LiveTree
from tess_shell.model.look import Look, resolve_style
from tess_shell.schema.model import (
    BarDef,
    FrameBorder,
    FrameDef,
    MonitorDef,
    PanelDef,
    PeekDef,
    ShellDef,
)
from tess_shell.surfaces import handle as handles
from tess_shell.surfaces.bar import Geometry
from tess_shell.surfaces.join import Join, JoinRun, Seekable, make_join
from tess_shell.surfaces.panel import px_size
from tess_shell.surfaces.ring import MeldSpec, Rect4, Ring, RingSpec, Sides, padded, ring

if TYPE_CHECKING:
    from tess_re import LayerWindow, Output
    from tess_re import Node as TreNode

    from tess_shell.surfaces.manager import Planned, Surface, SurfaceManager

RGBA = tuple[int, int, int, int]
Box = tuple[float, float, float, float]  # x, y, width, height in the painter's logical pixels
SIDES = ("left", "top", "right", "bottom")
_ANCHORS = {
    "left": ("left", "top", "bottom"),
    "top": ("top", "left", "right"),
    "right": ("right", "top", "bottom"),
    "bottom": ("bottom", "left", "right"),
}
_SIZES = {"left": (1, 0), "top": (0, 1), "right": (1, 0), "bottom": (0, 1)}
_EMPTY = "M0,0 L0,0 Z"
# the painter's children, bottom to top: the ring, the join of a body that animates, the content of
# strips and melded Panels (a strip's blocks are never drawn over by the ring or a morph)
_Z_MORPH = 1
_Z_CONTENT = 2
_Z_HANDLE = 3  # the icon on a tab: above the ring, the join and the content
DRAG_SLOP = 4.0  # pixels a press may move and still be a click (the Edge Shell's value)
DRAG_OPENS = 0.5  # a drag released at this fraction of the way or more opens it (the Edge Shell's)
STRIP_PEEK_MS = 200  # how long a peeking strip takes to come out and go back
_DIRECTION = {"left": "vertical", "right": "vertical", "top": "horizontal", "bottom": "horizontal"}


@dataclass(frozen=True, slots=True)
class Paint:
    """The colours of a Frame, resolved: ``None`` is not drawn."""

    fill: RGBA | None = None
    outer: RGBA | None = None
    inner: RGBA | None = None
    opacity: float = 1.0


def _rgba(value: Value | None) -> RGBA | None:
    if isinstance(value, Color):
        return convert.color(value, ("fill",))["fill"]  # type: ignore[no-any-return]
    return None


def resolve_paint(frame: FrameDef, look: Look | None) -> tuple[Paint, list[BindError]]:
    """The colours of ``frame`` with every token reference replaced by ``look``'s value; the
    errors name each reference that could not be resolved (that colour is then not drawn)."""
    errors: list[BindError] = []
    style = resolve_style(frame.style or {}, look, errors)

    def border(b: FrameBorder | None, label: str) -> RGBA | None:
        if b is None or b.color is None:
            return None
        got = resolve_style({f"{label}.Color": b.color}, look, errors)
        return _rgba(got.get(f"{label}.Color"))

    opacity = style.get("Opacity")
    return (
        Paint(
            fill=_rgba(style.get("Background")),
            outer=border(frame.outer_border, "Outer_Border"),
            inner=border(frame.inner_border, "Inner_Border"),
            opacity=min(max(float(opacity.value), 0.0), 1.0)
            if isinstance(opacity, Number)
            else 1.0,
        ),
        errors,
    )


def _thickness(frame: FrameDef) -> Sides:
    """The fill band of each side: the Frame's ``Thickness`` and, for a side with an ``Edges``
    entry that gives its own, that. A strip with ``Peek`` rests as a sliver of its ``Size``: that
    is what the side holds and reserves; the rest of its ``Thickness`` is a body that comes out
    over the windows (see ``strip_body``)."""
    out = list(frame.thickness)
    for i, side in enumerate(SIDES):
        edge = frame.edges.get(side)
        if edge is not None and edge.peek is not None:
            out[i] = edge.peek.size
        elif edge is not None and edge.thickness is not None:
            out[i] = edge.thickness
    return out[0], out[1], out[2], out[3]


def _commands(path: str) -> str:
    """The commands of path data, without the numbers: two contours blend only if they match."""
    return re.sub(r"-?\d+(?:\.\d+)?", "", path)


def _extend(band: Rect4, side: str, by: float) -> Rect4:
    """``band`` grown ``by`` pixels away from the edge ``side`` (into the opening)."""
    if side == "top":
        return Rect4(band.x0, band.y0, band.x1, band.y1 + by)
    if side == "bottom":
        return Rect4(band.x0, band.y0 - by, band.x1, band.y1)
    if side == "left":
        return Rect4(band.x0, band.y0, band.x1 + by, band.y1)
    return Rect4(band.x0 - by, band.y0, band.x1, band.y1)


def strip_name(frame: FrameDef, side: str) -> str:
    """What a strip is called in logs and as the target of Show, Hide and Toggle: its ``Name``
    or ``<Frame>.<Side>``."""
    edge = frame.edges.get(side)
    if edge is not None and edge.name:
        return edge.name
    return f"{frame.name}.{side.capitalize()}"


def strip_thickness(frame: FrameDef, side: str) -> float:
    """The full thickness of a strip: its own ``Thickness`` or the Frame's for that side."""
    edge = frame.edges.get(side)
    if edge is not None and edge.thickness is not None:
        return edge.thickness
    return frame.thickness[SIDES.index(side)]


_WHOLE_SIDE = 1_000_000.0  # a body this long is clamped to the opening: it runs edge to edge


def strip_body(frame: FrameDef, side: str) -> MeldSpec:
    """The part of a peeking strip beyond its sliver, as a melded body that runs the whole side
    (both ends flush with the opening's corners) and is ``Thickness - Size`` deep: the ring draws
    it and the join animates it like any melded Panel."""
    edge = frame.edges[side]
    assert edge.peek is not None
    depth = max(strip_thickness(frame, side) - edge.peek.size, 1.0)
    along_x = side in ("top", "bottom")
    return MeldSpec(
        side=side,
        width=_WHOLE_SIDE if along_x else depth,
        height=depth if along_x else _WHOLE_SIDE,
        alignment="START",
    )


def _opaque(color: RGBA | None, paint: Paint) -> bool:
    return color is not None and color[3] == 255 and paint.opacity >= 1.0


def ring_spec(
    frame: FrameDef, melds: tuple[MeldSpec, ...] = (), paint: Paint | None = None
) -> RingSpec:
    """The ring a Frame asks for. With its ``paint``, an opaque border is sealed to the fill."""
    return RingSpec(
        seal_inner=paint is not None and _opaque(paint.inner, paint),
        seal_outer=paint is not None and _opaque(paint.outer, paint),
        thickness=_thickness(frame),
        margin=frame.margin,
        outer_radius=frame.outer_radius,
        inner_radius=frame.inner_radius,
        outer_border=frame.outer_border.width if frame.outer_border else 0,
        inner_border=frame.inner_border.width if frame.inner_border else 0,
        melds=melds,
    )


def slide_side(panel: PanelDef) -> tuple[str, str]:
    """The side a melded Panel grows from and its alignment along that side. A Panel in a corner
    with ``Peek { Slide_From }`` naming the other edge it touches grows from that edge: the body is
    the same rectangle in the corner, and slides along its other extent (its ``Length`` becomes the
    depth). Aligned START or END along ``Attach``, the Panel is against the opening's corner, so
    the end it is aligned to says which end of the new side it sits at."""
    side = (panel.attach or "TOP").lower()
    peek = panel.peek
    if peek is None or peek.slide_from is None or peek.slide_from.lower() == side:
        return side, panel.alignment
    new = peek.slide_from.lower()
    return new, "START" if side in ("top", "left") else "END"


def meld_spec(panel: PanelDef, output: tuple[int, int], look: Look | None) -> MeldSpec:
    """The body a melded Panel asks for: its ``Depth`` (away from the Frame's edge) and ``Length``
    (along it), the side it grows from (``Attach``, or ``Slide_From`` of a corner Panel),
    ``Alignment`` along it and the ``Corner_Radius`` of its style. On a top or bottom side the
    length runs along x."""
    attached = (panel.attach or "TOP").lower()
    along_x = attached in ("top", "bottom")
    side, alignment = slide_side(panel)
    depth, length = panel.depth, panel.length
    style = resolve_style(panel.style or {}, look)
    radius = style.get("Corner_Radius")
    corners: tuple[float, float, float, float] = (0, 0, 0, 0)
    if isinstance(radius, Length):
        r = float(radius.px)
        corners = (r, r, r, r)
    elif isinstance(radius, Seq) and len(radius.items) == 4:
        a, b, c, d = (float(x.px) if isinstance(x, Length) else 0.0 for x in radius.items)
        corners = (a, b, c, d)
    return MeldSpec(
        side=side,
        width=px_size(length if along_x else depth, output[0]),
        height=px_size(depth if along_x else length, output[1]),
        alignment=alignment,
        radius=corners,
    )


_TEXT_INPUT_KINDS = ("TextInput",)  # no such block yet: the painter's keyboard stays "none"


def wants_keyboard(expanded: Expanded) -> bool:
    """Whether a hosted tree holds a text input (Frame > What a Frame Holds: the painter then
    takes the keyboard ``on_demand``)."""

    def walk(nodes: Sequence[Any]) -> bool:
        for node in nodes:
            if getattr(node, "kind", None) in _TEXT_INPUT_KINDS:
                return True
            for attr in ("children", "body", "else_body"):
                if walk(getattr(node, attr, None) or ()):
                    return True
        return False

    return walk(expanded.nodes)


@dataclass(frozen=True, slots=True)
class PeekPlan:
    """A ``Peek`` as planned: the pixels at rest (a tab of a melded Panel, the sliver of a strip),
    the pixels of the whole (the Panel's ``Depth``, the strip's ``Thickness``) and the delays."""

    size: float
    full: float
    enter_delay: float
    exit_delay: float
    trigger: str = "HOVER"  # HOVER, CLICK or DRAG
    handle: str | None = None  # the icon drawn on the tab: DOTS, BAR or CHEVRON; None draws none


@dataclass(slots=True)
class HostPlan:
    """Content hosted in the painter: a strip or a melded Panel."""

    key: str
    name: str  # a strip: ``<Frame>.<Side>`` or its ``Name``; a melded Panel: its ``Name``
    kind: str  # "strip" or "meld"
    side: str  # left, top, right, bottom
    planned: Planned
    padding: Sides = (0, 0, 0, 0)
    peek: PeekPlan | None = None


@dataclass(slots=True)
class FramePlan:
    """One Frame on one output, as planned: nothing is open yet."""

    key: str  # ``<Shell>.<Monitor>[@<output>].<Frame>``, like a Bar's
    frame: FrameDef
    output: Output
    group: str  # ``<Monitor>@<output>``
    size: tuple[int, int]  # the output's logical size
    ring: Ring
    paint: Paint
    hosts: list[HostPlan] = field(default_factory=list)
    # every melded Panel, then the body of every peeking strip (named like its host)
    melds: list[tuple[str, MeldSpec]] = field(default_factory=list)
    peeks: dict[str, PeekPlan] = field(default_factory=dict)  # by host name

    @property
    def where(self) -> str:
        return f"{self.frame.name} on {self.output.name}"

    def uses(self) -> list[Any]:
        return [u for h in self.hosts for u in h.planned.expanded.uses]

    def rest_tab(self, name: str, visible: bool) -> bool:
        """Whether a melded Panel rests as a tab (it has a ``Peek`` and is ``Visible``)."""
        return visible and name in self.peeks and name in {p.name for p in self.frame.melds}

    def rest_sets(self) -> tuple[frozenset[str], frozenset[str]]:
        """Where each melded body is at start: the names hidden (a ``Visible: false`` Panel, the
        body of a strip that peeks) and the names at rest as a tab."""
        panels = {p.name: p for p in self.frame.melds}
        strips = {name for name, _ in self.melds if name not in panels}
        hidden = {n for n, p in panels.items() if not p.visible} | strips
        tabs = {n for n, p in panels.items() if self.rest_tab(n, p.visible)}
        return frozenset(hidden), frozenset(tabs)

    def refresh_melds(self, look: Look | None) -> None:
        """Take the bodies of the Panels again from ``look`` (a token may have changed a radius);
        the bodies of the strips stay."""
        panels = {p.name for p in self.frame.melds}
        kept = [(n, spec) for n, spec in self.melds if n not in panels]
        self.melds = kept + [(p.name, meld_spec(p, self.size, look)) for p in self.frame.melds]

    def ring_for(
        self,
        size: tuple[float, float],
        hidden: frozenset[str],
        tabs: frozenset[str] = frozenset(),
    ) -> Ring:
        """The ring at ``size`` with the melded bodies not in ``hidden``, those in ``tabs`` only
        as deep as their peek (a tab), the others at full depth."""
        melds = tuple(
            spec.shallow(self.peeks[name].size) if name in tabs and name in self.peeks else spec
            for name, spec in self.melds
            if name not in hidden
        )
        return ring(ring_spec(self.frame, melds, self.paint), size)


@dataclass(frozen=True, slots=True)
class Axis:
    """Where a peeking body slides, in the painter's pixels: ``(ox, oy)`` is the point on the near
    edge (the Frame's band edge for a Panel, the screen-side edge of a strip's band) at the middle
    of the body along it, ``(nx, ny)`` the unit vector into the opening, ``size`` the depth of the
    tab or sliver and ``full`` the depth of the whole."""

    side: str
    ox: float
    oy: float
    nx: float
    ny: float
    size: float
    full: float

    def depth_of(self, x: float, y: float) -> float:
        """How far the painter's point is from the near edge, along the slide."""
        return (x - self.ox) * self.nx + (y - self.oy) * self.ny

    def point(self, depth: float) -> tuple[float, float]:
        return self.ox + self.nx * depth, self.oy + self.ny * depth


@dataclass(slots=True)
class Drag:
    """A press on a peek whose ``Trigger`` is DRAG, until the button goes up."""

    start: float  # the depth of the pointer at the press
    p0: float  # how far out the body was then: 0 at its tab, 1 out
    p: float = 0.0  # how far out it follows the pointer now
    moved: bool = False  # the pointer has gone past DRAG_SLOP
    began: bool = False  # the join is drawing it


@dataclass(slots=True)
class HostState:
    plan: HostPlan
    surface: Surface
    container: TreNode  # the box the tree is bound under
    # a melded Panel only: ``clip`` (clips to the body) holds ``mover`` (the node an animation
    # translates or fades) which holds the ``container``; ``join`` draws the body and its fillets
    # while it animates (see "a melded Panel" below and ``surfaces/join.py``)
    clip: TreNode | None = None
    mover: TreNode | None = None
    join: Join | None = None
    anim: str | None = None  # "in" (showing) or "out" (hiding) while an animation runs
    kind: str = "NONE"  # the animation that runs: SLIDE or FADE
    away: tuple[str, float] = ("translate_y", 0.0)  # the property and value of "not shown"
    # a peek: whether the pointer is on the host (its ``clip``) and the delays that wait to act
    inside: bool = False
    enter_timer: Any = None
    exit_timer: Any = None
    handle: handles.Handle | None = None  # the icon on the tab (Peek { Handle })
    axis: Axis | None = None  # where it slides, as last placed
    drag: Drag | None = None


@dataclass(slots=True)
class FrameState:
    plan: FramePlan
    hidden: bool = False  # closed by a Hide (or ``Visible: false``): no window at all
    size: tuple[float, float] = (0, 0)  # what the ring was last drawn for
    painter: LayerWindow | None = None
    nodes: list[TreNode] = field(default_factory=list)  # outer border, fill, inner border
    reservers: dict[str, LayerWindow] = field(default_factory=dict)
    zones: dict[str, int] = field(default_factory=dict)  # the zone each reserver holds
    drawn: Any = None  # what the nodes were last set to, so an equal draw sets nothing
    hosts: dict[str, HostState] = field(default_factory=dict)
    hidden_melds: set[str] = field(default_factory=set)  # melded bodies hidden now (a strip's at
    # rest: it is the sliver that shows)
    tab_melds: set[str] = field(default_factory=set)  # melded Panels at rest as a tab
    shape: Ring | None = None  # the ring as last drawn, without the melded bodies that animate
    full: Ring | None = None  # the ring with every melded Panel that is shown or on its way
    keyboard: str = "none"
    # the whole bodies of the melded Panels that peek, for the plan and size they were made for
    full_rects: tuple[Any, ...] = ()


class Frames:
    """The Frames of the shell. They share the manager's value store, look, dispatcher and
    popups, so what a strip or a melded Panel holds behaves like what a Bar holds."""

    def __init__(self, manager: SurfaceManager) -> None:
        self._m = manager
        self._look: Look | None = None
        self.states: dict[str, FrameState] = {}
        self._warned: set[str] = set()  # join options already warned about

    # -- planning: no side effect but logging ---------------------------------------------------

    def plan(
        self,
        shell: ShellDef,
        outputs: Sequence[Output],
        assigned: Sequence[tuple[MonitorDef, list[int]]],
        look: Look | None,
        by_output: Callable[[MonitorDef], bool],
        expand: Callable[[tuple[Any, ...], str, str, bool], Expanded],
    ) -> list[FramePlan]:
        """The Frame of each Monitor on each output it applies to. ``by_output`` says whether a
        Monitor's keys carry the output (the same rule as its Bars' keys); ``expand`` expands the
        children of a strip or a melded Panel (``children, path, output name, has popups``). A
        radius the ring cannot hold is reduced and a warning names it; a token that does not
        resolve is logged."""
        from tess_shell.surfaces.manager import Planned

        plans: list[FramePlan] = []
        for monitor, indices in assigned:
            for frame in monitor.frames:
                for i in indices:
                    output = outputs[i]
                    suffix = f"@{output.name}" if by_output(monitor) else ""
                    prefix = f"{shell.name}.{monitor.name}{suffix}"
                    size = (output.width, output.height)
                    panels = [(p.name, meld_spec(p, size, look)) for p in frame.melds]
                    paint, errors = resolve_paint(frame, look)
                    peeks, bodies = self._peeks(frame, panels, output.name)
                    plan = FramePlan(
                        f"{prefix}.{frame.name}",
                        frame,
                        output,
                        f"{monitor.name}@{output.name}",
                        size,
                        ring(ring_spec(frame), size),  # replaced below, once the hosts are known
                        paint,
                        melds=bodies + panels,
                        peeks=peeks,
                    )
                    plan.ring = plan.ring_for(size, *plan.rest_sets())
                    where = plan.where
                    for warning in plan.ring.warnings:
                        logger.warning(f"{frame.origin}: Frame {where}: {warning}")
                    for error in errors:
                        logger.error(
                            f"{error.origin}: {error.message}"
                            + (f" ({error.hint})" if error.hint else "")
                        )
                    geometry = Geometry(
                        ("top", "right", "bottom", "left"), (0, 0), (0, 0, 0, 0), -1
                    )
                    has_popups = bool(monitor.popups)
                    for side in SIDES:
                        edge = frame.edges.get(side)
                        if edge is None or not edge.children:
                            continue
                        key = f"{plan.key}.{side.capitalize()}"
                        bar = BarDef(
                            strip_name(frame, side),
                            edge.origin,
                            side.upper(),
                            Expand(),
                            Length(0),
                            style={},
                            children=edge.children,
                        )
                        expanded = expand(edge.children, key, output.name, has_popups)
                        planned = Planned(
                            key,
                            bar,
                            output,
                            expanded,
                            geometry,
                            f"{bar.name} on {output.name}",
                            plan.group,
                        )
                        pad = edge.padding if edge.padding is not None else frame.padding
                        plan.hosts.append(
                            HostPlan(
                                key,
                                bar.name,
                                "strip",
                                side,
                                planned,
                                pad,
                                peeks.get(bar.name),
                            )
                        )
                    for panel in frame.melds:
                        key = f"{prefix}.{panel.name}"
                        expanded = expand(panel.children, key, output.name, has_popups)
                        planned = Planned(
                            key,
                            panel,
                            output,
                            expanded,
                            geometry,
                            f"{panel.name} on {output.name}",
                            plan.group,
                        )
                        plan.hosts.append(
                            HostPlan(
                                key,
                                panel.name,
                                "meld",
                                slide_side(panel)[0],
                                planned,
                                peek=peeks.get(panel.name),
                            )
                        )
                    plans.append(plan)
        return plans

    @staticmethod
    def _handle_kind(
        frame: FrameDef, name: str, peek: PeekDef, side: str, output: str
    ) -> str | None:
        """The handle a peek draws: what ``Handle`` and ``Trigger`` say, or ``None`` when it is
        ``NONE`` or does not fit (the tab or the side is thinner than the handle's minimum: one
        DEBUG line, not an error)."""
        kind = handles.resolve(peek.handle, peek.trigger)
        if kind is None:
            return None
        thickness = _thickness(frame)[SIDES.index(side)]
        if not handles.fits(kind, peek.size, thickness):
            logger.debug(
                f"Frame {frame.name} on {output}: {name} has no {kind.lower()} handle: its tab "
                f"({peek.size:g} px) or the {side} side ({thickness:g} px) is thinner than "
                f"{handles.MIN_THICKNESS[kind]:g} px"
            )
            return None
        return kind

    @staticmethod
    def _peeks(
        frame: FrameDef, panels: list[tuple[str, MeldSpec]], output: str
    ) -> tuple[dict[str, PeekPlan], list[tuple[str, MeldSpec]]]:
        """The peek of each melded Panel and strip that has one, and the bodies of the strips
        (first, so that on a side they share a strip that is out covers a Panel). A Panel's Size
        is checked against its Depth here: a percentage is known only now."""
        peeks: dict[str, PeekPlan] = {}
        depth = {name: spec.depth for name, spec in panels}
        for panel in frame.melds:
            peek = panel.peek
            if peek is None:
                continue
            if peek.size >= depth[panel.name]:
                logger.error(
                    f"{peek.origin or panel.origin}: Panel {panel.name} on {output}: Peek Size "
                    f"{peek.size:g} is not smaller than its Depth {depth[panel.name]:g}: "
                    "it has no peek here"
                )
                continue
            peeks[panel.name] = PeekPlan(
                peek.size,
                depth[panel.name],
                peek.enter_delay,
                peek.exit_delay,
                peek.trigger,
                Frames._handle_kind(frame, panel.name, peek, slide_side(panel)[0], output),
            )
        bodies: list[tuple[str, MeldSpec]] = []
        for side in SIDES:
            edge = frame.edges.get(side)
            if edge is None or edge.peek is None or not edge.children:
                continue
            name = strip_name(frame, side)
            peeks[name] = PeekPlan(
                edge.peek.size,
                strip_thickness(frame, side),
                edge.peek.enter_delay,
                edge.peek.exit_delay,
                edge.peek.trigger,
                Frames._handle_kind(frame, name, edge.peek, side, output),
            )
            bodies.append((name, strip_body(frame, side)))
            for panel in frame.melds:
                if slide_side(panel)[0] == side:
                    logger.warning(
                        f"{panel.origin}: Panel {panel.name} melds into the {side} side, which "
                        f"has the peeking strip {name}: the Panel is covered while the strip "
                        "is out"
                    )
        return peeks, bodies

    # -- opening, reloading, hot-plug -----------------------------------------------------------

    def sync(self, plans: Sequence[FramePlan], look: Look | None = None) -> None:
        """Make the open Frames match ``plans``: close the windows of a Frame that is gone (or
        that moved to another output), open a new one, and bring a kept one to the new ring and
        zones by ``set``, adding or closing a reserver when a side gains or loses its thickness,
        and its strips and melded Panels by the keyed diff. A Frame hidden at run time stays
        hidden unless its ``Visible`` changed in the file; so does a melded Panel."""
        if look is not None:
            self._look = look
        wanted = {p.key: p for p in plans}
        for key in [k for k in self.states if k not in wanted]:
            self._close(self.states.pop(key))
        for key, plan in wanted.items():
            st = self.states.get(key)
            if st is not None and st.plan.output.name != plan.output.name:
                self._close(self.states.pop(key))
                st = None
            if st is None:
                st = self.states[key] = FrameState(plan, hidden=not plan.frame.visible)
                hidden, tabs = plan.rest_sets()
                st.hidden_melds, st.tab_melds = set(hidden), set(tabs)
            else:
                if plan.frame.visible != st.plan.frame.visible:
                    st.hidden = not plan.frame.visible
                before = {p.name: p.visible for p in st.plan.frame.melds}
                for p in plan.frame.melds:
                    if p.name not in before or before[p.name] != p.visible:
                        # the file decides: nothing is left as the run left it
                        st.hidden_melds.discard(p.name)
                        st.tab_melds.discard(p.name)
                        if not p.visible:
                            st.hidden_melds.add(p.name)
                        elif plan.rest_tab(p.name, True):
                            st.tab_melds.add(p.name)
                        for host in st.hosts.values():
                            if host.plan.name == p.name and host.anim:
                                self._snap(host)
                hidden, _ = plan.rest_sets()
                for name in hidden - {n for n, _ in st.plan.melds}:  # a strip that peeks, new
                    st.hidden_melds.add(name)
                names = {n for n, _ in plan.melds}
                st.hidden_melds &= names
                st.tab_melds &= {p.name for p in plan.frame.melds if p.name in plan.peeks}
                for host in st.hosts.values():  # a Panel that lost its Peek is shown, not a tab
                    if (
                        host.plan.peek is not None
                        and host.plan.name not in plan.peeks
                        and host.anim
                    ):
                        self._snap(host)
                if plan.size != st.plan.size:
                    st.size = plan.size  # the output changed: draw for it until tre configures
                st.plan = plan
            self._reconcile(st)

    def set_look(self, look: Look) -> None:
        """The theme or the accent changed: every token is read again, the ring is redrawn in
        place and what the strips and melded Panels hold is rebuilt by the keyed diff."""
        self._look = look
        for st in self.states.values():
            paint, errors = resolve_paint(st.plan.frame, look)
            for error in errors:
                logger.error(f"{error.origin}: {error.message}")
            st.plan.paint = paint
            st.plan.refresh_melds(look)  # a token may have changed a body's radius
            self._draw(st)
            for host in st.hosts.values():
                if host.surface.view is not None:
                    host.surface.live.look = look
                    self._m._rebuild(host.surface)

    def names(self) -> set[str]:
        """The ``Name`` of every Frame and melded Panel (the target of ``Show``, ``Hide`` and
        ``Toggle``)."""
        out: set[str] = set()
        for st in self.states.values():
            out.add(st.plan.frame.name)
            out.update(p.name for p in st.plan.frame.melds)
            out.update(n for n in st.plan.peeks)  # a strip that peeks has a ``Name``
        return out

    def host_surfaces(self) -> list[Surface]:
        """The open strips and melded Panels, as surfaces whose window is a painter."""
        return [h.surface for st in self.states.values() for h in st.hosts.values()]

    def run(self, action: str, target: object) -> bool:
        """``Show``, ``Hide`` or ``Toggle`` on the Frame or melded Panel named ``target``;
        ``False`` when none has that name. Hiding a Frame closes every window of it, so its zones
        are released and windows use the whole output; showing makes them again. Hiding a melded
        Panel takes its body out of the ring's contour; the ring closes up where it was."""
        found = False
        for st in self.states.values():
            if st.plan.frame.name == target:
                found = True
                hide = not st.hidden if action == "Toggle" else action == "Hide"
                if hide != st.hidden:
                    st.hidden = hide
                    logger.info(f"Frame {st.plan.where} {'hidden' if hide else 'shown'}")
                    self._reconcile(st)
            elif any(h.name == target and (h.kind == "meld" or h.peek) for h in st.plan.hosts):
                found = True
                host = next((h for h in st.hosts.values() if h.plan.name == target), None)
                if host is None:  # the Frame is hidden: nothing is drawn, so nothing to move
                    name = str(target)
                    out = name not in st.hidden_melds and name not in st.tab_melds
                    hide = out if action == "Toggle" else action == "Hide"
                    self._set_rest(st, name, hide)
                    continue
                if action == "Toggle":
                    self._m._fire(host.surface, "On_Toggle")  # before: the request is made
                show = host.surface.hidden if action == "Toggle" else action == "Show"
                self._meld_to(st, host, show)
        return found

    def _set_rest(self, st: FrameState, name: str, hide: bool) -> None:
        """Put a melded body at rest at once: out (``hide`` false), or hidden or a tab."""
        st.hidden_melds.discard(name)
        st.tab_melds.discard(name)
        if hide:
            panel = next((p for p in st.plan.frame.melds if p.name == name), None)
            if panel is not None and st.plan.rest_tab(name, panel.visible):
                st.tab_melds.add(name)
            else:
                st.hidden_melds.add(name)

    # -- windows --------------------------------------------------------------------------------

    def _close(self, st: FrameState) -> None:
        self._drop_hosts(st)
        painter, reservers = st.painter, list(st.reservers.values())
        st.painter, st.nodes, st.reservers, st.zones, st.drawn = None, [], {}, {}, None
        for window in (painter, *reservers):
            if window is not None:
                self._shut(st, window)

    @staticmethod
    def _shut(st: FrameState, window: LayerWindow) -> None:
        try:
            window.close()
        except Exception:  # tre already closed it (its output went away): nothing to do
            logger.debug(f"Frame {st.plan.where}: a window was already closed", exc_info=True)

    def _reconcile(self, st: FrameState) -> None:
        plan = st.plan
        if st.hidden:
            if st.painter is not None or st.reservers:
                self._close(st)
            return
        if st.painter is None:
            self._open_painter(st)
        self._draw(st)
        self._reconcile_hosts(st)
        self._set_keyboard(st)
        for side, zone in zip(SIDES, plan.ring.totals, strict=True):
            window = st.reservers.get(side)
            if zone == 0:
                if window is not None:
                    st.reservers.pop(side)
                    st.zones.pop(side, None)
                    self._shut(st, window)
            elif window is None:
                self._open_reserver(st, side, zone)
            elif st.zones.get(side) != zone:
                try:
                    window.set(exclusive_zone=zone)
                except (ValueError, RuntimeError) as exc:
                    logger.error(f"Frame {plan.where}: {side} zone {zone}: {exc}")
                    continue
                st.zones[side] = zone
                logger.info(f"Frame {plan.where}: {side} zone {zone}")

    def _open_painter(self, st: FrameState) -> None:
        from tess_re import LayerWindow

        plan = st.plan
        window = LayerWindow(
            f"tesserae-shell.frame.{plan.frame.name}",
            layer="top",
            anchor=("top", "right", "bottom", "left"),
            size=(0, 0),
            exclusive_zone=-1,
            keyboard="none",
            input_region="auto",
            output=plan.output.name,
        )
        st.size = plan.size
        st.nodes = []
        st.keyboard = "none"
        for _ in range(3):
            node = window.create(
                "path",
                data=_EMPTY,
                hit_shape="painted",
                a11y_hidden=True,  # the ring is decoration (Frame > Accessibility)
                position="absolute",
                left=0,
                top=0,
                width=plan.size[0],
                height=plan.size[1],
                visible=False,
            )
            window.root.add_child(node)
            st.nodes.append(node)
        st.painter, st.drawn = window, None
        where = plan.where

        def configure(event: Any, st: FrameState = st) -> None:
            size = (float(event.width), float(event.height))
            logger.info(f"Frame {where} painter configured {int(size[0])}x{int(size[1])}")
            if size[0] > 0 and size[1] > 0 and size != st.size:
                st.size = size  # the surface is not the size the output reported: draw for it
                self._draw(st)

        def closed(event: Any, st: FrameState = st, window: Any = window) -> None:
            logger.info(f"Frame {where} painter closed ({getattr(event, 'reason', '')})")
            if st.painter is window:
                self._drop_hosts(st)
                st.painter = None  # a later sync makes it again

        def pointer_down(event: Any) -> None:
            self._m.popups.surface_pointer_down()  # tre gives a click on a surface to the surface

        def key_down(event: Any) -> None:
            logger.debug(f"Frame {where} painter key {getattr(event, 'key', None)!r}")

        window.on("configure", configure)
        window.on("closed", closed)
        window.root.on("pointer_down", pointer_down)
        window.root.on("key_down", key_down)  # a key bubbles up from the focused node
        self._m._app.add_window(window)
        logger.info(
            f"Frame {where}: painter {plan.size[0]}x{plan.size[1]}, zones "
            + ",".join(str(z) for z in plan.ring.totals)
        )

    def _open_reserver(self, st: FrameState, side: str, zone: int) -> None:
        from tess_re import LayerWindow

        plan = st.plan
        window = LayerWindow(
            f"tesserae-shell.frame.{plan.frame.name}.{side}",
            layer="top",
            anchor=_ANCHORS[side],
            size=_SIZES[side],
            exclusive_zone=zone,
            keyboard="none",
            input_region=[],
            output=plan.output.name,
        )
        st.reservers[side], st.zones[side] = window, zone
        where = plan.where

        def closed(event: Any, st: FrameState = st, window: Any = window) -> None:
            if st.reservers.get(side) is window:
                st.reservers.pop(side)
                st.zones.pop(side, None)

        window.on("closed", closed)
        self._m._app.add_window(window)
        logger.info(f"Frame {where}: {side} reserver, zone {zone}")

    def _set_keyboard(self, st: FrameState) -> None:
        """``on_demand`` when the Frame asks for it (``Keyboard: ON_DEMAND``) or a strip or melded
        Panel holds a text input (Frame > What a Frame Holds), else ``none``."""
        if st.painter is None:
            return
        mode = (
            "on_demand"
            if st.plan.frame.keyboard == "ON_DEMAND"
            or any(wants_keyboard(h.plan.planned.expanded) for h in st.hosts.values())
            else "none"
        )
        if mode != st.keyboard:
            st.painter.set(keyboard=mode)
            st.keyboard = mode
            logger.info(f"Frame {st.plan.where}: painter keyboard {mode}")

    def _draw(self, st: FrameState) -> None:
        """Set the ring's three nodes to the ring and colours, and each hosted box to its place;
        nothing is set that is equal to what was set before."""
        if st.painter is None:
            return
        plan = st.plan
        moving = {h.plan.name for h in st.hosts.values() if h.anim}
        tab_moving = {n for n in moving if self._rest_is_tab(st, n)}  # they keep their tab
        shape = plan.ring_for(
            st.size,
            frozenset(st.hidden_melds | (moving - tab_moving)),
            frozenset(st.tab_melds | tab_moving),
        )
        st.shape = shape
        # the bodies of the Panels that animate are in ``full`` only (at full depth), drawn by
        # their own join; a tab at rest is as deep as its peek
        st.full = (
            plan.ring_for(st.size, frozenset(st.hidden_melds), frozenset(st.tab_melds - moving))
            if moving
            else shape
        )
        paint = plan.paint
        sliding = any(
            h.anim and h.kind == "SLIDE" and h.join is not None and h.join.ghost
            for h in st.hosts.values()
        )

        def ghost(color: RGBA | None) -> RGBA | None:
            """Under a sliding body's join the ring nodes are only the shape that takes clicks."""
            return (color[0], color[1], color[2], 1) if sliding and color is not None else color

        bands = (
            (shape.outer_border, paint.outer),
            (shape.fill, ghost(paint.fill)),
            (shape.inner_border, ghost(paint.inner)),
        )
        key = (st.size, paint.opacity, bands)
        if key != st.drawn:
            for node, (data, color) in zip(st.nodes, bands, strict=True):
                props: dict[str, Any] = {
                    "width": st.size[0],
                    "height": st.size[1],
                    "opacity": paint.opacity,
                }
                if data and color is not None:
                    props.update(data=data, fill=color, visible=True)
                else:
                    props["visible"] = False
                node.set(**props)
            st.drawn = key
        for host in st.hosts.values():
            if host.clip is not None:
                self._place_meld(st, host)
            else:
                self._place(st, host.plan, host.container, host.surface)

    # -- strips and melded Panels ---------------------------------------------------------------

    def _rect(self, st: FrameState, hp: HostPlan) -> tuple[float, float, float, float] | None:
        """Where a hosted box sits in the painter: a strip's band less its padding; a melded
        Panel's body. ``None`` for a hidden or unplaced one."""
        shape = st.shape
        if shape is None:
            return None
        if hp.kind == "strip":
            r = padded(shape.bands[SIDES.index(hp.side)], hp.padding)
            return (r.x0, r.y0, r.width, r.height)
        full = st.full or shape
        visible = [name for name, _ in st.plan.melds if name not in st.hidden_melds]
        if hp.name not in visible or not full.bodies:
            return None
        body = full.bodies[visible.index(hp.name)]
        return None if body is None else (body.x0, body.y0, body.width, body.height)

    def _place(self, st: FrameState, hp: HostPlan, container: TreNode, surface: Surface) -> None:
        rect = self._rect(st, hp)
        if rect is None or rect[2] <= 0 or rect[3] <= 0:
            if not surface.hidden:
                self._m.popups.parent_closed(surface)
                container.set(visible=False)
                surface.hidden = True
            return
        x, y, w, h = rect
        container.set(left=x, top=y, width=w, height=h, visible=True)
        surface.hidden = False

    # -- a melded Panel: placement, show, hide and the animation ---------------------------------
    #
    # At rest a shown body is part of the ring's one contour (one ``path`` node, painted hit
    # shape). While it animates, the ring nodes are drawn without it and a *join* (``join.py``,
    # chosen by ``Debug { Frame_Join }``) draws the body with its fillets growing out of the band,
    # on tre's own clock. The default join is PARAM (a path template whose depth and fillet radius
    # tre animates); SMIL is an ``svg`` holding the contour at depth 0 and at full depth with the
    # same commands, an ``<animate attributeName="d">`` between them sampled at ``svg_time``. The
    # body's content moves with it (``translate`` of the mover node, on the same clock and easing)
    # inside the clip box, which is the body at rest. When it
    # ends the ring nodes take the body back and the join stops drawing; the two renderings agree
    # to the pixel (tests/test_frame_anim.py). A join that ``ghost``s (the SMIL svg takes no
    # input) has the ring nodes drawn at alpha 1 meanwhile so they keep the ring's click shape.
    # FADE draws the ring without the body, and the join draws it faded in or out.

    def _rest_is_tab(self, st: FrameState, name: str) -> bool:
        """Whether ``name`` is a melded Panel that rests as a tab: it has a ``Peek`` and is
        ``Visible`` in the plan now."""
        panel = next((p for p in st.plan.frame.melds if p.name == name), None)
        return panel is not None and st.plan.rest_tab(name, panel.visible)

    def _geometry(
        self, st: FrameState, host: HostState
    ) -> tuple[Box, Box, tuple[str, float]] | None:
        """Where a hosted body sits in the painter: its clip box (the visible part: at rest a tab
        or a sliver, else the whole), its content box relative to the clip, and the translation
        that puts the content out of the clip. ``None`` when it is hidden or not placed."""
        hp = host.plan
        if hp.kind == "strip":
            if st.shape is None or hp.peek is None:
                return None
            base = st.shape.bands[SIDES.index(hp.side)]
            band = _extend(base, hp.side, hp.peek.full - hp.peek.size)
            clip = base if hp.name in st.hidden_melds and not host.anim else band
            inner = padded(band, hp.padding)
            by = hp.peek.full
            box = (inner.x0 - clip.x0, inner.y0 - clip.y0, inner.width, inner.height)
            away = {
                "top": ("translate_y", -by),
                "bottom": ("translate_y", by),
                "left": ("translate_x", -by),
                "right": ("translate_x", by),
            }[hp.side]
            return (clip.x0, clip.y0, clip.width, clip.height), box, away
        rect = self._rect(st, hp)
        if rect is None:
            return None
        x, y, w, h = rect
        away = {
            "top": ("translate_y", -h),
            "bottom": ("translate_y", h),
            "left": ("translate_x", -w),
            "right": ("translate_x", w),
        }[hp.side]
        return rect, (0, 0, w, h), away

    def _place_meld(self, st: FrameState, host: HostState) -> None:
        """Put a melded Panel's (or a peeking strip's) clip box and content where the ring says."""
        surface = host.surface
        assert host.clip is not None and host.mover is not None
        geometry = self._geometry(st, host)
        if geometry is None or st.full is None or st.shape is None:
            if not surface.hidden:
                self._m.popups.parent_closed(surface)
                surface.hidden = True
            host.clip.set(visible=False)
            if host.join is not None:
                host.join.stop()
            host.axis = None
            self._place_handle(st, host)
            return
        (x, y, w, h), (ix, iy, iw, ih), host.away = geometry
        name = host.plan.name
        # a tab or a sliver shows no content: it is clipped away but would still take clicks
        resting = host.anim is None and (name in st.hidden_melds or name in st.tab_melds)
        host.clip.set(left=x, top=y, width=w, height=h, visible=True)
        host.mover.set(width=w, height=h)
        host.container.set(left=ix, top=iy, width=iw, height=ih, visible=not resting)
        surface.hidden = host.anim == "out" or resting
        host.axis = self._axis(st, host)
        self._place_handle(st, host)

    # -- the handle: the icon on a tab or a sliver ----------------------------------------------

    def _full_rect(self, st: FrameState, name: str) -> Rect4 | None:
        """The whole body of the melded Panel ``name`` (not its tab), from the ring with every
        other body left out; kept for the plan and size it was made for."""
        if not st.full_rects or st.full_rects[0] is not st.plan or st.full_rects[1] != st.size:
            st.full_rects = (st.plan, st.size, {})
        cache: dict[str, Rect4 | None] = st.full_rects[2]
        if name not in cache:
            alone = st.plan.ring_for(
                st.size, frozenset(n for n, _ in st.plan.melds if n != name), frozenset()
            )
            cache[name] = alone.bodies[0] if alone.bodies else None
        return cache[name]

    def _axis(self, st: FrameState, host: HostState) -> Axis | None:
        """The slide of a peeking host: from its near edge into the opening, ``Size`` px at rest and
        the whole depth out."""
        hp = host.plan
        peek = hp.peek
        if peek is None or st.shape is None:
            return None
        side = hp.side
        if hp.kind == "strip":
            r = st.shape.bands[SIDES.index(side)]
            full = peek.full
        else:
            body = self._full_rect(st, hp.name)
            if body is None:
                return None
            r = body
            full = body.height if side in ("top", "bottom") else body.width
        edge = {"top": r.y0, "bottom": r.y1, "left": r.x0, "right": r.x1}[side]
        cx, cy = (r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2
        ox, oy = (cx, edge) if side in ("top", "bottom") else (edge, cy)
        nx, ny = handles.TOWARD[side]
        return Axis(side, ox, oy, nx, ny, peek.size, full)

    def _handle_colour(self, st: FrameState) -> RGBA:
        """The handle's colour: the Frame's inner border, else its outer, else a light or dark
        that shows on the fill."""
        paint = st.plan.paint
        for colour in (paint.inner, paint.outer):
            if colour is not None and colour[3] > 0:
                return colour
        fill = paint.fill
        light = fill is None or (0.299 * fill[0] + 0.587 * fill[1] + 0.114 * fill[2]) < 140
        return (235, 235, 235, 255) if light else (30, 30, 30, 255)

    def _rest_state(self, st: FrameState, host: HostState) -> str:
        """``tab`` (a Panel's tab or a strip's sliver), ``hidden`` (a Panel with nothing showing)
        or ``out``."""
        name = host.plan.name
        if name in st.tab_melds or (host.plan.kind == "strip" and name in st.hidden_melds):
            return "tab"
        return "hidden" if name in st.hidden_melds else "out"

    def _place_handle(self, st: FrameState, host: HostState) -> None:
        """Make, change or remove the host's handle and put it where the state says: at the middle
        of the tab, or of the far strip of the body when it is out. While it slides the holder is
        at the tab and its ``translate`` is animated (see ``_run``)."""
        peek = host.plan.peek
        want = peek.handle if peek is not None else None
        have = host.handle
        if have is not None and (want is None or (have.kind, have.side) != (want, host.plan.side)):
            have.destroy()
            host.handle = have = None
        if want is None or st.painter is None:
            return
        if have is None:
            have = host.handle = handles.make(
                st.painter, want, host.plan.side, _Z_HANDLE, self._handle_colour(st)
            )
        axis = host.axis
        state = self._rest_state(st, host)
        if axis is None or (state == "hidden" and host.anim is None):
            have.holder.set(visible=False)
            return
        out = state == "out" and host.anim is None
        fade = host.anim is not None and host.kind == "FADE"
        depth = axis.size / 2 + (axis.full - axis.size) * (1.0 if out or fade else 0.0)
        have.place(*axis.point(depth))
        have.holder.set(visible=True)
        have.paint(self._handle_colour(st))
        if host.anim is None or fade:
            have.seek(1.0 if out or fade else 0.0, 0.0, 0.0)

    def _snap(self, host: HostState) -> None:
        """Stop an animation where it is and put the node back to rest."""
        host.anim = None
        host.drag = None
        host.surface.generation += 1
        self._cancel_hover(host)
        if host.mover is not None:
            host.mover.set(translate_x=0, translate_y=0, opacity=1.0)
        if host.join is not None:
            host.join.stop()

    def _reduced(self) -> bool:
        look = self._m._look
        return bool(look is not None and look.appearance.reduced_motion)

    def _timer(self, host: HostState, st: FrameState) -> None:
        """(Re)start the ``Hide_After`` timer of a shown melded Panel."""
        surface = host.surface
        if surface.timer is not None:
            surface.timer.cancel()
            surface.timer = None
        panel = surface.planned.bar if surface.planned else None
        if st.painter is not None and isinstance(panel, PanelDef) and panel.hide_after is not None:
            surface.timer = st.painter.after(int(panel.hide_after), lambda: self._expire(st, host))

    def _expire(self, st: FrameState, host: HostState) -> None:
        """``Hide_After`` ran out. With the pointer on a peeking Panel it waits: leaving brings
        the Panel back after ``Exit_Delay`` anyway."""
        host.surface.timer = None
        peek = host.plan.peek
        if host.inside and peek is not None:
            if peek.trigger != "HOVER":
                self._timer(host, st)  # leaving does not send it back: look again later
            return
        self._meld_to(st, host, False)

    # -- peek: the pointer on the tab or the sliver ------------------------------------------------
    #
    # The host's ``clip`` box is the visible part (a tab, a sliver, or the whole body while it is
    # out or on its way), so tre's ``pointer_enter`` and ``pointer_leave`` on it (they fire for the
    # box and everything in it, and not between the box and its own children) say whether the
    # pointer is on the Panel. Each waits its delay on a timer of the painter; a quick in and out
    # cancels the timer that had not run yet, so nothing flickers.

    @staticmethod
    def _cancel_hover(host: HostState) -> None:
        for attr in ("enter_timer", "exit_timer"):
            timer = getattr(host, attr)
            if timer is not None:
                timer.cancel()
                setattr(host, attr, None)

    def _is_out(self, st: FrameState, host: HostState) -> bool:
        """Whether the body is out, or coming out, rather than at rest or going back."""
        name = host.plan.name
        return host.anim == "in" or (
            host.anim is None and name not in st.hidden_melds and name not in st.tab_melds
        )

    def _hover(self, st: FrameState, host: HostState, inside: bool) -> None:
        peek = host.plan.peek
        if peek is None or st.painter is None:
            return
        host.inside = inside
        if host.handle is not None:
            host.handle.hover(inside)  # the icon brightens while the pointer is on the tab
        if peek.trigger != "HOVER":
            return  # a click or a drag opens it: the pointer being there does nothing
        self._cancel_hover(host)
        out = self._is_out(st, host)
        if inside and not out:
            host.enter_timer = self._after(st, peek.enter_delay, lambda: self._enter(st, host))
        elif not inside and out:
            host.exit_timer = self._after(st, peek.exit_delay, lambda: self._exit(st, host))

    @staticmethod
    def _after(st: FrameState, ms: float, call: Callable[[], None]) -> Any:
        """``call`` after ``ms`` on the painter's clock. Never in the event that asks for it, so a
        leave and an enter in one turn of the loop (the pointer crossing from the tab to the
        body) cancel each other whatever the delay."""
        assert st.painter is not None
        return st.painter.after(max(int(ms), 1), call)

    def _enter(self, st: FrameState, host: HostState) -> None:
        host.enter_timer = None
        if host.inside:
            self._meld_to(st, host, True)

    def _exit(self, st: FrameState, host: HostState) -> None:
        host.exit_timer = None
        if host.inside:
            return
        popup = self._m.popups.current
        peek = host.plan.peek
        if popup is not None and popup.parent is host.surface and peek is not None:
            # a Popup that hangs off it is open (the pointer is in the Popup, a window of its own):
            # going back would close it, so wait and look again
            host.exit_timer = self._after(st, peek.exit_delay, lambda: self._exit(st, host))
            return
        self._meld_to(st, host, False)

    # -- peek: a click, or a press and a drag ----------------------------------------------------
    #
    # ``Trigger: CLICK``: a click on the tab (or on the far strip of the body when it is out, where
    # the handle is) toggles it. ``Trigger: DRAG``: a press there captures the pointer; once it has
    # moved ``DRAG_SLOP`` px the join starts drawing the body and every ``pointer_move`` puts it at
    # the pointer's progress along the slide (``Join.seek``, the contour, the content and the
    # handle together); the button going up finishes the move to the nearer end, from where it is,
    # on tre's clock. A press that does not move is a click. The pointer events are input, not
    # per-frame work: nothing runs between them.

    def _in_zone(self, st: FrameState, host: HostState, x: float, y: float) -> bool:
        """Whether a press at the painter's point grabs the peek: anywhere on the tab at rest, the
        far strip of the body (``Size`` px, where the handle is) when it is out, either while it
        moves."""
        axis, peek = host.axis, host.plan.peek
        if axis is None or peek is None:
            return False
        state = self._rest_state(st, host)
        if state == "hidden" and host.anim is None:
            return False
        if state == "tab" and host.anim is None:
            return True
        depth = axis.depth_of(x, y)
        far = depth >= axis.full - axis.size
        return far if host.anim is None else (far or depth <= axis.size)

    @staticmethod
    def _primary(event: Any) -> bool:
        return getattr(event, "button", None) in (None, "primary")

    def _click(self, st: FrameState, host: HostState, event: Any) -> None:
        peek = host.plan.peek
        if peek is None or peek.trigger != "CLICK" or not self._primary(event):
            return
        if event.window_x is None or not self._in_zone(st, host, event.window_x, event.window_y):
            return
        self._meld_to(st, host, not self._is_out(st, host))

    def _press(self, st: FrameState, host: HostState, event: Any) -> None:
        peek, axis = host.plan.peek, host.axis
        if peek is None or peek.trigger != "DRAG" or axis is None or not self._primary(event):
            return
        if host.anim is not None or event.window_x is None:
            return  # a body that moves is not grabbed; let it arrive
        if not self._in_zone(st, host, event.window_x, event.window_y):
            return
        if host.clip is not None:
            host.clip.capture_pointer()
        out = self._rest_state(st, host) == "out"
        host.drag = Drag(axis.depth_of(event.window_x, event.window_y), 1.0 if out else 0.0)
        host.drag.p = host.drag.p0

    def _move(self, st: FrameState, host: HostState, event: Any) -> None:
        drag, axis = host.drag, host.axis
        if drag is None or axis is None or event.window_x is None:
            return
        delta = axis.depth_of(event.window_x, event.window_y) - drag.start
        if not drag.moved and abs(delta) < DRAG_SLOP:
            return
        drag.moved = True
        if not drag.began:
            if not self._drag_begin(st, host):
                host.drag = None
                return
        span = max(axis.full - axis.size, 1.0)
        drag.p = min(max(drag.p0 + delta / span, 0.0), 1.0)
        self._seek(host, drag.p)

    def _release(self, st: FrameState, host: HostState, event: Any) -> None:
        drag, host.drag = host.drag, None
        if drag is None or not self._primary(event):
            return
        if not drag.moved or not drag.began:
            self._meld_to(st, host, drag.p0 == 0.0)  # it did not move: a click toggles it
            return
        self._drag_end(st, host, drag)

    def _seek(self, host: HostState, p: float) -> None:
        """Put the body ``p`` of the way out at once: the contour, the content and the handle."""
        axis = host.axis
        assert host.mover is not None and axis is not None
        if isinstance(host.join, Seekable):
            host.join.seek(p)
        prop, away = host.away
        host.mover.set(**{prop: away * (1.0 - p)})
        if host.handle is not None:
            far = axis.full - axis.size
            host.handle.seek(p, axis.nx * far * p, axis.ny * far * p)

    def _drag_begin(self, st: FrameState, host: HostState) -> bool:
        """The first move of a drag: the join starts drawing the body, from its tab (it opens) or
        from fully out (it is pulled back). ``False`` when it cannot be drawn."""
        drag, surface = host.drag, host.surface
        assert drag is not None and host.join is not None
        if not isinstance(host.join, Seekable):
            logger.error(f"{host.plan.name}: the {self._m.join_mode} join cannot follow a drag")
            return False
        name, show = host.plan.name, drag.p0 == 0.0
        tab = self._rest_is_tab(st, name)
        if surface.timer is not None:
            surface.timer.cancel()
            surface.timer = None
        self._cancel_hover(host)
        surface.generation += 1
        if show:
            st.hidden_melds.discard(name)
            st.tab_melds.discard(name)
            surface.hidden = False
        else:
            surface.hidden = True
            self._m.popups.parent_closed(surface)
        host.anim, host.kind = ("in" if show else "out"), "SLIDE"
        self._draw(st)
        what = "Panel" if host.plan.kind == "meld" else "strip"
        if not self._begin_motion(st, host, "SLIDE", show, tab, what):
            host.anim = None
            self._set_rest(st, name, show)  # back where it was
            self._draw(st)
            return False
        drag.began = True
        return True

    def _drag_end(self, st: FrameState, host: HostState, drag: Drag) -> None:
        """The button went up: finish at the nearer end (``DRAG_OPENS``), from where it is."""
        surface, m, name = host.surface, self._m, host.plan.name
        final = drag.p >= DRAG_OPENS
        changed = final != (drag.p0 == 1.0)  # it ends somewhere else than it started
        surface.generation += 1
        gen = surface.generation
        panel = surface.planned.bar if surface.planned else None
        ms = int(panel.duration) if isinstance(panel, PanelDef) else STRIP_PEEK_MS
        if self._reduced() or ms <= 0:
            self._snap(host)
            self._set_rest(st, name, not final)
            surface.hidden = not final
            self._draw(st)
            if changed:
                m._fire(surface, "On_Open" if final else "On_Close")
            if final:
                self._timer(host, st)
            else:
                m.popups.parent_closed(surface)
            if changed:
                m._fire(surface, "On_Visible" if final else "On_Hidden")
            return
        if changed:
            m._fire(surface, "On_Open" if final else "On_Close")
            m._fire(surface, "On_Anim_Start")
        surface.hidden = not final
        remaining = abs((1.0 if final else 0.0) - drag.p)
        easing = (0.0, 0.0, 0.2, 1.0) if final else (0.4, 0.0, 1.0, 1.0)
        self._run(st, host, final, max(int(ms * remaining), 1), easing, gen, changed)

    def _join_run(
        self, st: FrameState, host: HostState, kind: str, show: bool, tab: bool
    ) -> JoinRun | None:
        """What the join draws for this body's slide or fade (for a peek, between the tab and the
        whole body). ``None`` when the body is not placed or its tab cannot be blended with it."""
        full = st.full
        if full is None or full.morph is None:
            return None
        names = [name for name, _ in st.plan.melds if name not in st.hidden_melds]
        if host.plan.name not in names:
            return None
        index = names.index(host.plan.name)
        if index >= len(full.bodies) or full.bodies[index] is None:
            return None
        paint = st.plan.paint
        # the other bodies that animate are left out: each draws its own join
        others = {
            names.index(h.plan.name): 0.0
            for h in st.hosts.values()
            if h is not host and h.anim and h.plan.name in names
        }
        low = None
        if tab:
            moving = {h.plan.name for h in st.hosts.values() if h.anim}
            small = st.plan.ring_for(
                st.size,
                frozenset(st.hidden_melds),
                frozenset((st.tab_melds - moving) | {host.plan.name}),
            )
            if small.morph is None or index >= len(small.bodies) or small.bodies[index] is None:
                return None
            low = small.morph(others)
            end = full.morph({**others, index: 1.0})
            if any(_commands(a) != _commands(b) for a, b in zip(low, end, strict=True)):
                logger.warning(
                    f"Panel {host.plan.name} on {st.plan.output.name}: its tab and its body do not"
                    " have the same contour (the border does not fit the tab), so it is shown or"
                    " hidden at once"
                )
                return None
        return JoinRun(
            kind, show, st.size, full, index, others, paint.fill, paint.inner, paint.opacity, low
        )

    def _motion(self, st: FrameState, host: HostState) -> tuple[str, int]:
        """The animation of a body and its duration in milliseconds: a Panel's ``Animation``, a
        peeking strip's slide."""
        panel = host.surface.planned.bar if host.surface.planned else None
        if isinstance(panel, PanelDef):
            return panel.animation, int(panel.duration)
        return "SLIDE", STRIP_PEEK_MS

    def _meld_to(self, st: FrameState, host: HostState, show: bool) -> None:
        """Show or hide a melded Panel or a peeking strip (idempotent). A hide while it is showing
        turns round from where it is, and the other way. Hiding goes back to the rest: the tab of
        a peeking Panel, else nothing (or the sliver of a strip)."""
        surface, m = host.surface, self._m
        if st.painter is None:
            return
        name = host.plan.name
        tab = self._rest_is_tab(st, name)
        resting = name in st.hidden_melds or name in st.tab_melds
        if show:
            if host.anim == "in":
                return
            if host.anim is None and not resting:
                self._timer(host, st)  # shown again: the timer starts over
                return
        else:
            if host.anim == "out" or (host.anim is None and resting):
                return
        if surface.timer is not None:
            surface.timer.cancel()
            surface.timer = None
        m._fire(surface, "On_Open" if show else "On_Close")  # before: the request is made
        kind, ms = self._motion(st, host)
        if tab and kind != "NONE":
            kind = "SLIDE"  # a tab and a body are one contour: the depth is what moves
        instant = kind == "NONE" or ms <= 0 or self._reduced()
        what = "Panel" if host.plan.kind == "meld" else "strip"
        detail = ("melded" if host.plan.kind == "meld" else "peek") + (
            "" if instant else f", {kind.lower()}"
        )
        logger.info(
            f"{what} {name} on {st.plan.output.name} {'shown' if show else 'hiding'} ({detail})"
        )
        surface.generation += 1
        gen = surface.generation
        if instant:
            if host.anim:
                self._snap(host)
            self._set_rest(st, name, not show)
            surface.hidden = not show
            self._draw(st)
            if not show:
                m.popups.parent_closed(surface)
            if show:
                self._timer(host, st)
                st.painter.after(
                    1, lambda: m._fire(surface, "On_Visible") if not surface.hidden else None
                )
            else:
                m._fire(surface, "On_Hidden")
            return
        turning = host.anim is not None
        if show:
            st.hidden_melds.discard(name)
            st.tab_melds.discard(name)
            surface.hidden = False
        else:
            surface.hidden = True
            m.popups.parent_closed(surface)
        host.anim, host.kind = ("in" if show else "out"), kind
        self._draw(st)  # the ring nodes are drawn without the body; the join draws it
        if not turning and not self._begin_motion(st, host, kind, show, tab, what):
            self._set_rest(st, name, not show)  # not placed or not drawable: no animation
            self._draw(st)
            return
        easing = (0.0, 0.0, 0.2, 1.0) if show else (0.4, 0.0, 1.0, 1.0)
        m._fire(surface, "On_Anim_Start")
        self._run(st, host, show, ms, easing, gen, True)

    def _begin_motion(
        self, st: FrameState, host: HostState, kind: str, show: bool, tab: bool, what: str
    ) -> bool:
        """Draw the start of a slide or fade: the join at its start state (the tab or nothing for
        a show, fully out for a hide), the content and the handle where they begin. ``False``
        (and the animation cleared) when the join cannot draw this body."""
        assert host.mover is not None and host.join is not None
        run = self._join_run(st, host, kind, show, tab)
        drawn = run is not None and host.join.begin(run)
        if run is not None and not drawn:
            logger.warning(
                f"{what} {host.plan.name} on {st.plan.output.name}: the {self._m.join_mode} join"
                " cannot draw this body, so it is shown or hidden at once"
            )
        if not drawn:
            host.anim = None
            return False
        prop, away = host.away
        host.mover.set(translate_x=0, translate_y=0, opacity=1.0)
        if kind == "SLIDE":
            host.mover.set(**{prop: away if show else 0.0})
            axis = host.axis
            if host.handle is not None and axis is not None:
                far = axis.full - axis.size
                p = 0.0 if show else 1.0
                host.handle.seek(p, axis.nx * far * p, axis.ny * far * p)
        else:
            host.mover.set(opacity=0.0 if show else 1.0)
        return True

    def _run(
        self,
        st: FrameState,
        host: HostState,
        show: bool,
        ms: int,
        easing: tuple[float, float, float, float],
        gen: int,
        events: bool,
    ) -> None:
        """Animate a body that is drawn by its join to its end (out for ``show``, else back to its
        rest) from where it is, and settle it there: the ring takes the body, the join stops,
        ``Hide_After`` starts and, with ``events``, ``On_Anim_End`` and ``On_Visible`` or
        ``On_Hidden`` fire."""
        surface, m, name = host.surface, self._m, host.plan.name
        assert host.mover is not None and host.join is not None

        def done() -> None:
            if surface.generation != gen or host.anim is None:
                return
            if events:
                m._fire(surface, "On_Anim_End")
            host.anim = None
            assert host.mover is not None and host.join is not None
            host.mover.set(translate_x=0, translate_y=0, opacity=1.0)
            if not show:
                self._set_rest(st, name, True)
            self._draw(st)  # the body is part of the ring's one contour again (or gone from it)
            host.join.stop()
            if show:
                self._timer(host, st)
            if events:
                m._fire(surface, "On_Visible" if show else "On_Hidden")

        prop, away = host.away
        host.join.play(show, ms, easing, done)
        if host.kind == "SLIDE":
            host.mover.animate(prop, 0.0 if show else away, ms, easing)
            axis = host.axis
            if host.handle is not None and axis is not None:
                far = axis.full - axis.size
                p = 1.0 if show else 0.0
                host.handle.animate(p, axis.nx * far * p, axis.ny * far * p, ms, easing)
        else:
            host.mover.animate("opacity", 1.0 if show else 0.0, ms, easing)

    def _join_mode(self, hp: HostPlan) -> str:
        """How this host's join is drawn. A Panel that peeks starts its join from a tab, which
        the shader and the boxes (they draw a body from nothing, over the ring) cannot, so it
        takes PARAM; the warning is given once per option."""
        mode = self._m.join_mode
        if mode not in ("SHADER", "CONCAVE") or hp.peek is None:
            return mode
        if hp.kind == "meld":
            why = (
                "cannot draw a Panel that peeks (a body that starts as deep as its tab, not from "
                "nothing)"
            )
        elif hp.peek.trigger == "DRAG":
            why = "cannot follow a drag (its pieces are moved by animations, not set)"
        else:
            return mode
        key = f"{mode} {why}"
        if key not in self._warned:
            self._warned.add(key)
            logger.warning(f"Debug {{ Frame_Join: {mode} }} {why}: PARAM draws it")
        return "PARAM"

    def _drop_hosts(self, st: FrameState) -> None:
        for host in list(st.hosts.values()):
            self._drop_host(st, host)

    def _drop_host(self, st: FrameState, host: HostState) -> None:
        st.hosts.pop(host.plan.key, None)
        host.anim = None
        host.surface.generation += 1  # an animation that was running ends silent
        host.drag = None
        self._cancel_hover(host)
        if host.handle is not None:
            host.handle.destroy()
            host.handle = None
        if host.surface.timer is not None:
            host.surface.timer.cancel()
            host.surface.timer = None
        self._m.popups.parent_closed(host.surface)
        if host.surface.view is not None:
            host.surface.view.dispose()
        host.surface.view = None
        if host.join is not None:
            host.join.destroy()
        for node in (host.clip or host.container,):
            try:
                if node is not None:
                    node.destroy()
            except Exception:  # the window is gone: so is the node
                logger.debug("hosted box already destroyed", exc_info=True)

    def _reconcile_hosts(self, st: FrameState) -> None:
        """Bring the strips and melded Panels to the plan: those no longer planned are dropped, new
        ones are built, kept ones have their tree rebuilt by the keyed diff."""
        if st.painter is None:
            return
        wanted = {h.key: h for h in st.plan.hosts}
        for key in [k for k in st.hosts if k not in wanted]:
            self._drop_host(st, st.hosts[key])
        for key, hp in wanted.items():
            host = st.hosts.get(key)
            if (
                host is not None
                and host.plan.kind == "strip"
                and (host.plan.peek is None) != (hp.peek is None)
            ):
                self._drop_host(st, host)  # it gains or loses its clip box and join
                host = None
            if host is None:
                self._open_host(st, hp)
            else:
                self._update_host(st, host, hp)
        self._draw(st)

    def _open_host(self, st: FrameState, hp: HostPlan) -> None:
        from tess_shell.surfaces.manager import Surface

        assert st.painter is not None
        m, planned = self._m, hp.planned
        container = st.painter.create(
            "box",
            position="absolute",
            left=0,
            top=0,
            width=0,
            height=0,
            visible=False,
            **({"flex_direction": _DIRECTION[hp.side]} if hp.kind == "strip" else {}),
        )
        clip = mover = join = None
        if hp.kind == "meld" or hp.peek is not None:
            clip = st.painter.create(
                "box",
                position="absolute",
                left=0,
                top=0,
                width=0,
                height=0,
                visible=False,
                clip_children=True,
                z_index=_Z_CONTENT,
            )
            mover = st.painter.create("box", position="absolute", left=0, top=0, width=0, height=0)
            join = make_join(self._join_mode(hp), st.painter, _Z_MORPH)
            mover.add_child(container)
            clip.add_child(mover)
            st.painter.root.add_child(clip)
        else:
            container.set(z_index=_Z_CONTENT)
            st.painter.root.add_child(container)
        live = LiveTree(m._store, m._all_uses, look=m._look)
        surface = Surface(
            planned.key,
            hp.name,
            planned.output.name,
            "TOP",
            st.painter,
            None,
            live,
            planned.expanded,
            planned.geometry,
            body=container,
            planned=planned,
            hidden=True,
        )
        host = HostState(hp, surface, container, clip, mover, join)
        st.hosts[hp.key] = host
        if clip is not None:  # a peek may come with a reload: ``_hover`` looks at the plan
            clip.on("pointer_enter", lambda: self._hover(st, host, True))
            clip.on("pointer_leave", lambda: self._hover(st, host, False))
            clip.on("pointer_down", lambda e: self._press(st, host, e))
            clip.on("pointer_move", lambda e: self._move(st, host, e))
            clip.on("pointer_up", lambda e: self._release(st, host, e))
            clip.on("click", lambda e: self._click(st, host, e))
        errors = list(planned.expanded.errors)
        if not errors:
            try:
                surface.view = build(live.resolve(planned.expanded), st.painter, container)
                surface.view.sink = m._dispatch
                m.popups.watch(surface.view, planned)
            except BindFailed as failed:
                errors = failed.errors
        for error in errors:
            logger.error(
                f"{error.origin}: {error.message}" + (f" ({error.hint})" if error.hint else "")
            )
        what = "strip" if hp.kind == "strip" else "melded Panel"
        if surface.view is None:
            logger.error(f"Frame {st.plan.where}: {what} {hp.name} is empty: it did not bind")
        else:
            logger.info(f"Frame {st.plan.where}: {what} {hp.name} built")
        if hp.kind == "meld" and hp.name not in st.hidden_melds | st.tab_melds:
            # shown at start: Hide_After counts from now, On_Visible follows the first frame
            self._timer(host, st)
            st.painter.after(
                1, lambda: m._fire(surface, "On_Visible") if not surface.hidden else None
            )

    def _update_host(self, st: FrameState, host: HostState, hp: HostPlan) -> None:
        assert st.painter is not None
        m, planned = self._m, hp.planned
        surface = host.surface
        live = LiveTree(m._store, m._all_uses, look=m._look)
        try:
            nodes = live.resolve(planned.expanded)
            if surface.view is None:
                surface.view = build(nodes, st.painter, host.container)
                surface.view.sink = m._dispatch
            else:
                surface.view.rebuild(nodes)
            m.popups.watch(surface.view, planned)
        except BindFailed as failed:
            for error in failed.errors:
                logger.error(f"{error.origin}: {error.message}")
            logger.error(f"Frame {st.plan.where}: {hp.name} keeps what it shows")
            host.plan = dataclasses.replace(hp, planned=host.plan.planned)
            return
        surface.live, surface.expanded, surface.planned = live, planned.expanded, planned
        host.plan = hp
