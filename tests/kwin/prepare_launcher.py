"""Regenerate the launcher KWin check in /tmp/tess-kwin-launcher (not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_launcher.py``. It writes scratch configs,
made-up desktop entries and scripts under ``/tmp/tess-kwin-launcher`` and starts nothing, reads
nothing and touches nothing outside that folder. The checks are the ones only a real KWin session can
answer (Applications Module > Questions After Testing): a REAL application started from the launcher,
whether its window takes the focus (the activation token), whether the Panel gets the keyboard when
it opens from a key, and that a started application outlives the shell.

* ``run.sh``: the shell on your real session with the shipped ``Launcher`` Panel and NO global
  shortcut (``Global_Shortcuts: false``): open it with ``tesserae-shell toggle Launcher`` (from a
  terminal, or bind that command to any key in System Settings). The kit's made-up applications are
  added to the list (``XDG_DATA_DIRS`` gets the kit's folder in front), so your real ones are there
  too: this is the check of a real start.
* ``run-key.sh``: the same with ``Toggle_Launcher: Ctrl+Alt+Shift+F9`` registered with your REAL
  ``org.kde.kglobalaccel`` (it writes to ``~/.config/kglobalshortcutsrc``: the M6c kit's
  ``backup.sh`` and its clean-up lines apply; this is the check of "the Panel gets the keyboard
  after a global key").
* ``real-start.sh``: starts the kit's marker script through the shell's own starter, the plain and
  the scope branch, OUTSIDE the test suite (where the real starter is allowed), and checks the
  marker file and that the process is not a child of the checker. Nothing but the marker (a shell
  script that writes a line and sleeps 20 s) is started.
* ``check.sh``: ``tesserae-shell check`` on each config. ``checklist.txt``: every line to check.

The state directory is ``/tmp/tess-kwin-launcher/state``, never the real one (so the start counts of
the check do not rank your real launcher).
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.shell_samples import write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-launcher")
# the environment this generator runs in, so that run.sh runs this code (generate the kit from a
# NON-editable install, so removing a worktree cannot break it)
BIN = Path(sys.executable).parent
KEY = "Ctrl+Alt+Shift+F9"
HEAD = "---\nTDL: 0.2\nName: Settings\n---\n"
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
        }
    }
}
"""


def settings(extra: str = "") -> str:
    # the shell file writes no Panel: the Shortcuts entry names Launcher, so the shell brings the
    # shipped one (a registration with the desktop is off unless the config turns it on)
    return (
        f"{HEAD}Settings {{\n  Logging {{ Level: DEBUG }}\n{extra}"
        f'  Shortcuts {{ Toggle_Launcher: "{KEY}" }}\n}}\n'
    )


CONFIGS: dict[str, str] = {
    "cfg": settings("  Global_Shortcuts: false\n"),
    "cfg-key": settings(),
}


def entry(name: str, exec_line: str, **keys: str) -> str:
    lines = ["[Desktop Entry]", "Type=Application", f"Name={name}", f"Exec={exec_line}"]
    lines += [f"{k}={v}" for k, v in keys.items()]
    return "\n".join(lines) + "\n"


def entries(root: Path) -> dict[str, str]:
    marker = f"{root}/bin/marker"
    return {
        "tess-marker.desktop": entry(
            "Tesserae Marker",
            f"{marker} %U",
            Comment="Writes a line and sleeps",
            Path=f"{root}/work",
        ),
        "tess-marker-hidden.desktop": entry("Tesserae Hidden Marker", marker, NoDisplay="true"),
        "tess-marker-terminal.desktop": entry(
            "Tesserae Terminal Marker", marker, Terminal="true", GenericName="Terminal test"
        ),
        "tess-marker-gone.desktop": entry(
            "Tesserae Missing Program", "/nonexistent/tess-no-such-program"
        ),
    }


def marker_script(root: Path) -> str:
    return (
        "#!/bin/sh\n"
        f'echo "pid=$$ ppid=$PPID cwd=$(pwd) args=$* token=${{XDG_ACTIVATION_TOKEN:+set}}" '
        f">> {root}/marker.txt\n"
        "sleep 20\n"
    )


def real_start_check(root: Path) -> str:
    return f'''"""Start the kit's marker through the shell's own starter, outside pytest (written by
tests/kwin/prepare_launcher.py)."""

import os
import sys
import time
from pathlib import Path

from tess_shell.services.apps import SystemRunner, build_command
from tess_shell.services.desktop_entries import parse_entry

ROOT = Path({str(root)!r})
MARKER = ROOT / "marker.txt"


def main() -> int:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        print("not under pytest: the real starter refuses there")
        return 2
    path = ROOT / "data" / "applications" / "tess-marker.desktop"
    entry = parse_entry(path.read_text(), path.name, path)
    runner = SystemRunner()
    branches = [False] + ([True] if runner.scope_available() else [])
    print("systemd scope available:", runner.scope_available())
    failed = 0
    for scope in branches:
        MARKER.unlink(missing_ok=True)
        spec = build_command(entry, runner, os.environ, str(Path.home()), "kit-token", scope)
        print("starting", "in a scope" if scope else "plain", spec.argv)
        runner.spawn(spec)
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not MARKER.exists():
            time.sleep(0.05)
        if not MARKER.exists():
            print("FAIL: the marker file never appeared")
            failed += 1
            continue
        line = MARKER.read_text().strip()
        print("marker:", line)
        fields = dict(part.split("=", 1) for part in line.split(" ") if "=" in part)
        pid = int(fields["pid"])
        parent = int(Path(f"/proc/{{pid}}/stat").read_text().rsplit(")", 1)[1].split()[1])
        ok = parent != os.getpid() and fields["cwd"] == str(ROOT / "work")
        ok = ok and fields.get("token") == "set"
        print("PASS" if ok else "FAIL", f"(parent {{parent}}, this process {{os.getpid()}})")
        failed += 0 if ok else 1
        os.kill(pid, 15)
    return 1 if failed else 0


sys.exit(main())
'''


def checklist(root: Path) -> str:
    return f"""Launcher (M6d) on KWin: one list, every line to run.  Nothing here touches your files outside
{root}.  The shell uses a state folder of its own ({root}/state), so the start counts of this check
do not rank your real launcher.  Your shell is fish: use $status, not $?.

SETUP
 0  {root}/check.sh : every config checks clean.  {root}/real-start.sh : both branches print PASS (the
    marker appeared, its working folder is {root}/work, the token the check passed is in its
    environment, and its parent is NOT the checker: the start is detached).  This line needs no desktop.

PART 1: open it, search, start  (start {root}/run.sh; it has no global shortcut)
 1  In a terminal:  tesserae-shell toggle Launcher   The Panel opens in the middle of the screen
    over the windows, the text field has the keyboard AT ONCE: type "mark" with no click first.
    [spec question 2: does KWin hand keyboard focus to the Panel?  Write down: yes, or no, or only
    after a click.  The shell asks for the keyboard EXCLUSIVE while the Panel is open.]
 2  The list shows "Tesserae Marker" first.  "Tesserae Hidden Marker" (NoDisplay) is NOT there.
    "Tesserae Terminal Marker" is there.  Down and Up move the marking, which wraps; Page Down and
    Page Up move by the rows shown (8); Home and End still move the caret in the field.  Hovering a
    row with the pointer does not move the marking.  Each row has the application's icon.
 3  Escape with text clears the field and keeps the Panel; Escape again hides it.  Open it again:
    the text you left is selected (typing replaces it).  Open it, type "zzz": the list says
    "No results".
 4  Type "marker", select "Tesserae Marker" and press Enter: the Panel hides at once, no window shows
    (the marker is a script), and {root}/marker.txt has a line:  cwd={root}/work  and, if the Panel
    gave a token, token=set.  [what a token of None means: see line 7]
 5  Open the Panel and click a row with the pointer: it starts and the Panel hides.  Open it,
    type "Missing": Enter: the Panel stays open and says "Could not start Tesserae Missing Program"
    under the list; the shell log has one WARNING naming the entry.  Typing again clears the text.
 6  "Tesserae Terminal Marker": with xdg-terminal-exec installed it starts in a terminal; without it
    the Panel says "Could not start ..." and the log has one warning naming xdg-terminal-exec.

PART 2: a REAL application, and focus  (spec question 1)
 7  Open the Panel and start an application you have with a window (for example Dolphin or Kate):
    its window opens AND has the keyboard focus (the cursor is in it, or its title is lit) without
    a click.  Do it three times.  Write down: focused / opened behind or unfocused / KWin showed
    "demands attention".  Then read the shell log:  "activation token: received for <id>" means the
    Panel's window gave a token (xdg_activation_v1); "activation token: none for <id>: launching
    without one" means the engine had none to give (the compositor did not offer the protocol,
    the window was not open, or the request failed): the application still starts, and KWin
    may open its window without focus or only mark it.  If lines show 'none' in this session, write
    down which of the two you saw.
 8  Start the same application with the Panel opened from a global key (PART 4) and compare with
    line 7: a token is asked inside the key or click that starts the application, so both should
    give the same result.

PART 3: detached, and the scope
 9  Start Tesserae Marker (line 4).  In a terminal:  systemctl --user list-units --type=scope | grep
    app-tess-marker   shows  app-tess-marker-XXXXXXXX.scope  while the marker sleeps (20 s).  Then
    stop the shell (Ctrl+C) while a marker still sleeps: the marker keeps running (ps shows it, its
    parent is not the shell).  [with no systemd user manager the start is plain and the line only
    asks that the marker survives]
10  Start an application with a long life (Kate), stop the shell, and the application stays.  Start
    the shell again (run.sh): the application is still there and the Panel lists it first (counts
    live in {root}/state/tesserae-shell/launcher-counts.json: a JSON object of ids and counts).

PART 4: the Panel from a global key  (spec question 2; THIS USES YOUR REAL SHORTCUT SERVICE)
11  The M6c kit's backup comes first:  /tmp/tess-kwin-m6c/backup.sh  (it only copies
    ~/.config/kglobalshortcutsrc; regenerate that kit if it is gone).  Stop run.sh.  Start
    {root}/run-key.sh : the log shows  "shortcuts: 1 of 1 actions registered".
12  Focus any ordinary window (a terminal).  Press {KEY}: the Panel opens although no shell surface
    had focus, and you can type at once (line 1 again, now from a key: the case the spec asks).
    Press {KEY} again: it closes.  Open it and press Escape twice: it closes.  Open it from the key
    and start an application (line 7 again): focus.
13  Clean up as the M6c kit says (System Settings, Shortcuts, remove "Tesserae Shell") and stop the
    shell.

PART 5: what is not built, so you know what you see
14  A click OUTSIDE the Panel does not hide it (the Panel has the keyboard EXCLUSIVE: the compositor
    tells a layer surface nothing about clicks elsewhere).  Escape or the key hides it.  Write down
    whether you want it (design gap 1 of the report: ON_DEMAND plus a hide when the keyboard goes).
15  Desktop actions of an entry (a "New window" item), categories and a grid are not in v1.
"""


def script(root: Path, name: str, text: str) -> None:
    path = root / name
    path.write_text("#!/bin/sh\n" + text)
    path.chmod(0o755)


REAL_WARNING = (
    'echo "THIS REGISTERS A SHORTCUT WITH YOUR REAL SHORTCUT SERVICE (kglobalaccel)." >&2\n'
    'echo "Did you run /tmp/tess-kwin-m6c/backup.sh? Ctrl+C within 5 s to stop." >&2\n'
    "sleep 5\n"
)


def write_kit(root: Path = ROOT) -> None:
    """Write every file of the kit under ``root`` (nothing outside it)."""
    root.mkdir(parents=True, exist_ok=True)
    for folder, text in CONFIGS.items():
        cfg = root / folder
        shutil.rmtree(cfg, ignore_errors=True)
        write_example(cfg, SHELL)
        (cfg / "settings.tdl").write_text(text)
    apps = root / "data" / "applications"
    shutil.rmtree(root / "data", ignore_errors=True)
    apps.mkdir(parents=True)
    for name, text in entries(root).items():
        (apps / name).write_text(text)
    (root / "work").mkdir(exist_ok=True)
    (root / "bin").mkdir(exist_ok=True)
    marker = root / "bin" / "marker"
    marker.write_text(marker_script(root))
    marker.chmod(0o755)
    (root / "real_start_check.py").write_text(real_start_check(root))
    (root / "checklist.txt").write_text(checklist(root))
    env = (
        f"export XDG_STATE_HOME={root}/state\n"
        f'export XDG_DATA_DIRS={root}/data:"${{XDG_DATA_DIRS:-/usr/local/share:/usr/share}}"\n'
    )
    script(root, "run.sh", env + f"exec {BIN}/tesserae-shell run --config-dir {root}/cfg\n")
    script(
        root,
        "run-key.sh",
        env + REAL_WARNING + f"exec {BIN}/tesserae-shell run --config-dir {root}/cfg-key\n",
    )
    script(root, "real-start.sh", f"{BIN}/python {root}/real_start_check.py\n")
    script(
        root,
        "check.sh",
        env
        + "".join(
            f"{BIN}/tesserae-shell check --config-dir {root}/{folder}\n" for folder in CONFIGS
        ),
    )


def main() -> None:
    write_kit()
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
