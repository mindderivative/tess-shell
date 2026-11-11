"""The TextBox module (Standard Modules > TextBox): a layout and the check of its two choices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tess_shell import Module

if TYPE_CHECKING:
    from tess_shell.modules.context import UseRecord


class TextBox(Module):
    def validate_use(self, use: UseRecord) -> None:
        if use.params["Wrap"] not in ("WORD", "NONE"):
            raise ValueError(f"Wrap is WORD or NONE, not {use.params['Wrap']!r}")
        lines = use.params["Max_Lines"]
        if isinstance(lines, bool) or not isinstance(lines, int) or lines < 0:
            raise ValueError(f"Max_Lines is a whole number, 0 or more, not {lines!r}")
