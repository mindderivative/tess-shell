"""``tesserae-shell check`` for the Python of user modules: the findings the shell would make when
it loads them, found without running anything, and with ``--import-modules`` found by a real import
in a throwaway process. The shipped modules are never read or imported by it."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from tess_shell.cli import main
from tess_shell.modproc import probe

HEADER = "---\nTDL: 0.2\nShell: 0.1\nName: {name}\n---\n"
SETTINGS = HEADER.format(name="S") + "Settings { Appearance { Follow_Desktop: false } }\n"
SHELL = HEADER.format(name="Main_Shell") + (
    "Shell { Monitor { Name: Main, Index: 0, Children { Bar { Name: Top, Edge: TOP, "
    "Width: EXPAND, Height: 30, Children { Mine { } } } } } }\n"
)
LAYOUT = HEADER.format(name="Mine") + "Module { Rectangle { Width: 10, Height: 10 } }\n"
GOOD = "from tess_shell import Module\nclass Mine(Module):\n    pass\n"


def config(tmp_path: Path, code: str | None) -> Path:
    cfg = tmp_path / "cfg"
    (cfg / "Shells").mkdir(parents=True)
    (cfg / "settings.tdl").write_text(SETTINGS)
    (cfg / "Shells" / "Main_Shell.tdl").write_text(SHELL)
    folder = cfg / "Modules" / "Mine"
    folder.mkdir(parents=True)
    (folder / "Mine_Module.tdl").write_text(LAYOUT)
    if code is not None:
        (folder / "Mine_Module.py").write_text(code)
    for path in (cfg, cfg / "Modules", folder, *folder.iterdir()):
        path.chmod(0o700 if path.is_dir() else 0o600)
    return cfg


def check(capsys: pytest.CaptureFixture[str], cfg: Path, *more: str) -> tuple[int, dict[str, Any]]:
    code = main(["check", "--config-dir", str(cfg), "--json", *more])
    return code, json.loads(capsys.readouterr().out)


def rules(report: dict[str, Any]) -> list[str]:
    return [e["rule"] for e in report["errors"]]


def test_a_good_module_checks_clean_both_ways(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = config(tmp_path, GOOD)
    assert check(capsys, cfg)[0] == 0
    code, report = check(capsys, cfg, "--import-modules")
    assert code == 0 and report["errors"] == []


def test_a_syntax_error_is_found_without_running_anything(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*args: Any, **kw: Any) -> Any:
        raise AssertionError("a plain check starts no process")

    monkeypatch.setattr(subprocess, "Popen", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)
    cfg = config(tmp_path, "from tess_shell import Module\nclass Mine(Module:\n")
    code, report = check(capsys, cfg)
    assert code == 1 and rules(report) == ["module-import"]
    (found,) = report["errors"]
    assert found["line"] == 2 and found["file"].endswith("Mine_Module.py")


def test_no_class_two_classes_and_a_missing_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert rules(check(capsys, config(tmp_path / "a", "x = 1\n"))[1]) == ["module-classes"]
    two = GOOD + "class Other(Module):\n    pass\n"
    assert rules(check(capsys, config(tmp_path / "b", two))[1]) == ["module-classes"]
    assert rules(check(capsys, config(tmp_path / "c", None))[1]) == ["module-no-python"]


def test_a_plain_check_does_not_run_the_modules_top_level_code(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    marker = tmp_path / "ran"
    code = f"open({str(marker)!r}, 'w').write('x')\n" + GOOD
    cfg = config(tmp_path, code)
    assert check(capsys, cfg)[0] == 0 and not marker.exists()
    assert check(capsys, cfg, "--import-modules")[0] == 0 and marker.exists()


def test_import_modules_finds_what_only_running_finds_with_its_line(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = config(tmp_path / "i", "import nothing_like_this_module\n" + GOOD)
    assert check(capsys, cfg)[0] == 0, "the syntax tree finds nothing wrong"
    code, report = check(capsys, cfg, "--import-modules")
    assert code == 1 and rules(report) == ["module-import"]
    (found,) = report["errors"]
    assert "ModuleNotFoundError" in found["message"] and found["line"] == 1
    cfg = config(
        tmp_path / "n",
        GOOD.replace("    pass", "    def __init__(self):\n        raise KeyError('k')"),
    )
    code, report = check(capsys, cfg, "--import-modules")
    assert code == 1 and rules(report) == ["module-init"]
    assert "KeyError" in report["errors"][0]["message"]


def test_a_module_that_never_finishes_importing_is_a_finding_not_a_hang(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(probe, "TIMEOUT", 0.8)
    monkeypatch.setattr(probe.import_findings, "__defaults__", (0.8,))
    cfg = config(tmp_path, "import time\ntime.sleep(60)\n" + GOOD)
    code, report = check(capsys, cfg, "--import-modules")
    assert code == 1 and "took more than 0.8 s" in report["errors"][0]["message"]


def test_the_shipped_modules_are_never_imported_by_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[str] = []
    real = probe.import_findings

    def spy(definition: Any, py_path: Path, *a: Any) -> Any:
        seen.append(py_path.name)
        return real(definition, py_path, *a)

    monkeypatch.setattr(probe, "import_findings", spy)
    check(capsys, config(tmp_path, GOOD), "--import-modules")
    assert seen == ["Mine_Module.py"], "only the user's own module, not the 22 that ship"
