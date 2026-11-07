"""Regenerate the M3c Frame strips and melded Panel KWin checklist setup in /tmp/tess-kwin-m3c/strips
(not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m3c_strips.py``. It writes a scratch
config and scripts under ``/tmp/tess-kwin-m3c`` and starts nothing. It does not touch what
``prepare_m3c_frame.py`` writes (the Frame ring checklist, ``measure.sh``).

* ``run-strips.sh``: run the shell: one Frame on HDMI-A-1 with a top strip (menu buttons that
  open Popups, a Clock), a left strip (coloured blocks and a button that toggles the Panel) and a
  Panel melded into the bottom of the Frame.
* ``toggle-strips.sh``: switch the saved shell file between variant A and B (a hot reload).
* ``check-strips.sh``: the file is valid.
* ``checklist-strips.txt``: the lines to check by eye, with the numbers this setup should show.

The state directory is ``/tmp/tess-kwin-m3c/state``, never the real one.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tess_shell.surfaces.ring import MeldSpec, RingSpec, ring  # noqa: E402
from tests.kwin.prepare_m3b_popups import BUTTON_PY, BUTTON_TDL, POPUPS, button  # noqa: E402
from tests.shell_samples import HEADER, SVG  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m3c")
CFG = ROOT / "strips"
BIN = Path.home() / "Projects/pyDev/pyEnvs/tess-shell/bin"
SETTINGS = (
    "---\nTDL: 0.1\nName: Settings\n---\nSettings {\n  Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default] }\n}\n"
)

TOP_CHILDREN = "\n".join(
    [
        button("Strip_Menu", "Menu", "Menu"),
        button("Strip_Tall", "Tall", "Tall"),
        button("Strip_Hint", "Hover me", "Menu", ", Tooltip: Hint"),
        'Clock { Name: Strip_Clock, format: "%H:%M" }',
        "Spacer { }",
        button("Strip_End", "Right edge", "Menu_End"),
    ]
)


def left_children() -> str:
    block = 'Rectangle {{ Name: {n}, Width: 16, Height: 40, Fill: "{c}", Corner_Radius: 3 }}'
    toggle = (
        "FlexBox { Name: Dock_Toggle, Width: 32, Height: 22, Padding: 3, "
        'Style { Background: "#89b4fa", Corner_Radius: 4 }, '
        "On_Click { Action: Toggle, Target: Dock }, Children { "
        'Text { Text: "Dock", Width: AUTO, Height: AUTO, Font_Size: 11, Foreground: "#1e1e2e" } } }'
    )
    return "\n".join(
        [
            block.format(n="Left_A", c="#f38ba8"),
            block.format(n="Left_B", c="#a6e3a1"),
            block.format(n="Left_C", c="#f9e2af"),
            toggle,
        ]
    )


def dock(side: str, alignment: str) -> str:
    return (
        f"Panel {{ Name: Dock, Meld: true, Attach_To: Screen_Frame, Attach: {side}, "
        f"Alignment: {alignment}, Length: 320, Depth: 56, Style {{ Corner_Radius: 12 }}, "
        "Children { FlexBox { Padding: 8, Spacing: 8, Children { "
        'Text { Text: "Docked: part of the frame", Font_Size: 14, Foreground: "#cdd6f4" } '
        "} } } }"
    )


def frame(variant: str) -> tuple[str, RingSpec]:
    if variant == "a":
        thick, pad, top_t, side = (40, 34, 8, 8), "[8, 3, 8, 3]", 34, ("BOTTOM", "CENTER")
        border = 2
    else:
        thick, pad, top_t, side = (48, 44, 8, 8), "[12, 6, 12, 6]", 44, ("RIGHT", "START")
        border = 3
    text = f"""            Frame {{
                Name: Screen_Frame
                Thickness {{ Left: {thick[0]}, Top: {thick[1]}, Right: {thick[2]}, Bottom: {thick[3]} }}
                Inner_Radius: 14
                Inner_Border {{ Width: {border}, Color: "#89b4fa" }}
                Padding: {pad}
                Style {{ Background: "#1e1e2e" }}
                Edges {{
                    Top {{
                        Thickness: {top_t}
                        Children {{
                            FlexBox {{
                                Width: 100%, Height: 100%, Spacing: 8
                                Children {{
{TOP_CHILDREN}
                                }}
                            }}
                        }}
                    }}
                    Left {{
                        Padding: 4
                        Children {{
                            FlexBox {{
                                Flex: VERTICAL, Width: 100%, Spacing: 6, Align_Items: CENTER
                                Children {{
{left_children()}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
            {dock(*side)}"""
    across = side[0] in ("BOTTOM", "TOP")  # the side runs along x: Length is the width
    meld = MeldSpec(
        side[0].lower(), 320 if across else 56, 56 if across else 320, side[1], (12, 12, 12, 12)
    )
    spec = RingSpec(
        thickness=(thick[0], top_t, thick[2], thick[3]),
        inner_radius=(14, 14, 14, 14),
        inner_border=border,
        melds=(meld,),
    )
    return text, spec


def shell_text(variant: str) -> str:
    return (
        HEADER
        + f"""
Shell {{
    Monitor {{
        Name: Main
        Connector: "HDMI-A-1"
        Children {{
{POPUPS}{frame(variant)[0]}
        }}
    }}
}}
"""
    )


def script(name: str, text: str) -> None:
    path = ROOT / name
    path.write_text("#!/usr/bin/env bash\n" + text)
    path.chmod(0o755)


def checklist() -> str:
    a, b = ring(frame("a")[1], (1920, 1080)), ring(frame("b")[1], (1920, 1080))
    return f"""M3c Frame strips and a melded Panel: KWin checklist (HDMI-A-1)

Setup: uv run python tests/kwin/prepare_m3c_strips.py   (already done if you read this)
  /tmp/tess-kwin-m3c/run-strips.sh      run the shell with the Frame (Ctrl+C stops it)
  /tmp/tess-kwin-m3c/toggle-strips.sh   variant A <-> B (a saved edit: hot reload)
  /tmp/tess-kwin-m3c/check-strips.sh    the file is valid
Send the newest file in /tmp/tess-kwin-m3c/strips/logs/ if anything below is off.
Cost: /tmp/tess-kwin-m3c/measure.sh --output=HDMI-A-1 --only=painter --melds=0|4|8
      (what the one-contour path and its input region cost; send the printed block)

Variant A (thickness left 40, top 34, right 8, bottom 8, a 2 px blue inner border)
  [ ] a maximised window stops {a.totals[0]} px from the left, {a.totals[1]} from the top, {a.totals[2]} from the
      right and {a.totals[3]} from the bottom (thickness + the 2 px border).
  [ ] the top strip runs the full width, corners included, and holds Menu, Tall, Hover me, a
      clock, then Right edge at the far right; the left strip runs between the top and the
      bottom band and stacks three coloured blocks vertically and a Dock button under them.
  [ ] a click on Menu opens a Popup below the button; Tall opens a scrolling one; hovering
      "Hover me" for about 0.4 s shows a tooltip; a click outside closes a Popup;
      Right edge opens its popup flush to the right edge.
  [ ] a melded Panel "Dock" (320 x 56) hangs from the bottom band, centred, in the ring's colour
      with the blue border following it, and a fillet (radius 14) at each join, no seam. Its
      text "Docked: part of the frame" is inside it.
  [ ] clicking the Dock button hides Dock (the bottom band closes up) and again shows it; the
      reserved space does not change (a maximised window stays {a.totals[3]} px from the bottom).
  [ ] a click in the opening, beside Dock and in the rounded notches 3 px or more inside the
      opening, reaches the window under it; a click on the strips, the ring or Dock does not.
  [ ] the Clock updates (it is a module in a strip with live values).
Toggle (variant B: left 48, top 44, a 3 px border, Dock on the RIGHT at the start)
  [ ] after toggle-strips.sh the ring changes within about a second: maximised windows stop
      {b.totals[0]} px from the left, {b.totals[1]} from the top, {b.totals[2]} from the right and {b.totals[3]} from the bottom; the top strip is
      44 high; Dock now hangs from the right band at its top end, 56 deep and 320 along.
  [ ] the strips' modules were not restarted (the clock keeps its second hand: no flash, one reload).
  [ ] toggle-strips.sh again returns to variant A.
Stop (Ctrl+C)
  [ ] every ring, strip and zone is gone at once.

Not built (each is a clear error or warning at load, not a silent no-op): strip expand, contract
and peek, a Bar melded to the Frame, a Panel's own window melded to the Frame (without Meld), a
Edges Visible key, a gradient background, a Frame shadow, fullscreen hiding.
"""


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    shutil.rmtree(CFG, ignore_errors=True)
    (CFG / "Shells").mkdir(parents=True)
    (CFG / "variants").mkdir()
    (CFG / "Shells" / "dot.svg").write_text(SVG)
    (CFG / "settings.tdl").write_text(SETTINGS)
    module = CFG / "Modules" / "Menu_Button"
    module.mkdir(parents=True)
    (module / "Menu_Button_Module.tdl").write_text(BUTTON_TDL)
    (module / "Menu_Button_Module.py").write_text(BUTTON_PY)
    for v in ("a", "b"):
        (CFG / "variants" / f"{v}.tdl").write_text(shell_text(v))
    shutil.copy(CFG / "variants" / "a.tdl", CFG / "Shells" / "Main_Shell.tdl")
    (ROOT / "state").mkdir(exist_ok=True)
    flag = ROOT / "state-flags"
    flag.mkdir(exist_ok=True)
    (flag / "strips").write_text("a")
    f = "/tmp/tess-kwin-m3c/state-flags/strips"
    script(
        "toggle-strips.sh",
        f'v=$(cat {f})\nif [ "$v" = a ]; then v=b; else v=a; fi\necho $v > {f}\n'
        f"cp /tmp/tess-kwin-m3c/strips/variants/$v.tdl /tmp/tess-kwin-m3c/strips/Shells/Main_Shell.tdl\n"
        'echo "strips: variant $v"\n',
    )
    script(
        "run-strips.sh",
        "# The Frame with strips and a melded Panel.  Usage: run-strips.sh   (Ctrl+C stops it)\n"
        "export XDG_STATE_HOME=/tmp/tess-kwin-m3c/state\n"
        f"echo a > {f}\n"
        "cp /tmp/tess-kwin-m3c/strips/variants/a.tdl /tmp/tess-kwin-m3c/strips/Shells/Main_Shell.tdl\n"
        f"exec {BIN}/tesserae-shell run --config-dir /tmp/tess-kwin-m3c/strips\n",
    )
    script(
        "check-strips.sh",
        "export XDG_STATE_HOME=/tmp/tess-kwin-m3c/state\n"
        f"{BIN}/tesserae-shell check --config-dir /tmp/tess-kwin-m3c/strips\n",
    )
    (ROOT / "checklist-strips.txt").write_text(checklist())
    print(f"wrote {ROOT} (read checklist-strips.txt)")


if __name__ == "__main__":
    main()
