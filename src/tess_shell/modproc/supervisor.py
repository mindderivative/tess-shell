"""The shell's side of the module processes: spawn, the messages, the failures, the watch, the start
gate. :class:`ModuleProcesses` is what ``ModuleHost.processes`` is (``modules.process_port``);
:class:`ProcessHandle` is one child (``instance._process`` of its stub).

Threads: a handle's reader thread (it calls ``ValueStore.send`` for a value, as a module thread of
the shell does, and hands everything else to the loop with ``call_soon``) and writer thread; the
watch runs on the shell's watchdog thread (``Watchdog.on_poll``) or, with none, on a thread of its
own. Nothing here blocks the loop: a child's answer arrives as a message, and the only waits are
``wait_all`` (after the loop has ended) and a throwaway ``threading.Timer``.
"""

from __future__ import annotations

import concurrent.futures
import mmap
import os
import signal
import socket
import struct
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from loguru import logger

from tess_shell.logging import note_finding
from tess_shell.modproc import broker
from tess_shell.modproc.static import inspect_module_file
from tess_shell.modproc.stub import (
    build_module,
    finding_for,
    signature_of,
    spec_dict,
    use_dict,
)
from tess_shell.modproc.wire import Channel
from tess_shell.modules.actions import action_spec
from tess_shell.modules.context import ModuleContext
from tess_shell.modules.host import ActionError, ModuleHost, report
from tess_shell.schema.findings import Finding, ModuleFinding
from tess_shell.schema.model import ModuleDef
from tess_shell.services.api import ServiceError
from tess_shell.watchdog import SCALE_VARIABLE

SEQ_AT = 8
ENTRY_AT = 16
ENTRY_MAX = 64
# what a child does not inherit: it is not the service (a child that pinged systemd is a bug)
STRIPPED = ("NOTIFY_SOCKET", "WATCHDOG_USEC", "WATCHDOG_PID", "LISTEN_FDS", "LISTEN_PID")
LEVELS = ("TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL")
KILL_SETTLE = 0.2  # seconds between asking a hung child for its tracebacks and killing it


@dataclass(frozen=True, slots=True)
class Timing:
    """Seconds. ``stall``: a callback that has run this long is named; ``kill``: it is killed;
    ``poll``: the period of the watch (the watchdog's own tick when it hooks in); ``gate``: the
    longest ``READY=1`` waits for the children; ``stop``: a module's ``stop()`` gets this long."""

    stall: float = 2.0
    kill: float = 5.0
    poll: float = 1.0
    gate: float = 10.0
    stop: float = 3.0

    def scaled(self, factor: float) -> Timing:
        return Timing(
            self.stall * factor,
            self.kill * factor,
            self.poll * factor,
            self.gate * factor,
            self.stop * factor,
        )


def timing_from_environment(environ: Mapping[str, str]) -> Timing:
    """The default times, scaled by ``TESS_SHELL_TEST_WATCHDOG_SCALE`` (the watchdog's test setting)
    so a test does not wait 5 s for a kill."""
    try:
        factor = float(environ.get(SCALE_VARIABLE, ""))
    except ValueError:
        return Timing()
    return Timing().scaled(factor) if factor > 0 else Timing()


def plain_result(value: Any) -> Any:
    """Dataclasses as dicts, containers rebuilt (tuples stay tuples: the wire tags them)."""
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, list):
        return [plain_result(v) for v in value]
    if isinstance(value, tuple):
        return tuple(plain_result(v) for v in value)
    return value


def error_dict(exc: BaseException) -> dict[str, Any]:
    if isinstance(exc, ServiceError):
        return {
            "type": type(exc).__name__,
            "msg": str(exc),
            "args": [exc.service, exc.detail, exc.name],
        }
    return {"type": type(exc).__name__, "msg": str(exc)}


def exit_words(code: int | None) -> str:
    if code is None:
        return "closed its pipe"
    if code < 0:
        try:
            return f"exit code {code} (killed by {signal.Signals(-code).name})"
        except ValueError:
            return f"exit code {code}"
    return f"exit code {code}"


class MirrorDict(dict[str, Any]):
    """``ctx.uses`` in the shell: every change the host makes is told to the process, in order, so
    the process sees the same uses at each hook as the shell's module would."""

    def __init__(self, initial: Mapping[str, Any], handle: ProcessHandle) -> None:
        super().__init__(initial)
        self._handle = handle

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key, value)
        self._handle.send({"t": "use_set", "rec": use_dict(value)})

    def pop(self, key: str, *default: Any) -> Any:
        had = key in self
        value = super().pop(key, *default)
        if had:
            self._handle.send({"t": "use_del", "key": key})
        return value


class ProcessHandle:
    """One module process, from the shell. ``phase`` is ``importing`` (spawned, the module's file is
    being imported), ``imported``, ``starting`` (``start`` was sent), ``running``, ``failed`` or
    ``ended``."""

    def __init__(
        self,
        sup: ModuleProcesses,
        name: str,
        py: Path,
        ctx: ModuleContext,
        static_actions: Mapping[str, Any],
    ) -> None:
        self.sup = sup
        self.host = sup.host
        self.name = name
        self.py = py
        self.ctx = ctx
        self.uid = ctx.uid
        self.static_actions = dict(static_actions)
        self.phase = "importing"
        self.intended = False  # the shell ended it (or asked it to): not a crash
        self.state: dict[str, Any] = {}  # the broker's (D-Bus proxies by id)
        self.pid = 0
        self.reaping = False
        self._disposed = False
        self._ids = 0
        self._lock = threading.Lock()
        self._pending: dict[int, Callable[[bool, Any], None]] = {}
        self._subs: dict[int, Any] = {}
        self._pool: concurrent.futures.ThreadPoolExecutor | None = None
        self._logged_stall = 0
        self._imported_cb: Callable[[Finding | None], None] | None = None
        self._import_result: tuple[bool, Finding | None] | None = None
        self._stop_waiting: Callable[[], None] | None = None
        parent_sock, child_sock = socket.socketpair()
        self.shm_fd = os.memfd_create(f"tess-{name}")
        os.ftruncate(self.shm_fd, 4096)
        self.shm = mmap.mmap(self.shm_fd, 4096)
        env = {
            k: v for k, v in os.environ.items() if k not in STRIPPED and not k.startswith("LISTEN_")
        }
        try:
            self.process = subprocess.Popen(
                [
                    sys.executable,
                    "-I",
                    "-m",
                    "tess_shell.modproc.child",
                    "--fd",
                    str(child_sock.fileno()),
                    "--shm",
                    str(self.shm_fd),
                    "--parent",
                    str(os.getpid()),
                    "--name",
                    name,
                ],
                pass_fds=(child_sock.fileno(), self.shm_fd),
                stdin=subprocess.DEVNULL,
                env=env,
            )
        except OSError:
            parent_sock.close()
            self.shm.close()
            os.close(self.shm_fd)
            raise
        finally:
            child_sock.close()
        self.pid = self.process.pid
        self.channel = Channel(
            parent_sock,
            self._on_message,
            self._on_closed,
            f"child-{name}",
            on_bad=lambda text: logger.error(f"module {name}: its process sent {text}; dropped"),
        )
        self.channel.start()
        sup.add(self)
        self.send(
            {
                "t": "init",
                "name": name,
                "uid": ctx.uid,
                "py": str(py),
                "config": dict(ctx.config),
                "uses": [use_dict(u) for u in ctx.uses.values()],
                "level": sup.level(),
            }
        )
        self._attach(ctx)

    def _attach(self, ctx: ModuleContext) -> None:
        """The host changes ``ctx.uses``, sends values through ``ctx.send`` (the shell's D-Bus layer
        sends ``available`` that way) and closes the context: each of the three is told to the
        process."""
        ctx.uses = MirrorDict(ctx.uses, self)
        original_send = ctx.send

        def send(key: str, value: object, use: Any = None) -> None:
            original_send(key, value, use)
            if key == "available" and use is None:
                self.send({"t": "avail", "v": bool(value)})

        ctx.send = send  # type: ignore[method-assign]
        original_close = ctx.close

        def close() -> None:
            original_close()
            self.close()

        ctx.close = close  # type: ignore[method-assign]

    # -- to the process ---------------------------------------------------------------------------

    def send(self, message: dict[str, Any]) -> None:
        self.channel.send(message)

    def cb(self, sid: int, *args: Any) -> None:
        """Call the callback ``sid`` of the process."""
        self.channel.send({"t": "cb", "id": sid, "a": args})

    def _reply(
        self, rid: int, ok: bool, value: Any = None, err: dict[str, Any] | None = None
    ) -> None:
        try:
            self.channel.send({"t": "re", "id": rid, "ok": ok, "v": value, "err": err})
        except TypeError as exc:  # a value the wire cannot carry
            self.channel.send({"t": "re", "id": rid, "ok": False, "err": error_dict(exc)})

    def next_id(self) -> int:
        with self._lock:
            self._ids += 1
            return self._ids

    def start(self) -> None:
        """``start()``, on the loop thread: it returns at once; the answer is ``started`` or
        ``failed`` (the pipe is in order, so a click that follows is not lost)."""
        if self.phase in ("importing", "imported"):
            self.phase = "starting"
        self.send({"t": "start"})

    def stop(self) -> None:
        """``stop()`` of a module that is stopped for good: told, not waited for."""
        self.send({"t": "stop"})

    def call(
        self,
        action: str,
        event: dict[str, Any],
        kw: dict[str, Any],
        caller: str | None,
        *,
        wants_result: bool,
    ) -> concurrent.futures.Future[Any] | None:
        message: dict[str, Any] = {
            "t": "call",
            "action": action,
            "event": event,
            "kw": kw,
            "caller": caller,
        }
        if not wants_result:
            self.send(message)
            return None
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()
        rid = self.next_id()

        def done(ok: bool, value: Any) -> None:
            if ok:
                future.set_result(value)
                return
            err = value if isinstance(value, dict) else {}
            future.set_exception(
                ActionError(
                    f"{self.name}.{action} raised {err.get('type', 'Exception')}: "
                    f"{err.get('msg', '')}"
                )
            )

        self._pending[rid] = done
        message["id"] = rid
        self.send(message)
        return future

    # -- what the host needs (RemoteModule) -------------------------------------------------------

    def when_imported(self, fn: Callable[[Finding | None], None]) -> None:
        self._imported_cb = fn
        if self._import_result is not None:
            self._deliver_import()

    def _deliver_import(self) -> None:
        fn, result = self._imported_cb, self._import_result
        if fn is None or result is None:
            return
        self._imported_cb = None
        self.sup.on_loop(lambda: fn(result[1]))

    def stop_then(self, fn: Callable[[], None]) -> None:
        done = threading.Event()

        def finish() -> None:
            if done.is_set():
                return
            done.set()
            timer.cancel()
            self._stop_waiting = None
            self.sup.on_loop(fn)

        def expire() -> None:
            if not done.is_set():
                logger.warning(
                    f"module {self.name}: stop() did not return in {self.sup.timing.stop:g} s; "
                    "killing the module process"
                )
                self.kill()
                finish()

        timer = threading.Timer(self.sup.timing.stop, expire)
        timer.daemon = True
        rid = self.next_id()
        self._pending[rid] = lambda ok, value: finish()
        self._stop_waiting = finish
        timer.start()
        self.send({"t": "stop", "id": rid})

    def cancel(self) -> None:
        """A reload that was replaced: the process goes, and nothing is said of it."""
        self.intended = True
        self._imported_cb = None
        self.kill()
        self.sup.reap(self)

    def kill(self) -> None:
        self.intended = True
        try:
            self.process.kill()
        except OSError:
            pass

    def close(self) -> None:
        """The module is over (stopped, replaced, failed): the process is told to leave and, if it
        does not within the stop time, killed."""
        if self.intended and self.channel.closed:
            return
        self.intended = True
        self.send({"t": "shutdown"})
        self.sup.reap(self)

    def helper(self, attr: str) -> Any:
        """``ctx.<attr>`` made under a lock (the pool's threads ask for the same helper)."""
        with self._lock:
            return getattr(self.ctx, attr)

    def subscribe(self, sid: int, subscription: Any) -> None:
        self._subs[sid] = subscription

    def unsubscribe(self, sid: int) -> None:
        sub = self._subs.pop(sid, None)
        if sub is not None:
            sub.cancel()

    # -- messages from the process (reader thread) ------------------------------------------------

    def _on_message(self, msg: dict[str, Any]) -> None:
        kind = msg.get("t")
        if kind == "s":
            self._value(msg)
        elif kind in ("rpc", "cmd"):
            self._serve(msg)
        elif kind == "re":
            done = self._pending.pop(msg.get("id"), None)  # type: ignore[arg-type]
            if done is not None:
                ok = bool(msg.get("ok"))
                done(ok, msg.get("v") if ok else msg.get("err"))
        elif kind == "log":
            level = msg.get("l")
            logger.bind(source=f"module:{self.name}", location="-").log(
                level if level in LEVELS else "INFO", str(msg.get("m", ""))
            )
        elif kind == "imported":
            self._imported(msg)
        elif kind == "started":
            self.phase = "running"
            self.sup.on_loop(lambda: self.sup.started(self))
        elif kind == "failed":
            self._failed(msg)
        elif kind == "warn":
            self.sup.on_loop(
                lambda: self.host.module_warning(self.name, str(msg["rule"]), str(msg["m"]))
            )
        elif kind == "finding":
            self._finding(msg)
        else:
            logger.error(f"module {self.name}: its process sent an unknown message {kind!r}")

    def _value(self, msg: dict[str, Any]) -> None:
        use = msg.get("u")
        if use is not None and (not isinstance(use, str) or use.split("@", 1)[0] != self.name):
            logger.error(f"module {self.name}: a value for {use!r}, which is not its use; dropped")
            return
        self.host.store.send(self.name, use, msg.get("k"), msg.get("v"))  # type: ignore[arg-type]

    def _failure_finding(self, what: str, err: Mapping[str, Any]) -> Finding:
        line = int(err.get("line") or 1)
        kind, text = err.get("type", "Exception"), err.get("msg", "")
        if what == "import":
            return Finding(
                str(self.py),
                line,
                1,
                "error",
                "module-import",
                f"{self.name}: importing the Python failed: {kind}: {text}",
                f"the layout file is {self.sup.layout_file(self.name)}",
            )
        if what == "init":
            return Finding(str(self.py), line, 1, "error", "module-init", f"{kind}: {text}")
        return Finding(
            str(self.py),
            line,
            1,
            "error",
            f"module-{what}",
            f"{self.name}: {what}() raised {kind}: {text}",
            f"the module is marked failed (UID {self.uid}); its surfaces keep their last values",
        )

    def _failed(self, msg: dict[str, Any]) -> None:
        what = str(msg.get("what", "start"))
        finding = self._failure_finding(what, msg.get("err") or {})
        if what in ("import", "init"):
            if self._imported_cb is not None or self._import_result is None:
                self._import_result = (False, finding)
                if self._imported_cb is not None:  # a reload waits: it keeps the old module
                    self._deliver_import()
                    return
        self.phase = "failed"
        self.sup.on_loop(lambda: self.host.process_failed(self.name, self, finding, what != "stop"))
        self.sup.on_loop(self.sup.settled)  # a failed module does not hold READY back

    def _imported(self, msg: dict[str, Any]) -> None:
        self.pid = int(msg.get("pid", self.pid))
        if self.phase == "importing":
            self.phase = "imported"
        self._import_result = (True, None)
        reported = msg.get("actions") or {}
        self.sup.on_loop(lambda: self._compare_actions(reported))
        if self._imported_cb is not None:
            self._deliver_import()

    def _compare_actions(self, reported: Mapping[str, Mapping[str, Any]]) -> None:
        """The actions the process found against those the file's text showed. A difference is an
        action the syntax tree cannot see (added by assignment, ``setattr`` or a metaclass): the
        stub learns it, and the module is told what to do."""
        shown = {n: spec_dict(action_spec(_bound(sig))) for n, sig in self.static_actions.items()}
        loaded = self.host.loaded.get(self.name)
        extra = sorted(set(reported) - set(shown))
        missing = sorted(set(shown) - set(reported))
        changed = sorted(n for n in set(shown) & set(reported) if dict(reported[n]) != shown[n])
        if not (extra or missing or changed):
            return
        parts = []
        if extra:
            parts.append(f"actions the file's text does not show: {', '.join(extra)}")
        if missing:
            parts.append(
                f"actions the text shows and the module does not have: {', '.join(missing)}"
            )
        if changed:
            parts.append(f"actions whose arguments differ: {', '.join(changed)}")
        report(
            [
                ModuleFinding(
                    str(self.py),
                    1,
                    1,
                    "warning",
                    "module-actions",
                    f"{self.name}: " + "; ".join(parts),
                    "write each action as a method decorated with @action in the class body of "
                    "the file, so that Call and check can see it",
                    module=self.name,
                )
            ]
        )
        if loaded is not None and loaded.remote is self:
            from tess_shell.modproc.stub import action_method

            for name in extra:
                setattr(
                    type(loaded.instance), name, action_method(name, signature_of(reported[name]))
                )

    def _finding(self, msg: dict[str, Any]) -> None:
        f = dict(msg.get("f") or {})
        try:
            finding = ModuleFinding(**f) if "module" in f else Finding(**f)
        except TypeError:
            logger.error(f"module {self.name}: its process sent a finding that is not one")
            return
        if msg.get("report"):
            self.sup.on_loop(lambda: report([finding]))
        else:
            note_finding(finding)

    def _fail_pending(self, why: str) -> None:
        """The process is gone: every control call still waiting for its answer ends with an error
        (the control interface would otherwise wait for its own timeout)."""
        pending, self._pending = self._pending, {}
        for done in pending.values():
            try:
                done(False, {"type": "RuntimeError", "msg": why})
            except Exception:
                logger.opt(exception=True).debug(f"module {self.name}: a waiting call raised")

    def _on_closed(self) -> None:
        """The pipe ended (reader thread): the process left, or the shell closed it."""
        self._fail_pending("the module process ended")
        waiting = self._stop_waiting
        if waiting is not None:
            waiting()
            return
        if self.intended:
            return
        try:
            code: int | None = self.process.wait(1.0)
        except subprocess.TimeoutExpired:
            code = None
        why = self.channel.reason
        if why == "overflow":
            text = "its end of the pipe did not read (hung); killed"
            self.kill()
        elif why == "protocol":
            text = "it sent bad lines three times in a row; killed"
            self.kill()
        else:
            text = exit_words(code)
        self.intended = True
        if self._imported_cb is not None and self._import_result is None:
            finding = Finding(
                str(self.py),
                1,
                1,
                "error",
                "module-import",
                f"{self.name}: the module process ended before it had imported the Python: {text}",
            )
            self._import_result = (False, finding)
            self._deliver_import()
            return
        self.phase = "ended"
        self.sup.on_loop(lambda: self.host.process_ended(self.name, self, self.pid, text))
        self.sup.on_loop(self.sup.settled)

    # -- what the process asks for -----------------------------------------------------------------

    def _serve(self, msg: dict[str, Any]) -> None:
        method = msg.get("m")
        args = msg.get("a", [])
        rid = msg.get("id")
        entry = broker.TABLE.get(method)  # type: ignore[arg-type]
        if entry is None:
            logger.error(f"module {self.name}: unknown call {method}")
            if rid is not None:
                self._reply(rid, False, err={"type": "RuntimeError", "msg": f"no call {method}"})
            return
        mode, fn = entry

        def finish(value: Any) -> None:
            if rid is None:
                return
            if isinstance(value, concurrent.futures.Future):
                value.add_done_callback(self._future_done(rid))
            else:
                self._reply(rid, True, plain_result(value))

        def guarded() -> None:
            try:
                finish(fn(self, *args))
            except Exception as exc:
                logger.opt(exception=True).error(
                    f"module {self.name}: {method} failed in the shell"
                )
                if rid is not None:
                    self._reply(rid, False, err=error_dict(exc))

        if self.sup.closing and mode == "loop":
            if rid is not None:
                self._reply(
                    rid, False, err={"type": "RuntimeError", "msg": "the shell is stopping"}
                )
            return
        if mode == "inline":
            guarded()
        elif mode == "loop":
            self.sup.on_loop(guarded)
        else:  # "pool": a read that may take a while (files, the index): off the reader thread
            if self._pool is None:
                self._pool = concurrent.futures.ThreadPoolExecutor(
                    max_workers=2, thread_name_prefix=f"serve-{self.name}"
                )
            self._pool.submit(guarded)

    def _future_done(self, rid: int) -> Callable[[concurrent.futures.Future[Any]], None]:
        def done(future: concurrent.futures.Future[Any]) -> None:
            try:
                self._reply(rid, True, plain_result(future.result()))
            except Exception as exc:
                self._reply(rid, False, err=error_dict(exc))

        return done

    # -- the watch (the watchdog's thread) ----------------------------------------------------

    def running_callback(self) -> tuple[int, str] | None:
        """The callback the process is running and when it began (monotonic ns), or ``None``."""
        for _ in range(3):
            seq1 = struct.unpack_from("<Q", self.shm, SEQ_AT)[0]
            started = struct.unpack_from("<q", self.shm, 0)[0]
            entry = bytes(self.shm[ENTRY_AT : ENTRY_AT + ENTRY_MAX])
            seq2 = struct.unpack_from("<Q", self.shm, SEQ_AT)[0]
            if seq1 == seq2 and seq1 % 2 == 0:
                if started == 0:
                    return None
                return started, entry.split(b"\0", 1)[0].decode("utf-8", "replace")
        return None

    def watch(self, now_ns: int) -> None:
        if self.intended or self.phase in ("failed", "ended"):
            return
        running = self.running_callback()
        if running is None:
            return
        started, entry = running
        age = (now_ns - started) / 1e9
        timing = self.sup.timing
        if age >= timing.stall and self._logged_stall != started:
            self._logged_stall = started
            logger.warning(
                f"module {self.name}: the callback {entry} has run for {age:.1f} s (stalled; "
                f"the process is killed at {timing.kill:g} s)"
            )
        if age >= timing.kill:
            logger.error(
                f"module {self.name} (UID {self.uid}): the callback {entry} did not return in "
                f"{timing.kill:g} s; killing the module process (pid {self.pid})"
            )
            self.intended = True
            try:  # its threads' tracebacks go to its stderr (the journal) before it is killed
                os.kill(self.pid, signal.SIGUSR1)
            except OSError:
                pass
            timer = threading.Timer(KILL_SETTLE, self.kill)
            timer.daemon = True
            timer.start()
            self.phase = "ended"
            self.sup.on_loop(
                lambda: self.host.process_ended(
                    self.name,
                    self,
                    self.pid,
                    f"killed: the callback {entry} did not return in {timing.kill:g} s",
                )
            )
            self.sup.on_loop(self.sup.settled)

    def dispose(self) -> None:
        """After the process is gone: close what the shell holds for it."""
        with self._lock:
            if self._disposed:
                return  # a second close of the same descriptor would close another object's
            self._disposed = True
        for sid in list(self._subs):
            self.unsubscribe(sid)
        if self._pool is not None:
            self._pool.shutdown(wait=False)
        self.channel.close()
        try:
            self.shm.close()
            os.close(self.shm_fd)
        except OSError, ValueError, BufferError:
            pass


def _bound(sig: Any) -> Callable[..., Any]:
    """A function with the signature ``sig`` (after ``self``), bound, for ``action_spec``."""
    import inspect

    def method(self: object) -> None: ...

    method.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        [
            inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            *sig.parameters.values(),
        ]
    )

    class Holder:
        pass

    Holder.method = method  # type: ignore[attr-defined]
    bound: Callable[..., Any] = Holder().method  # type: ignore[attr-defined]
    return bound


class _Gate:
    def __init__(self, fn: Callable[[], None], waiting: set[ProcessHandle]) -> None:
        self.fn = fn
        self.waiting = waiting
        self.timer: threading.Timer | None = None
        self.done = False


class ModuleProcesses:
    """``ModuleHost.processes`` (``modules.process_port.ProcessPort``): which modules run in a
    process, the handles, the watch and the start gate. ``is_shipped(path)`` is what the app's
    ``config.discovery.is_shipped`` says; ``enabled`` False (``Debug { User_Modules_In_Process:
    true }``) leaves every module in the shell."""

    def __init__(
        self,
        host: ModuleHost,
        is_shipped: Callable[[Path], bool],
        *,
        enabled: bool = True,
        timing: Timing | None = None,
        own_thread: bool = True,
        level: Callable[[], str] = lambda: "INFO",
    ) -> None:
        self.host = host
        host.store.settling = self.starting
        self._is_shipped = is_shipped
        self.enabled = enabled
        self.timing = timing or timing_from_environment(os.environ)
        self.own_thread = own_thread
        self.level = level
        self.closing = False
        self.handles: set[ProcessHandle] = set()
        self._lock = threading.Lock()
        self._gate: _Gate | None = None
        self._watcher: threading.Thread | None = None
        self._stop_watch = threading.Event()
        self._layouts: dict[str, str] = {}

    # -- ProcessPort ----------------------------------------------------------------------------

    def wants(self, py_path: Path) -> bool:
        return self.enabled and not self._is_shipped(py_path)

    def stub(
        self, definition: ModuleDef, py_path: Path
    ) -> tuple[ModuleType | None, Finding | None]:
        info = inspect_module_file(py_path)
        if info.problems:
            return None, finding_for(definition, py_path, info.problems[0])
        self._layouts[definition.name] = definition.file
        return build_module(self, definition, py_path, info.classes), None

    def starting(self, name: str) -> bool:
        """Has the process of module ``name`` not answered (started or failed) yet?"""
        with self._lock:
            return any(
                h.name == name and h.phase in ("importing", "imported", "starting")
                for h in self.handles
            )

    def layout_file(self, name: str) -> str:
        return self._layouts.get(name, "")

    def wait_all(self) -> None:
        """The shell is stopping: wait for every module process to end (they were told), then kill
        the rest."""
        self.closing = True
        self._stop_watch.set()
        if self._gate is not None and self._gate.timer is not None:
            self._gate.timer.cancel()  # a shell that stops before it is ready never says READY
        deadline = time.monotonic() + self.timing.stop
        with self._lock:
            alive = list(self.handles)
        for handle in alive:
            try:
                handle.process.wait(max(0.0, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                logger.warning(f"module {handle.name}: its process did not end; killing it")
                handle.kill()
                handle.process.wait()
            handle.dispose()

    # -- spawn ----------------------------------------------------------------------------------

    def spawn(
        self, name: str, py: Path, ctx: ModuleContext, static_actions: Mapping[str, Any]
    ) -> ProcessHandle:
        if threading.current_thread() is not threading.main_thread():
            # PR_SET_PDEATHSIG fires when the thread that started the process ends
            logger.debug(
                f"module {name}: its process is started from a thread that is not the main one"
            )
        return ProcessHandle(self, name, py, ctx, static_actions)

    def add(self, handle: ProcessHandle) -> None:
        with self._lock:
            self.handles.add(handle)
        if self.own_thread and self._watcher is None:
            self._watcher = threading.Thread(
                target=self._watch_loop, name="module-processes-watch", daemon=True
            )
            self._watcher.start()

    def reap(self, handle: ProcessHandle) -> None:
        """Wait for the process to end (the stop time at most), kill it if not, forget it."""
        if handle.reaping:
            return
        handle.reaping = True

        def run() -> None:
            try:
                handle.process.wait(self.timing.stop)
            except subprocess.TimeoutExpired:
                handle.kill()
                handle.process.wait()
            handle.dispose()
            with self._lock:
                self.handles.discard(handle)

        threading.Thread(target=run, name=f"reap-{handle.name}", daemon=True).start()

    def on_loop(self, fn: Callable[[], None]) -> None:
        call_soon = self.host.call_soon
        if call_soon is None:
            fn()
        else:
            call_soon(fn)

    # -- the watch ---------------------------------------------------------------------------

    def watch(self) -> None:
        """One look at every process's shared record (the watchdog's thread, each tick)."""
        now = time.monotonic_ns()
        with self._lock:
            alive = list(self.handles)
        for handle in alive:
            try:
                handle.watch(now)
            except Exception:
                logger.opt(exception=True).debug("the module watch failed")

    def _watch_loop(self) -> None:
        while not self._stop_watch.wait(self.timing.poll):
            self.watch()

    # -- the loop thread --------------------------------------------------------------------------

    def started(self, handle: ProcessHandle) -> None:
        self.host.process_started(handle.name, handle)
        self._say_deferred(handle.name)
        self._gate_check()

    def _say_deferred(self, name: str) -> None:
        """The module has started: a name its layout reads that it still has not sent is a warning
        after all (the surfaces did not wait for it: it was held back while the process started)."""
        store = self.host.store
        rest = []
        for item in store.deferred:
            use, key, text = item
            if use.split("@", 1)[0] != name:
                rest.append(item)
            elif key not in store.values.get(use, {}):
                logger.warning(text)
        store.deferred[:] = rest

    def settled(self) -> None:
        self._gate_check()

    def when_settled(self, fn: Callable[[], None]) -> None:
        """Call ``fn`` on the loop thread once every process started so far has answered (started,
        failed or ended), or after the gate time (:attr:`Timing.gate`) with a warning naming the
        ones still starting. With no process: ``fn()`` now."""
        waiting = {h for h in self.handles if h.phase not in ("running", "failed", "ended")}
        if not waiting:
            fn()
            return
        gate = self._gate = _Gate(fn, waiting)

        def expire() -> None:
            self.on_loop(lambda: self._open(gate, expired=True))

        gate.timer = threading.Timer(self.timing.gate, expire)
        gate.timer.daemon = True
        gate.timer.start()

    def _gate_check(self) -> None:
        gate = self._gate
        if gate is None or gate.done:
            return
        gate.waiting = {h for h in gate.waiting if h.phase not in ("running", "failed", "ended")}
        if not gate.waiting:
            self._open(gate, expired=False)

    def _open(self, gate: _Gate, *, expired: bool) -> None:
        if gate.done or self.closing:
            return
        gate.done = True
        if gate.timer is not None:
            gate.timer.cancel()
        if expired:
            names = ", ".join(
                sorted(h.name for h in gate.waiting if h.phase not in ("failed", "ended"))
            )
            if names:
                logger.warning(f"module {names} is still starting; the shell is ready")
        gate.fn()

    def status(self) -> list[dict[str, Any]]:
        with self._lock:
            handles = sorted(self.handles, key=lambda h: h.name)
        out = []
        for h in handles:
            tries = self.host.restarts.tries(h.name)
            out.append({"module": h.name, "pid": h.pid, "state": h.phase, "tries": tries})
        return out

    def set_level(self, level: str) -> None:
        with self._lock:
            handles = list(self.handles)
        for h in handles:
            h.send({"t": "level", "level": level})
