"""Spike C: the joins as masked boxes grown with ``scale``, the body with ``corner_radius``
(not collected).

tre has no transform origin: ``scale`` is about the node's centre, so each join piece (a box of
the ring colour, masked to the fillet shape) is translated as it scales to keep its corner on the
band edge. The body is a box whose bottom corner radius is animated from 0 to its own with
``animate("corner_radius", ...)`` while it slides out. ``--live`` prints the frame cost.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import spike_join_common as c  # noqa: E402

top, r = c.BAND, c.JOIN


def mask_for(left: bool) -> dict[str, object]:
    """The fillet in its own r x r box: the corner square less the quarter disc. The left join is
    solid at the box's top right (the disc's centre is the bottom left), the right join at its top
    left (the centre is the bottom right)."""
    if left:
        d = f"M0,0 L{r},0 L{r},{r} A{r},{r} 0 0 0 0,0 Z"
    else:
        d = f"M0,0 L{r},0 A{r},{r} 0 0 0 0,{r} Z"
    return {"path": d, "view_box": (0, 0, r, r)}


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
spots = ((c.BX0 - r, top, True), (c.BX1, top, False))  # (x of the box, y, left join?)
joins = []
for x, y, left in spots:
    j = w.create(
        "box",
        position="absolute",
        left=x,
        top=y - 1,
        width=r,
        height=r + 1,
        fill=c.FILL,
        mask=mask_for(left),
        scale=0.05,
    )
    w.root.add_child(j)
    joins.append((j, left))
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
    corner_radius=(0, 0, 0, 0),
)
clip.add_child(body)
w.root.add_child(clip)


def play(forward: bool, done: Callable[[], None] | None = None) -> None:
    s = 1.0 if forward else 0.05
    body.animate("translate_y", 0.0 if forward else -c.DEPTH, c.MS, c.EASING)
    body.animate("corner_radius", (0, 0, c.OWN, c.OWN) if forward else (0, 0, 0, 0), c.MS, c.EASING)
    for k, (j, left) in enumerate(joins):
        # scale about the centre: keep the corner on the band edge and beside the body side
        dx = (r / 2) * (1 - s) * (1 if left else -1)
        dy = -(r / 2) * (1 - s)
        j.animate("scale", s, c.MS, c.EASING, done if k == 0 else None)
        j.animate("translate_x", dx, c.MS, c.EASING)
        j.animate("translate_y", dy, c.MS, c.EASING)


body.set(translate_y=-c.DEPTH)
if c.LIVE:

    def loop(forward: bool = True) -> None:
        play(forward, lambda: loop(not forward))

    c.run_live(w, "C scaled pieces", loop)
else:
    w.snapshot()
    play(True)
    c.advance_to(w, c.FRAMES, lambda n, t: c.save(w, "c", n))
    c.verdict(
        "c", "masked boxes scaled about their centre; the mask is a hard edge (see the frames)"
    )
