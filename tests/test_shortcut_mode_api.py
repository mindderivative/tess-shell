"""The five shortcut actions through the shell's own commands, and ``ctx.focus`` for modules (T-050,
Focus and Keyboard > Python Contract). Headless, the real surface manager, no desktop."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

import pytest

from tess_shell.commands import ShellCommands
from tess_shell.config.settings import FIXED_SHORTCUTS
from tess_shell.modules.context import ModuleContext
from tess_shell.modules.ticks import TimeSource
from tess_shell.services.shortcuts import Action
from tests.mode_rig import Make, Rig, rigs
from tests.widgets_live import running


@pytest.fixture
def rig() -> Iterator[Make]:
    yield from rigs()


# -- the five actions through ``ShellCommands.press`` -----------------------------------------


def commands_of(r: Rig) -> ShellCommands:
    """The commands over the manager (a fixed action needs no module host and no reloader)."""
    return ShellCommands(r.manager, cast(Any, None), cast(Any, None), lambda: None, lambda: [])


def press(commands: ShellCommands, name: str) -> None:
    commands.press(Action(name, name.replace("_", " "), "fixed", name, ()))


def test_the_five_hooks_are_all_filled(rig: Make) -> None:
    commands = commands_of(rig())
    assert sorted(commands.fixed_actions) == sorted(FIXED_SHORTCUTS)


def test_each_action_runs_when_its_key_is_pressed(rig: Make) -> None:
    r = rig()
    commands = commands_of(r)
    press(commands, "Enter_Shortcut_Mode")
    assert r.state == ("F", "F")
    press(commands, "Next_Focus")
    assert r.state == ("F", "Dock")
    press(commands, "Next_Focus")
    press(commands, "Previous_Focus")
    assert r.state == ("F", "Dock")
    press(commands, "Set_Shortcut_Mode")
    assert r.state == ("Dock", "Dock")
    press(commands, "Enter_Shortcut_Mode")
    assert r.state == ("F", "F")
    press(commands, "Exit_Shortcut_Mode")
    assert r.state == (None, None)
    assert r.warnings() == []


def test_outside_the_mode_only_enter_does_anything_and_the_rest_say_so_at_debug(
    rig: Make,
) -> None:
    r = rig()
    commands = commands_of(r)
    for name in ("Next_Focus", "Previous_Focus", "Set_Shortcut_Mode", "Exit_Shortcut_Mode"):
        press(commands, name)
    assert r.state == (None, None)
    log = r.log()
    assert "Next_Focus: the shell is not in shortcut mode; nothing done" in log
    assert "Previous_Focus: the shell is not in shortcut mode; nothing done" in log
    assert "Set_Shortcut_Mode: no surface has the focus; nothing done" in log
    assert "Exit_Shortcut_Mode: the shell is not in shortcut mode; nothing done" in log
    assert r.warnings() == []


def test_the_key_a_user_bound_through_the_service_and_the_key_event_do_the_same_thing(
    rig: Make,
) -> None:
    from tess_shell.schema.keys import parse_chord
    from tess_shell.shortcuts import mode_keys

    r = rig()
    actions = (
        Action("Next_Focus", "Next Focus", "fixed", "Next_Focus", (parse_chord("Alt+J"),)),
        Action("Toggle_X", "Toggle X", "toggle", "Dock", (parse_chord("Alt+X"),)),
        Action("Exit_Shortcut_Mode", "Exit", "fixed", "Exit_Shortcut_Mode", ()),
    )
    r.mode.set_keys(mode_keys(actions))
    assert r.mode.keys == {parse_chord("Alt+J"): "Next_Focus"}  # fixed actions with a key only
    r.mode.enter()
    r.key("F", "j", alt=True)
    assert r.state == ("F", "Dock")


def test_only_enter_is_registered_with_a_key_the_other_four_are_declared_bare() -> None:
    from tess_shell.schema.keys import parse_chord
    from tess_shell.shortcuts import MODE_ONLY, registered

    key = (parse_chord("Alt+J"),)
    declared = tuple(
        Action(name, name, "fixed", name, key) for name in ("Enter_Shortcut_Mode", *MODE_ONLY)
    ) + (Action("Toggle_Dock", "Toggle Dock", "toggle", "Dock", key),)
    got = {a.id: a for a in registered(declared)}
    assert got["Enter_Shortcut_Mode"].keys == key and got["Toggle_Dock"].keys == key
    assert all(got[name].keys == () for name in MODE_ONLY)
    assert sorted(MODE_ONLY + ("Enter_Shortcut_Mode",)) == sorted(FIXED_SHORTCUTS)  # the five
    assert [a.id for a in registered(declared)] == [a.id for a in declared]  # same actions, order


# -- ctx.focus ---------------------------------------------------------------------------------


def context(r: Rig) -> ModuleContext:
    return ModuleContext(
        "Mod", "uid", {}, {}, lambda use, key, value: None, TimeSource(), focus=lambda: r.mode
    )


def test_ctx_focus_default_names_the_surface_that_starts_with_focus(rig: Make) -> None:
    r = rig()
    ctx = context(r)
    assert ctx.focus.default is None
    ctx.focus.default = "Dock"
    assert ctx.focus.default == "Dock"
    r.mode.enter()
    assert r.state == ("F", "Dock")
    ctx.focus.default = None
    assert ctx.focus.default is None


def test_ctx_focus_set_mode_puts_a_surface_in_the_mode_and_false_ends_it(rig: Make) -> None:
    r = rig()
    ctx = context(r)
    assert ctx.focus.set_mode("Dock", True) is True
    assert r.state == ("Dock", "Dock") and r.keyboard("Dock") == "exclusive"
    assert ctx.focus.set_mode("Top_Bar", False) is True  # not the one in the mode: nothing
    assert r.state == ("Dock", "Dock")
    assert ctx.focus.set_mode("Dock", False) is True  # the one in the mode: the shell leaves it
    assert r.state == (None, None) and r.keyboard("Dock") == "on_demand"


def test_ctx_focus_logs_a_name_that_is_no_surface_with_the_module_and_the_nearest(
    rig: Make,
) -> None:
    r = rig()
    ctx = context(r)
    ctx.focus.default = "Dok"
    assert ctx.focus.set_mode("Dok", True) is False
    errors = [x for x in r.lines if "| ERROR " in x]
    assert "ctx.focus.default (Mod): no surface named Dok (did you mean Dock?)" in errors[0]
    assert "ctx.focus.set_mode (Mod): no surface named Dok (did you mean Dock?)" in errors[1]
    assert ctx.focus.default is None and r.state == (None, None)


def test_ctx_focus_without_surfaces_raises_like_the_other_ports() -> None:
    ctx = ModuleContext("Mod", "uid", {}, {}, lambda use, key, value: None, TimeSource())
    with pytest.raises(RuntimeError, match="no surfaces"):
        _ = ctx.focus


DRIVER_PY = """
from tess_shell import Module, action

class Driver(Module):
    @action
    def go(self, event, name):
        self.ctx.focus.set_mode(name, True)

    @action
    def start_on(self, event, name):
        self.ctx.focus.default = name
"""


def test_a_module_loaded_by_the_host_reaches_the_mode_through_ctx_focus() -> None:
    with running("Label { Name: L, Text: x }", driver_py=DRIVER_PY) as w:
        w.host.focus = w.manager.mode  # the app does this (``host.focus = manager.mode``)
        assert w.manager.mode.machine.order == ["Top_Bar"]
        w.host.call_action("Driver", "start_on", ["Top_Bar"])
        assert w.manager.mode.get_default() == "Top_Bar"
        w.host.call_action("Driver", "go", ["Top_Bar"])
        assert w.manager.mode.machine.state.mode == "Top_Bar"
        assert w.bar.window.get("keyboard") == "exclusive"
