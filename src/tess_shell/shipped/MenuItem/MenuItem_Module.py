"""The MenuItem module (Standard Modules > Menu and MenuItem): a layout and the check of its
choices. The submenu and the closing of the menu are the Popup's (``surfaces.popup``)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tess_shell import Module

if TYPE_CHECKING:
    from tess_shell.modules.context import UseRecord


class MenuItem(Module):
    def validate_use(self, use: UseRecord) -> None:
        p = use.params
        if p["Separator"] and (p["Text"] or p["Icon"] or p["Submenu"]):
            raise ValueError("a Separator is a rule: it has no Text, Icon or Submenu")
        if p["Icon"] and not p["Text"] and not p["Label"] and not p["Separator"]:
            self.ctx.log.warning(f"{use.name}: a MenuItem with only an icon needs a Label")
