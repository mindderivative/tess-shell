"""What the shell schema produces from a shell file: monitors, Bars and typed block trees."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

import tess_dl

from tess_shell.binder.model import (
    ForNode,
    Handler,
    IfNode,
    Node,
    Origin,
    Shadows,
    UseNode,
    Value,
)


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
class PeekDef:
    """A ``Peek { Size, Enter_Delay, Exit_Delay }`` (Frame > Strip: Expand, Contract, Peek): a
    melded Panel or a strip that rests as a sliver and comes out when the pointer stays on it.
    ``size`` is the pixels that show at rest, the delays are milliseconds."""

    size: float = 24
    enter_delay: float = 150
    exit_delay: float = 300
    origin: Origin | None = None
    trigger: str = "HOVER"  # HOVER, CLICK or DRAG: what opens it
    handle: str = "AUTO"  # AUTO, NONE, DOTS, BAR or CHEVRON: the icon on the tab
    slide_from: str | None = None  # a corner Panel only: TOP, RIGHT, BOTTOM or LEFT; None is Attach


@dataclass(frozen=True, slots=True)
class PanelDef:
    """A ``Panel { }`` (Panel > Configuration): placed by ``Layer``, ``Anchor``, ``Inset``,
    ``Width`` and ``Height``. It has the fields of :class:`BarDef` the surface manager reads
    (``name``, ``origin``, ``layer``, ``style``, ``children``) plus its own."""

    name: str
    origin: Origin
    layer: str = "TOP"
    anchor: tuple[str, ...] = ()  # TOP, BOTTOM, LEFT, RIGHT; empty is floating (centred)
    inset: tuple[float, float, float, float] = (0, 0, 0, 0)  # left, top, right, bottom
    width: Value = None  # type: ignore[assignment]
    height: Value = None  # type: ignore[assignment]
    keyboard: str = "NONE"
    input: str = "WHOLE"  # WHOLE, NONE or AUTO (Input_Region)
    visible: bool = True
    hide_after: float | None = None  # milliseconds
    style: Mapping[str, Value] = None  # type: ignore[assignment]
    children: tuple[Node | UseNode | IfNode | ForNode, ...] = ()
    # attached to a target by name (Panel > Attachment Geometry); Anchor and Inset then give way
    attach_to: str | None = None
    meld: bool = False  # drawn inside the Frame it is attached to (hosted melding)
    depth: Value = None  # type: ignore[assignment]  # melded: the extent away from the Frame's edge
    length: Value = None  # type: ignore[assignment]  # melded: the extent along the Frame's edge
    attach: str | None = None  # LEFT, RIGHT, TOP, BOTTOM: the target's edge the Panel meets
    gap: float = 0  # pixels between the Panel and the target
    alignment: str = "CENTER"  # START, CENTER, END along the shared edge
    movable: bool = False  # the pointer can move it; the position is saved (Panel > Position)
    animation: str = "NONE"  # SLIDE, FADE or NONE: how it appears and disappears
    peek: PeekDef | None = None  # melded only: rests as a tab of ``Size`` pixels (see PeekDef)
    duration: float = 200  # milliseconds of the animation
    handlers: Mapping[str, Handler] = field(default_factory=dict)  # ``On_Open`` -> handler


@dataclass(frozen=True, slots=True)
class PopupDef:
    """A ``Popup { }`` (Popup > Configuration), or the inline popup of a ``Tooltip { }``
    (``name`` empty). ``Tooltip: true`` has already set the defaults it implies: the schema
    stores what each key means after that."""

    name: str
    origin: Origin
    attach: str = "BOTTOM"  # the anchor's edge the popup meets: TOP, BOTTOM, LEFT, RIGHT
    alignment: str = "START"  # START, CENTER, END along that edge
    gap: float = 0  # pixels between the anchor and the popup's body
    adjust: tuple[str, ...] = ("flip_y", "slide_x")  # tre's constraint adjustments
    width: Value = None  # type: ignore[assignment]  # a Length or Auto
    height: Value = None  # type: ignore[assignment]
    max_width: float = 300
    max_height: float = 400
    focus: bool = True  # tre's grab: the popup takes the keyboard and pointer
    tooltip: bool = False
    open_on_enter: bool = False
    enter_delay: float = 500  # milliseconds
    close_on_exit: bool = False
    exit_delay: float = 200
    style: Mapping[str, Value] = None  # type: ignore[assignment]
    children: tuple[Node | UseNode | IfNode | ForNode, ...] = ()


@dataclass(frozen=True, slots=True)
class FrameBorder:
    """An ``Inner_Border { Width, Color }`` or ``Outer_Border``. ``color`` is a colour or a token
    reference (resolved with the look); ``None`` takes the Frame's background."""

    width: float
    color: Value | None = None


@dataclass(frozen=True, slots=True)
class EdgeDef:
    """One entry of a Frame's ``Edges { }``: a side with its own ``Thickness`` (``None`` keeps
    the Frame's) and, when ``children`` is not empty, a strip that holds them. ``padding`` is the
    strip's (``None`` takes the Frame's)."""

    side: str  # left, top, right, bottom
    origin: Origin
    thickness: float | None = None
    padding: tuple[float, float, float, float] | None = None
    children: tuple[Node | UseNode | IfNode | ForNode, ...] = ()
    name: str | None = None  # the target of Show, Hide and Toggle (a strip with ``Peek`` only)
    peek: PeekDef | None = None  # the strip rests as a ``Size`` sliver; ``thickness`` is its full


@dataclass(frozen=True, slots=True)
class FrameDef:
    """A ``Frame { }`` (Frame > Configuration): a ring around the output. Lengths are logical
    pixels; sides are left, top, right, bottom and corners top-left, top-right, bottom-right,
    bottom-left. ``style`` holds the inline ``Style`` (``Background``, ``Opacity``)."""

    name: str
    origin: Origin
    thickness: tuple[float, float, float, float]
    margin: tuple[float, float, float, float] = (0, 0, 0, 0)
    outer_radius: tuple[float, float, float, float] = (0, 0, 0, 0)  # ``Corner_Radius``
    inner_radius: tuple[float, float, float, float] = (0, 0, 0, 0)
    inner_border: FrameBorder | None = None
    outer_border: FrameBorder | None = None
    visible: bool = True
    style: Mapping[str, Value] = None  # type: ignore[assignment]
    keyboard: str = "NONE"  # the painter's keyboard mode: NONE or ON_DEMAND
    padding: tuple[float, float, float, float] = (0, 0, 0, 0)  # of every strip (left, top, ...)
    edges: Mapping[str, EdgeDef] = field(default_factory=dict)  # ``left``, ``top``, ... -> strip
    melds: tuple[PanelDef, ...] = ()  # Panels with ``Meld: true`` attached to this Frame


@dataclass(frozen=True, slots=True)
class MonitorDef:
    name: str
    origin: Origin
    index: int | str | None  # a position, "default", or None
    connector: str | None
    description: str | None
    surfaces: tuple[BarDef | PanelDef, ...] = ()
    popups: tuple[PopupDef, ...] = ()
    frames: tuple[FrameDef, ...] = ()  # at most one


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


@dataclass(frozen=True, slots=True)
class Token:
    """One theme token: the written value (read by the key that refers to it) or, for
    ``Elevation.Max``, the shadow list."""

    value: tess_dl.Value | Shadows
    origin: Origin


MODES = ("light", "dark", "high_contrast", "reduced_motion")


@dataclass(frozen=True, slots=True)
class ThemeDef:
    """A ``<Name>_Theme.tdl``: tokens by lower-case dotted path (``color.on_surface``,
    ``type.body.font_size``), and the modes that override some of them."""

    name: str
    file: str
    tokens: Mapping[str, Token]
    modes: Mapping[str, Mapping[str, Token]]


@dataclass(frozen=True, slots=True)
class Rule:
    """One ``Rule { Selector: "...", <style values> }`` of a stylesheet."""

    kind: Literal["type", "module", "class", "name"]
    target: str  # the block word, the module's call name, the class name or the unique ``Name``
    values: Mapping[str, Value]
    origin: Origin
    state: str = ""  # ``hovered`` or ``pressed`` for ``"Button:hovered"``; empty for a base rule

    @property
    def specificity(self) -> int:
        return {"type": 1, "module": 5, "class": 10, "name": 100}[self.kind]


@dataclass(frozen=True, slots=True)
class StylesheetDef:
    name: str
    file: str
    rules: tuple[Rule, ...]


class IconSource(Protocol):
    """Where an icon name becomes an SVG document (``files.icons.IconSets``)."""

    def lookup(self, name: str) -> str | None: ...

    def nearest(self, name: str) -> list[str]: ...


def use_names(children: Sequence[Any]) -> list[str]:
    """The ``Name`` of every module use among ``children``, at any depth."""
    found: list[str] = []
    for child in children:
        if isinstance(child, UseNode) and child.name:
            found.append(child.name)
        found.extend(use_names(getattr(child, "children", ()) or ()))
        found.extend(use_names(getattr(child, "body", ()) or ()))
        found.extend(use_names(getattr(child, "else_body", ()) or ()))
    return found
