"""Budget regression of the logging (Performance Budgets B20): the threads the shell's own logging
adds do not wake while idle (a writer that sleeps until a record arrives)."""

from __future__ import annotations

import statistics
from pathlib import Path

import pytest

from tests.perf.budget_inproc_mod import log_costs

pytestmark = pytest.mark.skipif(not Path("/proc/self/task").is_dir(), reason="needs /proc")


def test_the_logging_threads_never_wake_while_idle_and_a_record_is_cheap() -> None:
    """``configure_logging`` with an enqueue=True file sink: after 300 records have drained, the
    threads it added (the writer and the midnight Timer) show no voluntary context switch over 3
    idle seconds, and there are at most 3 of them; a record on the calling thread costs a median
    under 81 us (3 times the vault's 27 us; about 22 us today) (about 4 s)."""
    got = log_costs(300, 3.0)
    assert got.new_threads <= 3
    assert got.idle_switches == 0
    assert statistics.median(got.record_us) < 81.0
