"""Regenerate the launcher kit in /tmp/tess-kwin-launcher (not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_launcher.py``. It writes the kit folder,
made-up desktop entries and a marker script, and starts nothing. Then
``/tmp/tess-kwin-launcher/run-all.sh`` runs every step that needs no person, in PRIVATE sandboxes
(``tests/kitlib.py``): the Launcher Panel is opened, searched and used by KEY EVENTS sent through a
private KWin's own fake input, a global key reaches it through the private KWin's own
``kglobalaccel``, and the shell's real starter (plain and scope branch) starts the marker in a
private systemd user manager. Nothing but the kit's marker script (writes a line, sleeps 20 s) and
a throwaway tre window is started. ``checklist.txt`` holds only what no session can do: a REAL
application's window and your real KWin's focus policy, the look of the Panel, and a real
pointer.

The scripts ``run.sh`` and ``run-key.sh`` start the shell on YOUR session for those lines; they are
not run by anything here. The state directory is ``/tmp/tess-kwin-launcher/state``, never the real
one.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests import kitlib  # noqa: E402
from tests.kitlib import Step  # noqa: E402
from tests.shell_samples import write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-launcher")
# the environment this generator runs in, so that run.sh runs this code (generate the kit from a
# NON-editable install, so removing a worktree cannot break it)
BIN = Path(sys.executable).parent
# tre's own virtual environment has pywayland, which the fake input needs
TRE_PY = str(
    Path(os.environ.get("TRE_DIR", Path.home() / "Projects/rustDev/projects/tre"))
    / ".venv"
    / "bin"
    / "python"
)
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
        # an application with a window: a throwaway tre client (tests/kwin/window_probe.py)
        "tess-window.desktop": entry(
            "Tesserae Launched Window", f'{sys.executable} {root}/window_probe.py "Launched Window"'
        ),
    }


def marker_script(root: Path) -> str:
    return (
        "#!/bin/sh\n"
        f'echo "pid=$$ ppid=$PPID cwd=$(pwd) args=$* token=${{XDG_ACTIVATION_TOKEN:+set}}" '
        f">> {root}/marker.txt\n"
        "exec sleep 20\n"  # the shell script becomes the sleep: one pid to stop
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


REAL_WARNING = (
    'echo "THIS REGISTERS A SHORTCUT WITH YOUR REAL SHORTCUT SERVICE (kglobalaccel)." >&2\n'
    'echo "Did you run /tmp/tess-kwin-m6c/backup.sh? Ctrl+C within 5 s to stop." >&2\n'
    "sleep 5\n"
)

OK = "^PASS "
NO = (r"^FAIL ",)


def steps(root: Path = ROOT) -> list[Step]:
    def drive(name: str) -> str:
        return f'"$PY" drive_launcher.py {name}'

    return [
        Step(
            "1-check",
            "both configs check clean",
            command=(
                '"$BIN" check --config-dir "$KIT/cfg" || exit 1\n'
                '"$BIN" check --config-dir "$KIT/cfg-key"\n'
            ),
            sandbox="bus",
            expect=(r"ok: \d+ files? checked[\s\S]*ok: \d+ files? checked",),
            forbid=("error", "warning"),
        ),
        Step(
            "2-real-start",
            "the shell's real starter starts the marker, plain and in a systemd scope, detached",
            command='"$PY" real_start_check.py',
            sandbox="systemd",
            expect=(r"systemd scope available: True", r"starting plain", r"starting in a scope"),
            forbid=(r"^FAIL",),
            check="""
def check(result):
    verdicts = [ln for ln in result.stdout.splitlines() if ln.startswith(("PASS", "FAIL"))]
    if len(verdicts) != 2 or not all(v.startswith("PASS") for v in verdicts):
        return f"verdicts: {verdicts}"
    return None
""",
        ),
        Step(
            "3-panel",
            "the Launcher by keys only: open, search, move, Escape, start, missing, a window, detach",
            command=drive("panel"),
            sandbox="kwin",
            tools=(TRE_PY,),
            expect=tuple(
                f"{OK}{n} " for n in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16, 17, 18)
            ),
            forbid=NO,
            timeout=300,
        ),
        Step(
            "3b-clickaway",
            "the Launcher closes on a click outside and on nothing else; typing works throughout",
            command=drive("clickaway"),
            sandbox="kwin",
            tools=(TRE_PY,),
            expect=tuple(f"{OK}{n} " for n in range(1, 13)),
            forbid=NO,
            timeout=300,
        ),
        Step(
            "4-key",
            "the Panel from a global key (the private kglobalaccel): opens, takes keys at once, closes",
            command=drive("key"),
            sandbox="kwin",
            tools=(TRE_PY,),
            expect=tuple(f"{OK}{n} " for n in range(1, 9)),
            forbid=NO,
            timeout=300,
        ),
        Step(
            "5-real-application",
            "a REAL application (Dolphin, Kate) started from the Panel opens with the keyboard focus",
            kind="manual",
            reason=(
                "needs a real application and your own KWin focus policy: step 3 starts only the "
                "kit's throwaway window (it becomes the active one) and reports whether a token "
                "was given, but whether KWin focuses a real application's window after a click "
                "or key on your session is your session's behaviour. Do it three times"
            ),
            expect=(
                "run.sh: start Dolphin or Kate: its window opens AND has the keyboard focus without a click",
            ),
        ),
        Step(
            "6-look",
            "the Panel's look: the list, the icons of the rows, Page Down/Up by 8 rows, hover does not move the marking",
            kind="manual",
            reason=(
                "looking at the screen and a real pointer: the keys and the selection are asserted "
                "in step 3, but the icons drawn in your real icon theme, the layout of the rows "
                "and the hover are what the pixels show; [not converted: a hover needs row "
                "coordinates this kit does not compute]"
            ),
            expect=(
                "run.sh, `tesserae-shell toggle Launcher`: each row has the application's icon",
            ),
        ),
        Step(
            "7-real-key",
            f"the Panel from {KEY} with your REAL shortcut service and a real keyboard",
            kind="real-session",
            reason=(
                "step 4 proves the whole path against a private KWin's own kglobalaccel; whether "
                "your real session's service and keyboard deliver the chord (and Ctrl+Alt+Fn is "
                "not a VT switch there) needs your real kglobalaccel"
            ),
            action=(
                "run /tmp/tess-kwin-m6c/backup.sh (copies ~/.config/kglobalshortcutsrc), then "
                f"{root}/run-key.sh (registers {KEY} with your real kglobalaccel), press the key "
                "with an ordinary window focused, then remove 'Tesserae Shell' in System Settings, "
                "Shortcuts"
            ),
        ),
    ]


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
    (root / "marker.txt").unlink(missing_ok=True)
    env = (
        f"export XDG_STATE_HOME={root}/state\n"
        f'export XDG_DATA_DIRS={root}/data:"${{XDG_DATA_DIRS:-/usr/local/share:/usr/share}}"\n'
    )
    files = {
        "bin/marker": marker_script(root),
        "real_start_check.py": real_start_check(root),
        "run.sh": "#!/bin/sh\n"
        + 'echo "This starts the SHELL on your real session (Ctrl+C stops it)." >&2\n'
        + env
        + f"exec {BIN}/tesserae-shell run --config-dir {root}/cfg\n",
        "run-key.sh": "#!/bin/sh\n"
        + env
        + REAL_WARNING
        + f"exec {BIN}/tesserae-shell run --config-dir {root}/cfg-key\n",
    }
    kitlib.write_kit(
        root,
        steps(root),
        title="Launcher kit: keys only on a private KWin, the real starter, a global key",
        intro=(
            "The Panel's keys, search and starts, the global key and the real starter run unattended\n"
            "in private sandboxes; only a real application's focus, the look and your real shortcut\n"
            "service are left."
        ),
        files=files,
        executable=tuple(files),
        variables={"BIN": str(BIN / "tesserae-shell"), "PY": sys.executable, "TRE_PY": TRE_PY},
        support=(
            "kitdrive.py",
            "fake_input_server.py",
            "kwin/drive_launcher.py",
            "kwin/window_probe.py",
        ),
        obsolete=("real-start.sh", "check.sh"),
    )


def main() -> None:
    write_kit()
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
