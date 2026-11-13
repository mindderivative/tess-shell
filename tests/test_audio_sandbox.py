"""The sound client, service and Audio module against the REAL protocol of a private PipeWire
stack (Audio Module > Acceptance Criteria), inside the bwrap sandbox of the T-018 spike.

These tests change the state of a sound server (volume, mute, default output, devices, restarts), so
they run only where no real server exists: ``guard.require_sandbox()`` is the first thing each test
does and aborts the run outside the sandbox (the real ``/run/user/<uid>`` is hidden by a tmpfs, the
canary connection to the real pulse socket must fail with ENOENT). A normal ``pytest`` deselects
them (marker ``audio_sandbox``). Run them with

    env -u WAYLAND_DISPLAY -u DISPLAY python -m tests.spikes.audio.run_sandbox_tests

The stack, its null sinks (``spike_speaker`` speaker/usb, ``spike_phones`` headphone/bluetooth), the
virtual microphone ``spike_mic`` and every ``pactl`` call are the private ones of
``tests/spikes/audio/stack.py``. Null sinks have no ports: the port type is proven by the in-process
fake only (``tests/test_audio_service.py``).
"""

from __future__ import annotations

import asyncio
import statistics
import time
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from tess_shell.services.api import AudioError, AudioState
from tess_shell.services.audio import AudioService
from tess_shell.services.bus import ServiceThread
from tess_shell.services.pulse_native import NORM, PulseClient
from tests.fake_dbus import wait_for
from tests.spikes.audio.guard import require_sandbox
from tests.spikes.audio.stack import PrivateStack
from tests.widgets_live import running

pytestmark = pytest.mark.audio_sandbox

SPEAKER, PHONES, MIC = "spike_speaker", "spike_phones", "spike_mic"


@pytest.fixture(autouse=True)
def sandbox() -> None:
    require_sandbox()  # first: SystemExit outside the sandbox (guard and canary)


@pytest.fixture(scope="module")
def stack() -> Iterator[PrivateStack]:
    require_sandbox()
    with PrivateStack() as s:
        s.prove_isolation()
        yield s


def reset(stack: PrivateStack) -> None:
    stack.pactl("set-default-sink", SPEAKER)
    stack.pactl("set-default-source", MIC)
    for name in (SPEAKER, PHONES):
        stack.pactl("set-sink-volume", name, "100%")
        stack.pactl("set-sink-mute", name, "0")
    stack.pactl("set-source-mute", MIC, "0")


class Rig:
    """An AudioService on its own service thread, pointed at the private stack's socket (never the
    environment), and the states a subscriber saw."""

    def __init__(self, stack: PrivateStack) -> None:
        self.stack = stack
        self.thread = ServiceThread()
        self.thread.start()
        self.audio = AudioService(self.thread, stack.socket, env={})
        self.helper = self.audio.for_module("Test")
        self.states: list[tuple[int, AudioState | None]] = []
        self.helper.on_changed(lambda s: self.states.append((time.monotonic_ns(), s)))

    @property
    def last(self) -> AudioState | None:
        return self.states[-1][1] if self.states else None

    def until(self, pred: Callable[[AudioState | None], object], timeout: float = 5.0) -> bool:
        return wait_for(lambda: bool(self.states) and bool(pred(self.last)), timeout)

    def close(self) -> None:
        self.helper.close()
        self.thread.stop()


@pytest.fixture
def rig(stack: PrivateStack) -> Iterator[Rig]:
    reset(stack)
    r = Rig(stack)
    assert r.until(lambda s: s is not None)
    yield r
    r.close()
    reset(stack)


def volume_of(stack: PrivateStack, name: str) -> list[int]:
    """The channel levels of a sink, in percent, read back with the private ``pactl``."""
    out = stack.pactl("get-sink-volume", name).stdout
    return [int(x.split("/")[1].strip().rstrip("%")) for x in out.split(",") if "/" in x]


def test_the_stack_is_private_and_has_only_the_spike_devices(stack: PrivateStack) -> None:
    names = {
        line.split("\t")[1]
        for line in stack.pactl("list", "short", "sinks").stdout.split("\n")
        if line
    }
    assert names <= {"auto_null", SPEAKER, PHONES}, names
    assert str(stack.socket).startswith("/tmp/asp-")


def test_the_client_negotiates_the_version_and_reads_the_devices(stack: PrivateStack) -> None:
    async def go() -> None:
        client = PulseClient(stack.socket)
        await client.connect()
        try:
            assert client.version >= 34  # PipeWire 1.x speaks protocol 35
            server, sinks, sources = await client.snapshot()
            assert server.default_sink in (SPEAKER, PHONES)
            by_name = {s.name: s for s in sinks}
            assert by_name[SPEAKER].props["device.form_factor"] == "speaker"
            assert by_name[SPEAKER].props["device.bus"] == "usb"
            assert by_name[PHONES].props["device.bus"] == "bluetooth"
            assert by_name[SPEAKER].percent == 100 and len(by_name[SPEAKER].volume) == 2
            assert MIC in {s.name for s in sources}
        finally:
            client.close()

    asyncio.run(go())


def test_the_first_state_and_the_kinds(rig: Rig) -> None:
    state = rig.last
    assert state is not None and state.output is not None
    assert (state.output.name, state.output.kind) == (SPEAKER, "SPEAKER")
    assert state.volume == 100 and not state.muted and state.has_mic and not state.mic_muted
    kinds = {o.name: o.kind for o in state.outputs}
    assert kinds[SPEAKER] == "SPEAKER" and kinds[PHONES] == "BLUETOOTH"  # the bus wins


def test_a_change_by_another_client_arrives_as_a_state(rig: Rig) -> None:
    s = rig.stack
    s.pactl("set-sink-volume", SPEAKER, "31%")
    assert rig.until(lambda st: st is not None and st.volume == 31)
    s.tool(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "0.47"])
    assert rig.until(lambda st: st is not None and st.volume == 47)
    s.pactl("set-sink-mute", SPEAKER, "1")
    assert rig.until(lambda st: st is not None and st.muted)
    s.pactl("set-source-mute", MIC, "1")
    assert rig.until(lambda st: st is not None and st.mic_muted)
    s.pactl("set-default-sink", PHONES)
    assert rig.until(
        lambda st: st is not None and st.output is not None and st.output.name == PHONES
    )
    module = s.add_null_sink("spike_extra", "hdmi")
    assert rig.until(lambda st: st is not None and len(st.outputs) == 3)
    kinds = {o.name: o.kind for o in (rig.last.outputs if rig.last else ())}
    assert kinds["spike_extra"] == "HDMI"
    s.pactl("unload-module", module)
    assert rig.until(lambda st: st is not None and len(st.outputs) == 2)


def test_the_setters_change_the_private_server_as_pactl_reads_it_back(rig: Rig) -> None:
    s, h = rig.stack, rig.helper
    h.set_volume(42).result(5)
    assert volume_of(s, SPEAKER) == [42, 42]
    h.set_volume(150).result(5)
    assert volume_of(s, SPEAKER) == [100, 100]  # clamped
    h.set_volume(60).result(5)
    assert rig.until(lambda st: st is not None and st.volume == 60)
    h.step(5).result(5)
    assert rig.until(lambda st: st is not None and st.volume == 65)
    h.step(-70).result(5)
    assert rig.until(lambda st: st is not None and st.volume == 0)
    h.toggle_mute().result(5)
    assert "yes" in s.pactl("get-sink-mute", SPEAKER).stdout
    h.toggle_mute().result(5)
    assert rig.until(lambda st: st is not None and not st.muted)
    assert "no" in s.pactl("get-sink-mute", SPEAKER).stdout
    h.toggle_mic().result(5)
    assert "yes" in s.pactl("get-source-mute", MIC).stdout
    h.set_output(PHONES).result(5)
    assert PHONES in s.pactl("get-default-sink").stdout
    with pytest.raises(AudioError):
        h.set_output("no-such-sink").result(5)


def test_a_balance_between_channels_is_kept_by_scaling(rig: Rig) -> None:
    s = rig.stack
    s.pactl("set-sink-volume", SPEAKER, "80%", "40%")
    assert rig.until(lambda st: st is not None and st.volume == 60)
    rig.helper.set_volume(30).result(5)
    left, right = volume_of(s, SPEAKER)
    assert (left, right) == (40, 20) or (abs(left - 40) <= 1 and abs(right - 20) <= 1)


def test_a_volume_above_100_is_shown_as_it_is(rig: Rig) -> None:
    rig.stack.pactl("set-sink-volume", SPEAKER, "120%")
    assert rig.until(lambda st: st is not None and st.volume == 120)


def test_the_module_hides_and_shows_when_pipewire_pulse_restarts(rig: Rig) -> None:
    s = rig.stack
    s.kill_pulse()
    assert rig.until(lambda st: st is None)
    s.start_pulse()
    assert rig.until(lambda st: st is not None, 15)
    s.pactl("set-sink-volume", SPEAKER, "66%")
    assert rig.until(lambda st: st is not None and st.volume == 66)
    rig.helper.set_volume(55).result(5)
    assert volume_of(s, SPEAKER) == [55, 55]


def test_the_module_hides_and_shows_when_pipewire_itself_restarts(rig: Rig) -> None:
    s = rig.stack
    s.restart_pipewire()
    assert rig.until(lambda st: st is not None, 20)  # after the gap, the state is back
    assert any(st is None for _, st in rig.states)  # and it was hidden for the gap
    reset(s)
    assert rig.until(lambda st: st is not None and st.output is not None)
    rig.helper.set_volume(35).result(5)
    assert volume_of(s, SPEAKER) == [35, 35]


def test_the_latency_of_a_change_is_a_few_milliseconds(rig: Rig) -> None:
    """From the change made by another client (a native-protocol driver) to the state in Python."""

    async def go() -> list[float]:
        driver = PulseClient(rig.stack.socket)
        await driver.connect("t029-driver")
        _info, sinks, _sources = await driver.snapshot()
        index = next(d.index for d in sinks if d.name == SPEAKER)
        out: list[float] = []
        for i in range(30):
            await asyncio.sleep(0.03)
            want = 10 + i
            n = len(rig.states)
            t0 = time.monotonic_ns()
            await driver.set_sink_volume(index, [round(want * NORM / 100)] * 2)
            for _ in range(500):
                hit = [t for t, st in rig.states[n:] if st is not None and st.volume == want]
                if hit:
                    out.append((hit[0] - t0) / 1e6)
                    break
                await asyncio.sleep(0.001)
        driver.close()
        return out

    values = asyncio.run(go())
    assert len(values) == 30
    print(
        f"\nlatency (service state): median {statistics.median(values):.2f} ms, "
        f"worst {max(values):.2f} ms"
    )
    assert statistics.median(values) < 5.0


def test_the_audio_module_follows_the_private_server(rig: Rig) -> None:
    s = rig.stack
    with running("Audio { }", audio=rig.audio) as w:
        key = next(u for u in w.uses if u.startswith("Audio@"))

        def until(pred: Callable[[], object], timeout: float = 5.0) -> bool:
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                w.flush()
                w.advance(16)
                if pred():
                    return True
                time.sleep(0.004)
            return False

        values: Any = w.store.values[key]
        assert until(lambda: values.get("ready") is True)
        assert values["name"] == "Spike Speaker" and values["icon"] == "volume-high"
        s.pactl("set-sink-volume", SPEAKER, "20%")
        assert until(lambda: values["volume"] == 20 and values["icon"] == "volume-low")
        w.window.simulate("click", node=w.of_use("Audio", "Toggle"))
        assert until(lambda: values["muted"] is True)
        assert "yes" in s.pactl("get-sink-mute", SPEAKER).stdout
        s.pactl("set-default-sink", PHONES)
        assert until(lambda: values["kind"] == "BLUETOOTH" and values["icon"] == "bluetooth-audio")
        w.host.stop_all()


def test_idle_over_60_s_the_service_thread_does_not_wake(rig: Rig) -> None:
    """The client's own cost with no change (the thread's timeslices, voluntary switches and CPU
    from ``/proc``), and the cost of the three private servers beside it. 60 s."""
    import os
    import threading
    from pathlib import Path

    async def native_id() -> int:
        return threading.get_native_id()

    tid = rig.thread.submit(native_id()).result(3)

    def counters(pid: int, task: int) -> tuple[int, int, int]:
        base = Path(f"/proc/{pid}/task/{task}")
        cpu, _wait, slices = (int(x) for x in (base / "schedstat").read_text().split())
        voluntary = 0
        for line in (base / "status").read_text().splitlines():
            if line.startswith("voluntary_ctxt_switches"):
                voluntary = int(line.split()[1])
        return cpu, slices, voluntary

    def process(pid: int) -> tuple[int, int]:
        cpu = slices = 0
        for task in Path(f"/proc/{pid}/task").iterdir():
            c, s, _v = counters(pid, int(task.name))
            cpu, slices = cpu + c, slices + s
        return cpu, slices

    servers = {n: rig.stack.pid(n) for n in ("pipewire", "wireplumber", "pipewire-pulse")}
    time.sleep(1.0)
    before = counters(os.getpid(), tid)
    servers_before = {n: process(p) for n, p in servers.items()}
    time.sleep(60.0)
    after = counters(os.getpid(), tid)
    servers_after = {n: process(p) for n, p in servers.items()}
    delta = tuple(a - b for a, b in zip(after, before, strict=True))
    print(
        f"\nidle 60 s (client thread): cpu {delta[0]} ns, timeslices {delta[1]}, "
        f"voluntary switches {delta[2]}; servers (cpu ns, timeslices): "
        + ", ".join(
            f"{n} {servers_after[n][0] - servers_before[n][0]}/"
            f"{servers_after[n][1] - servers_before[n][1]}"
            for n in servers
        )
    )
    assert (delta[1], delta[2]) == (0, 0)
