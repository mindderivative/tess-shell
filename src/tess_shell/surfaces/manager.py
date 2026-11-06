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
from tess_shell.schema.model import BarDef, ModuleDef, MonitorDef, PanelDef, ShellDef
from tess_shell.surfaces.bar import BarSpec, Geometry, ZeroSize, bar_geometry, input_region
from tess_shell.surfaces.panel import PanelSpec, panel_geometry

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
        panel.anchor, panel.inset, panel.width, panel.height, bleed=_bleed(panel, look)
    )


def _geometry(bar: BarDef | PanelDef, look: Look | None, output: tuple[int, int]) -> Geometry:
    """The geometry of a Bar or a Panel on ``output``; raises :class:`ZeroSize`."""
    if isinstance(bar, PanelDef):
        return panel_geometry(_panel_spec(bar, look), output)
    return bar_geometry(_spec(bar, look), output)


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


@dataclass(slots=True)
class Planned:
    key: str
    bar: BarDef | PanelDef
    output: Output
    expanded: Expanded
    geometry: Geometry
    where: str


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
        if h.builtin and target not in panels:
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
    ) -> None:
        self._app = app
        self.hide_mode = hide_mode  # KEEP (the default) or CLOSE (D44)
        self.sink = sink
        self._look = look
        self._modules = modules
        self._uid_of = uid_of
        self._store = store
        self.surfaces: list[Surface] = []
        self._planned: list[Planned] = []
        self._handle: Any = None
        self._all_uses: Mapping[str, Use] = {}

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
        rules = look.rules if look else ()
        if rules:
            modules = {
                n: dataclasses.replace(d, children=apply_rules(d.children, rules))
                for n, d in modules.items()
            }
        outputs: list[Output] = list(self._app.outputs())
        if not outputs:
            logger.warning("no outputs: no surface was opened")
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
                for bar in monitor.surfaces:
                    where = f"{bar.name} on {outputs[i].name}"
                    kind = _kind(bar)
                    try:
                        geometry = _geometry(bar, look, (outputs[i].width, outputs[i].height))
                    except ZeroSize as exc:
                        logger.warning(f"{bar.origin}: {kind} {where} is not created: {exc}")
                        continue
                    for warning in geometry.warnings:
                        logger.warning(f"{bar.origin}: {kind} {where}: {warning}")
                    suffix = f"@{outputs[i].name}" if len(indices) > 1 else ""
                    path = f"{shell.name}.{monitor.name}{suffix}.{bar.name}"
                    children = apply_rules(bar.children, rules)
                    expanded = expand(children, path, modules, self._uid_of, outputs[i].name, rules)
                    uses.extend(expanded.uses)
                    planned.append(Planned(path, bar, outputs[i], expanded, geometry, where))
        panel_names = {
            surface.name
            for m in shell.monitors
            for surface in m.surfaces
            if _kind(surface) == "Panel"
        }
        for p in planned:
            _check_targets(p.expanded, panel_names)
        return planned, uses

    def plan(self, shell: ShellDef) -> list[Use]:
        planned, uses = self._plan_bars(shell, self._modules, self._look)
        for use in uses:
            self._store.add_use(use.module, use.key)
        self._planned = planned
        return uses

    # -- opening ------------------------------------------------------------------------------

    def build(self) -> list[Surface]:
        """Evaluate the slots with the values the modules have sent so far, bind, and open."""
        all_uses = {u.key: u for p in self._planned for u in p.expanded.uses}
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
        body = window.create(
            "box",
            flex_grow=1,
            align_self="stretch",
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
        for pointer in ("pointer_down", "pointer_up"):  # a trace: where a click's time goes
            window.root.on(
                pointer,
                lambda e, n=where, k=kind, p=pointer: logger.debug(
                    f"{k} {n} {p} at {getattr(e, 'window_x', None)},{getattr(e, 'window_y', None)}"
                ),
            )
        view: View | None = None
        errors = list(planned.expanded.errors)
        if not errors:
            try:
                view = build(live.resolve(planned.expanded), window, body)
                view.sink = self._dispatch
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

    def hide(self, s: Surface) -> None:
        """Hide a Panel. KEEP (the default, D44): keep the surface, draw nothing, take no pointer
        and no keyboard; the tree and its state stay. CLOSE: destroy the window (the record, its
        place and what its modules know stay) and make a new one on show."""
        if s.hidden or s.planned is None or s.window is None:
            return
        if s.timer is not None:
            s.timer.cancel()
            s.timer = None
        window = s.window
        s.hidden = True
        if self.hide_mode == "KEEP":
            window.root.set(visible=False)
            window.set(input_region=[], keyboard="none")
            self._trace(s, "hidden")
            logger.info(f"Panel {s.planned.where} hidden (surface kept)")
            self.wake()
            return
        s.window, s.view, s.body = None, None, None
        window.close()
        logger.info(f"Panel {s.planned.where} hidden (window closed)")

    def show(self, s: Surface) -> None:
        if s.planned is None:
            return
        if not s.hidden:
            self._arm_hide_after(s)  # shown again: the timer starts over
            return
        if s.window is not None:  # KEEP: the surface is still there
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

    def run_builtin(self, handler: Handler) -> None:
        """A shell action (``Show``, ``Hide``, ``Toggle``) on the Panel it names."""
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
                (self.hide if not s.hidden else self.show)(s)

    # -- changes ------------------------------------------------------------------------------

    def _rebuild(self, surface: Surface) -> None:
        """A use with an If or For read something that changed: resolve the Bar's tree again and
        let the keyed diff change only what differs."""
        assert surface.view is not None
        try:
            stats = surface.view.rebuild(surface.live.resolve(surface.expanded))
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
        self.wake()

    def check(
        self, shell: ShellDef, modules: Mapping[str, ModuleDef], look: Look | None = None
    ) -> tuple[list[Planned], list[Use]] | None:
        """Plan ``shell`` for a reload without changing anything. ``None`` when a Bar's tree has
        an error that would leave it empty: the running state is kept."""
        planned, uses = self._plan_bars(shell, modules, look or self._look)
        failed = [p for p in planned if p.expanded.errors]
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
        all_uses = {u.key: u for p in planned for u in p.expanded.uses}
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

    @staticmethod
    def _close(s: Surface) -> None:
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
        for s in self.surfaces:
            p = s.planned
            if p is None or s.view is None:
                continue
            s.live.look = look
            self._rebuild(s)
            geometry = _geometry(p.bar, look, (p.output.width, p.output.height))
            self._sync_body(s, p.bar, geometry, p.where)
        self.wake()
