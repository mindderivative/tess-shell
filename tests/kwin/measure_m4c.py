"""Frames drawn by the M4c widgets at rest on a private sway (not collected by pytest): the gallery
(Buttons, Toggles, Checkboxes, Sliders, a List) and, once a Menu with two levels of submenu has
opened, the Panels and the three Popups.

    env -u WAYLAND_DISPLAY -u DISPLAY uv run python tests/kwin/measure_m4c.py

It writes the gallery and a module that opens the menus from a timer into a scratch directory, starts
a private sway and the shell on it, and prints the frames each window drew in 3 s at rest.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.kwin import prepare_m4c_gallery as gallery  # noqa: E402
from tests.sway import PrivateSway  # noqa: E402

AUTO_TDL = """---
TDL: 0.1
Name: Auto
---
Module {
    Params { Popup_Name { Type: string, Default: "" }  At { Type: number, Default: 1 } }
    FlexBox { Name: Root, Height: 8, Children { Text { Text: "", Width: AUTO, Height: AUTO } } }
}
"""
AUTO_PY = """from tess_shell import Module


class Auto(Module):
    def start(self):
        self.n = 0
        self.ctx.on_tick("second", self.tick)

    def tick(self):
        self.n += 1
        for use in self.ctx.uses.values():
            if self.n == use.params["At"]:
                self.ctx.popup(use.params["Popup_Name"], data={"Title": "File"}, use=use)
"""

# runs in the shell's process: wraps the surface manager so each window reports its frame count
CHILD = """
import sys
import tess_shell.surfaces.manager as M
from tess_shell.cli import main

orig = M.SurfaceManager.build


def build(self):
    out = orig(self)

    def report(label):
        windows = [(s.name, s.window) for s in self.surfaces if s.window is not None]
        windows += [(op.popup.name, op.window) for op in self.popups.chain()]
        for name, window in windows:
            print(f"MEASURE {label} {name}: {window.frame_stats(reset=True)['frames']}", flush=True)

    first = self.surfaces[0].window
    first.after(3000, lambda: report("settle"))
    first.after(6000, lambda: report("3 s, nothing open"))
    first.after(8000, lambda: report("settle after the menus opened"))
    first.after(11000, lambda: report("3 s with the menu and its submenus open"))
    return out


M.SurfaceManager.build = build
sys.exit(main(["run", "--config-dir", sys.argv[1]]))
"""


def main() -> None:
    work = Path(tempfile.mkdtemp(prefix="m4c-measure-"))
    cfg = work / "gallery"
    gallery.write_gallery(cfg)
    shell = cfg / "Shells" / "Main_Shell.tdl"
    text = shell.read_text()
    text = text.replace(
        "Probe { } } } } }",
        "Probe { } Auto { Name: A0, Popup_Name: File_Menu, At: 7 } } } } }",
        1,
    )
    text = text.replace(
        'MenuItem { Text: "Share", Submenu: Share_Menu }',
        "Auto { Name: A1, Popup_Name: Share_Menu, At: 8 } "
        'MenuItem { Text: "Share", Submenu: Share_Menu }',
        1,
    )
    text = text.replace(
        'MenuItem { Text: "More", Submenu: More_Menu }',
        "Auto { Name: A2, Popup_Name: More_Menu, At: 9 } "
        'MenuItem { Text: "More", Submenu: More_Menu }',
        1,
    )
    shell.write_text(text)
    folder = cfg / "Modules" / "Auto"
    folder.mkdir(parents=True)
    (folder / "Auto_Module.tdl").write_text(AUTO_TDL)
    (folder / "Auto_Module.py").write_text(AUTO_PY)
    sway = PrivateSway().start()
    try:
        env = dict(sway.env)
        env.setdefault("PYTHONPATH", str(REPO / "src"))
        proc = subprocess.Popen(
            [sys.executable, "-c", CHILD, str(cfg)],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        time.sleep(15)
        proc.terminate()
        out = proc.communicate(timeout=15)[0]
        print("\n".join(line for line in out.splitlines() if line.startswith("MEASURE")))
    finally:
        sway.stop()


if __name__ == "__main__":
    os.environ.pop("WAYLAND_DISPLAY", None)
    main()
