"""The keys and value kinds of the M1 blocks, as the schema checks them (ADR-0020).

A *kind* names how a written value is read (see :mod:`tess_shell.schema.values`); it is the same
word as the binder's converter for that key. ``tests/test_schema_blocks.py`` compares this
declaration with the binder's tables, so the two cannot drift.
"""

from __future__ import annotations

from tess_shell.binder.model import FIELD, FIELD_INPUT, FIELD_LINE, FIELD_SIZE, MARQUEE_TEXT

ALIGN = ("START", "CENTER", "END", "STRETCH")
JUSTIFY = ("START", "CENTER", "END", "SPACE_BETWEEN", "SPACE_AROUND", "SPACE_EVENLY")
# the accessibility roles tre knows (its node reference); the Block Reference lists the common ones
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

A11Y_STATE: dict[str, str] = {
    "Value": "a11y_value",
    "Value_Min": "number",
    "Value_Max": "number",
    "Value_Step": "number",
    "Checked": "bool",
    "Selected": "bool",
    "Expanded": "bool",
}
# key -> kind
COMMON: dict[str, str] = {
    "Visible": "bool",
    "Enabled": "enabled",
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
    # placement and transform (Block Reference > Size, Placement and Order, Transform and Clip)
    "Position": "enum",
    "Left": "length",
    "Top": "length",
    "Right": "length",
    "Bottom": "length",
    "Translate_X": "number",
    "Translate_Y": "number",
    "Scale": "positive",
    "Rotation": "number",
    "Clip_Children": "bool",
    # accessibility (Block Reference > Accessibility; Accessibility > Rules)
    "Role": "enum",
    "Description": "text",
    "Live": "enum",
    # the state a module sets on the block that has it (Block Reference > Accessibility: "set by
    # the block that has them, not written by the author"): a shell file may not write these
    **A11Y_STATE,
}

# the motion keys (Style Schema > Style Keys, Motion): a change of one of the ``Transition`` keys
# animates over ``Duration`` with ``Easing``
MOTION_STYLE: dict[str, str] = {
    "Transition": "transition",
    "Duration": "duration",
    "Easing": "enum",
}

BOX_STYLE: dict[str, str] = {
    **MOTION_STYLE,
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
    **MOTION_STYLE,
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
    **MOTION_STYLE,
    "Fill": "color",
    "Border_Width": "number",
    "Border_Color": "color",
    "Corner_Radius": "radius",
    "Margin": "sides",
    "Opacity": "number",
    "Elevation": "elevation",
    "Shadows": "shadows",
}

# the type keys of a Marquee's text (it is one line, cut or scrolled, and has no padding of its own)
MARQUEE_TEXT_STYLE: dict[str, str] = {
    k: v
    for k, v in TEXT_STYLE.items()
    if k not in ("Overflow", "Padding", "Text_Align", *MOTION_STYLE)
}

# a Circle or a Ring takes its size from ``Diameter``, so Width and Height are not its keys
COMMON_NO_SIZE: dict[str, str] = {k: v for k, v in COMMON.items() if k not in ("Width", "Height")}
CIRCLE_STYLE: dict[str, str] = {
    **MOTION_STYLE,
    "Fill": "color",
    "Border_Width": "number",
    "Border_Color": "color",
    "Margin": "sides",
    "Opacity": "number",
}
# a Ring is a Circle with no fill: its thickness is ``Border_Width``
RING_STYLE: dict[str, str] = {k: v for k, v in CIRCLE_STYLE.items() if k != "Fill"}

# (block, key) -> allowed words, for enum keys; a key not listed here is checked per block
CHOICES: dict[tuple[str, str], tuple[str, ...]] = {
    ("*", "Align_Self"): ALIGN,
    ("FlexBox", "Flex"): ("HORIZONTAL", "VERTICAL"),
    ("FlexBox", "Align_Items"): ALIGN,
    ("FlexBox", "Justify_Content"): JUSTIFY,
    ("Text", "Wrap"): ("WORD", "NONE"),
    ("Text", "Text_Align"): ("START", "CENTER", "END"),
    ("Text", "Overflow"): ("CLIP", "ELLIPSIS"),
    # a TextField: ``Wrap`` is for a multi-line field and ``Overflow`` for a single-line one
    # (``Wrap: CHAR`` is not built, ``TextField.input`` is the text input inside the composition)
    ("TextField", "Wrap"): ("WORD", "NONE"),
    ("TextField", "Overflow"): ("SCROLL", "ELLIPSIS", "CLIP"),
    ("TextField.input", "Wrap"): ("WORD", "NONE"),
    ("TextField.input", "Overflow"): ("SCROLL", "ELLIPSIS", "CLIP"),
    # a stylesheet rule's value is checked against every block that takes the key; a block takes
    # the words of its own row (a Text has no SCROLL: the fold skips the rule there)
    ("Rule", "Overflow"): ("CLIP", "ELLIPSIS", "SCROLL"),
    ("*", "Position"): ("RELATIVE", "ABSOLUTE"),
    ("*", "Role"): ROLES,
    ("*", "Live"): ("POLITE", "ASSERTIVE"),
    ("*", "Easing"): EASINGS,
    ("Bitmap", "Fit"): ("FILL", "CONTAIN", "COVER", "NONE"),
    ("Path", "Hit_Shape"): ("PAINTED", "BOX"),
    ("Marquee", "Direction"): ("LEFT", "RIGHT"),
    ("Marquee", "Loop"): ("RESTART", "BOUNCE"),
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
            "Selectable": "bool",
            "Wrap": "enum",
            "Max_Lines": "max_length",
        },
        TEXT_STYLE,
    ),
    "Rectangle": ({**COMMON, **SHAPE}, SHAPE),
    "Spacer": (COMMON, {}),
    "SVG": (
        {**COMMON, "Source": "svg_source", "Icon": "icon", "Color": "color"},
        {**MOTION_STYLE, "Foreground": "color", "Opacity": "number"},
    ),
    # Graphics (Block Reference > Bitmap, Shapes): a bitmap's pixels come from a file the shell
    # decodes; the shapes are tre paths, hit where they are painted
    "Bitmap": (
        {**COMMON, "Source": "image", "Fit": "fit"},
        {**MOTION_STYLE, "Opacity": "number"},
    ),
    "Circle": ({**COMMON_NO_SIZE, "Diameter": "diameter", **CIRCLE_STYLE}, CIRCLE_STYLE),
    "Ring": ({**COMMON_NO_SIZE, "Diameter": "diameter", **RING_STYLE}, RING_STYLE),
    "Path": (
        {
            **COMMON,
            **CIRCLE_STYLE,
            "Data": "text",
            "View_Box": "view_box",
            "Trim_Start": "unit",
            "Trim_End": "unit",
            "Hit_Shape": "enum",
        },
        CIRCLE_STYLE,
    ),
    # a long text that scrolls when it is wider than its box (Standard Modules > Marquee text);
    # ``model.field.compose_marquee`` splits it into a clipping box and the text it moves
    "Marquee": (
        {
            **COMMON,
            "Text": "text",
            "Speed": "positive",
            "Pause": "pause",
            "Direction": "enum",
            "Loop": "enum",
            "Animated": "bool",
        },
        {**MARQUEE_TEXT_STYLE, "Opacity": "number", **MOTION_STYLE},
    ),
    "TextField": (
        {
            **COMMON,
            "Padding": "sides",
            "Text": "text",
            "Placeholder": "text",
            "Multiline": "bool",
            "Selection": "selection",
            "Show_Whitespace": "bool",
            "Wrap": "enum",
            "Lines": "lines",
            "Read_Only": "bool",
            "Max_Length": "max_length",
            "Password": "bool",
        },
        {
            **BOX_STYLE,
            "Foreground": "color",
            "Font_Family": "font_family",
            "Font_Size": "positive",
            "Font_Weight": "whole",
            "Overflow": "enum",
            "Placeholder_Foreground": "color",
        },
    ),
}

# A TextField is a composition (tre's advice for a field): a box that paints the background and
# the border, around a text input, with a text node that gives the box the height of its lines.
# ``model.field.compose`` splits the block into these typed nodes before binding (the box, a line
# box in its cell that holds the size text and, over it, the text input); they are the kinds the
# binder builds and the model addresses slots to. The words have a dot, so no file can name one.
FIELD_BOX_KEYS = frozenset(
    {*COMMON, "Padding", *BOX_STYLE} - {"Label"},
)
FIELD_INPUT_KEYS = frozenset(
    {
        "Text",
        "Placeholder",
        "Multiline",
        "Selection",
        "Show_Whitespace",
        "Wrap",
        "Read_Only",
        "Max_Length",
        "Password",
        "Label",
        "Foreground",
        "Font_Family",
        "Font_Size",
        "Font_Weight",
        "Overflow",
        "Placeholder_Foreground",
    }
)
FIELD_SIZE_KEYS = frozenset({"Lines", "Font_Family", "Font_Size", "Font_Weight"})
FIELD_EVENTS = ("On_Changed", "On_Submit", "On_Text_Commit")
_FIELD_INPUT_PROPS: dict[str, str] = {
    "Text": "text",
    "Placeholder": "text",
    "Multiline": "bool",
    "Selection": "selection",
    "Show_Whitespace": "bool",
    "Wrap": "enum",
    "Read_Only": "bool",
    "Max_Length": "max_length",
    "Password": "bool",
    "Label": "text",
}
_FIELD_INPUT_STYLE: dict[str, str] = {
    "Foreground": "color",
    "Font_Family": "font_family",
    "Font_Size": "positive",
    "Font_Weight": "whole",
    "Overflow": "enum",
    "Placeholder_Foreground": "color",
}
_FIELD_BOX_PROPS: dict[str, str] = {
    k: v for k, v in {**COMMON, "Padding": "sides"}.items() if k != "Label"
}
# the kinds the model and the binder meet after the composition: key tables per kind
INTERNAL: dict[str, tuple[dict[str, str], dict[str, str]]] = {
    FIELD_LINE: ({"Align_Self": "enum"}, {}),
    FIELD_SIZE: (
        {"Lines": "lines"},
        {"Font_Family": "font_family", "Font_Size": "positive", "Font_Weight": "whole"},
    ),
    FIELD_INPUT: (_FIELD_INPUT_PROPS, _FIELD_INPUT_STYLE),
    # a Marquee is its clipping box and the text it moves (``model.marquee``)
    MARQUEE_TEXT: (
        {"Text": "text"},
        MARQUEE_TEXT_STYLE,
    ),
}
# the key tables of the box of a composed Marquee (kind ``Marquee`` after the split)
MARQUEE_BOX: tuple[dict[str, str], dict[str, str]] = (
    {
        **COMMON,
        "Speed": "positive",
        "Pause": "pause",
        "Direction": "enum",
        "Loop": "enum",
        "Animated": "bool",
    },
    {"Opacity": "number", **MOTION_STYLE},
)
# the key tables of the box of a composed TextField (kind ``TextField`` after the split)
FIELD_BOX: tuple[dict[str, str], dict[str, str]] = (_FIELD_BOX_PROPS, BOX_STYLE)


def table(kind: str) -> tuple[dict[str, str], dict[str, str]] | None:
    """The (property keys, style keys) of a block, or of an internal kind of the TextField or
    the Marquee."""
    return BLOCKS.get(kind) or INTERNAL.get(kind)


REQUIRED: dict[str, tuple[str | tuple[str, ...], ...]] = {
    "SVG": (("Source", "Icon"),),
    "Bitmap": ("Source",),
    "Circle": ("Diameter",),
    "Ring": ("Diameter",),
    "Path": ("Data",),
}

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


# The v1 events (Events and Actions; the text field's ``On_Submit`` and ``On_Text_Commit``, D80, are
# in Block Reference > TextField), as the TDL keys. A block raises only the events its
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
    "On_Submit",
    "On_Text_Commit",
)
# A tre text node takes no listener of its own (a click on it reaches the nearest box above it,
# measured on tre 0.6.1), so a Text raises nothing: put the handler on the box around it.
BLOCK_EVENTS: dict[str, tuple[str, ...]] = {
    kind: ("On_Click",)
    for kind in ("Box", "FlexBox", "Rectangle", "Spacer", "SVG", "Bitmap", "Circle", "Ring", "Path")
    + ("Marquee",)
}
# the text events are raised by the text input inside the composition; ``On_Click`` by its box
BLOCK_EVENTS[FIELD] = ("On_Click", *FIELD_EVENTS)
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
BUILTIN_BUILT = ("Show", "Hide", "Toggle", "Close", "Call")

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
# ``Peek { Size, Enter_Delay, Exit_Delay, Trigger, Handle, Slide_From }`` (Frame > Peek Triggers and
# Handles): what opens a peek, the icon on its tab and, for a Panel in a Frame corner, its edge
PEEK_TRIGGERS = ("HOVER", "CLICK", "DRAG")
PEEK_HANDLES = ("AUTO", "NONE", "DOTS", "BAR", "CHEVRON")
PEEK_EDGES = ("TOP", "RIGHT", "BOTTOM", "LEFT")
# the second edge a melded Panel touches in a corner: (``Attach``, ``Alignment``) -> edge. A Panel
# aligned CENTER touches one edge only
PEEK_CORNER_EDGE = {
    ("TOP", "START"): "LEFT",
    ("TOP", "END"): "RIGHT",
    ("BOTTOM", "START"): "LEFT",
    ("BOTTOM", "END"): "RIGHT",
    ("LEFT", "START"): "TOP",
    ("LEFT", "END"): "BOTTOM",
    ("RIGHT", "START"): "TOP",
    ("RIGHT", "END"): "BOTTOM",
}
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
