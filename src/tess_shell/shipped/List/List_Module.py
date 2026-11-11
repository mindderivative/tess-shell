"""The List module (Standard Modules > List): a layout and the check of its choice of selection.
The chosen entry is the binder's (``binder.controls``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tess_shell import Module

if TYPE_CHECKING:
    from tess_shell.modules.context import UseRecord

SELECTIONS = ("NONE", "SINGLE")


class List(Module):
    def validate_use(self, use: UseRecord) -> None:
        if use.params["Selection"] not in SELECTIONS:
            raise ValueError(
                f"Selection is NONE or SINGLE (MULTIPLE is not in v1), not "
                f"{use.params['Selection']!r}"
            )
