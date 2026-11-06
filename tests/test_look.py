"""Theme files, stylesheets, token references and the priority between them (Style Schema)."""

from __future__ import annotations

from pathlib import Path

import pytest
import tess_dl

from tess_shell.appearance import Appearance
from tess_shell.binder import model as m
from tess_shell.model.look import apply_rules, check_tokens, make_look, resolve
from tess_shell.schema.findings import Finding
from tess_shell.schema.look import effective_tokens, read_stylesheet, read_theme
from tess_shell.schema.model import StylesheetDef, ThemeDef

HEADER = "---\nTDL: 0.1\nName: T\n---\n\n"
THEME = (
    HEADER
    + """
Theme {
    Color { Surface: "#101010", On_Surface: "#eeeeee", Primary: "#6750A4", Accent: DESKTOP }
    Type { Body { Font_Size: 14, Font_Weight: 400, Line_Height: 20 } }
    Shape { Small: 4, Medium: 8 }
    Space { Step_1: 2, Step_3: 8 }
    Elevation { Max { Shadows { Shadow { Color: "#000000", Y: 10, Blur: 20 } } } }
    Motion { Duration { Short: 100, Long: 400 } }
    Modes {
        Light { Color { Surface: "#ffffff", On_Surface: "#111111" } }
        High_Contrast { Color { Surface: "#000000" } }
    }
}
"""
)


def theme(text: str = THEME) -> ThemeDef:
    result = tess_dl.parse(text, path="Themes/T_Theme.tdl")
    assert not result.errors and result.document is not None
    found, findings = read_theme(result.document, "Themes/T_Theme.tdl")
    assert found is not None, findings
    return found


def theme_errors(text: str) -> list[Finding]:
    result = tess_dl.parse(text, path="Themes/T_Theme.tdl")
    assert not result.errors and result.document is not None
    found, findings = read_theme(result.document, "Themes/T_Theme.tdl")
    assert found is None
    return [f for f in findings if f.severity == "error"]


def sheet(body: str, modules: set[str] | None = None) -> tuple[StylesheetDef, list[Finding]]:
    result = tess_dl.parse(HEADER + body, path="Stylesheets/T_Stylesheet.tdl")
    assert not result.errors and result.document is not None
    found, findings = read_stylesheet(
        result.document, "Stylesheets/T_Stylesheet.tdl", modules or set()
    )
    assert found is not None, findings
    return found, findings


def text(name: str | None = None, classes: tuple[str, ...] = (), **style: m.Value) -> m.Node:
    return m.Node(
        "Text", name=name, props={"Text": m.Text("x")}, style=dict(style), classes=classes
    )


def ref(path: str, kind: str) -> m.TokenRef:
    return m.TokenRef(path, kind)


# -- the theme file ---------------------------------------------------------------------------


def test_a_theme_with_every_token_group_loads_with_flat_lower_case_paths() -> None:
    t = theme()
    assert t.name == "T" or t.file == "Themes/T_Theme.tdl"
    assert {
        "color.on_surface",
        "type.body.font_size",
        "shape.medium",
        "space.step_3",
        "motion.duration.long",
        "elevation.max",
    } <= set(t.tokens)
    assert set(t.modes) == {"light", "high_contrast"}


@pytest.mark.parametrize(
    ("body", "needle"),
    [
        ('Color { Surface: "not-a-colour" }', "colour"),
        ("Color { Surface: 5 }", "colour"),
        ("Type { Body { Font_Size: 0 } }", "greater than 0"),
        ("Space { Step_1: red }", "number"),
        ('Colour { Surface: "#000000" }', "Color"),
        ("Elevation { Max { Reach: 3 } }", "Shadows"),
        ("Modes { Sepia { } }", "Light"),
    ],
)
def test_a_bad_theme_value_is_reported_at_its_own_line(body: str, needle: str) -> None:
    found = theme_errors(HEADER + "Theme {\n    " + body + "\n}\n")
    assert any(needle in (f.message + f.hint) for f in found), found
    assert all(f.file == "Themes/T_Theme.tdl" and f.line >= 7 for f in found)


# -- modes and the desktop --------------------------------------------------------------------


def colour(tokens: dict, path: str) -> object:  # type: ignore[type-arg]
    value = tokens[path].value
    return getattr(value, "value", getattr(value, "text", None))


def test_the_base_block_is_the_default_variant_and_light_overrides_it() -> None:
    t = theme()
    assert colour(effective_tokens(t, Appearance()), "color.surface") == "#101010"
    assert colour(effective_tokens(t, Appearance(scheme="dark")), "color.surface") == "#101010"
    light = effective_tokens(t, Appearance(scheme="light"))
    assert colour(light, "color.surface") == "#ffffff"
    assert colour(light, "color.primary") == "#6750A4"  # what a mode does not name is kept


def test_high_contrast_applies_on_top_of_the_scheme() -> None:
    t = theme()
    tokens = effective_tokens(t, Appearance(scheme="light", high_contrast=True))
    assert colour(tokens, "color.surface") == "#000000"
    assert colour(tokens, "color.on_surface") == "#111111"  # from Light, not overridden


def test_reduced_motion_zeroes_every_duration() -> None:
    tokens = effective_tokens(theme(), Appearance(reduced_motion=True))
    assert colour(tokens, "motion.duration.short") == 0
    assert colour(tokens, "motion.duration.long") == 0
    assert colour(effective_tokens(theme(), Appearance()), "motion.duration.long") == 400


def test_accent_desktop_takes_the_desktops_accent_else_the_primary() -> None:
    t = theme()
    assert colour(effective_tokens(t, Appearance(accent=(0, 128, 255))), "color.accent") == (
        "#0080ff"
    )
    assert colour(effective_tokens(t, Appearance()), "color.accent") == "#6750A4"


# -- resolving a token reference ---------------------------------------------------------------


def look(**appearance: object):  # type: ignore[no-untyped-def]
    return make_look(theme(), [], Appearance(**appearance))  # type: ignore[arg-type]


def test_a_reference_is_read_as_the_kind_of_the_key_that_names_it() -> None:
    node = text(
        Foreground=ref("color.on_surface", "color"),
        Font_Size=ref("type.body.font_size", "positive"),
    )
    (out,), errors = resolve([node], look())
    assert errors == []
    assert out.style["Foreground"] == m.Color(0xEE, 0xEE, 0xEE, 255)
    assert out.style["Font_Size"] == m.Number(14)


def test_a_light_look_resolves_the_same_reference_to_another_value() -> None:
    node = text(Foreground=ref("color.on_surface", "color"))
    (dark,), _ = resolve([node], look(scheme="dark"))
    (light,), _ = resolve([node], look(scheme="light"))
    assert dark.style["Foreground"] != light.style["Foreground"]
    assert light.style["Foreground"] == m.Color(0x11, 0x11, 0x11, 255)


def test_an_unknown_token_names_the_nearest_and_drops_the_key() -> None:
    (out,), errors = resolve([text(Foreground=ref("color.on_surfce", "color"))], look())
    assert "Foreground" not in out.style
    (error,) = errors
    assert "no token named $color.on_surfce" in error.message
    assert "$color.on_surface" in error.hint


def test_a_token_of_the_wrong_kind_is_an_error_not_a_guess() -> None:
    (_out,), errors = resolve([text(Foreground=ref("space.step_3", "color"))], look())
    assert errors and "cannot be used here" in errors[0].message


def test_elevation_uses_the_themes_own_max_shadow() -> None:
    node = m.Node("Rectangle", style={"Elevation": m.Percent(50)})
    (out,), _ = resolve([node], look())
    shadows = out.style["Shadows"]
    assert isinstance(shadows, m.Shadows)
    (shadow,) = shadows.items
    assert (shadow.y, shadow.blur) == (5, 10)  # half of the theme's Y 10, Blur 20


def test_check_finds_a_missing_token_before_the_shell_runs() -> None:
    node = text(Foreground=ref("color.nope", "color"), Font_Size=ref("space.step_3", "positive"))
    found = check_tokens([node], effective_tokens(theme(), Appearance()))
    assert [f.rule for f in found] == ["bad-token"]
    assert "color.nope" in found[0].message


# -- the stylesheet ---------------------------------------------------------------------------

SHEET = """
Stylesheet {
    Rule { Selector: "Text", Foreground: "#111111", Font_Size: 12 }
    Rule { Selector: ".warning", Foreground: "#ff0000" }
    Rule { Selector: "#clock", Foreground: "#00ff00" }
}
"""


def test_a_stylesheet_with_each_selector_form_loads() -> None:
    s, findings = sheet(SHEET)
    assert findings == []
    assert [(r.kind, r.target) for r in s.rules] == [
        ("type", "Text"),
        ("class", "warning"),
        ("name", "clock"),
    ]


def fg(node: object) -> m.Value | None:
    assert isinstance(node, m.Node)
    return node.style.get("Foreground")


def test_a_name_beats_a_class_beats_a_type() -> None:
    s, _ = sheet(SHEET)
    tree = (
        text(),  # type only
        text(classes=("warning",)),  # type and class
        text(name="clock", classes=("warning",)),  # type, class and name
    )
    plain, warned, named = apply_rules(tree, s.rules)
    assert fg(plain) == m.Color(0x11, 0x11, 0x11, 255)
    assert fg(warned) == m.Color(0xFF, 0, 0, 255)
    assert fg(named) == m.Color(0, 0xFF, 0, 255)
    assert isinstance(plain, m.Node) and plain.style["Font_Size"] == m.Number(12)  # from the type


def test_of_two_rules_of_one_weight_the_later_wins() -> None:
    s, _ = sheet(
        'Stylesheet { Rule { Selector: "Text", Foreground: "#111111" }\n'
        'Rule { Selector: "Text", Foreground: "#222222" } }'
    )
    (out,) = apply_rules((text(),), s.rules)
    assert fg(out) == m.Color(0x22, 0x22, 0x22, 255)


def test_the_blocks_own_style_and_keys_beat_the_stylesheet() -> None:
    s, _ = sheet(SHEET)
    own = text(Foreground=m.Color(1, 2, 3, 255))  # from its style file, a class or inline Style
    written = m.Node("Text", props={"Foreground": m.Color(9, 9, 9, 255)})
    a, b = apply_rules((own, written), s.rules)
    assert fg(a) == m.Color(1, 2, 3, 255)
    assert isinstance(b, m.Node) and "Foreground" not in b.style  # the key written on it wins


def test_a_rule_reaches_blocks_inside_other_blocks_and_in_if_and_for() -> None:
    s, _ = sheet(SHEET)
    inner = m.Node("FlexBox", children=(text(),))
    cond = m.IfNode(body=(text(),))
    (box, branch) = apply_rules((inner, cond), s.rules)  # type: ignore[misc]
    assert fg(box.children[0]) == m.Color(0x11, 0x11, 0x11, 255)  # type: ignore[union-attr]
    assert fg(branch.body[0]) == m.Color(0x11, 0x11, 0x11, 255)  # type: ignore[union-attr]


def test_a_key_the_block_does_not_take_is_skipped_not_an_error() -> None:
    s, _ = sheet(
        'Stylesheet { Rule { Selector: ".card", Background: "#123456", Foreground: "#fff" } }'
    )
    spacer = m.Node("Spacer", classes=("card",))
    (out,) = apply_rules((spacer,), s.rules)
    assert isinstance(out, m.Node) and out.style == {}  # a Spacer has no Background


@pytest.mark.parametrize(
    ("body", "needle"),
    [
        ('Rule { Foreground: "#fff" }', "needs a Selector"),
        ("Rule { Selector: Text }", "quoted string"),
        ('Rule { Selector: "Texxt", Foreground: "#fff" }', "unknown block"),
        ('Rule { Selector: "Text", Backgroundd: "#fff" }', "Background"),
        ('Rule { Selector: "Text", Corner_Radius: 4 }', "no style key"),
        ('Rule { Selector: "..x" }', "not a selector"),
    ],
)
def test_a_bad_rule_is_reported(body: str, needle: str) -> None:
    result = tess_dl.parse(HEADER + "Stylesheet {\n" + body + "\n}\n", path="S_Stylesheet.tdl")
    assert result.document is not None
    found, findings = read_stylesheet(result.document, "S_Stylesheet.tdl", set())
    assert found is None
    assert any(needle in f.message + f.hint for f in findings), findings


def test_state_and_part_selectors_are_skipped_with_a_warning() -> None:
    s, findings = sheet(
        'Stylesheet { Rule { Selector: "Text:hovered", Foreground: "#fff" }\n'
        'Rule { Selector: "Text::label", Foreground: "#fff" } }'
    )
    assert s.rules == ()
    assert [f.severity for f in findings] == ["warning", "warning"]
    assert all(f.rule == "not-built" for f in findings)


def test_a_module_name_selector_styles_the_modules_root_blocks_only() -> None:
    from tess_shell.model.look import apply_module_rules

    s, findings = sheet(
        'Stylesheet { Rule { Selector: "Clock", Foreground: "#ff00ff" }\n'
        'Rule { Selector: "Text", Foreground: "#111111" } }',
        {"Clock"},
    )
    assert findings == [] and [r.kind for r in s.rules] == ["module", "type"]
    inner = text()
    root = m.Node("FlexBox", children=(inner,))
    (styled,) = apply_module_rules([root], "Clock", s.rules)
    assert isinstance(styled, m.Node) and "Foreground" not in styled.style  # a FlexBox has none
    (plain,) = apply_module_rules([text()], "Clock", s.rules)
    assert fg(plain) == m.Color(0xFF, 0, 0xFF, 255)  # the root Text of the module
    (other,) = apply_module_rules([text()], "Other", s.rules)
    assert fg(other) is None  # a rule for Clock does not reach another module
    (kept,) = apply_rules((inner,), s.rules)  # the type rule still reaches an inner block
    assert fg(kept) == m.Color(0x11, 0x11, 0x11, 255)


def test_a_name_selector_beats_a_module_selector_on_a_root_block() -> None:
    from tess_shell.model.look import apply_module_rules

    s, _ = sheet('Stylesheet { Rule { Selector: "Clock", Foreground: "#ff00ff" } }', {"Clock"})
    kept = text(Foreground=m.Color(1, 2, 3, 255))  # the block's own style wins
    (out,) = apply_module_rules([kept], "Clock", s.rules)
    assert fg(out) == m.Color(1, 2, 3, 255)


def test_the_stylesheet_may_use_tokens_and_the_theme_resolves_them() -> None:
    s, _ = sheet('Stylesheet { Rule { Selector: "Text", Foreground: $color.on_surface } }')
    (styled,) = apply_rules((text(),), s.rules)
    (out,), errors = resolve([styled], make_look(theme(), [s], Appearance(scheme="light")))  # type: ignore[list-item]
    assert errors == [] and out.style["Foreground"] == m.Color(0x11, 0x11, 0x11, 255)


def test_the_shipped_theme_and_stylesheet_load_and_agree() -> None:
    from tess_shell.config.discovery import shipped_dir

    base = shipped_dir()
    t = theme((base / "Themes" / "Default_Theme.tdl").read_text())
    result = tess_dl.parse((base / "Stylesheets" / "Default_Stylesheet.tdl").read_text())
    assert result.document is not None
    s, findings = read_stylesheet(result.document, "Default_Stylesheet.tdl", set())
    assert s is not None and findings == []
    for rule in s.rules:  # every token the shipped sheet names exists in the shipped theme
        node = (
            text(**rule.values) if rule.target == "Text" else m.Node("SVG", style=dict(rule.values))
        )
        assert check_tokens([node], effective_tokens(t, Appearance())) == []
    assert {"color.accent", "color.surface", "elevation.max"} <= set(t.tokens)
    assert Path(base / "Themes" / "Default_Theme.tdl").is_file()


# -- a partial theme falls back to the Default theme, token by token (D42) ---------------------


def test_a_token_the_theme_lacks_comes_from_the_default_theme_in_the_current_look() -> None:
    from tess_shell.config.discovery import shipped_dir

    default = theme((shipped_dir() / "Themes" / "Default_Theme.tdl").read_text())
    partial = theme(
        HEADER
        + 'Theme { Color { Surface: "#112233" } Modes { Light { Color { Surface: "#ffffff" } } } }'
    )
    dark = effective_tokens(partial, Appearance(scheme="dark"), default)
    assert colour(dark, "color.surface") == "#112233"  # the theme's own
    assert colour(dark, "color.on_surface") == "#E4EAF1"  # the Default's, dark
    light = effective_tokens(partial, Appearance(scheme="light"), default)
    assert colour(light, "color.surface") == "#ffffff"  # the theme's own light mode
    assert colour(light, "color.on_surface") == "#16202B"  # the Default's light mode
    assert "type.body.font_size" in dark and "elevation.max" in dark
    assert "type.body.font_size" not in effective_tokens(partial, Appearance())  # no fallback given


def test_a_token_neither_theme_defines_is_still_an_error() -> None:
    node = text(Foreground=ref("color.nope", "color"))
    found = check_tokens([node], effective_tokens(theme(), Appearance(), theme()))
    assert [f.rule for f in found] == ["bad-token"]
