"""``insecure-permissions`` (Security Model, control 2): a configuration folder, a module folder or
a module file that group or others can write, or that another user owns, is a warning, once per
path, at start, at reload and in ``check``; ``check --strict`` fails on it; the shell starts."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import pytest

from tess_shell.cli import main
from tess_shell.config.discovery import shipped_dir
from tess_shell.config.permissions import permission_findings
from tess_shell.config.settings import load_settings
from tess_shell.scanner import permission_paths, scan
from tests.test_control_live import Make, desk  # noqa: F401 - the live fixture
from tests.test_module_import import LABEL, module, shell

RULE = "insecure-permissions"
HEAD_S = "---\nTDL: 0.2\nName: S\n---\n"


def tidy(cfg: Path) -> None:
    """Every folder 0755 and every file 0644, whatever the umask of the machine running the test."""
    for root, _dirs, files in os.walk(cfg):
        os.chmod(root, 0o755)
        for name in files:
            os.chmod(Path(root) / name, 0o644)


@pytest.fixture
def cfg(tmp_path: Path) -> Path:
    module(tmp_path, "Label", LABEL)
    shell(tmp_path, "Label { }")
    tidy(tmp_path)
    return tmp_path


def warned(
    cfg: Path, capsys: pytest.CaptureFixture[str], *extra: str
) -> tuple[int, list[dict[str, Any]]]:
    code = main(["check", "--json", "--config-dir", str(cfg), *extra])
    report = json.loads(capsys.readouterr().out)
    return code, [e for e in report["errors"] if e["rule"] == RULE]


def test_a_tree_only_you_can_write_has_no_warning(
    cfg: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert warned(cfg, capsys) == (0, [])


@pytest.mark.parametrize(
    ("relative", "mode", "who"),
    [
        ("", 0o775, "group"),  # the configuration folder
        ("Modules/Label", 0o757, "others"),  # the module's folder
        ("Modules/Label/Label_Module.py", 0o666, "group and others"),  # its Python file
    ],
)
def test_each_of_the_three_kinds_of_path_warns_once_and_the_check_passes(
    cfg: Path, capsys: pytest.CaptureFixture[str], relative: str, mode: int, who: str
) -> None:
    target = cfg / relative if relative else cfg
    os.chmod(target, mode)
    code, found = warned(cfg, capsys)
    assert code == 0  # a warning, not an error
    (finding,) = found
    assert finding["severity"] == "warning" and finding["file"] == str(target)
    assert f"writable by {who}" in finding["message"] and f"{mode:04o}" in finding["message"]
    assert "chmod go-w" in finding["hint"]


def test_strict_turns_the_warning_into_a_failing_exit(
    cfg: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    os.chmod(cfg / "Modules" / "Label" / "Label_Module.py", 0o664)
    assert warned(cfg, capsys)[0] == 0
    code, found = warned(cfg, capsys, "--strict")
    assert code == 1 and len(found) == 1
    # printed form: the warning, then the reason the exit is 1
    assert main(["check", "--strict", "--config-dir", str(cfg)]) == 1
    err = capsys.readouterr().err
    assert "warning: the file" in err and "writable by group" in err and "--strict" in err
    # without a warning, --strict passes
    os.chmod(cfg / "Modules" / "Label" / "Label_Module.py", 0o644)
    assert main(["check", "--strict", "--quiet", "--config-dir", str(cfg)]) == 0


def test_a_path_reached_twice_is_one_warning(cfg: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # the Modules folder is searched as the default and as a folder Directories names
    os.chmod(cfg / "Modules", 0o777)
    (cfg / "settings.tdl").write_text(
        HEAD_S + f'Settings {{ Directories {{ Modules: ["{cfg}/Modules"] }} }}\n'
    )
    os.chmod(cfg / "settings.tdl", 0o644)
    code, found = warned(cfg, capsys)
    assert code == 0 and [f["file"] for f in found] == [str(cfg / "Modules")]


def test_a_folder_that_directories_adds_for_modules_is_checked_too(
    cfg: Path, capsys: pytest.CaptureFixture[str], tmp_path_factory: pytest.TempPathFactory
) -> None:
    extra = tmp_path_factory.mktemp("more")
    os.chmod(extra, 0o770)
    (cfg / "settings.tdl").write_text(
        f'---\nTDL: 0.2\nName: S\n---\nSettings {{ Directories {{ Modules: "{extra}" }} }}\n'
    )
    os.chmod(cfg / "settings.tdl", 0o644)
    code, found = warned(cfg, capsys)
    assert code == 0 and [f["file"] for f in found] == [str(extra)]


def test_the_shipped_modules_are_never_judged(cfg: Path) -> None:
    settings, _ = load_settings(cfg)
    assert settings is not None
    result = scan(settings, cfg)
    assert any(mf.shipped for mf in result.modules.values())  # Clock and the others are loaded
    watched = permission_paths(cfg, settings, result.modules)
    assert watched and not [p for p in watched if shipped_dir() in p.parents]
    assert cfg / "Modules" / "Label" / "Label_Module.py" in watched  # and a module of yours is


def test_a_path_of_another_user_is_a_warning_even_when_only_that_user_can_write(
    cfg: Path,
) -> None:
    mine = cfg / "Modules" / "Label" / "Label_Module.py"
    (finding,) = permission_findings([mine], uid=os.getuid() + 1)
    assert finding.rule == RULE and "not owned by you" in finding.message
    assert "writable" not in finding.message and "chown" in finding.hint
    assert permission_findings([mine]) == []
    assert permission_findings([cfg / "no-such-file"]) == []  # the file checks say so


def test_a_shell_starts_with_the_warnings_and_logs_each_path_once(desk: Make) -> None:  # noqa: F811
    d = desk()
    folder = d.cfg / "Modules" / "Probe"
    for path, mode in ((d.cfg, 0o775), (folder, 0o775), (folder / "Probe_Module.py", 0o664)):
        os.chmod(path, mode)
    for path in (d.cfg / "Shells", d.cfg / "Modules", folder / "Probe_Module.tdl"):
        os.chmod(path, 0o755 if path.is_dir() else 0o644)
    shell_run = d.start()  # it reaches "running": a warning does not stop it
    assert d.finish() == 0
    log = shell_run.log_text()
    for path in (d.cfg, folder, folder / "Probe_Module.py"):
        lines = [ln for ln in log.splitlines() if f"{path}:1:1 {RULE}" in ln]
        assert len(lines) == 1 and "WARNING" in lines[0], (path, lines)
    assert log.count(RULE) == 3
    assert "warning:" in shell_run.stderr  # and the printed form, for the terminal


def test_a_reload_warns_about_a_path_that_became_writable_once_for_each_reload(
    desk: Make,  # noqa: F811
) -> None:
    d = desk()
    (d.cfg / "settings.tdl").write_text(
        HEAD_S + "Settings { Hot_Reload: false, Logging { Level: DEBUG } }\n"
    )
    tidy(d.cfg)  # nothing is writable by others: the shell starts without a warning
    py = d.cfg / "Modules" / "Probe" / "Probe_Module.py"
    shell_run = d.start()
    assert RULE not in shell_run.stderr
    os.chmod(py, 0o664)  # a module file that someone else can now write
    for reloads in (1, 2):
        assert d.run("reload").returncode == 0  # a warning does not refuse the reload
        shell_run.wait_log(f"{py}:1:1 {RULE}")
        deadline = time.monotonic() + 8
        while shell_run.log_text().count(f"{py}:1:1 {RULE}") < reloads:
            assert time.monotonic() < deadline
            time.sleep(0.05)
        assert shell_run.log_text().count(f"{py}:1:1 {RULE}") == reloads
    assert d.finish() == 0
