"""Route C: a ``pactl subscribe`` subprocess for events, ``pactl`` for reads and writes.

Run under ``asyncio.create_subprocess_exec``. Needs ``pactl`` (libpulse-utils). One event refreshes
the state with three concurrent ``pactl --format=json`` calls (info, list sinks, list sources); an
event that arrives meanwhile only marks the state dirty.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping
from typing import Any

from tests.spikes.audio.guard import checked_env
from tests.spikes.audio.model import AudioState, OnState, Output

BACKOFF = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 30.0)
NORM = 65536


def output_of(sink: Mapping[str, Any]) -> Output:
    props = sink.get("properties", {})
    return Output(
        sink["name"],
        props.get("device.description") or sink.get("description", ""),
        props.get("device.form_factor", ""),
        props.get("device.bus", ""),
        sink.get("active_port") or "",
    )


def volume_percent(dev: Mapping[str, Any]) -> int:
    values = [c["value"] for c in dev.get("volume", {}).values()]
    return round(sum(values) / len(values) * 100 / NORM) if values else 0


class RouteC:
    def __init__(self, env: Mapping[str, str]) -> None:
        self._env = checked_env(env)
        self._on_state: OnState | None = None
        self._last: AudioState | None = None
        self._proc: asyncio.subprocess.Process | None = None
        self._busy = False
        self._dirty = False
        self._task: asyncio.Task[None] | None = None
        self._stopped = False

    def child_pids(self) -> list[int]:
        return [self._proc.pid] if self._proc is not None and self._proc.returncode is None else []

    async def start(self, on_state: OnState) -> None:
        self._on_state = on_state
        self._task = asyncio.create_task(self._supervise())

    async def stop(self) -> None:
        self._stopped = True
        if self._task is not None:
            self._task.cancel()
        if self._proc is not None and self._proc.returncode is None:
            self._proc.kill()

    async def _pactl(self, *args: str) -> str:
        proc = await asyncio.create_subprocess_exec(
            "pactl",
            *args,
            env=self._env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await proc.communicate()
        if proc.returncode != 0:
            raise ConnectionError(f"pactl {args[0]} exited {proc.returncode}")
        return out.decode()

    async def _supervise(self) -> None:
        attempt = 0
        while not self._stopped:
            self._proc = await asyncio.create_subprocess_exec(
                "pactl",
                "subscribe",
                env=self._env,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            assert self._proc.stdout is not None
            try:
                await self._refresh()
                attempt = 0
                async for line in self._proc.stdout:  # "Event 'change' on sink #49"
                    if b" on sink #" in line or b" on source #" in line or b" on server" in line:
                        self._dirty = True
                        if not self._busy:
                            asyncio.create_task(self._refresh())
            except ConnectionError:
                pass
            if self._proc.returncode is None:
                self._proc.kill()
            await self._proc.wait()
            self._emit(AudioState(None, 0, False, "", False))
            await asyncio.sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
            attempt += 1

    async def _refresh(self) -> None:
        if self._busy:
            return
        self._busy = True
        try:
            self._dirty = True
            while self._dirty:
                self._dirty = False
                info, sinks, sources = await asyncio.gather(
                    self._pactl("--format=json", "info"),
                    self._pactl("--format=json", "list", "sinks"),
                    self._pactl("--format=json", "list", "sources"),
                )
                self._emit(self._state(json.loads(info), json.loads(sinks), json.loads(sources)))
        except ConnectionError, ValueError:
            pass
        finally:
            self._busy = False

    @staticmethod
    def _state(info: Mapping[str, Any], sinks: list[Any], sources: list[Any]) -> AudioState:
        sink = next((s for s in sinks if s["name"] == info["default_sink_name"]), None)
        source = next((s for s in sources if s["name"] == info["default_source_name"]), None)
        return AudioState(
            output_of(sink) if sink else None,
            volume_percent(sink) if sink else 0,
            bool(sink["mute"]) if sink else False,
            source["name"] if source else "",
            bool(source["mute"]) if source else False,
            tuple(output_of(s) for s in sinks),
        )

    def _emit(self, state: AudioState) -> None:
        if state != self._last and self._on_state is not None:
            self._last = state
            self._on_state(state)

    async def set_volume(self, percent: int) -> None:
        await self._pactl("set-sink-volume", "@DEFAULT_SINK@", f"{percent}%")

    async def set_muted(self, muted: bool) -> None:
        await self._pactl("set-sink-mute", "@DEFAULT_SINK@", "1" if muted else "0")

    async def set_default_output(self, name: str) -> None:
        await self._pactl("set-default-sink", name)
