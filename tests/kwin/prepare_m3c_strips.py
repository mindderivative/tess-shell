"""Regenerate the M3c Frame strips and melded Panel KWin checklist setup in /tmp/tess-kwin-m3c/strips
(not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m3c_strips.py``. It writes a scratch
config and scripts under ``/tmp/tess-kwin-m3c`` and starts nothing. It does not touch what
``prepare_m3c_frame.py`` writes (the Frame ring checklist, ``measure.sh``).

* ``run-strips.sh``: run the shell: one Frame on HDMI-A-1 with a top strip (menu buttons that
  open Popups, a Clock), a left strip (coloured blocks and a button that toggles the Panel) and a
  Panel melded into the bottom of the Frame.
* ``run-strips-join.sh OPTION``: the same shell, with ``Debug { Frame_Join: OPTION }`` (SMIL,
  CONCAVE, SHADER, STRUCTURE or PARAM): the way the Dock's join is drawn while it slides, so the
  five can be compared by eye on KWin (a restart applies a change).
* ``compare-join.sh [--join=OPTION] ...``: ``tests/kwin/compare_join.py --live`` on HDMI-A-1:
  the cost of each option in one table (frame time while sliding, frames drawn at idle, memory).
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

from tess_shell.surfaces.join import JOINS  # noqa: E402
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

SETTINGS_JOIN = SETTINGS.replace("Settings {\n", "Settings {\n  Debug { Frame_Join: @JOIN@ }\n")

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
        "FlexBox { Name: Dock_Toggle, Width: 32, Height: 22, Padding: 3, Align_Items: CENTER, "
        "Justify_Content: CENTER, "
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


def dock_size(side: str) -> tuple[int, int]:
    """(Length, Depth): a text that fits a 56 px band on the bottom needs more room on the side."""
    return (320, 56) if side in ("TOP", "BOTTOM") else (240, 150)


def dock(side: str, alignment: str) -> str:
    length, depth = dock_size(side)
    return (
        f"Panel {{ Name: Dock, Meld: true, Attach_To: Screen_Frame, Attach: {side}, "
        f"Alignment: {alignment}, Length: {length}, Depth: {depth}, Animation {{ Type: SLIDE, Duration: 300 }}, "
        "Style { Corner_Radius: 12 }, "
        "Children { FlexBox { Width: 100%, Height: 100%, Padding: 8, Align_Items: CENTER, "
        "Justify_Content: CENTER, Children { "
        'Text { Text: "Docked: part of the frame", Width: AUTO, Height: AUTO, Font_Size: 14, '
        'Foreground: "#cdd6f4" } '
        "} } } }"
    )


def frame(variant: str) -> tuple[str, RingSpec]:
    if variant == "a":
        thick, pad, top_t, side = (40, 34, 8, 8), "[8, 3, 8, 3]", 34, ("BOTTOM", "CENTER")
        border = 2
        keyboard = ""
    else:
        thick, pad, top_t, side = (48, 44, 8, 8), "[12, 6, 12, 6]", 44, ("RIGHT", "START")
        border = 3
        keyboard = "Keyboard: ON_DEMAND"
    text = f"""            Frame {{
                Name: Screen_Frame
                Thickness {{ Left: {thick[0]}, Top: {thick[1]}, Right: {thick[2]}, Bottom: {thick[3]} }}
                Inner_Radius: 14
                {keyboard}
                Inner_Border {{ Width: {border}, Color: "#89b4fa" }}
                Padding: {pad}
                Style {{ Background: "#1e1e2e" }}
                Edges {{
                    Top {{
                        Thickness: {top_t}
                        Children {{
                            FlexBox {{
                                Width: 100%, Height: 100%, Spacing: 8, Align_Items: CENTER
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
        side[0].lower(),
        dock_size(side[0])[0] if across else dock_size(side[0])[1],
        dock_size(side[0])[1] if across else dock_size(side[0])[0],
        side[1],
        (12, 12, 12, 12),
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
  /tmp/tess-kwin-m3c/run-strips-join.sh OPTION   the same, with one way of drawing the Dock's join
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
  [ ] clicking the Dock button hides Dock and again shows it, and the reserved space does not
      change (a maximised window stays {a.totals[3]} px from the bottom). It ANIMATES (300 ms):
      the body grows out of the bottom band (hiding: back into it) AND ITS TWO JOINS GROW WITH IT:
      watch the fillets: at the first frames they are tiny and round, they grow to radius 14
      as the body comes out; there is never a 90 degree corner and no chamfer. Where the body
      ends the contour does not jump (no pop at the start or the end of the 300 ms). The text
      slides with the body and stays inside it.
  [ ] the one that goes wrong most easily: click Dock repeatedly, and turn the shell's Frame
      off and on, while it moves; nothing is left behind (no stale blue shape, no missing band).
  [ ] click the Dock button again while it is still moving (twice quickly): it turns round
      from where it is, without a jump.
  [ ] while it moves, a click on the body's own box reaches the Dock; a click in the part of the
      opening it has not reached yet reaches the window below (the morph is an svg, which takes
      no input: the ring under it keeps the shape that took clicks before the move); at rest a
      click on Dock does not reach the window below.
  [ ] SMOOTHNESS AT REST at 1x, from a normal viewing distance and then with a magnifier: the
      join fillets and the corners of the opening are round, not stepped; the 2 px border
      follows the curve with an even thickness and no light hairline between it and the dark
      band (that seam is now sealed: the band runs under an opaque border). Say what you see: a
      curve of radius 14 at 1x has at most a one-pixel anti-aliased edge.
  [ ] a click in the opening, beside Dock and in the rounded notches 3 px or more inside the
      opening, reaches the window under it; a click on the strips, the ring or Dock does not.
  [ ] the Clock updates (it is a module in a strip with live values).
  [ ] VARIANT B check below (the overlap that was reported): in B the Dock is on the RIGHT band
      at its top end, under the top strip's "Right edge" button. While the Dock opens and closes
      the button is never covered: it stays whole and its text stays readable at every frame.
  [ ] CENTRING: the text of Menu, Tall, Hover me, Dock (left strip) and of the Dock panel is
      centred in its box, across and along (the boxes use Align_Items and Justify_Content CENTER
      with a Text that is Width and Height AUTO). The clock's text is at the top of its box: in
      tre 0.6.1 a Text with no size is not measured (fixed in 0.6.2): say how far it is off.
Toggle (variant B: left 48, top 44, a 3 px border, Dock on the RIGHT at the start)
  [ ] after toggle-strips.sh the ring changes within about a second: maximised windows stop
      {b.totals[0]} px from the left, {b.totals[1]} from the top, {b.totals[2]} from the right and {b.totals[3]} from the bottom; the top strip is
      44 high; Dock now hangs from the right band at its top end, 150 deep and 240 along.
  [ ] Keyboard: variant B has `Keyboard: ON_DEMAND` on the Frame, variant A none. The log shows
      "painter keyboard on_demand" after the toggle (and "none" back in A) with no new painter
      window ("painter 1920x1080" appears once). With the DEBUG log, click the ring (the
      compositor gives the painter keyboard focus), press keys: lines
      "Frame ... painter key 'a'" appear. Without a mouse: Alt+Tab to the painter is up to KWin
      (a layer surface with on_demand focus can be focused from the keyboard by KWin's own
      shortcuts if it has any); say what you found.
  [ ] the strips' modules were not restarted (the clock keeps its second hand: no flash, one reload).
  [ ] toggle-strips.sh again returns to variant A.
Stop (Ctrl+C)
  [ ] every ring, strip and zone is gone at once.

Join options (the Dock's join while it slides): Debug {{ Frame_Join }} in settings.tdl, one of
{", ".join(JOINS)}; a change needs a restart ("Debug applies after a restart" in the log). Run
  /tmp/tess-kwin-m3c/run-strips-join.sh OPTION     for each of the five, variant A then B (toggle-strips.sh)
and use the Dock button, at your display's scale (1.0, and 1.5 if you can), watching the left and right joins
and the far edge. The reference is SMIL (the default). For each option write what you see; the
points to look at, per option:
  [ ] START: the first frames: no pop (the body grows out of the band edge, the border is
      continuous with the band's); no frame in which the border has a gap, a corner or a step.
  [ ] MIDDLE: the fillets are round at every frame (no 90 degree corner, no chamfer, no
      polygon look), grow from tiny to radius 14, and the 2 px border keeps an even thickness
      round them (CONCAVE: the border is thinner on the fillet in the first frames; say how much).
  [ ] END (the last frame and the one after it): no pop when the animation hands over to the ring.
  [ ] HIDING is the same movement backwards; click Dock again while it moves: it turns round
      without a jump.
  [ ] variant B (Dock flush with the band's top end): the corner next to the top band is the
      Frame's own and never shows a notch or a stray arc while the body is small (CONCAVE and SHADER
      draw over the ring, so they may show the opening's rounded corner until the body covers it:
      say whether you see it).
  [ ] a click in the notch of a join, while it moves and at rest, reaches the window below.
  [ ] the edge at 1x and at 1.5x is as smooth as at rest (SHADER has analytic edges at every scale;
      the others are anti-aliased paths and boxes). Say which one you would pick, and why.
  [ ] frames at idle: with the Dock at rest the log shows no frames (DEBUG: "frames"), and the CPU
      is idle (top): none of the options may keep the painter drawing after the animation.
  [ ] the cost: /tmp/tess-kwin-m3c/compare-join.sh   (prints the table for all five on HDMI-A-1;
      add --join=SHADER for one). Send the printed block; it also writes PNG sheets (headless
      renders) to /tmp/join-compare.

Reduced motion: switch Plasma's animation speed to "instant" (or the portal's reduced motion):
  [ ] Dock then appears and disappears at once.

Not built (each is a clear error or warning at load, not a silent no-op): strip expand, contract
and peek, a Bar melded to the Frame, a Panel's own window melded to the Frame (without Meld), an
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
    (ROOT / "settings-join.tdl.in").write_text(SETTINGS_JOIN)
    script(
        "run-strips-join.sh",
        "# The Frame with strips and a melded Panel, with one way of drawing the join while the\n"
        "# Panel slides.  Usage: run-strips-join.sh SMIL|CONCAVE|SHADER|STRUCTURE|PARAM\n"
        f'opt="${{1:-}}"\ncase "$opt" in {"|".join(JOINS)}) ;;\n'
        f'  *) echo "usage: run-strips-join.sh {"|".join(JOINS)}" >&2; exit 2 ;;\nesac\n'
        "export XDG_STATE_HOME=/tmp/tess-kwin-m3c/state\n"
        'sed "s/@JOIN@/$opt/" /tmp/tess-kwin-m3c/settings-join.tdl.in'
        " > /tmp/tess-kwin-m3c/strips/settings.tdl\n"
        f"echo a > {f}\n"
        "cp /tmp/tess-kwin-m3c/strips/variants/a.tdl /tmp/tess-kwin-m3c/strips/Shells/Main_Shell.tdl\n"
        'echo "Frame_Join: $opt"\n'
        f"exec {BIN}/tesserae-shell run --config-dir /tmp/tess-kwin-m3c/strips\n",
    )
    script(
        "compare-join.sh",
        "# Cost of each way of drawing the join on HDMI-A-1 (opens the Frame once per option on the\n"
        "# real desktop, a few seconds each).  Usage: compare-join.sh [--join=OPTION] [--seconds=N]\n"
        f"cd {REPO}\n"
        f'exec {BIN}/python {REPO}/tests/kwin/compare_join.py --live --output=HDMI-A-1 "$@"\n',
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
