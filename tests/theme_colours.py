"""The colours of the shipped Default theme, read from the theme file, so a test that wants "the
outline colour" does not pin a literal that the next colour decision changes."""

from __future__ import annotations

import re
from pathlib import Path

THEME_FILE = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "tess_shell"
    / "shipped"
    / "Themes"
    / "Default_Theme.tdl"
)


def base(role: str) -> tuple[int, int, int, int]:
    """``role`` (``Outline``, ``Surface_Raised``...) of the base values, which are the Dark look,
    as the ``(r, g, b, a)`` tre holds."""
    text = THEME_FILE.read_text(encoding="utf-8")
    found = re.search(rf'^\s*{role}:\s*"#([0-9A-Fa-f]{{6}})"', text, re.M)
    assert found is not None, role
    h = found.group(1)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)
