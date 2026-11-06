"""The Clock: the time as a string, once a minute, or once a second when a format shows seconds
(Clock Module). One instance serves every use; each use has its own format, zone and locale, and
sends the text of its tooltip too (the layout's ``Tooltip`` shows it on hover)."""

from __future__ import annotations

import locale
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
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


def render_tooltip(params: Mapping[str, Any], now: datetime) -> str:
    zone = ZoneInfo(params["timezone"]) if params["timezone"] else None
    return now.astimezone(zone).strftime(str(params["tooltip_format"]))


def installed(name: str) -> str | None:
    """The spelling of the locale ``name`` (``de_DE``) this system has installed for time names,
    or ``None``: ``de_DE.UTF-8``, ``de_DE.utf8`` and ``de_DE`` are tried in that order."""
    previous = locale.setlocale(locale.LC_TIME)
    try:
        for candidate in (f"{name}.UTF-8", f"{name}.utf8", name):
            try:
                locale.setlocale(locale.LC_TIME, candidate)
            except locale.Error:
                continue
            return candidate
        return None
    finally:
        locale.setlocale(locale.LC_TIME, previous)


@contextmanager
def time_names(spelling: str | None) -> Iterator[None]:
    """Month and day names, and ``%p``, in ``spelling`` (from :func:`installed`) while the block
    runs. The C library keeps one such setting for the whole process, so it is put back at once;
    the Clock runs on the loop thread, one use after another."""
    if spelling is None:
        yield
        return
    previous = locale.setlocale(locale.LC_TIME)
    locale.setlocale(locale.LC_TIME, spelling)
    try:
        yield
    finally:
        locale.setlocale(locale.LC_TIME, previous)


class Clock(Module):
    def __init__(self) -> None:
        self._spellings: dict[str, str | None] = {}  # locale name -> its installed spelling

    def spelling(self, name: str) -> str | None:
        """The installed spelling of ``name``; a locale this system lacks is warned about once and
        the Clock uses the process's own names instead (Clock Module > Configuration, ``locale``).
        Empty follows the desktop, which is the process's locale until KDE's is read."""
        if not name:
            return None
        if name not in self._spellings:
            found = self._spellings[name] = installed(name)
            if found is None:
                self.ctx.log.warning(
                    f"locale {name!r} is not installed (see `locale -a`): the Clock shows the "
                    "default month and day names"
                )
        return self._spellings[name]

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
        try:
            render_tooltip(use.params, datetime.now())
        except ValueError as exc:
            raise ValueError(f"tooltip_format: {exc}") from None
        self.spelling(use.params["locale"])  # warns once when it is not installed

    def show(self, use: UseRecord, now: datetime) -> None:
        with time_names(self.spelling(use.params["locale"])):
            try:
                text = render(use.params, now)
            except Exception:
                text = FALLBACK
            try:
                tooltip = render_tooltip(use.params, now)
            except Exception:
                tooltip = FALLBACK
        self.ctx.send("time", text, use=use)
        self.ctx.send("tooltip", tooltip, use=use)

    def use_added(self, use: UseRecord) -> None:
        self.show(use, datetime.now().astimezone())

    def tick(self) -> None:
        now = datetime.now().astimezone()
        for use in self.ctx.uses.values():
            self.show(use, now)

    def tick_seconds(self) -> None:
        now = datetime.now().astimezone()
        for use in self.ctx.uses.values():
            if "%S" in pattern(use.params):
                self.show(use, now)
