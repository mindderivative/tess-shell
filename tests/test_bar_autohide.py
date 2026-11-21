"""``Auto_Hide`` of a Bar (headless: ``advance`` runs the engine's timers and animations)."""

from __future__ import annotations

from typing import Any

from tess_shell.appearance import Appearance
from tess_shell.schema.model import BarDef
from tests.test_panel import manager, surface

NO_AUTO = (
    "Bar { Name: Fixed, Edge: BOTTOM, Width: EXPAND, Height: 30, Auto_Hide: false, Children {\n"
    "  Rectangle { Name: Dot, Width: 10, Height: 10 } } }"
)
SLOW = (
    "Bar { Name: Slow, Edge: LEFT, Width: 40, Height: EXPAND, Auto_Hide_Delay: 3000, Children {\n"
    "  Rectangle { Name: Dot, Width: 10, Height: 10 } } }"
)


def zone(s: Any) -> int:
    return s.window.get("exclusive_zone")  # type: ignore[no-any-return]


def enter(s: Any) -> None:
    s.window.simulate("pointer_enter", node=s.window.root)


def leave(s: Any) -> None:
    enter(s)  # the pointer was on the Bar (a leave needs a pointer inside the window)
    s.window.simulate("pointer_leave")


def test_a_bar_hides_itself_by_default_and_the_delay_is_a_second() -> None:
    m = manager(hide_mode="KEEP")
    bar = surface(m, "Top_Bar")
    assert isinstance(bar.planned.bar, BarDef) and bar.planned.bar.auto_hide  # type: ignore[union-attr]
    assert bar.planned.bar.auto_hide_delay == 1000  # type: ignore[union-attr]


def test_a_bar_slides_out_after_the_delay_then_gives_its_space_back() -> None:
    m = manager(hide_mode="KEEP")
    s = surface(m, "Top_Bar")
    leave(s)
    s.window.advance(900)
    assert not s.auto_out and zone(s) == 32
    s.window.advance(150)  # the delay ends: the slide starts, the zone is still full
    assert s.auto_out and zone(s) == 32
    s.window.advance(250)  # the slide ends: the space is released, a strip is left
    assert zone(s) == 0 and s.window.get("margin")[0] == 1 - 32
    assert s.window.get("input_region") == [(0, 31, s.planned.output.width, 1)]


def test_the_pointer_coming_back_before_the_delay_cancels_it() -> None:
    m = manager(hide_mode="KEEP")
    s = surface(m, "Top_Bar")
    leave(s)
    s.window.advance(900)
    enter(s)
    s.window.advance(500)
    assert not s.auto_out
    leave(s)
    s.window.advance(900)
    assert not s.auto_out  # the next leave waits a whole delay


def test_the_pointer_on_the_strip_brings_it_back_zone_first() -> None:
    m = manager(hide_mode="KEEP")
    s = surface(m, "Top_Bar")
    leave(s)
    s.window.advance(1500)
    assert zone(s) == 0
    enter(s)
    assert not s.auto_out and zone(s) == 32  # the zone first
    assert s.window.get("margin")[0] == 1 - 32  # the slide has not run yet
    s.window.advance(250)
    assert s.window.get("margin") == s.geometry.margin
    assert s.window.get("input_region") != [(0, 31, s.planned.output.width, 1)]


def test_auto_hide_false_keeps_the_bar_and_its_zone() -> None:
    m = manager(panel=NO_AUTO, hide_mode="KEEP")
    s = surface(m, "Fixed")
    leave(s)
    s.window.advance(5000)
    assert not s.auto_out and zone(s) == 30


def test_auto_hide_delay_is_the_bars_own() -> None:
    m = manager(panel=SLOW, hide_mode="KEEP")
    s = surface(m, "Slow")
    leave(s)
    s.window.advance(2900)
    assert not s.auto_out
    s.window.advance(200)
    assert s.auto_out


def test_a_bar_with_the_keyboard_does_not_hide_until_it_lets_go() -> None:
    m = manager(hide_mode="KEEP")
    s = surface(m, "Top_Bar")
    m.focused = "Top_Bar"
    leave(s)
    s.window.advance(3500)
    assert not s.auto_out
    m.focused = None
    s.window.advance(1100)
    assert s.auto_out


def test_reduced_motion_slides_out_in_one_step() -> None:
    m = manager(hide_mode="KEEP", appearance=Appearance(animations=False))
    s = surface(m, "Top_Bar")
    leave(s)
    s.window.advance(1001)
    assert s.auto_out and zone(s) == 0 and s.window.get("margin")[0] == 1 - 32


def test_a_hide_by_the_user_is_not_the_strip() -> None:
    m = manager(hide_mode="KEEP")
    s = surface(m, "Top_Bar")
    leave(s)
    s.window.advance(1500)
    m.hide(s)
    assert s.hidden and not s.auto_out and s.window.get("input_region") == []
    m.show(s)
    assert zone(s) == 32 and s.window.get("margin") == s.geometry.margin


def test_shortcut_mode_brings_a_slid_out_bar_back_and_leaving_it_sends_it_out_again() -> None:
    m = manager(hide_mode="KEEP")
    s = surface(m, "Top_Bar")
    leave(s)
    s.window.advance(1500)
    assert s.auto_out and zone(s) == 0
    m.mode.enter()
    assert not s.auto_out and zone(s) == 32 and s.mode_revealed
    s.window.advance(5000)  # the mode holds it: no delay hides it
    assert not s.auto_out
    m.mode.exit()
    s.window.advance(900)
    assert not s.auto_out
    s.window.advance(1300)  # the delay, then the slide
    assert s.auto_out and zone(s) == 0 and not s.mode_revealed


def test_a_bar_that_stays_written_auto_hide_false_is_untouched_by_the_mode() -> None:
    m = manager(panel=NO_AUTO, hide_mode="KEEP")
    s = surface(m, "Fixed")
    m.mode.enter()
    m.mode.exit()
    s.window.advance(5000)
    assert not s.auto_out and not s.mode_revealed and zone(s) == 30
