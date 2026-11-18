"""Budget regressions for the D-Bus layer, the shortcut service and the portal reader (Performance
Budgets B13, B14, B15): connections and calls are counted, never timed tightly. The idle
wake-up counters of the layer and of the shortcut service are those of ``test_dbus_idle`` and
``test_shortcuts_idle``. Timing guards are at least 3 times the vault's number."""

from __future__ import annotations

import statistics
from pathlib import Path

import pytest

from tests.fake_dbus import HAVE_DAEMON
from tests.perf.budget_inproc_dbus import (
    FRAME_MS,
    connections_for,
    press_latencies,
    read_portal,
    register_ten,
)

pytestmark = [
    pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed"),
    pytest.mark.skipif(not Path("/proc/self/task").is_dir(), reason="needs /proc"),
]


def test_one_connection_per_bus_however_many_modules_use_it() -> None:
    """B13: 1 module and 8 modules, each with a property and a signal subscription on both
    buses, give the layer one connection on each daemon (about 2 s)."""
    one, many = connections_for(1), connections_for(8)
    assert (one.session_connects, one.system_connects) == (1, 1)
    assert (many.session_connects, many.system_connects) == (1, 1)
    assert one.shell_names == many.shell_names == 2  # as the private daemons see them


def test_ten_actions_are_registered_with_a_fixed_number_of_calls() -> None:
    """B14: one ``doRegister`` per action, the two ``setShortcutKeys`` the client library sends
    (present, default) and one availability check per chord: a call more per action is a
    regression. The time guard is 3 times the vault's 50 ms (about 1 s)."""
    got = register_ten()
    assert got.registered == 10
    assert got.do_register == 10
    assert got.set_keys == 20 and got.set_keys_flags == (2, 8)
    assert got.available == 10
    assert got.ms < 150, f"registering 10 actions took {got.ms:.0f} ms (budget 50 ms)"


def test_a_key_press_reaches_the_loop_within_three_frames() -> None:
    """B14: fake press to the callback on the loop thread; guard: p95 of 30 presses under 3
    frames (50 ms), the vault says one frame (about 1 s)."""
    latencies = sorted(press_latencies(30))
    p95 = latencies[int(len(latencies) * 0.95) - 1]
    assert p95 < 3 * FRAME_MS, f"p95 {p95:.1f} ms, median {statistics.median(latencies):.1f} ms"


def test_the_portal_is_read_once_at_start_and_then_never_polled() -> None:
    """B15: one ``Register`` and one ``ReadAll`` at start, no call over an idle second, and the
    read takes under 60 ms of service-thread time (3 times the vault's 20 ms) (about 2 s)."""
    ms, read_all, registers, idle_calls = read_portal(1.0)
    assert (read_all, registers) == (1, 1)
    assert idle_calls == 0
    assert ms < 60, f"the first read took {ms:.1f} ms"
