"""The Marquee block as typed nodes (Standard Modules > Marquee text).

``compose`` runs where ``model.field.compose`` does (in the expander, before slots are resolved)
and splits the block into two typed nodes the binder builds one to one: the box that clips (it
takes the common keys, the events and the behaviour keys ``Speed``, ``Pause``, ``Direction``,
``Loop`` and ``Animated``) and the text it moves (it takes the words and the type keys). The box's
``Label`` is the whole text, so assistive technology does not read a moving fragment. The binder
runs the scroll (``binder.marquee``).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping

from tess_shell.binder import model as m
from tess_shell.schema import blocks

_BOX_KEYS = frozenset(blocks.MARQUEE_BOX[0]) | frozenset(blocks.MARQUEE_BOX[1])
_TEXT_PROPS, _TEXT_STYLE = blocks.INTERNAL[m.MARQUEE_TEXT]
_TEXT_KEYS = frozenset(_TEXT_PROPS) | frozenset(_TEXT_STYLE)


def _token(path: str, kind: str, origin: m.Origin) -> m.TokenRef:
    return m.TokenRef(path, kind, origin=origin)


def compose(node: m.Node) -> m.Node:
    """The ``Marquee`` block ``node`` as its clipping box with the text as its one child. A node
    that is not a ``Marquee`` is returned as it is."""
    if node.kind != m.MARQUEE:
        return node
    origin = node.origin
    box: tuple[dict[str, m.Value], dict[str, m.Value]] = ({}, {})
    text: tuple[dict[str, m.Value], dict[str, m.Value]] = ({}, {})
    for scope, values in enumerate((node.props, node.style)):  # 0: written on the block, 1: Style
        for key, value in values.items():
            if key in _BOX_KEYS:
                box[scope][key] = value
            elif key in _TEXT_KEYS:
                text[scope if key in _TEXT_STYLE else 0][key] = value
    # the look of a text that is given none: the theme's text colour and body size
    for key, kind in (("Foreground", "color"), ("Font_Size", "positive")):
        if key not in text[1]:
            path = "color.on_surface" if key == "Foreground" else "type.body.font_size"
            text[1][key] = _token(path, kind, origin)
    words = text[0].get("Text")
    if words is not None and "Label" not in box[0]:
        box[0]["Label"] = words  # the whole text is the name, however much of it shows
    box_states, text_states = _split_states(node.states)
    child = m.Node(m.MARQUEE_TEXT, props=text[0], style=text[1], states=text_states, origin=origin)
    return dataclasses.replace(
        node, props=box[0], style=box[1], states=box_states, children=(child,)
    )


def _split_states(
    states: Mapping[str, Mapping[str, m.Value]],
) -> tuple[dict[str, Mapping[str, m.Value]], dict[str, Mapping[str, m.Value]]]:
    box: dict[str, Mapping[str, m.Value]] = {}
    text: dict[str, Mapping[str, m.Value]] = {}
    for state, values in states.items():
        mine = {k: v for k, v in values.items() if k in _BOX_KEYS}
        theirs = {k: v for k, v in values.items() if k in _TEXT_KEYS and k not in _BOX_KEYS}
        if mine:
            box[state] = mine
        if theirs:
            text[state] = theirs
    return box, text
