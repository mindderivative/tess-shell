"""Fake MPRIS players on a private session bus (M5d): each is a well-known name
``org.mpris.MediaPlayer2.<suffix>`` with the object ``/org/mpris/MediaPlayer2`` and the two
interfaces of the specification (``org.mpris.MediaPlayer2`` and ``org.mpris.MediaPlayer2.Player``),
with the properties and types of a real player (Media Module > What It Reads). The controls are
recorded in ``player.calls`` and change nothing: a test (or ``tests/kwin/fake_mpris.py``) models
what the player does by setting the properties and emitting ``Seeked`` itself, as a real player does
after it has played or paused. Never touches the real buses. Used by ``tests/test_media*.py``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from dbus_fast import Variant

from tests.fake_dbus import FakeObject, FakeService

PREFIX = "org.mpris.MediaPlayer2."
PATH = "/org/mpris/MediaPlayer2"
ROOT = "org.mpris.MediaPlayer2"
PLAYER = "org.mpris.MediaPlayer2.Player"


def metadata(
    title: str | None = "Song",
    artist: list[str] | None = None,
    album: str | None = "Album",
    art: str | None = None,
    length: int | None = 200_000_000,
    track: str | None = "/track/1",
    **extra: Variant,
) -> dict[str, Variant]:
    """The ``Metadata`` dictionary of a player: entries left ``None`` are missing."""
    entries: dict[str, Variant] = {}
    if title is not None:
        entries["xesam:title"] = Variant("s", title)
    if artist is not None:
        entries["xesam:artist"] = Variant("as", artist)
    if album is not None:
        entries["xesam:album"] = Variant("s", album)
    if art is not None:
        entries["mpris:artUrl"] = Variant("s", art)
    if length is not None:
        entries["mpris:length"] = Variant("x", length)
    if track is not None:
        entries["mpris:trackid"] = Variant("o", track)
    entries.update(extra)
    return entries


@dataclass
class Fake:
    """One fake player: its service, its two objects and what it was asked."""

    service: FakeService
    root: FakeObject
    player: FakeObject

    @property
    def name(self) -> str:
        return self.service.name

    @property
    def calls(self) -> list[tuple[str, tuple[Any, ...]]]:
        return self.player.calls

    def up(self) -> None:
        self.service.up()

    def down(self) -> None:
        self.service.down()

    def status(self, status: str) -> None:
        self.player.set("PlaybackStatus", status)

    def track(self, **kwargs: Any) -> None:
        self.player.set("Metadata", metadata(**kwargs))

    def seek(self, seconds: float) -> None:
        """What a player does after a seek: its position moves, then it says so."""
        self.player.silent_set("Position", int(seconds * 1_000_000))
        self.player.emit("Seeked", int(seconds * 1_000_000))


def add_player(
    bus: Any,
    suffix: str,
    *,
    identity: str = "Fake Player",
    status: str = "Paused",
    meta: dict[str, Variant] | None = None,
    position: int = 52_000_000,
    rate: float = 1.0,
    can_next: bool = True,
    can_previous: bool = True,
    can_seek: bool = True,
    can_control: bool = True,
    methods: dict[str, Any] | None = None,
) -> Fake:
    """A fake player on ``bus`` (a ``FakeBus``), not up yet."""
    service = bus.service(PREFIX + suffix)
    root = service.add(
        PATH,
        ROOT,
        properties={
            "Identity": ("s", identity),
            "DesktopEntry": ("s", suffix),
            "CanQuit": ("b", True),
        },
    )
    player = service.add(
        PATH,
        PLAYER,
        properties={
            "PlaybackStatus": ("s", status),
            "Metadata": ("a{sv}", metadata() if meta is None else meta),
            "Position": ("x", position),
            "Rate": ("d", rate),
            "CanPlay": ("b", True),
            "CanPause": ("b", True),
            "CanGoNext": ("b", can_next),
            "CanGoPrevious": ("b", can_previous),
            "CanSeek": ("b", can_seek),
            "CanControl": ("b", can_control),
        },
        methods={
            "PlayPause": ([], "", lambda: None),
            "Play": ([], "", lambda: None),
            "Pause": ([], "", lambda: None),
            "Next": ([], "", lambda: None),
            "Previous": ([], "", lambda: None),
            "SetPosition": (["o", "x"], "", lambda track, position: None),
            **(methods or {}),
        },
        signals={"Seeked": "x"},
        writable=[
            "PlaybackStatus",
            "Metadata",
            "Position",
            "Rate",
            "CanGoNext",
            "CanGoPrevious",
            "CanSeek",
            "CanControl",
        ],
    )
    return Fake(service, root, player)
