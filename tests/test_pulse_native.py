"""The PulseAudio native-protocol client (``services/pulse_native.py``) against the in-process fake
server (``tests/fake_pulse.py``): no real sound server is involved (Audio Module, safety)."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from tess_shell.services.pulse_native import (
    FACILITY_SERVER,
    FACILITY_SINK,
    FACILITY_SOURCE,
    NORM,
    TYPE_CHANGE,
    PulseAuthError,
    PulseClient,
    PulseError,
    cookie_paths,
    default_socket,
    read_cookie,
    scaled,
)
from tests.fake_pulse import FakePulse

VERSIONS = (13, 15, 16, 21, 24, 34, 35)
PORTS = [
    ("analog-output-speaker", "Speakers", "Speaker"),
    ("analog-output-headphones", "H", "Headphones"),
]


def populated(fake: FakePulse) -> None:
    fake.add_sink(
        "alsa_output.pci",
        "Mainboard",
        percent=45,
        bus="pci",
        ports=PORTS,
        active="analog-output-headphones",
        default=True,
    )
    fake.add_sink("alsa_output.usb", "Razer", percent=80, bus="usb")
    fake.add_source("mic", muted=True)
    fake.start()


def run[T](coro: asyncio.Future[T] | object) -> T:
    return asyncio.run(coro)  # type: ignore[arg-type]


# -- discovery ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        ({"PULSE_SERVER": "unix:/tmp/x/native"}, "/tmp/x/native"),
        ({"PULSE_SERVER": "/tmp/y/native"}, "/tmp/y/native"),
        ({"PULSE_SERVER": "{abc}unix:/tmp/z/native tcp:host"}, "/tmp/z/native"),
        ({"PULSE_SERVER": "tcp:somewhere:4713"}, None),
        ({"PULSE_RUNTIME_PATH": "/tmp/r"}, "/tmp/r/native"),
        ({"XDG_RUNTIME_DIR": "/tmp/u"}, "/tmp/u/pulse/native"),
        ({"PULSE_SERVER": "unix:/tmp/a", "XDG_RUNTIME_DIR": "/tmp/u"}, "/tmp/a"),
        ({}, None),
    ],
)
def test_default_socket_follows_the_environment_it_is_given(
    env: dict[str, str], expected: str | None
) -> None:
    assert default_socket(env) == (Path(expected) if expected else None)


def test_the_cookie_is_read_in_libpulses_order(tmp_path: Path) -> None:
    (tmp_path / ".config" / "pulse").mkdir(parents=True)
    good = bytes(range(256))
    (tmp_path / ".config" / "pulse" / "cookie").write_bytes(good)
    env = {"HOME": str(tmp_path)}
    assert cookie_paths(env) == [tmp_path / ".config/pulse/cookie", tmp_path / ".pulse-cookie"]
    assert read_cookie(env) == good
    (tmp_path / "short").write_bytes(b"abc")  # not 256 bytes: skipped
    assert read_cookie({"PULSE_COOKIE": str(tmp_path / "short"), **env}) == good
    assert read_cookie({"HOME": str(tmp_path / "none")}) is None


# -- volume arithmetic --------------------------------------------------------------------------


def test_scaled_sets_the_mean_and_keeps_the_balance() -> None:
    assert scaled([NORM, NORM], 50) == [NORM // 2, NORM // 2]
    left, right = scaled([NORM // 2, NORM // 4], 60)  # the right channel stays half of the left
    assert right * 2 == pytest.approx(left, abs=1)
    assert (left + right) / 2 == pytest.approx(0.6 * NORM, abs=1)
    assert scaled([0, 0], 30) == [round(0.3 * NORM)] * 2  # no balance to keep
    assert scaled([NORM], 150) == [NORM] and scaled([NORM], -5) == [0]
    assert max(scaled([NORM, NORM // 2], 100)) == NORM  # never above 100 %


# -- the protocol against the fake -----------------------------------------------------------


@pytest.mark.parametrize("version", VERSIONS)
def test_every_protocol_version_is_read(fake_pulse: FakePulse, version: int) -> None:
    fake_pulse.version = version
    populated(fake_pulse)

    async def go() -> None:
        client = PulseClient(fake_pulse.socket)
        await client.connect()
        try:
            assert client.version == version
            server, sinks, sources = await client.snapshot()
            assert server.default_sink == "alsa_output.pci" and server.default_source == "mic"
            assert [s.name for s in sinks] == ["alsa_output.pci", "alsa_output.usb"]
            assert sinks[0].percent == 45 and sinks[1].percent == 80
            assert sinks[0].description == "Mainboard"
            assert sinks[0].props["device.bus"] == "pci"
            assert [s.name for s in sources] == [
                "alsa_output.pci.monitor",
                "alsa_output.usb.monitor",
                "mic",
            ]
            mic = sources[2]
            assert mic.mute and sources[0].monitor == sinks[0].index
            ports = sinks[0].ports
            if version >= 16:
                assert sinks[0].active_port == "analog-output-headphones"
                assert [p.name for p in ports] == [p[0] for p in PORTS]
                # the type of a port arrives from protocol 34
                assert sinks[0].port_kind == ("Headphones" if version >= 34 else "")
            else:
                assert ports == [] and sinks[0].active_port == ""
        finally:
            client.close()

    run(go())


def test_the_version_is_the_lower_of_the_two(fake_pulse: FakePulse) -> None:
    fake_pulse.version = 24
    populated(fake_pulse)

    async def go() -> int:
        client = PulseClient(fake_pulse.socket)
        await client.connect()
        client.close()
        return client.version

    assert run(go()) == 24


def test_a_server_below_13_is_refused(fake_pulse: FakePulse) -> None:
    fake_pulse.version = 12
    fake_pulse.start()

    async def go() -> None:
        await PulseClient(fake_pulse.socket).connect()

    with pytest.raises(PulseError, match="below 13"):
        run(go())


def test_a_refused_cookie_is_an_auth_error_and_the_right_cookie_connects(
    fake_pulse: FakePulse,
) -> None:
    secret = bytes(range(256))
    fake_pulse.cookie = secret
    populated(fake_pulse)

    async def go() -> None:
        with pytest.raises(PulseAuthError):
            await PulseClient(fake_pulse.socket).connect()  # the zero cookie
        client = PulseClient(fake_pulse.socket, cookie=secret)
        await client.connect()
        client.close()

    run(go())
    assert fake_pulse.auths == [bytes(256), secret]


def test_no_socket_is_an_oserror(fake_pulse: FakePulse) -> None:
    async def go() -> None:
        await PulseClient(fake_pulse.socket).connect()

    with pytest.raises(OSError):
        run(go())


def test_an_event_arrives_for_each_change_and_only_what_was_subscribed(
    fake_pulse: FakePulse,
) -> None:
    populated(fake_pulse)

    async def go() -> list[tuple[int, int, int]]:
        events: list[tuple[int, int, int]] = []
        client = PulseClient(fake_pulse.socket, on_event=lambda *e: events.append(e))
        await client.connect()
        await client.subscribe()
        index = fake_pulse.sink("alsa_output.pci").index
        await asyncio.to_thread(fake_pulse.set_volume, "alsa_output.pci", 20)
        await asyncio.to_thread(fake_pulse.set_mute, "alsa_output.pci", True)
        await asyncio.to_thread(fake_pulse.set_default_sink, "alsa_output.usb")
        await asyncio.to_thread(fake_pulse.set_source_mute, "mic", False)
        await asyncio.to_thread(fake_pulse.set_volume, "alsa_output.pci", 20)  # no change: silent
        await asyncio.sleep(0.1)
        client.close()
        assert index == events[0][2]
        return events

    events: list[tuple[int, int, int]] = run(go())
    assert [(f, k) for f, k, _ in events] == [
        (FACILITY_SINK, TYPE_CHANGE),
        (FACILITY_SINK, TYPE_CHANGE),
        (FACILITY_SERVER, TYPE_CHANGE),
        (FACILITY_SOURCE, TYPE_CHANGE),
    ]


def test_the_setters_reach_the_server(fake_pulse: FakePulse) -> None:
    populated(fake_pulse)

    async def go() -> None:
        client = PulseClient(fake_pulse.socket)
        await client.connect()
        sink = fake_pulse.sink("alsa_output.pci")
        mic = fake_pulse.source("mic")
        await client.set_sink_volume(sink.index, [NORM // 2, NORM // 4])
        await client.set_sink_mute(sink.index, True)
        await client.set_source_mute(mic.index, False)
        await client.set_default_sink("alsa_output.usb")
        with pytest.raises(PulseError) as error:
            await client.set_default_sink("no-such-sink")
        assert error.value.code == 5
        client.close()

    run(go())
    assert fake_pulse.sink("alsa_output.pci").volume == [NORM // 2, NORM // 4]
    assert fake_pulse.sink("alsa_output.pci").mute
    assert not fake_pulse.source("mic").mute
    assert fake_pulse.default_sink == "alsa_output.usb"
    assert [c[0] for c in fake_pulse.commands] == [
        "set_sink_volume",
        "set_sink_mute",
        "set_source_mute",
        "set_default_sink",
        "set_default_sink",
    ]


def test_an_unknown_command_is_an_error_not_a_hang(fake_pulse: FakePulse) -> None:
    populated(fake_pulse)

    async def go() -> None:
        client = PulseClient(fake_pulse.socket)
        await client.connect()
        try:
            await client.call(999)
        finally:
            client.close()

    with pytest.raises(PulseError) as error:
        run(go())
    assert error.value.code == 20


def test_the_loss_of_the_server_is_reported_and_pending_calls_fail(fake_pulse: FakePulse) -> None:
    populated(fake_pulse)

    async def go() -> bool:
        lost = asyncio.Event()
        client = PulseClient(fake_pulse.socket, on_lost=lost.set)
        await client.connect()
        await asyncio.to_thread(fake_pulse.stop)
        await asyncio.wait_for(lost.wait(), 3)
        with pytest.raises(ConnectionError):
            await client.snapshot()
        return True

    assert run(go())
