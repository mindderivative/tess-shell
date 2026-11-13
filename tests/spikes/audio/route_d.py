"""Route D: ``pw-dump --monitor`` (JSON) for state and events, ``wpctl`` for writes.

``pw-dump --monitor`` prints the whole object graph as a JSON array, then one array per change
(objects that went away have ``"info": null``). Volume and mute are read from a node's ``Props``
param; the default sink and source from the ``default`` Metadata object. Node volume is the
CUBIC-scale value ``wpctl`` uses (``Props.volume``); on a hardware sink the hardware mixer lives in
the device's ``Route`` param, which this route does not read (the null sinks of the spike have no
device) and which is why D is reported as unproven for real hardware.
"""

from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Mapping
from typing import Any

from tests.spikes.audio.guard import checked_env
from tests.spikes.audio.model import AudioState, OnState, Output

BACKOFF = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 30.0)
NODE = "PipeWire:Interface:Node"
METADATA = "PipeWire:Interface:Metadata"


class RouteD:
    def __init__(self, env: Mapping[str, str]) -> None:
        self._env = checked_env(env)
        self._on_state: OnState | None = None
        self._last: AudioState | None = None
        self._proc: asyncio.subprocess.Process | None = None
        self._objects: dict[int, dict[str, Any]] = {}
        self._defaults: dict[str, str] = {}
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

    async def _wpctl(self, *args: str) -> None:
        proc = await asyncio.create_subprocess_exec(
            "wpctl",
            *args,
            env=self._env,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        if await proc.wait() != 0:
            raise ConnectionError(f"wpctl {args[0]} failed")

    async def _supervise(self) -> None:
        attempt = 0
        while not self._stopped:
            self._objects.clear()
            self._defaults.clear()
            self._proc = await asyncio.create_subprocess_exec(
                "pw-dump",
                "--monitor",
                env=self._env,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
                limit=1 << 22,
            )
            assert self._proc.stdout is not None
            batch: list[bytes] = []
            async for line in self._proc.stdout:
                batch.append(line)
                if line.rstrip() == b"]":  # one JSON array per change, closed at column 0
                    attempt = 0
                    self._apply(json.loads(b"".join(batch)))
                    batch.clear()
            if self._proc.returncode is None:
                self._proc.kill()
            await self._proc.wait()
            self._emit(AudioState(None, 0, False, "", False))
            await asyncio.sleep(BACKOFF[min(attempt, len(BACKOFF) - 1)])
            attempt += 1

    def _apply(self, objects: list[dict[str, Any]]) -> None:
        for obj in objects:
            if obj.get("info") is None and obj.get("type") != METADATA:
                self._objects.pop(obj["id"], None)
            elif obj["type"] == NODE:
                self._objects[obj["id"]] = obj
            elif obj["type"] == METADATA and obj.get("props", {}).get("metadata.name") == "default":
                for item in obj.get("metadata", []):
                    value = item.get("value")
                    if isinstance(value, dict):
                        self._defaults[item["key"]] = value.get("name", "")
        self._emit(self._state())

    @staticmethod
    def _props(node: Mapping[str, Any]) -> Mapping[str, Any]:
        for param in node.get("info", {}).get("params", {}).get("Props", []):
            if "volume" in param or "mute" in param:
                return param  # type: ignore[no-any-return]
        return {}

    @staticmethod
    def _output(node: Mapping[str, Any]) -> Output:
        props = node["info"]["props"]
        return Output(
            props["node.name"],
            props.get("node.description", ""),
            props.get("device.form_factor", ""),
            props.get("device.bus", ""),
            "",
        )

    def _state(self) -> AudioState:
        sinks = [n for n in self._objects.values() if _cls(n) == "Audio/Sink"]
        sources = [n for n in self._objects.values() if _cls(n).startswith("Audio/Source")]
        default_sink = self._defaults.get("default.audio.sink")
        sink = next((n for n in sinks if _name(n) == default_sink), None)
        source = next(
            (n for n in sources if _name(n) == self._defaults.get("default.audio.source")), None
        )
        props = self._props(sink) if sink else {}
        return AudioState(
            self._output(sink) if sink else None,
            _percent(props) if sink else 0,
            bool(props.get("mute", False)),
            _name(source) if source else "",
            bool(self._props(source).get("mute", False)) if source else False,
            tuple(self._output(n) for n in sinks),
        )

    def _emit(self, state: AudioState) -> None:
        if state != self._last and self._on_state is not None:
            self._last = state
            self._on_state(state)

    async def set_volume(self, percent: int) -> None:
        await self._wpctl("set-volume", "@DEFAULT_AUDIO_SINK@", f"{percent}%")

    async def set_muted(self, muted: bool) -> None:
        await self._wpctl("set-mute", "@DEFAULT_AUDIO_SINK@", "1" if muted else "0")

    async def set_default_output(self, name: str) -> None:
        node = next((n for n in self._objects.values() if _name(n) == name), None)
        if node is None:
            raise KeyError(name)
        await self._wpctl("set-default", str(node["id"]))


def _percent(props: Mapping[str, Any]) -> int:
    """The master ``volume`` times the mean of ``channelVolumes`` (both linear), on the cubic scale
    pulse and wpctl show (what pactl calls 31 % is 0.31 ** 3 = 0.0298 in the param)."""
    channels: list[float] = props.get("channelVolumes") or [1.0]
    level = float(props.get("volume", 1.0)) * sum(channels) / len(channels)
    return round(math.cbrt(level) * 100)


def _cls(node: Mapping[str, Any]) -> str:
    return str(node["info"]["props"].get("media.class", ""))


def _name(node: Mapping[str, Any]) -> str:
    return str(node["info"]["props"].get("node.name", ""))
