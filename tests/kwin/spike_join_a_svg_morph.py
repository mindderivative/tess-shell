"""Spike A: the join as part of ONE contour, morphed by SMIL in an ``svg`` node (not collected).

The ring's contour is written at depth 0 and at full depth with the *same commands* (lines and
cubic Beziers, a degenerate cubic where a fillet has radius 0), so ``<animate attributeName="d"
values="d0;d1">`` interpolates every control point linearly: the body grows out of the band edge
and its fillets grow with it. tre samples it by ``svg_time`` (``node.animate("svg_time", ...)``,
eased in the engine, no Python per frame). Needs the shell's pure contour builder
(``tess_shell.surfaces.ring``). ``--live`` prints the frame cost on a compositor.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import spike_join_common as c  # noqa: E402

from tess_shell.surfaces.ring import MeldSpec, RingSpec, ring  # noqa: E402

shaped = ring(
    RingSpec(
        thickness=(c.BAND,) * 4,  # type: ignore[arg-type]
        inner_radius=(c.JOIN,) * 4,  # type: ignore[arg-type]
        melds=(MeldSpec("top", c.BX1 - c.BX0, c.DEPTH, "CENTER", (c.OWN,) * 4),),  # type: ignore[arg-type]
    ),
    (c.W, c.H),
)
assert shaped.morph is not None
d0, _ = shaped.morph({0: 0.0})
d1, _ = shaped.morph({0: 1.0})
DOC = (
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{c.W}" height="{c.H}" viewBox="0 0 {c.W} {c.H}">'
    f'<path fill="rgb(30,30,46)" d="{d0}"><animate attributeName="d" values="{d0};{d1}" dur="1s" '
    'fill="freeze"/></path></svg>'
)

w = c.painter()
node = w.create(
    "svg", svg=DOC, position="absolute", left=0, top=0, width=c.W, height=c.H, hit_testable=False
)
w.root.add_child(node)

if c.LIVE:

    def loop(forward: bool = True) -> None:
        node.animate("svg_time", 1.0 if forward else 0.0, c.MS, c.EASING, lambda: loop(not forward))

    c.run_live(w, "A svg morph", loop)
else:
    node.set(svg_time=0.0)
    w.snapshot()
    node.animate("svg_time", 1.0, c.MS, c.EASING)
    c.advance_to(w, c.FRAMES, lambda n, t: c.save(w, "a", n))
    c.verdict(
        "a",
        "fillets grow with the body; corners are cubic curves; one node; svg takes no hit shape",
    )
