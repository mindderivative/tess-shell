"""What the Audio module needs from any route (Audio Access Spike > What the Audio Module Needs).

Every candidate route (A to D) turns the sound server's state into one :class:`AudioState` and
calls ``on_state`` on its own thread/loop whenever that state changed, with no timer. The three
setters act on the DEFAULT output (volume, mute) or name an output (default switch).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True, slots=True)
class Output:
    name: str
    description: str
    form_factor: str  # device.form_factor: speaker, headphone, hdmi, headset, ... ("" if none)
    bus: str  # device.bus: alsa, bluetooth, usb, ... ("" if none)
    port: str  # the active port name ("" if the device has no ports)


@dataclass(frozen=True, slots=True)
class AudioState:
    sink: Output | None  # the default output; None when the server has no sink
    volume: int  # percent of the default output, 0 if none (may exceed 100)
    muted: bool
    source_name: str  # the default input ("" if none)
    source_muted: bool
    outputs: tuple[Output, ...] = field(default_factory=tuple)  # every sink, for the Menu


OnState = Callable[[AudioState], None]


class Route(Protocol):
    """One way of reaching the sound server. Lives on its own loop (the ``dbus`` thread's)."""

    async def start(self, on_state: OnState) -> None: ...
    async def stop(self) -> None: ...
    async def set_volume(self, percent: int) -> None: ...
    async def set_muted(self, muted: bool) -> None: ...
    async def set_default_output(self, name: str) -> None: ...
    def child_pids(self) -> list[int]: ...  # processes the route spawned (for the idle count)


Starter = Callable[[], Awaitable[Route]]
