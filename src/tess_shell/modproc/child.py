"""The module process: ``python -I -m tess_shell.modproc.child --fd N --shm M --name NAME``.

It runs ONE module file's ``Module`` class with the real :class:`~tess_shell.modules.context.
ModuleContext`, whose ports are the proxies of :mod:`tess_shell.modproc.childctx`: every service is
the shell's. The module's own code is unchanged, and so are its rules: one thread (this process's
main thread, :class:`~tess_shell.modproc.childctx.Loop`) runs every callback one at a time, as the
shell's loop does in the shell.

Threads: main (the module loop), the reader and writer of the pipe, the service thread (only after
``ctx.dbus``, ``ctx.audio`` or ``ctx.tray`` was used) and the module's own. No timer thread
(ticks are messages) and nothing wakes an idle process.

The running-callback record is shared memory (a memfd the shell passed in): two stores around each
callback, read by the shell's watchdog, so a hung callback is noticed without a message
(:class:`SharedRecord` is the real :class:`~tess_shell.modules.running.CallbackRecord`, so the 4 ms
budget and ``slow-module`` are the same code). The process leaves on ``shutdown``, on the shell's
end of the pipe closing, or on SIGKILL (and ``PR_SET_PDEATHSIG`` kills it when the shell dies);
SIGINT, SIGTERM and SIGHUP are ignored, because systemd's stop signals the whole control group and
the shell's own stop sequence must run the module's ``stop()`` first.

``--probe FILE`` (``check --import-modules``) imports and constructs the module with a context that
has no shell behind it, prints one JSON line and exits.

Imports nothing of the shell's services, binder, surfaces or the engine (pinned by
``tests/test_modproc_child.py``).
"""

from __future__ import annotations

import argparse
import ctypes
import faulthandler
import inspect
import json
import mmap
import os
import signal
import socket
import struct
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path
from typing import Any

from loguru import logger

from tess_shell.logging import finding_sinks, note_module_error
from tess_shell.model.store import plain
from tess_shell.modproc.childctx import (
    Link,
    Loop,
    ProxyAppsPort,
    ProxyAudioPort,
    ProxyDBusPort,
    ProxyFocusPort,
    ProxyIconsPort,
    ProxyPopups,
    ProxySurfacePort,
    ProxyTrayPort,
    ProxyWindowsPort,
    RemoteTicks,
)
from tess_shell.modproc.wire import Channel, encode_error
from tess_shell.module import Event, Module
from tess_shell.modules import running
from tess_shell.modules.actions import action_spec, actions_of
from tess_shell.modules.context import ModuleContext, UseRecord
from tess_shell.modules.running import CallbackRecord
from tess_shell.modules.supervise import MANY_THREADS, thread_counts
from tess_shell.modules.ticks import TimeSource
from tess_shell.schema.findings import Finding

PACKAGE = "tess_shell_user_modules"
SEQ_AT = 8  # the shared record: start (ns, 8 bytes), a seqlock counter, then the entry name
ENTRY_AT = 16
ENTRY_MAX = 64
LOG_PER_SECOND = 200  # log lines a module may send in one second; the rest are dropped and counted
PR_SET_PDEATHSIG = 1
LEVELS = ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")


def where(exc: BaseException, py: str) -> int:
    """The line in the module's own file where ``exc`` was raised, else of the last frame."""
    if isinstance(exc, SyntaxError) and exc.lineno:
        return exc.lineno
    frames = traceback.extract_tb(exc.__traceback__)
    own = [f for f in frames if f.filename == py]
    frame = (own or frames)[-1] if frames else None
    return (frame.lineno or 1) if frame else 1


class SharedRecord(CallbackRecord):
    """:class:`CallbackRecord` that also stores the running callback in shared memory: ``enter`` and
    ``leave`` of the outermost callback write the start (monotonic ns, 0 for none) and the entry
    name between two bumps of a counter (a seqlock: the shell skips a read that saw it change)."""

    def __init__(
        self,
        mm: mmap.mmap,
        warn: Callable[[str, str, str], None],
        periodic: Callable[[], None],
    ) -> None:
        super().__init__(warn, periodic=periodic)
        self._mm = mm
        self._seq = 0

    def _publish(self, started: int, entry: str) -> None:
        mm = self._mm
        self._seq += 1
        struct.pack_into("<Q", mm, SEQ_AT, self._seq)  # odd: being written
        raw = entry.encode("utf-8", "replace")[:ENTRY_MAX]
        mm[ENTRY_AT : ENTRY_AT + ENTRY_MAX] = raw.ljust(ENTRY_MAX, b"\0")
        struct.pack_into("<q", mm, 0, started)
        self._seq += 1
        struct.pack_into("<Q", mm, SEQ_AT, self._seq)

    def enter(self, module: str, entry: str) -> Any:
        previous = super().enter(module, entry)
        if previous is None:
            self._publish(time.monotonic_ns(), entry)
        return previous

    def leave(self, previous: Any) -> None:
        super().leave(previous)
        if previous is None:
            self._publish(0, "")


class LogSink:
    """Every log record of this process goes to the shell, which logs it under the module. At most
    :data:`LOG_PER_SECOND` lines a second: a module that logs in a loop must not flood the shell's
    log; the dropped lines are counted and said once, in the next second."""

    def __init__(self, channel: Channel) -> None:
        self._channel = channel
        self._second = 0
        self._count = 0
        self._dropped = 0

    def __call__(self, message: Any) -> None:
        record = message.record
        now = int(time.monotonic())
        if now != self._second:
            self._second, self._count = now, 0
            if self._dropped:
                dropped, self._dropped = self._dropped, 0
                self._send(
                    "WARNING", f"{dropped} log lines were dropped (over {LOG_PER_SECOND} a second)"
                )
        if self._count >= LOG_PER_SECOND:
            self._dropped += 1
            return
        self._count += 1
        text = record["message"]
        exc = record["exception"]
        if exc is not None:
            text += "\n" + "".join(traceback.format_exception(exc.type, exc.value, exc.traceback))
        self._send(record["level"].name, text)

    def _send(self, level: str, text: str) -> None:
        self._channel.send({"t": "log", "l": level, "m": text})

    def flush(self) -> None:
        if self._dropped:
            dropped, self._dropped = self._dropped, 0
            self._send(
                "WARNING", f"{dropped} log lines were dropped (over {LOG_PER_SECOND} a second)"
            )


class StopWarner:
    """The ``_raw`` of an :class:`Event` in a module process: ``Event.stop()`` cannot work (the
    action runs after the shell's handler returned), so it says so, once."""

    def __init__(self, child: Child) -> None:
        self._child = child

    def stop(self) -> None:
        self._child.warn_once(
            "event-stop",
            f"{self._child.name}: Event.stop() has no effect in a module process (the shell's "
            "handler has already returned); a module that must stop an event has to run in the "
            "shell (Debug { User_Modules_In_Process: true })",
        )


class Child:
    def __init__(self, sock: socket.socket, mm: mmap.mmap) -> None:
        self.loop = Loop()
        self.channel = Channel(sock, self._on_message, self._on_closed, "module")
        self.link = Link("?", self.channel, self.loop)
        self.name = "?"
        self.py = ""
        self.ctx: ModuleContext | None = None
        self.instance: Module | None = None
        self.record = SharedRecord(mm, self._warn, self._periodic)
        self.log_sink = LogSink(self.channel)
        self._log_id: int | None = None
        self._warned: set[str] = set()
        self._shutdown = False
        self._many_threads_warned = False

    # -- to the shell ---------------------------------------------------------------------------

    def _warn(self, module: str, rule: str, message: str) -> None:
        self.channel.send({"t": "warn", "rule": rule, "m": message})

    def warn_once(self, rule: str, message: str) -> None:
        if rule not in self._warned:
            self._warned.add(rule)
            self._warn(self.name, rule, message)

    def _periodic(self) -> None:
        """Once a minute, at the end of a callback: warn once for more than 16 live threads of the
        module's own (:func:`~tess_shell.modules.supervise.thread_counts`, as in the shell)."""
        if self._many_threads_warned or not self.py:
            return
        py = Path(self.py)
        try:
            count = thread_counts({self.name: (py, py.parent.name == self.name)}).get(self.name, 0)
        except Exception:
            logger.opt(exception=True).debug("counting the module's threads failed")
            return
        if count > MANY_THREADS:
            self._many_threads_warned = True
            self._warn(
                self.name,
                "many-threads",
                f"{self.name}: {count} live threads of its own (more than {MANY_THREADS})",
            )

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
        self.channel.send({"t": "s", "u": use, "k": key, "v": value}, plain=True)

    def failed(self, what: str, exc: BaseException) -> None:
        logger.opt(exception=True).error(f"{self.name}: {what}() raised")
        err = encode_error(exc)
        err["line"] = where(exc, self.py)
        self.channel.send({"t": "failed", "what": what, "err": err})

    def forward_finding(self, finding: Finding) -> None:
        """A finding the module's code made (``note_module_error``): the shell tells its listeners
        (``ErrorReported``)."""
        self.channel.send({"t": "finding", "f": finding.to_dict(), "report": False})

    # -- the pipe -------------------------------------------------------------------------------

    def _on_message(self, msg: dict[str, Any]) -> None:  # reader thread
        kind = msg.get("t")
        if kind == "re":
            self.link.answer(msg)
        elif kind == "cb":
            self.link.dispatch(msg)
        elif kind == "avail":
            self.link.state["dbus_available"] = bool(msg.get("v"))
        else:
            self.loop.put(lambda: self.handle(msg))

    def _on_closed(self) -> None:  # reader thread
        if not self._shutdown:
            # the shell is gone (or gave up on this process): nothing to tell, nothing to wait for
            os._exit(1)

    def handle(self, msg: dict[str, Any]) -> None:  # the loop thread
        method = getattr(self, f"on_{msg['t']}", None)
        if method is None:
            logger.error(f"unknown message {msg['t']}")
            return
        method(msg)

    # -- the module -----------------------------------------------------------------------------

    def set_level(self, level: str) -> None:
        if self._log_id is not None:
            logger.remove(self._log_id)
        name = level if level in LEVELS else "INFO"
        self._log_id = logger.add(self.log_sink, level=name, format="{message}")

    def on_init(self, msg: dict[str, Any]) -> None:
        self.name = self.link.name = msg["name"]
        self.py = msg["py"]
        self.set_level(msg.get("level", "INFO"))
        logger.configure(extra={"source": f"module:{self.name}", "location": "-"})
        finding_sinks.append(self.forward_finding)
        link = self.link
        records = {
            u["key"]: UseRecord(u["key"], u["name"], u["uid"], u["monitor"], dict(u["params"]))
            for u in msg["uses"]
        }
        popups, focus = ProxyPopups(link), ProxyFocusPort(link)
        dbus, audio, icons = ProxyDBusPort(link), ProxyAudioPort(link), ProxyIconsPort(link)
        tray, windows = ProxyTrayPort(link), ProxyWindowsPort(link)
        apps, surfaces = ProxyAppsPort(link), ProxySurfacePort(link)
        ctx = ModuleContext(
            self.name,
            msg["uid"],
            msg["config"],
            records,
            self.send_value,
            RemoteTicks(link),
            lambda: popups,
            lambda: dbus,
            lambda: audio,
            lambda: icons,
            lambda: tray,
            lambda: self.loop.put,
            lambda: focus,
            lambda: windows,
            lambda: apps,
            lambda: surfaces,
            self.record,
        )
        link.run_callback = ctx.run_callback
        self.ctx = ctx
        what = "import"
        try:
            instance = self.import_module(self.py)
            what = "init"
            instance.ctx = ctx
            self.record.run(self.name, "__init__", instance.__init__)  # type: ignore[misc]
        except Exception as exc:
            self.failed(what, exc)
            return
        ctx.set_service_hooks(instance.on_service_lost, instance.on_service_found)
        self.instance = instance
        actions = {}
        for name in actions_of(type(instance)):
            spec = action_spec(getattr(instance, name))
            actions[name] = {
                "first": spec.first,
                "names": list(spec.names),
                "required": sorted(spec.required),
                "kwargs": spec.kwargs,
            }
        self.channel.send({"t": "imported", "pid": os.getpid(), "actions": actions})

    def import_module(self, py: str) -> Module:
        """Run the module's file and make the instance (no ``__init__`` yet)."""
        import importlib.util

        mod_name = f"{PACKAGE}.{self.name}"
        spec = importlib.util.spec_from_file_location(mod_name, py)
        if spec is None:
            raise ImportError(f"cannot import {py}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[mod_name] = module
        # compiled from the source every time: a file saved twice in one second at the same size
        # would otherwise load the old code; this is what loading a module is: its file runs
        code = compile(Path(py).read_text(encoding="utf-8"), py, "exec")
        self.record.run(self.name, "import", exec, code, module.__dict__)  # noqa: S102
        classes = [
            c
            for _, c in inspect.getmembers(module, inspect.isclass)
            if issubclass(c, Module) and c is not Module and c.__module__ == module.__name__
        ]
        if len(classes) != 1:
            raise RuntimeError(f"{py} has {len(classes)} classes extending Module")
        return classes[0].__new__(classes[0])

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
        try:
            self.record.run(self.name, what, fn, *args)
        except Exception as exc:
            self.failed(what, exc)
            return False
        return True

    def _validate(self, record: UseRecord) -> bool:
        """``validate_use``: a ``ValueError`` is the finding ``module-use`` (the module goes on);
        any other exception fails the module. False when it failed."""
        assert self.instance is not None
        try:
            self.record.run(self.name, "validate_use", self.instance.validate_use, record)
        except ValueError as exc:
            self.channel.send(
                {
                    "t": "finding",
                    "f": Finding(
                        self.py, 1, 1, "error", "module-use", f"{record.name}: {exc}"
                    ).to_dict(),
                    "report": True,
                }
            )
        except Exception as exc:
            self.failed("validate_use", exc)
            return False
        return True

    def on_start(self, msg: dict[str, Any]) -> None:
        if self.instance is None or self.ctx is None:
            return
        for record in list(self.ctx.uses.values()):
            if not self._validate(record):
                return
        if self._lifecycle("start", self.instance.start):
            self.channel.send({"t": "started"})

    def on_stop(self, msg: dict[str, Any]) -> None:
        ok = True
        if self.instance is not None:
            ok = self._lifecycle("stop", self.instance.stop)
        if msg.get("id") is not None:
            self.channel.send({"t": "re", "id": msg["id"], "ok": True, "v": ok})

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
        if record is not None:
            self._validate(record)

    def on_lost(self, msg: dict[str, Any]) -> None:
        assert self.ctx is not None
        self.ctx.lost(msg["name"])

    def on_found(self, msg: dict[str, Any]) -> None:
        assert self.ctx is not None
        self.ctx.found(msg["name"])

    def on_level(self, msg: dict[str, Any]) -> None:
        self.set_level(msg["level"])

    def on_call(self, msg: dict[str, Any]) -> None:
        """An ``@action``, from a handler of a shell file (no ``id``) or from a control call (an
        ``id``: the answer, or the error, goes back)."""
        assert self.ctx is not None
        rid = msg.get("id")
        action = msg["action"]
        fn = getattr(self.instance, action, None) if self.instance is not None else None
        if not callable(fn) or not getattr(fn, "__tess_action__", False):
            logger.error(f"{self.name} has no action {action}")
            if rid is not None:
                self.channel.send(
                    {
                        "t": "re",
                        "id": rid,
                        "ok": False,
                        "err": {
                            "type": "RuntimeError",
                            "msg": f"{self.name} has no action {action}",
                        },
                    }
                )
            return
        event = Event(**dict(msg["event"]), _raw=StopWarner(self))
        self.ctx.caller = self.ctx.uses.get(msg.get("caller") or "")
        previous = self.record.enter(self.name, action)
        try:
            result = fn(event, **msg.get("kw", {}))
        except Exception as exc:
            logger.opt(exception=True).error(f"{self.name}.{action} raised")
            note_module_error(self.name, f"{self.name}.{action}", exc)
            if rid is not None:
                self.channel.send(
                    {
                        "t": "re",
                        "id": rid,
                        "ok": False,
                        "err": {"type": type(exc).__name__, "msg": str(exc)},
                    }
                )
        else:
            if rid is not None:
                self._answer(rid, result)
        finally:
            self.record.leave(previous)
            self.ctx.caller = None

    def _answer(self, rid: int, result: Any) -> None:
        try:
            self.channel.send({"t": "re", "id": rid, "ok": True, "v": result})
        except TypeError:  # not plain data: the control interface says null for it, as ever
            self.channel.send({"t": "re", "id": rid, "ok": True, "v": None})

    def on_shutdown(self, msg: dict[str, Any]) -> None:
        self._shutdown = True
        if self.ctx is not None:
            try:
                self.ctx.close()
            except Exception:
                logger.opt(exception=True).debug("closing the context raised")
        self.link.stop_aio()
        self.loop.stop()

    def run(self) -> None:
        self.channel.start()
        self.loop.run()
        self.log_sink.flush()
        self.channel.drain(1.0)
        self.channel.close()


def _die_with_the_shell(parent: int) -> None:
    """``PR_SET_PDEATHSIG(SIGKILL)``: the kernel kills this process when the shell's thread that
    started it ends, however it ends. A parent already gone is a start that lost the race."""
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        libc.prctl(PR_SET_PDEATHSIG, int(signal.SIGKILL), 0, 0, 0)
    except OSError:
        pass
    if parent and os.getppid() != parent:
        os._exit(1)


def probe(py: str, name: str) -> int:
    """Import and construct the module with a context that has no shell behind it; one JSON line."""

    def say(result: dict[str, Any]) -> int:
        sys.stdout.write(json.dumps(result) + "\n")
        sys.stdout.flush()
        return 0 if result["ok"] else 1

    holder = Child.__new__(Child)
    holder.name, holder.py = name, py
    holder.record = CallbackRecord(lambda m, r, t: None)  # type: ignore[assignment]
    ctx = ModuleContext(
        name, "probe", {"name": name}, {}, lambda use, key, value: None, TimeSource()
    )
    what = "import"
    try:
        instance = Child.import_module(holder, py)
        what = "init"
        instance.ctx = ctx
        instance.__init__()  # type: ignore[misc]
    except Exception as exc:
        return say(
            {
                "ok": False,
                "what": what,
                "type": type(exc).__name__,
                "msg": str(exc),
                "line": where(exc, py),
            }
        )
    return say({"ok": True, "actions": actions_of(type(instance))})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fd", type=int)
    parser.add_argument("--shm", type=int)
    parser.add_argument("--parent", type=int, default=0)
    parser.add_argument("--name", default="", help="the module (shown in ps)")
    parser.add_argument("--probe", help="import this file, print one JSON line, exit")
    args = parser.parse_args(argv)
    if args.probe:
        return probe(args.probe, args.name or Path(args.probe).stem)
    if args.fd is None or args.shm is None:
        parser.error("--fd and --shm are needed")
    _die_with_the_shell(args.parent)
    try:  # the watchdog's test setting also shortens the minute of the thread and slow checks
        scale = float(os.environ.get("TESS_SHELL_TEST_WATCHDOG_SCALE", ""))
    except ValueError:
        scale = 0.0
    if scale > 0:
        running.WINDOW *= scale
    for number in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
        signal.signal(number, signal.SIG_IGN)
    # the shell asks for the threads' tracebacks (SIGUSR1) before it kills a module that hangs
    faulthandler.register(signal.SIGUSR1, file=sys.stderr, all_threads=True)
    logger.remove()
    sock = socket.socket(fileno=args.fd)
    mm = mmap.mmap(args.shm, 4096)
    child = Child(sock, mm)
    child.run()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(0)  # a thread of the module that is not a daemon must not keep the process


if __name__ == "__main__":
    raise SystemExit(main())
