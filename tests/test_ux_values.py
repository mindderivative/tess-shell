"""Values the UX specification fixes and the shipped files must carry (the b3 adoption batch)."""

from __future__ import annotations

import re
from importlib import resources

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
