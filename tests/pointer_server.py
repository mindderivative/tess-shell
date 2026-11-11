"""The helper process of ``tests/live_pointer.py`` (not collected by pytest): a persistent wlroots
virtual pointer on the compositor ``WAYLAND_DISPLAY`` names, driven by lines on stdin
(``move X Y W H``, ``down``, ``up``, ``click``, ``quit``; each answered by ``done``). It runs in a
Python that has ``pywayland`` and takes tre's own ``tests/wlr_pointer.py`` (which generates the
protocol bindings) from the directory in ``TRE_TESTS``."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.environ["TRE_TESTS"])
import wlr_pointer  # type: ignore[import-not-found]  # noqa: E402

pointer = wlr_pointer.Pointer(dict(os.environ))
print("ready", flush=True)
for line in sys.stdin:
    word = line.split()
    if not word:
        continue
    if word[0] == "move":
        pointer.move(*(int(v) for v in word[1:5]))
    elif word[0] == "down":
        pointer.press()
    elif word[0] == "up":
        pointer.release()
    elif word[0] == "click":
        pointer.click()
    elif word[0] == "quit":
        break
    print("done", flush=True)
os._exit(0)
