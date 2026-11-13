"""Route A: the PulseAudio native protocol, spoken by the shell itself (pulse_native.py).

The glue the Audio module would own: connect with a back-off, subscribe, turn an event into ONE
refresh (server info, sinks and sources in one round trip; an event that arrives while a refresh
runs only marks it dirty, so there is no timer and no debounce), and call ``on_state`` when the
state differs from the last one.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from tests.spikes.audio.guard import require_private_path
from tests.spikes.audio.model import AudioState, OnState, Output
from tests.spikes.audio.pulse_native import (
    FACILITY_SERVER,
    FACILITY_SINK,
    FACILITY_SOURCE,
    Device,
    PulseClient,
)

BACKOFF = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 30.0)


def output_of(dev: Device) -> Output:
    return Output(
        dev.name,
        dev.props.get("device.description") or dev.description,
        dev.props.get("device.form_factor", ""),
        dev.props.get("device.bus", ""),
        dev.active_port,
    )


class RouteA:
    def __init__(self, socket: Path, cookie: bytes = bytes(256)) -> None:
        require_private_path(socket)
        self._socket, self._cookie = str(socket), cookie
        self._client: PulseClient | None = None
        self._on_state: OnState | None = None
        self._last: AudioState | None = None
        self._sinks: list[Device] = []
        self._sources: list[Device] = []
        self._default_sink = ""
        self._busy = False
        self._dirty = False
        self._task: asyncio.Task[None] | None = None
        self._stopped = False

    def child_pids(self) -> list[int]:
        return []

    async def start(self, on_state: OnState) -> None:
        self._on_state = on_state
        self._task = asyncio.create_task(self._supervise())

    async def stop(self) -> None:
        self._stopped = True
        if self._task is not None:
            self._task.cancel()
        if self._client is not None:
            self._client.close()

    async def _supervise(self) -> None:
        """Keep a connection: connect, subscribe, refresh; when it drops, back off and retry."""
        attempt = 0
        while not self._stopped:
            lost = asyncio.Event()
            client = PulseClient(self._socket, self._event, lost.set, self._cookie)
            try:
                await client.connect()
                await client.subscribe()
                self._client = client
                attempt = 0
                await self._refresh()
                await lost.wait()
            except OSError, ConnectionError, TimeoutError:
                pass
            finally:
                client.close()
                self._client = None
            self._emit(None)  # no sound server: the module hides itself
            await asyncio.sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
            attempt += 1

    def _event(self, facility: int, kind: int, index: int) -> None:
        if facility in (FACILITY_SINK, FACILITY_SOURCE, FACILITY_SERVER):
            self._dirty = True
            if not self._busy:
                asyncio.get_running_loop().create_task(self._refresh())

    async def _refresh(self) -> None:
        client = self._client
        if client is None or self._busy:
            return
        self._busy = True
        try:
            while self._dirty or self._last is None:
                self._dirty = False
                server, self._sinks, self._sources = await client.snapshot()
                self._default_sink = server.default_sink
                self._emit(self._state(server.default_source))
        except ConnectionError, TimeoutError:
            pass  # the connection is gone; _supervise sees it
        finally:
            self._busy = False

    def _state(self, default_source: str) -> AudioState:
        sink = next((d for d in self._sinks if d.name == self._default_sink), None)
        source = next((d for d in self._sources if d.name == default_source), None)
        return AudioState(
            output_of(sink) if sink else None,
            sink.percent if sink else 0,
            sink.mute if sink else False,
            source.name if source else "",
            source.mute if source else False,
            tuple(output_of(d) for d in self._sinks),
        )

    def _emit(self, state: AudioState | None) -> None:
        if state is None:
            if self._last is not None and self._on_state is not None:
                self._last = None
                self._on_state(AudioState(None, 0, False, "", False))
            return
        if state != self._last and self._on_state is not None:
            self._last = state
            self._on_state(state)

    # setters -------------------------------------------------------------------------------
    def _default(self) -> Device:
        for dev in self._sinks:
            if dev.name == self._default_sink:
                return dev
        raise RuntimeError("no default output")

    async def set_volume(self, percent: int) -> None:
        assert self._client is not None
        dev = self._default()
        await self._client.set_sink_volume(dev.index, percent, len(dev.volume))

    async def set_muted(self, muted: bool) -> None:
        assert self._client is not None
        await self._client.set_sink_mute(self._default().index, muted)

    async def set_default_output(self, name: str) -> None:
        assert self._client is not None
        await self._client.set_default_sink(name)
