"""The watchdog: detect a hung event loop, log who hangs it, and let systemd restart the shell
(Crash Recovery and Watchdog > Detecting a Hang, The systemd side).

The loop cannot interrupt itself, so a thread watches a heartbeat. Each second the thread asks the
loop (``call_soon``) to store a counter and a monotonic time, and reads how old the last store is:

* **2 s:** one warning ``loop stalled for N s`` naming the module, the entry point and how long that
  callback has been running (``CallbackRecord.running()``), the tracebacks of every thread in the
  log, then the warning again every 5 s while it lasts;
* **10 s:** under systemd with a watchdog (``NOTIFY_SOCKET`` and ``WATCHDOG_USEC`` are set) the
  shell sends ``WATCHDOG=trigger`` and the manager terminates it with ``SIGABRT``; otherwise it
  logs ``loop stalled for 10 s, no supervisor can restart it`` and dumps the tracebacks every 30 s.
  Nothing at all is sent to ``NOTIFY_SOCKET`` when ``WATCHDOG_USEC`` is unset.

Pings (``WATCHDOG=1``) go out every half ``WATCHDOG_USEC``, only while the heartbeat is less than
5 s old, so a stalled loop stops the pings by itself. The thread never touches a node or a
module: it reads two numbers, queues one callback, and writes one datagram.

The times are a ``Timing``. ``TESS_SHELL_TEST_WATCHDOG_SCALE`` (a number; only the tests set it)
multiplies all of them, so a test does not wait 10 s for the decision.
"""

from __future__ import annotations

import faulthandler
import tempfile
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass

from loguru import logger

from tess_shell.modules.running import RunningCallback
from tess_shell.notify import WATCHDOG, WATCHDOG_TRIGGER, notify, notify_address, watchdog_interval

SCALE_VARIABLE = "TESS_SHELL_TEST_WATCHDOG_SCALE"


@dataclass(frozen=True, slots=True)
class Timing:
    """Seconds. ``tick`` is the period of the heartbeat and of the thread."""

    tick: float = 1.0
    warn: float = 2.0  # the first warning
    repeat: float = 5.0  # the warning again, while the stall lasts
    restart: float = 10.0  # the shell asks to be restarted
    dump_every: float = 30.0  # tracebacks again, with no supervisor
    fresh: float = 5.0  # a heartbeat younger than this lets the pings go on

    def scaled(self, factor: float) -> Timing:
        return Timing(*(getattr(self, f) * factor for f in self.__slots__))


def timing_from_environment(environ: Mapping[str, str]) -> Timing:
    """The default times, scaled by ``TESS_SHELL_TEST_WATCHDOG_SCALE`` when it is set to a positive
    number."""
    text = environ.get(SCALE_VARIABLE, "")
    try:
        factor = float(text)
    except ValueError:
        return Timing()
    if factor <= 0:
        return Timing()
    logger.warning(f"watchdog: all times scaled by {factor:g} ({SCALE_VARIABLE} is a test setting)")
    return Timing().scaled(factor)


class Heartbeat:
    """The counter and the monotonic time the loop stores. ``beat`` runs on the loop thread; the
    watchdog thread reads ``last``. A float store is one attribute write: no lock."""

    __slots__ = ("_clock", "count", "last", "pending")

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self.count = 0
        self.last = clock()
        self.pending = False  # a beat is queued on the loop and has not run yet

    def beat(self) -> None:
        self.count += 1
        self.last = self._clock()
        self.pending = False


def dump_tracebacks() -> str:
    """The Python traceback of every thread, as text (``faulthandler`` writes to a file
    descriptor, so it writes to a temporary file that is read back)."""
    with tempfile.TemporaryFile("w+", encoding="utf-8") as handle:
        faulthandler.dump_traceback(file=handle, all_threads=True)
        handle.seek(0)
        return handle.read().rstrip()


class Watchdog:
    """See the module's docstring. ``poll`` is one look (the thread calls it every ``tick``);
    a test calls it with its own clock."""

    def __init__(
        self,
        heartbeat: Heartbeat,
        running: Callable[[], RunningCallback | None],
        call_soon: Callable[[Callable[[], None]], None],
        *,
        interval: float | None = None,
        supervised: bool = False,
        timing: Timing | None = None,
        clock: Callable[[], float] = time.monotonic,
        send: Callable[[str], bool | None] = notify,
        dump: Callable[[], str] = dump_tracebacks,
    ) -> None:
        """``interval`` is ``WATCHDOG_USEC`` in seconds, ``supervised`` whether ``NOTIFY_SOCKET`` is
        set as well (both are needed to ping and to ask for a restart)."""
        self.heartbeat = heartbeat
        self.timing = timing or Timing()
        self._running = running
        self._call_soon = call_soon
        self._clock = clock
        self._send = send
        self._dump = dump
        self.interval = interval if supervised else None
        self._next_ping = 0.0
        self._stalled_since: float | None = None
        self._last_warning: float | None = None
        self._last_dump = 0.0
        self._decided = False
        self._stopping = False
        self._ping_failed = False
        self._thread: threading.Thread | None = None
        self._done = threading.Event()
        # one more look on each tick, on this thread: the shell's module processes read the record
        # of the callback each one is running (``modproc.supervisor``), so they cost no thread
        self.on_poll: Callable[[], None] | None = None

    @classmethod
    def from_environment(
        cls,
        heartbeat: Heartbeat,
        running: Callable[[], RunningCallback | None],
        call_soon: Callable[[Callable[[], None]], None],
        environ: Mapping[str, str],
    ) -> Watchdog:
        """The watchdog this process's environment asks for (systemd's ``WATCHDOG_USEC`` and
        ``NOTIFY_SOCKET``, and the test scale)."""
        interval = watchdog_interval(environ)
        supervised = interval is not None and notify_address(environ) is not None
        if interval is not None and not supervised:
            logger.warning("watchdog: WATCHDOG_USEC is set but NOTIFY_SOCKET is not; no pings")
        return cls(
            heartbeat,
            running,
            call_soon,
            interval=interval,
            supervised=supervised,
            timing=timing_from_environment(environ),
        )

    @property
    def supervised(self) -> bool:
        return self.interval is not None

    # -- the thread ------------------------------------------------------------------------------

    def start(self) -> None:
        """Begin: the loop calls this on its first turn (the heartbeat starts when the loop does,
        after the start sequence, so the start is not judged). Pings once at once."""
        if self._thread is not None:
            return
        self.begin()
        self._thread = threading.Thread(target=self._run, name="watchdog", daemon=True)
        self._thread.start()

    def begin(self) -> None:
        """The first beat and the first ping, with no thread (``start`` runs the thread after)."""
        self.heartbeat.beat()
        if self.interval is not None:
            self._ping(self._clock())

    def _period(self) -> float:
        if self.interval is None:
            return self.timing.tick
        return max(0.001, min(self.timing.tick, self.interval / 4))

    def _run(self) -> None:
        period = self._period()
        while not self._done.wait(period):
            try:
                self.poll()
            except Exception:
                logger.opt(exception=True).error("watchdog: a check failed")

    def begin_stop(self) -> None:
        """The loop has ended or is ending: the stop sequence is not a stall. The pings go on at
        their pace (a slow stop is bounded by its own timeouts), nothing is judged."""
        self._stopping = True

    def stop(self) -> None:
        self._stopping = True
        self._done.set()
        thread = self._thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)

    # -- one look --------------------------------------------------------------------------------

    def poll(self) -> None:
        if self.on_poll is not None:
            try:
                self.on_poll()
            except Exception:
                logger.opt(exception=True).debug("watchdog: the extra look raised")
        now = self._clock()
        beat = self.heartbeat
        age = now - beat.last
        if self._stopping:
            if self.interval is not None and now >= self._next_ping:
                self._ping(now)
            return
        if not beat.pending:
            beat.pending = True
            self._call_soon(beat.beat)
        if self.interval is not None and now >= self._next_ping and age < self.timing.fresh:
            self._ping(now)
        if age >= self.timing.warn:
            self._stalled(now, age)
        elif self._stalled_since is not None:
            logger.info(f"loop is running again after {now - self._stalled_since:.1f} s")
            self._stalled_since = None
            self._decided = False

    def _ping(self, now: float) -> None:
        assert self.interval is not None
        self._next_ping = now + self.interval / 2
        sent = self._send(WATCHDOG)
        if sent is False and not self._ping_failed:
            self._ping_failed = True
            logger.warning("watchdog: could not send WATCHDOG=1 to NOTIFY_SOCKET")

    def _stalled(self, now: float, age: float) -> None:
        timing = self.timing
        if self._stalled_since is None:
            self._stalled_since = self.heartbeat.last
            self._last_warning = None
        first = self._last_warning is None
        if self._last_warning is None or now - self._last_warning >= timing.repeat:
            self._last_warning = now
            logger.warning(self._words(now, age))
            if first:
                self._dumped(now)
        if age >= timing.restart:
            self._decide(now, age)

    def _words(self, now: float, age: float) -> str:
        head = f"loop stalled for {int(age)} s"
        callback = self._running()
        if callback is None:
            return f"{head}: no module callback is running (the shell or the engine holds the loop)"
        return (
            f"{head}: module {callback.module}, entry point {callback.entry}, "
            f"running for {now - callback.started:.1f} s"
        )

    def _decide(self, now: float, age: float) -> None:
        if not self._decided:
            self._decided = True
            if self.interval is not None:
                logger.error(
                    f"loop stalled for {int(age)} s, asking systemd to restart the shell "
                    "(WATCHDOG=trigger)"
                )
                self._dumped(now)
                self._send(WATCHDOG_TRIGGER)
            else:
                logger.error(
                    f"loop stalled for {self.timing.restart:g} s, no supervisor can restart it"
                )
                self._dumped(now)
        elif self.interval is None and now - self._last_dump >= self.timing.dump_every:
            self._dumped(now)

    def _dumped(self, now: float) -> None:
        self._last_dump = now
        logger.warning(f"the traceback of every thread:\n{self._dump()}")
