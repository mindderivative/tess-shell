"""Theme and stylesheet files through ``tesserae-shell check``: the scan finds them, names the
chosen ones, and reports a bad token at its line (Style Schema acceptance criteria)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tess_shell.appearance import Appearance
from tess_shell.cli import main
from tess_shell.config.settings import AppearanceSettings, load_settings
from tess_shell.scanner import build_look, scan
from tests.shell_samples import BODY, write_example

THEME = """---
TDL: 0.2
Name: Mine
---
Theme { Color { Surface: "#202020", On_Surface: "#f0f0f0" } Space { Step_3: 8 } }
"""
SHEET = """---
TDL: 0.2
Name: Mine_Rules
---
Stylesheet { Rule { Selector: "Text", Foreground: $color.on_surface } }
"""


def settings_file(cfg: Path, appearance: str) -> None:
    (cfg / "settings.tdl").write_text(
        f"---\nTDL: 0.2\nName: S\n---\nSettings {{ Appearance {{ {appearance} }} }}\n"
    )


def config(tmp_path: Path, body: str = BODY, appearance: str = "") -> Path:
    write_example(tmp_path, body)
    (tmp_path / "Themes").mkdir()
    (tmp_path / "Themes" / "Mine_Theme.tdl").write_text(THEME)
    (tmp_path / "Stylesheets").mkdir()
    (tmp_path / "Stylesheets" / "Mine_Rules_Stylesheet.tdl").write_text(SHEET)
    if appearance:
        settings_file(tmp_path, appearance)
    return tmp_path


def test_the_appearance_settings_are_read(tmp_path: Path) -> None:
    settings_file(
        tmp_path, "Theme: Mine, Stylesheets: [Mine_Rules, Default], Follow_Desktop: false"
    )
    settings, findings = load_settings(tmp_path)
    assert findings == [] and settings is not None
    assert settings.appearance == AppearanceSettings("Mine", ("Mine_Rules", "Default"), False)


def test_a_misspelt_appearance_key_names_the_nearest(tmp_path: Path) -> None:
    settings_file(tmp_path, "Themes: Mine")
    settings, findings = load_settings(tmp_path)
    assert settings is None and "Theme" in findings[0].hint


def test_the_shipped_theme_and_stylesheet_are_found_with_no_configuration(tmp_path: Path) -> None:
    write_example(tmp_path)
    settings, _ = load_settings(tmp_path)
    assert settings is not None
    result = scan(settings, tmp_path)
    assert result.errors == []
    assert "Default" in result.themes and "Default" in result.stylesheets
    look = build_look(result, settings, Appearance())
    assert look.theme.name == "Default" and look.rules  # the Default stylesheet (ADR-0022)


def test_no_stylesheets_key_means_default_and_an_empty_list_means_none(tmp_path: Path) -> None:
    """ADR-0022: absent is [Default]; an explicit [] is a choice and gives no rules."""
    write_example(tmp_path)
    settings, _ = load_settings(tmp_path)
    assert settings is not None and settings.appearance.stylesheets == ("Default",)
    settings_file(tmp_path, "Follow_Desktop: false")  # an Appearance block with no Stylesheets
    settings, _ = load_settings(tmp_path)
    assert settings is not None and settings.appearance.stylesheets == ("Default",)
    settings_file(tmp_path, "Stylesheets: []")
    settings, _ = load_settings(tmp_path)
    assert settings is not None and settings.appearance.stylesheets == ()
    look = build_look(scan(settings, tmp_path), settings, Appearance())
    assert look.rules == ()


FIELD_BODY = BODY.replace(
    "Children {\n                    FlexBox {",
    "Children {\n                    TextInput { }\n                    FlexBox {",
    1,
)


@pytest.mark.parametrize(
    ("appearance", "body", "noted"),
    [
        ("Stylesheets: []", FIELD_BODY, True),  # a TextField in use and no stylesheet
        ("Stylesheets: []", BODY, False),  # nothing that needs one
        ("Stylesheets: [Default]", FIELD_BODY, False),
        ("Follow_Desktop: false", FIELD_BODY, False),  # the key left out means Default
    ],
)
def test_the_note_about_no_stylesheet_only_when_a_field_or_list_is_in_use(
    tmp_path: Path, appearance: str, body: str, noted: bool
) -> None:
    assert body is BODY or "TextInput { }" in body
    write_example(tmp_path, body)
    settings_file(tmp_path, appearance)
    settings, _ = load_settings(tmp_path)
    assert settings is not None
    rules = [f.rule for f in scan(settings, tmp_path).findings]
    assert ("appearance-no-stylesheet" in rules) is noted


def test_a_named_theme_and_stylesheet_make_the_look(tmp_path: Path) -> None:
    cfg = config(tmp_path, appearance="Theme: Mine, Stylesheets: [Mine_Rules]")
    settings, _ = load_settings(cfg)
    assert settings is not None
    result = scan(settings, cfg)
    assert result.errors == []
    look = build_look(result, settings, Appearance())
    assert look.theme.name == "Mine" and len(look.rules) == 1


@pytest.mark.parametrize(
    ("appearance", "rule", "needle"),
    [
        ("Theme: Mime", "theme-not-found", "Mine"),
        ("Stylesheets: [Mine_Rule]", "stylesheet-not-found", "Mine_Rules"),
    ],
)
def test_an_unknown_name_suggests_the_nearest(
    tmp_path: Path, appearance: str, rule: str, needle: str
) -> None:
    cfg = config(tmp_path, appearance=appearance)
    settings, _ = load_settings(cfg)
    assert settings is not None
    (finding,) = scan(settings, cfg).errors
    assert finding.rule == rule and needle in finding.hint


def test_check_reports_an_unknown_token_at_its_line_with_the_nearest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body = BODY.replace('Style { Fill: "#1f1f1f" }', "Style { Fill: $color.surfce }")
    cfg = config(tmp_path, body, "Theme: Mine")
    assert main(["check", "--config-dir", str(cfg)]) == 1
    err = capsys.readouterr().err
    assert "Shells/Main_Shell.tdl:" in err and "no token named $color.surfce" in err
    assert "did you mean $color.surface" in err


def test_check_reports_a_token_of_the_wrong_kind(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body = BODY.replace("Spacing: 8", "Spacing: $color.surface")
    assert main(["check", "--config-dir", str(config(tmp_path, body, "Theme: Mine"))]) == 1
    assert "cannot be used here" in capsys.readouterr().err


def test_a_token_in_a_bar_key_that_is_not_style_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body = BODY.replace("Height: 32", "Height: $space.step_3")
    assert main(["check", "--config-dir", str(config(tmp_path, body, "Theme: Mine"))]) == 1
    assert "Height" in capsys.readouterr().err


def test_a_good_themed_config_checks_clean(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    body = BODY.replace('Style { Fill: "#1f1f1f" }', "Style { Fill: $color.surface }").replace(
        "Spacing: 8", "Spacing: $space.step_3"
    )
    assert main(["check", "--config-dir", str(config(tmp_path, body, "Theme: Mine"))]) == 0
    assert "ok:" in capsys.readouterr().out


STATE_SHEET = """---
TDL: 0.2
Name: Mine_Rules
---
Stylesheet {
    Rule { Selector: "FlexBox:hovered", Background: "#334455" }
    Rule { Selector: "Text:hovered", Foreground: "#ffffff" }
}
"""


def test_a_state_rule_that_reaches_a_text_is_a_warning_in_the_scan(tmp_path: Path) -> None:
    cfg = config(tmp_path, appearance="Theme: Mine, Stylesheets: [Mine_Rules]")
    (cfg / "Stylesheets" / "Mine_Rules_Stylesheet.tdl").write_text(STATE_SHEET)
    settings, _ = load_settings(cfg)
    assert settings is not None
    result = scan(settings, cfg)
    assert result.errors == []
    (warning,) = [f for f in result.findings if f.rule == "state-never-applies"]
    assert warning.severity == "warning" and "Mine_Rules_Stylesheet.tdl" in warning.file
    assert "Text" in warning.message


def test_check_reports_an_unknown_token_in_a_frames_colours(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    frame = (
        "Frame { Name: F, Thickness: 8, Inner_Border { Width: 1, Color: $color.on_surfce },"
        " Style { Background: $color.surfce } }\n            Bar {"
    )
    cfg = config(
        tmp_path, BODY.replace("            Bar {", f"            {frame}", 1), "Theme: Mine"
    )
    assert main(["check", "--config-dir", str(cfg)]) == 1
    err = capsys.readouterr().err
    assert "no token named $color.surfce" in err and "no token named $color.on_surfce" in err
