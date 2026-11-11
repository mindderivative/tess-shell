"""The Marquee text module (Standard Modules > Marquee text): a layout and the check of its keys."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tess_shell import Module

if TYPE_CHECKING:
    from tess_shell.modules.context import UseRecord


class Marquee_Text(Module):  # noqa: N801 - the module's call name is Marquee_Text
    def validate_use(self, use: UseRecord) -> None:
        if use.params["Speed"] <= 0:
            raise ValueError(f"Speed is pixels a second, above 0, not {use.params['Speed']!r}")
        if use.params["Pause"] < 0:
            raise ValueError(f"Pause is milliseconds, 0 or more, not {use.params['Pause']!r}")
        if use.params["Direction"] not in ("LEFT", "RIGHT"):
            raise ValueError(f"Direction is LEFT or RIGHT, not {use.params['Direction']!r}")
        if use.params["Loop"] not in ("RESTART", "BOUNCE"):
            raise ValueError(f"Loop is RESTART or BOUNCE, not {use.params['Loop']!r}")
