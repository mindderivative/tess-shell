"""Icon sets and ``SVG { Icon: name }`` (Block Reference > Icons; M2 Brief B5)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import tess_dl
from tess_re import Window

from tess_shell.binder import model as m
from tess_shell.binder.build import build
from tess_shell.cli import main
from tess_shell.config.settings import load_settings
from tess_shell.files.icons import IconSets
from tess_shell.schema.findings import Finding
from tess_shell.schema.shell import read_module

DOT = '<circle cx="12" cy="12" r="10" fill="currentColor"/>'
BOX = '<rect width="24" height="24" fill="currentColor"/>'


def write_set(
    directory: Path, name: str, prefix: str, icons: dict[str, str], **extra: object
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.json"
    path.write_text(
        json.dumps({"prefix": prefix, "icons": {k: {"body": v} for k, v in icons.items()}, **extra})
    )
    return path


def test_an_icon_becomes_an_svg_document_around_its_body(tmp_path: Path) -> None:
    write_set(tmp_path, "mdi", "mdi", {"dot": DOT})
    doc = IconSets([tmp_path]).lookup("dot")
    assert doc is not None
    assert doc.startswith('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"')
    assert DOT in doc and doc.endswith("</svg>")


def test_a_prefix_selects_a_set_and_no_prefix_looks_in_mdi_first(tmp_path: Path) -> None:
    write_set(tmp_path, "a_other", "oth", {"x": BOX, "only-oth": BOX})
    write_set(tmp_path, "z_mdi", "mdi", {"x": DOT})
    sets = IconSets([tmp_path])
    assert sets.lookup("x") == sets.lookup("mdi:x") and DOT in (sets.lookup("x") or "")
    assert BOX in (sets.lookup("oth:x") or "")
    assert sets.lookup("only-oth") is not None  # found in the other set when mdi lacks it
    assert sets.lookup("mdi:only-oth") is None and sets.lookup("nope:x") is None


def test_an_icon_may_carry_its_own_size_and_the_set_a_default(tmp_path: Path) -> None:
    path = tmp_path / "s.json"
    path.write_text(
        json.dumps(
            {
                "prefix": "s",
                "width": 16,
                "height": 16,
                "icons": {"a": {"body": DOT}, "b": {"body": DOT, "width": 32}},
            }
        )
    )
    sets = IconSets([tmp_path])
    assert 'viewBox="0 0 16 16"' in (sets.lookup("a") or "")
    assert 'viewBox="0 0 32 16"' in (sets.lookup("b") or "")


def test_nothing_is_read_until_the_first_lookup_and_a_bad_file_is_reported_once(
    tmp_path: Path,
) -> None:
    write_set(tmp_path, "mdi", "mdi", {"dot": DOT})
    (tmp_path / "zz.json").write_text("{not json")
    sets = IconSets([tmp_path])
    assert sets.problems == []  # constructing reads no file
    assert sets.lookup("dot") is not None  # a prefix is known only after reading, so all are read
    assert len(sets.problems) == 1 and "zz.json" in sets.problems[0]
    sets.lookup("missing")
    sets.lookup("dot")
    assert len(sets.problems) == 1  # read once, reported once, then skipped


def test_nearest_names_help_with_a_typo(tmp_path: Path) -> None:
    write_set(tmp_path, "mdi", "mdi", {"account": DOT, "account-alert": DOT, "battery": DOT})
    assert IconSets([tmp_path]).nearest("mdi:acount") == ["account"]


def module(text: str, sets: IconSets | None) -> tuple[m.Node | None, list[Finding]]:
    doc = tess_dl.parse("---\nTDL: 0.1\nName: Ico\n---\n" + text, path="Ico_Module.tdl").document
    assert doc is not None
    found, findings = read_module(doc, "Ico_Module.tdl", icons=sets)
    node = found.children[0] if found else None
    return (node if isinstance(node, m.Node) else None), findings


def test_an_icon_key_is_resolved_by_the_schema_into_the_svg_source(tmp_path: Path) -> None:
    write_set(tmp_path, "mdi", "mdi", {"dot": DOT})
    node, findings = module(
        'Module { SVG { Icon: "mdi:dot", Color: "#ff0000" } }', IconSets([tmp_path])
    )
    assert findings == [] and node is not None
    doc = node.props["Icon"]
    assert isinstance(doc, m.Text) and DOT in doc.value


def test_an_unknown_icon_is_an_error_at_its_value_with_the_nearest_names(tmp_path: Path) -> None:
    write_set(tmp_path, "mdi", "mdi", {"account": DOT})
    text = "Module {\n    SVG { Icon: acount }\n}\n"
    node, findings = module(text, IconSets([tmp_path]))
    assert node is None
    (f,) = findings
    assert f.rule == "icon-not-found" and "account" in f.hint
    assert (f.line, f.column) == (6, 17)


def test_with_no_icon_sets_the_hint_says_where_they_go() -> None:
    _, findings = module("Module { SVG { Icon: dot } }", None)
    assert findings[0].rule == "icon-not-found" and "Icons folder" in findings[0].hint


def test_an_svg_needs_a_source_or_an_icon_and_not_both(tmp_path: Path) -> None:
    write_set(tmp_path, "mdi", "mdi", {"dot": DOT})
    sets = IconSets([tmp_path])
    _, findings = module("Module { SVG { Width: 4 } }", sets)
    assert findings[0].rule == "missing-key" and "Source or Icon" in findings[0].message
    _, findings = module('Module { SVG { Icon: dot, Source: "x.svg" } }', sets)
    assert any(f.rule == "bad-key" for f in findings)


def test_the_icon_reaches_tre_and_takes_its_colour_from_color(tmp_path: Path) -> None:
    write_set(tmp_path, "mdi", "mdi", {"dot": DOT})
    node, findings = module(
        'Module { SVG { Icon: dot, Width: 40, Height: 40, Color: "#00ff00" } }',
        IconSets([tmp_path]),
    )
    assert findings == [] and node is not None
    window = Window(60, 60, decorations=False)
    window.root.set(fill=(0, 0, 0, 255), padding=0)
    build([node], window)
    rgba, _, _ = window.snapshot()
    green = sum(1 for i in range(0, len(rgba), 4) if rgba[i + 1] > 200 and rgba[i] < 60)
    assert green > 500  # a green disc, drawn from the icon's body


def test_the_config_icons_folder_comes_before_the_listed_directories(tmp_path: Path) -> None:
    (tmp_path / "Icons").mkdir()
    (tmp_path / "extra").mkdir()
    (tmp_path / "Styles").mkdir()
    (tmp_path / "other").mkdir()
    (tmp_path / "settings.tdl").write_text(
        "---\nTDL: 0.1\nName: Settings\n---\nSettings { Directories {\n"
        f'    Icons: "{tmp_path}/extra"\n    Styles: "{tmp_path}/other"\n}} }}\n'
    )
    settings, findings = load_settings(tmp_path)
    assert findings == [] and settings is not None
    assert settings.directories["Icons"] == (tmp_path / "Icons", tmp_path / "extra")
    assert settings.directories["Styles"] == (tmp_path / "other", tmp_path / "Styles")


def test_check_resolves_icons_from_the_config_folder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_set(tmp_path / "Icons", "mdi", "mdi", {"dot": DOT})
    folder = tmp_path / "Modules" / "Ico"
    folder.mkdir(parents=True)
    head = "---\nTDL: 0.1\nName: {n}\n---\n"
    (folder / "Ico_Module.tdl").write_text(
        head.format(n="Ico") + 'Module { SVG { Icon: "mdi:dot" } }\n'
    )
    (folder / "Ico_Module.py").write_text("")
    shells = tmp_path / "Shells"
    shells.mkdir()
    (shells / "Main_Shell.tdl").write_text(
        head.format(n="Main_Shell")
        + "Shell { Monitor { Name: M, Index: 0, Children { Bar { Name: B, Edge: TOP, "
        "Width: EXPAND, Height: 32, Children { Ico { } SVG { Icon: dot } } } } } }\n"
    )
    assert main(["check", "--config-dir", str(tmp_path)]) == 0
    capsys.readouterr()
    (shells / "Main_Shell.tdl").write_text(
        (shells / "Main_Shell.tdl").read_text().replace("Icon: dot", "Icon: dott")
    )
    assert main(["check", "--config-dir", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "no icon named dott" in err and "did you mean dot?" in err
