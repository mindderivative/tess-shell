"""Keyboard focus on a real compositor, the private headless sway only (M6a, T-041): a click on a
Bar that says ``Keyboard: ON_DEMAND`` gives it the keyboard, and Tab and Shift+Tab then move the
focus ring over its Buttons in the order of the file; a Bar that says
``Keyboard: NONE`` is given no key.

The pointer is ``tests/live_pointer.py`` (a ``zwlr_virtual_pointer_v1`` kept alive by tre's test
helper) and the keys are ``wtype`` (a ``zwp_virtual_keyboard_v1`` of its own, which is what tre's
own live tests use too), both aimed at the private sway through its ``WAYLAND_DISPLAY`` and nothing
else; no real device, no ``/dev/uinput`` and no real session is touched. The shell's DEBUG log says
which block has the focus (``focus: <block> (ring)``)."""

from __future__ import annotations

import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

from tests import live_pointer
from tests.shell_samples import HEADER
from tests.sway import PrivateSway
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not live_pointer.available(), reason="no pywayland (tre's virtual env)"),
    pytest.mark.skipif(shutil.which("wtype") is None, reason="no wtype (a virtual keyboard)"),
]

OUT = (1280, 720)
SETTINGS = (
    "---\nTDL: 0.2\nName: S\n---\n"
    "Settings { Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default], Follow_Desktop: false } }\n"
)
BODY = (
    "Shell { Monitor { Name: Main, Index: 0, Children { Bar { Name: Top, Edge: TOP, "
    "Width: EXPAND, Height: 32, %s Style { Background: $color.surface }, Children { FlexBox { "
    "Width: EXPAND, Flex: HORIZONTAL, Spacing: 4, Padding: 4, Align_Items: CENTER, Children { "
    'Button { Name: One, Text: "One" } '
    'Button { Name: Two, Text: "Two" } '
    'Button { Name: Three, Text: "Three" } '
    "} } } } } } }\n"
)


def focus_lines(shell: Shell) -> list[str]:
    """The blocks the shell says took keyboard focus, in order, as ``Label (ring | no ring)``."""
    found: list[str] = []
    for line in shell.seen:
        match = re.search(r"focus: \S+ '(.*)' \((ring|no ring)\)", line)
        if match:
            found.append(f"{match.group(1)} ({match.group(2)})")
    return found


def keys(private_sway: PrivateSway, *args: str) -> None:
    """Type with a virtual keyboard on the private compositor (``-s 300``: a fresh virtual
    keyboard sends its keymap first, and a key sent at once is lost)."""
    env = dict(private_sway.env)
    assert env["WAYLAND_DISPLAY"] == private_sway.display and private_sway.display
    subprocess.run(["wtype", "-s", "300", *args], env=env, timeout=20, check=True)


@pytest.mark.parametrize("mode", ["ON_DEMAND", "NONE"])
def test_a_click_gives_an_on_demand_bar_the_keyboard_and_tab_follows_the_file_order(
    private_sway: PrivateSway, tmp_path: Path, mode: str
) -> None:
    (tmp_path / "Shells").mkdir()
    (tmp_path / "Shells" / "Main_Shell.tdl").write_text(HEADER + BODY % f"Keyboard: {mode},")
    (tmp_path / "settings.tdl").write_text(SETTINGS)
    shell = Shell(tmp_path, private_sway.env)
    shell.wait_for("running")
    pointer: live_pointer.VirtualPointer | None = None
    try:
        time.sleep(2.0)  # the first layout
        pointer = live_pointer.VirtualPointer(private_sway.env, *OUT)
        pointer.move(20, 16)  # on the first Button ("One")
        pointer.click()
        time.sleep(0.5)
        keys(private_sway, "-k", "Tab")
        keys(private_sway, "-k", "Tab")
        keys(private_sway, "-M", "shift", "-k", "Tab", "-m", "shift")
        time.sleep(0.5)
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if pointer is not None:
            pointer.close()
        if shell.process.poll() is None:
            shell.process.kill()
    seen = focus_lines(shell)
    if mode == "ON_DEMAND":
        # a click focuses the Button with no ring; Tab goes on in the order of the file: from One
        # to Two and Three, and Shift+Tab goes back to Two
        assert seen == [
            "One (no ring)",
            "Two (ring)",
            "Three (ring)",
            "Two (ring)",
        ], seen
    else:
        assert seen == ["One (no ring)"], seen  # the compositor gave the Bar no key
    assert "| ERROR " not in "".join(shell.seen)
