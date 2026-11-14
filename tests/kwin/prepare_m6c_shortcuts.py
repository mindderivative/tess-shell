"""Regenerate the M6c global-shortcuts KWin check in /tmp/tess-kwin-m6c (not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m6c_shortcuts.py``. It writes scratch
configs and scripts under ``/tmp/tess-kwin-m6c`` and starts nothing, reads nothing and touches
nothing outside that folder. THIS IS THE ONLY PLACE the shell registers shortcuts with your REAL
``org.kde.kglobalaccel``: every test of the suite uses a fake service on a private bus, and no
session registers a shortcut with your real service (Orchestration Log D-019). Registering writes to
``~/.config/kglobalshortcutsrc`` and shows in System Settings, so the checklist starts with a copy.

* ``backup.sh``: copies ``~/.config/kglobalshortcutsrc`` to ``/tmp/tess-kwin-m6c/backup`` (run it
  FIRST; it only copies). ``checklist.txt`` says how to remove the component and how to put the copy
  back.
* ``run.sh``: the shell on your real session with two shortcuts in its ``settings.tdl``:
  ``Toggle_Launcher: Ctrl+Alt+Shift+F11`` and ``Toggle_Notes: Ctrl+Alt+Shift+F12`` (rare keys, free
  on a default Plasma). ``run-anycase.sh`` writes the first key as ``ctrl+ALT+shift+f11``;
  ``run-taken.sh KEY`` writes a key YOU name (one the desktop already uses, to see the warning);
  ``run-off.sh`` has ``Global_Shortcuts: false``.
* ``check.sh``: ``tesserae-shell check`` on each config.
* ``checklist.txt``: every line to check, in one list.

The state directory is ``/tmp/tess-kwin-m6c/state``, never the real one.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.shell_samples import write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m6c")
BIN = Path.home() / "Projects/pyDev/pyEnvs/tess-shell/bin"
KEY_ONE = "Ctrl+Alt+Shift+F11"
KEY_TWO = "Ctrl+Alt+Shift+F12"
HEAD = "---\nTDL: 0.1\nName: Settings\n---\n"
SHELL = """
Shell {
    Monitor {
        Name: Main
        Index: 0
        Children {
            Bar {
                Name: Top_Bar
                Edge: TOP
                Width: EXPAND
                Height: 36
                Style { Background: $color.surface }
                Children {
                    FlexBox {
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Padding: [8, 4, 8, 4]
                        Align_Items: CENTER
                        Children { Clock { } }
                    }
                }
            }
            Panel {
                Name: Launcher
                Layer: OVERLAY
                Width: 500
                Height: 300
                Visible: false
                Style { Background: $color.primary, Corner_Radius: 12 }
                Children { FlexBox { Padding: 24, Children { Clock { } } } }
            }
            Panel {
                Name: Notes
                Layer: TOP
                Anchor: [RIGHT, BOTTOM]
                Width: 300
                Height: 200
                Visible: false
                Style { Background: $color.surface_raised, Corner_Radius: 8 }
            }
        }
    }
}
"""


def settings(entries: str, extra: str = "") -> str:
    return (
        f"{HEAD}Settings {{\n  Logging {{ Level: DEBUG }}\n{extra}"
        f"  Shortcuts {{\n{entries}  }}\n}}\n"
    )


def entries(one: str = KEY_ONE, two: str = KEY_TWO) -> str:
    return f'    Toggle_Launcher: "{one}"\n    Toggle_Notes: "{two}"\n'


# (folder, settings.tdl text); run-taken.sh rewrites the first key to the one you name
CONFIGS: dict[str, str] = {
    "cfg": settings(entries()),
    "cfg-anycase": settings(entries(one="ctrl+ALT+shift+f11")),
    "cfg-taken": settings(entries(one="TAKEN_KEY")),
    "cfg-off": settings(entries(), extra="  Global_Shortcuts: false\n"),
}

CHECKLIST = f"""M6c global shortcuts: one list, every line to run.  THIS CHECK USES YOUR REAL SHORTCUT SERVICE
(org.kde.kglobalaccel, in kwin_wayland).  Registering a shortcut writes to ~/.config/kglobalshortcutsrc
and shows in System Settings.  Nothing in the suite does this: it is the one hand check of the live
registration (spec question 3 is open until you answer it).  Do NOT restart kwin_wayland to test line
13: on Wayland that ends your session.

SAFETY FIRST
 0  Copy the shortcut file BEFORE the first run:  /tmp/tess-kwin-m6c/backup.sh
    (it copies ~/.config/kglobalshortcutsrc to /tmp/tess-kwin-m6c/backup/kglobalshortcutsrc and
    changes nothing).  To REMOVE what the shell registered:  stop the shell, open System Settings,
    Shortcuts, find "Tesserae Shell" in the list of applications and remove it (the remove button of
    its entry).  To put the COPY back if anything looks wrong: stop the shell, log out, and from a
    text console run  cp /tmp/tess-kwin-m6c/backup/kglobalshortcutsrc ~/.config/kglobalshortcutsrc
    then log in (the service rewrites the file while a session runs).  [#needs-verification]
    Keys used, all rare:  {KEY_ONE} (Toggle Launcher) and {KEY_TWO} (Toggle Notes).
 1  /tmp/tess-kwin-m6c/check.sh : every config checks clean ("ok: 1 files checked"; run-taken is
    checked after you write its key).

PART 1: registration  (start with /tmp/tess-kwin-m6c/run.sh; your shell is fish: use $status, not $?)
 2  The log shows "shortcuts: 2 of 2 actions registered" and no WARNING about shortcuts.
 3  System Settings, Shortcuts: a component appears named "Tesserae Shell" (spec question 3: write
    down what you see: its friendly name, or only the id tesserae-shell, or nothing).  It lists two
    rows, "Toggle Launcher" and "Toggle Notes", with the keys {KEY_ONE} and {KEY_TWO}.
 4  Focus any ordinary window (a terminal).  Press {KEY_ONE}: the Launcher panel opens (a primary
    coloured box over the windows) although no shell surface has focus.  Press it again: it closes.
 5  Press {KEY_TWO}: the Notes panel opens at the bottom right; again: it closes.
 6  The commands work too:  tesserae-shell toggle Launcher   (from a terminal; it toggles the same
    panel).
 7  No key press opens a Popup (the Tray_Menu and the like): none does.

PART 2: the user's keys
 8  In System Settings change the key of "Toggle Launcher" to another rare key (for example
    Ctrl+Alt+Shift+F10).  WITHOUT restarting the shell: the new key opens the panel; {KEY_ONE} no
    longer does.
 9  Stop the shell (Ctrl+C) and run.sh again: the key you chose is still the one in System Settings
    (the default {KEY_ONE} did not win back), and it works.
10  Stop the shell: press the key: nothing happens (the action is inactive) and the shell's rows are
    still in System Settings with their keys.  Start it again: the keys work again.

PART 3: a key the desktop owns
11  Stop the shell.  Choose a key a Plasma shortcut already uses (look in System Settings, for
    example the one for Show Desktop).  Run  /tmp/tess-kwin-m6c/run-taken.sh "THAT KEY"  (write
    the key the way System Settings shows it, "Meta+D"): the log has exactly ONE warning naming
    Toggle_Launcher and the key ("is taken by the desktop"); the desktop's own shortcut still does
    what it did; System Settings shows "Toggle Launcher" with no key.  The shell runs.

PART 4: restarts and spellings
12  /tmp/tess-kwin-m6c/run-anycase.sh : the key reads ctrl+ALT+shift+f11 in the file, and System
    Settings shows {KEY_ONE} (the same key as in line 3); it works.
13  With the shell running, restart the shortcut service ONLY:
    systemctl --user restart plasma-kglobalaccel.service   (the unit name may differ:
    systemctl --user list-units | grep -i kglobalaccel; do NOT touch kwin_wayland)
    The log says "shortcuts: org.kde.kglobalaccel is back: registering again", and {KEY_ONE} works
    again with no restart of the shell (the component's rows in System Settings are as before).
    [#needs-verification: whether the unit exists on this session]
14  /tmp/tess-kwin-m6c/run-off.sh : Global_Shortcuts: false.  The log has one INFO line saying
    registration is off; no key works; System Settings gains nothing new.  (Stop first, so the rows
    of the earlier runs are not the proof.)

CLEAN UP
15  Stop the shell; remove "Tesserae Shell" in System Settings, Shortcuts (see line 0); look at
    ~/.config/kglobalshortcutsrc: no [tesserae-shell] group is left.  If anything else changed,
    put the copy back (line 0).
"""

REAL_WARNING = (
    'echo "THIS REGISTERS SHORTCUTS WITH YOUR REAL SHORTCUT SERVICE (kglobalaccel)." >&2\n'
    'echo "Did you run /tmp/tess-kwin-m6c/backup.sh? Ctrl+C within 5 s to stop." >&2\n'
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
        # the taken-key variant is a template: run-taken.sh writes the key you name
        (cfg / ("settings.tdl.in" if folder == "cfg-taken" else "settings.tdl")).write_text(text)
    (root / "checklist.txt").write_text(CHECKLIST)
    state = f"export XDG_STATE_HOME={root}/state\n"
    script(
        root,
        "backup.sh",
        f"mkdir -p {root}/backup\n"
        f"cp -p ~/.config/kglobalshortcutsrc {root}/backup/kglobalshortcutsrc\n"
        f"echo copied ~/.config/kglobalshortcutsrc to {root}/backup/kglobalshortcutsrc\n",
    )
    for name, folder in (
        ("run.sh", "cfg"),
        ("run-anycase.sh", "cfg-anycase"),
        ("run-off.sh", "cfg-off"),
    ):
        script(
            root,
            name,
            state + REAL_WARNING + f"exec {BIN}/tesserae-shell run --config-dir {root / folder}\n",
        )
    script(
        root,
        "run-taken.sh",
        'if [ -z "$1" ]; then echo "usage: run-taken.sh \\"Meta+D\\"  (a key the desktop uses)" >&2;'
        " exit 2; fi\n"
        + state
        + f'sed "s/TAKEN_KEY/$1/" {root}/cfg-taken/settings.tdl.in > {root}/cfg-taken/settings.tdl\n'
        + f"{BIN}/tesserae-shell check --config-dir {root}/cfg-taken || exit 1\n"
        + REAL_WARNING
        + f"exec {BIN}/tesserae-shell run --config-dir {root}/cfg-taken\n",
    )
    script(
        root,
        "check.sh",
        state
        + "".join(
            f"{BIN}/tesserae-shell check --config-dir {root}/{folder}\n"
            for folder in ("cfg", "cfg-anycase", "cfg-off")
        ),
    )


def main() -> None:
    write_kit()
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
