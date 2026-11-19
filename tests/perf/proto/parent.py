"""The shell's side of the posture B and C prototype.

``install(posture, services)`` patches ONE method, ``ModuleHost._import``, so that a module the
posture wants in a child is not imported in the shell at all: the host gets a STUB class instead,
built from the module file's syntax tree (``ast``, nothing runs), with the module's ``@action``
methods and the lifecycle methods. The host then loads, checks and starts the stub through its
unchanged code (``load``, ``check_calls``, ``dispatch``, ``start``, ``sync``, ``_replace``,
``_schedule``): the stub's ``__init__`` spawns the child, ``start`` waits for it (the first time) and
every other method forwards a message. No product file is edited.

Postures: ``A`` patches nothing; ``B`` runs every module file in a child; ``C`` runs only the modules
that are not shipped with the package (the user's own files) in a child; ``L`` (lean B) runs in a
child every module file that has Python of its own (``has_own_code``) and keeps the files with none
(a class that is only ``pass``: the TDL-only widget and popup modules) in the shell.
Services: ``B1`` gives each child its own D-Bus, PulseAudio and tray connections; ``B2`` keeps them in
the shell and proxies calls and signals. Popups, surfaces, windows, the application index and the
icon registry are the shell's in both (they are tre's or the shell's state, not connections).
"""

from __future__ import annotations

import ast
import concurrent.futures
import inspect
import mmap
import os
import socket
import struct
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import asdict, fields, is_dataclass
from functools import partial
from pathlib import Path
from types import ModuleType
from typing import Any

from loguru import logger
from tests.perf.proto.wire import Channel

import tess_shell
from tess_shell.module import Module
from tess_shell.modules.context import ModuleContext
from tess_shell.modules.host import PACKAGE, ModuleHost, report
from tess_shell.schema.findings import Finding
from tess_shell.services.api import ServiceError

REPO = Path(__file__).resolve().parents[3]
SHIPPED = Path(tess_shell.__file__).resolve().parent / "shipped"

# seconds a callback runs before the stall is logged (Crash Recovery: 2 s) and before the module
# process is killed. The shell-wide 10 s restart of Crash Recovery would let a 10 s sleep end on its
# own, and only one module restarts, so the kill is earlier. The environment variables are for the
# smoke test of the harness, which cannot wait 10 s.
STALL_LOG = float(os.environ.get("TESS_PROTO_STALL", "2.0"))
HANG_KILL = float(os.environ.get("TESS_PROTO_KILL", "5.0"))
WATCH_INTERVAL = float(os.environ.get("TESS_PROTO_WATCH", "1.0"))  # seconds between polls
START_TIMEOUT = 15.0  # a first start that has not answered by then marks the module failed
STOP_TIMEOUT = 2.0  # a module's stop() gets this long before the process is killed
ALLOWED = {"B1", "B2"}
POSTURES = {"B", "C", "L"}
RULES = ("strict", "validate")  # the lean B's test of "Python of its own" (``has_own_code``)
LEAN_RULE = os.environ.get("TESS_PROTO_LEAN_RULE", "strict")
DECISIONS = os.environ.get("TESS_PROTO_DECISIONS")  # a file: one line ``<module> child|shell``


# -- a module file read without running it ---------------------------------------------------------


def _is_name(node: ast.expr, name: str) -> bool:
    return (isinstance(node, ast.Name) and node.id == name) or (
        isinstance(node, ast.Attribute) and node.attr == name
    )


def _signature(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> inspect.Signature:
    """The signature the host reads with ``inspect`` (``action_spec``): ``self``, the parameters,
    with a default only as a marker (the value is not needed)."""
    a = fn.args
    params: list[inspect.Parameter] = []
    positional = [*a.posonlyargs, *a.args]
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(a.defaults)) + list(
        a.defaults
    )
    for arg, default in zip(positional[1:], defaults[1:], strict=True):  # not ``self``
        params.append(
            inspect.Parameter(
                arg.arg,
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                default=inspect.Parameter.empty if default is None else None,
            )
        )
    if a.vararg:
        params.append(inspect.Parameter(a.vararg.arg, inspect.Parameter.VAR_POSITIONAL))
    for arg, kw_default in zip(a.kwonlyargs, a.kw_defaults, strict=True):
        params.append(
            inspect.Parameter(
                arg.arg,
                inspect.Parameter.KEYWORD_ONLY,
                default=inspect.Parameter.empty if kw_default is None else None,
            )
        )
    if a.kwarg:
        params.append(inspect.Parameter(a.kwarg.arg, inspect.Parameter.VAR_KEYWORD))
    return inspect.Signature(params)


def scan(py_path: Path) -> dict[str, dict[str, inspect.Signature]]:
    """``{class name: {action name: signature}}`` for every class extending ``Module``."""
    tree = ast.parse(py_path.read_text(encoding="utf-8"), str(py_path))
    found: dict[str, dict[str, inspect.Signature]] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and any(_is_name(b, "Module") for b in node.bases):
            actions: dict[str, inspect.Signature] = {}
            for item in node.body:
                if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef) and any(
                    _is_name(d, "action") for d in item.decorator_list
                ):
                    actions[item.name] = _signature(item)
            found[node.name] = actions
    return found


def _trivial(node: ast.stmt) -> bool:
    """A statement that is no code: ``pass``, a docstring or ``...``."""
    return isinstance(node, ast.Pass) or (
        isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant)
    )


def _only_imports(nodes: list[ast.stmt]) -> bool:
    return all(isinstance(n, ast.Import | ast.ImportFrom) or _trivial(n) for n in nodes)


def _literal(node: ast.expr) -> bool:
    try:
        ast.literal_eval(node)
    except ValueError, TypeError, SyntaxError, RecursionError:
        return False
    return True


def has_own_code(py_path: Path, rule: str = "strict") -> bool:
    """Does the module file have Python of its own? Read from the syntax tree, as ``scan`` does.

    ``strict`` (the lean B as the maintainer described it, the TDL-only modules): NO when every
    top-level statement is an import (also under ``if TYPE_CHECKING:``), a docstring, ``pass``, or
    a class extending ``Module`` whose body is only ``pass``, a docstring or ``...``. A missing file
    has none. Anything else (a method, a constant, a function, a second class) is code of its own,
    and so is a file that does not parse: its child reports the error, as in B.

    ``validate``: as ``strict``, and a literal constant at the top level and a class body that
    holds a ``validate_use`` method are no code of their own either: the widget modules whose
    Python is only the check of their parameters (Button, Image, Slider, ...). That check then runs
    in the shell, as it does in A, when a use is added."""
    if rule not in RULES:
        raise ValueError(f"lean rule {rule!r}: use {' or '.join(RULES)}")
    validate = rule == "validate"
    if not py_path.is_file():
        return False
    try:
        tree = ast.parse(py_path.read_text(encoding="utf-8"), str(py_path))
    except SyntaxError:
        return True
    for node in tree.body:
        if _trivial(node) or isinstance(node, ast.Import | ast.ImportFrom):
            continue
        if isinstance(node, ast.If) and _only_imports(node.body) and _only_imports(node.orelse):
            continue
        if (
            validate
            and isinstance(node, ast.Assign | ast.AnnAssign)
            and node.value is not None
            and _literal(node.value)
        ):
            continue
        if (
            isinstance(node, ast.ClassDef)
            and any(_is_name(b, "Module") for b in node.bases)
            and not node.decorator_list
            and all(
                _trivial(item)
                or (
                    validate
                    and isinstance(item, ast.FunctionDef)
                    and item.name == "validate_use"
                    and not item.decorator_list
                )
                for item in node.body
            )
        ):
            continue
        return True
    return False


def event_fields(event: Any) -> dict[str, Any]:
    """An ``Event`` as plain data: everything but the engine's own object (``stop`` cannot cross)."""
    return {f.name: getattr(event, f.name) for f in fields(event) if f.name != "_raw"}


# -- the stub the host loads in place of the module ------------------------------------------------


class MirrorDict(dict[str, Any]):
    """``ctx.uses`` in the shell: every change the host makes is told to the child, in order."""

    def __init__(self, initial: Mapping[str, Any], handle: Child) -> None:
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


def use_dict(record: Any) -> dict[str, Any]:
    return {
        "key": record.key,
        "name": record.name,
        "uid": record.uid,
        "monitor": record.monitor,
        "params": dict(record.params),
    }


class StubModule(Module):
    """What ``load`` instantiates for a module that runs in a child."""

    _launcher: Launcher
    _definition_name: str
    _py: Path
    _proto: Child

    def __init__(self) -> None:
        self._proto = self._launcher.spawn(self._definition_name, self._py, self.ctx)

    def start(self) -> None:
        self._proto.start()

    def stop(self) -> None:
        self._proto.stop()

    def reload(self) -> None:
        self._proto.send({"t": "reload"})

    def validate_use(self, use: Any) -> None:
        return None  # the child validates every use before start (a ValueError is logged there)

    def use_added(self, use: Any) -> None:
        self._proto.send({"t": "use_added", "key": use.key})

    def use_removed(self, use: Any) -> None:
        self._proto.send({"t": "use_removed", "rec": use_dict(use)})

    def on_service_lost(self, name: str) -> None:
        self._proto.send({"t": "lost", "name": name})

    def on_service_found(self, name: str) -> None:
        self._proto.send({"t": "found", "name": name})


def _action(name: str, signature: inspect.Signature) -> Callable[..., None]:
    def stub(self: StubModule, event: Any, **kw: Any) -> None:
        caller = self.ctx.caller
        self._proto.send(
            {
                "t": "call",
                "action": name,
                "event": event_fields(event),
                "kw": kw,
                "caller": caller.key if caller is not None else None,
            }
        )

    stub.__name__ = name
    stub.__qualname__ = name
    stub.__tess_action__ = True  # type: ignore[attr-defined]
    stub.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        [
            inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD),
            *signature.parameters.values(),
        ]
    )
    return stub


# -- one child --------------------------------------------------------------------------------


class Child:
    """The shell's end of one module process."""

    def __init__(self, launcher: Launcher, name: str, py: Path, ctx: ModuleContext) -> None:
        self.launcher = launcher
        self.name = name
        self.py = py
        self.ctx = ctx  # the real context in the shell: the services the child proxies run on it
        self.uid = ctx.uid
        self.generation = launcher.generation(name)
        self.pid = 0
        self.intended = False  # the shell ended it (or asked it to): not a crash
        self.ready = threading.Event()
        self.started = threading.Event()
        self.failure: dict[str, Any] | None = None
        self._pending: dict[int, Callable[[bool, Any], None]] = {}
        self._ids = 0
        self._subs: dict[int, Any] = {}
        self._pool: concurrent.futures.ThreadPoolExecutor | None = None
        self._logged_stall = 0
        parent_sock, child_sock = socket.socketpair()
        self.shm_fd = os.memfd_create(f"tess-{name}")
        os.ftruncate(self.shm_fd, 4096)
        self.shm = mmap.mmap(self.shm_fd, 4096)
        self.process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "tests.perf.proto.child",
                "--fd",
                str(child_sock.fileno()),
                "--shm",
                str(self.shm_fd),
                "--name",
                name,
            ],
            pass_fds=(child_sock.fileno(), self.shm_fd),
            cwd=REPO,
            stdin=subprocess.DEVNULL,
        )
        self.pid = self.process.pid
        child_sock.close()
        self.channel = Channel(parent_sock, self._on_message, self._on_closed, f"child-{name}")
        self.channel.start()
        launcher.add(self)
        self.channel.send(
            {
                "t": "init",
                "name": name,
                "uid": ctx.uid,
                "py": str(py),
                "services": launcher.services,
                "config": dict(ctx.config),
                "uses": [use_dict(u) for u in ctx.uses.values()],
            }
        )
        # the host changes ctx.uses and calls the module's hooks: both go to the child
        ctx.uses = MirrorDict(ctx.uses, self)
        ctx.send_available = lambda record: self.send({"t": "avail", "key": record.key})  # type: ignore[method-assign]
        original_close = ctx.close

        def close() -> None:
            original_close()
            self.close()

        ctx.close = close  # type: ignore[method-assign]

    # -- sending ------------------------------------------------------------------------------

    def send(self, message: dict[str, Any]) -> None:
        self.channel.send(message)

    def cb(self, sid: int, *args: Any) -> None:
        """Call the callback ``sid`` of the child."""
        self.channel.send({"t": "cb", "id": sid, "a": args})

    def _reply(
        self, rid: int, ok: bool, value: Any = None, err: dict[str, Any] | None = None
    ) -> None:
        self.channel.send({"t": "re", "id": rid, "ok": ok, "v": value, "err": err})

    # -- lifecycle called by the stub (on the loop thread) --------------------------------------

    def start(self) -> None:
        """The first start of a module waits for the child (so ``READY=1`` means the modules ran
        ``start``, as in A); a restart or a reload does not wait, so the loop is never held for a
        process start: a failure comes back as a ``failed`` message."""
        self.send({"t": "start"})
        if self.generation > 0:
            return
        if not self.started.wait(START_TIMEOUT):
            self.kill()
            raise RuntimeError(f"the module process did not start within {START_TIMEOUT:g} s")
        if self.failure is not None:
            err = self.failure
            raise RuntimeError(f"{err['type']}: {err['msg']}")

    def stop(self) -> None:
        if self.channel.closed:
            return
        self._ids += 1
        rid = self._ids
        done = threading.Event()
        self._pending[rid] = lambda ok, value: done.set()
        self.send({"t": "stop", "id": rid})
        if not done.wait(STOP_TIMEOUT):
            logger.warning(
                f"module {self.name}: stop() did not return in {STOP_TIMEOUT:g} s; killing"
            )
            self.kill()

    def kill(self) -> None:
        self.intended = True
        try:
            self.process.kill()
        except OSError:
            pass

    def close(self) -> None:
        """The module is over (stopped, replaced, failed): the child goes."""
        if self.intended and self.channel.closed:
            return
        self.intended = True
        self.send({"t": "shutdown"})
        self.launcher.reap(self)

    # -- messages from the child (reader thread) ---------------------------------------------------

    def _on_message(self, msg: dict[str, Any]) -> None:
        kind = msg.get("t")
        if kind == "s":
            self.launcher.host.store.send(self.name, msg["u"], msg["k"], msg["v"])
        elif kind == "log":
            level = msg["l"]
            logger.bind(source=f"module:{self.name}", location="-").log(
                level if level in ("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL") else "INFO",
                msg["m"],
            )
        elif kind == "ready":
            self.ready.set()
        elif kind == "started":
            self.started.set()
        elif kind == "failed":
            self.failure = msg["err"]
            self.started.set()
            self.launcher.on_loop(
                partial(self.launcher.child_failed, self, msg["what"], msg["err"])
            )
        elif kind == "re":
            done = self._pending.pop(msg["id"], None)
            if done is not None:
                done(bool(msg.get("ok")), msg.get("v"))
        elif kind in ("rpc", "cmd"):
            self._serve(msg)

    def _on_closed(self) -> None:
        self.started.set()
        if not self.intended:
            self.launcher.on_loop(partial(self.launcher.child_died, self))

    # -- what the child asks for ------------------------------------------------------------

    def _serve(self, msg: dict[str, Any]) -> None:
        method = msg["m"]
        args = msg.get("a", [])
        rid = msg.get("id")
        entry = self.launcher.services_table.get(method)
        if entry is None:
            logger.error(f"module {self.name}: unknown call {method}")
            if rid is not None:
                self._reply(rid, False, err={"type": "RuntimeError", "msg": f"no call {method}"})
            return
        mode, fn = entry

        def run() -> Any:
            return fn(self, *args)

        def finish(value: Any) -> None:
            if rid is None:
                return
            if isinstance(value, concurrent.futures.Future):
                value.add_done_callback(self._future_done(rid))
            else:
                self._reply(rid, True, jsonable(value))

        def guarded() -> None:
            try:
                finish(run())
            except Exception as exc:
                self._failed_call(rid, method, exc)

        if mode == "inline":
            guarded()
        elif mode == "loop":
            self.launcher.on_loop(guarded)
        else:  # "pool": a read that may take a while (files, the index): off the reader thread
            if self._pool is None:
                self._pool = concurrent.futures.ThreadPoolExecutor(
                    max_workers=2, thread_name_prefix=f"serve-{self.name}"
                )
            self._pool.submit(guarded)

    def _future_done(self, rid: int) -> Callable[[concurrent.futures.Future[Any]], None]:
        def done(future: concurrent.futures.Future[Any]) -> None:
            try:
                self._reply(rid, True, jsonable(future.result()))
            except Exception as exc:
                self._failed_call(rid, "future", exc)

        return done

    def _failed_call(self, rid: int | None, method: str, exc: Exception) -> None:
        logger.opt(exception=True).error(f"module {self.name}: {method} failed in the shell")
        if rid is not None:
            self._reply(rid, False, err=error_dict(exc))

    def subscribe(self, sid: int, subscription: Any) -> None:
        self._subs[sid] = subscription

    def unsubscribe(self, sid: int) -> None:
        sub = self._subs.pop(sid, None)
        if sub is not None:
            sub.cancel()

    def watch(self, now_ns: int) -> None:
        """The watchdog's look at the shared record (its own thread)."""
        started = struct.unpack_from("<q", self.shm, 0)[0]
        if started == 0 or self.intended:
            return
        age = (now_ns - started) / 1e9
        entry = bytes(self.shm[16:80]).split(b"\0", 1)[0].decode("utf-8", "replace")
        if age >= STALL_LOG and self._logged_stall != started:
            self._logged_stall = started
            logger.warning(
                f"module {self.name}: the callback {entry} has run for {age:.1f} s "
                f"(stalled; the process is killed at {HANG_KILL:g} s)"
            )
        if age >= HANG_KILL:
            logger.error(
                f"module {self.name} (UID {self.uid}): the callback {entry} did not return in "
                f"{HANG_KILL:g} s; killing the module process (pid {self.pid})"
            )
            self.kill()
            self.launcher.on_loop(partial(self.launcher.child_died, self, "hung"))


def jsonable(value: Any) -> Any:
    """Dataclasses (``AppInfo``, ``WindowInfo``, ``AudioState``) as dicts, tuples as lists."""
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, list | tuple):
        return [jsonable(v) for v in value]
    return value


def error_dict(exc: BaseException) -> dict[str, Any]:
    if isinstance(exc, ServiceError):
        return {
            "type": type(exc).__name__,
            "msg": str(exc),
            "args": [exc.service, exc.detail, exc.name],
        }
    return {"type": type(exc).__name__, "msg": str(exc)}


# -- the launcher: what ModuleHost._import is replaced by ----------------------------------------


class Launcher:
    def __init__(self, host: ModuleHost, posture: str, services: str) -> None:
        self.host = host
        self.posture = posture
        self.services = services
        self.children: set[Child] = set()
        self.by_name: dict[str, Child] = {}
        self._generations: dict[str, int] = {}
        self._lock = threading.Lock()
        self._watchdog: threading.Thread | None = None
        self._stop = threading.Event()
        self._reaper = concurrent.futures.ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="reap"
        )
        from tests.perf.proto.brokers import TABLE

        self.services_table = TABLE

    # -- the choice -------------------------------------------------------------------------------

    def wants(self, py_path: Path) -> bool:
        """Does the posture run this module file in a child (recorded for the harness)?"""
        child = self._wants(py_path)
        if DECISIONS:
            name = py_path.parent.name
            with open(DECISIONS, "a") as out:
                out.write(f"{name} {'child' if child else 'shell'}\n")
        return child

    def _wants(self, py_path: Path) -> bool:
        if self.posture == "B":
            return True
        if self.posture == "L":
            return has_own_code(py_path, LEAN_RULE)
        if self.posture == "C":
            try:
                py_path.resolve().relative_to(SHIPPED)
            except ValueError:
                return True
        return False

    def stub(self, definition: Any, py_path: Path) -> ModuleType:
        name = f"{PACKAGE}.{definition.name}"
        module = ModuleType(name)
        module.__file__ = str(py_path)
        classes = scan(py_path)
        sys.modules[name] = module
        for cls_name, actions in classes.items():
            namespace: dict[str, Any] = {
                "__module__": name,
                "_launcher": self,
                "_definition_name": definition.name,
                "_py": py_path,
            }
            for action_name, signature in actions.items():
                namespace[action_name] = _action(action_name, signature)
            module.__dict__[cls_name] = type(cls_name, (StubModule,), namespace)
        return module

    # -- children -------------------------------------------------------------------------------

    def generation(self, name: str) -> int:
        with self._lock:
            n = self._generations.get(name, 0)
            self._generations[name] = n + 1
            return n

    def spawn(self, name: str, py: Path, ctx: ModuleContext) -> Child:
        return Child(self, name, py, ctx)

    def add(self, child: Child) -> None:
        with self._lock:
            self.children.add(child)
            self.by_name[child.name] = child
            if self._watchdog is None:
                self._watchdog = threading.Thread(
                    target=self._watch, name="proto-watchdog", daemon=True
                )
                self._watchdog.start()

    def reap(self, child: Child) -> None:
        self._reaper.submit(self._reap, child)

    def _reap(self, child: Child) -> None:
        try:
            child.process.wait(timeout=STOP_TIMEOUT)
        except subprocess.TimeoutExpired:
            child.process.kill()
            child.process.wait()
        child.channel.close()
        with self._lock:
            self.children.discard(child)
            if self.by_name.get(child.name) is child:
                del self.by_name[child.name]

    def on_loop(self, fn: Callable[[], None]) -> None:
        call_soon = self.host.call_soon
        if call_soon is None:
            fn()
        else:
            call_soon(fn)

    def _watch(self) -> None:
        while not self._stop.wait(WATCH_INTERVAL):
            now = time.monotonic_ns()
            with self._lock:
                alive = list(self.children)
            for child in alive:
                try:
                    child.watch(now)
                except Exception:
                    logger.opt(exception=True).debug("the watchdog's look failed")

    # -- failures (loop thread) -------------------------------------------------------------------

    def _current(self, child: Child) -> Any:
        loaded = self.host.loaded.get(child.name)
        if loaded is None or getattr(loaded.instance, "_proto", None) is not child:
            return None  # replaced or removed since
        return loaded

    def child_failed(self, child: Child, what: str, err: dict[str, Any]) -> None:
        """A lifecycle method raised in the child: as ``ModuleHost._call`` does for A."""
        loaded = self._current(child)
        if loaded is None or loaded.state == "failed":
            return
        loaded.state = "failed"
        loaded.ctx.close()
        if what != "stop":
            self.host._schedule(child.name, child.uid)
        report(
            [
                Finding(
                    str(child.py),
                    err.get("line", 0) or 1,
                    1,
                    "error",
                    f"module-{what}",
                    f"{child.name}: {what}() raised {err['type']}: {err['msg']}",
                    f"the module is marked failed (UID {child.uid}); its surfaces keep their "
                    "last values",
                )
            ]
        )

    def child_died(self, child: Child, why: str = "") -> None:
        """The module process ended by itself (a crash, a kill) or was killed as hung."""
        loaded = self._current(child)
        if loaded is None or loaded.state == "failed":
            return
        code = child.process.poll()
        reason = why or f"exit code {code}" if code is not None else why or "closed its pipe"
        logger.error(
            f"module {child.name} (UID {child.uid}): the module process (pid {child.pid}) ended: "
            f"{reason}; its surfaces keep their last values"
        )
        loaded.state = "failed"
        loaded.ctx.close()
        self.host._schedule(child.name, child.uid)

    def shutdown(self) -> None:
        self._stop.set()


_launchers: dict[int, Launcher] = {}


def install(posture: str, services: str) -> None:
    """Patch ``ModuleHost._import`` for the posture; ``A`` patches nothing."""
    if posture == "A":
        return
    if posture not in POSTURES or services not in ALLOWED:
        raise SystemExit(
            f"posture {posture!r} services {services!r}: use A, B, C or L and B1 or B2"
        )
    original = ModuleHost._import

    def _import(self: ModuleHost, definition: Any, py_path: Path) -> Any:
        launcher = _launchers.get(id(self))
        if launcher is None:
            launcher = _launchers[id(self)] = Launcher(self, posture, services)
        if not launcher.wants(py_path):
            return original(self, definition, py_path)
        try:
            return launcher.stub(definition, py_path), None
        except SyntaxError as exc:
            return None, Finding(
                str(py_path),
                exc.lineno or 1,
                1,
                "error",
                "module-import",
                f"{definition.name}: {exc}",
            )

    ModuleHost._import = _import  # type: ignore[method-assign]
