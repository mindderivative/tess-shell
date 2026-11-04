"""Turn SIGTERM and SIGINT into a clean stop, and a second signal into a forced exit.

The event loop blocks the main thread inside the engine, so Python signal handlers would not run.
Instead the C-level handler writes each signal number to a socket (``set_wakeup_fd``) and a
daemon thread reads it. Standard library only.
"""

from __future__ import annotations

import signal
import socket
import threading
from collections.abc import Callable
from types import FrameType
from typing import NoReturn


def _ignore(signum: int, frame: FrameType | None) -> None:
    """Python needs a handler installed for the C handler to write the wakeup fd."""


class SignalWatcher:
    def __init__(self, stop: Callable[[], None], force: Callable[[], NoReturn]) -> None:
        self._stop = stop
        self._force = force
        self._r, self._w = socket.socketpair()
        self._previous: dict[int, object] = {}
        self._old_fd = -1
        self._thread = threading.Thread(target=self._loop, name="signal-watcher", daemon=True)
        self._seen = False

    def start(self) -> None:
        """Must be called from the main thread."""
        self._w.setblocking(False)
        self._old_fd = signal.set_wakeup_fd(self._w.fileno(), warn_on_full_buffer=False)
        for sig in (signal.SIGTERM, signal.SIGINT):
            self._previous[sig] = signal.signal(sig, _ignore)
        self._thread.start()

    def _loop(self) -> None:
        while True:
            try:
                data = self._r.recv(64)
            except OSError:
                return
            if not data:
                return
            for _ in data:
                if self._seen:
                    self._force()
                self._seen = True
                self._stop()

    def close(self) -> None:
        """Restore the previous handlers. Must be called from the main thread."""
        signal.set_wakeup_fd(self._old_fd)
        for sig, handler in self._previous.items():
            signal.signal(sig, handler)  # type: ignore[arg-type]
        self._previous.clear()
        self._w.close()  # the reader sees end of file and returns
        self._thread.join(timeout=2)
        self._r.close()
