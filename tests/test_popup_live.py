"""A Popup on a private headless sway: it opens beside the module that called it through
``ctx.popup``, flips above a Bar at the bottom of the output, and is on the pixels its geometry
names (Popup acceptance criteria). The private sway has no pointer or keyboard, so a module opens
the Popup from the shared time source and the compositor's own dismissal is not exercised here
(``tests/test_popup.py`` runs the logic with simulated events)."""

from __future__ import annotations

import signal
import subprocess
import time
from pathlib import Path

import pytest

from tests.shell_samples import BODY, write_example
from tests.sway import PrivateSway
from tests.test_panel_live import _rect_of
from tests.test_run import Shell

pytestmark = pytest.mark.tre

BTN_TDL = (
    "---\nTDL: 0.1\nName: Btn\n---\n"
    'Module { Rectangle { Width: 60, Height: 20, Fill: "#0000ff" } }\n'
)
# opens the Popup from the first second tick, as an @action would from a click (use= is what the
# shell supplies as ctx.caller there), closes it on the third and opens an unknown one on the fourth
BTN_PY = """
from tess_shell import Module


class Btn(Module):
    ticks = 0

    def start(self):
        self.ctx.on_tick("second", self.tick)

    def tick(self):
        self.ticks += 1
        (use,) = self.ctx.uses.values()
        if self.ticks == 1:
            self.ctx.popup("Menu", use=use)
        elif self.ticks == 3:
            self.ctx.popup("Menu", use=use)  # the open one: a toggle, it closes
        elif self.ticks == 4:
            self.ctx.popup("Mnu", use=use)  # no such Popup: logged, nothing raised
"""
MENU = (
    'Popup { Name: Menu, Width: 100, Height: 40, Style { Fill: "#ff0000" }, '
    "Children { FlexBox { } } }"
)


def start(
    sway: PrivateSway, cfg: Path, bar_edge: str, popup: str = MENU, py: str = BTN_PY
) -> Shell:
    folder = cfg / "Modules" / "Btn"
    folder.mkdir(parents=True)
    (folder / "Btn_Module.tdl").write_text(BTN_TDL)
    (folder / "Btn_Module.py").write_text(py)
    body = BODY.replace(
        'Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }', "Btn { Name: Btn_One }"
    ).replace("Edge: TOP", f"Edge: {bar_edge}")
    body = body.replace("            Bar {", f"            {popup}\n            Bar {{", 1)
    write_example(cfg, body)
    return Shell(cfg, sway.env)


def finish(shell: Shell) -> None:
    shell.process.send_signal(signal.SIGTERM)
    assert shell.finish() == 0


def grab(sway: PrivateSway) -> bytes:
    return subprocess.run(
        ["grim", "-t", "ppm", "-"], env=sway.env, capture_output=True, check=True
    ).stdout


def wait_for_shot(
    sway: PrivateSway, colour: tuple[int, int, int], timeout: float = 5
) -> tuple[bytes, tuple[int, int, int, int]]:
    """Screenshots until a rectangle of ``colour`` is on screen (the popup takes a few frames)."""
    deadline = time.monotonic() + timeout
    while True:
        shot = grab(sway)
        found = _rect_of(shot, colour)
        if found is not None or time.monotonic() > deadline:
            assert found is not None, f"no {colour} on screen"
            return shot, found
        time.sleep(0.15)


def test_a_popup_called_from_a_module_opens_beside_it_flips_up_under_a_bottom_bar_and_toggles(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    shell = start(private_sway, tmp_path, "BOTTOM")
    try:
        shell.wait_for("Popup Menu on HEADLESS-1 opened")
        shot, red = wait_for_shot(private_sway, (255, 0, 0))
        blue = _rect_of(shot, (0, 0, 255))
        assert blue is not None
        bx0, by0, bx1, by1 = blue
        x0, y0, x1, y1 = red
        assert (x1 - x0 + 1, y1 - y0 + 1) == (100, 40)  # the body is the size asked for
        assert x0 == bx0  # Alignment START: its left edge on the module's
        assert y1 < by0  # flipped: no room below the module, the popup is above it
        shell.wait_for("Popup Menu on HEADLESS-1 placed")
        assert "on TOP (no room on BOTTOM)" in "".join(shell.seen)
        assert "the compositor flipped it" not in "".join(shell.seen)
        shell.wait_for("Popup Menu on HEADLESS-1 closing (toggled)")
        shell.wait_for("Popup Menu on HEADLESS-1 closed (app)")
        shell.wait_for("no Popup named Mnu on Monitor Main@HEADLESS-1")
        assert "did you mean Menu" in "".join(shell.seen)
        finish(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
    errors = [line for line in shell.seen if "| ERROR " in line]
    assert len(errors) == 1 and "ctx.popup('Mnu')" in errors[0]  # only the call that was wrong


@pytest.mark.parametrize("edge", ["TOP", "BOTTOM"])
@pytest.mark.parametrize("elevation", ["", "Elevation: 20%, "])
def test_the_body_is_gap_pixels_from_the_module_on_either_side_with_or_without_a_shadow(
    private_sway: PrivateSway, tmp_path: Path, edge: str, elevation: str
) -> None:
    """Under a top Bar the popup opens below, under a bottom Bar above; a 6 px Gap is 6 px between
    the module and the visible body, shadow margin or not (Popup > Placement)."""
    menu = MENU.replace("Width: 100", "Gap: 6, Width: 100").replace(
        "Style { ", "Style { " + elevation
    )
    shell = start(private_sway, tmp_path, edge, menu)
    try:
        shell.wait_for("Popup Menu on HEADLESS-1 opened")
        shot, red = wait_for_shot(private_sway, (255, 0, 0))
        height = int(shot.split(b"\n", 2)[1].split()[1])
        top = 4 if edge == "TOP" else height - 32 + 4  # the Bar is 32 high with 4 px of padding
        module = (top, top + 19)  # the module is 20 high
        if edge == "TOP":
            assert red[1] - module[1] - 1 == 6
        else:
            assert module[0] - red[3] - 1 == 6
        assert (red[2] - red[0] + 1, red[3] - red[1] + 1) == (100, 40)
        if not elevation:  # a shadow margin at the screen's left edge slides it (Popup > Placement)
            assert red[0] == 4  # START: its left edge on the module's
        finish(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()


def test_content_taller_than_max_height_makes_a_popup_of_max_height_on_screen(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    """Five 50 px rectangles are 250 px of content: the popup is Max_Height (120) tall and the
    rest scrolls (Popup > Size)."""
    column = (
        "FlexBox { Flex: VERTICAL, Children { "
        + 'Rectangle { Width: 80, Height: 50, Fill: "#ff0000" } ' * 5
        + "} }"
    )
    shell = start(
        private_sway,
        tmp_path,
        "TOP",
        f"Popup {{ Name: Menu, Max_Height: 120, Children {{ {column} }} }}",
    )
    try:
        shell.wait_for("Popup Menu on HEADLESS-1 opened")
        _, red = wait_for_shot(private_sway, (255, 0, 0))
        assert (red[2] - red[0] + 1, red[3] - red[1] + 1) == (80, 120)
        finish(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()


REPLACE_PY = (
    BTN_PY.split("    def tick")[0]
    + """    def tick(self):
        self.ticks += 1
        (use,) = self.ctx.uses.values()
        self.ctx.popup("Menu" if self.ticks == 1 else "Other", use=use)
"""
)
OTHER = (
    'Popup { Name: Other, Width: 50, Height: 30, Style { Fill: "#00ff00" }, '
    "Children { FlexBox { } } }"
)


def test_calling_another_popup_replaces_the_open_one_on_a_real_compositor(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    """The first Popup is still mapped when the second is made in the same turn: the compositor
    takes the second without a protocol error and only the second stays on screen."""
    shell = start(private_sway, tmp_path, "TOP", f"{MENU}\n{OTHER}", REPLACE_PY)
    try:
        shell.wait_for("Popup Menu on HEADLESS-1 opened")
        wait_for_shot(private_sway, (255, 0, 0))
        shell.wait_for("Popup Menu on HEADLESS-1 closing (replaced)")
        shell.wait_for("Popup Other on HEADLESS-1 opened")
        shot, green = wait_for_shot(private_sway, (0, 255, 0))
        assert (green[2] - green[0] + 1, green[3] - green[1] + 1) == (50, 30)
        deadline = time.monotonic() + 3
        while _rect_of(shot, (255, 0, 0)) is not None and time.monotonic() < deadline:
            time.sleep(0.15)
            shot = grab(private_sway)
        assert _rect_of(shot, (255, 0, 0)) is None  # the first one is gone
        shell.wait_for("Popup Menu on HEADLESS-1 closed (app)")
        assert shell.process.poll() is None  # no protocol error killed the shell
        finish(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
    assert not [line for line in shell.seen if "| ERROR " in line]
