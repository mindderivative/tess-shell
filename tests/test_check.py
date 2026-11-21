import json
from pathlib import Path

import pytest

from tess_shell.cli import main

HEAD = "---\nTDL: 0.2\nName: X\n---\n"


def make(cfg: Path, relative: str, body: str) -> Path:
    path = cfg / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEAD + body, encoding="utf-8")
    return path


def test_clean_tree_is_ok(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    make(tmp_path, "Shells/Main_Shell.tdl", "Shell {\n}\n")
    make(tmp_path, "Themes/Dark_Theme.tdl", "Theme {\n}\n")
    assert main(["check", "--config-dir", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "ok: 2 files checked"


def test_unclosed_block_is_located(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    make(tmp_path, "Shells/Foo_Shell.tdl", "Shell {\n")
    assert main(["check", "--config-dir", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "Shells/Foo_Shell.tdl:5:7: error: This block is never closed." in err
    assert "Shell {" in err and "^" in err and "hint:" in err


def test_json_shape(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    make(tmp_path, "Shells/Foo_Shell.tdl", "Shell {\n")
    assert main(["check", "--json", "--config-dir", str(tmp_path)]) == 1
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is False and out["files"] == 1 and out["omitted"] == 0
    (error,) = out["errors"]
    assert (error["file"], error["line"], error["column"]) == ("Shells/Foo_Shell.tdl", 5, 7)
    assert set(error) == {"file", "line", "column", "severity", "rule", "message", "hint"}


def test_more_than_fifty_errors_are_cut(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    for i in range(60):
        make(tmp_path, f"Shells/F{i:02}_Shell.tdl", "Shell {\n")
    assert main(["check", "--config-dir", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert err.count(": error:") == 50
    assert "... and 10 more" in err
    assert main(["check", "--json", "--config-dir", str(tmp_path)]) == 1
    out = json.loads(capsys.readouterr().out)
    assert len(out["errors"]) == 50 and out["omitted"] == 10


def test_editor_leftovers_and_hidden_files_are_not_parsed(tmp_path: Path) -> None:
    for name in (".hidden_Shell.tdl", "x_Shell.tdl~", "y_Shell.tdl.swp", "z_Shell.tdl.bak"):
        make(tmp_path, f"Shells/{name}", "Shell {\n")
    make(tmp_path, "Shells/schemas/s_Shell.tdl", "Shell {\n")
    make(tmp_path, "Shells/notes.tdl", "Shell {\n")
    assert main(["check", "--quiet", "--config-dir", str(tmp_path)]) == 0


def test_bad_encoding(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (tmp_path / "Shells").mkdir()
    (tmp_path / "Shells" / "A_Shell.tdl").write_bytes(b"\xff\xfe bad")
    assert main(["check", "--config-dir", str(tmp_path)]) == 1
    assert "A_Shell.tdl:1:1" in capsys.readouterr().err


def test_bad_settings_stop_before_any_file_scan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make(tmp_path, "settings.tdl", "Settings {\n    Nope: 1\n}\n")
    make(tmp_path, "Shells/Foo_Shell.tdl", "Shell {\n")
    assert main(["check", "--json", "--config-dir", str(tmp_path)]) == 1
    out = json.loads(capsys.readouterr().out)
    assert [e["file"] for e in out["errors"]] == ["settings.tdl"]
    assert out["files"] == 0


def test_missing_config_dir_exits_2_and_creates_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "nope"
    assert main(["check", "--config-dir", str(target)]) == 2
    assert f"config directory does not exist: {target}" in capsys.readouterr().err
    assert not target.exists()


def test_the_m1_example_checks_clean(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from tests.shell_samples import write_example

    write_example(tmp_path)
    assert main(["check", "--config-dir", str(tmp_path)]) == 0
    assert capsys.readouterr().out.strip() == "ok: 1 files checked"


def test_a_wrong_colour_is_reported_with_its_position(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from tests.shell_samples import BODY, write_example

    write_example(tmp_path, BODY.replace('Fill: "#1f1f1f"', 'Fill: "blue"'))
    assert main(["check", "--config-dir", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "Shells/Main_Shell.tdl:" in err and "error:" in err and "#RRGGBB" in err


def test_a_schema_error_and_a_warning_are_both_printed_and_only_the_error_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    from tests.shell_samples import BODY, write_example

    write_example(
        tmp_path, BODY.replace("Height: 32\n", "Height: 32\n                Exclusive_Zone: 30\n")
    )
    assert main(["check", "--config-dir", str(tmp_path)]) == 0
    assert "warning: the Bar key Exclusive_Zone is not built in M1" in capsys.readouterr().err


def test_a_slot_written_with_double_braces_is_refused_with_its_hint(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    make(tmp_path, "Modules/Clock/Clock_Module.tdl", "Module {\n  Text { Text: {{ time }} }\n}\n")
    assert main(["check", "--json", "--config-dir", str(tmp_path)]) == 1
    (error,) = json.loads(capsys.readouterr().out)["errors"]
    assert error["rule"] == "tdl-unexpected-text"
    assert (error["file"], error["line"]) == ("Modules/Clock/Clock_Module.tdl", 6)
    assert error["column"] > 1 and "<| expression |>" in error["message"]
    assert error["hint"] == "Write <| expression |>"


def test_a_file_written_for_tdl_0_1_is_refused_not_read_silently(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "Shells" / "Main_Shell.tdl"
    path.parent.mkdir(parents=True)
    path.write_text("---\nTDL: 0.1\nName: X\n---\nShell {\n}\n", encoding="utf-8")
    assert main(["check", "--json", "--config-dir", str(tmp_path)]) == 1
    (error,) = json.loads(capsys.readouterr().out)["errors"]
    assert error["rule"] == "tdl-old-version"
    assert (error["file"], error["line"], error["column"]) == ("Shells/Main_Shell.tdl", 2, 1)
    assert "TDL 0.1" in error["message"] and "TDL 0.2" in error["message"]
    assert "<| expression |>" in error["hint"] and "TDL: 0.2" in error["hint"]
