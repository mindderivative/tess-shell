"""A Frame's ``Shortcut`` key (Global Shortcuts, D-053): the same as ``Toggle_<Name>``; a press
toggles the Frame through the shell's own commands. Headless, the real surface manager."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any, cast

import pytest

from tess_shell.commands import ShellCommands
from tess_shell.schema.keys import parse_chord
from tess_shell.shortcuts import build_plan
from tests.mode_rig import Make, Rig, rigs, shell_of, text
from tests.test_frame_strips import module


@pytest.fixture
def rig() -> Iterator[Make]:
    yield from rigs()


def shown(r: Rig) -> bool:
    return next(i for i in r.manager.surface_infos() if i.name == "F").shown


def test_the_frames_key_is_a_toggle_action_and_a_press_toggles_the_frame(rig: Make) -> None:
    body = text(frame='Shortcut: "Ctrl+Alt+F",')
    r = rig(body)
    actions, findings = build_plan((), shell_of(body), module())
    assert findings == []
    (action,) = [a for a in actions if a.target == "F"]
    assert action.id == "Toggle_F" and action.kind == "toggle"
    assert action.keys == (parse_chord("Ctrl+Alt+F"),)
    commands = ShellCommands(r.manager, cast(Any, None), cast(Any, None), lambda: None, lambda: [])
    assert shown(r)
    commands.press(action)
    assert not shown(r)
    commands.press(action)
    assert shown(r)
