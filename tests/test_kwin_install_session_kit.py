"""The install-session kit (``tests/kwin/prepare_install_session.py``): its files exist, its scripts
are well-formed shell, only name the places the checklist says and call only the ``systemctl`` verbs
that read, and the checklist starts with the backup. Nothing here RUNS a script of the kit or
touches a real folder: ``sh -n`` only parses."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from tests.kwin import prepare_install_session as kit

SCRIPTS = (
    "1-backup.sh",
    "2-print.sh",
    "3-install.sh",
    "4-verify.sh",
    "5-stale.sh",
    "6-enable.sh",
    "7-after-login.sh",
    "9-undo.sh",
)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    kit.write_kit(tmp_path / "kit")
    return tmp_path / "kit"


def test_every_file_of_the_kit_exists_and_nothing_else_is_written(root: Path) -> None:
    assert sorted(p.name for p in root.iterdir()) == sorted([*SCRIPTS, "checklist.txt"])
    for name in SCRIPTS:
        assert (root / name).stat().st_mode & 0o111, f"{name} is not executable"


@pytest.mark.parametrize("name", SCRIPTS)
def test_each_script_is_well_formed_shell_without_being_run(root: Path, name: str) -> None:
    done = subprocess.run(["sh", "-n", str(root / name)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert (root / name).read_text().startswith("#!/bin/sh\n")


def test_the_scripts_change_systemd_only_through_install_session(root: Path) -> None:
    """``enable``, ``start``, ``disable`` and ``stop`` are the command's (or the maintainer's, typed
    from the checklist): a script runs only the verbs that read, and ``daemon-reload`` after the
    undo."""
    for name in SCRIPTS:
        text = (root / name).read_text()
        for verb in re.findall(r"systemctl --user (\S+)", text):
            assert verb in {"is-enabled", "status", "show", "daemon-reload"}, (name, verb)
        assert not re.search(r"\b(kill|pkill|mv)\b", text), name
        # rm only inside the temporary copy of 4-verify.sh
        assert "rm " not in text.replace('rm -r "$copy"', ""), name


def test_only_the_install_session_command_writes_the_two_real_files(root: Path) -> None:
    for name in SCRIPTS:
        text = (root / name).read_text()
        for target in re.findall(r">>?\s*(\S+)", text.replace(">&2", "").replace("2>&1", "")):
            assert target.startswith(("$KIT", '"$KIT', "/dev/null")), (name, target)


def test_the_checklist_starts_with_the_backup_and_names_the_undo(root: Path) -> None:
    text = (root / "checklist.txt").read_text()
    assert text.index("1-backup.sh") < text.index("2-print.sh") < text.index("3-install.sh")
    assert "9-undo.sh" in text and "REAL" in text
    numbers = [int(n) for n in re.findall(r"^ ?(\d+)  ", text, flags=re.M)]
    assert numbers == sorted(numbers) and numbers[0] == 0
