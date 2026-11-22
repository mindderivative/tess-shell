"""A throwaway tre-only client (not the shell; not collected by pytest): in the private KWin of
``tests/test_kwin_popup_fade.py`` it opens a layer surface, opens a GRABBING popup beside it, fades
the popup out and closes its window when the fade ends (what the shell's Popup ``Animation: FADE``
does), and prints one JSON line of what it saw: when the popup was asked to close, when its fade
ended, when tre said ``closed``, and the ``active`` (keyboard) events of both windows."""

from __future__ import annotations

import json
import sys
import time

import tess_re

FADE_MS = int(sys.argv[1]) if len(sys.argv) > 1 else 200
t0 = time.monotonic()
events: list[list[object]] = []


def mark(what: str) -> None:
    events.append([what, round((time.monotonic() - t0) * 1000)])


app = tess_re.App()
handle = app.thread_handle()
parent = tess_re.LayerWindow(
    "probe-fade", layer="top", anchor=("top", "left"), size=(300, 60), keyboard="on_demand"
)
parent.root.set(fill=(40, 60, 90, 255))
parent.on("active", lambda e: mark(f"parent active={bool(e.active)}"))
app.add_window(parent)
popup: list[tess_re.PopupWindow] = []


def open_popup() -> None:
    win = tess_re.PopupWindow(
        parent,
        size=(160, 80),
        anchor_rect=(10, 10, 50, 40),
        anchor="bottom_left",
        gravity="bottom_right",
        grab=True,
    )
    win.root.set(fill=(200, 80, 80, 255))
    win.on("active", lambda e: mark(f"popup active={bool(e.active)}"))
    win.on("closed", lambda e: mark(f"popup closed reason={getattr(e, 'reason', '')}"))
    app.add_window(win)
    popup.append(win)
    mark("popup opened")
    parent.after(700, fade_out)


def fade_out() -> None:
    mark("fade out asked")
    win = popup[0]

    def shut() -> None:
        mark("fade ended, window.close()")
        win.close()
        parent.after(600, finish)

    win.root.animate("opacity", 0.0, FADE_MS, (0.4, 0.0, 1.0, 1.0), shut)


def finish() -> None:
    mark("done")
    print(json.dumps(events), flush=True)
    handle.call_soon(handle.stop)


parent.after(800, open_popup)
parent.after(15000, finish)  # never hang
app.run()
