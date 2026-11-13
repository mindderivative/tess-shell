"""An in-process fake PulseAudio server for the tests of the sound client, the sound service and the
Audio module (Audio Module > Acceptance Criteria).

It speaks the native protocol over a unix socket under a path the test gives (inside pytest's tmp
dir), on its own thread and loop, so the client under test runs on the test's loop or on the
service thread and finds a real server. Nothing here, and nothing a test does with it, touches a
real sound server: the socket is named by the test, and the fake never connects anywhere.

What it answers: ``AUTH`` (checks a cookie when one is required; replies with the lower of the two
protocol versions), ``SET_CLIENT_NAME``, ``SUBSCRIBE``, ``GET_SERVER_INFO``,
``GET_SINK_INFO_LIST``, ``GET_SOURCE_INFO_LIST``, ``SET_SINK_VOLUME``, ``SET_SINK_MUTE``,
``SET_SOURCE_MUTE``, ``SET_DEFAULT_SINK``; and it sends ``SUBSCRIBE_EVENT`` for each change that
changes something. Its encoder of the info lists is written here from the protocol, not from the
client's parser: the fields depend on the protocol version the fake is told to speak (13 to 35).

A ``Fake*`` mutator (``set_volume``, ``set_mute``, ``set_default_sink``, ``add_sink``, ...) is what
"another client" (System Settings) does: it changes the state and sends the event. ``stop``
simulates the server going away (``unlink=False`` leaves a stale socket file, as a killed server
does), ``start`` brings it back on the same path, with the same state.
"""

from __future__ import annotations

import asyncio
import socket
import struct
import threading
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tess_shell.services.pulse_native import (
    AUTH,
    CONTROL,
    ERR_ACCESS,
    ERROR,
    FACILITY_SERVER,
    FACILITY_SINK,
    FACILITY_SOURCE,
    GET_SERVER_INFO,
    GET_SINK_INFO_LIST,
    GET_SOURCE_INFO_LIST,
    NORM,
    REPLY,
    SET_CLIENT_NAME,
    SET_DEFAULT_SINK,
    SET_SINK_MUTE,
    SET_SINK_VOLUME,
    SET_SOURCE_MUTE,
    SUBSCRIBE,
    SUBSCRIBE_EVENT,
    TYPE_CHANGE,
    TYPE_NEW,
    TYPE_REMOVE,
    Reader,
    Tag,
)

NO_INDEX = 0xFFFFFFFF
ERR_NOTIMPLEMENTED = 20
# pa_device_port_type_t: what the fake sends for the types a test names
PORT_CODES = {
    "Unknown": 0,
    "Speaker": 2,
    "Headphones": 3,
    "Line": 4,
    "Mic": 5,
    "Headset": 6,
    "HDMI": 10,
    "TV": 11,
    "USB": 14,
    "Bluetooth": 15,
    "Analog": 22,
}


@dataclass
class FakeDevice:
    index: int
    name: str
    description: str
    volume: list[int]  # per channel, NORM is 100 %
    mute: bool = False
    props: dict[str, str] = field(default_factory=dict)
    ports: list[tuple[str, str, str]] = field(default_factory=list)  # name, description, type
    active: str = ""
    monitor_of: int = NO_INDEX  # a source: the sink it monitors

    def levels(self, percent: float) -> list[int]:
        return [round(percent * NORM / 100)] * len(self.volume)


class FakePulse:
    """See the module docstring."""

    def __init__(
        self,
        folder: Path,
        *,
        version: int = 35,
        cookie: bytes | None = None,
    ) -> None:
        self.socket = folder / "pulse" / "native"
        self.version = version
        self.cookie = cookie  # a cookie the clients must send (``None``: any is accepted)
        self.sinks: list[FakeDevice] = []
        self.sources: list[FakeDevice] = []
        self.default_sink = ""
        self.default_source = ""
        self.commands: list[tuple[str, tuple[Any, ...]]] = []  # the setters a client called
        self.auths: list[bytes] = []  # the cookie of each AUTH
        self.connections = 0
        self._next = 0
        self._writers: dict[asyncio.StreamWriter, int] = {}  # connection -> subscription mask
        self._server: asyncio.Server | None = None
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="fake-pulse", daemon=True)
        self._thread.start()

    # -- the thread ---------------------------------------------------------------------------
    def _run(self) -> None:
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def sync[T](self, fn: Callable[[], T]) -> T:
        """Run ``fn`` on the fake's thread and wait for it."""
        return asyncio.run_coroutine_threadsafe(self._call(fn), self._loop).result(5)

    @staticmethod
    async def _call[T](fn: Callable[[], T]) -> T:
        return fn()

    def _coro[T](self, coro: Coroutine[Any, Any, T]) -> T:
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(5)

    def close(self) -> None:
        """Stop the server and the thread (the test's teardown)."""
        self.stop()
        self._loop.call_soon_threadsafe(self._loop.stop)
        self._thread.join(5)
        self._loop.close()

    # -- the server's life --------------------------------------------------------------------
    def start(self) -> None:
        self._coro(self._start())

    async def _start(self) -> None:
        self.socket.parent.mkdir(parents=True, exist_ok=True)
        if self.socket.exists():
            self.socket.unlink()
        self._server = await asyncio.start_unix_server(self._serve, str(self.socket))

    def stop(self, *, unlink: bool = True) -> None:
        """The server goes away: the listener and every connection close."""
        self._coro(self._stop(unlink))

    async def _stop(self, unlink: bool) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
        for writer in list(self._writers):
            writer.close()
        self._writers.clear()
        if unlink and self.socket.exists():
            self.socket.unlink()
        elif not unlink and not self.socket.exists():
            # asyncio unlinks the socket when its server closes; a killed server does not
            stale = socket.socket(socket.AF_UNIX)
            stale.bind(str(self.socket))
            stale.close()

    def drop_connections(self) -> None:
        """Close every connection, keep listening."""

        def close_all() -> None:
            for writer in list(self._writers):
                writer.close()

        self.sync(close_all)

    @property
    def listening(self) -> bool:
        return self._server is not None

    @property
    def clients(self) -> int:
        return len(self._writers)

    # -- the state ----------------------------------------------------------------------------
    def _index(self) -> int:
        self._next += 1
        return self._next

    def add_sink(
        self,
        name: str,
        description: str = "",
        *,
        percent: float = 100,
        channels: int = 2,
        form_factor: str = "",
        bus: str = "",
        ports: list[tuple[str, str, str]] | None = None,
        active: str = "",
        default: bool = False,
    ) -> FakeDevice:
        """A sink (an output) and its monitor source, as a server lists them."""
        props = {"device.description": description or name}
        if form_factor:
            props["device.form_factor"] = form_factor
        if bus:
            props["device.bus"] = bus
        sink = FakeDevice(
            self._index(), name, description or name, [round(percent * NORM / 100)] * channels
        )
        sink.props = props
        sink.ports = ports or []
        sink.active = active or (sink.ports[0][0] if sink.ports else "")

        def add() -> None:
            self.sinks.append(sink)
            self.sources.append(
                FakeDevice(
                    self._index(),
                    f"{name}.monitor",
                    f"Monitor of {sink.description}",
                    list(sink.volume),
                    props={"device.class": "monitor"},
                    monitor_of=sink.index,
                )
            )
            if default or not self.default_sink:
                self.default_sink = name
            self._event(FACILITY_SINK, TYPE_NEW, sink.index)

        self.sync(add)
        return sink

    def add_source(self, name: str, description: str = "", *, muted: bool = False) -> FakeDevice:
        """A microphone."""
        source = FakeDevice(
            self._index(), name, description or name, [NORM, NORM], muted, {"device.class": "sound"}
        )

        def add() -> None:
            self.sources.append(source)
            if not self.default_source or self.default_source.endswith(".monitor"):
                self.default_source = name
            self._event(FACILITY_SOURCE, TYPE_NEW, source.index)

        self.sync(add)
        return source

    def remove_source(self, name: str) -> None:
        """A microphone goes away; the server names a monitor (or nothing) as the default input."""

        def remove() -> None:
            source = self.source(name)
            self.sources.remove(source)
            if self.default_source == name:
                monitors = [s for s in self.sources if s.monitor_of != NO_INDEX]
                self.default_source = monitors[0].name if monitors else ""
                self._event(FACILITY_SERVER, TYPE_CHANGE, NO_INDEX)
            self._event(FACILITY_SOURCE, TYPE_REMOVE, source.index)

        self.sync(remove)

    def remove_sink(self, name: str) -> None:
        def remove() -> None:
            sink = self.sink(name)
            self.sinks.remove(sink)
            self.sources[:] = [s for s in self.sources if s.monitor_of != sink.index]
            if self.default_sink == name:
                self.default_sink = self.sinks[0].name if self.sinks else ""
                self._event(FACILITY_SERVER, TYPE_CHANGE, NO_INDEX)
            self._event(FACILITY_SINK, TYPE_REMOVE, sink.index)

        self.sync(remove)

    def sink(self, name: str) -> FakeDevice:
        return next(s for s in self.sinks if s.name == name)

    def source(self, name: str) -> FakeDevice:
        return next(s for s in self.sources if s.name == name)

    def set_volume(self, name: str, percent: float | list[int]) -> None:
        """Another client sets a sink's volume (a percent for every channel, or the levels)."""

        def go() -> None:
            sink = self.sink(name)
            levels = sink.levels(percent) if not isinstance(percent, list) else list(percent)
            self._set_volume(sink, levels)

        self.sync(go)

    def set_mute(self, name: str, muted: bool) -> None:
        self.sync(lambda: self._set_mute(self.sink(name), muted, FACILITY_SINK))

    def set_source_mute(self, name: str, muted: bool) -> None:
        self.sync(lambda: self._set_mute(self.source(name), muted, FACILITY_SOURCE))

    def set_default_sink(self, name: str) -> None:
        self.sync(lambda: self._set_default(name))

    def set_default_source(self, name: str) -> None:
        def go() -> None:
            self.default_source = name
            self._event(FACILITY_SERVER, TYPE_CHANGE, NO_INDEX)

        self.sync(go)

    def set_active_port(self, name: str, port: str) -> None:
        def go() -> None:
            sink = self.sink(name)
            sink.active = port
            self._event(FACILITY_SINK, TYPE_CHANGE, sink.index)

        self.sync(go)

    def _set_volume(self, dev: FakeDevice, levels: list[int]) -> None:
        if levels != dev.volume:
            dev.volume = levels
            self._event(FACILITY_SINK, TYPE_CHANGE, dev.index)

    def _set_mute(self, dev: FakeDevice, muted: bool, facility: int) -> None:
        if muted != dev.mute:
            dev.mute = muted
            self._event(facility, TYPE_CHANGE, dev.index)

    def _set_default(self, name: str) -> None:
        if name != self.default_sink:
            self.default_sink = name
            self._event(FACILITY_SERVER, TYPE_CHANGE, NO_INDEX)

    # -- the protocol -------------------------------------------------------------------------
    def _event(self, facility: int, kind: int, index: int) -> None:
        mask = {FACILITY_SINK: 0x01, FACILITY_SOURCE: 0x02, FACILITY_SERVER: 0x80}[facility]
        payload = Tag().u32(SUBSCRIBE_EVENT).u32(NO_INDEX).u32(facility | kind).u32(index)
        for writer, subscribed in list(self._writers.items()):
            if subscribed & mask:
                self._write(writer, bytes(payload.buf))

    @staticmethod
    def _write(writer: asyncio.StreamWriter, payload: bytes) -> None:
        writer.write(struct.pack(">IIIII", len(payload), CONTROL, 0, 0, 0) + payload)

    def _reply(self, writer: asyncio.StreamWriter, tag: int, body: Tag | None = None) -> None:
        payload = Tag().u32(REPLY).u32(tag)
        self._write(writer, bytes(payload.buf) + (bytes(body.buf) if body else b""))

    def _error(self, writer: asyncio.StreamWriter, tag: int, code: int) -> None:
        self._write(writer, bytes(Tag().u32(ERROR).u32(tag).u32(code).buf))

    async def _serve(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.connections += 1
        self._writers[writer] = 0
        try:
            while True:
                length, channel, *_ = struct.unpack(">IIIII", await reader.readexactly(20))
                payload = await reader.readexactly(length)
                if channel == CONTROL and not self._command(writer, Reader(payload)):
                    break
                await writer.drain()
        except asyncio.IncompleteReadError, ConnectionError, OSError:
            pass
        finally:
            self._writers.pop(writer, None)
            writer.close()

    def _command(self, writer: asyncio.StreamWriter, r: Reader) -> bool:
        """Answer one command; ``False`` closes the connection."""
        command, tag = r.u32(), r.u32()
        if command == AUTH:
            version = r.u32()
            cookie = r.raw()
            self.auths.append(cookie)
            if self.cookie is not None and cookie != self.cookie:
                self._error(writer, tag, ERR_ACCESS)
                return False
            self._reply(writer, tag, Tag().u32(min(version & 0xFFFF, self.version)))
        elif command == SET_CLIENT_NAME:
            self._reply(writer, tag, Tag().u32(self._index()))
        elif command == SUBSCRIBE:
            self._writers[writer] = r.u32()
            self._reply(writer, tag)
        elif command == GET_SERVER_INFO:
            self._reply(writer, tag, self._server_info())
        elif command == GET_SINK_INFO_LIST:
            self._reply(writer, tag, self._device_list(self.sinks, sink=True))
        elif command == GET_SOURCE_INFO_LIST:
            self._reply(writer, tag, self._device_list(self.sources, sink=False))
        elif command == SET_SINK_VOLUME:
            index, _name, volume = r.u32(), r.string(), r.cvolume()
            self.commands.append(("set_sink_volume", (index, volume)))
            self._set_volume(self._by_index(self.sinks, index), volume)
            self._reply(writer, tag)
        elif command in (SET_SINK_MUTE, SET_SOURCE_MUTE):
            index, _name, muted = r.u32(), r.string(), r.boolean()
            sink = command == SET_SINK_MUTE
            self.commands.append(("set_sink_mute" if sink else "set_source_mute", (index, muted)))
            dev = self._by_index(self.sinks if sink else self.sources, index)
            self._set_mute(dev, muted, FACILITY_SINK if sink else FACILITY_SOURCE)
            self._reply(writer, tag)
        elif command == SET_DEFAULT_SINK:
            name = r.string() or ""
            self.commands.append(("set_default_sink", (name,)))
            if not any(s.name == name for s in self.sinks):
                self._error(writer, tag, 5)  # no entity
            else:
                self._set_default(name)
                self._reply(writer, tag)
        else:
            self._error(writer, tag, ERR_NOTIMPLEMENTED)
        return True

    @staticmethod
    def _by_index(devices: list[FakeDevice], index: int) -> FakeDevice:
        return next(d for d in devices if d.index == index)

    def _server_info(self) -> Tag:
        t = Tag().string("fake-pulse").string("15.0.0").string("tester").string("fake-host")
        t.sample_spec().string(self.default_sink).string(self.default_source).u32(0xC0FFEE)
        if self.version >= 15:
            t.channel_map([1, 2])
        return t

    def _device_list(self, devices: list[FakeDevice], *, sink: bool) -> Tag:
        t = Tag()
        v = self.version
        for d in devices:
            t.u32(d.index).string(d.name).string(d.description).sample_spec()
            t.channel_map([1, 2][: len(d.volume)]).u32(NO_INDEX).cvolume(d.volume).boolean(d.mute)
            if sink:  # a sink's monitor source: the one the fake made for it
                monitor = next((s for s in self.sources if s.monitor_of == d.index), None)
                t.u32(monitor.index if monitor else NO_INDEX)
                t.string(monitor.name if monitor else None)
            else:  # a source: the sink it monitors
                t.u32(d.monitor_of)
                owner = next((s for s in self.sinks if s.index == d.monitor_of), None)
                t.string(owner.name if owner else None)
            t.usec(0).string("fake").u32(0x00000000)
            if v >= 13:
                t.proplist(d.props).usec(0)
            if v >= 15:
                t.volume(NORM).u32(2).u32(65537).u32(NO_INDEX)
            if v >= 16:
                t.u32(len(d.ports))
                for pname, pdesc, ptype in d.ports:
                    t.string(pname).string(pdesc).u32(100)
                    if v >= 24:
                        t.u32(0)
                    if v >= 34:
                        t.string(None).u32(PORT_CODES[ptype])
                t.string(d.active or None)
            if v >= 21:
                t.u8(1).format_info()
        return t
