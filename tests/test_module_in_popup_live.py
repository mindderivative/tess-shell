"""A module call in a ``For`` in a Popup on a private sway with a real (virtual) pointer: the
Popup opens with the entries of its data, a click on an entry runs the action with the entry's
arguments, the menu closes and the entries' uses end (Module File > Using a Module in a
Structure). The pointer is tre's ``wlr_pointer`` through ``tests/live_pointer.py``."""

from __future__ import annotations

import signal
import time
from pathlib import Path

import pytest

from tests import live_pointer
from tests.shell_samples import BODY, write_example
from tests.sway import PrivateSway
from tests.test_popup_live import grab
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not live_pointer.available(), reason="no pywayland (tre's virtual env)"),
]

OPENER_TDL = (
    "---\nTDL: 0.1\nName: Opener\n---\n"
    'Module { Rectangle { Name: Root, Width: 60, Height: 20, Fill: "#0000ff" } }\n'
)
OPENER_PY = """
from tess_shell import Module


class Opener(Module):
    ticks = 0

    def start(self):
        self.ctx.on_tick("second", self.tick)

    def tick(self):
        self.ticks += 1
        (use,) = self.ctx.uses.values()
        if self.ticks == 1:
            self.ctx.popup("Tray_Menu", use=use, data={"items": [
                {"id": "a", "text": "Alpha"}, {"id": "b", "text": "Beta"}]})
"""
TRAY_TDL = (
    "---\nTDL: 0.1\nName: TrayMenu\n---\n"
    "Module { FlexBox { Name: Root, Children { Menu { Children { "
    "For e In {{ caller.data.items }} Key {{ e.id }} { "
    "MenuItem { Text: {{ e.text }}, On_Click { Action: pick, Id: {{ e.id }} } } } } } } } }\n"
)
TRAY_PY = """
from tess_shell import Module, action


class TrayMenu(Module):
    @action
    def pick(self, event):
        self.ctx.log.info(f"picked {event.args['Id']}")
"""
POPUP = (
    'Popup { Name: Tray_Menu, Attach: BOTTOM, Style { Background: "#ff0000" }, '
    "Children { TrayMenu { } } }"
)
SETTINGS = (
    "---\nTDL: 0.1\nName: S\n---\n"
    "Settings { Logging { Level: DEBUG } Appearance { Stylesheets: [Default] } }\n"
)
OUT = (1280, 720)


def red_box(sway: PrivateSway) -> tuple[int, int, int, int] | None:
    ppm = grab(sway)
    _, size, _, pixels = ppm.split(b"\n", 3)
    width, height = map(int, size.split())
    hits = [
        (i % width, i // width)
        for i in range(width * height)
        if pixels[i * 3 : i * 3 + 3] == b"\xff\x00\x00"
    ]
    if not hits:
        return None
    xs, ys = [h[0] for h in hits], [h[1] for h in hits]
    return min(xs), min(ys), max(xs), max(ys)


def test_a_real_click_on_an_entry_of_a_popup_runs_its_action_and_ends_the_entries(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    for name, tdl, py in (
        ("Opener", OPENER_TDL, OPENER_PY),
        ("TrayMenu", TRAY_TDL, TRAY_PY),
    ):
        folder = tmp_path / "Modules" / name
        folder.mkdir(parents=True)
        (folder / f"{name}_Module.tdl").write_text(tdl)
        (folder / f"{name}_Module.py").write_text(py)
    body = BODY.replace(
        'Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }', "Opener { }"
    ).replace("            Bar {", f"            {POPUP}\n            Bar {{", 1)
    write_example(tmp_path, body)
    (tmp_path / "settings.tdl").write_text(SETTINGS)
    shell = Shell(tmp_path, private_sway.env)
    pointer = None
    try:
        shell.wait_for("Popup Tray_Menu on HEADLESS-1 opened", timeout=20)
        shell.wait_for("a use of an entry came")
        assert "".join(shell.seen).count("a use of an entry came") == 2
        deadline = time.monotonic() + 8
        box = red_box(private_sway)
        while box is None and time.monotonic() < deadline:
            time.sleep(0.2)
            box = red_box(private_sway)
        assert box is not None
        x0, y0, x1, y1 = box
        pointer = live_pointer.VirtualPointer(private_sway.env, *OUT)
        # the second row ("Beta"): the menu has 4 px of padding and 28 px rows
        pointer.move(x0 + 40, y0 + 4 + 28 + 14)
        pointer.click()
        shell.wait_for("picked b")
        shell.wait_for("Popup Tray_Menu on HEADLESS-1 closing")
        shell.wait_for("ended: MenuItem@Main_Shell.Main.Tray_Menu.TrayMenu_1.for0.MenuItem_0002")
        text = "".join(shell.seen)
        assert text.count("the use of an entry ended") == 2
        assert "picked a" not in text
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if pointer is not None:
            pointer.close()
        if shell.process.poll() is None:
            shell.process.kill()
    errors = [x for x in shell.seen if "| ERROR " in x]
    assert errors == [], errors
