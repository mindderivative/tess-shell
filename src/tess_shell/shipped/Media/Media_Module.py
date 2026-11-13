"""The Media: what an MPRIS media player plays, and its controls (Media Module). It finds the
players on the session bus by prefix (``org.mpris.MediaPlayer2.``, one ``ListNames`` and one
``NameOwnerChanged`` rule: no polling), follows ``PropertiesChanged`` and ``Seeked`` of each, picks
one active player by the spec's rule and shows it. The controls are calls through ``bus.run``; the
module predicts nothing: every state change comes from the player's own signals. One instance
serves every use.

Keys sent: ``has_player``, ``status`` (``PLAYING``, ``PAUSED``, ``STOPPED``), ``title``, ``artist``,
``album``, ``player`` (its ``Identity``), ``art`` (a local file path from a ``file://``
``mpris:artUrl`` that exists, else empty), ``length`` and ``position`` (seconds),
``can_play_pause``, ``can_next``, ``can_previous``, ``can_seek``, ``icon``, ``tooltip`` and
``label``. ``available`` is the layer's: true while the session bus can be reached. A layout shows
itself with ``Visible: {{ available and has_player }}``.

The position is not signalled by MPRIS while a track plays: it is the stored ``Position`` plus the
time since it was stored times ``Rate``. A tick of one second runs only while the chosen player is
``PLAYING`` and a use of the module shows the position (``show_position``): with none there is no
timer and nothing wakes.
"""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from functools import partial
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote, urlparse

from tess_shell import Module, action

if TYPE_CHECKING:
    from tess_shell.modules.context import UseRecord
    from tess_shell.modules.ticks import Subscription as TickSubscription
    from tess_shell.services.api import Bus, Proxy, Subscription

PREFIX = "org.mpris.MediaPlayer2."
PATH = "/org/mpris/MediaPlayer2"
ROOT = "org.mpris.MediaPlayer2"
PLAYER = "org.mpris.MediaPlayer2.Player"
# a player whose name has this suffix is the browser's own integration; when another browser
# player is there too, the pair is one browser and only the integration is shown
INTEGRATION = "plasma-browser-integration"
BROWSERS = ("chromium", "firefox")
WARN_EVERY = 60.0  # seconds between two warnings about a failed control call of one player

ICONS = frozenset({"play", "pause", "skip-next", "skip-previous", "music"})

# the one place the tooltip's wording lives (Media Module, open question 5)
STATUS_WORDS = {"PLAYING": "playing", "PAUSED": "paused", "STOPPED": "stopped"}


def status_of(value: object) -> str:
    words = {"Playing": "PLAYING", "Paused": "PAUSED"}
    return words.get(value, "STOPPED") if isinstance(value, str) else "STOPPED"


def number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def file_path(url: str) -> str | None:
    """The local path of a ``file://`` URL, or ``None`` for any other kind of URL."""
    parts = urlparse(url)
    if parts.scheme != "file" or parts.netloc not in ("", "localhost"):
        return None
    return unquote(parts.path) or None


def tooltip_text(title: str, artist: str, player: str, status: str) -> str:
    """``Song, Artist (Google Chrome), paused``."""
    head = ", ".join(x for x in (title or "No title", artist) if x)
    who = f" ({player})" if player else ""
    return f"{head}{who}, {STATUS_WORDS[status]}"


def label_text(title: str, artist: str, player: str, status: str) -> str:
    """The accessible name: the title, the artist, the player and the status."""
    return ", ".join(x for x in ("Media", title, artist, player, STATUS_WORDS[status]) if x)


class Playing:
    """One player on the bus: what it said last."""

    def __init__(
        self,
        name: str,
        *,
        status: str = "STOPPED",
        seen: bool = False,
        metadata: dict[str, Any] | None = None,
        since: int = 0,
        changed: int = 0,
    ) -> None:
        self.name = name
        self.identity = ""
        self.status = status
        self.metadata: dict[str, Any] = metadata if metadata is not None else {}
        self.rate = 1.0
        self.can_control = False
        self.can: dict[str, bool] = {}
        self.position = 0.0  # seconds, as read
        self.read_at = 0.0  # the monotonic time of that reading
        self.changed = changed  # a counter of the last change of status or metadata
        self.since = since  # a counter of the last time it began to play
        self.proxy: Proxy | None = None
        self.subs: list[Subscription] = []
        self.seen = seen  # its player properties were read

    @property
    def title(self) -> str:
        value = self.metadata.get("xesam:title")
        return value if isinstance(value, str) else ""

    def length(self) -> float:
        micro = number(self.metadata.get("mpris:length"))
        return micro / 1_000_000 if micro is not None and micro > 0 else 0.0


def is_duplicate(name: str, names: Sequence[str]) -> bool:
    """A browser player that the integration player of the same browser stands for."""
    short = name.removeprefix(PREFIX)
    if short.startswith(INTEGRATION):
        return False
    return any(n.removeprefix(PREFIX).startswith(INTEGRATION) for n in names) and any(
        b in short for b in BROWSERS
    )


def choose(players: Mapping[str, Playing], last: str | None) -> str | None:
    """The player to show (Media Module > Choosing the Active Player): the one playing since
    last; else the one shown before while it is not stopped; else the paused one that changed
    last; else none. A stopped player with no title is never chosen."""
    names = list(players)
    found = [
        p
        for p in players.values()
        if p.seen and not is_duplicate(p.name, names) and (p.status != "STOPPED" or p.title)
    ]
    playing = [p for p in found if p.status == "PLAYING"]
    if playing:
        return max(playing, key=lambda p: p.since).name
    before = players.get(last) if last is not None else None
    if before is not None and before in found and before.status != "STOPPED":
        return before.name
    paused = [p for p in found if p.status == "PAUSED"]
    if paused:
        return max(paused, key=lambda p: p.changed).name
    return None


class Media(Module):
    def __init__(self) -> None:
        self.players: dict[str, Playing] = {}
        self.sent: dict[str, Any] = {}
        self.active: str | None = None
        self.counter = 0
        self.warned: set[str] = set()
        self.failed: dict[str, float] = {}
        self.art_seen: set[str] = set()
        self.position_uses: set[str] = set()
        self.dragging: set[str] = set()
        self.pending: float | None = None  # the position a drag ended on, sent on release
        self.tick_sub: TickSubscription | None = None
        self.lock = threading.Lock()  # the timer
        self.send_lock = threading.Lock()  # what was sent: a refresh and a tick are two threads
        self.monotonic: Callable[[], float] = time.monotonic  # a test swaps it

    def start(self) -> None:
        # defaults, so a layout reading any key has a value before a player has answered
        self.publish(self.values(None))
        self.bus: Bus = self.ctx.dbus.session()
        self.position_uses = {k for k, u in self.ctx.uses.items() if u.params.get("show_position")}
        self.bus.watch_prefix(PREFIX, self.added, self.removed)

    def use_added(self, use: UseRecord) -> None:
        for key, value in list(self.sent.items()):
            self.ctx.send(key, value, use=use)
        if use.params.get("show_position"):
            self.position_uses.add(use.key)
            self.sync_timer()

    def use_removed(self, use: UseRecord) -> None:
        self.position_uses.discard(use.key)
        self.dragging.discard(use.key)
        self.sync_timer()

    # -- players come and go (dbus thread) ---------------------------------------------------

    def added(self, name: str) -> None:
        if name in self.players:
            return
        player = self.players[name] = Playing(name)
        root = self.bus.proxy(name, PATH, ROOT, optional=True)
        main = self.bus.proxy(name, PATH, PLAYER, optional=True)
        player.proxy = main
        player.subs = [
            root.on_property_changed(partial(self.root_changed, name)),
            main.on_property_changed(partial(self.player_changed, name)),
            main.on_signal("Seeked", partial(self.seeked, name)),
        ]

    def removed(self, name: str) -> None:
        player = self.players.pop(name, None)
        if player is None:
            return
        for sub in player.subs:
            sub.cancel()
        self.bus.forget(name)
        self.failed.pop(name, None)
        self.refresh()

    def root_changed(self, name: str, values: Mapping[str, Any]) -> None:
        player = self.players.get(name)
        if player is None:
            return
        identity = values.get("Identity")
        if isinstance(identity, str):
            player.identity = identity
            self.refresh()

    def player_changed(self, name: str, values: Mapping[str, Any]) -> None:
        player = self.players.get(name)
        if player is None:
            return
        reread = False
        if "PlaybackStatus" in values:
            status = status_of(values["PlaybackStatus"])
            if status != player.status or not player.seen:
                # the position up to now is kept as it was (a pause must not jump back to the
                # last reading); the fresh reading below corrects it
                player.position = self.current(player)
                player.read_at = self.monotonic()
                if status == "PLAYING":
                    self.counter += 1
                    player.since = self.counter
                self.counter += 1
                player.changed = self.counter
                reread = reread or player.seen
            player.status = status
        if "Metadata" in values:
            meta = values["Metadata"] if isinstance(values["Metadata"], dict) else {}
            before = player.metadata.get("mpris:trackid")
            player.metadata = dict(meta)
            self.counter += 1
            player.changed = self.counter
            reread = reread or (player.seen and meta.get("mpris:trackid") != before)
        if "Rate" in values:
            rate = number(values["Rate"])
            reread = reread or (player.seen and rate is not None and rate != player.rate)
            if rate is not None and rate != 0:
                player.rate = rate
        for key, member in (
            ("can_play_pause", "CanPause"),
            ("can_play", "CanPlay"),
            ("can_next", "CanGoNext"),
            ("can_previous", "CanGoPrevious"),
            ("can_seek", "CanSeek"),
        ):
            if member in values:
                player.can[key] = values[member] is True
        if "CanControl" in values:
            player.can_control = values["CanControl"] is True
        micro = number(values.get("Position"))
        if micro is not None:
            player.position = micro / 1_000_000
            player.read_at = self.monotonic()
        player.seen = True
        if reread and micro is None:
            self.bus.run(self.read_position(name))
        self.refresh()

    def seeked(self, name: str, *body: object) -> None:
        """The position jumped: read it from the player (Media Module > Position)."""
        if name in self.players:
            self.bus.run(self.read_position(name))

    async def read_position(self, name: str) -> None:
        player = self.players.get(name)
        if player is None or player.proxy is None:
            return
        try:
            micro = number(await player.proxy.get("Position", fresh=True))
        except Exception as exc:  # the player left (the layer says so) or does not answer
            self.ctx.log.debug(f"could not read the position of {name} ({exc})")
            return
        if micro is None or name not in self.players:
            return
        player.position = micro / 1_000_000
        player.read_at = self.monotonic()
        self.refresh()

    # -- what is shown (dbus thread, or the loop thread for a tick) -----------------------------

    def refresh(self) -> None:
        chosen = choose(self.players, self.active)
        if chosen != self.active:
            self.active = chosen
        player = self.players.get(chosen) if chosen is not None else None
        self.publish(self.values(player))
        self.sync_timer()

    def current(self, player: Playing) -> float:
        """The position now: the stored one plus the time since times the rate, up to the length."""
        position = player.position
        if player.status == "PLAYING":
            position += (self.monotonic() - player.read_at) * player.rate
        length = player.length()
        if length > 0:
            position = min(position, length)
        return max(position, 0.0)

    def values(self, player: Playing | None) -> dict[str, Any]:
        if player is None:
            return {
                "has_player": False,
                "status": "STOPPED",
                "title": "",
                "artist": "",
                "album": "",
                "player": "",
                "art": "",
                "length": 0,
                "position": 0,
                "can_play_pause": False,
                "can_next": False,
                "can_previous": False,
                "can_seek": False,
                "icon": "play",
                "tooltip": "",
                "label": "Media",
            }
        meta = player.metadata
        title = self.text(player, "xesam:title", meta.get("xesam:title"))
        album = self.text(player, "xesam:album", meta.get("xesam:album"))
        artist = self.artist(player, meta.get("xesam:artist"))
        length = player.length()
        control = player.can_control
        can_seek = control and player.can.get("can_seek", False) and length > 0
        return {
            "has_player": True,
            "status": player.status,
            "title": title,
            "artist": artist,
            "album": album,
            "player": player.identity,
            "art": self.art(player, meta.get("mpris:artUrl")),
            "length": round(length, 3),
            "position": int(self.current(player)),
            "can_play_pause": control and (player.can.get("can_play_pause", False)),
            "can_next": control and player.can.get("can_next", False),
            "can_previous": control and player.can.get("can_previous", False),
            "can_seek": can_seek,
            "icon": "pause" if player.status == "PLAYING" else "play",
            "tooltip": tooltip_text(title, artist, player.identity, player.status),
            "label": label_text(title, artist, player.identity, player.status),
        }

    def text(self, player: Playing, entry: str, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value
        self.warn_once(f"{player.name}: the metadata entry {entry} is not text; ignored")
        return ""

    def artist(self, player: Playing, value: object) -> str:
        if value is None:
            return ""
        if isinstance(value, str):  # the specification says a list; some players send text
            return value
        if isinstance(value, list) and all(isinstance(a, str) for a in value):
            return ", ".join(a for a in value if a)
        self.warn_once(f"{player.name}: the metadata entry xesam:artist is not a list of text")
        return ""

    def art(self, player: Playing, value: object) -> str:
        """The local file of the artwork: a ``file://`` URL whose file exists. Any other URL
        (``http``, ``https``) is not fetched (the shell makes no network request); it and a missing
        file give no art, and the Image shows its placeholder."""
        if value is None or value == "":
            return ""
        if not isinstance(value, str):
            self.warn_once(f"{player.name}: the metadata entry mpris:artUrl is not text; ignored")
            return ""
        path = file_path(value)
        if path is None:
            if value not in self.art_seen:
                self.art_seen.add(value)
                self.ctx.log.debug(f"artwork {value} is not a file:// URL: not fetched")
            return ""
        return path if os.path.isfile(path) else ""

    def publish(self, values: Mapping[str, Any]) -> None:
        """Send what changed since the last send: a refresh that changes nothing sends nothing."""
        with self.send_lock:
            for key, value in values.items():
                if key == "position" and self.dragging:
                    continue  # the user holds the handle
                if key not in self.sent or self.sent[key] != value:
                    self.sent[key] = value
                    self.ctx.send(key, value)

    def warn_once(self, message: str) -> None:
        if message not in self.warned:
            self.warned.add(message)
            self.ctx.log.warning(message)

    # -- the position's tick ----------------------------------------------------------------------

    def sync_timer(self) -> None:
        """A tick of one second exists only while the shown player is playing and a use shows
        the position; otherwise there is none and nothing wakes."""
        player = self.players.get(self.active) if self.active is not None else None
        want = player is not None and player.status == "PLAYING" and bool(self.position_uses)
        with self.lock:
            if want and self.tick_sub is None:
                self.tick_sub = self.ctx.on_tick("second", self.tick)
            elif not want and self.tick_sub is not None:
                self.tick_sub.cancel()
                self.tick_sub = None

    def tick(self) -> None:
        """Loop thread, once a second while playing: the position moves on."""
        player = self.players.get(self.active) if self.active is not None else None
        if player is not None and player.status == "PLAYING":
            self.publish({"position": int(self.current(player))})

    # -- the controls (loop thread) ---------------------------------------------------------------

    def target(self, can: str | None) -> Playing | None:
        player = self.players.get(self.active) if self.active is not None else None
        if player is None or player.proxy is None or not player.can_control:
            return None
        if can is not None and not player.can.get(can, False):
            return None
        return player

    def call(self, player: Playing, method: str, args: Sequence[Any] = (), sig: str = "") -> None:
        assert player.proxy is not None
        future = self.bus.run(player.proxy.call(method, args, sig))
        future.add_done_callback(partial(self.done, player.name, method))

    def done(self, name: str, method: str, future: Any) -> None:
        """A control call ended: a failure is logged once a minute for each player."""
        if future.cancelled() or future.exception() is None:
            return
        now = self.monotonic()
        if now - self.failed.get(name, -WARN_EVERY) >= WARN_EVERY:
            self.failed[name] = now
            self.ctx.log.warning(f"{name}: {method} failed: {future.exception()}")

    @action
    def play_pause(self, event: Any) -> None:
        if (player := self.target("can_play_pause")) is not None:
            self.call(player, "PlayPause")

    @action
    def next(self, event: Any) -> None:
        if (player := self.target("can_next")) is not None:
            self.call(player, "Next")

    @action
    def previous(self, event: Any) -> None:
        if (player := self.target("can_previous")) is not None:
            self.call(player, "Previous")

    @action
    def drag(self, event: Any, position: float) -> None:
        """The slider's handle moved by the user: nothing goes to the player until the release."""
        if event.use:
            self.dragging.add(event.use)
        self.pending = float(position)

    @action
    def release(self, event: Any) -> None:
        """The handle was let go: ask the player for the position the drag ended on and wait for
        its ``Seeked`` (the module moves nothing itself)."""
        self.dragging.discard(event.use)
        position, self.pending = self.pending, None
        if position is None:
            return
        self.seek_to(position)

    @action
    def seek(self, event: Any, position: float) -> None:
        """Ask the player to go to ``position`` seconds."""
        self.seek_to(float(position))

    def seek_to(self, position: float) -> None:
        player = self.target("can_seek")
        if player is None or player.length() <= 0:
            return
        track = player.metadata.get("mpris:trackid")
        if not isinstance(track, str):
            self.warn_once(f"{player.name}: no mpris:trackid in its metadata: cannot seek")
            return
        micro = int(min(max(position, 0.0), player.length()) * 1_000_000)
        self.call(player, "SetPosition", [track, micro], "ox")
