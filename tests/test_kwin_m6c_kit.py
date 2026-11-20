"""The M6c KWin kit (``tests/kwin/prepare_m6c_shortcuts.py``): its files exist, its configs check
clean, the unattended steps run in a private KWin (which hosts a real ``kglobalaccel`` of its own)
and touch no real file, the scripts that DO use the real service say so and are only parsed here,
and the checklist keeps only what no session can do. With ``kwin_wayland`` and tre's virtual
environment installed the whole kit runs end to end. Nothing here touches
``~/.config/kglobalshortcutsrc``."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tess_shell.schema.keys import parse_chord
from tests.kwin import prepare_m6c_shortcuts as kit

AUTO = ["1-check", "2-register", "3-user-keys", "4-taken", "5-anycase", "6-off"]
MANUAL = ["7-system-settings", "8-physical-keys", "9-restart-service"]
REAL = ["10-plasma-owned-key"]
SCRIPTS = ("backup.sh", "run.sh", "run-taken.sh")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    kit.write_kit(tmp_path / "kit")
    return tmp_path / "kit"


def test_every_file_of_the_kit_exists(root: Path) -> None:
    for name in (*SCRIPTS, "checklist.txt", "kit_runner.py", "run-all.sh", "drive_m6c.py"):
        assert (root / name).is_file(), name
    for name in (*SCRIPTS, "run-all.sh"):
        assert os.access(root / name, os.X_OK), f"{name} is not executable"
    for folder in kit.CONFIGS:
        assert (root / folder / "Shells" / "Main_Shell.tdl").is_file()
    assert (root / "cfg" / "settings.tdl").is_file()
    assert (root / "cfg-taken" / "settings.tdl.in").is_file()  # a template: a step fills it


def test_the_steps_are_six_unattended_three_manual_and_one_for_the_real_session() -> None:
    steps = kit.steps()
    assert [s.id for s in steps if s.kind == "auto"] == AUTO
    assert [s.id for s in steps if s.kind == "manual"] == MANUAL
    assert [s.id for s in steps if s.kind == "real-session"] == REAL
    (real,) = [s for s in steps if s.kind == "real-session"]
    assert "run-taken.sh" in real.action and "backup.sh" in real.action


def test_the_unattended_steps_run_in_a_sandbox_and_name_no_real_file() -> None:
    for step in kit.steps():
        if step.kind != "auto":
            continue
        assert step.sandbox in ("bus", "kwin"), step.id
        assert not re.search(r"\$HOME|~/|/home/|kglobalshortcutsrc", step.command_text()), step.id


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


def test_the_scripts_that_use_the_real_service_have_a_private_state_and_a_warning(
    root: Path,
) -> None:
    for name in ("run.sh", "run-taken.sh"):
        text = (root / name).read_text()
        assert f"XDG_STATE_HOME={root}/state" in text, name
        assert "REAL SHORTCUT SERVICE" in text and "sleep 5" in text, name
        assert "tesserae-shell run --config-dir" in text
    assert "usage: run-taken.sh" in (root / "run-taken.sh").read_text()


def test_the_checklist_keeps_only_what_no_session_can_do(root: Path) -> None:
    text = (root / "checklist.txt").read_text()
    assert f"{len(AUTO)} steps run unattended" in text and "results.txt" in text
    for step_id in (*MANUAL, *REAL):
        assert re.search(rf"^{step_id}  \[", text, re.M), step_id
    for step_id in AUTO:
        assert f"{step_id}  [" not in text
    assert "kwin_wayland, so restarting it is restarting KWin" in " ".join(text.split())
    assert "exact action (ask permission first)" in text


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


def test_the_driver_keys_are_the_keys_of_the_configs() -> None:
    """``drive_m6c.py`` writes the Qt codes of the two keys itself: they must be the file's."""
    source = (Path(__file__).parent / "kwin" / "drive_m6c.py").read_text()
    names = {
        "CTRL": 0x04000000,
        "ALT": 0x08000000,
        "SHIFT": 0x02000000,
        "F11": 0x0100003A,
        "F12": 0x0100003B,
    }
    for constant, key in (("KEY_ONE", kit.KEY_ONE), ("KEY_TWO", kit.KEY_TWO)):
        found = re.search(rf"^{constant} = (.+)$", source, re.M)
        assert found is not None
        assert eval(found.group(1), names) == parse_chord(key).qt  # noqa: S307 - the driver's own constants


@pytest.mark.parametrize("folder", ["cfg", "cfg-anycase", "cfg-off", "cfg-taken"])
def test_each_config_checks_clean(root: Path, tmp_path: Path, folder: str) -> None:
    cfg = root / folder
    if folder == "cfg-taken":  # what a step does with the key it picks
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


@pytest.mark.skipif(
    not (
        shutil.which("kwin_wayland")
        and shutil.which("dbus-run-session")
        and shutil.which("gdbus")
        and Path(kit.TRE_PY).exists()
    ),
    reason="needs kwin_wayland, dbus-run-session, gdbus and tre's virtual environment (pywayland)",
)
def test_the_whole_kit_runs_in_a_private_kwin_and_every_unattended_step_passes(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "kit"
    kit.write_kit(folder)
    done = subprocess.run(
        [str(folder / "run-all.sh")], capture_output=True, text=True, timeout=900, cwd="/"
    )
    summary = (folder / "results.txt").read_text()
    assert done.returncode == 0, done.stdout + done.stderr + summary
    for step_id in AUTO:
        assert re.search(rf"^PASS  {step_id}  ", summary, re.M), summary
    assert re.search(r"^PASS  cleanup", summary, re.M)
