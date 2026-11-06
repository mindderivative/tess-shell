"""The Frame: a ring around an output that reserves its sides (Frame > Parts on Tre).

Per Frame and output there are up to five windows, all on the ``top`` layer:

* one *painter*: all four anchors, size (0, 0), ``exclusive_zone`` -1 and ``input_region="auto"``.
  It draws the ring as three ``path`` nodes (outer border, fill, inner border; see
  :mod:`tess_shell.surfaces.ring`) with ``hit_shape="painted"``, so a click lands only on what is
  painted and the opening passes it on;
* up to four *reservers*, one per side with a thickness: anchored to that edge and both edges
  across it, 1 px thick, transparent, taking no input, with the side's total (thickness, borders
  and margin) as ``exclusive_zone``. They push maximised windows inside the ring.

:class:`Frames` keeps them keyed like the other surfaces; :meth:`Frames.sync` brings the open
windows to a plan (start, reload, hot-plug) and changes a zone, a radius or a colour live, without
making the painter again.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from loguru import logger

from tess_shell.binder import convert
from tess_shell.binder.model import BindError, Color, Number, Value
from tess_shell.model.look import Look, resolve_style
from tess_shell.schema.model import FrameBorder, FrameDef, MonitorDef, ShellDef
from tess_shell.surfaces.ring import Ring, RingSpec, ring

if TYPE_CHECKING:
    from tess_re import App, LayerWindow, Output
    from tess_re import Node as TreNode

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


def ring_spec(frame: FrameDef) -> RingSpec:
    return RingSpec(
        thickness=frame.thickness,
        margin=frame.margin,
        outer_radius=frame.outer_radius,
        inner_radius=frame.inner_radius,
        outer_border=frame.outer_border.width if frame.outer_border else 0,
        inner_border=frame.inner_border.width if frame.inner_border else 0,
    )


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

    @property
    def where(self) -> str:
        return f"{self.frame.name} on {self.output.name}"


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


class Frames:
    """The Frames of the shell. ``wake`` is called after the windows were changed from outside
    their own callbacks (``SurfaceManager.wake``)."""

    def __init__(self, app: App, wake: Callable[[], None]) -> None:
        self._app = app
        self._wake = wake
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
    ) -> list[FramePlan]:
        """The Frame of each Monitor on each output it applies to. ``by_output`` says whether a
        Monitor's keys carry the output (the same rule as its Bars' keys). A radius the ring
        cannot hold is reduced and a warning names it; a token that does not resolve is logged."""
        plans: list[FramePlan] = []
        for monitor, indices in assigned:
            for frame in monitor.frames:
                for i in indices:
                    output = outputs[i]
                    suffix = f"@{output.name}" if by_output(monitor) else ""
                    size = (output.width, output.height)
                    shape = ring(ring_spec(frame), size)
                    paint, errors = resolve_paint(frame, look)
                    where = f"{frame.name} on {output.name}"
                    for warning in shape.warnings:
                        logger.warning(f"{frame.origin}: Frame {where}: {warning}")
                    for error in errors:
                        logger.error(
                            f"{error.origin}: {error.message}"
                            + (f" ({error.hint})" if error.hint else "")
                        )
                    plans.append(
                        FramePlan(
                            f"{shell.name}.{monitor.name}{suffix}.{frame.name}",
                            frame,
                            output,
                            f"{monitor.name}@{output.name}",
                            size,
                            shape,
                            paint,
                        )
                    )
        return plans

    # -- opening, reloading, hot-plug -----------------------------------------------------------

    def sync(self, plans: Sequence[FramePlan], look: Look | None = None) -> None:
        """Make the open Frames match ``plans``: close the windows of a Frame that is gone (or
        that moved to another output), open a new one, and bring a kept one to the new ring and
        zones by ``set``, adding or closing a reserver when a side gains or loses its thickness.
        A Frame hidden at run time stays hidden unless its ``Visible`` changed in the file."""
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
            else:
                if plan.frame.visible != st.plan.frame.visible:
                    st.hidden = not plan.frame.visible
                if plan.size != st.plan.size:
                    st.size = plan.size  # the output changed: draw for it until tre configures
                st.plan = plan
            self._reconcile(st)
        self._wake()

    def set_look(self, look: Look) -> None:
        """The theme or the accent changed: every token is read again and the ring is redrawn
        in place. The caller wakes tre's loop (``SurfaceManager.set_look`` does, once)."""
        self._look = look
        for st in self.states.values():
            paint, errors = resolve_paint(st.plan.frame, look)
            for error in errors:
                logger.error(f"{error.origin}: {error.message}")
            st.plan.paint = paint
            self._draw(st)

    def names(self) -> set[str]:
        """The ``Name`` of every Frame (the target of ``Show``, ``Hide`` and ``Toggle``)."""
        return {st.plan.frame.name for st in self.states.values()}

    def run(self, action: str, target: object) -> bool:
        """``Show``, ``Hide`` or ``Toggle`` on the Frame named ``target``; ``False`` when no Frame
        has that name. Hiding closes every window of the Frame, so its zones are released and
        windows use the whole output; showing makes them again."""
        hits = [st for st in self.states.values() if st.plan.frame.name == target]
        for st in hits:
            hide = not st.hidden if action == "Toggle" else action == "Hide"
            if hide != st.hidden:
                st.hidden = hide
                logger.info(f"Frame {st.plan.where} {'hidden' if hide else 'shown'}")
                self._reconcile(st)
        if hits:
            self._wake()
        return bool(hits)

    # -- windows --------------------------------------------------------------------------------

    def _close(self, st: FrameState) -> None:
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
                st.painter = None  # a later sync makes it again

        window.on("configure", configure)
        window.on("closed", closed)
        self._app.add_window(window)
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
        self._app.add_window(window)
        logger.info(f"Frame {where}: {side} reserver, zone {zone}")

    def _draw(self, st: FrameState) -> None:
        """Set the ring's three nodes to the plan's ring and colours; nothing when equal."""
        if st.painter is None:
            return
        plan = st.plan
        shape = plan.ring
        if st.size != plan.size:
            shape = ring(ring_spec(plan.frame), st.size)  # the surface's own size
        paint = plan.paint
        bands = (
            (shape.outer_border, paint.outer),
            (shape.fill, paint.fill),
            (shape.inner_border, paint.inner),
        )
        key = (st.size, paint.opacity, bands)
        if key == st.drawn:
            return
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
