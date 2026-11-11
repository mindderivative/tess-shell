"""The TextInput module (Standard Modules > TextInput) has no Python of its own beyond checking a
call: its layout is a TextField and the events of a call are raised by that TextField."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tess_shell import Module

if TYPE_CHECKING:
    from tess_shell.modules.context import UseRecord


class TextInput(Module):
    def validate_use(self, use: UseRecord) -> None:
        limit = use.params.get("Max_Length")
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 0:
            raise ValueError(f"Max_Length is a whole number, 0 or more, not {limit!r}")
