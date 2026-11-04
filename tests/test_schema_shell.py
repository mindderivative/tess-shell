"""Stage 4: the shell schema types the M1 example and reports every problem with a position."""

from __future__ import annotations

import pytest
import tess_dl

from tess_shell.binder.model import Auto, Color, Enum, Expand, Length, Number, Text
from tess_shell.schema.findings import Finding
from tess_shell.schema.model import ShellDef
from tests.shell_samples import BODY, HEADER, SVG


def read(body: str) -> tuple[ShellDef | None, list[Finding]]:
    from tess_shell.schema.shell import read_shell

    result = tess_dl.parse(HEADER + body, path="Shells/Main_Shell.tdl")
    assert not result.errors and result.document is not None
    return read_shell(result.document, "Shells/Main_Shell.tdl", lambda p: SVG)


def errors(body: str) -> list[Finding]:
    shell, findings = read(body)
    assert shell is None
    return [f for f in findings if f.severity == "error"]


def test_the_example_is_typed() -> None:
    shell, findings = read(BODY)
    assert findings == [] and shell is not None
    assert shell.name == "Main_Shell"
    (monitor,) = shell.monitors
    assert (monitor.name, monitor.index) == ("Main", 0)
    (bar,) = monitor.surfaces
    assert (bar.name, bar.edge, bar.layer) == ("Top_Bar", "TOP", "TOP")
    assert bar.width == Expand() and bar.height == Length(32)
    assert bar.style["Fill"] == Color(0x1F, 0x1F, 0x1F, 255)
    (row,) = bar.children
    assert row.kind == "FlexBox"
    assert row.props["Width"] == Expand() and row.props["Spacing"] == Number(8)
    assert row.props["Flex"] == Enum("HORIZONTAL")
    text, spacer, svg, rect = row.children
    assert text.props["Text"] == Text("14:05") and text.props["Font_Size"] == Number(14)
    assert spacer.kind == "Spacer"
    assert svg.props["Source"] == Text(SVG)
    assert rect.props["Corner_Radius"] == Length(6)


def test_values_carry_the_position_of_their_key() -> None:
    shell, _ = read(BODY)
    assert shell is not None
    row = shell.monitors[0].surfaces[0].children[0]
    origin = row.props["Spacing"].origin
    assert (origin.file, origin.line, origin.column) == ("Shells/Main_Shell.tdl", 22, 25)


def test_unknown_key_suggests_the_nearest_names_at_its_position() -> None:
    (f,) = errors(BODY.replace("Font_Size: 14", "Font_Siz: 14"))
    assert (f.rule, f.line, f.column) == ("unknown-key", 25, 51)
    assert "Font_Size" in f.hint


def test_wrong_value_type_names_the_key() -> None:
    (f,) = errors(BODY.replace("Spacing: 8", 'Spacing: "wide"'))
    assert f.rule == "bad-value" and "Spacing" in f.message and (f.line, f.column) == (22, 34)


def test_a_wrong_colour_has_a_position_and_says_what_to_write() -> None:
    (f,) = errors(BODY.replace('"#89b4fa", Corner', '"blue", Corner'))
    assert f.rule == "bad-value" and "#RRGGBB" in f.hint and f.line == 28


def test_lower_case_enum_says_upper_case() -> None:
    (f,) = errors(BODY.replace("Edge: TOP", "Edge: top"))
    assert "write TOP" in f.hint


def test_unknown_block_lists_the_blocks_that_fit() -> None:
    (f,) = errors(BODY.replace("Spacer { }", "Spacr { }"))
    assert f.rule == "unknown-key" and "Spacer" in f.hint


def test_missing_required_keys() -> None:
    fs = errors(BODY.replace("                Edge: TOP\n", "").replace('Source: "dot.svg", ', ""))
    assert sorted(f.rule for f in fs) == ["missing-key", "missing-key"]
    assert any("Edge" in f.message for f in fs) and any("Source" in f.message for f in fs)


def test_key_in_block_and_style_is_reported_naming_both() -> None:
    body = BODY.replace(
        "Rectangle { Width: 12, Height: 12,",
        "Rectangle { Width: 12, Height: 12, Opacity: 1, Style { Opacity: 0.5 }, ",
    )
    (f,) = errors(body)
    assert f.rule == "style-duplicate" and "Main_Shell.tdl:" in f.message


def test_names_must_be_unique_and_well_formed() -> None:
    dup = BODY.replace("Spacer { }", "Spacer { Name: Top_Bar }")
    (f,) = errors(dup)
    assert f.rule == "name-duplicate" and "first at Shells/Main_Shell.tdl:" in f.message
    (f,) = errors(BODY.replace("Name: Main\n", "Name: DP-1\n"))
    assert f.rule == "bad-name"


def test_two_monitors_selecting_the_same_monitor() -> None:
    two = BODY.replace(
        "    Monitor {\n        Name: Main",
        "    Monitor { Name: Other\n        Index: 0 }\n    Monitor {\n        Name: Main",
    )
    fs = errors(two)
    assert [f.rule for f in fs] == ["monitor-duplicate"]


@pytest.mark.parametrize(
    ("snippet", "what"),
    [
        ("Panel { Name: P }", "Panel"),
        ("Import: Other_Shell.tdl", "Import"),
    ],
)
def test_surfaces_and_forms_not_built_in_m1_are_refused(snippet: str, what: str) -> None:
    body = BODY.replace("            Bar {", f"            {snippet}\n            Bar {{", 1)
    (f,) = errors(body)
    assert f.rule == "not-built" and what in f.message


def test_if_and_for_in_children_are_refused() -> None:
    body = BODY.replace("Spacer { }", "If {{ true }} { Spacer { } }")
    fs = errors(body)
    assert fs and all(f.rule in ("not-built", "unknown-key") for f in fs)


def test_bar_keys_m1_does_not_build_are_warnings_not_errors() -> None:
    body = BODY.replace("Height: 32\n", "Height: 32\n                Auto_Hide: false\n")
    shell, findings = read(body)
    assert shell is not None
    (w,) = findings
    assert (w.severity, w.rule) == ("warning", "not-built") and "Auto_Hide" in w.message


def test_four_sided_forms() -> None:
    def padding(written: str) -> object:
        body = BODY.replace("Padding: 4", written)
        shell, findings = read(body)
        assert findings == [] and shell is not None
        return shell.monitors[0].surfaces[0].children[0].props["Padding"]

    from tess_shell.binder.model import Sides

    assert padding("Padding: 4") == Length(4)
    assert padding("Padding: [1, 2, 3, 4]") == Sides(1, 2, 3, 4)
    assert padding("Padding { Left: 24, Top: 8 }") == Sides(24, 8, 0, 0)
    (f,) = errors(BODY.replace("Padding: 4", "Padding: [8, 4]"))
    assert f.rule == "bad-sides" and "CSS" in f.hint
    assert errors(BODY.replace("Padding: 4", "Padding: [8, 4, 2]"))[0].rule == "bad-sides"


def test_border_block_is_flattened() -> None:
    body = BODY.replace(
        "Rectangle { Width: 12,",
        'Rectangle { Border { Width: 2, Color: "#ffffff" }, Width: 12,',
    )
    shell, findings = read(body)
    assert findings == [] and shell is not None
    rect = shell.monitors[0].surfaces[0].children[0].children[3]
    assert rect.props["Border_Width"] == Number(2)
    assert rect.props["Border_Color"] == Color(255, 255, 255, 255)


def test_rgba_call_and_percent_and_auto() -> None:
    body = (
        BODY.replace('Fill: "#89b4fa", Corner', "Fill: rgba(10 20 30 0.5), Corner")
        .replace("Width: 12,", "Width: 50%,", 1)
        .replace("Height: 12", "Height: AUTO")
    )
    shell, findings = read(body)
    assert findings == [] and shell is not None
    rect = shell.monitors[0].surfaces[0].children[0].children[3]
    assert rect.props["Fill"] == Color(10, 20, 30, 128)
    assert rect.props["Height"] == Auto()


def test_a_float_is_never_a_length() -> None:
    (f,) = errors(BODY.replace("Width: 12,", "Width: 12.5,", 1))
    assert f.rule == "bad-value" and "whole number" in f.message


def test_an_unreadable_svg_source_is_reported_at_its_key() -> None:
    from tess_shell.schema.shell import read_shell

    def missing(path: str) -> str:
        raise FileNotFoundError(2, "No such file or directory", path)

    result = tess_dl.parse(HEADER + BODY, path="Shells/Main_Shell.tdl")
    assert result.document is not None
    shell, findings = read_shell(result.document, "Shells/Main_Shell.tdl", missing)
    assert shell is None
    (f,) = findings
    assert "dot.svg" in f.message and f.line == 27


def test_the_root_must_be_shell() -> None:
    result = tess_dl.parse(HEADER + "Module {\n}\n", path="x")
    assert result.document is not None
    from tess_shell.schema.shell import read_shell

    shell, findings = read_shell(result.document, "x", lambda p: "")
    assert shell is None and findings[0].rule == "shell-root"
