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
    "Elevation": "elevation",
    "Shadows": "shadows",
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
    "Elevation": "elevation",
    "Shadows": "shadows",
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
        {**COMMON, "Source": "svg_source", "Icon": "icon", "Color": "color"},
        {"Foreground": "color", "Opacity": "number"},
    ),
}

REQUIRED: dict[str, tuple[str | tuple[str, ...], ...]] = {"SVG": (("Source", "Icon"),)}

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
BAR_STYLE: dict[str, str] = {
    "Background": "color",
    "Fill": "color",
    "Opacity": "number",
    "Elevation": "elevation",
    "Shadows": "shadows",
    "Shadow_Bleed": "bleed",
}

# A Frame's keys and kinds (Frame > Configuration). ``Thickness`` and ``Margin`` are also blocks of
# named sides, the borders are blocks. Keys that ask for something not built are errors, so a
# Frame never opens as something it was not asked to be.
FRAME_KEYS: dict[str, str] = {
    "Layer": "enum",
    "Thickness": "sides",
    "Margin": "sides",
    "Corner_Radius": "radius",
    "Inner_Radius": "radius",
    "Visible": "bool",
    "Padding": "sides",
    # the painter's keyboard mode (opt-in): EXCLUSIVE would take every key of the desktop, so
    # only NONE and ON_DEMAND (the compositor gives the painter focus on a click) are offered
    "Keyboard": "enum",
}
FRAME_CHOICES: dict[str, tuple[str, ...]] = {
    "Layer": ("TOP",),
    "Keyboard": ("NONE", "ON_DEMAND"),
}
FRAME_NOT_BUILT_ERROR = (
    "Children",
    "Border_Tile",
    "Meld",
    "Exclusive_Zone",
    "Input_Region",
)
FRAME_NOT_BUILT_WARNING = ("Class",)
# an ``Edges`` entry: its own thickness, padding and the strip's children
EDGE_SIDES = ("Left", "Top", "Right", "Bottom")
EDGE_KEYS: dict[str, str] = {"Thickness": "number", "Padding": "sides"}
FRAME_BORDER_KEYS = ("Width", "Color")
# A Frame's inline Style: the background, the shorthand for the inner border (``Border_Width``,
# ``Border_Color`` or a ``Border { Width, Color }`` block, D78) and the opacity. Shadows are
# accepted by the table so that they are reported as not built, not as unknown.
FRAME_STYLE: dict[str, str] = {
    "Background": "color",
    "Border_Width": "number",
    "Border_Color": "color",
    "Opacity": "number",
    "Elevation": "elevation",
    "Shadows": "shadows",
    "Shadow_Bleed": "bleed",
}
FRAME_STYLE_NOT_BUILT = ("Elevation", "Shadows", "Shadow_Bleed")


# The twelve v1 events (Events and Actions), as the TDL keys. A block raises only the events its
# pointer or focus handling supports: M1's blocks take a click and nothing else; the rest wait for
# the surfaces and the value blocks that raise them.
EVENT_KEYS = (
    "On_Open",
    "On_Close",
    "On_Visible",
    "On_Hidden",
    "On_Focus",
    "On_Unfocus",
    "On_Toggle",
    "On_Click",
    "On_Anim_Start",
    "On_Anim_End",
    "On_Changed",
    "On_Change",
)
# A tre text node takes no listener of its own (a click on it reaches the nearest box above it,
# measured on tre 0.6.1), so a Text raises nothing: put the handler on the box around it.
BLOCK_EVENTS: dict[str, tuple[str, ...]] = {
    kind: ("On_Click",) for kind in ("Box", "FlexBox", "Rectangle", "Spacer", "SVG")
}
BLOCK_EVENTS["Panel"] = (
    "On_Open",
    "On_Close",
    "On_Visible",
    "On_Hidden",
    "On_Toggle",
    "On_Anim_Start",
    "On_Anim_End",
)
# the shell's own actions (Events and Actions > A Handler); built with the Panel
BUILTIN_ACTIONS = ("Show", "Hide", "Toggle", "Close", "Call")
BUILTIN_BUILT = ("Show", "Hide", "Toggle", "Close")  # Call is not built yet

# A Panel's keys and kinds (Panel > Configuration); the placement keys the shell does not build
# yet are errors, so a Panel never opens somewhere it was not asked to.
PANEL_KEYS: dict[str, str] = {
    "Layer": "enum",
    "Anchor": "anchor",
    "Inset": "sides",
    "Width": "length",
    "Height": "length",
    "Keyboard": "enum",
    "Input_Region": "input",
    "Visible": "bool",
    "Hide_After": "number",
    "Attach": "enum",
    "Gap": "number",
    "Alignment": "enum",
    "Movable": "bool",
    "Meld": "bool",
    # a melded Panel's size: ``Depth`` perpendicular to the Frame's edge, ``Length`` along it
    "Depth": "length",
    "Length": "length",
}
PANEL_CHOICES: dict[str, tuple[str, ...]] = {
    "Layer": ("BOTTOM", "TOP", "OVERLAY"),
    "Keyboard": ("NONE", "ON_DEMAND", "EXCLUSIVE"),
    "Attach": ("LEFT", "RIGHT", "TOP", "BOTTOM"),
    "Alignment": ("START", "CENTER", "END"),
}
# keys that only mean something with Attach_To, and keys that Attach_To replaces
PANEL_ATTACH_KEYS = ("Attach", "Gap", "Alignment")
PANEL_PLACED_KEYS = ("Anchor", "Inset")
PANEL_NOT_BUILT_ERROR = (
    "Open_With_Target",
    "Exclusive_Zone",
)
# keys of a Panel with ``Meld: true`` (hosted in its Frame's surface) that are not built
PANEL_MELD_NOT_BUILT = ("Movable", "Keyboard", "Input_Region")
# style keys a melded Panel does not use: it is drawn in the Frame's colour and border
PANEL_MELD_IGNORED_STYLE = (
    "Background",
    "Fill",
    "Opacity",
    "Elevation",
    "Shadows",
    "Shadow_Bleed",
    "Border_Width",
    "Border_Color",
)
PANEL_NOT_BUILT_WARNING = ("Margin", "Padding", "Class")
# ``Animation { Type, Duration }`` (Panel > Configuration): how a Panel comes and goes
PANEL_ANIMATION_TYPES = ("SLIDE", "FADE", "NONE")
# the events a Panel raises itself (Events and Actions): before and after its show and hide
PANEL_EVENTS = (
    "On_Open",
    "On_Close",
    "On_Visible",
    "On_Hidden",
    "On_Toggle",
    "On_Anim_Start",
    "On_Anim_End",
)

# A Panel's inline Style: the Bar's keys plus the corner radius and the border of its body
PANEL_STYLE: dict[str, str] = {
    **BAR_STYLE,
    "Corner_Radius": "radius",
    "Border_Width": "number",
    "Border_Color": "color",
}

# A Popup's keys and kinds (Popup > Configuration). ``Attach_To`` (a popup opened with no module
# caller) and ``Animation`` are not built; ``Tooltip`` on a Popup is a flag (a block's ``Tooltip``
# is a Popup block or a Popup's name, read by the schema).
POPUP_KEYS: dict[str, str] = {
    "Attach": "enum",
    "Alignment": "enum",
    "Gap": "number",
    "Adjust": "adjust",
    "Width": "length",
    "Height": "length",
    "Max_Width": "bound",
    "Max_Height": "bound",
    "Focus": "bool",
    "Tooltip": "bool",
    "Open_On_Enter": "bool",
    "Enter_Delay": "number",
    "Close_On_Exit": "bool",
    "Exit_Delay": "number",
}
POPUP_CHOICES: dict[str, tuple[str, ...]] = {
    "Attach": ("LEFT", "RIGHT", "TOP", "BOTTOM"),
    "Alignment": ("START", "CENTER", "END"),
}
POPUP_ADJUST = ("FLIP_X", "FLIP_Y", "SLIDE_X", "SLIDE_Y", "RESIZE_X", "RESIZE_Y")
POPUP_NOT_BUILT = ("Attach_To", "Animation")
# a Popup's body takes the Panel's inline Style keys
POPUP_STYLE: dict[str, str] = PANEL_STYLE
