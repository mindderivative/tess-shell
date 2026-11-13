"""Fake MPRIS players on a private session bus, for the maintainer's KWin check of the Media module
(``tests/kwin/prepare_m5d_gallery.py``; not collected by pytest).

``python fake_mpris.py --root DIR`` starts a private ``dbus-daemon`` and four players on it:
``alpha`` and ``beta`` (two players, one playing, one paused), and the browser pair of the
maintainer's desk, ``chrome`` (``chromium.instance1``) and ``integration``
(``plasma-browser-integration``), which are down until asked for. It writes the bus address to
``DIR/bus-address`` and its pid to ``DIR/fake.pid``. The players behave as real ones: ``PlayPause``
toggles the status, ``Next`` and ``Previous`` change the track, ``SetPosition`` seeks and says
``Seeked``, and each change is the player's own ``PropertiesChanged``. ``media-set.sh`` changes
them with ``busctl`` through one extra object, ``org.tess.FakeMpris``, on the same private bus.

It never connects to the real session bus or the real system bus: the daemon is its own, on a socket
in a temporary directory. ``SIGTERM`` / ``SIGINT`` end the daemon and this process.
"""

from __future__ import annotations

import argparse
import os
import signal
import struct
import sys
import time
import zlib
from pathlib import Path
from typing import Any

from dbus_fast import Variant

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.fake_dbus import FakeBus, FakeObject  # noqa: E402
from tests.fake_mpris import Fake, add_player, metadata  # noqa: E402

CONTROL = "org.tess.FakeMpris"
CONTROL_PATH = "/org/tess/Fake"
CONTROL_INTERFACE = "org.tess.FakeMpris.Control"
SUFFIX = {
    "alpha": "alpha",
    "beta": "beta",
    "chrome": "chromium.instance1",
    "integration": "plasma-browser-integration",
}
IDENTITY = {
    "alpha": "Alpha Player",
    "beta": "Beta Player",
    "chrome": "Google Chrome",
    "integration": "Google Chrome",
}
TRACKS = {
    "track1": ("First Song", ["Artist A"], "Album A", 180, "/track/1"),
    "track2": (
        "Second Song with a rather long title that does not fit and so scrolls",
        ["Artist B", "Guest"],
        "Album B",
        240,
        "/track/2",
    ),
}
ART = ("art", "noart", "httpart", "missingart")


def cover(path: Path) -> None:
    """A 64 by 64 PNG of a blue-to-orange gradient (stdlib only)."""
    rows = b""
    for y in range(64):
        rows += b"\x00" + b"".join(bytes((40 + 3 * x, 90 + 2 * y, 200 - 3 * y)) for x in range(64))

    def chunk(kind: bytes, data: bytes) -> bytes:
        body = kind + data
        return struct.pack(">I", len(data)) + body + struct.pack(">I", zlib.crc32(body))

    header = struct.pack(">IIBBBBB", 64, 64, 8, 2, 0, 0, 0)
    path.write_bytes(
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


async def emit(obj: FakeObject, prop: str, value: Any) -> None:
    """``PropertiesChanged`` for one property, from inside the fake's own loop."""
    obj.values[prop] = value
    if obj._iface is not None:
        obj._iface.emit_properties_changed({prop: value})


class Live:
    """One fake player that behaves like a real one."""

    def __init__(self, bus: FakeBus, root: Path, role: str, status: str, track: str) -> None:
        self.bus = bus
        self.role = role
        self.track = track
        self.titled = True
        self.art = "art"
        self.root = root
        self.rate = 1.0
        self.started = time.monotonic()
        self.base = 0.0  # seconds
        self.fake: Fake = self.make(status)

    def make(self, status: str) -> Fake:
        methods = {
            "PlayPause": ([], "", self.play_pause),
            "Next": ([], "", self.next),
            "Previous": ([], "", self.previous),
            "SetPosition": (["o", "x"], "", self.set_position),
        }
        return add_player(
            self.bus,
            SUFFIX[self.role],
            identity=IDENTITY[self.role],
            status=status,
            meta=self.meta(),
            position=0,
            methods=methods,
        )

    def meta(self) -> dict[str, Variant]:
        title, artist, album, seconds, track = TRACKS[self.track]
        url = {
            "art": f"file://{self.root}/cover.png",
            "noart": None,
            "httpart": "https://example.org/cover.png",
            "missingart": f"file://{self.root}/nothing.png",
        }[self.art]
        if not self.titled:
            return metadata(None, None, None, url, seconds * 1_000_000, track)
        return metadata(title, artist, album, url, seconds * 1_000_000, track)

    @property
    def player(self) -> FakeObject:
        return self.fake.player

    def now(self) -> float:
        """The position now, in seconds, as a player at its rate would have it."""
        if self.player.values["PlaybackStatus"] == "Playing":
            return self.base + (time.monotonic() - self.started) * self.rate
        return self.base

    def freeze(self) -> None:
        self.base, self.started = self.now(), time.monotonic()
        self.player.values["Position"] = int(self.base * 1_000_000)

    async def status(self, status: str) -> None:
        self.freeze()
        await emit(self.player, "PlaybackStatus", status)

    async def play_pause(self) -> None:
        playing = self.player.values["PlaybackStatus"] == "Playing"
        await self.status("Paused" if playing else "Playing")

    async def go(self, track: str) -> None:
        """``track1`` and ``track2``, or ``notitle``: the same track with no title in it."""
        self.titled = track != "notitle"
        self.track = track if track in TRACKS else self.track
        self.base, self.started = 0.0, time.monotonic()
        self.player.values["Position"] = 0
        await emit(self.player, "Metadata", self.meta())

    async def next(self) -> None:
        await self.go("track2" if self.track == "track1" else "track1")  # the other of two

    async def previous(self) -> None:
        await self.next()

    async def set_position(self, track: str, micro: int) -> None:
        if track != TRACKS.get(self.track, ("", [], "", 0, ""))[4]:
            return
        self.base, self.started = micro / 1_000_000, time.monotonic()
        self.player.values["Position"] = micro
        self.player._iface.Seeked(micro)  # type: ignore[union-attr]

    async def seek(self, seconds: int) -> None:
        await self.set_position(
            TRACKS.get(self.track, ("", [], "", 0, "/track/1"))[4], seconds * 10**6
        )

    async def art_is(self, which: str) -> None:
        self.art = which
        await emit(self.player, "Metadata", self.meta())

    async def rate_is(self, rate: float) -> None:
        self.freeze()
        self.rate = rate
        await emit(self.player, "Rate", rate)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=True)
    cover(args.root / "cover.png")
    bus = FakeBus()  # a private daemon, and the thread the fake players run on
    players = {
        "alpha": Live(bus, args.root, "alpha", "Playing", "track1"),
        "beta": Live(bus, args.root, "beta", "Paused", "track2"),
        "chrome": Live(bus, args.root, "chrome", "Playing", "track1"),
        "integration": Live(bus, args.root, "integration", "Playing", "track1"),
    }
    control = bus.service(CONTROL)

    def who(role: str) -> Live:
        return players[role]

    async def c_state(role: str, status: str) -> None:
        await who(role).status(status)

    async def c_track(role: str, track: str) -> None:
        await who(role).go(track)

    async def c_art(role: str, which: str) -> None:
        await who(role).art_is(which)

    async def c_seek(role: str, seconds: int) -> None:
        await who(role).seek(seconds)

    async def c_rate(role: str, rate: float) -> None:
        await who(role).rate_is(rate)

    async def c_can(role: str, which: str, value: bool) -> None:
        name = {
            "next": "CanGoNext",
            "previous": "CanGoPrevious",
            "seek": "CanSeek",
            "control": "CanControl",
        }[which]
        await emit(who(role).player, name, value)

    async def c_presence(role: str, what: str) -> None:
        service = who(role).fake.service
        await (service._up() if what == "back" else service._down())

    control.add(
        CONTROL_PATH,
        CONTROL_INTERFACE,
        methods={
            "State": (["s", "s"], "", c_state),
            "Track": (["s", "s"], "", c_track),
            "Art": (["s", "s"], "", c_art),
            "Seek": (["s", "x"], "", c_seek),
            "Rate": (["s", "d"], "", c_rate),
            "Can": (["s", "s", "b"], "", c_can),
            "Presence": (["s", "s"], "", c_presence),
        },
    )
    control.up()
    for role in ("alpha", "beta"):  # the browser pair is down until asked for
        players[role].fake.up()
    (args.root / "fake.pid").write_text(str(os.getpid()))
    (args.root / "bus-address").write_text(bus.address)
    print(f"fake players on {bus.address}", flush=True)
    stop = {"now": False}

    def on_term(*_: object) -> None:
        stop["now"] = True

    signal.signal(signal.SIGTERM, on_term)
    signal.signal(signal.SIGINT, on_term)
    try:
        while not stop["now"]:
            time.sleep(0.2)
    finally:
        bus.close()
        (args.root / "bus-address").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
