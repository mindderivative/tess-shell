"""``Auto_Hide`` of a Bar (headless: ``advance`` runs the engine's timers and animations)."""

from __future__ import annotations

from typing import Any

from tess_shell.appearance import Appearance
from tess_shell.schema.model import BarDef
from tests.test_panel import manager, surface

AUTO = (
    "Bar { Name: Auto, Edge: BOTTOM, Width: EXPAND, Height: 30, Auto_Hide: true, Children {\n"
    "  Rectangle { Name: Dot, Width: 10, Height: 10 } } }"
)
NO_AUTO = (
    "Bar { Name: Fixed, Edge: BOTTOM, Width: EXPAND, Height: 30, Auto_Hide: false, Children {\n"
    "  Rectangle { Name: Dot, Width: 10, Height: 10 } } }"
)
SLOW = (
    "Bar { Name: Slow, Edge: LEFT, Width: 40, Height: EXPAND, Auto_Hide: true,\n"
    "  Auto_Hide_Delay: 3000, Children {\n"
    "  Rectangle { Name: Dot, Width: 10, Height: 10 } } }"
)


def zone(s: Any) -> int:
    return s.window.get("exclusive_zone")  # type: ignore[no-any-return]


def enter(s: Any) -> None:
    s.window.simulate("pointer_enter", node=s.window.root)


def leave(s: Any) -> None:
    enter(s)  # the pointer was on the Bar (a leave needs a pointer inside the window)
    s.window.simulate("pointer_leave")


def auto() -> tuple[Any, Any]:
    m = manager(panel=AUTO, hide_mode="KEEP")
    return m, surface(m, "Auto")


def test_auto_hide_is_off_unless_a_bar_writes_it_and_the_delay_is_a_second() -> None:
    m = manager(hide_mode="KEEP")
    plain = surface(m, "Top_Bar")
    assert isinstance(plain.planned.bar, BarDef)  # type: ignore[union-attr]
    assert plain.planned.bar.auto_hide is False and plain.planned.bar.auto_hide_delay == 1000
    leave(plain)
    plain.window.advance(5000)
    assert not plain.auto_out and zone(plain) == 32


def test_a_bar_slides_out_after_the_delay_then_gives_its_space_back() -> None:
    _, s = auto()
    leave(s)
    s.window.advance(900)
    assert not s.auto_out and zone(s) == 30
    s.window.advance(150)  # the delay ends: the slide starts, the zone is still full
    assert s.auto_out and zone(s) == 30
    s.window.advance(250)  # the slide ends: the space is released, a strip is left
    assert zone(s) == 0 and s.window.get("margin")[2] == 1 - 30
    assert s.window.get("input_region") == [(0, 0, s.planned.output.width, 1)]


def test_the_pointer_coming_back_before_the_delay_cancels_it() -> None:
    _, s = auto()
    leave(s)
    s.window.advance(900)
    enter(s)
    s.window.advance(500)
    assert not s.auto_out
    leave(s)
    s.window.advance(900)
    assert not s.auto_out  # the next leave waits a whole delay


def test_the_pointer_on_the_strip_brings_it_back_zone_first() -> None:
    _, s = auto()
    leave(s)
    s.window.advance(1500)
    assert zone(s) == 0
    enter(s)
    assert not s.auto_out and zone(s) == 30  # the zone first
    assert s.window.get("margin")[2] == 1 - 30  # the slide has not run yet
    s.window.advance(250)
    assert s.window.get("margin") == s.geometry.margin
    assert s.window.get("input_region") != [(0, 0, s.planned.output.width, 1)]


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
    m, s = auto()
    m.focused = "Auto"
    leave(s)
    s.window.advance(3500)
    assert not s.auto_out
    m.focused = None
    s.window.advance(1100)
    assert s.auto_out


def test_reduced_motion_slides_out_in_one_step() -> None:
    m = manager(panel=AUTO, hide_mode="KEEP", appearance=Appearance(animations=False))
    s = surface(m, "Auto")
    leave(s)
    s.window.advance(1001)
    assert s.auto_out and zone(s) == 0 and s.window.get("margin")[2] == 1 - 30


def test_a_hide_by_the_user_is_not_the_strip() -> None:
    m, s = auto()
    leave(s)
    s.window.advance(1500)
    m.hide(s)
    assert s.hidden and not s.auto_out and s.window.get("input_region") == []
    m.show(s)
    assert zone(s) == 30 and s.window.get("margin") == s.geometry.margin


def test_shortcut_mode_brings_a_slid_out_bar_back_and_leaving_it_sends_it_out_again() -> None:
    m, s = auto()
    leave(s)
    s.window.advance(1500)
    assert s.auto_out and zone(s) == 0
    m.mode.enter()
    assert not s.auto_out and zone(s) == 30 and s.mode_revealed
    s.window.advance(5000)  # the mode holds it: no delay hides it
    assert not s.auto_out
    m.mode.exit()
    s.window.advance(900)
    assert not s.auto_out
    s.window.advance(1300)  # the delay, then the slide
    assert s.auto_out and zone(s) == 0 and not s.mode_revealed


def test_a_bar_with_auto_hide_false_is_untouched_by_the_mode() -> None:
    m = manager(panel=NO_AUTO, hide_mode="KEEP")
    s = surface(m, "Fixed")
    m.mode.enter()
    m.mode.exit()
    s.window.advance(5000)
    assert not s.auto_out and not s.mode_revealed and zone(s) == 30


def animated(block: str, name: str = "Anim") -> tuple[Any, Any]:
    text = (
        f"Bar {{ Name: {name}, Edge: BOTTOM, Width: EXPAND, Height: 30, Auto_Hide: true, "
        f"{block} Children {{ Rectangle {{ Name: Dot, Width: 10, Height: 10 }} }} }}"
    )
    m = manager(panel=text, hide_mode="KEEP")
    return m, surface(m, name)


def test_a_bar_with_no_animation_block_slides_for_200_ms_and_the_block_defaults_to_slide() -> None:
    _, s = auto()
    assert (s.planned.bar.animation, s.planned.bar.duration) == ("SLIDE", 200)
    _, s = animated("Animation { Duration: 500 },")
    assert (s.planned.bar.animation, s.planned.bar.duration) == ("SLIDE", 500)


def test_the_slide_takes_the_duration_the_bar_writes() -> None:
    _, s = animated("Animation { Type: SLIDE, Duration: 600 },")
    leave(s)
    s.window.advance(1010)  # the delay ends: the slide starts
    assert s.auto_out and zone(s) == 30
    s.window.advance(400)  # 400 ms of 600: the space is still held
    assert zone(s) == 30
    s.window.advance(300)  # 700 ms: the slide has ended
    assert zone(s) == 0 and s.window.get("margin")[2] == 1 - 30


def test_a_fade_goes_out_without_moving_then_leaves_the_strip_and_comes_back_by_fading() -> None:
    _, s = animated("Animation { Type: FADE, Duration: 400 },")
    rest = s.geometry.margin
    leave(s)
    s.window.advance(1200)  # 200 ms into the fade
    assert 0.0 < s.window.root.get("opacity") < 1.0 and s.window.get("margin") == rest
    assert zone(s) == 30
    s.window.advance(
        300
    )  # the fade has ended: off the screen but the strip, opaque for the way back
    assert zone(s) == 0 and s.window.get("margin")[2] == 1 - 30
    assert s.window.root.get("opacity") == 1.0
    enter(s)
    assert zone(s) == 30 and s.window.get("margin") == rest and s.window.root.get("opacity") == 0.0
    s.window.advance(450)
    assert s.window.root.get("opacity") == 1.0 and s.window.get("margin") == rest


def test_animation_none_changes_at_once() -> None:
    _, s = animated("Animation { Type: NONE },")
    leave(s)
    s.window.advance(1001)
    assert s.auto_out and zone(s) == 0 and s.window.get("margin")[2] == 1 - 30
    enter(s)
    assert zone(s) == 30 and s.window.get("margin") == s.geometry.margin


def test_reduced_motion_overrides_a_fade() -> None:
    text = (
        "Bar { Name: R, Edge: BOTTOM, Width: EXPAND, Height: 30, Auto_Hide: true, "
        "Animation { Type: FADE, Duration: 400 }, Children { Rectangle { Name: Dot, Width: 10, "
        "Height: 10 } } }"
    )
    m = manager(panel=text, hide_mode="KEEP", appearance=Appearance(animations=False))
    s = surface(m, "R")
    leave(s)
    s.window.advance(1001)
    assert zone(s) == 0 and s.window.root.get("opacity") == 1.0
