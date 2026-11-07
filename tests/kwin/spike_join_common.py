"""Shared scene and helpers of the join-animation spikes ``spike_join_*.py`` (not collected by
pytest; tess_re only, plus the shell's pure contour builders for the one spike that needs them).

The scene: a 400 x 300 painter, a Frame ring 20 px thick with a 14 px inner radius, and a body of
100 x 40 px growing out of the top band, centred, whose bottom corners have radius 8. Each spike
animates the body out of the band edge with its two joins (the concave fillets where the body
meets the band) and writes frames at t = 0, 0.25, 0.5, 0.75 and 1 to ``/tmp/frame-review/`` as
``spike_<name>_<n>.png`` (straight-alpha RGBA, a transparent opening), and prints the cost of a
frame when run with ``--live`` on a compositor (``frame_stats()['recent']`` while it loops).
"""

from __future__ import annotations

import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import tess_re
import tess_re.snapshot as snapshot

W, H = 400, 300
BAND = 20
JOIN = 14  # the inner radius, which is the radius of each join
BX0, BX1, DEPTH, OWN = 150, 250, 40, 8  # the body: x range, depth below the band, own corner radius
FILL = (30, 30, 46, 255)
OUT = Path("/tmp/frame-review")
MS = 400  # the duration of the animation
EASING = (0.4, 0.0, 0.2, 1.0)
FRAMES = (0.0, 0.25, 0.5, 0.75, 1.0)
LIVE = "--live" in sys.argv


def painter() -> Any:
    """A headless painter-sized layer window (a real one with ``--live``)."""
    return tess_re.LayerWindow(
        "spike.join",
        layer="top",
        anchor=("top", "right", "bottom", "left"),
        size=(0, 0) if LIVE else (W, H),
        exclusive_zone=-1,
        keyboard="none",
        input_region="auto" if LIVE else [],
    )


def ring_without_body() -> str:
    """The ring as one contour: the outer rectangle clockwise, the rounded opening the other way
    (so the non-zero fill leaves it open)."""
    x0, y0, x1, y1, r = BAND, BAND, W - BAND, H - BAND, JOIN
    return (
        f"M0,0 L{W},0 L{W},{H} L0,{H} Z "
        f"M{x0 + r},{y0} A{r},{r} 0 0 0 {x0},{y0 + r} L{x0},{y1 - r} A{r},{r} 0 0 0 {x0 + r},{y1} "
        f"L{x1 - r},{y1} A{r},{r} 0 0 0 {x1},{y1 - r} L{x1},{y0 + r} A{r},{r} 0 0 0 {x1 - r},{y0} Z"
    )


def advance_to(
    window: Any, steps: tuple[float, ...], on_frame: Callable[[int, float], None]
) -> None:
    """Advance a headless window through fractions of ``MS`` and call ``on_frame(n, t)``."""
    done = 0.0
    for n, t in enumerate(steps):
        window.advance(max(int(round((t - done) * MS)), 0))
        done = t
        on_frame(n, t)


def save(window: Any, name: str, n: int) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    rgba, w, h = window.snapshot()
    (OUT / f"spike_{name}_{n}.png").write_bytes(snapshot.png_bytes(rgba, w, h))


def run_live(window: Any, name: str, start: Callable[[], None], seconds: float = 3.0) -> None:
    """Open ``window`` on the compositor, loop ``start`` (which must re-arm itself on completion
    through ``loop``) for ``seconds`` and print the frame cost."""
    app = tess_re.App()
    handle = app.thread_handle()
    app.add_window(window)
    def kick() -> None:
        start()
        handle.call_soon(lambda: None)  # wake tre's loop (TRE-REQ-012: fixed in tre 0.6.2)

    window.after(500, kick)

    def report() -> None:
        recent = window.frame_stats()["recent"]
        print(
            f"{name}: {recent['count']} frames, cpu_ms mean {recent['cpu_ms']['mean']:.2f} "
            f"p95 {recent['cpu_ms']['p95']:.2f}, total_ms mean {recent['total_ms']['mean']:.1f}",
            flush=True,
        )
        handle.stop()

    window.after(500 + int(seconds * 1000), report)
    app.run(keep_alive=True)


def verdict(name: str, text: str) -> None:
    print(f"{name}: {text}  (frames: {OUT}/spike_{name}_0..4.png)")


def clock() -> float:
    return time.monotonic()
