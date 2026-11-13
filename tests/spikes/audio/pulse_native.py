"""A minimal client of the PulseAudio NATIVE protocol (what pipewire-pulse speaks), in asyncio.

Candidate A of the audio spike. Pure standard library. Only what the Audio module needs: AUTH,
SET_CLIENT_NAME, SUBSCRIBE, GET_SERVER_INFO, GET_SINK_INFO_LIST, GET_SOURCE_INFO_LIST,
SET_SINK_VOLUME, SET_SINK_MUTE, SET_SOURCE_MUTE, SET_DEFAULT_SINK and the SUBSCRIBE_EVENT
notification. Frames: a 20-byte big-endian descriptor (length, channel, offset hi/lo, flags) and a
tag-struct payload. Protocol 35 (what the server on this machine speaks); no shared memory.
"""

from __future__ import annotations

import asyncio
import struct
from collections.abc import Callable
from dataclasses import dataclass, field

from tests.spikes.audio.guard import require_private_path

VERSION = 35
NORM = 0x10000  # PA_VOLUME_NORM: 100 %
CONTROL = 0xFFFFFFFF
# command numbers (pulsecore/native-common.h)
ERROR, REPLY, AUTH, SET_CLIENT_NAME = 0, 2, 8, 9
GET_SERVER_INFO, GET_SINK_INFO_LIST, GET_SOURCE_INFO_LIST = 20, 22, 24
SUBSCRIBE, SET_SINK_VOLUME, SET_SOURCE_VOLUME = 35, 36, 38
SET_SINK_MUTE, SET_SOURCE_MUTE, SET_DEFAULT_SINK, SET_DEFAULT_SOURCE = 39, 40, 44, 45
SUBSCRIBE_EVENT = 66
# subscription masks and the event word: facility in the low 4 bits, type in bits 4-5
MASK_SINK, MASK_SOURCE, MASK_SERVER = 1, 2, 128
FACILITY_SINK, FACILITY_SOURCE, FACILITY_SERVER = 0, 1, 7
TYPE_NEW, TYPE_CHANGE, TYPE_REMOVE = 0x00, 0x10, 0x20


class PulseError(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(f"pulse error {code}")
        self.code = code


class Tag:
    """Writes one tag-struct."""

    def __init__(self) -> None:
        self.buf = bytearray()

    def u32(self, v: int) -> Tag:
        self.buf += b"L" + struct.pack(">I", v)
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

    def cvolume(self, values: list[int]) -> Tag:
        self.buf += b"v" + bytes([len(values)]) + struct.pack(f">{len(values)}I", *values)
        return self

    def proplist(self, props: dict[str, str]) -> Tag:
        self.buf += b"P"
        for key, value in props.items():
            data = value.encode() + b"\0"
            self.string(key).u32(len(data)).raw(data)
        return self.string(None)


class Reader:
    """Reads one tag-struct payload."""

    def __init__(self, data: bytes) -> None:
        self.data, self.pos = data, 0

    def _take(self, tag: bytes, size: int) -> bytes:
        if self.data[self.pos : self.pos + 1] != tag:
            got = self.data[self.pos : self.pos + 1]
            raise ValueError(f"expected tag {tag!r} at {self.pos}, got {got!r}")
        chunk = self.data[self.pos + 1 : self.pos + 1 + size]
        self.pos += 1 + size
        return chunk

    def u32(self) -> int:
        return int(struct.unpack(">I", self._take(b"L", 4))[0])

    def u8(self) -> int:
        return self._take(b"B", 1)[0]

    def boolean(self) -> bool:
        tag = self.data[self.pos : self.pos + 1]
        self.pos += 1
        return tag == b"1"

    def string(self) -> str | None:
        if self.data[self.pos : self.pos + 1] == b"N":
            self.pos += 1
            return None
        self._take(b"t", 0)
        end = self.data.index(b"\0", self.pos)
        text = self.data[self.pos : end].decode(errors="replace")
        self.pos = end + 1
        return text

    def skip(self, tag: bytes, size: int) -> None:
        self._take(tag, size)

    def cvolume(self) -> list[int]:
        count = self._take(b"v", 1)[0]
        values = list(struct.unpack(f">{count}I", self.data[self.pos : self.pos + 4 * count]))
        self.pos += 4 * count
        return values

    def channel_map(self) -> None:
        count = self._take(b"m", 1)[0]
        self.pos += count

    def proplist(self) -> dict[str, str]:
        self._take(b"P", 0)
        props: dict[str, str] = {}
        while (key := self.string()) is not None:
            length = self.u32()
            self._take(b"x", 4)  # the length word of the arbitrary
            blob = self.data[self.pos : self.pos + length]
            self.pos += length
            props[key] = blob.rstrip(b"\0").decode(errors="replace")
        return props

    def format_info(self) -> None:
        self._take(b"f", 0)
        self.u8()
        self.proplist()


@dataclass(slots=True)
class Device:
    """A sink or a source as the server describes it."""

    index: int
    name: str
    description: str
    volume: list[int]
    mute: bool
    props: dict[str, str]
    ports: list[tuple[str, str, int, int, int]] = field(default_factory=list)
    # (name, description, priority, available, type)
    active_port: str = ""

    @property
    def percent(self) -> int:
        return round(sum(self.volume) / len(self.volume) * 100 / NORM) if self.volume else 0


@dataclass(slots=True)
class ServerInfo:
    default_sink: str
    default_source: str


def parse_devices(r: Reader, is_sink: bool) -> list[Device]:
    out: list[Device] = []
    while r.pos < len(r.data):
        index, name, description = r.u32(), r.string() or "", r.string() or ""
        r.skip(b"a", 6)  # sample spec
        r.channel_map()
        r.u32()  # owner module
        volume, mute = r.cvolume(), r.boolean()
        r.u32()  # monitor source / monitor of sink
        r.string()  # its name
        r.skip(b"U", 8)  # latency
        r.string()  # driver
        r.u32()  # flags
        props = r.proplist()
        r.skip(b"U", 8)  # configured latency
        r.skip(b"V", 4)  # base volume
        r.u32()  # state
        r.u32()  # volume steps
        r.u32()  # card
        ports = []
        for _ in range(r.u32()):
            pname, pdesc, prio, avail = r.string() or "", r.string() or "", r.u32(), r.u32()
            r.string()  # availability group (protocol >= 34)
            ports.append((pname, pdesc, prio, avail, r.u32()))
        active = r.string() or ""
        for _ in range(r.u8()):
            r.format_info()
        out.append(Device(index, name, description, volume, mute, props, ports, active))
    return out


class PulseClient:
    """One connection. ``on_event(facility, kind, index)`` and ``on_lost()`` run on the loop."""

    def __init__(
        self,
        path: str,
        on_event: Callable[[int, int, int], None] | None = None,
        on_lost: Callable[[], None] | None = None,
        cookie: bytes = bytes(256),
    ) -> None:
        require_private_path(path)  # spike guard: never the real sound server
        self.path, self.cookie = path, cookie
        self.on_event, self.on_lost = on_event, on_lost
        self._pending: dict[int, asyncio.Future[Reader]] = {}
        self._tag = 0
        self._writer: asyncio.StreamWriter | None = None
        self._task: asyncio.Task[None] | None = None

    async def connect(self, name: str = "tesserae-shell") -> None:
        reader, self._writer = await asyncio.open_unix_connection(self.path)
        self._task = asyncio.create_task(self._read(reader))
        await self.call(AUTH, Tag().u32(VERSION).raw(self.cookie))
        await self.call(SET_CLIENT_NAME, Tag().proplist({"application.name": name}))

    def close(self) -> None:
        if self._task is not None:
            self._task.cancel()
        if self._writer is not None:
            self._writer.close()

    def send(self, command: int, args: Tag | None = None) -> asyncio.Future[Reader]:
        """Write a command now; the future is its reply. Several sends in a row share one round
        trip (the server answers in order)."""
        assert self._writer is not None
        self._tag += 1
        future: asyncio.Future[Reader] = asyncio.get_running_loop().create_future()
        self._pending[self._tag] = future
        body = Tag().u32(command).u32(self._tag)
        payload = bytes(body.buf) + (bytes(args.buf) if args else b"")
        self._writer.write(struct.pack(">IIIII", len(payload), CONTROL, 0, 0, 0) + payload)
        return future

    async def call(self, command: int, args: Tag | None = None) -> Reader:
        return await asyncio.wait_for(self.send(command, args), 5)

    async def _read(self, reader: asyncio.StreamReader) -> None:
        try:
            while True:
                length, channel, *_ = struct.unpack(">IIIII", await reader.readexactly(20))
                payload = await reader.readexactly(length)
                if channel == CONTROL:
                    self._dispatch(Reader(payload))
        except asyncio.IncompleteReadError, ConnectionError, OSError:
            pass
        finally:
            for future in self._pending.values():
                if not future.done():
                    future.set_exception(ConnectionError("pulse connection lost"))
            self._pending.clear()
            if self.on_lost is not None:
                self.on_lost()

    def _dispatch(self, r: Reader) -> None:
        command, tag = r.u32(), r.u32()
        if command == SUBSCRIBE_EVENT and self.on_event is not None:
            event, index = r.u32(), r.u32()
            self.on_event(event & 0x0F, event & 0x30, index)
        elif (future := self._pending.pop(tag, None)) is not None and not future.done():
            if command == REPLY:
                future.set_result(r)
            else:
                future.set_exception(PulseError(r.u32() if command == ERROR else -1))

    # the five commands the module needs --------------------------------------------------
    async def subscribe(self, mask: int = MASK_SINK | MASK_SOURCE | MASK_SERVER) -> None:
        await self.call(SUBSCRIBE, Tag().u32(mask))

    async def snapshot(self) -> tuple[ServerInfo, list[Device], list[Device]]:
        """Server info, sinks and sources in ONE round trip."""
        info, sinks, sources = (
            self.send(GET_SERVER_INFO),
            self.send(GET_SINK_INFO_LIST),
            self.send(GET_SOURCE_INFO_LIST),
        )
        r = await asyncio.wait_for(info, 5)
        for _ in range(4):
            r.string()  # name, version, user, host
        r.skip(b"a", 6)
        server = ServerInfo(r.string() or "", r.string() or "")
        return (
            server,
            parse_devices(await asyncio.wait_for(sinks, 5), True),
            parse_devices(await asyncio.wait_for(sources, 5), False),
        )

    async def set_sink_volume(self, index: int, percent: int, channels: int) -> None:
        level = round(percent * NORM / 100)
        await self.call(SET_SINK_VOLUME, Tag().u32(index).string(None).cvolume([level] * channels))

    async def set_sink_mute(self, index: int, muted: bool) -> None:
        await self.call(SET_SINK_MUTE, Tag().u32(index).string(None).boolean(muted))

    async def set_source_mute(self, index: int, muted: bool) -> None:
        await self.call(SET_SOURCE_MUTE, Tag().u32(index).string(None).boolean(muted))

    async def set_default_sink(self, name: str) -> None:
        await self.call(SET_DEFAULT_SINK, Tag().string(name))
