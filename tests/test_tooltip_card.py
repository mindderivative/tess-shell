"""One tooltip card (Tooltip, TSH-004): an inline ``Tooltip { }`` and ``Tooltip: "text"`` start from
the plain tooltip's look, read from tokens; the shipped modules carry no card of their own."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tess_shell.binder import model as m
from tests.test_contrast import look_of, ratio
from tests.test_focus import bar, read

SHIPPED = Path(__file__).resolve().parent.parent / "src" / "tess_shell" / "shipped"


def tooltip_of(snippet: str) -> m.TooltipRef:
    shell, findings = read(bar(snippet))
    assert shell is not None, findings
    (block,) = shell.monitors[0].surfaces[0].children  # type: ignore[union-attr]
    assert isinstance(block, m.Node) and block.tooltip is not None
    return block.tooltip


def style_of(tip: m.TooltipRef) -> dict[str, m.Value]:
    assert tip.popup is not None
    return dict(tip.popup.style)


def test_an_inline_tooltip_has_the_plain_card_from_tokens_and_no_shadow() -> None:
    style = style_of(tooltip_of("FlexBox { Tooltip { Children { FlexBox { } } } }"))
    assert isinstance(style["Background"], m.TokenRef)
    assert style["Background"].path == "color.inverse_surface"
    assert isinstance(style["Corner_Radius"], m.TokenRef)
    assert style["Corner_Radius"].path == "shape.small"
    assert "Elevation" not in style and "Shadows" not in style


def test_a_key_the_author_writes_in_the_tooltips_style_replaces_the_cards() -> None:
    tip = tooltip_of(
        "FlexBox { Tooltip { Style { Corner_Radius: 12 }, Children { FlexBox { } } } }"
    )
    style = style_of(tip)
    assert not isinstance(style["Corner_Radius"], m.TokenRef)  # the author's 12 stays
    assert style["Background"].path == "color.inverse_surface"  # type: ignore[union-attr]


def test_the_text_form_is_the_same_card_with_8_by_4_padding_and_the_inverse_ink() -> None:
    tip = tooltip_of('FlexBox { Tooltip: "Save" }')
    style = style_of(tip)
    assert style["Background"].path == "color.inverse_surface"  # type: ignore[union-attr]
    assert tip.popup is not None
    (body,) = tip.popup.children
    assert isinstance(body, m.Node)
    padding = body.props["Padding"]
    assert (padding.left, padding.top, padding.right, padding.bottom) == (8, 4, 8, 4)  # type: ignore[attr-defined]
    (label,) = body.children
    assert (
        isinstance(label, m.Node) and label.style["Foreground"].path == "color.inverse_on_surface"
    )  # type: ignore[union-attr]


def test_no_shipped_module_carries_a_card_of_its_own() -> None:
    """The six literal cards (a fill, a radius 8, a 20 percent shadow) are gone."""
    offenders = []
    for path in sorted(SHIPPED.glob("*/*_Module.tdl")):
        text = path.read_text(encoding="utf-8")
        for found in re.finditer(r"Tooltip \{(.*?)\n\s*Children \{", text, re.S):
            if re.search(r"Background|Corner_Radius|Elevation", found.group(1)):
                offenders.append(path.name)
    assert offenders == [], offenders


@pytest.mark.parametrize("scheme", ["dark", "light"])
def test_the_inverse_ink_reads_on_the_inverse_surface(scheme: str) -> None:
    look = look_of(scheme)
    ink = str(look.tokens["color.inverse_on_surface"].value.value)  # type: ignore[union-attr]
    fill = str(look.tokens["color.inverse_surface"].value.value)  # type: ignore[union-attr]
    assert ratio(ink, fill) >= 4.5
