"""The Image module (Standard Modules > Image): a layout and the check of its Fit."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tess_shell import Module

if TYPE_CHECKING:
    from tess_shell.modules.context import UseRecord

FITS = ("CONTAIN", "COVER", "FILL", "NONE")


class Image(Module):
    def validate_use(self, use: UseRecord) -> None:
        if use.params["Fit"] not in FITS:
            raise ValueError(f"Fit is one of {', '.join(FITS)}, not {use.params['Fit']!r}")
