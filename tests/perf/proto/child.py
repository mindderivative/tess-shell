"""The module process of the posture B prototype: ``python -m tests.perf.proto.child``.

Runs one module file's ``Module`` class with a REAL :class:`~tess_shell.modules.context.
ModuleContext` whose ports are either services of this process (B1: its own D-Bus connection, its
own PulseAudio connection, its own tray host) or proxies that ask the shell over the pipe (B2, and
always for what only the shell can do: popups, surfaces, the window list, the application index and
the icon registry). The module's own code is unchanged: it gets the same ``ctx``.

Threads of this process: the MAIN thread is "the loop" (a ``SimpleQueue`` of callables: messages from
the shell, ticks, the service hooks, ``ctx.call_soon``); a reader thread and a writer thread belong
to the pipe; a time source thread exists only while the module subscribed a tick; the D-Bus service
thread (B1) or the proxy service thread (B2) exists only after ``ctx.dbus`` or ``ctx.audio`` was
used. An idle module process wakes for nothing.

The running-callback record is shared memory (a memfd the shell passed in): two stores around each
callback, read by the shell's watchdog, so a hung callback is noticed without a message.
"""

from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import importlib.util
import inspect
import mmap
import os
import queue
import signal
import socket
import struct
import sys
import threading
import time
from collections.abc import Callable
from typing import Any

from loguru import logger
from tests.perf.proto.wire import Channel, encode_error

from tess_shell.model.store import plain
from tess_shell.module import Event, Module
from tess_shell.modules.context import ModuleContext, UseRecord
from tess_shell.modules.ticks import TimeSource
from tess_shell.services.api import (
    AudioError,
    ServiceError,
    ServiceTimeout,
    ServiceUnavailable,
)

PACKAGE = "tess_shell_user_modules"
ENTRY_AT = 16  # offset of the entry name in the shared record
ENTRY_MAX = 64


class ShmRecord:
    """The child's side of the running-callback record: ``enter``, ``leave`` and ``run`` as
    :class:`~tess_shell.modules.running.CallbackRecord` has them, stored in shared memory. The
    first 8 bytes are the monotonic start of the callback in nanoseconds (0: none is running)."""

    def __init__(self, mm: mmap.mmap) -> None:
        self._mm = mm
        self._current: tuple[str, str] | None = None

    def enter(self, module: str, entry: str) -> tuple[str, str] | None:
        previous = self._current
        self._current = (module, entry)
        if previous is None:
            raw = entry.encode("utf-8", "replace")[:ENTRY_MAX]
            self._mm[ENTRY_AT : ENTRY_AT + ENTRY_MAX] = raw.ljust(ENTRY_MAX, b"\0")
            struct.pack_into("<q", self._mm, 0, time.monotonic_ns())
        return previous

    def leave(self, previous: tuple[str, str] | None) -> None:
        self._current = previous
        if previous is None:
            struct.pack_into("<q", self._mm, 0, 0)

    def run(self, module: str, entry: str, fn: Callable[..., Any], *args: Any) -> Any:
        previous = self.enter(module, entry)
        try:
            return fn(*args)
        finally:
            self.leave(previous)

    def forget(self, module: str) -> None:
        return None


class Loop:
    """What the shell's loop thread is to a module: one thread runs what was queued, in order."""

    def __init__(self) -> None:
        self._queue: queue.SimpleQueue[Callable[[], None] | None] = queue.SimpleQueue()
        self.ident = 0

    def put(self, fn: Callable[[], None]) -> None:
        self._queue.put(fn)

    def stop(self) -> None:
        self._queue.put(None)

    def run(self) -> None:
        self.ident = threading.get_ident()
        while True:
            fn = self._queue.get()
            if fn is None:
                return
            try:
                fn()
            except Exception:
                logger.opt(exception=True).error("a callback of the module process raised")


class AioThread:
    """The proxy service thread (B2): an asyncio loop for the coroutines a module hands to
    ``Bus.run`` and for the callbacks the shell pushes (they ran on the D-Bus thread there)."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="proxy-service", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    @property
    def ident(self) -> int | None:
        return self._thread.ident

    def post(self, fn: Callable[[], None]) -> None:
        self.loop.call_soon_threadsafe(fn)

    def stop(self) -> None:
        self.loop.call_soon_threadsafe(self.loop.stop)


def raise_remote(err: dict[str, Any]) -> None:
    """Raise what the shell's side raised, as the class the module expects."""
    kind = err.get("type", "RuntimeError")
    args = err.get("args", [])
    if kind in ("ServiceError", "ServiceTimeout", "ServiceUnavailable") and len(args) == 3:
        cls = {
            "ServiceError": ServiceError,
            "ServiceTimeout": ServiceTimeout,
            "ServiceUnavailable": ServiceUnavailable,
        }[kind]
        raise cls(*args)
    if kind == "AudioError":
        raise AudioError(err.get("msg", ""))
    if kind == "ValueError":
        raise ValueError(err.get("msg", ""))
    raise RuntimeError(f"{kind}: {err.get('msg', '')}")


class Child:
    def __init__(self, sock: socket.socket, mm: mmap.mmap) -> None:
        self.loop = Loop()
        self.record = ShmRecord(mm)
        self.channel = Channel(sock, self._on_message, self._on_closed, "proto")
        self.name = "?"
        self.mode = "B1"
        self.ctx: ModuleContext | None = None
        self.instance: Module | None = None
        self.ticks = TimeSource()
        self._ids = 0
        self._ids_lock = threading.Lock()
        self._pending: dict[int, Callable[[bool, Any], None]] = {}
        self._callbacks: dict[
            int, tuple[Callable[..., Any], str, Callable[..., tuple[Any, ...]] | None]
        ] = {}
        self._service: Any = None  # the B1 ServiceThread
        self._layer: Any = None
        self._audio: Any = None
        self._tray: Any = None
        self._aio: AioThread | None = None
        self._proxies: dict[str, Any] = {}

    # -- ids, rpc, callbacks (any thread) -------------------------------------------------------

    def next_id(self) -> int:
        with self._ids_lock:
            self._ids += 1
            return self._ids

    def cmd(self, method: str, *args: Any) -> None:
        """A call that wants no answer."""
        self.channel.send({"t": "cmd", "m": method, "a": args})

    def rpc(self, method: str, *args: Any, timeout: float = 5.0) -> Any:
        """A call that waits for the shell's answer (a thread of the module, never the reader)."""
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        rid = self.next_id()

        def done(ok: bool, value: Any) -> None:
            if ok:
                future.set_result(value)
            else:
                try:
                    raise_remote(value)
                except Exception as exc:
                    future.set_exception(exc)

        self._pending[rid] = done
        if not self.channel.send({"t": "rpc", "id": rid, "m": method, "a": args}):
            self._pending.pop(rid, None)
            raise RuntimeError("the shell is gone")
        try:
            return future.result(timeout)
        except concurrent.futures.TimeoutError:
            self._pending.pop(rid, None)
            raise ServiceTimeout(method, "the shell did not answer") from None

    def call_future(self, method: str, *args: Any) -> concurrent.futures.Future[Any]:
        """A call whose answer completes a future (set from the reader thread)."""
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        rid = self.next_id()

        def done(ok: bool, value: Any) -> None:
            if ok:
                future.set_result(value)
            else:
                try:
                    raise_remote(value)
                except Exception as exc:
                    future.set_exception(exc)

        self._pending[rid] = done
        self.channel.send({"t": "rpc", "id": rid, "m": method, "a": args})
        return future

    async def arpc(self, method: str, *args: Any) -> Any:
        """A call awaited on the proxy service thread."""
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()
        rid = self.next_id()

        def settle(ok: bool, value: Any) -> None:
            if future.done():
                return
            if ok:
                future.set_result(value)
            else:
                try:
                    raise_remote(value)
                except Exception as exc:
                    future.set_exception(exc)

        def done(ok: bool, value: Any) -> None:
            loop.call_soon_threadsafe(settle, ok, value)

        self._pending[rid] = done
        self.channel.send({"t": "rpc", "id": rid, "m": method, "a": args})
        return await future

    def register(
        self,
        fn: Callable[..., Any],
        mode: str = "main",
        pre: Callable[..., tuple[Any, ...]] | None = None,
    ) -> int:
        """A callback the shell can call by id. ``mode`` is ``main`` (the module's loop, recorded
        as a callback), ``aio`` (the proxy service thread) or ``raw`` (the loop, not recorded)."""
        sid = self.next_id()
        self._callbacks[sid] = (fn, mode, pre)
        return sid

    def unregister(self, sid: int) -> None:
        self._callbacks.pop(sid, None)

    def aio(self) -> AioThread:
        if self._aio is None:
            self._aio = AioThread()
        return self._aio

    # -- the pipe -------------------------------------------------------------------------------

    def _on_message(self, msg: dict[str, Any]) -> None:  # reader thread
        kind = msg.get("t")
        if kind == "re":
            done = self._pending.pop(msg["id"], None)
            if done is not None:
                done(bool(msg.get("ok")), msg.get("v") if msg.get("ok") else msg.get("err"))
            return
        if kind == "cb":
            self._dispatch_callback(msg)
            return
        self.loop.put(lambda: self.handle(msg))

    def _on_closed(self) -> None:  # reader thread: the shell is gone
        self.loop.put(self._exit)

    def _exit(self) -> None:
        self.loop.stop()

    def _dispatch_callback(self, msg: dict[str, Any]) -> None:  # reader thread
        entry = self._callbacks.get(msg["id"])
        if entry is None:
            return
        fn, mode, pre = entry
        args = tuple(msg.get("a", ()))

        def run() -> None:
            try:
                call_args = pre(*args) if pre is not None else args
                if mode == "main" and self.ctx is not None:
                    self.ctx.run_callback(fn, *call_args)
                else:
                    fn(*call_args)
            except Exception:
                logger.opt(exception=True).error("a callback from the shell raised")

        if mode == "aio":
            self.aio().post(run)
        else:
            self.loop.put(run)

    def send_value(self, use: str | None, key: str, value: object) -> None:
        if not isinstance(key, str) or not key:
            logger.error("a send needs a key")
            return
        if not plain(value):
            logger.error(
                f"the value for '{key}' is a {type(value).__name__}, not a string, number, "
                "boolean, list or dict; the last value stays"
            )
            return
        self.channel.send({"t": "s", "u": use, "k": key, "v": value})

    # -- services of this process (B1) ----------------------------------------------------------

    def service(self) -> Any:
        if self._service is None:
            from tess_shell.services.bus import ServiceThread

            self._service = ServiceThread()
            self._service.start()
        return self._service

    def layer(self) -> Any:
        if self._layer is None:
            from tess_shell.services.layer import Layer

            self._layer = Layer(self.service(), self.loop.put, loop_thread=self.loop.ident)
        return self._layer

    def audio_port(self) -> Any:
        if self._audio is None:
            from tess_shell.services.audio import AudioService

            self._audio = AudioService(self.service())
        return self._audio

    def tray_port(self) -> Any:
        if self._tray is None:
            from tess_shell.services.tray import TrayService

            self._tray = TrayService(self.service())
        return self._tray

    # -- the module -----------------------------------------------------------------------------

    def handle(self, msg: dict[str, Any]) -> None:  # the loop thread
        kind = msg["t"]
        method = getattr(self, f"on_{kind}", None)
        if method is None:
            logger.error(f"unknown message {kind}")
            return
        method(msg)

    def failed(self, what: str, exc: BaseException) -> None:
        logger.opt(exception=True).error(f"{self.name}: {what}() raised")
        self.channel.send({"t": "failed", "what": what, "err": encode_error(exc)})

    def on_init(self, msg: dict[str, Any]) -> None:
        from tests.perf.proto import proxies

        self.name = msg["name"]
        self.mode = msg["services"]
        records = {
            u["key"]: UseRecord(u["key"], u["name"], u["uid"], u["monitor"], dict(u["params"]))
            for u in msg["uses"]
        }
        py = msg["py"]
        mod_name = f"{PACKAGE}.{self.name}"
        spec = importlib.util.spec_from_file_location(mod_name, py)
        assert spec is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        b2 = self.mode == "B2"
        ctx = ModuleContext(
            self.name,
            msg["uid"],
            msg["config"],
            records,
            self.send_value,
            self.ticks,
            lambda: proxies.ProxyPopups(self),
            (lambda: proxies.ProxyDBusPort(self)) if b2 else (lambda: self.layer()),
            (lambda: proxies.ProxyAudioPort(self)) if b2 else (lambda: self.audio_port()),
            lambda: proxies.ProxyIconsPort(self),
            (lambda: proxies.ProxyTrayPort(self)) if b2 else (lambda: self.tray_port()),
            lambda: self.loop.put,
            None,
            lambda: proxies.ProxyWindowsPort(self),
            lambda: proxies.ProxyAppsPort(self),
            lambda: proxies.ProxySurfacePort(self),
            self.record,  # type: ignore[arg-type]
        )
        self.ctx = ctx
        self.ticks.start(self.loop.put)
        logger.configure(extra={"source": f"module:{self.name}", "location": "-"})
        try:
            code = compile(open(py, encoding="utf-8").read(), py, "exec")
            self.record.run(self.name, "import", exec, code, module.__dict__)  # noqa: S102
            classes = [
                c
                for _, c in inspect.getmembers(module, inspect.isclass)
                if issubclass(c, Module) and c is not Module and c.__module__ == module.__name__
            ]
            if len(classes) != 1:
                raise RuntimeError(f"{py} has {len(classes)} classes extending Module")
            instance = classes[0].__new__(classes[0])
            instance.ctx = ctx
            self.record.run(self.name, "__init__", instance.__init__)  # type: ignore[misc]
        except Exception as exc:
            self.failed("import", exc)
            return
        ctx.set_service_hooks(instance.on_service_lost, instance.on_service_found)
        self.instance = instance
        self.channel.send({"t": "ready", "pid": os.getpid()})

    def on_use_set(self, msg: dict[str, Any]) -> None:
        assert self.ctx is not None
        u = msg["rec"]
        uses = self.ctx.uses
        assert isinstance(uses, dict)
        uses[u["key"]] = UseRecord(u["key"], u["name"], u["uid"], u["monitor"], dict(u["params"]))

    def on_use_del(self, msg: dict[str, Any]) -> None:
        assert self.ctx is not None
        uses = self.ctx.uses
        assert isinstance(uses, dict)
        uses.pop(msg["key"], None)

    def _lifecycle(self, what: str, fn: Callable[..., Any], *args: Any) -> bool:
        assert self.ctx is not None
        try:
            self.record.run(self.name, what, fn, *args)
        except Exception as exc:
            self.failed(what, exc)
            return False
        return True

    def on_start(self, msg: dict[str, Any]) -> None:
        if self.instance is None or self.ctx is None:
            return
        for record in list(self.ctx.uses.values()):
            try:
                self.record.run(self.name, "validate_use", self.instance.validate_use, record)
            except ValueError as exc:
                logger.error(f"module-use: {record.name}: {exc}")
            except Exception as exc:
                self.failed("validate_use", exc)
        if self._lifecycle("start", self.instance.start):
            self.channel.send({"t": "started"})

    def on_stop(self, msg: dict[str, Any]) -> None:
        ok = True
        if self.instance is not None:
            ok = self._lifecycle("stop", self.instance.stop)
        self.channel.send({"t": "re", "id": msg["id"], "ok": ok, "v": None})

    def on_reload(self, msg: dict[str, Any]) -> None:
        if self.instance is not None:
            self._lifecycle("reload", self.instance.reload)

    def on_use_added(self, msg: dict[str, Any]) -> None:
        if self.instance is None or self.ctx is None:
            return
        record = self.ctx.uses.get(msg["key"])
        if record is not None:
            self._lifecycle("use_added", self.instance.use_added, record)

    def on_use_removed(self, msg: dict[str, Any]) -> None:
        if self.instance is None:
            return
        u = msg["rec"]
        record = UseRecord(u["key"], u["name"], u["uid"], u["monitor"], dict(u["params"]))
        self._lifecycle("use_removed", self.instance.use_removed, record)

    def on_validate(self, msg: dict[str, Any]) -> None:
        if self.instance is None or self.ctx is None:
            return
        record = self.ctx.uses.get(msg["key"])
        if record is None:
            return
        try:
            self.record.run(self.name, "validate_use", self.instance.validate_use, record)
        except ValueError as exc:
            logger.error(f"module-use: {record.name}: {exc}")
        except Exception as exc:
            self.failed("validate_use", exc)

    def on_avail(self, msg: dict[str, Any]) -> None:
        assert self.ctx is not None
        record = self.ctx.uses.get(msg["key"])
        if record is not None:
            self.ctx.send_available(record)

    def on_lost(self, msg: dict[str, Any]) -> None:
        assert self.ctx is not None
        self.ctx.lost(msg["name"])

    def on_found(self, msg: dict[str, Any]) -> None:
        assert self.ctx is not None
        self.ctx.found(msg["name"])

    def on_call(self, msg: dict[str, Any]) -> None:
        assert self.ctx is not None
        if self.instance is None:
            return
        fn = getattr(self.instance, msg["action"], None)
        if not callable(fn) or not getattr(fn, "__tess_action__", False):
            logger.error(f"{self.name} has no action {msg['action']}")
            return
        fields = dict(msg["event"])
        if fields.get("rect") is not None:
            fields["rect"] = tuple(fields["rect"])
        event = Event(**fields)
        self.ctx.caller = self.ctx.uses.get(msg.get("caller") or "")
        previous = self.record.enter(self.name, msg["action"])
        try:
            fn(event, **msg.get("kw", {}))
        except Exception:
            logger.opt(exception=True).error(f"{self.name}.{msg['action']} raised")
        finally:
            self.record.leave(previous)
            self.ctx.caller = None

    def on_shutdown(self, msg: dict[str, Any]) -> None:
        if self.ctx is not None:
            try:
                self.ctx.close()
            except Exception:
                logger.opt(exception=True).debug("closing the context raised")
        self.ticks.close()
        self.loop.stop()

    def run(self) -> None:
        self.channel.start()
        self.loop.run()
        self.channel.close()


def _forward_logs(child: Child) -> None:
    """Every log record of this process goes to the shell, which logs it under the module."""
    logger.remove()

    def sink(message: Any) -> None:
        record = message.record
        text = record["message"]
        if record["exception"] is not None:
            import traceback

            exc = record["exception"]
            text += "\n" + "".join(traceback.format_exception(exc.type, exc.value, exc.traceback))
        child.channel.send({"t": "log", "l": record["level"].name, "m": text})

    level = os.environ.get("TESS_PROTO_CHILD_LEVEL", "INFO")
    logger.add(sink, level=level, format="{message}")
    logger.configure(extra={"source": "module", "location": "-"})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fd", type=int, required=True)
    parser.add_argument("--shm", type=int, required=True)
    args = parser.parse_args()
    sock = socket.socket(fileno=args.fd)
    mm = mmap.mmap(args.shm, 4096)
    child = Child(sock, mm)
    _forward_logs(child)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    child.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
