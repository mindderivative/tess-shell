"""The shell's side of its KWin script (KWin Integration, Tasks Module > The Window List).

KWin has no D-Bus call that lists windows or reports a fullscreen one, so a small script runs inside
KWin (``src/tess_shell/kwin/TesseraeShell``) and calls two methods of the shell's own interface,
``FullscreenState(s)`` and ``WindowsState(s)``. This module is what answers them and what loads and
unloads the script:

* **Loading** (mode R, ``KWin { Script: RUNTIME }``, the default): once the shell owns its name,
  ``/KWin supportInformation`` is read for the version, then ``/Scripting`` ``isScriptLoaded``,
  ``unloadScript`` (if it is), ``loadScript(path, id)`` and ``start()``; at stop ``unloadScript``.
  Mode P (``PERSISTENT``) loads nothing at start: the script was installed by ``tesserae-shell kwin
  script install`` and KWin runs it from login; the shell only checks that it is loaded. ``OFF``
  does neither. A KWin that is not there (another compositor), a refused load or a silent script
  (nothing within five seconds) switch the features off with one line in the log each; the shell
  keeps running.
* **Answering**: ``FullscreenState`` carries a JSON array of output names (the outputs with an
  ACTIVE fullscreen window); ``WindowsState`` a JSON array of window records, sent only while a
  Tasks module is in use. Each is answered with ``{"windows": true}`` or ``{"windows": false}``:
  that is how the shell turns the window list on and off (a script cannot receive a call). When the
  wanted state changes after the script has been told the other, the script is loaded again, so
  its first call gets the new answer. A malformed string is ignored with one warning that never
  holds its content; a window list nobody asked for is ignored.
* **Acting on a window**: a one-shot script (activate, minimise, close), written to the runtime
  folder from a template with a checked UUID, loaded, started and unloaded a moment later.

Threads. Everything that talks to KWin runs on the ``dbus`` service thread. ``fullscreen_state`` and
``windows_state`` run there too (the control interface calls them); what they accept is handed to
the loop thread with ``call_soon`` (``on_fullscreen``, ``on_windows``, ``on_state``), the window
list coalesced: a burst gives one call.

Safety. ``start``, ``reload`` and the actions refuse to touch a bus that is not private while the
process is a test (``kwin_package.refuse_real_bus``): nothing in a test is ever loaded into the
real KWin.
"""

from __future__ import annotations

import asyncio
import json
import os
import threading
from collections.abc import Callable
from concurrent.futures import Future
from pathlib import Path
from typing import Any

from loguru import logger

from tess_shell.services.api import ServiceError, ServiceUnavailable, WindowInfo
from tess_shell.services.bus import Bus, ServiceThread
from tess_shell.services.kwin_package import (
    ACTIONS,
    PACKAGE_ID,
    action_script,
    installed_main,
    main_script,
    parse_version,
    refuse_real_bus,
    scripts_folder,
)

KWIN = "org.kde.KWin"
KWIN_PATH = "/KWin"
KWIN_INTERFACE = "org.kde.KWin"
SCRIPTING_PATH = "/Scripting"
SCRIPTING_INTERFACE = "org.kde.kwin.Scripting"  # lower case ``kwin`` (libkwin's adaptor name)
MODES = ("RUNTIME", "PERSISTENT", "OFF")
CALL_TIMEOUT = 3.0  # seconds: a call to KWin that takes longer is a KWin that is not answering
SILENT_AFTER = 5.0  # seconds without a report after a load: the script is silent
ACTION_LINGER = 2.0  # seconds a one-shot script stays loaded: KWin reads its file on its own time
MAX_REPORT = 2 * 1024 * 1024  # a report longer than this is refused unread
SHELL_PREFIX = "tesserae-shell."  # the namespace of every surface the shell opens


def parse_fullscreen(raw: str) -> frozenset[str] | None:
    """The output names of a ``FullscreenState`` string, or ``None`` when it is not a JSON array
    of strings."""
    if len(raw) > MAX_REPORT:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
        return None
    return frozenset(data)


def _text(item: dict[str, object], key: str) -> str | None:
    value = item.get(key, "")
    return value if isinstance(value, str) else None


def _flag(item: dict[str, object], key: str) -> bool | None:
    value = item.get(key, False)
    return value if isinstance(value, bool) else None


def parse_windows(raw: str) -> tuple[WindowInfo, ...] | None:
    """The windows of a ``WindowsState`` string, in the script's order, or ``None`` when it is not
    what the script sends (a JSON array of records with an ``id`` each, no id twice). A record
    whose ``app`` starts with ``tesserae-shell.`` is one of the shell's own surfaces: dropped."""
    if len(raw) > MAX_REPORT:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, list):
        return None
    out: list[WindowInfo] = []
    seen: set[str] = set()
    for item in data:
        if not isinstance(item, dict):
            return None
        window_id = item.get("id")
        desktops = item.get("desktops", [])
        fields = (
            _text(item, "title"),
            _text(item, "app"),
            _text(item, "output"),
            _flag(item, "active"),
            _flag(item, "minimized"),
            _flag(item, "attention"),
        )
        if (
            not isinstance(window_id, str)
            or not window_id
            or window_id in seen
            or any(f is None for f in fields)
            or not isinstance(desktops, list)
            or not all(isinstance(d, str) for d in desktops)
        ):
            return None
        seen.add(window_id)
        title, app, output, active, minimized, attention = fields
        assert title is not None and app is not None and output is not None
        if app.startswith(SHELL_PREFIX):
            continue
        out.append(
            WindowInfo(
                window_id,
                title,
                app,
                bool(active),
                bool(minimized),
                tuple(desktops),
                output,
                bool(attention),
            )
        )
    return tuple(out)


class KWinService:
    """One per shell. ``call_soon`` queues a function for the loop thread. ``runtime_dir`` is where
    the one-shot scripts are written (a folder only the user can read: ``$XDG_RUNTIME_DIR/
    tesserae-shell``); ``scripts`` is KWin's scripts folder for mode P (default
    ``$XDG_DATA_HOME/kwin/scripts``)."""

    def __init__(
        self,
        service: ServiceThread,
        call_soon: Callable[[Callable[[], None]], None],
        *,
        mode: str = "RUNTIME",
        hide_on_fullscreen: bool = True,
        runtime_dir: Path | None = None,
        scripts: Path | None = None,
        silent_after: float = SILENT_AFTER,
        action_linger: float = ACTION_LINGER,
    ) -> None:
        self._service = service
        self._call_soon = call_soon
        self.mode = mode
        self.hide_on_fullscreen = hide_on_fullscreen
        self._runtime = runtime_dir
        self._scripts = scripts
        self._silent_after = silent_after
        self._action_linger = action_linger
        # what the loop thread is told (set by the app and the window service)
        self.on_fullscreen: Callable[[frozenset[str]], None] | None = None
        self.on_windows: Callable[[tuple[WindowInfo, ...]], None] | None = None
        self.on_state: Callable[[], None] | None = None
        # state, readable from any thread
        self.state = "stopped"  # stopped, off, not-kwin, failed, loaded
        self.detail = ""  # why, when it is not loaded
        self.version: str | None = None
        self.fullscreen: frozenset[str] = frozenset()
        self.windows_wanted = False
        self.silent = False  # the script was loaded and said nothing within ``silent_after``
        # counters (the tests and the status line)
        self.loads = 0  # scripts loaded (the shell's script, not the one-shot ones)
        self.fullscreen_reports = 0
        self.window_reports = 0
        self.actions_run = 0
        self._told: bool | None = None  # what the script was last answered since a load
        self._lock = threading.Lock()  # the pending window list
        self._pending: tuple[WindowInfo, ...] | None = None
        self._flush_posted = False
        self._warned: set[str] = set()
        self._loading: asyncio.Lock | None = None
        self._timers: list[asyncio.TimerHandle] = []
        self._actions: dict[str, tuple[Path, asyncio.TimerHandle]] = {}
        self._action_count = 0
        self._generation = 0  # counts loads, so a timer of an older one is ignored
        self._window_deadline: asyncio.TimerHandle | None = None

    # -- the state ------------------------------------------------------------------------------

    def _set_state(self, state: str, detail: str = "") -> None:
        if (state, detail) == (self.state, self.detail):
            return
        self.state, self.detail = state, detail
        sink = self.on_state
        if sink is not None:
            self._call_soon(sink)

    @property
    def loaded(self) -> bool:
        return self.state == "loaded"

    @property
    def available(self) -> bool:
        """The script is loaded and not silent: the window list can be had."""
        return self.state == "loaded" and not self.silent

    def _warn_once(self, key: str, message: str) -> None:
        if key not in self._warned:
            self._warned.add(key)
            logger.warning(message)

    # -- the loading (service thread) -----------------------------------------------------------

    @property
    def _bus(self) -> Bus:
        return self._service.session

    def _guard(self) -> None:
        address = self._bus.address or os.environ.get("DBUS_SESSION_BUS_ADDRESS")
        refuse_real_bus(address)

    async def _scripting(
        self, member: str, signature: str = "", body: list[object] | None = None
    ) -> Any:
        reply = await self._bus.call(
            KWIN,
            SCRIPTING_PATH,
            SCRIPTING_INTERFACE,
            member,
            signature,
            body or [],
            timeout=CALL_TIMEOUT,
        )
        return reply[0] if reply else None

    def _script_path(self) -> Path | None:
        if self.mode == "PERSISTENT":
            installed = installed_main(self._scripts or scripts_folder())
            return installed if installed.is_file() else None
        return main_script()

    async def start(self) -> None:
        """Check KWin and load the script (see the module's docstring). Never raises for a KWin
        that is not there or does not answer: the state says so."""
        if self.mode == "OFF":
            self._set_state("off", "KWin { Script: OFF }")
            logger.info("kwin: the script is off (KWin { Script: OFF })")
            return
        self._guard()
        self._loading = asyncio.Lock()
        try:
            reply = await self._bus.call(
                KWIN, KWIN_PATH, KWIN_INTERFACE, "supportInformation", timeout=CALL_TIMEOUT
            )
        except ServiceUnavailable as exc:
            self._set_state("not-kwin", f"{KWIN} is not on the session bus")
            logger.info(
                f"kwin: {KWIN} is not on the session bus ({exc.detail}): another compositor? "
                "fullscreen hiding and the window list are off"
            )
            return
        except ServiceError as exc:
            if exc.name.endswith(("UnknownMethod", "UnknownObject", "UnknownInterface")):
                # a name that is org.kde.KWin but has no /KWin to ask: not a KWin we can script
                self._set_state("not-kwin", f"{KWIN} has no supportInformation")
                logger.info(f"kwin: {KWIN} does not answer supportInformation ({exc.detail}): off")
                return
            self._set_state("failed", f"KWin did not answer ({exc.detail})")
            logger.warning(
                f"kwin: KWin did not answer supportInformation ({exc.detail}): no script"
            )
            return
        self.version = parse_version(str(reply[0]) if reply else "")
        logger.info(f"kwin: KWin {self.version or 'version unknown'}")
        async with self._loading:
            await self._load()

    async def _load(self) -> None:
        path = self._script_path()
        try:
            loaded = bool(await self._scripting("isScriptLoaded", "s", [PACKAGE_ID]))
            if self.mode == "PERSISTENT":
                if not loaded:
                    self._not_loaded("the script is not installed in KWin")
                    return
            else:
                if loaded:
                    await self._scripting("unloadScript", "s", [PACKAGE_ID])
                if path is None or not path.is_file():
                    self._not_loaded(f"the script file is missing ({path})")
                    return
                number = await self._scripting("loadScript", "ss", [str(path), PACKAGE_ID])
                if not isinstance(number, int) or number < 0:
                    self._not_loaded(f"KWin refused to load {path.name} (answered {number!r})")
                    return
                await self._scripting("start")
        except ServiceError as exc:
            self._not_loaded(f"the call to KWin failed ({exc.detail})")
            return
        self.loads += 1
        self._generation += 1
        self._told = None
        self.silent = False
        self._set_state("loaded")
        logger.info(f"kwin: the script {PACKAGE_ID} is loaded ({self.mode.lower()} mode)")
        self._arm_silence()

    def _not_loaded(self, why: str) -> None:
        self._set_state("failed", why)
        logger.warning(f"kwin: {why}: fullscreen hiding and the window list are off")

    async def stop(self) -> None:
        """Unload the script (mode R), the one-shot scripts that are still loaded, and cancel the
        timers."""
        self._cancel_timers()
        for name, (path, handle) in list(self._actions.items()):
            handle.cancel()
            await self._unload_action(name, path)
        self._actions.clear()
        if self.state == "loaded" and self.mode == "RUNTIME":
            try:
                await self._scripting("unloadScript", "s", [PACKAGE_ID])
            except ServiceError as exc:
                logger.debug(f"kwin: unloading the script did not go through ({exc})")
        self._set_state("stopped")

    # -- the silence check ----------------------------------------------------------------------

    def _cancel_timers(self) -> None:
        for timer in self._timers:
            timer.cancel()
        self._timers.clear()
        if self._window_deadline is not None:
            self._window_deadline.cancel()
            self._window_deadline = None

    def _arm_silence(self) -> None:
        self._cancel_timers()
        generation = self._generation
        loop = asyncio.get_running_loop()
        self._timers.append(loop.call_later(self._silent_after, self._check_silent, generation))

    def _check_silent(self, generation: int) -> None:
        if generation != self._generation or self.fullscreen_reports:
            return
        self._warn_once(
            f"silent:{generation}",
            f"kwin: the script is loaded but sent nothing within {self._silent_after:g} s "
            "(KWin's journal has its errors): fullscreen hiding and the window list are off",
        )
        self.silent = True  # after the line: whoever sees the flag finds the warning logged
        if self.on_state is not None:
            self._call_soon(self.on_state)

    def _check_windows_silent(self, generation: int) -> None:
        if generation != self._generation or self.window_reports or not self.windows_wanted:
            return
        self._warn_once(
            f"silent-windows:{generation}",
            f"kwin: the window list was asked for and the script sent none within "
            f"{self._silent_after:g} s: the Tasks module stays empty",
        )
        self.silent = True
        if self.on_state is not None:
            self._call_soon(self.on_state)

    # -- what the script sends (called on the service thread by the control interface) ----------

    def reply(self) -> str:
        """The answer to either call: whether the script is to send the window list."""
        wanted = self.windows_wanted
        self._told = wanted
        return json.dumps({"windows": wanted})

    def fullscreen_state(self, raw: str) -> str:
        """``FullscreenState(s outputs)``: the outputs that have an active fullscreen window."""
        outputs = parse_fullscreen(raw)
        if outputs is None:
            self._warn_once(
                "fullscreen-malformed",
                "kwin: a FullscreenState that is not a JSON array of output names was ignored",
            )
            return self.reply()
        self._warned.discard("fullscreen-malformed")
        self.fullscreen_reports += 1
        if self.silent and self.state == "loaded":
            self.silent = False  # it spoke after all
            if self.on_state is not None:
                self._call_soon(self.on_state)
        if outputs != self.fullscreen:
            self.fullscreen = outputs
            sink = self.on_fullscreen
            if self.hide_on_fullscreen and sink is not None:
                self._call_soon(lambda: sink(outputs))
        answer = self.reply()
        if self.windows_wanted and self._window_deadline is None and self.window_reports == 0:
            loop = asyncio.get_running_loop()
            self._window_deadline = loop.call_later(
                self._silent_after, self._check_windows_silent, self._generation
            )
        return answer

    def windows_state(self, raw: str) -> str:
        """``WindowsState(s windows)``: the open windows. Ignored (with no title read or logged)
        when no Tasks module asked for them."""
        if not self.windows_wanted:
            logger.debug("kwin: a window list nobody asked for was ignored")
            return self.reply()
        windows = parse_windows(raw)
        if windows is None:
            self._warn_once(
                "windows-malformed",
                "kwin: a WindowsState that is not a list of window records was ignored; the last "
                "list stays",
            )
            return self.reply()
        self._warned.discard("windows-malformed")
        self.window_reports += 1
        if self._window_deadline is not None:
            self._window_deadline.cancel()
            self._window_deadline = None
        if self.silent:
            self.silent = False
            if self.on_state is not None:
                self._call_soon(self.on_state)
        with self._lock:
            self._pending = windows
            if self._flush_posted:
                return self.reply()  # the loop will take the newest list
            self._flush_posted = True
        self._call_soon(self._flush)
        return self.reply()

    def _flush(self) -> None:
        """Loop thread: hand over the newest window list (a burst of reports is one call)."""
        with self._lock:
            windows, self._pending = self._pending, None
            self._flush_posted = False
        sink = self.on_windows
        if windows is not None and sink is not None:
            sink(windows)

    # -- the window list on and off (any thread) ------------------------------------------------

    def set_windows_wanted(self, wanted: bool) -> None:
        """A Tasks module is (not) in use. The script is told in its next answer; when it was told
        the other since its load, or the list was turned off and on again before the script
        noticed (it would not send a list it has no news of), it is loaded again so that the
        answer, and a fresh list, come at once."""
        if wanted == self.windows_wanted:
            return
        self.windows_wanted = wanted
        self.window_reports = 0  # a list from before is no list
        self._service.post(
            lambda: asyncio.ensure_future(self._wanted_changed()).add_done_callback(self._done)
        )

    @staticmethod
    def _done(task: asyncio.Future[None]) -> None:
        if not task.cancelled() and task.exception() is not None:
            logger.opt(exception=task.exception()).error("kwin: a task failed")

    async def _wanted_changed(self) -> None:
        if self.state != "loaded" or self._told is None:
            return  # not loaded, or the script has not called yet: its first answer will say
        if self._told != self.windows_wanted or (self.windows_wanted and not self.window_reports):
            await self.reload()

    async def reload(self) -> None:
        """Unload and load the script again (a fresh load sends the current state at once)."""
        self._guard()
        if self._loading is None:
            return
        async with self._loading:
            self.window_reports = 0
            self.fullscreen_reports = 0
            await self._load()

    # -- acting on a window ---------------------------------------------------------------------

    def act(self, kind: str, window_id: str) -> Future[bool]:
        """Any thread, never blocks: run the one-shot script ``kind`` (``activate``, ``minimize``
        or ``close``) on the window ``window_id``. The future is whether KWin loaded it."""
        return self._service.submit(self.run_action(kind, window_id))

    def _runtime_dir(self) -> Path:
        if self._runtime is not None:
            return self._runtime
        base = os.environ.get("XDG_RUNTIME_DIR")
        return (
            Path(base) / "tesserae-shell"
            if base
            else Path("/tmp") / f"tesserae-shell-{os.getuid()}"
        )

    async def run_action(self, kind: str, window_id: str) -> bool:
        if kind not in ACTIONS:
            raise ValueError(f"no such window action: {kind!r}")
        self._guard()
        if self.state != "loaded":
            self._warn_once(
                "action-no-script", f"kwin: {kind}: the script is not loaded; nothing done"
            )
            return False
        try:
            text = action_script(kind, window_id)
        except ValueError:
            self._warn_once(
                "action-bad-id", f"kwin: {kind}: the window id is not a UUID; nothing done"
            )
            return False
        self._action_count += 1
        name = f"{PACKAGE_ID}-{kind}-{self._action_count}"
        folder = self._runtime_dir()
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = folder / f"{kind}-{self._action_count}.js"
        path.write_text(text, encoding="utf-8")
        path.chmod(0o600)
        try:
            number = await self._scripting("loadScript", "ss", [str(path), name])
            if not isinstance(number, int) or number < 0:
                raise ServiceError(KWIN, f"loadScript answered {number!r}")
            await self._scripting("start")
        except ServiceError as exc:
            path.unlink(missing_ok=True)
            self._warn_once(
                f"action-failed:{kind}", f"kwin: the {kind} script did not load ({exc.detail})"
            )
            return False
        self.actions_run += 1
        loop = asyncio.get_running_loop()
        handle = loop.call_later(
            self._action_linger,
            lambda: asyncio.ensure_future(self._finish_action(name)).add_done_callback(self._done),
        )
        self._actions[name] = (path, handle)
        return True

    async def _finish_action(self, name: str) -> None:
        entry = self._actions.pop(name, None)
        if entry is not None:
            await self._unload_action(name, entry[0])

    async def _unload_action(self, name: str, path: Path) -> None:
        try:
            await self._scripting("unloadScript", "s", [name])
        except ServiceError as exc:
            logger.debug(f"kwin: unloading {name} did not go through ({exc.detail})")
        path.unlink(missing_ok=True)
