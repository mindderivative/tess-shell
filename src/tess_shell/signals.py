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
    def __init__(
        self,
        stop: Callable[[], None],
        force: Callable[[], NoReturn],
        reload: Callable[[], None] | None = None,
    ) -> None:
        self._stop = stop
        self._force = force
        self._reload = reload
        self._r, self._w = socket.socketpair()
        self._previous: dict[int, object] = {}
        self._old_fd = -1
        self._thread = threading.Thread(target=self._loop, name="signal-watcher", daemon=True)
        self._seen = False

    def start(self) -> None:
        """Must be called from the main thread."""
        self._w.setblocking(False)
        self._old_fd = signal.set_wakeup_fd(self._w.fileno(), warn_on_full_buffer=False)
        wanted = [signal.SIGTERM, signal.SIGINT]
        if self._reload is not None:
            wanted.append(signal.SIGHUP)
        for sig in wanted:
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
            for number in data:
                if number == signal.SIGHUP:
                    if self._reload is not None:
                        self._reload()
                    continue
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


class LoopStopper:
    """Ask an event loop to stop, even when the request comes before the loop has started.

    ``try_stop`` is ``LoopHandle.stop``: it returns False when no loop is running, and a stop is
    not remembered. A callback queued before the loop starts is not drained until the loop is next
    woken, so ``call_soon`` cannot cover the gap. Instead, retry in a thread of its own (so a
    second signal can still be read) until the loop has started or has finished. Nothing runs
    unless a stop was requested, so an idle shell holds no timer.
    """

    def __init__(self, try_stop: Callable[[], bool], interval: float = 0.05) -> None:
        self._try_stop = try_stop
        self._interval = interval
        self.requested = threading.Event()
        self.done = threading.Event()

    def request(self) -> None:
        self.requested.set()
        if self._try_stop():
            return
        threading.Thread(target=self._retry, name="stop-retry", daemon=True).start()

    def _retry(self) -> None:
        while not self.done.wait(self._interval):
            if self._try_stop():
                return

    def loop_finished(self) -> None:
        self.done.set()
