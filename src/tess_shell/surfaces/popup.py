"""The Popup surface and tooltips (Popup; Module Context > Calling a popup).

A Popup exists only while it is open: each open measures the content in a headless window,
creates a tre ``PopupWindow`` of that size beside the caller's rectangle, builds the content in it
with the binder, and each close destroys the window. One Popup is open at a time. A tooltip is a
Popup that opens when the pointer has stayed on its block for ``Enter_Delay`` and closes
``Exit_Delay`` after the pointer left the block and the popup.

Pure helpers (:func:`placement`, :func:`measure`) are separate from the controller
(:class:`Popups`), which the :class:`~tess_shell.surfaces.manager.SurfaceManager` owns and talks to.
"""

from __future__ import annotations

import difflib
import math
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from loguru import logger

from tess_shell.binder import convert
from tess_shell.binder import model as m
from tess_shell.binder.build import View, Wire, build
from tess_shell.binder.model import BindError, BindFailed, Handler
from tess_shell.binder.shadow import DEFAULT_MAX, style_bleed, style_shadows
from tess_shell.model import args
from tess_shell.model.expand import Expanded, ExpandedTooltip, expand
from tess_shell.model.live import LiveTree
from tess_shell.model.look import Look, apply_rules, resolve_style
from tess_shell.model.uses import Use
from tess_shell.schema.model import ModuleDef, PopupDef, ShellDef
from tess_shell.surfaces.bar import Rect, surface_rect

if TYPE_CHECKING:
    from tess_re import Node as TreNode
    from tess_re import Output, PopupWindow, Window

    from tess_shell.surfaces.manager import Planned, Surface, SurfaceManager

Bleed = tuple[int, int, int, int]  # top, right, bottom, left: tre's margin order

# Popup > Placement: (Attach, Alignment) -> (tre anchor, tre gravity)
ANCHORS: dict[tuple[str, str], tuple[str, str]] = {
    ("BOTTOM", "START"): ("bottom_left", "bottom_right"),
    ("BOTTOM", "CENTER"): ("bottom", "bottom"),
    ("BOTTOM", "END"): ("bottom_right", "bottom_left"),
    ("TOP", "START"): ("top_left", "top_right"),
    ("TOP", "CENTER"): ("top", "top"),
    ("TOP", "END"): ("top_right", "top_left"),
    ("RIGHT", "START"): ("top_right", "bottom_right"),
    ("RIGHT", "CENTER"): ("right", "right"),
    ("RIGHT", "END"): ("bottom_right", "top_right"),
    ("LEFT", "START"): ("top_left", "bottom_left"),
    ("LEFT", "CENTER"): ("left", "left"),
    ("LEFT", "END"): ("bottom_left", "top_left"),
}

PROBE = 4096  # the side of the headless window the content is measured in
GRAB_DENIED_MS = 150  # a focused popup dismissed this soon after it opened lost its grab
SWALLOW_MS = 1000  # how long the click that closed a popup is still its own


def placement(attach: str, alignment: str, gap: float) -> tuple[str, str, tuple[int, int]]:
    """tre's ``anchor``, ``gravity`` and ``offset`` for a popup whose body must meet the anchor
    rectangle's ``attach`` edge ``gap`` pixels away, aligned along it by ``alignment``. The
    compositor places the body (the popup's ``geometry``), so a shadow margin needs no allowance.
    """
    anchor, gravity = ANCHORS[(attach, alignment)]
    ox, oy = {"BOTTOM": (0, gap), "TOP": (0, -gap), "RIGHT": (gap, 0), "LEFT": (-gap, 0)}[attach]
    return anchor, gravity, (round(ox), round(oy))


OPPOSITE = {"BOTTOM": "TOP", "TOP": "BOTTOM", "LEFT": "RIGHT", "RIGHT": "LEFT"}


def choose_attach(
    attach: str,
    adjust: Sequence[str],
    anchor: Rect,
    size: tuple[int, int],
    gap: float,
    output: tuple[int, int],
) -> str:
    """The side of the anchor to open on: ``attach``, or its opposite when the popup would leave
    the output on that axis and fits on the other side (Popup > Placement: under a bottom Bar a
    menu opens upward with no setting).

    The compositor would flip it too (``flip_y`` or ``flip_x`` in ``adjust``), but it flips the
    anchor and the gravity and not the offset (measured on sway), so a gap that the offset puts
    right on one side lands wrong on the other. Choosing the side here makes
    the offset right for the side the popup opens on; the compositor still has ``adjust`` as a
    safety net. ``anchor`` is in the output's coordinates, ``size`` is the body.
    """
    axis_flip = "flip_y" if attach in ("BOTTOM", "TOP") else "flip_x"
    if axis_flip not in adjust:
        return attach
    width, height = size
    if attach in ("BOTTOM", "TOP"):
        low, extent, high, length = anchor.y, output[1], anchor.bottom, height
    else:
        low, extent, high, length = anchor.x, output[0], anchor.right, width

    def fits(side: str) -> bool:
        if side in ("BOTTOM", "RIGHT"):  # after the anchor's far edge
            start = high + gap
        else:  # before the anchor's near edge
            start = low - gap - length
        return start >= 0 and start + length <= extent

    if fits(attach) or not fits(OPPOSITE[attach]):
        return attach
    return OPPOSITE[attach]


@dataclass(frozen=True, slots=True)
class Measured:
    """The body a popup needs: its size (clamped to ``Max_Width`` and ``Max_Height``), and
    whether the content is taller than the height it was clamped to (it scrolls)."""

    width: float
    height: float
    scrolls: bool = False


def measure(
    meter: Window,
    nodes: Sequence[Any],
    popup: PopupDef,
    border: Mapping[str, Any] | None = None,
) -> Measured:
    """Lay ``nodes`` out in the headless ``meter`` window and read the body's size.

    Popup > Size: build the content, run a layout pass and read the laid-out size. ``Width`` and
    ``Height`` that are pixels are used as they are; ``AUTO`` reads the content's size, clamped
    to ``Max_Width`` / ``Max_Height``. Raises :class:`BindFailed` when the content does not bind.
    """
    fixed_w = popup.width.px if isinstance(popup.width, m.Length) else None
    fixed_h = popup.height.px if isinstance(popup.height, m.Length) else None
    props: dict[str, Any] = {"align_self": "start", **(border or {})}
    if fixed_w is not None:
        props["width"] = fixed_w
    else:
        props["max_width"] = popup.max_width
    if fixed_h is not None:
        props["height"] = fixed_h
    body = meter.create("box", **props)
    meter.root.add_child(body)
    view: View | None = None
    try:
        view = build(list(nodes), meter, body)
        for _ in range(3):  # a text lays out one pass after the box around it
            meter.advance(16)
        width = float(body.get("layout_width"))
        height = float(body.get("layout_height"))
    finally:
        if view is not None:
            view.dispose()
        body.destroy()
    if fixed_w is not None:
        width = fixed_w
    if fixed_h is not None:
        return Measured(width, fixed_h)
    scrolls = height > popup.max_height + 0.5
    return Measured(width, min(height, popup.max_height), scrolls)


def _border_props(style: Mapping[str, m.Value]) -> dict[str, Any]:
    """The tre properties of a Popup body's border and corners: they take part in its size."""
    out: dict[str, Any] = {}
    for key, (name, kind) in {
        "Corner_Radius": ("corner_radius", "radius"),
        "Border_Width": ("stroke_width", "number"),
        "Border_Color": ("stroke_color", "color"),
    }.items():
        value = style.get(key)
        if value is not None:
            out.update(convert.CONVERTERS[kind](value, (name,), ()))
    return out


@dataclass(frozen=True, slots=True)
class BodyLook:
    """What a Popup's own ``Style`` makes of its body: the transparent margin for the shadow,
    the fill, the shadows, and the corner and border properties."""

    bleed: Bleed
    fill: tuple[int, int, int, int] | None
    shadows: list[tuple[Any, ...]]
    border: dict[str, Any]
    errors: tuple[BindError, ...] = ()

    def props(self) -> dict[str, Any]:
        top, right, bottom, left = self.bleed
        props: dict[str, Any] = {
            "margin_top": top,
            "margin_right": right,
            "margin_bottom": bottom,
            "margin_left": left,
            "shadows": self.shadows,
            **self.border,
        }
        if self.fill is not None:
            props["fill"] = self.fill
        return props


def body_look(popup: PopupDef, look: Look | None) -> BodyLook:
    errors: list[BindError] = []
    style = resolve_style(popup.style or {}, look, errors)
    shadows = style_shadows(style, (look.max_shadows if look else None) or DEFAULT_MAX)
    fill = style.get("Fill") or style.get("Background")
    bleed = style_bleed(style, shadows)
    return BodyLook(
        bleed,
        convert.color(fill, ("fill",))["fill"] if isinstance(fill, m.Color) else None,
        convert.shadows(shadows, ("shadows",))["shadows"],
        _border_props(style),
        tuple(errors),
    )


@dataclass(slots=True)
class PopupPlan:
    """One Popup of a Monitor on one output, expanded."""

    key: str  # the dotted path, with the output when the Monitor opens on several
    popup: PopupDef
    output: Output
    group: str  # "<Monitor>@<output>": a Popup opens only for a caller of its own group
    expanded: Expanded


@dataclass(frozen=True, slots=True)
class Caller:
    """What called a Popup (Module Context > Calling a popup): the module, the use, the surface
    that holds it, the anchor rectangle in that surface's coordinates and the ``data`` passed (a
    plain copy: it does not follow later changes). ``block`` is the id of the block the Popup
    opens beside."""

    module: str
    use: str
    surface: str
    rect: Rect
    data: Mapping[str, Any] | None = None
    block: str = ""

    def record(self, use: Use | None) -> dict[str, Any]:
        """What a slot in the Popup's content reads as ``caller`` (Popup > What the Popup Knows,
        Events and Actions > caller.data): the module, the use (its key, uid, name, monitor and
        params), the anchor rectangle, ``data`` (an empty mapping when none was passed) and
        ``source``, the opening block's id."""
        r = self.rect
        return {
            "module": self.module,
            "use": {
                "key": self.use,
                "uid": self.use.split("@", 1)[1] if "@" in self.use else "",
                "name": use.name if use is not None else "",
                "monitor": use.monitor if use is not None else "",
                "params": dict(use.params) if use is not None else {},
            },
            "rect": {"x": r.x, "y": r.y, "width": r.width, "height": r.height},
            "data": dict(self.data or {}),
            "source": self.block,
        }


@dataclass(slots=True)
class OpenPopup:
    plan: PopupPlan
    window: PopupWindow
    view: View | None
    live: LiveTree
    parent: Surface
    caller: Caller
    where: str
    opened: float
    body: TreNode | None = None
    closing: bool = False
    timer: Any = None  # the pending Exit_Delay timer of a tooltip
    size: tuple[int, int] = (0, 0)
    placed: tuple[int, int] | None = None
    attach: str = ""  # the side of the anchor it was asked to open on
    block: str | None = None  # the block of a tooltip's surface the pointer must be on
    record: Mapping[str, Any] | None = None  # the ``caller`` its content's slots read

    @property
    def popup(self) -> PopupDef:
        return self.plan.popup


class _Hover:
    """A pointer hook on a block that has a tooltip. It is identified by the surface and block so
    that a rebuilt tree is hooked once."""

    __slots__ = ("block", "popups", "surface")

    def __init__(self, popups: Popups, surface: str, block: str) -> None:
        self.popups, self.surface, self.block = popups, surface, block

    def enter(self) -> None:
        self.popups.hover(self.surface, self.block, True)

    def leave(self) -> None:
        self.popups.hover(self.surface, self.block, False)


class Popups:
    """The Popups of a running shell: their plans, the one that is open and the tooltip timers."""

    def __init__(self, manager: SurfaceManager) -> None:
        self._m = manager
        self.plans: dict[tuple[str, str], PopupPlan] = {}
        self.current: OpenPopup | None = None
        self._meter: Window | None = None
        self._swallow: tuple[str, str] | None = None  # the click that closed a popup is its own
        self._swallow_timer: Any = None
        self._enter_timer: Any = None
        self._hovered: tuple[str, str] | None = None  # (surface key, block id) the pointer is on
        self._create: Callable[..., PopupWindow] | None = None

    # -- planning -----------------------------------------------------------------------------

    def plan(
        self,
        shell: ShellDef,
        modules: Mapping[str, ModuleDef],
        look: Look | None,
        outputs: Sequence[Output],
        uid_of: Callable[[str], str],
        assign: Callable[..., list[tuple[Any, list[int]]]],
        panels: set[str],
    ) -> tuple[list[PopupPlan], list[Use]]:
        """Expand each Popup of each Monitor for each output the Monitor opens on. ``modules`` are
        the module definitions with the stylesheet's rules already folded in."""
        from tess_shell.surfaces.manager import is_default  # it imports this module

        rules = look.rules if look else ()
        plans: list[PopupPlan] = []
        uses: list[Use] = []
        for monitor, indices in assign(shell.monitors, outputs):
            for i in indices:
                suffix = f"@{outputs[i].name}" if is_default(monitor) else ""
                for popup in monitor.popups:
                    path = f"{shell.name}.{monitor.name}{suffix}.{popup.name}"
                    expanded = expand(
                        apply_rules(popup.children, rules),
                        path,
                        modules,
                        uid_of,
                        outputs[i].name,
                        rules,
                        in_popup=True,
                    )
                    _check_close_targets(expanded, panels)
                    uses.extend(expanded.uses)
                    plans.append(
                        PopupPlan(
                            path, popup, outputs[i], f"{monitor.name}@{outputs[i].name}", expanded
                        )
                    )
        return plans, uses

    def set_plans(self, plans: Sequence[PopupPlan]) -> None:
        """The plans of the running shell. An open Popup is closed: it was built from the old."""
        self.close_current("reloaded")
        self.plans = {(p.group, p.popup.name): p for p in plans}

    def merge_plans(self, plans: Sequence[PopupPlan]) -> None:
        """The plans after a monitor came or went. An open Popup stays open: it keeps its own
        plan, and closes with its parent surface when that closes."""
        self.plans = {(p.group, p.popup.name): p for p in plans}

    def uses(self) -> dict[str, Use]:
        return {u.key: u for p in self.plans.values() for u in p.expanded.uses}

    # -- the module API -----------------------------------------------------------------------

    def call(self, module: str, use: str | None, name: str, data: Mapping[str, Any] | None) -> None:
        """``ctx.popup(name, data)``: open the Popup beside the calling use, or close it when it
        is the open one (a toggle). Errors are logged, never raised into the module."""
        found = self._holder(use) if use else None
        if found is None or use is None:
            logger.error(
                f"{module}: ctx.popup({name!r}): the use {use} is on no open surface, so the "
                "Popup has no parent"
            )
            return
        surface, node_id = found
        assert surface.planned is not None
        plan = self.plans.get((surface.planned.group, name))
        if plan is None:
            names = sorted(n for g, n in self.plans if g == surface.planned.group)
            close = difflib.get_close_matches(name, names, n=3, cutoff=0.5)
            hint = (
                f"did you mean {', '.join(close)}?"
                if close
                else ("the Popups here: " + (", ".join(names) or "none"))
            )
            logger.error(
                f"{module}: ctx.popup({name!r}): no Popup named {name} on Monitor "
                f"{surface.planned.group} ({hint})"
            )
            return
        try:
            copy = args.copy_plain(data or {}, "data")
        except ValueError as exc:
            logger.error(f"{module}: ctx.popup({name!r}): {exc}; the Popup was not opened")
            return
        current = self.current
        if current is not None and current.plan is plan and current.caller.use == use:
            self.close(current, "toggled")
            return
        if self._swallow == (name, use):  # the click that closed this popup was this one
            self._swallow = None
            logger.debug(f"Popup {name}: the click that closed it is not a call to open it again")
            return
        self.open(plan, surface, node_id, use, module, None, copy)

    def close_named(self, name: str | None = None) -> None:
        """``ctx.close_popup(name)``: close the open Popup (the named one, if a name is given)."""
        cur = self.current
        if cur is not None and (name is None or cur.popup.name == name):
            self.close(cur, "closed by a call")

    def _holder(self, use: str) -> tuple[Surface, str] | None:
        """The open surface that holds ``use`` and the id of the use's first root block."""
        for s in self._m.every_surface():
            if s.window is None or s.view is None or s.hidden:
                continue
            node_id = s.expanded.roots.get(use)
            if node_id is not None:
                return s, node_id
        return None

    # -- opening ------------------------------------------------------------------------------

    def rect_of(self, surface: Surface, node_id: str) -> Rect | None:
        """Where tre laid out the block ``node_id`` of ``surface``, in the surface's window."""
        node = surface.view.nodes.get(node_id) if surface.view else None
        if node is None:
            return None
        x, y, w, h = (
            float(node.get(k)) for k in ("layout_x", "layout_y", "layout_width", "layout_height")
        )
        if w <= 0 and h <= 0:
            return None
        return Rect(x, y, w, h)

    def open(
        self,
        plan: PopupPlan,
        surface: Surface,
        node_id: str,
        use: str,
        module: str,
        expanded: Expanded | None = None,
        data: Mapping[str, Any] | None = None,
    ) -> OpenPopup | None:
        """Open ``plan`` beside the block ``node_id`` of ``surface``. ``expanded`` is the content
        when it is not the plan's own (an inline tooltip)."""
        from tess_re import PopupWindow

        popup, where = plan.popup, f"{plan.popup.name or 'tooltip'} on {plan.output.name}"
        self.close_current("replaced")
        assert surface.window is not None and surface.planned is not None
        rect = self.rect_of(surface, node_id)
        if rect is None:
            logger.warning(f"Popup {where}: the caller has no laid-out rectangle yet; not opened")
            return None
        look = self._m.look
        shape = body_look(popup, look)
        for error in shape.errors:
            logger.warning(f"{error.origin}: {error.message}")
        caller = Caller(module, use, surface.key, rect, data, node_id)
        record = caller.record(self._m._all_uses.get(use))
        live = LiveTree(self._m._store, self._m._all_uses, look=look, caller=record)
        nodes = live.resolve(expanded or plan.expanded)
        try:
            size = measure(self._meter_window(), nodes, popup, shape.border)
        except BindFailed as failed:
            _log_errors(failed.errors)
            logger.error(f"Popup {where} is not opened: its contents did not bind")
            return None
        for axis, value in (("width", size.width), ("height", size.height)):
            if value <= 0:
                logger.warning(
                    f"Popup {where}: its content is {value:g} px {axis}: a Text in a Popup with "
                    f"AUTO {axis} needs Height: AUTO (and Width: AUTO) to take its own size"
                )
        top, right, bottom, left = shape.bleed
        width = max(math.ceil(size.width), 1)
        height = max(math.ceil(size.height), 1)
        surface_size = (width + left + right, height + top + bottom)
        parent = surface_rect(
            surface.geometry, (surface.planned.output.width, surface.planned.output.height)
        )
        # tre 0.6.3 takes the popup proper as ``geometry``: the compositor places, flips and slides
        # the body and ignores the transparent shadow margin around it (TRE-REQ-007), so the
        # placement is that of a popup with no margin
        attach = choose_attach(
            popup.attach,
            popup.adjust,
            Rect(parent.x + rect.x, parent.y + rect.y, rect.width, rect.height),
            (width, height),
            popup.gap,
            (surface.planned.output.width, surface.planned.output.height),
        )
        anchor, gravity, offset = placement(attach, popup.alignment, popup.gap)
        factory = self._create or PopupWindow
        anchor_rect = (
            round(rect.x),
            round(rect.y),
            max(round(rect.width), 1),
            max(round(rect.height), 1),
        )
        kwargs: dict[str, Any] = {
            "size": surface_size,
            "anchor_rect": anchor_rect,
            "anchor": anchor,
            "gravity": gravity,
            "constraint_adjustment": popup.adjust,
            "offset": offset,
            "grab": popup.focus,
        }
        if any(shape.bleed):
            kwargs["geometry"] = (left, top, width, height)
            # a click in the shadow margin reaches the window below (tre 0.6.5, TRE-REQ-014)
            kwargs["input_region"] = "geometry"
        try:
            window = factory(surface.window, **kwargs)
        except (ValueError, RuntimeError) as exc:  # a bad size, or no compositor
            logger.error(f"Popup {where} is not opened: {exc}")
            return None
        body = window.create("box", flex_grow=1, align_self="stretch", **shape.props())
        window.root.add_child(body)
        op = OpenPopup(
            plan,
            window,
            None,
            live,
            surface,
            caller,
            where,
            time.monotonic(),
            body,
            size=surface_size,
            attach=attach,
            record=record,
        )
        try:
            op.view = self._build_content(window, body, nodes, size.scrolls)
        except BindFailed as failed:
            _log_errors(failed.errors)
            logger.error(f"Popup {where} is not opened: its contents did not bind")
            window.close()
            return None
        op.view.sink = lambda h, k, raw, op=op: self._dispatch(op, h, k, raw)
        self._listen(op)
        self.current = op
        self._m._app.add_window(window)
        logger.info(
            f"Popup {where} opened beside {module} {use}: body {width}x{height} "
            f"on {attach}"
            + (f" (no room on {popup.attach})" if attach != popup.attach else "")
            + f", anchor {anchor} gravity {gravity} offset {offset}, "
            f"{'focus' if popup.focus else 'no focus'}"
        )
        return op

    def _build_content(
        self, window: PopupWindow, body: TreNode, nodes: Sequence[Any], scrolls: bool
    ) -> View:
        """Bind the content under the body; under a vertical scroll view when it is taller than
        the popup may be (Popup > Size: content beyond ``Max_Height`` scrolls)."""
        if not scrolls:
            return build(list(nodes), window, body)
        view = window.create(
            "scroll_view", orientation="vertical", flex_grow=1, align_self="stretch"
        )
        content = window.create("box", flex_direction="vertical", align_self="stretch")
        view.add_child(content)
        body.add_child(view)
        return build(list(nodes), window, content)

    def _meter_window(self) -> Window:
        if self._meter is None:
            import tess_re

            self._meter = tess_re.Window(PROBE, PROBE, decorations=False)
            self._meter.root.set(padding_left=0, padding_right=0, padding_top=0, padding_bottom=0)
        return self._meter

    def _listen(self, op: OpenPopup) -> None:
        w = op.window
        popup = op.popup
        w.on("configure", lambda e, op=op: self._configured(op, e))
        w.on("closed", lambda e, op=op: self._closed(op, str(getattr(e, "reason", ""))))
        if popup.focus:
            # Escape ends a focused popup; tre's grab should do it, and on KWin it did not
            w.root.on("key_down", lambda e, op=op: self._key(op, e))
        if popup.close_on_exit and op.body is not None:
            # the pointer crossing from the caller into the popup keeps a tooltip open
            op.body.on("pointer_enter", lambda _e, op=op: self._popup_enter(op))
            op.body.on("pointer_leave", lambda _e, op=op: self._popup_leave(op))

    def _key(self, op: OpenPopup, event: Any) -> None:
        key = getattr(event, "key", None)
        logger.debug(f"Popup {op.where}: key {key}")
        if key == "escape":
            self.close(op, "escape")

    def _configured(self, op: OpenPopup, event: Any) -> None:
        x, y = int(getattr(event, "x", 0)), int(getattr(event, "y", 0))
        op.placed = (x, y)
        c = op.caller.rect
        w, h = op.size
        mid_x, mid_y = x + w / 2, y + h / 2
        flipped = (
            (op.attach == "BOTTOM" and mid_y < c.y)
            or (op.attach == "TOP" and mid_y > c.bottom)
            or (op.attach == "RIGHT" and mid_x < c.x)
            or (op.attach == "LEFT" and mid_x > c.right)
        )
        logger.info(
            f"Popup {op.where} placed at {x},{y} size {int(event.width)}x{int(event.height)}"
            + (" (the compositor flipped it)" if flipped else "")
        )

    # -- closing ------------------------------------------------------------------------------

    def close(self, op: OpenPopup, why: str) -> None:
        """Close ``op`` now: it is no longer the open popup, its window closes on the loop's next
        turn (``closed`` then arrives with the reason ``app``)."""
        if op.closing:
            return
        op.closing = True
        if op.timer is not None:
            op.timer.cancel()
            op.timer = None
        if self.current is op:
            self.current = None
        logger.info(f"Popup {op.where} closing ({why})")
        try:
            op.window.close()
        except Exception:  # the window may be gone already
            logger.debug(f"Popup {op.where}: close raised", exc_info=True)
        self._free(op)

    def close_current(self, why: str) -> None:
        if self.current is not None:
            self.close(self.current, why)

    def _free(self, op: OpenPopup) -> None:
        if op.view is not None:
            op.view.dispose()
            op.view = None

    def _closed(self, op: OpenPopup, reason: str) -> None:
        """tre's ``closed``: the compositor dismissed it (``dismissed``), the parent was not open
        (``failed``), or this shell closed it (``app``)."""
        if op.timer is not None:
            op.timer.cancel()
            op.timer = None
        was_open = self.current is op
        if was_open:
            self.current = None
        self._free(op)
        op.closing = True
        logger.info(f"Popup {op.where} closed ({reason})")
        if reason == "failed":
            logger.warning(
                f"Popup {op.where}: tre closed it with reason failed: its parent "
                f"{op.parent.name} was not open; called by {op.caller.module} {op.caller.use}"
            )
        elif reason == "dismissed" and op.popup.focus:
            ms = (time.monotonic() - op.opened) * 1000
            if ms < GRAB_DENIED_MS:
                logger.warning(
                    f"Popup {op.where} was dismissed {ms:.0f} ms after it opened: the compositor "
                    "may have denied its grab (a grab needs a fresh user action: open a focused "
                    "Popup from a click or key, or write Focus: false)"
                )

    def parent_closed(self, surface: Surface) -> None:
        """A surface closed or hid: a Popup hanging off it closes with it."""
        cur = self.current
        if cur is not None and cur.parent is surface:
            self.close(cur, "its parent closed")
        if self._hovered is not None and self._hovered[0] == surface.key:
            self._hovered = None  # a tooltip waiting for its delay is not opened
            self._cancel_enter()

    # -- dismissal by a click on the shell's own surfaces --------------------------------------

    def surface_pointer_down(self) -> None:
        """A button went down on one of the shell's surfaces. tre delivers that click to the
        surface, not to the popup's grab, so a focused Popup closes here. The ``click`` that
        follows may be the call that opened the popup: it must not open it again."""
        self._swallow = None
        cur = self.current
        if cur is None or not cur.popup.focus:
            return
        self._swallow = (cur.popup.name, cur.caller.use)
        self.close(cur, "a click on a surface")
        if self._swallow_timer is not None:
            self._swallow_timer.cancel()
        self._swallow_timer = (
            cur.parent.window.after(SWALLOW_MS, self._forget_swallow)
            if (cur.parent.window is not None)
            else None
        )

    def _forget_swallow(self) -> None:
        self._swallow = None
        self._swallow_timer = None

    # -- tooltips -----------------------------------------------------------------------------

    def watch(self, view: View, planned: Planned) -> None:
        """Hook the pointer on every block of a surface's tree that has a tooltip (once each)."""
        for block in planned.expanded.tooltips:
            wire = view.wires.get(block)
            if wire is None:
                continue
            if not any(isinstance(getattr(h, "__self__", None), _Hover) for h in _hooks(wire)):
                hover = _Hover(self, planned.key, block)
                wire.add_hook("enter", hover.enter)
                wire.add_hook("leave", hover.leave)

    def _tooltip_plan(
        self, surface: Surface, block: str, tip: ExpandedTooltip
    ) -> tuple[PopupPlan, Expanded | None] | None:
        """The plan a tooltip opens and the content to build when it is not the plan's own."""
        assert surface.planned is not None
        group = surface.planned.group
        if tip.ref.name is not None:
            plan = self.plans.get((group, tip.ref.name))
            if plan is None:
                logger.error(
                    f"{tip.ref.origin}: Tooltip names {tip.ref.name}, which is no Popup of "
                    f"Monitor {group}"
                )
            return (plan, None) if plan is not None else None
        popup: PopupDef = tip.ref.popup
        plan = PopupPlan(
            f"{surface.key}/{block}/tooltip",
            popup,
            surface.planned.output,
            group,
            Expanded(nodes=tip.nodes, owner=surface.expanded.owner),
        )
        return plan, plan.expanded

    def hover(self, surface_key: str, block: str, entered: bool) -> None:
        """The pointer entered or left ``block`` of a surface that has a tooltip on it."""
        surface = next((s for s in self._m.every_surface() if s.key == surface_key), None)
        tip = surface.expanded.tooltips.get(block) if surface else None
        if surface is None or tip is None or surface.window is None:
            return
        key = (surface_key, block)
        if entered:
            self._hovered = key
            self._cancel_enter()
            cur = self.current
            if cur is not None:
                if cur.caller.surface == surface_key and cur.block == block:
                    if cur.timer is not None:  # back on the block: it stays open
                        cur.timer.cancel()
                        cur.timer = None
                    return
                if cur.popup.focus or cur.block is None:
                    return  # a focused Popup is open: a tooltip never opens over it
                self.close(cur, "the pointer moved to another block")
            wire = surface.view.wires.get(block) if surface.view is not None else None
            if wire is not None and wire.tooltip_gate is not None and not wire.tooltip_gate():
                return  # the block says its tooltip has nothing to add now (a Marquee that scrolls)
            found = self._tooltip_plan(surface, block, tip)
            if found is None:
                return
            plan, content = found
            delay = plan.popup.enter_delay
            self._enter_timer = surface.window.after(
                delay, lambda: self._open_tooltip(surface_key, block, plan, content)
            )
            return
        if self._hovered == key:
            self._hovered = None
        self._cancel_enter()
        cur = self.current
        if cur is not None and cur.block == block and cur.caller.surface == surface_key:
            self._arm_exit(cur)

    def _cancel_enter(self) -> None:
        if self._enter_timer is not None:
            self._enter_timer.cancel()
            self._enter_timer = None

    def _open_tooltip(
        self, surface_key: str, block: str, plan: PopupPlan, content: Expanded | None
    ) -> None:
        self._enter_timer = None
        if self._hovered != (surface_key, block):
            return
        if self.current is not None:  # a focused Popup, or another tooltip, is open
            return
        surface = next((s for s in self._m.every_surface() if s.key == surface_key), None)
        if surface is None or surface.window is None or surface.hidden:
            return
        use = surface.expanded.owner.get(block, "")
        module = use.split("@", 1)[0] if use else ""
        op = self.open(plan, surface, block, use, module, content)
        if op is not None:
            op.block = block

    def _arm_exit(self, op: OpenPopup) -> None:
        if not op.popup.close_on_exit or op.closing:
            return
        if op.timer is not None:
            op.timer.cancel()
        op.timer = (
            op.parent.window.after(op.popup.exit_delay, lambda: self._exit_due(op))
            if (op.parent.window is not None)
            else None
        )

    def _exit_due(self, op: OpenPopup) -> None:
        op.timer = None
        self.close(op, "the pointer left")

    def _popup_enter(self, op: OpenPopup) -> None:
        if op.timer is not None:
            op.timer.cancel()
            op.timer = None

    def _popup_leave(self, op: OpenPopup) -> None:
        if op.block != self._hovered_block():
            self._arm_exit(op)

    def _hovered_block(self) -> str | None:
        return self._hovered[1] if self._hovered else None

    # -- the content's events and values ------------------------------------------------------

    def _dispatch(self, op: OpenPopup, handler: Handler, key: str, raw: Any) -> None:
        """An event raised by a block of an open Popup: ``Close`` closes it, ``Show``, ``Hide``
        and ``Toggle`` act on a Panel, any other name is a module's ``@action``."""
        if handler.builtin:
            if handler.action == "Close":
                self.close(op, "closed by its content")
            else:
                self._m.run_builtin(handler)
            return
        self._m._dispatch(handler, key, raw, op.record)

    def on_change(self, changes: Sequence[Any]) -> None:
        """The store changed: the open Popup shows the new values (its size stays)."""
        op = self.current
        if op is None or op.view is None or op.closing:
            return
        result = op.live.apply_changes(list(changes))
        if result.rebuild:
            try:
                op.view.rebuild(op.live.resolve(op.plan.expanded))
            except BindFailed as failed:
                for error in failed.errors:
                    logger.warning(
                        f"{error.origin}: {error.message}; the Popup keeps what it shows"
                    )
            return
        for error in op.view.update(result.updates):
            logger.warning(f"{error.origin}: {error.message}")


def _hooks(wire: Wire) -> list[Callable[[], None]]:
    return [*wire.hooks.get("enter", ()), *wire.hooks.get("leave", ())]


def _log_errors(errors: Sequence[BindError]) -> None:
    for error in errors:
        logger.error(
            f"{error.origin}: {error.message}" + (f" ({error.hint})" if error.hint else "")
        )


def _check_close_targets(expanded: Expanded, panels: set[str]) -> None:
    """A shell action in a Popup names a Panel by ``Name``; ``Close`` names nothing."""
    from tess_shell.surfaces.manager import _handlers

    for h in _handlers(expanded.nodes):
        target = h.args.get("Target")
        if h.builtin and h.action != "Close" and target not in panels:
            expanded.errors.append(
                BindError(
                    f"{h.action}: no Panel named {target}", h.origin, "write the Name of a Panel"
                )
            )
