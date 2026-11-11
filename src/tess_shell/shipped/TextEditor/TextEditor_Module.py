"""The TextEditor module (Standard Modules > TextEditor) has no Python of its own beyond checking
a call: its layout is a multi-line TextField and the events of a call are raised by that
TextField."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tess_shell import Module

if TYPE_CHECKING:
    from tess_shell.modules.context import UseRecord


class TextEditor(Module):
    def validate_use(self, use: UseRecord) -> None:
        wrap = use.params.get("Wrap")
        if wrap == "CHAR":
            raise ValueError("Wrap: CHAR is not built (character wrapping comes later)")
        if wrap not in ("WORD", "NONE"):
            raise ValueError(f"Wrap is WORD or NONE, not {wrap!r}")
        lines = use.params.get("Lines")
        if isinstance(lines, bool) or not isinstance(lines, int) or lines < 1:
            raise ValueError(f"Lines is a whole number, 1 or more, not {lines!r}")
        limit = use.params.get("Max_Length")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError(f"Max_Length is a whole number, 0 or more, not {limit!r}")
