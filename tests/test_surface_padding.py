"""``Padding`` of a Bar and a Panel (TSH-055, AC-PNL-4): space between the surface's content and
its sides, applied to the body the content sits in."""

from __future__ import annotations

from tess_shell.schema.model import BarDef, PanelDef
from tess_shell.surfaces.manager import _body_extra
from tests.test_focus import bar, read

PANEL = (
    "Panel { Name: P, Anchor: [TOP, LEFT], Width: 200, Height: 100, %s Children { FlexBox { } } }"
)


def surface(source: str) -> BarDef | PanelDef:
    shell, findings = read(source)
    assert shell is not None and findings == [], findings
    return shell.monitors[0].surfaces[0]  # type: ignore[return-value]


def test_a_bar_with_padding_sets_it_on_the_body_and_one_without_sets_nothing() -> None:
    padded = surface(bar("FlexBox { }", keys="Padding: [4, 2, 6, 8],"))
    assert _body_extra(padded, None) == {
        "padding_left": 4,
        "padding_top": 2,
        "padding_right": 6,
        "padding_bottom": 8,
    }
    assert _body_extra(surface(bar("FlexBox { }")), None) == {}


def test_a_single_number_pads_every_side_of_a_panel() -> None:
    extra = _body_extra(surface(PANEL % "Padding: 12,"), None)
    assert [extra[f"padding_{s}"] for s in ("left", "top", "right", "bottom")] == [12] * 4


def test_padding_on_a_melded_panel_is_refused_not_ignored() -> None:
    shell, findings = read(
        "Frame { Name: F, Thickness: 20 } "
        "Panel { Name: P, Meld: true, Attach_To: F, Attach: TOP, Alignment: START, Length: 80, "
        "Depth: 40, Padding: 4, Children { FlexBox { } } }"
    )
    assert any("Padding" in f.message for f in findings), findings
