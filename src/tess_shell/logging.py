"""Loguru setup: a console sink and a daily log file (Logging and Diagnostics).

Imports only the standard library and Loguru. ``Capture_Stderr`` is stored by the settings but has
no behaviour yet, and the standard ``logging`` and ``warnings`` modules are not routed here.
"""

from __future__ import annotations

import os
import re
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from tess_shell.config.settings import LoggingSettings
    from tess_shell.schema.findings import Finding

_FILE_NAME = re.compile(r"^log_(\d{4})-(\d{2})-(\d{2})\.log$")
_LINE = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[source]} | {extra[location]} | {message}"
)
_LINE_JOURNAL = "{level: <8} | {extra[source]} | {extra[location]} | {message}"


@dataclass
class LogState:
    settings: LoggingSettings
    directory: Path | None = None
    file_sink: int | None = None
    console_sink: int | None = None
    timer: threading.Timer | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    closed: bool = False
    quiet: bool = False
    level: str | None = None  # set by ``set_level`` (the control interface): not the file's own


_state: LogState | None = None


def seconds_until_midnight(now: datetime) -> float:
    """Seconds from ``now`` (local, naive) to the next local midnight."""
    nxt = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return (nxt - now).total_seconds()


def log_path(directory: Path, now: datetime) -> Path:
    return directory / f"log_{now:%Y-%m-%d}.log"


def _add_file_sink(state: LogState, path: Path) -> int:
    # Pre-create 0o600 so Loguru's append open keeps the mode.
    os.close(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600))
    json_ = state.settings.format == "JSON"
    return logger.add(
        path,
        level=state.level or state.settings.level,
        format=_LINE,
        serialize=json_,
        enqueue=True,
        diagnose=state.settings.diagnose,
        backtrace=False,
        colorize=False,
    )


def apply_retention(directory: Path, days: int, now: datetime) -> list[Path]:
    """Delete ``log_YYYY-MM-DD.log`` files older than ``days`` days; nothing else is touched."""
    cutoff = now.date() - timedelta(days=days)
    removed: list[Path] = []
    for entry in directory.iterdir():
        m = _FILE_NAME.match(entry.name)
        if not m or not entry.is_file():
            continue
        try:
            day = datetime(int(m[1]), int(m[2]), int(m[3])).date()
        except ValueError:
            continue
        if day < cutoff:
            entry.unlink(missing_ok=True)
            removed.append(entry)
    return removed


def _schedule(state: LogState) -> None:
    if state.closed:
        return
    delay = seconds_until_midnight(datetime.now()) + 1.0
    timer = threading.Timer(delay, swap_file_sink)
    timer.daemon = True
    state.timer = timer
    timer.start()


def swap_file_sink(now: datetime | None = None) -> None:
    """Move the file sink to today's file and apply retention; any failure keeps the old sink."""
    state = _state
    if state is None or state.directory is None:
        return
    now = now or datetime.now()
    with state.lock:
        if state.closed:
            return
        try:
            new = _add_file_sink(state, log_path(state.directory, now))
            old, state.file_sink = state.file_sink, new
            if old is not None:
                logger.remove(old)
            if state.settings.retention is not None:
                apply_retention(state.directory, state.settings.retention, now)
        except Exception as exc:
            logger.warning(f"could not start the next log file: {exc}")
        _schedule(state)


def _add_console_sink(state: LogState) -> None:
    journal = "JOURNAL_STREAM" in os.environ
    state.console_sink = logger.add(
        sys.stderr,
        level="WARNING" if state.quiet else (state.level or state.settings.level),
        format=_LINE_JOURNAL if journal else _LINE,
        enqueue=True,
        colorize=sys.stderr.isatty(),
        diagnose=state.settings.diagnose,
        backtrace=False,
        filter=lambda record: not record["extra"].get("file_only"),
    )


def set_level(level: str) -> bool:
    """Change the level of the console and the file sink until the next ``configure_logging``
    (the control interface's ``SetLogLevel``; the reload of ``settings.tdl`` puts the file's level
    back). ``False`` when logging is not configured."""
    state = _state
    if state is None or state.closed:
        return False
    with state.lock:
        state.level = level
        if state.file_sink is not None and state.directory is not None:
            logger.remove(state.file_sink)
            state.file_sink = _add_file_sink(state, log_path(state.directory, datetime.now()))
        if state.console_sink is not None:
            logger.remove(state.console_sink)
            _add_console_sink(state)
    return True


def level_overridden() -> bool:
    """Whether ``set_level`` changed the level since logging was configured."""
    return _state is not None and _state.level is not None


# what hears every finding the shell logs: the control interface's last errors and its
# ``ErrorReported`` signal (any thread; a sink must not block)
finding_sinks: list[Callable[[Finding], None]] = []


def note_finding(finding: Finding) -> None:
    for sink in list(finding_sinks):
        try:
            sink(finding)
        except Exception:  # a listener never stops the logging of an error
            logger.opt(exception=True).debug("a finding listener raised")


def configure_logging(
    settings: LoggingSettings, *, quiet: bool = False, default_directory: Path | None = None
) -> LogState:
    """Replace Loguru's sinks with the console sink and the daily file."""
    global _state
    shutdown_logging()
    logger.remove()
    logger.configure(extra={"source": "shell", "location": "-"})
    state = LogState(settings=settings, quiet=quiet)
    _state = state
    directory = settings.directory or default_directory
    failure: str | None = None
    now = datetime.now()
    if directory is not None:
        try:
            directory.mkdir(parents=True, exist_ok=True, mode=0o700)
            state.file_sink = _add_file_sink(state, log_path(directory, now))
            state.directory = directory
            if settings.retention is not None:
                apply_retention(directory, settings.retention, now)
        except OSError as exc:
            failure = f"cannot write logs to {directory}: {exc.strerror or exc}; console only"
    else:
        failure = "no log directory; console only"
    if settings.console or state.file_sink is None:
        _add_console_sink(state)
    if failure:
        logger.warning(failure)
    if state.file_sink is not None:
        _schedule(state)
    return state


def log_finding(finding: Finding) -> None:
    note_finding(finding)
    location = f"{finding.file}:{finding.line}:{finding.column} {finding.rule}"
    # file only: the command prints the findings itself, with source lines and hints
    logger.bind(
        file_only=True,
        location=location,
        file=finding.file,
        line=finding.line,
        column=finding.column,
        rule=finding.rule,
        severity=finding.severity,
    ).log(finding.severity.upper(), finding.message)


def current_state() -> LogState | None:
    return _state


def shutdown_logging() -> None:
    """Stop the midnight timer and flush and remove every sink."""
    global _state
    state, _state = _state, None
    if state is not None:
        state.closed = True
        if state.timer is not None:
            state.timer.cancel()
    logger.remove()
