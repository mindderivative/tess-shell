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


def test_no_shipped_text_or_fill_is_a_literal_colour() -> None:
    """TSH-041: a literal ``#ffffff`` Clock face was 1.08 to 1 on the Light surface. Shipped style
    and layout files take their colours from the theme's tokens (a fully transparent fill is not a
    colour a user sees)."""
    import re

    root = Path(__file__).resolve().parent.parent / "src" / "tess_shell" / "shipped"
    pattern = re.compile(
        r'(Foreground|Background|Fill|Border_Color|Color):\s*"#([0-9A-Fa-f]{6,8})"'
    )
    found = []
    for path in sorted(root.rglob("*.tdl")):
        if path.name.endswith("_Theme.tdl"):
            continue  # a theme is where the literals live
        for number, line in enumerate(path.read_text().splitlines(), start=1):
            hit = pattern.search(line)
            if hit and hit.group(2).lower() not in ("00000000",):
                found.append(f"{path.relative_to(root)}:{number}: {line.strip()}")
    assert not found, "literal colours (use a $color token): " + "; ".join(found)


@pytest.mark.parametrize("scheme", ["dark", "light"])
def test_the_clock_face_reads_on_the_surface(scheme: str) -> None:
    """The Clock's text takes ``on_surface``, which reads on the surface of both modes."""
    look = look_of(scheme)
    style = (
        Path(__file__).resolve().parent.parent / "src/tess_shell/shipped/Clock/Clock_Style.tdl"
    ).read_text()
    assert "Foreground: $color.on_surface" in style
    on = str(look.tokens["color.on_surface"].value.value)  # type: ignore[union-attr]
    surface = str(look.tokens["color.surface"].value.value)  # type: ignore[union-attr]
    assert ratio(on, surface) >= TEXT, (scheme, on, surface)


# -- every role pair of the theme, in every mode (TSH-042, AC-COL-3, AC-COL-4) ---------------

# (foreground role, background role, what it needs): text 4.5 to 1; a pictogram, a border or a
# fill that carries meaning 3 to 1
PAIRS = [
    ("inverse_on_surface", "inverse_surface", TEXT),
    ("on_surface", "surface", TEXT),
    ("on_surface", "surface_raised", TEXT),
    ("on_surface_muted", "surface", TEXT),
    ("on_surface_muted", "surface_raised", TEXT),
    ("on_primary", "primary", TEXT),
    ("error", "surface", TEXT),
    ("warning", "surface", TEXT),
    ("success", "surface", TEXT),
    ("primary", "surface", ICON),
    ("primary", "surface_raised", ICON),
    ("outline", "surface", ICON),
    ("outline", "surface_raised", ICON),
    ("accent", "surface", ICON),
    ("accent", "surface_raised", ICON),
]
MODES = {
    "dark": ("dark", False),
    "light": ("light", False),
    "high_contrast": ("dark", True),
    "high_contrast_light": ("light", True),
}
# Known violations, with the ratio measured when they were recorded: the test fails when one is
# fixed (or changes) so that the list is kept true. The spec or the theme changes, not the test.
KNOWN: dict[tuple[str, str, str], float] = {}
# (the Dark ``outline`` #5F7188 and the High_Contrast block's own error, warning and success
# colours settled the three violations recorded in TSH-042: ADR-0025)
ACCENT_AS_TEXT = {  # the accent is never text (Colour Roles rule 12): below 4.5 by design
    ("dark", "surface"): 4.38,
    ("dark", "surface_raised"): 3.90,
    ("light", "surface"): 3.82,
    ("light", "surface_raised"): 4.11,
}


def mode_look(mode: str) -> Look:
    scheme, high = MODES[mode]
    folder = Path(tempfile.mkdtemp())
    write_example(folder)
    settings, _ = load_settings(folder)
    assert settings is not None
    appearance = Appearance(scheme=scheme, high_contrast=high)  # type: ignore[arg-type]
    return build_look(scan(settings, folder), settings, appearance)


@pytest.mark.parametrize("mode", sorted(MODES))
def test_every_role_pair_meets_its_ratio_except_the_recorded_violations(mode: str) -> None:
    look = mode_look(mode)
    failing: dict[tuple[str, str, str], float] = {}
    for fg, bg, need in PAIRS:
        got = ratio(
            str(look.tokens[f"color.{fg}"].value.value), str(look.tokens[f"color.{bg}"].value.value)
        )  # type: ignore[union-attr]
        if got < need:
            failing[(mode, fg, bg)] = round(got, 2)
    expected = {k: v for k, v in KNOWN.items() if k[0] == mode}
    assert failing == expected, f"violations changed in {mode}: {failing} (recorded {expected})"


@pytest.mark.parametrize(("mode", "background"), sorted(ACCENT_AS_TEXT))
def test_the_accent_as_text_is_below_4_5_and_nothing_shipped_uses_it_as_text(
    mode: str, background: str
) -> None:
    look = mode_look(mode)
    got = ratio(
        str(look.tokens["color.accent"].value.value),  # type: ignore[union-attr]
        str(look.tokens[f"color.{background}"].value.value),  # type: ignore[union-attr]
    )
    assert round(got, 2) == ACCENT_AS_TEXT[(mode, background)] and got < TEXT
    root = Path(__file__).resolve().parent.parent / "src" / "tess_shell" / "shipped"
    users = [
        p.name
        for p in sorted(root.rglob("*.tdl"))
        if "Foreground: $color.accent" in p.read_text() and not p.name.endswith("_Theme.tdl")
    ]
    assert users == [], f"the accent is used as text in {users}"
