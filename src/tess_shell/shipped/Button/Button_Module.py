"""The Button module (Standard Modules > Button): a layout and the check of its choices."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tess_shell import Module

if TYPE_CHECKING:
    from tess_shell.modules.context import UseRecord

POSITIONS = ("START", "END")


class Button(Module):
    def validate_use(self, use: UseRecord) -> None:
        if use.params["Icon_Position"] not in POSITIONS:
            raise ValueError(f"Icon_Position is START or END, not {use.params['Icon_Position']!r}")
        if use.params["Icon"] and not use.params["Text"] and not use.params["Label"]:
            self.ctx.log.warning(
                f"{use.name}: a Button with only an icon needs a Label, so assistive technology "
                "can name it"
            )
