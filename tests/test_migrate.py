"""``tesserae-shell migrate`` and the version policy (Version Policy and Migration, M7d).

Every file is migrated in a temporary folder; no test touches a real configuration directory or a
real shell (the single instance lock is taken in a temporary runtime folder).
"""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Iterator
from pathlib import Path

import pytest
import tess_dl

from tess_shell.cli import main
from tess_shell.config.lock import InstanceLock
from tess_shell.files.header import check_header
from tess_shell.migrate.slots import MigrationError, rewrite_slots
from tess_shell.schema import deprecations
from tess_shell.schema.deprecations import Deprecation
from tess_shell.schema.export import schema_dict
from tests.shell_samples import BODY

HEAD01 = "---\nTDL: 0.1\nShell: 0.1\nName: Main_Shell\n---\n"

# a 0.1 file with every case the rewrite must get right: a slot in a template, slots in strings
# (which are text), a quoted close, braces in a slot, an escaped quote, comments that look like
# slots, ``If`` and ``For`` heads, CRLF line ends and a byte-order mark
NASTY_01 = (
    "\ufeff---\r\nTDL: 0.1   # the version {{ not a slot }}\r\nName: X\r\n---\r\n"
    '# a comment with {{ x }} and a stray quote "\r\n'
    "Shell {\r\n"
    "  Monitor { Name: Main, Index: default, Children {\r\n"
    '    Text { Text: Battery {{ battery.percent }}% , Name: "a {{ not }} slot", '
    "Tip: 'it\\'s {{ no }}' }\r\n"
    "    Text { Text: {{ f({'a': 1}) }}, Foreground: {{ hovered ? \"#1e1e2e\" : '}}' }}, "
    "Tip: don't {{ a }} # {{ c }}\r\n"
    '      Name: "esc \\" {{ q }}", Spacing: {{ "|" + \'x\' }} }\r\n'
    "    If {{ battery.low }} { Spacer { } } Else { Spacer { } }\r\n"
    "    For item In {{ items }} Key {{ item.id }} { Text { Text: {{ item.title }} } }\r\n"
    "  } }\r\n"
    "}\r\n"
)


def _slot_texts(node: object) -> list[str]:
    found: list[str] = []
    if isinstance(node, tess_dl.Slot):
        found.append(node.text)
    elif isinstance(node, tess_dl.Template):
        for part in node.parts:
            found += _slot_texts(part)
    elif isinstance(node, tess_dl.Call):
        for arg in node.args:
            found += _slot_texts(arg)
    elif isinstance(node, tess_dl.List):
        for item in node.items:
            found += _slot_texts(item)
    elif isinstance(node, tess_dl.Property):
        found += _slot_texts(node.value)
    elif isinstance(node, tess_dl.Block):
        for entry in node.entries:
            found += _slot_texts(entry)
    elif isinstance(node, tess_dl.If):
        found += _slot_texts(node.condition)
        for entry in node.body + (node.else_body or ()):
            found += _slot_texts(entry)
    elif isinstance(node, tess_dl.For):
        found += _slot_texts(node.items) + _slot_texts(node.key)
        for entry in node.body:
            found += _slot_texts(entry)
    return found


# -- the rewrite of one file -----------------------------------------------------------------------


def test_the_rewrite_changes_only_the_delimiters_and_the_version() -> None:
    new, changes = rewrite_slots(NASTY_01, path="a")
    # the whole text, byte for byte: slots rewritten; metadata, comments, quoted text, CRLF kept
    assert new == (
        "\ufeff---\r\nTDL: 0.2   # the version {{ not a slot }}\r\nName: X\r\n---\r\n"
        '# a comment with {{ x }} and a stray quote "\r\n'
        "Shell {\r\n"
        "  Monitor { Name: Main, Index: default, Children {\r\n"
        '    Text { Text: Battery <| battery.percent |>% , Name: "a {{ not }} slot", '
        "Tip: 'it\\'s {{ no }}' }\r\n"
        "    Text { Text: <| f({'a': 1}) |>, Foreground: <| hovered ? \"#1e1e2e\" : '}}' |>, "
        "Tip: don't <| a |> # {{ c }}\r\n"
        '      Name: "esc \\" {{ q }}", Spacing: <| "|" + \'x\' |> }\r\n'
        "    If <| battery.low |> { Spacer { } } Else { Spacer { } }\r\n"
        "    For item In <| items |> Key <| item.id |> { Text { Text: <| item.title |> } }\r\n"
        "  } }\r\n"
        "}\r\n"
    )
    assert [c.kind for c in changes].count("slot") == 9
    assert [c.kind for c in changes].count("version") == 1
    assert (changes[0].kind, changes[0].line, changes[0].column) == ("version", 2, 6)


def test_the_result_parses_as_tdl_0_2_with_the_same_slots_as_0_1_read() -> None:
    new, _ = rewrite_slots(NASTY_01, path="a")
    result = tess_dl.parse(new.removeprefix("\ufeff"))
    assert result.errors == ()
    assert result.document is not None and result.document.language_version == "0.2"
    # the slot texts, in order, as the TDL 0.1.1 reader gave them for this very file
    assert _slot_texts(result.document.root) == [
        " battery.percent ",
        " f({'a': 1}) ",
        " hovered ? \"#1e1e2e\" : '}}' ",
        " a ",
        " \"|\" + 'x' ",
        " battery.low ",
        " items ",
        " item.id ",
        " item.title ",
    ]


def test_a_second_pass_changes_nothing() -> None:
    once, _ = rewrite_slots(NASTY_01, path="a")
    twice, changes = rewrite_slots(once, path="a")
    assert twice == once and changes == []


def test_a_file_already_at_tdl_0_2_is_left_alone_even_with_braces_in_its_text() -> None:
    text = '---\nTDL: 0.2\nName: X\n---\nShell {\n  Text { Text: a {{ b }}, Tip: "{{ c }}" }\n}\n'
    assert rewrite_slots(text, path="a") == (text, [])


def test_a_slot_text_with_the_new_close_outside_a_quote_is_refused_with_its_position() -> None:
    text = HEAD01 + "Shell {\n  Text { Text: {{ a |> b }} }\n}\n"
    with pytest.raises(MigrationError) as raised:
        rewrite_slots(text, path="a")
    assert (raised.value.line, raised.value.column) == (7, 16) and "|>" in str(raised.value)
    # inside a quote the same characters are fine
    quoted, _ = rewrite_slots(text.replace("a |> b", '"|>"'), path="a")
    assert '<| "|>" |>' in quoted


def test_a_slot_with_no_close_on_its_line_is_refused() -> None:
    text = HEAD01 + "Shell {\n  Text { Text: {{ a\n }}\n}\n"
    with pytest.raises(MigrationError, match="no }} on its line"):
        rewrite_slots(text, path="a")


# -- the command -----------------------------------------------------------------------------------


def _old_config(root: Path) -> dict[str, bytes]:
    """A 0.1-era folder: a shell file with a slot, a module with a slot, a file with none, and a
    file already at 0.2. Returns the original bytes of each file by relative path."""
    old_body = BODY.replace(
        'Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }',
        'Text { Text: Time {{ 1 + 1 }}, Font_Size: 14, Foreground: "#ffffff" }',
    )
    files = {
        "Shells/Main_Shell.tdl": HEAD01 + old_body,
        "Themes/Plain_Theme.tdl": "---\nTDL: 0.1\nName: Plain\n---\nTheme {\n}\n",
        "Styles/Fresh_Style.tdl": "---\nTDL: 0.2\nName: Fresh\n---\nStyle {\n}\n",
    }
    out: dict[str, bytes] = {}
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text.encode())
        out[name] = text.encode()
    (root / "Shells" / "dot.svg").write_text("<svg/>")
    return out


def _snapshot(root: Path) -> dict[str, bytes]:
    return {
        str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()
    }


@pytest.fixture
def runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    run = tmp_path / "runtime"
    run.mkdir(mode=0o700)
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(run))
    yield run


def test_check_lists_the_files_exits_1_and_changes_nothing(
    tmp_path: Path, runtime: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = tmp_path / "cfg"
    _old_config(cfg)
    before = _snapshot(cfg)
    assert main(["migrate", "--check", "--config-dir", str(cfg)]) == 1
    out = capsys.readouterr().out
    assert "would change: Shells/Main_Shell.tdl" in out
    assert "would change: Themes/Plain_Theme.tdl" in out
    assert "Styles/Fresh_Style.tdl" not in out
    assert "2 file(s) to change" in out
    assert _snapshot(cfg) == before  # not a byte, and no backup folder


def test_migrate_rewrites_backs_up_and_the_result_passes_check(
    tmp_path: Path, runtime: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = tmp_path / "cfg"
    originals = _old_config(cfg)
    assert main(["check", "--config-dir", str(cfg)]) == 1  # refused before: TDL 0.1
    capsys.readouterr()
    assert main(["migrate", "--config-dir", str(cfg)]) == 0
    out = capsys.readouterr().out
    assert "changed: Shells/Main_Shell.tdl" in out and "check: ok" in out
    shell = (cfg / "Shells/Main_Shell.tdl").read_text()
    assert "TDL: 0.2" in shell and "<| 1 + 1 |>" in shell and "{{" not in shell
    assert "TDL: 0.2" in (cfg / "Themes/Plain_Theme.tdl").read_text()
    assert (cfg / "Styles/Fresh_Style.tdl").read_bytes() == originals["Styles/Fresh_Style.tdl"]
    (backup,) = (cfg / ".migrate-backup").iterdir()
    assert {
        str(p.relative_to(backup)): p.read_bytes() for p in backup.rglob("*") if p.is_file()
    } == {
        "Shells/Main_Shell.tdl": originals["Shells/Main_Shell.tdl"],
        "Themes/Plain_Theme.tdl": originals["Themes/Plain_Theme.tdl"],
    }
    assert main(["check", "--config-dir", str(cfg)]) == 0  # now it passes


def test_a_second_run_changes_nothing_and_exits_0(
    tmp_path: Path, runtime: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = tmp_path / "cfg"
    _old_config(cfg)
    assert main(["migrate", "--config-dir", str(cfg)]) == 0
    capsys.readouterr()
    migrated = _snapshot(cfg)  # includes the first run's backup
    assert main(["migrate", "--config-dir", str(cfg)]) == 0
    assert "0 file(s) changed" in capsys.readouterr().out
    assert _snapshot(cfg) == migrated  # no new backup, the backup copies are not migrated
    assert main(["migrate", "--check", "--config-dir", str(cfg)]) == 0


def test_json_has_the_steps_the_files_and_the_skipped(
    tmp_path: Path, runtime: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = tmp_path / "cfg"
    _old_config(cfg)
    bad = cfg / "Shells" / "Bad_Shell.tdl"
    bad.write_text(HEAD01 + "Shell {\n  Text { Text: {{ a |> b }} }\n}\n")
    assert main(["migrate", "--check", "--json", "--config-dir", str(cfg)]) == 2
    got = json.loads(capsys.readouterr().out)
    assert got["ok"] is False and got["check"] is True and got["backup"] is None
    (step,) = got["steps"]
    assert (step["step"], step["from"], step["to"]) == ("0001", "TDL 0.1", "TDL 0.2")
    assert step["files"] == [
        {"path": "Shells/Main_Shell.tdl", "state": "would-change"},
        {"path": "Themes/Plain_Theme.tdl", "state": "would-change"},
    ]
    (skipped,) = got["skipped"]
    assert (skipped["path"], skipped["step"], skipped["line"]) == (
        "Shells/Bad_Shell.tdl",
        "0001",
        7,
    )


def test_an_unmigratable_file_is_left_whole_and_the_others_are_migrated(
    tmp_path: Path, runtime: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = tmp_path / "cfg"
    _old_config(cfg)
    bad = cfg / "Shells" / "Bad_Shell.tdl"
    # one good slot before the bad one: a half rewrite would show in the bytes
    bad.write_text(HEAD01 + "Shell {\n  Text { Text: {{ a }}, Tip: {{ a |> b }} }\n}\n")
    original = bad.read_bytes()
    assert main(["migrate", "--json", "--config-dir", str(cfg)]) == 2
    got = json.loads(capsys.readouterr().out)
    assert got["ok"] is False and got["skipped"][0]["path"] == "Shells/Bad_Shell.tdl"
    assert bad.read_bytes() == original
    assert "<| 1 + 1 |>" in (cfg / "Shells/Main_Shell.tdl").read_text()
    # the backup holds only what was rewritten
    (backup,) = (cfg / ".migrate-backup").iterdir()
    assert not (backup / "Shells/Bad_Shell.tdl").exists()


def test_a_read_only_folder_is_exit_2_and_the_other_files_are_still_migrated(
    tmp_path: Path, runtime: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = tmp_path / "cfg"
    originals = _old_config(cfg)
    themes = cfg / "Themes"
    themes.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        assert main(["migrate", "--json", "--config-dir", str(cfg)]) == 2
    finally:
        themes.chmod(stat.S_IRWXU)
    got = json.loads(capsys.readouterr().out)
    (skipped,) = got["skipped"]
    assert skipped["path"] == "Themes/Plain_Theme.tdl" and "cannot write" in skipped["message"]
    assert (themes / "Plain_Theme.tdl").read_bytes() == originals["Themes/Plain_Theme.tdl"]
    assert [f["path"] for f in got["steps"][0]["files"]] == ["Shells/Main_Shell.tdl"]
    assert not [p for p in cfg.rglob("*.migrate-tmp")]


def test_a_failed_rename_leaves_the_file_as_it_was_and_no_temporary_file(
    tmp_path: Path, runtime: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = tmp_path / "cfg"
    originals = _old_config(cfg)

    def refuse(src: object, dst: object) -> None:
        raise OSError(5, "Input/output error")

    monkeypatch.setattr(os, "replace", refuse)
    assert main(["migrate", "--config-dir", str(cfg)]) == 2
    monkeypatch.undo()
    assert (cfg / "Shells/Main_Shell.tdl").read_bytes() == originals["Shells/Main_Shell.tdl"]
    assert not list(cfg.rglob("*.migrate-tmp")) and not list(cfg.rglob(".*.migrate-tmp"))


def test_a_file_mode_survives_the_rewrite(tmp_path: Path, runtime: Path) -> None:
    cfg = tmp_path / "cfg"
    _old_config(cfg)
    path = cfg / "Shells/Main_Shell.tdl"
    path.chmod(0o640)
    assert main(["migrate", "--config-dir", str(cfg)]) == 0
    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_a_link_that_leaves_the_folder_is_not_written(tmp_path: Path, runtime: Path) -> None:
    cfg = tmp_path / "cfg"
    _old_config(cfg)
    outside = tmp_path / "outside_Theme.tdl"
    outside.write_text("---\nTDL: 0.1\nName: O\n---\nTheme {\n}\n")
    (cfg / "Themes" / "Out_Theme.tdl").symlink_to(outside)
    assert main(["migrate", "--config-dir", str(cfg)]) == 0
    assert "TDL: 0.1" in outside.read_text()


def test_a_missing_config_directory_is_the_environment_code(
    tmp_path: Path, runtime: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["migrate", "--config-dir", str(tmp_path / "nope")]) == 2
    assert "config directory does not exist" in capsys.readouterr().err


def test_it_refuses_while_a_shell_holds_the_lock_unless_forced(
    tmp_path: Path, runtime: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = tmp_path / "cfg"
    originals = _old_config(cfg)
    lock = InstanceLock()
    lock.acquire(runtime)
    try:
        assert main(["migrate", "--config-dir", str(cfg)]) == 4
        assert "is running" in capsys.readouterr().err
        assert _snapshot(cfg) == {**originals, "Shells/dot.svg": b"<svg/>"}
        # --check only looks, so a running shell does not stop it
        assert main(["migrate", "--check", "--config-dir", str(cfg)]) == 1
        capsys.readouterr()
        assert main(["migrate", "--force", "--config-dir", str(cfg)]) == 0
    finally:
        lock.release()
    assert "TDL: 0.2" in (cfg / "Shells/Main_Shell.tdl").read_text()


def test_it_does_not_refuse_when_no_shell_holds_the_lock_and_never_creates_it(
    tmp_path: Path, runtime: Path
) -> None:
    cfg = tmp_path / "cfg"
    _old_config(cfg)
    assert main(["migrate", "--config-dir", str(cfg)]) == 0
    assert not (runtime / "tesserae-shell").exists()


# -- the version policy: the pins and the refusals -------------------------------------------------


def _doc(meta: str) -> tess_dl.Document:
    result = tess_dl.parse(f"---\nTDL: 0.2\nName: X\n{meta}---\nShell {{\n}}\n")
    assert result.document is not None
    return result.document


def test_a_shell_pin_newer_than_the_shell_is_shell_too_old_with_position_and_hint() -> None:
    installed = {"Shell": "0.2.0", "TRE": "0.6.9", "TEL": "0.2.0"}
    (f,) = check_header(_doc("Shell: 0.3\n"), "Shells/a_Shell.tdl", installed)
    assert f.rule == "shell-too-old" and f.severity == "error"
    assert (f.line, f.column) == (4, 1)
    assert f.hint == "install tesserae-shell 0.3 or later"
    assert "0.3" in f.message and "0.2.0" in f.message
    # the pin is a major.minor release: 0.2.9 against 0.2.0 is not too new
    assert check_header(_doc("Shell: 0.2.9\n"), "a_Shell.tdl", installed) == []
    # a TRE pin keeps its own rule
    (g,) = check_header(_doc("TRE: 0.7.0\n"), "a_Shell.tdl", installed)
    assert g.rule == "version-pin"


def test_a_file_with_a_newer_shell_pin_is_refused_by_check(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "Shells" / "Main_Shell.tdl"
    path.parent.mkdir()
    path.write_text("---\nTDL: 0.2\nShell: 99.0\nName: X\n---\nShell {\n}\n")
    assert main(["check", "--json", "--config-dir", str(tmp_path)]) == 1
    (error,) = json.loads(capsys.readouterr().out)["errors"]
    assert (error["rule"], error["file"], error["line"]) == (
        "shell-too-old",
        "Shells/Main_Shell.tdl",
        3,
    )
    assert error["hint"] == "install tesserae-shell 99.0 or later"


def test_a_tdl_0_1_file_with_a_slot_is_refused_with_the_migrate_hint_not_a_syntax_error(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "Shells" / "Main_Shell.tdl"
    path.parent.mkdir()
    path.write_text(HEAD01 + "Shell {\n  Text { Text: {{ a }} }\n}\n")
    assert main(["check", "--json", "--config-dir", str(tmp_path)]) == 1
    (error,) = json.loads(capsys.readouterr().out)["errors"]
    assert error["rule"] == "tdl-old-version"
    assert (error["line"], error["column"]) == (2, 1)
    assert "tesserae-shell migrate" in error["hint"]


# -- deprecations ----------------------------------------------------------------------------------


@pytest.fixture
def renamed(monkeypatch: pytest.MonkeyPatch) -> tuple[Deprecation, ...]:
    table = (
        Deprecation("key", "Spacing", "Gap", "0.3", "0.5", block="FlexBox"),
        Deprecation("block", "Spacer", "Gap_Box", "0.3", "0.5"),
        Deprecation("command", "reload", "refresh", "0.3", "0.5"),
    )
    monkeypatch.setattr(deprecations, "DEPRECATIONS", table)
    return table


def test_a_deprecated_key_warns_with_the_replacement_and_the_release_that_removes_it(
    renamed: tuple[Deprecation, ...], tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "Shells" / "Main_Shell.tdl"
    path.parent.mkdir()
    path.write_text(HEAD01.replace("0.1", "0.2", 1) + BODY)
    (dot := path.parent / "dot.svg").write_text("<svg/>")
    assert dot.exists()
    assert main(["check", "--json", "--config-dir", str(tmp_path)]) == 0  # a warning is not a stop
    got = json.loads(capsys.readouterr().out)
    warnings = [
        e
        for e in got["errors"]
        if e["rule"] == "deprecated-key" and e["file"] == "Shells/Main_Shell.tdl"
    ]
    assert {(w["line"], w["column"]) for w in warnings} == {(22, 25), (26, 29)}
    spacing = next(w for w in warnings if w["line"] == 22)
    assert spacing["severity"] == "warning"
    assert spacing["message"] == "Spacing is deprecated since 0.3 and is removed in 0.5; use Gap"
    assert "migrate" in spacing["hint"]


def test_migrate_renames_a_deprecated_key_and_block_changing_only_their_names(
    renamed: tuple[Deprecation, ...], tmp_path: Path, runtime: Path
) -> None:
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    text = HEAD01.replace("0.1", "0.2", 1) + BODY
    path = cfg / "Main_Shell.tdl"
    path.write_text(text)
    assert main(["migrate", "--check", "--config-dir", str(cfg)]) == 1
    assert main(["migrate", "--config-dir", str(cfg)]) == 0
    new = path.read_text()
    assert new == text.replace("Spacing: 8", "Gap: 8").replace("Spacer { }", "Gap_Box { }")
    assert main(["migrate", "--check", "--config-dir", str(cfg)]) == 0  # idempotent


def test_the_schema_export_marks_a_deprecated_key_and_block(
    renamed: tuple[Deprecation, ...],
) -> None:
    blocks = schema_dict()["blocks"]
    assert blocks["FlexBox"]["keys"]["Spacing"]["deprecated"] == {
        "since": "0.3",
        "removed_in": "0.5",
        "use": "Gap",
    }
    assert blocks["Spacer"]["deprecated"]["use"] == "Gap_Box"
    assert "deprecated" not in blocks["FlexBox"]["keys"]["Padding"]


def test_the_export_has_no_deprecated_mark_when_nothing_is_deprecated() -> None:
    assert not deprecations.DEPRECATIONS
    blocks = schema_dict()["blocks"]
    assert not any(
        "deprecated" in spec or any("deprecated" in k for k in spec["keys"].values())
        for spec in blocks.values()
    )


def test_a_deprecated_command_warns_on_standard_error_and_still_runs(
    renamed: tuple[Deprecation, ...], capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    from tests.fake_dbus import fake_bus

    with fake_bus() as bus:
        os.environ["DBUS_SESSION_BUS_ADDRESS"] = bus.address
        try:
            code = main(["reload"])
        finally:
            del os.environ["DBUS_SESSION_BUS_ADDRESS"]
    assert code == 3  # no shell: the command still ran
    err = capsys.readouterr().err
    assert (
        "deprecated-command: reload is deprecated since 0.3 and is removed in 0.5; use refresh"
        in err
    )
