"""The read side of the crash record: what ``tesserae-shell status`` says about crashes, from the
files in the state folder (Crash Recovery and Watchdog > The Crash Record).

Standard library only, and nothing of the shell: the command-line client imports it, and the client
must stay fast and import neither the engine nor the parsers (``tests/test_client.py``). The writer
of the files is ``tess_shell.recovery``, which imports this module for the names they share.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

MARKER = "running"
STATE_FILE = "recovery.json"

UNCLEAN_LIMIT = 3  # unclean starts in a row that make the next start a safe start ...
UNCLEAN_WINDOW = 600.0  # ... when they all fall within this many seconds


def state_folder() -> Path:
    """``$XDG_STATE_HOME/tesserae-shell``, else ``~/.local/state/tesserae-shell``: the same folder
    as ``tess_shell.config.paths.state_dir`` (the client may not import that package; a test keeps
    the two equal)."""
    xdg = os.environ.get("XDG_STATE_HOME", "")
    if xdg and os.path.isabs(xdg):
        return Path(xdg) / "tesserae-shell"
    return Path.home() / ".local" / "state" / "tesserae-shell"


@dataclass(frozen=True, slots=True)
class Summary:
    """The facts ``status`` shows: ``unclean`` starts since the last clean stop, the time of the
    ``last_crash`` (``None`` when there never was one) and whether the next start would be a safe
    start."""

    unclean: int
    last_crash: float | None
    next_safe: bool


def iso(moment: float | None) -> str | None:
    """A time as ``status --json`` prints it: local, ISO 8601, whole seconds."""
    if moment is None:
        return None
    return datetime.fromtimestamp(moment).astimezone().isoformat(timespec="seconds")


def clock_text(moment: float) -> str:
    return datetime.fromtimestamp(moment).strftime("%Y-%m-%d %H:%M:%S")


def read_state(directory: Path) -> dict[str, object]:
    try:
        data = json.loads((directory / STATE_FILE).read_text(encoding="utf-8"))
    except OSError, ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def times_of(state: dict[str, object]) -> list[float]:
    raw = state.get("unclean")
    if not isinstance(raw, list):
        return []
    return [float(t) for t in raw if isinstance(t, int | float) and not isinstance(t, bool)]


def number_of(state: dict[str, object], key: str) -> float | None:
    value = state.get(key)
    return float(value) if isinstance(value, int | float) and not isinstance(value, bool) else None


def marker_id(directory: Path) -> str | None:
    try:
        data = json.loads((directory / MARKER).read_text(encoding="utf-8"))
    except OSError, ValueError:
        return None
    ident = data.get("id") if isinstance(data, dict) else None
    return str(ident) if isinstance(ident, str) else ""


def in_window(times: list[float], now: float) -> int:
    return sum(1 for t in times if now - t <= UNCLEAN_WINDOW)


def summary(directory: Path, *, shell_running: bool, now: float | None = None) -> Summary:
    """The recovery facts of ``directory``. With no shell running, a marker that is still there is
    one more unclean end that no start has counted yet."""
    now = time.time() if now is None else now
    state = read_state(directory)
    times = times_of(state)
    last = number_of(state, "last_crash")
    if not shell_running:
        ident = marker_id(directory)
        if ident is not None and ident != state.get("counted"):
            times = [*times, now]
            try:
                last = max(last or 0.0, (directory / MARKER).stat().st_mtime)
            except OSError:
                pass
    return Summary(len(times), last, in_window(times, now) >= UNCLEAN_LIMIT)
