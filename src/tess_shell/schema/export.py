"""The shell's schema as plain JSON, for a configuration application that builds forms from it
(``tesserae-shell schema --json``; the shape is version 1.0, see ``schema_version``).

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

import dataclasses
import functools
import json
from collections.abc import Mapping
from importlib import resources
from pathlib import Path
from typing import Any

import tess_dl

from tess_shell import __version__
from tess_shell.binder import marquee
from tess_shell.binder import model as m
from tess_shell.config import settings as cfg
from tess_shell.config.paths import FOLDERS
from tess_shell.schema import blocks, docs
from tess_shell.schema.look import GROUPS as THEME_GROUPS
from tess_shell.schema.look import STYLE_UNION, read_theme
from tess_shell.schema.look import _kind as _token_kind
from tess_shell.schema.model import (
    PARAM_TYPES,
    BarDef,
    EdgeDef,
    FrameDef,
    PanelDef,
    PeekDef,
    PopupDef,
)
from tess_shell.schema.shell import _BAR_CHOICES, _BAR_KEYS, _IMAGE_SUFFIXES, _PEEK_WORDS
from tess_shell.schema.values import ValueProblem, coerce

SCHEMA_VERSION = "1.0"

Json = dict[str, Any]

_ORIGIN = m.Origin("", 1, 1)
EDGES = ("TOP", "BOTTOM", "LEFT", "RIGHT")  # shell._anchors
SIDES = ("Left", "Top", "Right", "Bottom")
CORNERS = ("Top_Left", "Top_Right", "Bottom_Right", "Bottom_Left")
# the words a key reads as a colour (``binder.convert.parse_color``)
COLOR_FORMS = ('"#RRGGBB"', '"#RRGGBBAA"', '"#RGB"', '"#RGBA"', "rgba(r g b a)")
# the words that stand for a path of the file system in the output
IMAGE_FILTERS = tuple(f"*{suffix}" for suffix in _IMAGE_SUFFIXES)

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


_PIXEL_ONLY = {(s, k) for s in ("Popup", "Tooltip") for k in ("Max_Width", "Max_Height")}


def _kind_fields(
    model_kind: str, spec: str, key: str, choices: tuple[str, ...]
) -> tuple[str, Json]:
    """The output kind of a loader kind and the fields that kind carries."""
    unit = docs.UNITS.get(key)
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
        case "duration" | "pause" | "non_negative_ms":
            return "duration", {"min": 0, "max": None, "step": None, "unit": "ms"}
        case "color":
            return "color", {"alpha": True, "forms": list(COLOR_FORMS)}
        case "number":
            return "number", {"min": None, "max": None, "step": None, "unit": unit}
        case "positive":
            fields: Json = {"min": 0, "min_exclusive": True, "max": None, "step": None}
            return "number", {**fields, "unit": unit}
        case "non_negative":
            return "number", {"min": 0, "max": None, "step": None, "unit": unit}
        case "unit":
            return "number", {"min": 0, "max": 1, "step": None, "unit": None}
        case "peek_size":
            return "number", {"min": 1, "max": None, "step": None, "unit": "px"}
        case "whole":
            return "whole", {"min": None, "max": None, "step": 1, "unit": unit}
        case "max_length":
            return "whole", {"min": 0, "max": None, "step": 1, "unit": None}
        case "lines":
            return "whole", {"min": 1, "max": None, "step": 1, "unit": None}
        case "diameter":
            return "whole", {"min": 1, "max": None, "step": 1, "unit": "px"}
        case "length" | "text_length" | "bound":
            return "length", {
                "units": _length_units(spec, key, model_kind),
                "negative": False,
            }
        case "sides" | "bleed":
            fields = {
                "arity": [1, 4],
                "order": list(SIDES),
                "named_block": True,
                "negative": False,
                "unit": "px",
            }
            if model_kind == "bleed":
                fields["auto"] = True
            return "sides", fields
        case "radius":
            return "radius", {
                "arity": [1, 4],
                "order": list(CORNERS),
                "negative": False,
                "unit": "px",
            }
        case "bool" | "wrap_flag":
            return "bool", {}
        case "enabled":
            return "enabled", {}
        case "enum" | "fit":
            return "enum", {}
        case "elevation":
            return "percent", {"min": 0, "max": 100, "step": None}
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


def _default(spec: str, key: str) -> str | None:
    if (spec, key) in docs.LITERAL_DEFAULTS:
        return docs.LITERAL_DEFAULTS[(spec, key)]
    if (spec, key) in _FIELDS:
        return _default_text(_field_default(*_FIELDS[(spec, key)]))
    if (spec, key) in _CONSTANTS:
        return _default_text(_CONSTANTS[(spec, key)])
    return _sheet_defaults().get((spec, key))


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
        "Size": "peek_size",
        "Enter_Delay": "non_negative_ms",
        "Exit_Delay": "non_negative_ms",
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
            choices=_PEEK_WORDS.get(key, ()),
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
        **_table_keys("Bar", _BAR_KEYS, choices=_BAR_CHOICES, required=("Edge", "Width", "Height")),
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
            "Thickness": _key("Edge", "Thickness", "non_negative"),
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
            "Width": _key("Border", "Width", "non_negative", required=True),
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
            "Blur": _key("Shadow", "Blur", "non_negative"),
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
    }
    assert tuple(root) == cfg._ROOT_KEYS  # the order of the loader's own tuple
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
            "Panel_Hide": word("Debug", "Panel_Hide", cfg._PANEL_HIDE, debug.panel_hide),
            "Frame_Join": word("Debug", "Frame_Join", cfg._FRAME_JOIN, debug.frame_join),
            "Frame_Blend": word("Debug", "Frame_Blend", cfg._FRAME_BLEND, debug.frame_blend),
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
        model_kind = "shadows" if path == "elevation.max" else _token_kind(tuple(path.split(".")))
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
    "non_negative_ms",
    "color",
    "number",
    "positive",
    "non_negative",
    "unit",
    "peek_size",
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
    "block:Block",
)


def _kinds() -> dict[str, Json]:
    covers: dict[str, list[str]] = {}
    for model_kind in LOADER_KINDS:
        kind, _ = _kind_fields(model_kind, "", "", ())
        covers.setdefault(kind, []).append(model_kind)
    return {
        kind: {"ui": ui, "note": note, "model_kinds": covers.get(kind, [])}
        for kind, (ui, note) in _KINDS.items()
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
    }


def schema_json() -> str:
    """The export as JSON text: two-space indent, keys in the model's order, a newline at the end.
    Two calls give the same bytes."""
    return json.dumps(schema_dict(), indent=2, ensure_ascii=False) + "\n"
