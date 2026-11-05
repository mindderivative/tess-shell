"""The portal reader against a fake Settings portal on a private bus (Portals)."""

from __future__ import annotations

import time

import pytest
from dbus_fast import Variant

from tess_shell.services.bus import ServiceThread
from tess_shell.services.portal import Appearance, PortalReader, apply_key, parse
from tests.fake_portal import HAVE_DAEMON, fake_portal, wait_for

needs_daemon = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")


def test_parse_reads_the_four_keys() -> None:
    got = parse(
        {
            "color-scheme": Variant("u", 2),
            "accent-color": Variant("(ddd)", [0.0, 0.5, 1.0]),
            "contrast": Variant("u", 1),
            "reduced-motion": Variant("u", 1),
        }
    )
    assert got == Appearance("light", (0, 128, 255), True, True)


@pytest.mark.parametrize(
    ("key", "value", "expected"),
    [
        ("color-scheme", 7, Appearance(scheme="default")),  # an unknown value counts as 0
        ("contrast", 9, Appearance(high_contrast=False)),
        ("accent-color", [2.0, 0.0, 0.0], Appearance(accent=None)),  # out of range means unset
        ("accent-color", "red", Appearance(accent=None)),
        ("something-new", 1, Appearance()),  # an unknown key changes nothing
    ],
)
def test_odd_values_fall_back_to_the_defaults(
    key: str, value: object, expected: Appearance
) -> None:
    assert apply_key(Appearance(), key, value) == expected


@needs_daemon
def test_it_registers_first_reads_once_and_follows_changes() -> None:
    seen: list[tuple[float, Appearance]] = []
    with fake_portal() as (address, portal):
        service = ServiceThread(address)
        service.start()
        reader = PortalReader(service, lambda a: seen.append((time.monotonic(), a)))
        try:
            reader.start()
            assert reader.first(2.0) == Appearance("dark", (64, 128, 255), False, False)
            assert portal.settings.calls == ["Register", "ReadAll"]  # Register before any read
            assert portal.registry.ids == ["io.github.mindderivative.TesseraeShell"]
            sent = time.monotonic()
            portal.set("color-scheme", Variant("u", 2))
            assert wait_for(lambda: any(a.scheme == "light" for _, a in seen))
            arrived = next(t for t, a in seen if a.scheme == "light")
            assert arrived - sent < 0.1  # the 100 ms budget, signal to callback
            portal.set("reduced-motion", Variant("u", 1))
            assert wait_for(lambda: seen[-1][1].reduced_motion)
            assert portal.settings.calls.count("ReadAll") == 1  # signals only, no polling
        finally:
            reader.stop()
            service.stop()


@needs_daemon
def test_an_unchanged_value_does_not_call_back() -> None:
    seen: list[Appearance] = []
    with fake_portal() as (address, portal):
        service = ServiceThread(address)
        service.start()
        reader = PortalReader(service, seen.append)
        try:
            reader.start()
            first = reader.first(2.0)
            assert wait_for(lambda: len(seen) == 1)  # the first answer is announced once
            portal.set("color-scheme", Variant("u", 1))  # the value it already had
            time.sleep(0.2)
            assert seen == [first]
        finally:
            reader.stop()
            service.stop()


@needs_daemon
def test_no_portal_gives_the_defaults_with_one_warning_and_recovers() -> None:
    from loguru import logger

    lines: list[str] = []
    sink = logger.add(lambda m: lines.append(str(m)), level="WARNING")
    seen: list[Appearance] = []
    try:
        with fake_portal(running=False) as (address, portal):
            service = ServiceThread(address)
            service.start()
            reader = PortalReader(service, seen.append)
            try:
                reader.start()
                assert reader.first(2.0) == Appearance()
                assert sum("portal:" in x and "default appearance" in x for x in lines) == 1
                portal.up()  # the portal service appears later
                assert wait_for(lambda: bool(seen))
                assert seen[-1].scheme == "dark"
            finally:
                reader.stop()
                service.stop()
    finally:
        logger.remove(sink)


@needs_daemon
def test_a_slow_portal_does_not_hold_first_beyond_its_timeout() -> None:
    with fake_portal(running=False) as (address, _portal):
        service = ServiceThread(address)
        service.start()
        reader = PortalReader(service, lambda a: None)
        try:
            reader.start()
            started = time.monotonic()
            reader.first(0.05)
            assert time.monotonic() - started < 0.5
        finally:
            reader.stop()
            service.stop()
