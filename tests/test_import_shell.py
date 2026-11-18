"""``Import:`` of another ``_Shell.tdl`` in a Monitor's ``Children`` (Shell File > Structure, D22):
a shell split over several files. The imported file holds surface blocks only and takes the
importing Monitor's monitor; the surfaces come in at the position of the Import."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tess_shell.binder.model import Length
from tess_shell.cli import main
from tess_shell.config.settings import load_settings
from tess_shell.scanner import Scan, scan

HEAD = "---\nTDL: 0.2\nName: {name}\n---\n"

MAIN = """Shell {{
    Monitor {{
        Name: Main
        Index: 0
        Children {{
{children}
        }}
    }}
}}
"""

BAR = "Bar {{ Name: {name}, Edge: {edge}, Width: EXPAND, Height: {height} }}"


def bar(name: str, edge: str = "TOP", height: int = 32) -> str:
    return BAR.format(name=name, edge=edge, height=height)


def write(cfg: Path, relative: str, body: str) -> Path:
    path = cfg / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(HEAD.format(name=path.stem) + body)
    return path


def main_shell(cfg: Path, children: str) -> Path:
    return write(cfg, "Shells/Main_Shell.tdl", MAIN.format(children=children))


def surfaces(cfg: Path, *lines: str, relative: str = "Shells/Bottom_Shell.tdl") -> Path:
    return write(cfg, relative, "Shell {\n" + "\n".join(lines) + "\n}\n")


def check(cfg: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, list[dict[str, Any]]]:
    code = main(["check", "--json", "--config-dir", str(cfg)])
    found = json.loads(capsys.readouterr().out)["errors"]
    assert isinstance(found, list)
    return code, found


def where(path: Path, needle: str) -> tuple[int, int]:
    """The line and column of the first ``needle`` in ``path``."""
    for number, text in enumerate(path.read_text().splitlines(), 1):
        if needle in text:
            return number, text.index(needle) + 1
    raise AssertionError(needle)


def run_scan(cfg: Path) -> Scan:
    settings, findings = load_settings(cfg)
    assert settings is not None, findings
    return scan(settings, cfg)


# -- what a split shell is ----------------------------------------------------------------------


def test_a_shell_split_over_two_files_has_the_surfaces_of_both_in_the_order_written(
    tmp_path: Path,
) -> None:
    main_shell(
        tmp_path,
        f"{bar('First')}\nImport: Bottom_Shell.tdl\n{bar('Last', 'LEFT')}",
    )
    surfaces(tmp_path, bar("From_File", "BOTTOM", 24), bar("Second_From_File", "RIGHT"))
    result = run_scan(tmp_path)
    assert result.errors == []
    shell = result.shells[tmp_path / "Shells" / "Main_Shell.tdl"]
    (monitor,) = shell.monitors
    # the imported file's surfaces come in where the Import is, not at the end
    assert [s.name for s in monitor.surfaces] == ["First", "From_File", "Second_From_File", "Last"]
    assert [s.origin.file for s in monitor.surfaces] == [
        "Shells/Main_Shell.tdl",
        "Shells/Bottom_Shell.tdl",
        "Shells/Bottom_Shell.tdl",
        "Shells/Main_Shell.tdl",
    ]
    assert monitor.surfaces[1].height == Length(24)


def test_a_list_of_imports_and_imports_that_nest(tmp_path: Path) -> None:
    # Main imports A and B; A imports C by a path relative to A's own folder
    main_shell(tmp_path, "Import: [Parts/A_Shell.tdl, Parts/B_Shell.tdl]")
    surfaces(tmp_path, "Import: Deep/C_Shell.tdl", bar("In_A"), relative="Shells/Parts/A_Shell.tdl")
    surfaces(tmp_path, bar("In_B", "LEFT"), relative="Shells/Parts/B_Shell.tdl")
    surfaces(tmp_path, bar("In_C", "RIGHT"), relative="Shells/Parts/Deep/C_Shell.tdl")
    result = run_scan(tmp_path)
    assert result.errors == []
    (monitor,) = result.shells[tmp_path / "Shells" / "Main_Shell.tdl"].monitors
    assert [s.name for s in monitor.surfaces] == ["In_C", "In_A", "In_B"]


def test_a_panel_of_one_file_may_attach_to_a_bar_of_the_other(tmp_path: Path) -> None:
    main_shell(
        tmp_path,
        "Import: Bottom_Shell.tdl\n"
        "Panel { Name: Menu, Attach_To: Bottom_Bar, Attach: TOP, Alignment: START,"
        " Width: 200, Height: 100 }",
    )
    surfaces(tmp_path, bar("Bottom_Bar", "BOTTOM", 24))
    assert run_scan(tmp_path).errors == []


def test_a_file_of_surfaces_that_nothing_imports_is_not_an_error(tmp_path: Path) -> None:
    main_shell(tmp_path, bar("Only"))
    surfaces(tmp_path, bar("Spare", "BOTTOM"))
    result = run_scan(tmp_path)
    assert result.findings == []
    (monitor,) = result.shells[tmp_path / "Shells" / "Main_Shell.tdl"].monitors
    assert [s.name for s in monitor.surfaces] == ["Only"]  # nothing of it is shown


def test_an_imported_file_outside_the_shells_folder_gets_its_uid_like_any_shell_file(
    tmp_path: Path,
) -> None:
    main_shell(tmp_path, "Import: ../Parts/Top_Shell.tdl")
    part = surfaces(tmp_path, bar("Up"), relative="Parts/Top_Shell.tdl")
    result = run_scan(tmp_path)
    assert result.errors == []
    assert result.imported == (part,)
    assert set(result.shell_files) == {part, tmp_path / "Shells" / "Main_Shell.tdl"}
    assert result.count == 1  # only the discovered files count; the imported one is not in a folder


# -- errors -------------------------------------------------------------------------------------


def test_a_mistake_in_the_imported_file_is_reported_in_that_file_with_its_position(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main_shell(tmp_path, "Import: Bottom_Shell.tdl")
    part = surfaces(tmp_path, "Bar { Name: Low, Edge: BOTTOM, Width: EXPAND, Height: 24x }")
    code, found = check(tmp_path, capsys)
    assert code == 1
    line, column = where(part, "24x")
    (bad,) = [e for e in found if e["rule"] != "import-failed"]
    assert (bad["file"], bad["line"], bad["column"]) == ("Shells/Bottom_Shell.tdl", line, column)
    # reported once although the file is read alone and by the file that imports it
    assert len(found) == 1


def test_a_syntax_error_in_the_imported_file_is_reported_at_its_line_and_column(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main = main_shell(tmp_path, "Import: Parts/Low_Shell.tdl")
    part = write(tmp_path, "Shells/Parts/Low_Shell.tdl", "Shell {\n    Bar {\n")
    code, found = check(tmp_path, capsys)
    assert code == 1
    syntax = [e for e in found if e["file"] == "Shells/Parts/Low_Shell.tdl"]
    # the parser reports each block that is never closed, at the block's own position
    assert [e["rule"] for e in syntax] == ["tdl-unclosed-block"] * 2
    # (at the opening brace of the Shell on line 5 and of the Bar on line 6)
    assert {(e["line"], e["column"]) for e in syntax} == {(5, 7), (6, 9)}
    assert part.read_text().splitlines()[4] == "Shell {"
    # and the importer says which import it was, at the Import's own position
    (pointer,) = [e for e in found if e["rule"] == "import-failed"]
    line, column = where(main, "Parts/Low_Shell.tdl")
    assert (pointer["file"], pointer["line"], pointer["column"]) == (
        "Shells/Main_Shell.tdl",
        line,
        column,
    )


def test_a_file_that_is_not_a_shell_file_is_refused_with_both_names(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main_shell(tmp_path, "Import: Wrong_Shell.tdl")
    write(tmp_path, "Shells/Wrong_Shell.tdl", "Module { Text { Text: hi } }\n")
    code, found = check(tmp_path, capsys)
    assert code == 1
    assert {e["rule"] for e in found} == {"shell-root-suffix", "import-failed"}


def test_a_circle_of_imports_names_the_chain(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main_shell(tmp_path, "Import: A_Shell.tdl")
    surfaces(tmp_path, "Import: B_Shell.tdl", relative="Shells/A_Shell.tdl")
    b = surfaces(tmp_path, "Import: A_Shell.tdl", relative="Shells/B_Shell.tdl")
    code, found = check(tmp_path, capsys)
    assert code == 1
    cycles = [e for e in found if e["rule"] == "import-cycle"]
    # reported where the circle closes (B's import of A), with the files in order
    assert any(
        e["file"] == "Shells/B_Shell.tdl"
        and (e["line"], e["column"]) == where(b, "A_Shell.tdl")
        and "Shells/A_Shell.tdl -> Shells/B_Shell.tdl -> Shells/A_Shell.tdl" in e["message"]
        for e in cycles
    ), cycles


def test_a_file_that_imports_itself_is_a_circle_of_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main_shell(tmp_path, "Import: Self_Shell.tdl")
    surfaces(tmp_path, "Import: Self_Shell.tdl", relative="Shells/Self_Shell.tdl")
    code, found = check(tmp_path, capsys)
    assert code == 1 and any(e["rule"] == "import-cycle" for e in found)


def test_the_main_shell_imported_back_is_a_circle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main_shell(tmp_path, "Import: A_Shell.tdl")
    surfaces(tmp_path, "Import: Main_Shell.tdl", relative="Shells/A_Shell.tdl")
    code, found = check(tmp_path, capsys)
    assert code == 1
    (cycle,) = [e for e in found if e["rule"] == "import-cycle"]
    assert "Main_Shell.tdl -> Shells/A_Shell.tdl -> Shells/Main_Shell.tdl" in cycle["message"]


def test_a_missing_file_is_an_error_at_the_import_that_says_where_it_looked(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main = main_shell(tmp_path, "Import: Parts/Nope_Shell.tdl")
    code, found = check(tmp_path, capsys)
    assert code == 1
    (missing,) = found
    line, column = where(main, "Parts/Nope_Shell.tdl")
    assert missing["rule"] == "import-not-found"
    assert (missing["file"], missing["line"], missing["column"]) == (
        "Shells/Main_Shell.tdl",
        line,
        column,
    )
    assert str(tmp_path / "Shells" / "Parts" / "Nope_Shell.tdl") in missing["message"]


def test_a_path_outside_the_configuration_folder_is_path_outside_config(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = tmp_path / "cfg"
    surfaces(tmp_path, bar("Out"), relative="elsewhere/Out_Shell.tdl")
    main = main_shell(cfg, "Import: ../../elsewhere/Out_Shell.tdl")
    code, found = check(cfg, capsys)
    assert code == 1
    (error,) = found
    line, column = where(main, "../../elsewhere")
    assert error["rule"] == "path-outside-config"
    assert (error["file"], error["line"], error["column"]) == (
        "Shells/Main_Shell.tdl",
        line,
        column,
    )


def test_an_import_through_a_symbolic_link_that_leaves_the_folder_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    cfg = tmp_path / "cfg"
    out = surfaces(tmp_path, bar("Out"), relative="elsewhere/Out_Shell.tdl")
    main_shell(cfg, "Import: Linked_Shell.tdl")
    os.symlink(out, cfg / "Shells" / "Linked_Shell.tdl")
    code, found = check(cfg, capsys)
    assert code == 1 and "path-outside-config" in {e["rule"] for e in found}


def test_a_surface_name_used_in_both_files_names_both_positions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main = main_shell(tmp_path, f"{bar('Same')}\nImport: Bottom_Shell.tdl")
    part = surfaces(tmp_path, bar("Same", "BOTTOM"))
    code, found = check(tmp_path, capsys)
    assert code == 1
    (dup,) = found
    line, column = where(part, "Same")
    first_line, first_column = where(main, "Name: Same")
    assert dup["rule"] == "name-duplicate"
    assert (dup["file"], dup["line"]) == ("Shells/Bottom_Shell.tdl", line)
    assert f"first at Shells/Main_Shell.tdl:{first_line}:{first_column}" in dup["message"]
    assert column > 0


def test_the_same_file_imported_twice_is_an_error_naming_the_first_import(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # twice in one list, and again in the nested file: a diamond is the same mistake
    main = main_shell(
        tmp_path, "Import: [Bottom_Shell.tdl, Parts/Both_Shell.tdl, Bottom_Shell.tdl]"
    )
    surfaces(tmp_path, bar("Low", "BOTTOM"))
    surfaces(tmp_path, "Import: ../Bottom_Shell.tdl", relative="Shells/Parts/Both_Shell.tdl")
    code, found = check(tmp_path, capsys)
    assert code == 1
    twice = [e for e in found if e["rule"] == "import-twice"]
    assert len(twice) == 2
    line, _ = where(main, "Import:")
    assert all(f"first at Shells/Main_Shell.tdl:{line}:" in e["message"] for e in twice)


def test_an_imported_file_with_a_monitor_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    main_shell(tmp_path, "Import: Whole_Shell.tdl")
    part = write(
        tmp_path,
        "Shells/Whole_Shell.tdl",
        "Shell { Monitor { Name: Other, Index: 1, Children { } } }\n",
    )
    code, found = check(tmp_path, capsys)
    assert code == 1
    (error,) = [e for e in found if e["rule"] == "import-monitor"]
    assert (error["file"], error["line"]) == ("Shells/Whole_Shell.tdl", where(part, "Monitor")[0])


def test_a_main_shell_of_surfaces_only_is_an_error_not_an_empty_screen(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path, "Shells/Main_Shell.tdl", "Shell {\n" + bar("Lonely") + "\n}\n")
    code, found = check(tmp_path, capsys)
    assert code == 1 and [e["rule"] for e in found] == ["main-shell-surfaces"]


def test_a_shell_file_imported_where_modules_go_and_the_other_way_round(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    surfaces(tmp_path, bar("Low", "BOTTOM"))
    write(tmp_path, "Modules/Label/Label_Module.tdl", "Module {\n    Text { Text: hi }\n}\n")
    (tmp_path / "Modules" / "Label" / "Label_Module.py").write_text(
        "from tess_shell import Module\n\nclass Label(Module):\n    pass\n"
    )
    main = main_shell(
        tmp_path,
        "Import: ../Modules/Label/Label_Module.tdl\n"
        "Bar { Name: Top, Edge: TOP, Width: EXPAND, Height: 32,"
        " Children { Import: Bottom_Shell.tdl } }",
    )
    code, found = check(tmp_path, capsys)
    assert code == 1
    assert [e["rule"] for e in found] == ["import-misplaced", "import-misplaced"]
    assert {e["line"] for e in found} == {
        where(main, "Import: ../Modules")[0],
        where(main, "Children { Import")[0],
    }
