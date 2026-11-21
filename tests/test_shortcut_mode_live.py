"""Shortcut mode on the private headless sway, and through the FAKE ``org.kde.kglobalaccel`` on a
private session bus (T-050, Focus and Keyboard > How mode keys are delivered). Nothing here reaches
the real session: the shell's environment is ``PrivateSway.env`` (no real display, no real bus,
private runtime) and the virtual keys are ``wtype`` aimed at the private compositor, exactly as
``tests/test_focus_live.py`` does it; no ``/dev/uinput``, no real kglobalaccel, no real shortcut
settings.

* The mode is entered by a module (``ctx.focus.set_mode``), not by a key, so the key delivery is
  tested alone: the surface that has the focus asks for the keyboard (``EXCLUSIVE``), the keys the
  user bound (``Shortcuts { Next_Focus: "Tab" }``) and Escape arrive on it as ordinary key events,
  and the written keyboard word comes back when the mode ends.
* The five actions through the fake kglobalaccel: a key press the fake delivers runs each."""

from __future__ import annotations

import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

from tess_shell.schema.keys import parse_chord
from tests import live_pointer
from tests.shell_samples import HEADER, write_example
from tests.sway import PrivateSway
from tests.test_run import Shell
from tests.test_shortcuts_live import Desk, Make, desk  # noqa: F401  (the fixture)

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not live_pointer.available(), reason="no pywayland (tre's virtual env)"),
    pytest.mark.skipif(shutil.which("wtype") is None, reason="no wtype (a virtual keyboard)"),
]

STARTER_TDL = "Module {\n    Rectangle { Width: 4, Height: 4 }\n}\n"
STARTER_PY = """
from tess_shell import Module


class Starter(Module):
    def start(self):
        self.ticks = 0
        self.ctx.on_tick("second", self.tick)

    def tick(self):
        self.ticks += 1
        if self.ticks == 2:
            self.ctx.log.info("starter: entering the mode on F")
            self.ctx.focus.set_mode("F", True)
"""
BODY = (
    "Shell { Focus_Order: [F, Dock, Top_Bar]\n  Monitor { Name: Main, Index: 0, Children {\n"
    '  Frame { Name: F, Thickness: 6, Style { Background: "#202020" } }\n'
    "  Panel { Name: Dock, Anchor: [BOTTOM, LEFT], Width: 120, Height: 60,\n"
    "    Children { Rectangle { Name: One, Width: 20, Height: 20, Focusable: true } } }\n"
    "  Bar { Name: Top_Bar, Edge: TOP, Width: EXPAND, Height: 24,\n"
    "    Children { Starter { } } }\n"
    "} } }\n"
)
SETTINGS = (
    "---\nTDL: 0.2\nName: S\n---\n"
    "Settings { Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default], Follow_Desktop: false }\n"
    '  Shortcuts { Next_Focus: "Tab", Previous_Focus: "Shift+Tab",\n'
    '    Exit_Shortcut_Mode: "Ctrl+Q" } }\n'
)


def keys(private_sway: PrivateSway, *args: str) -> None:
    """Type with a virtual keyboard on the private compositor (``-s 300``: a fresh virtual
    keyboard sends its keymap first, and a key sent at once is lost)."""
    env = dict(private_sway.env)
    assert env["WAYLAND_DISPLAY"] == private_sway.display and private_sway.display
    subprocess.run(["wtype", "-s", "300", *args], env=env, timeout=20, check=True)


def mode_lines(shell: Shell) -> list[str]:
    """What the shell said of the mode, in order: ``mode F, focus F``, ``off``..."""
    found = []
    for line in shell.seen:
        match = re.search(r"shortcut mode: (mode \S+, focus \S+|off)\s*$", line)
        if match:
            found.append(match.group(1))
    return found


def test_the_keys_of_the_mode_arrive_on_the_surface_that_has_the_focus_and_the_keyboard_goes_back(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    write_example(tmp_path, BODY)
    folder = tmp_path / "Modules" / "Starter"
    folder.mkdir(parents=True)
    (folder / "Starter_Module.tdl").write_text(
        HEADER.replace("Main_Shell", "Starter") + STARTER_TDL
    )
    (folder / "Starter_Module.py").write_text(STARTER_PY)
    (tmp_path / "settings.tdl").write_text(SETTINGS)
    shell = Shell(tmp_path, private_sway.env)
    try:
        shell.wait_for("running")
        shell.wait_for("starter: entering the mode on F")
        shell.wait_for("shortcut mode: F takes the keyboard (exclusive)")
        time.sleep(1.0)  # sway gives the exclusive surface the keyboard
        keys(private_sway, "-k", "Tab")  # Next_Focus, bound in Shortcuts: a key event on the Frame
        shell.wait_for("key Tab -> Next_Focus")
        shell.wait_for("shortcut mode: Dock takes the keyboard (exclusive)")
        time.sleep(0.5)
        keys(private_sway, "-k", "Escape")  # the Frame has the mode: Escape leaves it
        shell.wait_for("key Escape -> Exit_Shortcut_Mode")
        shell.wait_for("shortcut mode: a window has its keyboard back (none)")
        time.sleep(0.5)
        keys(private_sway, "-k", "Tab")  # no mode now: the mode takes no key
        time.sleep(0.5)
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
    text = "".join(shell.seen)
    # the Frame is in the mode with the focus; Tab (Next_Focus) moves the focus to the Dock, with
    # the Frame still in the mode; Escape leaves
    assert mode_lines(shell) == ["mode F, focus F", "mode F, focus Dock", "off"]
    assert text.count("key Tab -> Next_Focus") == 1  # the Tab after the mode ended did nothing
    # sway made each surface active: the wait for the keyboard never ended in a warning
    assert "did not give" not in text
    assert "| ERROR " not in text


# -- the five actions through the fake kglobalaccel ----------------------------------------------

FIVE = (
    "    Shortcuts {\n"
    '        Enter_Shortcut_Mode: "Meta+F1"\n'
    '        Exit_Shortcut_Mode: "Meta+F2"\n'
    '        Set_Shortcut_Mode: "Meta+F3"\n'
    '        Next_Focus: "Meta+F4"\n'
    '        Previous_Focus: "Meta+F5"\n'
    "    }"
)
ENTER = parse_chord("Meta+F1").qt


def wait_for_modes(shell: Shell, count: int, timeout: float = 8) -> list[str]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        shell.seen.extend(_drain(shell))
        if len(mode_lines(shell)) >= count:
            break
        time.sleep(0.1)
    return mode_lines(shell)


def _drain(shell: Shell) -> list[str]:
    out = []
    while not shell.lines.empty():
        out.append(shell.lines.get())
    return out


def test_enter_is_the_one_global_key_and_the_other_four_run_when_the_desktop_runs_them(
    desk: Make,  # noqa: F811
) -> None:
    d = desk()
    body = BODY.replace(
        "    Children { Starter { } } }", "    Children { Rectangle { Width: 4, Height: 4 } } }"
    )
    write_example(d.cfg, body)
    d.settings(FIVE)
    shell = d.start()
    # all five are declared (the desktop lists them); only Enter carries its key: a key registered
    # with the desktop is a key taken from every application, and the mode's keys arrive as key
    # events on the surface that has the keyboard instead (see the first test)
    assert d.fake.names() == [
        "Enter_Shortcut_Mode",
        "Exit_Shortcut_Mode",
        "Set_Shortcut_Mode",
        "Next_Focus",
        "Previous_Focus",
    ]
    assert d.fake.keys_of("tesserae-shell", "Enter_Shortcut_Mode") == [ENTER]
    for name in ("Exit_Shortcut_Mode", "Set_Shortcut_Mode", "Next_Focus", "Previous_Focus"):
        assert d.fake.keys_of("tesserae-shell", name) == [], name
    d.fake.press("Next_Focus")  # a key the user bound in the desktop's settings: outside the mode
    d.seen("Next_Focus: the shell is not in shortcut mode; nothing done")
    assert d.fake.press_key(ENTER)  # Enter: the Frame, with the focus
    assert wait_for_modes(shell, 1) == ["mode F, focus F"]
    d.seen("shortcut mode: F takes the keyboard (exclusive)")
    d.fake.press("Next_Focus")  # the Dock
    assert wait_for_modes(shell, 2)[-1] == "mode F, focus Dock"
    d.fake.press("Set_Shortcut_Mode")  # on the focused Dock: the mode goes to it
    assert wait_for_modes(shell, 3)[-1] == "mode Dock, focus Dock"
    d.fake.press("Previous_Focus")  # in the Dock's own mode the Frame's keys do not apply
    d.seen("Previous_Focus: Dock is the surface in shortcut mode")
    assert d.fake.press_key(ENTER)  # Enter again: back to the Frame
    assert wait_for_modes(shell, 4)[-1] == "mode F, focus F"
    d.fake.press("Exit_Shortcut_Mode")
    assert wait_for_modes(shell, 5)[-1] == "off"
    assert d.finish() == 0
    assert mode_lines(shell) == [
        "mode F, focus F",
        "mode F, focus Dock",
        "mode Dock, focus Dock",
        "mode F, focus F",
        "off",
    ]
    assert "| ERROR " not in shell.stderr
