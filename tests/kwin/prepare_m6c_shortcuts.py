"""Regenerate the M6c global-shortcuts kit in /tmp/tess-kwin-m6c (not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m6c_shortcuts.py``. It writes the kit
folder and starts nothing. Then ``/tmp/tess-kwin-m6c/run-all.sh`` runs every step that needs no
person in a PRIVATE KWin inside a private ``dbus-run-session`` (``tests/kitlib.py``). KWin 6.8.2
hosts the ``org.kde.kglobalaccel`` service itself (there is no ``kglobalacceld`` program on this
machine: ``/usr/lib/libKGlobalAccelD.so`` is a library), so the private KWin IS a real
kglobalaccel: the shell registers its shortcuts with it, a key chord goes through KWin's fake input
like a keyboard's, and the service is asked what it holds as System Settings would. Nothing touches
the real ``kglobalaccel`` or ``~/.config/kglobalshortcutsrc``. ``checklist.txt`` holds only what no
session can do. The scripts that DO use the real service (``run.sh``, ``run-taken.sh``) are for the
lines of the checklist that name them; ``backup.sh`` copies ``kglobalshortcutsrc`` first.
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

ROOT = Path("/tmp/tess-kwin-m6c")
# the environment this generator runs in, so that run.sh runs this code
BIN = Path(sys.executable).parent
# tre's own virtual environment has pywayland, which the fake input needs
TRE_PY = str(
    Path(os.environ.get("TRE_DIR", Path.home() / "Projects/rustDev/projects/tre"))
    / ".venv"
    / "bin"
    / "python"
)
KEY_ONE = "Ctrl+Alt+Shift+F11"
KEY_TWO = "Ctrl+Alt+Shift+F12"
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

OK = "^PASS "
NO = (r"^FAIL ",)


def drive(name: str) -> str:
    return f'"$PY" drive_m6c.py {name}'


def steps() -> list[Step]:
    def auto(step_id: str, title: str, name: str, count: int) -> Step:
        return Step(
            step_id,
            title,
            command=drive(name),
            sandbox="kwin",
            tools=(TRE_PY,),
            expect=tuple(f"{OK}{n} " for n in range(1, count + 1)),
            forbid=NO,
            timeout=300,
        )

    return [
        Step(
            "1-check",
            "every config checks clean",
            command="".join(
                f'"$BIN" check --config-dir "$KIT/{folder}" || exit 1\n'
                for folder in ("cfg", "cfg-anycase", "cfg-off")
            ),
            sandbox="bus",
            expect=(r"(ok: \d+ files? checked[\s\S]*){3}",),
            forbid=("error", "warning"),
        ),
        auto(
            "2-register",
            "registration, the component, the keys open and close the panels",
            "register",
            10,
        ),
        auto(
            "3-user-keys",
            "the user changes and clears a key; restarts; the shell stopped",
            "user-keys",
            11,
        ),
        auto(
            "4-taken",
            "a key the desktop owns: one warning, no key, the desktop keeps its own",
            "taken",
            7,
        ),
        auto(
            "5-anycase",
            "ctrl+ALT+shift+f11 in the file is Ctrl+Alt+Shift+F11 in the service",
            "anycase",
            2,
        ),
        auto("6-off", "Global_Shortcuts: false registers nothing", "off", 3),
        Step(
            "7-system-settings",
            "System Settings lists 'Tesserae Shell' with Toggle Launcher and Toggle Notes and their keys",
            kind="manual",
            reason=(
                "looking at System Settings' own list on a real screen; step 2 asserts the same "
                "data from the service (the component's friendly name 'Tesserae Shell', the two "
                "rows, their keys), which System Settings reads"
            ),
            expect=("run.sh, then System Settings > Shortcuts shows the component with both rows",),
        ),
        Step(
            "8-physical-keys",
            f"pressing {KEY_ONE} and {KEY_TWO} on your keyboard, with an ordinary window focused, opens the panels",
            kind="manual",
            reason=(
                "a physical keyboard and your layout: steps 2 and 3 send the same chord through "
                "KWin's input pipeline, but whether your real keys (and a logind VT switch on "
                "Ctrl+Alt+Fn) deliver it is a hardware fact"
            ),
            expect=(
                "run.sh, a terminal focused: the key opens the Launcher panel; again: it closes",
            ),
        ),
        Step(
            "9-restart-service",
            "restarting the shortcut service with the shell running: 'org.kde.kglobalaccel is back: registering again'",
            kind="manual",
            reason=(
                "no sandbox can restart the service alone: KWin 6.8.2 hosts org.kde.kglobalaccel "
                "inside kwin_wayland, so restarting it is restarting KWin, which ends a Wayland "
                "session (never do it on yours); the shell's reaction to the name leaving and "
                "returning is covered by the suite's fake service (tests/fake_kglobalaccel.py). "
                "On a session where `systemctl --user list-units | grep -i kglobalaccel` shows a "
                "separate unit you may restart that one"
            ),
            expect=(
                "run.sh: after the restart the log says the service is back and the key works",
            ),
        ),
        Step(
            "10-plasma-owned-key",
            "a key a real Plasma shortcut owns (Ctrl+Alt+Del of Log Out) gives the one warning",
            kind="real-session",
            reason=(
                "Log Out belongs to plasma's ksmserver component, which a private KWin does not "
                "run; step 4 asserts the same logic with a key KWin's own component owns (the "
                "shell asks isGlobalShortcutAvailable before it requests a key), so this line only "
                "adds the exact key of your Plasma"
            ),
            action=(
                f"copy ~/.config/kglobalshortcutsrc with {ROOT}/backup.sh, remove 'Tesserae Shell' "
                f'in System Settings, run `{ROOT}/run-taken.sh "Ctrl+Alt+Del"` on your real '
                "session, read the log (one warning naming Toggle_Launcher), stop it, and remove "
                "'Tesserae Shell' again"
            ),
        ),
    ]


def script(root: Path, name: str, text: str) -> None:
    path = root / name
    path.write_text("#!/bin/sh\n" + text)
    path.chmod(0o755)


REAL_WARNING = (
    'echo "THIS REGISTERS SHORTCUTS WITH YOUR REAL SHORTCUT SERVICE (kglobalaccel)." >&2\n'
    'echo "Did you run /tmp/tess-kwin-m6c/backup.sh? Ctrl+C within 5 s to stop." >&2\n'
    "sleep 5\n"
)


def write_kit(root: Path = ROOT) -> None:
    """Write every file of the kit under ``root`` (nothing outside it). Only the scripts for the
    lines of the checklist that need your real session touch it; they start only when you run
    them."""
    root.mkdir(parents=True, exist_ok=True)
    for folder, text in CONFIGS.items():
        cfg = root / folder
        shutil.rmtree(cfg, ignore_errors=True)
        write_example(cfg, SHELL)
        # the taken-key variant is a template: a step (or run-taken.sh) writes the key
        (cfg / ("settings.tdl.in" if folder == "cfg-taken" else "settings.tdl")).write_text(text)
    state = f"export XDG_STATE_HOME={root}/state\n"
    files = {
        "backup.sh": (
            "#!/bin/sh\n"
            f"mkdir -p {root}/backup\n"
            f"cp -p ~/.config/kglobalshortcutsrc {root}/backup/kglobalshortcutsrc\n"
            f"echo copied ~/.config/kglobalshortcutsrc to {root}/backup/kglobalshortcutsrc\n"
        ),
        "run.sh": "#!/bin/sh\n"
        + state
        + REAL_WARNING
        + f"exec {BIN}/tesserae-shell run --config-dir {root}/cfg\n",
        "run-taken.sh": (
            "#!/bin/sh\n"
            'if [ -z "$1" ]; then echo "usage: run-taken.sh \\"Meta+D\\"  (a key the desktop uses)" >&2;'
            " exit 2; fi\n"
            + state
            + f'sed "s/TAKEN_KEY/$1/" {root}/cfg-taken/settings.tdl.in > {root}/cfg-taken/settings.tdl\n'
            + f"{BIN}/tesserae-shell check --config-dir {root}/cfg-taken || exit 1\n"
            + REAL_WARNING
            + f"exec {BIN}/tesserae-shell run --config-dir {root}/cfg-taken\n"
        ),
    }
    kitlib.write_kit(
        root,
        steps(),
        title="M6c kit: global shortcuts with kglobalaccel (a private KWin hosts a real one)",
        intro=(
            "The registration, the keys, a user's change and clearing, a taken key and the off\n"
            "switch run unattended against the private KWin's own kglobalaccel service."
        ),
        files=files,
        executable=tuple(files),
        variables={"BIN": str(BIN / "tesserae-shell"), "PY": sys.executable, "TRE_PY": TRE_PY},
        support=("kitdrive.py", "fake_input_server.py", "kwin/drive_m6c.py"),
        obsolete=("run-anycase.sh", "run-off.sh", "check.sh"),
    )


def main() -> None:
    write_kit()
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
