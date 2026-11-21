"""The shipped ``Launcher`` Panel and the ``Applications`` module in the schema (Applications Module
> Layout; Global Shortcuts > Action Names and Forms): the Panel is added to a shell that names it
and writes none, a shell that never names it gets no extra surface, and the keys and values the
module and its events add are in the schema export."""

from __future__ import annotations

from pathlib import Path

import pytest

from tess_shell.binder.model import Auto
from tess_shell.cli import main
from tess_shell.config.settings import load_settings
from tess_shell.scanner import Scan, scan
from tess_shell.schema.default_panels import PANELS, describe, named_surfaces
from tess_shell.schema.export import schema_dict
from tests.shell_samples import HEADER

HEAD = "---\nTDL: 0.2\nName: S\n---\n"
BAR = "Bar { Name: Top_Bar, Edge: TOP, Width: EXPAND, Height: 32%s }"
SHELL = (
    "Shell { Monitor { Name: Main, Index: 0, Children { %s } } Monitor { Name: Other, Index: 1 } }"
)


def build(tmp_path: Path, shell: str, settings: str = "") -> Scan:
    (tmp_path / "Shells").mkdir(parents=True, exist_ok=True)
    (tmp_path / "Shells" / "Main_Shell.tdl").write_text(HEADER + shell, encoding="utf-8")
    (tmp_path / "settings.tdl").write_text(f"{HEAD}Settings {{\n{settings}\n}}\n", encoding="utf-8")
    loaded, findings = load_settings(tmp_path)
    assert loaded is not None, findings
    result = scan(loaded, tmp_path)
    assert result.errors == [], result.errors
    return result


def surfaces(result: Scan) -> dict[str, list[str]]:
    """The surface names of each Monitor of the main shell."""
    (shell,) = result.shells.values()
    return {m.name: [s.name for s in m.surfaces] for m in shell.monitors}


def test_a_shell_that_never_names_the_launcher_gets_no_extra_surface(tmp_path: Path) -> None:
    result = build(tmp_path, SHELL % (BAR % ""))
    assert surfaces(result) == {"Main": ["Top_Bar"], "Other": []}


def test_a_shortcut_entry_that_names_it_brings_the_shipped_panel_on_the_first_monitor(
    tmp_path: Path,
) -> None:
    result = build(tmp_path, SHELL % (BAR % ""), '  Shortcuts { Toggle_Launcher: "Meta+Space" }')
    assert surfaces(result) == {"Main": ["Top_Bar", "Launcher"], "Other": []}
    # the shortcut has a Panel to act on: it is declared, with no "unknown surface" warning
    assert [a.id for a in result.shortcuts] == ["Toggle_Launcher"]
    assert not [f for f in result.findings if f.rule == "shortcut-unknown-surface"]
    (shell,) = result.shells.values()
    panel = shell.monitors[0].surfaces[1]
    assert (panel.layer, panel.keyboard) == ("OVERLAY", "EXCLUSIVE")
    assert panel.visible is False  # type: ignore[union-attr]
    assert panel.width.px == 480  # type: ignore[union-attr]
    assert isinstance(panel.height, Auto) and panel.max_height == 400  # content-sized (M7i)
    assert [getattr(c, "module", "") for c in panel.children] == ["Applications"]


@pytest.mark.parametrize("verb", ["Show", "Hide"])
def test_show_and_hide_entries_name_it_too(tmp_path: Path, verb: str) -> None:
    result = build(tmp_path, SHELL % (BAR % ""), f'  Shortcuts {{ {verb}_Launcher: "Meta+Space" }}')
    assert surfaces(result)["Main"] == ["Top_Bar", "Launcher"]


def test_a_handler_that_toggles_it_brings_the_panel_whatever_block_holds_the_handler(
    tmp_path: Path,
) -> None:
    on_click = (
        ", Children { Button { Text: Open, On_Click { Action: Toggle, Target: Launcher } } } "
    )
    result = build(tmp_path, SHELL % (BAR % on_click))
    assert surfaces(result)["Main"] == ["Top_Bar", "Launcher"]
    # a Panel's own handler counts as well
    panel = (
        "Panel { Name: Hello, Width: 10, Height: 10, Visible: false, "
        "On_Open { Action: Show, Target: Launcher } }"
    )
    result = build(tmp_path, SHELL % (BAR % "") + "")
    assert "Launcher" not in surfaces(result)["Main"]
    result = build(tmp_path, SHELL % ((BAR % "") + " " + panel))
    assert surfaces(result)["Main"] == ["Top_Bar", "Hello", "Launcher"]


def test_a_panel_the_user_writes_with_that_name_replaces_it_whole(tmp_path: Path) -> None:
    own = "Panel { Name: Launcher, Width: 100, Height: 50, Visible: false }"
    result = build(
        tmp_path,
        SHELL % ((BAR % "") + " " + own),
        '  Shortcuts { Toggle_Launcher: "Meta+Space" }',
    )
    assert surfaces(result)["Main"] == ["Top_Bar", "Launcher"]
    (shell,) = result.shells.values()
    panel = shell.monitors[0].surfaces[1]
    assert panel.keyboard == "NONE" and panel.width.px == 100  # type: ignore[union-attr]


def test_a_name_in_a_frame_or_popup_handler_is_found_as_well(tmp_path: Path) -> None:
    (shell_text) = (
        "Shell { Monitor { Name: Main, Index: 0, Children { "
        + (BAR % "")
        + " Popup { Name: Menu, Children { Button { Text: x, "
        "On_Click { Action: Show, Target: Launcher } } } } } } }"
    )
    result = build(tmp_path, shell_text)
    assert "Launcher" in surfaces(result)["Main"]
    (parsed,) = result.shells.values()
    assert named_surfaces(parsed) >= {"Launcher"}


def test_the_check_command_is_clean_for_a_shell_that_only_binds_the_key(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    build(tmp_path, SHELL % (BAR % ""), '  Shortcuts { Toggle_Launcher: "Meta+Space" }')
    assert main(["check", "--config-dir", str(tmp_path)]) == 0
    assert "error" not in capsys.readouterr().out.lower()


# -- the schema ------------------------------------------------------------------------------------


def test_the_applications_module_its_params_and_the_event_are_in_the_schema_export() -> None:
    data = schema_dict()
    assert data["schema_version"] == "1.14"
    module = data["modules"]["Applications"]
    params = {name: p for name, p in module["params"].items()}
    assert {n: (p["type"], p["default"]) for n, p in params.items()} == {
        "max_results": ("number", "8"),
        "show_comment": ("boolean", "true"),
        "icon_size": ("number", "24"),
        "placeholder": ("string", '"Search applications"'),  # the default as the TDL writes it
    }
    event = data["events"]["On_Key_Down"]
    assert "event.stop()" in event["doc"] and "TextField" in event["raised_by"]
    assert "On_Key_Down" in data["modules"]["TextInput"]["events"]
    shipped = data["panels"]["panels"]
    assert shipped["Launcher"]["content"] == "Applications"
    assert shipped["Launcher"]["keyboard"] == "EXCLUSIVE" and shipped["Launcher"]["doc"]
    assert set(shipped) == set(PANELS) and data["panels"]["when"]


def test_describe_reads_the_shipped_text_with_no_problem() -> None:
    from tests.widgets_live import _defs

    found = describe(_defs("Module { FlexBox { } }", {}))
    assert found["Launcher"]["visible"] is False and found["Launcher"]["doc"]
