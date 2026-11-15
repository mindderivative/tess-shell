"""A Popup closed before the compositor placed it (tre's ``PopupWindow.close()`` does nothing until
then: found by CI, where the first popup of a cold machine was closed 4 ms before its ``configure``
and stayed on screen)."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from tess_shell.surfaces.popup import OpenPopup, Popups


class Window:
    def __init__(self) -> None:
        self.closed = 0

    def close(self) -> None:
        self.closed += 1


def make() -> tuple[Popups, OpenPopup, Window]:
    manager = SimpleNamespace(settle_dynamic=lambda: None)
    popups = Popups(manager)  # type: ignore[arg-type]
    window = Window()
    live = SimpleNamespace(release=lambda: None)
    rect = SimpleNamespace(x=0, y=0, bottom=20, right=60)
    caller: Any = SimpleNamespace(module="Btn", use="u", rect=rect)
    op = OpenPopup(
        None, window, None, live, None, caller, "Menu on X", 0.0, size=(100, 40), attach="BOTTOM"
    )  # type: ignore[arg-type]
    popups.current = op
    return popups, op, window


def test_a_popup_closed_before_it_is_placed_is_closed_in_tre_when_it_is_placed() -> None:
    popups, op, window = make()
    popups.close(op, "replaced")
    assert window.closed == 0  # tre would ignore it now
    popups._configured(op, SimpleNamespace(x=4, y=24, width=100, height=40))  # type: ignore[arg-type]
    assert window.closed == 1 and not op.close_pending


def test_a_placed_popup_is_closed_at_once_and_only_once() -> None:
    popups, op, window = make()
    op.placed = (4, 24)
    popups.close(op, "toggled")
    popups.close(op, "toggled")
    assert window.closed == 1
