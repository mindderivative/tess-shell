"""The keys and value kinds of the M1 blocks, as the schema checks them (ADR-0020).

A *kind* names how a written value is read (see :mod:`tess_shell.schema.values`); it is the same
word as the binder's converter for that key. ``tests/test_schema_blocks.py`` compares this
declaration with the binder's tables, so the two cannot drift.
"""

from __future__ import annotations

ALIGN = ("START", "CENTER", "END", "STRETCH")
JUSTIFY = ("START", "CENTER", "END", "SPACE_BETWEEN", "SPACE_AROUND", "SPACE_EVENLY")

# key -> kind
COMMON: dict[str, str] = {
    "Visible": "bool",
    "Width": "length",
    "Height": "length",
    "Min_Width": "bound",
    "Min_Height": "bound",
    "Max_Width": "bound",
    "Max_Height": "bound",
    "Aspect_Ratio": "positive",
    "Margin": "sides",
    "Flex_Grow": "number",
    "Flex_Shrink": "number",
    "Align_Self": "enum",
    "Z_Index": "whole",
    "Label": "text",
    "A11y_Hidden": "bool",
    "Opacity": "number",
}

BOX_STYLE: dict[str, str] = {
    "Background": "color",
    "Border_Width": "number",
    "Border_Color": "color",
    "Corner_Radius": "radius",
    "Padding": "sides",
    "Margin": "sides",
    "Opacity": "number",
}

FLEX: dict[str, str] = {
    "Flex": "enum",
    "Wrap": "wrap_flag",
    "Align_Items": "enum",
    "Justify_Content": "enum",
    "Spacing": "number",
}

TEXT_STYLE: dict[str, str] = {
    "Foreground": "color",
    "Font_Family": "font_family",
    "Font_Size": "positive",
    "Font_Weight": "whole",
    "Line_Height": "positive",
    "Text_Align": "enum",
    "Overflow": "enum",
    "Padding": "sides",
    "Margin": "sides",
    "Opacity": "number",
}

SHAPE: dict[str, str] = {
    "Fill": "color",
    "Border_Width": "number",
    "Border_Color": "color",
    "Corner_Radius": "radius",
    "Margin": "sides",
    "Opacity": "number",
}

# (block, key) -> allowed words, for enum keys; a key not listed here is checked per block
CHOICES: dict[tuple[str, str], tuple[str, ...]] = {
    ("*", "Align_Self"): ALIGN,
    ("FlexBox", "Flex"): ("HORIZONTAL", "VERTICAL"),
    ("FlexBox", "Align_Items"): ALIGN,
    ("FlexBox", "Justify_Content"): JUSTIFY,
    ("Text", "Wrap"): ("WORD", "NONE"),
    ("Text", "Text_Align"): ("START", "CENTER", "END"),
    ("Text", "Overflow"): ("CLIP", "ELLIPSIS"),
}

# block -> (property keys, style keys); a style key is also accepted written on the block
BLOCKS: dict[str, tuple[dict[str, str], dict[str, str]]] = {
    "Box": ({**COMMON, "Padding": "sides"}, BOX_STYLE),
    "FlexBox": (
        {**COMMON, **FLEX, "Padding": "sides"},
        {**BOX_STYLE, "Spacing": "number"},
    ),
    "Text": (
        {
            **COMMON,
            "Padding": "sides",
            "Width": "text_length",
            "Height": "text_length",
            "Text": "text",
            "Wrap": "enum",
            "Max_Lines": "whole",
        },
        TEXT_STYLE,
    ),
    "Rectangle": ({**COMMON, **SHAPE}, SHAPE),
    "Spacer": (COMMON, {}),
    "SVG": (
        {**COMMON, "Source": "svg_source", "Color": "color"},
        {"Foreground": "color", "Opacity": "number"},
    ),
}

REQUIRED: dict[str, tuple[str, ...]] = {"SVG": ("Source",)}

# Surface keys of a Bar that M1 reads but does not build: accepted with a warning.
BAR_NOT_BUILT = (
    "Exclusive_Zone",
    "Keyboard",
    "Input_Region",
    "Auto_Hide",
    "Auto_Hide_Delay",
    "Reveal_Key",
    "Visible",
    "Attach_To",
    "Meld",
    "Animation",
    "Text_Rotation",
    "Padding",
    "Class",
)
BAR_STYLE: dict[str, str] = {"Background": "color", "Fill": "color", "Opacity": "number"}
OTHER_SURFACES = ("Frame", "Panel", "Popup")
