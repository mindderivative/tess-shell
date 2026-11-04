"""What the shell schema produces from a shell file: monitors, Bars and typed block trees."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tess_shell.binder.model import Node, Origin, Value


@dataclass(frozen=True, slots=True)
class BarDef:
    name: str
    origin: Origin
    edge: str  # TOP, BOTTOM, LEFT, RIGHT
    width: Value
    height: Value
    layer: str = "TOP"
    alignment: str | None = None
    offset: float | None = None
    gap: float = 0
    reserve: bool = True
    min_width: float | None = None
    min_height: float | None = None
    max_width: float | None = None
    max_height: float | None = None
    style: Mapping[str, Value] = None  # type: ignore[assignment]
    children: tuple[Node, ...] = ()


@dataclass(frozen=True, slots=True)
class MonitorDef:
    name: str
    origin: Origin
    index: int | str | None  # a position, "default", or None
    connector: str | None
    description: str | None
    surfaces: tuple[BarDef, ...] = ()


@dataclass(frozen=True, slots=True)
class ShellDef:
    file: str
    name: str
    monitors: tuple[MonitorDef, ...]
