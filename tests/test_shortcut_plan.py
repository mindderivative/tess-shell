"""The ``Shortcuts`` block of settings.tdl, the keys the surfaces declare, and the warnings found
when they are put together (Global Shortcuts > Action Names and Forms, Failure Modes); what
``tesserae-shell check`` reports; and what a key press does to the surfaces and the modules
through the shell's own commands (no bus)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from tess_shell.cli import main
from tess_shell.commands import ShellCommands
from tess_shell.config.settings import load_settings
from tess_shell.scanner import Scan, scan
from tess_shell.schema.keys import Chord, parse_chord
from tess_shell.services.shortcuts import Action
from tess_shell.shortcuts import build_plan, drop_failed, shortcut_handlers
from tests.shell_samples import HEADER
from tests.test_call import running
from tests.test_call_args import OTHER, OTHER_PY, shell_box

SETTINGS_HEAD = "---\nTDL: 0.1\nName: S\n---\n"
LAUNCHER = (
    "Panel { Name: Launcher, Layer: OVERLAY, Width: 600, Height: 400, Visible: false, "
    "%s Children { FlexBox { Name: Inside } } }"
)
SHELL_BODY = """Shell {
    Monitor {
        Name: Main
        Index: 0
        Children {
            Bar { Name: Top_Bar, Edge: TOP, Width: EXPAND, Height: 32, %(bar)s }
            %(launcher)s
            Panel { Name: Settings_Panel, Width: 300, Height: 200, Visible: false }
            Frame { Name: Border_Frame, Thickness: 4 }
            Popup { Name: Menu_Popup }
        }
    }
}
"""


def write(
    cfg: Path, settings: str, *, panel_key: str = "", bar_key: str = "", extra: str = ""
) -> None:
    (cfg / "Shells").mkdir(parents=True, exist_ok=True)
    body = SHELL_BODY % {"bar": bar_key, "launcher": LAUNCHER % panel_key} + extra
    (cfg / "Shells" / "Main_Shell.tdl").write_text(HEADER + body, encoding="utf-8")
    (cfg / "settings.tdl").write_text(
        SETTINGS_HEAD + "Settings {\n" + settings + "\n}\n", encoding="utf-8"
    )


def load(cfg: Path) -> tuple[Scan | None, list[Any]]:
    settings, findings = load_settings(cfg)
    if settings is None:
        return None, findings
    result = scan(settings, cfg)
    return result, result.findings


def plan(tmp_path: Path, settings: str, **kwargs: str) -> tuple[dict[str, Action], list[Any]]:
    write(tmp_path, settings, **kwargs)
    result, findings = load(tmp_path)
    assert result is not None, findings
    assert result.errors == [], result.errors
    return {a.id: a for a in result.shortcuts}, findings


def commands_of(live: Any) -> ShellCommands:
    """The shell's commands over a live manager and module host (a press needs no reloader)."""
    return ShellCommands(live.manager, live.host, cast(Any, None), lambda: None, lambda: [])


def at(path: Path, needle: str, occurrence: int = 0) -> str:
    """``line:column`` of the ``occurrence``-th ``needle`` in a file (1-based)."""
    text = path.read_text(encoding="utf-8")
    pos = -1
    for _ in range(occurrence + 1):
        pos = text.index(needle, pos + 1)
    return f"{text.count(chr(10), 0, pos) + 1}:{pos - text.rfind(chr(10), 0, pos)}"


def warnings(findings: list[Any], rule: str) -> list[Any]:
    return [f for f in findings if f.severity == "warning" and f.rule == rule]


# -- the block ---------------------------------------------------------------------------------


def test_every_form_of_an_entry_becomes_an_action_with_the_entrys_own_name(tmp_path: Path) -> None:
    actions, findings = plan(
        tmp_path,
        """
    Shortcuts {
        Enter_Shortcut_Mode: "Ctrl+Shift+F1"
        Toggle_Launcher: "Meta+Space"
        Show_Top_Bar: "Ctrl+Alt+B"
        Hide_Settings_Panel: "Ctrl+Alt+H"
        Toggle_Border_Frame: "Ctrl+Alt+F"
        Volume_Up { Keys: "XF86AudioRaiseVolume", Action: Toggle, Target: Launcher }
    }""",
    )
    assert findings == []
    assert list(actions) == [
        "Enter_Shortcut_Mode",
        "Toggle_Launcher",
        "Show_Top_Bar",
        "Hide_Settings_Panel",
        "Toggle_Border_Frame",
        "Volume_Up",
    ]
    kinds = {i: (a.kind, a.target) for i, a in actions.items()}
    assert kinds == {
        "Enter_Shortcut_Mode": ("fixed", "Enter_Shortcut_Mode"),
        "Toggle_Launcher": ("toggle", "Launcher"),
        "Show_Top_Bar": ("show", "Top_Bar"),
        "Hide_Settings_Panel": ("hide", "Settings_Panel"),
        "Toggle_Border_Frame": ("toggle", "Border_Frame"),  # a Frame is a surface too
        "Volume_Up": ("handler", ""),
    }
    assert actions["Toggle_Launcher"].friendly == "Toggle Launcher"  # underscores as spaces
    assert actions["Volume_Up"].friendly == "Volume Up"
    assert actions["Toggle_Launcher"].keys == (parse_chord("Meta+Space"),)
    assert actions["Volume_Up"].keys[0].key == "AudioRaiseVolume"  # the XF86 form is read


def test_keys_written_in_any_case_and_order_are_the_same_key(tmp_path: Path) -> None:
    for text in ("ctrl+shift+F1", "Ctrl+Shift+f1", "SHIFT+CTRL+F1"):
        actions, _ = plan(tmp_path, f'Shortcuts {{ Toggle_Launcher: "{text}" }}')
        assert actions["Toggle_Launcher"].keys == (Chord(("Ctrl", "Shift"), "F1"),)


def test_a_shell_with_no_shortcuts_declares_none(tmp_path: Path) -> None:
    actions, findings = plan(tmp_path, "")
    assert actions == {} and findings == []


def test_global_shortcuts_defaults_to_true_and_takes_a_boolean(tmp_path: Path) -> None:
    write(tmp_path, "")
    settings, _ = load_settings(tmp_path)
    assert settings is not None and settings.global_shortcuts is True
    write(tmp_path, "Global_Shortcuts: false")
    settings, _ = load_settings(tmp_path)
    assert settings is not None and settings.global_shortcuts is False
    write(tmp_path, "Global_Shortcuts: 1")
    settings, findings = load_settings(tmp_path)
    assert settings is None and findings[0].rule == "bad-value"
    assert "Global_Shortcuts must be true or false" in findings[0].message


def test_there_is_no_enabled_key_inside_shortcuts(tmp_path: Path) -> None:
    write(tmp_path, "Shortcuts { Enabled: false }")
    settings, findings = load_settings(tmp_path)
    assert settings is None
    assert findings[0].rule == "unknown-key" and "Enabled" in findings[0].message


def test_shortcuts_is_a_block_not_a_property(tmp_path: Path) -> None:
    write(tmp_path, "Shortcuts: 1")
    settings, findings = load_settings(tmp_path)
    assert settings is None and "Shortcuts must be a block" in findings[0].message


# -- errors with file:line:column --------------------------------------------------------------


def test_an_unparsable_key_is_a_value_error_at_the_value(tmp_path: Path) -> None:
    write(tmp_path, '    Shortcuts {\n        Toggle_Launcher: "Ctrl+Spce"\n    }')
    settings, findings = load_settings(tmp_path)
    assert settings is None
    (f,) = findings
    assert (f.file, f.severity, f.rule) == ("settings.tdl", "error", "bad-value")
    assert f"{f.line}:{f.column}" == at(tmp_path / "settings.tdl", '"Ctrl+Spce"')
    assert "unknown key name 'Spce'" in f.message and "Space" in f.hint


@pytest.mark.parametrize(
    ("value", "needle"),
    [
        ('"Ctrl+Alt"', "no key"),
        ('"Ctrl++A"', "empty part"),
        ('""', "empty"),
        ('"Hyper+A"', "unknown modifier"),
        ("5", "keys are a string"),
    ],
)
def test_each_malformed_key_is_reported_where_it_is_written(
    tmp_path: Path, value: str, needle: str
) -> None:
    write(tmp_path, f"Shortcuts {{ Next_Focus: {value} }}")
    settings, findings = load_settings(tmp_path)
    assert settings is None and needle in findings[0].message
    assert findings[0].file == "settings.tdl" and findings[0].line == 6


def test_an_unknown_action_name_is_an_error_naming_the_nearest(tmp_path: Path) -> None:
    write(tmp_path, 'Shortcuts { Next_Focuss: "Ctrl+N", Nothing: "Ctrl+M", Toggle: "Ctrl+T" }')
    settings, findings = load_settings(tmp_path)
    assert settings is None
    by_key = {f.message.split()[-1]: f for f in findings}
    assert set(by_key) == {"Next_Focuss", "Nothing", "Toggle"}
    assert "Next_Focus" in by_key["Next_Focuss"].hint
    assert all(f.rule == "unknown-key" for f in findings)


def test_a_block_entry_needs_keys_and_may_not_take_a_verb_name(tmp_path: Path) -> None:
    write(tmp_path, "Shortcuts { Volume_Up { Action: Toggle, Target: Launcher } }")
    _, findings = load_settings(tmp_path)
    assert findings[0].rule == "missing-key" and "needs Keys" in findings[0].message
    write(tmp_path, 'Shortcuts { Toggle_Launcher { Keys: "A", Action: Toggle, Target: Launcher } }')
    _, findings = load_settings(tmp_path)
    assert findings[0].rule == "bad-name" and "Toggle_" in findings[0].message


def test_an_entry_written_twice_is_an_error(tmp_path: Path) -> None:
    write(tmp_path, 'Shortcuts { Toggle_Launcher: "A", Toggle_Launcher: "B" }')
    settings, findings = load_settings(tmp_path)
    assert settings is None and findings  # the grammar or the reader refuses it, with a position
    assert findings[0].line == 6


# -- warnings found when the shell files are known --------------------------------------------


def test_a_name_that_matches_no_surface_is_a_warning_naming_the_nearest_and_not_registered(
    tmp_path: Path,
) -> None:
    actions, findings = plan(
        tmp_path, 'Shortcuts {\n    Toggle_Launchr: "Meta+Space"\n    Show_Top_Bar: "Ctrl+B"\n}'
    )
    assert "Toggle_Launchr" not in actions and "Show_Top_Bar" in actions
    (w,) = warnings(findings, "shortcut-unknown-surface")
    assert (w.file, f"{w.line}:{w.column}") == (
        "settings.tdl",
        at(tmp_path / "settings.tdl", "Toggle_Launchr"),
    )
    assert "no Panel, Bar or Frame is named Launchr" in w.message
    assert "Toggle_Launcher" in w.hint


def test_a_popup_is_named_with_a_warning_because_no_key_opens_a_popup(tmp_path: Path) -> None:
    actions, findings = plan(tmp_path, 'Shortcuts { Toggle_Menu_Popup: "Ctrl+M" }')
    assert actions == {}
    (w,) = warnings(findings, "shortcut-popup")
    assert "no key opens a Popup" in w.message


def test_a_bar_cannot_be_hidden_or_toggled_by_a_key(tmp_path: Path) -> None:
    actions, findings = plan(
        tmp_path,
        'Shortcuts { Hide_Top_Bar: "Ctrl+H", Toggle_Top_Bar: "Ctrl+T", Show_Top_Bar: "Ctrl+S" }',
    )
    assert list(actions) == ["Show_Top_Bar"]
    assert len(warnings(findings, "shortcut-bar")) == 2


def test_the_keys_a_panel_and_a_bar_declare_are_the_equal_entries(tmp_path: Path) -> None:
    actions, findings = plan(
        tmp_path, "", panel_key='Shortcut: "meta+space",', bar_key='Reveal_Key: "Ctrl+Alt+B",'
    )
    assert findings == []
    assert list(actions) == ["Show_Top_Bar", "Toggle_Launcher"]
    assert actions["Toggle_Launcher"].keys == (parse_chord("Meta+Space"),)
    assert actions["Toggle_Launcher"].kind == "toggle" and actions["Show_Top_Bar"].kind == "show"
    assert actions["Show_Top_Bar"].keys == (parse_chord("Ctrl+Alt+B"),)


def test_a_bad_key_on_a_surface_is_a_value_error_in_the_shell_file(tmp_path: Path) -> None:
    write(tmp_path, "", panel_key='Shortcut: "Meta+Spce",')
    result, findings = load(tmp_path)
    assert result is not None
    errors = [f for f in findings if f.severity == "error"]
    assert errors and errors[0].file == "Shells/Main_Shell.tdl"
    assert "Space" in errors[0].hint and errors[0].rule == "bad-value"


def test_the_entry_wins_over_the_surfaces_own_key_with_one_warning(tmp_path: Path) -> None:
    actions, findings = plan(
        tmp_path, 'Shortcuts { Toggle_Launcher: "Ctrl+Alt+L" }', panel_key='Shortcut: "Meta+Space",'
    )
    assert actions["Toggle_Launcher"].keys == (parse_chord("Ctrl+Alt+L"),)
    (w,) = warnings(findings, "shortcut-override")
    assert w.file == "Shells/Main_Shell.tdl"
    assert "settings.tdl" in w.message and "wins" in w.message
    assert len([a for a in actions if a == "Toggle_Launcher"]) == 1


# -- keys shared within the shell -------------------------------------------------------------


def test_two_actions_with_one_key_give_one_warning_naming_both_and_neither_gets_it(
    tmp_path: Path,
) -> None:
    actions, findings = plan(
        tmp_path,
        'Shortcuts {\n    Toggle_Launcher: "ctrl+alt+t"\n    Show_Top_Bar: "Alt+Ctrl+T"\n'
        '    Next_Focus: "Ctrl+N"\n}',
    )
    (w,) = warnings(findings, "shortcut-conflict")
    here = tmp_path / "settings.tdl"
    assert f"Toggle_Launcher (settings.tdl:{at(here, 'Toggle_Launcher')})" in w.message
    assert f"Show_Top_Bar (settings.tdl:{at(here, 'Show_Top_Bar')})" in w.message
    assert "Ctrl+Alt+T" in w.message and "neither gets it" in w.message
    assert actions["Toggle_Launcher"].keys == () and actions["Show_Top_Bar"].keys == ()
    assert actions["Next_Focus"].keys == (parse_chord("Ctrl+N"),)  # the others are untouched
    assert (w.file, f"{w.line}:{w.column}") == ("settings.tdl", at(here, "Toggle_Launcher"))


def test_a_surfaces_own_key_and_an_entry_with_the_same_key_conflict_across_files(
    tmp_path: Path,
) -> None:
    actions, findings = plan(
        tmp_path, 'Shortcuts { Next_Focus: "Meta+Space" }', panel_key='Shortcut: "Meta+Space",'
    )
    (w,) = warnings(findings, "shortcut-conflict")
    shell = tmp_path / "Shells" / "Main_Shell.tdl"
    assert f"Toggle_Launcher (Shells/Main_Shell.tdl:{at(shell, 'Shortcut:')})" in w.message
    assert "Next_Focus (settings.tdl:" in w.message
    assert actions["Toggle_Launcher"].keys == () and actions["Next_Focus"].keys == ()


def test_three_actions_with_one_key_are_one_warning(tmp_path: Path) -> None:
    actions, findings = plan(
        tmp_path,
        'Shortcuts { Next_Focus: "A", Previous_Focus: "a", Exit_Shortcut_Mode: "Alt+A" }',
    )
    (w,) = warnings(findings, "shortcut-conflict")
    assert w.message.count("(settings.tdl:") == 2
    assert actions["Next_Focus"].keys == actions["Previous_Focus"].keys == ()
    assert actions["Exit_Shortcut_Mode"].keys != ()


def test_the_shell_still_starts_a_conflict_is_a_warning_not_an_error(tmp_path: Path) -> None:
    write(tmp_path, 'Shortcuts { Next_Focus: "A", Previous_Focus: "a" }')
    result, _ = load(tmp_path)
    assert result is not None and result.errors == []


# -- handler entries ---------------------------------------------------------------------------


def test_a_handler_entry_is_a_call_with_its_arguments_and_keys(tmp_path: Path) -> None:
    (tmp_path / "live").mkdir(exist_ok=True)
    live = running(
        tmp_path / "live",
        children=shell_box(""),
        layouts={"Other": OTHER},
        code={"Other": OTHER_PY},
    )
    cfg = tmp_path / "cfg"
    write(
        cfg,
        'Shortcuts { Go_Now { Keys: "XF86AudioRaiseVolume", Action: Call, '
        'Target: "Other.go", Id: 5 } }',
    )
    settings, _ = load_settings(cfg)
    assert settings is not None
    defs = {n: m.definition for n, m in live.host.loaded.items()}
    actions, findings = build_plan(settings.shortcuts, None, defs)
    assert findings == []
    (a,) = actions
    assert (a.id, a.kind, a.friendly) == ("Go_Now", "handler", "Go Now")
    assert a.keys == (parse_chord("AudioRaiseVolume"),)
    assert (a.handler.module, a.handler.action, dict(a.handler.args)) == ("Other", "go", {"Id": 5})
    assert live.host.check_calls(shortcut_handlers(actions)) == []
    # a press runs the module's action with the named arguments
    commands_of(live).press(a)
    assert live.action_seen("Other") == [("go", 5, "a", {"Id": 5})]


def handler_findings(tmp_path: Path, entry: str) -> tuple[list[Any], tuple[Action, ...], Any]:
    (tmp_path / "live").mkdir(exist_ok=True)
    live = running(
        tmp_path / "live",
        children=shell_box(""),
        layouts={"Other": OTHER},
        code={"Other": OTHER_PY},
    )
    cfg = tmp_path / "cfg"
    write(cfg, f"Shortcuts {{\n{entry}\n}}")
    settings, findings = load_settings(cfg)
    assert settings is not None, findings
    defs = {n: m.definition for n, m in live.host.loaded.items()}
    actions, found = build_plan(settings.shortcuts, None, defs)
    return [*found, *live.host.check_calls(shortcut_handlers(actions))], actions, live


def test_the_call_argument_check_applies_to_a_shortcut(tmp_path: Path) -> None:
    entry = 'Go_Now { Keys: "A", Action: Call, Target: "Other.go", Moed: 2 }'
    found, actions, _ = handler_findings(tmp_path, entry)
    rules = sorted(f.rule for f in found)
    assert rules == ["missing-argument", "unknown-argument"]
    assert all(f.file == "settings.tdl" and f.line == 7 for f in found)
    assert drop_failed(actions, found) == ()  # such an action would fail at every press
    entry = 'Go_Now { Keys: "A", Action: Call, Target: "Other.go", Id: 1 }'
    found, actions, _ = handler_findings(tmp_path, entry)
    assert found == [] and drop_failed(actions, found) == actions


def test_a_call_to_a_module_that_does_not_exist_is_an_error_at_load(tmp_path: Path) -> None:
    write(tmp_path, 'Shortcuts { Go_Now { Keys: "A", Action: Call, Target: "Otther.go" } }')
    result, findings = load(tmp_path)
    assert result is not None
    (f,) = [f for f in findings if f.severity == "error"]
    assert f.rule == "unknown-module" and f.file == "settings.tdl"
    assert f.line == 6


def test_a_slot_has_nothing_to_read_in_a_shortcut(tmp_path: Path) -> None:
    write(
        tmp_path, 'Shortcuts { Go_Now { Keys: "A", Action: Toggle, Target: Launcher, X: {{ 1 }} } }'
    )
    result, findings = load(tmp_path)
    assert result is not None and any(
        f.severity == "error" and "slot" in f.message for f in findings
    )


def test_an_event_handler_name_is_not_a_shortcut_action(tmp_path: Path) -> None:
    write(tmp_path, 'Shortcuts { Go_Now { Keys: "A", Action: Frobnicate } }')
    result, findings = load(tmp_path)
    assert result is not None
    assert [f.rule for f in findings if f.severity == "error"] == ["unknown-action"]


# -- tesserae-shell check ---------------------------------------------------------------------


def test_check_reports_the_conflict_the_unknown_name_and_the_bad_chord(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    write(
        tmp_path,
        'Shortcuts {\n    Toggle_Launchr: "Meta+Space"\n    Next_Focus: "A"\n'
        '    Previous_Focus: "a"\n}',
    )
    assert main(["check", "--config-dir", str(tmp_path)]) == 0  # warnings only
    err = capsys.readouterr().err
    assert "settings.tdl:7:5: warning: Toggle_Launchr: no Panel, Bar or Frame is named" in err
    assert "warning: Next_Focus (settings.tdl:8:5) and Previous_Focus (settings.tdl:9:5)" in err
    write(tmp_path, 'Shortcuts {\n    Next_Focus: "Ctrl+Spce"\n}')
    assert main(["check", "--config-dir", str(tmp_path)]) == 1
    err = capsys.readouterr().err
    assert "settings.tdl:7:17: error: unknown key name 'Spce'" in err
    assert "did you mean Space" in err


# -- a key press through the shell's own commands -----------------------------------------------


def test_a_press_shows_hides_and_toggles_a_panel_and_never_opens_a_popup(tmp_path: Path) -> None:
    live = running(tmp_path, popups=LAUNCHER % "" + " Popup { Name: Menu_Popup }")
    commands = commands_of(live)

    def shown() -> bool:
        return next(i for i in live.manager.surface_infos() if i.name == "Launcher").shown

    def press(kind: str, target: str = "Launcher") -> None:
        commands.press(Action(f"X_{target}", "x", kind, target, (), where="settings.tdl:1:1"))

    assert not shown()
    press("toggle")
    assert shown()  # within the call: the surface changed before it returned
    press("toggle")
    assert not shown()
    press("show")
    press("show")
    assert shown()
    press("hide")
    assert not shown()
    infos_before = [(i.name, i.shown) for i in live.manager.surface_infos()]
    press("toggle", "Menu_Popup")  # a key never opens a Popup
    assert [(i.name, i.shown) for i in live.manager.surface_infos()] == infos_before
    assert "no command opens a Popup" in live.log()


def test_a_press_of_a_surface_that_is_gone_does_nothing_and_the_log_names_it(
    tmp_path: Path,
) -> None:
    live = running(tmp_path)
    commands = commands_of(live)
    commands.press(Action("Toggle_Gone", "x", "toggle", "Gone", (), where="settings.tdl:7:5"))
    assert "Toggle_Gone (settings.tdl:7:5): no surface named Gone" in live.log()


def test_the_five_fixed_actions_go_to_a_hook_table_and_do_nothing_until_it_is_filled(
    tmp_path: Path,
) -> None:
    live = running(tmp_path)
    commands = commands_of(live)
    action = Action("Next_Focus", "Next Focus", "fixed", "Next_Focus", ())
    commands.press(action)
    assert "Next_Focus: not built" in live.log()
    seen: list[str] = []
    commands.fixed_actions["Next_Focus"] = lambda: seen.append("next")
    commands.press(action)
    assert seen == ["next"]
