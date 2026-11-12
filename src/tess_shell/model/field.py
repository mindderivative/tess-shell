"""The TextField block as typed nodes (Block Reference > TextField).

tre's advice for a field is a text input inside a box that paints the background and the border.
A text input has no height of its own, so a text of the field's lines in the field's font, in a
line box under the input, gives the field the height of its lines (``Lines`` of a multi-line
field, one for a single-line one) without anyone measuring a font. :func:`compose` splits a
``TextField`` block into that composition, after the stylesheet's rules are folded into it and
before slots are resolved, so every later step (slots, tokens, the binder's keyed diff, states)
sees ordinary nodes:

* ``TextField`` (the box): the common keys, ``Padding`` and the box's style; ``On_Click``;
* ``TextField.line`` (a box in the box's cell): centred in it for a single-line field, filling it
  for a multi-line one;
* ``TextField.size`` (a text in the line): the font keys and ``Lines``; none for a multi-line
  field that has a ``Height``;
* ``TextField.input`` (the text input, over the line, not in the flow): the field's own keys, the
  font and ``Foreground``, the text events.

``Wrap`` is for a multi-line field and ``Overflow`` for a single-line one: tre makes a
single-line input one line only when ``overflow`` is set, so the field always sets one of them
(``WORD``, ``SCROLL``). A key that does not apply to the form is left out here; the schema warns
about one that was written.

Imports ``binder.model`` and ``schema.blocks`` only.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping, Sequence
from typing import Any

from tess_shell.binder import model as m
from tess_shell.schema import blocks

DEFAULT_LINES = 3  # the height of a multi-line field with no Height and no Lines

_INPUT_PROPS, _INPUT_STYLE = blocks.INTERNAL[m.FIELD_INPUT]
_SIZE_PROPS, _SIZE_STYLE = blocks.INTERNAL[m.FIELD_SIZE]
_BOX_PROPS, _BOX_STYLE = blocks.FIELD_BOX
# the state styles a field's two sides take: the box paints, the input draws the text
_BOX_STATE_KEYS = frozenset(_BOX_STYLE)
_INPUT_STATE_KEYS = frozenset(_INPUT_STYLE) - {"Overflow"}
_SINGLE_ONLY = ("Overflow", "Password")
_MULTI_ONLY = ("Wrap", "Lines")


def is_multiline(node: m.Node) -> bool:
    """Whether the block is written ``Multiline: true`` (a slot is refused by the schema)."""
    value = node.props.get("Multiline")
    return isinstance(value, m.Bool) and value.value


def _token(path: str, kind: str, origin: m.Origin) -> m.TokenRef:
    return m.TokenRef(path, kind, origin=origin)


def _defaults(origin: m.Origin) -> tuple[dict[str, m.Value], dict[str, m.Value]]:
    """The look of a field that is given none, from the theme's tokens (Block Reference >
    TextField: ``Padding`` is by theme): a raised surface with an outline, the text colour and
    the body size. A stylesheet's rule or the block's own keys replace each of them."""
    box: dict[str, m.Value] = {
        "Background": _token("color.surface_raised", "color", origin),
        "Border_Width": m.Number(1, origin=origin),
        "Border_Color": _token("color.outline", "color", origin),
        "Corner_Radius": _token("shape.small", "radius", origin),
        "Padding": m.Sides(10, 6, 10, 6, origin=origin),
    }
    text: dict[str, m.Value] = {
        "Foreground": _token("color.on_surface", "color", origin),
        "Font_Size": _token("type.body.font_size", "positive", origin),
    }
    return box, text


def _default_states(origin: m.Origin) -> dict[str, dict[str, m.Value]]:
    """What the box shows while the pointer is over it or while it is disabled, when no rule says
    otherwise: the outline takes the primary colour, a disabled field is faint."""
    return {
        "hovered": {"Border_Color": _token("color.primary", "color", origin)},
        "disabled": {"Opacity": m.Number(0.5, origin=origin)},
    }


def _has_explicit_height(node: m.Node) -> bool:
    return isinstance(node.props.get("Height"), m.Length | m.Percent | m.Expand)


def compose(node: m.Node) -> m.Node:
    """The ``TextField`` block ``node`` as its box with the size text and the text input as
    children. A node that is not a ``TextField`` is returned as it is."""
    if node.kind != m.FIELD:
        return node
    multiline = is_multiline(node)
    skip = _SINGLE_ONLY if multiline else _MULTI_ONLY
    box: tuple[dict[str, m.Value], dict[str, m.Value]] = ({}, {})
    inp: tuple[dict[str, m.Value], dict[str, m.Value]] = ({}, {})
    size: tuple[dict[str, m.Value], dict[str, m.Value]] = ({}, {})
    for scope, values in enumerate((node.props, node.style)):  # 0: written on the block, 1: Style
        for key, value in values.items():
            if key in skip:
                continue
            if key in blocks.FIELD_BOX_KEYS:
                box[scope][key] = value
            if key in blocks.FIELD_INPUT_KEYS:
                # a key the input takes only as a property is a property wherever it was written
                inp[scope if key in _INPUT_STYLE else 0][key] = value
            if key in blocks.FIELD_SIZE_KEYS:
                size[scope if key in _SIZE_STYLE else 0][key] = value
    origin = node.origin
    box_look, text_look = _defaults(origin)
    for key, value in box_look.items():
        if key not in box[0] and key not in box[1]:
            box[1 if key != "Padding" else 0][key] = value
    for key, value in text_look.items():
        if key not in inp[0] and key not in inp[1]:
            inp[1][key] = value
            if key in blocks.FIELD_SIZE_KEYS:  # the size text takes the font the input takes
                size[1][key] = value
    inp[0]["Multiline"] = m.Bool(multiline, origin=origin)
    written = inp[0].keys() | inp[1].keys()
    if multiline and "Wrap" not in written:
        inp[0]["Wrap"] = m.Enum("WORD", origin=origin)
    if not multiline and "Overflow" not in written:
        inp[1]["Overflow"] = m.Enum("SCROLL", origin=origin)
    if multiline and "Lines" not in size[0]:
        size[0]["Lines"] = m.Number(DEFAULT_LINES, origin=origin)

    box_states, input_states = _split_states(node.states)
    for state, values in _default_states(origin).items():
        box_states[state] = {**values, **box_states.get(state, {})}
    handlers = {k: h for k, h in node.handlers.items() if k not in blocks.FIELD_EVENTS}
    field_handlers = {k: h for k, h in node.handlers.items() if k in blocks.FIELD_EVENTS}
    if multiline:
        field_handlers.pop("On_Submit", None)  # Enter inserts a newline

    # a single-line field is one line, centred in its box; a multi-line field fills its box (and
    # is as high as its lines unless it has a Height)
    inner: list[m.Node | m.UseNode | m.IfNode | m.ForNode] = []
    if not multiline or not _has_explicit_height(node):
        inner.append(m.Node(m.FIELD_SIZE, props=size[0], style=size[1], origin=origin))
    inner.append(
        m.Node(
            m.FIELD_INPUT,
            props=inp[0],
            style=inp[1],
            handlers=field_handlers,
            states=input_states,
            origin=origin,
        )
    )
    line = m.Node(
        m.FIELD_LINE,
        props={"Align_Self": m.Enum("STRETCH" if multiline else "CENTER", origin=origin)},
        children=tuple(inner),
        origin=origin,
    )
    return dataclasses.replace(
        node,
        props=box[0],
        style=box[1],
        handlers=handlers,
        states=box_states,
        children=(line,),
    )


def _split_states(
    states: Mapping[str, Mapping[str, m.Value]],
) -> tuple[dict[str, Mapping[str, m.Value]], dict[str, Mapping[str, m.Value]]]:
    box: dict[str, Mapping[str, m.Value]] = {}
    inp: dict[str, Mapping[str, m.Value]] = {}
    for state, values in states.items():
        mine = {k: v for k, v in values.items() if k in _BOX_STATE_KEYS}
        theirs = {k: v for k, v in values.items() if k in _INPUT_STATE_KEYS}
        if mine:
            box[state] = mine
        if theirs:
            inp[state] = theirs
    return box, inp


def first_text_field(nodes: Sequence[Any]) -> Any | None:
    """The first TextField of a tree (the expanded nodes of a surface, ``If`` and ``For`` bodies
    too), or ``None``."""
    for node in nodes:
        if getattr(node, "kind", None) == m.FIELD:
            return node
        for attr in ("children", "body", "else_body"):
            found = first_text_field(getattr(node, attr, None) or ())
            if found is not None:
                return found
    return None


def holds_text_field(nodes: Sequence[Any]) -> bool:
    """Whether a tree holds a TextField: its surface then takes the keyboard ``on_demand``, so a
    click on the field gives it the keyboard (M4 Brief: a text field takes the keyboard when it is
    clicked)."""
    return first_text_field(nodes) is not None


def describe_text_field(node: Any) -> str:
    """A text field for a message: its ``Name``, the module use it stands in and its place in the
    file."""
    module = str(getattr(node, "owner", None) or "").split("@", 1)[0]
    parts = ["the text field"]
    if getattr(node, "name", None):
        parts.append(str(node.name))
    if module:
        parts.append(f"of {module}")
    origin = getattr(node, "origin", None)
    if origin is not None and origin.file:
        parts.append(f"({origin.file}:{origin.line})")
    return " ".join(parts)
