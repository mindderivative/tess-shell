"""The M6c KWin kit (``tests/kwin/prepare_m6c_shortcuts.py``): its files exist, its configs check
clean, its scripts are well-formed shell and only name the places the checklist says, and the
checklist is one numbered list that starts with the backup. Nothing here RUNS a script of the kit,
starts a shell, or touches ``~/.config/kglobalshortcutsrc`` or any bus: ``sh -n`` only parses."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from tess_shell.schema.keys import parse_chord
from tests.kwin import prepare_m6c_shortcuts as kit

SCRIPTS = (
    "backup.sh",
    "run.sh",
    "run-anycase.sh",
    "run-taken.sh",
    "run-off.sh",
    "check.sh",
)


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
    assert (root / "cfg" / "settings.tdl").is_file()
    assert (root / "cfg-taken" / "settings.tdl.in").is_file()  # a template: the script fills it


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


def test_every_run_script_has_a_private_state_directory_and_a_warning(root: Path) -> None:
    for name in ("run.sh", "run-anycase.sh", "run-taken.sh", "run-off.sh"):
        text = (root / name).read_text()
        assert f"XDG_STATE_HOME={root}/state" in text, name
        assert "REAL SHORTCUT SERVICE" in text and "sleep 5" in text, name
        assert "tesserae-shell run --config-dir" in text
    assert "usage: run-taken.sh" in (root / "run-taken.sh").read_text()


def test_the_checklist_is_one_numbered_list_that_starts_with_the_backup(root: Path) -> None:
    text = (root / "checklist.txt").read_text()
    numbers = [int(m.group(1)) for m in re.finditer(r"^ ?(\d+)  ", text, re.M)]
    assert numbers == list(range(0, 16))
    assert text.index("backup.sh") < text.index("run.sh")  # the copy comes first
    flat = " ".join(text.split())
    assert "THIS CHECK USES YOUR REAL SHORTCUT SERVICE" in flat
    assert 'System Settings, Shortcuts, find "Tesserae Shell"' in flat  # how to remove it
    assert "cp /tmp/tess-kwin-m6c/backup/kglobalshortcutsrc" in flat  # how to put the copy back
    assert "do NOT touch kwin_wayland" in flat and "ends your session" in flat
    for needle in (
        "Tesserae Shell",
        "taken",
        "ctrl+ALT+shift+f11",
        "WITHOUT restarting the shell",
        "plasma-kglobalaccel.service",
        "Global_Shortcuts: false",
        "$status",
    ):
        assert needle in text, needle
    for script in SCRIPTS:
        assert script in text, f"the checklist never names {script}"


def test_the_keys_are_rare_and_every_key_of_every_config_is_a_key_string(root: Path) -> None:
    parse_chord(kit.KEY_ONE)
    parse_chord(kit.KEY_TWO)
    assert parse_chord("ctrl+ALT+shift+f11") == parse_chord(kit.KEY_ONE)  # the any-case variant
    for folder in ("cfg", "cfg-anycase", "cfg-off"):
        text = (root / folder / "settings.tdl").read_text()
        keys = re.findall(r'Toggle_\w+: "([^"]+)"', text)
        assert len(keys) == 2
        for key in keys:
            parse_chord(key)
    assert "Global_Shortcuts: false" in (root / "cfg-off" / "settings.tdl").read_text()


@pytest.mark.parametrize("folder", ["cfg", "cfg-anycase", "cfg-off", "cfg-taken"])
def test_each_config_checks_clean(root: Path, tmp_path: Path, folder: str) -> None:
    cfg = root / folder
    if folder == "cfg-taken":  # what run-taken.sh does with the key the maintainer names
        text = (cfg / "settings.tdl.in").read_text().replace("TAKEN_KEY", "Meta+D")
        (cfg / "settings.tdl").write_text(text)
    done = subprocess.run(
        [sys.executable, "-m", "tess_shell", "check", "--config-dir", str(cfg)],
        capture_output=True,
        text=True,
        env={"XDG_STATE_HOME": str(tmp_path / "state"), "PATH": "/usr/bin:/bin"},
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "warning" not in done.stderr and "error" not in done.stderr
