"""The context (``self.ctx``): a module's whole view of the shell (Module Context).

M2 offers ``name``, ``uid``, ``config``, ``log``, ``uses``, ``send`` and ``on_tick``; later
milestones add ``popup``, ``dbus``, ``audio``, ``icons``, ``tray``, ``focus``, ``windows``, ``apps``
and ``surface``.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from loguru import logger

from tess_shell.logging import note_module_error
from tess_shell.modules.ticks import Subscription, TimeSource
from tess_shell.services.api import (
    AppInfo,
    AppsPort,
    AudioPort,
    DBusPort,
    IconsPort,
    LaunchResult,
    ModuleAudio,
    ModuleDBus,
    ModuleIcons,
    ModuleTray,
    ModuleWindows,
    SurfacePort,
    TrayPort,
    WindowsPort,
)
from tess_shell.services.api import Subscription as ServiceSubscription


@dataclass(frozen=True, slots=True)
class UseRecord:
    """A place where the module is used."""

    key: str  # <Module>@<uid>
    name: str
    uid: str
    monitor: str
    params: Mapping[str, Any]


class PopupPort(Protocol):
    """What the shell offers a module for its Popups (the surface manager's ``Popups``)."""

    def call(
        self,
        module: str,
        use: str | None,
        name: str,
        data: Mapping[str, Any] | None,
        anchor: tuple[float, float, float, float] | None = None,
    ) -> None: ...

    def close_named(self, name: str | None = None) -> None: ...

    def update_data(self, name: str, data: Mapping[str, Any]) -> bool: ...

    def is_open(self, name: str) -> bool: ...


class FocusPort(Protocol):
    """What the shell offers a module for shortcut mode (the surface manager's ``ModeDriver``)."""

    def get_default(self) -> str | None: ...

    def set_default(self, name: str | None, who: str = ...) -> None: ...

    def set_mode(self, name: str, value: bool, who: str = ...) -> bool: ...


class ModuleFocus:
    """``ctx.focus``: shortcut mode and the surface that starts with focus (Focus and Keyboard >
    Python Contract). Loop thread only, like ``ctx.popup``."""

    def __init__(self, port: FocusPort, who: str) -> None:
        self._port = port
        self._who = who

    @property
    def default(self) -> str | None:
        """The ``Name`` of the surface that starts with the focus when shortcut mode is entered
        with ``Enter_Shortcut_Mode``; ``None``, the start value, is the Frame. Set it to a surface's
        ``Name`` (a Bar, a Panel, a Frame or a strip written ``<Frame>.<side>``, as the focus
        order names them); a name that is no surface is logged with the nearest names and the
        value does not change."""
        return self._port.get_default()

    @default.setter
    def default(self, name: str | None) -> None:
        self._port.set_default(name, f"ctx.focus.default ({self._who})")

    def set_mode(self, name: str, value: bool) -> bool:
        """Set ``Shortcut_Mode`` of the surface ``name``. True puts that surface in shortcut mode
        with the focus (every other is false, the shell enters the mode if it was not in it);
        False on the surface that is in the mode leaves the mode for the whole shell, False on any
        other changes nothing. ``False`` is returned, and one error logged, when no surface has
        that name."""
        return self._port.set_mode(name, bool(value), f"ctx.focus.set_mode ({self._who})")


class ModuleApps:
    """``ctx.apps`` (Applications Module > The Application Index): the service's list, and a start
    that asks the surface of the module's use for an activation token first (the token must come
    from the handler of the key or click that starts the application). Loop thread only."""

    def __init__(
        self, port: AppsPort, surfaces: Callable[[], SurfacePort | None], ctx: ModuleContext
    ) -> None:
        self._port = port
        self._surfaces = surfaces
        self._ctx = ctx
        self._subscriptions: list[ServiceSubscription] = []

    @property
    def ready(self) -> bool:
        return self._port.ready

    def search(self, query: str, limit: int = 8) -> list[AppInfo]:
        return self._port.search(query, limit)

    def get(self, app: str) -> AppInfo | None:
        return self._port.get(app)

    def launch(
        self,
        app: str,
        *,
        use: str | None = None,
        on_done: Callable[[LaunchResult], None] | None = None,
    ) -> None:
        caller = self._ctx.caller
        key = use if use is not None else (caller.key if caller is not None else None)
        surfaces = self._surfaces()
        if key is None or surfaces is None:
            self._port.launch(app, None, on_done)
            return

        def got(token: str | None) -> None:
            if token:
                self._ctx.log.debug(f"activation token: received for {app}")
            else:
                self._ctx.log.debug(f"activation token: none for {app}: launching without one")
            self._port.launch(app, token, on_done)

        surfaces.request_token(key, got)

    def on_changed(self, callback: Callable[[], None]) -> ServiceSubscription:
        sub = self._port.on_changed(callback)
        self._subscriptions.append(sub)
        return sub

    def refresh(self) -> None:
        if not self._port.watching:
            self._port.refresh()

    def close(self) -> None:
        for sub in self._subscriptions:
            sub.cancel()
        self._subscriptions.clear()


class ModuleSurface:
    """``ctx.surface``: the surface a module's use is on (a Panel, for ``hide``). The use is the
    one that called (``ctx.caller``, set while an ``@action`` runs) or ``use``. Loop thread only."""

    def __init__(self, ctx: ModuleContext, port: SurfacePort) -> None:
        self._ctx = ctx
        self._port = port
        self._subscriptions: list[ServiceSubscription] = []

    def _key(self, use: UseRecord | str | None, what: str) -> str | None:
        if isinstance(use, UseRecord):
            return use.key
        if use is not None:
            return use
        if self._ctx.caller is not None:
            return self._ctx.caller.key
        self._ctx.log.error(
            f"ctx.surface.{what}() needs the use: call it from an @action or pass use="
        )
        return None

    def hide(self, use: UseRecord | str | None = None) -> bool:
        """Hide the Panel the use is on (as ``Hide`` does). False, with one error logged, when the
        use is on no Panel."""
        key = self._key(use, "hide")
        return key is not None and self._port.hide_use(key)

    def focus(
        self, name: str, *, select_all: bool = False, use: UseRecord | str | None = None
    ) -> bool:
        """Give the keyboard focus (inside the surface) to the block ``Name: name`` of the use, and
        with ``select_all`` select its text, so the next key replaces it. False when the use has no
        such block or it cannot take focus. The compositor decides whether the surface itself has
        the keyboard (its ``Keyboard`` word)."""
        key = self._key(use, "focus")
        return key is not None and self._port.focus_block(key, name, select_all)

    def on_shown(self, callback: Callable[[UseRecord], None]) -> ServiceSubscription:
        """``callback(use)`` on the loop thread for each use of this module on a Panel that was just
        shown (a Panel that shows again, from hidden). The shell cancels it when the module
        stops."""

        def shown(keys: tuple[str, ...]) -> None:
            for key in keys:
                use = self._ctx.uses.get(key)
                if use is not None:
                    callback(use)

        sub = self._port.watch_shown(shown)
        self._subscriptions.append(sub)
        return sub

    def close(self) -> None:
        for sub in self._subscriptions:
            sub.cancel()
        self._subscriptions.clear()


class ModuleContext:
    def __init__(
        self,
        name: str,
        uid: str,
        config: Mapping[str, Any],
        uses: Mapping[str, UseRecord],
        send: Callable[[str | None, str, object], None],
        ticks: TimeSource,
        popups: Callable[[], PopupPort | None] | None = None,
        dbus: Callable[[], DBusPort | None] | None = None,
        audio: Callable[[], AudioPort | None] | None = None,
        icons: Callable[[], IconsPort | None] | None = None,
        tray: Callable[[], TrayPort | None] | None = None,
        call_soon: Callable[[], Callable[[Callable[[], None]], None] | None] | None = None,
        focus: Callable[[], FocusPort | None] | None = None,
        windows: Callable[[], WindowsPort | None] | None = None,
        apps: Callable[[], AppsPort | None] | None = None,
        surfaces: Callable[[], SurfacePort | None] | None = None,
    ) -> None:
        self.name = name
        self.caller: UseRecord | None = None  # the use whose block raised the event being handled
        self._popups = popups
        self._dbus_port = dbus
        self._dbus: ModuleDBus | None = None
        self._audio_port = audio
        self._audio: ModuleAudio | None = None
        self._icons_port = icons
        self._icons: ModuleIcons | None = None
        self._tray_port = tray
        self._tray: ModuleTray | None = None
        self._windows_port = windows
        self._windows: ModuleWindows | None = None
        self._apps_port = apps
        self._apps: ModuleApps | None = None
        self._surfaces = surfaces
        self._surface: ModuleSurface | None = None
        self._call_soon = call_soon
        self._focus_port = focus
        self._focus: ModuleFocus | None = None
        self._on_lost: Callable[[str], None] | None = None
        self._on_found: Callable[[str], None] | None = None
        self._closed = False
        self.uid = uid
        self.config = config
        self.uses = uses
        self.log = logger.bind(source=f"module:{name}")
        self._send = send
        self._ticks = ticks
        self._subscriptions: list[Subscription] = []

    def send(self, key: str, value: object, use: UseRecord | str | None = None) -> None:
        """Send one value, for one use or (with no ``use``) for every use of this module. Thread
        safe, coalesced, never blocks."""
        use_key = use.key if isinstance(use, UseRecord) else use
        self._send(use_key, key, value)

    def popup(
        self,
        name: str,
        data: Mapping[str, Any] | None = None,
        use: UseRecord | str | None = None,
        anchor: tuple[float, float, float, float] | None = None,
    ) -> None:
        """Open the Popup ``name`` beside the use that called (``ctx.caller``, set while an
        ``@action`` runs; or ``use``) or, with ``anchor`` (``(x, y, width, height)`` in output
        coordinates, normally ``event.rect``), beside that rectangle: one block of a use's own
        ``For`` entries. Or close it when it is the open one. Loop thread only. A
        Popup that does not exist, or a use on no open surface, is logged with the module and
        the name; nothing is raised."""
        key = use.key if isinstance(use, UseRecord) else use
        if key is None and self.caller is not None:
            key = self.caller.key
        if key is None:
            self.log.error(
                f"ctx.popup({name!r}) needs the use that calls it: call it from an @action, "
                "or pass use="
            )
            return
        port = self._popups() if self._popups else None
        if port is None:
            self.log.error(f"ctx.popup({name!r}): the shell has no surfaces to open it on")
            return
        port.call(self.name, key, name, data, anchor)

    def close_popup(self, name: str | None = None) -> None:
        """Close the open Popup (the one called ``name``, if given). Loop thread only."""
        port = self._popups() if self._popups else None
        if port is not None:
            port.close_named(name)

    def update_popup(self, name: str, data: Mapping[str, Any]) -> bool:
        """Give the open Popup ``name`` (and the submenus open from it) new ``caller.data``: its
        content is resolved again and only what differs changes, so it stays open, in place, at its
        size. False when it is not open (nothing happens). Loop thread only."""
        port = self._popups() if self._popups else None
        return port is not None and port.update_data(name, data)

    def is_popup_open(self, name: str) -> bool:
        """Is the Popup ``name`` open (or one of its submenus)? Loop thread only."""
        port = self._popups() if self._popups else None
        return port is not None and port.is_open(name)

    def announce(
        self, text: str, *, politeness: str = "polite", use: UseRecord | str | None = None
    ) -> None:
        """Say ``text`` through assistive technology, once: a screen reader reads it (nothing
        happens when none is connected). ``politeness`` is ``"polite"`` (waits for the reader to
        finish) or ``"assertive"`` (interrupts). With no ``use`` it is said for the module's first
        use that is on an open window, so a module used on two Bars is not read twice; with ``use``
        for that use's window (``ctx.caller`` is not consulted). It is said even when the
        module's block is hidden, and the same text twice running is said twice. Safe from any
        thread. Nothing is said, with one debug line, when no use is on an open window. A text that
        is empty or a politeness other than the two raises ``ValueError``."""
        if not isinstance(text, str) or not text.strip():
            raise ValueError("ctx.announce needs a text that is not empty")
        if politeness not in ("polite", "assertive"):
            raise ValueError(
                f"ctx.announce: politeness is 'polite' or 'assertive', not {politeness!r}"
            )
        if use is None:
            keys = list(self.uses)
        else:
            keys = [use.key if isinstance(use, UseRecord) else use]
        port = self._surfaces() if self._surfaces else None
        if port is None or not keys:
            self.log.debug(f"ctx.announce({text!r}): no surface to say it on")
            return

        def say() -> None:
            if not port.announce(keys, text, politeness):
                self.log.debug(f"ctx.announce({text!r}): no use of the module is on an open window")

        hop = self._call_soon() if self._call_soon else None
        if hop is None:
            say()
            return

        def run() -> None:
            if self._closed:
                return
            try:
                say()
            except Exception as exc:
                self.log.opt(exception=True).error("ctx.announce raised")
                note_module_error(self.name, "ctx.announce", exc)

        hop(run)

    def call_soon(self, fn: Callable[[], None]) -> None:
        """Run ``fn`` on the loop thread soon, from any thread (a callback of the ``dbus``
        thread that must open a Popup does it this way). An exception is logged with the module's
        name. Dropped once the module has stopped."""
        port = self._call_soon() if self._call_soon else None
        if port is None:
            raise RuntimeError("the shell has no loop to call into")

        def run() -> None:
            if self._closed:
                return
            try:
                fn()
            except Exception as exc:
                self.log.opt(exception=True).error("a call_soon callback raised")
                note_module_error(self.name, "a call_soon callback", exc)

        port(run)

    @property
    def focus(self) -> ModuleFocus:
        """Shortcut mode and the default focus (Focus and Keyboard): ``ctx.focus.default = "Dock"``
        and ``ctx.focus.set_mode("Dock", True)``. Loop thread only."""
        if self._focus is None:
            port = self._focus_port() if self._focus_port else None
            if port is None:
                raise RuntimeError("the shell has no surfaces: no shortcut mode")
            self._focus = ModuleFocus(port, self.name)
        return self._focus

    @property
    def dbus(self) -> ModuleDBus:
        """The D-Bus helper (D-Bus Service Layer): ``ctx.dbus.session()`` and ``.system()`` give a
        bus with ``proxy(name, path)``. Nothing connects until a proxy is used. The first use
        sends ``available`` false at once; the layer sends the real value when it has read the
        module's services."""
        if self._dbus is None:
            port = self._dbus_port() if self._dbus_port else None
            if port is None:
                raise RuntimeError("the shell has no D-Bus service layer")
            self._dbus = port.for_module(self.name, lambda key, value: self.send(key, value), self)
            # a layout that reads ``available`` has a value before the layer has read a service
            self.send("available", False)
        return self._dbus

    @property
    def audio(self) -> ModuleAudio:
        """The sound server (Audio Module): ``on_changed(callback)`` for the default output's
        volume, mute, name and kind, the default input's mute and the list of outputs, and the
        setters. Nothing connects until it is used."""
        if self._audio is None:
            port = self._audio_port() if self._audio_port else None
            if port is None:
                raise RuntimeError("the shell has no sound service")
            self._audio = port.for_module(self.name)
        return self._audio

    @property
    def icons(self) -> ModuleIcons:
        """The shell's icon lookup (Tray Module > Icons): ``theme_icon(name, size, theme_path)``,
        ``pixmap_icon`` and ``png_icon`` give a reference a block's ``Icon:`` shows. They read
        files: not on the loop thread."""
        if self._icons is None:
            port = self._icons_port() if self._icons_port else None
            if port is None:
                raise RuntimeError("the shell has no icon service")
            self._icons = port.for_module(self.name)
        return self._icons

    @property
    def tray(self) -> ModuleTray:
        """The shell as a StatusNotifier host: ``on_host(callback)``. The shell owns the host's
        name; the helper offers no way to own another."""
        if self._tray is None:
            port = self._tray_port() if self._tray_port else None
            if port is None:
                raise RuntimeError("the shell has no tray host service")
            self._tray = port.for_module(self.name)
        return self._tray

    @property
    def windows(self) -> ModuleWindows:
        """The open windows from the shell's KWin script (Tasks Module): ``on_changed(callback)``,
        ``list()``, ``activate(id)``, ``minimize(id)``, ``close_window(id)``, ``available`` and
        ``ready``. The first ``on_changed`` turns the list on; with no subscriber the script sends
        no title, class or id. Loop thread only."""
        if self._windows is None:
            port = self._windows_port() if self._windows_port else None
            if port is None:
                raise RuntimeError("the shell has no window service")
            self._windows = port.for_module(self.name)
        return self._windows

    @property
    def apps(self) -> ModuleApps:
        """The installed applications (Applications Module): ``ready``, ``search(query, limit)``,
        ``get(id)``, ``launch(id)``, ``on_changed(callback)``. The first use builds the list on a
        worker thread. Loop thread only."""
        if self._apps is None:
            port = self._apps_port() if self._apps_port else None
            if port is None:
                raise RuntimeError("the shell has no application service")
            port.start()  # the first use builds the list, off the loop thread
            self._apps = ModuleApps(
                port, lambda: self._surfaces() if self._surfaces else None, self
            )
        return self._apps

    @property
    def surface(self) -> ModuleSurface:
        """The surface the module's use is on: ``hide()``, ``focus(name)``, ``on_shown(callback)``.
        Loop thread only."""
        if self._surface is None:
            port = self._surfaces() if self._surfaces else None
            if port is None:
                raise RuntimeError("the shell has no surfaces")
            self._surface = ModuleSurface(self, port)
        return self._surface

    def send_available(self, use: UseRecord) -> None:
        """Give a use that appeared after the layer sent ``available`` its current value (the
        host calls it for each new use of a module that has used ``ctx.dbus``)."""
        if self._dbus is not None:
            self.send("available", self._dbus.available, use=use)

    def set_service_hooks(self, lost: Callable[[str], None], found: Callable[[str], None]) -> None:
        """The module's ``on_service_lost`` and ``on_service_found`` (set by the host)."""
        self._on_lost, self._on_found = lost, found

    def lost(self, name: str) -> None:  # ServiceHooks: the layer calls it on the loop thread
        self._service_hook("on_service_lost", self._on_lost, name)

    def found(self, name: str) -> None:
        self._service_hook("on_service_found", self._on_found, name)

    def _service_hook(self, what: str, fn: Callable[[str], None] | None, name: str) -> None:
        if self._closed or fn is None:
            return
        try:
            fn(name)
        except Exception as exc:
            self.log.opt(exception=True).error(f"{what}({name!r}) raised")
            note_module_error(self.name, what, exc)

    def on_tick(self, unit: str, fn: Callable[[], None]) -> Subscription:
        """Call ``fn`` at the start of each ``"second"`` or ``"minute"``, on the loop thread."""
        guarded = self._guard(fn)
        sub = self._ticks.subscribe(unit, guarded)
        self._subscriptions.append(sub)
        return sub

    def _guard(self, fn: Callable[[], None]) -> Callable[[], None]:
        def run() -> None:
            try:
                fn()
            except Exception as exc:
                self.log.opt(exception=True).error("a tick callback raised")
                note_module_error(self.name, "a tick callback", exc)

        return run

    def close(self) -> None:
        for sub in self._subscriptions:
            sub.cancel()
        self._subscriptions.clear()
        self._closed = True
        if self._dbus is not None:
            self._dbus.close()
            self._dbus = None
        if self._audio is not None:
            self._audio.close()
            self._audio = None
        if self._icons is not None:
            self._icons.close()
            self._icons = None
        if self._tray is not None:
            self._tray.close()
            self._tray = None
        if self._windows is not None:
            self._windows.close()
            self._windows = None
        if self._apps is not None:
            self._apps.close()
            self._apps = None
        if self._surface is not None:
            self._surface.close()
            self._surface = None
