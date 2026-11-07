"""Animating a path's ``data`` between two contours with different structure resamples both by
length: a ring with a notch into the same ring (not collected by pytest; tess_re only).

What happens (tesserae-engine 0.6.1, checked 2026-11-07): the moment ``animate("data", ...)`` is
set, ``get("data")`` is a polygon of ``MORPH_SAMPLES`` points per subpath (96 per subpath; every
corner of the notch is chamfered by the sampling, even at t = 0, before anything has moved), and
mid-animation the notch does not shrink: because the points are matched by arc length, every
point after the notch is shifted along the contour, so the notch smears across the top edge.

What is wanted instead: either a morph that follows the commands of two paths with the same
structure (lines, cubics, arcs: interpolate the control points, as SVG SMIL does in an ``svg`` node
for ``d``), or at least that t = 0 is exactly the source path (no resampling until it moves).

Run: ``uv run python tests/kwin/repro_path_morph_resample.py``; it prints the numbers and writes
``/tmp/frame-review/repro_morph_{source,0,50,100}.png`` (straight-alpha RGBA, 400 x 300).
"""

from __future__ import annotations

from pathlib import Path

import tess_re
import tess_re.snapshot as snapshot

W, H = 400, 300
OUT = Path("/tmp/frame-review")
# the opening is wound the other way, so the non-zero fill leaves it open
WITH_NOTCH = (
    "M0,0 L400,0 L400,300 L0,300 Z "
    "M36,280 L364,280 A16,16 0 0 0 380,264 L380,36 A16,16 0 0 0 364,20 L266,20 A16,16 0 0 0 250,36 "
    "L250,54 A6,6 0 0 1 244,60 L156,60 A6,6 0 0 1 150,54 L150,36 A16,16 0 0 0 134,20 L36,20 "
    "A16,16 0 0 0 20,36 L20,264 A16,16 0 0 0 36,280 Z"
)
PLAIN = (
    "M0,0 L400,0 L400,300 L0,300 Z "
    "M36,280 L364,280 A16,16 0 0 0 380,264 L380,36 A16,16 0 0 0 364,20 L36,20 "
    "A16,16 0 0 0 20,36 L20,264 A16,16 0 0 0 36,280 Z"
)


def window(data: str) -> tuple[tess_re.LayerWindow, tess_re.Node]:
    w = tess_re.LayerWindow(
        "repro.morph", layer="top", anchor=("top", "left"), size=(W, H), exclusive_zone=-1
    )
    node = w.create(
        "path",
        data=data,
        fill=(30, 30, 46, 255),
        position="absolute",
        left=0,
        top=0,
        width=W,
        height=H,
    )
    w.root.add_child(node)
    return w, node


def pixels(w: tess_re.LayerWindow) -> bytes:
    rgba, _, _ = w.snapshot()
    return bytes(rgba)


def save(w: tess_re.LayerWindow, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rgba, width, height = w.snapshot()
    (OUT / f"repro_morph_{name}.png").write_bytes(snapshot.png_bytes(rgba, width, height))


def differing(a: bytes, b: bytes) -> int:
    return sum(1 for i in range(0, len(a), 4) if a[i : i + 4] != b[i : i + 4])


source_w, _ = window(WITH_NOTCH)
source = pixels(source_w)
save(source_w, "source")

w, node = window(WITH_NOTCH)
w.snapshot()
node.animate("data", PLAIN, 1000, "linear")
w.advance(0)
t0 = pixels(w)
print(f"t=0: data has {node.get('data').count('L')} line segments (the source has 19 commands)")
print(f"t=0: {differing(source, t0)} pixels differ from the source path, which has not moved")
save(w, "0")
w.advance(500)
save(w, "50")
mid = pixels(w)
w.advance(500)
save(w, "100")
end = pixels(w)
plain_w, _ = window(PLAIN)
print(f"t=1: {differing(pixels(plain_w), end)} pixels differ from the target (it is exact)")


def run_from_top(image: bytes, x: int) -> int:
    """Filled rows from the top edge down the column ``x``."""
    y = 0
    while y < H and image[(y * W + x) * 4 + 3] > 128:
        y += 1
    return y


# the band is 20 px; the notch is the body, 40 px deep: 60 rows at t=0, 20 at t=1, so a morph that
# moved the notch's floor evenly would give 40 at t=0.5 (and no filled row beside the body)
print(
    f"column x=200: {run_from_top(source, 200)} filled rows in the source, "
    f"{run_from_top(t0, 200)} at t=0, {run_from_top(mid, 200)} at t=0.5 (40 expected), "
    f"{run_from_top(end, 200)} at t=1"
)
print(f"column x=100 (beside the notch): {run_from_top(mid, 100)} rows at t=0.5 (20 expected)")
print(f"frames written to {OUT}/repro_morph_*.png")
