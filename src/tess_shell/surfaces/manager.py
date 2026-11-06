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
from tess_shell.model.expand import Expanded, expand
from tess_shell.model.live import LiveTree
from tess_shell.model.look import Look, apply_rules, resolve_style
from tess_shell.model.store import Change, ValueStore
from tess_shell.model.uses import Use
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


def _resolve(
    monitors: Sequence[MonitorDef], outputs: Sequence[OutputLike]
) -> tuple[list[tuple[MonitorDef, list[int]]], list[tuple[MonitorDef, MonitorDef, int]]]:
    result: list[tuple[MonitorDef, list[int]]] = []
    conflicts: list[tuple[MonitorDef, MonitorDef, int]] = []
    taken: dict[int, MonitorDef] = {}
    defaults: list[MonitorDef] = []
    for monitor in monitors:
        has_selector = (
            monitor.connector is not None
            or monitor.description is not None
            or isinstance(monitor.index, int)
        )
        if monitor.index == "default" and not has_selector:
            defaults.append(monitor)
            continue
        if not has_selector and monitor.index is None:
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


def _keyboard(bar: BarDef | PanelDef, hidden: bool = False) -> str:
    """tre's ``keyboard`` word: a Panel's ``Keyboard``, ``none`` for a Bar or a hidden Panel."""
    if hidden or not isinstance(bar, PanelDef):
        return "none"
    return bar.keyboard.lower()


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
            hint = f"did you mean {', '.join(close)}?" if close else "write the Name of a Panel"
            expanded.errors.append(
                BindError(f"{h.action}: no Panel named {target}", h.origin, hint)
            )


def _nothing() -> None:
    return None


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
    ) -> None:
        self._app = app
        self._positions = positions  # where the user left each Movable Panel (the registry)
        self._shell_name = ""
        self.hide_mode = hide_mode  # KEEP (the default) or CLOSE (D44)
        self._depth = 0  # how deep Panel event handlers have called one another
        self.sink = sink
        self._look = look
        self._modules = modules
        self._uid_of = uid_of
        self._store = store
        self.surfaces: list[Surface] = []
        self._planned: list[Planned] = []
        self._handle: Any = None
        self._all_uses: Mapping[str, Use] = {}
        from tess_shell.surfaces.popup import PopupPlan, Popups  # popup.py imports this module

        self.popups = Popups(self)
        self._popup_plans: list[PopupPlan] = []  # from the last planning: set_plans commits them

    def wake(self) -> None:
        """Wake tre's loop after the shell changed a window. tre does not request a frame for a
        window whose node was changed during a callback of another window (a click on the Bar
        changing a Panel; a theme change touching every window): the change waits for the next
        wake, and a Panel could stay stale for as long as that takes. A queued no-op is a wake
        (measured on tre 0.6.1, ``tests/kwin/probe_hide.py``)."""
        handle = getattr(self, "_handle", None)
        if handle is None:
            thread_handle = getattr(self._app, "thread_handle", None)
            if thread_handle is None:  # a stub app in a test
                return
            handle = self._handle = thread_handle()
        handle.call_soon(_nothing)

    def _dispatch(self, handler: Handler, key: str, raw: Any) -> None:
        logger.debug(f"{key} -> {handler.action} {dict(handler.args)} ({handler.origin})")
        if self.sink is not None:
            self.sink(handler, key, raw)

    @property
    def look(self) -> Look:
        assert self._look is not None, "the manager was made without a look"
        return self._look

    # -- planning: no side effect but logging -------------------------------------------------

    def _plan_bars(
        self, shell: ShellDef, modules: Mapping[str, ModuleDef], look: Look | None
    ) -> tuple[list[Planned], list[Use]]:
        """Match monitors to outputs, compute each Bar's geometry and expand its module calls.
        The stylesheet's rules are folded into every block first, so ``#name`` selectors see the
        names as written."""
        self._shell_name = shell.name
        rules = look.rules if look else ()
        if rules:
            modules = {
                n: dataclasses.replace(d, children=apply_rules(d.children, rules))
                for n, d in modules.items()
            }
        outputs: list[Output] = list(self._app.outputs())
        if not outputs:
            logger.warning("no outputs: no surface was opened")
            self._popup_plans = []
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
                    suffix = f"@{outputs[i].name}" if len(indices) > 1 else ""
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
                        bool(monitor.popups),
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
        for p in planned:
            _check_targets(p.expanded, panel_names)
        self._popup_plans, popup_uses = self.popups.plan(
            shell, modules, look, outputs, self._uid_of, assign, panel_names
        )
        uses.extend(popup_uses)
        return planned, uses

    def plan(self, shell: ShellDef) -> list[Use]:
        planned, uses = self._plan_bars(shell, self._modules, self._look)
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
        self._all_uses = all_uses
        for planned in self._planned:
            self.surfaces.append(self._open(planned, all_uses))
        return self.surfaces

    def _make_window(self, planned: Planned, live: LiveTree, hidden: bool = False) -> Surface:
        """Create the window of a Bar or a Panel and bind its tree. The window is not added to the
        app yet; the caller does that (at start, or when a hidden Panel is shown)."""
        from tess_re import LayerWindow

        bar, output, geometry, where = planned.bar, planned.output, planned.geometry, planned.where
        kind = _kind(bar)
        window = LayerWindow(
            f"tesserae-shell.{kind.lower()}.{bar.name}",
            layer=bar.layer.lower(),  # type: ignore[arg-type]
            anchor=geometry.anchor,
            size=geometry.size,
            margin=geometry.margin,
            exclusive_zone=geometry.exclusive_zone,
            exclusive_edge=geometry.exclusive_edge,  # type: ignore[arg-type]
            keyboard=_keyboard(bar, hidden),  # type: ignore[arg-type]
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
        window.on(
            "closed",
            lambda e, n=where: logger.info(f"{kind} {n} closed ({getattr(e, 'reason', '')})"),
        )

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
        live = LiveTree(self._store, all_uses, look=self._look)
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
    # tre 0.6.1 cannot unmap a layer surface. KEEP (the default) leaves it mapped and drawing
    # nothing. That needed ``wake()``: a node changed in one window during a callback of another
    # was not drawn until something else woke tre's loop, so a shown Panel stayed empty and a
    # hidden one stayed on screen (TRE-REQ-012). CLOSE avoids it by making a new window on show;
    # what a module knows lives in the module.

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
        inset = {"left": left + b_left, "top": top + b_top, "right": right + b_right,
                 "bottom": bottom + b_bottom}
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

    def _saved(
        self, group: str, bars: Sequence[BarDef | PanelDef]
    ) -> dict[str, dict[str, float]]:
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
            self.wake()  # this runs in the Bar's callback: tre draws another window only when woken

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
            self.wake()
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
            s.window.root.set(visible=True)
            s.window.set(
                input_region=_input_for(bar, s.geometry, self._output_size(s)),
                keyboard=_keyboard(bar),
            )
            self._arm_hide_after(s)
            self._trace(s, "shown")
            logger.info(f"Panel {s.planned.where} shown (surface kept)")
            self._enter(s)
            self.wake()
            return
        fresh = self._make_window(s.planned, LiveTree(self._store, self._all_uses, look=self._look))
        assert fresh.window is not None
        s.window, s.view, s.body = fresh.window, fresh.view, fresh.body
        s.live, s.fill, s.shadows, s.extra = fresh.live, fresh.fill, fresh.shadows, fresh.extra
        s.expanded, s.geometry, s.hidden = s.planned.expanded, s.planned.geometry, False
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
        self.wake()  # tre draws this window's animation only once its loop is awake (TRE-REQ-012)

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

    def run_builtin(self, handler: Handler) -> None:
        """A shell action (``Show``, ``Hide``, ``Toggle``) on the Panel it names."""
        if handler.action == "Close":  # a Popup's own blocks close it (Popups); this one is not
            logger.warning(f"{handler.origin}: Close: the block is not in a Popup; nothing closed")
            return
        target = handler.args.get("Target")
        hits = [
            s
            for s in self.surfaces
            if s.name == target and s.planned and _kind(s.planned.bar) == "Panel"
        ]
        if not hits:
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
        for surface in self.surfaces:
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
        self.wake()

    def check(
        self, shell: ShellDef, modules: Mapping[str, ModuleDef], look: Look | None = None
    ) -> tuple[list[Planned], list[Use]] | None:
        """Plan ``shell`` for a reload without changing anything. ``None`` when a Bar's tree has
        an error that would leave it empty: the running state is kept."""
        planned, uses = self._plan_bars(shell, modules, look or self._look)
        failed = [p for p in planned if p.expanded.errors]
        failed.extend(p for p in self._popup_plans if p.expanded.errors)  # type: ignore[misc]
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
        if look is not None:
            self._look = look
        self.popups.set_plans(self._popup_plans)  # the plans of the check just made
        all_uses = {u.key: u for p in planned for u in p.expanded.uses}
        all_uses.update(self.popups.uses())
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
        keep = {u.key for u in store_uses}
        for key in [k for k in self._store.values if k not in keep]:
            self._store.remove_use(key)
        self.wake()

    def _close(self, s: Surface) -> None:
        self.popups.parent_closed(s)
        if s.timer is not None:
            s.timer.cancel()
            s.timer = None
        if s.window is not None:
            s.window.close()

    def _update(self, s: Surface, p: Planned, all_uses: Mapping[str, Use]) -> None:
        live = LiveTree(self._store, all_uses, look=self._look)
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
        self.wake()
