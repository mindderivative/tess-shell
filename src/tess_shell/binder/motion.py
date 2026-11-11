"""Transitions: a change of a listed key eases instead of jumping (Style Schema > Motion keys).

``Transition: [Width, Opacity]`` lists the keys, ``Duration`` is the time in milliseconds (the
theme's ``motion.duration.medium`` when it is not written; 0 under reduced motion, which the model
resolves) and ``Easing`` is STANDARD, EMPHASIZED or LINEAR. A block built with a value shows it at
once: only a *change* of a listed key animates, and tre runs the animation (``Node.animate``), so
nothing runs in Python while it plays and the window draws no frame when it is over.

tre animates a size to a number of pixels only. A size that changes to ``AUTO`` is measured first
(the node is laid out at ``auto`` and read back) and an animation to a percentage is to that part
of the parent's laid-out size; when it arrives the node is set to ``auto`` or the percentage again,
so it follows its content and its parent afterwards. This is what an Expander and a ProgressBar do.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from tess_shell.binder.model import BindError, Node, Number, Seq, Text, Value
from tess_shell.binder.tables import BLOCKS

if TYPE_CHECKING:
    from tess_re import Node as TreNode

DEFAULT_DURATION = 200  # milliseconds, when no theme gave one
EASINGS: Mapping[str, Any] = {
    "STANDARD": (0.2, 0.0, 0.0, 1.0),
    "EMPHASIZED": (0.05, 0.7, 0.1, 1.0),
    "LINEAR": "linear",
}
# the tre properties that animate to a number or a colour
ANIMATABLE = frozenset(
    {
        "fill",
        "stroke_color",
        "stroke_width",
        "opacity",
        "corner_radius",
        "shadows",
        "translate_x",
        "translate_y",
        "scale",
        "rotation_deg",
        "width",
        "height",
        "min_width",
        "min_height",
        "max_width",
        "max_height",
        "gap",
        "padding_top",
        "padding_right",
        "padding_bottom",
        "padding_left",
        "margin_top",
        "margin_right",
        "margin_bottom",
        "margin_left",
        "svg_color",
    }
)
_SIZES = ("width", "height")


@dataclass(frozen=True, slots=True)
class Motion:
    """Which tre properties ease when they change, for how long and how."""

    props: frozenset[str]
    duration: int  # milliseconds
    easing: Any  # tre's easing argument


def _words(listed: Value | None) -> list[str]:
    items = listed.items if isinstance(listed, Seq) else (listed,)
    return [i.value for i in items if isinstance(i, Text)]


def _written(node: Node, key: str) -> Value | None:
    return node.style.get(key) or node.props.get(key)


def motion_of(node: Node) -> Motion | None:
    """The transition ``node`` asks for, or ``None``: no ``Transition``, a ``Duration`` of 0 or a
    list that names no key that can ease."""
    row = BLOCKS.get(node.kind)
    listed = _written(node, "Transition")
    if row is None or listed is None:
        return None
    keys = {**row.keys, **row.style}
    props = frozenset(
        name
        for word in _words(listed)
        if word in keys
        for name in keys[word].tre
        if name in ANIMATABLE
    )
    duration = _written(node, "Duration")
    ms = DEFAULT_DURATION if not isinstance(duration, Number) else int(duration.value)
    if not props or ms <= 0:
        return None
    easing = _written(node, "Easing")
    word = getattr(easing, "name", "STANDARD")
    return Motion(props, ms, EASINGS.get(word, EASINGS["STANDARD"]))


def check(node: Node) -> list[BindError]:
    """The words of ``Transition`` that name no key of the block, or one that cannot ease."""
    row = BLOCKS.get(node.kind)
    listed = _written(node, "Transition")
    if row is None or listed is None:
        return []
    keys = {**row.keys, **row.style}
    errors: list[BindError] = []
    for word in _words(listed):
        key = keys.get(word)
        if key is None or not any(n in ANIMATABLE for n in key.tre):
            can = sorted(k for k, v in keys.items() if any(n in ANIMATABLE for n in v.tre))
            errors.append(
                BindError(
                    f"Transition names {word}, which a {node.kind} cannot animate",
                    listed.origin,
                    f"it can animate: {', '.join(can)}",
                )
            )
    return errors


def start(tre: TreNode, changes: Mapping[str, Any], motion: Motion) -> dict[str, Any]:
    """Begin the animation of each change that ``motion`` lists; return the changes left, which
    the caller sets as they are."""
    rest: dict[str, Any] = {}
    for name, value in changes.items():
        if name not in motion.props or not _animate(tre, name, value, motion):
            rest[name] = value
    return rest


def _animate(tre: TreNode, name: str, value: Any, motion: Motion) -> bool:
    try:
        if name in _SIZES and (value == "auto" or _percent(value) is not None):
            return _to_relative(tre, name, value, motion)
        if isinstance(value, str):
            return False
        tre.animate(name, value, motion.duration, motion.easing)
        return True
    except ValueError, TypeError:
        return False


def _percent(value: Any) -> float | None:
    if isinstance(value, str) and value.endswith("%"):
        try:
            return float(value[:-1])
        except ValueError:
            return None
    return None


def _to_relative(tre: TreNode, name: str, value: str, motion: Motion) -> bool:
    """Animate a width or height to ``auto`` or to a percentage: measure where it ends, start from
    where it is, and settle on the written value when it arrives."""
    side = f"layout_{name}"
    now = float(tre.get(side))  # what is on screen, before anything changes
    percent = _percent(value)
    if percent is not None:
        parent = tre.parent()
        if parent is None:
            return False
        target = float(parent.get(side)) * percent / 100
    else:
        tre.set(**{name: "auto"})
        target = float(tre.get(side))
    tre.set(**{name: now})  # ends an animation that was running, and starts from here

    def settle() -> None:
        try:
            tre.set(**{name: value})
        except ValueError:  # the node is gone
            return

    tre.animate(name, target, motion.duration, motion.easing, on_complete=settle)
    return True
