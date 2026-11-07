"""Repro (not collected by pytest): a ``stroke`` on a box with a concave corner strokes the whole
box, not the concave arc, so a join fillet cannot take its border from the box's own stroke.

    uv run python tests/kwin/repro_concave_stroke.py

A 16 x 16 fillet under a band (concave bottom-left corner, radius 16) with a 2 px green stroke:
the stroke is drawn along the arc AND along the box's top and right edges (the others are cut
away). The border of a join runs along the arc only (the other edges are against the band and the body), so the shell
(``surfaces/join_concave.py``) draws the border as a second, larger fillet box under the fill box
instead; its thickness along the arc then follows the scale of the boxes, not a fixed width.
Wanted (a request, not a defect): a stroke that follows only the concave corners, or a per-side
border, so the border of a fillet can be a stroke of fixed width.
"""

from __future__ import annotations

import tess_re

window = tess_re.LayerWindow(
    "repro.concave",
    layer="top",
    anchor=("top", "right", "bottom", "left"),
    size=(60, 40),
    exclusive_zone=-1,
    keyboard="none",
    input_region=[],
)
band = window.create(
    "box", position="absolute", left=0, top=0, width=60, height=8, fill=(0, 0, 255, 255)
)
fillet = window.create(
    "box",
    position="absolute",
    left=10,
    top=8,
    width=16,
    height=16,
    fill=(0, 0, 255, 255),
    corner_radius=(0, 0, 0, 16),
    corner_style=("round", "round", "round", "concave"),
    stroke_color=(0, 255, 0, 255),
    stroke_width=2,
)
window.root.add_child(band)
window.root.add_child(fillet)
rgba, width, _ = window.snapshot()


def green(x: int, y: int) -> bool:
    i = (y * width + x) * 4
    return rgba[i + 1] > 200 and rgba[i + 2] < 100


# the fillet box is x 10..26, y 8..24; its concave corner is bottom left, so the arc runs from
# (10, 8) to (26, 24) through the middle of the box; the left and bottom edges are cut away
print("stroke along the right edge (x 24, y 16):", green(24, 16))
print("stroke along the top edge (x 18, y 9):", green(18, 9))
print("expected for a border of the arc only: False, False")
