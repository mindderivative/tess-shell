"""Style files and inline module styles (Style, Theme and Stylesheet Files > Rules)."""

from __future__ import annotations

from pathlib import Path

import pytest
import tess_dl
from tess_re import Window

from tess_shell.binder import model as m
from tess_shell.binder.build import build
from tess_shell.cli import main
from tess_shell.schema.findings import Finding
from tess_shell.schema.model import ModuleDef, StyleDef
from tess_shell.schema.shell import read_module, read_style

HEAD = "---\nTDL: 0.1\nName: {name}\n---\n"

STYLE = """
Style {
    Classes {
        big { Kind: Text, Font_Size: 30, Foreground: "#ff0000" }
        box { Kind: Box, Background: "#00ff00" }
    }
    Text { Font_Size: 12, Foreground: "#0000ff" }
    FlexBox { Padding: 3 }
}
"""


def style(text: str = STYLE) -> tuple[StyleDef | None, list[Finding]]:
    doc = tess_dl.parse(HEAD.format(name="S_Style") + text, path="S_Style.tdl").document
    assert doc is not None
    return read_style(doc, "S_Style.tdl")


def module(body: str, loader: object = None) -> tuple[ModuleDef | None, list[Finding]]:
    doc = tess_dl.parse(HEAD.format(name="Mod") + body, path="Mod_Module.tdl").document
    assert doc is not None
    return read_module(doc, "Mod_Module.tdl", None, None, loader)  # type: ignore[arg-type]


def loader(text: str = STYLE) -> object:
    found, _ = style(text)
    return lambda name: found


def node(found: ModuleDef | None, *path: int) -> m.Node:
    assert found is not None
    n = found.children[0]
    for i in path:
        assert isinstance(n, m.Node)
        n = n.children[i]
    assert isinstance(n, m.Node)
    return n


def test_a_style_file_is_typed_into_defaults_and_classes() -> None:
    found, findings = style()
    assert found is not None and findings == []
    assert found.defaults["Text"] == {"Font_Size": m.Number(12), "Foreground": m.Color(0, 0, 255)}
    assert found.classes["big"].kind == "Text"
    assert found.classes["big"].values["Font_Size"] == m.Number(30)


def test_priority_runs_from_the_type_default_through_the_class_to_inline_to_the_block_itself() -> (
    None
):
    body = """
    Module { Style: S_Style.tdl
        FlexBox { Children {
            Text { Text: a }
            Text { Text: b, Class: big }
            Text { Text: c, Class: big, Style { Font_Size: 50 } }
            Text { Text: d, Class: big, Font_Size: 60 }
        } }
    }
    """
    found, findings = module(body, loader())
    assert findings == [] and found is not None
    plain, classed, inline, onblock = (node(found, i) for i in range(4))
    assert plain.style["Font_Size"] == m.Number(12) and plain.style["Foreground"] == m.Color(
        0, 0, 255
    )
    assert classed.style["Font_Size"] == m.Number(30) and classed.style["Foreground"] == m.Color(
        255, 0, 0
    )
    assert inline.style["Font_Size"] == m.Number(50) and inline.style["Foreground"] == m.Color(
        255, 0, 0
    )
    # a key written on the block wins and is not repeated in style (no style-duplicate)
    assert onblock.props["Font_Size"] == m.Number(60) and "Font_Size" not in onblock.style
    assert onblock.style["Foreground"] == m.Color(255, 0, 0)
    assert node(found).style["Padding"] == m.Length(3)  # a default for FlexBox


def test_a_style_changes_only_what_it_names() -> None:
    found, _ = module("Module { Style: S_Style.tdl\n    Spacer { } }", loader())
    assert node(found).style == {}


def test_an_inline_module_style_block_works_like_a_file() -> None:
    body = "Module { Style { Text { Font_Size: 9 } }\n    Text { Text: x } }"
    found, findings = module(body)
    assert findings == [] and node(found).style == {"Font_Size": m.Number(9)}


def test_a_class_that_is_not_defined_names_the_file_and_the_nearest_class() -> None:
    found, findings = module(
        "Module { Style: S_Style.tdl\n    Text { Text: x, Class: bgi } }", loader()
    )
    assert found is None
    (f,) = findings
    assert f.rule == "class-not-found" and "S_Style.tdl" in f.message and "big" in f.hint


def test_a_class_for_another_block_type_is_an_error() -> None:
    found, findings = module(
        "Module { Style: S_Style.tdl\n    Text { Text: x, Class: box } }", loader()
    )
    assert found is None and findings[0].rule == "class-kind"
    assert "Box blocks" in findings[0].message


def test_a_class_with_no_style_at_all_is_an_error() -> None:
    found, findings = module("Module {\n    Text { Text: x, Class: big } }")
    assert found is None and findings[0].rule == "class-not-found"


def test_style_file_errors_are_located() -> None:
    found, findings = style(STYLE.replace("Font_Size: 30", "Font_Siz: 30"))
    assert found is None and findings[0].rule == "unknown-key" and "Font_Size" in findings[0].hint
    found, findings = style("Style {\n    Classes { c { Font_Size: 3 } }\n}\n")
    assert found is None and findings[0].rule == "missing-key"
    found, findings = style("Style {\n    Textt { Font_Size: 3 }\n}\n")
    assert found is None and "Text" in findings[0].hint
    doc = tess_dl.parse(HEAD.format(name="X") + "Module {\n}\n").document
    assert doc is not None and read_style(doc, "X_Style.tdl")[1][0].rule == "style-root"


def test_a_module_with_two_styles_is_an_error() -> None:
    body = (
        "Module { Style: S_Style.tdl\n    Style { Text { Font_Size: 1 } }\n    Text { Text: x } }"
    )
    found, findings = module(body, loader())
    assert found is None and findings[0].rule == "style-duplicate"


def test_the_look_really_comes_from_the_file_in_pixels() -> None:
    found, findings = module(
        "Module { Style: S_Style.tdl\n    Text { Text: Hello, Class: big } }", loader()
    )
    assert findings == [] and found is not None
    window = Window(200, 60, decorations=False)
    window.root.set(fill=(0, 0, 0, 255))
    build(list(c for c in found.children if isinstance(c, m.Node)), window)
    rgba, width, height = window.snapshot()
    red = sum(1 for i in range(0, len(rgba), 4) if rgba[i] > 200 and rgba[i + 1] < 60)
    assert red > 100  # the class's colour and size (30 px red text) reached tre


def write_module(config: Path, name: str, module_text: str, style_text: str | None) -> None:
    folder = config / "Modules" / name
    folder.mkdir(parents=True)
    (folder / f"{name}_Module.tdl").write_text(HEAD.format(name=name) + module_text)
    (folder / f"{name}_Module.py").write_text(
        "from tess_shell import Module\n\nclass M(Module):\n    pass\n"
    )
    if style_text is not None:
        (folder / f"{name}_Style.tdl").write_text(HEAD.format(name=f"{name}_Style") + style_text)
    shells = config / "Shells"
    shells.mkdir()
    (shells / "Main_Shell.tdl").write_text(
        HEAD.format(name="Main_Shell")
        + "Shell { Monitor { Name: M, Index: 0, Children { Bar { Name: B, Edge: TOP, "
        + f"Width: EXPAND, Height: 32, Children {{ {name} {{ }} }} }} }} }} }}\n"
    )


def test_check_loads_the_style_file_next_to_a_module(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_module(
        tmp_path, "Mod", "Module { Style: Mod_Style.tdl\n Text { Text: x, Class: big } }", STYLE
    )
    assert main(["check", "--config-dir", str(tmp_path)]) == 0
    capsys.readouterr()


def test_check_reports_a_missing_style_file_and_a_bad_one_at_their_own_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write_module(tmp_path, "Mod", "Module { Style: Nope_Style.tdl\n Text { Text: x } }", None)
    assert main(["check", "--config-dir", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "style-not-found" in err or "does not exist" in err
    other = tmp_path / "other"
    other.mkdir()
    write_module(
        other,
        "Mod",
        "Module { Style: Mod_Style.tdl\n Text { Text: x } }",
        "Style {\n    Text { Font_Siz: 1 }\n}\n",
    )
    assert main(["check", "--config-dir", str(other)]) == 1
    err = capsys.readouterr().err
    assert "Mod_Style.tdl:" in err and "Font_Size" in err
