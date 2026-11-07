"""Strips and a melded Panel on a private headless sway: they are drawn by the painter at the
band and body the geometry names, a module in a strip runs, and the opening still shows what is
behind it."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from tests.sway import PrivateSway
from tests.test_frame_live import BEHIND, OUT, pixel, run_shell, screenshot, stop, usable

pytestmark = pytest.mark.tre

MAGENTA, BLUE, RED, GREEN = (255, 0, 255), (0, 0, 255), (255, 0, 0), (0, 255, 0)

FRAME = (
    "Frame { Name: F, Thickness: [24, 30, 24, 24], Inner_Radius: 10, "
    'Style { Background: "#0000ff" }, Edges { '
    "Top { Padding: [4, 4, 4, 4], Children { "
    'Rectangle { Name: Dot, Width: 40, Height: 20, Fill: "#ff0000" } } }, '
    "Left { Children { "
    'Rectangle { Name: A, Width: 12, Height: 30, Fill: "#ff0000" }, '
    'Rectangle { Name: B, Width: 12, Height: 30, Fill: "#00ff00" } } } } }'
)
TAB = (
    "Panel { Name: Tab, Meld: true, Attach_To: F, Attach: BOTTOM, Alignment: END, Length: 200, "
    'Depth: 50, Children { Rectangle { Name: Chip, Width: 30, Height: 30, Fill: "#00ff00" } } }'
)


def test_strips_and_a_melded_panel_are_drawn_where_the_geometry_says(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    shell = run_shell(private_sway, tmp_path, f"{BEHIND}\n{FRAME}\n{TAB}")
    try:
        rect = usable(private_sway, 24, 30, 24, 24)  # the strips reserve what the Frame says
        assert (rect["x"], rect["y"]) == (24, 30)
        time.sleep(0.6)
        shot = screenshot(private_sway)
        # top strip: band 30 high, padding 4: the 40 x 20 dot from (4, 4)
        assert pixel(shot, 4, 4) == RED and pixel(shot, 43, 23) == RED
        assert pixel(shot, 45, 10) == BLUE and pixel(shot, 4, 25) == BLUE
        # left strip: between the top and the bottom band, two 30 px children stacked
        assert pixel(shot, 5, 30 + 5) == RED and pixel(shot, 5, 30 + 35) == GREEN
        assert pixel(shot, 5, 30 + 70) == BLUE
        # the melded Panel: 200 x 50 against the bottom, to the right end of the opening
        right = OUT[0] - 24
        floor = OUT[1] - 24
        assert pixel(shot, right - 5, floor - 25) == BLUE  # in its body
        assert pixel(shot, right - 205, floor - 25) == MAGENTA  # left of it: the opening
        assert pixel(shot, right - 5, floor - 55) == MAGENTA  # above it: the opening
        assert pixel(shot, right - 195, floor - 45) == GREEN  # its content: a chip at the start
        assert pixel(shot, OUT[0] // 2, OUT[1] // 2) == MAGENTA  # what is behind shows
        text = "".join(shell.seen)
        while not shell.lines.empty():
            text += shell.lines.get()
        assert "strip F.Top built" in text and "melded Panel Tab built" in text
        stop(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()


CLOCK_STRIP = (
    'Frame { Name: F, Thickness: 30, Style { Background: "#0000ff" }, '
    'Edges { Top { Children { Clock { Name: Time, format: "%H:%M" } } } } }'
)


def test_a_module_in_a_strip_runs_and_its_text_is_drawn(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    shell = run_shell(private_sway, tmp_path, CLOCK_STRIP)
    try:
        usable(private_sway, 30, 30, 30, 30)
        deadline = time.monotonic() + 6
        found = False
        while time.monotonic() < deadline and not found:
            time.sleep(0.3)
            shot = screenshot(private_sway)
            # the Clock's text is drawn light on the blue band: some pixel is not the band colour
            found = any(pixel(shot, x, y) != BLUE for x in range(0, 200) for y in range(2, 26))
        assert found, "the Clock drew nothing in the strip"
        text = "".join(shell.seen)
        while not shell.lines.empty():
            text += shell.lines.get()
        assert "step 12 (modules): started" in text and "strip F.Top built" in text
        stop(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()


def test_saving_a_changed_strip_updates_it_on_screen_and_a_new_output_gets_its_own(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    import json
    import subprocess

    def sway(*args: str) -> str:
        return subprocess.run(
            ["swaymsg", *args], env=private_sway.env, capture_output=True, text=True
        ).stdout

    def seen(needle: str, timeout: float = 8) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            while not shell.lines.empty():
                shell.seen.append(shell.lines.get())
            if any(needle in line for line in shell.seen):
                return
            time.sleep(0.05)
        pytest.fail(f"never saw {needle!r}:\n{''.join(shell.seen)}")

    frame = (
        'Frame { Name: F, Thickness: 30, Style { Background: "#0000ff" }, Edges { Top { '
        'Children { Rectangle { Name: Dot, Width: 40, Height: 20, Fill: "#ff0000" } } } } }'
    )
    shell = run_shell(private_sway, tmp_path, frame, index="default")
    try:
        usable(private_sway, 30, 30, 30, 30)
        time.sleep(0.5)
        assert pixel(screenshot(private_sway), 10, 10) == RED
        file = tmp_path / "Shells" / "Main_Shell.tdl"
        file.write_text(file.read_text().replace('Fill: "#ff0000"', 'Fill: "#00ff00"'))
        deadline = time.monotonic() + 8
        while pixel(screenshot(private_sway), 10, 10) != GREEN and time.monotonic() < deadline:
            time.sleep(0.2)
        assert pixel(screenshot(private_sway), 10, 10) == GREEN  # the hot reload reached it
        sway("create_output")
        seen("Frame F on HEADLESS-2: strip F.Top built")
        sway("output", "HEADLESS-2", "unplug")
        seen("Frame F on HEADLESS-2 painter closed")
        outputs = json.loads(sway("-t", "get_outputs"))
        assert [o["name"] for o in outputs] == ["HEADLESS-1"]
        assert "Frame F on HEADLESS-1 painter closed" not in "".join(shell.seen)
        stop(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()


def test_a_popup_opens_beside_a_module_in_a_strip(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    from tests.test_panel_live import _rect_of
    from tests.test_popup_live import BTN_PY, BTN_TDL, MENU

    folder = tmp_path / "Modules" / "Btn"
    folder.mkdir(parents=True)
    (folder / "Btn_Module.tdl").write_text(BTN_TDL)
    (folder / "Btn_Module.py").write_text(BTN_PY)
    frame = (
        'Frame { Name: F, Thickness: 40, Style { Background: "#202020" }, Edges { Top { '
        "Children { Btn { Name: Btn_One } } } } }"
    )
    shell = run_shell(private_sway, tmp_path, f"{MENU}\n{frame}")
    try:
        shell.wait_for("Popup Menu")
        time.sleep(0.6)
        shot = screenshot(private_sway)
        assert (width := shot[0]) == OUT[0]
        ppm = b"P6\n%d %d\n255\n" % (shot[0], shot[1]) + shot[2]
        # the Btn is 60 x 20 at the start of the strip; the Popup (100 x 40, red) opens below it
        assert _rect_of(ppm, (255, 0, 0)) == (0, 20, 99, 59), width
        assert _rect_of(ppm, (0, 0, 255)) == (0, 0, 59, 19)
        stop(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
