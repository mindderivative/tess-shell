"""``Event.rect`` (Events and Actions): the block a pointer event was raised on, ``(x, y, width,
height)`` in the output's coordinates, for the four pointer events; and ``ctx.popup(anchor=...)``,
which opens a Popup beside such a rectangle. Headless: a real binder, host and Popups."""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

import pytest

from tess_shell.surfaces.bar import Rect, surface_rect
from tests.fake_dbus import HAVE_DAEMON
from tests.test_tray_module import centre, ids, item_node, settle, up
from tests.tray_rig import tray_desk, tray_shell
from tests.widgets_live import running

DRIVER = (
    "Module { FlexBox { Name: Root, Flex: HORIZONTAL, Children { "
    "FlexBox { Name: A, Width: 30, Height: 20, On_Click: note, On_Secondary_Click: note, "
    "On_Middle_Click: note, On_Scroll: note } "
    "FlexBox { Name: B, Width: 50, Height: 24, Margin: [0, 0, 0, 7], On_Click: note } } } }"
)
DRIVER_PY = """
from tess_shell import Module, action

class Driver(Module):
    def __init__(self):
        self.events = []

    @action
    def note(self, event):
        self.events.append(event)
"""
POPUPS = (
    "Popup { Name: Menu_Popup, Attach: BOTTOM, Style { Background: $color.surface_raised }, "
    "Children { Label { Text: Inside, Name: Inside } } }"
)


def shifted(w: Any, margin: tuple[int, int, int, int]) -> Rect:
    """Move the Bar on the output (as a margin would) and say where its window is now."""
    s = w.bar
    s.geometry = dataclasses.replace(s.geometry, margin=margin)
    return surface_rect(s.geometry, (s.planned.output.width, s.planned.output.height))


def block(w: Any, name: str) -> tuple[float, float, float, float]:
    node = w.of_use("Driver", name)
    return tuple(  # type: ignore[return-value]
        float(node.get(k)) for k in ("layout_x", "layout_y", "layout_width", "layout_height")
    )


def test_each_pointer_event_carries_the_blocks_rectangle_in_output_coordinates() -> None:
    with running("Driver { }", driver=DRIVER, driver_py=DRIVER_PY) as w:
        origin = shifted(w, (10, 0, 0, 20))
        a, b = block(w, "A"), block(w, "B")
        a_node, b_node = w.of_use("Driver", "A"), w.of_use("Driver", "B")
        w.window.simulate("click", node=a_node)
        w.window.simulate("secondary_click", node=a_node)
        w.window.simulate("pointer_down", node=a_node, button="middle")
        w.window.simulate("pointer_up", node=a_node, button="middle")
        w.window.simulate("wheel", node=a_node, delta_y=10.0)
        w.window.simulate("click", node=b_node)
        events = w.host.loaded["Driver"].instance.events
    assert [e.name for e in events] == [
        "click",
        "secondary_click",
        "middle_click",
        "scroll",
        "click",
    ]
    want_a = (origin.x + a[0], origin.y + a[1], a[2], a[3])
    want_b = (origin.x + b[0], origin.y + b[1], b[2], b[3])
    assert [e.rect for e in events[:4]] == [want_a] * 4
    assert events[4].rect == want_b and want_b[2:] == (50.0, 24.0)
    assert want_b[0] - want_a[0] >= 30  # the second block is further right: its own box


def test_a_block_in_a_popup_has_no_rect_and_a_non_pointer_event_neither() -> None:
    driver = "Module { FlexBox { Name: Root, Width: 40, Height: 20, On_Click: open_it } }"
    py = DRIVER_PY + (
        "\n    @action\n    def open_it(self, event):\n"
        "        self.events.append(event)\n"
        "        self.ctx.popup('Menu_Popup', anchor=event.rect)\n"
    )
    with running("Driver { }", driver=driver, driver_py=py, popups=POPUPS) as w:
        w.window.simulate("click", node=w.of_use("Driver", "Root"))
        assert w.manager.popups.current is not None
        (event,) = w.host.loaded["Driver"].instance.events
        assert event.rect == (0.0, 0.0, 40.0, 20.0)  # a Bar at the output's origin


def test_a_popup_with_an_anchor_opens_beside_it_and_not_beside_the_use() -> None:
    driver = (
        "Module { FlexBox { Name: Root, Width: 200, Height: 20, Flex: HORIZONTAL, Children { "
        "FlexBox { Name: A, Width: 30, Height: 20 } "
        "FlexBox { Name: B, Width: 30, Height: 20, On_Click: open_it } } } }"
    )
    py = DRIVER_PY + (
        "\n    @action\n    def open_it(self, event):\n"
        "        self.ctx.popup('Menu_Popup', anchor=event.rect)\n"
    )
    with running("Driver { }", driver=driver, driver_py=py, popups=POPUPS) as w:
        w.window.simulate("click", node=w.of_use("Driver", "B"))
        op = w.manager.popups.current
        assert op is not None
        b = block(w, "B")
        root = block(w, "Root")
        assert b[0] > root[0]  # B is not where the use's first block is
        rect = op.caller.rect  # in the surface's window coordinates
        assert (rect.x, rect.y, rect.width, rect.height) == b


def test_an_anchor_in_output_coordinates_is_taken_back_to_the_surface_window() -> None:
    driver = "Module { FlexBox { Name: Root, Width: 60, Height: 20, On_Click: open_it } }"
    py = DRIVER_PY + (
        "\n    @action\n    def open_it(self, event):\n"
        "        self.ctx.popup('Menu_Popup', anchor=event.rect)\n"
    )
    with running("Driver { }", driver=driver, driver_py=py, popups=POPUPS) as w:
        shifted(w, (10, 0, 0, 20))
        w.window.simulate("click", node=w.of_use("Driver", "Root"))
        op = w.manager.popups.current
        assert op is not None
        assert (op.caller.rect.x, op.caller.rect.y) == (0.0, 0.0)  # the block, in its window


# -- the Tray -----------------------------------------------------------------------------------


@pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")
def test_the_tray_sends_the_icons_centre_and_opens_the_menu_beside_the_icon(
    tmp_path: Path,
) -> None:
    from tests.fake_sni import sample_tree

    with tray_desk(tmp_path) as t:
        a, b = t.item("1-1", menu=sample_tree()), t.item("2-1", menu=sample_tree())
        up(t, a, b)
        with tray_shell(t) as w:
            assert settle(t, w, lambda: len(ids(w)) == 2)
            origin = shifted(w, (6, 0, 0, 30))
            second = item_node(w, 1)
            cx, cy = centre(second)
            w.window.simulate("secondary_click", node=second)
            assert settle(t, w, lambda: w.manager.popups.current is not None)
            op = w.manager.popups.current
            assert op is not None
            rect = op.caller.rect  # beside the SECOND icon, not the whole row
            x, y, wd, ht = (
                float(second.get(k))
                for k in ("layout_x", "layout_y", "layout_width", "layout_height")
            )
            assert (rect.x, rect.y, rect.width, rect.height) == (x, y, wd, ht)
            tray_root = w.of_use("Tray", "Root")
            assert float(tray_root.get("layout_width")) > wd  # the row is wider than one icon
            # the click calls send the icon's centre in OUTPUT coordinates
            w.manager.popups.close_current("test")
            c = item_node(w, 0)
            w.window.simulate("click", node=c)
            from tests.fake_dbus import wait_for

            assert wait_for(lambda: bool([m for m, _ in a.calls if m == "Activate"]), 5)
            (args,) = [x for m, x in a.calls if m == "Activate"]
            ccx, ccy = centre(c)
            assert args == (round(origin.x + ccx), round(origin.y + ccy))
            assert (cx, cy) != (ccx, ccy)
