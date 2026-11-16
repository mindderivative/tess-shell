"""Hiding the shell's surfaces on an output with an active fullscreen window (KWin Integration >
The KWin script, Surface Types > Fullscreen and Maximised Windows). Headless: the surface manager
over a stub ``App`` with two outputs; the windows are real tre windows, so their properties are read
back. The compositor side (what KWin does with them) is the hand check of
``tests/kwin/prepare_m5g_kwin.py``."""

from __future__ import annotations

from typing import Any

import pytest
import tess_dl

from tess_shell.appearance import Appearance
from tess_shell.model.look import make_look
from tess_shell.model.store import ValueStore
from tess_shell.schema.look import read_theme
from tess_shell.schema.model import ShellDef
from tess_shell.surfaces.manager import SurfaceManager
from tests.test_look import THEME
from tests.test_schema_shell import read


class Out(str):
    width = 800
    height = 600

    @property
    def name(self) -> str:
        return str(self)


class App:
    def __init__(self) -> None:
        self.windows: list[Any] = []

    def outputs(self) -> list[Any]:
        return [Out("HDMI-A-1"), Out("DP-1")]

    def add_window(self, window: object) -> None:
        self.windows.append(window)


ONE = (
    "Monitor { Name: One, Index: 0, Children { "
    "Bar { Name: Bar_One, Edge: TOP, Width: EXPAND, Height: 30, Children { FlexBox { Name: A } } } "
    "Panel { Name: Panel_One, Layer: OVERLAY, Width: 100, Height: 50, Anchor: [BOTTOM], "
    "Children { FlexBox { Name: B } } } "
    "Panel { Name: Hidden_One, Layer: OVERLAY, Width: 100, Height: 50, Visible: false, "
    "Children { FlexBox { Name: C } } } } }"
)
TWO = (
    "Monitor { Name: Two, Index: 1, Children { "
    "Bar { Name: Bar_Two, Edge: TOP, Width: EXPAND, Height: 30, Children { FlexBox { Name: D } } } "
    'Frame { Name: F, Thickness: [10, 20, 30, 40], Style { Background: "#0000ff" } } } }'
)


def shell_of(*monitors: str) -> ShellDef:
    shell, findings = read("Shell { " + " ".join(monitors) + " }")
    assert shell is not None, findings
    return shell


def started(*monitors: str) -> SurfaceManager:
    doc = tess_dl.parse(THEME, path="T_Theme.tdl").document
    assert doc is not None
    theme, _ = read_theme(doc, "T_Theme.tdl")
    assert theme is not None
    look = make_look(theme, [], Appearance(scheme="dark"))
    manager = SurfaceManager(App(), {}, lambda key: key, ValueStore(), look, blend_mode="SRGB")  # type: ignore[arg-type]
    manager.plan(shell_of(*(monitors or (ONE, TWO))))
    manager.build()
    return manager


def surface(manager: SurfaceManager, name: str) -> Any:
    return next(s for s in manager.surfaces if s.name == name)


def look_of(s: Any) -> dict[str, Any]:
    """What a surface's window shows and takes now."""
    return {
        "visible": s.window.root.get("visible"),
        "input": s.window.get("input_region"),
        "keyboard": s.window.get("keyboard"),
        "zone": s.window.get("exclusive_zone"),
    }


def frame_state(manager: SurfaceManager) -> Any:
    (state,) = manager.frames.states.values()
    return state


def test_a_fullscreen_window_hides_the_bar_and_the_panels_of_its_output_only() -> None:
    manager = started()
    before = {n: look_of(surface(manager, n)) for n in ("Bar_One", "Panel_One", "Bar_Two")}
    assert before["Bar_One"]["zone"] == 30 and before["Bar_One"]["visible"] is True
    manager.set_fullscreen({"HDMI-A-1"})
    for name in ("Bar_One", "Panel_One"):
        assert look_of(surface(manager, name)) == {
            "visible": False,
            "input": [],
            "keyboard": "none",
            "zone": 0,
        }, name
        assert surface(manager, name).covered
    assert look_of(surface(manager, "Bar_Two")) == before["Bar_Two"]  # the other output: untouched
    assert not surface(manager, "Bar_Two").covered
    assert len(frame_state(manager).reservers) == 4  # the Frame is on DP-1: still there


def test_the_surfaces_come_back_exactly_as_they_were_when_the_output_is_no_longer_named() -> None:
    manager = started()
    before = {s.name: look_of(s) for s in manager.surfaces if s.name != "Hidden_One"}
    manager.set_fullscreen({"HDMI-A-1", "DP-1"})
    manager.set_fullscreen(set())
    assert {s.name: look_of(s) for s in manager.surfaces if s.name != "Hidden_One"} == before
    assert not any(s.covered for s in manager.surfaces)
    assert manager.covered_outputs == frozenset()


def test_the_state_is_the_full_list_so_a_repeat_does_nothing_and_a_move_changes_both() -> None:
    manager = started()
    calls: list[str] = []
    real = manager._cover_state
    manager._cover_state = lambda s: (calls.append(s.name), real(s))[1]  # type: ignore[method-assign]
    manager.set_fullscreen({"HDMI-A-1"})
    assert sorted(calls) == ["Bar_One", "Hidden_One", "Panel_One"]
    calls.clear()
    manager.set_fullscreen({"HDMI-A-1"})  # the same state again: not one window is touched
    assert calls == []
    manager.set_fullscreen({"DP-1"})  # the fullscreen window moved to the other output
    assert sorted(calls) == ["Bar_One", "Bar_Two", "Hidden_One", "Panel_One"]
    assert not surface(manager, "Bar_One").covered and surface(manager, "Bar_Two").covered


def test_a_panel_the_user_hid_stays_hidden_through_a_fullscreen_window() -> None:
    manager = started()
    hidden = surface(manager, "Hidden_One")
    assert hidden.hidden and look_of(hidden)["visible"] is False
    manager.set_fullscreen({"HDMI-A-1"})
    manager.set_fullscreen(set())
    assert hidden.hidden and look_of(hidden)["visible"] is False and look_of(hidden)["input"] == []
    # a Panel shown during the fullscreen window stays invisible until it ends
    manager.set_fullscreen({"HDMI-A-1"})
    manager.show(hidden)
    assert not hidden.hidden and look_of(hidden)["visible"] is False
    assert look_of(hidden)["input"] == [] and look_of(hidden)["keyboard"] == "none"
    manager.set_fullscreen(set())
    assert look_of(hidden)["visible"] is True and look_of(hidden)["input"] != []


def test_a_panel_hidden_by_the_user_while_covered_stays_hidden_afterwards() -> None:
    manager = started()
    panel = surface(manager, "Panel_One")
    manager.set_fullscreen({"HDMI-A-1"})
    manager.hide(panel)
    manager.set_fullscreen(set())
    assert panel.hidden and look_of(panel)["visible"] is False and look_of(panel)["input"] == []
    assert look_of(panel)["zone"] == panel.geometry.exclusive_zone  # no space is kept back


def test_the_frame_releases_its_zones_and_comes_back_with_them() -> None:
    manager = started()
    state = frame_state(manager)
    zones = {side: w.get("exclusive_zone") for side, w in state.reservers.items()}
    assert set(zones) == {"left", "top", "right", "bottom"} and all(zones.values())
    painter = state.painter
    manager.set_fullscreen({"DP-1"})
    assert state.painter is None and state.reservers == {} and state.covered
    assert state.hidden is False  # the user's own state is not changed
    manager.set_fullscreen(set())
    assert state.painter is not None and state.painter is not painter and not state.covered
    assert {side: w.get("exclusive_zone") for side, w in state.reservers.items()} == zones


def test_a_frame_the_user_hid_does_not_come_back_with_the_fullscreen_window_gone() -> None:
    manager = started()
    state = frame_state(manager)
    manager.set_fullscreen({"DP-1"})
    manager.frames.run("Hide", "F")
    manager.set_fullscreen(set())
    assert state.hidden and state.painter is None and state.reservers == {}
    manager.frames.run("Show", "F")
    assert state.painter is not None


def test_a_frame_that_opens_while_its_output_is_covered_opens_closed() -> None:
    manager = started(ONE)
    manager.set_fullscreen({"DP-1"})
    manager.frames.sync([], manager._look)  # nothing yet
    checked = manager.check(shell_of(ONE, TWO), {})
    assert checked is not None
    manager.apply(checked[0], {}, checked[1])
    state = frame_state(manager)
    assert state.covered and state.painter is None and state.reservers == {}
    assert look_of(surface(manager, "Bar_Two"))["visible"] is False  # the new Bar too
    manager.set_fullscreen(set())
    assert state.painter is not None and look_of(surface(manager, "Bar_Two"))["visible"] is True


def test_a_reload_that_changes_a_covered_bar_keeps_it_covered() -> None:
    manager = started()
    manager.set_fullscreen({"HDMI-A-1"})
    taller = ONE.replace("Height: 30", "Height: 40")
    checked = manager.check(shell_of(taller, TWO), {})
    assert checked is not None
    manager.apply(checked[0], {}, checked[1])
    bar = surface(manager, "Bar_One")
    assert look_of(bar) == {"visible": False, "input": [], "keyboard": "none", "zone": 0}
    manager.set_fullscreen(set())
    assert look_of(bar)["zone"] == 40 and look_of(bar)["visible"] is True  # the new height


def test_a_popup_does_not_stay_open_without_its_parent() -> None:
    manager = started()
    closed: list[str] = []
    manager.popups.parent_closed = lambda s: closed.append(s.name)  # type: ignore[method-assign]
    manager.set_fullscreen({"HDMI-A-1"})
    assert sorted(closed) == ["Bar_One", "Hidden_One", "Panel_One"]


@pytest.mark.parametrize("outputs", [[], ["DP-9"], ["HDMI-A-1", "HDMI-A-1"]])
def test_an_output_that_does_not_exist_or_is_named_twice_does_no_harm(outputs: list[str]) -> None:
    manager = started()
    manager.set_fullscreen(outputs)
    assert manager.covered_outputs == frozenset(outputs) and len(manager.surfaces) == 4
    manager.set_fullscreen([])
    assert not any(s.covered for s in manager.surfaces)
