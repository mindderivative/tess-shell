"""A node changed in window B during a callback of window A is not drawn (tess_re 0.6.1; TRE-REQ-012).

Not collected by pytest; it uses only ``tess_re``. It needs a Wayland compositor with layer-shell
(KWin, sway). Run ``python repro_cross_window_redraw.py``.

It opens two layer surfaces: A, a bar, and B, a card. A timer of A changes B's card (its fill
between two opaque colours) once every 1.5 s, six times with a plain ``set`` and then six times
with a ``set`` followed by ``LoopHandle.call_soon(lambda: None)``. B's ``frame`` events are
timestamped; at the end the script prints, for each change, the time to B's next frame.

Expected: a few ms in both cases (a surface draws when something changed). Seen on tess_re 0.6.1 on
KWin 6.8.2 and on sway: after the plain ``set`` B draws only at the next unrelated wake of the loop,
which here is the next change 1.5 s later (about 1500 ms, the last one never); after
``set`` plus ``call_soon`` B draws in 1 to 3 ms.
"""

from __future__ import annotations

import time

import tess_re

TRIALS = 6  # per variant
GAP_MS = 1500

app = tess_re.App()
handle = app.thread_handle()

a = tess_re.LayerWindow("repro.a", layer="top", anchor=("top", "left", "right"), size=(0, 32))
a.root.set(fill=(30, 30, 40, 255))
b = tess_re.LayerWindow(
    "repro.b",
    layer="overlay",
    anchor=("top", "left"),
    size=(200, 100),
    margin=(60, 0, 0, 20),
    keyboard="none",
    input_region=[],
)
card = b.create("box", width=200, height=100, fill=(200, 60, 60, 255), corner_radius=10)
b.root.add_child(card)

frames: list[float] = []  # when B drew
changes: list[tuple[str, float]] = []  # (variant, when B was changed)
b.on("frame", lambda _e: frames.append(time.monotonic()))
colours = [(200, 60, 60, 255), (60, 90, 200, 255)]


def change(variant: str, n: int) -> None:
    changes.append((variant, time.monotonic()))
    card.set(fill=colours[n % 2])  # a change to B, made in a callback of A's timer
    if variant == "set+call_soon":
        handle.call_soon(lambda: None)


for i in range(TRIALS * 2):
    variant = "set" if i < TRIALS else "set+call_soon"
    a.after(1000 + i * GAP_MS, lambda v=variant, n=i: change(v, n))  # type: ignore[misc]


def report() -> None:
    print(f"tess_re on {time.strftime('%H:%M:%S')}: ms from each change to B's next frame")
    for variant in ("set", "set+call_soon"):
        delays = []
        for v, t0 in changes:
            if v == variant:
                nxt = next((f for f in frames if f >= t0), None)
                delays.append("never" if nxt is None else f"{(nxt - t0) * 1000:.0f}")
        print(f"  {variant:14} {', '.join(delays)}")
    handle.stop()


a.after(1000 + TRIALS * 2 * GAP_MS + 500, report)
app.add_window(a)
app.add_window(b)
app.run(keep_alive=True)
