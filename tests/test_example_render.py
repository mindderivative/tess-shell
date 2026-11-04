"""The M1 example, schema to binder to pixels, on a headless layer window (no compositor)."""

from __future__ import annotations

import tess_dl
from tess_re import LayerWindow

from tess_shell.binder.build import build
from tess_shell.schema.shell import read_shell
from tess_shell.surfaces.manager import _bar_fill
from tests.shell_samples import BODY, HEADER, SVG


def render() -> tuple[list[tuple[int, int, int, int]], int]:
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
    rgba, width, _ = window.snapshot()
    pixels = [tuple(rgba[i : i + 4]) for i in range(0, len(rgba), 4)]
    return pixels, width  # type: ignore[return-value]


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
