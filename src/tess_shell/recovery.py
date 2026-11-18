"""What the shell keeps so that a crash leaves evidence and a crash loop stops hiding its cause
(Crash Recovery and Watchdog > The Crash Record, A Crash Loop).

Three small files in the state directory (``$XDG_STATE_HOME/tesserae-shell``):

* ``running``: the unclean-exit marker. Written when a run starts (after it holds the instance
  lock), removed when it ends in a way the shell chose. A start that finds it knows the run before
  it ended uncleanly (``SIGKILL``, the out-of-memory killer, a crash, the watchdog's ``SIGABRT``).
* ``recovery.json``: the times of the unclean starts since the last clean stop. Three of them
  within ten minutes make the next start a safe start (user modules are not loaded).
* ``crash.log``: ``faulthandler``'s file for a fatal signal and the traceback of an exception that
  reaches the top. The previous file is kept as ``crash.log.1`` and one older as ``crash.log.2``; a
  run that leaves it empty removes it, so clean runs never push a real crash record out.

``tess_shell.recovery_state`` reads the same files for ``tesserae-shell status`` with no shell
running (standard library only, imported by the client); this module writes them.
"""

from __future__ import annotations

import faulthandler
import json
import os
import tempfile
import time
import traceback
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import IO

from tess_shell.recovery_state import (
    MARKER,
    STATE_FILE,
    UNCLEAN_LIMIT,
    in_window,
    marker_id,
    number_of,
    read_state,
    times_of,
)

CRASH_LOG = "crash.log"

OLDER_CRASH_LOGS = 2  # crash.log.1 and crash.log.2; nothing older is kept
_KEPT_STARTS = 20  # times kept in recovery.json: more than the limit needs, fewer than a loop makes


@dataclass(frozen=True, slots=True)
class Start:
    """What this start found: ``unclean`` starts since the last clean stop (this one included
    when it found the marker), the ``previous`` run's marker time (``None``: it ended cleanly),
    whether this start is a ``safe`` start and the time of the ``last_crash`` on record."""

    unclean: int
    previous: float | None
    safe: bool
    last_crash: float | None = None


def _write(path: Path, text: str) -> None:
    """A temporary file in the same folder, then a rename: a kill leaves the old file or the new."""
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(name, path)
    except BaseException:
        Path(name).unlink(missing_ok=True)
        raise


class Recovery:
    """The files of one run. ``begin`` after the instance lock; ``finish`` or ``leave`` at the end;
    ``clock`` (wall seconds) is injectable."""

    def __init__(self, directory: Path, clock: Callable[[], float] = time.time) -> None:
        self.directory = directory
        self._clock = clock
        self._crash: IO[str] | None = None
        self.start = Start(0, None, False)

    # -- the marker and the count -------------------------------------------------------------

    def begin(self) -> Start:
        """Count an unclean end of the run before this one, decide on a safe start, write the
        marker. Never raises for a missing or corrupt file: an unreadable state is an empty one."""
        self.directory.mkdir(parents=True, exist_ok=True)
        now = self._clock()
        state = read_state(self.directory)
        times = times_of(state)
        last = number_of(state, "last_crash")
        counted = state.get("counted") if isinstance(state.get("counted"), str) else ""
        previous: float | None = None
        ident = marker_id(self.directory)
        if ident is not None:
            try:
                previous = (self.directory / MARKER).stat().st_mtime
            except OSError:
                previous = now
            if ident == "" or ident != counted:  # a marker some start already counted is not again
                times = [*times, now][-_KEPT_STARTS:]
                last = max(last or 0.0, previous, self._crash_time(previous))
                counted = ident
        safe = in_window(times, now) >= UNCLEAN_LIMIT
        marker = uuid.uuid4().hex
        _write(
            self.directory / STATE_FILE,
            json.dumps({"unclean": times, "last_crash": last, "counted": counted or ""}) + "\n",
        )
        _write(
            self.directory / MARKER,
            json.dumps({"id": marker, "pid": os.getpid(), "started": now}) + "\n",
        )
        self.start = Start(len(times), previous, safe, last)
        return self.start

    def _crash_time(self, floor: float) -> float:
        """When the crash file of the run that ended uncleanly was last written, if it holds
        anything (a fatal signal or a traceback is a better time than the run's start)."""
        try:
            info = (self.directory / CRASH_LOG).stat()
        except OSError:
            return 0.0
        return info.st_mtime if info.st_size > 0 and info.st_mtime >= floor else 0.0

    def finish(self) -> None:
        """A clean stop: the marker goes and the count starts again from zero."""
        state = read_state(self.directory)
        last = number_of(state, "last_crash")
        try:
            _write(
                self.directory / STATE_FILE,
                json.dumps({"unclean": [], "last_crash": last, "counted": ""}) + "\n",
            )
        except OSError:
            pass
        self.leave()

    def leave(self) -> None:
        """The run ends in a way the shell chose, with a code that is not a crash (a refused
        configuration, a lost compositor): the marker goes, the count stays."""
        (self.directory / MARKER).unlink(missing_ok=True)

    # -- the crash file -----------------------------------------------------------------------

    def open_crash_log(self) -> Path:
        """Keep the previous ``crash.log`` as ``crash.log.1`` (and the one before as ``.2``) when it
        holds anything, open a new one, and point ``faulthandler`` at it for every thread."""
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / CRASH_LOG
        try:
            used = path.stat().st_size > 0
        except OSError:
            used = False
        if used:
            for number in range(OLDER_CRASH_LOGS, 1, -1):
                older = self.directory / f"{CRASH_LOG}.{number - 1}"
                if older.exists():
                    os.replace(older, self.directory / f"{CRASH_LOG}.{number}")
            os.replace(path, self.directory / f"{CRASH_LOG}.1")
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        self._crash = os.fdopen(fd, "w", encoding="utf-8")
        faulthandler.enable(file=self._crash, all_threads=True)
        return path

    def record_exception(
        self,
        exc_type: type[BaseException],
        exc: BaseException,
        tb: TracebackType | None,
        where: str = "",
    ) -> None:
        """An exception that reached the top (or a thread's top): its traceback goes to the file."""
        handle = self._crash
        if handle is None:
            return
        try:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self._clock()))
            handle.write(f"unhandled exception{where} at {stamp}\n")
            traceback.print_exception(exc_type, exc, tb, file=handle)
            handle.flush()
        except OSError, ValueError:
            pass

    def close_crash_log(self) -> None:
        """The run is over: ``faulthandler`` lets go, and a file that holds nothing is removed."""
        handle, self._crash = self._crash, None
        if handle is None:
            return
        faulthandler.disable()
        try:
            handle.flush()
            empty = os.fstat(handle.fileno()).st_size == 0
            handle.close()
            if empty:
                (self.directory / CRASH_LOG).unlink(missing_ok=True)
        except OSError, ValueError:
            pass
