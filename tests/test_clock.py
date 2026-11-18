"""The shipped Clock: its text and its tooltip, ``locale`` and ``tooltip_format`` (Clock Module)."""

from __future__ import annotations

import importlib.util
import locale
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from loguru import logger

from tess_shell.appearance import Appearance
from tess_shell.config.discovery import shipped_dir
from tess_shell.config.settings import load_settings
from tess_shell.model.store import ValueStore
from tess_shell.modules.context import ModuleContext, UseRecord
from tess_shell.modules.ticks import TimeSource
from tess_shell.scanner import build_look, scan
from tess_shell.surfaces.manager import SurfaceManager
from tests.shell_samples import BODY, write_example
from tests.test_panel import StubApp

CLOCK_PY = shipped_dir() / "Clock" / "Clock_Module.py"
FRIDAY = datetime(2026, 11, 6, 14, 5, 9)


def load_clock() -> ModuleType:
    spec = importlib.util.spec_from_file_location("shipped_clock", CLOCK_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeLocale:
    """``locale.setlocale`` for LC_TIME with a list of installed names and a record of changes."""

    def __init__(self, installed: set[str]) -> None:
        self.installed = installed | {"C"}
        self.current = "C"
        self.history: list[str] = []

    def setlocale(self, category: int, value: str | None = None) -> str:
        assert category == locale.LC_TIME
        if value is None:
            return self.current
        if value not in self.installed:
            raise locale.Error("unsupported locale setting")
        self.history.append(value)
        self.current = value
        return value


def clock(
    params: dict[str, Any], module: ModuleType | None = None
) -> tuple[Any, UseRecord, list[tuple[str | None, str, object]], list[str]]:
    """A Clock with a context that records what it sends, and the warnings it logs."""
    module = module or load_clock()
    sent: list[tuple[str | None, str, object]] = []
    record = UseRecord(
        "Clock@u1",
        "S.M.B.Clock_1",
        "u1",
        "Main",
        {
            "format": "%H:%M",
            "locale": "",
            "hour_cycle": "24",
            "timezone": "",
            "tooltip_format": "%A, %d %B %Y",
            **params,
        },
    )
    ctx = ModuleContext(
        "Clock",
        "uid",
        {},
        {record.key: record},
        lambda use, key, value: sent.append((use, key, value)),
        TimeSource(),
    )
    lines: list[str] = []
    sink = logger.add(lambda m: lines.append(str(m)), level="WARNING")
    _SINKS.append(sink)
    instance = module.Clock.__new__(module.Clock)
    instance.ctx = ctx
    instance.__init__()
    return instance, record, sent, lines


_SINKS: list[int] = []


@pytest.fixture(autouse=True)
def _drop_sinks() -> Iterator[None]:
    yield
    while _SINKS:
        logger.remove(_SINKS.pop())


def sent_value(sent: list[tuple[str | None, str, object]], key: str) -> object:
    return next(value for _, k, value in sent if k == key)


def test_a_use_sends_its_time_and_its_tooltip_text_in_tooltip_format() -> None:
    instance, use, sent, _ = clock({"tooltip_format": "%d.%m.%Y"})
    instance.show(use, FRIDAY.astimezone())
    assert sent_value(sent, "time") == "14:05"
    assert sent_value(sent, "tooltip") == "06.11.2026"


def test_the_tooltip_defaults_to_the_weekday_day_month_and_year() -> None:
    instance, use, sent, _ = clock({})
    instance.show(use, FRIDAY.astimezone())
    assert sent_value(sent, "tooltip") == "Friday, 06 November 2026"  # the process's own names


def test_a_locale_that_is_installed_names_the_days_and_months_and_the_process_locale_returns(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_clock()
    fake = FakeLocale({"de_DE.UTF-8"})
    monkeypatch.setattr(locale, "setlocale", fake.setlocale)
    seen: list[str] = []
    monkeypatch.setattr(
        module, "render_tooltip", lambda params, now: seen.append(fake.current) or "Freitag"
    )
    instance, use, sent, _ = clock({"locale": "de_DE"}, module)
    instance.show(use, FRIDAY.astimezone())
    assert seen == ["de_DE.UTF-8"]  # the text was made while the locale was set
    assert fake.current == "C"  # and the process's own is back
    assert sent_value(sent, "tooltip") == "Freitag"


def test_a_locale_the_system_lacks_is_warned_about_once_and_the_default_names_are_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(locale, "setlocale", FakeLocale(set()).setlocale)
    instance, use, sent, lines = clock({"locale": "xx_XX"})
    instance.show(use, FRIDAY.astimezone())
    instance.show(use, FRIDAY.astimezone())
    assert [v for _, k, v in sent if k == "tooltip"] == ["Friday, 06 November 2026"] * 2
    warnings = [x for x in lines if "xx_XX" in x]
    assert len(warnings) == 1 and "not installed" in warnings[0] and "locale -a" in warnings[0]


def german_installed() -> bool:
    previous = locale.setlocale(locale.LC_TIME)
    try:
        locale.setlocale(locale.LC_TIME, "de_DE.UTF-8")
    except locale.Error:
        return False
    finally:
        locale.setlocale(locale.LC_TIME, previous)
    return True


@pytest.mark.skipif(not german_installed(), reason="de_DE.UTF-8 is not installed (locale -a)")
def test_with_the_real_german_locale_the_tooltip_has_german_names() -> None:
    before = locale.setlocale(locale.LC_TIME)
    instance, use, sent, _ = clock({"locale": "de_DE"})
    instance.show(use, FRIDAY.astimezone())
    assert sent_value(sent, "tooltip") == "Freitag, 06 November 2026"
    assert locale.setlocale(locale.LC_TIME) == before


# -- the shipped layout: hovering the clock opens the tooltip ---------------------------------


def test_hovering_the_shipped_clock_opens_a_tooltip_with_the_text_the_clock_sent(
    tmp_path: Path,
) -> None:
    body = BODY.replace(
        'Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }', "Clock { Name: Clock_One }"
    )
    write_example(tmp_path, body)
    settings, _ = load_settings(tmp_path)
    assert settings is not None
    result = scan(settings, tmp_path)
    assert not result.errors, result.findings
    shell = result.shells[next(iter(result.shells))]
    store = ValueStore()
    manager = SurfaceManager(
        StubApp(),  # type: ignore[arg-type]
        {n: mf.definition for n, mf in result.modules.items()},
        lambda key: key,
        store,
        build_look(result, settings, Appearance()),
    )
    (use,) = manager.plan(shell)
    store.send("Clock", use.key, "time", "14:05")
    store.send("Clock", use.key, "tooltip", "Friday, 06 November 2026")
    store.flush()
    manager.build()
    bar = next(s for s in manager.surfaces if s.name == "Top_Bar")
    assert bar.window is not None and bar.view is not None
    bar.window.advance(16)
    (block,) = bar.expanded.tooltips  # the box around the Clock's text
    bar.window.simulate("pointer_enter", bar.view.nodes[block])
    bar.window.advance(499)
    assert manager.popups.current is None  # Enter_Delay is 500 ms
    bar.window.advance(2)
    op = manager.popups.current
    assert op is not None and op.view is not None and op.window.get("grab") is False
    texts = [n.get("text") for n in op.view.nodes.values() if n.get("kind") == "text"]
    assert texts == ["Friday, 06 November 2026"]
    assert op.window.get("anchor_rect")[:2] == tuple(
        round(float(bar.view.nodes[block].get(k))) for k in ("layout_x", "layout_y")
    )


# -- hour_cycle: desktop is the time format of the locale (Clock Module > Configuration) -----------

T_FMT = {"C": "%H:%M:%S", "en_US.UTF-8": "%r", "de_DE.UTF-8": "%T", "en_GB.UTF-8": "%T"}


def fake_time_locales(monkeypatch: pytest.MonkeyPatch, module: ModuleType) -> FakeLocale:
    """Installed: en_US, de_DE and en_GB; each has its own ``T_FMT``, read as the real one is,
    from whatever LC_TIME is set when it is asked."""
    fake = FakeLocale({"en_US.UTF-8", "de_DE.UTF-8", "en_GB.UTF-8"})
    monkeypatch.setattr(locale, "setlocale", fake.setlocale)
    monkeypatch.setattr(locale, "nl_langinfo", lambda item: T_FMT[fake.current])
    for variable in ("LC_ALL", "LC_TIME", "LANG"):
        monkeypatch.delenv(variable, raising=False)
    return fake


def shown(
    monkeypatch: pytest.MonkeyPatch, params: dict[str, Any], **env: str
) -> tuple[object, FakeLocale]:
    module = load_clock()
    fake = fake_time_locales(monkeypatch, module)
    for variable, value in env.items():
        monkeypatch.setenv(variable, value)
    instance, use, sent, _ = clock({"hour_cycle": "desktop", "format": "", **params}, module)
    instance.show(use, FRIDAY.astimezone())
    return sent_value(sent, "time"), fake


def test_desktop_is_12_hours_when_the_locale_of_the_use_counts_to_12(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    text, fake = shown(monkeypatch, {"locale": "en_US"})
    assert text == "02:05 PM"
    assert fake.current == "C"  # the process's own locale is back


def test_desktop_is_24_hours_when_the_locale_of_the_use_counts_to_24(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert shown(monkeypatch, {"locale": "de_DE"})[0] == "14:05"
    assert shown(monkeypatch, {"locale": "en_GB"})[0] == "14:05"  # English, 24 hours


def test_desktop_without_a_locale_follows_the_environments_locale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert shown(monkeypatch, {}, LANG="en_US.UTF-8")[0] == "02:05 PM"
    assert shown(monkeypatch, {}, LANG="en_US.UTF-8", LC_TIME="de_DE.UTF-8")[0] == "14:05"
    assert shown(monkeypatch, {}, LANG="de_DE.UTF-8", LC_ALL="en_US.UTF-8")[0] == "02:05 PM"


@pytest.mark.parametrize("env", [{}, {"LANG": "C"}, {"LANG": "POSIX"}, {"LANG": "fr_FR.UTF-8"}])
def test_desktop_is_24_hours_when_no_locale_is_set_or_it_is_not_installed(
    monkeypatch: pytest.MonkeyPatch, env: dict[str, str]
) -> None:
    assert shown(monkeypatch, {}, **env)[0] == "14:05"


def test_an_explicit_hour_cycle_or_format_wins_over_the_desktop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert shown(monkeypatch, {"hour_cycle": "24"}, LANG="en_US.UTF-8")[0] == "14:05"
    assert shown(monkeypatch, {"hour_cycle": "12"}, LANG="de_DE.UTF-8")[0] == "02:05 PM"
    assert shown(monkeypatch, {"format": "%H.%M"}, LANG="en_US.UTF-8")[0] == "14.05"
