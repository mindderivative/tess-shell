"""The tre 0.6.8 KWin kit (``tests/kwin/prepare_tre068.py``): its files exist, its two shell configs
check clean, the token script compiles and the scripts only name the places the checklist says.
Nothing here RUNS a script of the kit or starts a shell or an application: ``sh -n`` and
``compile`` only parse, ``check`` only reads."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from tests.kwin import prepare_tre068 as kit

SCRIPTS = ("run-tab.sh", "run-popup.sh", "run-token.sh", "check.sh")


@pytest.fixture
def root(tmp_path: Path) -> Path:
    kit.write_kit(tmp_path / "kit")
    return tmp_path / "kit"


def test_every_file_of_the_kit_exists(root: Path) -> None:
    for name in (*SCRIPTS, "checklist.txt", "token_probe.py"):
        assert (root / name).is_file(), name
    for name in SCRIPTS:
        assert (root / name).stat().st_mode & 0o111, f"{name} is not executable"
    for folder in kit.CONFIGS:
        assert (root / folder / "Shells" / "Main_Shell.tdl").is_file()
        assert (root / folder / "settings.tdl").is_file()
    probe = root / "cfg-popup" / "Modules" / "Probe"
    assert (probe / "Probe_Module.tdl").is_file() and (probe / "Probe_Module.py").is_file()
    assert not (root / "cfg-tab" / "Modules").exists()


@pytest.mark.parametrize("name", SCRIPTS)
def test_each_script_is_well_formed_shell_without_being_run(root: Path, name: str) -> None:
    done = subprocess.run(["sh", "-n", str(root / name)], capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    assert (root / name).read_text().startswith("#!/bin/sh\n")


def test_the_python_files_compile_without_being_run(root: Path) -> None:
    for path in (root / "token_probe.py", root / "cfg-popup/Modules/Probe/Probe_Module.py"):
        compile(path.read_text(), str(path), "exec")


def test_the_scripts_start_only_what_the_checklist_says_and_write_only_in_the_kit(
    root: Path,
) -> None:
    for name in SCRIPTS:
        text = (root / name).read_text()
        for tool in ("kwriteconfig", "kbuildsycoca", "kquitapp", "busctl", "dbus-send", "konsole"):
            assert tool not in text, (name, tool)
        assert not re.search(r"\b(rm|mv)\b", text), name
        assert f"XDG_STATE_HOME={root}/state" in text, name
        for target in re.findall(r">\s*(\S+)", text.replace(">&2", "")):
            assert target.startswith(str(root)), (name, target)
    for name, folder in (("run-tab.sh", "cfg-tab"), ("run-popup.sh", "cfg-popup")):
        text = (root / name).read_text()
        assert "Ctrl+C" in text and "sleep 3" in text
        assert f"exec {kit.BIN}/tesserae-shell run --config-dir {root}/{folder}\n" in text
    token = (root / "run-token.sh").read_text()
    assert f"exec {kit.BIN}/python {root}/token_probe.py\n" in token
    assert "ONLY when you click" in token


def test_the_token_script_asks_for_a_token_and_starts_an_app_only_in_the_callback(
    root: Path,
) -> None:
    text = (root / "token_probe.py").read_text()
    assert "request_activation_token(launch)" in text
    assert '"konsole", "kate", "dolphin"' in text
    assert "no token: the compositor did not offer xdg_activation_v1" in text
    assert text.count("subprocess.Popen") == 1 and "def launch" in text
    assert text.index("subprocess.Popen") > text.index("def launch")
    assert text.index("def clicked") > text.index("subprocess.Popen")
    header = " ".join(text.split('"""')[1].split())
    assert "starts NOTHING until you click" in header and "Ctrl+C" in header
    assert "close it yourself" in header


def test_the_probe_opens_and_closes_in_one_turn_once_and_twenty_times(root: Path) -> None:
    text = (root / "cfg-popup/Modules/Probe/Probe_Module.py").read_text()
    assert text.count('self.ctx.popup("Menu", use=use)') == 1  # one helper that toggles
    assert "TIMES = 20" in text and "for _ in range(TIMES)" in text
    shell = (root / "cfg-popup/Shells/Main_Shell.tdl").read_text()
    assert 'Target: "Probe.open_close"' in shell and 'Target: "Probe.open_close_20"' in shell
    assert 'Fill: "#ff0000"' in shell  # a red body: a stuck popup is obvious


def test_the_tab_config_holds_the_three_controls_in_the_order_of_the_note(root: Path) -> None:
    text = (root / "cfg-tab/Shells/Main_Shell.tdl").read_text()
    assert "Keyboard: ON_DEMAND" in text
    order = [text.index(block) for block in ("TextEditor {", "TextInput {", "Button {")]
    assert order == sorted(order)


def test_the_checklist_is_one_numbered_list_with_the_notes_tables(root: Path) -> None:
    text = (root / "checklist.txt").read_text()
    numbers = [int(m.group(1)) for m in re.finditer(r"^ ?(\d+)  ", text, re.M)]
    assert numbers == list(range(1, 12))
    flat = " ".join(text.split())
    for needle in (
        "no tab character was typed into the TextEditor",
        "focus returns to the TextEditor",
        "no popup is left on screen",
        "Escape straight after the click",
        "focus-stealing prevention",
        "xdg_activation_v1",
        "Ctrl+C",
    ):
        assert needle in flat, needle
    for name in ("run-tab.sh", "run-popup.sh", "run-token.sh", "check.sh"):
        assert name in text


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
