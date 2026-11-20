"""What a module process sees of the shell's services: objects with the methods of the ports and
helpers of ``tess_shell.services.api`` and ``tess_shell.modules.context``, each call a message to
the shell, which keeps every connection and all state (B2 for every service: the shell's own
``Layer``, ``AudioService``, ``TrayService``, window list, application index and icon registry).

The module's own code is unchanged: the child builds the real ``ModuleContext`` with these ports.

Three kinds of call, named for what the calling thread does:

* ``cmd``: the shell is told and nothing comes back (a popup to open, a subscription);
* ``rpc``: the thread waits for the answer, at most :data:`SHELL_CALL_TIMEOUT` seconds, then
  :class:`ShellCallTimeout` (a ``RuntimeError`` that names the module and the call): the members of
  the context whose contract says they answer at once on the loop thread, which across a pipe cost a
  round trip (``update_popup``, ``is_popup_open``, ``focus``, ``surface.hide``, ``apps.search``,
  ``icons.*`` ...);
* a future or a coroutine: ``windows.activate`` and ``audio.set_volume`` return a future completed
  by the shell's answer, ``Proxy.get`` and ``Proxy.call`` are awaited on the process's service
  thread.

A callback the shell pushes (``cb``) runs on the module's loop thread, or on the service thread for
the ones the contract runs on the D-Bus thread. Standard library, the ports' protocols and the
service errors only: no ``dbus_fast``, no engine.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import queue
import threading
from collections.abc import Callable, Coroutine, Mapping, Sequence
from typing import Any

from loguru import logger

from tess_shell.modproc.wire import Channel
from tess_shell.services.api import (
    AppInfo,
    AudioError,
    AudioState,
    BlockingCallError,
    LaunchResult,
    Output,
    ServiceError,
    ServiceState,
    ServiceTimeout,
    ServiceUnavailable,
    ShellCallTimeout,
    WindowInfo,
)


def _scale() -> float:
    """``TESS_SHELL_TEST_WATCHDOG_SCALE``, the watchdog's test setting, scales the wait too."""
    try:
        factor = float(os.environ.get("TESS_SHELL_TEST_WATCHDOG_SCALE", ""))
    except ValueError:
        return 1.0
    return factor if factor > 0 else 1.0


SHELL_CALL_TIMEOUT = 2.0 * _scale()  # seconds a synchronous member waits (below the 5 s hang)
AWAIT_SLACK = 2.0  # seconds a coroutine waits beyond the timeout the call itself has


class Loop:
    """What the shell's loop thread is to a module: one thread (the process's main thread) runs
    what was queued, in order, one callable at a time."""

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
    """The service thread: an asyncio loop for the coroutines a module hands to ``Bus.run`` and for
    the callbacks the shell pushes that the contract runs on the D-Bus thread."""

    def __init__(self) -> None:
        self.loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, name="module-service", daemon=True)
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


def raise_remote(err: Mapping[str, Any]) -> None:
    """Raise what the shell's side raised, as the class the module expects."""
    kind = err.get("type", "RuntimeError")
    args = err.get("args", [])
    classes: dict[str, type[ServiceError]] = {
        "ServiceError": ServiceError,
        "ServiceTimeout": ServiceTimeout,
        "ServiceUnavailable": ServiceUnavailable,
    }
    if kind in classes and len(args) == 3:
        raise classes[kind](*args)
    if kind == "AudioError":
        raise AudioError(err.get("msg", ""))
    if kind == "ValueError":
        raise ValueError(err.get("msg", ""))
    raise RuntimeError(f"{kind}: {err.get('msg', '')}")


class Link:
    """The module process's end of the pipe, for the proxies: calls, answers and the callbacks the
    shell can call by id. ``name`` is the module (it goes into every timeout message)."""

    def __init__(self, name: str, channel: Channel, loop: Loop) -> None:
        self.name = name
        self.channel = channel
        self.loop = loop
        self.state: dict[str, Any] = {"dbus_available": False}  # what the shell pushes
        self._ids = 0
        self._lock = threading.Lock()
        self._pending: dict[int, Callable[[bool, Any], None]] = {}
        self._callbacks: dict[
            int, tuple[Callable[..., Any], str, Callable[..., tuple[Any, ...]] | None]
        ] = {}
        self._aio: AioThread | None = None
        self.run_callback: Callable[..., None] | None = None  # the context's, once it exists

    def next_id(self) -> int:
        with self._lock:
            self._ids += 1
            return self._ids

    def cmd(self, method: str, *args: Any) -> None:
        """A call that wants no answer."""
        self.channel.send({"t": "cmd", "m": method, "a": args})

    def _ask(self, method: str, args: tuple[Any, ...], done: Callable[[bool, Any], None]) -> int:
        rid = self.next_id()
        self._pending[rid] = done
        if not self.channel.send({"t": "rpc", "id": rid, "m": method, "a": args}):
            self._pending.pop(rid, None)
            raise RuntimeError(f"module {self.name}: the shell is gone ({method})")
        return rid

    def rpc(self, method: str, *args: Any, timeout: float = SHELL_CALL_TIMEOUT) -> Any:
        """A call that waits for the shell's answer (a thread of the module, never the reader)."""
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()

        def done(ok: bool, value: Any) -> None:
            if ok:
                future.set_result(value)
                return
            try:
                raise_remote(value)
            except Exception as exc:
                future.set_exception(exc)

        rid = self._ask(method, args, done)
        try:
            return future.result(timeout)
        except concurrent.futures.TimeoutError:
            self._pending.pop(rid, None)
            raise ShellCallTimeout(
                f"module {self.name}: the shell did not answer {method} within {timeout:g} s"
            ) from None

    def call_future(self, method: str, *args: Any) -> concurrent.futures.Future[Any]:
        """A call whose answer completes a future (set from the reader thread)."""
        future: concurrent.futures.Future[Any] = concurrent.futures.Future()

        def done(ok: bool, value: Any) -> None:
            if ok:
                future.set_result(value)
                return
            try:
                raise_remote(value)
            except Exception as exc:
                future.set_exception(exc)

        self._ask(method, args, done)
        return future

    async def arpc(self, method: str, *args: Any, wait: float = 7.0) -> Any:
        """A call awaited on the service thread; ``wait`` is how long the shell may take."""
        loop = asyncio.get_running_loop()
        future: asyncio.Future[Any] = loop.create_future()

        def settle(ok: bool, value: Any) -> None:
            if future.done():
                return
            if ok:
                future.set_result(value)
                return
            try:
                raise_remote(value)
            except Exception as exc:
                future.set_exception(exc)

        def done(ok: bool, value: Any) -> None:
            loop.call_soon_threadsafe(settle, ok, value)

        rid = self._ask(method, args, done)
        try:
            return await asyncio.wait_for(future, wait)
        except TimeoutError:
            self._pending.pop(rid, None)
            raise ShellCallTimeout(
                f"module {self.name}: the shell did not answer {method} within {wait:g} s"
            ) from None

    def answer(self, msg: Mapping[str, Any]) -> None:
        """A ``re`` from the shell (reader thread)."""
        done = self._pending.pop(msg["id"], None)
        if done is not None:
            ok = bool(msg.get("ok"))
            done(ok, msg.get("v") if ok else msg.get("err", {}))

    def register(
        self,
        fn: Callable[..., Any],
        mode: str = "main",
        pre: Callable[..., tuple[Any, ...]] | None = None,
    ) -> int:
        """A callback the shell can call by id. ``mode`` is ``main`` (the module's loop, recorded
        as a callback), ``aio`` (the service thread) or ``raw`` (the loop, not recorded)."""
        sid = self.next_id()
        self._callbacks[sid] = (fn, mode, pre)
        return sid

    def unregister(self, sid: int) -> None:
        self._callbacks.pop(sid, None)

    def aio(self) -> AioThread:
        if self._aio is None:
            self._aio = AioThread()
        return self._aio

    def stop_aio(self) -> None:
        if self._aio is not None:
            self._aio.stop()

    def dispatch(self, msg: Mapping[str, Any]) -> None:
        """A ``cb`` from the shell (reader thread): run the callback on the thread its mode says."""
        entry = self._callbacks.get(msg["id"])
        if entry is None:
            return
        fn, mode, pre = entry
        args = tuple(msg.get("a", ()))

        def run() -> None:
            try:
                call_args = pre(*args) if pre is not None else args
                if mode == "main" and self.run_callback is not None:
                    self.run_callback(fn, *call_args)
                else:
                    fn(*call_args)
            except Exception:
                logger.opt(exception=True).error("a callback from the shell raised")

        if mode == "aio":
            self.aio().post(run)
        else:
            self.loop.put(run)


class Sub:
    """A ``Subscription``: cancelling tells the shell and forgets the callback."""

    def __init__(self, link: Link, *sids: int) -> None:
        self._link = link
        self._sids = sids

    def cancel(self) -> None:
        for sid in self._sids:
            self._link.unregister(sid)
            self._link.cmd("unsub", sid)


# -- ticks ------------------------------------------------------------------------------------


class RemoteTicks:
    """The shell's one time source, for ``ctx.on_tick``: the shell sends a message each tick, so all
    subscribers still tick together and the process has no timer thread of its own."""

    def __init__(self, link: Link) -> None:
        self._link = link

    def subscribe(self, unit: str, fn: Callable[[], None]) -> Sub:
        if unit not in ("second", "minute"):
            raise ValueError(f"a tick unit is 'second' or 'minute', not {unit!r}")
        sid = self._link.register(fn, "raw")
        self._link.cmd("tick.sub", sid, unit)
        return Sub(self._link, sid)


# -- popups, surfaces, focus, applications -----------------------------------------------------


class ProxyPopups:
    """``PopupPort``."""

    def __init__(self, link: Link) -> None:
        self._c = link

    def call(
        self,
        module: str,
        use: str | None,
        name: str,
        data: Mapping[str, Any] | None,
        anchor: tuple[float, float, float, float] | None = None,
    ) -> None:
        self._c.cmd("popup.call", use, name, data, list(anchor) if anchor else None)

    def close_named(self, name: str | None = None) -> None:
        self._c.cmd("popup.close", name)

    def update_data(self, name: str, data: Mapping[str, Any]) -> bool:
        return bool(self._c.rpc("popup.update", name, data))

    def is_open(self, name: str) -> bool:
        return bool(self._c.rpc("popup.is_open", name))


class ProxyFocusPort:
    """``FocusPort``."""

    def __init__(self, link: Link) -> None:
        self._c = link

    def get_default(self) -> str | None:
        got = self._c.rpc("focus.get_default")
        return None if got is None else str(got)

    def set_default(self, name: str | None, who: str = "") -> None:
        self._c.cmd("focus.set_default", name, who)

    def set_mode(self, name: str, value: bool, who: str = "") -> bool:
        return bool(self._c.rpc("focus.set_mode", name, value, who))


class ProxySurfacePort:
    """``SurfacePort``."""

    def __init__(self, link: Link) -> None:
        self._c = link

    def hide_use(self, use_key: str) -> bool:
        return bool(self._c.rpc("surface.hide", use_key))

    def show_use(self, use_key: str, hide_after: float | None = None) -> bool:
        return bool(self._c.rpc("surface.show", use_key, hide_after))

    def focus_block(self, use_key: str, name: str, select_all: bool = False) -> bool:
        return bool(self._c.rpc("surface.focus", use_key, name, select_all))

    def watch_shown(self, callback: Callable[[tuple[str, ...]], None]) -> Sub:
        sid = self._c.register(callback, "raw", lambda keys: (tuple(keys),))
        self._c.cmd("surface.watch_shown", sid)
        return Sub(self._c, sid)

    def request_token(self, use_key: str, callback: Callable[[str | None], None]) -> None:
        sid = 0

        def once(token: str | None) -> None:
            self._c.unregister(sid)
            callback(token)

        sid = self._c.register(once, "raw")
        self._c.cmd("surface.token", use_key, sid)

    def announce(self, use_keys: Sequence[str], text: str, politeness: str) -> bool:
        self._c.cmd("surface.announce", list(use_keys), text, politeness)
        return True


def _app(d: Mapping[str, Any] | None) -> AppInfo | None:
    return None if d is None else AppInfo(**{**d, "keywords": tuple(d["keywords"])})


class ProxyAppsPort:
    """``AppsPort``: the index stays in the shell."""

    def __init__(self, link: Link) -> None:
        self._c = link

    @property
    def ready(self) -> bool:
        return bool(self._c.rpc("apps.ready"))

    @property
    def watching(self) -> bool:
        return bool(self._c.rpc("apps.watching"))

    def start(self) -> None:
        self._c.cmd("apps.start")

    def search(self, query: str, limit: int = 8) -> list[AppInfo]:
        found = self._c.rpc("apps.search", query, limit)
        return [a for a in (_app(d) for d in found) if a is not None]

    def get(self, entry_id: str) -> AppInfo | None:
        return _app(self._c.rpc("apps.get", entry_id))

    def launch(
        self,
        entry_id: str,
        token: str | None = None,
        on_done: Callable[[LaunchResult], None] | None = None,
    ) -> None:
        sid = 0
        if on_done is not None:
            done = on_done

            def finished(result: Mapping[str, Any]) -> None:
                self._c.unregister(sid)
                done(LaunchResult(**result))

            sid = self._c.register(finished, "raw")
        self._c.cmd("apps.launch", entry_id, token, sid)

    def on_changed(self, callback: Callable[[], None]) -> Sub:
        sid = self._c.register(callback, "raw")
        self._c.cmd("apps.on_changed", sid)
        return Sub(self._c, sid)

    def refresh(self) -> None:
        self._c.cmd("apps.refresh")


# -- icons -----------------------------------------------------------------------------------


class ProxyIconsPort:
    def __init__(self, link: Link) -> None:
        self._c = link

    def for_module(self, module: str) -> ProxyIcons:
        return ProxyIcons(self._c)


class ProxyIcons:
    """``ModuleIcons``: the registry of decoded pixels is the engine's, so the lookups stay in the
    shell and only the references (text) come back."""

    def __init__(self, link: Link) -> None:
        self._c = link

    def theme_icon(self, name: str, size: int, theme_path: str | None = None) -> str | None:
        got = self._c.rpc("icons.theme_icon", name, size, theme_path)
        return None if got is None else str(got)

    def pixmap_icon(
        self, pixmaps: Sequence[Sequence[Any]], size: int, source: str = ""
    ) -> str | None:
        got = self._c.rpc("icons.pixmap_icon", [list(p) for p in pixmaps], size, source)
        return None if got is None else str(got)

    def png_icon(self, data: bytes, source: str = "") -> str | None:
        got = self._c.rpc("icons.png_icon", data, source)
        return None if got is None else str(got)

    def app_icon(self, app: str, size: int) -> str:
        return str(self._c.rpc("icons.app_icon", app, size))

    def app_name(self, app: str) -> str:
        return str(self._c.rpc("icons.app_name", app))

    def on_theme_changed(self, callback: Callable[[], None]) -> Sub:
        sid = self._c.register(callback, "raw")
        self._c.cmd("icons.on_theme_changed", sid)
        return Sub(self._c, sid)

    def close(self) -> None:
        return None


# -- windows ---------------------------------------------------------------------------------


class ProxyWindowsPort:
    def __init__(self, link: Link) -> None:
        self._c = link

    def for_module(self, module: str) -> ProxyWindows:
        return ProxyWindows(self._c)


class ProxyWindows:
    """``ModuleWindows``: the shell pushes the list with each change; ``list()`` reads the copy."""

    def __init__(self, link: Link) -> None:
        self._c = link
        self._list: tuple[WindowInfo, ...] = ()

    @property
    def available(self) -> bool:
        return bool(self._c.rpc("windows.available"))

    @property
    def ready(self) -> bool:
        return bool(self._c.rpc("windows.ready"))

    def list(self) -> tuple[WindowInfo, ...]:
        return self._list

    def on_changed(self, callback: Callable[[], None]) -> Sub:
        def pre(windows: Sequence[Mapping[str, Any]]) -> tuple[Any, ...]:
            self._list = tuple(
                WindowInfo(**{**w, "desktops": tuple(w["desktops"])}) for w in windows
            )
            return ()

        sid = self._c.register(callback, "main", pre)
        self._c.cmd("windows.on_changed", sid)
        return Sub(self._c, sid)

    def activate(self, window_id: str) -> concurrent.futures.Future[bool]:
        return self._c.call_future("windows.activate", window_id)

    def minimize(self, window_id: str) -> concurrent.futures.Future[bool]:
        return self._c.call_future("windows.minimize", window_id)

    def close_window(self, window_id: str) -> concurrent.futures.Future[bool]:
        return self._c.call_future("windows.close_window", window_id)

    def close(self) -> None:
        return None


# -- the sound server --------------------------------------------------------------------------


def _state(d: Mapping[str, Any] | None) -> AudioState | None:
    if d is None:
        return None
    out = None if d["output"] is None else Output(**d["output"])
    return AudioState(
        out,
        d["volume"],
        d["muted"],
        d["has_mic"],
        d["mic_muted"],
        tuple(Output(**o) for o in d["outputs"]),
    )


class ProxyAudioPort:
    def __init__(self, link: Link) -> None:
        self._c = link

    def for_module(self, module: str) -> ProxyAudio:
        return ProxyAudio(self._c)


class ProxyAudio:
    """``ModuleAudio`` over the shell's one connection to the sound server."""

    def __init__(self, link: Link) -> None:
        self._c = link
        self._state: AudioState | None = None

    @property
    def available(self) -> bool:
        return bool(self._c.rpc("audio.available"))

    @property
    def state(self) -> AudioState | None:
        return self._state

    def on_changed(self, callback: Callable[[AudioState | None], None]) -> Sub:
        def pre(state: Mapping[str, Any] | None) -> tuple[Any, ...]:
            self._state = _state(state)
            return (self._state,)

        sid = self._c.register(callback, "aio", pre)
        self._c.cmd("audio.on_changed", sid)
        return Sub(self._c, sid)

    def set_volume(self, percent: float) -> concurrent.futures.Future[None]:
        return self._c.call_future("audio.set_volume", percent)

    def step(self, delta: float) -> concurrent.futures.Future[None]:
        return self._c.call_future("audio.step", delta)

    def set_muted(self, muted: bool) -> concurrent.futures.Future[None]:
        return self._c.call_future("audio.set_muted", muted)

    def toggle_mute(self) -> concurrent.futures.Future[None]:
        return self._c.call_future("audio.toggle_mute")

    def toggle_mic(self) -> concurrent.futures.Future[None]:
        return self._c.call_future("audio.toggle_mic")

    def set_output(self, name: str) -> concurrent.futures.Future[None]:
        return self._c.call_future("audio.set_output", name)

    def close(self) -> None:
        return None


class ProxyTrayPort:
    def __init__(self, link: Link) -> None:
        self._c = link

    def for_module(self, module: str) -> ProxyTray:
        return ProxyTray(self._c)


class ProxyTray:
    def __init__(self, link: Link) -> None:
        self._c = link

    def on_host(self, callback: Callable[[bool], None]) -> Sub:
        sid = self._c.register(callback, "aio")
        self._c.cmd("tray.on_host", sid)
        return Sub(self._c, sid)

    def close(self) -> None:
        return None


# -- D-Bus: the shell's layer holds the connections --------------------------------------------


class ProxyDBusPort:
    def __init__(self, link: Link) -> None:
        self._c = link

    def for_module(
        self, module: str, send: Callable[[str, object], None], hooks: Any
    ) -> ProxyModuleDBus:
        return ProxyModuleDBus(self._c)


class ProxyModuleDBus:
    """``ModuleDBus``. ``available`` is the layer's, pushed by the shell each time it changes, so
    reading it from any thread costs nothing."""

    def __init__(self, link: Link) -> None:
        self._c = link
        self._buses: dict[str, ProxyBus] = {}

    @property
    def available(self) -> bool:
        return bool(self._c.state["dbus_available"])

    def session(self) -> ProxyBus:
        return self._buses.setdefault("session", ProxyBus(self._c, "session"))

    def system(self) -> ProxyBus:
        return self._buses.setdefault("system", ProxyBus(self._c, "system"))

    def close(self) -> None:
        return None


class ProxyBus:
    def __init__(self, link: Link, kind: str) -> None:
        self._c = link
        self._kind = kind

    def proxy(
        self, name: str, path: str, interface: str | None = None, *, optional: bool = False
    ) -> ProxyProxy:
        pid = self._c.next_id()
        self._c.cmd("dbus.proxy", self._kind, pid, name, path, interface, optional)
        return ProxyProxy(self._c, pid)

    def watch_prefix(
        self, prefix: str, on_added: Callable[[str], None], on_removed: Callable[[str], None]
    ) -> Sub:
        added = self._c.register(on_added, "aio")
        removed = self._c.register(on_removed, "aio")
        self._c.cmd("dbus.watch_prefix", self._kind, prefix, added, removed)
        return Sub(self._c, added, removed)

    def forget(self, name: str) -> None:
        self._c.cmd("dbus.forget", self._kind, name)

    def state(self, name: str) -> ServiceState:
        return ServiceState(self._c.rpc("dbus.state", self._kind, name))

    def run[T](self, coro: Coroutine[Any, Any, T]) -> concurrent.futures.Future[T]:
        return asyncio.run_coroutine_threadsafe(coro, self._c.aio().loop)

    def run_blocking[T](self, coro: Coroutine[Any, Any, T], timeout: float | None = None) -> T:
        if threading.get_ident() in (self._c.loop.ident, self._c.aio().ident):
            coro.close()
            raise BlockingCallError("a blocking call on the loop thread or the service thread")
        return self.run(coro).result(timeout)


class ProxyProxy:
    def __init__(self, link: Link, pid: int) -> None:
        self._c = link
        self._pid = pid

    async def get(self, prop: str, *, interface: str | None = None, fresh: bool = False) -> Any:
        return await self._c.arpc("dbus.get", self._pid, prop, interface, fresh)

    async def call(
        self,
        method: str,
        args: Sequence[Any] = (),
        signature: str = "",
        *,
        interface: str | None = None,
        timeout: float = 5.0,
    ) -> Any:
        return await self._c.arpc(
            "dbus.call",
            self._pid,
            method,
            list(args),
            signature,
            interface,
            timeout,
            wait=timeout + AWAIT_SLACK,
        )

    async def set(
        self,
        prop: str,
        value: Any,
        signature: str,
        *,
        interface: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        await self._c.arpc(
            "dbus.set",
            self._pid,
            prop,
            value,
            signature,
            interface,
            timeout,
            wait=timeout + AWAIT_SLACK,
        )

    def on_property_changed(
        self,
        callback: Callable[[Mapping[str, Any]], None],
        *,
        interface: str | None = None,
        initial: bool = True,
    ) -> Sub:
        sid = self._c.register(callback, "aio")
        self._c.cmd("dbus.on_property_changed", self._pid, sid, interface, initial)
        return Sub(self._c, sid)

    def on_signal(
        self, member: str, callback: Callable[..., None], *, interface: str | None = None
    ) -> Sub:
        sid = self._c.register(callback, "aio")
        self._c.cmd("dbus.on_signal", self._pid, sid, member, interface)
        return Sub(self._c, sid)
