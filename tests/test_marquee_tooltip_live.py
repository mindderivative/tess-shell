"""A disabled Marquee text that is cut with an ellipsis shows its whole text in a tooltip on a real
compositor (M4 Brief, question 24): a real (virtual) pointer on the private sway, which goes through
the surface's input region as the maintainer's pointer does on KWin, and which ``Window.simulate``
does not. Nothing else disabled opens a tooltip."""

from __future__ import annotations

import signal
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
]

OUT = (1280, 720)
LONG = "a very long text that does not fit in a hundred pixels"
SETTINGS = (
    "---\nTDL: 0.1\nName: S\n---\n"
    "Settings { Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default], Follow_Desktop: false } }\n"
)
TIP = 'Tooltip: "tip"'
BOX = "Width: 100, Height: 20, Style { Background: $color.primary }"
# left to right, 100 wide and 12 apart from x = 4: a disabled cut Marquee_Text, a disabled one that
# fits, an enabled one that scrolls, an enabled block with a tooltip, a disabled block with one
BODY = (
    "Shell { Monitor { Name: Main, Index: 0, Children { Bar { Name: Top, Edge: TOP, "
    "Width: EXPAND, Height: 32, Style { Background: $color.surface }, Children { FlexBox { "
    "Width: EXPAND, Flex: HORIZONTAL, Spacing: 12, Padding: 4, Align_Items: CENTER, Children { "
    f'Marquee_Text {{ Text: "{LONG}", Width: 100, Enabled: false }} '
    'Marquee_Text { Text: "fits", Width: 100, Enabled: false } '
    f'Marquee_Text {{ Text: "{LONG}", Width: 100 }} '
    f"FlexBox {{ {BOX}, {TIP} }} "
    f"FlexBox {{ {BOX}, Enabled: false, {TIP} }} "
    "} } } } } } }\n"
)
CENTRES = [54, 166, 278, 390, 502]


def test_only_the_disabled_cut_marquee_opens_a_tooltip_over_a_disabled_block(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    from tests.live_pointer import VirtualPointer

    (tmp_path / "Shells").mkdir()
    (tmp_path / "Shells" / "Main_Shell.tdl").write_text(HEADER + BODY)
    (tmp_path / "settings.tdl").write_text(SETTINGS)
    shell = Shell(tmp_path, dict(private_sway.env))
    shell.wait_for("running")
    pointer = VirtualPointer(private_sway.env, *OUT)
    try:
        # the disabled cut one first, then each of the others; between them the pointer leaves the
        # Bar, so the open tooltip closes. The log is read once the shell has stopped.
        for x in CENTRES:
            pointer.move(x - 20, 100)
            pointer.move(x - 10, 16)
            pointer.move(x, 16)
            time.sleep(1.3)  # the Enter_Delay is 500 ms
            pointer.move(x, 100)
            time.sleep(0.8)
        shell.process.send_signal(signal.SIGTERM)
        shell.finish()
    finally:
        pointer.close()
        if shell.process.poll() is None:
            shell.process.kill()
    opened = [x for x in shell.seen if "Popup tooltip" in x and " opened " in x]
    assert len(opened) == 2, opened
    assert "beside Marquee_Text" in opened[0]  # the disabled cut one
    assert "beside Marquee_Text" not in opened[1]  # the enabled block with a tooltip
    assert "| ERROR " not in "".join(shell.seen)
