"""Open the shell's surfaces: match each ``Monitor`` to outputs, create one ``LayerWindow`` per
Bar, bind its children and add it to the app (Shell Start and Stop, start steps 10 and 11).

A bind error leaves that Bar empty and logs every error; other Bars still open. A Bar whose size
resolves to 0 is not created (D46). Closing is the engine's job: stopping the loop closes every
window.
"""

from __future__ import annotations

import dataclasses
import difflib
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Protocol

from loguru import logger

from tess_shell.binder import convert
from tess_shell.binder.build import View, build
from tess_shell.binder.model import BindError, BindFailed, Color, Handler, Value
from tess_shell.binder.shadow import DEFAULT_MAX, style_bleed, style_shadows
from tess_shell.model import args
from tess_shell.model.expand import Expanded, expand
from tess_shell.model.field import describe_text_field, first_text_field, holds_text_field
from tess_shell.model.live import LiveTree
from tess_shell.model.look import Look, apply_rules, resolve_style
from tess_shell.model.store import Change, ValueStore
from tess_shell.model.uses import Use, UseScope
from tess_shell.schema.default_popups import SHIPPED_POPUP_MODULES
from tess_shell.schema.findings import nearest
from tess_shell.schema.model import BarDef, ModuleDef, MonitorDef, PanelDef, ShellDef, use_names
from tess_shell.surfaces.bar import (
    BarSpec,
    Geometry,
    Rect,
    ZeroSize,
    bar_geometry,
    body_rect,
    input_region,
    surface_rect,
)
from tess_shell.surfaces.focus import next_surface, surface_order
from tess_shell.surfaces.frame import FramePlan, Frames
from tess_shell.surfaces.panel import PanelSpec, panel_geometry, px_size

if TYPE_CHECKING:
    from tess_re import App, LayerWindow, Output
    from tess_re import Node as TreNode


class OutputLike(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def description(self) -> str: ...


def _claims(monitor: MonitorDef, outputs: Sequence[OutputLike]) -> int | None:
    """The output a monitor block names: ``Connector``, then ``Description``, then ``Index``."""
    if monitor.connector is not None:
        for i, o in enumerate(outputs):
            if o.name == monitor.connector:
                return i
    if monitor.description is not None:
        for i, o in enumerate(outputs):
            if o.description == monitor.description:
                return i
    if isinstance(monitor.index, int) and monitor.index < len(outputs):
        return monitor.index
    return None


def _has_selector(monitor: MonitorDef) -> bool:
    return (
        monitor.connector is not None
        or monitor.description is not None
        or isinstance(monitor.index, int)
    )


def is_default(monitor: MonitorDef) -> bool:
    """``Index: default`` with no other selector: the block opens on every output no other block
    named, so its surfaces' paths always carry the output, whatever the count is now (a second
    screen plugged in must not rename, and so recreate, the first one's)."""
    return monitor.index == "default" and not _has_selector(monitor)


def _resolve(
    monitors: Sequence[MonitorDef], outputs: Sequence[OutputLike]
) -> tuple[list[tuple[MonitorDef, list[int]]], list[tuple[MonitorDef, MonitorDef, int]]]:
    result: list[tuple[MonitorDef, list[int]]] = []
    conflicts: list[tuple[MonitorDef, MonitorDef, int]] = []
    taken: dict[int, MonitorDef] = {}
    defaults: list[MonitorDef] = []
    for monitor in monitors:
        if is_default(monitor):
            defaults.append(monitor)
            continue
        if not _has_selector(monitor) and monitor.index is None:
            continue
        found = _claims(monitor, outputs)
        if found is None:
            result.append((monitor, []))
            continue
        if found in taken:
            conflicts.append((monitor, taken[found], found))
            result.append((monitor, []))
            continue
        taken[found] = monitor
        result.append((monitor, [found]))
    free = [i for i in range(len(outputs)) if i not in taken]
    result.extend((monitor, list(free)) for monitor in defaults)
    return result, conflicts


def assign(
    monitors: Sequence[MonitorDef], outputs: Sequence[OutputLike]
) -> list[tuple[MonitorDef, list[int]]]:
    """Which outputs each monitor block applies to (indices into ``outputs``).

    A block with a selector takes the output it names; a block that names an output another block
    already took gets none (the first wins). ``Index: default`` takes every output no other block
    named. A block with no selector is ignored; a block that matches nothing gets an empty list.
    """
    return _resolve(monitors, outputs)[0]


def conflicts(
    monitors: Sequence[MonitorDef], outputs: Sequence[OutputLike]
) -> list[tuple[MonitorDef, MonitorDef, int]]:
    """Blocks that name an output an earlier block took: ``(loser, winner, output index)``."""
    return _resolve(monitors, outputs)[1]


@dataclass(slots=True)
class Surface:
    key: str  # the Bar's dotted path, with the output when a block opens on several
    name: str
    output: str
    layer: str
    window: LayerWindow | None  # None while a Panel is hidden
    view: View | None
    live: LiveTree
    expanded: Expanded
    geometry: Geometry
    fill: tuple[int, int, int, int] | None = None
    body: TreNode | None = None  # the Bar's body: fill, shadows and the transparent margin
    shadows: list[tuple[Any, ...]] | None = None
    planned: Planned | None = None  # what the surface was last planned from
    extra: dict[str, Any] | None = None  # corner radius and border of a Panel's body
    hidden: bool = False  # a Panel with no window now (D44, revised); a Bar is never hidden
    timer: Any = None  # the pending ``Hide_After`` timer of a Panel
    trace: Any = None  # (label, start, frames left to log): the first frames after a change
    generation: int = 0  # counts shows and hides, so an animation that was replaced stays silent


def _bar_fill(style: dict[str, Value] | None) -> tuple[int, int, int, int] | None:
    if not style:
        return None
    value = style.get("Fill") or style.get("Background")
    if isinstance(value, Color):
        return convert.color(value, ("fill",))["fill"]  # type: ignore[no-any-return]
    return None


def _spec(bar: BarDef, look: Look | None) -> BarSpec:
    from tess_shell.surfaces import bar as bar_module

    return bar_module.BarSpec(
        edge=bar.edge,  # type: ignore[arg-type]
        width=bar.width,  # type: ignore[arg-type]
        height=bar.height,  # type: ignore[arg-type]
        alignment=bar.alignment,  # type: ignore[arg-type]
        offset=bar.offset,
        gap=bar.gap,
        layer=bar.layer,  # type: ignore[arg-type]
        reserve=bar.reserve,
        min_width=bar.min_width,
        min_height=bar.min_height,
        max_width=bar.max_width,
        max_height=bar.max_height,
        bleed=_bleed(bar, look),
    )


def _panel_spec(panel: PanelDef, look: Look | None) -> PanelSpec:
    return PanelSpec(
        panel.anchor,
        panel.inset,
        panel.width,
        panel.height,
        bleed=_bleed(panel, look),
        attach=panel.attach if panel.attach_to else None,
        gap=panel.gap,
        alignment=panel.alignment,
    )


def _geometry(
    bar: BarDef | PanelDef,
    look: Look | None,
    output: tuple[int, int],
    target: Rect | None = None,
    clearance: Rect | None = None,
    saved: Mapping[str, float] | None = None,
) -> Geometry:
    """The geometry of a Bar or a Panel on ``output``; raises :class:`ZeroSize`. ``target`` is the
    rectangle an attached Panel meets, ``clearance`` the Bar around a module it meets, ``saved``
    where the user left a Movable Panel."""
    if isinstance(bar, PanelDef):
        bar = _movable(bar, output, saved)
        return panel_geometry(_panel_spec(bar, look), output, target, clearance)
    return bar_geometry(_spec(bar, look), output)


def _movable(
    panel: PanelDef, output: tuple[int, int], saved: Mapping[str, float] | None
) -> PanelDef:
    """A Movable Panel is moved by tre changing the margins of the edges it is anchored to, so a
    floating one is anchored top and left, where it starts centred (or at its ``Inset``) until it
    is moved. The saved position replaces the ``Inset`` of each side it is anchored to, and is
    kept on the output."""
    if not panel.movable:
        return panel
    anchors = panel.anchor or ("TOP", "LEFT")
    left, top, right, bottom = panel.inset
    width, height = px_size(panel.width, output[0]), px_size(panel.height, output[1])
    if not panel.anchor and not (left or top):
        left, top = (output[0] - width) / 2, (output[1] - height) / 2
    sides = {"left": left, "top": top, "right": right, "bottom": bottom}
    sides.update({k: v for k, v in (saved or {}).items() if k in anchors_lower(anchors)})
    for side, room in (
        ("left", output[0] - width),
        ("right", output[0] - width),
        ("top", output[1] - height),
        ("bottom", output[1] - height),
    ):
        sides[side] = min(max(sides[side], 0), max(room, 0))
    return dataclasses.replace(
        panel, anchor=anchors, inset=(sides["left"], sides["top"], sides["right"], sides["bottom"])
    )


def anchors_lower(anchors: Sequence[str]) -> set[str]:
    return {a.lower() for a in anchors}


def _place(
    bars: Sequence[BarDef | PanelDef],
    look: Look | None,
    output: tuple[int, int],
    hosts: Mapping[str, str] | None = None,
    module_rect: Callable[[str], Rect | None] | None = None,
    saved: Mapping[str, Mapping[str, float]] | None = None,
) -> tuple[dict[str, Geometry], dict[str, str]]:
    """The geometry of every surface of one Monitor on one output, by ``Name``, and the reason
    for each one that gets none. A target is placed before the Panel attached to it, so a chain of
    attached Panels resolves in order; a Panel whose target is not on this Monitor, or was not
    created, is not created either. ``hosts`` maps the ``Name`` of a module used in a Bar to the
    Bar; ``module_rect`` gives the module's laid-out rectangle on the output, or ``None`` before
    the Bar has been laid out, when the Bar's own rectangle stands in for it."""
    hosts = hosts or {}
    geometries: dict[str, Geometry] = {}
    failed: dict[str, str] = {}
    rects: dict[str, Rect] = {}
    pending = list(bars)
    while pending:
        progress = False
        for bar in list(pending):
            target = clearance = None
            if isinstance(bar, PanelDef) and bar.attach_to:
                holder = hosts.get(bar.attach_to, bar.attach_to)  # the surface that is placed first
                if holder in failed:
                    failed[bar.name] = f"its target {bar.attach_to} was not created"
                    pending.remove(bar)
                    progress = True
                    continue
                if holder not in rects:
                    continue  # the target is placed later in this pass, or not at all
                target = rects[holder]
                if bar.attach_to in hosts:
                    clearance = target
                    target = (module_rect and module_rect(bar.attach_to)) or target
            try:
                geometries[bar.name] = _geometry(
                    bar, look, output, target, clearance, (saved or {}).get(bar.name)
                )
            except ZeroSize as exc:
                failed[bar.name] = str(exc)
            else:
                rects[bar.name] = body_rect(geometries[bar.name], output)
            pending.remove(bar)
            progress = True
        if not progress:
            for bar in pending:
                failed[bar.name] = (
                    f"its target {getattr(bar, 'attach_to', None)} is not on this Monitor"
                )
            break
    return geometries, failed


def _keyboard(bar: BarDef | PanelDef, hidden: bool = False, text_field: bool = False) -> str:
    """tre's ``keyboard`` word: the surface's ``Keyboard``, ``none`` for a hidden Panel. A surface
    that holds a TextField and has ``Keyboard: NONE`` (the default) takes ``on_demand``: the
    compositor gives it the keyboard when the field is clicked. A surface with focusable blocks
    and no ``Keyboard`` takes none: Tab does nothing there (Focus and Keyboard > Focusable Things
    and the Focus Ring). ``EXCLUSIVE`` is only ever written."""
    if hidden:
        return "none"
    mode = bar.keyboard.lower()
    return "on_demand" if mode == "none" and text_field else mode


def _kind(bar: BarDef | PanelDef) -> str:
    return "Panel" if isinstance(bar, PanelDef) else "Bar"


def _input_for(
    bar: BarDef | PanelDef, geometry: Geometry, output: tuple[int, int], hidden: bool = False
) -> Any:
    """The ``input_region`` of a surface: a Bar's body; a Panel's ``Input_Region`` (the body,
    nothing, or ``auto``); nothing while a Panel is hidden with its surface kept."""
    if hidden:
        return []
    if isinstance(bar, PanelDef):
        if bar.input == "NONE":
            return []
        if bar.input == "AUTO":
            return "auto"
    return input_region(geometry, output)


def _bar_style(bar: BarDef | PanelDef, look: Look | None) -> dict[str, Value]:
    """The Bar's own style with its token references resolved."""
    errors: list[BindError] = []
    style = resolve_style(bar.style or {}, look, errors)
    _log_errors(errors)
    return style


def _bleed(bar: BarDef | PanelDef, look: Look | None) -> tuple[int, int, int, int]:
    style = resolve_style(bar.style or {}, look)
    return style_bleed(style, _shadows(style, look))


def _shadows(style: dict[str, Value], look: Look | None) -> Any:
    return style_shadows(style, (look.max_shadows if look else None) or DEFAULT_MAX)


def _body_props(
    bar: BarDef | PanelDef, look: Look | None
) -> tuple[tuple[int, int, int, int] | None, list[tuple[Any, ...]]]:
    """The fill and the tre shadows of a Bar's body."""
    style = _bar_style(bar, look)
    shadows: list[tuple[Any, ...]] = convert.shadows(_shadows(style, look), ("shadows",))["shadows"]
    return _bar_fill(style), shadows


SLIDE_DISTANCE = 24  # pixels a slide travels (Panel > Animation)

_EXTRA_KEYS = {
    "Corner_Radius": ("corner_radius", "radius"),
    "Border_Width": ("stroke_width", "number"),
    "Border_Color": ("stroke_color", "color"),
}


def _body_extra(bar: BarDef | PanelDef, look: Look | None) -> dict[str, Any]:
    """The tre properties a Panel's body takes from its style besides fill and shadows: the
    corner radius and the border."""
    if not isinstance(bar, PanelDef):
        return {}
    style = _bar_style(bar, look)
    out: dict[str, Any] = {}
    for key, (name, kind) in _EXTRA_KEYS.items():
        value = style.get(key)
        if value is not None:
            out.update(convert.CONVERTERS[kind](value, (name,), ()))
    return out


def _body_style(
    geometry: Geometry,
    fill: tuple[int, int, int, int] | None,
    shadows: list[tuple[Any, ...]],
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    top, right, bottom, left = geometry.body_margin
    props: dict[str, Any] = {
        "margin_top": top,
        "margin_right": right,
        "margin_bottom": bottom,
        "margin_left": left,
        "shadows": shadows,
    }
    if fill is not None:
        props["fill"] = fill
    props.update(extra or {})
    return props


class PositionStore(Protocol):
    """Where a Movable Panel was left: its ``Inset`` for each side it is anchored to."""

    def position(self, key: str) -> dict[str, float] | None: ...

    def set_position(self, key: str, position: dict[str, float]) -> None: ...


@dataclass(slots=True)
class Planned:
    key: str
    bar: BarDef | PanelDef
    output: Output
    expanded: Expanded
    geometry: Geometry
    where: str
    group: str = (
        ""  # the Monitor and output the surface was planned for: attachment stays inside it
    )


@dataclass(frozen=True, slots=True)
class SurfaceInfo:
    """What the control interface says of a surface (``Status``): its ``Name``, its kind (``bar``,
    ``panel``, ``frame``), the output it is on, the Monitor block it came from and whether it is
    shown now."""

    name: str
    kind: str
    output: str
    monitor: str
    shown: bool


def _handlers(nodes: Sequence[Any]) -> list[Handler]:
    found: list[Handler] = []
    for node in nodes:
        if hasattr(node, "handlers"):
            found.extend(node.handlers.values())
        found.extend(_handlers(getattr(node, "children", ()) or ()))
        found.extend(_handlers(getattr(node, "body", ()) or ()))
        found.extend(_handlers(getattr(node, "else_body", ()) or ()))
    return found


def _check_targets(expanded: Expanded, panels: set[str]) -> None:
    """A shell action names a Panel by its ``Name``; one that names nothing is an error at the
    handler, with the nearest names."""
    for h in _handlers(expanded.nodes):
        target = h.args.get("Target")
        if h.builtin and h.action != "Close" and target not in panels:
            close = difflib.get_close_matches(str(target), sorted(panels), n=3, cutoff=0.5)
            hint = (
                f"did you mean {', '.join(close)}?"
                if close
                else "write the Name of a Panel (or of a Popup, for Show and Toggle)"
            )
            expanded.errors.append(
                BindError(f"{h.action}: no Panel named {target}", h.origin, hint)
            )


def _log_errors(errors: Sequence[BindError]) -> None:
    for error in errors:
        logger.error(
            f"{error.origin}: {error.message}" + (f" ({error.hint})" if error.hint else "")
        )


class SurfaceManager:
    """Two steps at start, so the modules can start between them: :meth:`plan` expands each Bar and
    finds the module uses; :meth:`build` evaluates the slots, binds and opens the windows.
    :meth:`apply` brings the running surfaces to a new shell definition (hot reload)."""

    def __init__(
        self,
        app: App,
        modules: Mapping[str, ModuleDef],
        uid_of: Callable[[str], str],
        store: ValueStore,
        look: Look | None = None,
        sink: Callable[[Handler, str, Any], None] | None = None,
        hide_mode: str = "KEEP",
        positions: PositionStore | None = None,
        join_mode: str = "PARAM",
        blend_mode: str = "LINEAR",
    ) -> None:
        self._app = app
        self._positions = positions  # where the user left each Movable Panel (the registry)
        self._shell_name = ""
        self.hide_mode = hide_mode  # KEEP (the default) or CLOSE (D44)
        self.join_mode = join_mode  # how a melded Panel's join animates (surfaces/join.py)
        # how the Frame's ring is drawn: SRGB, with paths (tre blends their edges in sRGB), or
        # LINEAR, with one shader that blends in linear light (surfaces/frame_shader.py)
        self.blend_mode = blend_mode
        self._depth = 0  # how deep Panel event handlers have called one another
        self.sink = sink
        self._look = look
        self._modules = modules
        self._uid_of = uid_of
        self._store = store
        self.surfaces: list[Surface] = []
        self._planned: list[Planned] = []
        self._kb_warned: set[str] = set()  # surfaces whose ``Keyboard: NONE`` was overridden
        # keyboard focus between surfaces (Focus and Keyboard): the order of the shell's surfaces
        # by ``Tab_Index`` (derived from the planned shell, never a file), and the ``Name`` of the
        # surface that has the OS's keyboard focus (``None``: none of ours)
        self.focus_order: list[str] = []
        self.focused: str | None = None
        self._handle: Any = None
        self._all_uses: Mapping[str, Use] = {}
        from tess_shell.surfaces.popup import PopupPlan, Popups  # popup.py imports this module

        self.popups = Popups(self)
        self._popup_plans: list[PopupPlan] = []  # from the last planning: set_plans commits them
        self.frames = Frames(self)  # the Frames: a painter, reservers, strips and melded Panels
        self._frame_plans: list[FramePlan] = []  # the last planning: ``frames.sync`` opens them
        self._shell: ShellDef | None = None  # the shell definition that is running
        self._planned_shell: ShellDef | None = None  # the one last planned (a check, not yet run)
        from tess_shell.surfaces.hotplug import OutputWatch  # it imports this module

        self.hotplug = OutputWatch(self)
        # a hot-plug re-plans the uses; the host brings the modules to them (the reloader's
        # ``sync_uses``: the same path a reload takes). ``None`` where there are no modules.
        self.sync_uses: Callable[[list[Use]], None] | None = None
        # the uses made for the entries of a For (Module File > Using a Module in a Structure):
        # the ones told to the modules, who is told, and the changes a module's first sends make
        self._dyn_registered: dict[str, Use] = {}
        self.dynamic_sink: Callable[[list[Use], list[str]], None] | None = None
        self._deferred: list[Change] = []
        # the control interface (services/control.py): told when a Panel or a Frame is shown or
        # hidden (``name``, ``"shown"`` or ``"hidden"``); the errors the last ``check`` found
        self.on_surface: Callable[[str, str], None] | None = None
        self.check_errors: list[BindError] = []

    def _dispatch(
        self, handler: Handler, key: str, raw: Any, caller: Mapping[str, Any] | None = None
    ) -> None:
        """A block raised ``key``: evaluate the arguments written as slots (the event fires now,
        so they read the values as they are now; ``caller`` is the record of the Popup the block
        is in) and hand the handler to the sink. A slot that fails is logged at its position and
        the action does not run."""
        if handler.slots:
            try:
                resolved = args.evaluate(handler, self._arg_scope(handler, key, raw, caller))
            except args.ArgError as exc:
                hint = f" ({exc.hint})" if exc.hint else ""
                logger.error(
                    f"{exc.origin}: {exc.message}{hint}; {handler.action} did not run on {key}"
                )
                return
            handler = dataclasses.replace(handler, args=resolved, slots={})
        logger.debug(f"{key} -> {handler.action} {dict(handler.args)} ({handler.origin})")
        self._place(raw)
        if self.sink is not None:
            self.sink(handler, key, raw)

    def _place(self, raw: Any) -> None:
        """``Event.rect``: the block a pointer event was raised on, in output coordinates. The
        binder said where it is in its window (``window_rect``); the window is a Bar's, a Panel's
        or a Frame's strip... whose place on the output is known. A block in a Popup, whose
        place the shell does not track, gets none."""
        in_window = getattr(raw, "window_rect", None)
        window = getattr(raw, "window", None)
        if in_window is None or window is None:
            return
        for s in self.every_surface():
            if s.window is window and s.planned is not None:
                where = surface_rect(s.geometry, self._output_size(s))
                x, y, w, h = in_window
                raw.rect = (where.x + x, where.y + y, w, h)
                return

    def _arg_scope(
        self, handler: Handler, key: str, raw: Any, caller: Mapping[str, Any] | None
    ) -> Any:
        use = self._all_uses.get(handler.use) if handler.use else None
        base = UseScope(use.params, self._store.snapshot(use.key)) if use is not None else None
        return args.scope_for(args.event_record(key, raw), base, handler.entries, caller)

    @property
    def look(self) -> Look:
        assert self._look is not None, "the manager was made without a look"
        return self._look

    # -- planning: no side effect but logging -------------------------------------------------

    def _plan_bars(
        self,
        shell: ShellDef,
        modules: Mapping[str, ModuleDef],
        look: Look | None,
        outputs: Sequence[Output] | None = None,
    ) -> tuple[list[Planned], list[Use]]:
        """Match monitors to outputs, compute each Bar's geometry and expand its module calls.
        The stylesheet's rules are folded into every block first, so ``#name`` selectors see the
        names as written. ``outputs`` is the list the hot-plug code tracks; without it the
        outputs are read from the compositor, and the tracked list starts over from them."""
        self._shell_name = shell.name
        self._planned_shell = shell
        # a Bar that shows the Tray or Audio gets shipped Popups: its modules need a root block id
        shipped_popups = bool(SHIPPED_POPUP_MODULES & modules.keys())
        rules = look.rules if look else ()
        if rules:
            modules = {
                n: dataclasses.replace(d, children=apply_rules(d.children, rules, n))
                for n, d in modules.items()
            }
        if outputs is None:
            outputs = list(self._app.outputs())
            self.hotplug.known = list(outputs)
        if not outputs:
            logger.warning("no outputs: no surface was opened")
            self._popup_plans = []
            self._frame_plans = []
            return [], []
        for loser, winner, i in conflicts(shell.monitors, outputs):
            logger.warning(
                f"{loser.origin}: Monitor {loser.name} names {outputs[i].name}, which Monitor "
                f"{winner.name} ({winner.origin}) already took; {winner.name} wins and "
                f"{loser.name} opens nothing"
            )
        planned: list[Planned] = []
        uses: list[Use] = []
        for monitor, indices in assign(shell.monitors, outputs):
            if not indices:
                logger.info(
                    f"monitor {monitor.name} matches no output; its surfaces are not opened"
                )
                continue
            for i in indices:
                group = f"{monitor.name}@{outputs[i].name}"
                hosts = {
                    use: surface.name
                    for surface in monitor.surfaces
                    if isinstance(surface, BarDef)
                    for use in use_names(surface.children)
                }
                wanted = frozenset(
                    p.attach_to
                    for p in monitor.surfaces
                    if isinstance(p, PanelDef) and p.attach_to in hosts
                )
                geometries, failed = _place(
                    monitor.surfaces,
                    look,
                    (outputs[i].width, outputs[i].height),
                    hosts,
                    lambda label, group=group: self._module_rect(group, label),  # type: ignore[misc]
                    self._saved(group, monitor.surfaces),
                )
                for bar in monitor.surfaces:
                    where = f"{bar.name} on {outputs[i].name}"
                    kind = _kind(bar)
                    if bar.name in failed:
                        logger.warning(
                            f"{bar.origin}: {kind} {where} is not created: {failed[bar.name]}"
                        )
                        continue
                    geometry = geometries[bar.name]
                    for warning in geometry.warnings:
                        logger.warning(f"{bar.origin}: {kind} {where}: {warning}")
                    suffix = f"@{outputs[i].name}" if is_default(monitor) else ""
                    path = f"{shell.name}.{monitor.name}{suffix}.{bar.name}"
                    children = apply_rules(bar.children, rules)
                    expanded = expand(
                        children,
                        path,
                        modules,
                        self._uid_of,
                        outputs[i].name,
                        rules,
                        wanted,
                        bool(monitor.popups) or shipped_popups,
                    )
                    uses.extend(expanded.uses)
                    planned.append(
                        Planned(
                            path,
                            bar,
                            outputs[i],
                            expanded,
                            geometry,
                            where,
                            group,
                        )
                    )
        panel_names = {
            surface.name
            for m in shell.monitors
            for surface in m.surfaces
            if _kind(surface) == "Panel"
        }
        frame_names = {f.name for m in shell.monitors for f in m.frames}
        melded = {p.name for m in shell.monitors for f in m.frames for p in f.melds}
        melded |= {
            e.name for m in shell.monitors for f in m.frames for e in f.edges.values() if e.name
        }
        popup_names = {p.name for m in shell.monitors for p in m.popups}
        targets = panel_names | frame_names | melded | popup_names
        for p in planned:
            _check_targets(p.expanded, targets)

        def expand_hosted(children: Any, path: str, output: str, popups: bool) -> Expanded:
            return expand(
                apply_rules(children, rules),
                path,
                modules,
                self._uid_of,
                output,
                rules,
                frozenset(),
                popups,
            )

        self._frame_plans = self.frames.plan(
            shell, outputs, assign(shell.monitors, outputs), look, is_default, expand_hosted
        )
        for fp in self._frame_plans:
            uses.extend(fp.uses())
            for hp in fp.hosts:
                _check_targets(hp.planned.expanded, targets)
        self._popup_plans, popup_uses = self.popups.plan(
            shell, modules, look, outputs, self._uid_of, assign, targets, uses
        )
        uses.extend(popup_uses)
        return planned, uses

    def planned_handlers(self, planned: Sequence[Planned] | None = None) -> list[Handler]:
        """Every handler of the last planning: the Bars and Panels (``planned``, or the ones
        :meth:`plan` made), the Popups, the tooltips and the Frames' strips and melded Panels."""
        expanded = [p.expanded for p in (self._planned if planned is None else planned)]
        expanded.extend(p.expanded for p in self._popup_plans)
        expanded.extend(h.planned.expanded for fp in self._frame_plans for h in fp.hosts)
        found: list[Handler] = []
        for e in expanded:
            found.extend(_handlers(e.nodes))
            for tip in e.tooltips.values():
                found.extend(_handlers(tip.nodes))
        return found

    def _frame_uses(self) -> dict[str, Use]:
        """The module uses of the strips and melded Panels of the last planning."""
        return {u.key: u for fp in self._frame_plans for u in fp.uses()}

    # -- the uses made for the entries of a For -------------------------------------------------

    def new_live(self, uses: Mapping[str, Use], **kwargs: Any) -> LiveTree:
        """A live tree for one surface; the uses it makes for the entries of a ``For`` are
        announced to the modules the moment it makes them (their first values are in the store
        before the blocks that read them are resolved)."""
        live = LiveTree(self._store, uses, look=self._look, **kwargs)
        live.activate = self._activate_dynamic
        return live

    def _activate_dynamic(self, use: Use) -> None:
        if self._dyn_registered.get(use.key) == use:
            return
        self._dyn_registered[use.key] = use
        self._store.add_use(use.module, use.key)
        if isinstance(self._all_uses, dict):
            self._all_uses[use.key] = use
        if self.dynamic_sink is not None:
            self.dynamic_sink([use], [])
        self._deferred.extend(self._store.flush())

    def merge_dynamic(self, uses: dict[str, Use]) -> None:
        """Keep the uses made for entries in a map of uses that was made again."""
        uses.update(self._dyn_registered)

    def settle_dynamic(self) -> None:
        """Tell the modules of the uses whose entries are gone, then apply what the modules sent
        for the uses that came (the surfaces were resolved with it already; the rest is news)."""
        live: set[str] = set()
        for surface in self.every_surface():
            if surface.live is not None:
                live.update(surface.live.dyn_uses)
        for popup_live in self.popups.lives():
            live.update(popup_live.dyn_uses)
        gone = [key for key in self._dyn_registered if key not in live]
        if gone:
            removed = [self._dyn_registered.pop(key) for key in gone]
            if isinstance(self._all_uses, dict):
                for key in gone:
                    self._all_uses.pop(key, None)
            if self.dynamic_sink is not None:
                self.dynamic_sink([], gone)
            for use in removed:
                self._store.remove_use(use.key)
        if self._deferred:
            pending, self._deferred = self._deferred, []
            self.on_change(pending)

    def dynamic_module_names(self, planned: Sequence[Planned] | None = None) -> set[str]:
        """The modules a ``For`` of the last planning calls: they are loaded though nothing uses
        them until an entry does."""
        expanded = [p.expanded for p in (self._planned if planned is None else planned)]
        expanded.extend(p.expanded for p in self._popup_plans)
        expanded.extend(h.planned.expanded for fp in self._frame_plans for h in fp.hosts)
        names: set[str] = set()
        for e in expanded:
            names |= e.dynamic_modules
        return names

    def every_surface(self) -> list[Surface]:
        """The Bars and Panels, and the strips and melded Panels hosted in a Frame's painter."""
        return [*self.surfaces, *self.frames.host_surfaces()]

    def plan(self, shell: ShellDef) -> list[Use]:
        planned, uses = self._plan_bars(shell, self._modules, self._look)
        self._shell = shell
        self.focus_order = surface_order(shell)
        for use in uses:
            self._store.add_use(use.module, use.key)
        self._planned = planned
        self.popups.set_plans(self._popup_plans)
        return uses

    # -- opening ------------------------------------------------------------------------------

    def build(self) -> list[Surface]:
        """Evaluate the slots with the values the modules have sent so far, bind, and open."""
        all_uses = {u.key: u for p in self._planned for u in p.expanded.uses}
        all_uses.update(self.popups.uses())
        all_uses.update(self._frame_uses())
        self._all_uses = all_uses
        for planned in self._planned:
            self.surfaces.append(self._open(planned, all_uses))
        self.frames.sync(self._frame_plans, self._look)
        self.settle_dynamic()
        return self.surfaces

    def _make_window(self, planned: Planned, live: LiveTree, hidden: bool = False) -> Surface:
        """Create the window of a Bar or a Panel and bind its tree. The window is not added to the
        app yet; the caller does that (at start, or when a hidden Panel is shown)."""
        from tess_re import LayerWindow

        bar, output, geometry, where = planned.bar, planned.output, planned.geometry, planned.where
        kind = _kind(bar)
        found = first_text_field(planned.expanded.nodes)
        field = found is not None
        if field and not hidden and _keyboard(bar, False, True) != _keyboard(bar):
            if getattr(bar, "keyboard_written", False) and planned.key not in self._kb_warned:
                # ``Keyboard: NONE`` is written, and a field needs the keyboard to be typed in
                # (M4 Brief, question 17): the override is said once, not silent
                self._kb_warned.add(planned.key)
                logger.warning(
                    f"{bar.origin}: {kind} {where}: Keyboard: NONE is written, but it holds "
                    f"{describe_text_field(found)}; the surface takes the keyboard on_demand "
                    "(a click on the field gives it the keyboard)"
                )
            logger.info(f"{kind} {where}: keyboard on_demand, it holds a text field")
        window = LayerWindow(
            f"tesserae-shell.{kind.lower()}.{bar.name}",
            layer=bar.layer.lower(),  # type: ignore[arg-type]
            anchor=geometry.anchor,
            size=geometry.size,
            margin=geometry.margin,
            exclusive_zone=geometry.exclusive_zone,
            exclusive_edge=geometry.exclusive_edge,  # type: ignore[arg-type]
            keyboard=_keyboard(bar, hidden, field),  # type: ignore[arg-type]
            input_region=_input_for(bar, geometry, (output.width, output.height), hidden),
            output=output,
        )
        fill, shadows = _body_props(bar, self._look)
        extra = _body_extra(bar, self._look)
        handle = {"window_region": "drag_margin"} if getattr(bar, "movable", False) else {}
        body = window.create(
            "box",
            flex_grow=1,
            align_self="stretch",
            **handle,
            **_body_style(geometry, fill, shadows, extra),
        )
        window.root.add_child(body)
        window.on(
            "configure",
            lambda e, n=where: logger.info(f"{kind} {n} configured {int(e.width)}x{int(e.height)}"),
        )

        def closed(e: Any, n: str = where, k: str = kind, name: str = bar.name) -> None:
            logger.info(f"{k} {n} closed ({getattr(e, 'reason', '')})")
            self._surface_gone(name)

        window.on("closed", closed)
        window.on("active", lambda e, name=bar.name: self._surface_active(name, bool(e.active)))

        def pointer_trace(e: Any, n: str = where, k: str = kind, p: str = "") -> None:
            logger.debug(
                f"{k} {n} {p} at {getattr(e, 'window_x', None)},{getattr(e, 'window_y', None)}"
            )
            if p == "pointer_down":  # tre gives a click on another window to that window
                self.popups.surface_pointer_down()

        for pointer in ("pointer_down", "pointer_up"):  # a trace: where a click's time goes
            window.root.on(pointer, lambda e, p=pointer: pointer_trace(e, p=p))
        view: View | None = None
        errors = list(planned.expanded.errors)
        if not errors:
            try:
                view = build(live.resolve(planned.expanded), window, body)
                view.sink = self._dispatch
                self._watch_targets(view, planned)
                self.popups.watch(view, planned)
            except BindFailed as failed:
                errors = failed.errors
        _log_errors(errors)
        if view is None:
            logger.error(f"{kind} {where} is empty: its contents did not bind")
        return Surface(
            planned.key,
            bar.name,
            output.name,
            bar.layer,
            window,
            view,
            live,
            planned.expanded,
            geometry,
            fill,
            body,
            shadows,
            planned,
            extra,
        )

    def _open(self, planned: Planned, all_uses: Mapping[str, Use]) -> Surface:
        bar, output, geometry, where = planned.bar, planned.output, planned.geometry, planned.where
        kind = _kind(bar)
        live = self.new_live(all_uses)
        if isinstance(bar, PanelDef) and not bar.visible and self.hide_mode == "CLOSE":
            # a hidden Panel has no surface at all: nothing to go stale, nothing for the
            # compositor to hold, and no flash when it is first shown (D44, CLOSE)
            logger.info(f"{kind} {where}: anchor {','.join(geometry.anchor) or 'none'} (hidden)")
            return Surface(
                planned.key,
                bar.name,
                output.name,
                bar.layer,
                None,
                None,
                live,
                planned.expanded,
                geometry,
                planned=planned,
                hidden=True,
            )
        keep_hidden = isinstance(bar, PanelDef) and not bar.visible  # KEEP: a mapped, empty surface
        surface = self._make_window(planned, live, keep_hidden)
        assert surface.window is not None
        self._app.add_window(surface.window)
        logger.info(
            f"{kind} {where}: anchor {','.join(geometry.anchor) or 'none'} size {geometry.size} "
            f"zone {geometry.exclusive_zone}" + (" (hidden, surface kept)" if keep_hidden else "")
        )
        if isinstance(bar, PanelDef):
            self._panel_events(surface)
            self._watch_frames(surface)
            if keep_hidden:
                surface.hidden = True
                surface.window.root.set(visible=False)
            else:
                self._arm_hide_after(surface)
                surface.window.after(1, lambda: self._fire(surface, "On_Visible"))
        return surface

    # -- Panel: hide, show, Hide_After, Escape (D44) ----------------------------------------------
    #
    # tre cannot unmap a layer surface. KEEP (the default) leaves it mapped and drawing nothing.
    # CLOSE makes a new window on show; what a module knows lives in the module. (Before tre 0.6.2
    # KEEP needed a wake after every change, TRE-REQ-012; before 0.6.4 an animation started from a
    # timer needed one too. Both are fixed in tre and the shell no longer wakes the loop.)

    def _panel_events(self, s: Surface) -> None:
        """Escape hides a Panel that takes the keyboard."""
        assert s.window is not None

        def on_key(event: Any) -> None:
            current = s.planned.bar if s.planned else None
            if (
                getattr(event, "key", None) == "escape"
                and isinstance(current, PanelDef)
                and current.keyboard != "NONE"
            ):
                self.hide(s)

        s.window.root.on("key_down", on_key)  # a key bubbles up from the focused node
        s.window.on("moved", lambda event: self._moved(s, tuple(event.margin)))

    def _moved(self, s: Surface, margin: tuple[int, int, int, int]) -> None:
        """tre moved a Movable Panel by its margins and the button went up: the margins are the
        position. Each anchored side's ``Inset`` is its margin plus the transparent margin of the
        shadow, and is saved (Panel > Position and Attachment)."""
        if s.planned is None:
            return
        top, right, bottom, left = margin
        b_top, b_right, b_bottom, b_left = s.geometry.body_margin
        inset = {
            "left": left + b_left,
            "top": top + b_top,
            "right": right + b_right,
            "bottom": bottom + b_bottom,
        }
        position = {k: float(v) for k, v in inset.items() if k in s.geometry.anchor}
        s.geometry = dataclasses.replace(s.geometry, margin=margin)
        s.planned.geometry = s.geometry
        logger.info(f"Panel {s.planned.where} moved to {position}")
        if self._positions is not None:
            self._positions.set_position(self._position_key(s.planned.group, s.name), position)

    def _arm_hide_after(self, s: Surface) -> None:
        """(Re)start the ``Hide_After`` timer: showing a Panel again resets it."""
        if s.timer is not None:
            s.timer.cancel()
            s.timer = None
        panel = s.planned.bar if s.planned else None
        if s.window is not None and isinstance(panel, PanelDef) and panel.hide_after is not None:
            s.timer = s.window.after(panel.hide_after, lambda: self.hide(s))

    def _watch_frames(self, s: Surface) -> None:
        """Log the first frames a Panel draws after a show or a hide (DEBUG): what tells a late
        event from a late repaint on a real compositor."""
        assert s.window is not None and s.planned is not None
        where = s.planned.where

        def on_frame(event: Any) -> None:
            trace = s.trace
            if trace is None:
                return
            label, started, left = trace
            ms = (time.monotonic() - started) * 1000
            logger.debug(f"Panel {where}: a frame {ms:.0f} ms after it was {label}")
            s.trace = (label, started, left - 1) if left > 1 else None

        s.window.on("frame", on_frame)

    def _trace(self, s: Surface, label: str) -> None:
        assert s.window is not None and s.planned is not None
        s.trace = (label, time.monotonic(), 3)
        where, window = s.planned.where, s.window

        def frames_so_far() -> None:
            try:
                count = window.frame_stats()["frames"]
            except Exception:  # the window may be gone by now
                return
            logger.debug(f"Panel {where}: {count} frames drawn 250 ms after it was {label}")

        window.after(250, frames_so_far)

    def _place_group(
        self, group: str, look: Look | None
    ) -> tuple[dict[str, Geometry], dict[str, str]]:
        """Place every open surface of one Monitor and output again, with the modules' laid-out
        rectangles as they are now."""
        members = [s.planned for s in self.surfaces if s.planned and s.planned.group == group]
        bars = [p.bar for p in members]
        hosts = {
            use: p.bar.name
            for p in members
            if isinstance(p.bar, BarDef)
            for use in use_names(p.bar.children)
        }
        size = (members[0].output.width, members[0].output.height)
        saved = self._saved(group, bars)
        return _place(bars, look, size, hosts, lambda label: self._module_rect(group, label), saved)

    def _position_key(self, group: str, name: str) -> str:
        return f"position:{self._shell_name}.{group}.{name}"

    def _saved(self, group: str, bars: Sequence[BarDef | PanelDef]) -> dict[str, dict[str, float]]:
        """Where the user left each Movable Panel of this Monitor and output."""
        if self._positions is None:
            return {}
        found: dict[str, dict[str, float]] = {}
        for bar in bars:
            if isinstance(bar, PanelDef) and bar.movable:
                position = self._positions.position(self._position_key(group, bar.name))
                if position:
                    found[bar.name] = position
        return found

    def _module_rect(self, group: str, label: str) -> Rect | None:
        """Where tre laid out the root block of the module used under ``Name: label``, on the
        output; ``None`` while its Bar has no tree or no layout yet."""
        for t in self.surfaces:
            if t.planned is None or t.planned.group != group or t.view is None:
                continue
            node_id = t.planned.expanded.targets.get(label)
            node = t.view.nodes.get(node_id) if node_id else None
            if node is None:
                continue
            x, y, w, h = (
                float(node.get(k))
                for k in ("layout_x", "layout_y", "layout_width", "layout_height")
            )
            if w <= 0 and h <= 0:
                return None
            origin = surface_rect(t.geometry, self._output_size(t))
            return Rect(origin.x + x, origin.y + y, w, h)
        return None

    def _watch_targets(self, view: View, planned: Planned) -> None:
        """A Panel attached to a module follows it: tre's ``layout`` event says when the module's
        root block was first laid out or changed size (only a node with a listener is watched), and
        the Panel is placed again from where the block is now."""
        for node_id in planned.expanded.targets.values():
            node = view.nodes.get(node_id)
            if node is not None:
                node.on("layout", lambda _e, g=planned.group: self._relayout_attached(g))

    def _relayout_attached(self, group: str) -> None:
        for t in list(self.surfaces):
            if t.planned and t.planned.group == group and not t.hidden:
                self._refresh_attached(t)

    def _refresh_attached(self, s: Surface) -> None:
        """A Panel attached to a module is placed again when it is shown, from where the module
        is now: the module's width may have changed since the Bar was planned."""
        p = s.planned
        if p is None or not isinstance(p.bar, PanelDef) or not p.bar.attach_to:
            return
        geometry = self._place_group(p.group, self._look)[0].get(p.bar.name)
        if geometry is None or geometry == p.geometry:
            return
        p.geometry = geometry
        if s.window is not None:
            self._sync_body(s, p.bar, geometry, p.where)

    def _attached_to(self, s: Surface) -> list[Surface]:
        """The open Panels attached to ``s`` (same Monitor and output)."""
        if s.planned is None:
            return []
        return [
            t
            for t in self.surfaces
            if t.planned is not None
            and t.planned.group == s.planned.group
            and isinstance(t.planned.bar, PanelDef)
            and t.planned.bar.attach_to == s.name
        ]

    def _target_of(self, s: Surface) -> Surface | None:
        """The surface ``s`` is attached to, if it is."""
        if (
            s.planned is None
            or not isinstance(s.planned.bar, PanelDef)
            or not s.planned.bar.attach_to
        ):
            return None
        name = s.planned.bar.attach_to
        return next(
            (
                t
                for t in self.surfaces
                if t.planned and t.planned.group == s.planned.group and t.name == name
            ),
            None,
        )

    def hide(self, s: Surface) -> None:
        """Hide a Panel. KEEP (the default, D44): keep the surface, draw nothing, take no pointer
        and no keyboard; the tree and its state stay. CLOSE: destroy the window (the record, its
        place and what its modules know stay) and make a new one on show. With an ``Animation``
        the Panel leaves first and is hidden when the animation ends."""
        if s.hidden or s.planned is None or s.window is None:
            return
        for attached in self._attached_to(s):  # a Panel does not stay open without its target
            self.hide(attached)
        self.popups.parent_closed(s)  # a Popup does not stay open without its parent
        if s.timer is not None:
            s.timer.cancel()
            s.timer = None
        self._fire(s, "On_Close")  # before: the request is made
        s.hidden = True
        self.changed(s.name, False)
        if self.hide_mode == "KEEP":  # a hiding Panel takes no input, whatever its animation
            s.window.set(input_region=[], keyboard="none")
        self._leave(s, lambda: self._finish_hide(s))

    def _finish_hide(self, s: Surface) -> None:
        """The Panel has left: draw nothing (KEEP) or destroy the window (CLOSE)."""
        window = s.window
        if window is None or s.planned is None:
            return
        if self.hide_mode == "KEEP":
            window.set(margin=s.geometry.margin)  # back at rest for the next show; ends any slide
            window.root.set(opacity=1.0, visible=False)
            self._trace(s, "hidden")
            logger.info(f"Panel {s.planned.where} hidden (surface kept)")
        else:
            s.window, s.view, s.body = None, None, None
            window.close()
            logger.info(f"Panel {s.planned.where} hidden (window closed)")
        self._fire(s, "On_Hidden")  # after: it is hidden

    def show(self, s: Surface) -> None:
        if s.planned is None:
            return
        if not s.hidden:
            self._arm_hide_after(s)  # shown again: the timer starts over
            return
        target = self._target_of(s)
        if target is not None and target.hidden:
            logger.info(f"Panel {s.planned.where} stays hidden: its target {target.name} is hidden")
            return
        self._refresh_attached(s)
        self._fire(s, "On_Open")  # before: the request is made
        if s.window is not None:  # KEEP: the surface is still there (or it is still leaving)
            bar = s.planned.bar
            s.hidden = False
            self.changed(s.name, True)
            s.window.root.set(visible=True)
            s.window.set(
                input_region=_input_for(bar, s.geometry, self._output_size(s)),
                keyboard=_keyboard(bar, False, holds_text_field(s.planned.expanded.nodes)),
            )
            self._arm_hide_after(s)
            self._trace(s, "shown")
            logger.info(f"Panel {s.planned.where} shown (surface kept)")
            self._enter(s)
            return
        fresh = self._make_window(s.planned, self.new_live(self._all_uses))
        assert fresh.window is not None
        s.window, s.view, s.body = fresh.window, fresh.view, fresh.body
        s.live, s.fill, s.shadows, s.extra = fresh.live, fresh.fill, fresh.shadows, fresh.extra
        s.expanded, s.geometry, s.hidden = s.planned.expanded, s.planned.geometry, False
        self.changed(s.name, True)
        self._app.add_window(s.window)
        self._panel_events(s)
        self._watch_frames(s)
        self._arm_hide_after(s)
        self._trace(s, "shown")
        logger.info(f"Panel {s.planned.where} shown (window created)")
        self._enter(s)

    # -- Panel: animation (Panel > Configuration, Animation) -------------------------------------
    #
    # SLIDE moves the surface's margin a short way toward the edge it grows from (its attached
    # target, or its anchored edge) while its opacity runs 0 to 1, so it never covers its
    # neighbour; FADE is the opacity alone. tre runs both in the engine, one small commit per step
    # and no Python until the end. With the desktop's reduced-motion setting on, nothing moves.

    def _animated(self, s: Surface) -> bool:
        panel = s.planned.bar if s.planned else None
        if not isinstance(panel, PanelDef) or panel.animation == "NONE" or s.window is None:
            return False
        return not (self._look is not None and self._look.appearance.reduced_motion)

    @staticmethod
    def _slide_from(panel: PanelDef, geometry: Geometry) -> tuple[int, int] | None:
        """The margin a slide starts from: its index in tre's (top, right, bottom, left) order and
        the signed distance from the resting margin, or ``None`` when there is nothing to slide
        along (a centred floating Panel)."""
        d = SLIDE_DISTANCE
        if panel.attach_to:
            return {"BOTTOM": (0, -d), "TOP": (0, d), "RIGHT": (3, -d), "LEFT": (3, d)}.get(
                panel.attach or "BOTTOM"
            )
        for edge, index in (("top", 0), ("bottom", 2), ("left", 3), ("right", 1)):
            if edge in geometry.anchor:
                return (index, -d)  # closer to its edge: a smaller margin
        return None

    def _move(self, s: Surface, toward_rest: bool, done: Callable[[], None]) -> None:
        """Run the animation: in (``toward_rest``) or out; ``done`` runs when it ends, unless
        another show or hide replaced it first."""
        assert s.window is not None and s.planned is not None
        panel = s.planned.bar
        assert isinstance(panel, PanelDef)
        window, ms = s.window, int(panel.duration)
        s.generation += 1
        generation = s.generation
        slide = self._slide_from(panel, s.geometry) if panel.animation == "SLIDE" else None
        self._fire(s, "On_Anim_Start")
        logger.debug(
            f"Panel {s.planned.where} {panel.animation.lower()} {'in' if toward_rest else 'out'}, "
            f"{ms} ms"
        )

        def ended() -> None:
            if s.generation == generation:
                self._fire(s, "On_Anim_End")
                done()

        easing = (0.0, 0.0, 0.2, 1.0) if toward_rest else (0.4, 0.0, 1.0, 1.0)
        if slide is not None:
            index, away = slide
            rest = s.geometry.margin
            far = tuple(v + away if i == index else v for i, v in enumerate(rest))
            if toward_rest and window.get("margin") == rest:
                window.set(margin=far)  # start from the far side, unless a hide left it midway
            window.animate(
                ("margin_top", "margin_right", "margin_bottom", "margin_left")[index],
                (rest if toward_rest else far)[index],
                ms,
                easing,
            )
        if toward_rest and window.root.get("opacity") == 1.0:
            window.root.set(opacity=0.0)
        window.root.animate("opacity", 1.0 if toward_rest else 0.0, ms, easing, ended)

    def _enter(self, s: Surface) -> None:
        """The Panel is shown: slide or fade it in, then it is visible."""
        if self._animated(s):
            self._move(s, True, lambda: self._fire(s, "On_Visible"))
            return
        s.generation += 1  # a hide that was still leaving is cancelled
        if s.window is not None:
            s.window.set(margin=s.geometry.margin)
            s.window.root.set(opacity=1.0)
            s.window.after(1, lambda: self._fire(s, "On_Visible") if not s.hidden else None)

    def _leave(self, s: Surface, done: Callable[[], None]) -> None:
        if self._animated(s):
            self._move(s, False, done)
        else:
            s.generation += 1
            done()

    # -- Panel: its own events (Events and Actions) ------------------------------------------------

    def _fire(self, s: Surface, key: str) -> None:
        """Run the handler a Panel wrote for ``key``. A shell file can name only the shell's own
        actions (Show, Hide, Toggle); a handler that shows a Panel that shows this one again is
        stopped after a few turns and logged, not left to loop."""
        panel = s.planned.bar if s.planned else None
        handler = panel.handlers.get(key) if isinstance(panel, PanelDef) else None
        if handler is None:
            return
        if self._depth >= 8:
            logger.error(
                f"{handler.origin}: {key} on Panel {s.name} calls itself in a loop; stopped"
            )
            return
        self._depth += 1
        try:
            self.run_builtin(handler)
        except Exception:
            logger.exception(f"{handler.origin}: {key} on Panel {s.name} raised")
        finally:
            self._depth -= 1

    # -- the control interface ----------------------------------------------------------------

    def changed(self, name: str, shown: bool) -> None:
        """A Panel or a Frame was shown or hidden: tell the control interface (it makes the
        ``SurfaceChanged`` signal)."""
        if self.on_surface is not None:
            self.on_surface(name, "shown" if shown else "hidden")

    def surface_infos(self) -> list[SurfaceInfo]:
        """Every surface a command can name: the Bars and Panels, the Frames and their melded
        Panels (a Frame's strips are parts of it, not surfaces of their own)."""
        out: list[SurfaceInfo] = []
        for s in self.surfaces:
            if s.planned is not None:
                kind = _kind(s.planned.bar).lower()
                out.append(
                    SurfaceInfo(s.name, kind, s.output, s.planned.group.split("@")[0], not s.hidden)
                )
        for st in self.frames.states.values():
            monitor, output = st.plan.group.split("@")[0], st.plan.output.name
            out.append(SurfaceInfo(st.plan.frame.name, "frame", output, monitor, not st.hidden))
            for meld in st.plan.frame.melds:
                shown = meld.name not in st.hidden_melds and not st.hidden
                out.append(SurfaceInfo(meld.name, "panel", output, monitor, shown))
        return out

    def control_surface(self, action: str, name: str) -> tuple[bool, str]:
        """``Show``, ``Hide`` or ``Toggle`` for the control interface: on the Panel, the Frame or
        the melded Panel called ``name``. ``(ok, message)``: an unknown name is an error with the
        nearest names, a Popup is never opened by a command, a Bar is always shown, and showing a
        Panel whose target is hidden reports that it stays hidden. Idempotent: showing what is
        shown succeeds and does nothing."""
        infos = self.surface_infos()
        found = [i for i in infos if i.name == name]
        if not found:
            popups = sorted({n for _, n in self.popups.plans})
            if name in popups:
                return False, (
                    f"{name} is a Popup: no command opens a Popup (a Popup needs the pointer "
                    "or key press that opened it); a Panel can be opened by a command"
                )
            names = sorted({i.name for i in infos})
            close = nearest(name, names)
            hint = (
                f"did you mean {', '.join(close)}?"
                if close
                else f"the surfaces: {', '.join(names) or 'none'}"
            )
            return False, f"no surface named {name} ({hint})"
        if all(i.kind == "bar" for i in found):
            if action == "Show":
                return True, f"{name} is a Bar and is always shown"
            return False, f"{name} is a Bar: a Bar cannot be hidden"
        self.run_builtin(Handler(action, {"Target": name}, builtin=True))
        plain = [i for i in self.surface_infos() if i.name == name and i.kind == "panel"]
        framed = {m.name for st in self.frames.states.values() for m in st.plan.frame.melds}
        if action != "Toggle" and name not in framed and plain:
            shown = all(i.shown for i in plain)
            if shown != (action == "Show"):  # the log says why (a hidden target)
                return False, f"{name} stays {'shown' if shown else 'hidden'}: see the log"
        now = [i for i in self.surface_infos() if i.name == name]
        return True, f"{name} is {'shown' if all(i.shown for i in now) else 'hidden'}"

    def run_builtin(self, handler: Handler, raw: Any = None) -> None:
        """A shell action (``Show``, ``Hide``, ``Toggle``) on the Panel or the Popup it names;
        ``raw`` is the event of the block that raised it (a Popup opens beside that block)."""
        if handler.action == "Close":  # a Popup's own blocks close it (Popups); this one is not
            logger.warning(f"{handler.origin}: Close: the block is not in a Popup; nothing closed")
            return
        target = handler.args.get("Target")
        if self.frames.run(handler.action, target):
            return
        hits = [
            s
            for s in self.surfaces
            if s.name == target and s.planned and _kind(s.planned.bar) == "Panel"
        ]
        if not hits:
            if self.popups.run_named(handler, raw):
                return
            logger.warning(f"{handler.origin}: {handler.action}: Panel {target} is not open")
            return
        for s in hits:
            if handler.action == "Show":
                self.show(s)
            elif handler.action == "Hide":
                self.hide(s)
            else:
                self._fire(s, "On_Toggle")  # before: the request is made
                (self.hide if not s.hidden else self.show)(s)

    # -- changes ------------------------------------------------------------------------------

    def _rebuild(self, surface: Surface) -> None:
        """A use with an If or For read something that changed: resolve the Bar's tree again and
        let the keyed diff change only what differs."""
        assert surface.view is not None
        try:
            stats = surface.view.rebuild(surface.live.resolve(surface.expanded))
            if surface.planned is not None:
                self._watch_targets(surface.view, surface.planned)
                self.popups.watch(surface.view, surface.planned)
            logger.debug(f"rebuilt Bar {surface.name}: {stats}")
        except BindFailed as failed:
            for error in failed.errors:
                logger.warning(f"{error.origin}: {error.message}; the Bar keeps what it shows")

    def on_change(self, changes: list[Change]) -> None:
        """Loop thread: the store changed. One ``apply`` per surface per turn."""
        for surface in self.every_surface():
            if surface.view is None:
                continue
            result = surface.live.apply_changes(changes)
            if result.rebuild:
                self._rebuild(surface)
                continue
            updates = result.updates
            for node_id, key, value in updates:
                shown = getattr(value, "value", value)
                logger.debug(f"update {node_id} {key} = {shown!r}")
            for error in surface.view.update(updates):
                logger.warning(f"{error.origin}: {error.message}")
        self.popups.on_change(changes)
        self.settle_dynamic()

    def check(
        self, shell: ShellDef, modules: Mapping[str, ModuleDef], look: Look | None = None
    ) -> tuple[list[Planned], list[Use]] | None:
        """Plan ``shell`` for a reload without changing anything. ``None`` when a Bar's tree has
        an error that would leave it empty: the running state is kept."""
        planned, uses = self._plan_bars(shell, modules, look or self._look)
        failed = [p for p in planned if p.expanded.errors]
        failed.extend(p for p in self._popup_plans if p.expanded.errors)  # type: ignore[misc]
        failed.extend(
            h.planned for fp in self._frame_plans for h in fp.hosts if h.planned.expanded.errors
        )
        self.check_errors = [e for p in failed for e in p.expanded.errors]
        for p in failed:
            _log_errors(p.expanded.errors)
        if failed:
            return None
        return planned, uses

    def apply(
        self,
        planned: list[Planned],
        modules: Mapping[str, ModuleDef],
        store_uses: Sequence[Use],
        look: Look | None = None,
    ) -> None:
        """Make the running surfaces match ``planned`` (from :meth:`check`): a surface whose key,
        output, layer and exclusive edge are unchanged is kept, its tree rebuilt by the keyed diff
        and its geometry set live; the rest are closed or opened. All-or-nothing per surface: a
        tree that does not bind leaves that surface as it was."""
        self._modules = modules
        self._shell = self._planned_shell  # the shell ``check`` just planned
        if self._shell is not None:
            self.focus_order = surface_order(self._shell)
        if look is not None:
            self._look = look
        self.popups.set_plans(self._popup_plans)  # the plans of the check just made
        all_uses = {u.key: u for p in planned for u in p.expanded.uses}
        all_uses.update(self.popups.uses())
        all_uses.update(self._frame_uses())
        self.merge_dynamic(all_uses)
        self._all_uses = all_uses
        old = {s.key: s for s in self.surfaces}
        out: list[Surface] = []
        for p in planned:
            s = old.pop(p.key, None)
            if (
                s is not None
                and s.output == p.output.name
                and s.layer == p.bar.layer
                and s.geometry.exclusive_edge == p.geometry.exclusive_edge
            ):
                self._update(s, p, all_uses)
                out.append(s)
                continue
            if s is not None:
                self._close(s)
            out.append(self._open(p, all_uses))
        for s in old.values():
            self._close(s)
        self.surfaces = out
        self.frames.sync(self._frame_plans, self._look)
        self.settle_dynamic()
        keep = {u.key for u in store_uses} | set(self._dyn_registered)
        for key in [k for k in self._store.values if k not in keep]:
            self._store.remove_use(key)

    def _surface_active(self, name: str, active: bool) -> None:
        """The OS gave a surface of ours the keyboard focus (``active``), or took it away."""
        if active:
            self.focused = name
        elif self.focused == name:
            self.focused = None

    def _surface_gone(self, name: str) -> None:
        """A surface closed. When it had the keyboard focus, focus goes to the next surface in the
        shell's order, or to none when no other is left (Focus and Keyboard > Failure Modes). The
        compositor decides which layer surface has the keyboard; moving it there is the shortcut
        mode's (M6c, M6d), so this is the surface that mode will focus."""
        if self.focused != name:
            return
        open_names = {s.name for s in self.surfaces if s.window is not None}
        open_names |= {st.plan.frame.name for st in self.frames.states.values() if st.painter}
        self.focused = next_surface(
            [n for n in self.focus_order if n == name or n in open_names], name
        )
        logger.info(f"surface {name} had the keyboard focus and closed; next: {self.focused}")

    def _close(self, s: Surface) -> None:
        self.popups.parent_closed(s)
        s.generation += 1  # an animation that was running ends silent
        s.trace = None
        if s.timer is not None:
            s.timer.cancel()
            s.timer = None
        if s.window is not None:
            try:
                s.window.close()
            except Exception:  # tre already closed it (its output went away): nothing to do
                logger.debug(f"closing {s.name} on {s.output}: already gone", exc_info=True)

    def _update(self, s: Surface, p: Planned, all_uses: Mapping[str, Use]) -> None:
        live = self.new_live(all_uses)
        if s.hidden and s.window is None:  # the next show builds from the new definition
            s.live, s.expanded, s.name, s.planned, s.geometry = (
                live,
                p.expanded,
                p.bar.name,
                p,
                p.geometry,
            )
            logger.info(f"{_kind(p.bar)} {p.where} reloaded (hidden)")
            return
        try:
            nodes = live.resolve(p.expanded)
            stats = "built"
            if s.view is None:
                assert s.window is not None
                s.view = build(nodes, s.window, s.body)
                s.view.sink = self._dispatch
            else:
                stats = str(s.view.rebuild(nodes))
                self._watch_targets(s.view, p)
                self.popups.watch(s.view, p)
        except BindFailed as failed:
            _log_errors(failed.errors)
            logger.error(
                f"{_kind(p.bar)} {p.where} keeps what it shows: the new contents did not bind"
            )
            return
        s.live, s.expanded, s.name, s.planned = live, p.expanded, p.bar.name, p
        self._sync_body(s, p.bar, p.geometry, p.where)
        logger.info(f"{_kind(p.bar)} {p.where} reloaded: {stats}")

    @staticmethod
    def _output_size(s: Surface) -> tuple[int, int]:
        assert s.planned is not None
        return (s.planned.output.width, s.planned.output.height)

    def _sync_body(
        self, s: Surface, bar: BarDef | PanelDef, geometry: Geometry, where: str
    ) -> None:
        """Bring a kept surface's body (fill, shadows, margin) and its window geometry to what the
        Bar asks for; each is set only when it differs."""
        if s.window is None:
            return
        fill, shadows = _body_props(bar, self._look)
        extra = _body_extra(bar, self._look)
        if s.body is not None and (
            fill != s.fill
            or shadows != s.shadows
            or extra != (s.extra or {})
            or geometry.body_margin != s.geometry.body_margin
        ):
            props = _body_style(geometry, fill, shadows, extra)
            if fill is None and s.fill is not None:
                props["fill"] = (0, 0, 0, 0)  # tre cannot unset a fill: transparent is the default
            s.body.set(**props)
            s.fill, s.shadows, s.extra = fill, shadows, extra
        if geometry != s.geometry:
            try:
                s.window.set(
                    anchor=geometry.anchor,
                    size=geometry.size,
                    margin=geometry.margin,
                    exclusive_zone=geometry.exclusive_zone,
                    input_region=_input_for(bar, geometry, self._output_size(s), s.hidden),
                )
                s.geometry = geometry
                logger.info(
                    f"{_kind(bar)} {where}: size {geometry.size} zone {geometry.exclusive_zone}"
                )
            except ValueError as exc:
                logger.error(f"{_kind(bar)} {where}: {exc}; the geometry was not changed")

    # -- the desktop's look changed ------------------------------------------------------------

    def set_look(self, look: Look) -> None:
        """Loop thread: a new light or dark setting, accent or motion flag. Every token is read
        again, so each surface is rebuilt by the keyed diff, which changes only what differs, and
        a shadow that grew or shrank resizes its surface."""
        self._look = look
        self.frames.set_look(look)
        a = look.appearance
        logger.info(
            f"look: scheme {a.scheme}, accent {a.accent}, high contrast {a.high_contrast}, "
            f"reduced motion {a.reduced_motion}"
        )
        placed = {
            g: self._place_group(g, look)[0]
            for g in {x.planned.group for x in self.surfaces if x.planned}
        }
        for s in self.surfaces:
            p = s.planned
            if p is None or s.view is None:
                continue
            s.live.look = look
            self._rebuild(s)
            geometry = placed[p.group].get(p.bar.name)
            if geometry is not None:
                self._sync_body(s, p.bar, geometry, p.where)
