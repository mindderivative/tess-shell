"""Keys of the widgets on a real compositor, the private headless sway only (M6b, T-048): a click on
a Bar that says ``Keyboard: ON_DEMAND`` gives it the keyboard, Tab then reaches a Button, Enter and
Space press it (the module's action runs), Tab goes on to a Slider and the arrow keys move its
value: ``On_Changed`` then ``On_Released`` for each step.

The pointer is ``tests/live_pointer.py`` (a ``zwlr_virtual_pointer_v1``) and the keys are ``wtype``
(a ``zwp_virtual_keyboard_v1`` of its own), both aimed at the private sway through its
``WAYLAND_DISPLAY`` and nothing else, exactly as ``tests/test_focus_live.py`` does; no real device,
no ``/dev/uinput`` and no real session is touched. What the ``Probe`` test module of the M4c gallery
logs says which handler ran and with what value.
"""

from __future__ import annotations

import re
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest

from tests import live_pointer
from tests.kwin.prepare_m4c_gallery import PROBE_PY, PROBE_TDL
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
    "Width: EXPAND, Height: 32, Keyboard: ON_DEMAND, Style { Background: $color.surface }, "
    "Children { FlexBox { Width: EXPAND, Flex: HORIZONTAL, Spacing: 12, Padding: 4, "
    "Align_Items: CENTER, Children { "
    'Button { Name: Save, Text: "Save", '
    'On_Click { Action: Call, Target: "Probe.clicked", Who: "Save" } } '
    'Slider { Name: Vol, Value: 50, Label: "Volume", '
    'On_Changed { Action: Call, Target: "Probe.changed", Who: "Volume" } '
    'On_Released { Action: Call, Target: "Probe.released", Who: "Volume" } } '
    "Probe { } "
    "} } } } } } }\n"
)


def keys(private_sway: PrivateSway, *args: str) -> None:
    """Type with a virtual keyboard on the private compositor (``-s 300``: a fresh virtual
    keyboard sends its keymap first, and a key sent at once is lost)."""
    env = dict(private_sway.env)
    assert env["WAYLAND_DISPLAY"] == private_sway.display and private_sway.display
    subprocess.run(["wtype", "-s", "300", *args], env=env, timeout=20, check=True)


def test_tab_reaches_a_button_and_a_slider_and_enter_space_and_the_arrows_operate_them(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    (tmp_path / "Shells").mkdir()
    (tmp_path / "Shells" / "Main_Shell.tdl").write_text(HEADER + BODY)
    (tmp_path / "settings.tdl").write_text(SETTINGS)
    folder = tmp_path / "Modules" / "Probe"
    folder.mkdir(parents=True)
    (folder / "Probe_Module.tdl").write_text(PROBE_TDL)
    (folder / "Probe_Module.py").write_text(PROBE_PY)
    shell = Shell(tmp_path, private_sway.env)
    shell.wait_for("running")
    pointer: live_pointer.VirtualPointer | None = None
    try:
        # the Bar is configured by the compositor, then laid out: a click or a key before that
        # goes nowhere (a cold CI machine took longer than the 2 s this once waited)
        shell.wait_for("Bar Top on HEADLESS-1 configured", timeout=60)
        time.sleep(1.0)  # the first layout
        pointer = live_pointer.VirtualPointer(private_sway.env, *OUT)
        pointer.move(1000, 16)  # on the Bar, away from the widgets: it takes the keyboard
        pointer.click()
        time.sleep(0.5)
        keys(private_sway, "-k", "Tab")  # the Button
        keys(private_sway, "-k", "Return")
        keys(private_sway, "-k", "space")
        keys(private_sway, "-k", "Tab")  # the Slider
        keys(private_sway, "-k", "Right")
        keys(private_sway, "-k", "Right")
        keys(private_sway, "-k", "Left")
        keys(private_sway, "-k", "End")
        time.sleep(0.5)
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if pointer is not None:
            pointer.close()
        if shell.process.poll() is None:
            shell.process.kill()
    said = [m.group(1) for x in shell.seen if (m := re.search(r"\| Probe: (.*)$", x.rstrip()))]
    focus = [m.group(1) for x in shell.seen if (m := re.search(r"focus: \S+ '(.*)' \(ring\)", x))]
    log = "".join(shell.seen)[-4000:]  # what the shell said, for a failure
    assert focus == ["Save", "Volume"], f"{focus}\n{log}"  # Tab: the keyboard moved the focus
    assert said == [
        "Save clicked",  # Enter
        "Save clicked",  # Space
        "Volume: 50 -> 51",  # Right: On_Changed, then On_Released
        "Volume released at 51 (pressed at 50)",
        "Volume: 51 -> 52",
        "Volume released at 52 (pressed at 51)",
        "Volume: 52 -> 51",  # Left
        "Volume released at 51 (pressed at 52)",
        "Volume: 51 -> 100",  # End
        "Volume released at 100 (pressed at 51)",
    ], f"{said}\n{log}"
    assert "| ERROR " not in "".join(shell.seen)
