"""The install-session kit (``tests/kwin/prepare_install_session.py``): its files exist, every
unattended step runs in a private sandbox and names no real folder, the checklist keeps only what no
session can do, and (when ``dbus-run-session``, the systemd user manager and ``kwin_wayland`` are
installed) the whole kit runs end to end in private sandboxes and every unattended step passes.
Nothing here touches the real home, bus or systemd manager."""

from __future__ import annotations

import os
import pwd
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests import kitlib
from tests.kwin import prepare_install_session as kit

FILES = ["checklist.txt", "kit_runner.py", "run-all.sh", "steps.json"]
AUTO = [
    "2-print",
    "3a-install",
    "3b-install-again",
    "4a-verify-unit",
    "4b-verify-desktop",
    "5a-stale-status",
    "5b-stale-json",
    "5c-stale-kept",
    "5d-stale-force",
    "5e-stale-gone",
    "6-enable",
    "7a-start",
    "7b-status",
    "8a-kill-restarts",
    "8b-stop",
    "8c-quit-no-restart",
    "8d-disable",
    "10-remove",
]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    kit.write_kit(tmp_path / "kit")
    return tmp_path / "kit"


def test_every_file_of_the_kit_exists_and_nothing_else_is_written(root: Path) -> None:
    assert sorted(p.name for p in root.iterdir()) == FILES
    assert os.access(root / "run-all.sh", os.X_OK)


def test_the_steps_are_the_unattended_ones_plus_the_two_a_person_must_do() -> None:
    steps = kit.steps()
    assert [s.id for s in steps if s.kind == "auto"] == AUTO
    assert [(s.id, s.kind) for s in steps if s.kind != "auto"] == [
        ("9-login", "manual"),
        ("7d-portal", "real-session"),
    ]


def test_every_unattended_step_runs_in_a_sandbox_and_names_no_real_folder() -> None:
    for step in kit.steps():
        if step.kind != "auto":
            continue
        assert step.sandbox != "none", step.id
        text = step.command_text()
        # only the sandbox's XDG folders: never the real home, ~, $HOME or an absolute home path
        real = r"\$HOME|\$\{HOME|~/|/home/|\.config/systemd|\.local/share"
        assert not re.search(real, text), step.id
        assert "XDG_RUNTIME_DIR" in text or "$XDG_" in text or "$BIN" in text, step.id


def test_the_systemd_verbs_run_only_in_a_systemd_sandbox() -> None:
    for step in kit.steps():
        if step.kind == "auto" and re.search(r"\$CTL ", step.command_text()):
            assert "systemd" in step.sandbox, step.id


def test_the_scripts_are_well_formed_shell_without_being_run() -> None:
    for step in kit.steps():
        if step.kind != "auto":
            continue
        done = subprocess.run(
            ["bash", "-n", "-c", step.command_text()], capture_output=True, text=True
        )
        assert done.returncode == 0, (step.id, done.stderr)


def test_the_checklist_keeps_only_what_no_session_can_do(root: Path) -> None:
    text = (root / "checklist.txt").read_text()
    assert f"{len(AUTO)} steps run unattended" in text
    assert "results.txt" in text
    assert "9-login  [manual]" in text and "7d-portal  [real-session]" in text
    assert "why a session cannot" in text
    assert "exact action (ask permission first)" in text
    assert "Register failed" in text  # likely already shown by the absence of the warning
    for step_id in AUTO:
        assert f"{step_id}  [" not in text
    assert "1-backup" not in text and "9-undo" not in text


def test_the_earlier_scripts_that_touched_the_real_home_are_removed(tmp_path: Path) -> None:
    folder = tmp_path / "kit"
    folder.mkdir()
    for name in kit.OBSOLETE:
        (folder / name).write_text("old")
    (folder / "backup").mkdir()
    (folder / "backup" / "state.txt").write_text("the maintainer's backup")
    kit.write_kit(folder)
    assert not any((folder / name).exists() for name in kit.OBSOLETE)
    assert (folder / "backup" / "state.txt").read_text() == "the maintainer's backup"


@pytest.mark.skipif(
    not (
        shutil.which("dbus-run-session")
        and shutil.which("kwin_wayland")
        and shutil.which("systemctl")
        and os.path.exists(kitlib.SYSTEMD)
    ),
    reason="needs dbus-run-session, kwin_wayland and the systemd user manager",
)
def test_the_whole_kit_runs_in_private_sandboxes_and_every_unattended_step_passes(
    tmp_path: Path,
) -> None:
    if not kitlib.systemd_works():
        pytest.skip("a private systemd user manager cannot be started on this machine")
    home = Path(pwd.getpwuid(os.getuid()).pw_dir)
    real_unit = home / ".config" / "systemd" / "user" / kit.UNIT
    real_desktop = home / ".local" / "share" / "applications" / kit.DESKTOP
    before = (real_unit.exists(), real_desktop.exists())
    folder = tmp_path / "kit"
    kit.write_kit(folder)
    sandboxes_before = set(Path(tempfile.gettempdir()).glob("tk-*"))
    done = subprocess.run(
        [str(folder / "run-all.sh")], capture_output=True, text=True, timeout=600, cwd="/"
    )
    summary = (folder / "results.txt").read_text()
    assert done.returncode == 0, done.stdout + done.stderr + summary
    verdicts = {
        line.split()[1]: line.split()[0]
        for line in summary.splitlines()
        if line.split() and line.split()[0] in ("PASS", "FAIL", "SKIP")
    }
    assert [i for i in AUTO if verdicts[i] != "PASS"] == [], summary
    assert verdicts["9-login"] == "SKIP" and verdicts["7d-portal"] == "SKIP"
    assert verdicts["cleanup"] == "PASS"
    # no sandbox folder (and no stale gvfs mount in one) is left behind
    assert set(Path(tempfile.gettempdir()).glob("tk-*")) == sandboxes_before
    # the real home was not touched
    assert (real_unit.exists(), real_desktop.exists()) == before
