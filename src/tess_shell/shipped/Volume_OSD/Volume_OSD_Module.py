"""The Volume_OSD: the volume on-screen display (M7h). It follows the sound server through
``ctx.audio`` itself (the Audio module need not be used anywhere) and, when the default output's
volume or mute changes, shows the Panel that holds it for ``duration`` milliseconds
(``ctx.surface.show``; the Panel's own ``Hide_After`` is replaced by it for that show).

Nothing is shown for the first reading of the server, for the first reading after the server came
back, for a change of the default output (its volume becomes the baseline), or for a change of the
microphone or of the list of outputs: only the default output's volume and mute are compared. The
module says nothing aloud (the Audio module's ``announce`` does), so a screen reader hears each
change once.

Keys sent: ``volume`` (percent, as the server says), ``bar`` (the volume held to 0 to 100),
``volume_text`` (``"45 %"``), ``readout`` (the volume text, or ``"Muted"``), ``muted``, ``icon``,
``name`` (the output's description) and ``label`` (the accessible name of the group).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from tess_shell import Module

if TYPE_CHECKING:
    from tess_shell.modules.context import UseRecord
    from tess_shell.services.api import AudioState, Subscription

DEFAULT_DURATION = 1500.0  # milliseconds, the param's default
MAX_DURATION = 60_000  # milliseconds: a minute is longer than any OSD should stay

# every icon the module can send; a test checks each against the shipped ``mdi`` set
ICONS = frozenset({"volume-off", "volume-mute", "volume-low", "volume-medium", "volume-high"})


def level_icon(volume: int, muted: bool) -> str:
    """The icon for the level: the crossed speaker when muted (the shape says it, not the colour),
    then one more wave for each third."""
    if muted:
        return "volume-off"
    if volume <= 0:
        return "volume-mute"
    return "volume-low" if volume <= 33 else "volume-medium" if volume <= 66 else "volume-high"


def label_text(name: str, volume: int, muted: bool) -> str:
    """``Volume, Razer Leviathan V2 X, 45 %`` or ``Volume, ..., muted``."""
    state = "muted" if muted else f"{volume} %"
    return f"Volume, {name}, {state}" if name else f"Volume, {state}"


def values(state: AudioState) -> dict[str, Any]:
    """What the layout shows for a state that has a default output."""
    output = state.output
    assert output is not None
    return {
        "volume": state.volume,
        "bar": min(max(state.volume, 0), 100),
        "volume_text": f"{state.volume} %",
        "readout": "Muted" if state.muted else f"{state.volume} %",
        "muted": state.muted,
        "icon": level_icon(state.volume, state.muted),
        "name": output.description,
        "label": label_text(output.description, state.volume, state.muted),
    }


class Volume_OSD(Module):
    def __init__(self) -> None:
        # (the default output's name, volume, muted) of the last state, or None before the first
        # reading and while there is no server; only the service thread reads and writes it
        self.baseline: tuple[str, int, bool] | None = None
        self.subscription: Subscription | None = None
        self.refused: set[str] = set()  # uses that are on no Panel: said once, then left alone

    def validate_use(self, use: UseRecord) -> None:
        duration = use.params.get("duration")
        if isinstance(duration, int | float) and not 0 < duration <= MAX_DURATION:
            raise ValueError(
                f"duration is {duration}; it must be above 0 and at most {MAX_DURATION} "
                "(milliseconds)"
            )

    def start(self) -> None:
        # defaults, so a layout reading any key has a value before the server has answered
        self.ctx.send("volume", 0)
        self.ctx.send("bar", 0)
        self.ctx.send("volume_text", "0 %")
        self.ctx.send("readout", "0 %")
        self.ctx.send("muted", False)
        self.ctx.send("icon", "volume-off")
        self.ctx.send("name", "")
        self.ctx.send("label", "Volume")
        self.subscription = self.ctx.audio.on_changed(self.changed)

    def stop(self) -> None:
        if self.subscription is not None:
            self.subscription.cancel()
            self.subscription = None

    def use_added(self, use: UseRecord) -> None:
        self.refused.discard(use.key)

    def use_removed(self, use: UseRecord) -> None:
        self.refused.discard(use.key)

    # -- the server's state (service thread) ------------------------------------------------------

    def changed(self, state: AudioState | None) -> None:
        if state is None or state.output is None:
            self.baseline = None  # the next reading is a first reading again: nothing is shown
            return
        now = (state.output.name, state.volume, state.muted)
        before, self.baseline = self.baseline, now
        # the values first: they are in the store before the Panel is shown
        for key, value in values(state).items():
            self.ctx.send(key, value)
        if before is not None and before[0] == now[0] and before[1:] != now[1:]:
            self.ctx.call_soon(self.reveal)

    # -- the Panel (loop thread) ------------------------------------------------------------------

    def reveal(self) -> None:
        """Show the Panel of each use, for that use's ``duration``; a change in that time starts it
        again."""
        for use in list(self.ctx.uses.values()):
            if use.key in self.refused:
                continue
            duration = float(use.params.get("duration") or DEFAULT_DURATION)
            if not self.ctx.surface.show(use, hide_after=duration):
                self.refused.add(use.key)
                self.ctx.log.warning(
                    f"{use.key} is not on a Panel: put Volume_OSD in a Panel that starts hidden"
                )
