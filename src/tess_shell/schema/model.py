"""What the shell schema produces from a shell file: monitors, Bars and typed block trees."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tess_shell.binder.model import ForNode, IfNode, Node, Origin, UseNode, Value


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
    children: tuple[Node | UseNode | IfNode | ForNode, ...] = ()


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


PARAM_TYPES = ("string", "number", "boolean")


@dataclass(frozen=True, slots=True)
class ParamDecl:
    """A param a module accepts (Module File > Params): ``string``, ``number`` or ``boolean``."""

    name: str
    type: str
    default: Value | None
    origin: Origin


@dataclass(frozen=True, slots=True)
class ModuleDef:
    """A parsed ``<Name>_Module.tdl``: its call name, params and layout."""

    name: str
    file: str
    origin: Origin
    params: Mapping[str, ParamDecl]
    children: tuple[Node | UseNode | IfNode | ForNode, ...]
    style_file: str = ""  # the style file the layout names (the files it depends on)


@dataclass(frozen=True, slots=True)
class ClassDef:
    """``Classes { text_style { Kind: Text, ... } }``: values for the blocks of one type."""

    kind: str
    values: Mapping[str, Value]
    origin: Origin


@dataclass(frozen=True, slots=True)
class StyleDef:
    """A style file or a module's inline ``Style { }``: defaults per block type, and classes."""

    file: str
    defaults: Mapping[str, Mapping[str, Value]]
    classes: Mapping[str, ClassDef]
