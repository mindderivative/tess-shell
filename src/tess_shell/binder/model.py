"""The typed tree: what the schema produces and the binder consumes.

Every value carries the :class:`Origin` of its **key** in the TDL file, the position reported
when the value is wrong. An origin never takes part in equality, so a tree read from a file
equals the same tree built in code.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class Origin:
    file: str
    line: int
    column: int

    def __str__(self) -> str:
        return f"{self.file}:{self.line}:{self.column}"


NO_ORIGIN = Origin("<code>", 1, 1)


def _origin() -> Origin:
    return field(default=NO_ORIGIN, compare=False, kw_only=True)


@dataclass(frozen=True, slots=True)
class Length:
    """Logical pixels."""

    px: float
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class Percent:
    value: float
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class Auto:
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class Expand:
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class Color:
    """Each channel 0 to 255."""

    r: int
    g: int
    b: int
    a: int = 255
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class Enum:
    """An upper-case TDL enum word, such as ``SPACE_BETWEEN``."""

    name: str
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class Bool:
    value: bool
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class Number:
    value: int | float
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class Text:
    value: str
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class Sides:
    """Padding or margin in the TDL order: left, top, right, bottom."""

    left: float
    top: float
    right: float
    bottom: float
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class Seq:
    items: tuple[Value, ...]
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class Shadow:
    """One drop shadow (CSS ``box-shadow`` model): a colour, an offset, a blur and a spread."""

    color: Color
    x: float = 0
    y: float = 0
    blur: float = 0
    spread: float = 0
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class Shadows:
    """Shadows, first on top. An empty list is no shadow."""

    items: tuple[Shadow, ...]
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class TokenRef:
    """``$color.surface``: a theme token, resolved by the model before binding (Style Schema >
    Theme Tokens). ``path`` is lower case; ``kind`` is the key's value kind, so the token's written
    value is read the way the key reads it."""

    path: str
    kind: str
    choices: tuple[str, ...] = ()
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class SlotPart:
    """One ``{{ }}`` slot: its source text and the origin of that text (not of the braces)."""

    text: str
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class SlotValue:
    """A written value that holds slots. ``parts`` alternates literal text and slots; a value that
    is exactly one slot keeps the type of its result. The model evaluates it and replaces it with a
    typed value before binding: the binder refuses an unresolved one."""

    parts: tuple[str | SlotPart, ...]
    origin: Origin = _origin()

    @property
    def single(self) -> bool:
        return len(self.parts) == 1 and isinstance(self.parts[0], SlotPart)


Value = (
    Length
    | Percent
    | Auto
    | Expand
    | Color
    | Enum
    | Bool
    | Number
    | Text
    | Sides
    | Seq
    | Shadows
    | TokenRef
    | SlotValue
)

# The style states a stylesheet rule can name after a colon (``Button:hovered``), weakest first: a
# pressed block that is also hovered shows both, the pressed values on top, and a disabled block
# shows its ``disabled`` values over everything (it takes no pointer, so it is never hovered or
# pressed while it is disabled).
STATES = ("hovered", "pressed", "disabled")

# Blocks that tre sends no pointer events: a listener on a ``text`` node is accepted and never
# called (a click goes to the box around it), so a state style cannot apply to one.
NO_POINTER_BLOCKS = ("Text",)


@dataclass(frozen=True, slots=True)
class Handler:
    """An ``On_<Event>`` value: the action's name, its named arguments (plain values) and the key
    of the module use the block belongs to (empty outside a module). The model fills ``use``."""

    action: str
    args: Mapping[str, object] = field(default_factory=dict)
    use: str = ""
    builtin: bool = False  # a shell action (Show, Hide, Toggle): the shell runs it, not a module
    # ``Call``: the module whose ``@action`` runs, when it is not the block's own (empty: the
    # module of ``use``)
    module: str = ""
    # arguments written as ``{{ }}`` slots: evaluated when the event fires (Events and Actions >
    # Call), with ``event`` in scope, the module's values and the enclosing ``For`` variables
    slots: Mapping[str, SlotValue] = field(default_factory=dict, compare=False)
    # the ``For`` entries around the block, outermost first (set by the model): what a slot in
    # ``slots`` reads the loop variables from
    entries: tuple[Any, ...] = field(default=(), compare=False)
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class TooltipRef:
    """A ``Tooltip`` written on a block or a module use (Popup > Tooltips): an inline Popup
    (``popup``, a ``schema.model.PopupDef``; typed loosely because the schema imports this
    module) or the ``Name`` of a Popup of the shell (``name``). The model moves it out of the
    tree into ``Expanded.tooltips``; the binder never sees one."""

    popup: Any = None
    name: str | None = None
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class Node:
    kind: str  # the block word: "Text", "FlexBox", "Rectangle"
    name: str | None = None  # the Name: value
    props: Mapping[str, Value] = field(default_factory=dict)  # by TDL key
    style: Mapping[str, Value] = field(default_factory=dict)  # the inline Style block
    children: tuple[Node | UseNode | IfNode | ForNode, ...] = ()
    classes: tuple[str, ...] = ()  # ``Class:`` names; the schema folds them into ``style``
    handlers: Mapping[str, Handler] = field(default_factory=dict)  # ``On_Click`` -> handler
    # State styles by state name (``hovered``, ``pressed``): the values a stylesheet rule gives the
    # block while the pointer is over it or presses it, on top of the base style
    states: Mapping[str, Mapping[str, Value]] = field(default_factory=dict)
    tooltip: TooltipRef | None = None
    # ``Part: track`` in a module's layout: the name a stylesheet addresses as ``Slider::track``
    part: str | None = None
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class UseNode:
    """A call of a module (``Clock { format: "%H:%M" }``). The model expands it into the module's
    layout before binding; the binder refuses it."""

    module: str
    name: str | None = None
    params: Mapping[str, Value] = field(default_factory=dict)
    tooltip: TooltipRef | None = None
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class IfNode:
    """``If {{ cond }} { ... } Else { ... }``. The model picks the branch; the binder refuses an
    unresolved one."""

    condition: SlotPart | None = None
    body: tuple[Node | UseNode | IfNode | ForNode, ...] = ()
    else_body: tuple[Node | UseNode | IfNode | ForNode, ...] | None = None
    use: str = ""  # the key of the module use whose layout holds it; set by the model
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class ForNode:
    """``For w In {{ items }} Key {{ w.id }} { ... }``. ``name`` is what the entries are called
    (``<name>_0001``): the head of the body's first block, else ``For``."""

    variable: str = ""
    items: SlotPart | None = None
    key: SlotPart | None = None
    name: str = "For"
    body: tuple[Node | UseNode | IfNode | ForNode, ...] = ()
    use: str = ""
    origin: Origin = _origin()


class BindError(Exception):
    """One problem, with the position of the key that caused it."""

    def __init__(self, message: str, origin: Origin, hint: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.origin = origin
        self.hint = hint

    def __str__(self) -> str:
        return f"{self.origin}: {self.message}"


class BindFailed(Exception):
    """Every problem found while binding one tree; the surface was not built."""

    def __init__(self, errors: list[BindError]) -> None:
        super().__init__("; ".join(str(e) for e in errors))
        self.errors = errors
