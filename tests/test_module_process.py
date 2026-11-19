"""The module process test, the fast part: the posture B prototype against the fakes, and the
harness's own logic. Under 30 seconds in all. The slow part (every posture end to end, the C form
with user modules, the reload measure) is ``tests/test_module_process_smoke.py``, marked ``perf``.
The lean B (L1, L2) has its own fast tests in ``tests/test_module_process_lean.py``.

* The prototype (B1, one process per module file): the default shell's modules start in processes,
  one value reaches the surfaces, a hung module and a killed module leave the surfaces painting and
  are restarted. B2 (the shell keeps the connections) is checked to start.
* The harness: the refusal under load, and the verdict table on canned numbers (a threshold just on
  each side of every row, and what the decision rule gives).
"""

from __future__ import annotations

import shutil
import time
from collections.abc import Iterator
from typing import Any

import pytest

from tests.fake_dbus import HAVE_DAEMON
from tests.perf import module_process_test as h
from tests.perf.proto import measure as M
from tests.perf.proto import rig as R
from tests.sway import SwayUnavailable


@pytest.fixture(scope="module")
def sandbox() -> Iterator[R.Rig]:
    try:
        with R.rig() as rig:
            yield rig
    except SwayUnavailable as exc:
        pytest.skip(str(exc))


# -- the prototype against the fakes -----------------------------------------------------------


@pytest.mark.tre
@pytest.mark.skipif(not HAVE_DAEMON, reason="no dbus-daemon")
@pytest.mark.parametrize("cell", [M.B1, M.B2], ids=["B1", "B2"])
def test_the_default_shells_modules_run_in_their_own_processes(
    sandbox: R.Rig, cell: M.Cell
) -> None:
    """B puts a process behind each of the 22 module files of the default shell and the shell is
    ready; in A the same shell has no module process."""
    with M.running(sandbox, M.A, "default") as (shell, _, _):
        in_process = len(R.tree_pids(shell.pid))
    with M.running(sandbox, cell, "default") as (shell, ready, _):
        time.sleep(0.5)
        assert len(R.tree_pids(shell.pid)) >= in_process + 22
        assert ready < 10
        log = shell.stderr()
        assert "Traceback" not in log and "failed: restart" not in log, log[-1500:]


@pytest.mark.tre
@pytest.mark.skipif(not HAVE_DAEMON, reason="no dbus-daemon")
def test_one_value_sent_in_a_module_process_reaches_the_surfaces(sandbox: R.Rig) -> None:
    got = M.measure_latency(
        sandbox,
        M.B1,
        singles=5,
        gap_ms=5,
        burst_rate=200,
        burst_seconds=0.5,
        ladder=[],
        ladder_seconds=1,
        frame_ms=h.LATENCY_P95_MS,
    )
    assert len(got["single_ms"]) == 5 and len(got["burst_ms"]) > 20
    # a send is seen after it was made (one clock across the processes), and in well under a second
    assert all(0 < ms < 1000 for ms in got["single_ms"] + got["burst_ms"])


@pytest.mark.tre
@pytest.mark.skipif(not HAVE_DAEMON, reason="no dbus-daemon")
@pytest.mark.skipif(shutil.which("grim") is None, reason="no grim (the paint of the node)")
def test_a_hung_module_and_a_killed_module_are_contained_and_restarted(sandbox: R.Rig) -> None:
    """The benefit of B: the scrolling test node keeps painting while a module's callback sleeps
    and while its process is killed, the module is detected, killed if hung, and started again."""
    got = M.measure_containment(
        sandbox, M.B1, hang_seconds=1.5, stall=0.3, kill=1.0, baseline=1.0, reload=False
    )
    assert got["base"]["changed"] > 0.5  # the test node does paint
    for phase in ("hang_paint", "crash_paint"):
        assert got[phase]["changed"] > 0.5 and got[phase]["max_gap_s"] < 1.0, (phase, got[phase])
    assert got["hang_detect_s"] is not None and got["hang_recover_s"] is not None
    assert got["crash_restart_s"] > 0
    assert "ended" in got["crash_log"] and "Victim" in got["crash_log"]


@pytest.mark.tre
@pytest.mark.skipif(not HAVE_DAEMON, reason="no dbus-daemon")
def test_the_products_user_module_value_reaches_the_surfaces(sandbox: R.Rig) -> None:
    """Cell ``P``: the shell as built (posture C, a process per user module, no patch)."""
    got = M.measure_latency(
        sandbox,
        M.P,
        singles=5,
        gap_ms=5,
        burst_rate=200,
        burst_seconds=0.5,
        ladder=[],
        ladder_seconds=1,
        frame_ms=h.LATENCY_P95_MS,
    )
    assert len(got["single_ms"]) == 5 and len(got["burst_ms"]) > 20
    assert all(0 < ms < 1000 for ms in got["single_ms"] + got["burst_ms"])


@pytest.mark.tre
@pytest.mark.skipif(not HAVE_DAEMON, reason="no dbus-daemon")
@pytest.mark.skipif(shutil.which("grim") is None, reason="no grim (the paint of the node)")
def test_the_products_hung_and_killed_user_module_are_contained_and_restarted(
    sandbox: R.Rig,
) -> None:
    got = M.measure_containment(
        sandbox, M.P, hang_seconds=1.5, stall=0.3, kill=1.0, baseline=1.0, reload=False
    )
    assert got["base"]["changed"] > 0.5
    for phase in ("hang_paint", "crash_paint"):
        assert got[phase]["changed"] > 0.5 and got[phase]["max_gap_s"] < 1.0, (phase, got[phase])
    assert got["hang_detect_s"] is not None and got["hang_recover_s"] is not None
    assert got["crash_restart_s"] > 0
    assert "ended" in got["crash_log"] and "Victim" in got["crash_log"]


# -- the harness: refusal and the verdict table ---------------------------------------------------


def test_the_harness_refuses_a_loaded_machine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(h.os, "getloadavg", lambda: (3.0, 2.0, 1.0))
    with pytest.raises(SystemExit) as refused:
        h.refuse_when_loaded(False)
    assert "refusing to start" in str(refused.value) and "--allow-load" in str(refused.value)
    assert h.refuse_when_loaded(True) is True  # allowed, and the report will say so
    monkeypatch.setattr(h.os, "getloadavg", lambda: (0.5, 0.5, 0.5))
    assert h.refuse_when_loaded(False) is False  # the limit itself is allowed


def rep(
    hang: float = 1.0, hang_gap: float = 0.03, crash: float = 1.0, crash_gap: float = 0.03
) -> dict[str, Any]:
    return {
        "base": {"changed": 1.0, "max_gap_s": 0.03},
        "hang_paint": {"changed": hang, "max_gap_s": hang_gap},
        "hang_recover_s": 5.0,
        "crash_paint": {"changed": crash, "max_gap_s": crash_gap},
        "crash_restart_s": 1.2,
    }


def canned(
    *,
    start: float = 0.0,
    wake: float = 0.0,
    pss: float = 0.0,
    p95: float = 1.0,
    contain: dict[str, Any] | None = None,
    only: tuple[str, ...] = ("B1", "B2", "C1", "C2"),
    cells: dict[str, dict[str, Any]] | None = None,
    postures: str | None = None,
) -> dict[str, Any]:
    """Results of a run: A at 300 ms, 2 wake-ups a second and 160 MB, and every other cell ``start``
    ms later, ``wake`` a second more and ``pss`` MB more (B1, B2 and C1 on the default shell, C1 and
    C2 on the shell with three user modules, L1 and L2 on the default shell). ``cells`` overrides
    the numbers of one cell (``start``, ``wake``, ``pss``, ``p95``, ``contain``); ``postures`` is
    what the run was asked for (``--postures``), which the results of a real run say."""
    own = cells or {}
    res: dict[str, Any] = {"start": {}, "idle": {}, "latency": {}, "contain": {}}
    if postures is not None:
        res["args"] = {"postures": postures}

    def cell(label: str, kind: str, extra: tuple[float, float, float]) -> None:
        res["start"][f"{label}/{kind}"] = {"ready_ms": [300.0 + extra[0]] * 3}
        res["idle"][f"{label}/{kind}"] = [
            {"wakeups_per_s": 2.0 + extra[1], "pss_mb": 160.0 + extra[2]}
        ] * 3

    for kind in ("default", "plus3"):
        cell("A", kind, (0, 0, 0))
    for label, kind in (
        ("B1", "default"),
        ("B2", "default"),
        ("C1", "default"),
        ("L1", "default"),
        ("L2", "default"),
        ("C1", "plus3"),
        ("C2", "plus3"),
    ):
        if label in only:
            mine = own.get(label, {})
            cell(
                label,
                kind,
                (mine.get("start", start), mine.get("wake", wake), mine.get("pss", pss)),
            )
    for label in only:
        mine = own.get(label, {})
        value = mine.get("p95", p95)
        res["latency"][label] = [{"single_ms": [value] * 20, "burst_ms": [value] * 20}]
        res["contain"][label] = [mine.get("contain", contain or rep())]
    return res


def verdict(res: dict[str, Any], test: str, cell: str) -> bool | None:
    (row,) = [r for r in h.verdicts(res) if r.test == test and r.cell == cell]
    return row.ok


@pytest.mark.parametrize(
    ("test", "limit", "arg"),
    [
        ("Start", h.START_EXTRA_MS, "start"),
        ("Wake-ups", h.WAKEUPS_EXTRA_PER_S, "wake"),
        ("Memory", h.MEMORY_EXTRA_MB, "pss"),
    ],
)
def test_a_cost_row_passes_at_its_threshold_and_fails_just_over_it(
    test: str, limit: float, arg: str
) -> None:
    """Start, wake-ups and memory are the difference from A: at the limit passes, a little more
    fails, for every cell and for the +3 user modules form of C."""
    for cell in ("B1", "B2", "C1"):
        assert verdict(canned(**{arg: limit}), test, cell) is True
        assert verdict(canned(**{arg: limit + 0.5}), test, cell) is False
        assert verdict(canned(**{arg: limit - 0.5}), test, cell) is True
    plus3 = [r for r in h.verdicts(canned(**{arg: limit + 0.5})) if "(+3 user" in r.test]
    assert [r.ok for r in plus3 if r.test.startswith(test)] == [False, False]  # C1 and C2


def test_value_to_screen_passes_up_to_one_frame_and_fails_over_it() -> None:
    for test in ("Value to screen, single", "Value to screen, burst"):
        assert verdict(canned(p95=16.6), test, "B1") is True
        assert verdict(canned(p95=16.8), test, "B1") is False


@pytest.mark.parametrize(
    ("bad", "passes"),
    [
        (rep(hang=0.49), False),  # the test node painted less than half as much
        (rep(hang=0.51), True),
        (rep(hang_gap=0.9), True),
        (rep(hang_gap=1.1), False),  # it stopped for over a second
        (rep(crash=0.49), False),
        (rep(crash_gap=1.1), False),
        (rep(crash=0.51, crash_gap=0.9), True),
    ],
)
def test_containment_needs_painting_and_no_long_stop(bad: dict[str, Any], passes: bool) -> None:
    assert verdict(canned(contain=bad), "Containment", "B1") is passes


def test_containment_fails_when_the_module_does_not_come_back() -> None:
    no_restart = rep()
    no_restart["crash_restart_s"] = None
    assert verdict(canned(contain=no_restart), "Containment", "B1") is False
    no_recover = rep()
    no_recover["hang_recover_s"] = None
    assert verdict(canned(contain=no_recover), "Containment", "B1") is False


def test_a_cell_that_was_not_measured_is_not_a_pass() -> None:
    assert verdict(canned(only=("B1",)), "Start", "B2") is None
    assert verdict(canned(only=("B1",)), "Containment", "B2") is None


def test_the_decision_rule_follows_the_rows() -> None:
    """B passing every row: B; B failing on cost and C passing: C; neither: A; a gap: no answer."""
    ok = canned()
    assert "moves to B" in h.decision(h.verdicts(ok))[0]
    costly = canned(pss=h.MEMORY_EXTRA_MB + 1)  # every cell pays more memory, C1 and C2 too
    assert "A stays" in h.decision(h.verdicts(costly))[0]
    res = canned()
    for label in ("B1", "B2"):
        res["idle"][f"{label}/default"] = [{"wakeups_per_s": 2.0, "pss_mb": 160.0 + 400}] * 3
    assert "moves to C" in h.decision(h.verdicts(res))[0]
    assert "cannot be applied" in h.decision(h.verdicts(canned(only=("B1",))))[0]
