"""``Import:`` of module files, nested module calls, and cycles (Module File > Using a Module)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tess_shell.cli import main

HEAD = "---\nTDL: 0.1\nName: {name}\n---\n"

SHELL = """
Shell {{
    Monitor {{
        Name: Main
        Index: 0
        Children {{
            Bar {{
                Name: Top
                Edge: TOP
                Width: EXPAND
                Height: 32
                Children {{
{children}
                }}
            }}
        }}
    }}
}}
"""


def module(config: Path, name: str, body: str) -> Path:
    folder = config / "Modules" / name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{name}_Module.tdl"
    path.write_text(HEAD.format(name=name) + body)
    (folder / f"{name}_Module.py").write_text(
        "from tess_shell import Module\n\nclass M(Module):\n    pass\n"
    )
    return path


def shell(config: Path, children: str) -> Path:
    (config / "Shells").mkdir(parents=True, exist_ok=True)
    path = config / "Shells" / "Main_Shell.tdl"
    path.write_text(HEAD.format(name="Main_Shell") + SHELL.format(children=children))
    return path


def check(config: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, dict[str, object]]:
    code = main(["check", "--json", "--config-dir", str(config)])
    return code, json.loads(capsys.readouterr().out)


def rules(report: dict[str, object]) -> list[str]:
    return [e["rule"] for e in report["errors"]]  # type: ignore[index, union-attr]


LABEL = "Module {\n    Text { Text: hi }\n}\n"


def test_import_embeds_a_module_file_by_a_relative_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module(tmp_path, "Label", LABEL)
    shell(tmp_path, "Import: ../Modules/Label/Label_Module.tdl")
    code, report = check(tmp_path, capsys)
    assert code == 0 and report["ok"] is True, report


def test_a_list_of_imports_and_a_call_in_one_children_block(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module(tmp_path, "Label", LABEL)
    module(tmp_path, "Other", LABEL)
    shell(
        tmp_path,
        "Import: [../Modules/Label/Label_Module.tdl, ../Modules/Other/Other_Module.tdl]\nLabel { }",
    )
    assert check(tmp_path, capsys)[0] == 0


def test_an_import_that_is_not_a_module_file_says_so_with_its_position(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module(tmp_path, "Label", LABEL)
    path = shell(tmp_path, "Import: ../Modules/Nope/Nope_Module.tdl")
    code, report = check(tmp_path, capsys)
    assert code == 1 and rules(report) == ["import-not-found"]
    (error,) = report["errors"]  # type: ignore[misc]
    line = next(i for i, t in enumerate(path.read_text().splitlines(), 1) if "Import:" in t)
    assert error["line"] == line and "Nope_Module.tdl" in error["message"]  # type: ignore[index]


def test_importing_a_shell_file_is_not_built_yet(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    shell(tmp_path, "Import: Other_Shell.tdl")
    code, report = check(tmp_path, capsys)
    assert code == 1 and rules(report) == ["not-built"]


def test_a_module_may_call_another_in_any_file_order(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # "Aaa" sorts before "Label", and calls it
    module(tmp_path, "Aaa", "Module {\n    Box { Children { Label { } } }\n}\n")
    module(tmp_path, "Label", LABEL)
    shell(tmp_path, "Aaa { }")
    code, report = check(tmp_path, capsys)
    assert code == 0, report


def test_a_module_that_imports_another_by_path(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module(tmp_path, "Label", LABEL)
    module(
        tmp_path,
        "Pair",
        "Module {\n    FlexBox { Children {\n"
        "        Import: ../Label/Label_Module.tdl\n        Label { }\n    } }\n}\n",
    )
    shell(tmp_path, "Pair { }")
    assert check(tmp_path, capsys)[0] == 0


def test_a_cycle_names_the_chain_once(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    module(tmp_path, "Aa", "Module {\n    Box { Children { Bb { } } }\n}\n")
    module(tmp_path, "Bb", "Module {\n    Box { Children { Cc { } } }\n}\n")
    module(tmp_path, "Cc", "Module {\n    Box { Children { Aa { } } }\n}\n")
    shell(tmp_path, "Aa { }")
    code, report = check(tmp_path, capsys)
    assert code == 1
    (error,) = [e for e in report["errors"] if e["rule"] == "import-cycle"]  # type: ignore[union-attr]
    assert "Aa -> Bb -> Cc -> Aa" in error["message"]
    assert error["file"].endswith("Aa_Module.tdl")


def test_a_module_that_calls_itself_is_a_cycle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module(tmp_path, "Loop", "Module {\n    Box { Children { Loop { } } }\n}\n")
    shell(tmp_path, "Loop { }")
    code, report = check(tmp_path, capsys)
    assert code == 1 and "Loop -> Loop" in report["errors"][0]["message"]  # type: ignore[index]


def test_two_user_modules_with_one_name_are_an_error_naming_both(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module(tmp_path, "Label", LABEL)
    other = tmp_path / "Modules" / "Copy"
    other.mkdir()
    (other / "Copy_Module.tdl").write_text(HEAD.format(name="Label") + LABEL)
    (other / "Copy_Module.py").write_text("")
    code, report = check(tmp_path, capsys)
    assert code == 1 and rules(report) == ["name-duplicate"]
    error = report["errors"][0]  # type: ignore[index]
    named = error["file"] + error["message"]
    assert "Label_Module.tdl" in named and "Copy_Module.tdl" in named


def test_a_user_module_overrides_the_shipped_clock(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module(tmp_path, "Clock", "Module {\n    Text { Text: mine }\n}\n")
    shell(tmp_path, "Clock { }")
    code, report = check(tmp_path, capsys)
    assert code == 0, report
