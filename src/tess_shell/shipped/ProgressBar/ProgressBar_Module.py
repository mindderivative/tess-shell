"""The ProgressBar module (Standard Modules > ProgressBar): a layout and the check of its range."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tess_shell import Module

if TYPE_CHECKING:
    from tess_shell.modules.context import UseRecord


class ProgressBar(Module):
    def validate_use(self, use: UseRecord) -> None:
        low, high = use.params["Min"], use.params["Max"]
        if high <= low:
            raise ValueError(f"Max ({high}) must be above Min ({low})")
