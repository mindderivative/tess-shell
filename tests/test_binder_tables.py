"""Every block row and key row builds a node on a headless ``tess_re`` window (T3).

This is the guard for the hand-written tables and for the Block Reference's "tre" columns: a wrong
tre name or form fails here, not for a user.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from tess_re import Window

from tess_shell.binder.build import build
from tess_shell.binder.convert import CONVERTERS
from tess_shell.binder.model import (
    Auto,
    Bool,
    Color,
    Enum,
    Length,
    Node,
    Number,
    Percent,
    Seq,
    Shadow,
    Shadows,
    Sides,
    Text,
    Value,
)
from tess_shell.binder.tables import BLOCKS, KeyRow

SVG = "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 4 4'><rect width='4' height='4'/></svg>"
PNG = str(Path(__file__).parent / "fixtures" / "png.png")

# the keys a block needs to be built at all
REQUIRED_PROPS: dict[str, dict[str, Value]] = {
    "SVG": {"Source": Text(SVG)},
    "Bitmap": {"Source": Text(PNG)},
    "Circle": {"Diameter": Length(10)},
    "Ring": {"Diameter": Length(10)},
    "Path": {"Data": Text("M0,0 L8,8")},
}


def samples(row: KeyRow) -> list[Value]:
    if row.convert == "enum":
        return [Enum(c) for c in row.choices]
    return {
        "length": [Length(10), Auto()],
        "text_length": [Length(10), Auto()],
        "bound": [Length(5)],
        "number": [Number(1)],
        "whole": [Number(2)],
        "positive": [Number(1.5)],
        "bool": [Bool(True), Bool(False)],
        "max_length": [Number(0), Number(5)],
        "lines": [Number(1), Number(3)],
        "selection": [Seq((Number(0), Number(0)))],
        "enabled": [Bool(True), Bool(False)],
        "text": [Text("x")],
        "color": [Color(1, 2, 3, 255)],
        "wrap_flag": [Bool(True), Bool(False)],
        "sides": [Length(3), Sides(1, 2, 3, 4)],
        "radius": [Length(4), Seq((Length(1), Length(2), Length(3), Length(4)))],
        "font_family": [Text("Inter")],
        "elevation": [Percent(25), Percent(100)],
        "image": [Text(PNG)],
        "a11y_value": [Number(3), Text("three")],
        "view_box": [Seq((Number(0), Number(0), Number(10), Number(10)))],
        "unit": [Number(0), Number(0.5), Number(1)],
        "pause": [Number(0), Number(1500)],
        "duration": [Number(0), Number(200)],
        "transition": [Seq((Text("Opacity"),))],
        "diameter": [Length(12)],
        "fit": [Enum("FILL"), Enum("CONTAIN"), Enum("COVER"), Enum("NONE")],
        "shadows": [
            Shadows(
                (Shadow(Color(0, 0, 0, 64), 0, 2, 6, 0), Shadow(Color(0, 0, 0, 32), 0, 8, 16, 2))
            )
        ],
    }[row.convert]


def cases() -> list[Any]:
    out = []
    for block, row in BLOCKS.items():
        for scope, table in (("props", row.keys), ("style", row.style)):
            for key, key_row in table.items():
                for value in samples(key_row):
                    if block == "SVG" and key in ("Source", "Icon"):
                        value = Text(SVG)
                    if block == "Bitmap" and key == "Source":
                        value = Text(PNG)
                    if block == "Path" and key == "Data":
                        value = Text("M0,0 L8,8")
                    out.append(
                        pytest.param(
                            block, scope, key, value, id=f"{block}.{scope}.{key}.{value!r:.40}"
                        )
                    )
    return out


def test_every_convert_name_exists() -> None:
    names = {
        k.convert for row in BLOCKS.values() for t in (row.keys, row.style) for k in t.values()
    }
    assert names <= set(CONVERTERS)


@pytest.mark.parametrize(("block", "scope", "key", "value"), cases())
def test_every_key_row_builds_a_node(block: str, scope: str, key: str, value: Value) -> None:
    window = Window(120, 60)
    props: dict[str, Value] = {
        k: v for k, v in REQUIRED_PROPS.get(block, {}).items() if k != key and k != "Icon"
    }
    if block == "SVG" and key == "Icon":
        props = {}
    if scope == "props":
        props[key] = value
        node = Node(block, props=props)
    else:
        node = Node(block, props=props, style={key: value})
    view = build([node], window)
    try:
        (root,) = view.roots
        table = BLOCKS[block].keys if scope == "props" else BLOCKS[block].style
        key_row = table[key]
        converted = CONVERTERS[key_row.convert](value, key_row.tre, key_row.choices)
        for name, expected in converted.items():
            got = root.get(name)
            assert got == (expected if name == "shadows" else pytest.approx(expected))
    finally:
        view.dispose()


@pytest.mark.parametrize("block", sorted(BLOCKS))
def test_every_block_row_builds_a_node(block: str) -> None:
    row = BLOCKS[block]
    props: dict[str, Value] = dict(REQUIRED_PROPS.get(block, {}))
    window = Window(120, 60)
    view = build([Node(block, props=props)], window)
    try:
        (root,) = view.roots
        for name, expected in row.fixed.items():
            assert root.get(name) == expected
    finally:
        view.dispose()
