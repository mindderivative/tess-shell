"""Open the shell's surfaces: match each ``Monitor`` to outputs, create one ``LayerWindow`` per
Bar, bind its children and add it to the app (Shell Start and Stop, start steps 10 and 11).

A bind error leaves that Bar empty and logs every error; other Bars still open. A Bar whose size
resolves to 0 is not created (D46). Closing is the engine's job: stopping the loop closes every
window.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from loguru import logger

from tess_shell.binder import convert
from tess_shell.binder.build import View, build
from tess_shell.binder.model import BindError, BindFailed, Color, Value
from tess_shell.model.expand import Expanded, expand
from tess_shell.model.live import LiveTree
from tess_shell.model.store import Change, ValueStore
from tess_shell.model.uses import Use
from tess_shell.schema.model import BarDef, ModuleDef, MonitorDef, ShellDef
from tess_shell.surfaces.bar import BarSpec, Geometry, ZeroSize, bar_geometry

if TYPE_CHECKING:
    from tess_re import App, LayerWindow, Output


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
    window: LayerWindow
    view: View | None
    live: LiveTree
    expanded: Expanded
    geometry: Geometry
    fill: tuple[int, int, int, int] | None = None


def _bar_fill(style: dict[str, Value] | None) -> tuple[int, int, int, int] | None:
    if not style:
        return None
    value = style.get("Fill") or style.get("Background")
    if isinstance(value, Color):
        return convert.color(value, ("fill",))["fill"]  # type: ignore[no-any-return]
    return None


def _spec(bar: BarDef) -> BarSpec:
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
    )


@dataclass(slots=True)
class Planned:
    key: str
    bar: BarDef
    output: Output
    expanded: Expanded
    geometry: Geometry
    where: str


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
    ) -> None:
        self._app = app
        self._modules = modules
        self._uid_of = uid_of
        self._store = store
        self.surfaces: list[Surface] = []
        self._planned: list[Planned] = []

    # -- planning: no side effect but logging -------------------------------------------------

    def _plan_bars(
        self, shell: ShellDef, modules: Mapping[str, ModuleDef]
    ) -> tuple[list[Planned], list[Use]]:
        """Match monitors to outputs, compute each Bar's geometry and expand its module calls."""
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
                    try:
                        geometry = bar_geometry(_spec(bar), (outputs[i].width, outputs[i].height))
                    except ZeroSize as exc:
                        logger.warning(f"{bar.origin}: Bar {where} is not created: {exc}")
                        continue
                    for warning in geometry.warnings:
                        logger.warning(f"{bar.origin}: Bar {where}: {warning}")
                    suffix = f"@{outputs[i].name}" if len(indices) > 1 else ""
                    path = f"{shell.name}.{monitor.name}{suffix}.{bar.name}"
                    expanded = expand(bar.children, path, modules, self._uid_of, outputs[i].name)
                    uses.extend(expanded.uses)
                    planned.append(Planned(path, bar, outputs[i], expanded, geometry, where))
        return planned, uses

    def plan(self, shell: ShellDef) -> list[Use]:
        planned, uses = self._plan_bars(shell, self._modules)
        for use in uses:
            self._store.add_use(use.module, use.key)
        self._planned = planned
        return uses

    # -- opening ------------------------------------------------------------------------------

    def build(self) -> list[Surface]:
        """Evaluate the slots with the values the modules have sent so far, bind, and open."""
        all_uses = {u.key: u for p in self._planned for u in p.expanded.uses}
        for planned in self._planned:
            self.surfaces.append(self._open(planned, all_uses))
        return self.surfaces

    def _open(self, planned: Planned, all_uses: Mapping[str, Use]) -> Surface:
        from tess_re import LayerWindow

        bar, output, geometry, where = planned.bar, planned.output, planned.geometry, planned.where
        window = LayerWindow(
            f"tesserae-shell.bar.{bar.name}",
            layer=bar.layer.lower(),  # type: ignore[arg-type]
            anchor=geometry.anchor,
            size=geometry.size,
            margin=geometry.margin,
            exclusive_zone=geometry.exclusive_zone,
            exclusive_edge=geometry.exclusive_edge,  # type: ignore[arg-type]
            output=output,
        )
        fill = _bar_fill(dict(bar.style) if bar.style else None)
        if fill is not None:
            window.root.set(fill=fill)
        window.on(
            "configure",
            lambda e, n=where: logger.info(f"Bar {n} configured {int(e.width)}x{int(e.height)}"),
        )
        window.on(
            "closed",
            lambda e, n=where: logger.info(f"Bar {n} closed ({getattr(e, 'reason', '')})"),
        )
        live = LiveTree(self._store, all_uses)
        view: View | None = None
        errors = list(planned.expanded.errors)
        if not errors:
            try:
                view = build(live.resolve(planned.expanded), window)
            except BindFailed as failed:
                errors = failed.errors
        _log_errors(errors)
        if view is None:
            logger.error(f"Bar {where} is empty: its contents did not bind")
        self._app.add_window(window)
        logger.info(
            f"Bar {where}: anchor {','.join(geometry.anchor)} size {geometry.size} "
            f"zone {geometry.exclusive_zone}"
        )
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
        )

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

    def check(
        self, shell: ShellDef, modules: Mapping[str, ModuleDef]
    ) -> tuple[list[Planned], list[Use]] | None:
        """Plan ``shell`` for a reload without changing anything. ``None`` when a Bar's tree has
        an error that would leave it empty: the running state is kept."""
        planned, uses = self._plan_bars(shell, modules)
        failed = [p for p in planned if p.expanded.errors]
        for p in failed:
            _log_errors(p.expanded.errors)
        if failed:
            return None
        return planned, uses

    def apply(
        self, planned: list[Planned], modules: Mapping[str, ModuleDef], store_uses: Sequence[Use]
    ) -> None:
        """Make the running surfaces match ``planned`` (from :meth:`check`): a surface whose key,
        output, layer and exclusive edge are unchanged is kept, its tree rebuilt by the keyed diff
        and its geometry set live; the rest are closed or opened. All-or-nothing per surface: a
        tree that does not bind leaves that surface as it was."""
        self._modules = modules
        all_uses = {u.key: u for p in planned for u in p.expanded.uses}
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
                s.window.close()
            out.append(self._open(p, all_uses))
        for s in old.values():
            s.window.close()
        self.surfaces = out
        keep = {u.key for u in store_uses}
        for key in [k for k in self._store.values if k not in keep]:
            self._store.remove_use(key)

    def _update(self, s: Surface, p: Planned, all_uses: Mapping[str, Use]) -> None:
        live = LiveTree(self._store, all_uses)
        try:
            nodes = live.resolve(p.expanded)
            stats = "built"
            if s.view is None:
                s.view = build(nodes, s.window)
            else:
                stats = str(s.view.rebuild(nodes))
        except BindFailed as failed:
            _log_errors(failed.errors)
            logger.error(f"Bar {p.where} keeps what it shows: the new contents did not bind")
            return
        s.live, s.expanded, s.name = live, p.expanded, p.bar.name
        fill = _bar_fill(dict(p.bar.style) if p.bar.style else None)
        if fill is not None and fill != s.fill:
            s.window.root.set(fill=fill)
            s.fill = fill
        if p.geometry != s.geometry:
            try:
                s.window.set(
                    anchor=p.geometry.anchor,
                    size=p.geometry.size,
                    margin=p.geometry.margin,
                    exclusive_zone=p.geometry.exclusive_zone,
                )
                s.geometry = p.geometry
                logger.info(
                    f"Bar {p.where}: size {p.geometry.size} zone {p.geometry.exclusive_zone}"
                )
            except ValueError as exc:
                logger.error(f"Bar {p.where}: {exc}; the geometry was not changed")
        logger.info(f"Bar {p.where} reloaded: {stats}")
