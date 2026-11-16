"""Regenerate the M5g KWin kit in /tmp/tess-kwin-m5g (not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m5g_kwin.py``. It writes the kit folder
and starts nothing. Then ``/tmp/tess-kwin-m5g/run-all.sh`` runs every step that needs no person in
a PRIVATE KWin (its own kwinrc, kwinrulesrc and script folder) inside a private ``dbus-run-session``
(``tests/kitlib.py``) and writes ``results.txt``: the names the code could only confirm from KWin's
files (``/Scripting``), the shell's script loaded in mode R with a window list that follows open,
retitle, activate, minimise, un-minimise, close and fullscreen of a client window, ``KWin { Script:
OFF }``, the ``kwin script`` and ``kwin rule`` commands, and an answer to whether the layer rule
applies to a layer-shell surface. The suite never loads anything into a real KWin and neither does
this kit; ``checklist.txt`` holds only what a session cannot do.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests import kitlib  # noqa: E402
from tests.kitlib import Step  # noqa: E402

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
                        Children { Workspaces { } Tasks { } Clock { } WinLog { } }
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

WINLOG_TDL = """---
TDL: 0.2
Name: WinLog
---

# A test module: a 4 px block; its Python half logs the window list the shell's KWin script sends.
Module { Rectangle { Width: 4, Height: 4, Fill: "#00ff00" } }
"""

WINLOG_PY = """import json

from tess_shell import Module


class WinLog(Module):
    def start(self):
        self.sub = self.ctx.windows.on_changed(self.changed)

    def changed(self):
        rows = [
            {
                "id": w.id,
                "title": w.title,
                "app": w.app,
                "active": w.active,
                "minimized": w.minimized,
                "output": w.output,
                "desktops": list(w.desktops),
            }
            for w in self.ctx.windows.list()
        ]
        self.ctx.log.info("winlog: " + json.dumps(rows))
"""

OK = "^PASS "
NO = (r"^FAIL ",)


def drive(name: str) -> str:
    return f'"$PY" drive_m5g.py {name}'


def steps() -> list[Step]:
    def auto(
        step_id: str, title: str, name: str, expect: tuple[int, ...], timeout: float = 300.0
    ) -> Step:
        return Step(
            step_id,
            title,
            command=drive(name),
            sandbox="kwin",
            expect=tuple(f"{OK}{n} " for n in expect),
            forbid=NO,
            timeout=timeout,
        )

    return [
        Step(
            "1-check",
            "tesserae-shell check on both configs",
            command=(
                '"$BIN" check --config-dir "$KIT/cfg" || exit 1\n'
                '"$BIN" check --config-dir "$KIT/cfg-off"\n'
            ),
            sandbox="bus",
            expect=(r"ok: \d+ files? checked[\s\S]*ok: \d+ files? checked",),
            forbid=("error", "warning"),
        ),
        auto(
            "2-introspect",
            "the names the code could only confirm from KWin's files",
            "introspect",
            (1, 2, 3, 4, 6),
        ),
        auto(
            "3-script",
            "mode R: load, window list, actions, fullscreen, unload",
            "script",
            tuple(range(1, 18)),
        ),
        auto(
            "4-off", "KWin { Script: OFF } loads nothing and hides nothing", "off", (1, 2, 3, 4, 5)
        ),
        auto(
            "5-commands",
            "kwin script install/status/remove and kwin rule show/install/remove",
            "commands",
            (1, 2, 3, 4, 5, 6, 7, 8, 9, 10),
        ),
        auto(
            "6-layer-rule",
            "does the layer rule apply to a layer-shell surface?",
            "layer",
            (1, 2, 3, 4),
        ),
        Step(
            "7-icons",
            "the application icons match the applications, and follow the icon theme",
            kind="manual",
            reason=(
                "looking at the screen: the icons of real applications drawn in your real icon theme "
                "(System Settings, Appearance); a private KWin has neither your applications nor your "
                "theme"
            ),
            expect=(
                "run run.sh: each button shows the application's icon; change the icon theme: the icons change",
            ),
        ),
        Step(
            "8-click-latency",
            "a click on a task button reacts in under 100 ms; middle click closes; the wheel cycles",
            kind="manual",
            reason=(
                "a person's click and eye: the actions themselves (activate, minimise, close, cycle) "
                "run in step 3 through `tesserae-shell call Tasks ...`, but the pointer route from a "
                "button to the action and the felt latency need a real pointer on your real bar; "
                "[not converted: the private KWin's fake input could click a button once its "
                "position is known, which this kit does not compute]"
            ),
            expect=("run.sh: click an inactive window's button: it activates in under 100 ms",),
        ),
        Step(
            "9-monitors-desktops",
            "windows of another desktop are hidden from the row; on two monitors each bar shows its own",
            kind="manual",
            reason=(
                "needs your real virtual desktops and two real monitors; [not converted: a private "
                "KWin can have virtual desktops and a second virtual output, but moving a window to "
                "another desktop and a two-output Tasks check are not built in this kit]"
            ),
            expect=("run.sh: a window on another desktop is not in the row (desktop: CURRENT)",),
        ),
        Step(
            "10-rule-in-system-settings",
            "the rule written by `kwin rule install` equals the one System Settings writes",
            kind="manual",
            reason=(
                "needs the System Settings Window Rules dialog of your real Plasma to make the rule "
                "by hand; step 5 asserts every key the code writes, but not that KWin's own dialog "
                "writes the same ones"
            ),
            expect=(
                "create the same rule in System Settings and compare with `tesserae-shell kwin rule show`",
            ),
        ),
        Step(
            "11-above-plasma-panel",
            "a bar's windows sit above a Plasma panel",
            kind="manual",
            reason=(
                "needs a real Plasma panel (plasmashell) on your real session: the private KWin runs "
                "none; step 6 reports what the rule does to a layer-shell surface"
            ),
            expect=("run.sh with the rule installed: the bar is above the panel",),
        ),
    ]


def write_config(cfg: Path, text: str) -> None:
    shutil.rmtree(cfg, ignore_errors=True)
    (cfg / "Shells").mkdir(parents=True)
    (cfg / "settings.tdl").write_text(text)
    (cfg / "Shells" / "Main_Shell.tdl").write_text(SHELL_HEAD + SHELL)
    module = cfg / "Modules" / "WinLog"
    module.mkdir(parents=True)
    (module / "WinLog_Module.tdl").write_text(WINLOG_TDL)
    (module / "WinLog_Module.py").write_text(WINLOG_PY)


def write_kit(root: Path = ROOT) -> None:
    """Write every file of the kit under ``root``. The folder's ``backup`` (a copy of the
    maintainer's kwinrc and kwinrulesrc from the earlier kit) is never touched."""
    root.mkdir(parents=True, exist_ok=True)
    for child in root.iterdir():
        if child.name == "backup":
            continue  # the maintainer's copy of kwinrc and kwinrulesrc: never deleted
        if child.name in CONFIGS or child.name == "state":
            shutil.rmtree(child, ignore_errors=True)
    for name, text in CONFIGS.items():
        write_config(root / name, text)
    run_sh = (
        "#!/bin/sh\n"
        'echo "This starts the SHELL on your real session (Ctrl+C stops it). It loads its script into'
        ' your real KWin." >&2\n'
        'echo "Did you copy ~/.config/kwinrc and ~/.config/kwinrulesrc first? Ctrl+C within 5 s." >&2\n'
        "sleep 5\n"
        f"XDG_STATE_HOME={root}/state exec {BIN}/tesserae-shell run --config-dir {root}/cfg\n"
    )
    kitlib.write_kit(
        root,
        steps(),
        title="M5g kit: the shell's KWin script, the Tasks list, fullscreen, the kwin commands",
        intro="Everything the shell does to KWin is exercised in a private KWin; nothing loads in your own.",
        files={"run.sh": run_sh},
        executable=("run.sh",),
        variables={"BIN": str(BIN / "tesserae-shell"), "PY": sys.executable},
        support=("kitdrive.py", "kwin/drive_m5g.py", "kwin/window_probe.py"),
        obsolete=("introspect.sh", "backup.sh", "run-off.sh"),
    )


def main() -> None:
    write_kit()
    print(f"wrote {ROOT}: run {ROOT}/run-all.sh, then read results.txt and checklist.txt")


if __name__ == "__main__":
    main()
