"""The crash-recovery kit (``tests/kwin/prepare_m7b_watchdog.py``): its files exist, every step runs
in a sandbox and names no real folder, the shell scripts are well formed, and (when
``dbus-run-session``, the systemd user manager and ``sway`` work) the whole kit runs end to end in
private sandboxes and every step passes. Nothing here touches the real home, bus or systemd
manager."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from tests import kitlib
from tests.kwin import prepare_m7b_watchdog as kit

FILES = ["checklist.txt", "config", "kit_runner.py", "run-all.sh", "silent.py", "steps.json"]
AUTO = [
    "1-unit",
    "2-start",
    "3-pings",
    "4-hang",
    "5-silent-service",
    "6-sigkill",
    "7-lost-compositor",
    "8-stop",
    "9-remove",
]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    kit.write_kit(tmp_path / "kit")
    return tmp_path / "kit"


def test_every_file_of_the_kit_exists_and_nothing_else_is_written(root: Path) -> None:
    assert sorted(p.name for p in root.iterdir()) == FILES
    assert os.access(root / "run-all.sh", os.X_OK)
    assert (root / "config" / "Modules" / "Hang" / "Hang_Module.py").is_file()


def test_every_step_is_unattended_and_runs_in_a_systemd_and_sway_sandbox() -> None:
    steps = kit.steps()
    assert [s.id for s in steps] == AUTO
    for step in steps:
        assert step.kind == "auto" and step.sandbox == "systemd+sway", step.id


def test_no_step_names_a_real_folder_or_the_real_session() -> None:
    real = r"\$HOME|\$\{HOME|~/|/home/|\.config/systemd|\.local/share|/run/user"
    for step in kit.steps():
        text = step.command_text().replace(kit.PYTHON, "<python>")  # the interpreter is the one
        assert not re.search(real, text), step.id  # exception: it is only run, never written to
    # the only absolute paths are the sandbox's own variables, the interpreter and the kit
    assert "/run/user" not in kit.SILENT_PY and "/home/" not in kit.SILENT_PY


def test_the_scripts_are_well_formed_shell_without_being_run() -> None:
    for step in kit.steps():
        done = subprocess.run(
            ["bash", "-n", "-c", step.command_text()], capture_output=True, text=True
        )
        assert done.returncode == 0, (step.id, done.stderr)


def test_the_compositor_that_is_killed_is_the_sandbox_s_own_second_one() -> None:
    """The kill in step 7 aims at a pid read from a file the step wrote for a sway it started
    itself: never ``pkill`` or a name, which could match a real compositor."""
    script = next(s for s in kit.steps() if s.id == "7-lost-compositor").command_text()
    assert "pkill" not in script and "killall" not in script
    assert 'kill -KILL "$(cat "$pidf")"' in script
    assert "env -u WAYLAND_DISPLAY -u SWAYSOCK" in script  # never nested in another compositor


@pytest.mark.skipif(
    not (
        shutil.which("dbus-run-session")
        and shutil.which("sway")
        and shutil.which("systemctl")
        and os.path.exists(kitlib.SYSTEMD)
    ),
    reason="needs dbus-run-session, sway and the systemd user manager",
)
def test_the_whole_kit_runs_in_private_sandboxes_and_every_step_passes(tmp_path: Path) -> None:
    if not kitlib.systemd_works():
        pytest.skip("a private systemd user manager cannot be started on this machine")
    folder = tmp_path / "kit"
    kit.write_kit(folder)
    sandboxes_before = set(Path(tempfile.gettempdir()).glob("tk-*"))
    done = subprocess.run(
        [str(folder / "run-all.sh")], capture_output=True, text=True, timeout=900, cwd="/"
    )
    summary = (folder / "results.txt").read_text()
    assert done.returncode == 0, done.stdout + done.stderr + summary
    verdicts = {
        line.split()[1]: line.split()[0]
        for line in summary.splitlines()
        if line.split() and line.split()[0] in ("PASS", "FAIL", "SKIP")
    }
    assert [i for i in AUTO if verdicts[i] != "PASS"] == [], summary
    assert verdicts["cleanup"] == "PASS"
    assert set(Path(tempfile.gettempdir()).glob("tk-*")) == sandboxes_before
