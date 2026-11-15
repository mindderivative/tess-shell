"""``Shortcut_Mode`` in the files (Focus and Keyboard > Shortcut Mode, Failure Modes): the key on a
Bar, a Panel, a Frame and a strip; two surfaces written true are one warning naming both with
``file:line:column`` and the first in document order keeps it; a Popup takes none; ``check`` says
so. The settings key ``Debug { Mode_Keyboard }`` is here too."""

from __future__ import annotations

from pathlib import Path

import pytest
import tess_dl

from tess_shell.cli import main
from tess_shell.config.settings import DebugSettings, load_settings
from tess_shell.schema.findings import Finding
from tess_shell.schema.model import BarDef, FrameDef, PanelDef, ShellDef
from tess_shell.schema.shell import read_shell
from tess_shell.surfaces.focus import surface_order
from tess_shell.surfaces.mode_driver import lowest_surface, surface_flags
from tests.shell_samples import HEADER, SVG
from tests.test_shortcut_plan import write

FILE = "Shells/Main_Shell.tdl"


def read(body: str) -> tuple[ShellDef | None, list[Finding]]:
    result = tess_dl.parse(HEADER + body, path=FILE)
    assert not result.errors and result.document is not None
    return read_shell(result.document, FILE, lambda p: SVG)


def shell_with(children: str) -> str:
    return f"Shell {{ Monitor {{ Name: Main, Index: 0, Children {{\n{children}\n}} }} }}\n"


BAR = "Bar { Name: Top_Bar, Edge: TOP, Width: EXPAND, Height: 32, %s }"
PANEL = "Panel { Name: Dock, Width: 100, Height: 50, %s }"
FRAME = (
    "Frame { Name: F, Thickness: 10, %s Edges { Top { Thickness: 20, %s Children { Box { } } } } }"
)


def typed(children: str) -> tuple[ShellDef, list[Finding]]:
    shell, findings = read(shell_with(children))
    assert shell is not None, findings
    return shell, findings


def warnings_of(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.rule == "shortcut-mode-twice"]


# -- the key ----------------------------------------------------------------------------------


def test_the_key_is_false_by_default_and_carries_the_position_of_the_key_when_true() -> None:
    shell, findings = typed(
        "\n".join(
            [
                BAR % "",
                PANEL % "Shortcut_Mode: false,",
                FRAME % ("", ""),
            ]
        )
    )
    assert findings == []
    bar, panel = shell.monitors[0].surfaces
    (frame,) = shell.monitors[0].frames
    assert isinstance(bar, BarDef) and isinstance(panel, PanelDef)
    assert bar.shortcut_mode is None and panel.shortcut_mode is None
    assert frame.shortcut_mode is None and frame.edges["top"].shortcut_mode is None


@pytest.mark.parametrize("kind", ["Bar", "Panel", "Frame", "strip"])
def test_a_bar_a_panel_a_frame_and_a_strip_take_the_key(kind: str) -> None:
    key = "Shortcut_Mode: true,"
    children = {
        "Bar": BAR % key,
        "Panel": PANEL % key,
        "Frame": FRAME % (key, ""),
        "strip": FRAME % ("", key),
    }[kind]
    text = HEADER + shell_with(children)
    result = tess_dl.parse(text, path=FILE)
    assert result.document is not None
    shell, findings = read_shell(result.document, FILE, lambda p: SVG)
    assert shell is not None and findings == []
    (monitor,) = shell.monitors
    if kind in ("Bar", "Panel"):
        origin = monitor.surfaces[0].shortcut_mode
    elif kind == "Frame":
        origin = monitor.frames[0].shortcut_mode
    else:
        origin = monitor.frames[0].edges["top"].shortcut_mode
    assert origin is not None and origin.file == FILE
    # the position is the key's own in the file
    assert text.splitlines()[origin.line - 1][origin.column - 1 :].startswith("Shortcut_Mode")


def test_a_value_that_is_not_true_or_false_is_an_error_with_its_position() -> None:
    shell, findings = read(shell_with(PANEL % "Shortcut_Mode: maybe,"))
    assert shell is None
    (error,) = [f for f in findings if f.severity == "error"]
    assert "Shortcut_Mode" in error.message and error.line > 0


def test_a_popup_takes_no_shortcut_mode() -> None:
    shell, findings = read(
        shell_with("Popup { Name: Menu, Shortcut_Mode: true, Children { Box { } } }")
    )
    assert shell is None
    (error,) = [f for f in findings if f.severity == "error"]
    assert "Shortcut_Mode" in error.message


def test_a_melded_panel_takes_no_shortcut_mode_it_has_no_window_of_its_own() -> None:
    shell, findings = read(
        shell_with(
            "Frame { Name: F, Thickness: 10 }\n"
            "Panel { Name: Tab, Meld: true, Attach_To: F, Attach: LEFT, Length: 50, Depth: 20, "
            "Shortcut_Mode: true }"
        )
    )
    assert shell is None
    assert any(
        "Shortcut_Mode on a Panel with Meld: true" in f.message
        for f in findings
        if f.severity == "error"
    )


# -- two surfaces written true -----------------------------------------------------------------


def test_one_surface_written_true_is_no_warning() -> None:
    _, findings = typed("\n".join([BAR % "", PANEL % "Shortcut_Mode: true,"]))
    assert warnings_of(findings) == []


def test_two_written_true_are_one_warning_naming_both_with_file_line_column() -> None:
    children = "\n".join([BAR % "Shortcut_Mode: true,", PANEL % "Shortcut_Mode: true,"])
    shell, findings = typed(children)
    (warning,) = warnings_of(findings)
    assert warning.severity == "warning"
    lines = (HEADER + shell_with(children)).splitlines()
    bar_at = f"{FILE}:{_where(lines, 'Top_Bar')}"
    dock_at = f"{FILE}:{_where(lines, 'Dock')}"
    assert f"Bar Top_Bar ({bar_at})" in warning.message
    assert f"Panel Dock ({dock_at})" in warning.message
    assert "Top_Bar keeps it" in warning.message
    # the warning is at the first in document order, and the loader keeps the file's flags
    assert (warning.line, warning.column) == tuple(int(x) for x in bar_at.split(":")[1:])
    flags = surface_flags(shell, surface_order(shell))
    # what the files write, in document order: the first is the one the mode starts with
    assert list(flags.items()) == [("Top_Bar", True), ("Dock", True)]


def _where(lines: list[str], name: str) -> str:
    """``line:column`` of the ``Shortcut_Mode`` key on the line of the surface called ``name``."""
    for i, line in enumerate(lines, 1):
        if f"Name: {name}" in line:
            return f"{i}:{line.index('Shortcut_Mode') + 1}"
    raise AssertionError(name)


def test_three_written_true_are_still_one_warning_and_the_frame_and_a_strip_count() -> None:
    _, findings = typed(
        "\n".join(
            [
                FRAME % ("Shortcut_Mode: true,", "Shortcut_Mode: true,"),
                PANEL % "Shortcut_Mode: true,",
            ]
        )
    )
    (warning,) = warnings_of(findings)
    assert "3 surfaces" in warning.message
    assert "Frame F" in warning.message and "strip F.top" in warning.message
    assert "Panel Dock" in warning.message


def test_the_first_in_document_order_is_the_first_in_the_flags_whatever_kind_it_is() -> None:
    key = "Shortcut_Mode: true,"
    shell, _ = typed("\n".join([PANEL % key, FRAME % (key, "")]))
    order = surface_order(shell)
    flags = surface_flags(shell, order)
    assert [n for n, v in flags.items() if v][0] == "Dock"
    assert set(flags) == set(order) == {"Dock", "F", "F.top"}


def test_the_lowest_level_is_the_first_frame_else_the_first_surface() -> None:
    shell, _ = typed("\n".join([PANEL % "", FRAME % ("", "")]))
    assert lowest_surface(shell, surface_order(shell)) == "F"
    shell, _ = typed(PANEL % "")
    assert lowest_surface(shell, surface_order(shell)) == "Dock"
    assert lowest_surface(shell, []) is None


# -- check ------------------------------------------------------------------------------------


def test_check_says_where_each_of_the_two_is_written(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(tmp_path, "", bar_key="Shortcut_Mode: true,", panel_key="Shortcut_Mode: true,")
    assert main(["check", "--config-dir", str(tmp_path)]) == 0  # a warning, not an error
    err = capsys.readouterr().err
    assert "warning: Shortcut_Mode: true is written on 2 surfaces: Bar Top_Bar (" in err
    assert "Panel Launcher (" in err and "Top_Bar keeps it" in err


# -- the settings key ---------------------------------------------------------------------------


def test_debug_mode_keyboard_defaults_to_exclusive_and_takes_on_demand(tmp_path: Path) -> None:
    assert load_settings(tmp_path / "none")[0].debug.mode_keyboard == "EXCLUSIVE"  # type: ignore[union-attr]
    for word in ("EXCLUSIVE", "ON_DEMAND"):
        (tmp_path / "settings.tdl").write_text(
            f"---\nTDL: 0.2\nName: S\n---\nSettings {{ Debug {{ Mode_Keyboard: {word} }} }}\n"
        )
        settings, findings = load_settings(tmp_path)
        assert findings == [] and settings is not None
        assert settings.debug == DebugSettings(mode_keyboard=word)


def test_debug_mode_keyboard_refuses_none_and_a_lower_case_word(tmp_path: Path) -> None:
    for text, needle in (
        ("Mode_Keyboard: NONE", "ON_DEMAND"),
        ("Mode_Keyboard: on_demand", "upper case, write ON_DEMAND"),
    ):
        (tmp_path / "settings.tdl").write_text(
            f"---\nTDL: 0.2\nName: S\n---\nSettings {{ Debug {{ {text} }} }}\n"
        )
        settings, findings = load_settings(tmp_path)
        assert settings is None and needle in findings[0].message + findings[0].hint


def test_the_frame_and_bar_definitions_hold_the_key_as_an_origin() -> None:
    assert FrameDef.__dataclass_fields__["shortcut_mode"].default is None
    assert BarDef.__dataclass_fields__["shortcut_mode"].default is None
