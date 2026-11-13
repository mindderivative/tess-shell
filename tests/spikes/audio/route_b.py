"""Route B: ``pulsectl-asyncio`` (libpulse through ctypes, driven by the asyncio loop).

Needs ``pulsectl`` and ``pulsectl-asyncio`` on the path and ``libpulse.so.0`` on the system. The
spike installs them into a temp target (``/tmp/audio-spike-libs``), never into the project venv.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import pulsectl  # type: ignore[import-not-found]
import pulsectl_asyncio  # type: ignore[import-not-found]

from tests.spikes.audio.guard import require_private_env, require_private_path
from tests.spikes.audio.model import AudioState, OnState, Output

BACKOFF = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 30.0)


def output_of(sink: Any) -> Output:
    props = sink.proplist
    return Output(
        sink.name,
        props.get("device.description") or sink.description,
        props.get("device.form_factor", ""),
        props.get("device.bus", ""),
        sink.port_active.name if sink.port_active else "",
    )


class RouteB:
    def __init__(self, socket: Path) -> None:
        require_private_path(socket)
        require_private_env(os.environ)  # libpulse reads the environment too
        self._server = f"unix:{socket}"
        self._on_state: OnState | None = None
        self._last: AudioState | None = None
        self._pulse: Any = None
        self._default: Any = None
        self._task: asyncio.Task[None] | None = None

    def child_pids(self) -> list[int]:
        return []

    async def start(self, on_state: OnState) -> None:
        self._on_state = on_state
        self._task = asyncio.create_task(self._supervise())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
        if self._pulse is not None:
            self._pulse.close()

    async def _supervise(self) -> None:
        attempt = 0
        while True:
            pulse = pulsectl_asyncio.PulseAsync("tesserae-shell", server=self._server)
            try:
                await pulse.connect()
                self._pulse = pulse
                attempt = 0
                await self._refresh(pulse)
                async for _event in pulse.subscribe_events("sink", "source", "server"):
                    await self._refresh(pulse)
            except pulsectl.PulseError, pulsectl.PulseDisconnected, OSError:
                pass
            finally:
                self._pulse = None
                pulse.close()
            self._emit(AudioState(None, 0, False, "", False))
            await asyncio.sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
            attempt += 1

    async def _refresh(self, pulse: Any) -> None:
        info = await pulse.server_info()
        sinks = await pulse.sink_list()
        sources = await pulse.source_list()
        sink = next((s for s in sinks if s.name == info.default_sink_name), None)
        source = next((s for s in sources if s.name == info.default_source_name), None)
        self._default = sink
        self._emit(
            AudioState(
                output_of(sink) if sink else None,
                round(sink.volume.value_flat * 100) if sink else 0,
                bool(sink.mute) if sink else False,
                source.name if source else "",
                bool(source.mute) if source else False,
                tuple(output_of(s) for s in sinks),
            )
        )

    def _emit(self, state: AudioState) -> None:
        if state != self._last and self._on_state is not None:
            self._last = state
            self._on_state(state)

    async def set_volume(self, percent: int) -> None:
        await self._pulse.volume_set_all_chans(self._default, percent / 100)

    async def set_muted(self, muted: bool) -> None:
        await self._pulse.mute(self._default, muted)

    async def set_default_output(self, name: str) -> None:
        sink = await self._pulse.get_sink_by_name(name)
        await self._pulse.default_set(sink)
