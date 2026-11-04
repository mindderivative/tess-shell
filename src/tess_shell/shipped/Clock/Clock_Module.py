"""The Clock: the time as a string, once a minute, or once a second when a format shows seconds
(Clock Module). One instance serves every use; each use has its own format and zone."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tess_shell import Module

if TYPE_CHECKING:
    from tess_shell.modules.context import UseRecord

FALLBACK = "--:--"


def pattern(params: Mapping[str, Any]) -> str:
    """The strftime pattern of a use: its ``format``, else one chosen by ``hour_cycle``.

    ``desktop`` follows 24 hours until KDE's regional setting is read (Clock Module, open)."""
    if params["format"]:
        return str(params["format"])
    return "%I:%M %p" if params["hour_cycle"] == "12" else "%H:%M"


def render(params: Mapping[str, Any], now: datetime) -> str:
    zone = ZoneInfo(params["timezone"]) if params["timezone"] else None
    return now.astimezone(zone).strftime(pattern(params))


class Clock(Module):
    def start(self) -> None:
        self.tick()
        self.ctx.on_tick("minute", self.tick)
        if any("%S" in pattern(u.params) for u in self.ctx.uses.values()):
            self.ctx.on_tick("second", self.tick_seconds)

    def validate_use(self, use: UseRecord) -> None:
        if use.params["hour_cycle"] not in ("desktop", "12", "24"):
            raise ValueError("hour_cycle is desktop, 12 or 24")
        try:
            render(use.params, datetime.now())
        except ZoneInfoNotFoundError:
            raise ValueError(f"timezone: unknown zone {use.params['timezone']!r}") from None
        except ValueError as exc:
            raise ValueError(f"format: {exc}") from None

    def show(self, use: UseRecord, now: datetime) -> None:
        try:
            text = render(use.params, now)
        except Exception:
            text = FALLBACK
        self.ctx.send("time", text, use=use)

    def tick(self) -> None:
        now = datetime.now().astimezone()
        for use in self.ctx.uses.values():
            self.show(use, now)

    def tick_seconds(self) -> None:
        now = datetime.now().astimezone()
        for use in self.ctx.uses.values():
            if "%S" in pattern(use.params):
                self.show(use, now)
