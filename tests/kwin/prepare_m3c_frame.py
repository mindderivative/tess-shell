"""Regenerate the M3c Frame measurement and KWin checklist setup in /tmp/tess-kwin-m3c (not
collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m3c_frame.py``. It writes scripts and a
scratch config under ``/tmp/tess-kwin-m3c`` and starts nothing:

* ``measure.sh [args]``: the C1 measurement (``tests/kwin/measure_frame.py``), the painter and the
  four reservers alone on one output, with their memory, idle CPU and idle frames;
* ``frame/``: a shell config with a Frame on each monitor (HDMI-A-1 and DP-1), and the scripts
  ``run-frame.sh``, ``check-frame.sh`` and the toggles ``toggle-hdmi.sh`` and ``toggle-dp.sh``
  (each writes one of four prepared files, so running it twice goes back);
* ``checklist.txt``: the lines to check by eye, with the numbers this setup should show.

Nothing here touches what the other ``prepare_*.py`` scripts write, and the state directory is
``/tmp/tess-kwin-m3c/state``, never the real one.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tess_shell.surfaces.ring import RingSpec, totals  # noqa: E402
from tests.shell_samples import HEADER, SVG  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m3c")
BIN = Path.home() / "Projects/pyDev/pyEnvs/tess-shell/bin"
SETTINGS = "---\nTDL: 0.1\nName: Settings\n---\nSettings {\n  Logging { Level: DEBUG }\n}\n"


def four(n: float) -> tuple[float, float, float, float]:
    return n, n, n, n


HDMI = {
    # thickness 10, margin 5, a 2 px inner border: every side reserves 17 (Frame > Acceptance)
    "a": (
        "Frame {\n"
        "                Name: Main_Frame\n"
        "                Thickness: 10\n"
        "                Margin: 5\n"
        "                Inner_Radius: 14\n"
        '                Inner_Border { Width: 2, Color: "#89b4fa" }\n'
        '                Style { Background: "#1e1e2e" }\n'
        "            }",
        RingSpec(four(10), four(5), four(0), four(14), 0, 2),
    ),
    # a thick bottom, rounded outer corners, both borders
    "b": (
        "Frame {\n"
        "                Name: Main_Frame\n"
        "                Thickness { Left: 12, Top: 12, Right: 12, Bottom: 40 }\n"
        "                Corner_Radius: 24\n"
        "                Inner_Radius: 18\n"
        '                Outer_Border { Width: 1, Color: "#ffffff55" }\n'
        '                Inner_Border { Width: 2, Color: "#f38ba8" }\n'
        '                Style { Background: "#313244" }\n'
        "            }",
        RingSpec((12, 12, 12, 40), four(0), four(24), four(18), 1, 2),
    ),
}
DP = {
    # a different Frame on the second monitor: thin, square, no borders
    "a": (
        "Frame {\n"
        "                Name: Second_Frame\n"
        "                Thickness: 6\n"
        "                Inner_Radius: 10\n"
        '                Style { Background: "#a6e3a1" }\n'
        "            }",
        RingSpec(four(6), four(0), four(0), four(10), 0, 0),
    ),
    # no Frame: only the first monitor has one (a monitor with no Frame gets none)
    "b": ("", None),
}


def shell_text(hdmi: str, dp: str) -> str:
    second = (
        f"""
    Monitor {{
        Name: Second
        Connector: "DP-1"
        Children {{
            {DP[dp][0]}
        }}
    }}"""
        if DP[dp][0]
        else ""
    )
    return (
        HEADER
        + f"""
Shell {{
    Monitor {{
        Name: Main
        Connector: "HDMI-A-1"
        Children {{
            {HDMI[hdmi][0]}
        }}
    }}{second}
}}
"""
    )


def script(name: str, text: str) -> None:
    path = ROOT / name
    path.write_text("#!/usr/bin/env bash\n" + text)
    path.chmod(0o755)


def checklist() -> str:
    main_a = totals(HDMI["a"][1])
    main_b = totals(HDMI["b"][1])
    dp = totals(DP["a"][1] or RingSpec())
    return f"""M3c Frame: KWin checklist (HDMI-A-1 above, DP-1 below)

Setup: uv run python tests/kwin/prepare_m3c_frame.py   (already done if you read this)
  /tmp/tess-kwin-m3c/measure.sh              the C1 measurement (see below)
  /tmp/tess-kwin-m3c/run-frame.sh            run the shell with the Frames (Ctrl+C stops it)
  /tmp/tess-kwin-m3c/toggle-hdmi.sh          HDMI-A-1: Frame A <-> Frame B (a saved edit: hot reload)
  /tmp/tess-kwin-m3c/toggle-dp.sh            DP-1: Frame present <-> none
  /tmp/tess-kwin-m3c/check-frame.sh          the file is valid
Send the newest file in /tmp/tess-kwin-m3c/frame/logs/ if anything below is off.
Every zone is added to the Plasma panel's on the same edge (KWin orders them): note which edge
has the panel; the Frame is drawn inside it or the panel must be hidden on that monitor.

C1: the cost (run first, from a terminal; the figures go in G8)
  1. measure.sh --output=HDMI-A-1        painter + four reservers.  Send the printed block.
  2. measure.sh --output=HDMI-A-1 --only=painter       and again with --only=reservers.
  Each run prints RSS, peak and Pss before and with the windows open, the video memory, the CPU
  time in 5 s idle and the frames drawn in 3 s idle (it should be 0).  Then it stays open:
  maximise a window; it must stop inside the ring on all four sides.

Frame A on HDMI-A-1 (the first state; sizes in px)
  [ ] a ring of colour #1e1e2e with a blue (#89b4fa) 2 px line on its inside, rounded inner corners
      (radius 14), square outer corners at a 5 px transparent margin: the desktop shows in the
      margin and in the opening.
  [ ] a maximised window stops {main_a[0]} px from the left, {main_a[1]} from the top, {main_a[2]} from the
      right, {main_a[3]} from the bottom (10 + 5 margin + 2 border = 17 on every side).
  [ ] a click on the ring is taken by the shell (nothing under it reacts); a click in the opening
      reaches the window or the desktop under it, also in the rounded corners of the opening
      (3 px or more inside the opening).
  [ ] a window dragged over the ring is tucked under it (the Frame is on the Top layer).
Toggle HDMI (Frame B)
  [ ] after toggle-hdmi.sh the ring changes within about a second, with one reflow of the windows:
      12 px left/top/right and 40 px at the bottom; rounded screen corners (radius 24) cut off;
      a maximised window stops at {main_b[0]}, {main_b[1]}, {main_b[2]}, {main_b[3]} px (12 + 1 + 2 = 15,
      40 + 1 + 2 = 43).
  [ ] the corners: the screen corners are transparent and a click there reaches what is under.
  [ ] toggle-hdmi.sh again returns to Frame A; a maximised window follows.
DP-1
  [ ] DP-1 has its own thin green Frame; {dp[0]} px reserved on every side (6).  Nothing is drawn
      between the monitors.
  [ ] toggle-dp.sh removes it: DP-1's windows get the whole monitor; again, it returns.
Stop (Ctrl+C)
  [ ] every ring and every zone is gone at once.

Known and not tested here: a fullscreen window should hide the Frame (not built yet), the
position of the Frame with fractional scale, and melded Panels and strips (not built).
"""


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    cfg = ROOT / "frame"
    shutil.rmtree(cfg, ignore_errors=True)
    (cfg / "Shells").mkdir(parents=True)
    (cfg / "variants").mkdir()
    (cfg / "Shells" / "dot.svg").write_text(SVG)
    (cfg / "settings.tdl").write_text(SETTINGS)
    for h in HDMI:
        for d in DP:
            (cfg / "variants" / f"{h}_{d}.tdl").write_text(shell_text(h, d))
    (ROOT / "state").mkdir(exist_ok=True)
    state = ROOT / "state-flags"
    state.mkdir(exist_ok=True)
    (state / "hdmi").write_text("a")
    (state / "dp").write_text("a")
    shutil.copy(cfg / "variants" / "a_a.tdl", cfg / "Shells" / "Main_Shell.tdl")
    flags = "/tmp/tess-kwin-m3c/state-flags"
    apply = (
        f"h=$(cat {flags}/hdmi); d=$(cat {flags}/dp)\n"
        f'cp /tmp/tess-kwin-m3c/frame/variants/"$h"_"$d".tdl '
        "/tmp/tess-kwin-m3c/frame/Shells/Main_Shell.tdl\n"
        'echo "HDMI-A-1: Frame $h, DP-1: Frame $d"\n'
    )
    script(
        "toggle-hdmi.sh",
        f'h=$(cat {flags}/hdmi)\nif [ "$h" = a ]; then echo b > {flags}/hdmi; '
        f"else echo a > {flags}/hdmi; fi\n" + apply,
    )
    script(
        "toggle-dp.sh",
        f'd=$(cat {flags}/dp)\nif [ "$d" = a ]; then echo b > {flags}/dp; '
        f"else echo a > {flags}/dp; fi\n" + apply,
    )
    script(
        "run-frame.sh",
        "# The Frames on both monitors.  Usage: run-frame.sh   (Ctrl+C stops it)\n"
        "export XDG_STATE_HOME=/tmp/tess-kwin-m3c/state\n"
        f"exec {BIN}/tesserae-shell run --config-dir /tmp/tess-kwin-m3c/frame\n",
    )
    script(
        "check-frame.sh",
        "export XDG_STATE_HOME=/tmp/tess-kwin-m3c/state\n"
        f"{BIN}/tesserae-shell check --config-dir /tmp/tess-kwin-m3c/frame\n",
    )
    script(
        "measure.sh",
        "# C1: what the Frame costs.  Usage: measure.sh [--output=HDMI-A-1] [--only=painter|reservers]\n"
        "#     [--thickness=24] [--auto] (Ctrl+C stops it)\n"
        f"cd {REPO}\n"
        "unset VIRTUAL_ENV\n"
        "export UV_PROJECT_ENVIRONMENT=$HOME/Projects/pyDev/pyEnvs/tess-shell\n"
        'exec uv run python tests/kwin/measure_frame.py "$@"\n',
    )
    (ROOT / "checklist.txt").write_text(checklist())
    print(f"wrote {ROOT} (read checklist.txt)")


if __name__ == "__main__":
    main()
