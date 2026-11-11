"""The block table and the key table for the M1 blocks (plain data; Render Binder Design).

Hand-written and guarded by ``tests/test_binder_tables.py``, which builds a node for every row on
a headless ``tess_re`` window. A TDL key is looked up per block: a block row lists the keys it
accepts as properties and, separately, the keys its inline ``Style`` accepts. A key that is both
(``Padding``, ``Margin``, ``Spacing``, ``Opacity``, and ``Fill`` on a Rectangle) is the same row;
written in ``Style`` it wins over the property (Block Reference, R2).
"""

from __future__ import annotations

import dataclasses
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
    post: str = ""  # a function of ``binder.shapes.POSTS`` that completes the converted props


def _k(tre: str | tuple[str, ...], convert: str, *choices: str) -> KeyRow:
    return KeyRow((tre,) if isinstance(tre, str) else tre, convert, choices)


def _four(prefix: str) -> tuple[str, ...]:
    return tuple(f"{prefix}_{side}" for side in ("top", "right", "bottom", "left"))


ALIGN = ("START", "CENTER", "END", "STRETCH")
ROLES = (
    "BUTTON",
    "CHECKBOX",
    "RADIO",
    "SWITCH",
    "SLIDER",
    "PROGRESSBAR",
    "LINK",
    "TEXTBOX",
    "TAB",
    "TABLIST",
    "TABPANEL",
    "MENU",
    "MENUITEM",
    "DIALOG",
    "ALERT",
    "LIST",
    "LISTITEM",
    "TREE",
    "TREEITEM",
    "HEADING",
    "IMG",
    "GROUP",
    "NONE",
    "SEPARATOR",
)
EASINGS = ("STANDARD", "EMPHASIZED", "LINEAR")

_COMMON: dict[str, KeyRow] = {
    "Visible": _k("visible", "bool"),
    "Enabled": _k("disabled", "enabled"),
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
    "Position": _k("position", "enum", "RELATIVE", "ABSOLUTE"),
    "Left": _k("left", "length"),
    "Top": _k("top", "length"),
    "Right": _k("right", "length"),
    "Bottom": _k("bottom", "length"),
    "Translate_X": _k("translate_x", "number"),
    "Translate_Y": _k("translate_y", "number"),
    "Scale": _k("scale", "positive"),
    "Rotation": _k("rotation_deg", "number"),
    "Clip_Children": _k("clip_children", "bool"),
    "Role": _k("role", "enum", *ROLES),
    "Description": _k("description", "text"),
    "Live": _k("live", "enum", "POLITE", "ASSERTIVE"),
    # accessibility state, set by a module (a shell file may not write it: the schema says so)
    "Value": _k("value", "a11y_value"),
    "Value_Min": _k("value_min", "number"),
    "Value_Max": _k("value_max", "number"),
    "Value_Step": _k("value_step", "number"),
    "Checked": _k("checked", "bool"),
    "Selected": _k("selected", "bool"),
    "Expanded": _k("expanded", "bool"),
}

# the motion keys have no tre property: the binder animates a change of a listed key
# (``binder.motion``)
_MOTION: dict[str, KeyRow] = {
    "Transition": _k((), "transition"),
    "Duration": _k((), "duration"),
    "Easing": _k((), "enum", *EASINGS),
}

_PADDING = {"Padding": _k(_four("padding"), "sides")}

_BOX_STYLE: dict[str, KeyRow] = {
    **_MOTION,
    "Background": _k("fill", "color"),
    "Border_Width": _k("stroke_width", "number"),
    "Border_Color": _k("stroke_color", "color"),
    "Corner_Radius": _k("corner_radius", "radius"),
    "Padding": _PADDING["Padding"],
    "Margin": _COMMON["Margin"],
    "Opacity": _COMMON["Opacity"],
    "Elevation": _k("shadows", "elevation"),
    "Shadows": _k("shadows", "shadows"),
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
    **_MOTION,
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
    **_MOTION,
    "Fill": _k("fill", "color"),
    "Border_Width": _k("stroke_width", "number"),
    "Border_Color": _k("stroke_color", "color"),
    "Corner_Radius": _k("corner_radius", "radius"),
    "Margin": _COMMON["Margin"],
    "Opacity": _COMMON["Opacity"],
    "Elevation": _k("shadows", "elevation"),
    "Shadows": _k("shadows", "shadows"),
}

# a Circle or a Ring is sized by ``Diameter``: the block takes no Width or Height. A shape's keys
# are the fill and the border of a path; the stroke is centred on the outline
_COMMON_NO_SIZE: dict[str, KeyRow] = {
    k: v for k, v in _COMMON.items() if k not in ("Width", "Height")
}
_CIRCLE: dict[str, KeyRow] = {
    **_MOTION,
    "Fill": _k("fill", "color"),
    "Border_Width": _k("stroke_width", "number"),
    "Border_Color": _k("stroke_color", "color"),
    "Margin": _COMMON["Margin"],
    "Opacity": _COMMON["Opacity"],
}
_RING: dict[str, KeyRow] = {k: v for k, v in _CIRCLE.items() if k != "Fill"}

_ROWS: dict[str, BlockRow] = {
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
            "Selectable": _k("selectable", "bool"),
            "Wrap": _k("wrap", "enum", "WORD", "NONE"),
            "Max_Lines": _k("max_lines", "max_length"),
        },
        style=_TEXT_STYLE,
        defaults={"text": ""},
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
        style={**_MOTION, "Foreground": _k("svg_color", "color"), "Opacity": _COMMON["Opacity"]},
        required=(("Source", "Icon"),),
    ),
    # an image: tre takes pixels, so ``Source`` is a file the shell decodes (``binder.images``);
    # tre sizes an image by its ``width`` and ``height`` only (it has no natural size), so a Fit of
    # NONE sizes it by its pixels (``binder.shapes``)
    "Bitmap": BlockRow(
        "image",
        keys={
            **_COMMON,
            "Source": _k(("rgba", "pixel_width", "pixel_height"), "image"),
            "Fit": _k("fit", "fit", "FILL", "CONTAIN", "COVER", "NONE"),
        },
        style={**_MOTION, "Opacity": _COMMON["Opacity"]},
        required=("Source",),
        defaults={"fit": "contain"},
        post="bitmap",
    ),
    # the shapes are tre paths whose data the shell writes from ``Diameter`` and the border; their
    # hit shape is what is painted (Block Reference > Shapes)
    "Circle": BlockRow(
        "path",
        keys={**_COMMON_NO_SIZE, "Diameter": _k(("width", "height"), "diameter"), **_CIRCLE},
        style=_CIRCLE,
        required=("Diameter",),
        defaults={"hit_shape": "painted"},
        post="circle",
    ),
    "Ring": BlockRow(
        "path",
        keys={**_COMMON_NO_SIZE, "Diameter": _k(("width", "height"), "diameter"), **_RING},
        style=_RING,
        required=("Diameter",),
        defaults={"hit_shape": "painted", "stroke_width": 2},
        fixed={"fill": (0, 0, 0, 0)},
        post="ring",
    ),
    "Path": BlockRow(
        "path",
        keys={
            **_COMMON,
            **_CIRCLE,
            "Data": _k("data", "text"),
            "View_Box": _k("view_box", "view_box"),
            "Trim_Start": _k("trim_start", "unit"),
            "Trim_End": _k("trim_end", "unit"),
            "Hit_Shape": _k("hit_shape", "enum", "PAINTED", "BOX"),
        },
        style=_CIRCLE,
        required=("Data",),
        defaults={"hit_shape": "painted"},
    ),
    # a Marquee is two nodes (``model.marquee``): a box that clips, and the text it moves
    "Marquee": BlockRow(
        "box",
        keys={
            **_COMMON,
            "Speed": _k((), "positive"),
            "Pause": _k((), "pause"),
            "Direction": _k((), "enum", "LEFT", "RIGHT"),
            "Loop": _k((), "enum", "RESTART", "BOUNCE"),
            "Animated": _k((), "bool"),
        },
        style={"Opacity": _COMMON["Opacity"], **_MOTION},
        # the box may be narrower than its text (it clips and the text scrolls)
        defaults={"clip_children": True, "min_width": 0},
        children_ok=True,
    ),
    "Marquee.text": BlockRow(
        "text",
        keys={"Text": _k("text", "text")},
        style={
            k: v
            for k, v in _TEXT_STYLE.items()
            if k not in ("Overflow", "Padding", "Text_Align", *_MOTION)
        },
        fixed={"wrap": "none", "flex_shrink": 0, "overflow": "clip"},
        defaults={"text": ""},
    ),
}

# A TextField is four tre nodes (the model splits the block before binding, ``model.field``): the
# box paints the background and the border and holds the padding; the line box sits in its cell
# (centred, or filling it for a multi-line field); the text node in the line gives it the height of
# the field's lines (a text input has no height of its own); the text input, over the line, edits.
# The text input and the text node take the same font, so they agree on the height of a line.
_FONT: dict[str, KeyRow] = {
    "Font_Family": _TEXT_STYLE["Font_Family"],
    "Font_Size": _TEXT_STYLE["Font_Size"],
    "Font_Weight": _TEXT_STYLE["Font_Weight"],
}
_FIELD_BOX_KEYS: dict[str, KeyRow] = {k: v for k, v in _COMMON.items() if k != "Label"}
_FIELD_CHILD = {"grid_column": 1, "grid_row": 1}
_ROWS["TextField"] = BlockRow(
    "box",
    keys={**_FIELD_BOX_KEYS, **_PADDING},
    style=_BOX_STYLE,
    fixed={"display": "grid", "grid_template_columns": "1fr", "grid_template_rows": "1fr"},
    # a field with no Width is as wide as a field usually is; tre lays an unset width out at 0
    defaults={"width": 200},
    child_props=_FIELD_CHILD,
    children_ok=True,
)
_ROWS["TextField.line"] = BlockRow(
    "box",
    keys={"Align_Self": _COMMON["Align_Self"]},
    style={},
    children_ok=True,
)
_ROWS["TextField.size"] = BlockRow(
    "text",
    keys={"Lines": _k("text", "lines")},
    style=_FONT,
    fixed={
        "fill": (0, 0, 0, 0),
        "hit_testable": False,
        "a11y_hidden": True,
        "wrap": "none",
        "overflow": "clip",
    },
    defaults={"text": "x"},
)
_ROWS["TextField.input"] = BlockRow(
    "text_input",
    # over the line box, exactly as large: it is not in the flow, so the size text sets the height
    fixed={"position": "absolute", "left": 0, "top": 0, "right": 0, "bottom": 0},
    keys={
        "Text": _k("text", "text"),
        "Placeholder": _k("placeholder", "text"),
        "Multiline": _k("multiline", "bool"),
        "Selection": _k("selection", "selection"),
        "Show_Whitespace": _k("show_whitespace", "bool"),
        "Wrap": _k("wrap", "enum", "WORD", "NONE"),
        "Read_Only": _k("read_only", "bool"),
        "Max_Length": _k("max_length", "max_length"),
        "Password": _k("obscured", "bool"),
        "Label": _COMMON["Label"],
    },
    style={
        "Foreground": _TEXT_STYLE["Foreground"],
        **_FONT,
        "Overflow": _k("overflow", "enum", "SCROLL", "ELLIPSIS", "CLIP"),
        "Placeholder_Foreground": _k("placeholder_fill", "color"),
    },
    defaults={
        "text": "",
        "placeholder": "",
        "multiline": False,
        "show_whitespace": False,
        "read_only": False,
        "max_length": None,
        "obscured": False,
    },
)

# every node is built with ``disabled`` set, so a reload that drops ``Enabled: false`` sets it back
# in place instead of replacing the node (tre cannot unset a property)
BLOCKS: Mapping[str, BlockRow] = {
    name: dataclasses.replace(row, defaults={"disabled": False, **row.defaults})
    for name, row in _ROWS.items()
}
