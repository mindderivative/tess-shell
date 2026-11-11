"""The Slider module (Standard Modules > Slider): a layout and the check of its range. The value
and the drag are the binder's (``binder.controls``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tess_shell import Module

if TYPE_CHECKING:
    from tess_shell.modules.context import UseRecord

ORIENTATIONS = ("HORIZONTAL", "VERTICAL")


class Slider(Module):
    def validate_use(self, use: UseRecord) -> None:
        p = use.params
        if p["Orientation"] not in ORIENTATIONS:
            raise ValueError(f"Orientation is HORIZONTAL or VERTICAL, not {p['Orientation']!r}")
        if p["Max"] <= p["Min"]:
            raise ValueError(f"Max ({p['Max']}) must be above Min ({p['Min']})")
        if p["Step"] <= 0:
            raise ValueError(f"Step must be above 0, not {p['Step']!r}")
