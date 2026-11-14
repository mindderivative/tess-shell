"""The shell's schema as plain JSON, for a configuration application that builds forms from it
(``tesserae-shell schema --json``; the shape is version 1.3, see ``schema_version``).

Everything is read from the tables the loader uses, so there is no second list of keys to drift:
:mod:`tess_shell.schema.blocks` (blocks, surfaces, kinds, choices, required keys, events, what is
not built), the surface key tables of :mod:`tess_shell.schema.shell`, :mod:`tess_shell.config.
settings` (settings.tdl), the shipped ``Default`` theme and stylesheet (tokens and the defaults a
stylesheet gives) and the defaults of the typed model. What the tables cannot say is ``null`` in
the output, never a guess. The only text written by hand is :mod:`tess_shell.schema.docs` (a line
for each key, form groups, units, examples), which ``tests/test_schema_export.py`` checks key by
key against the loader.

A *kind* is how a written value is read. The loader's own kind words (``tess_shell.schema.values``)
are mapped to the vocabulary of the output in :func:`_kind_fields`; ``kinds`` in the output lists
the words with the loader kinds each one covers.
"""

from __future__ import annotations

import ast
import dataclasses
import functools
import json
from collections.abc import Mapping
from importlib import resources
from pathlib import Path
from typing import Any

import tess_dl

from tess_shell import __version__
from tess_shell.binder import marquee, motion
from tess_shell.binder import model as m
from tess_shell.binder.defaults import tre_defaults
from tess_shell.config import settings as cfg
from tess_shell.config.paths import FOLDERS
from tess_shell.schema import blocks, default_popups, docs
from tess_shell.schema import keys as chords
from tess_shell.schema.look import GROUPS as THEME_GROUPS
from tess_shell.schema.look import STYLE_UNION, read_theme, token_kind
from tess_shell.schema.model import (
    PARAM_TYPES,
    BarDef,
    EdgeDef,
    FrameDef,
    PanelDef,
    PeekDef,
    PopupDef,
)
from tess_shell.schema.ranges import percent_range, range_of, scoped
from tess_shell.schema.shell import (
    BAR_CHOICES,
    BAR_KEYS,
    IMAGE_SUFFIXES,
    PEEK_WORDS,
    read_module_params,
)
from tess_shell.schema.values import ValueProblem, coerce

SCHEMA_VERSION = "1.3"
EXAMPLE_CHORD = "Ctrl+Shift+F1"

Json = dict[str, Any]

_ORIGIN = m.Origin("", 1, 1)
EDGES = ("TOP", "BOTTOM", "LEFT", "RIGHT")  # shell._anchors
SIDES = ("Left", "Top", "Right", "Bottom")
CORNERS = ("Top_Left", "Top_Right", "Bottom_Right", "Bottom_Left")
# the words a key reads as a colour (``binder.convert.parse_color``)
COLOR_FORMS = ('"#RRGGBB"', '"#RRGGBBAA"', '"#RGB"', '"#RGBA"', "rgba(r g b a)")
# the words that stand for a path of the file system in the output
IMAGE_FILTERS = tuple(f"*{suffix}" for suffix in IMAGE_SUFFIXES)

# the keys every block takes besides the tables (``shell._block``)
IDENTITY_KEYS = ("Name", "Part", "Class", "Tooltip")
# a block takes children only in these; the rest answer ``bad-children``
CONTAINERS = ("Box", "FlexBox", "ScrollBox")

# named lists of words, shared by many keys: the key gives ``enum`` when its choices are one
NAMED_ENUMS: dict[str, tuple[str, ...]] = {
    "Align": blocks.ALIGN,
    "Justify": blocks.JUSTIFY,
    "Role": blocks.ROLES,
    "Easing": blocks.EASINGS,
    "Edge": EDGES,
    "Layer": ("BOTTOM", "TOP", "OVERLAY"),
    "Keyboard": ("NONE", "ON_DEMAND", "EXCLUSIVE"),
    "Position": ("RELATIVE", "ABSOLUTE"),
    "Orientation": ("VERTICAL", "HORIZONTAL"),
    "Alignment": ("START", "CENTER", "END"),
    "Peek_Trigger": blocks.PEEK_TRIGGERS,
    "Peek_Handle": blocks.PEEK_HANDLES,
    "Log_Level": cfg.LEVELS,
}

# -- the kinds ----------------------------------------------------------------------------------

# the loader's kind words that take no theme token whatever the theme holds: a token's written
# value would pass as text there, which says nothing of what the key means
_NO_TOKEN_KINDS = frozenset(
    {"text", "svg_source", "image", "icon", "a11y_value", "name", "name_ref", "class", "tooltip"}
)

_KINDS: dict[str, tuple[str, str]] = {
    # export kind: (widget hint, note); the loader kinds each one covers come from LOADER_KINDS
    "string": (
        "text",
        "A string, written quoted or as one word; a module's layout may hold {{ }} slots in it.",
    ),
    "text_or_number": ("text", "A number or a string."),
    "name": ("text", "An identifier: letters, digits and _, starting with a letter."),
    "name_ref": ("text", "The Name of another block or surface of the shell."),
    "bool": ("toggle", "true or false, in lower case."),
    "enabled": (
        "toggle",
        "true or false; false disables the block (the key is Enabled, not Disabled).",
    ),
    "number": (
        "number",
        "A number; min, max, step and unit say what the loader or the "
        "converter checks, null where it says nothing.",
    ),
    "whole": ("integer", "A whole number."),
    "percent": ("slider", "A percentage written 20%, from min to max."),
    "length": (
        "length",
        "Pixels (a whole number), a percentage, or the words in units; EXPAND "
        "only on Width and Height.",
    ),
    "sides": (
        "sides",
        "One number for all four sides, a list of four in the order of order, or "
        "a block of named sides (unnamed sides are 0).",
    ),
    "radius": ("corners", "One number for all corners or a list of four in the order of order."),
    "color": (
        "color",
        "A quoted colour written in one of forms, or rgba(r g b a) with alpha "
        "from 0.0 to 1.0; a token reference where tokens lists the group.",
    ),
    "enum": ("select", "One upper-case word of choices."),
    "list": (
        "list",
        "A list of item_kind items written [a, b]; one_or_list says a lone item is also a list.",
    ),
    "font": ("font", "A font family name, or a list of names in the order of fallback."),
    "duration": ("duration", "A time in milliseconds."),
    "path": (
        "path",
        "A file or folder path; mode says open (a file that exists), save or "
        "folder. A path in a shell file is relative to that file.",
    ),
    "icon": ("icon", "An icon name such as mdi:account; a prefix selects an icon set."),
    "shadows": (
        "shadows",
        "A block of Shadow blocks, the first on top, or a token reference (elevation.max).",
    ),
    "input_region": ("select", "[] (nothing takes the pointer) or the word in choices."),
    "block": ("block", "A block of its own: block names the spec in roots."),
    "tooltip": ("tooltip", "A Popup's Name, a short quoted text or an inline Tooltip block."),
    "monitor_index": ("text", "A whole number 0 or more, or the word default."),
    "key_chord": (
        "key",
        'A key press written as modifiers and one key joined by +, such as "Ctrl+Shift+F1": '
        "modifiers lists the modifiers in the written order, keys the key names by group, "
        "aliases the other names that are read and never written; any case and order is read.",
    ),
    "token_ref": (
        "token",
        "$group.name, a reference to a theme token; valid where the key's "
        "tokens list names the group.",
    ),
    "expression": (
        "expression",
        "{{ }}: an expression of the module's values, evaluated in a "
        "module's layout; a key with slot true takes it.",
    ),
}


def _tokens_accepted(model_kind: str, choices: tuple[str, ...]) -> list[str]:
    """The token groups of the Default theme whose tokens this loader kind reads as a value."""
    if model_kind in _NO_TOKEN_KINDS:
        return []
    if model_kind == "shadows":
        return ["elevation"]
    theme = _theme()
    found: set[str] = set()
    for path, token in theme.tokens.items():
        if isinstance(token.value, m.Shadows):
            continue
        try:
            coerce(model_kind, token.value, _ORIGIN, choices)
        except ValueProblem, AssertionError, TypeError, AttributeError:
            continue
        found.add(path.split(".")[0])
    return [g.lower() for g in THEME_GROUPS if g.lower() in found]


def _length_units(spec: str, key: str, model_kind: str) -> list[str]:
    if model_kind == "bound":
        return ["px"] if (spec, key) in _PIXEL_ONLY else ["px", "%"]
    if spec in ("Panel",) and key in ("Width", "Height", "Depth", "Length"):
        return ["px", "%"]  # AUTO and EXPAND are not built (shell._panel)
    if spec in ("Popup", "Tooltip") and key in ("Width", "Height"):
        return ["px", "AUTO"]  # a percentage and EXPAND are not built (shell._popup)
    return ["px", "%", "AUTO", "EXPAND"] if key in ("Width", "Height") else ["px", "%", "AUTO"]


_PIXEL_ONLY = {(s, k) for s in ("Popup", "Tooltip") for k in ("Max_Width",)}


WHOLE_KINDS = ("whole", "max_length", "lines", "diameter")


def _bounds(model_kind: str, key: str) -> Json:
    """``min`` and ``max`` of a key of this loader kind: the table the loader judges by. A whole
    number above 0 has 1 as its least, so that is its ``min`` (not exclusive)."""
    rng = range_of(model_kind, key)
    if rng is None:
        return {"min": None, "max": None}
    low = rng.low
    if rng.low_open and low is not None and model_kind in WHOLE_KINDS:
        return {"min": low + 1, "max": rng.high}
    out: Json = {"min": low, "max": rng.high}
    if rng.low_open:
        out["min_exclusive"] = True
    return out


def _negative(model_kind: str, key: str) -> bool:
    """Whether the loader takes a negative number in a key of this kind."""
    rng = range_of(model_kind, key)
    return rng is None or rng.low is None or rng.low < 0


def _kind_fields(
    model_kind: str, spec: str, key: str, choices: tuple[str, ...]
) -> tuple[str, Json]:
    """The output kind of a loader kind and the fields that kind carries."""
    unit = docs.UNITS.get(key)
    rkey = scoped(spec, key)  # the name the key's range is listed under
    match model_kind:
        case "text":
            return "string", {}
        case "svg_source":
            return "path", {"mode": "open", "filters": ["*.svg"]}
        case "image":
            return "path", {"mode": "open", "filters": list(IMAGE_FILTERS)}
        case "icon":
            return "icon", {}
        case "font_family":
            return "font", {"multiple": True}
        case "a11y_value":
            return "text_or_number", {}
        case "duration" | "pause":
            return "duration", {**_bounds(model_kind, rkey), "step": None, "unit": "ms"}
        case "color":
            return "color", {"alpha": True, "forms": list(COLOR_FORMS)}
        case "number" | "positive" | "unit":
            return "number", {**_bounds(model_kind, rkey), "step": None, "unit": unit}
        case "whole" | "max_length" | "lines" | "diameter":
            return "whole", {
                **_bounds(model_kind, rkey),
                "step": 1,
                "unit": "px" if model_kind == "diameter" else unit,
            }
        case "length" | "text_length" | "bound":
            fields = {
                "units": _length_units(spec, key, model_kind),
                "negative": _negative(model_kind, rkey),
            }
            share = percent_range(spec, key)
            if share is not None:  # a percentage has a range of its own (a Popup's Max_Height)
                fields["percent_min"] = share.low
                fields["percent_max"] = share.high
                fields["percent_min_exclusive"] = share.low_open
            return "length", fields
        case "sides" | "bleed":
            fields = {
                "arity": [1, 4],
                "order": list(SIDES),
                "named_block": True,
                "negative": _negative(model_kind, rkey),
                "unit": "px",
            }
            if model_kind == "bleed":
                fields["auto"] = True
            return "sides", fields
        case "radius":
            return "radius", {
                "arity": [1, 4],
                "order": list(CORNERS),
                "negative": _negative(model_kind, rkey),
                "unit": "px",
            }
        case "bool" | "wrap_flag":
            return "bool", {}
        case "enabled":
            return "enabled", {}
        case "enum" | "fit":
            return "enum", {}
        case "elevation":
            return "percent", {**_bounds(model_kind, rkey), "step": None}
        case "shadows":
            return "shadows", {"block": "Shadows"}
        case "view_box":
            return "list", {"item_kind": "number", "length": 4, "one_or_list": False}
        case "selection":
            return "list", {"item_kind": "whole", "length": 2, "min": 0, "one_or_list": False}
        case "transition":
            return "list", {
                "item_kind": "string",
                "min_length": 1,
                "one_or_list": True,
                "note": "style key names",
            }
        case "anchor":
            return "list", {
                "item_kind": "enum",
                "choices": list(EDGES),
                "unique": True,
                "one_or_list": True,
            }
        case "adjust":
            return "list", {
                "item_kind": "enum",
                "choices": [w.upper() for w in blocks.POPUP_ADJUST],
                "unique": True,
                "one_or_list": True,
                "min_length": 0,
            }
        case "input":
            return "input_region", {"choices": ["AUTO"], "empty_list": True}
        case "name":
            return "name", {"pattern": "^[A-Za-z][A-Za-z0-9_]*$"}
        case "name_ref":
            return "name_ref", {"pattern": "^[A-Za-z][A-Za-z0-9_]*$"}
        case "class":
            return "list", {"item_kind": "name", "one_or_list": True}
        case "tooltip":
            return "tooltip", {}
        case "monitor_index":
            return "monitor_index", {"min": 0, "word": "default"}
        case "key_chord":
            return "key_chord", {"example": EXAMPLE_CHORD}
        case _ if model_kind.startswith("block:"):
            return "block", {"block": model_kind.split(":", 1)[1]}
    raise AssertionError(f"no output kind for the loader kind {model_kind!r}")  # a table bug


# -- one key --------------------------------------------------------------------------------------


def _named_enum(choices: tuple[str, ...]) -> str | None:
    for name, words in NAMED_ENUMS.items():
        if tuple(words) == tuple(choices):
            return name
    return None


def _doc(spec: str, key: str) -> str:
    return docs.SPEC_DOCS.get((spec, key)) or docs.KEY_DOCS.get(key, "")


_GROUP_OF: dict[str, str] = {k: g for g, keys in docs.GROUPS.items() for k in keys}


def _group(spec: str, key: str) -> str | None:
    return docs.SPEC_GROUPS.get((spec, key)) or _GROUP_OF.get(key)


def _key(
    spec: str,
    key: str,
    model_kind: str | None,
    *,
    choices: tuple[str, ...] = (),
    default: str | None = None,
    required: bool = False,
    slot: bool = False,
    tokens: bool = False,
    built: bool = True,
    refused: bool = False,
    module_only: bool = False,
) -> Json:
    out: Json = {}
    kind, fields = (
        (None, {}) if model_kind is None else _kind_fields(model_kind, spec, key, choices)
    )
    out["kind"] = kind
    out["choices"] = list(choices) if kind == "enum" else None
    out["enum"] = _named_enum(choices) if kind == "enum" else None
    out["default"] = default
    out["doc"] = _doc(spec, key)
    out["slot"] = slot
    out["required"] = required
    out["built"] = built
    if not built:
        out["refused"] = refused
    if module_only:
        out["module_only"] = True
    out["group"] = _group(spec, key)
    out.update(fields)
    out["tokens"] = (
        _tokens_accepted(model_kind, choices) if tokens and model_kind is not None else []
    )
    out["preferred_tokens"] = _preferred(key, model_kind) if tokens else []
    return out


# -- defaults -------------------------------------------------------------------------------------


def _number_text(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else repr(float(value))


def _default_text(value: object) -> str | None:
    """A model default as the text a file would write; ``None`` when the model has none to write
    (an absent key, an empty list)."""
    if value is None or value == () or value == "":
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return _number_text(value)
    if isinstance(value, str):
        return value
    if (
        isinstance(value, tuple)
        and len(value) == 4
        and all(isinstance(v, int | float) for v in value)
    ):
        if len(set(value)) == 1:
            return _number_text(value[0])
        return "[" + ", ".join(_number_text(v) for v in value) + "]"
    return None


# (spec, key) -> (the model class, its field): the default is the field's
_FIELDS: dict[tuple[str, str], tuple[type, str]] = {
    ("Bar", "Layer"): (BarDef, "layer"),
    ("Bar", "Gap"): (BarDef, "gap"),
    ("Bar", "Reserve"): (BarDef, "reserve"),
    ("Panel", "Layer"): (PanelDef, "layer"),
    ("Panel", "Inset"): (PanelDef, "inset"),
    ("Panel", "Keyboard"): (PanelDef, "keyboard"),
    ("Panel", "Visible"): (PanelDef, "visible"),
    ("Panel", "Gap"): (PanelDef, "gap"),
    ("Panel", "Alignment"): (PanelDef, "alignment"),
    ("Panel", "Movable"): (PanelDef, "movable"),
    ("Panel", "Meld"): (PanelDef, "meld"),
    ("Panel", "Content_Fade"): (PanelDef, "content_fade"),
    ("Animation", "Duration"): (PanelDef, "duration"),
    ("Popup", "Attach"): (PopupDef, "attach"),
    ("Popup", "Alignment"): (PopupDef, "alignment"),
    ("Popup", "Gap"): (PopupDef, "gap"),
    ("Popup", "Max_Width"): (PopupDef, "max_width"),
    ("Popup", "Max_Height"): (PopupDef, "max_height"),
    ("Popup", "Focus"): (PopupDef, "focus"),
    ("Popup", "Tooltip"): (PopupDef, "tooltip"),
    ("Popup", "Open_On_Enter"): (PopupDef, "open_on_enter"),
    ("Popup", "Enter_Delay"): (PopupDef, "enter_delay"),
    ("Popup", "Close_On_Exit"): (PopupDef, "close_on_exit"),
    ("Popup", "Exit_Delay"): (PopupDef, "exit_delay"),
    ("Frame", "Visible"): (FrameDef, "visible"),
    ("Frame", "Keyboard"): (FrameDef, "keyboard"),
    ("Frame", "Margin"): (FrameDef, "margin"),
    ("Frame", "Corner_Radius"): (FrameDef, "outer_radius"),
    ("Frame", "Inner_Radius"): (FrameDef, "inner_radius"),
    ("Frame", "Padding"): (FrameDef, "padding"),
    ("Edge", "Content_Fade"): (EdgeDef, "content_fade"),
    ("Peek", "Size"): (PeekDef, "size"),
    ("Peek", "Enter_Delay"): (PeekDef, "enter_delay"),
    ("Peek", "Exit_Delay"): (PeekDef, "exit_delay"),
    ("Peek", "Trigger"): (PeekDef, "trigger"),
    ("Peek", "Handle"): (PeekDef, "handle"),
    ("Peek", "Handle_Opacity"): (PeekDef, "handle_opacity"),
    ("Edge_Peek", "Size"): (PeekDef, "size"),
    ("Edge_Peek", "Enter_Delay"): (PeekDef, "enter_delay"),
    ("Edge_Peek", "Exit_Delay"): (PeekDef, "exit_delay"),
    ("Edge_Peek", "Trigger"): (PeekDef, "trigger"),
    ("Edge_Peek", "Handle"): (PeekDef, "handle"),
    ("Edge_Peek", "Handle_Opacity"): (PeekDef, "handle_opacity"),
}
# defaults the binder holds as constants
_CONSTANTS: dict[tuple[str, str], object] = {
    ("Marquee", "Speed"): marquee.DEFAULT_SPEED,
    ("Marquee", "Pause"): marquee.DEFAULT_PAUSE,
}


def _field_default(cls: type, name: str) -> object:
    for f in dataclasses.fields(cls):
        if f.name == name:
            if f.default is dataclasses.MISSING:
                return None
            return f.default
    raise AssertionError(f"{cls.__name__} has no field {name}")  # a table bug


@functools.cache
def _sheet_defaults() -> dict[tuple[str, str], str]:
    """(block, key) -> the written value the shipped Default stylesheet gives a block type."""
    text = (
        resources.files("tess_shell") / "shipped" / "Stylesheets" / "Default_Stylesheet.tdl"
    ).read_text(encoding="utf-8")
    document = tess_dl.parse(text, path="Default_Stylesheet.tdl").document
    assert document is not None
    out: dict[tuple[str, str], str] = {}
    for rule in document.root.entries:
        if not (isinstance(rule, tess_dl.Block) and rule.type == "Rule"):
            continue
        selector = next(
            (
                e.value.value
                for e in rule.entries
                if isinstance(e, tess_dl.Property)
                and e.key == "Selector"
                and isinstance(e.value, tess_dl.String)
            ),
            None,
        )
        if selector is None or selector not in blocks.BLOCKS:
            continue  # a class, a name, a module, a state or a part: no block type's default
        for e in rule.entries:
            if isinstance(e, tess_dl.Property) and e.key != "Selector":
                out[(selector, e.key)] = _text(e.value)
    return out


# key constants of the shell's code that no table row states (the binder's own default)
_KEY_CONSTANTS: dict[str, object] = {"Duration": motion.DEFAULT_DURATION}


def _default(spec: str, key: str) -> str | None:
    """The default of a key as the text a file would write, or ``None`` where nothing states one.

    In order: a literal of the loader, a field of the typed model, a constant of the binder, what
    the shipped Default stylesheet gives the block, what tre reads on a bare block, a constant of
    the shell for keys that set no tre property, then the small authored table (``docs``)."""
    if (spec, key) in docs.LITERAL_DEFAULTS:
        return docs.LITERAL_DEFAULTS[(spec, key)]
    if (spec, key) in _FIELDS:
        return _default_text(_field_default(*_FIELDS[(spec, key)]))
    if (spec, key) in _CONSTANTS:
        return _default_text(_CONSTANTS[(spec, key)])
    found = _sheet_defaults().get((spec, key)) or tre_defaults().get((spec, key))
    if found is not None or spec not in blocks.BLOCKS:
        return found
    if key in _KEY_CONSTANTS:
        return _default_text(_KEY_CONSTANTS[key])
    authored = docs.AUTHORED_DEFAULTS.get(key)
    return None if authored is None else authored[0]


def _text(value: tess_dl.Value | tess_dl.Block) -> str:
    """A tess_dl value as the text a file would write."""
    match value:
        case tess_dl.String() | tess_dl.Number() | tess_dl.Percent() | tess_dl.Word():
            return value.text
        case tess_dl.List():
            return "[" + ", ".join(_text(i) for i in value.items) + "]"
        case tess_dl.Call():
            return f"{value.name}({' '.join(_text(a) for a in value.args)})"
        case tess_dl.Block():
            inner = ", ".join(
                f"{e.key}: {_text(e.value)}" if isinstance(e, tess_dl.Property) else _text(e)
                for e in value.entries
                if isinstance(e, tess_dl.Property | tess_dl.Block)
            )
            return f"{value.type} {{ {inner} }}"
    raise AssertionError(f"no text for {value!r}")  # a tess_dl change


# -- the specs ------------------------------------------------------------------------------------


def _spec(
    spec: str,
    *,
    heads: list[str] | None = None,
    keys: Mapping[str, Json] | None = None,
    style: Mapping[str, Json] | None = None,
    events: tuple[str, ...] = (),
    required: list[list[str]] | None = None,
    repeatable: bool = True,
    allowed_children: list[str] | None = None,
    module_calls: bool = False,
    not_built: list[str] | None = None,
) -> Json:
    return {
        "doc": docs.SPEC_NOTES.get(spec, ""),
        "heads": heads or [spec],
        "keys": dict(keys or {}),
        "style": dict(style or {}),
        "events": list(events),
        "required": required or [],
        "repeatable": repeatable,
        "allowed_children": allowed_children or [],
        "module_calls": module_calls,
        "example": docs.EXAMPLES.get(spec),
        "not_built": not_built or [],
    }


def _table_keys(
    spec: str,
    table: Mapping[str, str],
    *,
    choices: Mapping[str, tuple[str, ...]] | None = None,
    skip: tuple[str, ...] = (),
    tokens: bool = False,
    required: tuple[str, ...] = (),
) -> dict[str, Json]:
    """The keys of a surface table, in the table's order."""
    out: dict[str, Json] = {}
    for key, kind in table.items():
        if key in skip:
            continue
        words = (choices or {}).get(key, ())
        out[key] = _key(
            spec,
            key,
            kind,
            choices=words,
            default=_default(spec, key),
            required=key in required,
            tokens=tokens,
        )
    return out


def _not_built(
    spec: str,
    names: tuple[str, ...],
    *,
    refused: bool,
    kinds: Mapping[str, str],
    choices: Mapping[str, tuple[str, ...]] | None = None,
) -> dict[str, Json]:
    return {
        name: _key(
            spec,
            name,
            kinds.get(name),
            choices=(choices or {}).get(name, ()),
            built=False,
            refused=refused,
        )
        for name in names
    }


# the loader kinds of keys that an other table has and a not-built list repeats; a key in none of
# them has no kind the model can give
_SHARED_KINDS: dict[str, str] = {
    **blocks.COMMON,
    **blocks.FRAME_KEYS,
    **blocks.PANEL_KEYS,
    "Attach_To": "name_ref",
    "Class": "class",
    "Animation": "block:Animation",
}

_SURFACE_CHOICES: dict[str, tuple[str, ...]] = {
    **blocks.FRAME_CHOICES,
    **blocks.PANEL_CHOICES,
}


def _block_spec(name: str) -> Json:
    props, style = blocks.BLOCKS[name]
    needs = blocks.REQUIRED.get(name, ())
    alone = {n for n in needs if isinstance(n, str)}
    keys: dict[str, Json] = {
        "Name": _key(name, "Name", "name"),
        "Part": _key(name, "Part", "name"),
        "Class": _key(name, "Class", "class"),
    }
    if name in blocks.BLOCK_EVENTS:  # a tooltip opens on the pointer: a Text raises none
        keys["Tooltip"] = _key(name, "Tooltip", "tooltip", slot=True)
    for key, kind in props.items():
        keys[key] = _key(
            name,
            key,
            kind,
            choices=_choices(name, key),
            default=_default(name, key),
            required=key in alone,
            slot=not (name == m.FIELD and key == "Multiline"),
            tokens=True,
            module_only=key in blocks.A11Y_STATE,
        )
    styles: dict[str, Json] = {}
    for key, kind in style.items():
        styles[key] = _key(
            name,
            key,
            kind,
            choices=_choices(name, key),
            default=_default(name, key),
            slot=True,
            tokens=True,
        )
    return _spec(
        name,
        keys=keys,
        style=styles,
        events=blocks.BLOCK_EVENTS.get(name, ()),
        required=[[n] if isinstance(n, str) else list(n) for n in needs],
        allowed_children=list(blocks.BLOCKS) if name in CONTAINERS else [],
        module_calls=name in CONTAINERS,
    )


def _choices(block: str, key: str) -> tuple[str, ...]:
    return blocks.CHOICES.get((block, key)) or blocks.CHOICES.get(("*", key)) or ()


def _peek_spec(spec: str, strip: bool) -> Json:
    kinds = {
        "Size": "number",
        "Enter_Delay": "duration",
        "Exit_Delay": "duration",
        "Trigger": "enum",
        "Handle": "enum",
        "Handle_Opacity": "unit",
    }
    if not strip:
        kinds["Slide_From"] = "enum"
    keys = {
        key: _key(
            spec,
            key,
            kind,
            choices=PEEK_WORDS.get(key, ()),
            default=_default(spec, key),
        )
        for key, kind in kinds.items()
    }
    return _spec(
        spec,
        heads=["Peek"],
        keys=keys,
        repeatable=False,
    )


def _surface_children() -> list[str]:
    return list(blocks.BLOCKS)


def _roots() -> dict[str, Json]:
    roots: dict[str, Json] = {}
    # -- a shell file
    roots["Shell"] = _spec("Shell", repeatable=False, allowed_children=["Monitor"])
    roots["Monitor"] = _spec(
        "Monitor",
        keys={
            "Name": _key("Monitor", "Name", "name", required=True),
            "Index": _key("Monitor", "Index", "monitor_index"),
            "Connector": _key("Monitor", "Connector", "text"),
            "Description": _key("Monitor", "Description", "text"),
        },
        required=[["Name"]],
        allowed_children=["Bar", "Panel", "Popup", "Frame"],
    )
    # a Bar
    bar_keys = {
        "Name": _key("Bar", "Name", "name", required=True),
        **_table_keys("Bar", BAR_KEYS, choices=BAR_CHOICES, required=("Edge", "Width", "Height")),
        **_not_built(
            "Bar",
            blocks.BAR_NOT_BUILT,
            refused=False,
            kinds=_SHARED_KINDS,
            choices=_SURFACE_CHOICES,
        ),
    }
    roots["Bar"] = _spec(
        "Bar",
        keys=bar_keys,
        style=_table_keys("Bar", blocks.BAR_STYLE, tokens=True),
        required=[["Name"], ["Edge"], ["Width"], ["Height"]],
        allowed_children=_surface_children(),
        module_calls=True,
        not_built=list(blocks.BAR_NOT_BUILT),
    )
    # a Panel
    panel_keys = {
        "Name": _key("Panel", "Name", "name", required=True),
        **_table_keys("Panel", blocks.PANEL_KEYS, choices=blocks.PANEL_CHOICES),
        "Attach_To": _key("Panel", "Attach_To", "name_ref"),
        "Animation": _key("Panel", "Animation", "block:Animation"),
        "Peek": _key("Panel", "Peek", "block:Peek"),
        **_not_built("Panel", blocks.PANEL_NOT_BUILT_ERROR, refused=True, kinds=_SHARED_KINDS),
        **_not_built("Panel", blocks.PANEL_NOT_BUILT_WARNING, refused=False, kinds=_SHARED_KINDS),
    }
    roots["Panel"] = _spec(
        "Panel",
        keys=panel_keys,
        style=_table_keys("Panel", blocks.PANEL_STYLE, tokens=True),
        events=blocks.BLOCK_EVENTS["Panel"],
        required=[["Name"], ["Width", "Depth"], ["Height", "Length"]],
        allowed_children=_surface_children(),
        module_calls=True,
        not_built=[*blocks.PANEL_NOT_BUILT_ERROR, *blocks.PANEL_NOT_BUILT_WARNING],
    )
    # a Popup and the tooltip written inline
    for spec in ("Popup", "Tooltip"):
        inline = spec == "Tooltip"
        popup_keys = {
            **({} if inline else {"Name": _key(spec, "Name", "name", required=True)}),
            **_table_keys(
                spec,
                blocks.POPUP_KEYS,
                choices=blocks.POPUP_CHOICES,
                skip=("Tooltip",) if inline else (),
            ),
            **_not_built(spec, blocks.POPUP_NOT_BUILT, refused=True, kinds=_SHARED_KINDS),
        }
        roots[spec] = _spec(
            spec,
            keys=popup_keys,
            style=_table_keys(spec, blocks.POPUP_STYLE, tokens=True),
            required=[] if inline else [["Name"]],
            allowed_children=_surface_children(),
            module_calls=True,
            not_built=list(blocks.POPUP_NOT_BUILT),
            repeatable=not inline,
        )
    # a Frame, its sides and its borders
    frame_keys = {
        "Name": _key("Frame", "Name", "name", required=True),
        **_table_keys(
            "Frame", blocks.FRAME_KEYS, choices=blocks.FRAME_CHOICES, required=("Thickness",)
        ),
        "Inner_Border": _key("Frame", "Inner_Border", "block:Border"),
        "Outer_Border": _key("Frame", "Outer_Border", "block:Border"),
        "Edges": _key("Frame", "Edges", "block:Edges"),
        **_not_built(
            "Frame",
            blocks.FRAME_NOT_BUILT_ERROR,
            refused=True,
            kinds=_SHARED_KINDS,
            choices=_SURFACE_CHOICES,
        ),
        **_not_built("Frame", blocks.FRAME_NOT_BUILT_WARNING, refused=False, kinds=_SHARED_KINDS),
    }
    frame_style = _table_keys("Frame", blocks.FRAME_STYLE, tokens=True)
    for name in blocks.FRAME_STYLE_NOT_BUILT:
        frame_style[name]["built"] = False
        frame_style[name]["refused"] = True
        frame_style[name]["slot"] = False
    roots["Frame"] = _spec(
        "Frame",
        keys=frame_keys,
        style=frame_style,
        required=[["Name"], ["Thickness"]],
        repeatable=False,
        not_built=[*blocks.FRAME_NOT_BUILT_ERROR, *blocks.FRAME_NOT_BUILT_WARNING],
    )
    roots["Edges"] = _spec("Edges", repeatable=False, allowed_children=list(blocks.EDGE_SIDES))
    roots["Edge"] = _spec(
        "Edge",
        heads=list(blocks.EDGE_SIDES),
        keys={
            "Name": _key("Edge", "Name", "name"),
            "Thickness": _key("Edge", "Thickness", "number"),
            "Padding": _key("Edge", "Padding", "sides"),
            "Content_Fade": _key(
                "Edge", "Content_Fade", "bool", default=_default("Edge", "Content_Fade")
            ),
            "Peek": _key("Edge", "Peek", "block:Edge_Peek"),
        },
        repeatable=False,
        allowed_children=_surface_children(),
        module_calls=True,
    )
    roots["Border"] = _spec(
        "Border",
        heads=["Inner_Border", "Outer_Border"],
        keys={
            "Width": _key("Border", "Width", "number", required=True),
            "Color": _key("Border", "Color", "color", required=True, tokens=True),
        },
        required=[["Width"], ["Color"]],
        repeatable=False,
    )
    roots["Animation"] = _spec(
        "Animation",
        keys={
            "Type": _key(
                "Animation",
                "Type",
                "enum",
                choices=blocks.PANEL_ANIMATION_TYPES,
                default=_default("Animation", "Type"),
            ),
            "Duration": _key(
                "Animation", "Duration", "duration", default=_default("Animation", "Duration")
            ),
        },
        repeatable=False,
    )
    roots["Peek"] = _peek_spec("Peek", strip=False)
    roots["Edge_Peek"] = _peek_spec("Edge_Peek", strip=True)
    roots["Sides"] = _spec(
        "Sides",
        heads=["Padding", "Margin", "Inset", "Thickness"],
        keys={side: _key("Sides", side, "number") for side in SIDES},
        repeatable=False,
    )
    roots["Shadows"] = _spec("Shadows", repeatable=False, allowed_children=["Shadow"])
    roots["Shadow"] = _spec(
        "Shadow",
        keys={
            "Color": _key("Shadow", "Color", "color", required=True),
            "X": _key("Shadow", "X", "number"),
            "Y": _key("Shadow", "Y", "number"),
            "Blur": _key("Shadow", "Blur", "number"),
            "Spread": _key("Shadow", "Spread", "number"),
        },
        required=[["Color"]],
    )
    # the other files
    roots["Stylesheet"] = _spec("Stylesheet", repeatable=False, allowed_children=["Rule"])
    rule_choices = {"Overflow": blocks.CHOICES[("Rule", "Overflow")]}
    roots["Rule"] = _spec(
        "Rule",
        keys={"Selector": _key("Rule", "Selector", "text", required=True)},
        style={
            key: _key(
                "Rule",
                key,
                kind,
                choices=rule_choices.get(key) or _choices_any(key),
                default=None,
                tokens=True,
            )
            for key, kind in STYLE_UNION.items()
        },
        required=[["Selector"]],
    )
    roots["Style"] = _spec("Style", repeatable=False, allowed_children=["Classes", *blocks.BLOCKS])
    roots["Classes"] = _spec("Classes", repeatable=False)
    roots["Class"] = _spec(
        "Class",
        heads=[],
        keys={
            "Kind": _key("Class", "Kind", "enum", choices=tuple(blocks.BLOCKS), required=True),
        },
        required=[["Kind"]],
    )
    roots["Module"] = _spec(
        "Module",
        repeatable=False,
        allowed_children=["Params", "Children", "Style", *blocks.BLOCKS],
        module_calls=True,
    )
    roots["Params"] = _spec("Params", repeatable=False)
    roots["Param"] = _spec(
        "Param",
        heads=[],
        keys={
            "Type": _key("Param", "Type", "enum", choices=PARAM_TYPES, required=True),
            "Default": _key("Param", "Default", "text"),
        },
        required=[["Type"]],
    )
    return roots


def _choices_any(key: str) -> tuple[str, ...]:
    """The words of an enum style key in a stylesheet: the union of the blocks that take it."""
    words: list[str] = []
    for (block, k), choices in blocks.CHOICES.items():
        if k == key and block != "*":
            words.extend(w for w in choices if w not in words)
    return tuple(words) or blocks.CHOICES.get(("*", key), ())


# -- settings.tdl ---------------------------------------------------------------------------------


def _settings_key(section: str, key: str, kind: str, fields: Json, default: str | None) -> Json:
    out: Json = {
        "kind": kind,
        "choices": list(fields.pop("choices")) if "choices" in fields else None,
        "enum": None,
        "default": default,
        "doc": docs.SETTINGS_DOCS.get((section, key), ""),
        "slot": False,
        "required": False,
        "built": True,
        "group": section,
    }
    if out["choices"] is not None:
        out["enum"] = _named_enum(tuple(out["choices"]))
    out.update(fields)
    out["tokens"] = []
    return out


def _settings() -> dict[str, dict[str, Json]]:
    """settings.tdl by section; the keys are those of ``config.settings`` (its tuples)."""
    defaults = cfg.Settings(config_dir=Path("."))
    logging, appearance, debug = defaults.logging, defaults.appearance, defaults.debug
    folder: Json = {"mode": "folder", "absolute": True, "multiple": True}

    def block(section: str, name: str) -> Json:
        return _settings_key(section, name, "block", {"block": name}, None)

    def boolean(section: str, name: str, value: bool) -> Json:
        return _settings_key(section, name, "bool", {}, _default_text(value))

    def word(section: str, name: str, words: tuple[str, ...], value: str) -> Json:
        return _settings_key(section, name, "enum", {"choices": words}, value)

    root = {
        "Main_Shell": _settings_key(
            "Settings",
            "Main_Shell",
            "path",
            {"mode": "open", "filters": ["*_Shell.tdl"], "search_in": "Shells"},
            f'"{defaults.main_shell}"',
        ),
        "Registry": _settings_key(
            "Settings", "Registry", "path", {"mode": "save", "absolute": True}, None
        ),
        "Directories": block("Settings", "Directories"),
        "Logging": block("Settings", "Logging"),
        "Validation": block("Settings", "Validation"),
        "Hot_Reload": boolean("Settings", "Hot_Reload", defaults.hot_reload),
        "Reload_Debounce": _settings_key(
            "Settings",
            "Reload_Debounce",
            "number",
            {"min": 0, "max": None, "step": None, "unit": "ms"},
            _number_text(defaults.reload_debounce * 1000),
        ),
        "Appearance": block("Settings", "Appearance"),
        "Debug": block("Settings", "Debug"),
        "Control": boolean("Settings", "Control", defaults.control),
        "Shortcuts": block("Settings", "Shortcuts"),
        "Global_Shortcuts": boolean("Settings", "Global_Shortcuts", defaults.global_shortcuts),
    }
    assert tuple(root) == cfg.ROOT_KEYS  # the order of the loader's own tuple
    out: dict[str, dict[str, Json]] = {
        "Settings": root,
        "Directories": {
            name: _settings_key("Directories", name, "path", dict(folder), None) for name in FOLDERS
        },
        "Logging": {
            "Level": word("Logging", "Level", cfg.LEVELS, logging.level),
            "Directory": _settings_key(
                "Logging", "Directory", "path", {"mode": "folder", "absolute": True}, None
            ),
            "Retention": _settings_key(
                "Logging",
                "Retention",
                "whole",
                {"min": 0, "max": None, "step": 1, "unit": "days"},
                None,
            ),
            "Format": word("Logging", "Format", cfg.FORMATS, logging.format),
            "Diagnose": boolean("Logging", "Diagnose", logging.diagnose),
            "Console": boolean("Logging", "Console", logging.console),
            "Capture_Stderr": boolean("Logging", "Capture_Stderr", logging.capture_stderr),
        },
        "Validation": {"Enabled": boolean("Validation", "Enabled", defaults.validation_enabled)},
        "Shortcuts": {
            name: _settings_key("Shortcuts", name, "key_chord", {"example": EXAMPLE_CHORD}, None)
            for name in cfg.FIXED_SHORTCUTS
        },
        "Appearance": {
            "Theme": _settings_key("Appearance", "Theme", "string", {}, None),
            "Stylesheets": _settings_key(
                "Appearance",
                "Stylesheets",
                "list",
                {"item_kind": "string", "one_or_list": True},
                None,
            ),
            "Follow_Desktop": boolean("Appearance", "Follow_Desktop", appearance.follow_desktop),
        },
        "Debug": {
            "Panel_Hide": word("Debug", "Panel_Hide", cfg.PANEL_HIDE, debug.panel_hide),
            "Frame_Join": word("Debug", "Frame_Join", cfg.FRAME_JOIN, debug.frame_join),
            "Frame_Blend": word("Debug", "Frame_Blend", cfg.FRAME_BLEND, debug.frame_blend),
        },
    }
    return out


# -- the theme ------------------------------------------------------------------------------------


@functools.cache
def _theme_source() -> tuple[tess_dl.Document, str]:
    path = resources.files("tess_shell") / "shipped" / "Themes" / "Default_Theme.tdl"
    text = path.read_text(encoding="utf-8")
    document = tess_dl.parse(text, path="Default_Theme.tdl").document
    assert document is not None
    return document, "Default_Theme.tdl"


@functools.cache
def _theme() -> Any:
    document, file = _theme_source()
    theme, findings = read_theme(document, file)
    assert theme is not None, findings  # the shipped theme is checked by the test suite
    return theme


def _flatten(
    block: tess_dl.Block, prefix: tuple[str, ...], out: dict[str, tess_dl.Value | tess_dl.Block]
) -> None:
    """The written entry of every token, by the path ``schema.look`` gives it."""
    for entry in block.entries:
        if isinstance(entry, tess_dl.Property):
            out[".".join((*prefix, entry.key.lower()))] = entry.value
        elif isinstance(entry, tess_dl.Block):
            if prefix == ("elevation",) and entry.type == "Max":
                out["elevation.max"] = entry
            else:
                _flatten(entry, (*prefix, entry.type.lower()), out)


def _tokens() -> dict[str, dict[str, Json]]:
    document, _ = _theme_source()
    theme = _theme()
    written: dict[str, tess_dl.Value | tess_dl.Block] = {}
    for entry in document.root.entries:
        if isinstance(entry, tess_dl.Block) and entry.type in THEME_GROUPS:
            _flatten(entry, (entry.type.lower(),), written)
    out: dict[str, dict[str, Json]] = {g.lower(): {} for g in THEME_GROUPS}
    for path in theme.tokens:
        group, _, name = path.partition(".")
        # the loader checks a token's value only for the groups ``look._kind`` names; the
        # easing words and ``elevation.reach`` it reads as written, so their kind is not known
        model_kind = "shadows" if path == "elevation.max" else token_kind(tuple(path.split(".")))
        kind, fields = (
            (None, {}) if model_kind is None else _kind_fields(model_kind, "Theme", name, ())
        )
        out[group][name] = {
            "kind": kind,
            "ref": f"${path}",
            "default": _text(written[path]),
            "doc": docs.TOKEN_DOCS.get(path, ""),
            "modes": [mode for mode, tokens in theme.modes.items() if path in tokens],
            **fields,
        }
    return out


# -- events, actions ------------------------------------------------------------------------------


def _events() -> dict[str, Json]:
    out: dict[str, Json] = {}
    for name in blocks.EVENT_KEYS:
        needs = blocks.CONTROL_EVENTS.get(name)
        out[name] = {
            "doc": docs.EVENT_DOCS.get(name, ""),
            "module_only": needs is not None,
            "needs": list(needs) if needs else [],
            "raised_by": [b for b, events in blocks.BLOCK_EVENTS.items() if name in events],
        }
    return out


def _actions() -> list[Json]:
    target = {
        "name": "Target",
        "kind": "name_ref",
        "required": True,
        "doc": "The Name of the Panel or strip.",
    }
    data = {
        "name": "Data",
        "kind": "block",
        "required": False,
        "doc": "Values the opened Popup reads as caller.data.",
    }
    args: dict[str, list[Json]] = {
        "Show": [target, data],
        "Hide": [target],
        "Toggle": [target, data],
        "Close": [],
        "Call": [
            {
                "name": "Target",
                "kind": "string",
                "required": True,
                "doc": 'The module and its @action, "Module.action".',
            }
        ],
    }
    return [
        {
            "name": name,
            "doc": docs.ACTION_DOCS.get(name, ""),
            "args": args[name],
            "built": name in blocks.BUILTIN_BUILT,
        }
        for name in blocks.BUILTIN_ACTIONS
    ]


# every loader kind word the export reads (the tables' and its own); the test suite checks that
# each one is mapped and that every kind of every table is in the list
LOADER_KINDS = (
    "text",
    "svg_source",
    "image",
    "icon",
    "font_family",
    "a11y_value",
    "duration",
    "pause",
    "color",
    "number",
    "positive",
    "unit",
    "whole",
    "max_length",
    "lines",
    "diameter",
    "length",
    "text_length",
    "bound",
    "sides",
    "bleed",
    "radius",
    "bool",
    "wrap_flag",
    "enabled",
    "enum",
    "fit",
    "elevation",
    "shadows",
    "view_box",
    "selection",
    "transition",
    "anchor",
    "adjust",
    "input",
    "name",
    "name_ref",
    "class",
    "tooltip",
    "monitor_index",
    "key_chord",
    "block:Block",
)


def _kinds() -> dict[str, Json]:
    covers: dict[str, list[str]] = {}
    for model_kind in LOADER_KINDS:
        kind, _ = _kind_fields(model_kind, "", "", ())
        covers.setdefault(kind, []).append(model_kind)
    out: dict[str, Json] = {
        kind: {"ui": ui, "note": note, "model_kinds": covers.get(kind, [])}
        for kind, (ui, note) in _KINDS.items()
    }
    out["key_chord"].update(chords.key_names())  # the names a key string may use
    return out


# -- preferred tokens ---------------------------------------------------------------------------


def _preferred(key: str, model_kind: str | None) -> list[str]:
    """The token patterns a form should offer first for a key (``docs.PREFERRED_TOKENS``; a colour
    key is offered the ``color`` group)."""
    if key in docs.PREFERRED_TOKENS:
        return list(docs.PREFERRED_TOKENS[key])
    return ["color"] if model_kind == "color" else []


# -- the shipped modules ----------------------------------------------------------------------

_PARAM_KINDS = {"string": "text", "number": "number", "boolean": "bool", "icon": "icon"}


def _param_text(value: m.Value | None) -> str | None:
    """A param's default as the text a file would write."""
    match value:
        case m.Text():
            return json.dumps(value.value)
        case m.Number():
            return _number_text(value.value)
        case m.Bool():
            return "true" if value.value else "false"
    return None


def _shipped_modules() -> dict[str, tuple[tess_dl.Document, str | None]]:
    """The shipped modules by name: the parsed ``<Name>_Module.tdl`` and the source of its
    ``<Name>_Module.py`` (read, never imported)."""
    out: dict[str, tuple[tess_dl.Document, str | None]] = {}
    root = resources.files("tess_shell") / "shipped"
    for folder in sorted(root.iterdir(), key=lambda p: p.name):
        tdl = folder / f"{folder.name}_Module.tdl"
        if not folder.is_dir() or not tdl.is_file():
            continue
        parsed = tess_dl.parse(tdl.read_text(encoding="utf-8"), path=tdl.name)
        assert parsed.document is not None, parsed.errors  # shipped files are tested
        py = folder / f"{folder.name}_Module.py"
        source = py.read_text(encoding="utf-8") if py.is_file() else None
        out[folder.name] = (parsed.document, source)
    return out


def _layout_root(document: tess_dl.Document) -> tess_dl.Block | None:
    for entry in document.root.entries:
        if not isinstance(entry, tess_dl.Block) or entry.type in ("Params", "Style"):
            continue
        if entry.type == "Children":
            return next((e for e in entry.entries if isinstance(e, tess_dl.Block)), None)
        return entry
    return None


def _root_block(
    name: str, modules: Mapping[str, tuple[tess_dl.Document, str | None]]
) -> tuple[str, set[str]]:
    """The block kind of a module's layout root and the keys written on it; a root that is itself
    a module call is that module's (it passes events and keys on, ``model.expand``)."""
    root = _layout_root(modules[name][0])
    if root is None:
        return "", set()
    if root.type in modules and root.type != name:
        return _root_block(root.type, modules)
    return root.type, {e.key for e in root.entries if isinstance(e, tess_dl.Property)}


def _events_of(kind: str, keys: set[str]) -> list[str]:
    """The events a call of a module may handle: what its root block raises, a control event only
    when the root has a key that makes it one (the rule of ``model.expand``)."""
    raised = blocks.BLOCK_EVENTS.get(kind, ())
    out = []
    for event in raised:
        needs = blocks.CONTROL_EVENTS.get(event)
        if needs is None or kind not in blocks.CONTROL_KINDS or any(k in keys for k in needs):
            out.append(event)
    return out


def _is_action(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for deco in fn.decorator_list:
        target = deco.func if isinstance(deco, ast.Call) else deco
        if (isinstance(target, ast.Name) and target.id == "action") or (
            isinstance(target, ast.Attribute) and target.attr == "action"
        ):
            return True
    return False


def _actions_of(source: str | None) -> list[Json]:
    """The ``@action`` methods of a module's class: their arguments are the parameters after the
    event (``modules.host.action_spec``): required when they have no default."""
    if source is None:
        return []
    found: list[Json] = []
    for cls in (n for n in ast.parse(source).body if isinstance(n, ast.ClassDef)):
        if not any(isinstance(b, ast.Name) and b.id == "Module" for b in cls.bases):
            continue
        for fn in (n for n in cls.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)):
            if not _is_action(fn):
                continue
            a = fn.args
            positional = [*a.posonlyargs, *a.args]
            defaults = [None] * (len(positional) - len(a.defaults)) + list(a.defaults)
            pairs = list(zip(positional, defaults, strict=True))[2:]  # self, then the event
            pairs += list(zip(a.kwonlyargs, a.kw_defaults, strict=True))
            args = [{"name": arg.arg, "required": default is None} for arg, default in pairs]
            doc = ast.get_docstring(fn) or ""
            found.append(
                {
                    "name": fn.name,
                    "doc": doc.split("\n\n")[0].replace("\n", " ").strip(),
                    "args": args,
                    "kwargs": a.kwarg is not None,
                }
            )
    return sorted(found, key=lambda action: str(action["name"]))


def _modules() -> dict[str, Json]:
    """The shipped modules: their params (read with ``read_module_params``), the events a call
    may handle, the common keys it may write and the actions ``Call`` may run."""
    modules = _shipped_modules()
    out: dict[str, Json] = {}
    for name, (document, source) in modules.items():
        found = read_module_params(document, f"{name}_Module.tdl")
        assert found is not None
        params: dict[str, Json] = {}
        for param, decl in found.params.items():
            if decl.type == "path":
                kind, fields = "path", {"mode": "open", "filters": None}
            else:
                kind, fields = _kind_fields(_PARAM_KINDS[decl.type], "Module", "", ())
            params[param] = {
                "type": decl.type,
                "kind": kind,
                "default": _param_text(decl.default),
                "doc": docs.PARAM_DOCS.get((name, param), ""),
                "required": decl.default is None,
                **fields,
            }
        kind_of_root, keys = _root_block(name, modules)
        table = blocks.table(kind_of_root)
        takes = set() if table is None else {*table[0], *table[1]}
        out[name] = {
            "doc": docs.MODULE_NOTES.get(name, ""),
            "params": params,
            "root_block": kind_of_root,
            "events": _events_of(kind_of_root, keys),
            "common_keys": [k for k in blocks.COMMON if k not in blocks.A11Y_STATE and k in takes],
            "actions": _actions_of(source),
        }
    return out


def _popups() -> Json:
    """The Popups the shell provides (``schema.default_popups``), and which Monitors get them."""
    stubs = {}
    for name, (document, _source) in _shipped_modules().items():
        found = read_module_params(document, f"{name}_Module.tdl")
        assert found is not None
        stubs[name] = found
    return {"monitors": default_popups.MONITORS, "popups": default_popups.describe(stubs)}


def _shortcuts() -> Json:
    """The forms of an entry of ``Shortcuts { }`` (``config.settings.FIXED_SHORTCUTS``,
    ``SHORTCUT_VERBS``) and the keys a surface declares; the key names are those of the
    ``key_chord`` kind."""
    named = {"kind": "name_ref", "doc": "The Name of the surface, written exactly."}
    forms: list[Json] = [
        {
            "form": f"{verb}_<Name>",
            "verb": verb,
            "value": "key_chord",
            "target": named,
            "targets": ["Panel", "Frame"] if verb == "Hide" else ["Panel", "Bar", "Frame"],
            "doc": docs.SHORTCUT_FORMS[verb],
        }
        for verb in cfg.SHORTCUT_VERBS
    ]
    forms.append(
        {
            "form": "<Any_Name> { Keys, Action }",
            "verb": None,
            "value": "block",
            "keys": {"kind": "key_chord", "key": "Keys", "required": True},
            "actions": ["Show", "Hide", "Toggle", "Call"],
            "doc": docs.SHORTCUT_FORMS["Handler"],
        }
    )
    return {
        "fixed": list(cfg.FIXED_SHORTCUTS),
        "forms": forms,
        "surface_keys": {
            "Panel": {"key": "Shortcut", "same_as": "Toggle_<Name>"},
            "Bar": {"key": "Reveal_Key", "same_as": "Show_<Name>"},
        },
        "doc": "A surface's own key and a Shortcuts entry for the same action: the entry wins, "
        "with one warning. Two actions with the same key (any case, order or alias) are both "
        "left without it, with one warning. A name that matches no surface is a warning and "
        "the shortcut is not registered.",
    }


# -- the whole ------------------------------------------------------------------------------------


def schema_dict() -> Json:
    """The export as plain data (dicts, lists, strings, numbers, booleans, ``None``), in a stable
    order."""
    return {
        "schema_version": SCHEMA_VERSION,
        "shell_version": __version__,
        "kinds": _kinds(),
        "roots": _roots(),
        "blocks": {name: _block_spec(name) for name in blocks.BLOCKS},
        "settings": _settings(),
        "events": _events(),
        "actions": _actions(),
        "enums": {name: list(words) for name, words in NAMED_ENUMS.items()},
        "tokens": _tokens(),
        "modules": _modules(),
        "popups": _popups(),
        "shortcuts": _shortcuts(),
    }


def schema_json() -> str:
    """The export as JSON text: two-space indent, keys in the model's order, a newline at the end.
    Two calls give the same bytes."""
    return json.dumps(schema_dict(), indent=2, ensure_ascii=False) + "\n"
