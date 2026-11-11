"""The Icon module (Standard Modules > Icon): a layout and the check of its size."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tess_shell import Module

if TYPE_CHECKING:
    from tess_shell.modules.context import UseRecord


class Icon(Module):
    def validate_use(self, use: UseRecord) -> None:
        size = use.params["Size"]
        if size <= 0 or int(size) != size:
            raise ValueError(f"Size is a whole number of pixels above 0, not {size!r}")
