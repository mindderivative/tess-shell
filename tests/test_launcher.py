"""The launcher, headless (M6d, Applications Module > Acceptance Criteria): the shipped ``Launcher``
Panel and ``Applications`` module in a real surface window with no compositor, driven by key events
and the toggle a shortcut runs, over TEMPORARY desktop entries and a recorded starter. Nothing here
starts a process or reads the user's applications (``tests/launcher_rig.py``).

What a start did is read from the recorder: the command line, the working folder and the
environment the application would get."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from loguru import logger

from tests.launcher_rig import ENV, FakeRunner, launcher_desk
from tests.test_popup import _SINKS

BROWSERS = {
    "Firefox": {"Exec": "fake-app --new-window %u", "GenericName": "Web Browser"},
    "Files": {"Exec": "fake-app --files %F", "Comment": "Browse folders"},
    "Fire Dragon": {"Exec": "fake-app --dragon"},
    "Terminal": {"Exec": "fake-app --tui", "Terminal": "true"},
}


@pytest.fixture(autouse=True)
def _drain_the_rig_sinks() -> Iterator[None]:
    """As in ``tests/test_keys.py``: the popup rig's log sinks are left for its own module."""
    yield
    while _SINKS:
        logger.remove(_SINKS.pop())


# -- opening ---------------------------------------------------------------------------------------


def test_the_panel_is_hidden_until_the_shortcut_toggles_it_and_the_field_has_the_focus(
    tmp_path: Path,
) -> None:
    with launcher_desk(tmp_path, BROWSERS) as d:
        assert d.w.warnings() == []
        assert d.hidden and d.panel.window.get("keyboard") == "none"  # a hidden Panel takes no key
        d.toggle()  # what a press of Toggle_Launcher runs
        assert not d.hidden
        assert d.panel.window.get("keyboard") == "exclusive"
        field = d.field()
        assert field.get("focused") and field.get("text") == ""
        assert field.get("placeholder") == "Search applications"
        # an empty query lists every application, by name (nothing was started yet)
        assert d.names() == ["Files", "Fire Dragon", "Firefox", "Terminal"]
        d.toggle()  # the same key again
        assert d.hidden and d.panel.window.get("keyboard") == "none"


def test_when_the_panel_shows_again_the_field_takes_the_focus_with_its_text_selected(
    tmp_path: Path,
) -> None:
    with launcher_desk(tmp_path, BROWSERS) as d:
        d.toggle()
        d.type("fire")
        field = d.field()
        assert field.get("text") == "fire" and field.get("selection") == (4, 4)
        d.toggle()  # hidden with text in the field
        assert d.hidden
        d.toggle()
        field = d.field()
        assert field.get("focused") and field.get("text") == "fire"
        assert field.get("selection") == (0, 4)  # all of it: typing starts a new search
        d.type("fil")
        assert field.get("text") == "fil" and d.names() == ["Files"]


# -- typing, the selection, the keys ---------------------------------------------------------------


def test_typing_narrows_the_list_within_one_frame_and_selects_the_first_result(
    tmp_path: Path,
) -> None:
    with launcher_desk(tmp_path, BROWSERS) as d:
        d.toggle()
        assert d.selected() == ["Files"]
        d.press("arrow_down")
        d.press("arrow_down")
        assert d.selected() == ["Firefox"]
        d.type("f")  # ``type`` is one key and one frame: the list is already the new one
        assert d.names() == ["Files", "Fire Dragon", "Firefox"] and d.selected() == ["Files"]
        d.type("ir")
        assert d.names() == ["Fire Dragon", "Firefox"] and d.selected() == ["Fire Dragon"]
        d.type("ef")
        assert d.names() == ["Firefox"]
        d.type("x")
        assert d.names() == [] and d.message() == "No results"
        assert not d.rows()  # no list at all: nothing to select


def test_down_and_up_move_the_selection_and_wrap_and_the_field_keeps_the_keyboard(
    tmp_path: Path,
) -> None:
    with launcher_desk(tmp_path, BROWSERS) as d:
        d.toggle()
        d.type("fi")
        field = d.field()
        assert d.names() == ["Files", "Fire Dragon", "Firefox"]
        for expected in ("Fire Dragon", "Firefox", "Files", "Fire Dragon"):  # Down wraps
            d.press("arrow_down")
            assert d.selected() == [expected]
        d.press("arrow_up")
        assert d.selected() == ["Files"]
        d.press("arrow_up")  # Up wraps too: from the first row to the last
        assert d.selected() == ["Firefox"]
        assert field.get("focused") and field.get("text") == "fi"  # the keys did not touch it
        assert field.get("selection") == (2, 2)


def test_page_down_and_page_up_move_by_the_rows_shown_and_stop_at_the_ends(
    tmp_path: Path,
) -> None:
    many = {f"App {n:02d}": {"Exec": "fake-app"} for n in range(20)}
    with launcher_desk(tmp_path, many) as d:
        d.toggle()
        assert len(d.names()) == 8  # max_results rows
        d.press("page_down")
        assert d.selected() == ["App 07"]  # a page of 8 from the first row: the last shown
        d.press("page_down")
        assert d.selected() == ["App 07"]  # a page stops at the end
        d.press("arrow_down")
        assert d.selected() == ["App 00"]  # a single step wraps
        d.press("page_up")
        assert d.selected() == ["App 00"]
        d.press("arrow_up")
        d.press("page_up")
        assert d.selected() == ["App 00"]


def test_other_keys_belong_to_the_field_and_a_key_with_ctrl_or_alt_moves_nothing(
    tmp_path: Path,
) -> None:
    with launcher_desk(tmp_path, BROWSERS) as d:
        d.toggle()
        d.type("fi")
        field = d.field()
        d.press("home")
        assert field.get("selection") == (0, 0) and d.selected() == ["Files"]
        d.press("end")
        assert field.get("selection") == (2, 2)
        d.press("arrow_down", ctrl=True)  # a shortcut of the user's, not the list's
        d.press("arrow_down", alt=True)
        assert d.selected() == ["Files"]
        d.press("backspace")
        assert field.get("text") == "f" and d.names() == ["Files", "Fire Dragon", "Firefox"]


def test_hover_does_not_change_the_selection(tmp_path: Path) -> None:
    with launcher_desk(tmp_path, BROWSERS) as d:
        d.toggle()
        d.press("arrow_down")
        assert d.selected() == ["Fire Dragon"]
        last = d.rows()[-1]
        d.window.simulate("pointer_enter", node=last)
        d.window.simulate("pointer_move", node=last, x=5.0, y=5.0)
        d.window.advance(16)
        d.settle(lambda: True)
        assert d.selected() == ["Fire Dragon"]  # the pointer resting over the list
        d.press("arrow_down")
        assert d.selected() == ["Firefox"]  # and the keys go on from where they were


# -- starting ------------------------------------------------------------------------------------


def test_enter_starts_the_selected_entry_with_its_command_and_environment_then_hides(
    tmp_path: Path,
) -> None:
    with launcher_desk(tmp_path, BROWSERS) as d:
        d.toggle()
        d.type("fire")
        d.press("arrow_down")
        assert d.selected() == ["Firefox"]
        d.press("enter")
        assert d.settle(lambda: d.runner.started)
        (spec,) = d.runner.started
        # %u removed, the program found on the path, in a scope because systemd-run is there
        assert spec.argv[0] == "systemd-run"
        assert spec.argv[-3:] == ("--", "fake-app", "--new-window")
        assert spec.scope is not None and spec.scope.startswith("app-firefox-")
        assert spec.cwd == str(d.home)  # no Path: the user's home
        # the shell's own variables stay out; the token is absent: the window gave none (headless)
        assert "NOTIFY_SOCKET" not in spec.env and "INVOCATION_ID" not in spec.env
        assert "TESS_SHELL_LAUNCH_RECORD" not in spec.env
        assert "XDG_ACTIVATION_TOKEN" not in spec.env  # also not the stale one of the environment
        assert spec.env["HOME"] == ENV["HOME"] and spec.env["PATH"] == ENV["PATH"]
        # after the start: the field is empty and the Panel hidden
        assert d.settle(lambda: d.hidden)
        d.toggle()
        field = d.field()
        assert field.get("text") == "" and field.get("focused")
        assert d.names()[0] == "Firefox"  # the most started is first in an empty query
        assert d.apps.count("firefox.desktop") == 1


def test_enter_with_no_results_starts_nothing_and_a_plain_start_runs_without_systemd_run(
    tmp_path: Path,
) -> None:
    with launcher_desk(tmp_path, BROWSERS, runner=FakeRunner(scope=False)) as d:
        d.toggle()
        d.type("zzz")
        d.press("enter")
        d.settle(lambda: False, 0.2)
        assert d.runner.started == [] and not d.hidden
        d.type("")  # (an empty commit changes nothing)
        d.press("backspace")
        d.press("backspace")
        d.press("backspace")
        d.press("end")
        for _ in range(3):
            d.press("backspace")
        assert d.field().get("text") == "" and d.selected() == ["Files"]
        d.press("enter")
        assert d.settle(lambda: d.runner.started)
        assert d.runner.started[0].argv == ("fake-app", "--files")
        assert d.runner.started[0].scope is None


def test_a_click_on_a_row_starts_that_application(tmp_path: Path) -> None:
    with launcher_desk(tmp_path, BROWSERS) as d:
        d.toggle()
        d.type("fi")
        d.window.simulate("click", node=d.rows()[2])  # Firefox
        assert d.settle(lambda: d.runner.started)
        assert d.runner.started[0].argv[-2:] == ("fake-app", "--new-window")
        assert d.settle(lambda: d.hidden)


def test_the_field_codes_the_path_the_terminal_and_the_icon_come_from_the_entry(
    tmp_path: Path,
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    entries = {
        "Coded": {
            "Exec": 'fake-app %i --title "%c" --file %k %U 100%%',
            "Icon": "fake-icon",
            "Path": str(work),
        },
        "Shell Tool": {"Exec": "fake-app --tui", "Terminal": "true"},
    }
    with launcher_desk(tmp_path, entries, runner=FakeRunner(scope=False)) as d:
        d.toggle()
        d.type("coded")
        d.press("enter")
        assert d.settle(lambda: d.runner.started)
        spec = d.runner.started[0]
        assert spec.argv == (
            "fake-app",
            "--icon",
            "fake-icon",
            "--title",
            "Coded",
            "--file",
            str(d.folder / "coded.desktop"),
            "100%",
        )
        assert spec.cwd == str(work)
        assert d.settle(lambda: d.hidden)
        d.toggle()
        d.type("shell")
        d.press("enter")
        assert d.settle(lambda: len(d.runner.started) == 2)
        assert d.runner.started[1].argv == ("xdg-terminal-exec", "fake-app", "--tui")


def test_a_token_from_the_window_is_in_the_environment_and_none_is_logged_at_debug(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []
    sink = logger.add(lambda m: seen.append(str(m)), level="DEBUG")
    try:
        with launcher_desk(tmp_path, BROWSERS) as d:
            asked: list[str] = []
            manager = d.w.manager
            real = manager.request_token

            def with_token(use: str, callback: Callable[[str | None], None]) -> None:
                asked.append(use)
                callback("token-from-the-window")

            monkeypatch.setattr(manager, "request_token", with_token)
            d.toggle()
            d.press("enter")
            assert d.settle(lambda: d.runner.started)
            assert d.runner.started[0].env["XDG_ACTIVATION_TOKEN"] == "token-from-the-window"
            assert len(asked) == 1 and asked[0].startswith("Applications@")
            assert any("activation token: received" in line for line in seen)
            seen.clear()
            monkeypatch.setattr(manager, "request_token", real)  # the headless window: None
            assert d.settle(lambda: d.hidden)
            d.toggle()
            d.press("enter")
            assert d.settle(lambda: len(d.runner.started) == 2)
            assert "XDG_ACTIVATION_TOKEN" not in d.runner.started[1].env
            assert any("activation token: none" in line for line in seen)
    finally:
        logger.remove(sink)


def test_a_start_that_fails_keeps_the_panel_open_and_says_so_until_the_next_search(
    tmp_path: Path,
) -> None:
    entries = {"Broken": {"Exec": "no-such-program"}, "Fine": {"Exec": "fake-app"}}
    with launcher_desk(tmp_path, entries) as d:
        d.toggle()
        assert d.selected() == ["Broken"]
        d.press("enter")
        assert d.settle(lambda: d.message() == "Could not start Broken")
        assert not d.hidden and d.runner.started == []
        assert d.names() == ["Broken", "Fine"]  # the list stays
        d.type("f")
        assert d.message() == ""
        assert d.names() == ["Fine"]
        d.press("enter")
        assert d.settle(lambda: d.runner.started)
        assert d.settle(lambda: d.hidden)


# -- Escape ----------------------------------------------------------------------------------------


def test_escape_clears_the_field_and_the_next_escape_hides_the_panel(tmp_path: Path) -> None:
    with launcher_desk(tmp_path, BROWSERS) as d:
        d.toggle()
        d.type("fi")
        field = d.field()
        d.press("escape")
        # with text: the field is cleared and the Panel stays (its own Escape did not also fire)
        assert field.get("text") == "" and not d.hidden
        assert d.names() == ["Files", "Fire Dragon", "Firefox", "Terminal"]
        assert d.selected() == ["Files"]
        d.press("escape")  # without text: it hides
        assert d.hidden and d.panel.window.get("keyboard") == "none"
        d.toggle()
        assert d.field().get("focused") and not d.hidden


# -- what the list says when it is empty ---------------------------------------------------------


def test_no_applications_found_is_said_when_there_are_none_and_before_the_list_is_built_nothing(
    tmp_path: Path,
) -> None:
    with launcher_desk(tmp_path, [], ready=False) as d:
        # the Panel is usable before the list is built: no rows, and no message yet
        assert d.settle(lambda: d.apps.ready)
        d.toggle()
        assert d.message() == "No applications found" and not d.rows()
        d.press("arrow_down")  # nothing to move
        d.press("enter")  # nothing to start
        d.settle(lambda: False, 0.1)
        assert d.runner.started == [] and not d.hidden


def test_an_entry_file_that_comes_while_the_panel_is_open_is_in_the_list(tmp_path: Path) -> None:
    from tests.launcher_rig import write_entry

    with launcher_desk(tmp_path, {"Alpha": {"Exec": "fake-app"}}) as d:
        d.toggle()
        d.type("a")
        assert d.names() == ["Alpha"]
        write_entry(d.folder, "Beta Alpha", Exec="fake-app")
        d.apps.index.invalidate()
        d.apps.refresh()
        assert d.settle(lambda: d.names() == ["Alpha", "Beta Alpha"])
        assert d.selected() == ["Alpha"]
        d.type("lpha")  # the field kept what the user typed
        assert d.field().get("text") == "alpha" and d.names() == ["Alpha", "Beta Alpha"]


def test_the_icon_of_each_row_is_the_applications_and_the_fallback_until_it_is_read(
    tmp_path: Path,
) -> None:
    entries = {"Painter": {"Exec": "fake-app", "Icon": "fake-icon"}, "Plain": {"Exec": "fake-app"}}
    with launcher_desk(tmp_path, entries) as d:
        module: Any = d.w.host.loaded["Applications"].instance
        d.toggle()
        assert d.names() == ["Painter", "Plain"]
        # the worker reads the theme's SVG for the entry with an icon (a red square); the entry with
        # none keeps the shipped fallback; the row shows what the module has made
        assert d.settle(lambda: "#ff0000" in module.icons.get(("painter.desktop", 24), ""))
        assert module.icons[("plain.desktop", 24)] == "mdi:application-outline"


def test_each_use_keeps_its_own_query(tmp_path: Path) -> None:
    """Two Panels on two outputs do not share a query: the module's state is per use."""
    with launcher_desk(tmp_path, BROWSERS) as d:
        module: Any = d.w.host.loaded["Applications"].instance
        (use,) = d.w.host.loaded["Applications"].ctx.uses.values()
        assert set(module.states) == {use.key}
        d.toggle()
        d.type("fire")
        assert module.states[use.key].query == "fire"


def test_a_launcher_that_had_the_keyboard_closes_when_another_surface_of_the_shell_takes_it() -> (
    None
):
    """M7k: the keyboard going to another of the shell's own surfaces (``active``) closes a
    Launcher that had it; a Launcher that never had it, one already hidden, the surface that
    gained it and a Panel without the Applications module are left alone. (Sway keeps an
    exclusive keyboard on the earlier surface, so the compositor cannot show this live.)"""
    from types import SimpleNamespace

    from tess_shell.surfaces.manager import SurfaceManager

    def surface(name: str, *, had: bool, hidden: bool = False, launcher: bool = True) -> Any:
        return SimpleNamespace(name=name, had_keys=had, hidden=hidden, launcher=launcher)

    closed: list[str] = []
    manager = SimpleNamespace(
        surfaces=[
            surface("Launcher", had=True),
            surface("Never", had=False),
            surface("Hidden", had=True, hidden=True),
            surface("Other", had=True),
            surface("Plain", had=True, launcher=False),
        ],
        _click_away_panel=lambda s: s.launcher,
        hide=lambda s: closed.append(s.name),
    )
    SurfaceManager._keyboard_taken(manager, "Other")  # type: ignore[arg-type]
    assert closed == ["Launcher"]
