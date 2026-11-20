"""The module process test's harness (``tests/perf/module_process_test.py``) runs end to end in its
smoke configuration, a couple of seconds for each measure and posture, on a private headless sway,
private buses and the fakes. It proves the harness and the prototype work, not any number: the full
measurement is run by hand on an idle machine and is far longer.

One run serves every test below (the shell is started about 30 times, about two and a half
minutes), so
all of them are marked ``perf`` and run only when asked (``pytest -m perf``). The fast tests that
every run has are in ``tests/test_module_process.py``.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from tests.fake_dbus import HAVE_DAEMON
from tests.perf import module_process_test as harness
from tests.sway import SwayUnavailable

pytestmark = [
    pytest.mark.perf,  # about two minutes: deselected by default, run with ``pytest -m perf``
    pytest.mark.tre,
    pytest.mark.skipif(not HAVE_DAEMON, reason="no dbus-daemon"),
    pytest.mark.skipif(shutil.which("grim") is None, reason="no grim (the paint of the node)"),
]

POSTURES = "A,B1,B2,C1,P,L1,L2"


@pytest.fixture(scope="module")
def smoke(tmp_path_factory: pytest.TempPathFactory) -> tuple[dict[str, Any], str]:
    out = tmp_path_factory.mktemp("process-test") / "report.md"
    try:
        code = harness.main(["--smoke", "--allow-load", "--postures", POSTURES, "--out", str(out)])
    except SwayUnavailable as exc:
        pytest.skip(str(exc))
    data = json.loads(out.with_suffix(".json").read_text())
    assert code == 0, f"a measurement failed: {data['errors']}"
    return data, Path(out).read_text()


def test_every_posture_gives_a_start_time_and_an_idle_row(
    smoke: tuple[dict[str, Any], str],
) -> None:
    data, _ = smoke
    for cell in (
        "A/default",
        "B1/default",
        "B2/default",
        "C1/default",
        "L1/default",
        "L2/default",
        "A/plus3",
        "C1/plus3",
        "P/default",
        "P/plus3",
    ):
        assert data["start"][cell]["ready_ms"] and all(
            ms > 0 for ms in data["start"][cell]["ready_ms"]
        )
        (rep,) = data["idle"][cell]
        assert rep["pss_mb"] > 0 and rep["wakeups_per_s"] >= 0 and rep["cpu_percent"] >= 0


def test_the_postures_really_differ_in_how_many_processes_run_the_modules(
    smoke: tuple[dict[str, Any], str],
) -> None:
    """B puts a process behind each module file, C only behind the user's: a harness that ran the
    same in-process shell three times would show the same count everywhere."""
    data, _ = smoke
    count = {cell: rep[0]["processes"] for cell, rep in data["idle"].items()}
    assert count["A/default"] <= 3  # the shell and the interpreter's own helper
    assert count["B1/default"] >= count["A/default"] + 20  # every module file of the default shell
    assert count["B2/default"] >= count["A/default"] + 20
    assert count["C1/default"] == count["A/default"]  # no user module, so nothing runs apart
    # the lean B: the 19 module files with Python of their own, not the 3 TDL-only ones
    assert count["L1/default"] == count["B1/default"] - 3
    assert count["L2/default"] == count["B2/default"] - 3
    assert count["C1/plus3"] == count["A/plus3"] + 3  # the three user modules, one process each
    assert count["P/default"] == count["A/default"]  # the product: no user module, no process
    assert count["P/plus3"] == count["A/plus3"] + 3  # and a process for each of the three


def test_value_to_screen_is_timed_for_every_posture_in_one_clock(
    smoke: tuple[dict[str, Any], str],
) -> None:
    data, _ = smoke
    for label in ("A", "B1", "B2", "C1", "P", "L1", "L2"):
        (rep,) = data["latency"][label]
        for key in ("single_ms", "burst_ms"):
            assert len(rep[key]) > 10
            # a send is never seen before it was made, and nothing takes seconds on an idle shell
            assert all(0 < ms < 2000 for ms in rep[key]), (label, key, max(rep[key]))
        assert rep["throughput"] > 0


def test_a_hang_freezes_the_surfaces_in_a_and_not_in_a_module_process(
    smoke: tuple[dict[str, Any], str],
) -> None:
    """The benefit of B and C: the test node keeps painting while a module's callback sleeps, and
    the killed module is started again."""
    data, _ = smoke
    (a,) = data["contain"]["A"]
    assert a["hang_paint"]["changed"] < 0.3  # A: the loop is stuck in the callback
    assert a["hang_paint"]["max_gap_s"] > 1.0
    assert a["hang_recover_s"] is None  # and nothing restarts it
    for label in ("B1", "B2", "C1", "P", "L1", "L2"):
        (rep,) = data["contain"][label]
        assert rep["hang_paint"]["changed"] > 0.5, (label, rep["hang_paint"])
        assert rep["hang_paint"]["max_gap_s"] < 1.0, (label, rep["hang_paint"])
        assert rep["hang_detect_s"] is not None and rep["hang_recover_s"] is not None
        assert rep["crash_restart_s"] is not None and rep["crash_restart_s"] > 0
        assert "ended" in rep["crash_log"] and "Victim" in rep["crash_log"]


def test_a_saved_module_file_is_running_again_in_every_posture(
    smoke: tuple[dict[str, Any], str],
) -> None:
    data, _ = smoke
    for label in ("A", "B1", "B2", "C1", "P", "L1", "L2"):
        (rep,) = data["contain"][label]
        assert 0 < rep["reload_s"] < 30


def test_the_report_has_the_verdict_table_and_says_it_was_a_smoke_run(
    smoke: tuple[dict[str, Any], str],
) -> None:
    _, text = smoke
    assert "SMOKE RUN" in text and "## Verdict table" in text
    assert "| Test | Cell | Measured | Passes when | Verdict |" in text
    assert "**The maintainer decides**" in text
    assert "## What the prototype leaves out" in text and "## The cost in code of the move" in text
    # the lean B: its rows, the rule applied to them, the module files in and out of processes
    assert "| Memory | P |" in text and "| Memory (+3 user modules) | P |" in text
    assert "## Which C: the product (P)" in text and "P, the product" in text
    assert "| Memory | L1 |" in text and "## Which lean B: L1 or L2" in text
    assert "## Lean B: which module files run in a process" in text
    assert "**22** module files: **19 run in a process** and **3 stay in the shell**" in text
