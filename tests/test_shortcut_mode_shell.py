"""Shortcut mode through the real surface manager, headless (T-050, Focus and Keyboard > Shortcut
Mode): a Frame with two peeks (a peeking strip and a peeking melded Panel), two Panels and a Bar,
real tre windows over a stub ``App`` (``tests/mode_rig.py``). ``tests/test_shortcut_mode.py`` is
the rules; this is what the manager does with each change: who takes the keyboard (the window
property), which peeks are out, where the focus ring is, what a key does, what a reload and a
closing surface do."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from tess_shell.schema.keys import parse_chord
from tests.mode_rig import DOCK, FRAME, TAB, Make, Rig, rigs, text


@pytest.fixture
def rig() -> Iterator[Make]:
    yield from rigs()


# -- the surfaces and their order -----------------------------------------------------------


def test_the_order_is_tab_index_with_the_frame_first_and_the_strip_by_its_own_index(
    rig: Make,
) -> None:
    r = rig()
    assert r.mode.machine.order == ["F", "Dock", "Top_Bar", "F.top", "Launcher"]
    assert r.mode.machine.lowest == "F" and r.state == (None, None)


# -- Enter: the Frame, its focus, every peek (rule 3, 4, 7) --------------------------------


def test_enter_puts_the_frame_in_the_mode_takes_the_keyboard_and_shows_every_peek(
    rig: Make,
) -> None:
    r = rig()
    assert r.at_rest("TopStrip") and r.at_rest("Tab")
    assert r.keyboard("F") == "none"
    r.mode.enter()
    assert r.state == ("F", "F")
    assert r.keyboard("F") == "exclusive"
    r.settle()
    assert r.out("TopStrip") and r.out("Tab")  # all of them at the same time
    assert r.warnings() == []


def test_the_peeks_stay_out_for_the_whole_mode_whatever_their_timers_and_the_pointer_say(
    rig: Make,
) -> None:
    r = rig(text(tab="Hide_After: 100,"))
    r.mode.enter()
    r.settle()
    r.frame.painter.advance(5000)  # a Hide_After of 100 ms ran out long ago
    assert r.out("Tab") and r.out("TopStrip")
    st = r.frame
    for host in st.hosts.values():  # the pointer left a hover peek: that does not send it back
        host.inside = False
        r.manager.frames._exit(st, host)
    r.settle()
    assert r.out("Tab") and r.out("TopStrip")


def test_leaving_the_mode_sends_the_peeks_back_and_gives_the_keyboard_back(rig: Make) -> None:
    r = rig()
    r.mode.enter()
    r.settle()
    r.mode.exit()
    r.settle()
    assert r.state == (None, None)
    assert r.at_rest("TopStrip") and r.at_rest("Tab")
    assert r.keyboard("F") == "none"


def test_a_peek_that_was_out_before_the_mode_stays_out_after_it(rig: Make) -> None:
    r = rig()
    r.manager.frames.run("Show", "Tab")
    r.settle()
    assert r.out("Tab") and r.at_rest("TopStrip")
    r.mode.enter()
    r.settle()
    r.mode.exit()
    r.settle()
    assert r.out("Tab") and r.at_rest("TopStrip")


def test_mode_keyboard_on_demand_asks_for_on_demand_instead(rig: Make) -> None:
    r = rig(mode_keyboard="ON_DEMAND")
    r.mode.enter()
    assert r.keyboard("F") == "on_demand"
    r.mode.exit()
    assert r.keyboard("F") == "none"


# -- Next_Focus and Previous_Focus (rule 5) -----------------------------------------------------


def test_next_and_previous_move_the_focus_through_the_surfaces_in_tab_index_order_and_wrap(
    rig: Make,
) -> None:
    r = rig()
    r.mode.enter()
    seen = []
    for _ in range(5):
        r.mode.step(True)
        seen.append(r.state[1])
    # the hidden Launcher has no window and is skipped
    assert seen == ["Dock", "Top_Bar", "F.top", "F", "Dock"]
    assert {s for s, _ in [r.state]} == {"F"}  # the Frame stays in the mode
    back = []
    for _ in range(4):
        r.mode.step(False)
        back.append(r.state[1])
    assert back == ["F", "F.top", "Top_Bar", "Dock"]


def test_the_surface_with_the_focus_has_the_keyboard_and_the_one_before_it_has_its_written_word(
    rig: Make,
) -> None:
    r = rig()
    r.mode.enter()
    r.mode.step(True)  # Dock
    assert r.keyboard("Dock") == "exclusive" and r.keyboard("F") == "none"
    r.mode.step(True)  # Top_Bar
    assert r.keyboard("Top_Bar") == "exclusive"
    assert r.keyboard("Dock") == "on_demand"  # what the Dock is written with


def test_the_focus_ring_starts_on_the_first_stop_of_the_surface_that_has_the_focus(
    rig: Make,
) -> None:
    r = rig()
    r.mode.enter()
    r.mode.step(True)  # Dock
    assert r.ring("Dock") == ["B1"]
    r.mode.step(True)  # Top_Bar
    assert r.ring("Top_Bar") == ["Btn"]


def test_a_strip_takes_the_focus_through_the_frames_painter_and_rings_its_first_stop(
    rig: Make,
) -> None:
    r = rig()
    r.mode.enter()
    for _ in range(3):
        r.mode.step(True)
    assert r.state == ("F", "F.top")
    assert r.keyboard("F") == "exclusive"  # the strip is in the painter's window
    host = next(h for h in r.frame.hosts.values() if h.plan.name == "TopStrip")
    assert [k for k, n in host.surface.view.nodes.items() if n.get("focused")] == ["S1"]


def test_next_and_previous_do_nothing_outside_the_mode(rig: Make) -> None:
    r = rig()
    r.mode.step(True)
    r.mode.step(False)
    assert r.state == (None, None)
    assert "Next_Focus: the shell is not in shortcut mode; nothing done" in r.log()
    assert r.warnings() == []


# -- Set_Shortcut_Mode and a surface's own mode (rules 1, 2, 6) --------------------------------


def test_set_on_the_focused_dock_moves_the_mode_to_it_and_the_frames_peeks_go_back(
    rig: Make,
) -> None:
    r = rig()
    r.mode.enter()
    r.mode.step(True)  # Dock
    r.settle()
    assert r.out("Tab")
    r.mode.toggle()
    assert r.state == ("Dock", "Dock")  # rule 1: the Frame's mode is off
    r.settle()
    assert r.at_rest("Tab") and r.at_rest("TopStrip")
    assert r.keyboard("Dock") == "exclusive" and r.keyboard("F") == "none"


def test_set_again_turns_the_whole_shell_off_it_does_not_go_back_to_the_frame(
    rig: Make,
) -> None:
    r = rig()
    r.mode.enter()
    r.mode.step(True)
    r.mode.toggle()
    r.mode.toggle()
    assert r.state == (None, None)
    r.settle()
    assert r.at_rest("Tab") and r.keyboard("Dock") == "on_demand"  # Dock's written word


def test_enter_in_a_docks_own_mode_goes_back_to_the_frame(rig: Make) -> None:
    r = rig()
    r.mode.set_mode("Dock", True)
    r.mode.enter()
    assert r.state == ("F", "F")
    r.settle()
    assert r.out("Tab")


def test_in_a_docks_own_mode_next_and_previous_leave_its_keys_alone(rig: Make) -> None:
    r = rig()
    r.mode.set_mode("Dock", True)
    r.mode.step(True)
    assert r.state == ("Dock", "Dock")
    assert "Dock is the surface in shortcut mode, so the keys of its blocks apply" in r.log()


def test_set_with_no_focus_does_nothing_and_says_so_at_debug(rig: Make) -> None:
    r = rig()
    r.mode.toggle()
    assert r.state == (None, None)
    assert "Set_Shortcut_Mode: no surface has the focus; nothing done" in r.log()


# -- Exit and Escape (rule 3) -------------------------------------------------------------------


def test_exit_clears_every_mode_from_whatever_surface_has_it(rig: Make) -> None:
    r = rig()
    r.mode.set_mode("Top_Bar", True)
    assert r.keyboard("Top_Bar") == "exclusive"
    r.mode.exit()
    assert r.state == (None, None) and r.keyboard("Top_Bar") == "none"


def test_escape_on_the_surface_with_the_focus_leaves_the_mode_when_the_frame_has_it(
    rig: Make,
) -> None:
    r = rig()
    r.mode.enter()
    r.mode.step(True)  # the Dock has the focus, the Frame the mode
    r.key("Dock", "escape")
    assert r.state == (None, None)
    assert r.surface("Dock").hidden is False  # the Dock's own Escape did not run


def test_escape_on_the_frame_leaves_the_mode(rig: Make) -> None:
    r = rig()
    r.mode.enter()
    r.key("F", "escape")
    assert r.state == (None, None)
    r.settle()
    assert r.at_rest("Tab")


def test_escape_in_a_panels_own_mode_is_the_panels_which_hides_it_and_the_mode_ends(
    rig: Make,
) -> None:
    r = rig()
    r.mode.set_mode("Dock", True)
    r.key("Dock", "escape")
    assert r.surface("Dock").hidden is True
    assert r.state == (None, None)


def test_escape_with_no_mode_is_not_taken_by_the_mode(rig: Make) -> None:
    r = rig()
    assert r.mode.on_key(type("E", (), {"key": "escape"})()) is False


# -- the keys of the mode (Shortcuts { }) -----------------------------------------------------


def keys(r: Rig) -> None:
    r.mode.set_keys(
        {
            parse_chord("Ctrl+N"): "Next_Focus",
            parse_chord("Ctrl+Shift+N"): "Previous_Focus",
            parse_chord("Ctrl+Space"): "Set_Shortcut_Mode",
            parse_chord("Ctrl+Q"): "Exit_Shortcut_Mode",
            parse_chord("Ctrl+E"): "Enter_Shortcut_Mode",
        }
    )


def test_the_keys_shortcuts_names_arrive_as_key_events_on_the_surface_with_the_focus(
    rig: Make,
) -> None:
    r = rig()
    keys(r)
    r.mode.enter()
    r.key("F", "n", ctrl=True)
    assert r.state == ("F", "Dock")
    r.key("Dock", "n", ctrl=True)
    assert r.state == ("F", "Top_Bar")
    r.key("Top_Bar", "N", ctrl=True, shift=True)  # tre gives "N" with Shift
    assert r.state == ("F", "Dock")
    r.key("Dock", " ", ctrl=True)  # Set_Shortcut_Mode
    assert r.state == ("Dock", "Dock")
    r.key("Dock", "e", ctrl=True)  # Enter again: back to the Frame
    assert r.state == ("F", "F")
    r.key("F", "q", ctrl=True)
    assert r.state == (None, None)


def test_a_key_the_mode_does_not_know_goes_on_to_the_surface(rig: Make) -> None:
    r = rig()
    keys(r)
    r.mode.enter()
    assert r.mode.on_key(type("E", (), {"key": "x", "ctrl": True})()) is False
    assert r.state == ("F", "F")


def test_a_key_event_names_map_to_the_key_strings_shortcuts_writes() -> None:
    from tess_shell.surfaces.mode import chord_of

    assert chord_of("arrow_left") == parse_chord("Left")
    assert chord_of("page_up", shift=True) == parse_chord("Shift+PageUp")
    assert chord_of("f5", ctrl=True, alt=True) == parse_chord("Ctrl+Alt+F5")
    assert chord_of("tab", shift=True) == parse_chord("Shift+Tab")
    assert chord_of("+") == parse_chord("Plus") and chord_of(" ") == parse_chord("Space")
    assert chord_of("escape") == parse_chord("Escape") and chord_of("enter") == parse_chord("Enter")
    assert chord_of("shift") is None and chord_of("caps_lock") is None and chord_of(None) is None
    assert chord_of("!") is None  # no key name for a symbol that needs Shift to type


def test_in_a_surfaces_own_mode_a_key_bound_to_next_focus_is_left_to_the_surface(
    rig: Make,
) -> None:
    r = rig()
    keys(r)
    r.mode.set_mode("Dock", True)
    event = type("E", (), {"key": "n", "ctrl": True, "stopped": False})()
    assert r.mode.on_key(event) is False  # Next_Focus is the Frame's key: the Dock's blocks win
    assert r.state == ("Dock", "Dock")
    r.key("Dock", " ", ctrl=True)  # Set_Shortcut_Mode still works there
    assert r.state == (None, None)


# -- a surface that closes, a Panel that hides (Failure Modes) -----------------------------------


def test_the_focus_moves_on_when_the_surface_that_has_it_is_hidden(rig: Make) -> None:
    r = rig()
    r.mode.enter()
    r.mode.step(True)  # Dock
    r.manager.hide(r.surface("Dock"))
    assert r.state == ("F", "Top_Bar")
    assert r.keyboard("Top_Bar") == "exclusive"


def test_the_mode_ends_when_the_panel_in_it_is_hidden(rig: Make) -> None:
    r = rig()
    r.mode.set_mode("Dock", True)
    r.manager.hide(r.surface("Dock"))
    assert r.state == (None, None)


def test_a_hidden_panel_is_skipped_and_a_shown_one_takes_its_place_in_the_order(
    rig: Make,
) -> None:
    r = rig()
    r.manager.show(r.surface("Launcher"))
    r.mode.enter()
    seen = []
    for _ in range(5):
        r.mode.step(True)
        seen.append(r.state[1])
    assert seen == ["Dock", "Top_Bar", "F.top", "Launcher", "F"]


def test_a_reload_that_drops_the_surface_with_the_focus_moves_the_focus_on(rig: Make) -> None:
    r = rig()
    r.mode.enter()
    r.mode.step(True)  # Dock
    without_dock = text().replace(DOCK % "", "")
    r.reload(without_dock)
    assert r.state == ("F", "Top_Bar")
    assert r.keyboard("Top_Bar") == "exclusive"


def test_a_reload_that_drops_the_frame_ends_the_mode(rig: Make) -> None:
    r = rig()
    r.mode.enter()
    r.reload(text().replace(FRAME % "", "").replace(TAB % "", ""))  # a meld needs its Frame
    assert r.state == (None, None)


# -- the files: Shortcut_Mode written in them (rules 1, 2) ----------------------------------------


def test_a_surface_written_true_starts_the_shell_in_the_mode_on_that_surface(rig: Make) -> None:
    r = rig(text(dock="Shortcut_Mode: true,"))
    assert r.state == ("Dock", "Dock")
    assert r.keyboard("Dock") == "exclusive"
    assert r.ring("Dock") == ["B1"]


def test_the_frame_written_true_starts_with_every_peek_out(rig: Make) -> None:
    r = rig(text(frame="Shortcut_Mode: true,"))
    assert r.state == ("F", "F")
    r.settle()
    assert r.out("Tab") and r.out("TopStrip")


def test_two_written_true_the_first_in_document_order_has_the_mode(rig: Make) -> None:
    r = rig(text(bar="Shortcut_Mode: true,", dock="Shortcut_Mode: true,"))
    assert r.state == ("Top_Bar", "Top_Bar")  # the file writes the Bar before the Dock
    assert r.keyboard("Top_Bar") == "exclusive" and r.keyboard("Dock") == "on_demand"


def test_a_reload_that_writes_another_surface_true_moves_the_mode_by_rule_1(rig: Make) -> None:
    r = rig()
    r.mode.enter()
    r.reload(text(bar="Shortcut_Mode: true,"))
    assert r.state == ("Top_Bar", "Top_Bar")
    r.settle()
    assert r.at_rest("Tab")  # the Frame's peeks went back


def test_a_reload_that_writes_the_surface_in_the_mode_false_turns_the_shell_off(
    rig: Make,
) -> None:
    r = rig(text(dock="Shortcut_Mode: true,"))
    r.reload(text(dock="Shortcut_Mode: false,"))
    assert r.state == (None, None)
    assert r.keyboard("Dock") == "on_demand"


def test_a_reload_that_changes_nothing_keeps_the_mode_and_its_keyboard(rig: Make) -> None:
    r = rig()
    r.mode.enter()
    r.mode.step(True)  # Dock
    r.reload(text())
    assert r.state == ("F", "Dock")
    assert r.keyboard("Dock") == "exclusive"  # the reload's own keyboard sync left it alone


def test_a_reload_that_changes_a_written_keyboard_applies_it_when_the_mode_ends(
    rig: Make,
) -> None:
    r = rig()
    r.mode.set_mode("Dock", True)
    r.reload(text().replace("Keyboard: ON_DEMAND, Tab_Index: 2,", "Keyboard: NONE, Tab_Index: 2,"))
    assert r.keyboard("Dock") == "exclusive"
    r.mode.exit()
    assert r.keyboard("Dock") == "none"


# -- the status ---------------------------------------------------------------------------------


def status_of(r: Rig, name: str) -> tuple[str, str]:
    window = r.frame.painter if name == "F" else r.surface(name).window
    node = r.mode._status[id(window)]
    return str(node.get("text")), str(node.get("live"))


def test_entering_and_leaving_the_mode_are_a_polite_status(rig: Make) -> None:
    r = rig()
    r.mode.enter()
    assert status_of(r, "F") == ("Shortcut mode on, F", "polite")
    r.mode.step(True)
    assert status_of(r, "Dock") == ("Dock", "polite")
    r.mode.exit()
    assert status_of(r, "Dock") == ("Shortcut mode off", "polite")


# -- the python contract: default and set_mode ----------------------------------------------------


def test_a_default_focus_starts_the_mode_with_the_focus_on_that_surface(rig: Make) -> None:
    r = rig()
    r.mode.set_default("Dock")
    r.mode.enter()
    assert r.state == ("F", "Dock")
    assert r.keyboard("Dock") == "exclusive"
    r.mode.exit()
    r.mode.set_default(None)
    r.mode.enter()
    assert r.state == ("F", "F")


def test_a_default_or_a_mode_for_a_name_that_is_no_surface_is_one_error_with_the_nearest(
    rig: Make,
) -> None:
    r = rig()
    r.mode.set_default("Dok")
    assert r.mode.get_default() is None
    assert r.mode.set_mode("Dok", True) is False
    errors = [x for x in r.lines if "| ERROR " in x]
    assert len(errors) == 2 and all("did you mean Dock?" in x for x in errors)
    assert r.state == (None, None)


# -- the compositor that does not hand the keyboard over (Failure Modes) --------------------------


def test_a_surface_that_is_not_given_the_keyboard_is_one_warning_after_the_wait(
    rig: Make,
) -> None:
    r = rig()
    r.mode.watch_focus = True  # the app sets it on a real compositor; headless there is none
    r.mode.enter()
    r.frame.painter.advance(1000)
    assert r.warnings() == []  # the wait is not over
    r.frame.painter.advance(1000)
    (warning,) = r.warnings()
    assert "the compositor did not give F the keyboard (exclusive) within 1500 ms" in warning
    r.mode.step(True)  # the Dock asks too, and is not given it either
    r.surface("Dock").window.advance(2000)
    assert len(r.warnings()) == 2 and "did not give Dock the keyboard" in r.warnings()[1]
    r.mode.step(False)  # F again: it was warned about already, once is enough
    r.frame.painter.advance(3000)
    assert len(r.warnings()) == 2


def test_a_surface_the_os_made_active_is_no_warning(rig: Make) -> None:
    r = rig()
    r.mode.watch_focus = True
    r.mode.enter()
    r.frame.painter.simulate("active", active=True)  # the compositor gave it the keyboard
    r.frame.painter.advance(3000)
    assert r.warnings() == []
    assert r.manager.focused == "F"
