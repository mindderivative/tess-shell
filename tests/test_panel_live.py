"""A Panel on a private headless sway: it opens where it is asked, an OSD hides itself, and a
Panel with ``Visible: false`` opens hidden (Panel acceptance criteria)."""

from __future__ import annotations

import signal
import time
from pathlib import Path

import pytest

from tests.shell_samples import BODY, write_example
from tests.sway import PrivateSway
from tests.test_reload_live import stamp
from tests.test_run import Shell

pytestmark = pytest.mark.tre

OSD = (
    "Panel { Name: Volume_OSD, Layer: OVERLAY, Anchor: [BOTTOM], Inset: [0, 0, 0, 80], "
    "Width: 260, Height: 60, Input_Region: [], Hide_After: 400, "
    'Style { Fill: "#202020", Elevation: 20% }, Children { FlexBox { Name: Bar_Inside } } }'
)
LAUNCHER = (
    "Panel { Name: Launcher, Layer: OVERLAY, Keyboard: EXCLUSIVE, Width: 600, Height: 400, "
    "Visible: false }"
)


def start(sway: PrivateSway, cfg: Path, panels: str) -> Shell:
    body = BODY.replace("            Bar {", f"            {panels}\n            Bar {{", 1)
    write_example(cfg, body)
    return Shell(cfg, sway.env)


def finish(shell: Shell) -> None:
    shell.process.send_signal(signal.SIGTERM)
    assert shell.finish() == 0


def test_an_osd_opens_with_its_size_and_hides_itself_after_hide_after(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    shell = start(private_sway, tmp_path, OSD)
    try:
        shell.wait_for("Panel Volume_OSD on HEADLESS-1 configured")
        # 260 x 60 body plus the 20 % elevation's margin: 11 each side, 8 above and 14 below
        text = "".join(shell.seen)
        assert "Volume_OSD on HEADLESS-1: anchor bottom size (282, 82) zone 0" in text
        assert "Volume_OSD on HEADLESS-1 configured 282x82" in text
        shell.wait_for("Panel Volume_OSD on HEADLESS-1 hidden")
        opened = next(x for x in shell.seen if "Volume_OSD on HEADLESS-1: anchor" in x)
        hidden = next(x for x in shell.seen if "Volume_OSD on HEADLESS-1 hidden" in x)
        assert 0.35 < stamp(hidden) - stamp(opened) < 1.5  # about Hide_After (400 ms)
        finish(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()


def test_a_panel_with_visible_false_opens_hidden_and_the_shell_stops_cleanly(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    shell = start(private_sway, tmp_path, LAUNCHER)
    try:
        shell.wait_for("Panel Launcher on HEADLESS-1")
        shell.wait_for("running")
        text = "".join(shell.seen)
        assert "Panel Launcher on HEADLESS-1: anchor none size (600, 400)" in text
        assert "(hidden)" in text and "Panel Launcher on HEADLESS-1 hidden" not in text
        time.sleep(0.3)
        finish(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
    assert "| ERROR " not in "".join(shell.seen)
