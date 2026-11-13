"""The control commands (``reload``, ``quit``, ``status``, ``show``, ``hide``, ``toggle``, ``call``,
``log-level``): a thin client of the shell's own D-Bus interface (IPC and CLI > The Command Line).

Fast to start: this module imports the standard library and ``jeepney`` (a blocking, pure Python
D-Bus client) and nothing else of the shell: never the engine, Loguru, the TDL parser, TEL or
``dbus-fast``, so a command from a keyboard shortcut costs about what a bare Python start and one
bus call cost (``tests/test_client_fast.py`` lists the imported modules). The names of the bus, the
object and the interface are repeated here from ``services/control.py`` for that reason; a test
keeps the two equal.

Exit codes (IPC and CLI > Exit Codes of the Client): 0 done, 1 the command ran and failed (an
unknown name, a rejected action, errors in the files), 2 no session bus, 3 no shell is running, 5
the call timed out. With ``--json`` the answer is one JSON object on standard output, an error
too (``{"ok": false, "error": ..., "exit": N}``) next to the exit code, so a program that drives the
command reads one stream.
"""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Sequence
from typing import Any

from tess_shell import __version__
from tess_shell.exit_codes import ExitCode
from tess_shell.options import Options

NAME = "io.github.mindderivative.TesseraeShell"
PATH = "/io/github/mindderivative/TesseraeShell"
INTERFACE = "io.github.mindderivative.TesseraeShell1"

_NO_OWNER = (
    "org.freedesktop.DBus.Error.ServiceUnknown",
    "org.freedesktop.DBus.Error.NameHasNoOwner",
)
_UNKNOWN_METHOD = (
    "org.freedesktop.DBus.Error.UnknownMethod",
    "org.freedesktop.DBus.Error.UnknownInterface",
)


class Failure(Exception):
    """A command that ends with ``code``; ``message`` is what the user reads."""

    def __init__(self, code: ExitCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def session_address() -> str:
    """The session bus the way ``libdbus`` finds it: ``DBUS_SESSION_BUS_ADDRESS``, else the
    systemd user bus socket in ``XDG_RUNTIME_DIR``."""
    address = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
    if address:
        return address
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime and os.path.exists(f"{runtime}/bus"):
        return f"unix:path={runtime}/bus"
    raise Failure(
        ExitCode.ENVIRONMENT,
        "no session bus: DBUS_SESSION_BUS_ADDRESS is not set and "
        f"{runtime or '$XDG_RUNTIME_DIR'}/bus does not exist",
    )


class Shell:
    """One connection to the session bus, for the calls of one command."""

    def __init__(self, timeout: float) -> None:
        from jeepney import DBusAddress
        from jeepney.io.blocking import open_dbus_connection

        self.timeout = timeout
        self.address = DBusAddress(PATH, bus_name=NAME, interface=INTERFACE)
        try:
            self.connection = open_dbus_connection(bus=session_address(), enable_fds=False)
        except Failure:
            raise
        except (OSError, KeyError, ValueError) as exc:
            raise Failure(ExitCode.ENVIRONMENT, f"cannot reach the session bus ({exc})") from exc

    def close(self) -> None:
        self.connection.close()

    def call(self, method: str, signature: str = "", body: Sequence[Any] = ()) -> tuple[Any, ...]:
        """The reply's values. Raises :class:`Failure` for an error reply, a missing shell or a
        timeout."""
        from jeepney import HeaderFields, MessageType, new_method_call

        message = new_method_call(self.address, method, signature, tuple(body))
        try:
            reply = self.connection.send_and_get_reply(message, timeout=self.timeout)
        except TimeoutError as exc:
            raise Failure(
                ExitCode.TIMEOUT,
                f"the shell did not answer within {self.timeout:g} s (its loop is busy or stuck)",
            ) from exc
        except OSError as exc:
            raise Failure(ExitCode.ENVIRONMENT, f"lost the session bus ({exc})") from exc
        if reply.header.message_type == MessageType.error:
            name = reply.header.fields.get(HeaderFields.error_name, "")
            text = str(reply.body[0]) if reply.body else ""
            raise self.failure(name, text, method)
        return tuple(reply.body)

    def failure(self, name: str, text: str, method: str) -> Failure:
        if name in _NO_OWNER:
            return Failure(ExitCode.NOT_RUNNING, "no shell is running (nobody owns the bus name)")
        if name in _UNKNOWN_METHOD:
            return Failure(ExitCode.CONFIG, self.older(method))
        return Failure(ExitCode.CONFIG, text or name)

    def older(self, method: str) -> str:
        """The running shell does not know a method this client sends: say both versions."""
        from jeepney import Properties

        running = "unknown"
        try:
            reply = self.connection.send_and_get_reply(
                Properties(self.address).get("Version"), timeout=self.timeout
            )
            running = str(reply.body[0][1])
        except Exception:  # an old shell with no such property: the version stays unknown
            pass
        return (
            f"the running shell (version {running}) does not know '{method}'; "
            f"this client is version {__version__}"
        )


def _emit(options: Options, text: str, data: dict[str, Any]) -> None:
    print(json.dumps(data) if options.json else text)


def _fail(options: Options, failure: Failure) -> int:
    if options.json:
        print(json.dumps({"ok": False, "error": failure.message, "exit": int(failure.code)}))
    else:
        print(f"tesserae-shell: {failure.message}", file=sys.stderr)
    return int(failure.code)


def _answer(options: Options, ok: bool, message: str) -> int:
    """A ``(b ok, s message)`` reply: the message on standard output when it worked, on standard
    error (as ``--json``: one object on standard output) when it did not."""
    if options.json:
        print(json.dumps({"ok": ok, "message": message}))
    elif ok:
        print(message)
    else:
        print(message, file=sys.stderr)
    return int(ExitCode.OK if ok else ExitCode.CONFIG)


def parse_argument(text: str) -> Any:
    """One ``ARG`` of ``call``: a JSON value, or the text itself when it is not valid JSON."""
    try:
        return json.loads(text)
    except ValueError:
        return text


def text_status(status: dict[str, Any]) -> str:
    version = status.get("version", {})
    lines = [
        f"state: {status.get('state')}",
        f"tesserae-shell {version.get('shell')} (tess_re {version.get('tess_re')}, "
        f"python {version.get('python')})",
    ]
    monitors = status.get("monitors", [])
    lines.append(
        "monitors: " + (", ".join(f"{m['name']} ({m['output']})" for m in monitors) or "none")
    )
    surfaces = status.get("surfaces", [])
    lines.append("surfaces:" + ("" if surfaces else " none"))
    for s in surfaces:
        lines.append(
            f"  {s['name']}  {s['kind']}  {'shown' if s['shown'] else 'hidden'}  {s['output']}"
        )
    lines.append("modules: " + (", ".join(status.get("modules", [])) or "none"))
    errors = status.get("errors", [])
    lines.append("last errors:" + ("" if errors else " none"))
    for e in errors:
        lines.append(f"  {e['file']}:{e['line']}: {e['rule']}: {e['message']}")
    return "\n".join(lines)


def run(command: str, args: Any, options: Options) -> int:
    """Run a control command; the exit code."""
    try:
        shell = Shell(options.timeout)
    except Failure as failure:
        return _fail(options, failure)
    try:
        return _run(shell, command, args, options)
    except Failure as failure:
        return _fail(options, failure)
    finally:
        shell.close()


def _run(shell: Shell, command: str, args: Any, options: Options) -> int:
    if command == "reload":
        ok, message = shell.call("Reload")
        return _answer(options, ok, message)
    if command == "quit":
        shell.call("Quit")
        _emit(options, "stopping", {"ok": True, "message": "stopping"})
        return int(ExitCode.OK)
    if command == "status":
        (text,) = shell.call("Status")
        if options.json:
            print(text)
        else:
            print(text_status(json.loads(text)))
        return int(ExitCode.OK)
    if command in ("show", "hide", "toggle"):
        ok, message = shell.call(command.capitalize(), "s", [args.name])
        return _answer(options, ok, message)
    if command == "call":
        values = [parse_argument(a) for a in args.args]
        (result,) = shell.call("Call", "sss", [args.module, args.action, json.dumps(values)])
        if options.json:
            print(json.dumps({"ok": True, "result": json.loads(result)}))
        else:
            print(result)
        return int(ExitCode.OK)
    if command == "log-level":
        shell.call("SetLogLevel", "s", [args.level])
        _emit(options, f"log level {args.level.upper()}", {"ok": True, "message": args.level})
        return int(ExitCode.OK)
    raise Failure(ExitCode.CONFIG, f"unknown command '{command}'")
