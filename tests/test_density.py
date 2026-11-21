"""The density levels (Spacing and Density, ADR-0002): ``Appearance.Density`` in settings.tdl, a
surface's own ``Density``, the ``density.*`` tokens and what the standard modules read from them."""

from __future__ import annotations

import pytest

from tess_shell.appearance import Appearance
from tests.widgets_live import running

LEVELS = (("default", 40, 40, 40), ("compact", 32, 32, 32), ("dense", 28, 24, 28))


@pytest.mark.parametrize(("level", "control", "row", "menu"), LEVELS)
def test_a_button_a_toggle_a_checkbox_and_a_menu_item_take_the_height_of_the_level(
    level: str, control: int, row: int, menu: int
) -> None:
    body = 'Button { Text: "Go" } Toggle { } Checkbox { Text: "x" } MenuItem { Text: "Open" }'
    with running(body, appearance=Appearance(density=level)) as w:  # type: ignore[arg-type]
        assert w.warnings() == []
        assert w.of_use("Button", "Root").get("height") == control
        assert w.of_use("Toggle", "Root").get("height") == control
        assert w.of_use("Checkbox", "Root").get("height") == control
        assert w.of_use("MenuItem", "Root").get("height") == menu


def test_the_toggle_keeps_its_painted_track_centred_in_the_taller_row() -> None:
    with running("Toggle { }", appearance=Appearance(density="default")) as w:
        track, thumb = w.of_use("Toggle", "Track"), w.of_use("Toggle", "Thumb")
        assert track.get("height") == 22 and track.get("top") == (40 - 22) // 2
        assert thumb.get("top") == (40 - 22) // 2


def test_compact_is_the_default_level() -> None:
    assert Appearance().density == "compact"


SHELL = """
Shell { Monitor { Name: Main, Index: 0, Children {
    Bar { Name: Top_Bar, Edge: TOP, Width: EXPAND, Height: 40, Children {
        Button { Text: "Shell" } } }
    Bar { Name: Side, Edge: LEFT, Width: 60, Height: EXPAND, Density: DENSE, Children {
        Button { Text: "Own" } } }
} } }
"""


def test_a_surface_with_its_own_density_reads_that_level_and_the_others_the_shell_s() -> None:
    with running("", body=SHELL, appearance=Appearance(density="default")) as w:
        heights = sorted(w.view.nodes[k].get("height") for k in w.view.nodes if k.endswith("/Root"))
        assert heights == [40]  # the Top_Bar's Button, at the shell's DEFAULT level
        # the Side Bar's view is another one; its Button reads DENSE
        side = next(s for s in w.manager.surfaces if s.name == "Side")
        assert side.view is not None
        own = [n.get("height") for k, n in side.view.nodes.items() if k.endswith("/Root")]
        assert own == [28]


FIELD_SHELL = (
    "Shell { Monitor { Name: Main, Index: 0, Children { Bar { Name: Top_Bar, Edge: TOP, "
    "Width: EXPAND, Height: 120, Children { FlexBox { Align_Items: START, Children { "
    "TextField { Name: F, Width: 200 } } } } } } } }"
)


@pytest.mark.parametrize(("level", "height", "side"), [("default", 40, 12), ("compact", 32, 8)])
def test_a_text_field_is_as_high_as_the_level_and_takes_its_padding_from_the_token(
    level: str, height: int, side: int
) -> None:
    with running("", body=FIELD_SHELL, appearance=Appearance(density=level)) as w:  # type: ignore[arg-type]
        field = next(n for k, n in w.view.nodes.items() if k.endswith("F"))
        assert field.get("layout_height") == height
        padding = field.get("padding")  # a number when the four sides are equal
        assert (padding if isinstance(padding, float) else padding[0]) == side


def test_a_dense_field_is_28_high_and_a_field_written_with_a_padding_keeps_it() -> None:
    with running("", body=FIELD_SHELL, appearance=Appearance(density="dense")) as w:
        field = next(n for k, n in w.view.nodes.items() if k.endswith("F"))
        assert field.get("layout_height") == 28
    own = FIELD_SHELL.replace("Width: 200", "Width: 200, Padding: 3")
    with running("", body=own, appearance=Appearance(density="default")) as w:
        field = next(n for k, n in w.view.nodes.items() if k.endswith("F"))
        assert field.get("padding") == 3
