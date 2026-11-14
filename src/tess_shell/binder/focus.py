"""Which blocks take keyboard focus, and in what order (Focus and Keyboard).

Pure functions over :mod:`tess_shell.binder.model`. tre does the traversing: a node with
``focusable`` is a Tab stop, Tab and Shift+Tab walk the stops (the first positive ``tab_index``
ascending, then the rest in tree order, and round again), and ``focus_visible`` on its ``focus``
event says whether the keyboard moved it. What is the shell's is the data: which blocks are
focusable (:func:`default_focusable`), where a ``Tab_Index`` puts a block (:func:`tab_order`) and
which blocks show a ring (:func:`takes_ring`).
"""

from __future__ import annotations

from collections.abc import Sequence

from tess_shell.binder.model import FIELD, FIELD_INPUT, Bool, Enum, Node

# The roles of a block that takes input and is a Tab stop on its own. A List or a Menu is one stop
# whose entries are reached by the arrow keys, and an entry takes no Tab stop: that is the keyboard
# operation of M6b, so those roles are not here yet.
INTERACTIVE_ROLES = frozenset(
    {"BUTTON", "CHECKBOX", "RADIO", "SWITCH", "SLIDER", "LINK", "TAB"},
)


def default_focusable(node: Node) -> bool:
    """Whether a block with no ``Focusable`` key takes focus: a block with an interactive role, a
    block a control makes a switch or a slider (``Toggles``, ``Slides``). A TextField's text input
    is focusable in tre already."""
    role = node.props.get("Role")
    if isinstance(role, Enum) and role.name in INTERACTIVE_ROLES:
        return True
    toggles = node.props.get("Toggles")
    if isinstance(toggles, Bool) and toggles.value:
        return True
    slides = node.props.get("Slides")
    return isinstance(slides, Enum) and slides.name != "NONE"


def _field_input(box: Node) -> Node | None:
    """The text input of a composed TextField (in the line box that is the box's one child)."""
    for line in box.children:
        if isinstance(line, Node):
            for child in line.children:
                if isinstance(child, Node) and child.kind == FIELD_INPUT:
                    return child
    return None


def takes_ring(node: Node) -> bool:
    """Whether keyboard focus on this block shows a ring: a focusable block, and a TextField's
    box when its text input is focusable. The text input itself shows none: its box does."""
    if node.kind == FIELD_INPUT:
        return False
    if node.kind == FIELD:
        inner = _field_input(node)
        flag = None if inner is None else inner.props.get("Focusable")
        return inner is not None and not (isinstance(flag, Bool) and not flag.value)
    flag = node.props.get("Focusable")
    if isinstance(flag, Bool):
        return flag.value
    return default_focusable(node)


def tab_order(indices: Sequence[int | None]) -> list[int]:
    """The positions of ``indices`` (given in document order) in Tab order: ascending ``Tab_Index``,
    equal indices in document order, and the items with no ``Tab_Index`` after all the others, in
    document order (Focus and Keyboard > Tab Order)."""
    return sorted(range(len(indices)), key=lambda i: (indices[i] is None, indices[i] or 0, i))
