"""Converters: a typed value to what tre takes, one form per kind of value (ADR-0018).

Pure functions over :mod:`tess_shell.binder.model`. The forms that several Tesserae projects share
(a colour's written forms, four-sided values and their order, corner radii, enum words) belong to
``tess_utils`` (the carried compiled file, ``tess_shell._vendor``); what is left here wraps them in
the shell's typed values and raises :class:`BindError` at the value's origin. Each converter takes
the value and the tre property names of the key's row and returns
``{tre property: tre value}``. The parsers at the end turn written forms into typed values; the
schema uses them.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from tess_shell._vendor import tess_utils
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
    Shadows,
    Sides,
    Text,
    Value,
)
from tess_shell.binder.shadow import DEFAULT_MAX, scale

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


def text_length(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    """A text node's size: ``AUTO`` is tre's ``"fit-content"`` (Block Reference, Text)."""
    if isinstance(value, Auto):
        (name,) = names
        return {name: "fit-content"}
    return length(value, names)


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


def _whole_of(value: Value) -> int | None:
    if isinstance(value, Number) and isinstance(value.value, int):
        return None if isinstance(value.value, bool) else value.value
    return None


def max_length(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    """The most characters a text input takes; ``0`` is no limit (tre's ``None``)."""
    (name,) = names
    n = _whole_of(value)
    if n is None:
        raise _bad(value, "a whole number")
    if n < 0:
        raise BindError("must be 0 or more", value.origin)
    return {name: n or None}


def lines(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    """``Lines: 3`` is a text of three lines (``x`` each): a field is as high as its lines."""
    (name,) = names
    n = _whole_of(value)
    if n is None:
        raise _bad(value, "a whole number")
    if n < 1:
        raise BindError("must be 1 or more", value.origin)
    return {name: "\n".join(["x"] * n)}


def selection(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    """``Selection: [2, 5]`` is tre's ``(start, end)``, UTF-8 byte offsets."""
    (name,) = names
    if (
        isinstance(value, Seq)
        and len(value.items) == 2
        and all(isinstance(i, Number) and isinstance(i.value, int) for i in value.items)
    ):
        start, end = (i.value for i in value.items if isinstance(i, Number))
        return {name: (start, end)}
    raise _bad(value, "[start, end]")


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
    try:
        return {name: tess_utils.to_tre_word(value.name)}
    except ValueError as exc:
        raise BindError(str(exc), value.origin) from None


def enabled(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    """``Enabled: false`` is tre's ``disabled: true`` (an accessibility state only: the shell stops
    the pointer itself, see :class:`~tess_shell.binder.build.Wire`)."""
    (name,) = names
    if isinstance(value, Bool):
        return {name: not value.value}
    raise _bad(value, "true or false")


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
        written: float | tuple[float, float, float, float] = (
            value.px if isinstance(value, Length) else value.value
        )
    elif isinstance(value, Sides):
        written = (value.left, value.top, value.right, value.bottom)
    else:
        raise _bad(value, "a number or four sides")
    try:
        left_top_right_bottom = tess_utils.expand_sides(written)
    except ValueError as exc:
        raise BindError(str(exc), value.origin) from None
    if min(left_top_right_bottom) < 0:
        raise BindError("a side cannot be negative", value.origin)
    return dict(
        zip(names, (_num(x) for x in tess_utils.to_tre_order(left_top_right_bottom)), strict=True)
    )


def radius(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    """One number, or four from the top-left corner clockwise."""
    (name,) = names
    if isinstance(value, Length | Number):
        one = value.px if isinstance(value, Length) else value.value
        if one < 0:
            raise BindError("a radius cannot be negative", value.origin)
        return {name: _num(one)}
    if isinstance(value, Seq) and len(value.items) == 4:
        numbers: list[float] = []
        for item in value.items:
            if not isinstance(item, Length | Number):
                raise _bad(item, "a number")
            n = item.px if isinstance(item, Length) else item.value
            if n < 0:
                raise BindError("a radius cannot be negative", item.origin)
            numbers.append(n)
        return {name: tuple(_num(x) for x in tess_utils.expand_radius(numbers))}
    raise _bad(value, "one number or four")


def font_family(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    """tre takes one string, so a list of families is joined with ``", "`` (the fallback order is
    checked on a live compositor, in the KWin checklist)."""
    (name,) = names
    if isinstance(value, Text):
        return {name: value.value}
    if isinstance(value, Seq) and value.items and all(isinstance(i, Text) for i in value.items):
        return {name: ", ".join(i.value for i in value.items if isinstance(i, Text))}
    raise _bad(value, "a font family name or a list of names")


def _tre_shadows(value: Shadows) -> list[tuple[Any, ...]]:
    return [
        (
            (s.color.r, s.color.g, s.color.b, s.color.a),
            _num(s.x),
            _num(s.y),
            _num(s.blur),
            _num(s.spread),
        )
        for s in value.items
    ]


def shadows(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    """A list of shadows becomes tre's ``(color, dx, dy, blur, spread)`` tuples."""
    (name,) = names
    if isinstance(value, Shadows):
        for s in value.items:
            if s.blur < 0:
                raise BindError("a shadow's blur cannot be negative", s.origin)
        return {name: _tre_shadows(value)}
    raise _bad(value, "shadows")


def elevation(value: Value, names: tuple[str, ...], choices: tuple[str, ...] = ()) -> Converted:
    """``Elevation: 20%`` with the default ``Max`` (a theme's ``Max`` is applied before binding
    and arrives as :func:`shadows`)."""
    if isinstance(value, Percent):
        if not 0 <= value.value <= 100:
            raise BindError("an elevation is 0% to 100%", value.origin)
        return shadows(scale(DEFAULT_MAX, value.value, value.origin), names)
    raise _bad(value, "a percentage")


CONVERTERS: Mapping[str, Converter] = {
    "length": length,
    "text_length": text_length,
    "bound": bound,
    "number": number,
    "whole": whole,
    "positive": positive,
    "bool": boolean,
    "max_length": max_length,
    "lines": lines,
    "selection": selection,
    "text": text,
    "color": color,
    "enum": enum,
    "wrap_flag": wrap_flag,
    "enabled": enabled,
    "sides": sides,
    "radius": radius,
    "font_family": font_family,
    "shadows": shadows,
    "elevation": elevation,
}


def _nearest_hint(word: str, choices: tuple[str, ...]) -> str:
    import difflib

    close = difflib.get_close_matches(word, choices, n=3, cutoff=0.5)
    return f"did you mean {', '.join(close)}?" if close else f"allowed: {', '.join(choices)}"


# --- parsers: written form to typed value ------------------------------------------------


def parse_color(written: str, origin: Origin) -> Color:
    """``#RRGGBB``, ``#RRGGBBAA``, ``#RGB``, ``#RGBA``, ``rgb(r g b)``, ``rgba(r g b a)`` (alpha 0.0
    to 1.0) or ``transparent``; the reading is ``tess_utils.parse_color``'s."""
    try:
        r, g, b, a = tess_utils.parse_color(written)
    except ValueError as exc:
        raise BindError(
            str(exc),
            origin,
            hint='write "#RRGGBB", "#RRGGBBAA" or "rgba(r g b a)"',
        ) from None
    return Color(r, g, b, a, origin=origin)
