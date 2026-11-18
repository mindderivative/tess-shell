"""What a module process sees of the shell's services when the shell keeps them (B2, and always for
popups, surfaces, windows, applications and icons): objects with the same methods as the ports and
helpers of ``tess_shell.services.api``, each call a message to the shell.

Three kinds of call, named for what the module's thread does:

* ``cmd``: the shell is told and nothing comes back (a popup to open, a subscription);
* ``rpc``: the thread waits for the answer (a read: ``is_popup_open``, ``apps.search``,
  ``icons.app_icon``). These are the members whose contract says they return at once on the loop
  thread; across a pipe they cost a round trip, which is one of the findings of the prototype;
* a future or a coroutine: the call returns a future (``windows.activate``, ``audio.set_volume``) or
  is awaited on the proxy service thread (``Proxy.get`` and ``Proxy.call``), the answer completing it.

A callback the shell pushes (``cb``) runs on the module's loop thread, or on the proxy service thread
for the ones the contract runs on the D-Bus thread.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import threading
from collections.abc import Callable, Coroutine, Mapping, Sequence
from typing import TYPE_CHECKING, Any

from tess_shell.services.api import (
    AppInfo,
    AudioState,
    BlockingCallError,
    LaunchResult,
    Output,
    ServiceState,
    WindowInfo,
)

if TYPE_CHECKING:
    from tests.perf.proto.child import Child


class Sub:
    """A ``Subscription``: cancelling tells the shell and forgets the callback."""

    def __init__(self, child: Child, *sids: int) -> None:
        self._child = child
        self._sids = sids

    def cancel(self) -> None:
        for sid in self._sids:
            self._child.unregister(sid)
            self._child.cmd("unsub", sid)


# -- popups, surfaces, applications -----------------------------------------------------------


class ProxyPopups:
    """``PopupPort``."""

    def __init__(self, child: Child) -> None:
        self._c = child

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


class ProxySurfacePort:
    """``SurfacePort``."""

    def __init__(self, child: Child) -> None:
        self._c = child

    def hide_use(self, use_key: str) -> bool:
        return bool(self._c.rpc("surface.hide", use_key))

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

    def __init__(self, child: Child) -> None:
        self._c = child

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


# -- icons ---------------------------------------------------------------------------------


class ProxyIconsPort:
    def __init__(self, child: Child) -> None:
        self._c = child

    def for_module(self, module: str) -> ProxyIcons:
        return ProxyIcons(self._c)


class ProxyIcons:
    """``ModuleIcons``: the registry of decoded pixels is the engine's, so the lookups stay in the
    shell and only the references (text) come back."""

    def __init__(self, child: Child) -> None:
        self._c = child

    def theme_icon(self, name: str, size: int, theme_path: str | None = None) -> str | None:
        return self._c.rpc("icons.theme_icon", name, size, theme_path)  # type: ignore[no-any-return]

    def pixmap_icon(
        self, pixmaps: Sequence[Sequence[Any]], size: int, source: str = ""
    ) -> str | None:
        return self._c.rpc("icons.pixmap_icon", [list(p) for p in pixmaps], size, source)  # type: ignore[no-any-return]

    def png_icon(self, data: bytes, source: str = "") -> str | None:
        return self._c.rpc("icons.png_icon", data, source)  # type: ignore[no-any-return]

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


# -- windows -------------------------------------------------------------------------------


class ProxyWindowsPort:
    def __init__(self, child: Child) -> None:
        self._c = child

    def for_module(self, module: str) -> ProxyWindows:
        return ProxyWindows(self._c)


class ProxyWindows:
    """``ModuleWindows``: the shell pushes the list with each change; ``list()`` reads the copy."""

    def __init__(self, child: Child) -> None:
        self._c = child
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


# -- the sound server (B2) --------------------------------------------------------------------


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
    def __init__(self, child: Child) -> None:
        self._c = child

    def for_module(self, module: str) -> ProxyAudio:
        return ProxyAudio(self._c)


class ProxyAudio:
    """``ModuleAudio`` over the shell's one connection to the sound server."""

    def __init__(self, child: Child) -> None:
        self._c = child
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
        self._c.cmd("audio.close")


class ProxyTrayPort:
    def __init__(self, child: Child) -> None:
        self._c = child

    def for_module(self, module: str) -> ProxyTray:
        return ProxyTray(self._c)


class ProxyTray:
    def __init__(self, child: Child) -> None:
        self._c = child

    def on_host(self, callback: Callable[[bool], None]) -> Sub:
        sid = self._c.register(callback, "aio")
        self._c.cmd("tray.on_host", sid)
        return Sub(self._c, sid)

    def close(self) -> None:
        return None


# -- D-Bus (B2): the shell's layer holds the connections -----------------------------------------


class ProxyDBusPort:
    def __init__(self, child: Child) -> None:
        self._c = child

    def for_module(
        self, module: str, send: Callable[[str, object], None], hooks: Any
    ) -> ProxyModuleDBus:
        return ProxyModuleDBus(self._c)


class ProxyModuleDBus:
    """``ModuleDBus``. ``available`` is read from the shell's helper (it is the layer's)."""

    def __init__(self, child: Child) -> None:
        self._c = child
        self._buses: dict[str, ProxyBus] = {}

    @property
    def available(self) -> bool:
        return bool(self._c.rpc("dbus.available"))

    def session(self) -> ProxyBus:
        return self._buses.setdefault("session", ProxyBus(self._c, "session"))

    def system(self) -> ProxyBus:
        return self._buses.setdefault("system", ProxyBus(self._c, "system"))

    def close(self) -> None:
        self._c.cmd("dbus.close")


class ProxyBus:
    def __init__(self, child: Child, kind: str) -> None:
        self._c = child
        self._kind = kind

    def proxy(
        self, name: str, path: str, interface: str | None = None, *, optional: bool = False
    ) -> ProxyProxy:
        pid = self._c.next_id()
        self._c.cmd("dbus.proxy", self._kind, pid, name, path, interface, optional)
        return ProxyProxy(self._c, pid, interface)

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
    def __init__(self, child: Child, pid: int, interface: str | None) -> None:
        self._c = child
        self._pid = pid
        self._interface = interface

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
        result = await self._c.arpc(
            "dbus.call", self._pid, method, list(args), signature, interface, timeout
        )
        if isinstance(result, dict) and set(result) == {"$tuple"}:
            return tuple(result["$tuple"])  # several results: a tuple, as in A
        return result

    async def set(
        self,
        prop: str,
        value: Any,
        signature: str,
        *,
        interface: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        await self._c.arpc("dbus.set", self._pid, prop, value, signature, interface, timeout)

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
