"""A melded Panel that peeks, on a private headless sway (grim reads the pixels): the tab at rest,
the whole body after a ``Show``, the tab again after ``Hide_After``. The pointer cannot be put on a
headless sway, so the hover logic is tested headless (``test_frame_peek``); here ``Show`` comes
from another melded Panel's ``On_Hidden`` after its own ``Hide_After``, the click-less path."""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.sway import PrivateSway
from tests.test_frame_live import BEHIND, OUT, pixel, run_shell, screenshot, stop, usable

pytestmark = pytest.mark.tre

MAGENTA, BLUE = (255, 0, 255), (0, 0, 255)

FRAME = 'Frame { Name: F, Thickness: 30, Style { Background: "#0000ff" } }'
TRIGGER = (
    "Panel { Name: Trigger, Meld: true, Attach_To: F, Attach: LEFT, Alignment: START, "
    "Length: 60, Depth: 40, Hide_After: 1500, Animation { Type: NONE }, "
    "On_Hidden { Action: Show, Target: Tab } }"
)
TAB = (
    "Panel { Name: Tab, Meld: true, Attach_To: F, Attach: BOTTOM, Alignment: CENTER, "
    "Length: 200, Depth: 50, Peek { Size: 14 }, Hide_After: 2500, "
    "Animation { Type: SLIDE, Duration: 300 } }"
)


def until(sway: PrivateSway, want: Callable[[tuple[int, int, bytes]], bool], what: str) -> None:
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        if want(screenshot(sway)):
            return
        time.sleep(0.1)
    pytest.fail(f"never saw {what}")


def test_a_peeking_panel_rests_as_a_tab_comes_out_on_show_and_goes_back(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    shell = run_shell(private_sway, tmp_path, f"{BEHIND}\n{FRAME}\n{TRIGGER}\n{TAB}")
    try:
        usable(private_sway, 30, 30, 30, 30)  # the zones do not change with the tab or the body
        x, floor = OUT[0] // 2, OUT[1] - 30
        time.sleep(0.4)
        first = screenshot(private_sway)
        assert pixel(first, x, floor - 7) == BLUE  # in the tab: 14 px above the band
        assert pixel(first, x, floor - 20) == MAGENTA  # above it: the opening, what is behind
        assert pixel(first, x, OUT[1] - 10) == BLUE  # the band is whole
        # Trigger hides after 1.5 s and its On_Hidden shows the Panel: the body comes out
        until(
            private_sway,
            lambda s: pixel(s, x, floor - 40) == BLUE and pixel(s, x, floor - 55) == MAGENTA,
            "the whole body (50 px) after the Show",
        )
        rect = usable(private_sway, 30, 30, 30, 30)
        assert (rect["x"], rect["y"]) == (30, 30)  # still no reflow
        # Hide_After (2.5 s from when it was out) sends it back to the tab, not away
        until(
            private_sway,
            lambda s: pixel(s, x, floor - 40) == MAGENTA and pixel(s, x, floor - 7) == BLUE,
            "the tab again after Hide_After",
        )
        text = "".join(shell.seen)
        while not shell.lines.empty():
            text += shell.lines.get()
        assert "melded Panel Tab built" in text
        stop(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()


def test_the_kwin_peek_demo_builds_and_rests_as_a_tab_and_a_sliver(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    """The scratch config ``tests/kwin/prepare_m3c_strips.py`` writes for the KWin checklist
    (variant C) runs on the private sway: the Dock rests as a 24 px tab, the left strip as a
    6 px sliver with its blocks not drawn, the zones are the sliver's, and it stops cleanly."""
    from tests.kwin.prepare_m3b_popups import BUTTON_PY, BUTTON_TDL
    from tests.kwin.prepare_m3c_strips import SETTINGS as DEMO_SETTINGS
    from tests.kwin.prepare_m3c_strips import shell_text
    from tests.shell_samples import SVG
    from tests.test_run import Shell

    (tmp_path / "Shells").mkdir()
    (tmp_path / "Shells" / "dot.svg").write_text(SVG)
    (tmp_path / "settings.tdl").write_text(DEMO_SETTINGS)
    module = tmp_path / "Modules" / "Menu_Button"
    module.mkdir(parents=True)
    (module / "Menu_Button_Module.tdl").write_text(BUTTON_TDL)
    (module / "Menu_Button_Module.py").write_text(BUTTON_PY)
    text = shell_text("c").replace('Connector: "HDMI-A-1"', "Index: 0")
    (tmp_path / "Shells" / "Main_Shell.tdl").write_text(text)
    shell = Shell(tmp_path, private_sway.env)
    shell.wait_for("running")
    try:
        rect = usable(private_sway, 8, 36, 10, 10)  # the sliver + border, 34 + border, 8 + border
        assert (rect["x"], rect["y"]) == (8, 36)
        time.sleep(0.8)
        shot = screenshot(private_sway)
        mid = OUT[0] // 2 + (40 - 8) // 2  # the Dock is centred in the opening
        floor = OUT[1] - 8
        assert pixel(shot, mid, floor - 12) != pixel(shot, mid, floor - 60)  # a tab, not a body
        assert pixel(shot, 3, 300) == pixel(shot, mid, floor - 4)  # the sliver: the Frame colour
        assert pixel(shot, 20, 300) != pixel(shot, 3, 300)  # beside it, the opening
        text = "".join(shell.seen)
        while not shell.lines.empty():
            text += shell.lines.get()
        assert "strip Left_Strip built" in text and "melded Panel Dock built" in text
        stop(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
