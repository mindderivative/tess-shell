"""A throwaway tre-only client for the M5g kit (not the shell; not collected by pytest): opens one
ordinary window for each title on the command line (``python window_probe.py "Kit One" "Kit Two"``)
and keeps them open. Lines on standard input steer it: ``fullscreen N`` and ``windowed N`` switch
the N-th window (from 0), ``title N TEXT`` retitles it, ``close N`` closes it. It ends when the last window is closed, or on
SIGTERM. It runs in the private KWin of the kit's step and nowhere else."""

from __future__ import annotations

import os
import sys
import threading

import tess_re

from tess_shell.signals import SignalWatcher

app = tess_re.App()
handle = app.thread_handle()
windows: list[tess_re.Window] = []


def on_close_requested() -> None:
    """The compositor asked the window to close (KWin's closeWindow): end the probe, which is how
    a one-window application closes (tre 0.6.8's ``Window.close`` does not unmap the window)."""
    handle.call_soon(handle.stop)


for title in sys.argv[1:]:
    window = tess_re.Window(320, 200, title)
    window.root.set(fill=(40, 60, 90, 255))
    window.on("close_requested", lambda _event: on_close_requested())
    app.add_window(window)
    windows.append(window)
print("windows open:", len(windows), flush=True)


def steer() -> None:
    for line in sys.stdin:
        word = line.split(maxsplit=2)
        if len(word) < 2 or not word[1].isdigit() or int(word[1]) >= len(windows):
            continue
        window = windows[int(word[1])]
        if word[0] == "fullscreen":
            handle.call_soon(lambda w=window: w.set(fullscreen=True))
        elif word[0] == "windowed":
            handle.call_soon(lambda w=window: w.set(fullscreen=False))
        elif word[0] == "title" and len(word) == 3:
            text = word[2].strip()
            handle.call_soon(lambda w=window, t=text: w.set(title=t))
        elif word[0] == "close":
            handle.call_soon(handle.stop)


threading.Thread(target=steer, daemon=True).start()


def force() -> None:
    os._exit(130)


watcher = SignalWatcher(handle.stop, force)
watcher.start()
try:
    app.run()
finally:
    watcher.close()
