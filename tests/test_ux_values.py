"""Values the UX specification fixes and the shipped files must carry (the b3 adoption batch)."""

from __future__ import annotations

import re
from importlib import resources
from typing import Any

SHIPPED = resources.files("tess_shell") / "shipped"


def default_stylesheet() -> str:
    return (SHIPPED / "Stylesheets" / "Default_Stylesheet.tdl").read_text(encoding="utf-8")


def test_every_disabled_rule_of_the_default_stylesheet_sets_opacity_038() -> None:
    rules = re.findall(
        r'Selector: "([^"]*:disabled)"([^}]*)\}', default_stylesheet()
    )
    seen = [(sel, re.search(r"Opacity: ([0-9.]+)", body)) for sel, body in rules]
    opacities = {sel: float(found.group(1)) for sel, found in seen if found}
    assert len(opacities) >= 10
    assert set(opacities.values()) == {0.38}, opacities


def test_badge_is_a_6_dp_dot_and_a_16_dp_pill_with_the_caption_size() -> None:
    from tests.test_display_widgets import running

    with running("Badge { Count: 7 } Badge { Dot: true }") as w:
        pill, dot = w.of_use("Badge", "Root", 0), w.of_use("Badge", "Root", 1)
        assert (dot.get("width"), dot.get("height")) == (6, 6)
        assert pill.get("height") == 16 and pill.get("min_width") == 16
        assert w.of_use("Badge", "Digits", 0).get("font_size") == 12


def test_a_label_ends_an_overlong_text_with_an_ellipsis_by_default() -> None:
    from tests.test_display_widgets import running

    with running('Label { Text: "Hello", Width: 80 }') as w:
        assert w.of_use("Label", "#0").get("overflow") == "ellipsis"


def test_the_network_name_text_is_bounded_and_ends_with_an_ellipsis() -> None:
    style = (SHIPPED / "Network" / "Network_Style.tdl").read_text(encoding="utf-8")
    body = style.split("network_text {", 1)[1].split("}", 1)[0]
    assert "Overflow: ELLIPSIS" in body
    module = (SHIPPED / "Network" / "Network_Module.tdl").read_text(encoding="utf-8")
    assert module.count("Class: network_text") == module.count("Max_Width: 160") == 3


def _linear(v: float) -> float:
    v /= 255
    return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4


def _luminance(hex_colour: str) -> float:
    r, g, b = (int(hex_colour[i : i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * _linear(r) + 0.7152 * _linear(g) + 0.0722 * _linear(b)


def _ratio(a: str, b: str) -> float:
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_the_launcher_hover_fill_differs_from_the_card_and_keeps_the_text_readable() -> None:
    import tess_dl

    from tess_shell.appearance import Appearance
    from tess_shell.schema.look import effective_tokens, read_theme

    hovered = re.search(
        r'Selector: "\.list_item:hovered", Background: \$color\.(\w+)', default_stylesheet()
    )
    assert hovered
    text = (SHIPPED / "Themes" / "Default_Theme.tdl").read_text(encoding="utf-8")
    parsed = tess_dl.parse(text, path="Default_Theme.tdl")
    assert parsed.document is not None
    theme, _ = read_theme(parsed.document, "Default_Theme.tdl")
    assert theme is not None
    for scheme in ("dark", "light"):
        tokens = effective_tokens(theme, Appearance(scheme=scheme))

        def colour(name: str, tokens: dict[str, Any] = tokens) -> str:
            return str(tokens[f"color.{name}"].value.value).upper()

        fill, card = colour(hovered.group(1)), colour("surface_raised")  # the Launcher card fill
        assert fill != card, scheme
        assert _ratio(fill, card) >= 2.0, scheme  # the hover is seen
        assert _ratio(colour("on_surface"), fill) >= 4.5, scheme


def test_the_emphasized_easing_is_the_curve_the_motion_spec_gives() -> None:
    from tess_shell.binder.motion import EASINGS

    assert EASINGS["EMPHASIZED"] == (0.2, 0.0, 0.0, 1.0)


def test_the_shadow_fallback_matches_the_themes_elevation_max() -> None:
    from tess_shell.binder.shadow import DEFAULT_MAX

    theme = (SHIPPED / "Themes" / "Default_Theme.tdl").read_text(encoding="utf-8")
    written = re.search(r'Shadow \{ Color: "#([0-9A-Fa-f]{8})"', theme)
    assert written
    assert DEFAULT_MAX.items[0].color.a == int(written.group(1)[6:], 16) == 0x66


def test_the_themes_reduced_motion_block_carries_the_zero_durations() -> None:
    assert re.search(
        r"Reduced_Motion \{\s*Motion \{ Duration \{ Short: 0, Medium: 0, Long: 0 \} \}\s*\}",
        (SHIPPED / "Themes" / "Default_Theme.tdl").read_text(encoding="utf-8"),
    )


def test_the_shape_scale_has_the_seven_steps_of_the_spec() -> None:
    import tess_dl

    from tess_shell.appearance import Appearance
    from tess_shell.schema.look import effective_tokens, read_theme

    text = (SHIPPED / "Themes" / "Default_Theme.tdl").read_text(encoding="utf-8")
    parsed = tess_dl.parse(text, path="Default_Theme.tdl")
    assert parsed.document is not None
    theme, findings = read_theme(parsed.document, "Default_Theme.tdl")
    assert theme is not None and findings == []
    tokens = effective_tokens(theme, Appearance())
    radii = {
        path.split(".", 1)[1]: token.value.value  # type: ignore[attr-defined]
        for path, token in tokens.items()
        if path.startswith("shape.")
    }
    assert radii == {
        "none": 0,
        "small": 4,
        "medium": 8,
        "medium_large": 12,
        "large": 16,
        "extra_large": 28,
        "full": 999,
    }
