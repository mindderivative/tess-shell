"""What a module sees of the D-Bus service layer (D-Bus Service Layer > Python Contract).

Standard library only: the module host and a module author import these names, and neither may
import ``dbus_fast``. The implementation is ``tess_shell.services.layer``.

Threads. ``Bus.proxy``, ``Proxy.on_property_changed`` and ``Proxy.on_signal`` are plain functions
for the loop thread (they return at once; the work happens on the ``dbus`` service thread).
``Proxy.get`` and ``Proxy.call`` are coroutines that run on the service thread: start one with
``Bus.run`` (a future, any thread, never blocks) or ``Bus.run_blocking`` (any thread except the loop
thread and the service thread, where it raises :class:`BlockingCallError`). A callback given to
``on_property_changed`` or ``on_signal`` runs on the service thread: short, never blocking; it
calls ``ctx.send``, which crosses to the loop.
"""

from __future__ import annotations

import concurrent.futures
import enum
from collections.abc import Callable, Coroutine, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

CALL_TIMEOUT = 5.0  # seconds; every call has one


class ServiceState(enum.Enum):
    """What the layer knows of a service. ``UNAVAILABLE``: the well-known name has no owner (or
    the bus is not reachable)."""

    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"


class ServiceError(Exception):
    """A call failed. ``service`` is the bus name; ``name`` the D-Bus error name, if the service
    sent one."""

    def __init__(self, service: str, message: str, name: str = "") -> None:
        super().__init__(f"{service}: {message}")
        self.service = service
        self.detail = message  # without the service's name in front
        self.name = name


class ServiceTimeout(ServiceError):
    """The call did not finish within its timeout (default 5 s)."""


class ServiceUnavailable(ServiceError):
    """The service has no owner on the bus (``ServiceUnknown``, ``NameHasNoOwner``, ``NoReply``) or
    the bus is not reachable. The layer has set the service's state to ``UNAVAILABLE``."""

    state = ServiceState.UNAVAILABLE


class BlockingCallError(RuntimeError):
    """A blocking form was used on the loop thread (or on the service thread, where it would wait
    for itself)."""


PropertyCallback = Callable[[Mapping[str, Any]], None]
SignalCallback = Callable[..., None]


class Subscription(Protocol):
    def cancel(self) -> None:
        """Stop the callback. The match rule goes with the last subscriber. The shell also cancels
        every subscription of a module when the module stops."""


class Proxy(Protocol):
    """One object on a service: a bus name and a path, with an optional default interface."""

    async def get(self, prop: str, *, interface: str | None = None, fresh: bool = False) -> Any:
        """The value of a property. Read from the cache the layer keeps for the interface (filled
        by one ``GetAll`` when the interface is first used, kept current from
        ``PropertiesChanged``); ``fresh=True`` asks the service (for a property that does not emit
        changes). Plain Python values: a ``Variant`` is unwrapped."""
        ...

    async def call(
        self,
        method: str,
        args: Sequence[Any] = (),
        signature: str = "",
        *,
        interface: str | None = None,
        timeout: float = CALL_TIMEOUT,
    ) -> Any:
        """Call a method. ``signature`` is the D-Bus type string of ``args``; an argument of type
        ``v`` is written as a ``(signature, value)`` pair (``("s", "")``). The result is the
        reply's one value, ``None`` for no value, or a tuple for several. Raises
        :class:`ServiceTimeout`, :class:`ServiceUnavailable` or :class:`ServiceError`."""
        ...

    async def set(
        self,
        prop: str,
        value: Any,
        signature: str,
        *,
        interface: str | None = None,
        timeout: float = CALL_TIMEOUT,
    ) -> None:
        """Write a property (``org.freedesktop.DBus.Properties.Set``); ``signature`` is the D-Bus
        type of the value. The cache follows from the service's ``PropertiesChanged``, not from
        this call. Raises as :meth:`call` does."""
        ...

    def on_property_changed(
        self, callback: PropertyCallback, *, interface: str | None = None, initial: bool = True
    ) -> Subscription:
        """``callback(changed)`` with a mapping of property name to value, on the service thread.
        The first call (unless ``initial=False``) holds every property, once the layer has read
        them; later calls hold what ``PropertiesChanged`` reports. When the service returns after
        it left the bus, the callback gets every property again (before ``on_service_found``)."""
        ...

    def on_signal(
        self, member: str, callback: SignalCallback, *, interface: str | None = None
    ) -> Subscription:
        """``callback(*body)`` for each signal of ``member`` from this object, on the service
        thread."""
        ...


class Bus(Protocol):
    def proxy(
        self, name: str, path: str, interface: str | None = None, *, optional: bool = False
    ) -> Proxy:
        """A proxy for the object ``path`` of the service ``name``. The layer watches ``name`` from
        now on (a well-known name): when its owner goes away the module gets
        ``on_service_lost(name)`` and ``available`` false, and ``on_service_found(name)`` with
        ``available`` true when an owner returns. An ``optional`` service (a value the module can
        do without) still gets the hooks, but does not count in ``available``, and its absence is
        only a debug line in the log."""
        ...

    def watch_prefix(
        self, prefix: str, on_added: Callable[[str], None], on_removed: Callable[[str], None]
    ) -> Subscription:
        """Follow every well-known name that starts with ``prefix`` (``org.mpris.MediaPlayer2.``):
        ``on_added(name)`` for each that has an owner now and for each that appears later,
        ``on_removed(name)`` when one goes. One ``ListNames`` at the start and one
        ``NameOwnerChanged`` rule, no polling; the callbacks run on the service thread. The names
        are not made services of the module: make a proxy for each with ``optional=True`` (a
        player may leave at any time without the module being unavailable). ``available`` stays
        true while the bus can be reached."""
        ...

    def forget(self, name: str) -> None:
        """Let go of a name the module made a proxy for (a player that left): its watch and its
        cached properties. Cancel the subscriptions on it first."""
        ...

    def state(self, name: str) -> ServiceState:
        """The state of a service this module has made a proxy for (any thread)."""
        ...

    def run[T](self, coro: Coroutine[Any, Any, T]) -> concurrent.futures.Future[T]:
        """Run ``coro`` on the service thread. Never blocks; any thread. An exception that nobody
        reads from the future is logged with the module's name."""
        ...

    def run_blocking[T](self, coro: Coroutine[Any, Any, T], timeout: float | None = None) -> T:
        """Run ``coro`` on the service thread and wait for it. Raises :class:`BlockingCallError`
        on the loop thread and on the service thread. ``timeout`` is for the whole wait; the
        calls inside have their own."""
        ...


class ModuleDBus(Protocol):
    """``ctx.dbus``. Nothing connects until a proxy is used; the system bus opens on the first
    use that needs it."""

    @property
    def available(self) -> bool:
        """True while every service this module made a proxy for has an owner (any thread). A
        service that is not read yet counts as absent, so this is false right after ``proxy()``;
        the layer sends ``available`` with ``ctx.send`` each time this value changes (the
        empty-state convention: ``Children`` wrap in ``If: available``). A module that also
        needs a condition of its own (a battery that is not present) sends a key of its own and
        combines the two in its layout; it does not send ``available`` itself."""
        ...

    def session(self) -> Bus: ...

    def system(self) -> Bus: ...

    def close(self) -> None:
        """End every subscription and watch of the module (the shell calls it when the module
        stops)."""
        ...


class ServiceHooks(Protocol):
    """The module's hooks, called on the loop thread."""

    def lost(self, name: str) -> None: ...

    def found(self, name: str) -> None: ...


class DBusPort(Protocol):
    """What the module host needs of the layer: one helper per module."""

    def for_module(
        self,
        module: str,
        send: Callable[[str, object], None],
        hooks: ServiceHooks,
    ) -> ModuleDBus: ...


# -- the sound server (Audio Module, ADR-0021 Audio Access) ---------------------------------------


class AudioError(Exception):
    """A call to the sound server failed (the server said no, or it did not answer)."""


class AudioUnavailable(AudioError):
    """There is no sound server to call (none is running, or it went away)."""


@dataclass(frozen=True, slots=True)
class Output:
    """One output (a sink) of the sound server."""

    name: str  # the sink's name: what ``set_output`` takes
    description: str
    kind: str  # SPEAKER, HEADPHONES, HDMI, BLUETOOTH or OTHER (Audio Module > Kind and Icon)


@dataclass(frozen=True, slots=True)
class AudioState:
    """What the Audio module shows. ``volume`` is the mean of the default output's channels in
    percent, as the server reports it (above 100 stays above 100)."""

    output: Output | None  # the default output; ``None`` when the server has no sink
    volume: int
    muted: bool
    has_mic: bool  # a default input exists
    mic_muted: bool
    outputs: tuple[Output, ...]  # every output, in the server's order


AudioCallback = Callable[[AudioState | None], None]


class ModuleAudio(Protocol):
    """``ctx.audio``: the sound server, through the shell's own client of the PulseAudio native
    protocol. Nothing connects until it is first used. Everything runs on the ``dbus`` service
    thread's loop: a callback runs there (short, never blocking: it calls ``ctx.send``), and a
    setter returns a future at once from any thread. The shell cancels a module's subscription
    when the module stops."""

    @property
    def available(self) -> bool:
        """True while a sound server is connected (any thread)."""
        ...

    @property
    def state(self) -> AudioState | None:
        """The last state, or ``None`` while there is no server (any thread)."""
        ...

    def on_changed(self, callback: AudioCallback) -> Subscription:
        """``callback(state)`` on the service thread: once with the current state (``None`` while
        there is no server) as soon as it is known, then each time the state differs from the
        last one handed over. ``None`` means the server went away; it comes back as a state."""
        ...

    def set_volume(self, percent: float) -> concurrent.futures.Future[None]:
        """Set every channel of the default output so that their mean is ``percent`` (clamped to 0
        to 100); a balance between the channels is kept by scaling them."""
        ...

    def step(self, delta: float) -> concurrent.futures.Future[None]:
        """``set_volume`` of the volume plus ``delta``, clamped to 0 to 100. Steps that follow each
        other before the server's event arrives add up (the base is what the last call wrote)."""
        ...

    def set_muted(self, muted: bool) -> concurrent.futures.Future[None]: ...

    def toggle_mute(self) -> concurrent.futures.Future[None]: ...

    def toggle_mic(self) -> concurrent.futures.Future[None]:
        """Toggle the default input's mute."""
        ...

    def set_output(self, name: str) -> concurrent.futures.Future[None]:
        """Make the output ``name`` the default. Raises :class:`AudioError` in the future if the
        server has no such output."""
        ...

    def close(self) -> None:
        """Cancel every subscription of the module."""
        ...


class AudioPort(Protocol):
    """What the module host needs of the sound service: one helper per module."""

    def for_module(self, module: str) -> ModuleAudio: ...


# -- icons from the desktop's theme and the tray host (Tray Module) --------------------------------


class ModuleIcons(Protocol):
    """``ctx.icons``: icon names and pixmaps become something a block's ``Icon:`` shows (Tray Module
    > Icons). A reference is an SVG document (text that starts with ``<``) or ``pixels:...``, the
    name of decoded pixels the shell holds for the engine; never a path. The calls read files
    (a theme's ``index.theme``, the icon, a png's bytes) and may build the index of a theme chain
    the first time (under 100 ms): call them from the ``dbus`` thread or a worker, never the loop
    thread. A lookup after that reads no folder; its result is cached by (name, size, theme path)
    and the file's modification time."""

    def theme_icon(self, name: str, size: int, theme_path: str | None = None) -> str | None:
        """``name`` as the freedesktop icon theme spec finds it: in ``theme_path`` (an item's
        ``IconThemePath``, when set), then in the user's theme, the themes it inherits and
        ``hicolor``, then in ``/usr/share/pixmaps``. A scalable SVG is preferred; otherwise the png
        whose size is nearest above ``size``. ``None`` when no theme has it. An absolute path to an
        image file is read as it is."""
        ...

    def pixmap_icon(
        self, pixmaps: Sequence[Sequence[Any]], size: int, source: str = ""
    ) -> str | None:
        """The pixmap of ``pixmaps`` (``(width, height, bytes)``: ARGB32, network byte order, the
        StatusNotifierItem way) nearest above ``size`` (else the largest), as RGBA. A pixmap whose
        length is not width times height times 4 is ignored, with one warning naming ``source``.
        ``None`` when none is usable."""
        ...

    def png_icon(self, data: bytes, source: str = "") -> str | None:
        """The pixels of png (or other image) ``data``, as a reference; ``None`` (with one warning
        naming ``source``) when it cannot be decoded."""
        ...


class IconsPort(Protocol):
    """What the module host needs of the icon service."""

    def for_module(self, module: str) -> ModuleIcons: ...


HostCallback = Callable[[bool], None]


class ModuleTray(Protocol):
    """``ctx.tray``: the shell as a StatusNotifier host. The shell owns the bus name
    ``org.kde.StatusNotifierHost-<pid>`` and registers it with the watcher
    (``RegisterStatusNotifierHost``), again whenever the watcher comes back or the bus does. A
    module cannot take any other name: the name is the service's own."""

    def on_host(self, callback: HostCallback) -> Subscription:
        """``callback(hosted)`` on the service thread: ``True`` once the shell is registered with
        a watcher, ``False`` while it is not (no watcher on the bus, or the host name could not be
        had). Called when the state is known and each time it changes. The first subscription
        starts the host; the last one cancelled gives the name up."""
        ...

    def close(self) -> None:
        """Cancel every subscription of the module."""
        ...


class TrayPort(Protocol):
    """What the module host needs of the tray host service."""

    def for_module(self, module: str) -> ModuleTray: ...
