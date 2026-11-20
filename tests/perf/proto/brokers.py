"""What the shell does when a module process asks for something (B2, and always for popups,
surfaces, windows, applications and icons).

``TABLE`` maps a call name to ``(mode, function)``; the function takes the :class:`Child` and the
call's arguments and returns the answer (or a ``concurrent.futures.Future`` that completes it).

A read that a module may make inside ``start()`` must be ``inline`` or ``pool``: the shell waits for
the first ``start()`` on its loop thread, so a ``loop`` call made there would wait for the loop
(``windows.ready`` was that deadlock in the first run).

``mode`` is where it runs: ``inline`` on the child's reader thread (a cheap read), ``pool`` on a small
pool of that child (a read that may take a while: files, the index), ``loop`` on the shell's loop
thread through ``call_soon`` (everything that touches tre, the surfaces or the layer, which are loop
thread only, and everything whose order matters: a proxy must exist before it is read).
"""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from dataclasses import asdict
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tests.perf.proto.parent import Child

Entry = tuple[str, Callable[..., Any]]
TABLE: dict[str, Entry] = {}


def serve(name: str, mode: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def register(fn: Callable[..., Any]) -> Callable[..., Any]:
        TABLE[name] = (mode, fn)
        return fn

    return register


def _host(c: Child) -> Any:
    return c.launcher.host


# -- popups ----------------------------------------------------------------------------------


@serve("popup.call", "loop")
def popup_call(c: Child, use: str | None, name: str, data: Any, anchor: Any) -> None:
    port = _host(c).popups
    if port is None:
        raise RuntimeError("the shell has no surfaces to open a Popup on")
    port.call(c.name, use, name, data, tuple(anchor) if anchor else None)


@serve("popup.close", "loop")
def popup_close(c: Child, name: str | None) -> None:
    c.ctx.close_popup(name)


@serve("popup.update", "loop")
def popup_update(c: Child, name: str, data: Any) -> bool:
    return c.ctx.update_popup(name, data)


@serve("popup.is_open", "inline")
def popup_is_open(c: Child, name: str) -> bool:
    return c.ctx.is_popup_open(name)


# -- surfaces -------------------------------------------------------------------------------


@serve("surface.hide", "loop")
def surface_hide(c: Child, use: str) -> bool:
    return bool(_host(c).surfaces.hide_use(use))


@serve("surface.focus", "loop")
def surface_focus(c: Child, use: str, name: str, select_all: bool) -> bool:
    return bool(_host(c).surfaces.focus_block(use, name, select_all))


@serve("surface.watch_shown", "loop")
def surface_watch_shown(c: Child, sid: int) -> None:
    c.subscribe(sid, _host(c).surfaces.watch_shown(lambda keys: c.cb(sid, list(keys))))


@serve("surface.token", "loop")
def surface_token(c: Child, use: str, sid: int) -> None:
    _host(c).surfaces.request_token(use, lambda token: c.cb(sid, token))


@serve("surface.announce", "loop")
def surface_announce(c: Child, keys: list[str], text: str, politeness: str) -> None:
    _host(c).surfaces.announce(keys, text, politeness)


# -- applications ---------------------------------------------------------------------------


@serve("apps.ready", "inline")
def apps_ready(c: Child) -> bool:
    return bool(_host(c).apps.ready)


@serve("apps.watching", "inline")
def apps_watching(c: Child) -> bool:
    return bool(_host(c).apps.watching)


@serve("apps.start", "loop")
def apps_start(c: Child) -> None:
    _host(c).apps.start()


@serve("apps.search", "pool")
def apps_search(c: Child, query: str, limit: int) -> list[dict[str, Any]]:
    return [asdict(a) for a in _host(c).apps.search(query, limit)]


@serve("apps.get", "pool")
def apps_get(c: Child, entry_id: str) -> dict[str, Any] | None:
    found = _host(c).apps.get(entry_id)
    return None if found is None else asdict(found)


@serve("apps.launch", "loop")
def apps_launch(c: Child, entry_id: str, token: str | None, sid: int) -> None:
    done = (lambda result: c.cb(sid, asdict(result))) if sid else None
    _host(c).apps.launch(entry_id, token, done)


@serve("apps.on_changed", "loop")
def apps_on_changed(c: Child, sid: int) -> None:
    c.subscribe(sid, _host(c).apps.on_changed(lambda: c.cb(sid)))


@serve("apps.refresh", "loop")
def apps_refresh(c: Child) -> None:
    _host(c).apps.refresh()


# -- icons -----------------------------------------------------------------------------------


@serve("icons.theme_icon", "pool")
def icons_theme_icon(c: Child, name: str, size: int, theme_path: str | None) -> str | None:
    return c.ctx.icons.theme_icon(name, size, theme_path)


@serve("icons.pixmap_icon", "pool")
def icons_pixmap_icon(c: Child, pixmaps: list[Any], size: int, source: str) -> str | None:
    return c.ctx.icons.pixmap_icon(pixmaps, size, source)


@serve("icons.png_icon", "pool")
def icons_png_icon(c: Child, data: bytes, source: str) -> str | None:
    return c.ctx.icons.png_icon(data, source)


@serve("icons.app_icon", "pool")
def icons_app_icon(c: Child, app: str, size: int) -> str:
    return c.ctx.icons.app_icon(app, size)


@serve("icons.app_name", "pool")
def icons_app_name(c: Child, app: str) -> str:
    return c.ctx.icons.app_name(app)


@serve("icons.on_theme_changed", "loop")
def icons_on_theme_changed(c: Child, sid: int) -> None:
    c.subscribe(sid, c.ctx.icons.on_theme_changed(lambda: c.cb(sid)))


# -- windows -------------------------------------------------------------------------------


@serve("windows.on_changed", "loop")
def windows_on_changed(c: Child, sid: int) -> None:
    helper = c.ctx.windows
    c.subscribe(sid, helper.on_changed(lambda: c.cb(sid, [asdict(w) for w in helper.list()])))


@serve("windows.available", "inline")
def windows_available(c: Child) -> bool:
    return bool(c.ctx.windows.available)


@serve("windows.ready", "inline")
def windows_ready(c: Child) -> bool:
    return bool(c.ctx.windows.ready)


@serve("windows.activate", "loop")
def windows_activate(c: Child, window_id: str) -> Any:
    return c.ctx.windows.activate(window_id)


@serve("windows.minimize", "loop")
def windows_minimize(c: Child, window_id: str) -> Any:
    return c.ctx.windows.minimize(window_id)


@serve("windows.close_window", "loop")
def windows_close_window(c: Child, window_id: str) -> Any:
    return c.ctx.windows.close_window(window_id)


# -- the sound server and the tray host (B2) ---------------------------------------------------


@serve("audio.available", "inline")
def audio_available(c: Child) -> bool:
    return bool(c.ctx.audio.available)


@serve("audio.on_changed", "loop")
def audio_on_changed(c: Child, sid: int) -> None:
    c.subscribe(
        sid,
        c.ctx.audio.on_changed(lambda state: c.cb(sid, None if state is None else asdict(state))),
    )


@serve("audio.set_volume", "loop")
def audio_set_volume(c: Child, percent: float) -> Any:
    return c.ctx.audio.set_volume(percent)


@serve("audio.step", "loop")
def audio_step(c: Child, delta: float) -> Any:
    return c.ctx.audio.step(delta)


@serve("audio.set_muted", "loop")
def audio_set_muted(c: Child, muted: bool) -> Any:
    return c.ctx.audio.set_muted(muted)


@serve("audio.toggle_mute", "loop")
def audio_toggle_mute(c: Child) -> Any:
    return c.ctx.audio.toggle_mute()


@serve("audio.toggle_mic", "loop")
def audio_toggle_mic(c: Child) -> Any:
    return c.ctx.audio.toggle_mic()


@serve("audio.set_output", "loop")
def audio_set_output(c: Child, name: str) -> Any:
    return c.ctx.audio.set_output(name)


@serve("audio.close", "loop")
def audio_close(c: Child) -> None:
    return None


@serve("tray.on_host", "loop")
def tray_on_host(c: Child, sid: int) -> None:
    c.subscribe(sid, c.ctx.tray.on_host(lambda hosted: c.cb(sid, hosted)))


# -- D-Bus (B2): the shell's layer holds the connections ----------------------------------------


def _proxies(c: Child) -> dict[int, tuple[Any, Any]]:
    table: dict[int, tuple[Any, Any]] = c.__dict__.setdefault("dbus_proxies", {})
    return table


def _variants(signature: str, args: list[Any]) -> list[Any]:
    """A ``v`` argument arrives as a two-element list; the layer wants the ``(signature, value)``
    tuple."""
    if "v" not in signature:
        return list(args)
    from dbus_fast import SignatureTree

    types = SignatureTree(signature).types
    return [
        tuple(a) if t.token == "v" and isinstance(a, list) and len(a) == 2 else a
        for t, a in zip(types, args, strict=False)
    ]


def _tupled(future: concurrent.futures.Future[Any]) -> concurrent.futures.Future[Any]:
    """A call with several results returns a tuple (``Proxy.call``); JSON would make it a list, and a
    module (the Tray's ``GetLayout``) tells the two apart, so it is tagged and restored."""
    out: concurrent.futures.Future[Any] = concurrent.futures.Future()

    def done(done_future: concurrent.futures.Future[Any]) -> None:
        try:
            result = done_future.result()
        except BaseException as exc:
            out.set_exception(exc)
        else:
            out.set_result({"$tuple": list(result)} if isinstance(result, tuple) else result)

    future.add_done_callback(done)
    return out


@serve("dbus.available", "inline")
def dbus_available(c: Child) -> bool:
    return bool(c.ctx.dbus.available)


@serve("dbus.close", "loop")
def dbus_close(c: Child) -> None:
    return None


@serve("dbus.proxy", "loop")
def dbus_proxy(
    c: Child, kind: str, pid: int, name: str, path: str, interface: str | None, optional: bool
) -> None:
    bus = getattr(c.ctx.dbus, kind)()
    _proxies(c)[pid] = (bus, bus.proxy(name, path, interface, optional=optional))


@serve("dbus.get", "loop")
def dbus_get(c: Child, pid: int, prop: str, interface: str | None, fresh: bool) -> Any:
    bus, proxy = _proxies(c)[pid]
    return bus.run(proxy.get(prop, interface=interface, fresh=fresh))


@serve("dbus.call", "loop")
def dbus_call(
    c: Child,
    pid: int,
    method: str,
    args: list[Any],
    signature: str,
    interface: str | None,
    timeout: float,
) -> Any:
    bus, proxy = _proxies(c)[pid]
    return _tupled(
        bus.run(
            proxy.call(
                method, _variants(signature, args), signature, interface=interface, timeout=timeout
            )
        )
    )


@serve("dbus.set", "loop")
def dbus_set(
    c: Child,
    pid: int,
    prop: str,
    value: Any,
    signature: str,
    interface: str | None,
    timeout: float,
) -> Any:
    bus, proxy = _proxies(c)[pid]
    return bus.run(proxy.set(prop, value, signature, interface=interface, timeout=timeout))


@serve("dbus.on_property_changed", "loop")
def dbus_on_property_changed(
    c: Child, pid: int, sid: int, interface: str | None, initial: bool
) -> None:
    _, proxy = _proxies(c)[pid]
    c.subscribe(
        sid,
        proxy.on_property_changed(
            lambda changed: c.cb(sid, dict(changed)), interface=interface, initial=initial
        ),
    )


@serve("dbus.on_signal", "loop")
def dbus_on_signal(c: Child, pid: int, sid: int, member: str, interface: str | None) -> None:
    _, proxy = _proxies(c)[pid]
    c.subscribe(sid, proxy.on_signal(member, lambda *body: c.cb(sid, *body), interface=interface))


@serve("dbus.watch_prefix", "loop")
def dbus_watch_prefix(c: Child, kind: str, prefix: str, added: int, removed: int) -> None:
    bus = getattr(c.ctx.dbus, kind)()
    c.subscribe(
        added,
        bus.watch_prefix(prefix, lambda n: c.cb(added, n), lambda n: c.cb(removed, n)),
    )


@serve("dbus.forget", "loop")
def dbus_forget(c: Child, kind: str, name: str) -> None:
    getattr(c.ctx.dbus, kind)().forget(name)


@serve("dbus.state", "loop")
def dbus_state(c: Child, kind: str, name: str) -> str:
    return str(getattr(c.ctx.dbus, kind)().state(name).value)


@serve("unsub", "inline")
def unsub(c: Child, sid: int) -> None:
    c.unsubscribe(sid)
