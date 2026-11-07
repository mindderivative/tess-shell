"""The Frame on a private headless sway: the ring is drawn at the output's edges with its
thickness, the opening shows what is behind it, and the four sides are reserved (Frame
acceptance criteria). A click cannot be injected there (no pointer device): what a click does is
tested on the nodes in ``test_ring.py``."""

from __future__ import annotations

import re
import signal
import subprocess
import time
from pathlib import Path

import pytest

from tests.shell_samples import HEADER
from tests.sway import PrivateSway
from tests.test_run import Shell
from tests.test_surfaces_live import workspace_rect

pytestmark = pytest.mark.tre

SETTINGS = "---\nTDL: 0.1\nName: S\n---\nSettings { Logging { Level: DEBUG } }\n"
OUT = (1280, 720)  # the headless output
BEHIND = (
    "Panel { Name: Behind, Layer: BOTTOM, Anchor: [TOP, LEFT], Width: 1280, Height: 720,"
    ' Style { Fill: "#ff00ff" } }'
)


def run_shell(sway: PrivateSway, cfg: Path, children: str, index: str = "0") -> Shell:
    shells = cfg / "Shells"
    shells.mkdir(parents=True, exist_ok=True)
    body = f"\nShell {{ Monitor {{ Name: Main, Index: {index}, Children {{ {children} }} }} }}\n"
    (shells / "Main_Shell.tdl").write_text(HEADER + body)
    (cfg / "settings.tdl").write_text(SETTINGS)
    shell = Shell(cfg, sway.env)
    shell.wait_for("running")
    return shell


def stop(shell: Shell) -> None:
    shell.process.send_signal(signal.SIGTERM)
    assert shell.finish() == 0
    assert "| ERROR " not in "".join(shell.seen)


def screenshot(sway: PrivateSway) -> tuple[int, int, bytes]:
    ppm = subprocess.run(
        ["grim", "-t", "ppm", "-"], env=sway.env, capture_output=True, check=True
    ).stdout
    _, size, _, pixels = ppm.split(b"\n", 3)
    width, height = map(int, size.split())
    return width, height, pixels


def pixel(shot: tuple[int, int, bytes], x: int, y: int) -> tuple[int, int, int]:
    width, _, pixels = shot
    i = (y * width + x) * 3
    return pixels[i], pixels[i + 1], pixels[i + 2]


def wait_rect(sway: PrivateSway, want: dict[str, int], timeout: float = 6) -> dict[str, int]:
    """The workspace rectangle once it matches ``want`` (sway applies a zone later)."""
    deadline = time.monotonic() + timeout
    rect = workspace_rect(sway)
    while any(rect[k] != v for k, v in want.items()) and time.monotonic() < deadline:
        time.sleep(0.05)
        rect = workspace_rect(sway)
    return rect


def usable(sway: PrivateSway, left: int, top: int, right: int, bottom: int) -> dict[str, int]:
    return wait_rect(
        sway,
        {"x": left, "y": top, "width": OUT[0] - left - right, "height": OUT[1] - top - bottom},
    )


RING = (
    "Frame { Name: F, Thickness: [10, 20, 30, 40], Margin: 5,"
    ' Outer_Border { Width: 1, Color: "#ff0000" }, Inner_Border { Width: 2, Color: "#00ff00" },'
    ' Style { Background: "#0000ff" } }'
)


def test_the_ring_is_drawn_at_the_edges_the_opening_shows_what_is_behind_and_sides_are_reserved(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    shell = run_shell(private_sway, tmp_path, f"{BEHIND}\n{RING}")
    try:
        # totals: thickness + margin 5 + outer border 1 + inner border 2
        want = (18, 28, 38, 48)
        rect = usable(private_sway, *want)
        assert (rect["x"], rect["y"]) == want[:2]
        assert (rect["width"], rect["height"]) == (OUT[0] - 18 - 38, OUT[1] - 28 - 48)
        time.sleep(0.5)
        shot = screenshot(private_sway)
        magenta, blue, red, green = (255, 0, 255), (0, 0, 255), (255, 0, 0), (0, 255, 0)
        y, x = OUT[1] // 2, OUT[0] // 2
        # left: margin 5 (what is behind shows), outer border 1, fill 10, inner border 2
        assert [pixel(shot, i, y) for i in (4, 5, 6, 15, 16, 17, 18)] == [
            magenta,
            red,
            blue,
            blue,
            green,
            green,
            magenta,
        ]
        # top: margin 5, border 1, fill 20, inner border 2
        assert [pixel(shot, x, i) for i in (4, 5, 6, 25, 26, 27, 28)] == [
            magenta,
            red,
            blue,
            blue,
            green,
            green,
            magenta,
        ]
        # right 30 and bottom 40 thick
        assert pixel(shot, OUT[0] - 1 - 5, y) == red and pixel(shot, OUT[0] - 1 - 35, y) == blue
        assert pixel(shot, OUT[0] - 1 - 36, y) == green
        assert pixel(shot, x, OUT[1] - 1 - 5) == red and pixel(shot, x, OUT[1] - 1 - 45) == blue
        assert pixel(shot, x, OUT[1] - 1 - 46) == green
        assert pixel(shot, x, y) == magenta  # the opening
        assert pixel(shot, 0, 0) == magenta  # the margin is transparent, the corner too
        stop(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()


@pytest.mark.parametrize(
    ("frame", "total"),
    [
        ('Thickness: 10, Inner_Border { Width: 2, Color: "#ffffff" }', 12),
        (
            'Thickness: 10, Inner_Border { Width: 2, Color: "#fff" }, '
            'Outer_Border { Width: 2, Color: "#fff" }',
            14,
        ),
        ('Thickness: 10, Margin: [5, 5, 5, 5], Inner_Border { Width: 2, Color: "#fff" }', 17),
    ],
)
def test_the_reserved_zone_is_thickness_plus_borders_plus_margin(
    private_sway: PrivateSway, tmp_path: Path, frame: str, total: int
) -> None:
    shell = run_shell(private_sway, tmp_path, f"Frame {{ Name: F, {frame} }}")
    try:
        rect = usable(private_sway, total, total, total, total)
        assert rect == {**rect, "x": total, "y": total, "width": OUT[0] - 2 * total}
        assert rect["height"] == OUT[1] - 2 * total
        stop(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()


def test_saving_a_new_thickness_changes_the_zones_and_the_ring_not_the_painter(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    shell = run_shell(private_sway, tmp_path, f"{BEHIND}\n{RING}")
    try:
        usable(private_sway, 18, 28, 38, 48)
        file = tmp_path / "Shells" / "Main_Shell.tdl"
        file.write_text(
            file.read_text()
            .replace("Thickness: [10, 20, 30, 40]", "Thickness: [10, 20, 0, 40]")
            .replace("Margin: 5", "Margin: 3")
        )
        # right has no thickness now: no reserver, the zone is released; the rest follows
        rect = usable(private_sway, 16, 26, 0, 46)
        assert (rect["x"], rect["y"], rect["width"]) == (16, 26, OUT[0] - 16)
        time.sleep(0.4)
        shot = screenshot(private_sway)
        assert pixel(shot, OUT[0] - 3, OUT[1] // 2) == (255, 0, 255)  # no band on the right
        assert pixel(shot, 3, OUT[1] // 2) == (255, 0, 0)  # margin 3, outer border from x = 3
        text = "".join(shell.seen)
        while not shell.lines.empty():
            text += shell.lines.get()
        assert len(re.findall(r"painter \d+x\d+, zones", text)) == 1  # the painter stayed
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if shell.process.poll() is None:
            shell.process.kill()


def test_two_monitors_each_have_a_frame_and_unplugging_one_closes_only_its_windows(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    import json

    def sway(*args: str) -> str:
        return subprocess.run(
            ["swaymsg", *args], env=private_sway.env, capture_output=True, text=True
        ).stdout

    def rects() -> dict[str, dict[str, int]]:
        return {w["output"]: w["rect"] for w in json.loads(sway("-t", "get_workspaces"))}

    def seen(shell: Shell, needle: str, timeout: float = 30) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            while not shell.lines.empty():
                shell.seen.append(shell.lines.get())
            if any(needle in line for line in shell.seen):
                return
            time.sleep(0.05)
        pytest.fail(f"never saw {needle!r}:\n{''.join(shell.seen)}")

    shell = run_shell(
        private_sway,
        tmp_path,
        'Frame { Name: F, Thickness: [10, 20, 30, 40], Style { Background: "#0000ff" } }',
        index="default",  # every output no other Monitor named
    )
    try:
        sway("create_output")
        seen(shell, "Frame F on HEADLESS-2: bottom reserver, zone 40")
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:  # sway applies a zone a little after the configure
            found = rects()
            second = found.get("HEADLESS-2")
            if second and (second["width"], second["height"]) == (1920 - 40, 1080 - 60):
                break
            time.sleep(0.05)
        second = rects()["HEADLESS-2"]
        assert (second["width"], second["height"]) == (1920 - 40, 1080 - 60)
        first = rects()["HEADLESS-1"]
        assert (first["width"], first["height"]) == (OUT[0] - 40, OUT[1] - 60)
        sway("output", "HEADLESS-2", "unplug")
        seen(shell, "Frame F on HEADLESS-2 painter closed")
        time.sleep(0.5)
        text = "".join(shell.seen)
        assert "Frame F on HEADLESS-1 painter closed" not in text  # the other monitor is left alone
        rect = usable(private_sway, 10, 20, 30, 40)
        assert (rect["x"], rect["y"]) == (10, 20)
        stop(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
