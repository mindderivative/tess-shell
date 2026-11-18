"""The Clock: the time as a string, once a minute, or once a second when a format shows seconds
(Clock Module). One instance serves every use; each use has its own format, zone and locale, and
sends the text of its tooltip too (the layout's ``Tooltip`` shows it on hover)."""

from __future__ import annotations

import locale
import os
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import datetime
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from tess_shell import Module

if TYPE_CHECKING:
    from tess_shell.modules.context import UseRecord

FALLBACK = "--:--"


def pattern(params: Mapping[str, Any], desktop_12: bool = False) -> str:
    """The strftime pattern of a use: its ``format``, else one chosen by ``hour_cycle``.

    ``desktop`` is 12 hours when ``desktop_12`` (the locale's own time format counts hours to 12,
    see :func:`uses_12_hours`) and 24 hours otherwise."""
    if params["format"]:
        return str(params["format"])
    twelve = params["hour_cycle"] == "12" or (params["hour_cycle"] == "desktop" and desktop_12)
    return "%I:%M %p" if twelve else "%H:%M"


def render(params: Mapping[str, Any], now: datetime, desktop_12: bool = False) -> str:
    zone = ZoneInfo(params["timezone"]) if params["timezone"] else None
    return now.astimezone(zone).strftime(pattern(params, desktop_12))


def environment_locale() -> str:
    """The locale name the environment gives time (``LC_ALL``, then ``LC_TIME``, then ``LANG``, the
    first that is not empty, as the C library reads them); empty when none is set. The shell
    does not call ``setlocale`` for itself, so this is the desktop session's locale, not the
    process's."""
    for variable in ("LC_ALL", "LC_TIME", "LANG"):
        value = os.environ.get(variable, "")
        if value:
            return value
    return ""


def uses_12_hours() -> bool:
    """Whether the time format of the current ``LC_TIME`` locale counts hours to 12: its
    ``T_FMT`` (``%r`` or ``%I:%M:%S %p`` in en_US, ``%T`` in de_DE) names ``%p``, ``%P``, ``%r``,
    ``%I`` or ``%l``."""
    fmt = locale.nl_langinfo(locale.T_FMT)
    return any(token in fmt for token in ("%p", "%P", "%r", "%I", "%l"))


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

    def desktop_12(self, params: Mapping[str, Any]) -> bool:
        """What ``hour_cycle: desktop`` means for a use: 12 hours when the time format of its
        locale counts to 12. The locale is the use's ``locale`` param, else the environment's
        (``LC_ALL``, ``LC_TIME``, ``LANG``); one that is unset, ``C`` or not installed gives 24.
        The shell reads no clock-format value from the desktop (the Settings portal values it
        follows are appearance ones), so the locale's own time format is the source."""
        if params["hour_cycle"] != "desktop" or params["format"]:
            return False
        name = params["locale"] or environment_locale()
        if name in ("", "C", "POSIX"):
            return False
        spelling = self.spelling(params["locale"]) if params["locale"] else installed(name)
        if spelling is None:
            return False
        with time_names(spelling):
            return uses_12_hours()

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
        twelve = self.desktop_12(use.params)
        with time_names(self.spelling(use.params["locale"])):
            try:
                text = render(use.params, now, twelve)
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
