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


def start(sway: PrivateSway, cfg: Path, panels: str, hide: str | None = None) -> Shell:
    body = BODY.replace("            Bar {", f"            {panels}\n            Bar {{", 1)
    write_example(cfg, body)
    if hide is not None:
        (cfg / "settings.tdl").write_text(
            "---\nTDL: 0.1\nName: S\n---\n"
            f"Settings {{ Logging {{ Level: DEBUG }} Debug {{ Panel_Hide: {hide} }} }}\n"
        )
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
        assert "Volume_OSD on HEADLESS-1: anchor bottom size (282, 82) zone -1" in text
        assert "Volume_OSD on HEADLESS-1 configured 282x82" in text
        shell.wait_for("Panel Volume_OSD on HEADLESS-1 hidden")
        opened = next(x for x in shell.seen if "Volume_OSD on HEADLESS-1: anchor" in x)
        hidden = next(x for x in shell.seen if "Volume_OSD on HEADLESS-1 hidden" in x)
        assert 0.35 < stamp(hidden) - stamp(opened) < 1.5  # about Hide_After (400 ms)
        finish(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()


def test_a_panel_with_visible_false_keeps_a_mapped_empty_surface_by_default(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    shell = start(private_sway, tmp_path, LAUNCHER)
    try:
        shell.wait_for("Panel Launcher on HEADLESS-1 configured 600x400")
        shell.wait_for("running")
        assert "anchor none size (600, 400) zone -1 (hidden, surface kept)" in "".join(shell.seen)
        time.sleep(0.3)
        finish(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
    assert "| ERROR " not in "".join(shell.seen)


def test_with_panel_hide_close_a_visible_false_panel_has_no_surface_at_all(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    shell = start(private_sway, tmp_path, LAUNCHER, hide="CLOSE")
    try:
        shell.wait_for("Panel Launcher on HEADLESS-1")
        shell.wait_for("running")
        text = "".join(shell.seen)
        assert "Panel Launcher on HEADLESS-1: anchor none (hidden)" in text
        assert "Panel Launcher on HEADLESS-1 configured" not in text  # no surface was made
        time.sleep(0.3)
        finish(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
    assert "| ERROR " not in "".join(shell.seen)


SCRIPT = """
import sys
from pathlib import Path
import tess_re
from tess_shell.appearance import Appearance
from tess_shell.config.settings import load_settings
from tess_shell.model.store import ValueStore
from tess_shell.scanner import build_look, scan
from tess_shell.surfaces.manager import SurfaceManager

cfg = Path(sys.argv[1])
settings, _ = load_settings(cfg)
result = scan(settings, cfg)
app = tess_re.App()
handle = app.thread_handle()
manager = SurfaceManager(
    app,
    {},
    lambda key: key,
    ValueStore(),
    build_look(result, settings, Appearance()),
    hide_mode=sys.argv[2],
)
manager.plan(next(iter(result.shells.values())))
manager.build()
bar = next(s for s in manager.surfaces if s.name == "Top_Bar")
panel = next(s for s in manager.surfaces if s.name == "Launcher")
assert (panel.window is None) == (sys.argv[2] == 'CLOSE')
bar.window.after(300, lambda: manager.show(panel))
bar.window.after(900, lambda: manager.hide(panel))
bar.window.after(1500, lambda: manager.show(panel))
bar.window.after(2300, handle.stop)
app.run(keep_alive=True)
"""


def run_script(sway: PrivateSway, cfg: Path, mode: str) -> str:
    import subprocess
    import sys

    body = BODY.replace("            Bar {", f"            {LAUNCHER}\n            Bar {{", 1)
    write_example(cfg, body)
    done = subprocess.run(
        [sys.executable, "-c", SCRIPT, str(cfg), mode],
        env=sway.env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert done.returncode == 0, done.stderr
    return done.stderr


def test_close_mode_makes_a_new_window_each_time_a_panel_is_shown_on_a_real_compositor(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    log = run_script(private_sway, tmp_path / "cfg", "CLOSE")
    assert log.count("Panel Launcher on HEADLESS-1 shown (window created)") == 2
    assert log.count("Panel Launcher on HEADLESS-1 hidden (window closed)") == 1
    assert log.count("Panel Launcher on HEADLESS-1 configured 600x400") == 2  # a new surface each
    assert log.count("Panel Launcher on HEADLESS-1: a frame") >= 2  # and each one drew


def test_keep_mode_draws_a_frame_after_every_show_and_hide(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    """The default route (D44). The shell's wake is what makes the frame follow a change made
    from another window's callback (TRE-REQ-012); without it this fails on KWin and on sway."""
    import re

    log = run_script(private_sway, tmp_path / "cfg", "KEEP")
    assert log.count("Launcher on HEADLESS-1 shown (surface kept)") == 2
    assert log.count("Launcher on HEADLESS-1 hidden (surface kept)") == 1
    assert log.count("Launcher on HEADLESS-1 configured 600x400") == 1  # one surface throughout
    for label in ("shown", "hidden"):
        delays = [int(m) for m in re.findall(rf"a frame (\d+) ms after it was {label}", log)]
        assert delays, f"no frame was drawn after it was {label}:\n{log}"
        assert max(delays) < 100, f"{label}: a frame only after {delays} ms"


def _rect_of(ppm: bytes, colour: tuple[int, int, int]) -> tuple[int, int, int, int] | None:
    """The bounding box (x0, y0, x1, y1) of the pixels of ``colour`` in a binary PPM."""
    _, size, _, pixels = ppm.split(b"\n", 3)
    width, height = map(int, size.split())
    hits = [
        (i % width, i // width)
        for i in range(width * height)
        if tuple(pixels[i * 3 : i * 3 + 3]) == colour
    ]
    if not hits:
        return None
    xs, ys = [h[0] for h in hits], [h[1] for h in hits]
    return min(xs), min(ys), max(xs), max(ys)


ATTACHED = (
    "Panel { Name: Menu, Layer: OVERLAY, Width: 100, Height: 50, Attach_To: Top_Bar, "
    'Attach: BOTTOM, Gap: 10, Alignment: START, Style { Fill: "#ff0000" } }\n'
    "Panel { Name: Side, Layer: OVERLAY, Width: 40, Height: 30, Attach_To: Menu, Attach: RIGHT, "
    'Gap: 6, Alignment: END, Style { Fill: "#00ff00" } }'
)


def test_an_attached_panel_lands_on_the_pixels_its_geometry_names(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    import subprocess

    shell = start(private_sway, tmp_path, ATTACHED)
    try:
        shell.wait_for("Panel Side on HEADLESS-1 configured")
        shell.wait_for("Panel Menu on HEADLESS-1 configured")
        shell.wait_for("running")
        time.sleep(0.6)
        shot = subprocess.run(
            ["grim", "-t", "ppm", "-"], env=private_sway.env, capture_output=True, check=True
        ).stdout
        # the Bar is 32 high at the top; the Menu is 10 below it, flush left, 100 x 50
        assert _rect_of(shot, (255, 0, 0)) == (0, 42, 99, 91)
        # the Side Panel is 6 right of the Menu, its bottom on the Menu's (END): 40 x 30
        assert _rect_of(shot, (0, 255, 0)) == (106, 62, 145, 91)
        finish(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
    assert "| ERROR " not in "".join(shell.seen)


TILE_TDL = (
    "---\nTDL: 0.1\nName: Tile\n---\n"
    'Module { Rectangle { Width: 60, Height: 20, Fill: "#0000ff" } }\n'
)
TILE_PY = "from tess_shell import Module\n\n\nclass Tile(Module):\n    pass\n"
UNDER_TILE = (
    "Panel { Name: Under, Layer: OVERLAY, Width: 40, Height: 30, Attach_To: Tile_One, "
    'Attach: BOTTOM, Gap: 10, Alignment: END, Style { Fill: "#ff0000" } }'
)


def test_a_panel_attached_to_a_module_follows_the_module_and_clears_the_bar(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    import subprocess

    folder = tmp_path / "Modules" / "Tile"
    folder.mkdir(parents=True)
    (folder / "Tile_Module.tdl").write_text(TILE_TDL)
    (folder / "Tile_Module.py").write_text(TILE_PY)
    body = BODY.replace(
        'Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }',
        "Tile { Name: Tile_One }",
    ).replace("            Bar {", f"            {UNDER_TILE}\n            Bar {{", 1)
    write_example(tmp_path, body)
    shell = Shell(tmp_path, private_sway.env)
    try:
        shell.wait_for("Panel Under on HEADLESS-1 configured")
        shell.wait_for("running")
        time.sleep(0.8)  # the Panel is placed again once the Bar has been laid out and drawn
        shot = subprocess.run(
            ["grim", "-t", "ppm", "-"], env=private_sway.env, capture_output=True, check=True
        ).stdout
        tile = _rect_of(shot, (0, 0, 255))
        assert tile is not None
        x0, y0, x1, _ = tile
        assert (x1 - x0 + 1, y0) == (60, 4)  # 60 wide, 4 below the Bar's top (its Padding)
        # END along the module (its right edge, 40 wide); the Bar's bottom edge (32) + Gap 10,
        # not the module's bottom (26) + Gap 10
        assert _rect_of(shot, (255, 0, 0)) == (x1 - 39, 42, x1, 71)
        finish(shell)
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
    assert "| ERROR " not in "".join(shell.seen)
