"""The sound service: what the Audio module reads and sets (Audio Module; ADR-0021 Audio Access).

One :class:`AudioService` per shell lives on the ``dbus`` service thread's asyncio loop beside the
D-Bus layer. It owns one :class:`~tess_shell.services.pulse_native.PulseClient`: connect, subscribe,
and on every sink, source or server event read the server's state once (three commands, one round
trip) and hand the modules the new :class:`~tess_shell.services.api.AudioState` when it differs
from the last one. Nothing runs between events: no timer, no thread, no subprocess.

Reconnecting has no timer either. While there is no server (or the connection broke and a connect
fails) the service watches the socket's folder with inotify (the nearest folder that exists, so a
runtime folder that has no ``pulse`` yet is handled) and tries again when something is created
there; while connected it holds no watch. A connect that is refused right after the socket appears
(the server has bound it and not yet listened) is tried three times, 50 ms apart; a connection that
ends within a second of its start waits one second before the next try, so a server that accepts
and drops cannot make a tight loop.

A module reaches it through ``ctx.audio`` (:class:`~tess_shell.services.api.ModuleAudio`).
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import time
from collections import deque
from collections.abc import Callable, Coroutine, Mapping
from pathlib import Path
from typing import Any

from inotify_simple import INotify, flags
from loguru import logger

from tess_shell.services.api import (
    AudioCallback,
    AudioError,
    AudioState,
    AudioUnavailable,
    Output,
    Subscription,
)
from tess_shell.services.bus import ServiceThread
from tess_shell.services.pulse_native import (
    NO_INDEX,
    Device,
    PulseAuthError,
    PulseClient,
    PulseError,
    default_socket,
    read_cookie,
    scaled,
)

WARN_EVERY = 60.0  # seconds between two warnings about a failed call of one module
SLOW_CALLBACK = 0.05  # a module's callback over this is a warning
CONNECT_TRIES = 3  # a connect refused right after the socket appeared
CONNECT_RETRY = 0.05  # seconds between those
SHORT_SESSION = 1.0  # a connection that ended sooner than this waits before the next try
HINT_TTL = 1.0  # s: a written volume stays the next step's base until the server shows it
_STATS_KEPT = 4096

# device.form_factor -> kind; a form factor not listed here is passed over (the port type, then
# the bus, decide)
FORM_FACTORS = {
    "headphone": "HEADPHONES",
    "headset": "HEADPHONES",
    "speaker": "SPEAKER",
    "internal": "SPEAKER",
    "tv": "HDMI",
    "hdmi": "HDMI",
}
# the type of the active port -> kind (a server below protocol 34 sends no type)
PORT_KINDS = {
    "Headphones": "HEADPHONES",
    "Headset": "HEADPHONES",
    "HDMI": "HDMI",
    "TV": "HDMI",
    "Speaker": "SPEAKER",
    "Analog": "SPEAKER",
    "Line": "SPEAKER",
    "Bluetooth": "BLUETOOTH",
}


def output_kind(props: Mapping[str, str], port_kind: str) -> str:
    """The kind of an output (Audio Module > Kind and Icon): a Bluetooth bus wins whatever the
    form factor says; else the form factor; else the active port's type; else ``SPEAKER``."""
    if props.get("device.bus") == "bluetooth":
        return "BLUETOOTH"
    kind = FORM_FACTORS.get(props.get("device.form_factor", ""))
    if kind is None:
        kind = PORT_KINDS.get(port_kind)
    return kind or "SPEAKER"


def output_of(dev: Device) -> Output:
    return Output(
        dev.name,
        dev.description or dev.props.get("device.description", "") or dev.name,
        output_kind(dev.props, dev.port_kind),
    )


def is_monitor(dev: Device) -> bool:
    """A source that is a sink's monitor is not a microphone."""
    return dev.monitor != NO_INDEX or dev.props.get("device.class") == "monitor"


class SocketWatch:
    """An inotify watch on the nearest existing folder above (or holding) the socket, armed only
    while no connection exists."""

    def __init__(self, path: Path, loop: asyncio.AbstractEventLoop) -> None:
        self._path = path
        self._loop = loop
        self._ino: INotify | None = None
        self._wd: int | None = None
        self._dir: Path | None = None
        self._event = asyncio.Event()

    def arm(self) -> None:
        """Watch the nearest existing folder; forget the events of before (the caller looks at the
        file system after this, so nothing that happened earlier is needed)."""
        folder = self._path.parent
        while not folder.exists() and folder != folder.parent:
            folder = folder.parent
        ino = self._ino
        if ino is None:
            ino = self._ino = INotify(nonblocking=True)
            self._loop.add_reader(ino.fd, self._readable)
        if self._dir != folder or self._wd is None:
            self._drop_watch()
            self._wd = ino.add_watch(str(folder), flags.CREATE | flags.MOVED_TO)
            self._dir = folder
        self._event.clear()

    def _drop_watch(self) -> None:
        if self._ino is not None and self._wd is not None:
            try:
                self._ino.rm_watch(self._wd)
            except OSError:  # the folder is gone, and the watch with it
                pass
        self._wd = None
        self._dir = None

    def disarm(self) -> None:
        """No watch, no reader: a connected service wakes only for its socket."""
        self._drop_watch()
        if self._ino is not None:
            self._loop.remove_reader(self._ino.fd)
            self._ino.close()
            self._ino = None

    def _readable(self) -> None:
        assert self._ino is not None
        for event in self._ino.read(timeout=0):
            if event.mask & flags.IGNORED:  # the watched folder was removed
                self._wd = None
                self._dir = None
        self._event.set()

    async def changed(self) -> None:
        """Wait for the next event of the watched folder."""
        await self._event.wait()


class _Sub:
    def __init__(self, service: AudioService, module: str, callback: AudioCallback) -> None:
        self.service, self.module, self.callback = service, module, callback
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True
        self.service.service.post(lambda: self.service.drop(self))


class AudioService:
    """See the module docstring. ``socket`` is the server's socket (a test names its own; ``None``
    asks the environment, :func:`~tess_shell.services.pulse_native.default_socket`); ``env`` is the
    environment that is read for it and for the cookie (``os.environ`` when ``None``); ``cookie`` is
    given instead of reading the user's cookie file."""

    def __init__(
        self,
        service: ServiceThread,
        socket: Path | None = None,
        *,
        env: Mapping[str, str] | None = None,
        cookie: bytes | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.service = service
        self._socket = socket
        self._env = env
        self._cookie = cookie
        self._clock = clock
        self._started = False
        self._subs: list[_Sub] = []
        self._state: AudioState | None = None
        self._settled = False  # the first connect has ended (a connection or a failure)
        self._client: PulseClient | None = None
        self._sinks: list[Device] = []
        self._sources: list[Device] = []
        self._default_sink = ""
        self._default_source = ""
        self._busy = False
        self._dirty = False
        # what a setter wrote, until the server's read shows it (or HINT_TTL has passed): a read of
        # an EARLIER step's echo must not make the next step start from the stale value
        self._volume_hint: float | None = None
        self._volume_hint_at = 0.0
        self._mute_hint: bool | None = None
        self._mic_hint: bool | None = None
        self._tasks: set[asyncio.Future[Any]] = set()
        self._warned: dict[str, float] = {}
        self.callback_times: dict[str, deque[float]] = {}  # module -> seconds of each callback
        self.reads = 0  # snapshots read (a test counts them)
        self.connects = 0

    # -- what any thread may read -----------------------------------------------------------------

    @property
    def state(self) -> AudioState | None:
        return self._state

    @property
    def available(self) -> bool:
        return self._state is not None

    def for_module(self, module: str) -> _ModuleAudio:
        return _ModuleAudio(self, module)

    def callback_summary(self, module: str | None = None) -> tuple[int, float, float, float]:
        """``(count, p50, p99, max)`` in seconds of the callbacks run on the service thread."""
        pool = (
            list(self.callback_times.get(module, ()))
            if module is not None
            else [t for times in self.callback_times.values() for t in times]
        )
        ordered = sorted(pool)

        def at(fraction: float) -> float:
            return ordered[min(len(ordered) - 1, round(fraction * (len(ordered) - 1)))]

        if not ordered:
            return (0, 0.0, 0.0, 0.0)
        return (len(ordered), at(0.5), at(0.99), ordered[-1])

    def ensure_started(self) -> None:
        """Start the connection loop on the service thread (once; any thread)."""
        if not self._started:
            self._started = True
            self.service.submit(self._run())

    # -- the connection loop (service thread) -----------------------------------------------------

    async def _run(self) -> None:
        env = self._env if self._env is not None else os.environ
        path = self._socket or default_socket(env)
        if path is None:
            logger.info("audio: no local sound-server socket is named; the module stays hidden")
            self._set_settled()
            return
        watch = SocketWatch(path, asyncio.get_running_loop())
        warned_auth = False
        try:
            while True:
                watch.arm()
                try:
                    client = await self._connect(path, env)
                except PulseAuthError:
                    client = None
                    if not warned_auth:
                        warned_auth = True
                        logger.warning(
                            f"audio: the sound server at {path} refused the cookie; "
                            "the Audio module stays hidden"
                        )
                if client is None:
                    self._set_settled()
                    await watch.changed()
                    continue
                warned_auth = False
                watch.disarm()
                started = self._clock()
                self.connects += 1
                logger.info(f"audio: connected to the sound server (protocol {client.version})")
                try:
                    await self._session(client)
                finally:
                    client.close()
                    self._client = None
                    self._volume_hint = self._mute_hint = self._mic_hint = None
                    self._publish(None)
                logger.info("audio: the sound server went away")
                if self._clock() - started < SHORT_SESSION:
                    await asyncio.sleep(SHORT_SESSION)
        finally:
            watch.disarm()
            for task in list(self._tasks):
                task.cancel()

    def _set_settled(self) -> None:
        """The first connect ended without a connection: tell the subscribers there is none."""
        if not self._settled:
            self._settled = True
            for sub in list(self._subs):
                self._notify(sub, None)

    async def _connect(self, path: Path, env: Mapping[str, str]) -> PulseClient | None:
        for attempt in range(CONNECT_TRIES):
            if not path.exists():
                return None
            try:
                return await self._open(path, self._cookie or bytes(256))
            except PulseAuthError:
                cookie = self._cookie or read_cookie(env)
                if cookie is None:
                    raise
                return await self._open(path, cookie)  # a second refusal raises
            except ConnectionRefusedError:
                if attempt + 1 < CONNECT_TRIES:
                    await asyncio.sleep(CONNECT_RETRY)
            except (OSError, PulseError) as exc:
                logger.debug(f"audio: connecting to {path} failed: {exc}")
                return None
        return None

    async def _open(self, path: Path, cookie: bytes) -> PulseClient:
        client = PulseClient(path, self._event, None, cookie)
        try:
            await client.connect()
        except BaseException:
            client.close()
            raise
        return client

    async def _session(self, client: PulseClient) -> None:
        self._client = client
        try:
            await client.subscribe()
            self._dirty = True
            await self._refresh()
        except (PulseError, ConnectionError, OSError) as exc:
            logger.debug(f"audio: the first read failed: {exc}")
            return
        await client.lost.wait()

    # -- reading (service thread) -----------------------------------------------------------------

    def _event(self, facility: int, kind: int, index: int) -> None:
        self._dirty = True
        if not self._busy:
            task = asyncio.get_running_loop().create_task(self._refresh())
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    async def _refresh(self) -> None:
        client = self._client
        if client is None or self._busy:
            return
        self._busy = True
        try:
            while self._dirty and self._client is client:
                self._dirty = False
                server, sinks, sources = await client.snapshot()
                self.reads += 1
                self._sinks, self._sources = sinks, sources
                self._default_sink = server.default_sink
                self._default_source = server.default_source
                self._apply()
        except (PulseError, ConnectionError, OSError) as exc:
            logger.debug(f"audio: a read failed: {exc}")  # the connection's loss follows
        finally:
            self._busy = False

    def _apply(self) -> None:
        sink = self._device(self._sinks, self._default_sink)
        source = self._device(self._sources, self._default_source)
        mic = source is not None and not is_monitor(source)
        self._mute_hint = self._mic_hint = None
        if self._volume_hint is not None and (
            sink is None
            or abs(float(sink.percent) - self._volume_hint) <= 0.5
            or self._clock() - self._volume_hint_at > HINT_TTL
        ):
            self._volume_hint = None
        self._publish(
            AudioState(
                output_of(sink) if sink else None,
                sink.percent if sink else 0,
                sink.mute if sink else False,
                mic,
                bool(mic and source and source.mute),
                tuple(output_of(d) for d in self._sinks),
            )
        )

    @staticmethod
    def _device(devices: list[Device], name: str) -> Device | None:
        return next((d for d in devices if d.name == name), None)

    # -- the subscribers (service thread) ---------------------------------------------------------

    def _publish(self, state: AudioState | None) -> None:
        self._settled = True
        if state == self._state:
            return
        self._state = state
        for sub in list(self._subs):
            self._notify(sub, state)

    def _notify(self, sub: _Sub, state: AudioState | None) -> None:
        if sub.cancelled:
            return
        start = time.perf_counter()
        try:
            sub.callback(state)
        except Exception:
            logger.bind(source=f"module:{sub.module}").opt(exception=True).error(
                "an audio callback raised"
            )
        took = time.perf_counter() - start
        self.callback_times.setdefault(sub.module, deque(maxlen=_STATS_KEPT)).append(took)
        if took > SLOW_CALLBACK:
            logger.warning(
                f"module {sub.module}: an audio callback took {took * 1000:.0f} ms on the "
                f"service thread (over {SLOW_CALLBACK * 1000:.0f} ms); hand slow work to a thread"
            )

    def add(self, sub: _Sub) -> None:  # service thread
        if sub.cancelled:
            return
        self._subs.append(sub)
        if self._settled:
            self._notify(sub, self._state)

    def drop(self, sub: _Sub) -> None:  # service thread
        if sub in self._subs:
            self._subs.remove(sub)

    # -- the setters (service thread; each is a coroutine the helper runs) ------------------------

    def _need(self) -> PulseClient:
        if self._client is None:
            raise AudioUnavailable("there is no sound server")
        return self._client

    def _default(self) -> Device:
        sink = self._device(self._sinks, self._default_sink)
        if sink is None:
            raise AudioError("the sound server has no default output")
        return sink

    async def set_volume(self, percent: float) -> None:
        client, sink = self._need(), self._default()
        percent = min(max(percent, 0.0), 100.0)
        self._volume_hint = percent  # before the await: the next step starts from it
        self._volume_hint_at = self._clock()
        try:
            await client.set_sink_volume(sink.index, scaled(sink.volume, percent))
        except BaseException:
            self._volume_hint = None
            raise

    async def step(self, delta: float) -> None:
        sink = self._default()
        base = self._volume_hint if self._volume_hint is not None else float(sink.percent)
        await self.set_volume(base + delta)

    async def set_muted(self, muted: bool) -> None:
        client, sink = self._need(), self._default()
        self._mute_hint = muted
        try:
            await client.set_sink_mute(sink.index, muted)
        except BaseException:
            self._mute_hint = None
            raise

    async def toggle_mute(self) -> None:
        sink = self._default()
        now = self._mute_hint if self._mute_hint is not None else sink.mute
        await self.set_muted(not now)

    async def toggle_mic(self) -> None:
        client = self._need()
        source = self._device(self._sources, self._default_source)
        if source is None or is_monitor(source):
            raise AudioError("the sound server has no default input")
        now = self._mic_hint if self._mic_hint is not None else source.mute
        self._mic_hint = not now
        try:
            await client.set_source_mute(source.index, not now)
        except BaseException:
            self._mic_hint = None
            raise

    async def set_output(self, name: str) -> None:
        client = self._need()
        if self._device(self._sinks, name) is None:
            raise AudioError(f"the sound server has no output {name!r}")
        await client.set_default_sink(name)

    def warn_limited(self, key: str, message: str) -> None:
        """A warning, at most one per ``key`` in :data:`WARN_EVERY` seconds; the rest are debug."""
        now = self._clock()
        last = self._warned.get(key)
        if last is None or now - last >= WARN_EVERY:
            self._warned[key] = now
            logger.warning(message)
        else:
            logger.debug(message)


class _ModuleAudio:
    """``ctx.audio`` of one module."""

    def __init__(self, audio: AudioService, module: str) -> None:
        self._audio = audio
        self.module = module
        self._subs: list[_Sub] = []
        self.log = logger.bind(source=f"module:{module}")

    @property
    def available(self) -> bool:
        return self._audio.available

    @property
    def state(self) -> AudioState | None:
        return self._audio.state

    def on_changed(self, callback: AudioCallback) -> Subscription:
        sub = _Sub(self._audio, self.module, callback)
        self._subs.append(sub)
        self._audio.ensure_started()
        self._audio.service.post(lambda: self._audio.add(sub))
        return sub

    def _run(
        self, name: str, make: Callable[[], Coroutine[Any, Any, None]]
    ) -> concurrent.futures.Future[None]:
        self._audio.ensure_started()
        future = self._audio.service.submit(make())
        future.add_done_callback(lambda f: self._done(name, f))
        return future

    def _done(self, name: str, future: concurrent.futures.Future[None]) -> None:
        """A call ended: a failure is logged once a minute for the module."""
        if future.cancelled() or future.exception() is None:
            return
        self._audio.warn_limited(
            f"{self.module}:{name}", f"module {self.module}: {name} failed: {future.exception()}"
        )

    def set_volume(self, percent: float) -> concurrent.futures.Future[None]:
        return self._run("set_volume", lambda: self._audio.set_volume(percent))

    def step(self, delta: float) -> concurrent.futures.Future[None]:
        return self._run("step", lambda: self._audio.step(delta))

    def set_muted(self, muted: bool) -> concurrent.futures.Future[None]:
        return self._run("set_muted", lambda: self._audio.set_muted(muted))

    def toggle_mute(self) -> concurrent.futures.Future[None]:
        return self._run("toggle_mute", self._audio.toggle_mute)

    def toggle_mic(self) -> concurrent.futures.Future[None]:
        return self._run("toggle_mic", self._audio.toggle_mic)

    def set_output(self, name: str) -> concurrent.futures.Future[None]:
        return self._run("set_output", lambda: self._audio.set_output(name))

    def close(self) -> None:
        for sub in self._subs:
            sub.cancel()
        self._subs.clear()
