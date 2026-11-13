"""What tre says a block's keys are when nothing is written: the defaults of the schema export.

Each block is built bare on a headless ``tess_re`` window, through the binder (so the values the
shell itself sets, ``defaults`` of a table row, are included), and every tre property a key sets is
read back with ``node.get``. The value is turned into the text a file would write for that key's
kind (``"#1e1e2e"``, ``RELATIVE``, ``32``, ``AUTO``, ``true``). A key that sets no tre property, a
key tre has no value for (``None``) and a value the key cannot be written as give nothing: the
export then says ``null``, it does not guess.
"""

from __future__ import annotations

import functools
import json
from collections.abc import Sequence
from typing import Any

from tess_re import Window

from tess_shell.binder.build import build
from tess_shell.binder.images import ERROR_IMAGE
from tess_shell.binder.model import (
    FIELD,
    FIELD_INPUT,
    FIELD_SIZE,
    MARQUEE,
    MARQUEE_TEXT,
    Length,
    Node,
    Text,
    Value,
)
from tess_shell.binder.tables import BLOCKS, KeyRow

# the keys a block needs to be built at all (the table's ``required``): no default, and a value so
# the node can be built
_BUILD_WITH: dict[str, dict[str, Value]] = {
    "SVG": {
        "Source": Text(
            "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 4 4'>"
            "<rect width='4' height='4'/></svg>"
        )
    },
    "Bitmap": {"Source": Text(str(ERROR_IMAGE))},
    "Circle": {"Diameter": Length(10)},
    "Ring": {"Diameter": Length(10)},
    "Path": {"Data": Text("M0,0 L8,8")},
}

# the rows a block's keys are read from, in order: a TextField and a Marquee are several nodes
_ROWS: dict[str, tuple[str, ...]] = {
    FIELD: (FIELD, FIELD_INPUT, FIELD_SIZE),
    MARQUEE: (MARQUEE, MARQUEE_TEXT),
}


def _number(x: Any) -> str | None:
    if isinstance(x, bool) or not isinstance(x, int | float):
        return None
    return str(int(x)) if float(x).is_integer() else repr(float(x))


def _hex(color: Any) -> str | None:
    if not (isinstance(color, Sequence) and len(color) == 4):
        return None
    r, g, b, a = (int(c) for c in color)
    return f'"#{r:02x}{g:02x}{b:02x}{"" if a == 255 else f"{a:02x}"}"'


def _sides(values: Sequence[Any]) -> str | None:
    """tre's top, right, bottom, left as the file's left, top, right, bottom."""
    nums = [_number(v) for v in values]
    if len(nums) != 4 or any(n is None for n in nums):
        return None
    top, right, bottom, left = nums
    if len({top, right, bottom, left}) == 1:
        return left
    return f"[{left}, {top}, {right}, {bottom}]"


def _text(kind: str, key_row: KeyRow, values: Sequence[Any]) -> str | None:
    """The written form of what tre read for a key of this kind, or ``None``."""
    first = values[0] if values else None
    match kind:
        case "sides":
            return _sides(values)
        case "length" | "text_length" | "bound":
            if first in ("auto", "fit-content"):
                return None if kind == "bound" else "AUTO"
            if isinstance(first, str) and first.endswith("%"):
                return first
            return _number(first)
        case "number" | "positive" | "unit" | "whole" | "diameter":
            return _number(first)
        case "bool":
            return "true" if first is True else "false" if first is False else None
        case "enabled":  # tre's ``disabled``
            return "true" if first is False else "false" if first is True else None
        case "wrap_flag":
            return {"wrap": "true", "no_wrap": "false"}.get(str(first))
        case "enum" | "fit":
            word = first.upper() if isinstance(first, str) else None
            return word if word in key_row.choices else None
        case "text" | "font_family":
            return json.dumps(first) if isinstance(first, str) else None
        case "color":
            return _hex(first)
        case "radius":
            if isinstance(first, Sequence) and not isinstance(first, str):
                nums = [_number(v) for v in first]
                if len(nums) == 4 and None not in nums:
                    same = len(set(nums)) == 1
                    return nums[0] if same else "[" + ", ".join(str(n) for n in nums) + "]"
                return None
            return _number(first)
        case "max_length":  # tre's ``None`` is no limit, which a file writes as 0
            return "0" if first is None else _number(first)
        case "lines":  # the size text is one ``x`` for each line
            return str(first.count("\n") + 1) if isinstance(first, str) and first else None
        case "selection":
            ok = isinstance(first, Sequence) and len(first) == 2 and first[0] == first[1] == 0
            return "[0, 0]" if ok else None
        case "elevation":  # no shadows is no elevation
            return "0%" if first == [] or first == () else None
    return None


@functools.cache
def tre_defaults() -> dict[tuple[str, str], str]:
    """``(block, key)`` -> the default tre gives the key of a bare block, as TDL text."""
    window = Window(120, 60)
    out: dict[tuple[str, str], str] = {}
    for block in (b for b in BLOCKS if "." not in b):
        build_with = _BUILD_WITH.get(block, {})
        needed = {
            k
            for group in BLOCKS[block].required
            for k in ((group,) if isinstance(group, str) else group)
        }
        for row_name in _ROWS.get(block, (block,)):
            row = BLOCKS[row_name]
            props = dict(build_with) if row_name == block else {}
            view = build([Node(row_name, props=props)], window)
            try:
                (root,) = view.roots
                for key, key_row in {**row.keys, **row.style}.items():
                    if not key_row.tre or key in needed or (block, key) in out:
                        continue
                    text = _text(key_row.convert, key_row, [root.get(n) for n in key_row.tre])
                    if text is not None:
                        out[(block, key)] = text
            finally:
                view.dispose()
    return out
