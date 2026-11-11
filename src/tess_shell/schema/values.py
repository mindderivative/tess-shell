"""Read a written TDL value as a typed binder value of the key's kind."""

from __future__ import annotations

import re
from collections.abc import Callable

import tess_dl
from tess_dl import Number as DlNumber

from tess_shell.binder import convert
from tess_shell.binder import model as m
from tess_shell.binder.model import BindError
from tess_shell.schema.findings import nearest

SIDES_HINT = (
    "Use one number, four items (left, top, right, bottom) or named sides. CSS orders its "
    "sides top, right, bottom, left and accepts two or three items; this language does not."
)


class ValueProblem(Exception):
    def __init__(self, rule: str, message: str, hint: str = "") -> None:
        super().__init__(message)
        self.rule = rule
        self.message = message
        self.hint = hint


def _kind_name(value: tess_dl.Value) -> str:
    return type(value).__name__.lower()


def _bad(expected: str, value: tess_dl.Value, hint: str = "") -> ValueProblem:
    return ValueProblem("bad-value", f"expected {expected}, found a {_kind_name(value)}", hint)


def _word(value: tess_dl.Value) -> str | None:
    return value.text if isinstance(value, tess_dl.Word) else None


def _number(value: tess_dl.Value) -> int | float | None:
    return value.value if isinstance(value, DlNumber) else None


def _whole_length(value: tess_dl.Value, origin: m.Origin) -> m.Length:
    n = _number(value)
    if n is None:
        raise _bad("a whole number of pixels", value)
    if isinstance(n, float):
        raise ValueProblem(
            "bad-value", "a length is a whole number of pixels", "write 16, not 16.0"
        )
    return m.Length(n, origin=origin)


def _upper_hint(word: str, choices: tuple[str, ...]) -> str:
    if word.upper() in choices:
        return f"enum values are upper case, write {word.upper()}"
    close = nearest(word, choices)
    return f"did you mean {', '.join(close)}?" if close else f"allowed: {', '.join(choices)}"


_TOKEN = re.compile(r"^\$([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+)$")


def token_ref(
    value: tess_dl.Value, kind: str, choices: tuple[str, ...], origin: m.Origin
) -> m.TokenRef | None:
    """``$color.surface`` as a reference to a theme token; ``None`` when ``value`` is not written
    that way. A ``$`` word of another shape is a ``bad-token``."""
    word = _word(value)
    if word is None or not word.startswith("$"):
        return None
    found = _TOKEN.match(word)
    if found is None:
        raise ValueProblem(
            "bad-token",
            f"{word} is not a token reference",
            "write $group.name, such as $color.surface or $type.body.font_size",
        )
    return m.TokenRef(found.group(1).lower(), kind, choices, origin=origin)


def coerce(
    kind: str,
    value: tess_dl.Value,
    origin: m.Origin,
    choices: tuple[str, ...] = (),
    read_text: Callable[[str], str] | None = None,
) -> m.Value:
    """Return the typed value; raise :class:`ValueProblem` when the form is wrong."""
    match kind:
        case "length" | "text_length":
            if isinstance(value, tess_dl.Percent):
                return m.Percent(value.value, origin=origin)
            if (word := _word(value)) is not None:
                if word == "AUTO":
                    return m.Auto(origin=origin)
                if word == "EXPAND":
                    return m.Expand(origin=origin)
                raise ValueProblem(
                    "bad-value",
                    f"{word} is not a length",
                    _upper_hint(word, ("AUTO", "EXPAND")),
                )
            return _whole_length(value, origin)
        case "bound":
            if isinstance(value, tess_dl.Percent):
                return m.Percent(value.value, origin=origin)
            return _whole_length(value, origin)
        case "number" | "positive":
            n = _number(value)
            if n is None:
                raise _bad("a number", value)
            return m.Number(n, origin=origin)
        case "whole":
            n = _number(value)
            if n is None or isinstance(n, float):
                raise _bad("a whole number", value)
            return m.Number(n, origin=origin)
        case "bool" | "wrap_flag" | "enabled":
            word = _word(value)
            if word in ("true", "false"):
                return m.Bool(word == "true", origin=origin)
            raise _bad("true or false", value, "write true or false in lower case")
        case "text" | "svg_source":
            if isinstance(value, tess_dl.String):
                text = value.value
            elif isinstance(value, tess_dl.Word):
                text = value.text
            else:
                raise _bad("a string", value)
            if kind == "svg_source":
                assert read_text is not None
                try:
                    return m.Text(read_text(text), origin=origin)
                except OSError as exc:
                    raise ValueProblem(
                        "bad-value",
                        f"cannot read '{text}': {exc.strerror}",
                        "the path is relative to this file",
                    ) from exc
            return m.Text(text, origin=origin)
        case "color":
            return _color(value, origin)
        case "enum":
            word = _word(value)
            if word is None:
                raise _bad("an upper-case word", value, f"allowed: {', '.join(choices)}")
            if word not in choices:
                raise ValueProblem(
                    "bad-value",
                    f"{word} is not one of {', '.join(choices)}",
                    _upper_hint(word, choices),
                )
            return m.Enum(word, origin=origin)
        case "sides":
            return _sides(value, origin)
        case "bleed":
            if _word(value) == "AUTO":
                return m.Auto(origin=origin)
            return _sides(value, origin)
        case "elevation":
            if isinstance(value, tess_dl.Percent) and 0 <= value.value <= 100:
                return m.Percent(value.value, origin=origin)
            raise _bad("a percentage from 0% to 100%", value)
        case "shadows":
            raise ValueProblem(
                "bad-value",
                "Shadows is a block, not a value",
                "write Shadows { Shadow { Color: ..., X: 0, Y: 2, Blur: 6, Spread: 0 } }",
            )
        case "radius":
            n = _number(value)
            if n is not None:
                return m.Length(n, origin=origin)
            if isinstance(value, tess_dl.List) and len(value.items) == 4:
                items = []
                for item in value.items:
                    k = _number(item)
                    if k is None:
                        raise _bad("a number", item)
                    items.append(m.Length(k, origin=origin))
                return m.Seq(tuple(items), origin=origin)
            raise _bad("one number or four (from the top-left corner clockwise)", value)
        case "font_family":
            if isinstance(value, tess_dl.List):
                names = []
                for item in value.items:
                    text_ = item.value if isinstance(item, tess_dl.String) else _word(item)
                    if text_ is None:
                        raise _bad("a font family name", item)
                    names.append(m.Text(text_, origin=origin))
                return m.Seq(tuple(names), origin=origin)
            return coerce("text", value, origin)
    raise AssertionError(f"unknown kind {kind}")  # a table bug


def _color(value: tess_dl.Value, origin: m.Origin) -> m.Color:
    try:
        if isinstance(value, tess_dl.String):
            return convert.parse_color(value.value, origin)
        if isinstance(value, tess_dl.Call) and value.name == "rgba":
            parts = [_number(a) for a in value.args]
            if len(parts) not in (3, 4) or any(p is None for p in parts):
                raise ValueProblem(
                    "bad-value", "rgba takes red green blue and an alpha", "write rgba(r g b a)"
                )
            numbers = [p for p in parts if p is not None]
            text = f"rgba({' '.join(str(p) for p in numbers)})"
            return convert.parse_color(text, origin)
    except BindError as exc:
        raise ValueProblem("bad-value", exc.message, exc.hint) from exc
    raise _bad(
        "a colour",
        value,
        'a colour is "#RRGGBB", "#RRGGBBAA" or rgba(r g b a); '
        "quote the hex form, # starts a comment",
    )


def _sides(value: tess_dl.Value, origin: m.Origin) -> m.Value:
    n = _number(value)
    if n is not None:
        return m.Length(n, origin=origin)
    if isinstance(value, tess_dl.List):
        if len(value.items) != 4:
            raise ValueProblem("bad-sides", "a list of sides has four items", SIDES_HINT)
        nums = [_number(i) for i in value.items]
        if any(x is None for x in nums):
            raise _bad("four numbers", value)
        left, top, right, bottom = (float(x) for x in nums if x is not None)
        return m.Sides(left, top, right, bottom, origin=origin)
    raise _bad("one number, four items or named sides", value, SIDES_HINT)


def named_sides(block: tess_dl.Block, origin: m.Origin) -> m.Sides:
    """``Padding { Left: 24, Top: 8 }``: unnamed sides are 0."""
    sides = {"Left": 0.0, "Top": 0.0, "Right": 0.0, "Bottom": 0.0}
    for entry in block.entries:
        if isinstance(entry, tess_dl.Property):
            if entry.key not in sides:
                raise ValueProblem(
                    "unknown-key", f"unknown side {entry.key}", f"sides: {', '.join(sides)}"
                )
            n = _number(entry.value)
            if n is None:
                raise _bad("a number", entry.value)
            sides[entry.key] = float(n)
    return m.Sides(sides["Left"], sides["Top"], sides["Right"], sides["Bottom"], origin=origin)


_SHADOW_KEYS = ("Color", "X", "Y", "Blur", "Spread")


def named_shadows(block: tess_dl.Block, origin: m.Origin) -> m.Shadows:
    """``Shadows { Shadow { Color: "#00000040", X: 0, Y: 2, Blur: 6, Spread: 0 } ... }``, first on
    top. ``Color`` is required; the numbers default to 0."""
    items: list[m.Shadow] = []
    for entry in block.entries:
        if not isinstance(entry, tess_dl.Block) or entry.type != "Shadow":
            raise ValueProblem("bad-value", "Shadows holds Shadow blocks", "write Shadow { ... }")
        found: dict[str, tess_dl.Value] = {}
        for sub in entry.entries:
            if not isinstance(sub, tess_dl.Property) or sub.key not in _SHADOW_KEYS:
                raise ValueProblem(
                    "unknown-key",
                    f"unknown Shadow key {getattr(sub, 'key', getattr(sub, 'type', '?'))}",
                    f"keys: {', '.join(_SHADOW_KEYS)}",
                )
            found[sub.key] = sub.value
        if "Color" not in found:
            raise ValueProblem("missing-key", "a Shadow needs a Color", 'write Color: "#00000040"')
        numbers: dict[str, float] = {}
        for key in _SHADOW_KEYS[1:]:
            if key in found:
                n = _number(found[key])
                if n is None or (key == "Blur" and n < 0):
                    raise _bad("a number" if key != "Blur" else "a number of 0 or more", found[key])
                numbers[key] = float(n)
        items.append(
            m.Shadow(
                _color(found["Color"], origin),
                numbers.get("X", 0),
                numbers.get("Y", 0),
                numbers.get("Blur", 0),
                numbers.get("Spread", 0),
                origin=origin,
            )
        )
    return m.Shadows(tuple(items), origin=origin)


def _py_kind(value: object) -> str:
    return type(value).__name__


def _py_number(value: object) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return value


def from_python(
    kind: str, value: object, origin: m.Origin, choices: tuple[str, ...] = ()
) -> m.Value:
    """The typed value of an evaluated slot (a plain Python value), for the key's ``kind``.

    Raises :class:`ValueProblem` when the value cannot be that kind.
    """

    def bad(expected: str) -> ValueProblem:
        return ValueProblem("bad-value", f"expected {expected}, the slot gave a {_py_kind(value)}")

    match kind:
        case "text" | "svg_source":
            if isinstance(value, str):
                return m.Text(value, origin=origin)
            raise bad("a string")
        case "number" | "positive" | "whole":
            n = _py_number(value)
            if n is None or (kind == "whole" and isinstance(n, float)):
                raise bad("a whole number" if kind == "whole" else "a number")
            return m.Number(n, origin=origin)
        case "bool" | "wrap_flag" | "enabled":
            if isinstance(value, bool):
                return m.Bool(value, origin=origin)
            raise bad("true or false")
        case "length" | "text_length" | "bound":
            n = _py_number(value)
            if n is not None:
                if isinstance(n, float) and not n.is_integer():
                    raise ValueProblem("bad-value", "a length is a whole number of pixels")
                return m.Length(n, origin=origin)
            if isinstance(value, str):
                word = value.strip()
                if word.endswith("%") and word[:-1].isdigit():
                    return m.Percent(int(word[:-1]), origin=origin)
                if kind != "bound" and word == "AUTO":
                    return m.Auto(origin=origin)
                if kind != "bound" and word == "EXPAND":
                    return m.Expand(origin=origin)
            raise bad("a number of pixels, a percentage, AUTO or EXPAND")
        case "color":
            if isinstance(value, str):
                try:
                    return convert.parse_color(value, origin)
                except BindError as exc:
                    raise ValueProblem("bad-value", exc.message, exc.hint) from exc
            raise bad("a colour string")
        case "enum":
            if isinstance(value, str) and value in choices:
                return m.Enum(value, origin=origin)
            raise ValueProblem(
                "bad-value",
                f"expected one of {', '.join(choices)}, the slot gave {value!r}",
                _upper_hint(value, choices) if isinstance(value, str) else "",
            )
        case "sides" | "radius":
            n = _py_number(value)
            if n is not None:
                return m.Length(n, origin=origin)
            if isinstance(value, list | tuple) and len(value) == 4:
                nums = [_py_number(v) for v in value]
                if all(x is not None for x in nums):
                    good = [x for x in nums if x is not None]
                    if kind == "sides":
                        a, b, c, d = (float(x) for x in good)
                        return m.Sides(a, b, c, d, origin=origin)
                    return m.Seq(tuple(m.Length(x, origin=origin) for x in good), origin=origin)
            raise bad("a number or a list of four numbers")
        case "font_family":
            if isinstance(value, str):
                return m.Text(value, origin=origin)
            if isinstance(value, list | tuple) and value and all(isinstance(v, str) for v in value):
                return m.Seq(tuple(m.Text(v, origin=origin) for v in value), origin=origin)
            raise bad("a font family name or a list of names")
    raise AssertionError(f"unknown kind {kind}")  # a table bug
