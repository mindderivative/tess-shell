"""The typed tree: what the schema produces and the binder consumes.

Every value carries the :class:`Origin` of its **key** in the TDL file, the position reported
when the value is wrong. An origin never takes part in equality, so a tree read from a file
equals the same tree built in code.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field


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


Value = Length | Percent | Auto | Expand | Color | Enum | Bool | Number | Text | Sides | Seq


@dataclass(frozen=True, slots=True)
class Node:
    kind: str  # the block word: "Text", "FlexBox", "Rectangle"
    name: str | None = None  # the Name: value
    props: Mapping[str, Value] = field(default_factory=dict)  # by TDL key
    style: Mapping[str, Value] = field(default_factory=dict)  # the inline Style block
    children: tuple[Node | IfNode | ForNode, ...] = ()
    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class IfNode:
    """Exists so the types are stable; M1 refuses it."""

    origin: Origin = _origin()


@dataclass(frozen=True, slots=True)
class ForNode:
    """Exists so the types are stable; M1 refuses it."""

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
