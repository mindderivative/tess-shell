"""The engine's baseline colours follow the shell's look (tre 0.6.11 scheme): an unstyled text takes
the theme's ``on_surface`` and the window the desktop's light or dark."""

from __future__ import annotations

import pytest

from tess_shell.appearance import Appearance
from tests.test_panel import manager, surface


@pytest.mark.parametrize(("scheme", "resolved"), [("light", "light"), ("dark", "dark")])
def test_a_surface_takes_the_looks_scheme_and_the_themes_roles(scheme: str, resolved: str) -> None:
    m = manager(hide_mode="KEEP", appearance=Appearance(scheme=scheme))  # type: ignore[arg-type]
    window = surface(m, "Top_Bar").window
    assert window is not None
    assert window.get("scheme") == resolved
    roles = window.get("scheme_colors")
    tokens = m.look.tokens
    checked = 0
    for token, role in m.BASELINE.items():
        if token not in tokens:
            continue  # the test theme names fewer roles than the shipped one
        checked += 1
        found = tokens[token].value.text.strip('"#')  # type: ignore[union-attr]
        rgb = tuple(int(found[i : i + 2], 16) for i in (0, 2, 4))
        assert tuple(roles[role][:3]) == rgb, (token, role)
    assert checked >= 3


def test_no_preference_is_the_themes_default_variant_which_is_dark() -> None:
    window = surface(manager(hide_mode="KEEP"), "Top_Bar").window
    assert window is not None and window.get("scheme_resolved") == "dark"


def test_a_change_of_the_desktops_scheme_reaches_the_windows_that_are_open() -> None:
    m = manager(hide_mode="KEEP", appearance=Appearance(scheme="dark"))
    window = surface(m, "Top_Bar").window
    assert window is not None
    dark_on_surface = window.get("scheme_colors")["on_surface"]
    m.set_look(m.look.with_appearance(Appearance(scheme="light")))
    assert window.get("scheme_resolved") == "light"
    assert window.get("scheme_colors")["on_surface"] != dark_on_surface


def test_every_window_ignores_a_press_that_moves_less_than_4_px() -> None:
    """tre 0.6.12 ``drag_start_px``: a click with a little pointer jitter is a click, not the start
    of a drag (a peek drag, a scrollbar thumb, a movable Panel)."""
    m = manager()
    assert surface(m, "Top_Bar").window.get("drag_start_px") == 4
