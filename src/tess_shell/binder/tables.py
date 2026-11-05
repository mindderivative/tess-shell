"""The block table and the key table for the M1 blocks (plain data; Render Binder Design).

Hand-written and guarded by ``tests/test_binder_tables.py``, which builds a node for every row on
a headless ``tess_re`` window. A TDL key is looked up per block: a block row lists the keys it
accepts as properties and, separately, the keys its inline ``Style`` accepts. A key that is both
(``Padding``, ``Margin``, ``Spacing``, ``Opacity``, and ``Fill`` on a Rectangle) is the same row;
written in ``Style`` it wins over the property (Block Reference, R2).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class KeyRow:
    tre: tuple[str, ...]  # the tre property, or four for a four-sided key
    convert: str  # a name in convert.CONVERTERS
    choices: tuple[str, ...] = ()  # allowed enum words, in TDL case


@dataclass(frozen=True, slots=True)
class BlockRow:
    tre_kind: str
    keys: Mapping[str, KeyRow]  # accepted as properties
    style: Mapping[str, KeyRow]  # accepted in the inline Style block
    fixed: Mapping[str, Any] = field(default_factory=dict)  # tre props always set
    defaults: Mapping[str, Any] = field(default_factory=dict)  # tre props set when absent
    required: tuple[str | tuple[str, ...], ...] = ()  # keys that must be present; a tuple is any of
    child_props: Mapping[str, Any] = field(default_factory=dict)  # added to every child
    children_ok: bool = False


def _k(tre: str | tuple[str, ...], convert: str, *choices: str) -> KeyRow:
    return KeyRow((tre,) if isinstance(tre, str) else tre, convert, choices)


def _four(prefix: str) -> tuple[str, ...]:
    return tuple(f"{prefix}_{side}" for side in ("top", "right", "bottom", "left"))


ALIGN = ("START", "CENTER", "END", "STRETCH")

_COMMON: dict[str, KeyRow] = {
    "Visible": _k("visible", "bool"),
    "Width": _k("width", "length"),
    "Height": _k("height", "length"),
    "Min_Width": _k("min_width", "bound"),
    "Min_Height": _k("min_height", "bound"),
    "Max_Width": _k("max_width", "bound"),
    "Max_Height": _k("max_height", "bound"),
    "Aspect_Ratio": _k("aspect_ratio", "positive"),
    "Margin": _k(_four("margin"), "sides"),
    "Flex_Grow": _k("flex_grow", "number"),
    "Flex_Shrink": _k("flex_shrink", "number"),
    "Align_Self": _k("align_self", "enum", *ALIGN),
    "Z_Index": _k("z_index", "whole"),
    "Label": _k("label", "text"),
    "A11y_Hidden": _k("a11y_hidden", "bool"),
    "Opacity": _k("opacity", "number"),
}

_PADDING = {"Padding": _k(_four("padding"), "sides")}

_BOX_STYLE: dict[str, KeyRow] = {
    "Background": _k("fill", "color"),
    "Border_Width": _k("stroke_width", "number"),
    "Border_Color": _k("stroke_color", "color"),
    "Corner_Radius": _k("corner_radius", "radius"),
    "Padding": _PADDING["Padding"],
    "Margin": _COMMON["Margin"],
    "Opacity": _COMMON["Opacity"],
}

_FLEX: dict[str, KeyRow] = {
    "Flex": _k("flex_direction", "enum", "HORIZONTAL", "VERTICAL"),
    "Wrap": _k("flex_wrap", "wrap_flag"),
    "Align_Items": _k("align_items", "enum", *ALIGN),
    "Justify_Content": _k(
        "justify_content",
        "enum",
        "START",
        "CENTER",
        "END",
        "SPACE_BETWEEN",
        "SPACE_AROUND",
        "SPACE_EVENLY",
    ),
    "Spacing": _k("gap", "number"),
}

_TEXT_STYLE: dict[str, KeyRow] = {
    "Foreground": _k("fill", "color"),
    "Font_Family": _k("font_family", "font_family"),
    "Font_Size": _k("font_size", "positive"),
    "Font_Weight": _k("font_weight", "whole"),
    "Line_Height": _k("line_height", "positive"),
    "Text_Align": _k("text_align", "enum", "START", "CENTER", "END"),
    "Overflow": _k("overflow", "enum", "CLIP", "ELLIPSIS"),
    "Padding": _PADDING["Padding"],
    "Margin": _COMMON["Margin"],
    "Opacity": _COMMON["Opacity"],
}

_SHAPE: dict[str, KeyRow] = {
    "Fill": _k("fill", "color"),
    "Border_Width": _k("stroke_width", "number"),
    "Border_Color": _k("stroke_color", "color"),
    "Corner_Radius": _k("corner_radius", "radius"),
    "Margin": _COMMON["Margin"],
    "Opacity": _COMMON["Opacity"],
}

BLOCKS: Mapping[str, BlockRow] = {
    # A Box is a one-cell grid: every child sits in cell (1, 1) (Block Reference, R1).
    "Box": BlockRow(
        "box",
        keys={**_COMMON, **_PADDING},
        style=_BOX_STYLE,
        fixed={"display": "grid", "grid_template_columns": "1fr", "grid_template_rows": "1fr"},
        child_props={"grid_column": 1, "grid_row": 1},
        children_ok=True,
    ),
    "FlexBox": BlockRow(
        "box",
        keys={**_COMMON, **_FLEX, **_PADDING},
        style={**_BOX_STYLE, "Spacing": _FLEX["Spacing"]},
        fixed={"display": "flex"},
        children_ok=True,
    ),
    "Text": BlockRow(
        "text",
        keys={
            **_COMMON,
            **_PADDING,
            "Width": _k("width", "text_length"),
            "Height": _k("height", "text_length"),
            "Text": _k("text", "text"),
            "Wrap": _k("wrap", "enum", "WORD", "NONE"),
            "Max_Lines": _k("max_lines", "whole"),
        },
        style=_TEXT_STYLE,
        # tre lays out a text with no width at width 0 (two texts in a row overlap): fit content
        defaults={"text": "", "width": "fit-content"},
    ),
    # Drawn as a rounded tre box, not a path: a path needs numeric sizes, and Width may be AUTO.
    "Rectangle": BlockRow(
        "box",
        keys={**_COMMON, **_SHAPE},
        style=_SHAPE,
    ),
    # Takes the free space along its parent's main axis.
    "Spacer": BlockRow("box", keys=_COMMON, style={}, defaults={"flex_grow": 1}),
    "SVG": BlockRow(
        "svg",
        keys={
            **_COMMON,
            "Source": _k("svg", "text"),
            "Icon": _k("svg", "text"),
            "Color": _k("svg_color", "color"),
        },
        style={"Foreground": _k("svg_color", "color"), "Opacity": _COMMON["Opacity"]},
        required=(("Source", "Icon"),),
    ),
}
