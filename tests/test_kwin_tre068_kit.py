"""The tre 0.6.8 kit (``tests/kwin/prepare_tre068.py``): its files exist, its two shell configs
check clean, the token probe and the drivers compile, the unattended steps run in a private KWin
and name no real folder, and the checklist keeps only what no session can do. With ``kwin_wayland``
and tre's virtual environment installed the whole kit runs end to end and every unattended step
passes. Nothing here touches the real session."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from tests.kwin import prepare_tre068 as kit

FILES = [
    "cfg-popup",
    "cfg-tab",
    "checklist.txt",
    "drive_tre068.py",
    "fake-app",
    "fake_input_server.py",
    "kit_runner.py",
    "kitdrive.py",
    "run-all.sh",
    "run-popup.sh",
    "run-tab.sh",
    "steps.json",
    "token_probe.py",
]
AUTO = ["1-check", "2-tab", "3-popup", "4-token"]
MANUAL = ["5-focus-ring", "6-no-popup-on-screen", "7-real-app-focus", "8-tray-menu-keyboard"]


@pytest.fixture
def root(tmp_path: Path) -> Path:
    kit.write_kit(tmp_path / "kit")
    return tmp_path / "kit"


def test_every_file_of_the_kit_exists(root: Path) -> None:
    assert sorted(p.name for p in root.iterdir()) == FILES
    for name in ("run-all.sh", "run-tab.sh", "run-popup.sh", "fake-app"):
        assert os.access(root / name, os.X_OK), name
    probe = root / "cfg-popup" / "Modules" / "Probe"
    assert (probe / "Probe_Module.tdl").is_file() and (probe / "Probe_Module.py").is_file()
    assert not (root / "cfg-tab" / "Modules").exists()


def test_the_steps_are_four_unattended_and_four_for_a_person() -> None:
    steps = kit.steps()
    assert [s.id for s in steps if s.kind == "auto"] == AUTO
    assert [s.id for s in steps if s.kind == "manual"] == MANUAL
    for step in steps:
        if step.kind == "manual":
            assert step.reason, step.id


def test_the_unattended_steps_run_in_a_sandbox_and_start_no_real_application() -> None:
    for step in kit.steps():
        if step.kind != "auto":
            continue
        assert step.sandbox != "none", step.id
        text = step.command_text()
        assert not re.search(r"konsole|kate|dolphin|\$HOME|~/|/home/", text), step.id
    assert kit.steps()[1].sandbox == "kwin"


@pytest.mark.parametrize("name", ["run-tab.sh", "run-popup.sh", "fake-app"])
def test_each_script_is_well_formed_shell_without_being_run(root: Path, name: str) -> None:
    done = subprocess.run(["sh", "-n", str(root / name)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert (root / name).read_text().startswith("#!/bin/sh\n")


def test_the_run_scripts_name_the_real_session_and_start_only_the_shell(root: Path) -> None:
    for name, folder in (("run-tab.sh", "cfg-tab"), ("run-popup.sh", "cfg-popup")):
        text = (root / name).read_text()
        assert "real session" in text and "sleep 3" in text
        assert f"XDG_STATE_HOME={root}/state" in text
        assert f"exec {kit.BIN}/tesserae-shell run --config-dir {root}/{folder}\n" in text
        assert not re.search(r"kwriteconfig|busctl|dbus-send|konsole", text)


def test_the_python_files_compile_without_being_run(root: Path) -> None:
    for path in (
        root / "token_probe.py",
        root / "drive_tre068.py",
        root / "kitdrive.py",
        root / "fake_input_server.py",
        root / "cfg-popup/Modules/Probe/Probe_Module.py",
    ):
        compile(path.read_text(), str(path), "exec")


def test_the_token_probe_starts_the_named_program_only_in_the_callback(root: Path) -> None:
    text = (root / "token_probe.py").read_text()
    assert "request_activation_token(launch)" in text
    assert "TOKEN_PROGRAM" in text and "konsole" not in text
    assert "no token: the compositor did not offer xdg_activation_v1" in text
    assert text.count("subprocess.Popen") == 1 and text.index("subprocess.Popen") > text.index(
        "def launch"
    )
    assert text.index("def clicked") > text.index("subprocess.Popen")
    fake = (root / "fake-app").read_text()
    assert 'env -0 > "$TOKEN_ENV_OUT"' in fake and fake.count("\n") <= 4


def test_the_probe_opens_and_closes_in_one_turn_once_and_twenty_times(root: Path) -> None:
    text = (root / "cfg-popup/Modules/Probe/Probe_Module.py").read_text()
    assert text.count('self.ctx.popup("Menu", use=use)') == 1  # one helper that toggles
    assert "TIMES = 20" in text and "for _ in range(TIMES)" in text and "def open_hold" in text
    shell = (root / "cfg-popup/Shells/Main_Shell.tdl").read_text()
    assert 'Target: "Probe.open_close"' in shell and 'Target: "Probe.open_close_20"' in shell
    assert 'Fill: "#ff0000"' in shell  # a red body: a stuck popup is obvious


def test_the_tab_config_holds_the_three_controls_in_the_order_of_the_note(root: Path) -> None:
    text = (root / "cfg-tab/Shells/Main_Shell.tdl").read_text()
    assert "Keyboard: ON_DEMAND" in text
    order = [text.index(block) for block in ("TextEditor {", "TextInput {", "Button {")]
    assert order == sorted(order)


def test_the_checklist_keeps_only_what_no_session_can_do(root: Path) -> None:
    text = (root / "checklist.txt").read_text()
    assert f"{len(AUTO)} steps run unattended" in text and "results.txt" in text
    for step_id in MANUAL:
        assert f"{step_id}  [manual]" in text
    for step_id in AUTO:
        assert f"{step_id}  [" not in text
    assert text.count("why a session cannot") == len(MANUAL)


@pytest.mark.parametrize("folder", ["cfg-tab", "cfg-popup"])
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
        and Path(kit.TRE_PY).exists()
    ),
    reason="needs kwin_wayland, dbus-run-session and tre's virtual environment (pywayland)",
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
