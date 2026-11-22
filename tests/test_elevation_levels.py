"""The MD3 elevation levels (Elevation): ``Elevation { Level_1 ... Level_5 }`` in the theme and
``Elevation: LEVEL_n`` on a block."""

from __future__ import annotations

import pytest
import tess_dl

from tess_shell.appearance import Appearance
from tess_shell.binder import model as m
from tess_shell.model.look import make_look, resolve_style
from tess_shell.schema.look import read_theme
from tess_shell.schema.values import coerce
from tests.widgets_live import THEME

# the table of the Elevation note: key shadow (30 percent) then ambient shadow (15 percent), as
# (y, blur, spread) with x 0
LEVELS = {
    1: ((1, 2, 0), (1, 3, 1)),
    2: ((1, 2, 0), (2, 6, 2)),
    3: ((1, 3, 0), (4, 8, 3)),
    4: ((2, 3, 0), (6, 10, 4)),
    5: ((4, 4, 0), (8, 12, 6)),
}


def look():  # type: ignore[no-untyped-def]
    doc = tess_dl.parse(THEME, path="T_Theme.tdl").document
    assert doc is not None
    theme, findings = read_theme(doc, "T_Theme.tdl")
    assert theme is not None, findings
    return make_look(theme, [], Appearance())


@pytest.mark.parametrize("level", sorted(LEVELS))
def test_each_level_is_the_two_shadows_of_the_table(level: int) -> None:
    token = look().tokens[f"elevation.level_{level}"].value
    assert isinstance(token, m.Shadows) and len(token.items) == 2
    key, ambient = token.items
    assert (key.color.a, ambient.color.a) == (0x4D, 0x26)  # 30 and 15 percent of 255
    assert [(s.x, s.y, s.blur, s.spread) for s in (key, ambient)] == [
        (0, *LEVELS[level][0]),
        (0, *LEVELS[level][1]),
    ]


def test_a_block_that_names_a_level_gets_its_shadows_and_level_0_none() -> None:
    lk = look()
    node = coerce("elevation", tess_dl.Word("LEVEL_3"), m.Origin("<t>", 1, 1))
    out = resolve_style({"Elevation": node}, lk)
    assert out["Shadows"] == lk.tokens["elevation.level_3"].value and "Elevation" not in out
    zero = coerce("elevation", tess_dl.Word("LEVEL_0"), m.Origin("<t>", 1, 1))
    assert resolve_style({"Elevation": zero}, lk)["Shadows"] == m.Shadows(())


def test_a_percentage_still_scales_the_maximum() -> None:
    lk = look()
    out = resolve_style({"Elevation": m.Percent(50)}, lk)
    (shadow,) = out["Shadows"].items  # type: ignore[union-attr]
    assert shadow.y == 8 and shadow.blur == 24  # half of the maximum, 16 and 48


def test_a_word_that_is_no_level_is_refused_and_a_missing_token_is_reported() -> None:
    with pytest.raises(Exception, match="LEVEL_0 to LEVEL_5"):
        coerce("elevation", tess_dl.Word("LEVEL_9"), m.Origin("<t>", 1, 1))
    lk = look()
    bare = lk.__class__(lk.theme, lk.sheets, lk.appearance, {}, (), None, None)
    errors: list[m.BindError] = []
    out = resolve_style({"Elevation": m.Enum("LEVEL_2")}, bare, errors)
    assert "Shadows" not in out and "LEVEL_2" in errors[0].message
