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
* ``run-strips-linear.sh [SRGB|LINEAR]``: the same shell, with ``Debug { Frame_Blend: ... }``
  (default ``LINEAR``: the ring, its borders and its bodies in one shader that blends in linear
  light, TRE-REQ-015 option 2; ``SRGB``: paths, whose anti-aliased edges tre blends in sRGB): does
  the border read as 2 px on a curve as on a straight? ``run-peek-linear.sh [SRGB|LINEAR]`` is the Peek demo
  with it. A restart applies a change.
* ``compare-join.sh [--join=OPTION] [--blend=SRGB|LINEAR] ...``: ``tests/kwin/compare_join.py
  --live`` on HDMI-A-1: the cost of each option in one table (frame time while sliding, frames
  drawn at idle, memory).
* ``toggle-strips.sh``: switch the saved shell file between variant A and B (a hot reload).
* ``check-strips.sh``: the file is valid.
* ``run-peek.sh [OPTION]``, ``toggle-peek.sh``, ``check-peek.sh``: variant C, the Peek demo, in
  its own config directory ``/tmp/tess-kwin-m3c/peek``: the Dock rests as a 24 px tab and the left
  strip as a 6 px sliver; the pointer on either brings it out after a delay, leaving sends it
  back; ``OPTION`` is a ``Frame_Join``; ``toggle-peek.sh`` saves the shell file again as C with a
  changed delay and back (a hot reload that keeps the state).
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
    "  Appearance { Stylesheets: [Default], Follow_Desktop: true }\n}\n"
)

SETTINGS_JOIN = SETTINGS.replace("Settings {\n", "Settings {\n  Debug { Frame_Join: @JOIN@ }\n")
SETTINGS_BLEND = SETTINGS.replace("Settings {\n", "Settings {\n  Debug { Frame_Blend: @BLEND@ }\n")

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
    block = "Rectangle {{ Name: {n}, Width: 16, Height: 40, Fill: {c}, Corner_Radius: 3 }}"
    toggle = (
        "FlexBox { Name: Dock_Toggle, Width: 32, Height: 22, Padding: 3, Align_Items: CENTER, "
        "Justify_Content: CENTER, "
        "Style { Background: $color.primary, Corner_Radius: 4 }, "
        "On_Click { Action: Toggle, Target: Dock }, Children { "
        'Text { Text: "Dock", Width: AUTO, Height: AUTO, Font_Size: 11, Foreground: $color.on_primary } } }'
    )
    return "\n".join(
        [
            block.format(n="Left_A", c="$color.error"),
            block.format(n="Left_B", c="$color.success"),
            block.format(n="Left_C", c="$color.warning"),
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
        "Foreground: $color.on_surface } "
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
                Inner_Border {{ Width: {border}, Color: $color.primary }}
                Padding: {pad}
                Style {{ Background: $color.surface }}
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


def body(label: str, button: str, target: str) -> str:
    """The content of a peeking Panel: its text and a labelled button (a FlexBox with an On_Click)
    that Toggles ``target``, a visible Panel or strip: it proves a click inside an open body reaches
    its own action and does not toggle the peek."""
    return (
        "Children { FlexBox { Width: 100%, Height: 100%, Padding: 8, Spacing: 12, "
        "Align_Items: CENTER, Justify_Content: CENTER, Children { "
        f'Text {{ Text: "{label}", Width: AUTO, Height: AUTO, Font_Size: 14, '
        "Foreground: $color.on_surface }, "
        f"FlexBox {{ Name: {button.replace(' ', '_')}_Button, Width: 96, Height: 24, Padding: 3, "
        "Align_Items: CENTER, Justify_Content: CENTER, "
        "Style { Background: $color.primary, Corner_Radius: 4 }, "
        f"On_Click {{ Action: Toggle, Target: {target} }}, Children {{ "
        f'Text {{ Text: "{button}", Width: AUTO, Height: AUTO, Font_Size: 11, '
        "Foreground: $color.on_primary } } } } } }"
    )


def peek_dock(enter: int = 150, size: int = 24) -> str:
    return (
        "Panel { Name: Dock, Meld: true, Attach_To: Screen_Frame, Attach: BOTTOM, "
        "Alignment: CENTER, Length: 320, Depth: 56, "
        f"Peek {{ Size: {size}, Trigger: HOVER, Enter_Delay: {enter}, Exit_Delay: 300 }}, "
        "Animation { Type: SLIDE, Duration: 300 }, Style { Corner_Radius: 12 }, "
        + body("Docked: part of the frame", "Toggle Left", "Left_Strip")
        + " }"
    )


def peek_panel(
    name: str,
    attach: str,
    alignment: str,
    length: int,
    depth: int,
    peek: str,
    button: str,
    target: str,
    more: str = "",
) -> str:
    return (
        f"Panel {{ Name: {name}, Meld: true, Attach_To: Screen_Frame, Attach: {attach}, "
        f"Alignment: {alignment}, Length: {length}, Depth: {depth}, {peek}, {more}"
        "Animation { Type: SLIDE, Duration: 300 }, Style { Corner_Radius: 12 }, "
        + body(f"{name}: part of the frame", button, target)
        + " }"
    )


def toggle(name: str, label: str, target: str) -> str:
    return (
        f"FlexBox {{ Name: {name}, Width: 44, Height: 22, Padding: 3, Align_Items: CENTER, "
        "Justify_Content: CENTER, "
        "Style { Background: $color.primary, Corner_Radius: 4 }, "
        f"On_Click {{ Action: Toggle, Target: {target} }}, Children {{ "
        f'Text {{ Text: "{label}", Width: AUTO, Height: AUTO, Font_Size: 11, '
        "Foreground: $color.on_primary } } }"
    )


def peek_frame(enter: int = 150, size: int | None = None) -> tuple[str, RingSpec]:
    """Variant C, the Peek demo. The top strip stays, with buttons that Toggle the others (the way
    in without a pointer). The Dock rests as a 24 px tab at the bottom and opens on HOVER (dots);
    Notes is a top-right corner Panel that slides out of the RIGHT edge, opens on CLICK (a chevron);
    Tray at the bottom left opens by DRAG (a bar); the left strip rests as a 10 px sliver, opens by
    DRAG (a bar) and comes out to 56."""
    tab = {"dock": size or 24, "notes": size or 12, "tray": size or 14, "left": size or 10}
    toggles = [
        toggle("Dock_Toggle", "Dock", "Dock"),
        toggle("Left_Toggle", "Left", "Left_Strip"),
        toggle("Notes_Toggle", "Notes", "Notes"),
        toggle("Tray_Toggle", "Tray", "Tray"),
    ]
    top = "\n".join([*TOP_CHILDREN.split("\n"), *toggles])
    left = left_children().rsplit("\n", 1)[0]  # the blocks, without variant A's Dock button
    thick = (tab["left"], 34, 12, 14)  # wide enough for each handle: 8 px for dots, bar and chevron
    text = f"""            Frame {{
                Name: Screen_Frame
                Thickness {{ Left: {thick[0]}, Top: {thick[1]}, Right: {thick[2]}, Bottom: {thick[3]} }}
                Inner_Radius: 14
                Keyboard: ON_DEMAND
                Inner_Border {{ Width: 2, Color: $color.primary }}
                Padding: [8, 3, 8, 3]
                Style {{ Background: $color.surface }}
                Edges {{
                    Top {{
                        Thickness: 34
                        Children {{
                            FlexBox {{
                                Width: 100%, Height: 100%, Spacing: 8, Align_Items: CENTER
                                Children {{
{top}
                                }}
                            }}
                        }}
                    }}
                    Left {{
                        Name: Left_Strip
                        Thickness: 56
                        Padding: 6
                        Peek {{ Size: {tab["left"]}, Trigger: DRAG }}
                        Children {{
                            FlexBox {{
                                Flex: VERTICAL, Width: 100%, Spacing: 6, Align_Items: CENTER
                                Children {{
{left}
                                }}
                            }}
                        }}
                    }}
                }}
            }}
            {peek_dock(enter, tab["dock"])}
            {peek_panel("Notes", "TOP", "END", 220, 90, f"Peek {{ Size: {tab['notes']}, Trigger: CLICK, Slide_From: RIGHT, Handle_Opacity: 0.3 }}", "Toggle Dock", "Dock")}
            {peek_panel("Tray", "BOTTOM", "START", 200, 60, f"Peek {{ Size: {tab['tray']}, Trigger: DRAG }}", "Toggle Notes", "Notes", "Content_Fade: false,")}"""
    spec = RingSpec(
        thickness=thick,
        inner_radius=(14, 14, 14, 14),
        inner_border=2,
        melds=(
            MeldSpec("bottom", 320, 24, "CENTER", (12, 12, 12, 12)),
            MeldSpec("right", 12, 90, "START", (12, 12, 12, 12)),
            MeldSpec("bottom", 200, 14, "START", (12, 12, 12, 12)),
        ),
    )
    return text, spec


def shell_text(variant: str) -> str:
    if variant in ("c", "c2", "ct"):
        return (
            HEADER
            + f"""
Shell {{
    Monitor {{
        Name: Main
        Connector: "HDMI-A-1"
        Children {{
{POPUPS}{peek_frame(400 if variant == "c2" else 150, 7 if variant == "ct" else None)[0]}
        }}
    }}
}}
"""
        )
    return _shell_text(variant)


def _shell_text(variant: str) -> str:
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


def peek_checklist() -> str:
    c = ring(peek_frame()[1], (1920, 1080))
    return f"""Peek (variant C, its own config: /tmp/tess-kwin-m3c/peek; HDMI-A-1)
Setup (nothing else needs to run):
  /tmp/tess-kwin-m3c/check-peek.sh          the file is valid
  /tmp/tess-kwin-m3c/run-peek.sh [OPTION]   run it (Ctrl+C stops); OPTION is a Frame_Join
  /tmp/tess-kwin-m3c/toggle-peek.sh         save the file again with Enter_Delay 400 / 150 (hot reload)
  /tmp/tess-kwin-m3c/toggle-thin.sh         every Peek Size 7 (handles vanish) / back to 24, 12, 14, 10
Variant C: the top strip (34 px, Menu, Tall, ... plus buttons Dock, Left, Notes and Tray) stays.
Four things peek (the Frame is 10 left, 34 top, 12 right, 14 bottom so each handle fits its side):
  Dock   melded Panel at the bottom centre, 320 x 56:  Peek {{ Size: 24, Trigger: HOVER }}   (3 dots)
  Notes  melded Panel in the TOP-RIGHT corner, 220 wide x 90 high, Slide_From: RIGHT: it slides out
         of the right band, its tab is 12 px wide at the right edge:  Peek {{ Size: 12, Trigger: CLICK, Handle_Opacity: 0.3 }}   (chevron, dim)
  Tray   melded Panel at the bottom left, 200 x 60:  Peek {{ Size: 14, Trigger: DRAG }}, Content_Fade: false   (a bar; its content does not fade)
  Left   the left strip (three coloured blocks), Thickness 56:  Peek {{ Size: 10, Trigger: DRAG }}   (a bar)
Tell me what you see, line by line.
  [ ] AT REST the Dock is a 24 px TAB hanging up from the bottom band at the centre (320 wide): the
      ring's own colour, the blue border following it, a fillet at each join and rounded far
      corners, no text in it, three 6 px dots 2 px apart (the maintainer's icon, 24 x 8 box) at the middle of the tab. Notes is a
      12 px tab on the right band at its top end with the maintainer's chevron (a wide flat filled
      triangle, 22 x 6.7 px) pointing LEFT (apex into the
      opening, away from the Frame). Tray is a 14 px tab at the bottom left with the maintainer's bar (22 x 4 px, rounded ends). The
      left edge is a 10 px sliver with the border beside it and a bar
      along the edge, no blocks. Say how each icon looks at 1x (and 1.5x): size, colour (the border
      blue at 60 %), whether it is too small or too faint (the dots and the bar are 60 % of the border blue until the pointer is on the tab; with 6 px dots is 60 % now too faint or fine?), and whether any needs a minimum other
      than 8 px (dots, bar, chevron). The chevron has no area at the middle of its turn: during the
      slide it shrinks to nothing and grows back the other way: say if that looks wrong.
  [ ] RESERVED SPACE: a maximised window stops {c.totals[0]} px from the left, {c.totals[1]} from the top, {c.totals[2]} from the
      right and {c.totals[3]} from the bottom, and does not move at any point below (zones are the same in
      every state).
  [ ] HOVER THE TAB: put the pointer on the tab and keep it still. After about 150 ms the Dock
      raises to 56 px in 300 ms: the contour of the whole body moves (the two join fillets and the
      far corners grow, they do not stay as a box sliding), the border follows, and the text slides
      in with it, clipped inside. No pop at the start or at the end.
  [ ] LEAVE: move the pointer away. After about 300 ms it goes back to the tab the same way
      (joins shrinking back), and the text disappears with it.
  [ ] FAST IN AND OUT: sweep the pointer across the tab in less than 150 ms: nothing moves. With
      the Dock out, leave and come back in less than 300 ms: it stays out; no flicker.
  [ ] TURN ROUND: leave while it is still coming out (after the 150 ms): after the 300 ms it turns
      round from where it is, without a jump; the same coming back while it goes in.
  [ ] MOVING FROM THE TAB INTO THE BODY (down the tab, over the text) never counts as leaving.
  [ ] CLICKS: a click on the tab does not reach the window below; a click beside the tab, in the
      opening, reaches it; a click in the 40 px above the tab while it is at rest reaches it.
  [ ] HOVER DOES NOTHING ON THE OTHERS: the pointer resting on the Notes tab, the Tray tab or the
      left sliver for two seconds opens nothing (only the icon brightens while the pointer is on it).
  [ ] CLICK (Notes): a click on its tab slides it out of the RIGHT edge (not down from the top): the
      contour grows leftwards from the right band, the border follows, the chevron moves with the far
      edge and TURNS during the slide to point RIGHT (towards the Frame) when it is out. A second
      click on the chevron, at the left edge of the open body, slides it back and the chevron turns
      LEFT again. A click inside the open body away from the chevron does nothing to it.
  [ ] DRAG (Tray): press on the tab and drag UP: the body follows the pointer exactly (the far edge
      under the pointer, fillets and border following, the bar moving with the edge). Release past
      the half (28 px of 46) and it finishes opening; release before and it goes back. A press that
      moves under 4 px is a click and toggles. Dragging the open body's bar down closes it the same
      way. The press may leave the tab while dragging (the pointer is captured).
  [ ] DRAG (the left strip): press on its sliver and drag RIGHT: the strip's edge follows the pointer
      over a maximised window (the window is not resized or moved), the blocks slide in with it;
      release at 50 % of 46 px or more and it stays out, else it goes back. Reserved space does not
      change at any point.
  [ ] KEYBOARD WAY IN, no pointer: the top strip's buttons "Dock", "Left", "Notes" and "Tray" Toggle
      the Panel and the strip by Name (click them, or Tab/Enter to a focused painter with Keyboard:
      ON_DEMAND): each brings the body fully out and again back to the TAB (not away). Say what you
      found about reaching the buttons from the keyboard alone (it is not built: D102).
  [ ] Show/Hide leave the pointer alone: with the Dock out by the button and the pointer far away
      it stays out (no hover), a second click sends it back to the tab.
  [ ] The log (DEBUG) shows "Panel Dock on HDMI-A-1 shown (melded, slide)" when it comes out and
      "hiding" when it goes back, and "strip Left_Strip ... (peek, slide)" for the strip.
  [ ] HANDLE_OPACITY: Notes' chevron rests at 30 % (Handle_Opacity: 0.3) and the Dock's dots, the
      Left bar and the Tray bar at the default 60 %; hovering a tab raises its handle to full in
      about 120 ms and leaving lowers it back to ITS rest value. Edit one Peek to Handle_Opacity: 0
      (the icon is gone but the tab works) and 1 (always bright); a value above 1 is a load error.
  [ ] CONTENT FADE: coming out, the text and the button in the Dock, in Notes and in the left
      strip's blocks fade IN as the contour grows (fully clear exactly when it stops) and fade OUT as
      it goes back; nothing of the content shows on the tab. Dragging (Tray excepted), the content's
      brightness follows the pointer, exactly with the edge, at 125 moves a second without lagging
      behind the contour, with Debug {{ Frame_Blend: SRGB }} and with LINEAR (set it in settings.tdl,
      restart). A Show/Hide from a button fades the same. The Tray has Content_Fade: false: its
      text is opaque during the whole move, only its contour grows. Reduced motion: no fade.
  [ ] A plain Panel with no Peek (Visible: false in your own file, then Show) also fades its content
      with the slide; an Expander's content fades on its own (Content_Fade module parameter).
  [ ] REDUCED MOTION (Plasma animation speed "instant"): all switch at once, the delays stay; a
      dragged one still follows the pointer, and a release settles at once; the chevron flips at once.
  [ ] toggle-peek.sh: after it the Dock needs about 400 ms of hover; a Dock that was out stays out
      across the reload; a Frame that is hot-reloaded does not close its painter.
  [ ] run-peek.sh SMIL / STRUCTURE / PARAM do the same by the same contour, also while dragging.
      SHADER and CONCAVE log ONE warning per reason (a Panel that peeks; a drag) and use PARAM for the
      Panels and for the dragged left strip.
  [ ] MINIMUMS: run /tmp/tess-kwin-m3c/toggle-thin.sh (a saved edit: every Peek Size becomes 7, the
      left sliver too): the dots, both bars and the chevron all disappear, the tabs stay (7 px) and still
      work, and the log (DEBUG) says "has no ... handle" four times. Run it again: Sizes 24/12/14/10
      and the handles are back. (Edit "Handle: NONE" into a Peek by hand to remove one icon.)
  [ ] BUTTONS IN A BODY: each open Panel holds a labelled button: Dock "Toggle Left" (hover it out
      first), Notes "Toggle Dock" (click it out), Tray "Toggle Notes" (drag it out). Click the
      button away from the Panel's far strip: it Toggles its target (the left strip, the Dock, Notes)
      and the Panel itself stays out; the pointer leaving Dock does not close it while you click.
  [ ] THEME: switch Plasma between Light and Dark (System Settings > Colors): the Frame, the border,
      the Panels, the strip's blocks, the button colours, the text and the handles all change at once,
      also while a Panel is out (a slide in flight finishes at once). Settings has
      Appearance {{ Stylesheets: [Default], Follow_Desktop: true }}.
  [ ] a Popup from a strip button (Menu on the top strip) opens and closes as before; one that
      hangs off the left strip keeps it out while the Popup is open.
"""


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
and the far edge. The default is PARAM (the maintainer's choice); SMIL is the reference the others are measured against. For each option write what you see; the
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

@BLEND@
@PEEK@
Not built (each is a clear error or warning at load, not a silent no-op): strip expand and
contract (a peek is built), a Bar melded to the Frame, a Panel's own window melded to the Frame (without Meld), an
Edges Visible key, a gradient background, a Frame shadow, fullscreen hiding.
"""


def blend_checklist() -> str:
    return """Blend: Debug { Frame_Blend: SRGB | LINEAR } in settings.tdl (TRE-REQ-015, option 2)
SRGB draws the ring and its borders as paths: tre blends the anti-aliased edge of a
path in sRGB, so a light 2 px border on the dark ring looks thinner on a curve than on a straight
(1.69 of 2.00 at 1x, 1.79 at 1.5x, measured as summed linear light). LINEAR draws the ring, the
borders and every melded body in ONE shader that mixes the colours in linear light itself. A
restart applies a change ("Debug applies after a restart"). Run, at your display's scale (1.0 and,
if you can, 1.5), for each of SRGB and LINEAR:
  /tmp/tess-kwin-m3c/run-strips-linear.sh SRGB|LINEAR    variant A of the strips demo (Dock at the bottom;
                                                          toggle-strips.sh for variant B, the right band)
  /tmp/tess-kwin-m3c/run-peek-linear.sh SRGB|LINEAR      the Peek demo (variant C)
What LINEAR can fix: an edge between two colours the shader paints itself, here the border's outer
edge (against the dark ring). The border's INNER edge is against what is behind the Frame, which
the compositor blends in sRGB whatever the shader writes, so a curve over a dark desktop is
expected to read about 94 % of a straight at 1x and 96 % at 1.5x (paths: 84 % and 90 %), not 100 %.
Tell me what you see, line by line.
  [ ] the log (DEBUG) shows "ring drawn in linear light" once with LINEAR (and nothing of the sort
      with SRGB), and no line "draws it with paths".
  [ ] BORDER ON CURVES (the point of it): look at the 2 px blue border at the four opening corners, at
      the Dock's two joins and its far corners, and at the Dock's far corners when it is a Panel with
      a radius, SRGB then LINEAR, at 1x and at 1.5x (a magnifier helps). Does it read as 2 px on the
      curve as on the straight? Which of the two looks better, and by how much (none, a little, clearly)?
      Does anything look worse (too bold, a bright fringe on the desktop side, a darker one)?
  [ ] AT REST the ring is the same: positions of every edge, the colours, the strip areas, the
      margins; no hairline between the ring and the border, nothing shifted by a pixel anywhere
      (flip between the two runs).
  [ ] The DOCK SLIDE (the Dock button): the same movement as PARAM: the joins are round at every
      frame, grow with the body, no pop at the start or the end of the 300 ms, turning round without a
      jump; the left strip's blocks and the text slide with it.
  [ ] PEEK (run-peek-linear.sh): the Dock's tab (24 px), Notes (click), Tray (drag, the body follows
      the pointer exactly) and the left sliver (drag) look and move as with SRGB; the handles are on
      top of the ring.
  [ ] THEME: switch Plasma between Light and Dark: the ring, the border and the content change at
      once, also with a Panel out; a slide in flight finishes at once.
  [ ] CLICKS: a click in the opening, in the notch of a join (also while it slides) and in the margin
      reaches the window below; a click on the ring, the border or the Dock does not.
  [ ] IDLE: with nothing moving the log shows no frames drawn (DEBUG "frames"), and the CPU is idle.
  [ ] COST: /tmp/tess-kwin-m3c/compare-join.sh --join=PARAM --blend=SRGB  and  --blend=LINEAR (print both
      tables, the ring is one full-screen shader that redraws while a body slides).
  [ ] a reload (toggle-strips.sh) changes the ring within a second and the painter is not made again.
"""


def prepare_peek() -> None:
    """The Peek demo (variant C) in its own config directory, so the strips demo is untouched."""
    peek = ROOT / "peek"
    shutil.rmtree(peek, ignore_errors=True)
    (peek / "Shells").mkdir(parents=True)
    (peek / "Shells" / "dot.svg").write_text(SVG)
    (peek / "settings.tdl").write_text(SETTINGS)
    module = peek / "Modules" / "Menu_Button"
    module.mkdir(parents=True)
    (module / "Menu_Button_Module.tdl").write_text(BUTTON_TDL)
    (module / "Menu_Button_Module.py").write_text(BUTTON_PY)
    (peek / "variants").mkdir()
    for v in ("c", "c2", "ct"):
        (peek / "variants" / f"{v}.tdl").write_text(shell_text(v))
    shutil.copy(peek / "variants" / "c.tdl", peek / "Shells" / "Main_Shell.tdl")
    flag = ROOT / "state-flags"
    flag.mkdir(exist_ok=True)
    (flag / "peek").write_text("c")
    f = "/tmp/tess-kwin-m3c/state-flags/peek"
    script(
        "run-peek.sh",
        "# The Peek demo (variant C).  Usage: run-peek.sh [SMIL|CONCAVE|SHADER|STRUCTURE|PARAM]\n"
        "export XDG_STATE_HOME=/tmp/tess-kwin-m3c/state\n"
        f'opt="${{1:-}}"\nif [ -n "$opt" ]; then\n  case "$opt" in {"|".join(JOINS)}) ;;\n'
        f'    *) echo "usage: run-peek.sh [{"|".join(JOINS)}]" >&2; exit 2 ;;\n  esac\n'
        '  sed "s/@JOIN@/$opt/" /tmp/tess-kwin-m3c/settings-join.tdl.in'
        " > /tmp/tess-kwin-m3c/peek/settings.tdl\n"
        '  echo "Frame_Join: $opt"\nfi\n'
        f"echo c > {f}\n"
        "cp /tmp/tess-kwin-m3c/peek/variants/c.tdl /tmp/tess-kwin-m3c/peek/Shells/Main_Shell.tdl\n"
        f"exec {BIN}/tesserae-shell run --config-dir /tmp/tess-kwin-m3c/peek\n",
    )
    script(
        "run-peek-linear.sh",
        "# The Peek demo (variant C), the ring blended in sRGB (paths) or in linear light (one\n"
        "# shader).  Usage: run-peek-linear.sh [SRGB|LINEAR]   (default LINEAR)\n"
        'opt="${1:-LINEAR}"\ncase "$opt" in SRGB|LINEAR) ;;\n'
        '  *) echo "usage: run-peek-linear.sh [SRGB|LINEAR]" >&2; exit 2 ;;\nesac\n'
        "export XDG_STATE_HOME=/tmp/tess-kwin-m3c/state\n"
        'sed "s/@BLEND@/$opt/" /tmp/tess-kwin-m3c/settings-blend.tdl.in'
        " > /tmp/tess-kwin-m3c/peek/settings.tdl\n"
        'echo "Frame_Blend: $opt"\n'
        f"echo c > {f}\n"
        "cp /tmp/tess-kwin-m3c/peek/variants/c.tdl /tmp/tess-kwin-m3c/peek/Shells/Main_Shell.tdl\n"
        f"exec {BIN}/tesserae-shell run --config-dir /tmp/tess-kwin-m3c/peek\n",
    )
    script(
        "toggle-peek.sh",
        f'v=$(cat {f})\nif [ "$v" = c ]; then v=c2; else v=c; fi\necho $v > {f}\n'
        "cp /tmp/tess-kwin-m3c/peek/variants/$v.tdl /tmp/tess-kwin-m3c/peek/Shells/Main_Shell.tdl\n"
        'echo "peek: variant $v (c: Enter_Delay 150, c2: 400)"\n',
    )
    script(
        "toggle-thin.sh",
        f'v=$(cat {f})\nif [ "$v" = ct ]; then v=c; else v=ct; fi\necho $v > {f}\n'
        "cp /tmp/tess-kwin-m3c/peek/variants/$v.tdl /tmp/tess-kwin-m3c/peek/Shells/Main_Shell.tdl\n"
        'echo "peek: variant $v (ct: every Peek Size 7, c: 24/12/14/10; a saved edit, hot reload)"\n',
    )
    script(
        "check-peek.sh",
        "export XDG_STATE_HOME=/tmp/tess-kwin-m3c/state\n"
        f"{BIN}/tesserae-shell check --config-dir /tmp/tess-kwin-m3c/peek\n",
    )


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
    (ROOT / "settings-blend.tdl.in").write_text(SETTINGS_BLEND)
    script(
        "run-strips-linear.sh",
        "# The Frame with strips and a melded Panel, the ring blended in sRGB (paths) or in linear\n"
        "# light (one shader).  Usage: run-strips-linear.sh [SRGB|LINEAR]   (default LINEAR)\n"
        'opt="${1:-LINEAR}"\ncase "$opt" in SRGB|LINEAR) ;;\n'
        '  *) echo "usage: run-strips-linear.sh [SRGB|LINEAR]" >&2; exit 2 ;;\nesac\n'
        "export XDG_STATE_HOME=/tmp/tess-kwin-m3c/state\n"
        'sed "s/@BLEND@/$opt/" /tmp/tess-kwin-m3c/settings-blend.tdl.in'
        " > /tmp/tess-kwin-m3c/strips/settings.tdl\n"
        f"echo a > {f}\n"
        "cp /tmp/tess-kwin-m3c/strips/variants/a.tdl /tmp/tess-kwin-m3c/strips/Shells/Main_Shell.tdl\n"
        'echo "Frame_Blend: $opt"\n'
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
    prepare_peek()
    (ROOT / "checklist-strips.txt").write_text(
        checklist().replace("@BLEND@", blend_checklist()).replace("@PEEK@", peek_checklist())
    )
    print(f"wrote {ROOT} (read checklist-strips.txt)")


if __name__ == "__main__":
    main()
