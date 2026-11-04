"""Converters: a typed value to what tre takes, one form per kind of value (ADR-0018).

Pure functions over :mod:`tess_shell.binder.model`, standard library only, so they can move to
``tess_utils`` unchanged. Each takes the value and the tre property names of the key's row and
returns ``{tre property: tre value}``, or raises :class:`BindError` at the value's origin.
The parsers at the end turn written forms into typed values; the schema will use them.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from typing import Any

from tess_shell.binder.model import (
    Auto,
    BindError,
    Bool,
    Color,
    Enum,
    Expand,
    Length,
    Number,
    Origin,
    Percent,
    Seq,
    Sides,
    Text,
    Value,
)

Converted = dict[str, Any]
Converter = Callable[[Value, tuple[str, ...], tuple[str, ...]], Converted]


def _what(value: Value) -> str:
    return type(value).__name__.lower()


def _bad(value: Value, expected: str) -> BindError:
    return BindError(f"expected {expected}, found {_what(value)}", value.origin)


def _num(x: float) -> int | float:
    return int(x) if float(x).is_integer() else x


def length(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    """Pixels, ``50%``, ``AUTO`` and ``EXPAND``. ``EXPAND`` is flex growth plus stretch
    (Block Reference, proposed mapping); it needs a size key, so it is refused elsewhere."""
    (name,) = names
    match value:
        case Length(px=px):
            if px < 0:
                raise BindError("a length cannot be negative", value.origin)
            return {name: _num(px)}
        case Percent(value=p):
            if p < 0:
                raise BindError("a percentage cannot be negative", value.origin)
            return {name: f"{_num(p)}%"}
        case Auto():
            return {name: "auto"}
        case Expand():
            if name not in ("width", "height"):
                raise BindError("EXPAND is only allowed for Width and Height", value.origin)
            return {"flex_grow": 1, "align_self": "stretch"}
    raise _bad(value, "a length, a percentage, AUTO or EXPAND")


def bound(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    """A bound (``Min_Width``): pixels or a percentage."""
    if isinstance(value, Length | Percent):
        return length(value, names)
    raise _bad(value, "a length or a percentage")


def number(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    (name,) = names
    if isinstance(value, Number) and not isinstance(value.value, bool):
        return {name: value.value}
    if isinstance(value, Length):
        return {name: _num(value.px)}
    raise _bad(value, "a number")


def whole(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    (name,) = names
    if isinstance(value, Number) and isinstance(value.value, int):
        return {name: value.value}
    if isinstance(value, Length) and float(value.px).is_integer():
        return {name: int(value.px)}
    raise _bad(value, "a whole number")


def positive(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    result = number(value, names)
    if next(iter(result.values())) <= 0:
        raise BindError("must be greater than 0", value.origin)
    return result


def boolean(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    (name,) = names
    if isinstance(value, Bool):
        return {name: value.value}
    raise _bad(value, "true or false")


def text(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    (name,) = names
    if isinstance(value, Text):
        return {name: value.value}
    raise _bad(value, "a string")


def color(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    (name,) = names
    if isinstance(value, Color):
        for channel in (value.r, value.g, value.b, value.a):
            if not 0 <= channel <= 255:
                raise BindError("a colour channel is 0 to 255", value.origin)
        return {name: (value.r, value.g, value.b, value.a)}
    raise _bad(value, "a colour")


def enum(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    """An upper-case enum word becomes tre's lower-case word."""
    (name,) = names
    if not isinstance(value, Enum):
        raise _bad(value, "one of " + ", ".join(choices) if choices else "an enum word")
    if choices and value.name not in choices:
        raise BindError(
            f"{value.name} is not one of {', '.join(choices)}",
            value.origin,
            hint=_nearest_hint(value.name, choices),
        )
    return {name: value.name.lower()}


def wrap_flag(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    """``Wrap: true`` is tre's ``flex_wrap: "wrap"``."""
    (name,) = names
    if isinstance(value, Bool):
        return {name: "wrap" if value.value else "no_wrap"}
    raise _bad(value, "true or false")


def sides(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    """Four-sided values, left, top, right, bottom, become tre's top, right, bottom, left."""
    if len(names) != 4:
        raise ValueError("a sides row names four tre properties")  # a table bug
    if isinstance(value, Length | Number):
        one = value.px if isinstance(value, Length) else value.value
        left = top = right = bottom = float(one)
    elif isinstance(value, Sides):
        left, top, right, bottom = value.left, value.top, value.right, value.bottom
    else:
        raise _bad(value, "a number or four sides")
    if min(left, top, right, bottom) < 0:
        raise BindError("a side cannot be negative", value.origin)
    return dict(zip(names, (_num(top), _num(right), _num(bottom), _num(left)), strict=True))


def radius(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    """One number, or four from the top-left corner clockwise."""
    (name,) = names
    if isinstance(value, Length | Number):
        one = value.px if isinstance(value, Length) else value.value
        if one < 0:
            raise BindError("a radius cannot be negative", value.origin)
        return {name: _num(one)}
    if isinstance(value, Seq) and len(value.items) == 4:
        corners = []
        for item in value.items:
            if not isinstance(item, Length | Number):
                raise _bad(item, "a number")
            n = item.px if isinstance(item, Length) else item.value
            if n < 0:
                raise BindError("a radius cannot be negative", item.origin)
            corners.append(_num(n))
        return {name: tuple(corners)}
    raise _bad(value, "one number or four")


def font_family(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    """tre takes one family name (a list is refused), so a list gives its first entry."""
    (name,) = names
    if isinstance(value, Text):
        return {name: value.value}
    if isinstance(value, Seq) and value.items and all(isinstance(i, Text) for i in value.items):
        first = value.items[0]
        assert isinstance(first, Text)
        return {name: first.value}
    raise _bad(value, "a font family name or a list of names")


CONVERTERS: Mapping[str, Converter] = {
    "length": length,
    "bound": bound,
    "number": number,
    "whole": whole,
    "positive": positive,
    "bool": boolean,
    "text": text,
    "color": color,
    "enum": enum,
    "wrap_flag": wrap_flag,
    "sides": sides,
    "radius": radius,
    "font_family": font_family,
}


def _nearest_hint(word: str, choices: tuple[str, ...]) -> str:
    import difflib

    close = difflib.get_close_matches(word, choices, n=3, cutoff=0.5)
    return f"did you mean {', '.join(close)}?" if close else f"allowed: {', '.join(choices)}"


# --- parsers: written form to typed value ------------------------------------------------

_HEX = re.compile(r"^#([0-9a-fA-F]{6}|[0-9a-fA-F]{8}|[0-9a-fA-F]{3}|[0-9a-fA-F]{4})$")
_RGBA = re.compile(r"^rgba?\(\s*([^)]*)\)$")


def parse_color(written: str, origin: Origin) -> Color:
    """``#RRGGBB``, ``#RRGGBBAA``, ``#RGB``, ``#RGBA``, ``rgba(r g b a)`` (alpha 0.0 to 1.0)."""
    text_ = written.strip()
    if m := _HEX.match(text_):
        digits = m.group(1)
        if len(digits) in (3, 4):
            digits = "".join(c * 2 for c in digits)
        channels = [int(digits[i : i + 2], 16) for i in range(0, len(digits), 2)]
        if len(channels) == 3:
            channels.append(255)
        r, g, b, a = channels
        return Color(r, g, b, a, origin=origin)
    if m := _RGBA.match(text_):
        parts = m.group(1).replace(",", " ").split()
        try:
            if len(parts) not in (3, 4):
                raise ValueError
            r, g, b = (int(p) for p in parts[:3])
            alpha = float(parts[3]) if len(parts) == 4 else 1.0
        except ValueError:
            raise BindError(f"not a colour: {written!r}", origin) from None
        if not (0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255 and 0.0 <= alpha <= 1.0):
            raise BindError(f"colour channel out of range in {written!r}", origin)
        return Color(r, g, b, round(alpha * 255), origin=origin)
    raise BindError(
        f"not a colour: {written!r}",
        origin,
        hint='write "#RRGGBB", "#RRGGBBAA" or "rgba(r g b a)"',
    )
