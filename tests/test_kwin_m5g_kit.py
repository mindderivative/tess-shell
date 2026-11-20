"""The M5g KWin kit (``tests/kwin/prepare_m5g_kwin.py``): it writes only under its own folder, keeps
the ``backup`` folder the maintainer made with the earlier kit, its configs check clean, every
unattended step runs in a private KWin and the checklist keeps only what no session can do. With
``kwin_wayland`` and tre's virtual environment installed the whole kit runs end to end."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tess_shell.app import check
from tess_shell.options import Options
from tests.kwin import prepare_m5g_kwin as kit

AUTO = ["1-check", "2-introspect", "3-script", "4-off", "5-commands", "6-layer-rule"]
MANUAL = [
    "7-icons",
    "8-click-latency",
    "9-monitors-desktops",
    "10-rule-in-system-settings",
    "11-above-plasma-panel",
]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    kit.write_kit(tmp_path / "kit")
    return tmp_path / "kit"


def test_the_kit_writes_its_files_and_its_configs_check_clean(root: Path) -> None:
    assert sorted(p.name for p in root.iterdir()) == [
        "cfg",
        "cfg-off",
        "checklist.txt",
        "drive_m5g.py",
        "kit_runner.py",
        "kitdrive.py",
        "run-all.sh",
        "run.sh",
        "steps.json",
        "window_probe.py",
    ]
    for name in ("cfg", "cfg-off"):
        assert check(Options(config_dir=root / name)) == 0


def test_running_the_generator_again_keeps_the_backup_the_maintainer_made(tmp_path: Path) -> None:
    """The earlier kit's ``backup.sh`` copied the real ``kwinrc`` and ``kwinrulesrc`` into the kit's
    folder; the generator once removed the whole folder, and with it the way to undo that check."""
    root = tmp_path / "kit"
    kit.write_kit(root)
    (root / "backup").mkdir()
    (root / "backup" / "kwinrulesrc").write_text("[General]\ncount=1\n")
    (root / "cfg" / "stale.txt").write_text("left by an earlier run")
    (root / "introspect.sh").write_text("old")  # a script of the earlier kit
    kit.write_kit(root)
    assert (root / "backup" / "kwinrulesrc").read_text() == "[General]\ncount=1\n"
    assert not (root / "cfg" / "stale.txt").exists()  # the rest is made again
    assert not (root / "introspect.sh").exists()


def test_the_steps_are_six_unattended_and_five_for_a_person() -> None:
    steps = kit.steps()
    assert [s.id for s in steps if s.kind == "auto"] == AUTO
    assert [s.id for s in steps if s.kind == "manual"] == MANUAL


def test_the_unattended_steps_run_in_a_sandbox_and_touch_no_real_file() -> None:
    for step in kit.steps():
        if step.kind != "auto":
            continue
        assert step.sandbox in ("bus", "kwin"), step.id
        text = step.command_text()
        assert not re.search(r"\$HOME|~/|/home/|kwinrc|kwinrulesrc|busctl", text), step.id


def test_run_sh_is_the_only_script_that_touches_a_real_session(root: Path) -> None:
    text = (root / "run.sh").read_text()
    assert "real session" in text and "sleep 5" in text
    assert f"XDG_STATE_HOME={root}/state exec {kit.BIN}/tesserae-shell run" in text
    done = subprocess.run(["sh", "-n", str(root / "run.sh")], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr


def test_the_python_files_compile_without_being_run(root: Path) -> None:
    for name in ("drive_m5g.py", "window_probe.py", "kitdrive.py"):
        compile((root / name).read_text(), name, "exec")
    module = root / "cfg" / "Modules" / "WinLog" / "WinLog_Module.py"
    compile(module.read_text(), str(module), "exec")


def test_the_checklist_keeps_only_what_no_session_can_do(root: Path) -> None:
    text = (root / "checklist.txt").read_text()
    assert f"{len(AUTO)} steps run unattended" in text and "results.txt" in text
    for step_id in MANUAL:
        assert f"{step_id}  [manual]" in text
    for step_id in AUTO:
        assert f"{step_id}  [" not in text
    assert text.count("why a session cannot") == len(MANUAL)


@pytest.mark.skipif(
    not (
        shutil.which("kwin_wayland") and shutil.which("dbus-run-session") and shutil.which("gdbus")
    ),
    reason="needs kwin_wayland, dbus-run-session and gdbus",
)
def test_the_whole_kit_runs_in_a_private_kwin_and_every_unattended_step_passes(
    tmp_path: Path,
) -> None:
    folder = tmp_path / "kit"
    kit.write_kit(folder)
    real_rules = Path(f"/home/{os.environ.get('USER', '')}/.config/kwinrulesrc")
    before = real_rules.stat().st_mtime if real_rules.exists() else None
    done = subprocess.run(
        [str(folder / "run-all.sh")], capture_output=True, text=True, timeout=900, cwd="/"
    )
    summary = (folder / "results.txt").read_text()
    assert done.returncode == 0, done.stdout + done.stderr + summary
    for step_id in AUTO:
        assert re.search(rf"^PASS  {step_id}  ", summary, re.M), summary
    assert re.search(r"^PASS  cleanup", summary, re.M)
    after = real_rules.stat().st_mtime if real_rules.exists() else None
    assert before == after  # the real kwinrulesrc is untouched
