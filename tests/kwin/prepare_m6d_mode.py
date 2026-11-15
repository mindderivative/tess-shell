"""Regenerate the M6d shortcut-mode KWin check in /tmp/tess-kwin-m6d (not collected by pytest).

Run from the repo root: ``env -u WAYLAND_DISPLAY -u DISPLAY PYTHONDONTWRITEBYTECODE=1 uv run python
tests/kwin/prepare_m6d_mode.py``. It writes scratch configs and scripts under ``/tmp/tess-kwin-m6d``
and starts nothing, reads nothing and touches nothing outside that folder.

THE MODE'S ENTER KEY IS THE ONE GLOBAL KEY: the shell registers ``Enter_Shortcut_Mode`` (and the four
other mode actions, with no key) with your REAL ``org.kde.kglobalaccel``. Registering writes to
``~/.config/kglobalshortcutsrc`` and shows in System Settings, so the checklist starts with a copy,
exactly like the M6c check. No test of the suite does this: they use a fake service on a private
bus and a private sway (Orchestration Log D-019). The mode's own keys (Tab, Shift+Tab, Ctrl+Enter,
Ctrl+Q, Escape) are NOT registered: they arrive as key events on the surface that has the
keyboard, which is what this check is about (spec question 2 of Focus and Keyboard: which keyboard
mode KWin needs).

* ``backup.sh``: copies ``~/.config/kglobalshortcutsrc`` to ``/tmp/tess-kwin-m6d/backup`` (run it
  FIRST; it only copies).
* ``run.sh``: the shell on your real session; ``Debug { Mode_Keyboard: EXCLUSIVE }`` (the default).
  ``run-ondemand.sh``: the same with ``Mode_Keyboard: ON_DEMAND``, to see whether KWin hands the
  keyboard over without EXCLUSIVE.
* ``check.sh``: ``tesserae-shell check`` on each config.
* ``checklist.txt``: every line to check, in one list.

The state directory is ``/tmp/tess-kwin-m6d/state``, never the real one. The scripts use the main
shell venv (``~/Projects/pyDev/pyEnvs/tess-shell``).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.shell_samples import write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m6d")
BIN = Path.home() / "Projects/pyDev/pyEnvs/tess-shell/bin"
KEY_ENTER = "Ctrl+Alt+Shift+F9"  # a rare key, free on a default Plasma
HEAD = "---\nTDL: 0.2\nName: Settings\n---\n"

SHELL = """
Shell {
    Monitor {
        Name: Main
        Index: 0
        Children {
            Frame {
                Name: Screen_Frame
                Thickness: 10
                Tab_Index: 1
                Inner_Radius: 12
                Inner_Border { Width: 2, Color: $color.primary }
                Style { Background: $color.surface }
                Edges {
                    Top {
                        Name: Clock_Strip
                        Thickness: 34
                        Tab_Index: 5
                        Peek { Size: 6, Trigger: HOVER }
                        Children {
                            FlexBox {
                                Flex: HORIZONTAL
                                Padding: [8, 4, 8, 4]
                                Align_Items: CENTER
                                Children { Button { Name: Strip_Button, Text: "Strip" } Clock { } }
                            }
                        }
                    }
                }
            }
            Panel {
                Name: Side_Tab
                Meld: true
                Attach_To: Screen_Frame
                Attach: LEFT
                Alignment: START
                Length: 220
                Depth: 160
                Peek { Size: 14, Trigger: HOVER }
                Animation { Type: SLIDE, Duration: 200 }
                Children {
                    FlexBox {
                        Flex: VERTICAL
                        Spacing: 8
                        Padding: 12
                        Children { Label { Text: "A peeking Panel" } }
                    }
                }
            }
            Bar {
                Name: Top_Bar
                Edge: BOTTOM
                Width: EXPAND
                Height: 40
                Tab_Index: 4
                Style { Background: $color.surface }
                Children {
                    FlexBox {
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Spacing: 8
                        Padding: [8, 4, 8, 4]
                        Align_Items: CENTER
                        Children {
                            Button { Name: Bar_One, Text: "Bar one" }
                            Button { Name: Bar_Two, Text: "Bar two" }
                            Clock { }
                        }
                    }
                }
            }
            Panel {
                Name: Notes
                Layer: TOP
                Anchor: [RIGHT, BOTTOM]
                Inset: [0, 0, 60, 60]
                Width: 300
                Height: 140
                Tab_Index: 2
                Style { Background: $color.surface_raised, Corner_Radius: 8 }
                Children {
                    FlexBox {
                        Flex: VERTICAL
                        Spacing: 8
                        Padding: 16
                        Children {
                            Button { Name: Notes_One, Text: "Notes one" }
                            Button { Name: Notes_Two, Text: "Notes two" }
                        }
                    }
                }
            }
            Panel {
                Name: Dock
                Layer: TOP
                Anchor: [LEFT, BOTTOM]
                Inset: [60, 0, 0, 60]
                Width: 300
                Height: 140
                Tab_Index: 3
                Style { Background: $color.surface_raised, Corner_Radius: 8 }
                Children {
                    FlexBox {
                        Flex: VERTICAL
                        Spacing: 8
                        Padding: 16
                        Children { Button { Name: Dock_One, Text: "Dock one" } }
                    }
                }
            }
        }
    }
}
"""

# the mode's own keys are plain keys here, and that is safe: only Enter_Shortcut_Mode is registered
# with the desktop; the others arrive as key events on the surface that has the keyboard (Set is a
# Ctrl chord: in a Panel's own mode a plain Space or Enter belongs to its buttons)
KEYS = f"""  Shortcuts {{
    Enter_Shortcut_Mode: "{KEY_ENTER}"
    Exit_Shortcut_Mode: "Ctrl+Q"
    Set_Shortcut_Mode: "Ctrl+Enter"
    Next_Focus: "Tab"
    Previous_Focus: "Shift+Tab"
  }}
"""


def settings(extra: str = "") -> str:
    return f"{HEAD}Settings {{\n  Logging {{ Level: DEBUG }}\n{extra}{KEYS}}}\n"


# folder -> settings.tdl
CONFIGS: dict[str, str] = {
    "cfg": settings(),
    "cfg-ondemand": settings("  Debug { Mode_Keyboard: ON_DEMAND }\n"),
}

CHECKLIST = f"""M6d shortcut mode: one list, every line to run.  THIS CHECK USES YOUR REAL SHORTCUT SERVICE
(org.kde.kglobalaccel, in kwin_wayland): the shell registers ONE key, {KEY_ENTER}
(Enter Shortcut Mode), and four more actions with no key.  Registering writes to
~/.config/kglobalshortcutsrc and shows in System Settings.  Nothing in the suite does this.  The mode
TAKES THE KEYBOARD while it is on (your other windows get no typing): Escape or Ctrl+Q leaves it.
Do NOT restart kwin_wayland: on Wayland that ends your session.

SAFETY FIRST
 0  Copy the shortcut file BEFORE the first run:  /tmp/tess-kwin-m6d/backup.sh
    (it copies ~/.config/kglobalshortcutsrc to /tmp/tess-kwin-m6d/backup/kglobalshortcutsrc and
    changes nothing).  To REMOVE what the shell registered:  stop the shell, open System Settings,
    Shortcuts, find "Tesserae Shell" in the list of applications and remove it.  To put the COPY
    back if anything looks wrong: stop the shell, log out, and from a text console run
    cp /tmp/tess-kwin-m6d/backup/kglobalshortcutsrc ~/.config/kglobalshortcutsrc  then log in.
 1  /tmp/tess-kwin-m6d/check.sh : both configs check clean ("ok: 1 files checked").
    Before each run open a terminal for the log (run.sh prints it) and keep another window
    (a text editor) open to see where the keyboard goes back to.

PART 1: entering  (start with /tmp/tess-kwin-m6d/run.sh; your shell is fish: use $status, not $?)
 2  The log shows "shortcuts: 5 of 5 actions registered" and no WARNING about shortcuts.  System
    Settings, Shortcuts, "Tesserae Shell": five rows (Enter Shortcut Mode with {KEY_ENTER}; Exit
    Shortcut Mode, Set Shortcut Mode, Next Focus, Previous Focus with NO key).  If one of the
    four has a key, the shell registered a mode-only key globally: that is a bug, write it down.
 3  Focus the text editor.  Press {KEY_ENTER}.  The log says "shortcut mode: mode Screen_Frame,
    focus Screen_Frame" and "Screen_Frame takes the keyboard (exclusive)".  Both peeks come out at
    once: the clock strip at the top and the "A peeking Panel" at the left (they were slivers).
 4  SPEC QUESTION 2: type a letter: it does NOT appear in the editor (the mode has the keyboard).
    Press Tab: the log says "key Tab -> Next_Focus" and "mode Screen_Frame, focus Notes": the
    keyboard moved to the Notes panel (it shows a focus ring on "Notes one").  If Tab does
    nothing (no "key Tab" line) the compositor did not give the surface the keyboard: write that
    down, then do part 5.

PART 2: moving and going in
 5  Tab again: focus Dock (ring on "Dock one"), then Top_Bar (ring on "Bar one"), then Clock_Strip
    (ring on "Strip"), then Screen_Frame, then Notes again: the Tab_Index order 1 to 5, round.
    Shift+Tab goes back.  The peeks stay out the whole time.
 6  On Notes press Ctrl+Enter (Set_Shortcut_Mode): the log says "mode Notes, focus Notes"; the
    peeks go back to slivers (the Frame's mode is off); Tab inside Notes moves between its two
    buttons (those are the panel's own keys: Tab is not taken by the mode there); Tab does NOT
    leave Notes.  Space on a button presses it (the widget's key).
 7  Press {KEY_ENTER} again: back to the Frame ("mode Screen_Frame, focus Screen_Frame", peeks out).
 8  Next to Notes, press Ctrl+Enter (Notes in the mode), then Ctrl+Q: the log says "shortcut mode: off";
    the peeks are slivers; the keyboard is back in the text editor (type: the letters appear).

PART 3: leaving
 9  Press {KEY_ENTER}, then Escape: the mode ends ("key Escape -> Exit_Shortcut_Mode", "off") and
    the keyboard goes back to the window that had it (the editor).
10  Press {KEY_ENTER}, Tab (focus on Notes), then from a SECOND terminal that you opened first:
    tesserae-shell hide Notes   (type it before the key press if the mode would stop you: use
    "sleep 8; tesserae-shell hide Notes" started first).  The focus goes on to the next surface
    ("mode Screen_Frame, focus Dock"), the mode stays; with Notes in its own mode (step 6) the
    hide ends the whole mode.
11  A Next_Focus or Previous_Focus key outside the mode does nothing: with the mode off press Tab
    in the editor: it is the editor's Tab (the shell took no Tab from your session).

PART 4: the status (Orca, if you use it)
12  With Orca running: entering says "Shortcut mode on, Screen_Frame", each Tab says the surface's
    name, leaving says "Shortcut mode off" (a polite status).  [#needs-verification: how Orca
    treats a live region of a layer surface]  Write down what you hear.

PART 5: the keyboard mode (spec question 2, which one KWin needs)
13  Stop the shell and run /tmp/tess-kwin-m6d/run-ondemand.sh (Mode_Keyboard: ON_DEMAND).  Press
    {KEY_ENTER}: does Tab still reach the surface ("key Tab -> Next_Focus")?  Write down yes or no:
    that decides whether EXCLUSIVE is needed on KWin.  If the keys do not arrive the log should
    carry a WARNING after one second saying the compositor did not hand the keyboard over.

CLEAN UP
14  Stop the shell; remove "Tesserae Shell" in System Settings, Shortcuts (see line 0); look at
    ~/.config/kglobalshortcutsrc: no [tesserae-shell] group is left.  If anything else changed,
    put the copy back (line 0).
"""

REAL_WARNING = (
    'echo "THIS REGISTERS SHORTCUTS WITH YOUR REAL SHORTCUT SERVICE (kglobalaccel)." >&2\n'
    'echo "Did you run /tmp/tess-kwin-m6d/backup.sh? Ctrl+C within 5 s to stop." >&2\n'
    "sleep 5\n"
)


def script(root: Path, name: str, text: str) -> None:
    path = root / name
    path.write_text("#!/bin/sh\n" + text)
    path.chmod(0o755)


def write_kit(root: Path = ROOT) -> None:
    """Write every file of the kit under ``root`` (nothing outside it)."""
    root.mkdir(parents=True, exist_ok=True)
    for folder, text in CONFIGS.items():
        cfg = root / folder
        shutil.rmtree(cfg, ignore_errors=True)
        write_example(cfg, SHELL)
        (cfg / "settings.tdl").write_text(text)
    (root / "checklist.txt").write_text(CHECKLIST)
    state = f"export XDG_STATE_HOME={root}/state\n"
    script(
        root,
        "backup.sh",
        f"mkdir -p {root}/backup\n"
        f"cp -p ~/.config/kglobalshortcutsrc {root}/backup/kglobalshortcutsrc\n"
        f"echo copied ~/.config/kglobalshortcutsrc to {root}/backup/kglobalshortcutsrc\n",
    )
    for name, folder in (("run.sh", "cfg"), ("run-ondemand.sh", "cfg-ondemand")):
        script(
            root,
            name,
            state + REAL_WARNING + f"exec {BIN}/tesserae-shell run --config-dir {root / folder}\n",
        )
    script(
        root,
        "check.sh",
        state
        + "".join(
            f"{BIN}/tesserae-shell check --config-dir {root}/{folder}\n" for folder in CONFIGS
        ),
    )


def main() -> None:
    write_kit()
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
