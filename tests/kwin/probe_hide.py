"""Which way of hiding a layer surface still repaints when it is shown? (D44; not collected by pytest)

Run it on KWin: ``tests/kwin/probe_hide.py`` (the generator writes ``/tmp/tess-kwin-m3b/probe-hide.sh``).
A row of buttons at the top toggles six cards in the middle of the screen, one method each. After
every toggle the card logs how long its first frame took, or that none came within 500 ms. A method
that shows ``no frame`` is not repainted after the toggle. ``--auto`` toggles every card by itself
(for a private compositor, where no pointer exists); ``--only=<method>`` runs one method alone.

The methods, hide then show:

* ``visible``: the root node not visible, then visible (the shell's first route).
* ``resize``: the same, and showing nudges the surface's size by 1 px and back, a resize-paced
  frame that tre presents without waiting for the compositor's frame callback.
* ``tiny``: hiding makes the surface 1 by 1 px and showing restores its size.
* ``alpha``: the card stays drawn at 1/255 opacity instead of vanishing.
* ``alphawake``: ``alpha`` plus ``call_soon`` after the change (does a wake draw it?).
* ``alphasoon``: ``alpha`` with the change made inside a ``call_soon`` callback.
* ``wake``: the first route plus ``call_soon`` after showing (does a wake draw a frame?).
* ``close``: the window is closed and a new one made (the shell's primary route).
"""

from __future__ import annotations

import sys
import time
from typing import Any

import tess_re

AUTO = "--auto" in sys.argv
ONLY = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--only=")), None)
W, H = 240, 120
METHODS = tuple(
    m
    for m in ("visible", "resize", "tiny", "alpha", "alphawake", "alphasoon", "wake", "close")
    if ONLY in (None, m)
)
COLOURS = [(200, 70, 70, 255), (70, 160, 90, 255), (70, 110, 200, 255), (200, 160, 60, 255)]

app = tess_re.App()
handle = app.thread_handle()


def say(text: str) -> None:
    print(f"{time.strftime('%H:%M:%S')}.{int(time.time() * 1000) % 1000:03d} {text}", flush=True)


class Card:
    def __init__(self, index: int, method: str) -> None:
        self.index, self.method = index, method
        self.colour = COLOURS[index % len(COLOURS)]
        self.shown = True
        self.t0 = 0.0
        self.waiting = ""
        self.window = self.make()
        self.timer = None

    def make(self) -> Any:
        col, row = self.index % 3, self.index // 3
        window = tess_re.LayerWindow(
            f"probe.{self.method}",
            layer="overlay",
            anchor=("top", "left"),
            size=(W, H),
            margin=(120 + row * (H + 24), 0, 0, 40 + col * (W + 24)),
            keyboard="none",
            input_region=[],
        )
        self.card = window.create(
            "box", width=W, height=H, fill=self.colour, corner_radius=12, padding=12
        )
        self.card.add_child(
            window.create(
                "text",
                text=self.method,
                font_size=22,
                fill=(255, 255, 255, 255),
                width="fit-content",
            )
        )
        window.root.add_child(self.card)
        window.on("frame", self.on_frame)
        return window

    def on_frame(self, _event: Any) -> None:
        if self.waiting:
            say(
                f"{self.method:8} {self.waiting}: a frame {(time.monotonic() - self.t0) * 1000:.0f} ms later"
            )
            self.waiting = ""

    def command(self, label: str) -> None:
        self.t0, self.waiting = time.monotonic(), label
        method = self.method

        def check() -> None:
            if self.waiting == label:
                say(f"{method:8} {label}: NO FRAME within 500 ms")
                self.waiting = ""

        self.window.after(500, check)

    def toggle(self) -> None:
        on = not self.shown
        self.shown = on
        label = "shown" if on else "hidden"
        m = self.method
        if m == "close" and on:
            self.window = self.make()
            app.add_window(self.window)
            self.command(label)
            return
        self.command(label)
        w = self.window
        if m in ("visible", "wake"):
            w.root.set(visible=on)
            if on and m == "wake":
                handle.call_soon(lambda: None)
        elif m == "resize":
            w.root.set(visible=on)
            if on:
                w.set(size=(W, H + 1))
                w.after(40, lambda: w.set(size=(W, H)))
        elif m == "tiny":
            w.set(size=(W, H) if on else (1, 1))
            w.root.set(visible=on)
        elif m == "alpha":
            self.card.set(fill=self.colour if on else (*self.colour[:3], 1))
        elif m == "alphawake":
            self.card.set(fill=self.colour if on else (*self.colour[:3], 1))
            handle.call_soon(lambda: None)
        elif m == "alphasoon":
            fill = self.colour if on else (*self.colour[:3], 1)
            handle.call_soon(lambda: self.card.set(fill=fill))
        elif m == "close":
            w.close()


cards = [Card(i, m) for i, m in enumerate(METHODS)]

controls = tess_re.LayerWindow(
    "probe.controls",
    layer="overlay",
    anchor=("top", "left"),
    size=(len(METHODS) * 100 + 20, 60),
    margin=(40, 0, 0, 40),
    keyboard="none",
)
bar = controls.create(
    "box",
    display="flex",
    flex_direction="horizontal",
    gap=8,
    padding=8,
    fill=(30, 30, 40, 255),
    corner_radius=10,
    width=len(METHODS) * 100 + 20,
    height=60,
)
for card in cards:
    button = controls.create(
        "box",
        width=92,
        height=44,
        fill=(80, 90, 120, 255),
        corner_radius=8,
        align_items="center",
        justify_content="center",
    )
    button.add_child(
        controls.create(
            "text", text=card.method, font_size=14, fill=(255, 255, 255, 255), width="fit-content"
        )
    )
    button.on("click", lambda _e, c=card: c.toggle())
    bar.add_child(button)
controls.root.add_child(bar)

app.add_window(controls)
for card in cards:
    app.add_window(card.window)

if AUTO:
    for round_ in range(2):
        for i, card in enumerate(cards):
            controls.after(1000 + round_ * 4000 + i * 600, card.toggle)  # hide, then
            controls.after(3000 + round_ * 4000 + i * 600, card.toggle)  # show
    controls.after(9500, handle.stop)

# the event loop blocks the main thread in the engine, so Ctrl+C needs the shell's signal watcher
from tess_shell.signals import SignalWatcher  # noqa: E402


def force() -> None:
    import os

    os._exit(130)


watcher = SignalWatcher(handle.stop, force)  # type: ignore[arg-type]
watcher.start()
say("click a method's button to hide its card, again to show it; Ctrl+C to stop")
try:
    app.run(keep_alive=True)
finally:
    watcher.close()
say("stopped")
