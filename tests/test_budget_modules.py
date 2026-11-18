"""Budget regressions of the modules on the loop and the control interface (Performance Budgets
B09, B11, B12, B22, B24): callbacks counted over 4 ms, the callback record's allocations, motion
token values, the Clock's tick units. Timing guards are at least 3 times the vault's number."""

from __future__ import annotations

import gc
import statistics
import time

import pytest

from tess_shell.modules.running import CallbackRecord
from tests.fake_dbus import HAVE_DAEMON
from tests.perf.budget_inproc_mod import (
    BUDGET_MS,
    callback_timings,
    clock_tick_costs,
    clock_units,
    record_growth,
    toggle_costs,
)
from tests.perf.budget_inproc_ui import VAULT_DURATIONS, motion_durations

needs_daemon = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")


def test_the_motion_durations_are_100_200_and_400_ms() -> None:
    """B11: the Default theme's Duration tokens (Short, Medium, Long)."""
    assert motion_durations() == VAULT_DURATIONS == {"short": 100, "medium": 200, "long": 400}


def test_a_clock_without_seconds_never_subscribes_to_the_second_unit() -> None:
    """B22, "no timer faster than the shown unit": %H:%M ticks on the minute only; seconds in
    any use add the second unit."""
    assert clock_units("%H:%M") == ["minute"]
    assert clock_units("%H:%M:%S") == ["minute", "second"]


@needs_daemon
def test_a_clock_tick_on_the_loop_is_well_under_five_milliseconds() -> None:
    """B22: show + flush + a frame for 40 ticks, p99 under 5 ms (5 times the vault's 1 ms; about
    0.5 ms today) (about 1 s)."""
    ms = sorted(clock_tick_costs(40))
    assert ms[int(len(ms) * 0.99) - 1] < 5.0, ms[-3:]


@needs_daemon
def test_module_callbacks_are_not_over_four_milliseconds() -> None:
    """B09: Battery, Workspaces and Clock through 15 rounds of events. At most 2 % of the callbacks
    may be over 4 ms; a failure names the heaviest entry points (about 3 s)."""
    _startup, steady = callback_timings(15)
    assert len(steady.seen) >= 50, "the rounds ran few callbacks"
    over = len(steady.over()) / len(steady.seen)
    assert over < 0.02, f"{over:.1%} over {BUDGET_MS} ms; heaviest: {steady.heaviest()}"


@needs_daemon
def test_a_toggle_command_on_the_loop_is_well_under_five_milliseconds() -> None:
    """B12: ``ShellCommands.surface('Toggle', 'Dock')`` 30 times on the real surface manager:
    median under 3 ms (3 times the vault's 1 ms p99; about 0.3 ms today) (about 1 s)."""
    ms = toggle_costs(30)
    assert statistics.median(ms) < 5.0, ms


def test_the_callback_record_allocates_nothing_that_stays() -> None:
    """B24: 100,000 enter/leave pairs and runs leave the allocated blocks and the tracked objects
    where they were (a few blocks of slack for the interpreter) (about 0.2 s)."""
    gc.collect()
    blocks, objects = record_growth(100_000)
    assert blocks < 200, blocks
    assert objects < 50, objects


def test_leave_stays_far_under_forty_microseconds_with_the_default_clock() -> None:
    """B24: the vault's keep-the-record line is 40 us; the median of 20,000 ``leave`` calls with the
    default clock (about 0.1 us) must stay under it (about 0.1 s)."""
    record = CallbackRecord(lambda module, rule, message: None)
    took: list[float] = []
    for _ in range(20_000):
        previous = record.enter("Module", "entry")
        started = time.perf_counter_ns()
        record.leave(previous)
        took.append((time.perf_counter_ns() - started) / 1000)
    assert statistics.median(took) < 40.0
