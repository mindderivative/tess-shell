"""The idle budgets, counted on a real shell (Performance Budgets: at most 5 wake-ups a second and
0.5 % of a core, nothing animating; D-Bus Service Layer, Hot Reload and Logging: no timer in the
layer, the watcher blocks in a read, the writers sleep until a record arrives).

A shell with a Bar and a static text runs on a private headless sway. After it has settled, every
thread's context switches are read once a second for ``WINDOW`` seconds and grouped by the thread's
name (``tests/perf/budget_process.py``: the loop, the watchdog, tre's helpers, the shell's own
threads). The expectations are the design's rates with a margin; what a regression shows:

* a timer left running on the loop (say every 10 ms) puts tens of switches a second on the loop;
* a thread of the shell that polls (the service thread, the watcher, a writer) leaves its group at
  zero;
* the heartbeat sped up to ten a second multiplies the loop and watchdog groups.

``test_budgets_idle_the_shells_own_threads_stay_asleep`` takes about 14 s; the 60 s window of the
budget is the harness's (``python -m tests.perf.read_budgets``) and ``test_..._60_s`` here, marked
``perf`` (``pytest -m perf tests/test_budget_idle.py``).
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from tests.fake_dbus import HAVE_DAEMON, FakeBus
from tests.perf.budget_process import Bin, sample
from tests.perf.budget_rig import thread_counts
from tests.shell_samples import write_example
from tests.sway import PrivateSway
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed"),
]

# the groups that belong to the shell and have no reason to wake with nothing to do
SILENT = (
    "dbus service thread",
    "logging writers",
    "file watcher",
    "time source",
    "signal watcher",
)


def idle_bins(sway: PrivateSway, tmp_path: Path, seconds: float) -> list[Bin]:
    config = tmp_path / "cfg"
    write_example(config)
    bus = FakeBus()  # a private session bus: the control interface, as on a desktop
    shell = Shell(config, {**sway.env, "DBUS_SESSION_BUS_ADDRESS": bus.address})
    try:
        shell.wait_for("running")
        shell.wait_for("configured")
        time.sleep(3.0)  # the first frames, the first heartbeat and the start's log are over
        bins = sample(shell.process.pid, seconds)
        names = {t.name for t in thread_counts(shell.process.pid).values()}
        assert "watchdog" in names, names  # the instrument finds the thread it is about
    finally:
        shell.process.terminate()
        shell.process.wait(timeout=15)
        bus.close()
    return bins


def rates(bins: list[Bin], *, voluntary: bool) -> dict[str, float]:
    span = sum(b.end - b.begin for b in bins)
    out: dict[str, float] = {}
    for b in bins:
        for group, count in (b.voluntary if voluntary else b.switches).items():
            out[group] = out.get(group, 0.0) + count / span
    return out


def check(bins: list[Bin]) -> None:
    quiet = rates(bins, voluntary=True)
    for group in SILENT:
        assert quiet.get(group, 0.0) == 0.0, (group, quiet)
    total = rates(bins, voluntary=False)
    # the control: the instrument sees the heartbeat, so a zero above is a zero and not a blind spot
    assert total.get("watchdog", 0.0) > 0.0, total
    assert total.get("loop (main thread)", 0.0) > 0.0, total
    # the heartbeat: one queued beat a second wakes the loop once, the thread wakes once a second
    assert total.get("loop (main thread)", 0.0) <= 2.5, total
    assert total.get("watchdog", 0.0) <= 2.5, total
    # tre's own helpers (the OS-preference watcher) wake about twice a second: not ours to fix
    assert total.get("tre helpers", 0.0) <= 4.0, total
    # the budget itself is 5 a second for the whole shell: with the engine's floor and the
    # heartbeat it is about 4.3 on a quiet machine; twice the budget is a regression, not noise
    assert sum(total.values()) <= 10.0, total


def test_budgets_idle_the_shells_own_threads_stay_asleep(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    bins = idle_bins(private_sway, tmp_path, 8.0)
    check(bins)


@pytest.mark.perf
def test_budgets_idle_the_shells_own_threads_stay_asleep_60_s(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    bins = idle_bins(private_sway, tmp_path, 60.0)
    check(bins)
