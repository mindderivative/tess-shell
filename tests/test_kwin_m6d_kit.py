"""The M6d KWin kit (``tests/kwin/prepare_m6d_mode.py``): its files exist, its configs check clean,
its scripts are well-formed shell and only name the places the checklist says, and the checklist is
one numbered list that starts with the backup. Nothing here RUNS a script of the kit, starts a
shell, or touches ``~/.config/kglobalshortcutsrc`` or any bus: ``sh -n`` only parses, ``check``
only reads."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from tess_shell.config.settings import load_settings
from tess_shell.schema.keys import parse_chord
from tests.kwin import prepare_m6d_mode as kit

SCRIPTS = ("backup.sh", "run.sh", "run-ondemand.sh", "check.sh")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    kit.write_kit(tmp_path / "kit")
    return tmp_path / "kit"


def test_every_file_of_the_kit_exists(root: Path) -> None:
    for name in (*SCRIPTS, "checklist.txt"):
        assert (root / name).is_file(), name
    for name in SCRIPTS:
        assert (root / name).stat().st_mode & 0o111, f"{name} is not executable"
    for folder in kit.CONFIGS:
        assert (root / folder / "Shells" / "Main_Shell.tdl").is_file()
        assert (root / folder / "settings.tdl").is_file()


@pytest.mark.parametrize("name", SCRIPTS)
def test_each_script_is_well_formed_shell_without_being_run(root: Path, name: str) -> None:
    done = subprocess.run(["sh", "-n", str(root / name)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert (root / name).read_text().startswith("#!/bin/sh\n")


def test_a_script_writes_only_inside_the_kits_folder_and_touches_no_kde_tool(root: Path) -> None:
    for name in SCRIPTS:
        text = (root / name).read_text()
        for tool in ("kwriteconfig", "kbuildsycoca", "kquitapp", "busctl", "dbus-send"):
            assert tool not in text, (name, tool)
        assert not re.search(r"\b(rm|mv)\b", text), name
        for target in re.findall(r">\s*(\S+)", text.replace(">&2", "")):
            assert target.startswith(str(root)), (name, target)
        if name != "backup.sh":
            assert "kglobalshortcutsrc" not in text  # only the backup script names the real file
    backup = (root / "backup.sh").read_text()
    assert "cp -p ~/.config/kglobalshortcutsrc" in backup
    assert f"{root}/backup/kglobalshortcutsrc" in backup  # the copy goes to the kit's folder


def test_the_run_scripts_use_the_main_venv_a_private_state_directory_and_warn(root: Path) -> None:
    for name in ("run.sh", "run-ondemand.sh"):
        text = (root / name).read_text()
        assert f"XDG_STATE_HOME={root}/state" in text, name
        assert "REAL SHORTCUT SERVICE" in text and "sleep 5" in text, name
        assert (
            f"exec {Path.home()}/Projects/pyDev/pyEnvs/tess-shell/bin/tesserae-shell run "
            f"--config-dir {root}/" in text
        )


def test_the_checklist_is_one_numbered_list_that_starts_with_the_backup(root: Path) -> None:
    text = (root / "checklist.txt").read_text()
    numbers = [int(m.group(1)) for m in re.finditer(r"^ ?(\d+)  ", text, re.M)]
    assert numbers == list(range(0, 15))
    assert text.index("backup.sh") < text.index("run.sh")  # the copy comes first
    flat = " ".join(text.split())
    assert "THIS CHECK USES YOUR REAL SHORTCUT SERVICE" in flat
    assert 'System Settings, Shortcuts, find "Tesserae Shell"' in flat  # how to remove it
    assert "cp /tmp/tess-kwin-m6d/backup/kglobalshortcutsrc" in flat  # how to put the copy back
    assert "Do NOT restart kwin_wayland" in flat and "ends your session" in flat
    for needle in (
        "Tesserae Shell",
        "Mode_Keyboard: ON_DEMAND",
        "key Tab -> Next_Focus",
        "Escape",
        "SPEC QUESTION 2",
        "polite status",
        "$status",
    ):
        assert needle in text, needle
    for script in SCRIPTS:
        assert script in text, f"the checklist never names {script}"


def test_the_enter_key_is_rare_and_every_key_of_every_config_is_a_key_string(root: Path) -> None:
    enter = parse_chord(kit.KEY_ENTER)
    for folder in kit.CONFIGS:
        text = (root / folder / "settings.tdl").read_text()
        keys = dict(re.findall(r'(\w+): "([^"]+)"', text))
        assert set(keys) == {
            "Enter_Shortcut_Mode",
            "Exit_Shortcut_Mode",
            "Set_Shortcut_Mode",
            "Next_Focus",
            "Previous_Focus",
        }
        chords = {name: parse_chord(key) for name, key in keys.items()}
        assert chords["Enter_Shortcut_Mode"] == enter
        assert len(set(chords.values())) == 5  # no key twice


def test_the_ondemand_config_differs_from_the_other_by_the_one_debug_key(root: Path) -> None:
    plain = (root / "cfg" / "settings.tdl").read_text()
    on_demand = (root / "cfg-ondemand" / "settings.tdl").read_text()
    assert "Mode_Keyboard" not in plain
    assert on_demand.replace("  Debug { Mode_Keyboard: ON_DEMAND }\n", "") == plain
    settings, findings = load_settings(root / "cfg-ondemand")
    assert findings == [] and settings is not None and settings.debug.mode_keyboard == "ON_DEMAND"
    settings, _ = load_settings(root / "cfg")
    assert settings is not None and settings.debug.mode_keyboard == "EXCLUSIVE"


@pytest.mark.parametrize("folder", list(kit.CONFIGS))
def test_each_config_checks_clean(root: Path, tmp_path: Path, folder: str) -> None:
    done = subprocess.run(
        [sys.executable, "-m", "tess_shell", "check", "--config-dir", str(root / folder)],
        capture_output=True,
        text=True,
        env={"XDG_STATE_HOME": str(tmp_path / "state"), "PATH": "/usr/bin:/bin"},
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "warning" not in done.stderr and "error" not in done.stderr


def test_the_shell_of_the_kit_has_what_the_checklist_walks_through(root: Path) -> None:
    from tess_shell.scanner import scan
    from tess_shell.surfaces.focus import surface_order
    from tess_shell.surfaces.mode_driver import lowest_surface

    settings, findings = load_settings(root / "cfg")
    assert settings is not None and settings.main_shell_path is not None, findings
    result = scan(settings, root / "cfg")
    assert not [f for f in result.findings if f.severity == "error"], result.findings
    shell = result.shells[settings.main_shell_path]
    order = surface_order(shell)
    # the checklist says: Frame, Notes, Dock, Top_Bar, the strip (Tab_Index 1 to 5), round
    assert order == ["Screen_Frame", "Notes", "Dock", "Top_Bar", "Screen_Frame.top"]
    assert lowest_surface(shell, order) == "Screen_Frame"
    frame = shell.monitors[0].frames[0]
    assert frame.edges["top"].peek is not None and frame.melds and frame.melds[0].peek is not None
