"""The M1 example, schema to binder to pixels, on a headless layer window (no compositor)."""

from __future__ import annotations

import os
from pathlib import Path

import tess_dl
from tess_re import LayerWindow

from tess_shell.binder.build import build
from tess_shell.schema.shell import read_shell
from tess_shell.surfaces.manager import _bar_fill
from tests import png
from tests.shell_samples import BODY, HEADER, SVG


def snapshot() -> tuple[bytes, int, int]:
    result = tess_dl.parse(HEADER + BODY, path="Shells/Main_Shell.tdl")
    assert result.document is not None
    shell, findings = read_shell(result.document, "Shells/Main_Shell.tdl", lambda _: SVG)
    assert shell is not None and findings == []
    bar = shell.monitors[0].surfaces[0]
    window = LayerWindow(
        "tesserae-shell.bar.Top_Bar", anchor=("top", "left", "right"), size=(0, 32)
    )
    window.resize(400, 32)
    fill = _bar_fill(dict(bar.style))
    assert fill == (0x1F, 0x1F, 0x1F, 255)
    window.root.set(fill=fill)
    build(list(bar.children), window)
    rgba, width, height = window.snapshot()
    return bytes(rgba), width, height


def render() -> tuple[list[tuple[int, int, int, int]], int]:
    rgba, width, _ = snapshot()
    pixels = [(rgba[i], rgba[i + 1], rgba[i + 2], rgba[i + 3]) for i in range(0, len(rgba), 4)]
    return pixels, width


def test_the_bar_shows_its_content_as_written() -> None:
    pixels, width = render()
    rows = [pixels[y * width : (y + 1) * width] for y in range(len(pixels) // width)]
    background = (0x1F, 0x1F, 0x1F, 255)
    assert rows[0][width // 2] == background

    def lit(pred: object) -> list[int]:
        return [x for x in range(width) if any(pred(row[x]) for row in rows)]  # type: ignore[operator]

    white = lit(lambda p: p[0] > 200 and p[1] > 200 and p[2] > 200)
    blue = lit(lambda p: p[2] > 200 and p[0] < 200)
    assert white and max(white) < width // 4  # the clock text sits at the left
    assert blue and min(blue) > width // 2  # the spacer pushed the icon and circle to the right
    black = lit(lambda p: p[0] < 8 and p[1] < 8 and p[2] < 8)
    assert black == []  # the SVG takes its colour from Color, not the default black


REFERENCE = Path(__file__).parent / "snapshots" / "m1_example.png"


def test_the_example_matches_the_reference_image() -> None:
    """One reference image of the example (M1 Brief, T10). Regenerate on purpose with
    ``UPDATE_SNAPSHOTS=1`` and look at the new picture before committing it."""
    rgba, width, height = snapshot()
    if os.environ.get("UPDATE_SNAPSHOTS"):
        REFERENCE.parent.mkdir(exist_ok=True)
        REFERENCE.write_bytes(png.encode(rgba, width, height))
    expected, ewidth, eheight = png.decode(REFERENCE.read_bytes())
    assert (width, height) == (ewidth, eheight)
    # Anti-aliasing may differ a little between engine builds: a channel may move by 16 on at
    # most 2 % of the pixels; a moved or missing element changes far more than that.
    off = sum(
        1
        for i in range(0, len(rgba), 4)
        if max(abs(rgba[i + c] - expected[i + c]) for c in range(4)) > 16
    )
    assert off <= width * height * 0.02, f"{off} of {width * height} pixels differ"
