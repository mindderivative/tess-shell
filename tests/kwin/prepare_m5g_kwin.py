"""Regenerate the M5g KWin check in /tmp/tess-kwin-m5g (not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m5g_kwin.py``. It writes a scratch config
and scripts under ``/tmp/tess-kwin-m5g`` and STARTS NOTHING, reads no bus and touches nothing outside
that folder. The suite never loads anything into your real KWin (fake ``/Scripting`` and a fake
script on private buses); this kit is the one place the shell's script runs inside the real KWin.

* ``introspect.sh``: READ-ONLY ``busctl --user`` calls that check the names the code could confirm
  only from KWin's files (``/Scripting`` and its interface name, the method signatures,
  ``supportInformation``). Run it first and compare with the list in ``checklist.txt``.
* ``backup.sh``: copies ``kwinrc`` and ``kwinrulesrc`` to ``/tmp/tess-kwin-m5g/backup`` (run it
  FIRST; it only copies).
* ``run.sh``: the shell on your real session with a Tasks module in the bar (mode R: the shell loads
  the script at start and unloads it at stop). ``run-off.sh`` has ``KWin { Script: OFF }``.
* ``checklist.txt``: every line to check.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

ROOT = Path("/tmp/tess-kwin-m5g")
BIN = Path(sys.executable).parent
HEAD = "---\nTDL: 0.2\nName: Settings\n---\n"
SHELL_HEAD = "---\nTDL: 0.2\nShell: 0.1\nName: Main_Shell\n---\n"
SHELL = """Shell {
    Monitor {
        Name: Main
        Index: 0
        Children {
            Bar {
                Name: Top_Bar
                Edge: TOP
                Width: EXPAND
                Height: 40
                Style { Background: $color.surface }
                Children {
                    FlexBox {
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Padding: [8, 4, 8, 4]
                        Align_Items: CENTER
                        Spacing: 12
                        Children { Workspaces { } Tasks { } Clock { } }
                    }
                }
            }
        }
    }
}
"""


def settings(extra: str) -> str:
    return f"{HEAD}Settings {{\n  Logging {{ Level: DEBUG }}\n{extra}}}\n"


CONFIGS = {
    # the shipped Default stylesheet gives the active task its look (``.task_item:selected``) and applies
    # only when it is named (Style Schema D36): without it the active window is not marked
    "cfg": settings(
        "  Appearance { Stylesheets: [Default] }\n  KWin { Script: RUNTIME, Hide_On_Fullscreen: true }\n"
    ),
    "cfg-off": settings("  KWin { Script: OFF }\n"),
}

INTROSPECT = """#!/bin/sh
# READ-ONLY: introspection of your real KWin. Nothing here changes a setting or loads a script.
busctl --user introspect org.kde.KWin /Scripting | grep -E 'loadScript|unloadScript|isScriptLoaded|start|org.kde'
busctl --user call org.kde.KWin /KWin org.kde.KWin supportInformation | head -c 400; echo
busctl --user tree org.kde.KWin | grep -i script
"""

CHECKLIST = """M5g KWin integration: every line to run.  The shell loads ITS OWN script into your real KWin
(mode R) and, only in line 20, edits kwinrulesrc.  Nothing in the suite does this.

NAMES THE CODE COULD NOT CONFIRM FROM FILES (check with introspect.sh, read-only)
  - /Scripting is the object path and org.kde.kwin.Scripting (lower case) the interface; methods
    loadScript(ss)->i, unloadScript(s)->b, isScriptLoaded(s)->b, start().  Seen in libkwin.so strings
    only (the object path as UTF-16 text), not on a bus.
  - loadScript returns an id (>= 0) and a bare .js path outside KWin's folders loads (spec test of
    2026-10-29); that start() runs it, and that the script file is read after start() (the shell
    keeps a one-shot script loaded 2 s).
  - the QUuid of window.internalId reads as "{uuid}" in JavaScript (the script strips the braces).
  - /KWin reconfigure (a NoReply method) makes KWin reload kwinrulesrc and kwinrc; the spec says
    'reloadConfig is a method' but KWin's own XML lists reloadConfig as a SIGNAL.
  - the rule file: group keys Description, layer=4, layerrule=2, wmclass, wmclasscomplete,
    wmclassmatch=2 and [General] count/rules.  Create the same rule in System Settings (Window
    Rules, force the layer, match the window class 'tesserae-shell.') and compare with
    `tesserae-shell kwin rule show`.

SAFETY
  0  /tmp/tess-kwin-m5g/backup.sh  (copies kwinrc and kwinrulesrc).  To undo everything: stop the
     shell (it unloads its script), run `tesserae-shell kwin rule remove` and
     `tesserae-shell kwin script remove`, or copy the backup files back while logged out.
  1  /tmp/tess-kwin-m5g/introspect.sh and compare with the names above.

PART 1: the script (run.sh)
  2  The log shows "kwin: KWin 6.x.y" and "kwin: the script tesserae-shell-kwin is loaded".
  3  `tesserae-shell kwin script status` says "loaded in KWin now: yes".
  4  With Tasks in the bar: one button per open window, in the order the windows were opened, with the
     application icon and the title; the active window is marked (a raised
     background and a 2 px border in the primary colour: the Default stylesheet, which this config
     names); your shell's own bar is not in it.
  5  Open, close, retitle (a terminal's title), minimise and move a window to another desktop: the
     row follows each within a moment.
  6  Click an inactive window: it activates (and un-minimises). Click the active one: it minimises.
     Middle click: it closes. Wheel over the row: next and previous window. Time one click: the
     window should react in under 100 ms (Tasks spec, question after testing 2).
  7  Windows of another desktop are hidden from the row (desktop: CURRENT); on two monitors each
     bar shows its own monitor's windows.
  8  Icons match the applications; change the icon theme in System Settings: the icons change.

PART 2: fullscreen
  9  Play a video fullscreen on the bar's monitor and make it the active window: the bar vanishes,
     the space it reserved is released. Leave fullscreen: the bar returns.
 10  A fullscreen window that is NOT active (click another window): the bar shows again.
 11  Fullscreen on another monitor than the bar: the bar stays.
 12  Stop the shell and start it while a window is fullscreen: the bar starts hidden (the fresh load
     reports the state).
 13  Stop the shell (Ctrl+C): `tesserae-shell kwin script status` says loaded: no.
 14  run-off.sh (KWin { Script: OFF }): nothing is loaded, no hiding, Tasks stays empty and hidden.
 15  The log has no ERROR and no 'silent' warning.

PART 3: the commands
 16  `tesserae-shell kwin script install` then status (package installed, enabled in kwinrc, loaded
     yes after KWin reconfigures; if it says no, log out and in), then `kwin script remove`.
 17  `tesserae-shell kwin rule show`.
 18  `tesserae-shell kwin rule install` (shows the rule, asks), then check that a bar's windows sit
     above a Plasma panel and that a second `install` is still one group in kwinrulesrc.
 19  `tesserae-shell kwin rule remove`: kwinrulesrc is as the backup, except for KWin's own
     rewrites. Write down whether the layer rule applies to a layer-shell surface at all.
"""


def main() -> None:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True)
    state = ROOT / "state"
    state.mkdir()
    for name, text in CONFIGS.items():
        cfg = ROOT / name
        (cfg / "Shells").mkdir(parents=True)
        (cfg / "settings.tdl").write_text(text)
        (cfg / "Shells" / "Main_Shell.tdl").write_text(SHELL_HEAD + SHELL)
    scripts = {
        "introspect.sh": INTROSPECT,
        "backup.sh": "#!/bin/sh\nmkdir -p /tmp/tess-kwin-m5g/backup\n"
        "cp -a ~/.config/kwinrc ~/.config/kwinrulesrc /tmp/tess-kwin-m5g/backup/ 2>/dev/null; "
        "echo copied\n",
        "run.sh": f"#!/bin/sh\nXDG_STATE_HOME={state} exec {BIN}/tesserae-shell run "
        f"--config-dir {ROOT}/cfg\n",
        "run-off.sh": f"#!/bin/sh\nXDG_STATE_HOME={state} exec {BIN}/tesserae-shell run "
        f"--config-dir {ROOT}/cfg-off\n",
    }
    for name, text in scripts.items():
        path = ROOT / name
        path.write_text(text)
        path.chmod(0o755)
    (ROOT / "checklist.txt").write_text(CHECKLIST)
    print(f"wrote {ROOT}: read checklist.txt, run introspect.sh, backup.sh, then run.sh")


if __name__ == "__main__":
    main()
