"""Open the shell's surfaces: match each ``Monitor`` to outputs, create one ``LayerWindow`` per
Bar, bind its children and add it to the app (Shell Start and Stop, start steps 10 and 11).

A bind error leaves that Bar empty and logs every error; other Bars still open. A Bar whose size
resolves to 0 is not created (D46). Closing is the engine's job: stopping the loop closes every
window.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from loguru import logger

from tess_shell.binder import convert
from tess_shell.binder.build import View, build
from tess_shell.binder.model import BindFailed, Color, Value
from tess_shell.schema.model import BarDef, MonitorDef, ShellDef
from tess_shell.surfaces.bar import BarSpec, ZeroSize, bar_geometry

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


def assign(
    monitors: Sequence[MonitorDef], outputs: Sequence[OutputLike]
) -> list[tuple[MonitorDef, list[int]]]:
    """Which outputs each monitor block applies to (indices into ``outputs``).

    A block with a selector takes the output it names; a block that names an output another block
    already took is skipped (the first wins). ``Index: default`` takes every output no other block
    named. A block with no selector is ignored; a block that matches nothing gets an empty list.
    """
    result: list[tuple[MonitorDef, list[int]]] = []
    taken: set[int] = set()
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
        if found is None or found in taken:
            result.append((monitor, []))
            continue
        taken.add(found)
        result.append((monitor, [found]))
    free = [i for i in range(len(outputs)) if i not in taken]
    result.extend((monitor, list(free)) for monitor in defaults)
    return result


@dataclass(slots=True)
class Surface:
    name: str
    output: str
    window: LayerWindow
    view: View | None


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


class SurfaceManager:
    def __init__(self, app: App) -> None:
        self._app = app
        self.surfaces: list[Surface] = []

    def open_shell(self, shell: ShellDef) -> list[Surface]:
        outputs: list[Output] = list(self._app.outputs())
        if not outputs:
            logger.warning("no outputs: no surface was opened")
            return []
        for monitor, indices in assign(shell.monitors, outputs):
            if not indices:
                logger.info(
                    f"monitor {monitor.name} matches no output; its surfaces are not opened"
                )
                continue
            for i in indices:
                for bar in monitor.surfaces:
                    self._open_bar(bar, outputs[i], monitor)
        return self.surfaces

    def _open_bar(self, bar: BarDef, output: Output, monitor: MonitorDef) -> None:
        from tess_re import LayerWindow

        where = f"{bar.name} on {output.name}"
        try:
            geometry = bar_geometry(_spec(bar), (output.width, output.height))
        except ZeroSize as exc:
            logger.warning(f"{bar.origin}: Bar {where} is not created: {exc}")
            return
        for warning in geometry.warnings:
            logger.warning(f"{bar.origin}: Bar {where}: {warning}")
        layer = bar.layer.lower()
        window = LayerWindow(
            f"tesserae-shell.bar.{bar.name}",
            layer=layer,  # type: ignore[arg-type]
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
            "closed", lambda e, n=where: logger.info(f"Bar {n} closed ({getattr(e, 'reason', '')})")
        )
        view: View | None = None
        try:
            view = build(list(bar.children), window)
        except BindFailed as failed:
            for error in failed.errors:
                logger.error(
                    f"{error.origin}: {error.message}" + (f" ({error.hint})" if error.hint else "")
                )
            logger.error(f"Bar {where} is empty: its contents did not bind")
        self._app.add_window(window)
        self.surfaces.append(Surface(bar.name, output.name, window, view))
        logger.info(
            f"Bar {where}: anchor {','.join(geometry.anchor)} size {geometry.size} "
            f"zone {geometry.exclusive_zone}"
        )
