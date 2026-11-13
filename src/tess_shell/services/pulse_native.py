"""A client of the PulseAudio native protocol (what ``pipewire-pulse`` and PulseAudio speak), in
asyncio. It is the shell's way to the sound server (ADR-0021 Audio Access, option A): standard
library only, a socket in the loop's ``epoll`` and nothing else, so with no change an idle client
costs nothing.

Only what the Audio module needs: ``AUTH`` (the version is negotiated: the reply carries the
server's), ``SET_CLIENT_NAME``, ``SUBSCRIBE`` and its ``SUBSCRIBE_EVENT``, ``GET_SERVER_INFO``,
``GET_SINK_INFO_LIST``, ``GET_SOURCE_INFO_LIST``, ``SET_SINK_VOLUME``, ``SET_SINK_MUTE``,
``SET_SOURCE_MUTE`` and ``SET_DEFAULT_SINK``. A frame is a 20 byte big-endian descriptor (length,
channel, offset high and low, flags) and a tag-struct payload; there is no shared memory.

The fields a server of protocol ``v`` sends depend on ``v``: the property list from 13, ports from
16, a port's availability from 24, its availability group and type from 34 (a server below 34 has
no port types: the Audio module then takes the kind from the form factor and the bus). A server
below 13 is refused.

Nothing here reads the environment except in :func:`default_socket` and :func:`cookie_paths`,
which take the environment as an argument, so a test passes its own and never the real one.
"""

from __future__ import annotations

import asyncio
import struct
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path

VERSION = 35  # the highest protocol version this client speaks
MIN_VERSION = 13  # the property list arrives here
NORM = 0x10000  # PA_VOLUME_NORM: 100 %
CONTROL = 0xFFFFFFFF  # the channel of a command or a reply
NO_INDEX = 0xFFFFFFFF  # "no such index" (PA_INVALID_INDEX)
TIMEOUT = 5.0  # seconds a command waits for its reply

# command numbers (pulsecore/native-common.h)
ERROR, REPLY, AUTH, SET_CLIENT_NAME = 0, 2, 8, 9
GET_SERVER_INFO, GET_SINK_INFO_LIST, GET_SOURCE_INFO_LIST = 20, 22, 24
SUBSCRIBE, SET_SINK_VOLUME, SET_SINK_MUTE, SET_SOURCE_MUTE = 35, 36, 39, 40
SET_DEFAULT_SINK = 44
SUBSCRIBE_EVENT = 66
# error codes (pulse/def.h)
ERR_ACCESS = 1

# the subscription masks, and the event word: the facility in the low 4 bits, the type in bits 4-5
MASK_SINK, MASK_SOURCE, MASK_SERVER = 0x01, 0x02, 0x80
MASK_ALL = MASK_SINK | MASK_SOURCE | MASK_SERVER
FACILITY_SINK, FACILITY_SOURCE, FACILITY_SERVER = 0, 1, 7
TYPE_NEW, TYPE_CHANGE, TYPE_REMOVE = 0x00, 0x10, 0x20

# the type of a port (pa_device_port_type_t); a server of protocol 34 or later sends it
PORT_TYPES = {
    0: "Unknown",
    1: "Aux",
    2: "Speaker",
    3: "Headphones",
    4: "Line",
    5: "Mic",
    6: "Headset",
    7: "Handset",
    8: "Earpiece",
    9: "SPDIF",
    10: "HDMI",
    11: "TV",
    12: "Radio",
    13: "Video",
    14: "USB",
    15: "Bluetooth",
    16: "Portable",
    17: "Handsfree",
    18: "Car",
    19: "HiFi",
    20: "Phone",
    21: "Network",
    22: "Analog",
}


class PulseError(Exception):
    """The server answered a command with an error (``code``) or the connection broke."""

    def __init__(self, message: str, code: int = -1) -> None:
        super().__init__(message)
        self.code = code


class PulseAuthError(PulseError):
    """The server refused the cookie."""


class Tag:
    """Writes one tag-struct (the arguments of a command)."""

    def __init__(self) -> None:
        self.buf = bytearray()

    def u32(self, v: int) -> Tag:
        self.buf += b"L" + struct.pack(">I", v)
        return self

    def u8(self, v: int) -> Tag:
        self.buf += b"B" + bytes([v])
        return self

    def string(self, s: str | None) -> Tag:
        self.buf += b"N" if s is None else b"t" + s.encode() + b"\0"
        return self

    def boolean(self, v: bool) -> Tag:
        self.buf += b"1" if v else b"0"
        return self

    def raw(self, data: bytes) -> Tag:
        self.buf += b"x" + struct.pack(">I", len(data)) + data
        return self

    def usec(self, v: int) -> Tag:
        self.buf += b"U" + struct.pack(">Q", v)
        return self

    def volume(self, v: int) -> Tag:
        self.buf += b"V" + struct.pack(">I", v)
        return self

    def sample_spec(self, fmt: int = 5, channels: int = 2, rate: int = 48000) -> Tag:
        self.buf += b"a" + struct.pack(">BBI", fmt, channels, rate)
        return self

    def channel_map(self, positions: list[int]) -> Tag:
        self.buf += b"m" + bytes([len(positions)]) + bytes(positions)
        return self

    def cvolume(self, values: list[int]) -> Tag:
        self.buf += b"v" + bytes([len(values)]) + struct.pack(f">{len(values)}I", *values)
        return self

    def proplist(self, props: Mapping[str, str]) -> Tag:
        self.buf += b"P"
        for key, value in props.items():
            data = value.encode() + b"\0"
            self.string(key).u32(len(data)).raw(data)
        return self.string(None)

    def format_info(self, encoding: int = 1, props: Mapping[str, str] | None = None) -> Tag:
        self.buf += b"f"
        return self.u8(encoding).proplist(props or {})


class Reader:
    """Reads one tag-struct (a reply, an event, or the arguments a server was sent)."""

    def __init__(self, data: bytes) -> None:
        self.data, self.pos = data, 0

    def _take(self, tag: bytes, size: int) -> bytes:
        got = self.data[self.pos : self.pos + 1]
        if got != tag:
            raise PulseError(f"expected tag {tag!r} at {self.pos}, got {got!r}")
        chunk = self.data[self.pos + 1 : self.pos + 1 + size]
        if len(chunk) < size:
            raise PulseError(f"the tag {tag!r} at {self.pos} is cut short")
        self.pos += 1 + size
        return chunk

    def done(self) -> bool:
        return self.pos >= len(self.data)

    def u32(self) -> int:
        return int(struct.unpack(">I", self._take(b"L", 4))[0])

    def u8(self) -> int:
        return self._take(b"B", 1)[0]

    def boolean(self) -> bool:
        tag = self.data[self.pos : self.pos + 1]
        if tag not in (b"0", b"1"):
            raise PulseError(f"expected a boolean at {self.pos}, got {tag!r}")
        self.pos += 1
        return tag == b"1"

    def string(self) -> str | None:
        if self.data[self.pos : self.pos + 1] == b"N":
            self.pos += 1
            return None
        self._take(b"t", 0)
        end = self.data.find(b"\0", self.pos)
        if end < 0:
            raise PulseError(f"the string at {self.pos} has no end")
        text = self.data[self.pos : end].decode(errors="replace")
        self.pos = end + 1
        return text

    def skip(self, tag: bytes, size: int) -> None:
        self._take(tag, size)

    def raw(self) -> bytes:
        length = int(struct.unpack(">I", self._take(b"x", 4))[0])
        chunk = self.data[self.pos : self.pos + length]
        if len(chunk) < length:
            raise PulseError(f"the bytes at {self.pos} are cut short")
        self.pos += length
        return chunk

    def cvolume(self) -> list[int]:
        count = self._take(b"v", 1)[0]
        end = self.pos + 4 * count
        if end > len(self.data):
            raise PulseError(f"the volume at {self.pos} is cut short")
        values = list(struct.unpack(f">{count}I", self.data[self.pos : end]))
        self.pos = end
        return values

    def channel_map(self) -> None:
        count = self._take(b"m", 1)[0]
        self.pos += count

    def proplist(self) -> dict[str, str]:
        self._take(b"P", 0)
        props: dict[str, str] = {}
        while (key := self.string()) is not None:
            self.u32()  # the length of the value; the arbitrary that follows carries it too
            props[key] = self.raw().rstrip(b"\0").decode(errors="replace")
        return props

    def format_info(self) -> None:
        self._take(b"f", 0)
        self.u8()
        self.proplist()


@dataclass(frozen=True, slots=True)
class Port:
    name: str
    description: str
    kind: str  # PORT_TYPES, "" when the server (protocol below 34) sends no type


@dataclass(slots=True)
class Device:
    """A sink or a source as the server describes it."""

    index: int
    name: str
    description: str
    volume: list[int]  # one level per channel, ``NORM`` is 100 %
    mute: bool
    props: dict[str, str]
    ports: list[Port] = field(default_factory=list)
    active_port: str = ""
    monitor: int = NO_INDEX  # a source: the sink it monitors (``NO_INDEX``: none)

    @property
    def percent(self) -> int:
        """The mean of the channels in percent, rounded (a value above 100 is kept)."""
        return round(sum(self.volume) / len(self.volume) * 100 / NORM) if self.volume else 0

    @property
    def port_kind(self) -> str:
        """The type of the active port (``""`` if there is none or the server sends no type)."""
        for port in self.ports:
            if port.name == self.active_port:
                return port.kind
        return ""


@dataclass(frozen=True, slots=True)
class ServerInfo:
    default_sink: str
    default_source: str


def parse_server_info(r: Reader) -> ServerInfo:
    for _ in range(4):
        r.string()  # server name, version, user name, host name
    r.skip(b"a", 6)  # the default sample specification
    return ServerInfo(r.string() or "", r.string() or "")


def parse_devices(r: Reader, version: int) -> list[Device]:
    """The list a ``GET_SINK_INFO_LIST`` or ``GET_SOURCE_INFO_LIST`` reply holds; the two have the
    fields this reads in the same order."""
    out: list[Device] = []
    while not r.done():
        index, name, description = r.u32(), r.string() or "", r.string() or ""
        r.skip(b"a", 6)  # sample specification
        r.channel_map()
        r.u32()  # the owner module
        volume, mute = r.cvolume(), r.boolean()
        monitor = r.u32()  # the monitor source of a sink (the sink a source monitors)
        r.string()  # ... and its name
        r.skip(b"U", 8)  # latency
        r.string()  # driver
        r.u32()  # flags
        props = r.proplist()  # version 13
        r.skip(b"U", 8)  # configured latency
        ports: list[Port] = []
        active = ""
        if version >= 15:
            r.skip(b"V", 4)  # base volume
            r.u32()  # state
            r.u32()  # volume steps
            r.u32()  # card
        if version >= 16:
            for _ in range(r.u32()):
                pname, pdesc = r.string() or "", r.string() or ""
                r.u32()  # priority
                if version >= 24:
                    r.u32()  # availability
                kind = ""
                if version >= 34:
                    r.string()  # availability group
                    kind = PORT_TYPES.get(r.u32(), "Unknown")
                ports.append(Port(pname, pdesc, kind))
            active = r.string() or ""
        if version >= 21:
            for _ in range(r.u8()):
                r.format_info()
        out.append(Device(index, name, description, volume, mute, props, ports, active, monitor))
    return out


def default_socket(env: Mapping[str, str]) -> Path | None:
    """Where the sound server's socket is, the way libpulse looks: ``PULSE_SERVER`` (the first
    ``unix:`` entry, or a plain path), ``PULSE_RUNTIME_PATH`` or ``XDG_RUNTIME_DIR`` with
    ``pulse/native``. ``None`` when the server is not a local socket or nothing names a place."""
    server = env.get("PULSE_SERVER", "").strip()
    if server:
        for entry in server.split():
            if entry.startswith("{") and "}" in entry:  # a machine-id prefix: not used here
                entry = entry.split("}", 1)[1]
            if entry.startswith("unix:"):
                return Path(entry.removeprefix("unix:"))
            if entry.startswith("/"):
                return Path(entry)
        return None  # tcp: and the like are not spoken here
    runtime = env.get("PULSE_RUNTIME_PATH")
    if runtime:
        return Path(runtime) / "native"
    xdg = env.get("XDG_RUNTIME_DIR")
    return Path(xdg) / "pulse" / "native" if xdg else None


def cookie_paths(env: Mapping[str, str]) -> list[Path]:
    """Where the user's cookie may be, in libpulse's order (``PULSE_COOKIE``, then the config
    folder, then the old home file)."""
    paths: list[Path] = []
    if env.get("PULSE_COOKIE"):
        paths.append(Path(env["PULSE_COOKIE"]))
    home = env.get("HOME")
    config = env.get("XDG_CONFIG_HOME") or (f"{home}/.config" if home else "")
    if config:
        paths.append(Path(config) / "pulse" / "cookie")
    if home:
        paths.append(Path(home) / ".pulse-cookie")
    return paths


def read_cookie(env: Mapping[str, str]) -> bytes | None:
    """The first cookie file that holds 256 bytes, or ``None``."""
    for path in cookie_paths(env):
        try:
            data = path.read_bytes()
        except OSError:
            continue
        if len(data) == 256:
            return data
    return None


class PulseClient:
    """One connection. ``on_event(facility, kind, index)`` and ``on_lost()`` run on the loop that
    :meth:`connect` runs on. The connection is not re-made: its owner makes a new client."""

    def __init__(
        self,
        path: str | Path,
        on_event: Callable[[int, int, int], None] | None = None,
        on_lost: Callable[[], None] | None = None,
        cookie: bytes = bytes(256),
    ) -> None:
        self.path, self.cookie = str(path), cookie
        self.on_event, self.on_lost = on_event, on_lost
        self.lost = asyncio.Event()  # set when the connection ends, from either side
        self.version = 0  # what the server answered (the lower of the two versions)
        self._pending: dict[int, asyncio.Future[Reader]] = {}
        self._tag = 0
        self._lost = False
        self._writer: asyncio.StreamWriter | None = None
        self._task: asyncio.Task[None] | None = None

    async def connect(self, name: str = "tesserae-shell") -> None:
        """Open the socket, authenticate and name the client. Raises ``OSError`` when there is no
        server, :class:`PulseAuthError` when the cookie is refused, :class:`PulseError` for a
        server too old."""
        reader, self._writer = await asyncio.open_unix_connection(self.path)
        self._task = asyncio.create_task(self._read(reader))
        try:
            reply = await self.call(AUTH, Tag().u32(VERSION).raw(self.cookie))
        except PulseError as exc:
            self.close()
            if exc.code == ERR_ACCESS:
                raise PulseAuthError("the server refused the cookie", exc.code) from exc
            raise
        self.version = reply.u32() & 0xFFFF
        if self.version < MIN_VERSION:
            self.close()
            raise PulseError(f"the server speaks protocol {self.version}, below {MIN_VERSION}")
        await self.call(SET_CLIENT_NAME, Tag().proplist({"application.name": name}))

    def close(self) -> None:
        """End the connection. ``on_lost`` is for a connection the server ended, not this."""
        self.on_lost = None
        if self._task is not None:
            self._task.cancel()
            self._task = None
        if self._writer is not None:
            self._writer.close()
            self._writer = None

    def send(self, command: int, args: Tag | None = None) -> asyncio.Future[Reader]:
        """Write a command now; the future is its reply. Several sends in a row share one round
        trip (the server answers in order)."""
        if self._writer is None or self._lost:
            raise ConnectionError("the pulse connection is closed")
        self._tag += 1
        future: asyncio.Future[Reader] = asyncio.get_running_loop().create_future()
        self._pending[self._tag] = future
        payload = bytes(Tag().u32(command).u32(self._tag).buf) + (bytes(args.buf) if args else b"")
        self._writer.write(struct.pack(">IIIII", len(payload), CONTROL, 0, 0, 0) + payload)
        return future

    async def call(self, command: int, args: Tag | None = None) -> Reader:
        try:
            return await asyncio.wait_for(self.send(command, args), TIMEOUT)
        except TimeoutError as exc:
            raise PulseError(f"command {command} timed out") from exc

    async def _read(self, reader: asyncio.StreamReader) -> None:
        try:
            while True:
                length, channel, *_ = struct.unpack(">IIIII", await reader.readexactly(20))
                payload = await reader.readexactly(length)
                if channel == CONTROL:
                    self._dispatch(Reader(payload))
        except asyncio.IncompleteReadError, ConnectionError, OSError, PulseError:
            pass
        finally:
            self._lost = True
            self.lost.set()
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(ConnectionError("the pulse connection was lost"))
            self._pending.clear()
            if self.on_lost is not None:
                self.on_lost()

    def _dispatch(self, r: Reader) -> None:
        command, tag = r.u32(), r.u32()
        if command == SUBSCRIBE_EVENT:
            if self.on_event is not None:
                event, index = r.u32(), r.u32()
                self.on_event(event & 0x0F, event & 0x30, index)
        elif (future := self._pending.pop(tag, None)) is not None and not future.done():
            if command == REPLY:
                future.set_result(r)
            else:
                code = r.u32() if command == ERROR else -1
                future.set_exception(PulseError(f"the server answered error {code}", code))

    # -- the commands -----------------------------------------------------------------------
    async def subscribe(self, mask: int = MASK_ALL) -> None:
        await self.call(SUBSCRIBE, Tag().u32(mask))

    async def snapshot(self) -> tuple[ServerInfo, list[Device], list[Device]]:
        """Server info, sinks and sources in ONE round trip."""
        info = self.send(GET_SERVER_INFO)
        sinks = self.send(GET_SINK_INFO_LIST)
        sources = self.send(GET_SOURCE_INFO_LIST)
        try:
            server = parse_server_info(await asyncio.wait_for(info, TIMEOUT))
            return (
                server,
                parse_devices(await asyncio.wait_for(sinks, TIMEOUT), self.version),
                parse_devices(await asyncio.wait_for(sources, TIMEOUT), self.version),
            )
        except TimeoutError as exc:
            raise PulseError("the server did not answer the read in time") from exc

    async def set_sink_volume(self, index: int, volume: list[int]) -> None:
        await self.call(SET_SINK_VOLUME, Tag().u32(index).string(None).cvolume(volume))

    async def set_sink_mute(self, index: int, muted: bool) -> None:
        await self.call(SET_SINK_MUTE, Tag().u32(index).string(None).boolean(muted))

    async def set_source_mute(self, index: int, muted: bool) -> None:
        await self.call(SET_SOURCE_MUTE, Tag().u32(index).string(None).boolean(muted))

    async def set_default_sink(self, name: str) -> None:
        await self.call(SET_DEFAULT_SINK, Tag().string(name))


def scaled(volume: list[int], percent: float) -> list[int]:
    """``volume`` with its mean at ``percent`` (0 to 100), the balance between channels kept: every
    channel is multiplied by the same factor, and none goes above 100 %. Channels that are all 0
    (no balance to keep) are all set to ``percent``."""
    percent = min(max(percent, 0.0), 100.0)
    target = percent * NORM / 100
    mean = sum(volume) / len(volume) if volume else 0
    if mean <= 0:
        return [round(target)] * len(volume)
    factor = target / mean
    return [min(round(v * factor), NORM) for v in volume]
