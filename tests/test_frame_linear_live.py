"""The Frame drawn in linear light (``Debug { Frame_Blend: LINEAR }``) on a private headless sway:
the compositor puts the shader's pixels over the desktop, so this is the width a 2 px border
really has on a curve there (the opening corner, measured on the screenshot as the headless tests
measure the snapshot), and the painter draws no frame once everything is still. A click cannot be
injected on that compositor (no pointer device): the hit shape is tested on the nodes in
``test_frame_linear.py``."""

from __future__ import annotations

import math
import time
from pathlib import Path

import pytest

from tess_shell.surfaces.join import JOINS
from tests.kwin.compare_join import live_run
from tests.shell_samples import HEADER
from tests.sway import PrivateSway
from tests.test_frame_linear import DARK, LIGHT, RING_AREA, luminance
from tests.test_frame_live import screenshot, stop
from tests.test_run import Shell

pytestmark = pytest.mark.tre

FRAME = (
    "Frame { Name: F, Thickness: 24, Inner_Radius: 14, "
    'Inner_Border { Width: 2, Color: "#89b4fa" }, Style { Background: "#1e1e2e" } }'
)
# the desktop the opening shows: the ring's own dark
BEHIND = (
    "Panel { Name: Behind, Layer: BOTTOM, Anchor: [TOP, LEFT], Width: 1920, Height: 1080,"
    ' Style { Fill: "#1e1e2e" } }'
)


def drawn(sway: PrivateSway, scale: float, timeout: float = 15) -> tuple[int, int, bytes]:
    """The screenshot once the ring is on it (its fill at x = 5, y = 300) and a moment later, so
    nothing is half drawn; the poll is generous because a loaded machine is slow."""
    deadline = time.monotonic() + timeout
    shot = screenshot(sway)
    while time.monotonic() < deadline:
        width, _, pixels = shot
        i = (round(300 * scale) * width + 5) * 3
        if all(abs(pixels[i + k] - DARK[k]) <= 2 for k in range(3)):
            time.sleep(0.5)
            return screenshot(sway)
        time.sleep(0.2)
        shot = screenshot(sway)
    pytest.fail("the ring was never drawn")


def border_width(sway: PrivateSway, cfg: Path, blend: str, scale: float) -> tuple[float, float]:
    """(a straight, the opening corner): the 2 px border's width as the sum of linear light over
    the compositor's screenshot (2.00 is exact)."""
    sway.msg("output", "*", "resolution", "1920x1080")
    sway.msg("output", "*", "scale", f"{scale:g}")
    time.sleep(0.4)
    (cfg / "Shells").mkdir(parents=True, exist_ok=True)
    body = f"\nShell {{ Monitor {{ Name: Main, Index: 0, Children {{ {BEHIND}\n{FRAME} }} }} }}\n"
    (cfg / "Shells" / "Main_Shell.tdl").write_text(HEADER + body)
    (cfg / "settings.tdl").write_text(
        "---\nTDL: 0.1\nName: S\n---\n"
        f"Settings {{ Logging {{ Level: DEBUG }} Debug {{ Frame_Blend: {blend} }} }}\n"
    )
    shell = Shell(cfg, sway.env)
    try:
        shell.wait_for("running")
        shell.wait_for("painter configured")
        width, _, pixels = drawn(sway, scale)
    finally:
        stop(shell)

    span = luminance(LIGHT) - luminance(DARK)

    def lit(x: int, y: int) -> float:
        i = (y * width + x) * 3
        return (luminance(tuple(pixels[i : i + 3])) - luminance(DARK)) / span

    lo, hi = round(24 * scale), round(40 * scale)
    corner = sum(lit(x, y) for y in range(lo, hi) for x in range(lo, hi)) / scale**2
    left, right = round(24 * scale), round(26 * scale)
    straight = sum(
        lit(x, y) for y in range(round(300 * scale), round(500 * scale)) for x in range(left, right)
    ) / (200 * scale**2)
    return straight, 2 * corner / RING_AREA


@pytest.mark.parametrize(("scale", "paths", "shader"), [(1.0, 1.72, 1.85), (1.5, 1.82, 1.90)])
def test_on_the_compositor_the_border_is_wider_on_a_curve_with_the_shader_than_with_paths(
    private_sway: PrivateSway, tmp_path: Path, scale: float, paths: float, shader: float
) -> None:
    """The compositor's own blend of the inner edge is sRGB, so the ring over a dark desktop reads
    about 1.88 (1x) and 1.93 (1.5x) of 2.00 with the shader, and 1.69 and 1.79 with paths: what the
    headless ``test_over_a_dark_desktop`` composites."""
    got = {}
    for blend in ("SRGB", "LINEAR"):
        straight, corner = border_width(private_sway, tmp_path / blend.lower(), blend, scale)
        assert straight == pytest.approx(2.0, abs=0.05), (blend, straight)
        got[blend] = corner
    assert not math.isnan(got["SRGB"])
    assert got["SRGB"] < paths and got["LINEAR"] > shader, got
    assert got["LINEAR"] < 2.03, got


def test_sliding_a_body_with_the_shader_ring_draws_frames_and_nothing_once_still(
    private_sway: PrivateSway,
) -> None:
    results = live_run(
        ["PARAM"], private_sway.output_names()[0], 1.0, private_sway.env, 0.7, "LINEAR"
    )
    assert [r["join"] for r in results] == ["PARAM"] and results[0]["blend"] == "LINEAR"
    r = results[0]
    assert r["frames"] >= 15, f"the slide drew {r['frames']} frames"
    assert r["idle_frames"] == 0, f"{r['idle_frames']} frames drawn at idle"
    assert "PARAM" in JOINS


def test_a_saved_change_of_colour_repaints_the_shader_ring_though_nothing_else_changes(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    """A change of uniforms alone draws no frame in a window that is still: the ring writes to its
    node as well, so the hot reload shows (the ring's colour at x = 5, then its new one)."""
    private_sway.msg("output", "*", "resolution", "1920x1080")
    private_sway.msg("output", "*", "scale", "1")
    time.sleep(0.4)
    shells = tmp_path / "Shells"
    shells.mkdir(parents=True)

    def save(background: str) -> None:
        frame = FRAME.replace("#1e1e2e", background)
        body = (
            f"\nShell {{ Monitor {{ Name: Main, Index: 0, Children {{ {BEHIND}\n{frame} }} }} }}\n"
        )
        (shells / "Main_Shell.tdl").write_text(HEADER + body)

    save("#1e1e2e")
    (tmp_path / "settings.tdl").write_text(
        "---\nTDL: 0.1\nName: S\n---\n"
        "Settings { Logging { Level: DEBUG } Debug { Frame_Blend: LINEAR } }\n"
    )
    shell = Shell(tmp_path, private_sway.env)
    try:
        shell.wait_for("running")
        shell.wait_for("painter configured")
        width, _, pixels = drawn(private_sway, 1.0)
        assert tuple(pixels[(300 * width + 5) * 3 :][:3]) == (0x1E, 0x1E, 0x2E)
        save("#336699")
        shell.wait_for("reloaded")
        deadline = time.monotonic() + 5
        got: tuple[int, ...] = ()
        while time.monotonic() < deadline:
            time.sleep(0.2)
            width, _, pixels = screenshot(private_sway)
            got = tuple(pixels[(300 * width + 5) * 3 :][:3])
            if got == (0x33, 0x66, 0x99):
                break
        assert got == (0x33, 0x66, 0x99), got
    finally:
        stop(shell)
