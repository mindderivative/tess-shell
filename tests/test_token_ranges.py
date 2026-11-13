"""A value that arrives through a theme token is judged by the range of the key it fills, like a
value written in the file (T-028): the finding names the key, the token and the range, and points
at the token's own line in the theme."""

from __future__ import annotations

from tess_shell.appearance import Appearance
from tess_shell.binder import model as m
from tess_shell.model.look import check_tokens, make_look, resolve
from tess_shell.schema.look import effective_tokens
from tests.test_look import HEADER, ref, text, theme

THEME = (
    HEADER
    + """
Theme {
    Color { Surface: "#101010" }
    Type { Body { Font_Size: 14, Font_Weight: 400, Line_Height: 20 } }
    Shape { Small: 0.5 }
    Space { Step_1: 2, Step_3: 8 }
    Modes {
        High_Contrast { Space { Step_1: 0 } Shape { Small: 3 } }
    }
}
"""
)


def look(**appearance: object):  # type: ignore[no-untyped-def]
    return make_look(theme(THEME), [], Appearance(**appearance))  # type: ignore[arg-type]


def box(**style: m.Value) -> m.Node:
    return m.Node("Box", style=dict(style))


def test_a_token_value_above_the_range_of_opacity_is_an_error_at_the_use_site() -> None:
    node = box(Opacity=ref("space.step_1", "number"))
    (out,), errors = resolve([node], look())
    assert "Opacity" not in out.style  # the key keeps its default
    (error,) = errors
    assert error.message.startswith("Opacity: $space.step_1 cannot be used here")
    assert "expected a number, from 0 to 1, found 2" in error.message
    assert "defined at" in error.hint and "T_Theme.tdl" in error.hint


def test_a_token_value_inside_the_range_is_taken() -> None:
    node = box(Opacity=ref("space.step_1", "number"), Padding=ref("space.step_3", "sides"))
    (out,), errors = resolve([node], look(high_contrast=True))
    assert errors == []
    assert out.style["Opacity"] == m.Number(0) and out.style["Padding"] == m.Length(8)


def test_the_modes_overrides_go_through_the_same_check() -> None:
    node = box(Opacity=ref("shape.small", "number"))
    (ok,), errors = resolve([node], look())
    assert errors == [] and ok.style["Opacity"] == m.Number(0.5)
    (bad,), errors = resolve([node], look(high_contrast=True))  # the mode makes it 3
    assert "Opacity" not in bad.style
    assert "expected a number, from 0 to 1, found 3" in errors[0].message
    assert "$shape.small" in errors[0].message
    weight = text(Font_Weight=ref("space.step_1", "whole"))
    (bad,), errors = resolve([weight], look(high_contrast=True))  # 0 there
    assert "expected a whole number, from 1 to 1000, found 0" in errors[0].message


def test_check_tokens_names_the_key_the_token_and_the_range_before_the_shell_runs() -> None:
    node = box(Opacity=ref("space.step_1", "number"), Flex_Grow=ref("space.step_3", "number"))
    found = check_tokens([node], effective_tokens(theme(THEME), Appearance()))
    assert [f.rule for f in found] == ["bad-token"]
    assert found[0].message.startswith("Opacity: $space.step_1")
    assert "from 0 to 1" in found[0].message
    assert found[0].line > 0


def test_a_kind_range_applies_to_a_token_as_well() -> None:
    node = text(Font_Size=ref("space.step_1", "positive"))
    (_out,), errors = resolve([node], look(high_contrast=True))  # Step_1 is 0 there
    assert "expected a number, greater than 0, found 0" in errors[0].message


def shipped_references() -> list[tuple[str, str, m.TokenRef]]:
    """(file, key, reference) of every theme token a shipped stylesheet, style or module uses."""
    from importlib import resources

    import tess_dl

    from tess_shell.model.look import _walk
    from tess_shell.schema.look import read_stylesheet
    from tess_shell.schema.shell import read_module, read_module_params, read_style

    root = resources.files("tess_shell") / "shipped"
    files = sorted(p for p in root.rglob("*.tdl"))
    stubs = {}
    for path in files:
        if path.name.endswith("_Module.tdl"):
            doc = tess_dl.parse(path.read_text(encoding="utf-8"), path=path.name).document
            assert doc is not None
            found = read_module_params(doc, path.name)
            assert found is not None
            stubs[found.name] = found
    out: list[tuple[str, str, m.TokenRef]] = []

    def collect(name: str, table: dict[str, m.Value]) -> None:
        out.extend((name, k, v) for k, v in table.items() if isinstance(v, m.TokenRef))

    for path in files:
        parsed = tess_dl.parse(path.read_text(encoding="utf-8"), path=path.name)
        assert parsed.document is not None
        kind = parsed.document.root.type
        if kind == "Stylesheet":
            sheet, _ = read_stylesheet(parsed.document, path.name, set(stubs))
            assert sheet is not None
            for rule in sheet.rules:
                collect(path.name, dict(rule.values))
        elif kind == "Style":
            style, _ = read_style(parsed.document, path.name)
            assert style is not None
            for defaults in style.defaults.values():
                collect(path.name, dict(defaults))
            for cls in style.classes.values():
                collect(path.name, dict(cls.values))
        elif kind == "Module":
            module, _ = read_module(parsed.document, path.name, stubs)
            if module is None:
                continue
            for node in _walk(module.children):
                collect(path.name, {**node.props, **node.style})
    return out


def test_every_token_the_shipped_files_use_passes_the_range_of_its_key_in_every_mode() -> None:
    from importlib import resources

    import tess_dl

    from tess_shell.model.look import _ref_value
    from tess_shell.schema.look import read_theme

    path = resources.files("tess_shell") / "shipped" / "Themes" / "Default_Theme.tdl"
    parsed = tess_dl.parse(path.read_text(encoding="utf-8"), path="Default_Theme.tdl")
    assert parsed.document is not None
    default, findings = read_theme(parsed.document, "Default_Theme.tdl")
    assert default is not None and findings == []
    used = shipped_references()
    assert len(used) > 50
    for appearance in (
        Appearance(),
        Appearance(scheme="light"),
        Appearance(high_contrast=True),
        Appearance(reduced_motion=True),
        Appearance(scheme="light", high_contrast=True, reduced_motion=True),
    ):
        tokens = effective_tokens(default, appearance)
        for _file, key, reference in used:
            _ref_value(reference, tokens, key)  # raises TokenProblem on any finding: none may
