"""Contrast of the shipped look, computed from the theme's tokens (WCAG 2.x relative luminance), in
the Dark and the Light mode. Each case is a pair a user reads: text 4.5 to 1, a pictogram 3 to 1."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from tess_shell.appearance import Appearance
from tess_shell.binder.model import TokenRef
from tess_shell.config.settings import load_settings
from tess_shell.model.look import Look
from tess_shell.scanner import build_look, scan
from tests.shell_samples import write_example

TEXT, ICON = 4.5, 3.0


def luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def look_of(scheme: str) -> Look:
    folder = Path(tempfile.mkdtemp())
    write_example(folder)
    settings, _ = load_settings(folder)
    assert settings is not None
    return build_look(scan(settings, folder), settings, Appearance(scheme=scheme))  # type: ignore[arg-type]


def colour(look: Look, value: object) -> str:
    assert isinstance(value, TokenRef), value
    return str(look.tokens[value.path].value.value)  # type: ignore[union-attr]


def rule(look: Look, target: str, part: str, state: str) -> dict[str, object]:
    found = [
        r
        for r in look.rules
        if r.kind == "module" and r.target == target and r.part == part and r.state == state
    ]
    assert found, f"no rule {target}::{part}:{state}"
    return dict(found[-1].values)


@pytest.mark.parametrize("scheme", ["dark", "light"])
@pytest.mark.parametrize(("part", "need"), [("label", TEXT), ("shortcut", TEXT), ("icon", ICON)])
def test_the_pressed_menu_row_reads_on_its_fill(scheme: str, part: str, need: float) -> None:
    """TSH-040: the pressed row (a Menu, the tray menu) is filled with ``primary``; its text, its
    shortcut and its icon must read on it (on_surface on primary was 2.58 and 2.89 to 1)."""
    look = look_of(scheme)
    fill = colour(look, rule(look, "MenuItem", "", "pressed")["Background"])
    ink = colour(look, rule(look, "MenuItem", part, "pressed")["Foreground"])
    assert ratio(ink, fill) >= need, (scheme, part, ink, fill, ratio(ink, fill))
