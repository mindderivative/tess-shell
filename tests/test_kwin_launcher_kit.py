"""The launcher kit (``tests/kwin/prepare_launcher.py``): its files exist, its configs check clean,
its desktop entries read as the index reads them, the unattended steps run in private sandboxes
and name no real folder, the scripts for the real session are only parsed here, and the checklist
keeps only what no session can do. With ``kwin_wayland``, the systemd user manager and tre's virtual
environment installed the whole kit runs end to end. Nothing here starts the marker or touches
``~/.config`` or the real bus."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tess_shell.schema.keys import parse_chord
from tess_shell.services.desktop_entries import ApplicationIndex
from tests import kitlib
from tests.kwin import prepare_launcher as kit

AUTO = ["1-check", "2-real-start", "3-panel", "3b-clickaway", "4-key"]
MANUAL = ["5-real-application", "6-look"]
REAL = ["7-real-key"]
SCRIPTS = ("run.sh", "run-key.sh", "bin/marker")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    kit.write_kit(tmp_path / "kit")
    return tmp_path / "kit"


def test_every_file_of_the_kit_exists_and_the_scripts_are_executable(root: Path) -> None:
    for name in (
        *SCRIPTS,
        "checklist.txt",
        "real_start_check.py",
        "drive_launcher.py",
        "window_probe.py",
        "kit_runner.py",
        "run-all.sh",
    ):
        assert (root / name).is_file(), name
    for name in (*SCRIPTS, "run-all.sh"):
        assert os.access(root / name, os.X_OK), f"{name} is not executable"
    for folder in kit.CONFIGS:
        assert (root / folder / "Shells" / "Main_Shell.tdl").is_file()
        assert (root / folder / "settings.tdl").is_file()
    assert (root / "work").is_dir()


def test_the_steps_are_four_unattended_two_manual_and_one_for_the_real_session() -> None:
    steps = kit.steps()
    assert [s.id for s in steps if s.kind == "auto"] == AUTO
    assert [s.id for s in steps if s.kind == "manual"] == MANUAL
    assert [s.id for s in steps if s.kind == "real-session"] == REAL
    (real,) = [s for s in steps if s.kind == "real-session"]
    assert "backup.sh" in real.action and "run-key.sh" in real.action


def test_the_unattended_steps_run_in_a_sandbox_and_name_no_real_folder() -> None:
    for step in kit.steps():
        if step.kind != "auto":
            continue
        assert step.sandbox in ("bus", "systemd", "kwin"), step.id
        assert not re.search(r"\$HOME|~/|/home/|kglobalshortcutsrc", step.command_text()), step.id


@pytest.mark.parametrize("name", SCRIPTS)
def test_each_script_is_well_formed_shell_without_being_run(root: Path, name: str) -> None:
    done = subprocess.run(["sh", "-n", str(root / name)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert (root / name).read_text().startswith("#!/bin/sh\n")


def test_the_marker_becomes_its_own_sleep_so_one_pid_stops_it(root: Path) -> None:
    text = (root / "bin/marker").read_text()
    assert text.rstrip().endswith("exec sleep 20")
    assert f">> {root}/marker.txt" in text


def test_the_real_start_check_compiles_and_is_not_run(root: Path) -> None:
    source = (root / "real_start_check.py").read_text()
    compile(source, "real_start_check.py", "exec")
    assert 'if os.environ.get("PYTEST_CURRENT_TEST")' in source  # it refuses to run in the suite
    assert "SystemRunner" in source and "build_command" in source
    # it writes nothing outside the kit's folder
    assert str(root) in source and "~" not in source.replace("str(Path.home())", "")


def test_the_scripts_write_only_inside_the_kits_folder_and_touch_no_kde_tool(root: Path) -> None:
    for name in SCRIPTS:
        text = (root / name).read_text()
        for tool in ("kwriteconfig", "kbuildsycoca", "kquitapp", "busctl", "dbus-send"):
            assert tool not in text, (name, tool)
        assert not re.search(r"\b(rm|mv)\b", text), name
        assert "kglobalshortcutsrc" not in text, name
        for target in re.findall(r">>?\s*(\S+)", text.replace(">&2", "")):
            assert target.startswith(str(root)), (name, target)


def test_the_real_session_scripts_have_a_private_state_directory_and_the_key_one_a_warning(
    root: Path,
) -> None:
    for name in ("run.sh", "run-key.sh"):
        text = (root / name).read_text()
        assert f"XDG_STATE_HOME={root}/state" in text, name
        assert f"{root}/data" in text, name  # the kit's entries are in the list
        assert "tesserae-shell run --config-dir" in text
    key = (root / "run-key.sh").read_text()
    assert "REAL SHORTCUT SERVICE" in key and "sleep 5" in key
    assert "REAL SHORTCUT SERVICE" not in (root / "run.sh").read_text()


def test_the_made_up_entries_read_as_the_index_reads_them_and_the_hidden_one_is_hidden(
    root: Path,
) -> None:
    index = ApplicationIndex(
        folders=[root / "data" / "applications"],
        locale="",
        desktops=(),
        which=lambda program: f"/usr/bin/{program}",
    )
    listed = sorted(e.name for e in index.applications())
    assert listed == [
        "Tesserae Launched Window",
        "Tesserae Marker",
        "Tesserae Missing Program",
        "Tesserae Terminal Marker",
    ]
    assert len(index.entries()) == 5  # the NoDisplay one is read, and not listed
    marker = index.get("tess-marker")
    assert marker is not None and marker.working_dir == f"{root}/work"
    assert marker.exec == f"{root}/bin/marker %U"
    assert index.get("tess-marker-terminal").terminal is True  # type: ignore[union-attr]


def test_the_checklist_keeps_only_what_no_session_can_do(root: Path) -> None:
    text = (root / "checklist.txt").read_text()
    assert f"{len(AUTO)} steps run unattended" in text and "results.txt" in text
    for step_id in (*MANUAL, *REAL):
        assert re.search(rf"^{step_id}  \[", text, re.M), step_id
    for step_id in AUTO:
        assert f"{step_id}  [" not in text
    assert "/tmp/tess-kwin-m6c/backup.sh" in text  # the exact action names the backup first


def test_the_key_is_rare_and_the_configs_name_the_launcher(root: Path) -> None:
    parse_chord(kit.KEY)
    for folder in kit.CONFIGS:
        text = (root / folder / "settings.tdl").read_text()
        assert f'Toggle_Launcher: "{kit.KEY}"' in text
    assert "Global_Shortcuts: false" in (root / "cfg" / "settings.tdl").read_text()
    assert "Global_Shortcuts" not in (root / "cfg-key" / "settings.tdl").read_text()
    source = (Path(__file__).parent / "kwin" / "drive_launcher.py").read_text()
    constants = {"CTRL": 0x04000000, "ALT": 0x08000000, "SHIFT": 0x02000000}
    found = re.search(r"^CTRL, ALT, SHIFT, F9 = (.+)$", source, re.M)
    assert found is not None
    ctrl, alt, shift, f9 = (int(n, 16) for n in re.findall(r"0x[0-9A-Fa-f]+", found.group(1)))
    assert (ctrl, alt, shift) == tuple(constants.values())
    assert ctrl | alt | shift | f9 == parse_chord(kit.KEY).qt


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


@pytest.mark.skipif(
    not (
        shutil.which("kwin_wayland")
        and shutil.which("dbus-run-session")
        and shutil.which("gdbus")
        and shutil.which("systemd-run")
        and os.path.exists(kitlib.SYSTEMD)
        and Path(kit.TRE_PY).exists()
    ),
    reason="needs kwin_wayland, dbus-run-session, gdbus, the systemd user manager and tre's venv",
)
def test_the_whole_kit_runs_in_private_sandboxes_and_every_unattended_step_passes(
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
