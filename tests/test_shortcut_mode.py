"""The shortcut-mode state machine (Focus and Keyboard > Shortcut Mode), table-tested: the
maintainer's seven rules of 2026-11-10, with no tre and no D-Bus.
``tests/test_shortcut_mode_shell.py`` proves what the surface manager does with each change."""

from __future__ import annotations

import pytest

from tess_shell.surfaces.mode import OFF, ModeState, ShortcutMode

ORDER = ["Frame", "Dock", "Frame.top", "Top_Bar"]


def make(
    written: dict[str, bool] | None = None,
    lowest: str | None = "Frame",
    order: list[str] | None = None,
) -> tuple[ShortcutMode, list[tuple[ModeState, ModeState]]]:
    changes: list[tuple[ModeState, ModeState]] = []
    mode = ShortcutMode(lambda old, new: changes.append((old, new)))
    mode.configure(order or ORDER, lowest, written or {n: False for n in order or ORDER})
    return mode, changes


def at(mode: str | None, focus: str | None) -> ModeState:
    return ModeState(mode, focus)


# -- rule 3: Enter and Exit --------------------------------------------------------------------


def test_the_shell_starts_outside_the_mode() -> None:
    m, changes = make()
    assert m.state == OFF and not m.on and changes == []


def test_enter_puts_the_frame_in_the_mode_with_the_focus_on_it() -> None:
    m, changes = make()
    assert m.enter()
    assert m.state == at("Frame", "Frame")
    assert changes == [(OFF, at("Frame", "Frame"))]


def test_enter_without_a_frame_takes_the_first_surface_in_tab_order() -> None:
    m, _ = make(lowest="Dock")  # the manager says which one is the lowest level
    m.enter()
    assert m.state == at("Dock", "Dock")


def test_enter_with_nothing_to_enter_does_nothing() -> None:
    m, changes = make(lowest=None, order=[])
    assert m.enter() is False
    assert m.state == OFF and changes == []


def test_exit_clears_every_mode_and_the_focus() -> None:
    m, changes = make()
    m.enter()
    m.set_mode("Dock", True)
    changes.clear()
    assert m.exit()
    assert m.state == OFF
    assert changes == [(at("Dock", "Dock"), OFF)]


def test_exit_outside_the_mode_changes_nothing() -> None:
    m, changes = make()
    assert m.exit() is False
    assert changes == []


def test_enter_twice_changes_nothing_the_second_time() -> None:
    m, changes = make()
    m.enter()
    m.enter()
    assert len(changes) == 1


# -- rule 4: the focus starts on the Frame, or where a developer said ---------------------------


def test_a_default_focus_starts_the_mode_on_that_surface_with_the_frame_in_the_mode() -> None:
    m, _ = make()
    m.default = "Dock"
    m.enter()
    assert m.state == at("Frame", "Dock")


def test_a_default_that_is_no_surface_falls_back_to_the_frame() -> None:
    m, _ = make()
    m.default = "Nothing"
    m.enter()
    assert m.state == at("Frame", "Frame")


# -- rule 5: Next_Focus and Previous_Focus -------------------------------------------------------


@pytest.mark.parametrize(
    ("forward", "expected"),
    [
        (True, ["Dock", "Frame.top", "Top_Bar", "Frame", "Dock"]),
        (False, ["Top_Bar", "Frame.top", "Dock", "Frame", "Top_Bar"]),
    ],
)
def test_next_and_previous_visit_the_surfaces_in_tab_order_and_go_round(
    forward: bool, expected: list[str]
) -> None:
    m, _ = make()
    m.enter()
    seen = [m.step(forward) for _ in expected]
    assert seen == expected
    assert m.mode == "Frame"  # the Frame stays in the mode while the focus moves


def test_next_does_nothing_outside_the_mode() -> None:
    m, changes = make()
    assert m.step(True) is None and m.step(False) is None
    assert m.state == OFF and changes == []


def test_next_does_not_move_between_surfaces_in_a_surfaces_own_mode() -> None:
    m, _ = make()
    m.enter()
    m.set_mode("Dock", True)
    assert not m.navigating
    assert m.step(True) is None
    assert m.state == at("Dock", "Dock")


def test_next_starts_from_the_first_surface_when_the_focus_is_on_none() -> None:
    m, _ = make()
    m.enter()
    m.state = at("Frame", None)
    assert m.step(True) == "Frame"


# -- rule 1: at most one ---------------------------------------------------------------------


def test_setting_one_true_sets_every_other_false() -> None:
    m, _ = make()
    m.enter()
    assert m.set_mode("Dock", True)
    assert m.mode == "Dock"
    m.set_mode("Top_Bar", True)
    assert m.mode == "Top_Bar" and m.focus == "Top_Bar"


# -- rule 2: false with no other true is the whole shell off -----------------------------------


def test_setting_the_one_in_the_mode_false_turns_the_whole_mode_off() -> None:
    m, _ = make()
    m.set_mode("Dock", True)
    m.set_mode("Dock", False)
    assert m.state == OFF


def test_setting_a_surface_false_that_is_not_in_the_mode_changes_nothing() -> None:
    m, changes = make()
    m.set_mode("Dock", True)
    changes.clear()
    assert m.set_mode("Top_Bar", False)
    assert m.state == at("Dock", "Dock") and changes == []


def test_a_name_that_is_no_surface_is_refused() -> None:
    m, changes = make()
    assert m.set_mode("Nope", True) is False
    assert m.state == OFF and changes == []


# -- rule 6: Set_Shortcut_Mode on the focused surface ------------------------------------------


def test_set_on_a_focused_surface_moves_the_mode_to_it_and_the_frames_turns_off() -> None:
    m, _ = make()
    m.enter()
    m.step(True)  # the focus is on Dock; the Frame is still the one in the mode
    assert m.state == at("Frame", "Dock")
    assert m.toggle_focused()
    assert m.state == at("Dock", "Dock")  # rule 1: the Frame's mode is off now


def test_set_again_on_the_surface_in_the_mode_turns_the_whole_shell_off_not_back_to_the_frame() -> (
    None
):
    m, _ = make()
    m.enter()
    m.step(True)
    m.toggle_focused()
    assert m.toggle_focused()
    assert m.state == OFF  # the consequence of rules 1 and 2: Enter goes back to the Frame


def test_set_on_the_frame_itself_turns_the_whole_shell_off() -> None:
    m, _ = make()
    m.enter()
    m.toggle_focused()
    assert m.state == OFF


def test_set_with_no_focus_does_nothing() -> None:
    m, changes = make()
    assert m.toggle_focused() is False
    assert changes == []


def test_enter_inside_a_surfaces_own_mode_goes_back_to_the_frame() -> None:
    m, _ = make()
    m.set_mode("Dock", True)
    m.enter()
    assert m.state == at("Frame", "Frame")


# -- a surface that closes -------------------------------------------------------------------


def test_the_surface_with_the_focus_closing_passes_the_focus_to_the_next_in_order() -> None:
    m, _ = make()
    m.enter()
    m.step(True)  # Dock
    m.gone("Dock", ["Frame", "Frame.top", "Top_Bar"])
    assert m.state == at("Frame", "Frame.top")


def test_the_last_in_order_closing_passes_the_focus_to_the_first() -> None:
    m, _ = make()
    m.enter()
    m.step(False)  # Top_Bar
    m.gone("Top_Bar", ["Frame", "Dock", "Frame.top"])
    assert m.state == at("Frame", "Frame")


def test_the_surface_in_the_mode_closing_ends_the_mode() -> None:
    m, _ = make()
    m.set_mode("Dock", True)
    m.gone("Dock", ["Frame", "Frame.top", "Top_Bar"])
    assert m.state == OFF


def test_the_mode_ends_when_no_surface_is_left_for_the_focus() -> None:
    m, _ = make()
    m.enter()
    m.step(True)  # Dock
    m.gone("Dock", [])
    assert m.state == OFF


def test_another_surface_closing_changes_nothing() -> None:
    m, changes = make()
    m.enter()
    changes.clear()
    m.gone("Top_Bar", ["Frame", "Dock"])
    assert m.state == at("Frame", "Frame") and changes == []


# -- the files (configure) -------------------------------------------------------------------


def files(**flags: bool) -> dict[str, bool]:
    return {n: flags.get(n.replace(".", "_"), False) for n in ORDER}


def test_a_surface_written_true_starts_in_the_mode() -> None:
    m = ShortcutMode()
    m.configure(ORDER, "Frame", files(Dock=True))
    assert m.state == at("Dock", "Dock")


def test_two_written_true_the_first_in_document_order_keeps_it() -> None:
    m = ShortcutMode()
    m.configure(ORDER, "Frame", files(Dock=True, Top_Bar=True))
    assert m.mode == "Dock"


def test_the_frame_written_true_starts_in_the_frames_mode() -> None:
    m = ShortcutMode()
    m.configure(ORDER, "Frame", files(Frame=True))
    assert m.state == at("Frame", "Frame")


def test_a_reload_that_changes_nothing_keeps_what_the_run_made() -> None:
    m, _ = make()
    m.enter()
    m.step(True)
    m.configure(ORDER, "Frame", files())
    assert m.state == at("Frame", "Dock")


def test_a_reload_that_writes_a_surface_true_takes_the_mode_by_rule_1() -> None:
    m, _ = make()
    m.enter()
    m.configure(ORDER, "Frame", files(Top_Bar=True))
    assert m.state == at("Top_Bar", "Top_Bar")


def test_a_reload_that_writes_the_surface_in_the_mode_false_turns_the_whole_shell_off() -> None:
    m = ShortcutMode()
    m.configure(ORDER, "Frame", files(Dock=True))
    m.configure(ORDER, "Frame", files())
    assert m.state == OFF


def test_a_reload_that_writes_another_surface_false_keeps_the_mode() -> None:
    m = ShortcutMode()
    m.configure(ORDER, "Frame", files(Dock=True, Top_Bar=True))  # Top_Bar lost (a warning)
    m.configure(ORDER, "Frame", files(Dock=True))
    assert m.state == at("Dock", "Dock")


def test_a_reload_keeps_the_mode_when_its_surface_is_still_there() -> None:
    m, _ = make()
    m.enter()
    m.set_mode("Dock", True)
    m.configure(["Dock", "Top_Bar"], "Dock", {"Dock": False, "Top_Bar": False})
    assert m.state == at("Dock", "Dock")


def test_a_reload_ends_the_mode_when_its_surface_is_gone() -> None:
    m, _ = make()
    m.set_mode("Dock", True)
    m.configure(["Frame", "Top_Bar"], "Frame", {"Frame": False, "Top_Bar": False})
    assert m.state == OFF


def test_a_reload_moves_the_focus_on_when_its_surface_is_gone() -> None:
    m, _ = make()
    m.enter()
    m.step(True)  # Dock
    m.configure(["Frame", "Frame.top", "Top_Bar"], "Frame", {n: False for n in ORDER[:1]})
    assert m.state == at("Frame", "Frame.top")


def test_a_default_focus_that_left_the_files_is_forgotten() -> None:
    m, _ = make()
    m.default = "Dock"
    m.configure(["Frame"], "Frame", {"Frame": False})
    assert m.default is None


def test_two_newly_true_on_a_reload_the_first_in_document_order_wins() -> None:
    m, _ = make()
    m.configure(ORDER, "Frame", files(Top_Bar=True, Dock=True))
    assert m.mode == "Dock"
