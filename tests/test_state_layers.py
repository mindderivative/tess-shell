"""State layers (State Layers, ADR-0009): ``Hover_Layer``, ``Pressed_Layer`` and ``Focus_Layer``
take a colour role and draw it at the opacity of the theme's ``state.*`` token (tre 0.6.11)."""

from __future__ import annotations

import pytest
import tess_dl

from tess_shell.appearance import Appearance
from tess_shell.binder import model as m
from tess_shell.model.look import make_look, resolve_style
from tess_shell.schema.look import read_theme
from tests.widgets_live import THEME, running


def look():  # type: ignore[no-untyped-def]
    doc = tess_dl.parse(THEME, path="T_Theme.tdl").document
    assert doc is not None
    theme, findings = read_theme(doc, "T_Theme.tdl")
    assert theme is not None, findings
    return make_look(theme, [], Appearance())


def test_the_state_tokens_are_the_percentages_of_the_note() -> None:
    tokens = look().tokens
    assert [tokens[f"state.{s}"].value.value for s in ("hover", "focus", "pressed", "dragged")] == [  # type: ignore[union-attr]
        0.08,
        0.10,
        0.10,
        0.16,
    ]


def test_a_layer_colour_role_takes_the_opacity_of_its_state() -> None:
    lk = look()
    base = m.Color(10, 20, 30, 255)
    out = resolve_style({"Hover_Layer": base, "Pressed_Layer": base, "Focus_Layer": base}, lk)
    assert [out[k].a for k in ("Hover_Layer", "Pressed_Layer", "Focus_Layer")] == [20, 26, 26]
    assert (out["Hover_Layer"].r, out["Hover_Layer"].g, out["Hover_Layer"].b) == (10, 20, 30)


def test_a_colour_with_its_own_alpha_is_kept() -> None:
    own = m.Color(255, 255, 255, 0x14)
    assert resolve_style({"Hover_Layer": own}, look())["Hover_Layer"] == own


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_a_button_draws_the_three_layers_in_the_content_colour(scheme: str) -> None:
    with running('Button { Text: "Go" }', appearance=Appearance(scheme=scheme)) as w:  # type: ignore[arg-type]
        root = w.of_use("Button", "Root")
        hover, pressed, focus = (
            root.get(k) for k in ("hover_layer", "pressed_layer", "focus_layer")
        )
        assert (hover[3], pressed[3], focus[3]) == (20, 26, 26)
        assert hover[:3] == pressed[:3] == focus[:3]
        assert root.get("focus_layer_any_modality") is False  # keyboard focus only


def test_the_layers_replace_the_old_opacity_and_border_hover_literals() -> None:
    with running("Toggle { } Checkbox { Text: x }") as w:
        for module in ("Toggle", "Checkbox"):
            root = w.of_use(module, "Root")
            assert root.get("hover_layer") is not None


def test_each_layer_fades_for_the_time_of_its_state_token() -> None:
    with running('Button { Text: "Go" }') as w:
        root = w.of_use("Button", "Root")
        assert [root.get(k) for k in ("hover_layer_ms", "pressed_layer_ms", "focus_layer_ms")] == [
            100,
            105,
            150,
        ]
