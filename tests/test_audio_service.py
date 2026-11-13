"""The sound service (``services/audio.py``) on the ``dbus`` service thread against the in-process
fake PulseAudio server: state from events, the setters, the kind lookup, the reconnect by inotify
and no timer. No real sound server is involved (Audio Module, safety)."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tess_shell.services import audio as audio_module
from tess_shell.services.api import AudioError, AudioState
from tess_shell.services.audio import AudioService, output_kind
from tess_shell.services.bus import ServiceThread
from tess_shell.services.pulse_native import NORM
from tests.fake_dbus import wait_for
from tests.fake_pulse import FakePulse

PORTS = [
    ("analog-output-speaker", "Speakers", "Speaker"),
    ("analog-output-headphones", "H", "Headphones"),
]


class Seen:
    """What a module's callback received, on the service thread."""

    def __init__(self) -> None:
        self.states: list[AudioState | None] = []
        self.lock = threading.Lock()

    def __call__(self, state: AudioState | None) -> None:
        with self.lock:
            self.states.append(state)

    @property
    def last(self) -> AudioState | None:
        with self.lock:
            return self.states[-1] if self.states else "none-yet"  # type: ignore[return-value]

    def count(self) -> int:
        with self.lock:
            return len(self.states)


class Rig:
    def __init__(self, fake: FakePulse, **kwargs: Any) -> None:
        self.fake = fake
        self.thread = ServiceThread()
        self.thread.start()
        kwargs.setdefault("env", {})  # never the real environment, not even for a cookie
        self.audio = AudioService(self.thread, fake.socket, **kwargs)
        self.helper = self.audio.for_module("Test")
        self.seen = Seen()
        self.sub = self.helper.on_changed(self.seen)

    def until(self, predicate: Any, timeout: float = 3.0) -> bool:
        return wait_for(lambda: predicate(self.seen.last), timeout)

    def close(self) -> None:
        self.helper.close()
        self.thread.stop()


@pytest.fixture
def quick(monkeypatch: pytest.MonkeyPatch) -> None:
    """No wait after a connection that ends at once (tests restart the fake in no time)."""
    monkeypatch.setattr(audio_module, "SHORT_SESSION", 0.0)


@pytest.fixture
def rig(fake_pulse: FakePulse, quick: None) -> Iterator[Rig]:
    fake_pulse.add_sink(
        "pci", "Mainboard", percent=45, bus="pci", ports=PORTS, active="analog-output-speaker",
        default=True,
    )  # fmt: skip
    fake_pulse.add_sink("usb", "Razer", percent=80, bus="usb")
    fake_pulse.add_source("mic", "Microphone")
    fake_pulse.start()
    r = Rig(fake_pulse)
    assert r.until(lambda s: isinstance(s, AudioState))
    yield r
    r.close()


def test_the_first_state_is_the_default_output_and_its_neighbours(rig: Rig) -> None:
    state = rig.seen.last
    assert isinstance(state, AudioState)
    assert state.output is not None
    assert (state.output.name, state.output.description, state.output.kind) == (
        "pci",
        "Mainboard",
        "SPEAKER",
    )
    assert (state.volume, state.muted, state.has_mic, state.mic_muted) == (45, False, True, False)
    assert [(o.name, o.kind) for o in state.outputs] == [("pci", "SPEAKER"), ("usb", "SPEAKER")]
    assert rig.audio.available and rig.audio.state == state
    assert rig.helper.state == state


def test_a_change_by_another_client_arrives_as_a_state(rig: Rig) -> None:
    rig.fake.set_volume("pci", 70)
    assert rig.until(lambda s: s is not None and s.volume == 70)
    rig.fake.set_mute("pci", True)
    assert rig.until(lambda s: s is not None and s.muted)
    rig.fake.set_source_mute("mic", True)
    assert rig.until(lambda s: s is not None and s.mic_muted)
    rig.fake.set_default_sink("usb")
    assert rig.until(lambda s: s is not None and s.output is not None and s.output.name == "usb")
    assert isinstance(rig.seen.last, AudioState) and rig.seen.last.volume == 80
    rig.fake.add_sink("hdmi", "HDMI output", form_factor="hdmi")
    assert rig.until(lambda s: s is not None and len(s.outputs) == 3)
    rig.fake.remove_sink("hdmi")
    assert rig.until(lambda s: s is not None and len(s.outputs) == 2)


def test_a_change_that_changes_nothing_hands_nothing_over(rig: Rig) -> None:
    before = rig.seen.count()
    rig.fake.set_active_port("pci", "analog-output-speaker")  # the same port: an event, same state
    rig.fake.sync(lambda: rig.fake._event(0, 0x10, rig.fake.sink("pci").index))
    time.sleep(0.15)
    assert rig.seen.count() == before


def test_a_volume_above_100_is_shown_as_it_is(rig: Rig) -> None:
    rig.fake.set_volume("pci", 130)
    assert rig.until(lambda s: s is not None and s.volume == 130)


def test_the_setters_change_the_server_and_the_state_follows(rig: Rig) -> None:
    rig.helper.set_volume(30).result(3)
    assert rig.until(lambda s: s is not None and s.volume == 30)
    rig.helper.set_volume(150).result(3)  # clamped to 100
    assert rig.until(lambda s: s is not None and s.volume == 100)
    rig.helper.set_volume(-4).result(3)
    assert rig.until(lambda s: s is not None and s.volume == 0)
    rig.helper.toggle_mute().result(3)
    assert rig.until(lambda s: s is not None and s.muted)
    rig.helper.toggle_mute().result(3)
    assert rig.until(lambda s: s is not None and not s.muted)
    rig.helper.set_muted(True).result(3)
    assert rig.until(lambda s: s is not None and s.muted)
    rig.helper.toggle_mic().result(3)
    assert rig.until(lambda s: s is not None and s.mic_muted)
    rig.helper.set_output("usb").result(3)
    assert rig.until(lambda s: s is not None and s.output is not None and s.output.name == "usb")


def test_set_volume_keeps_the_balance_by_scaling(rig: Rig) -> None:
    rig.fake.set_volume("pci", [NORM // 2, NORM // 4])  # left twice the right
    assert rig.until(lambda s: s is not None and s.volume == 38)  # the mean, 37.5 rounded
    rig.helper.set_volume(60).result(3)
    left, right = rig.fake.sink("pci").volume
    assert left == pytest.approx(2 * right, abs=2)
    assert (left + right) / 2 == pytest.approx(0.6 * NORM, abs=2)
    rig.helper.set_volume(100).result(3)
    assert max(rig.fake.sink("pci").volume) <= NORM


def test_steps_that_come_before_the_servers_event_add_up(rig: Rig) -> None:
    futures = [rig.helper.step(5) for _ in range(4)]
    for f in futures:
        f.result(3)
    assert rig.until(lambda s: s is not None and s.volume == 65)
    for f in [rig.helper.step(-5) for _ in range(3)]:
        f.result(3)
    assert rig.until(lambda s: s is not None and s.volume == 50)
    for f in [rig.helper.step(20) for _ in range(5)]:
        f.result(3)
    assert rig.until(lambda s: s is not None and s.volume == 100)  # clamped


def test_a_failed_setter_is_an_error_in_its_future(rig: Rig) -> None:
    with pytest.raises(AudioError):
        rig.helper.set_output("no-such-output").result(3)


def test_toggle_mic_with_no_microphone_is_an_error(fake_pulse: FakePulse, quick: None) -> None:
    fake_pulse.add_sink("pci", "Mainboard", default=True)  # only its monitor: not a microphone
    fake_pulse.start()
    rig = Rig(fake_pulse)
    try:
        assert rig.until(lambda s: isinstance(s, AudioState))
        assert isinstance(rig.seen.last, AudioState) and not rig.seen.last.has_mic
        with pytest.raises(AudioError):
            rig.helper.toggle_mic().result(3)
    finally:
        rig.close()


def test_no_output_at_all_is_a_state_with_no_output(fake_pulse: FakePulse, quick: None) -> None:
    fake_pulse.start()
    rig = Rig(fake_pulse)
    try:
        assert rig.until(lambda s: isinstance(s, AudioState))
        state = rig.seen.last
        assert isinstance(state, AudioState)
        assert state.output is None and state.outputs == () and state.volume == 0
        with pytest.raises(AudioError):
            rig.helper.set_volume(10).result(3)
    finally:
        rig.close()


# -- the kind lookup ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("props", "port", "kind"),
    [
        ({"device.form_factor": "headphone"}, "", "HEADPHONES"),
        ({"device.form_factor": "headset"}, "Speaker", "HEADPHONES"),  # the form factor first
        ({"device.form_factor": "speaker"}, "Headphones", "SPEAKER"),
        ({"device.form_factor": "internal"}, "", "SPEAKER"),
        ({"device.form_factor": "tv"}, "", "HDMI"),
        ({"device.form_factor": "hdmi"}, "", "HDMI"),
        ({}, "Headphones", "HEADPHONES"),
        ({}, "Headset", "HEADPHONES"),
        ({}, "HDMI", "HDMI"),
        ({}, "TV", "HDMI"),
        ({}, "Speaker", "SPEAKER"),
        ({}, "Analog", "SPEAKER"),
        ({}, "Line", "SPEAKER"),
        ({"device.bus": "bluetooth"}, "", "BLUETOOTH"),
        ({"device.bus": "bluetooth", "device.form_factor": "speaker"}, "Speaker", "BLUETOOTH"),
        ({"device.bus": "bluetooth", "device.form_factor": "headphone"}, "", "BLUETOOTH"),
        ({"device.form_factor": "car"}, "HDMI", "HDMI"),  # an unknown form factor is passed over
        ({"device.bus": "usb"}, "", "SPEAKER"),
        ({"device.bus": "pci"}, "Unknown", "SPEAKER"),
        ({}, "", "SPEAKER"),
    ],
)
def test_the_kind_lookup_order(props: dict[str, str], port: str, kind: str) -> None:
    assert output_kind(props, port) == kind


def test_the_machines_three_outputs_get_their_kinds_from_the_port_type(
    fake_pulse: FakePulse, quick: None
) -> None:
    """No output on the maintainer's machine sets a form factor (Audio Module > What It Reads)."""
    fake_pulse.add_sink(
        "main", "Mainboard", bus="pci", default=True, active="analog-output-speaker",
        ports=PORTS,
    )  # fmt: skip
    fake_pulse.add_sink("razer", "Razer", bus="usb", ports=[("analog-output", "Out", "Analog")])
    fake_pulse.add_sink("gpu", "HDMI", bus="pci", ports=[("hdmi-output-0", "HDMI", "HDMI")])
    fake_pulse.start()
    rig = Rig(fake_pulse)
    try:
        assert rig.until(lambda s: isinstance(s, AudioState))
        state = rig.seen.last
        assert isinstance(state, AudioState)
        assert [o.kind for o in state.outputs] == ["SPEAKER", "SPEAKER", "HDMI"]
        fake_pulse.set_active_port("main", "analog-output-headphones")
        assert rig.until(
            lambda s: s is not None and s.output is not None and s.output.kind == "HEADPHONES"
        )
    finally:
        rig.close()


def test_a_server_below_protocol_34_gives_the_kind_from_the_form_factor_and_the_bus(
    fake_pulse: FakePulse, quick: None
) -> None:
    fake_pulse.version = 24
    fake_pulse.add_sink("a", "A", form_factor="headphone", default=True, ports=PORTS)
    fake_pulse.add_sink("b", "B", bus="bluetooth")
    fake_pulse.add_sink("c", "C", ports=[("hdmi-output-0", "HDMI", "HDMI")])  # no port type
    fake_pulse.start()
    rig = Rig(fake_pulse)
    try:
        assert rig.until(lambda s: isinstance(s, AudioState))
        state = rig.seen.last
        assert isinstance(state, AudioState)
        assert [o.kind for o in state.outputs] == ["HEADPHONES", "BLUETOOTH", "SPEAKER"]
    finally:
        rig.close()


# -- no server, and the server coming and going -----------------------------------------------


def test_no_server_is_none_and_a_server_that_starts_shows_up_with_no_timer(
    fake_pulse: FakePulse, quick: None
) -> None:
    fake_pulse.add_sink("pci", "Mainboard", default=True)
    rig = Rig(fake_pulse)  # the socket's folder does not exist yet
    try:
        assert rig.until(lambda s: s is None)
        assert not rig.audio.available
        fake_pulse.start()
        assert rig.until(lambda s: isinstance(s, AudioState))
        assert rig.audio.connects == 1
    finally:
        rig.close()


def test_a_restart_hides_the_module_for_the_gap_and_brings_it_back(rig: Rig) -> None:
    rig.fake.stop()
    assert rig.until(lambda s: s is None)
    assert not rig.audio.available
    with pytest.raises(Exception, match="no sound server"):
        rig.helper.set_volume(10).result(3)
    rig.fake.start()
    assert rig.until(lambda s: isinstance(s, AudioState))
    assert rig.audio.connects == 2
    rig.fake.set_volume("pci", 12)  # events and setters work on the new connection
    assert rig.until(lambda s: s is not None and s.volume == 12)
    rig.helper.set_volume(33).result(3)
    assert rig.until(lambda s: s is not None and s.volume == 33)


def test_a_stale_socket_file_is_tried_and_waited_for(rig: Rig) -> None:
    rig.fake.stop(unlink=False)  # a killed server leaves its socket file behind
    assert rig.until(lambda s: s is None)
    assert rig.fake.socket.exists()
    time.sleep(0.3)  # the refused connects ended; nothing retries by itself
    count = rig.audio.connects
    rig.fake.start()  # the new server unlinks the file and binds again: an event
    assert rig.until(lambda s: isinstance(s, AudioState))
    assert rig.audio.connects == count + 1


def test_a_dropped_connection_is_remade_at_once(rig: Rig) -> None:
    rig.fake.drop_connections()
    assert wait_for(lambda: rig.audio.connects == 2)
    assert rig.until(lambda s: isinstance(s, AudioState))


def test_a_connection_that_ends_at_once_does_not_loop(
    fake_pulse: FakePulse, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(audio_module, "SHORT_SESSION", 0.5)
    fake_pulse.add_sink("pci", "Mainboard", default=True)
    fake_pulse.start()
    rig = Rig(fake_pulse)
    try:
        assert rig.until(lambda s: isinstance(s, AudioState))
        for _ in range(3):
            fake_pulse.drop_connections()
            time.sleep(0.1)
        assert rig.audio.connects <= 3  # the wait of half a second between the tries
    finally:
        rig.close()


def test_the_cookie_is_read_from_the_users_files_when_the_zero_cookie_is_refused(
    fake_pulse: FakePulse, tmp_path: Path, quick: None
) -> None:
    secret = bytes(range(256))
    fake_pulse.cookie = secret
    fake_pulse.add_sink("pci", "Mainboard", default=True)
    fake_pulse.start()
    (tmp_path / ".config" / "pulse").mkdir(parents=True)
    (tmp_path / ".config" / "pulse" / "cookie").write_bytes(secret)
    rig = Rig(fake_pulse, env={"HOME": str(tmp_path)})
    try:
        assert rig.until(lambda s: isinstance(s, AudioState))
        assert fake_pulse.auths == [bytes(256), secret]
    finally:
        rig.close()


def test_a_cookie_that_is_refused_leaves_the_module_hidden(
    fake_pulse: FakePulse, tmp_path: Path, quick: None
) -> None:
    fake_pulse.cookie = bytes(range(256))
    fake_pulse.add_sink("pci", "Mainboard", default=True)
    fake_pulse.start()
    rig = Rig(fake_pulse, env={"HOME": str(tmp_path)})  # no cookie file
    try:
        assert rig.until(lambda s: s is None)
        time.sleep(0.2)
        assert rig.audio.connects == 0 and len(fake_pulse.auths) == 1
    finally:
        rig.close()


# -- subscriptions ------------------------------------------------------------------------------


def test_nothing_connects_until_the_service_is_used(fake_pulse: FakePulse) -> None:
    fake_pulse.add_sink("pci", "Mainboard", default=True)
    fake_pulse.start()
    thread = ServiceThread()
    thread.start()
    try:
        helper = AudioService(thread, fake_pulse.socket, env={}).for_module("Test")
        time.sleep(0.2)
        assert fake_pulse.connections == 0 and helper.state is None
    finally:
        thread.stop()


def test_a_second_subscriber_gets_the_current_state_and_a_cancelled_one_nothing(rig: Rig) -> None:
    second = Seen()
    sub = rig.helper.on_changed(second)
    assert wait_for(lambda: isinstance(second.last, AudioState))
    sub.cancel()
    time.sleep(0.1)
    before = second.count()
    rig.fake.set_volume("pci", 9)
    assert rig.until(lambda s: s is not None and s.volume == 9)
    assert second.count() == before


def test_a_callback_that_raises_does_not_stop_the_others(rig: Rig) -> None:
    def bad(state: AudioState | None) -> None:
        raise RuntimeError("boom")

    rig.helper.on_changed(bad)
    rig.fake.set_volume("pci", 61)
    assert rig.until(lambda s: s is not None and s.volume == 61)
    count, p50, p99, worst = rig.audio.callback_summary("Test")
    assert count >= 2 and p50 <= p99 <= worst


# -- no timer -----------------------------------------------------------------------------------


def _counters(tid: int) -> tuple[int, int, int]:
    task = Path(f"/proc/{os.getpid()}/task/{tid}")
    cpu, _delay, slices = (int(x) for x in (task / "schedstat").read_text().split())
    voluntary = 0
    for line in (task / "status").read_text().splitlines():
        if line.startswith("voluntary_ctxt_switches"):
            voluntary = int(line.split()[1])
    return cpu, slices, voluntary


def _idle(rig: Rig, seconds: float) -> tuple[int, int, int]:
    tid = rig.thread.thread_id
    assert tid is not None
    # a thread's own id as /proc names it: the native id of the dbus thread
    native = rig.thread.submit(_native_id()).result(3)
    time.sleep(0.5)
    before = _counters(native)
    time.sleep(seconds)
    after = _counters(native)
    return (after[0] - before[0], after[1] - before[1], after[2] - before[2])


async def _native_id() -> int:
    return threading.get_native_id()


@pytest.mark.skipif(not Path("/proc/self/task").is_dir(), reason="needs /proc")
def test_idle_wakeups_5_s(rig: Rig, capsys: pytest.CaptureFixture[str]) -> None:
    cpu, slices, voluntary = _idle(rig, 5.0)
    with capsys.disabled():
        print(
            f"\naudio idle 5 s: timeslices {slices}, voluntary switches {voluntary}, cpu {cpu} ns"
        )
    assert (slices, voluntary) == (0, 0)


@pytest.mark.perf
@pytest.mark.skipif(not Path("/proc/self/task").is_dir(), reason="needs /proc")
def test_idle_wakeups_60_s(rig: Rig, capsys: pytest.CaptureFixture[str]) -> None:
    cpu, slices, voluntary = _idle(rig, 60.0)
    with capsys.disabled():
        print(
            f"\naudio idle 60 s: timeslices {slices}, voluntary switches {voluntary}, cpu {cpu} ns"
        )
    assert (slices, voluntary) == (0, 0)


def test_the_watch_is_armed_only_while_there_is_no_connection(rig: Rig) -> None:
    """While connected no inotify descriptor is open on the service thread (nothing to wake it
    but its socket)."""
    fds = [p for p in Path(f"/proc/{os.getpid()}/fd").iterdir() if "inotify" in _link(p)]
    # this process has the shell's own watchers elsewhere in a full run: count the change
    rig.fake.stop()
    assert rig.until(lambda s: s is None)
    time.sleep(0.2)
    during = [p for p in Path(f"/proc/{os.getpid()}/fd").iterdir() if "inotify" in _link(p)]
    assert len(during) == len(fds) + 1
    rig.fake.start()
    assert rig.until(lambda s: isinstance(s, AudioState))
    time.sleep(0.2)
    after = [p for p in Path(f"/proc/{os.getpid()}/fd").iterdir() if "inotify" in _link(p)]
    assert len(after) == len(fds)


def _link(path: Path) -> str:
    try:
        return os.readlink(path)
    except OSError:
        return ""
