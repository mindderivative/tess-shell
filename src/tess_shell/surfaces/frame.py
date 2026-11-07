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
from tess_shell.schema.model import BarDef, FrameBorder, FrameDef, MonitorDef, PanelDef, ShellDef
from tess_shell.surfaces.bar import Geometry
from tess_shell.surfaces.panel import px_size
from tess_shell.surfaces.ring import MeldSpec, Ring, RingSpec, Sides, padded, ring

if TYPE_CHECKING:
    from tess_re import LayerWindow, Output
    from tess_re import Node as TreNode

    from tess_shell.surfaces.manager import Planned, Surface, SurfaceManager

RGBA = tuple[int, int, int, int]
SIDES = ("left", "top", "right", "bottom")
_ANCHORS = {
    "left": ("left", "top", "bottom"),
    "top": ("top", "left", "right"),
    "right": ("right", "top", "bottom"),
    "bottom": ("bottom", "left", "right"),
}
_SIZES = {"left": (1, 0), "top": (0, 1), "right": (1, 0), "bottom": (0, 1)}
_EMPTY = "M0,0 L0,0 Z"
_EMPTY_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'
# the painter's children, bottom to top: the ring, the svg of a body that animates, the content of
# strips and melded Panels (a strip's blocks are never drawn over by the ring or a morph)
_Z_MORPH = 1
_Z_CONTENT = 2
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
    entry that gives its own, that."""
    out = list(frame.thickness)
    for i, side in enumerate(SIDES):
        edge = frame.edges.get(side)
        if edge is not None and edge.thickness is not None:
            out[i] = edge.thickness
    return out[0], out[1], out[2], out[3]


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


def meld_spec(panel: PanelDef, output: tuple[int, int], look: Look | None) -> MeldSpec:
    """The body a melded Panel asks for: its ``Depth`` (away from the Frame's edge) and ``Length``
    (along it), the side it grows from (``Attach``), ``Alignment`` along it and the
    ``Corner_Radius`` of its style. On a top or bottom side the length runs along x."""
    side = (panel.attach or "TOP").lower()
    along_x = side in ("top", "bottom")
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
        side=(panel.attach or "TOP").lower(),
        width=px_size(length if along_x else depth, output[0]),
        height=px_size(depth if along_x else length, output[1]),
        alignment=panel.alignment,
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


@dataclass(slots=True)
class HostPlan:
    """Content hosted in the painter: a strip or a melded Panel."""

    key: str
    name: str  # a strip: ``<Frame>.<Side>``; a melded Panel: its ``Name``
    kind: str  # "strip" or "meld"
    side: str  # left, top, right, bottom
    planned: Planned
    padding: Sides = (0, 0, 0, 0)


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
    melds: list[tuple[str, MeldSpec]] = field(default_factory=list)  # every melded Panel

    @property
    def where(self) -> str:
        return f"{self.frame.name} on {self.output.name}"

    def uses(self) -> list[Any]:
        return [u for h in self.hosts for u in h.planned.expanded.uses]

    def ring_for(self, size: tuple[float, float], hidden: frozenset[str]) -> Ring:
        """The ring at ``size`` with the melded Panels not in ``hidden``."""
        melds = tuple(spec for name, spec in self.melds if name not in hidden)
        return ring(ring_spec(self.frame, melds, self.paint), size)


@dataclass(slots=True)
class HostState:
    plan: HostPlan
    surface: Surface
    container: TreNode  # the box the tree is bound under
    # a melded Panel only: ``clip`` (clips to the body) holds ``mover`` (the node an animation
    # translates or fades) which holds the ``container``; ``svg`` draws the ring's contour while
    # the body animates (see "a melded Panel" below)
    clip: TreNode | None = None
    mover: TreNode | None = None
    svg: TreNode | None = None
    anim: str | None = None  # "in" (showing) or "out" (hiding) while an animation runs
    kind: str = "NONE"  # the animation that runs: SLIDE or FADE
    away: tuple[str, float] = ("translate_y", 0.0)  # the property and value of "not shown"


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
    hidden_melds: set[str] = field(default_factory=set)  # melded Panels hidden now
    shape: Ring | None = None  # the ring as last drawn, without the melded bodies that animate
    full: Ring | None = None  # the ring with every melded Panel that is shown or on its way
    keyboard: str = "none"


class Frames:
    """The Frames of the shell. They share the manager's value store, look, dispatcher and
    popups, so what a strip or a melded Panel holds behaves like what a Bar holds."""

    def __init__(self, manager: SurfaceManager) -> None:
        self._m = manager
        self._look: Look | None = None
        self.states: dict[str, FrameState] = {}

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
                    melds = [(p.name, meld_spec(p, size, look)) for p in frame.melds]
                    paint, errors = resolve_paint(frame, look)
                    plan = FramePlan(
                        f"{prefix}.{frame.name}",
                        frame,
                        output,
                        f"{monitor.name}@{output.name}",
                        size,
                        ring(ring_spec(frame), size),  # replaced below, once the hosts are known
                        paint,
                        melds=melds,
                    )
                    hidden = frozenset(p.name for p in frame.melds if not p.visible)
                    plan.ring = plan.ring_for(size, hidden)
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
                            f"{frame.name}.{side.capitalize()}",
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
                        plan.hosts.append(HostPlan(key, bar.name, "strip", side, planned, pad))
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
                                key, panel.name, "meld", (panel.attach or "TOP").lower(), planned
                            )
                        )
                    plans.append(plan)
        return plans

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
                st.hidden_melds = {p.name for p in plan.frame.melds if not p.visible}
            else:
                if plan.frame.visible != st.plan.frame.visible:
                    st.hidden = not plan.frame.visible
                before = {p.name: p.visible for p in st.plan.frame.melds}
                for p in plan.frame.melds:
                    if p.name not in before or before[p.name] != p.visible:
                        (st.hidden_melds.discard if p.visible else st.hidden_melds.add)(p.name)
                        for host in st.hosts.values():  # the file decides: no animation goes on
                            if host.plan.name == p.name and host.anim:
                                self._snap(host)
                st.hidden_melds &= {p.name for p in plan.frame.melds}
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
            size = st.plan.size
            st.plan.melds = [
                (p.name, meld_spec(p, size, look)) for p in st.plan.frame.melds
            ]  # a token may have changed a body's radius
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
            elif any(p.name == target for p in st.plan.frame.melds):
                found = True
                host = next(
                    (
                        h
                        for h in st.hosts.values()
                        if h.plan.kind == "meld" and h.plan.name == target
                    ),
                    None,
                )
                if host is None:  # the Frame is hidden: nothing is drawn, so nothing to move
                    hide = target not in st.hidden_melds if action == "Toggle" else action == "Hide"
                    (st.hidden_melds.add if hide else st.hidden_melds.discard)(str(target))
                    continue
                if action == "Toggle":
                    self._m._fire(host.surface, "On_Toggle")  # before: the request is made
                show = host.surface.hidden if action == "Toggle" else action == "Show"
                self._meld_to(st, host, show)
        return found

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
        shape = plan.ring_for(st.size, frozenset(st.hidden_melds | moving))
        st.shape = shape
        # the bodies of the Panels that animate are in ``full`` only, drawn by their own svg
        st.full = plan.ring_for(st.size, frozenset(st.hidden_melds)) if moving else shape
        paint = plan.paint
        sliding = any(h.anim and h.kind == "SLIDE" for h in st.hosts.values())

        def ghost(color: RGBA | None) -> RGBA | None:
            """Under a sliding body's svg the ring nodes are only the shape that takes clicks."""
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
            if host.plan.kind == "meld":
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
    # shape). While it animates, the ring nodes are drawn without it (their colour at alpha 1, so
    # they still take the ring's clicks) and an ``svg`` node draws the ring with the body in it:
    # the document holds the contour at depth 0 and at full depth with the same commands (lines
    # and cubic Beziers, a degenerate cubic where a fillet has radius 0), and an ``<animate
    # attributeName="d">`` between them is sampled by tre's own clock (``svg_time``, eased by
    # ``animate``): the body grows out of the band edge and its joins grow with it, drawn by tre
    # with no Python per frame. The body's content moves with it (``translate`` of the mover node,
    # on the same clock and easing). When it ends the ring nodes take the body back and the svg
    # is hidden; the two renderings agree to the pixel (tests/test_frame_anim.py). The svg takes
    # no input (``hit_testable=False``): the ring nodes under it and the body's own box do.
    # FADE draws the ring without the body, and the ring with it in the svg, faded in or out.

    def _clip_rect(
        self, st: FrameState, host: HostState
    ) -> tuple[float, float, float, float] | None:
        """The clip box of a melded Panel: its body at rest. ``None`` when it is not placed."""
        return self._rect(st, host.plan)

    def _place_meld(self, st: FrameState, host: HostState) -> None:
        """Put a melded Panel's clip box, content and svg where the ring says."""
        surface = host.surface
        rect = self._clip_rect(st, host)
        assert host.clip is not None and host.mover is not None
        if rect is None or st.full is None or st.shape is None:
            if not surface.hidden:
                self._m.popups.parent_closed(surface)
                surface.hidden = True
            host.clip.set(visible=False)
            if host.svg is not None:
                host.svg.set(visible=False)
            return
        x, y, w, h = rect
        host.clip.set(left=x, top=y, width=w, height=h, visible=True)
        host.mover.set(width=w, height=h)
        host.container.set(left=0, top=0, width=w, height=h, visible=True)
        side = host.plan.side
        host.away = {
            "top": ("translate_y", -h),
            "bottom": ("translate_y", h),
            "left": ("translate_x", -w),
            "right": ("translate_x", w),
        }[side]
        surface.hidden = host.anim == "out"

    def _snap(self, host: HostState) -> None:
        """Stop an animation where it is and put the node back to rest."""
        host.anim = None
        host.surface.generation += 1
        if host.mover is not None:
            host.mover.set(translate_x=0, translate_y=0, opacity=1.0)
        if host.svg is not None:
            host.svg.set(visible=False, opacity=1.0)

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
            surface.timer = st.painter.after(
                int(panel.hide_after), lambda: self._meld_to(st, host, False)
            )

    def _morph_document(
        self, st: FrameState, host: HostState, kind: str
    ) -> tuple[str, bool] | None:
        """The svg document of the ring with this body in it, and whether it morphs. ``None``
        when the body is not placed."""
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
        # the other bodies that animate are left out: each draws its own svg
        others = {
            names.index(h.plan.name): 0.0
            for h in st.hosts.values()
            if h is not host and h.anim and h.plan.name in names
        }
        end = full.morph({**others, index: 1.0})
        start = full.morph({**others, index: 0.0})
        w, h = st.size
        parts: list[str] = []
        for (d1, color), d0 in zip(
            ((end[0], paint.fill), (end[1], paint.inner)), (start[0], start[1]), strict=True
        ):
            if not d1 or color is None:
                continue
            fill = f"rgb({color[0]},{color[1]},{color[2]})"
            alpha = f' fill-opacity="{color[3] / 255:.4f}"' if color[3] != 255 else ""
            if kind == "SLIDE":
                body = f'<animate attributeName="d" values="{d0};{d1}" dur="1s" fill="freeze"/>'
                parts.append(f'<path fill="{fill}"{alpha} d="{d0}">{body}</path>')
            else:
                parts.append(f'<path fill="{fill}"{alpha} d="{d1}"/>')
        document = (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}" height="{h:g}" '
            f'viewBox="0 0 {w:g} {h:g}">{"".join(parts)}</svg>'
        )
        return document, kind == "SLIDE"

    def _meld_to(self, st: FrameState, host: HostState, show: bool) -> None:
        """Show or hide a melded Panel (idempotent). A hide while it is showing turns round from
        where it is, and the other way."""
        surface, m = host.surface, self._m
        panel = surface.planned.bar if surface.planned else None
        if not isinstance(panel, PanelDef) or st.painter is None:
            return
        name = host.plan.name
        if show:
            if host.anim == "in":
                return
            if host.anim is None and name not in st.hidden_melds:
                self._timer(host, st)  # shown again: the timer starts over
                return
        else:
            if host.anim == "out" or (host.anim is None and name in st.hidden_melds):
                return
        if surface.timer is not None:
            surface.timer.cancel()
            surface.timer = None
        m._fire(surface, "On_Open" if show else "On_Close")  # before: the request is made
        kind = panel.animation
        instant = kind == "NONE" or self._reduced()
        logger.info(
            f"Panel {name} on {st.plan.output.name} {'shown' if show else 'hiding'} (melded"
            f"{'' if instant else ', ' + kind.lower()})"
        )
        surface.generation += 1
        gen = surface.generation
        if instant:
            if host.anim:
                self._snap(host)
            (st.hidden_melds.discard if show else st.hidden_melds.add)(name)
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
            surface.hidden = False
        else:
            surface.hidden = True
            m.popups.parent_closed(surface)
        host.anim, host.kind = ("in" if show else "out"), kind
        self._draw(st)  # the ring nodes are drawn without the body; the svg draws it
        assert host.mover is not None and host.svg is not None
        paint = st.plan.paint
        if not turning:
            made = self._morph_document(st, host, kind)
            if made is None:  # not placed: nothing to animate
                host.anim = None
                (st.hidden_melds.discard if show else st.hidden_melds.add)(name)
                self._draw(st)
                return
            document, morphs = made
            w, h = st.size
            props: dict[str, Any] = {
                "svg": document,
                "left": 0,
                "top": 0,
                "width": w,
                "height": h,
                "visible": True,
            }
            prop, away = host.away
            host.mover.set(translate_x=0, translate_y=0, opacity=1.0)
            if kind == "SLIDE":
                props.update(svg_time=0.0 if show else 1.0, opacity=paint.opacity)
                host.mover.set(**{prop: away if show else 0.0})
            else:
                faded = 0.0 if show else paint.opacity
                props["opacity"] = faded
                host.mover.set(opacity=0.0 if show else 1.0)
            host.svg.set(**props)
            del morphs
        ms = int(panel.duration)
        easing = (0.0, 0.0, 0.2, 1.0) if show else (0.4, 0.0, 1.0, 1.0)
        m._fire(surface, "On_Anim_Start")

        def done() -> None:
            if surface.generation != gen or host.anim is None:
                return
            m._fire(surface, "On_Anim_End")
            host.anim = None
            assert host.mover is not None and host.svg is not None
            host.mover.set(translate_x=0, translate_y=0, opacity=1.0)
            if not show:
                st.hidden_melds.add(name)
            self._draw(st)  # the body is part of the ring's one contour again (or gone from it)
            host.svg.set(visible=False, opacity=1.0)
            if show:
                self._timer(host, st)
                m._fire(surface, "On_Visible")
            else:
                m._fire(surface, "On_Hidden")

        prop, away = host.away
        if kind == "SLIDE":
            host.svg.animate("svg_time", 1.0 if show else 0.0, ms, easing, done)
            host.mover.animate(prop, 0.0 if show else away, ms, easing)
        else:
            host.svg.animate("opacity", paint.opacity if show else 0.0, ms, easing, done)
            host.mover.animate("opacity", 1.0 if show else 0.0, ms, easing)

    def _drop_hosts(self, st: FrameState) -> None:
        for host in list(st.hosts.values()):
            self._drop_host(st, host)

    def _drop_host(self, st: FrameState, host: HostState) -> None:
        st.hosts.pop(host.plan.key, None)
        host.anim = None
        host.surface.generation += 1  # an animation that was running ends silent
        if host.surface.timer is not None:
            host.surface.timer.cancel()
            host.surface.timer = None
        self._m.popups.parent_closed(host.surface)
        if host.surface.view is not None:
            host.surface.view.dispose()
        host.surface.view = None
        for node in (host.svg, host.clip or host.container):
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
        clip = mover = svg = None
        if hp.kind == "meld":
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
            svg = st.painter.create(
                "svg",
                svg=_EMPTY_SVG,
                position="absolute",
                left=0,
                top=0,
                width=1,
                height=1,
                visible=False,
                hit_testable=False,  # tre cannot hit-test an svg by what it paints: it takes none
                a11y_hidden=True,
                z_index=_Z_MORPH,
            )
            mover.add_child(container)
            clip.add_child(mover)
            st.painter.root.add_child(svg)
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
        host = HostState(hp, surface, container, clip, mover, svg)
        st.hosts[hp.key] = host
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
        if hp.kind == "meld" and hp.name not in st.hidden_melds:
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
