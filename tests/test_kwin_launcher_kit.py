"""The launcher KWin kit (``tests/kwin/prepare_launcher.py``): its files exist, its configs check
clean, its desktop entries read as the index reads them, its scripts are well-formed shell and only
name the places the checklist says, and the checklist is one numbered list. Nothing here RUNS a
script, the marker or the real-start check, starts a shell, or touches ``~/.config`` or any bus:
``sh -n`` and ``compile`` only parse."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from tess_shell.schema.keys import parse_chord
from tess_shell.services.desktop_entries import ApplicationIndex
from tests.kwin import prepare_launcher as kit

SCRIPTS = ("run.sh", "run-key.sh", "real-start.sh", "check.sh")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    kit.write_kit(tmp_path / "kit")
    return tmp_path / "kit"


def test_every_file_of_the_kit_exists_and_the_scripts_are_executable(root: Path) -> None:
    for name in (*SCRIPTS, "checklist.txt", "real_start_check.py", "bin/marker"):
        assert (root / name).is_file(), name
    for name in (*SCRIPTS, "bin/marker"):
        assert (root / name).stat().st_mode & 0o111, f"{name} is not executable"
    for folder in kit.CONFIGS:
        assert (root / folder / "Shells" / "Main_Shell.tdl").is_file()
        assert (root / folder / "settings.tdl").is_file()
    assert (root / "work").is_dir()


@pytest.mark.parametrize("name", [*SCRIPTS, "bin/marker"])
def test_each_script_is_well_formed_shell_without_being_run(root: Path, name: str) -> None:
    done = subprocess.run(["sh", "-n", str(root / name)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert (root / name).read_text().startswith("#!/bin/sh\n")


def test_the_real_start_check_compiles_and_is_not_run(root: Path) -> None:
    source = (root / "real_start_check.py").read_text()
    compile(source, "real_start_check.py", "exec")
    assert 'if os.environ.get("PYTEST_CURRENT_TEST")' in source  # it refuses to run in the suite
    assert "SystemRunner" in source and "build_command" in source
    # it writes nothing outside the kit's folder
    assert str(root) in source and "~" not in source.replace("str(Path.home())", "")


def test_a_script_writes_only_inside_the_kits_folder_and_touches_no_kde_tool(root: Path) -> None:
    for name in (*SCRIPTS, "bin/marker"):
        text = (root / name).read_text()
        for tool in ("kwriteconfig", "kbuildsycoca", "kquitapp", "busctl", "dbus-send"):
            assert tool not in text, (name, tool)
        assert not re.search(r"\b(rm|mv)\b", text), name
        assert "kglobalshortcutsrc" not in text, name
        for target in re.findall(r">>?\s*(\S+)", text.replace(">&2", "")):
            assert target.startswith(str(root)), (name, target)


def test_every_run_script_has_a_private_state_directory_and_the_key_one_a_warning(
    root: Path,
) -> None:
    for name in ("run.sh", "run-key.sh", "check.sh"):
        text = (root / name).read_text()
        assert f"XDG_STATE_HOME={root}/state" in text, name
        assert f"{root}/data" in text, name  # the kit's entries are in the list
    for name in ("run.sh", "run-key.sh"):
        assert "tesserae-shell run --config-dir" in (root / name).read_text()
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
    assert listed == ["Tesserae Marker", "Tesserae Missing Program", "Tesserae Terminal Marker"]
    assert len(index.entries()) == 4  # the NoDisplay one is read, and not listed
    marker = index.get("tess-marker")
    assert marker is not None and marker.working_dir == f"{root}/work"
    assert marker.exec == f"{root}/bin/marker %U"
    assert index.get("tess-marker-terminal").terminal is True  # type: ignore[union-attr]


def test_the_checklist_is_one_numbered_list_with_the_two_questions_of_the_spec(root: Path) -> None:
    text = (root / "checklist.txt").read_text()
    numbers = [int(m.group(1)) for m in re.finditer(r"^ ?(\d+)  ", text, re.M)]
    assert numbers == list(range(0, 16))
    flat = " ".join(text.split())
    for needle in (
        "spec question 2",
        "spec question 1",
        "activation token: received",
        "activation token: none",
        "app-tess-marker",
        "THIS USES YOUR REAL SHORTCUT SERVICE",
        "/tmp/tess-kwin-m6c/backup.sh",
        "Could not start",
        "$status",
        "does not hide it",
    ):
        assert needle in flat, needle
    for script in (*SCRIPTS, "marker.txt"):
        assert script in text, f"the checklist never names {script}"
    # the part that needs no desktop comes first
    assert text.index("real-start.sh") < text.index("run.sh")


def test_the_key_is_rare_and_the_configs_name_the_launcher(root: Path) -> None:
    parse_chord(kit.KEY)
    for folder in kit.CONFIGS:
        text = (root / folder / "settings.tdl").read_text()
        assert f'Toggle_Launcher: "{kit.KEY}"' in text
    assert "Global_Shortcuts: false" in (root / "cfg" / "settings.tdl").read_text()
    assert "Global_Shortcuts" not in (root / "cfg-key" / "settings.tdl").read_text()


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
