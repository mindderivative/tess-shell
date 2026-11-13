"""The Audio: the default sound output (Audio Module). It follows the sound server through
``ctx.audio`` (the shell's own client of the PulseAudio native protocol, ADR-0021): the callback
runs on the ``dbus`` thread when the server says something changed, derives the values and sends
only the ones that changed. No timer, no thread, no subprocess. One instance serves every use.

Keys sent: ``ready`` (a sound server is connected), ``volume`` (percent, the mean of the channels;
above 100 as the server says), ``volume_text`` (``"45 %"``), ``muted``, ``kind`` (``SPEAKER``,
``HEADPHONES``, ``HDMI``, ``BLUETOOTH`` or ``OTHER``), ``name`` (the output's description),
``mic_muted``, ``has_mic``, ``outputs`` (a list of ``id``, ``name``, ``kind``, ``icon``,
``current``), ``icon``, ``tooltip`` and ``label`` (the accessible name). A layout shows itself with
``Visible: {{ ready }}``.

The module does not predict a change: the setters call the server and the values change when its
event arrives. While the user drags a slider the module sends no ``volume`` for that use (the
handle is the user's) and sends the final value on release.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from tess_shell import Module, action

if TYPE_CHECKING:
    from tess_shell.module import Event
    from tess_shell.modules.context import UseRecord
    from tess_shell.services.api import AudioState, Output, Subscription

DRAG_EVERY = 0.05  # seconds between two volume writes of one drag: at most 20 a second
POPUP = "Audio_Outputs"

# every icon the module can send; a test checks each against the shipped ``mdi`` set
KIND_ICONS = {
    "SPEAKER": "speaker",
    "OTHER": "speaker",
    "HEADPHONES": "headphones",
    "HDMI": "hdmi-port",
    "BLUETOOTH": "bluetooth-audio",
}
VOLUME_STEPS = ("volume-mute", "volume-low", "volume-medium", "volume-high")
ICONS = frozenset(
    {
        *KIND_ICONS.values(),
        *VOLUME_STEPS,
        "volume-off",
        "headphones-off",
        "microphone-off",
    }
)


def level_icon(kind: str, volume: int, muted: bool) -> str:
    """The icon of the default output (Audio Module > Kind and Icon)."""
    if muted:
        return "headphones-off" if kind == "HEADPHONES" else "volume-off"
    if kind == "HEADPHONES":
        return "headphones"
    if kind == "BLUETOOTH":
        return "bluetooth-audio"
    if volume <= 0:
        return VOLUME_STEPS[0]
    return VOLUME_STEPS[1 if volume <= 33 else 2 if volume <= 66 else 3]


def tooltip_text(name: str, volume: int, muted: bool) -> str:
    """``Razer Leviathan V2 X, 45 %`` or ``..., muted``."""
    return f"{name}, muted" if muted else f"{name}, {volume} %"


def output_entry(output: Output, current: bool) -> dict[str, Any]:
    return {
        "id": output.name,
        "name": output.description,
        "kind": output.kind,
        "icon": KIND_ICONS.get(output.kind, "speaker"),
        "current": current,
    }


class Audio(Module):
    def __init__(self) -> None:
        self.sent: dict[str, Any] = {}
        self.state: AudioState | None = None
        self.dragging: set[str] = set()
        self.last_write = float("-inf")  # the monotonic time of the last drag write
        self.monotonic: Callable[[], float] = time.monotonic  # a test swaps it
        self.send_lock = threading.Lock()  # a callback and a drag are two threads
        self.subscription: Subscription | None = None

    def validate_use(self, use: UseRecord) -> None:
        step = use.params.get("step")
        if isinstance(step, int | float) and not 0 < step <= 100:
            raise ValueError(f"step is {step}; it must be above 0 and at most 100 (percent)")

    def start(self) -> None:
        # defaults, so a layout reading any key has a value before the server has answered
        self.publish(self.values(None))
        self.subscription = self.ctx.audio.on_changed(self.changed)

    def stop(self) -> None:
        if self.subscription is not None:
            self.subscription.cancel()
            self.subscription = None

    def use_added(self, use: UseRecord) -> None:
        with self.send_lock:
            for key, value in list(self.sent.items()):
                self.ctx.send(key, value, use=use)

    def use_removed(self, use: UseRecord) -> None:
        self.dragging.discard(use.key)

    # -- the server's state (dbus thread) ---------------------------------------------------------

    def changed(self, state: AudioState | None) -> None:
        self.state = state
        self.publish(self.values(state))

    def values(self, state: AudioState | None) -> dict[str, Any]:
        if state is None:
            return {
                "ready": False,
                "volume": 0,
                "volume_text": "0 %",
                "muted": False,
                "kind": "SPEAKER",
                "name": "",
                "mic_muted": False,
                "has_mic": False,
                "outputs": [],
                "icon": "volume-off",
                "tooltip": "",
                "label": "Audio",
            }
        output = state.output
        if output is None:
            return {
                "ready": True,
                "volume": 0,
                "volume_text": "0 %",
                "muted": False,
                "kind": "SPEAKER",
                "name": "",
                "mic_muted": state.mic_muted,
                "has_mic": state.has_mic,
                "outputs": [],
                "icon": "volume-off",
                "tooltip": "No output",
                "label": "Audio, no output",
            }
        tip = tooltip_text(output.description, state.volume, state.muted)
        default = output.name
        return {
            "ready": True,
            "volume": state.volume,
            "volume_text": f"{state.volume} %",
            "muted": state.muted,
            "kind": output.kind,
            "name": output.description,
            "mic_muted": state.mic_muted,
            "has_mic": state.has_mic,
            "outputs": [output_entry(o, o.name == default) for o in state.outputs],
            "icon": level_icon(output.kind, state.volume, state.muted),
            "tooltip": tip,
            "label": f"Audio, {tip}",
        }

    def publish(self, values: dict[str, Any]) -> None:
        """Send what changed since the last send: a refresh that changes nothing sends nothing."""
        with self.send_lock:
            for key, value in values.items():
                if key in ("volume", "volume_text") and self.dragging:
                    continue  # the user holds the handle
                if key not in self.sent or self.sent[key] != value:
                    self.sent[key] = value
                    self.ctx.send(key, value)

    # -- the actions (loop thread) ----------------------------------------------------------------

    @action
    def toggle_mute(self, event: Event) -> None:
        self.ctx.audio.toggle_mute()

    @action
    def toggle_mic(self, event: Event) -> None:
        self.ctx.audio.toggle_mic()

    @action
    def step(self, event: Event, delta: float) -> None:
        """Change the volume by ``delta`` percent (the layout gives ``step`` times the way)."""
        self.ctx.audio.step(float(delta))

    @action
    def drag(self, event: Event, percent: float) -> None:
        """The slider's handle moved by the user: write at most every 50 ms; the release writes the
        final value."""
        if event.use:
            self.dragging.add(event.use)
        value = min(max(float(percent), 0.0), 100.0)
        self.ctx.send("volume_text", f"{round(value)} %")
        now = self.monotonic()
        if now - self.last_write >= DRAG_EVERY:
            self.last_write = now
            self.ctx.audio.set_volume(value)

    @action
    def set_volume(self, event: Event, percent: float) -> None:
        """Set the volume (clamped to 0 to 100); a slider's release sends its final value here."""
        self.dragging.discard(event.use)
        value = min(max(float(percent), 0.0), 100.0)
        self.last_write = self.monotonic()
        self.ctx.audio.set_volume(value)
        self.resync(round(value))

    def resync(self, final: int) -> None:
        """After a drag: forget what was sent for the volume, so the server's next report of it
        is sent even if it equals the value before the drag. When the server already holds the
        final value (the last drag write was it, so no event is coming) send it now."""
        with self.send_lock:
            self.sent.pop("volume", None)
            self.sent.pop("volume_text", None)
        state = self.state
        if state is not None and state.volume == final and not self.dragging:
            self.publish({"volume": state.volume, "volume_text": f"{state.volume} %"})

    @action
    def set_output(self, event: Event, id: str) -> None:
        self.ctx.audio.set_output(id)

    @action
    def show_outputs(self, event: Event) -> None:
        """Open the Popup ``Audio_Outputs`` with the outputs as they are now."""
        self.ctx.popup(POPUP, data={"outputs": list(self.sent.get("outputs", []))})
