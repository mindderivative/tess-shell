"""The shell's own control interface on the session bus (IPC and CLI > The Bus Name, The Interface,
Threading; ADR-0013).

The shell owns ``io.github.mindderivative.TesseraeShell`` and exports ``/io/github/mindderivative/
TesseraeShell`` with the interface ``io.github.mindderivative.TesseraeShell1``: the methods
``Reload``, ``Quit``, ``Status``, ``Show``, ``Hide``, ``Toggle``, ``ClosePopup``, ``Call`` and
``SetLogLevel``, the properties ``State``, ``Version`` and ``ApiVersion`` and the signals
``Reloaded``, ``ErrorReported`` and ``SurfaceChanged``. The ``tesserae-shell`` commands are its
clients (``tess_shell.client``).

Threads. Every handler runs on the ``dbus`` service thread and never touches a node, a window or a
module: it hands the command to the loop with ``call_soon`` and awaits the answer with a timeout of
five seconds (a stuck loop gives the ``Timeout`` error and the caller is answered all the same).
``Reload`` validates the files on a worker thread of the default executor (it reads and parses
files: it must not block the ``dbus`` thread) and applies on the loop. ``Quit`` also asks the engine
to stop from this thread (``LoopHandle.stop`` may be called from any), so a quit works when the loop
is busy. Idle, the interface does nothing: there is no timer, and a signal is emitted only when
something happened.

The name is taken with ``Bus.own_name`` (``DO_NOT_QUEUE``): a name that is owned means another shell
is running (exit code 4). The object is exported on every connection to the bus, before the name is
asked for on it, so a reconnect brings both back (``Bus.on_reconnect``).
"""

from __future__ import annotations

import asyncio
import inspect
import json
from collections import deque
from collections.abc import Callable
from typing import Any, Protocol

from dbus_fast import DBusError, PropertyAccess
from dbus_fast.aio import MessageBus
from dbus_fast.service import ServiceInterface, dbus_method, dbus_property, dbus_signal
from loguru import logger

from tess_shell.services.bus import Bus, ServiceThread, Unsubscribe

NAME = "io.github.mindderivative.TesseraeShell"
PATH = "/io/github/mindderivative/TesseraeShell"
INTERFACE = "io.github.mindderivative.TesseraeShell1"
ERROR = INTERFACE + ".Error."
API_VERSION = 1  # the ``1`` of the interface name: a breaking change makes 2
LOOP_TIMEOUT = 5.0  # seconds a command waits for the loop
STATES = ("starting", "running", "stopping")
LAST_ERRORS = 20


class CommandError(Exception):
    """A command that cannot be done, with the words for the caller (the unknown name, the module's
    name, ...). It becomes the D-Bus error ``<interface>.Error.<name>``."""

    def __init__(self, message: str, name: str = "Failed") -> None:
        super().__init__(message)
        self.name = name


class Commands(Protocol):
    """What the shell does for the interface (``tess_shell.commands.ShellCommands``). Everything
    but ``reload_validate`` and ``quit`` runs on the loop thread."""

    def status(self) -> dict[str, Any]: ...

    def surface(self, action: str, name: str) -> tuple[bool, str]: ...

    def close_popup(self) -> None: ...

    def call(self, module: str, action: str, values: list[Any]) -> Any: ...

    def set_log_level(self, level: str) -> None: ...

    def reload_validate(self) -> Any:
        """Any thread but the loop's. Returns ``(ok, message)`` for a reload that was refused, or
        an opaque ticket for ``reload_apply``."""

    def reload_apply(self, ticket: Any) -> tuple[bool, str]: ...

    def quit(self) -> None:
        """Any thread: ask the engine to stop."""


class Reported(Protocol):
    """A finding of the shell (``schema.findings.Finding``): the fields the interface uses."""

    @property
    def severity(self) -> str: ...

    @property
    def rule(self) -> str: ...

    @property
    def file(self) -> str: ...

    @property
    def line(self) -> int: ...

    @property
    def message(self) -> str: ...


class ErrorLog:
    """The last errors the shell reported (rule, file, line, message): what ``Status`` lists. Never
    a log line and never a value of a param."""

    def __init__(self, size: int = LAST_ERRORS) -> None:
        self._errors: deque[dict[str, Any]] = deque(maxlen=size)

    def add(self, finding: Reported) -> None:
        self._errors.append(
            {
                "rule": finding.rule,
                "file": finding.file,
                "line": finding.line,
                "message": finding.message,
            }
        )

    def last(self) -> list[dict[str, Any]]:
        return list(self._errors)


def _method(name: str, ins: list[str], out: str, fn: Callable[..., Any]) -> Any:
    async def impl(self: Any, *args: Any) -> Any:
        return await fn(*args)

    params = [inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD)]
    params += [
        inspect.Parameter(f"a{i}", inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=sig)
        for i, sig in enumerate(ins)
    ]
    impl.__signature__ = inspect.Signature(params, return_annotation=out or None)  # type: ignore[attr-defined]
    impl.__name__ = name
    return dbus_method(name=name)(impl)


def _property(name: str, sig: str, get: Callable[[], Any]) -> Any:
    def getter(self: Any) -> Any:
        return get()

    getter.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
        [inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD)],
        return_annotation=sig,
    )
    getter.__name__ = name
    return dbus_property(access=PropertyAccess.READ, name=name)(getter)


def _signal(name: str, sig: str, count: int) -> Any:
    def impl(self: Any, *args: Any) -> Any:
        return list(args) if count != 1 else args[0]

    params = [inspect.Parameter("self", inspect.Parameter.POSITIONAL_OR_KEYWORD)]
    params += [
        inspect.Parameter(f"a{i}", inspect.Parameter.POSITIONAL_OR_KEYWORD) for i in range(count)
    ]
    impl.__signature__ = inspect.Signature(params, return_annotation=sig)  # type: ignore[attr-defined]
    impl.__name__ = name
    return dbus_signal(name=name)(impl)


class ControlService:
    """The interface on the ``dbus`` service thread. ``call_soon`` queues a function for the loop
    (``LoopHandle.call_soon``); ``version`` is the shell's version (the ``Version`` property)."""

    def __init__(
        self,
        service: ServiceThread,
        call_soon: Callable[[Callable[[], None]], None],
        commands: Commands,
        version: str,
        errors: ErrorLog | None = None,
        *,
        loop_timeout: float = LOOP_TIMEOUT,
    ) -> None:
        self.service = service
        self.call_soon = call_soon
        self.commands = commands
        self.version = version
        self.loop_timeout = loop_timeout
        self.state = "starting"
        self.errors = errors if errors is not None else ErrorLog()
        self.owned = False  # the shell owns the bus name now
        self.exported = 0  # connections the object was exported on (tests)
        self._iface: ServiceInterface | None = None
        self._conn: MessageBus | None = None
        self._unhook: Unsubscribe | None = None

    @property
    def bus(self) -> Bus:
        return self.service.session

    # -- starting and stopping (service thread, awaited by the shell) ---------------------------

    async def start(self) -> bool:
        """Export the object and own the name. ``True`` when the shell owns it; ``False`` when
        another process does (another shell is running). Raises ``ServiceUnavailable`` when the
        session bus cannot be reached."""
        self._unhook = self.bus.on_reconnect(self._reconnected)  # before the name's own hook
        try:
            self._export(await self.bus.connection())
            owned = await self.bus.own_name(NAME)
        except BaseException:
            await self.stop()
            raise
        self.owned = owned
        if not owned:
            await self.stop()
        return owned

    async def stop(self) -> None:
        """Give the name up and take the object off the bus."""
        if self._unhook is not None:
            self._unhook()
            self._unhook = None
        if self.owned:
            await self.bus.release_name(NAME)
            self.owned = False
        self._unexport()

    async def _reconnected(self, conn: MessageBus) -> None:
        self._export(conn)

    def _export(self, conn: MessageBus) -> None:
        if self._conn is conn and self._iface is not None:
            return
        self._unexport()
        iface = self._build()
        conn.export(PATH, iface)
        self._conn, self._iface = conn, iface
        self.exported += 1
        logger.debug(f"control: {PATH} exported on the session bus")

    def _unexport(self) -> None:
        conn, iface = self._conn, self._iface
        self._conn = self._iface = None
        if conn is not None and iface is not None and conn.connected:
            try:
                conn.unexport(PATH, iface)
            except Exception:
                logger.debug("control: the object was already gone from the bus")

    # -- the state, the signals (any thread) ----------------------------------------------------

    def set_state(self, state: str) -> None:
        """``starting``, ``running`` or ``stopping``: the ``State`` property, with its change
        notification."""
        if state == self.state:
            return
        self.state = state

        def emit() -> None:
            if self._iface is not None:
                self._iface.emit_properties_changed({"State": state})

        self.service.post(emit)

    def reloaded(self, ok: bool, summary: str) -> None:
        self._emit("Reloaded", ok, summary)

    def error_reported(self, finding: Reported) -> None:
        """A finding the shell logged: remembered for ``Status``, and the ``ErrorReported`` signal
        when it is an error."""
        if finding.severity != "error":
            return
        self.errors.add(finding)
        self._emit("ErrorReported", finding.rule, finding.file, finding.line, finding.message)

    def surface_changed(self, name: str, state: str) -> None:
        self._emit("SurfaceChanged", name, state)

    def _emit(self, signal: str, *args: Any) -> None:
        def emit() -> None:
            iface = self._iface
            if iface is not None:
                try:
                    getattr(iface, signal)(*args)
                except Exception:
                    logger.opt(exception=True).debug(f"control: could not emit {signal}")

        self.service.post(emit)

    # -- the interface --------------------------------------------------------------------------

    def _build(self) -> ServiceInterface:
        ns: dict[str, Any] = {
            "Reload": _method("Reload", [], "bs", self._reload),
            "Quit": _method("Quit", [], "", self._quit),
            "Status": _method("Status", [], "s", self._status),
            "Show": _method("Show", ["s"], "bs", lambda n: self._surface("Show", n)),
            "Hide": _method("Hide", ["s"], "bs", lambda n: self._surface("Hide", n)),
            "Toggle": _method("Toggle", ["s"], "bs", lambda n: self._surface("Toggle", n)),
            "ClosePopup": _method("ClosePopup", [], "", self._close_popup),
            "Call": _method("Call", ["s", "s", "s"], "s", self._call),
            "SetLogLevel": _method("SetLogLevel", ["s"], "", self._set_log_level),
            "State": _property("State", "s", lambda: self.state),
            "Version": _property("Version", "s", lambda: self.version),
            "ApiVersion": _property("ApiVersion", "u", lambda: API_VERSION),
            "Reloaded": _signal("Reloaded", "bs", 2),
            "ErrorReported": _signal("ErrorReported", "ssis", 4),
            "SurfaceChanged": _signal("SurfaceChanged", "ss", 2),
        }
        cls = type("TesseraeShell1", (ServiceInterface,), ns)
        return cls(INTERFACE)  # type: ignore[no-any-return]

    # -- the handlers (service thread) ----------------------------------------------------------

    def _require_running(self) -> None:
        if self.state != "running":
            raise DBusError(ERROR + "NotRunning", f"the shell is {self.state}, not running")

    async def on_loop[T](self, fn: Callable[[], T]) -> T:
        """Run ``fn`` on the loop thread and wait for its result, at most ``loop_timeout``
        seconds. The handler touches nothing itself."""
        aio = asyncio.get_running_loop()
        done: asyncio.Future[T] = aio.create_future()

        def settle(setter: Callable[[Any], None], value: Any) -> None:
            if not done.done():  # a timed out call is no longer waited for
                setter(value)

        def run() -> None:
            try:
                result = fn()
            except BaseException as exc:
                aio.call_soon_threadsafe(settle, done.set_exception, exc)
            else:
                aio.call_soon_threadsafe(settle, done.set_result, result)

        self.call_soon(run)
        try:
            return await asyncio.wait_for(done, self.loop_timeout)
        except TimeoutError:
            raise DBusError(
                ERROR + "Timeout",
                f"the shell's loop did not answer within {self.loop_timeout:g} s",
            ) from None
        except CommandError as exc:
            raise DBusError(ERROR + exc.name, str(exc)) from exc
        except DBusError:
            raise
        except Exception as exc:
            logger.opt(exception=True).error("control: a command raised")
            raise DBusError(ERROR + "Failed", f"internal error: {exc!r}") from exc

    async def _reload(self) -> list[Any]:
        self._require_running()
        try:
            ticket = await asyncio.to_thread(self.commands.reload_validate)
        except Exception as exc:
            logger.opt(exception=True).error("control: reload failed")
            raise DBusError(ERROR + "Failed", f"internal error: {exc!r}") from exc
        if isinstance(ticket, tuple):  # refused: nothing to apply
            return [ticket[0], ticket[1]]
        ok, message = await self.on_loop(lambda: self.commands.reload_apply(ticket))
        return [ok, message]

    async def _quit(self) -> None:
        self._require_running()
        self.set_state("stopping")
        logger.info("quit requested over the control interface")
        self.commands.quit()  # LoopHandle.stop() from this thread: a busy loop does not hold it up

    async def _status(self) -> str:
        if self.state != "running":  # the loop is not running yet (or not any more)
            return json.dumps(
                {
                    "state": self.state,
                    "version": {"shell": self.version},
                    "api_version": API_VERSION,
                }
            )
        status = await self.on_loop(self.commands.status)
        return json.dumps({"state": self.state, "api_version": API_VERSION, **status})

    async def _surface(self, action: str, name: str) -> list[Any]:
        self._require_running()
        ok, message = await self.on_loop(lambda: self.commands.surface(action, name))
        return [ok, message]

    async def _close_popup(self) -> None:
        self._require_running()
        await self.on_loop(self.commands.close_popup)

    async def _call(self, module: str, action: str, args: str) -> str:
        self._require_running()
        try:
            values = json.loads(args)
        except ValueError as exc:
            raise DBusError(ERROR + "BadArguments", f"the arguments are not JSON ({exc})") from exc
        if not isinstance(values, list):
            raise DBusError(ERROR + "BadArguments", "the arguments are a JSON array")
        result = await self.on_loop(lambda: self.commands.call(module, action, values))
        try:
            return json.dumps(result)
        except TypeError, ValueError:
            return "null"  # an action that returns something that is not plain data

    async def _set_log_level(self, level: str) -> None:
        self._require_running()
        await self.on_loop(lambda: self.commands.set_log_level(level))
