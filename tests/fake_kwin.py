"""A fake KWin and a fake KWin script on a private bus (KWin Integration, Tasks Module).

NEVER the real KWin: the fake owns ``org.kde.KWin`` on a private ``dbus-daemon`` (``tests/
fake_dbus.py``) and offers what the shell calls:

* ``/KWin`` ``org.kde.KWin.supportInformation() -> s`` (a text with ``KWin version: <version>``);
* ``/Scripting`` ``org.kde.kwin.Scripting``: ``loadScript(ss) -> i``, ``unloadScript(s) -> b``,
  ``isScriptLoaded(s) -> b`` and ``start()``.

``FakeScript`` stands in for the script the shell loads: started by ``start()`` once the shell's
own script (the package's ``main.js``, recognised by its id) is loaded, it calls the shell's
``FullscreenState`` and ``WindowsState`` through a connection of its own, the way ``callDBus`` does,
reads the JSON answer, and turns the window list on and off by it, exactly as ``main.js`` does (that
logic is also run for real, under Node, by ``tests/test_kwin_script_js.py``). A one-shot script
(``activate``, ``minimize``, ``close``) is only recorded: its id, its path and the text KWin would
have read.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dbus_fast import Message, MessageType
from dbus_fast.aio import MessageBus

from tess_shell.services.control import INTERFACE, NAME, PATH
from tess_shell.services.kwin import KWIN, KWIN_INTERFACE, SCRIPTING_INTERFACE
from tess_shell.services.kwin_package import PACKAGE_ID
from tests.fake_dbus import FakeBus, FakeService, wait_for

SUPPORT = """Version
=======
KWin version: {version}
Qt Version: 6.11.0
Operating System: Arch Linux
"""


@dataclass
class Loaded:
    """One script KWin has loaded: its name, its path and, for a one-shot script, its text."""

    name: str
    path: str
    text: str
    started: bool = False


class FakeScript:
    """The shell's KWin script, as ``main.js`` behaves: on a load it reports the fullscreen state;
    each answer ``{"windows": true|false}`` turns the window list on or off."""

    def __init__(self, bus: FakeBus) -> None:
        self._bus = bus
        self._conn: MessageBus | None = None
        self._lock: asyncio.Lock | None = None
        self._reports: asyncio.Lock | None = None
        self.fullscreen: list[str] = []  # the outputs with an active fullscreen window
        self.windows: list[dict[str, Any]] = []  # what the window list holds
        self.sends_windows = False
        self.silent = False  # a script that throws inside KWin: it never calls
        self.running = False
        self.calls: list[tuple[str, str]] = []  # (method, payload) the shell was sent
        self.replies: list[str | None] = []  # what the shell answered
        self.errors: list[str] = []  # D-Bus errors the shell answered with

    # -- the connection (on the fake thread) -----------------------------------------------------

    async def _connection(self) -> MessageBus:
        # one connection, made once: two calls that begin together (the script's first report and
        # an event sent right after the start) would each connect, send on their own connection,
        # and the shell could take them in the other order (a stale state last)
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            if self._conn is None or not self._conn.connected:
                self._conn = await MessageBus(bus_address=self._bus.address).connect()
            return self._conn

    async def call(
        self, method: str, payload: str, signature: str = "s", interface: str = INTERFACE
    ) -> str | None:
        """A call to the shell the way ``callDBus`` makes it; its answer, or ``None`` when there is
        none (no shell, an error: ``main.js`` ignores both)."""
        self.calls.append((method, payload))
        conn = await self._connection()
        body: list[Any] = [payload]
        if signature == "as":
            body = [[payload]]
        reply = await conn.call(
            Message(
                destination=NAME,
                path=PATH,
                interface=interface,
                member=method,
                signature=signature,
                body=body,
            )
        )
        if reply is None or reply.message_type != MessageType.METHOD_RETURN:
            self.errors.append(reply.error_name if reply is not None and reply.error_name else "?")
            self.replies.append(None)
            return None
        answer = str(reply.body[0]) if reply.body else None
        self.replies.append(answer)
        return answer

    # -- what the script does --------------------------------------------------------------------

    async def run(self) -> None:
        """The script was started: report the state now (a fresh load)."""
        self.running, self.sends_windows = True, False
        if self.silent:
            return
        await self.report_fullscreen()

    # Reports go one at a time and read the state when it is their turn, so that of two that begin
    # together (the first one of a load and one sent by an event right after it) the one that
    # reaches the shell last carries the latest state, as KWin's script does: it has one thread.
    async def report_fullscreen(self) -> None:
        async with self._report_lock():
            if not self.running or self.silent:
                return
            self._answered(await self.call("FullscreenState", json.dumps(self.fullscreen)))

    async def report_windows(self) -> None:
        async with self._report_lock():
            if not self.running or self.silent or not self.sends_windows:
                return
            self._answered(await self.call("WindowsState", json.dumps(self.windows)))

    def _report_lock(self) -> asyncio.Lock:
        if self._reports is None:
            self._reports = asyncio.Lock()
        return self._reports

    def _answered(self, answer: str | None) -> None:
        """The callback of ``callDBus``: read ``{"windows": ...}``; anything else is ignored."""
        try:
            wanted = json.loads(answer or "")["windows"] is True
        except ValueError, KeyError, TypeError:
            return
        if wanted != self.sends_windows:
            self.sends_windows = wanted
            if wanted:
                asyncio.ensure_future(self.report_windows())

    def stop(self) -> None:
        self.running = False

    async def close(self) -> None:
        self.running = False
        if self._conn is not None:
            self._conn.disconnect()
            self._conn = None


class FakeKWin:
    """``org.kde.KWin`` with ``/KWin`` and ``/Scripting`` on ``bus`` (not up until ``up()``)."""

    def __init__(self, bus: FakeBus, version: str = "6.8.2", refuse_load: bool = False) -> None:
        self.bus = bus
        self.version = version
        self.refuse_load = refuse_load  # loadScript answers -1, as KWin does for a bad file
        self.fail_calls = False  # every /Scripting call raises a D-Bus error
        self.calls: list[tuple[str, tuple[Any, ...]]] = []  # every call, in order
        self.scripts: dict[str, Loaded] = {}  # what is loaded now, by name
        self.history: list[Loaded] = []  # everything that was ever loaded
        self.script = FakeScript(bus)
        self._next = 0
        self.service: FakeService = bus.service(KWIN)
        self.service.add(
            "/KWin",
            KWIN_INTERFACE,
            methods={
                "supportInformation": ([], "s", self._support),
                "reconfigure": ([], "", self._reconfigure),
            },
        )
        self.service.add(
            "/Scripting",
            SCRIPTING_INTERFACE,
            methods={
                "loadScript": (["s", "s"], "i", self._load),
                "unloadScript": (["s"], "b", self._unload),
                "isScriptLoaded": (["s"], "b", self._is_loaded),
                "start": ([], "", self._start),
            },
        )

    # -- the methods (fake thread) ---------------------------------------------------------------

    def _support(self) -> str:
        self.calls.append(("supportInformation", ()))
        return SUPPORT.format(version=self.version)

    def _reconfigure(self) -> None:
        self.calls.append(("reconfigure", ()))

    def _check(self, member: str, args: tuple[Any, ...]) -> None:
        self.calls.append((member, args))
        if self.fail_calls:
            from dbus_fast import DBusError

            raise DBusError("org.kde.kwin.Scripting.FileError", "the fake refuses")

    def _load(self, path: str, name: str) -> int:
        self._check("loadScript", (path, name))
        if self.refuse_load:
            return -1
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError:
            return -1
        loaded = Loaded(name, path, text)
        self.scripts[name] = loaded
        self.history.append(loaded)
        self._next += 1
        return self._next

    def _unload(self, name: str) -> bool:
        self._check("unloadScript", (name,))
        loaded = self.scripts.pop(name, None)
        if loaded is None:
            return False
        if name == PACKAGE_ID:
            self.script.stop()
        return True

    def _is_loaded(self, name: str) -> bool:
        self._check("isScriptLoaded", (name,))
        return name in self.scripts

    def _start(self) -> None:
        self._check("start", ())
        for loaded in self.scripts.values():
            if loaded.started:
                continue
            loaded.started = True
            if loaded.name == PACKAGE_ID:
                asyncio.ensure_future(self.script.run())

    # -- for the test ----------------------------------------------------------------------------

    def up(self) -> None:
        self.service.up()

    def down(self) -> None:
        self.service.down()

    def names(self, member: str) -> list[tuple[Any, ...]]:
        return [args for m, args in list(self.calls) if m == member]

    def order(self) -> list[str]:
        return [m for m, _ in list(self.calls)]

    def loaded(self, name: str = PACKAGE_ID) -> bool:
        return name in self.scripts

    def one_shots(self) -> list[Loaded]:
        return [h for h in self.history if h.name != PACKAGE_ID]

    # -- the script's side, from the test thread --------------------------------------------------

    def set_fullscreen(self, outputs: Sequence[str]) -> None:
        """An active fullscreen window appeared or left: the script reports."""
        self.script.fullscreen = list(outputs)
        self.bus.thread.run(self.script.report_fullscreen())

    def set_windows(self, windows: Sequence[dict[str, Any]]) -> None:
        """The window list changed: the script reports it, if it was asked to."""
        self.script.windows = [dict(w) for w in windows]
        self.bus.thread.run(self.script.report_windows())

    def raw(self, method: str, payload: str, signature: str = "s") -> str | None:
        """Any call to the shell's interface, as a script could make it."""
        return self.bus.thread.run(self.script.call(method, payload, signature))

    def wait_until(self, predicate: Any, timeout: float = 5.0) -> bool:
        return wait_for(predicate, timeout)

    def close(self) -> None:
        try:
            self.bus.thread.run(self.script.close())
        except Exception:
            pass


def window(
    window_id: str,
    title: str = "A window",
    app: str = "org.example.app",
    *,
    active: bool = False,
    minimized: bool = False,
    desktops: Sequence[str] = (),
    output: str = "DP-1",
    attention: bool = False,
) -> dict[str, Any]:
    """One record of the script's window list."""
    return {
        "id": window_id,
        "title": title,
        "app": app,
        "active": active,
        "minimized": minimized,
        "desktops": list(desktops),
        "output": output,
        "attention": attention,
    }


def uuid(n: int) -> str:
    """A window id that is a UUID (the only kind an action script accepts)."""
    return f"{n:08x}-0000-4000-8000-{n:012x}"
