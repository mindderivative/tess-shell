"""A closed Popup keeps nothing of what the shell built for it (Popup retention; the Popup half of
``tests/test_reload_leak.py``).

tre's ``App`` keeps every window it was given, closed or not, so with a real ``tess_re.App`` (the
stub app of ``tests/test_popup.py`` ignores ``add_window``, which is why no popup test saw this)
a closed Popup's window object stays. What it held was the shell's: the listeners on the window and
its nodes held the ``OpenPopup``, its ``LiveTree`` and its content tree. ``Popups._closed`` takes
them off. The windows are real tre windows with no compositor; ``closed`` is delivered the way tre
delivers it, once the shell has asked for the close.
"""

from __future__ import annotations

import gc
import tracemalloc
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from loguru import logger

from tests.reload_rig import RealApp, count_objects
from tests.test_popup import CARD, HOT, TIP, Rig, card, hover, rig

CYCLES, WARM = 100, 10
SHELL_TYPES = ("OpenPopup", "LiveTree", "View", "Surface")
# a closed window's own state is tre's (about 1.5 KiB per Popup measured); the shell's part was 5.7
# KiB per Popup (the unfixed code leaks more than twice this bound with one Popup per cycle)
HEAP_PER_POPUP = 3 * 1024

MENUS = (
    f"Popup {{ Name: Menu, Gap: 4, Alignment: END, Children {{ {CARD} }} }} "
    f"Popup {{ Name: Other, Children {{ {card('Card_Two')} }} }} "
    + TIP.replace(CARD, card("Card_Three"))
)
BAR = "Btn { Name: Btn_One } " + HOT


class Tre:
    """What tre does that a headless window does not: it sends ``closed`` for a window the shell
    closed, one turn later."""

    def __init__(self, r: Rig) -> None:
        self.r = r
        self.asked: list[Any] = []  # Popups opened and not yet delivered their ``closed``
        self.opened = 0
        opener = r.popups.open

        def open_and_note(*args: Any, **kwargs: Any) -> Any:
            op = opener(*args, **kwargs)
            if op is not None:
                self.asked.append(op)
                self.opened += 1
            return op

        r.popups.open = open_and_note

    def turn(self) -> None:
        self.r.advance(16)
        for op in [o for o in self.asked if o.closing]:
            self.asked.remove(op)
            op.window.simulate("closed")
        self.r.advance(16)


def call_and_close(r: Rig, tre: Tre) -> None:
    r.call("Menu")
    tre.turn()
    r.call("Menu")  # a second call toggles it closed
    tre.turn()


def replaced_by_another(r: Rig, tre: Tre) -> None:
    r.call("Menu")
    tre.turn()
    r.call("Other")  # a Popup of another name closes the open one
    tre.turn()
    r.popups.close_current("test")
    tre.turn()


def opened_while_closing(r: Rig, tre: Tre) -> None:
    r.call("Menu")
    r.popups.close_current("test")
    r.call("Menu")  # the first one's ``closed`` has not arrived yet
    r.popups.close_current("test")
    tre.turn()


def dismissed_by_the_compositor(r: Rig, tre: Tre) -> None:
    op = r.call("Menu")
    tre.turn()
    tre.asked.remove(op)
    op.window.simulate("closed")  # tre's ``closed`` with no close asked for by the shell
    tre.turn()


def tooltip(r: Rig, tre: Tre) -> None:
    hover(r)
    r.advance(101)
    assert r.popups.current is not None
    hover(r, False)
    r.advance(60)
    tre.turn()


def submenu(r: Rig, tre: Tre) -> None:
    op = r.call("Menu")
    tre.turn()
    plan = next(p for (_, name), p in r.popups.plans.items() if name == "Other")
    sub = r.popups.open(plan, r.bar, "Card", r.use, "Btn", parent=op)
    assert sub is not None and op.sub is sub
    tre.turn()
    r.popups.close(op, "test")  # the submenu goes first, then its parent
    tre.turn()


PATHS: dict[str, tuple[Callable[[Rig, Tre], None], int]] = {
    "call and close": (call_and_close, 1),
    "replaced by another popup": (replaced_by_another, 2),
    "opened while closing": (opened_while_closing, 2),
    "dismissed by the compositor": (dismissed_by_the_compositor, 1),
    "tooltip": (tooltip, 1),
    "submenu and its parent": (submenu, 2),
}


class Reading:
    def __init__(self, name: str) -> None:
        cycle, per_cycle = PATHS[name]
        (r,) = list(rig(MENUS, BAR, app=RealApp()))
        logger.remove()  # the rig's log sink keeps every line: it would be the heap's growth
        tre = Tre(r)
        for _ in range(WARM):
            cycle(r, tre)
        tracemalloc.start()
        try:
            gc.collect()
            self.before = count_objects(*SHELL_TYPES, "PopupWindow")
            heap = tracemalloc.get_traced_memory()[0]
            opened = tre.opened
            for _ in range(CYCLES):
                cycle(r, tre)
            gc.collect()
            self.after = count_objects(*SHELL_TYPES, "PopupWindow")
            self.heap = tracemalloc.get_traced_memory()[0] - heap
            self.popups = tre.opened - opened
        finally:
            tracemalloc.stop()
        assert self.popups == CYCLES * per_cycle
        assert not r.popups.chain()

    def grew(self, name: str) -> int:
        return self.after[name] - self.before[name]


@pytest.fixture(scope="module", params=list(PATHS))
def path(request: pytest.FixtureRequest) -> Iterator[tuple[str, Reading]]:
    name = request.param
    yield name, Reading(name)


def test_a_closed_popup_leaves_no_open_popup_live_tree_or_view_behind(
    path: tuple[str, Reading],
) -> None:
    name, reading = path
    for type_name in SHELL_TYPES:
        assert reading.grew(type_name) == 0, (name, reading.before, reading.after)


def test_the_python_heap_grows_only_by_what_tre_keeps_of_a_closed_window(
    path: tuple[str, Reading],
) -> None:
    name, reading = path
    assert reading.heap <= HEAP_PER_POPUP * reading.popups, (name, reading.heap, reading.popups)


@pytest.mark.xfail(
    strict=True,
    reason="tre's App keeps the object of every window it was given, closed or not (TRE-REQ-028)",
)
def test_tre_lets_go_of_a_closed_popup_window(path: tuple[str, Reading]) -> None:
    _, reading = path
    assert reading.grew("PopupWindow") == 0
