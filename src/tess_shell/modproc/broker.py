"""What the shell does when a module process asks for something: the services stay in the shell
(B2 for every service), and each call lands on the real helper of the process's real
``ModuleContext`` (``ctx.apps``, ``ctx.icons``, ``ctx.dbus`` ...), so subscriptions,
``available`` and the cleanup when the module ends are the shell's own.

``TABLE`` maps a call name to ``(mode, function)``; the function takes the
:class:`ProcessHandle` and the call's arguments and returns the answer (or a
``concurrent.futures.Future`` that completes it).
``mode`` says where it runs:

* ``loop``: on the shell's loop thread through ``call_soon``: everything that touches tre, the
  surfaces, the layer or a service's loop-thread state, and everything whose order matters (the
  requests of one process run in the order it made them, so a proxy exists before it is read);
* ``pool``: on a small pool of that process, a read that may take a while (files, the index);
* ``inline``: on the process's reader thread, a cheap read of thread safe state.

The module a call is for is always the process's own (``handle.name``, taken from the channel, never
from a message), and a use key that is not of that module is refused: a module process cannot hide
another module's Panel or send it a value.
"""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tess_shell.modproc.supervisor import ProcessHandle

Entry = tuple[str, Callable[..., Any]]
TABLE: dict[str, Entry] = {}


def serve(name: str, mode: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def register(fn: Callable[..., Any]) -> Callable[..., Any]:
        TABLE[name] = (mode, fn)
        return fn

    return register


def own_use(c: ProcessHandle, use: object) -> str:
    """``use`` as a key of this module's uses, or ``ValueError``."""
    if not isinstance(use, str) or use.split("@", 1)[0] != c.name:
        raise ValueError(f"module {c.name}: {use!r} is not a use of this module")
    return use


# -- popups ----------------------------------------------------------------------------------


@serve("popup.call", "loop")
def popup_call(c: ProcessHandle, use: str | None, name: str, data: Any, anchor: Any) -> None:
    port = c.host.popups
    if port is None:
        raise RuntimeError("the shell has no surfaces to open a Popup on")
    key = None if use is None else own_use(c, use)
    port.call(c.name, key, name, data, tuple(anchor) if anchor else None)


@serve("popup.close", "loop")
def popup_close(c: ProcessHandle, name: str | None) -> None:
    c.ctx.close_popup(name)


@serve("popup.update", "loop")
def popup_update(c: ProcessHandle, name: str, data: Any) -> bool:
    return c.ctx.update_popup(name, data)


@serve("popup.is_open", "loop")
def popup_is_open(c: ProcessHandle, name: str) -> bool:
    return c.ctx.is_popup_open(name)


# -- focus and surfaces ------------------------------------------------------------------------


@serve("focus.get_default", "loop")
def focus_get_default(c: ProcessHandle) -> str | None:
    return c.ctx.focus.default


@serve("focus.set_default", "loop")
def focus_set_default(c: ProcessHandle, name: str | None, who: str) -> None:
    c.ctx.focus.default = name


@serve("focus.set_mode", "loop")
def focus_set_mode(c: ProcessHandle, name: str, value: bool, who: str) -> bool:
    return c.ctx.focus.set_mode(name, value)


def _surfaces(c: ProcessHandle) -> Any:
    port = c.host.surfaces
    if port is None:
        raise RuntimeError("the shell has no surfaces")
    return port


@serve("surface.hide", "loop")
def surface_hide(c: ProcessHandle, use: str) -> bool:
    return bool(_surfaces(c).hide_use(own_use(c, use)))


@serve("surface.show", "loop")
def surface_show(c: ProcessHandle, use: str, hide_after: float | None) -> bool:
    return bool(_surfaces(c).show_use(own_use(c, use), hide_after))


@serve("surface.focus", "loop")
def surface_focus(c: ProcessHandle, use: str, name: str, select_all: bool) -> bool:
    return bool(_surfaces(c).focus_block(own_use(c, use), name, select_all))


@serve("surface.watch_shown", "loop")
def surface_watch_shown(c: ProcessHandle, sid: int) -> None:
    c.subscribe(sid, _surfaces(c).watch_shown(lambda keys: c.cb(sid, list(keys))))


@serve("surface.token", "loop")
def surface_token(c: ProcessHandle, use: str, sid: int) -> None:
    _surfaces(c).request_token(own_use(c, use), lambda token: c.cb(sid, token))


@serve("surface.announce", "loop")
def surface_announce(c: ProcessHandle, keys: list[str], text: str, politeness: str) -> None:
    _surfaces(c).announce([own_use(c, k) for k in keys], text, politeness)


# -- applications -------------------------------------------------------------------------------


def _apps(c: ProcessHandle) -> Any:
    port = c.host.apps
    if port is None:
        raise RuntimeError("the shell has no application service")
    return port


@serve("apps.ready", "loop")
def apps_ready(c: ProcessHandle) -> bool:
    return bool(_apps(c).ready)


@serve("apps.watching", "loop")
def apps_watching(c: ProcessHandle) -> bool:
    return bool(_apps(c).watching)


@serve("apps.start", "loop")
def apps_start(c: ProcessHandle) -> None:
    _apps(c).start()


@serve("apps.search", "pool")
def apps_search(c: ProcessHandle, query: str, limit: int) -> list[dict[str, Any]]:
    return [asdict(a) for a in _apps(c).search(query, limit)]


@serve("apps.get", "pool")
def apps_get(c: ProcessHandle, entry_id: str) -> dict[str, Any] | None:
    found = _apps(c).get(entry_id)
    return None if found is None else asdict(found)


@serve("apps.launch", "loop")
def apps_launch(c: ProcessHandle, entry_id: str, token: str | None, sid: int) -> None:
    done = (lambda result: c.cb(sid, asdict(result))) if sid else None
    _apps(c).launch(entry_id, token, done)


@serve("apps.on_changed", "loop")
def apps_on_changed(c: ProcessHandle, sid: int) -> None:
    c.subscribe(sid, _apps(c).on_changed(lambda: c.cb(sid)))


@serve("apps.refresh", "loop")
def apps_refresh(c: ProcessHandle) -> None:
    _apps(c).refresh()


# -- icons ---------------------------------------------------------------------------------------


@serve("icons.theme_icon", "pool")
def icons_theme_icon(c: ProcessHandle, name: str, size: int, theme_path: str | None) -> str | None:
    return c.helper("icons").theme_icon(name, size, theme_path)  # type: ignore[no-any-return]


@serve("icons.pixmap_icon", "pool")
def icons_pixmap_icon(c: ProcessHandle, pixmaps: list[Any], size: int, source: str) -> str | None:
    return c.helper("icons").pixmap_icon(pixmaps, size, source)  # type: ignore[no-any-return]


@serve("icons.png_icon", "pool")
def icons_png_icon(c: ProcessHandle, data: bytes, source: str) -> str | None:
    return c.helper("icons").png_icon(data, source)  # type: ignore[no-any-return]


@serve("icons.app_icon", "pool")
def icons_app_icon(c: ProcessHandle, app: str, size: int) -> str:
    return c.helper("icons").app_icon(app, size)  # type: ignore[no-any-return]


@serve("icons.app_name", "pool")
def icons_app_name(c: ProcessHandle, app: str) -> str:
    return c.helper("icons").app_name(app)  # type: ignore[no-any-return]


@serve("icons.on_theme_changed", "loop")
def icons_on_theme_changed(c: ProcessHandle, sid: int) -> None:
    c.subscribe(sid, c.ctx.icons.on_theme_changed(lambda: c.cb(sid)))


# -- windows -------------------------------------------------------------------------------------


@serve("windows.on_changed", "loop")
def windows_on_changed(c: ProcessHandle, sid: int) -> None:
    helper = c.ctx.windows
    c.subscribe(sid, helper.on_changed(lambda: c.cb(sid, [asdict(w) for w in helper.list()])))


@serve("windows.available", "loop")
def windows_available(c: ProcessHandle) -> bool:
    return bool(c.ctx.windows.available)


@serve("windows.ready", "loop")
def windows_ready(c: ProcessHandle) -> bool:
    return bool(c.ctx.windows.ready)


@serve("windows.activate", "loop")
def windows_activate(c: ProcessHandle, window_id: str) -> Any:
    return c.ctx.windows.activate(window_id)


@serve("windows.minimize", "loop")
def windows_minimize(c: ProcessHandle, window_id: str) -> Any:
    return c.ctx.windows.minimize(window_id)


@serve("windows.close_window", "loop")
def windows_close_window(c: ProcessHandle, window_id: str) -> Any:
    return c.ctx.windows.close_window(window_id)


# -- the sound server and the tray host -----------------------------------------------------------


@serve("audio.available", "loop")
def audio_available(c: ProcessHandle) -> bool:
    return bool(c.ctx.audio.available)


@serve("audio.on_changed", "loop")
def audio_on_changed(c: ProcessHandle, sid: int) -> None:
    c.subscribe(
        sid,
        c.ctx.audio.on_changed(lambda state: c.cb(sid, None if state is None else asdict(state))),
    )


@serve("audio.set_volume", "loop")
def audio_set_volume(c: ProcessHandle, percent: float) -> Any:
    return c.ctx.audio.set_volume(percent)


@serve("audio.step", "loop")
def audio_step(c: ProcessHandle, delta: float) -> Any:
    return c.ctx.audio.step(delta)


@serve("audio.set_muted", "loop")
def audio_set_muted(c: ProcessHandle, muted: bool) -> Any:
    return c.ctx.audio.set_muted(muted)


@serve("audio.toggle_mute", "loop")
def audio_toggle_mute(c: ProcessHandle) -> Any:
    return c.ctx.audio.toggle_mute()


@serve("audio.toggle_mic", "loop")
def audio_toggle_mic(c: ProcessHandle) -> Any:
    return c.ctx.audio.toggle_mic()


@serve("audio.set_output", "loop")
def audio_set_output(c: ProcessHandle, name: str) -> Any:
    return c.ctx.audio.set_output(name)


@serve("tray.on_host", "loop")
def tray_on_host(c: ProcessHandle, sid: int) -> None:
    c.subscribe(sid, c.ctx.tray.on_host(lambda hosted: c.cb(sid, hosted)))


# -- D-Bus: the shell's layer holds the connections ----------------------------------------------


def _proxies(c: ProcessHandle) -> dict[int, tuple[Any, Any]]:
    table: dict[int, tuple[Any, Any]] = c.state.setdefault("dbus_proxies", {})
    return table


def _bus(c: ProcessHandle, kind: str) -> Any:
    if kind not in ("session", "system"):
        raise ValueError(f"no bus {kind!r}")
    return getattr(c.ctx.dbus, kind)()


def _variants(signature: str, args: list[Any]) -> list[Any]:
    """A ``v`` argument arrives as a ``(signature, value)`` tuple through the wire (a two element
    list when it came from a module that wrote a list): the layer wants the tuple."""
    if "v" not in signature:
        return list(args)
    from dbus_fast import SignatureTree

    types = SignatureTree(signature).types
    return [
        tuple(a) if t.token == "v" and isinstance(a, list) and len(a) == 2 else a
        for t, a in zip(types, args, strict=False)
    ]


@serve("dbus.proxy", "loop")
def dbus_proxy(
    c: ProcessHandle,
    kind: str,
    pid: int,
    name: str,
    path: str,
    interface: str | None,
    optional: bool,
) -> None:
    bus = _bus(c, kind)
    _proxies(c)[pid] = (bus, bus.proxy(name, path, interface, optional=optional))


@serve("dbus.get", "loop")
def dbus_get(
    c: ProcessHandle, pid: int, prop: str, interface: str | None, fresh: bool
) -> concurrent.futures.Future[Any]:
    bus, proxy = _proxies(c)[pid]
    return bus.run(proxy.get(prop, interface=interface, fresh=fresh))  # type: ignore[no-any-return]


@serve("dbus.call", "loop")
def dbus_call(
    c: ProcessHandle,
    pid: int,
    method: str,
    args: list[Any],
    signature: str,
    interface: str | None,
    timeout: float,
) -> concurrent.futures.Future[Any]:
    bus, proxy = _proxies(c)[pid]
    return bus.run(  # type: ignore[no-any-return]
        proxy.call(
            method, _variants(signature, args), signature, interface=interface, timeout=timeout
        )
    )


@serve("dbus.set", "loop")
def dbus_set(
    c: ProcessHandle,
    pid: int,
    prop: str,
    value: Any,
    signature: str,
    interface: str | None,
    timeout: float,
) -> concurrent.futures.Future[Any]:
    bus, proxy = _proxies(c)[pid]
    return bus.run(  # type: ignore[no-any-return]
        proxy.set(prop, value, signature, interface=interface, timeout=timeout)
    )


@serve("dbus.on_property_changed", "loop")
def dbus_on_property_changed(
    c: ProcessHandle, pid: int, sid: int, interface: str | None, initial: bool
) -> None:
    _, proxy = _proxies(c)[pid]
    c.subscribe(
        sid,
        proxy.on_property_changed(
            lambda changed: c.cb(sid, dict(changed)), interface=interface, initial=initial
        ),
    )


@serve("dbus.on_signal", "loop")
def dbus_on_signal(
    c: ProcessHandle, pid: int, sid: int, member: str, interface: str | None
) -> None:
    _, proxy = _proxies(c)[pid]
    c.subscribe(sid, proxy.on_signal(member, lambda *body: c.cb(sid, *body), interface=interface))


@serve("dbus.watch_prefix", "loop")
def dbus_watch_prefix(c: ProcessHandle, kind: str, prefix: str, added: int, removed: int) -> None:
    bus = _bus(c, kind)
    c.subscribe(
        added, bus.watch_prefix(prefix, lambda n: c.cb(added, n), lambda n: c.cb(removed, n))
    )


@serve("dbus.forget", "loop")
def dbus_forget(c: ProcessHandle, kind: str, name: str) -> None:
    _bus(c, kind).forget(name)


@serve("dbus.state", "loop")
def dbus_state(c: ProcessHandle, kind: str, name: str) -> str:
    return str(_bus(c, kind).state(name).value)


# -- ticks and subscriptions ---------------------------------------------------------------------


@serve("tick.sub", "loop")
def tick_sub(c: ProcessHandle, sid: int, unit: str) -> None:
    c.subscribe(sid, c.host.ticks.subscribe(unit, lambda: c.cb(sid)))


@serve("unsub", "inline")
def unsub(c: ProcessHandle, sid: int) -> None:
    c.unsubscribe(sid)
