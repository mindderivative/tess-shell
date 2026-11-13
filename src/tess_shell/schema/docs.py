"""The authored text of the schema export: one line for every key, form groups, units, defaults the
code states only inside the loader, examples (Block Reference, Style Schema, Settings File).

The export (:mod:`tess_shell.schema.export`) walks the tables the loader uses and takes this text
from here; ``tests/test_schema_export.py`` requires a line for every key the loader accepts and
refuses a line for a key nothing accepts, so the two cannot drift. Nothing in this module is read
by the loader.
"""

from __future__ import annotations

# -- keys: one line each; a (spec, key) entry in ``SPEC_DOCS`` says it better for that spec --------

KEY_DOCS: dict[str, str] = {
    # identity and state
    "Name": "The unique name of this block in the shell: letters, digits and _, starting with a "
    "letter. Actions and Attach_To refer to it.",
    "Part": "In a module's layout: names a part of the module that a stylesheet addresses as "
    "Module::part; unique in the module.",
    "Class": "One style class name, or a list of them; the rules of those classes apply to the "
    "block.",
    "Tooltip": "What opens when the pointer rests on the block: the Name of a Popup, a short text "
    "or an inline Tooltip block.",
    "Key": "The name of an entry of a list in a module's layout; an entry of a For has its "
    "repeater's key unless it writes one.",
    "Visible": "False hides the block from everyone, assistive technology included, and it takes "
    "no space.",
    "Enabled": "False disables the block: it ignores input, takes the disabled style state and "
    "is announced as disabled.",
    "Tooltip_When_Disabled": "Lets a disabled block open its tooltip; without it a disabled "
    "block opens none.",
    # size
    "Width": "The width: pixels, a percentage, AUTO (fit the content) or EXPAND (take the free "
    "space).",
    "Height": "The height: pixels, a percentage, AUTO (fit the content) or EXPAND (take the free "
    "space).",
    "Min_Width": "The least width the block may resolve to, in pixels or a percentage.",
    "Min_Height": "The least height the block may resolve to, in pixels or a percentage.",
    "Max_Width": "The greatest width the block may resolve to, in pixels or a percentage.",
    "Max_Height": "The greatest height the block may resolve to, in pixels or a percentage.",
    "Aspect_Ratio": "The width over the height, above 0; the other side follows from it.",
    # placement
    "Margin": "Transparent space around the block: one number or four (left, top, right, bottom).",
    "Padding": "Space between the content and the four sides: one number or four (left, top, "
    "right, bottom).",
    "Position": "RELATIVE lays the block out in its parent; ABSOLUTE takes it out of the layout "
    "and places it by Left, Top, Right and Bottom.",
    "Left": "The inset of an absolute block from its parent's left side.",
    "Top": "The inset of an absolute block from its parent's top side.",
    "Right": "The inset of an absolute block from its parent's right side.",
    "Bottom": "The inset of an absolute block from its parent's bottom side.",
    "Z_Index": "The paint order among siblings; a higher number paints later, on top.",
    "Flex_Grow": "How much of the free space along the parent's flex axis the block takes, "
    "relative to its siblings.",
    "Flex_Shrink": "How much the block gives up, relative to its siblings, when the parent is "
    "too small.",
    "Align_Self": "Where this block sits across its parent's flex axis, replacing the parent's "
    "Align_Items.",
    # transform
    "Translate_X": "Moves the painted block sideways without changing the layout.",
    "Translate_Y": "Moves the painted block up or down without changing the layout.",
    "Scale": "Scales the painted block around its centre; 1 is its own size.",
    "Rotation": "Rotates the painted block, in degrees.",
    "Clip_Children": "Clips the children to the block; the block's own paint is not clipped.",
    # appearance
    "Opacity": "How opaque the block and what it holds is painted, from 0 (invisible) to 1.",
    "Background": "The fill behind the block's content, a colour or a theme token.",
    "Fill": "The fill of the shape, a colour or a theme token.",
    "Foreground": "The colour of the text or of the icon, a colour or a theme token.",
    "Color": "The colour that currentColor takes in the SVG; the Foreground style key sets it "
    "from the theme.",
    "Border_Width": "The width of the border line; 0 draws none.",
    "Border_Color": "The colour of the border line, a colour or a theme token.",
    "Corner_Radius": "The radius of the corners: one number, or four from the top-left corner "
    "clockwise.",
    "Elevation": "How high the block floats, as a percentage of the theme's largest shadow; 0% is "
    "no shadow.",
    "Shadows": "A list of Shadow blocks, the first on top; it replaces Elevation when both are "
    "written.",
    "Shadow_Bleed": "The transparent margin a surface keeps around its body for the shadow: AUTO "
    "computes it from the shadow, or one number or four.",
    # motion
    "Transition": "The keys whose change animates, a key name or a list of them.",
    "Duration": "How long a change of a Transition key takes, in milliseconds.",
    "Easing": "The curve of the animation: STANDARD, EMPHASIZED or LINEAR.",
    # accessibility
    "Role": "What assistive technology announces the block as.",
    "Label": "The name assistive technology reads aloud; a text node's words are not exposed "
    "alone, so the block carries the label.",
    "Description": "A longer description for assistive technology; a text Tooltip is also the "
    "description.",
    "Live": "Announces changes of the block: POLITE waits for a pause, ASSERTIVE interrupts.",
    "A11y_Hidden": "Hides the block from assistive technology while it stays visible.",
    "Value": "The accessible value of a control, a number or a string; set by a module, not "
    "written in a shell file.",
    "Value_Min": "The least value of a control, for assistive technology; set by a module.",
    "Value_Max": "The greatest value of a control, for assistive technology; set by a module.",
    "Value_Step": "The step of a control's value, for assistive technology; set by a module.",
    "Checked": "Whether the block is checked, for a toggle or a checkbox; set by a module.",
    "Selected": "Whether the block is the selected entry of a list; set by a module.",
    "Expanded": "Whether the block's submenu or section is open; set by a module.",
    # controls
    "Toggles": "Makes a click flip Checked and raise On_Changed: the block acts as a toggle or a "
    "checkbox.",
    "Selection_Mode": "SINGLE makes the block's children the entries of a list of which one is "
    "chosen; NONE is a plain block.",
    "Chosen": "The Key of the chosen entry of a list.",
    "Slides": "Makes the block a slider along its axis: HORIZONTAL or VERTICAL; NONE is a plain "
    "block.",
    "Reveals": "Makes the block an expander: OPEN or CLOSED is the state the module wants; the "
    "block raises On_Changed (event.value true or false) when its size has finished easing there. "
    "NONE is a plain block.",
    "Menu_Item": "Makes the block take the pointer as a menu item.",
    "Opens": "The Name of the Popup this menu item opens as its submenu; empty opens nothing.",
    # flex
    "Flex": "How the children are stacked: HORIZONTAL (a row) or VERTICAL (a column).",
    "Wrap": "Wraps the children onto further lines.",
    "Align_Items": "Where the children sit across the stacking direction.",
    "Justify_Content": "How the children share the space along the stacking direction.",
    "Spacing": "The space between the children, in pixels.",
    # text
    "Text": "The words; may hold {{ }} slots in a module.",
    "Selectable": "Lets the user select the text.",
    "Max_Lines": "Cuts the text after this many lines; 0 is no limit.",
    "Font_Family": "A font family name, or a list of them in the order of fallback.",
    "Font_Size": "The size of the type, above 0.",
    "Font_Weight": "The weight of the type as a whole number, 400 regular, 700 bold.",
    "Line_Height": "The height of one line, above 0.",
    "Text_Align": "How a line sits in the text's box: START, CENTER or END.",
    "Overflow": "What happens to text that does not fit: CLIP cuts it, ELLIPSIS ends it with "
    "dots (a TextField also has SCROLL).",
    # text field
    "Placeholder": "The text shown while the field is empty.",
    "Placeholder_Foreground": "The colour of the placeholder text.",
    "Multiline": "Makes the field several lines; Enter then inserts a new line.",
    "Selection": "The selected text as [start, end], in byte offsets.",
    "Show_Whitespace": "Draws marks for spaces and tabs, for a code editor.",
    "Lines": "How many lines high a multi-line field is, 1 or more.",
    "Read_Only": "The text can be selected and copied but not changed.",
    "Max_Length": "The most characters the field takes; 0 is no limit.",
    "Password": "Hides the characters as dots in a single-line field.",
    # graphics
    "Source": "The file to show, written relative to the file that names it.",
    "Icon": "An icon name such as mdi:account; a prefix selects an icon set. An SVG has a "
    "Source or an Icon, not both.",
    "Fit": "How the image fits its box: FILL stretches it, CONTAIN shows all of it, COVER fills "
    "the box and crops, NONE keeps its size.",
    "Diameter": "The width and the height of the shape, in whole pixels above 0.",
    "Data": "The path in SVG path syntax.",
    "View_Box": "The part of the path's coordinates that is drawn: [min_x, min_y, width, height].",
    "Trim_Start": "Where along the path the line starts, from 0.0 to 1.0.",
    "Trim_End": "Where along the path the line ends, from 0.0 to 1.0.",
    "Hit_Shape": "Where the pointer hits the path: PAINTED only on its paint, BOX anywhere in its "
    "box.",
    # scroll box and marquee
    "Orientation": "The scrolling direction: VERTICAL or HORIZONTAL.",
    "Scroll_Offset": "How far the content is scrolled, in pixels.",
    "Speed": "How fast the text scrolls, in pixels a second, above 0.",
    "Pause": "How long the text waits at each end, in milliseconds.",
    "Direction": "The way the text moves: LEFT shows its start first, RIGHT its end first.",
    "Loop": "RESTART jumps back to the start; BOUNCE scrolls back.",
    "Animated": "False keeps a text that does not fit still, cut with an ellipsis.",
    # surfaces
    "Edge": "The screen edge the Bar attaches to.",
    "Layer": "The layer of the compositor the surface is drawn in.",
    "Alignment": "Where the surface sits along the edge it shares: START, CENTER or END.",
    "Offset": "Moves the Bar along its edge, in pixels, forward or back.",
    "Gap": "The space between the surface and what it is placed against, in pixels.",
    "Reserve": "Whether the Bar keeps its space free of windows (its size across the edge plus "
    "the Gap).",
    "Keyboard": "Whether the surface takes the keyboard: NONE never, ON_DEMAND on a click, "
    "EXCLUSIVE all keys.",
    "Input_Region": "Which part of the surface takes the pointer: [] none (clicks pass through) "
    "or AUTO the drawn shapes; leaving it out is the whole surface.",
    "Exclusive_Zone": "The raw space to reserve, in pixels. Not built.",
    "Auto_Hide": "Slides the Bar out when the pointer leaves it. Not built.",
    "Auto_Hide_Delay": "How long the pointer is away before the Bar hides, in milliseconds. Not "
    "built.",
    "Reveal_Key": "A shortcut that reveals a hidden Bar. Not built.",
    "Text_Rotation": "Rotates the text of a vertical Bar. Not built.",
    "Attach_To": "The Name of the Bar, Panel or Frame this Panel is placed against.",
    "Attach": "The edge of the target the surface meets: LEFT, RIGHT, TOP or BOTTOM.",
    "Meld": "Draws the surface inside its Frame's surface instead of in a window of its own.",
    "Anchor": "The screen edges the Panel is anchored to: one or a list; none is a floating "
    "Panel centred by the compositor.",
    "Inset": "The distance from the anchored edges: one number, four (left, top, right, bottom) "
    "or named sides.",
    "Hide_After": "Hides the Panel after this many milliseconds; showing it again restarts the "
    "time.",
    "Movable": "Lets the pointer move the Panel; its position is saved.",
    "Content_Fade": "Whether the content's opacity follows the slide of the Panel.",
    "Depth": "A melded Panel's extent away from the Frame's edge.",
    "Length": "A melded Panel's extent along the Frame's edge.",
    "Open_With_Target": "Opening the target also opens this Panel. Not built.",
    "Animation": "How the surface comes and goes: an Animation block with Type and Duration.",
    # popup
    "Adjust": "What the compositor may do to keep the popup on screen: one or a list of "
    "FLIP_X, FLIP_Y, SLIDE_X, SLIDE_Y, RESIZE_X, RESIZE_Y; [] asks for nothing.",
    "Focus": "Takes the keyboard and the pointer while open.",
    "Open_On_Enter": "Opens when the pointer enters the block it is the tooltip of.",
    "Enter_Delay": "How long the pointer rests before it opens, in milliseconds.",
    "Close_On_Exit": "Closes when the pointer leaves.",
    "Exit_Delay": "How long the pointer is away before it closes, in milliseconds.",
    # frame
    "Thickness": "The thickness of the Frame's ring: one number, four (left, top, right, bottom) "
    "or named sides.",
    "Inner_Radius": "The radius of the corners of the opening inside the ring: one number or "
    "four from the top-left clockwise.",
    "Inner_Border": "A line along the inside of the ring: a block with Width and Color.",
    "Outer_Border": "A line along the outside of the ring: a block with Width and Color.",
    "Edges": "The sides of the Frame that have their own thickness or are strips: a block with "
    "Left, Top, Right and Bottom.",
    "Border_Tile": "A tiled border image. Not built.",
    "Children": "The blocks inside, in order.",
    # peek
    "Peek": "Makes the Panel or strip rest as a sliver that comes out when asked: a Peek block.",
    "Size": "How many pixels show at rest, 1 or more.",
    "Trigger": "What opens it: HOVER, CLICK or DRAG.",
    "Handle": "The icon on its tab: AUTO, NONE, DOTS, BAR or CHEVRON.",
    "Handle_Opacity": "How bright the handle is at rest, from 0 to 1; hover raises it.",
    "Slide_From": "For a Panel in a Frame corner: the edge it slides out of.",
    # monitor, shell, files
    "Index": "The position of the monitor (0, 1, ...) or default for the ones nothing else names.",
    "Connector": "The connector of the monitor, such as DP-1.",
    "Selector": 'What a rule styles: a block type ("Text"), a class (".warning"), a name '
    '("#clock") or a module ("Slider::track"), with an optional ":state".',
    "Kind": "The block type a class is for.",
    "Type": "The kind of value: string, number, boolean, path or icon.",
    "Default": "The value used when a call gives none.",
    # shadow
    "X": "The shadow's offset to the right, in pixels.",
    "Y": "The shadow's offset downward, in pixels.",
    "Blur": "How far the shadow's edge softens, in pixels, 0 or more.",
    "Spread": "How much the shadow grows beyond the block, in pixels.",
}

# the lines that say it better for one spec: (spec, key) -> line
SPEC_DOCS: dict[tuple[str, str], str] = {
    ("Bar", "Width"): "The Bar's width: pixels, a percentage, AUTO or EXPAND (edge to edge along "
    "the Edge).",
    ("Bar", "Height"): "The Bar's height: pixels, a percentage, AUTO or EXPAND (edge to edge "
    "along the Edge).",
    ("Bar", "Min_Width"): "The least width of the Bar, in pixels.",
    ("Bar", "Min_Height"): "The least height of the Bar, in pixels.",
    ("Bar", "Max_Width"): "The greatest width of the Bar, in pixels.",
    ("Bar", "Max_Height"): "The greatest height of the Bar, in pixels.",
    ("Bar", "Visible"): "Starts the Bar shown or hidden. Not built.",
    ("Bar", "Keyboard"): "Whether the Bar takes the keyboard. Not built.",
    ("Bar", "Input_Region"): "Which part of the Bar takes the pointer. Not built.",
    ("Bar", "Meld"): "Draws the Bar inside its Frame. Not built.",
    ("Bar", "Padding"): "Space between the Bar's children and its sides. Not built.",
    ("Bar", "Class"): "A style class for the Bar. Not built.",
    ("Bar", "Attach_To"): "Attaches the Bar to a Frame. Not built.",
    ("Bar", "Animation"): "How the Bar comes and goes. Not built.",
    ("Bar", "Alignment"): "Where a Bar shorter than the edge sits along it: START, CENTER or "
    "END; no effect on an EXPAND axis.",
    ("Bar", "Gap"): "The space between the screen edge and the Bar, in pixels; the reserved "
    "space includes it.",
    ("Bar", "Layer"): "The layer the Bar is drawn in: BOTTOM, TOP or OVERLAY.",
    ("Bar", "Name"): "The unique name of the Bar; required.",
    ("Panel", "Name"): "The unique name of the Panel; Show, Hide, Toggle and Attach_To use it.",
    ("Panel", "Width"): "The Panel's width in pixels or a percentage; AUTO and EXPAND are not "
    "built. 0 stretches between two opposite anchors.",
    ("Panel", "Height"): "The Panel's height in pixels or a percentage; AUTO and EXPAND are not "
    "built. 0 stretches between two opposite anchors.",
    ("Panel", "Depth"): "The extent of a Panel with Meld: true away from the Frame's edge.",
    ("Panel", "Length"): "The extent of a Panel with Meld: true along the Frame's edge.",
    ("Panel", "Visible"): "Starts the Panel shown (true) or hidden (false).",
    ("Panel", "Layer"): "The layer the Panel is drawn in: BOTTOM, TOP or OVERLAY.",
    ("Panel", "Keyboard"): "Whether the Panel takes the keyboard: NONE never, ON_DEMAND on a "
    "click, EXCLUSIVE all keys.",
    ("Panel", "Gap"): "The space between the Panel and its target, in pixels (with Attach_To).",
    ("Panel", "Alignment"): "How the Panel lines up along the edge it shares with its target: "
    "START, CENTER or END (with Attach_To).",
    ("Panel", "Attach"): "The edge of the target the Panel meets (needs Attach_To).",
    ("Panel", "Margin"): "Space around the Panel. Not built.",
    ("Panel", "Padding"): "Space between the children and the Panel's sides. Not built.",
    ("Panel", "Class"): "A style class for the Panel. Not built.",
    ("Panel", "Exclusive_Zone"): "Space the Panel reserves. Not built.",
    ("Panel", "Peek"): "Makes a melded Panel rest as a tab of Size pixels that comes out when "
    "asked.",
    ("Panel", "Meld"): "True draws the Panel inside the Frame it is attached to; needs "
    "Attach_To a Frame.",
    ("Panel", "Input_Region"): "Which part of the Panel takes the pointer: [] none, AUTO the "
    "drawn shapes; leaving it out is the whole Panel.",
    ("Popup", "Name"): "The unique name of the Popup; Show, Toggle and Tooltip use it.",
    ("Popup", "Width"): "The Popup's width in pixels or AUTO.",
    ("Popup", "Height"): "The Popup's height in pixels or AUTO.",
    ("Popup", "Max_Width"): "The greatest width of the Popup, in pixels.",
    ("Popup", "Max_Height"): "The greatest height of the Popup, in pixels.",
    ("Popup", "Attach"): "The edge of the block it opens from that the Popup meets.",
    ("Popup", "Alignment"): "How the Popup lines up along the edge it shares with the block: "
    "START, CENTER or END.",
    ("Popup", "Gap"): "The space between the block and the Popup, in pixels.",
    ("Popup", "Tooltip"): "Makes the Popup a tooltip: it takes no focus, opens when the pointer "
    "enters the block and closes when it leaves.",
    ("Popup", "Attach_To"): "A Popup opened with no module as the caller. Not built.",
    ("Popup", "Animation"): "How the Popup comes and goes. Not built.",
    ("Frame", "Name"): "The unique name of the Frame; Attach_To of a melded Panel uses it.",
    ("Frame", "Layer"): "The layer the Frame is drawn in; only TOP is built.",
    ("Frame", "Margin"): "Space around the Frame's ring: one number, four or named sides.",
    ("Frame", "Padding"): "Space between a strip's children and its sides, for every strip.",
    ("Frame", "Corner_Radius"): "The radius of the outer corners of the ring: one number or "
    "four from the top-left clockwise.",
    ("Frame", "Visible"): "Starts the Frame shown (true) or hidden (false).",
    ("Frame", "Keyboard"): "Whether the Frame's surface takes the keyboard: NONE or ON_DEMAND.",
    ("Frame", "Children"): "Not built: a Frame holds its blocks in the strips of Edges.",
    ("Frame", "Meld"): "Not built.",
    ("Frame", "Exclusive_Zone"): "Space the Frame reserves. Not built.",
    ("Frame", "Input_Region"): "Which part of the Frame takes the pointer. Not built.",
    ("Frame", "Class"): "A style class for the Frame. Not built.",
    ("Frame", "Background"): "The colour of the ring, a colour or a theme token.",
    ("Frame", "Opacity"): "How opaque the ring is painted, from 0 to 1.",
    ("Frame", "Border_Width"): "The width of the inner border: shorthand for Inner_Border.",
    ("Frame", "Border_Color"): "The colour of the inner border: shorthand for Inner_Border.",
    ("Frame", "Elevation"): "A shadow for the Frame. Not built.",
    ("Frame", "Shadows"): "Shadows for the Frame. Not built.",
    ("Frame", "Shadow_Bleed"): "The margin for a shadow. Not built.",
    ("Edge", "Name"): "The target of Show, Hide and Toggle; only a strip with a Peek has one.",
    ("Edge", "Thickness"): "The thickness of this side's strip in pixels, replacing the "
    "Frame's for this side (the full extent of a strip with a Peek).",
    ("Edge", "Padding"): "Space between the strip's children and its sides, replacing the Frame's.",
    ("Edge", "Content_Fade"): "Whether the strip's children fade with its slide.",
    ("Edge", "Peek"): "Makes the strip rest as a sliver of Size pixels that comes out when "
    "asked; needs Children.",
    ("Edge_Peek", "Size"): "How many pixels of the strip show at rest, 1 or more and below the "
    "strip's thickness.",
    ("Border", "Width"): "The width of the border line, in pixels, 0 or more.",
    ("Border", "Color"): "The colour of the border line, a colour or a theme token.",
    ("Animation", "Type"): "How the Panel comes and goes: SLIDE, FADE or NONE.",
    ("Animation", "Duration"): "How long it takes, in milliseconds; 0 is no animation.",
    ("Panel", "Animation"): "How the Panel comes and goes: an Animation block with Type and "
    "Duration.",
    ("FlexBox", "Wrap"): "Wraps the children onto further lines.",
    ("Text", "Wrap"): "WORD wraps the text at word ends, NONE keeps it on one line.",
    ("TextField", "Wrap"): "WORD or NONE for a multi-line field; has no effect on a single-line "
    "one.",
    ("TextField", "Overflow"): "What a single-line field does with text that does not fit: "
    "SCROLL, ELLIPSIS or CLIP.",
    ("TextField", "Label"): "The name assistive technology reads aloud for the field.",
    ("TextField", "Text"): "The value of the field; edits come out through On_Changed.",
    ("Marquee", "Text"): "The words; they scroll when wider than the box.",
    ("SVG", "Foreground"): "The colour that currentColor takes in the SVG.",
    ("Bitmap", "Source"): "The image file, written relative to the file that names it; the "
    "shell decodes it.",
    ("SVG", "Source"): "The SVG file, written relative to the file that names it.",
    ("Circle", "Fill"): "The fill of the circle, a colour or a theme token.",
    ("Rule", "Selector"): "What the rule styles: a block type, a .class, a #name or a "
    "Module::part, with an optional :state.",
    ("Peek", "Size"): "How many pixels of the Panel show at rest, 1 or more and below its Depth.",
    ("Shadow", "Color"): "The colour of the shadow, with its alpha.",
    ("Sides", "Left"): "The left side; unnamed sides are 0.",
    ("Sides", "Top"): "The top side; unnamed sides are 0.",
    ("Sides", "Right"): "The right side; unnamed sides are 0.",
    ("Sides", "Bottom"): "The bottom side; unnamed sides are 0.",
    ("Monitor", "Description"): "The description of the monitor, as the compositor reports it.",
    ("Class", "Kind"): "The block type this class is for; its style keys are that block's.",
    ("Param", "Type"): "The kind of value the param takes: string, number, boolean, path or icon.",
    ("Param", "Default"): "The value used when a call gives none; a param with none is required.",
    ("Rule", "Opacity"): "How opaque the block is painted, from 0 to 1.",
}
# a key a spec has only as a block's own accessible text
for _spec in ("Box", "FlexBox", "Text", "Rectangle", "ScrollBox", "Spacer", "SVG", "Bitmap"):
    SPEC_DOCS.setdefault((_spec, "Description"), KEY_DOCS["Description"])
del _spec

# -- form groups: how an editor lays the keys out ------------------------------------------------

GROUPS: dict[str, tuple[str, ...]] = {
    "Identity": (
        "Name",
        "Part",
        "Class",
        "Tooltip",
        "Key",
        "Label",
        "Index",
        "Connector",
        "Selector",
        "Kind",
        "Type",
        "Default",
    ),
    "State": ("Visible", "Enabled", "Tooltip_When_Disabled"),
    "Size": (
        "Width",
        "Height",
        "Min_Width",
        "Min_Height",
        "Max_Width",
        "Max_Height",
        "Aspect_Ratio",
        "Diameter",
        "Depth",
        "Length",
        "Size",
        "Thickness",
    ),
    "Placement": (
        "Position",
        "Left",
        "Top",
        "Right",
        "Bottom",
        "Z_Index",
        "Flex_Grow",
        "Flex_Shrink",
        "Align_Self",
        "Margin",
        "Anchor",
        "Inset",
        "Edge",
        "Layer",
        "Alignment",
        "Offset",
        "Gap",
        "Reserve",
        "Attach_To",
        "Attach",
        "Meld",
        "Movable",
        "Slide_From",
        "Exclusive_Zone",
        "Edges",
        "Children",
    ),
    "Layout": (
        "Padding",
        "Flex",
        "Wrap",
        "Align_Items",
        "Justify_Content",
        "Spacing",
        "Orientation",
        "Scroll_Offset",
    ),
    "Transform": ("Translate_X", "Translate_Y", "Scale", "Rotation", "Clip_Children"),
    "Fill": (
        "Background",
        "Fill",
        "Foreground",
        "Color",
        "Opacity",
        "Elevation",
        "Shadows",
        "Shadow_Bleed",
        "Placeholder_Foreground",
        "X",
        "Y",
        "Blur",
        "Spread",
    ),
    "Border": (
        "Border_Width",
        "Border_Color",
        "Corner_Radius",
        "Inner_Radius",
        "Inner_Border",
        "Outer_Border",
        "Border_Tile",
    ),
    "Text": (
        "Font_Family",
        "Font_Size",
        "Font_Weight",
        "Line_Height",
        "Text_Align",
        "Overflow",
        "Max_Lines",
        "Selectable",
    ),
    "Content": (
        "Text",
        "Placeholder",
        "Source",
        "Icon",
        "Fit",
        "Data",
        "View_Box",
        "Trim_Start",
        "Trim_End",
        "Hit_Shape",
        "Multiline",
        "Selection",
        "Show_Whitespace",
        "Lines",
        "Read_Only",
        "Max_Length",
        "Password",
        "Speed",
        "Pause",
        "Direction",
        "Loop",
        "Animated",
    ),
    "Motion": ("Transition", "Duration", "Easing", "Animation", "Content_Fade"),
    "Accessibility": (
        "Role",
        "Description",
        "Live",
        "A11y_Hidden",
        "Value",
        "Value_Min",
        "Value_Max",
        "Value_Step",
        "Checked",
        "Selected",
        "Expanded",
    ),
    "Behaviour": (
        "Toggles",
        "Selection_Mode",
        "Chosen",
        "Slides",
        "Reveals",
        "Menu_Item",
        "Opens",
        "Keyboard",
        "Input_Region",
        "Hide_After",
        "Open_With_Target",
        "Adjust",
        "Focus",
        "Open_On_Enter",
        "Enter_Delay",
        "Close_On_Exit",
        "Exit_Delay",
        "Peek",
        "Trigger",
        "Handle",
        "Handle_Opacity",
        "Auto_Hide",
        "Auto_Hide_Delay",
        "Reveal_Key",
        "Text_Rotation",
    ),
}

# a key whose group differs on one spec: (spec, key) -> group
SPEC_GROUPS: dict[tuple[str, str], str] = {
    ("Animation", "Duration"): "Motion",
    ("Border", "Width"): "Border",
    ("Border", "Color"): "Border",
    ("Animation", "Type"): "Motion",
    ("Peek", "Size"): "Size",
    ("Edge_Peek", "Size"): "Size",
    ("Edge", "Padding"): "Layout",
    ("Frame", "Padding"): "Layout",
    ("Sides", "Left"): "Placement",
    ("Sides", "Top"): "Placement",
    ("Sides", "Right"): "Placement",
    ("Sides", "Bottom"): "Placement",
    ("Frame", "Background"): "Fill",
    ("Frame", "Margin"): "Placement",
}

# -- units of number keys, where the reference says them -----------------------------------------

UNITS: dict[str, str] = {
    "Offset": "px",
    "Gap": "px",
    "Spacing": "px",
    "Border_Width": "px",
    "Width": "px",  # of a border line: a size key is a length, which carries its own units
    "Translate_X": "px",
    "Translate_Y": "px",
    "Rotation": "deg",
    "Scroll_Offset": "px",
    "Hide_After": "ms",
    "Enter_Delay": "ms",
    "Exit_Delay": "ms",
    "Pause": "ms",
    "Duration": "ms",
    "Speed": "px/s",
    "Size": "px",
    "Thickness": "px",
    "Blur": "px",
    "Spread": "px",
    "X": "px",
    "Y": "px",
    "Font_Size": "px",
    "Line_Height": "px",
    "Corner_Radius": "px",
    "Inner_Radius": "px",
    "Diameter": "px",
    "Left": "px",
    "Top": "px",
    "Right": "px",
    "Bottom": "px",
    "Inset": "px",
    "Margin": "px",
    "Padding": "px",
    "Depth": "px",
    "Length": "px",
    "Shadow_Bleed": "px",
}

# -- defaults the loader states in its own code, not in a model field ------------------------------
# (spec, key) -> the default as TDL text; each is checked against the loader in the export tests

LITERAL_DEFAULTS: dict[tuple[str, str], str] = {
    ("Animation", "Type"): "SLIDE",  # shell._animation
    ("Marquee", "Direction"): "LEFT",  # binder.marquee.MarqueeRunner
    ("Marquee", "Loop"): "RESTART",
    ("Marquee", "Animated"): "true",
    ("Popup", "Adjust"): "[FLIP_Y, SLIDE_X]",  # PopupDef.adjust, written the way the file does
    ("Popup", "Focus"): "true",  # false for a tooltip
}

# -- the events, the actions, the tokens -----------------------------------------------------------

EVENT_DOCS: dict[str, str] = {
    "On_Open": "A Panel is about to show.",
    "On_Close": "A Panel is about to hide.",
    "On_Visible": "A Panel has shown.",
    "On_Hidden": "A Panel has hidden.",
    "On_Focus": "The block took keyboard focus. Not raised yet.",
    "On_Unfocus": "The block lost keyboard focus. Not raised yet.",
    "On_Toggle": "A Panel was toggled.",
    "On_Click": "A click: the mouse, Space or Enter on a focused block, or assistive activation.",
    "On_Secondary_Click": "A click with the secondary (right) button; event.button is "
    '"secondary". It does not run On_Click.',
    "On_Middle_Click": "A click with the middle button (a press and a release on the block); "
    'event.button is "middle". It does not run On_Click.',
    "On_Scroll": "One step of the mouse wheel over the block (the nearest block with the handler "
    "takes it); event.delta is +1 for a step down and -1 for a step up.",
    "On_Anim_Start": "A Panel's animation started.",
    "On_Anim_End": "A Panel's animation ended.",
    "On_Changed": "A control's value changed by the user: a toggle flipped, an entry chosen, a "
    "slider moved; for each new value while the pointer moves. A TextField raises it for each "
    "change of its text. An Expander raises it when an opening or a closing has finished "
    "(event.value is whether it is open), whoever set the new state.",
    "On_Released": "A slider's press ended, once, with the final value.",
    "On_Change": "Reserved: the old spelling of On_Changed.",
    "On_Submit": "Enter in a single-line TextField.",
    "On_Text_Commit": "Committed text in a TextField, such as an input-method composition.",
}

ACTION_DOCS: dict[str, str] = {
    "Show": "Shows the Panel or strip named by Target; Data is given to a Popup as caller.data.",
    "Hide": "Hides the Panel or strip named by Target.",
    "Toggle": "Shows the Panel or strip named by Target if it is hidden, else hides it.",
    "Close": "Closes the Popup that holds the block.",
    "Call": "Runs a module's @action: Target is Module.action, the other keys are its arguments.",
}

TOKEN_DOCS: dict[str, str] = {
    "color.surface": "The ground of bars and panels.",
    "color.surface_raised": "A surface above the ground: popups, buttons, tooltips.",
    "color.on_surface": "Text and icons on a surface.",
    "color.on_surface_muted": "Secondary text and icons on a surface, and a disabled state.",
    "color.primary": "The main colour of controls: a filled slider, a checked toggle.",
    "color.on_primary": "Text and icons on the primary colour.",
    "color.accent": "The accent colour; DESKTOP follows the desktop's accent.",
    "color.error": "An error or a critical state.",
    "color.warning": "A warning or a low state.",
    "color.success": "A success state.",
    "color.outline": "Borders, dividers and tracks.",
    "color.scrim": "The colour laid over what a modal surface covers.",
    "type.caption.font_size": "The size of caption type.",
    "type.caption.font_weight": "The weight of caption type.",
    "type.caption.line_height": "The line height of caption type.",
    "type.label.font_size": "The size of label type.",
    "type.label.font_weight": "The weight of label type.",
    "type.label.line_height": "The line height of label type.",
    "type.body.font_size": "The size of body type.",
    "type.body.font_weight": "The weight of body type.",
    "type.body.line_height": "The line height of body type.",
    "type.title.font_size": "The size of title type.",
    "type.title.font_weight": "The weight of title type.",
    "type.title.line_height": "The line height of title type.",
    "type.display.font_size": "The size of display type.",
    "type.display.font_weight": "The weight of display type.",
    "type.display.line_height": "The line height of display type.",
    "shape.none": "No rounding.",
    "shape.small": "Slightly rounded corners.",
    "shape.medium": "Rounded corners.",
    "shape.large": "Strongly rounded corners.",
    "shape.full": "Fully rounded: a pill or a circle.",
    "space.step_1": "The smallest step of spacing.",
    "space.step_2": "A small step of spacing.",
    "space.step_3": "A step of spacing between small things.",
    "space.step_4": "A step of spacing inside controls.",
    "space.step_5": "A step of spacing between controls.",
    "space.step_6": "A step of spacing between groups.",
    "space.step_7": "A large step of spacing.",
    "space.step_8": "The largest step of spacing.",
    "elevation.reach": "How far the largest shadow reaches, in pixels.",
    "elevation.max": "The shadow list at 100% elevation; a smaller Elevation scales it.",
    "motion.duration.short": "A short animation, in milliseconds.",
    "motion.duration.medium": "A medium animation, in milliseconds.",
    "motion.duration.long": "A long animation, in milliseconds.",
    "motion.easing.standard": "The standard curve.",
    "motion.easing.emphasized": "The emphasised curve.",
}

# settings.tdl: (section, key) -> line; the sections are "Settings" (the root) and its blocks
SETTINGS_DOCS: dict[tuple[str, str], str] = {
    ("Settings", "Main_Shell"): "The shell file to start, looked up in the Shells directories.",
    ("Settings", "Registry"): "The registry file that remembers UIDs and positions; an absolute "
    "path.",
    ("Settings", "Directories"): "Extra folders to search for each kind of file.",
    ("Settings", "Logging"): "Where and how the shell logs.",
    ("Settings", "Validation"): "Whether files are validated at load.",
    ("Settings", "Hot_Reload"): "Applies a saved file to the running shell.",
    ("Settings", "Reload_Debounce"): "How long files must be quiet before a reload, in "
    "milliseconds.",
    ("Settings", "Appearance"): "The theme and the stylesheets in use.",
    ("Settings", "Debug"): "Switches for finding a fault.",
    ("Settings", "Control"): "Whether the shell exports its control interface on the session bus "
    "(the tesserae-shell commands); a restart applies it.",
    ("Directories", "Shells"): "Folders searched for shell files.",
    ("Directories", "Modules"): "Folders searched for module files.",
    ("Directories", "Styles"): "Folders searched for style files.",
    ("Directories", "Themes"): "Folders searched for theme files.",
    ("Directories", "Stylesheets"): "Folders searched for stylesheet files.",
    ("Directories", "Icons"): "Folders searched for icon sets.",
    ("Logging", "Level"): "The least severe message that is logged.",
    ("Logging", "Directory"): "The folder of the log files; the default is logs in the config "
    "directory.",
    ("Logging", "Retention"): "How many days of log files are kept; leaving it out keeps them all.",
    ("Logging", "Format"): "TEXT for lines a person reads, JSON for lines a program reads.",
    ("Logging", "Diagnose"): "Adds the values of variables to a logged traceback.",
    ("Logging", "Console"): "Also logs to the terminal.",
    ("Logging", "Capture_Stderr"): "Routes the standard error stream into the log.",
    ("Validation", "Enabled"): "Whether files are checked against the schema at load.",
    ("Appearance", "Theme"): "The Name of the theme to use; the shell's Default theme when left "
    "out.",
    ("Appearance", "Stylesheets"): "The Name of a stylesheet or a list of them, lowest priority "
    "first.",
    ("Appearance", "Follow_Desktop"): "Follows the desktop's colour scheme, accent, contrast "
    "and reduced-motion settings.",
    ("Debug", "Panel_Hide"): "How a Panel is hidden: KEEP leaves the surface mapped and draws "
    "nothing, CLOSE destroys the window.",
    ("Debug", "Frame_Join"): "How the join of a melded Panel animates: PARAM, SMIL, CONCAVE, "
    "SHADER or STRUCTURE. A restart applies it.",
    ("Debug", "Frame_Blend"): "How the Frame's ring is blended: LINEAR in linear light or SRGB. "
    "A restart applies it.",
}

# -- what each spec is, and an example that loads ---------------------------------------------

SPEC_NOTES: dict[str, str] = {
    "Shell": "The root block of a shell file: monitors.",
    "Monitor": "One monitor, chosen by Connector, Description or Index, and the surfaces on it.",
    "Bar": "A strip along a screen edge that reserves its space.",
    "Panel": "A surface placed by anchors or against a target; a launcher, an OSD, a dock. Width "
    "and Height size it, or Depth and Length with Meld: true.",
    "Popup": "A surface that opens from a block: a menu or a tooltip.",
    "Tooltip": "An inline Popup that is a tooltip, written inside a block or a module call.",
    "Frame": "A ring around the output, with strips along its sides that hold blocks.",
    "Edges": "The sides of a Frame that have a thickness of their own or are strips.",
    "Edge": "One side of a Frame: its thickness, padding and, with Children, a strip.",
    "Border": "A line around the Frame's opening or outside: a width and a colour.",
    "Animation": "How a Panel comes and goes.",
    "Peek": "Makes a melded Panel rest as a tab that comes out when asked.",
    "Edge_Peek": "Makes a strip rest as a sliver that comes out when asked.",
    "Sides": "Named sides: Left, Top, Right and Bottom; a side left out is 0.",
    "Shadows": "A list of shadows, the first on top.",
    "Shadow": "One shadow: a colour, an offset, a blur and a spread.",
    "Stylesheet": "The root block of a stylesheet file: rules.",
    "Rule": "One rule: a Selector and the style keys to apply to what it selects.",
    "Style": "The root block of a style file, or a module's inline Style: classes and per-type "
    "defaults.",
    "Classes": "The named classes of a style.",
    "Class": "One class: Kind names the block type it is for, and the style keys of that block "
    "follow.",
    "Module": "The root block of a module file: params and one layout.",
    "Params": "The params a module accepts.",
    "Param": "One param: its type and, optionally, its default.",
    "Box": "A plain container; its children are placed by their own keys.",
    "FlexBox": "A container that lays its children out in a row or a column.",
    "Text": "Text in one style.",
    "Rectangle": "A filled rectangle with an optional border and rounded corners.",
    "ScrollBox": "A clipped viewport that scrolls its one content child.",
    "Spacer": "Takes the free space between its siblings in a flex container.",
    "SVG": "An SVG image from a file or an icon set; it takes the Foreground colour.",
    "Bitmap": "A raster image from a file.",
    "Circle": "A filled circle sized by its Diameter.",
    "Ring": "A circle drawn as a border only; Border_Width is its thickness.",
    "Path": "A vector path in SVG path syntax.",
    "Marquee": "A line of text that scrolls when it is wider than its box.",
    "TextField": "An editable text field, single line or multi-line.",
}

EXAMPLES: dict[str, str] = {
    "Shell": "Shell {\n    Monitor { Name: Main, Index: default, Children { } }\n}",
    "Monitor": "Monitor {\n    Name: Main\n    Index: default\n    Children {\n"
    "        Bar { Name: Top_Bar, Edge: TOP, Width: EXPAND, Height: 32 }\n    }\n}",
    "Bar": "Bar {\n    Name: Top_Bar\n    Edge: TOP\n    Width: EXPAND\n    Height: 32\n"
    '    Style { Background: $color.surface }\n    Children { Text { Text: "Hello" } }\n}',
    "Panel": "Panel {\n    Name: Launcher\n    Anchor: [TOP, LEFT]\n    Inset: [8, 40, 0, 0]\n"
    "    Width: 320\n    Height: 400\n    Visible: false\n"
    '    Children { Text { Text: "Apps" } }\n}',
    "Popup": "Popup {\n    Name: Tray_Menu\n    Attach: BOTTOM\n    Alignment: START\n"
    '    Children { Text { Text: "Menu" } }\n}',
    "Frame": "Frame {\n    Name: Screen_Frame\n    Thickness: 8\n    Corner_Radius: 12\n"
    "    Style { Background: $color.surface }\n}",
    "Peek": "Peek { Size: 24, Enter_Delay: 150, Exit_Delay: 300, Trigger: HOVER }",
    "Animation": "Animation { Type: SLIDE, Duration: 200 }",
    "Border": 'Inner_Border { Width: 2, Color: "#ffffff22" }',
    "Box": "Box {\n    Width: 100\n    Height: 24\n"
    "    Style { Background: $color.surface_raised }\n}",
    "FlexBox": "FlexBox {\n    Flex: HORIZONTAL\n    Spacing: 8\n    Align_Items: CENTER\n"
    '    Children { Text { Text: "One" }, Text { Text: "Two" } }\n}',
    "Text": 'Text { Text: "Battery", Font_Size: 14 }',
    "Rectangle": "Rectangle { Width: 40, Height: 4, Fill: $color.primary, Corner_Radius: 2 }",
    "Spacer": "Spacer { }",
    "SVG": 'SVG { Icon: "mdi:account", Width: 16, Height: 16 }',
    "Circle": "Circle { Diameter: 12, Fill: $color.error }",
    "Ring": "Ring { Diameter: 12, Border_Width: 2, Border_Color: $color.primary }",
    "Marquee": 'Marquee { Text: "A long title", Width: 120, Speed: 30 }',
    "Rule": 'Rule { Selector: "Text", Foreground: $color.on_surface }',
    "Stylesheet": 'Stylesheet {\n    Rule { Selector: "Text", Foreground: $color.on_surface }\n}',
}

# -- defaults tre and the tables do not give -----------------------------------------------------
# key -> (default as TDL text, why it is authored). Only keys that set no tre property (the
# shell's own keys), whose default is the behaviour of the binder when the key is absent; each is
# pinned by ``tests/test_schema_export.py`` against that behaviour.

AUTHORED_DEFAULTS: dict[str, tuple[str, str]] = {
    "Easing": (
        "STANDARD",
        "no tre property; binder.motion.motion_of uses the STANDARD curve when none is written",
    ),
    "Toggles": (
        "false",
        "no tre property; binder.controls.kind_of makes a block a toggle only when it is true",
    ),
    "Selection_Mode": (
        "NONE",
        "no tre property; binder.controls.kind_of makes a block a list only when it is SINGLE",
    ),
    "Slides": (
        "NONE",
        "no tre property; binder.controls.kind_of makes a block a slider only with HORIZONTAL "
        "or VERTICAL",
    ),
    "Reveals": (
        "NONE",
        "no tre property; binder.controls.kind_of makes a block an expander only with OPEN "
        "or CLOSED",
    ),
    "Menu_Item": (
        "false",
        "no tre property; binder.controls.kind_of makes a block a menu item only when it is true",
    ),
}

# -- theme tokens a form should offer first -------------------------------------------------------
# key -> token patterns: a group (``color``) or a group with ``*`` in its path
# (``type.*.font_size``); every pattern names a group and a token of the shipped Default theme and
# the key can read every token it matches (tested). A key of the ``color`` kind with no entry here
# is offered the ``color`` group.

PREFERRED_TOKENS: dict[str, tuple[str, ...]] = {
    "Corner_Radius": ("shape",),
    "Inner_Radius": ("shape",),
    "Spacing": ("space",),
    "Padding": ("space",),
    "Margin": ("space",),
    "Gap": ("space",),
    "Inset": ("space",),
    "Thickness": ("space",),
    "Duration": ("motion.duration.*",),
    "Font_Size": ("type.*.font_size",),
    "Font_Weight": ("type.*.font_weight",),
    "Line_Height": ("type.*.line_height",),
    "Shadows": ("elevation.max",),
}

# -- the shipped modules ----------------------------------------------------------------------

MODULE_NOTES: dict[str, str] = {
    "Audio": "The default sound output: an icon for its kind and level, mute on a click, the "
    "volume on the wheel, an optional percent and slider, and a menu of outputs.",
    "Audio_Outputs": "The content of the Audio module's outputs Popup: one row per output.",
    "Badge": "A pill with a count, or a dot, in the error colour.",
    "Battery": "The battery's charge as an icon and a number, with a tooltip; hides without one.",
    "Button": "A pressable control with an optional icon and text.",
    "Checkbox": "A box that is checked or not, with an optional text beside it.",
    "Clock": "The time, with a tooltip that shows the date.",
    "Expander": "A block that shows or hides its content with an animation.",
    "Icon": "An icon from an icon set or a file, sized by one number.",
    "Image": "A picture from a file, with a placeholder while it loads.",
    "Label": "A line of text in the theme's body type.",
    "List": "A list of entries of which one can be chosen.",
    "Marquee_Text": "A line of text that scrolls when it is wider than its box.",
    "Media": "What a media player plays, with previous, play or pause and next buttons.",
    "Menu": "The content of a Popup: a column of menu items.",
    "MenuItem": "A row of a menu: text, an icon, a key hint, a rule or a submenu.",
    "Network": "How the machine is connected, as NetworkManager reports it.",
    "ProgressBar": "A bar that shows a value between a minimum and a maximum.",
    "Slider": "A control that sets a value between a minimum and a maximum by dragging.",
    "TextBox": "Several lines of text that can wrap, be cut and be selected.",
    "TextEditor": "A multi-line text field.",
    "TextInput": "A single-line text field.",
    "Toggle": "A switch that is on or off.",
    "Tray": "The system tray: one icon per StatusNotifier application, with its tooltip, clicks "
    "and menu; the shell is a second tray host beside Plasma's.",
    "Tray_Item": "One icon of the Tray, with a tooltip.",
    "Tray_Menu": "The content of the Popups that draw a tray item's menu, one level of it.",
    "Workspaces": "The virtual desktops as buttons: the current one is marked, a click switches.",
}

# (module, param) -> one line
PARAM_DOCS: dict[tuple[str, str], str] = {
    ("Audio", "show_percent"): "Shows the volume as a number next to the icon.",
    ("Audio", "show_slider"): "Shows a volume slider.",
    ("Audio", "show_mic"): "Shows a microphone mark while the default input is muted.",
    ("Audio", "step"): "The percent one wheel step changes the volume by.",
    ("Badge", "Count"): "The number shown; 0 shows nothing unless Show_Zero is true.",
    ("Badge", "Show_Zero"): "Shows the badge for a count of 0.",
    ("Badge", "Max"): "The largest number shown; above it the badge reads that number and a plus.",
    ("Badge", "Dot"): "Shows a dot with no number.",
    ("Battery", "show_percent"): "Shows the charge as a number next to the icon.",
    ("Button", "Text"): "The words on the button.",
    ("Button", "Icon"): "An icon name such as mdi:home, or a file path, shown beside the text.",
    ("Button", "Icon_Position"): "Where the icon sits: START (before the text) or END (after it).",
    ("Button", "Label"): "The name assistive technology reads aloud; the text when it is empty.",
    ("Checkbox", "Checked"): "Whether the box is checked; set from outside.",
    ("Checkbox", "Text"): "A label beside the box; a click on it flips the checkbox too.",
    ("Checkbox", "Label"): "The name assistive technology reads aloud; the text when it is empty.",
    ("Clock", "format"): "A strftime pattern; empty is chosen by hour_cycle.",
    ("Clock", "locale"): "A locale name such as de_DE for month and day names; empty is the "
    "process's own. The system must have it; a missing one is warned about and ignored.",
    ("Clock", "hour_cycle"): "desktop, 12 or 24.",
    ("Clock", "timezone"): "An IANA zone such as Europe/Berlin; empty is the local zone.",
    ("Clock", "tooltip_format"): "A strftime pattern for the text of the tooltip the pointer "
    "opens on the clock.",
    ("Expander", "Expanded"): "Whether the content is shown; set from outside.",
    ("Expander", "Direction"): "The edge the content grows from: DOWN, UP, LEFT or RIGHT.",
    ("Expander", "Duration"): "The animation time in milliseconds; -1 takes the theme's.",
    ("Expander", "Content_Fade"): "Whether the content's opacity follows the animation.",
    ("Icon", "Icon"): "An icon name such as mdi:account, or a file path relative to the file.",
    ("Icon", "Size"): "The width and the height, in pixels.",
    ("Image", "Source"): "The file to show, relative to the file that names it.",
    ("Image", "Fit"): "How the picture fits its box: CONTAIN, COVER, FILL or NONE.",
    ("Image", "Placeholder"): "A colour or an icon shown while the picture loads or fails.",
    ("Label", "Text"): "The words.",
    ("List", "Selected"): "The Key of the chosen entry, set from outside; empty is none.",
    ("List", "Selection"): "SINGLE lets one entry be chosen; NONE does not.",
    ("List", "Label"): "The name assistive technology reads aloud for the list.",
    ("Marquee_Text", "Text"): "The words; they scroll when wider than the box.",
    ("Marquee_Text", "Speed"): "How fast the text scrolls, in pixels a second.",
    ("Marquee_Text", "Pause"): "How long the text waits at each end, in milliseconds.",
    ("Marquee_Text", "Direction"): "The way the text moves: LEFT or RIGHT.",
    ("Marquee_Text", "Loop"): "RESTART jumps back to the start; BOUNCE scrolls back.",
    ("Media", "show_art"): "Shows the artwork, 24 px (a file:// URL of the player's; a "
    "placeholder icon otherwise).",
    ("Media", "show_title"): "Shows the title, scrolling when it is wider than max_width.",
    ("Media", "show_controls"): "Shows the previous, play or pause and next buttons.",
    ("Media", "show_position"): "Shows the seek slider; it turns on the one-second tick while "
    "the player plays.",
    ("Media", "max_width"): "The title's width in pixels.",
    ("Menu", "Label"): "The name assistive technology reads aloud for the menu.",
    ("MenuItem", "Text"): "The words of the row.",
    ("MenuItem", "Icon"): "An icon name or a file path shown before the text.",
    ("MenuItem", "Shortcut_Text"): "A key hint shown at the end of the row; display only.",
    ("MenuItem", "Separator"): "Makes the row a rule between groups; it takes no events.",
    ("MenuItem", "Submenu"): "The Name of the Popup that opens beside the row as its submenu; "
    "empty has none.",
    ("MenuItem", "Label"): "The name assistive technology reads aloud; the text when it is empty.",
    ("MenuItem", "Id"): "A text the row carries for the code that built the menu; shown nowhere. "
    "A submenu reads it as caller.use.params.Id.",
    ("Network", "show_name"): "Shows the connection's name (or the Wi-Fi network's) next to the "
    "icon.",
    ("Network", "show_vpn"): "Shows a second icon while a VPN is up.",
    ("ProgressBar", "Value"): "The progress, between Min and Max.",
    ("ProgressBar", "Min"): "The value at which the bar is empty.",
    ("ProgressBar", "Max"): "The value at which the bar is full.",
    ("Slider", "Value"): "The value, set from outside.",
    ("Slider", "Min"): "The least value.",
    ("Slider", "Max"): "The greatest value.",
    ("Slider", "Step"): "The increment; a drag snaps to it.",
    ("Slider", "Orientation"): "The direction: HORIZONTAL or VERTICAL.",
    ("Slider", "Label"): "The name assistive technology reads aloud for the slider.",
    ("TextBox", "Text"): "The words.",
    ("TextBox", "Wrap"): "WORD wraps at word ends; NONE keeps the lines as written.",
    ("TextBox", "Max_Lines"): "Cuts the text after this many lines; 0 is no limit.",
    ("TextBox", "Selectable"): "Lets the user select the text.",
    ("TextEditor", "Text"): "The value, set from outside; edits come out through On_Changed.",
    ("TextEditor", "Placeholder"): "The text shown while the editor is empty.",
    ("TextEditor", "Read_Only"): "The text can be selected and copied but not changed.",
    ("TextEditor", "Max_Length"): "The most characters the editor takes; 0 is no limit.",
    ("TextEditor", "Wrap"): "WORD wraps at the width by word; NONE does not wrap and scrolls "
    "sideways.",
    ("TextEditor", "Lines"): "The height in lines, when the height is AUTO.",
    ("TextEditor", "Enabled"): "False disables the editor.",
    ("TextEditor", "Width"): "The width in pixels.",
    ("TextInput", "Text"): "The value, set from outside; edits come out through On_Changed.",
    ("TextInput", "Placeholder"): "The text shown while the field is empty.",
    ("TextInput", "Read_Only"): "The text can be selected and copied but not changed.",
    ("TextInput", "Max_Length"): "The most characters the field takes; 0 is no limit.",
    ("TextInput", "Password"): "Shows dots instead of the text and blocks copy and cut.",
    ("TextInput", "Enabled"): "False disables the field.",
    ("TextInput", "Width"): "The width in pixels.",
    ("Toggle", "Checked"): "Whether the switch is on; set from outside.",
    ("Toggle", "Label"): "The name assistive technology reads aloud for the switch.",
    ("Tray", "icon_size"): "The size of each icon in pixels.",
    ("Tray", "show_passive"): "Shows the items whose status is Passive.",
    ("Tray", "spacing"): "The space between two items in pixels.",
    (
        "Tray_Item",
        "icon",
    ): "The icon: an SVG document or pixels the shell holds (the Tray sends it).",
    ("Tray_Item", "size"): "The icon's size in pixels.",
    ("Tray_Item", "tooltip_title"): "The first line of the tooltip.",
    ("Tray_Item", "tooltip_text"): "The second line of the tooltip; empty shows none.",
    ("Tray_Item", "label"): "The name assistive technology reads aloud.",
    ("Tray_Item", "description"): "The description assistive technology reads after the name.",
    ("Tray_Item", "attention"): "The item needs attention: the block takes the :selected look.",
    ("Tray_Menu", "Level"): "1 is the menu itself; 2 and 3 are the submenus of the row that "
    "opened the Popup.",
    ("Workspaces", "label"): "name shows each desktop's name (its number when it has none); "
    "number shows 1, 2, 3.",
}
