from pathlib import Path

import pytest

from tess_shell.config.settings import Settings, load_settings
from tess_shell.schema.findings import Finding

HEAD = "---\nTDL: 0.1\nName: Settings\n---\n"


def write(cfg: Path, body: str) -> None:
    (cfg / "settings.tdl").write_text(HEAD + body, encoding="utf-8")


def load_ok(cfg: Path) -> Settings:
    settings, findings = load_settings(cfg)
    assert findings == []
    assert settings is not None
    return settings


def load_bad(cfg: Path) -> list[Finding]:
    settings, findings = load_settings(cfg)
    assert settings is None
    assert findings
    return findings


def test_no_file_gives_defaults(tmp_path: Path) -> None:
    s = load_ok(tmp_path)
    assert (s.logging.level, s.logging.format, s.logging.console) == ("INFO", "TEXT", True)
    assert s.main_shell == "Main_Shell.tdl" and s.main_shell_path is None
    assert s.registry == tmp_path / "registry.json"
    assert s.validation_enabled is True


def test_every_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    for d in ("a", "b", "Shells"):
        (tmp_path / d).mkdir()
    (tmp_path / "Shells" / "Mine_Shell.tdl").write_text("x")
    write(
        tmp_path,
        f"""Settings {{
    Main_Shell: Mine_Shell.tdl
    Registry: "{tmp_path}/reg.json"
    Directories {{
        Shells: [~/a, "$HOME/b"]
        Themes: ~/a
    }}
    Logging {{
        Level: DEBUG
        Directory: ~/logs
        Retention: 7
        Format: JSON
        Diagnose: true
        Console: false
        Capture_Stderr: false
    }}
    Validation {{ Enabled: false }}
}}
""",
    )
    s = load_ok(tmp_path)
    assert s.directories["Shells"] == (tmp_path / "a", tmp_path / "b", tmp_path / "Shells")
    assert s.directories["Themes"] == (tmp_path / "a",)
    assert s.main_shell_path == tmp_path / "Shells" / "Mine_Shell.tdl"
    assert s.registry == tmp_path / "reg.json"
    lg = s.logging
    assert (lg.level, lg.format, lg.retention) == ("DEBUG", "JSON", 7)
    assert lg.directory == tmp_path / "logs"
    assert (lg.diagnose, lg.console, lg.capture_stderr) == (True, False, False)
    assert s.validation_enabled is False


def test_unknown_key_suggests_nearest(tmp_path: Path) -> None:
    write(tmp_path, "Settings {\n    Logging {\n        Levl: INFO\n    }\n}\n")
    (f,) = load_bad(tmp_path)
    assert (f.rule, f.line, f.column) == ("unknown-key", 7, 9)
    assert "Level" in f.hint


def test_lowercase_enum_says_upper_case(tmp_path: Path) -> None:
    write(tmp_path, "Settings {\n    Logging { Level: info }\n}\n")
    (f,) = load_bad(tmp_path)
    assert f.rule == "bad-value" and "write INFO" in f.hint


def test_bad_bool_and_retention(tmp_path: Path) -> None:
    write(
        tmp_path,
        "Settings {\n    Logging {\n        Console: yes\n        Retention: -1\n    }\n}\n",
    )
    assert [f.line for f in load_bad(tmp_path)] == [7, 8]


def test_relative_path(tmp_path: Path) -> None:
    write(tmp_path, "Settings {\n    Directories { Shells: some/dir }\n}\n")
    (f,) = load_bad(tmp_path)
    assert f.rule == "relative-path"


def test_unset_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TESS_UNSET_VAR", raising=False)
    write(tmp_path, "Settings {\n    Directories { Shells: $TESS_UNSET_VAR/x }\n}\n")
    (f,) = load_bad(tmp_path)
    assert f.rule == "unresolved-path" and "TESS_UNSET_VAR" in f.message


def test_missing_directory(tmp_path: Path) -> None:
    write(tmp_path, f'Settings {{\n    Directories {{ Shells: "{tmp_path}/nope" }}\n}}\n')
    (f,) = load_bad(tmp_path)
    assert f.rule == "missing-directory"


def test_explicit_main_shell_missing_lists_directories(tmp_path: Path) -> None:
    (tmp_path / "Shells").mkdir()
    write(tmp_path, "Settings {\n    Main_Shell: Gone.tdl\n}\n")
    (f,) = load_bad(tmp_path)
    assert f.rule == "main-shell-not-found" and str(tmp_path / "Shells") in f.message


def test_wrong_root_block(tmp_path: Path) -> None:
    write(tmp_path, "Shell {\n}\n")
    (f,) = load_bad(tmp_path)
    assert f.rule == "settings-root" and "Settings { }" in f.hint


def test_syntax_error_reported_alone_with_position(tmp_path: Path) -> None:
    write(tmp_path, "Settings {\n    Bogus: 1\n")
    (f,) = load_bad(tmp_path)
    assert (f.file, f.rule, f.line) == ("settings.tdl", "tdl-unclosed-block", 5)


def test_block_written_as_property_is_one_error(tmp_path: Path) -> None:
    write(tmp_path, "Settings {\n    Directories: x\n}\n")
    findings = load_bad(tmp_path)
    assert [f.rule for f in findings] == ["bad-value"]


def test_configured_directory_listed_before_default(tmp_path: Path) -> None:
    (tmp_path / "Styles").mkdir()
    (tmp_path / "extra").mkdir()
    write(tmp_path, f'Settings {{\n    Directories {{ Styles: "{tmp_path}/extra" }}\n}}\n')
    assert load_ok(tmp_path).directories["Styles"] == (tmp_path / "extra", tmp_path / "Styles")


def test_multiple_problems_all_collected(tmp_path: Path) -> None:
    write(tmp_path, "Settings {\n    Nope: 1\n    Logging { Level: x }\n}\n")
    assert len(load_bad(tmp_path)) == 2
