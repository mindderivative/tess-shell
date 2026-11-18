"""The unclean-exit marker, the count of unclean starts, safe start and the crash file
(Crash Recovery and Watchdog > The Crash Record, A Crash Loop)."""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

from tess_shell.recovery import (
    CRASH_LOG,
    MARKER,
    STATE_FILE,
    UNCLEAN_WINDOW,
    Recovery,
    summary,
)


class Clock:
    def __init__(self, start: float = 1_000_000.0) -> None:
        self.now = start

    def __call__(self) -> float:
        return self.now

    def after(self, seconds: float) -> None:
        self.now += seconds


@pytest.fixture
def state(tmp_path: Path) -> Path:
    return tmp_path / "state"


def crash_and_start(state: Path, clock: Clock, gap: float = 30.0) -> Recovery:
    """A run that ends with no clean stop (the marker stays), then the next start."""
    clock.after(gap)
    recovery = Recovery(state, clock)
    recovery.begin()
    return recovery


# -- the marker ----------------------------------------------------------------------------------


def test_a_first_start_finds_nothing_and_a_clean_stop_leaves_no_marker(state: Path) -> None:
    recovery = Recovery(state)
    start = recovery.begin()
    assert (start.unclean, start.previous, start.safe) == (0, None, False)
    assert (state / MARKER).is_file()  # a running shell has its marker
    recovery.finish()
    assert not (state / MARKER).exists()
    assert Recovery(state).begin().unclean == 0


def test_a_start_that_finds_the_marker_counts_one_unclean_start_and_knows_when(
    state: Path,
) -> None:
    clock = Clock()
    Recovery(state, clock).begin()  # this run is killed: it never removes its marker
    marker_time = (state / MARKER).stat().st_mtime
    start = crash_and_start(state, clock).start
    assert start.unclean == 1 and start.safe is False
    assert start.previous == pytest.approx(marker_time)  # "the file's time"
    assert start.last_crash is not None and start.last_crash >= marker_time


def test_a_marker_that_a_start_counted_is_not_counted_again(state: Path) -> None:
    """A kill between writing the count and writing the new marker leaves the old marker: the next
    start must not count that one crash twice."""
    clock = Clock()
    Recovery(state, clock).begin()
    crash_and_start(state, clock)  # counts the marker of the first run (1)
    # the second run died right after it wrote the count: put the first marker back
    first_marker = json.loads((state / MARKER).read_text())
    counted = json.loads((state / STATE_FILE).read_text())["counted"]
    (state / MARKER).write_text(json.dumps({**first_marker, "id": counted}))
    assert crash_and_start(state, clock).start.unclean == 1


def test_a_clean_stop_resets_the_count_but_keeps_the_time_of_the_last_crash(state: Path) -> None:
    clock = Clock()
    Recovery(state, clock).begin()
    run = crash_and_start(state, clock)
    assert run.start.unclean == 1
    run.finish()
    again = Recovery(state, clock)
    start = again.begin()
    assert start.unclean == 0 and start.last_crash is not None


def test_a_refusal_the_shell_chose_leaves_the_marker_out_and_the_count_where_it_is(
    state: Path,
) -> None:
    """Exit 1, 2, 4 or 69 is not a crash and not a good run: no new count, no reset."""
    clock = Clock()
    Recovery(state, clock).begin()
    run = crash_and_start(state, clock)
    run.leave()
    assert not (state / MARKER).exists()
    assert Recovery(state, clock).begin().unclean == 1


# -- safe start ----------------------------------------------------------------------------------


def test_three_unclean_starts_in_a_row_make_the_next_start_a_safe_start(state: Path) -> None:
    clock = Clock()
    Recovery(state, clock).begin()  # run 1 crashes
    assert crash_and_start(state, clock).start.safe is False  # sees 1
    assert crash_and_start(state, clock).start.safe is False  # sees 2
    third = crash_and_start(state, clock)  # sees 3: three runs ended uncleanly
    assert third.start.unclean == 3 and third.start.safe is True


def test_the_three_must_fall_within_ten_minutes(state: Path) -> None:
    clock = Clock()
    Recovery(state, clock).begin()
    crash_and_start(state, clock, gap=UNCLEAN_WINDOW)  # 1
    crash_and_start(state, clock, gap=UNCLEAN_WINDOW)  # 2
    slow = crash_and_start(state, clock, gap=UNCLEAN_WINDOW)  # 3, but spread over 20 minutes
    assert slow.start.unclean == 3 and slow.start.safe is False
    # two quick crashes after them: still only two of the last three are inside ten minutes ...
    assert crash_and_start(state, clock, gap=5.0).start.safe is False
    # ... and with the third quick one all three are
    assert crash_and_start(state, clock, gap=5.0).start.safe is True


def test_a_clean_stop_of_the_safe_start_ends_it(state: Path) -> None:
    clock = Clock()
    Recovery(state, clock).begin()
    crash_and_start(state, clock)
    crash_and_start(state, clock)
    safe = crash_and_start(state, clock)
    assert safe.start.safe is True
    safe.finish()  # the user fixed the module and restarted
    assert Recovery(state, clock).begin().safe is False


def test_a_crash_of_the_safe_start_keeps_it_safe(state: Path) -> None:
    clock = Clock()
    Recovery(state, clock).begin()
    for _ in range(3):
        crash_and_start(state, clock)
    assert crash_and_start(state, clock).start.safe is True


# -- status with no shell running ----------------------------------------------------------------


def test_status_counts_the_marker_of_a_run_that_died_and_nobody_has_started_since(
    state: Path,
) -> None:
    clock = Clock()
    Recovery(state, clock).begin()  # killed; the unit gave up (five starts in 60 s) or is waiting
    found = summary(state, shell_running=False, now=clock())
    assert found.unclean == 1 and found.last_crash is not None
    assert summary(state, shell_running=True, now=clock()).unclean == 0  # a live run's own marker


def test_status_says_the_next_start_is_a_safe_start_after_three_crashes(state: Path) -> None:
    clock = Clock()
    Recovery(state, clock).begin()
    crash_and_start(state, clock)
    crash_and_start(state, clock)  # the third crash is the marker of this run
    assert summary(state, shell_running=False, now=clock()).next_safe is True
    clock.after(UNCLEAN_WINDOW + 1)
    assert summary(state, shell_running=False, now=clock()).next_safe is False


def test_status_of_a_folder_with_nothing_is_quiet(state: Path) -> None:
    found = summary(state, shell_running=False)
    assert (found.unclean, found.last_crash, found.next_safe) == (0, None, False)


def test_a_corrupt_state_file_is_an_empty_one(state: Path) -> None:
    state.mkdir()
    (state / STATE_FILE).write_text("{not json")
    assert Recovery(state).begin().unclean == 0


# -- the crash file ------------------------------------------------------------------------------

ABORT = """
import os, signal, sys, threading, time
from pathlib import Path
from tess_shell.recovery import Recovery

Recovery(Path(sys.argv[1])).open_crash_log()

def blocked_in_a_named_function():
    time.sleep(60)

threading.Thread(target=blocked_in_a_named_function, name="stuck-thread", daemon=True).start()
time.sleep(0.2)  # the thread is in sleep() by now
print("ready", flush=True)
os.kill(os.getpid(), signal.SIGABRT)
time.sleep(60)
"""


def abort_a_run(state: Path) -> subprocess.CompletedProcess[str]:
    state.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [sys.executable, "-c", ABORT, str(state)], capture_output=True, text=True, timeout=30
    )


def test_a_sigabrt_writes_the_traceback_of_every_thread_to_crash_log(state: Path) -> None:
    done = abort_a_run(state)
    assert done.returncode == -6  # killed by SIGABRT, as systemd's watchdog kills it
    text = (state / CRASH_LOG).read_text()
    assert "Fatal Python error: Aborted" in text
    assert "blocked_in_a_named_function" in text  # the thread that was stuck
    assert "stuck-thread" not in done.stderr  # it went to the file, not only to stderr


def test_the_previous_crash_file_is_kept_as_one_and_two_and_no_more(state: Path) -> None:
    abort_a_run(state)  # crash.log
    first = (state / CRASH_LOG).read_text()
    abort_a_run(state)  # the first is crash.log.1
    assert (state / f"{CRASH_LOG}.1").read_text() == first
    abort_a_run(state)
    abort_a_run(state)
    names = sorted(p.name for p in state.iterdir())
    assert names == [CRASH_LOG, f"{CRASH_LOG}.1", f"{CRASH_LOG}.2"]


def test_a_clean_run_leaves_no_crash_file_and_does_not_push_out_a_real_one(state: Path) -> None:
    abort_a_run(state)
    real = (state / CRASH_LOG).read_text()
    for _ in range(3):  # three clean runs
        recovery = Recovery(state)
        recovery.open_crash_log()
        recovery.close_crash_log()
    assert (state / f"{CRASH_LOG}.1").read_text() == real  # rotated once, by the first of them
    assert not (state / f"{CRASH_LOG}.2").exists()
    assert not (state / CRASH_LOG).exists()  # an empty one is not kept


def test_an_exception_that_reaches_the_top_is_written_to_crash_log(state: Path) -> None:
    recovery = Recovery(state)
    recovery.open_crash_log()
    try:
        raise RuntimeError("the module blew up")
    except RuntimeError as exc:
        recovery.record_exception(type(exc), exc, exc.__traceback__)
    recovery.close_crash_log()
    text = (state / CRASH_LOG).read_text()  # a file that holds something stays
    assert "RuntimeError: the module blew up" in text and "unhandled exception" in text


def test_the_crash_file_is_private(state: Path) -> None:
    recovery = Recovery(state)
    recovery.open_crash_log()
    assert stat.S_IMODE(os.stat(state / CRASH_LOG).st_mode) == 0o600
    recovery.close_crash_log()


def test_a_killed_run_leaves_an_empty_crash_file_that_does_not_push_a_real_one_out(
    state: Path,
) -> None:
    """SIGKILL gives faulthandler no chance to write: the file of that run stays, empty. The next
    starts must not rotate it into ``crash.log.1`` over the traceback of an earlier real crash."""
    abort_a_run(state)
    real = (state / CRASH_LOG).read_text()
    killed = Recovery(state)
    killed.open_crash_log()  # rotates the real one to crash.log.1; this run is then killed
    assert (state / CRASH_LOG).stat().st_size == 0
    for _ in range(3):  # three more starts, each killed: an empty file, again and again
        again = Recovery(state)
        again.open_crash_log()
    assert (state / f"{CRASH_LOG}.1").read_text() == real
    assert not (state / f"{CRASH_LOG}.2").exists()
