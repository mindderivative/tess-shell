"""Every kind of peek reached by a real pointer, on a private headless sway, with the Frame's ring
drawn as paths (``SRGB``) and as one shader (``LINEAR``): a hover that raises a Panel after its
delay and sends it back, a click on a tab, a drag of a tab and a drag of a strip's sliver.

``Window.simulate`` goes through tre's own hit test and passes whatever the compositor would do;
the compositor delivers input only inside the surface's input region (``input_region="auto"``, the
union of what the painter draws), so a ring that is not counted in it has a painter that never
gets the pointer (the LINEAR build once had none: nothing peeked on KWin). A virtual pointer
(``tests/live_pointer.py``, pywayland in tre's environment) sends the events; the test is skipped
where that is not there."""

from __future__ import annotations

import re
import time
from pathlib import Path

import pytest

from tests import live_pointer
from tests.shell_samples import HEADER
from tests.sway import PrivateSway
from tests.test_frame_live import pixel, screenshot, stop
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not live_pointer.available(), reason="no pywayland (tre's virtual env)"),
]

OUT = (1920, 1080)
FRAME = """
Frame {
    Name: F
    Thickness { Left: 10, Top: 34, Right: 12, Bottom: 14 }
    Inner_Radius: 14
    Inner_Border { Width: 2, Color: "#89b4fa" }
    Style { Background: "#1e1e2e" }
    Edges {
        Left {
            Name: Left_Strip
            Thickness: 56
            Padding: 6
            Peek { Size: 10, Trigger: DRAG }
            Children { Rectangle { Name: Chip, Width: 16, Height: 40, Fill: "#f38ba8" } }
        }
    }
}
Panel { Name: Dock, Meld: true, Attach_To: F, Attach: BOTTOM, Alignment: CENTER, Length: 320,
    Depth: 56, Peek { Size: 24, Trigger: HOVER, Enter_Delay: 150, Exit_Delay: 300 },
    Animation { Type: SLIDE, Duration: 300 }, Style { Corner_Radius: 12 },
    Children { Rectangle { Name: DockDot, Width: 20, Height: 20, Fill: "#f9e2af" } } }
Panel { Name: Notes, Meld: true, Attach_To: F, Attach: TOP, Alignment: END, Length: 220, Depth: 90,
    Peek { Size: 12, Trigger: CLICK, Slide_From: RIGHT },
    Animation { Type: SLIDE, Duration: 300 }, Style { Corner_Radius: 12 },
    Children { Rectangle { Name: NotesDot, Width: 20, Height: 20, Fill: "#a6e3a1" } } }
Panel { Name: Tray, Meld: true, Attach_To: F, Attach: BOTTOM, Alignment: START, Length: 200,
    Depth: 60, Peek { Size: 14, Trigger: DRAG },
    Animation { Type: SLIDE, Duration: 300 }, Style { Corner_Radius: 12 },
    Children { Rectangle { Name: TrayDot, Width: 20, Height: 20, Fill: "#89dceb" } } }
"""
EVENT = re.compile(r"(Panel|strip) (\w+) on \S+ (shown|hiding)")


def run(sway: PrivateSway, cfg: Path, blend: str) -> list[str]:
    """The pointer script; the ``shown``/``hiding`` log lines it caused, in order."""
    (cfg / "Shells").mkdir(parents=True, exist_ok=True)
    body = f"\nShell {{ Monitor {{ Name: Main, Index: 0, Children {{ {FRAME} }} }} }}\n"
    (cfg / "Shells" / "Main_Shell.tdl").write_text(HEADER + body)
    (cfg / "settings.tdl").write_text(
        "---\nTDL: 0.1\nName: S\n---\n"
        f"Settings {{ Logging {{ Level: DEBUG }} Debug {{ Frame_Blend: {blend} }} }}\n"
    )
    sway.msg("output", "*", "resolution", f"{OUT[0]}x{OUT[1]}")
    sway.msg("output", "*", "scale", "1")
    time.sleep(0.4)
    shell = Shell(cfg, sway.env)
    pointer = live_pointer.VirtualPointer(sway.env, *OUT)
    seen: list[str] = []

    def events() -> list[str]:
        for line in shell.seen:
            if m := EVENT.search(line):
                seen.append(" ".join(m.groups()))
        shell.seen.clear()
        return seen

    def expect(count: int, what: str) -> None:
        deadline = time.monotonic() + 8
        while len(events()) < count and time.monotonic() < deadline:
            try:
                shell.seen.append(shell.lines.get(timeout=0.1))
            except Exception:  # queue.Empty: look again
                pass
        assert len(events()) >= count, f"{what}: {events()}"

    def ring_at(x: int, y: int, what: str) -> None:
        """The pixel is the Frame's own colour (a body is out there) within 8 s. A drag logs nothing
        (only a show or a hide by a delay or a click does), so it is the pixels that say."""
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            if pixel(screenshot(sway), x, y) == (0x1E, 0x1E, 0x2E):
                seen.append(what)
                return
            time.sleep(0.2)
        raise AssertionError(f"{what}: nothing at {x},{y}; {events()}")

    try:
        shell.wait_for("painter configured", timeout=30)
        time.sleep(1.0)
        pointer.move(100, 500)  # in the opening
        # HOVER: the Dock's 24 px tab (x 800..1120, y 1042..1066); out after Enter_Delay, back
        # after Exit_Delay when the pointer leaves
        pointer.move(960, 1055)
        expect(1, "hover on the Dock tab")
        time.sleep(0.6)
        pointer.move(960, 500)
        expect(2, "leaving the Dock")
        time.sleep(0.6)
        assert pixel(screenshot(sway), 100, 1030) != (0x1E, 0x1E, 0x2E)  # at rest: only a tab
        # CLICK: Notes' 12 px tab on the right band at its top end (x 1896..1908, y 34..124)
        pointer.move(1902, 80)
        time.sleep(0.2)
        pointer.click()
        expect(3, "a click on the Notes tab")
        time.sleep(0.6)
        pointer.move(960, 500)
        # DRAG: Tray's 14 px tab at the bottom left (x 10..210, y 1052..1066), pulled up past half
        pointer.move(100, 1058)
        time.sleep(0.2)
        pointer.down()
        for y in (1050, 1030, 1010):
            pointer.move(100, y)
            time.sleep(0.1)
        pointer.up()
        ring_at(100, 1030, "Tray dragged out")
        time.sleep(0.6)
        pointer.move(960, 500)
        # DRAG a strip's sliver: Left_Strip's 10 px sliver (x 0..10), pulled right past half
        pointer.move(5, 500)
        time.sleep(0.2)
        pointer.down()
        for x in (20, 40, 60):
            pointer.move(x, 500)
            time.sleep(0.1)
        pointer.up()
        ring_at(30, 700, "Left_Strip dragged out")
        time.sleep(0.5)
        return events()
    finally:
        pointer.close()
        stop(shell)


def test_every_peek_trigger_works_with_a_real_pointer_and_the_same_with_either_blend(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    got = {blend: run(private_sway, tmp_path / blend, blend) for blend in ("SRGB", "LINEAR")}
    want = [
        "Panel Dock shown",
        "Panel Dock hiding",
        "Panel Notes shown",
        "Tray dragged out",
        "Left_Strip dragged out",
    ]
    assert got["SRGB"] == want, got
    assert got["LINEAR"] == want, got
