"""Icon sets: Iconify-style JSON files found in the ``Icons`` folders (Block Reference > Icons).

A file holds ``prefix``, ``icons`` (name to ``{"body": ...}``) and optionally ``width`` and
``height`` (24). A name may carry its set's prefix, ``mdi:account``, which selects that set; a name
with no prefix is looked up in ``mdi`` first, then in the other sets in file order. A name may end
in ``+dot`` (``mdi:battery-10+dot``): the icon with a dot of the same colour drawn to its right,
inside the same document (the document is half an icon's height wider; shown at the icon's height
the dot is 3/8 of it across). A status dot that is part of the icon needs no second node. A file
is read the first time a lookup needs it, and an unreadable one is reported once and skipped.
"""

from __future__ import annotations

import difflib
import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SVG_NAMESPACE = "http://www.w3.org/2000/svg"
DOT_SUFFIX = "+dot"


@dataclass(slots=True)
class _Set:
    path: Path
    prefix: str = ""
    icons: dict[str, Any] = field(default_factory=dict)
    width: int = 24
    height: int = 24
    loaded: bool = False
    ok: bool = True


def _num(x: float) -> str:
    return f"{x:g}"


def document(body: str, width: int, height: int) -> str:
    """An SVG document around an icon's body; the body draws with ``currentColor``."""
    return (
        f'<svg xmlns="{SVG_NAMESPACE}" viewBox="0 0 {width} {height}" '
        f'width="{width}" height="{height}">{body}</svg>'
    )


class IconSets:
    def __init__(self, directories: Sequence[Path]) -> None:
        self._sets: list[_Set] = []
        for directory in directories:
            if directory.is_dir():
                self._sets.extend(_Set(p) for p in sorted(directory.glob("*.json")))
        self.problems: list[str] = []

    def _load(self, s: _Set) -> _Set:
        if s.loaded:
            return s
        s.loaded = True
        try:
            data = json.loads(s.path.read_text(encoding="utf-8"))
            icons = data["icons"]
            if not isinstance(icons, dict):
                raise ValueError("'icons' is not an object")
            s.prefix = str(data.get("prefix", s.path.stem))
            s.icons = icons
            s.width = int(data.get("width", 24))
            s.height = int(data.get("height", 24))
        except (OSError, ValueError, KeyError, TypeError) as exc:
            s.ok = False
            self.problems.append(f"icon set {s.path} cannot be read: {exc}")
        return s

    def _candidates(self, prefix: str | None) -> list[_Set]:
        loaded = [self._load(s) for s in self._sets]
        good = [s for s in loaded if s.ok]
        if prefix is not None:
            return [s for s in good if s.prefix == prefix]
        return sorted(good, key=lambda s: s.prefix != "mdi")  # mdi first, the rest in file order

    def lookup(self, name: str) -> str | None:
        """The SVG document of ``name`` (``mdi:account`` or ``account``), or ``None``."""
        dot = name.endswith(DOT_SUFFIX)
        prefix, _, bare = name.removesuffix(DOT_SUFFIX).rpartition(":")
        for s in self._candidates(prefix or None):
            icon = s.icons.get(bare)
            if isinstance(icon, dict) and isinstance(icon.get("body"), str):
                width, height = int(icon.get("width", s.width)), int(icon.get("height", s.height))
                if not dot:
                    return document(icon["body"], width, height)
                # the dot: 3/8 of the height across, its centre 1/4 of the height right of the icon
                r, cx = height * 3 / 16, width + height / 4
                circle = (
                    f'<circle cx="{_num(cx)}" cy="{_num(height / 2)}" r="{_num(r)}" '
                    'fill="currentColor"/>'
                )
                return document(icon["body"] + circle, width + height // 2, height)
        return None

    def names(self) -> list[str]:
        out: list[str] = []
        for s in self._candidates(None):
            out.extend(s.icons)
        return out

    def nearest(self, name: str) -> list[str]:
        bare = name.removesuffix(DOT_SUFFIX).rpartition(":")[2]
        return difflib.get_close_matches(bare, self.names(), n=3, cutoff=0.7)
