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
