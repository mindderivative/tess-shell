"""The window list for modules (``ctx.windows``; Tasks Module > Needs from the Shell).

One service per shell over the KWin script (``services.kwin``). It counts the subscribers: the
script is told to send the window list while at least one module is subscribed and to stop when the
last one cancels, so with no Tasks module in use no title, class or id ever reaches the shell. The
list and every callback live on the loop thread (the KWin service hands each new list over with
``call_soon``); the actions (activate, minimise, close) are one-shot KWin scripts started from any
thread and never block.
"""

from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future

from loguru import logger

from tess_shell.services.api import ModuleWindows, Subscription, WindowInfo
from tess_shell.services.kwin import KWinService


class WindowService:
    def __init__(self, kwin: KWinService) -> None:
        self._kwin = kwin
        self._listeners: list[tuple[str, Callable[[], None]]] = []
        self._list: tuple[WindowInfo, ...] = ()
        self._ready = False
        # told of an exception a module's callback raised: (module, what, exception)
        self.on_module_error: Callable[[str, str, Exception], None] | None = None
        kwin.on_windows = self._windows
        kwin.on_state = self._state

    def for_module(self, module: str) -> ModuleWindows:
        """The helper for one module (``ctx.windows``)."""
        return _ModuleWindows(self, module)

    # -- state (loop thread) --------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return self._kwin.available

    @property
    def ready(self) -> bool:
        return self._ready

    @property
    def subscribers(self) -> int:
        return len(self._listeners)

    def list(self) -> tuple[WindowInfo, ...]:
        return self._list

    def _windows(self, windows: tuple[WindowInfo, ...]) -> None:
        if not self._listeners:  # the last module left while the list was on its way
            return
        self._list, self._ready = windows, True
        self._notify()

    def _state(self) -> None:
        self._notify()

    def _notify(self) -> None:
        for module, callback in list(self._listeners):
            try:
                callback()
            except Exception as exc:
                logger.opt(exception=True).error(f"windows: a callback of {module} raised")
                if self.on_module_error is not None:
                    self.on_module_error(module, "a windows callback", exc)

    # -- subscribing ----------------------------------------------------------------------------

    def subscribe(self, module: str, callback: Callable[[], None]) -> Subscription:
        entry = (module, callback)
        self._listeners.append(entry)
        if len(self._listeners) == 1:
            self._list, self._ready = (), False  # a list from before is stale
            self._kwin.set_windows_wanted(True)
        return _Subscription(self, entry)

    def unsubscribe(self, entry: tuple[str, Callable[[], None]]) -> None:
        if entry in self._listeners:
            self._listeners.remove(entry)
            if not self._listeners:
                self._kwin.set_windows_wanted(False)
                self._list, self._ready = (), False

    # -- acting (any thread) --------------------------------------------------------------------

    def act(self, kind: str, window_id: str) -> Future[bool]:
        return self._kwin.act(kind, window_id)


class _Subscription:
    def __init__(self, service: WindowService, entry: tuple[str, Callable[[], None]]) -> None:
        self._service = service
        self._entry = entry

    def cancel(self) -> None:
        self._service.unsubscribe(self._entry)


class _ModuleWindows:
    """``ctx.windows`` of one module."""

    def __init__(self, service: WindowService, module: str) -> None:
        self._service = service
        self._module = module
        self._subs: list[Subscription] = []

    @property
    def available(self) -> bool:
        return self._service.available

    @property
    def ready(self) -> bool:
        return self._service.ready

    def list(self) -> tuple[WindowInfo, ...]:
        return self._service.list()

    def on_changed(self, callback: Callable[[], None]) -> Subscription:
        sub = self._service.subscribe(self._module, callback)
        self._subs.append(sub)
        return sub

    def activate(self, window_id: str) -> Future[bool]:
        return self._service.act("activate", window_id)

    def minimize(self, window_id: str) -> Future[bool]:
        return self._service.act("minimize", window_id)

    def close_window(self, window_id: str) -> Future[bool]:
        return self._service.act("close", window_id)

    def close(self) -> None:
        for sub in self._subs:
            sub.cancel()
        self._subs.clear()
