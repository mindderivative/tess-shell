"""Spike B: each join is its own small closed path, morphed with path ``data`` (not collected).

The ring is drawn without the body. The body is a rounded box that slides out of the band edge
(``translate_y``, clipped at the edge). Each join is a closed single-subpath piece (the corner
square minus a quarter disc) overlapping the band by 1 px, morphed from a tiny collapsed copy of
itself to the full fillet with ``animate("data", ...)``. tre resamples both contours by length
(96 points a subpath), so a small closed shape should resample smoothly where a whole ring does not.
``--live`` prints the frame cost on a compositor.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import spike_join_common as c  # noqa: E402


def piece(cx: float, top: float, r: float, left: bool) -> str:
    """The fillet of radius ``r`` at the band edge ``top``, beside a body side at ``cx``: the
    square r x r between the edge and the side, less the quarter disc; one closed subpath that
    starts 1 px inside the band."""
    s = -1 if left else 1  # the side the piece lies on
    ox = cx + s * r
    sweep = 0 if left else 1
    return (
        f"M{ox:g},{top - 1:g} L{cx:g},{top - 1:g} L{cx:g},{top + r:g} "
        f"A{r:g},{r:g} 0 0 {sweep} {ox:g},{top:g} Z"
    )


top = c.BAND
full_l, full_r = piece(c.BX0, top, c.JOIN, True), piece(c.BX1, top, c.JOIN, False)
tiny_l, tiny_r = piece(c.BX0, top, 0.5, True), piece(c.BX1, top, 0.5, False)

w = c.painter()
w.root.add_child(
    w.create(
        "path",
        data=c.ring_without_body(),
        fill=c.FILL,
        position="absolute",
        left=0,
        top=0,
        width=c.W,
        height=c.H,
    )
)
pieces = [
    w.create(
        "path", data=tiny, fill=c.FILL, position="absolute", left=0, top=0, width=c.W, height=c.H
    )
    for tiny in (tiny_l, tiny_r)
]
clip = w.create(
    "box",
    position="absolute",
    left=c.BX0,
    top=top,
    width=c.BX1 - c.BX0,
    height=c.DEPTH,
    clip_children=True,
)
body = w.create(
    "box",
    position="absolute",
    left=0,
    top=0,
    width=c.BX1 - c.BX0,
    height=c.DEPTH,
    fill=c.FILL,
    corner_radius=(0, 0, c.OWN, c.OWN),
)
clip.add_child(body)
for p in pieces:
    w.root.add_child(p)
w.root.add_child(clip)


def play(forward: bool, done: Callable[[], None] | None = None) -> None:
    body.animate("translate_y", 0.0 if forward else -c.DEPTH, c.MS, c.EASING)
    for p, full, tiny in zip(pieces, (full_l, full_r), (tiny_l, tiny_r), strict=True):
        p.animate("data", full if forward else tiny, c.MS, c.EASING, done)


if c.LIVE:

    def loop(forward: bool = True) -> None:
        play(forward, lambda: loop(not forward))

    body.set(translate_y=-c.DEPTH)
    c.run_live(w, "B pieces morphed", loop)
else:
    body.set(translate_y=-c.DEPTH)
    w.snapshot()
    play(True)
    c.advance_to(w, c.FRAMES, lambda n, t: c.save(w, "b", n))
    c.verdict("b", "pieces are resampled polygons (96 points); see the frames for chamfers")
