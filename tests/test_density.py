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
