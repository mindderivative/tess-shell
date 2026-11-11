"""The Expander module (Standard Modules > Expander): a layout and the check of its choices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tess_shell import Module

if TYPE_CHECKING:
    from tess_shell.modules.context import UseRecord

DIRECTIONS = ("DOWN", "UP", "LEFT", "RIGHT")


class Expander(Module):
    def validate_use(self, use: UseRecord) -> None:
        if use.params["Direction"] not in DIRECTIONS:
            raise ValueError(
                f"Direction is one of {', '.join(DIRECTIONS)}, not {use.params['Direction']!r}"
            )
