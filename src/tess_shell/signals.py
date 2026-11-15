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


class EarlyStop:
    """Hold the first SIGTERM or SIGINT of the start, until the real watcher can act on it.

    The shell logs ``starting`` long before the event loop and the ``SignalWatcher`` exist (it
    takes the lock, opens the registry, scans every shell file and imports the engine first). A
    SIGTERM in that time would hit the default action and kill the process with no clean stop. So
    the first signal is remembered (``requested``) and the start goes on; ``SignalWatcher.start``
    takes it over and stops the shell as it does for any signal. A second signal still forces an
    exit, so a start that hangs can be interrupted. Main thread only; ``uninstall`` puts the
    handlers back (and does nothing for one that is no longer ours).
    """

    def __init__(self, force: Callable[[], NoReturn]) -> None:
        self._force = force
        self.requested = threading.Event()
        self.previous: dict[int, object] = {}

    def install(self) -> None:
        for sig in (signal.SIGTERM, signal.SIGINT):
            self.previous[sig] = signal.signal(sig, self._handle)

    def _handle(self, signum: int, frame: FrameType | None) -> None:
        if self.requested.is_set():
            self._force()
        self.requested.set()

    def uninstall(self) -> None:
        for sig, handler in self.previous.items():
            if signal.getsignal(sig) == self._handle:
                signal.signal(sig, handler)  # type: ignore[arg-type]
        self.previous.clear()


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

    def start(self, early: EarlyStop | None = None) -> None:
        """Must be called from the main thread. ``early`` is the hold on a signal of the start: its
        handlers are replaced (the handlers to restore are the ones it replaced, not itself), and a
        signal it kept is acted on now, as a first signal."""
        self._w.setblocking(False)
        self._old_fd = signal.set_wakeup_fd(self._w.fileno(), warn_on_full_buffer=False)
        wanted = [signal.SIGTERM, signal.SIGINT]
        if self._reload is not None:
            wanted.append(signal.SIGHUP)
        for sig in wanted:
            replaced: object = signal.signal(sig, _ignore)
            if early is not None and sig in early.previous and replaced == early._handle:
                replaced = early.previous[sig]
            self._previous[sig] = replaced
        self._thread.start()
        if early is not None and early.requested.is_set():
            self._seen = True
            self._stop()

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
