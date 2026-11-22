"""A throwaway tre-only client (not the shell; not collected by pytest): in the private KWin of
``tests/test_kwin_clipboard.py`` it selects part of a selectable Text and runs the shell's own
``copy_selection`` on a window of ``Window`` type, then prints one JSON line: what ``copy_selection``
returned, what the window reads back from the clipboard, and what tre's ``write_clipboard`` said."""

from __future__ import annotations

import json
import sys
import time
from types import SimpleNamespace

import tess_re

from tess_shell.surfaces.selection_copy import copy_selection

app = tess_re.App()
handle = app.thread_handle()
window = tess_re.LayerWindow(
    "probe-clip", layer="top", anchor=("top", "left"), size=(300, 60), keyboard="on_demand"
)
text = window.create("text", text="hello clipboard world", selectable=True)
window.root.add_child(text)
app.add_window(window)
result: dict[str, object] = {}


def run() -> None:
    text.set(selection=(6, 15))  # "clipboard"
    result["selected"] = str(text.get("selection"))
    result["copied"] = copy_selection(window, SimpleNamespace(key="c", ctrl=True))
    time.sleep(0.2)
    result["read_back"] = window.read_clipboard()
    print(json.dumps(result), flush=True)
    handle.call_soon(handle.stop)


window.after(1000, run)
window.after(15000, lambda: (print(json.dumps({"timeout": True}), flush=True), handle.stop()))
sys.setswitchinterval(0.005)
app.run()
