"""The lean B (L1 and L2) of the module process test, the fast part. Under 30 seconds in all; the
posture B tests and the verdict table of B and C are in ``tests/test_module_process.py``, and the
end-to-end run of every posture is ``tests/test_module_process_smoke.py`` (marked ``perf``).

L runs in a child every module file that has Python of its own and keeps the others in the shell:

* the test of "Python of its own" (``has_own_code``), file by file, in both of its rules, and on the
  shipped modules;
* the default shell started in L1 and L2: exactly the expected module files in processes, a TDL-only
  module staying in the shell; a value from a module in a process reaches the surfaces; a hung and a
  killed module process are contained and restarted;
* the harness: which cells a run plans, the verdict table and the decision rule on canned numbers
  with L rows (a threshold on each side), and the report of a lean run.
"""

from __future__ import annotations

import shutil
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.fake_dbus import HAVE_DAEMON
from tests.perf import module_process_test as h
from tests.perf.proto import measure as M
from tests.perf.proto import parent as P
from tests.perf.proto import rig as R
from tests.sway import SwayUnavailable
from tests.test_module_process import canned, rep, verdict

# the 23 module files the default shell loads, and the ones with no Python of their own by each rule
DEFAULT_SHELL = {
    "Applications", "Audio", "Audio_Outputs", "Battery", "Button", "Clock", "Icon", "Image",
    "List", "Marquee_Text", "Media", "Menu", "MenuItem", "Network", "Slider", "Task_Item",
    "Tasks", "TextInput", "Tray", "Tray_Item", "Tray_Menu", "Workspaces", "Workspace_Item",
}  # fmt: skip
STAYS = {"strict": {"Menu", "Task_Item", "Tray_Item", "Workspace_Item"}}
STAYS["validate"] = STAYS["strict"] | {
    "Button", "Icon", "Image", "List", "Marquee_Text", "MenuItem", "Slider", "TextInput",
}  # fmt: skip


@pytest.fixture(scope="module")
def sandbox() -> Iterator[R.Rig]:
    try:
        with R.rig() as rig:
            yield rig
    except SwayUnavailable as exc:
        pytest.skip(str(exc))


# -- Python of its own -------------------------------------------------------------------------


def module_file(tmp_path: Path, body: str) -> Path:
    py = tmp_path / "Thing_Module.py"
    py.write_text(body)
    return py


@pytest.mark.parametrize(
    ("body", "strict", "validate"),
    [
        ("from tess_shell import Module\n\n\nclass Menu(Module):\n    pass\n", False, False),
        ('"""doc"""\nfrom tess_shell import Module\nclass M(Module):\n    """x"""\n', False, False),
        ("from tess_shell import Module\nclass M(Module):\n    ...\n", False, False),
        (
            "from typing import TYPE_CHECKING\nfrom tess_shell import Module\n"
            "if TYPE_CHECKING:\n    from x import Y\nclass M(Module):\n    pass\n",
            False,
            False,
        ),
        # a method, a constant, a function, a second class, a decorator: code of its own
        ("from tess_shell import Module\nclass M(Module):\n    def start(self): ...\n", True, True),
        ("from tess_shell import Module\nclass M(Module):\n    X = 1\n", True, True),
        ("from tess_shell import Module\nX = 1\nclass M(Module):\n    pass\n", True, False),
        ("from tess_shell import Module\ndef f(): ...\nclass M(Module):\n    pass\n", True, True),
        (
            "from tess_shell import Module\nclass M(Module):\n    pass\nclass N(Module):\n"
            "    def stop(self): ...\n",
            True,
            True,
        ),
        ("class M:\n    pass\n", True, True),  # not a Module: it is a class with code of its own
        ("from tess_shell import Module\nX = f()\nclass M(Module):\n    pass\n", True, True),
        # the check of the parameters alone is code in `strict` and none in `validate`
        (
            "from tess_shell import Module\nFITS = ('A', 'B')\n"
            "class M(Module):\n    def validate_use(self, use): ...\n",
            True,
            False,
        ),
        (
            "from tess_shell import Module\n"
            "class M(Module):\n    def validate_use(self, use): ...\n    def start(self): ...\n",
            True,
            True,
        ),
        ("from tess_shell import Module\nclass M(Module:\n", True, True),  # does not parse
    ],
)
def test_python_of_its_own_is_read_from_the_syntax_tree(
    tmp_path: Path, body: str, strict: bool, validate: bool
) -> None:
    py = module_file(tmp_path, body)
    assert P.has_own_code(py, "strict") is strict, body
    assert P.has_own_code(py, "validate") is validate, body


def test_a_module_file_that_is_missing_has_no_python_of_its_own(tmp_path: Path) -> None:
    for rule in P.RULES:
        assert P.has_own_code(tmp_path / "Nothing_Module.py", rule) is False


def test_an_unknown_rule_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="lean rule"):
        P.has_own_code(module_file(tmp_path, "pass\n"), "everything")


@pytest.mark.parametrize("rule", P.RULES)
def test_the_shipped_modules_without_python_of_their_own(rule: str) -> None:
    """The real files: the three TDL-only modules of the default shell stay by both rules, the eight
    widgets whose Python is only ``validate_use`` stay by ``validate`` alone."""
    shipped = {
        py.parent.name for py in P.SHIPPED.glob("*/*_Module.py") if not P.has_own_code(py, rule)
    }
    assert shipped & DEFAULT_SHELL == STAYS[rule]


# -- the default shell in L1 and L2 ------------------------------------------------------------


@pytest.mark.tre
@pytest.mark.skipif(not HAVE_DAEMON, reason="no dbus-daemon")
@pytest.mark.parametrize(
    ("cell", "rule"),
    [(M.L1, "strict"), (M.L2, "strict"), (M.L1, "validate")],
    ids=["L1-strict", "L2-strict", "L1-validate"],
)
def test_the_module_files_with_python_of_their_own_run_in_processes_and_the_rest_in_the_shell(
    sandbox: R.Rig, monkeypatch: pytest.MonkeyPatch, cell: M.Cell, rule: str
) -> None:
    """Exactly the expected module files are in processes (counted from the processes themselves,
    not from what the launcher says), the TDL-only ones are imported in the shell, and the shell is
    ready with no failure."""
    monkeypatch.setenv("TESS_PROTO_LEAN_RULE", rule)
    expected = DEFAULT_SHELL - STAYS[rule]
    with M.running(sandbox, cell, "default") as (shell, ready, root):
        decided = M.read_decisions(root / "decisions.log")
        assert set(decided) == DEFAULT_SHELL  # every file of the default shell was decided once
        assert {n for n, where in decided.items() if where == "shell"} == STAYS[rule]
        assert R.child_names(shell.pid) == sorted(expected)  # the processes that really run
        assert len(expected) == (19 if rule == "strict" else 11)
        assert "Menu" not in R.child_names(shell.pid)  # a TDL-only module stays in the shell
        assert ready < 10
        log = shell.stderr()
        assert "Traceback" not in log and "failed: restart" not in log, log[-1500:]


@pytest.mark.tre
@pytest.mark.skipif(not HAVE_DAEMON, reason="no dbus-daemon")
def test_one_value_sent_in_a_module_process_of_l1_reaches_the_surfaces(sandbox: R.Rig) -> None:
    got = M.measure_latency(
        sandbox,
        M.L1,
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
def test_a_hung_and_a_killed_module_process_are_contained_and_restarted_in_l1(
    sandbox: R.Rig,
) -> None:
    """In L the scrolling test node keeps painting while a module process's callback sleeps and
    while the process is killed; the hung one is detected, killed and started again. (One cell:
    the hang and the kill take 12 s; the services variant does not change what is contained, B1
    and B2 are checked the same way in ``tests/test_module_process.py``.)"""
    got = M.measure_containment(
        sandbox, M.L1, hang_seconds=1.5, stall=0.3, kill=1.0, baseline=1.0, reload=False
    )
    assert got["base"]["changed"] > 0.5  # the test node does paint
    for phase in ("hang_paint", "crash_paint"):
        assert got[phase]["changed"] > 0.5 and got[phase]["max_gap_s"] < 1.0, (phase, got[phase])
    assert got["hang_detect_s"] is not None and got["hang_recover_s"] is not None
    assert got["crash_restart_s"] > 0
    assert "ended" in got["crash_log"] and "Victim" in got["crash_log"]


# -- the harness: what a run plans -------------------------------------------------------------


def test_a_lean_run_plans_a_and_the_lean_cells_on_the_default_shell_only() -> None:
    todo = h.plan(h.parse(["--postures=A,L1,L2"]))
    assert todo.start == todo.idle == [("A", "default"), ("L1", "default"), ("L2", "default")]
    assert todo.probe == ["A", "L1", "L2"]  # no plus3 cell: A there would only be C's base


def test_the_cells_of_the_first_full_measurement_are_planned_as_before() -> None:
    todo = h.plan(h.parse([]))
    assert todo.start == [
        ("A", "default"),
        ("B1", "default"),
        ("B2", "default"),
        ("C1", "default"),
        ("A", "plus3"),
        ("C1", "plus3"),
        ("C2", "plus3"),
    ]
    assert todo.probe == ["A", "B1", "B2", "C1", "C2"]
    assert h.plan(h.parse(["--postures=A,B1"])).start == [("A", "default"), ("B1", "default")]


def test_an_unknown_posture_is_refused_and_the_lean_ones_are_known() -> None:
    assert {"L1", "L2"} <= set(M.ALL)
    with pytest.raises(SystemExit, match="unknown posture 'L3'"):
        h.plan(h.parse(["--postures=A,L3"]))
    args = h.parse(["--postures=A,L1", "--latency-reps=1", "--contain-reps=2", "--reps=3"])
    assert (args.reps, args.latency_reps, args.contain_reps) == (3, 1, 2)
    assert h.parse(["--lean-rule=validate"]).lean_rule == "validate"
    assert h.parse([]).lean_rule == "strict"


def test_the_lead_s_lean_commands_plan_a_l1_and_l2_and_write_their_own_report() -> None:
    for command in (h.LEAN_RUN, h.LEAN_RUN_VALIDATE):
        args = h.parse(command)
        assert args.postures == "A,L1,L2"
        assert args.out != h.parse([]).out  # the report of the full run stays as it is
        assert 10 < h.estimate_minutes(args) < 25  # the lead asked for 15 to 20 minutes
    assert h.parse(h.LEAN_RUN_VALIDATE).lean_rule == "validate"


# -- the harness: the verdict table with the lean rows -----------------------------------------


@pytest.mark.parametrize(
    ("test", "limit", "arg"),
    [
        ("Start", h.START_EXTRA_MS, "start"),
        ("Wake-ups", h.WAKEUPS_EXTRA_PER_S, "wake"),
        ("Memory", h.MEMORY_EXTRA_MB, "pss"),
    ],
)
def test_a_cost_row_of_l_passes_at_its_threshold_and_fails_just_over_it(
    test: str, limit: float, arg: str
) -> None:
    """The same thresholds as B and C, against A of the same run, for each lean cell on its own."""
    for cell in ("L1", "L2"):
        other = "L2" if cell == "L1" else "L1"
        for delta, passes in ((0.0, True), (0.5, False), (-0.5, True)):
            res = canned(only=("L1", "L2"), cells={cell: {arg: limit + delta}})
            assert verdict(res, test, cell) is passes, (cell, delta)
            assert verdict(res, test, other) is True  # the other cell is at A's numbers


def test_value_to_screen_and_containment_of_l_have_their_rows() -> None:
    for test in ("Value to screen, single", "Value to screen, burst"):
        assert verdict(canned(only=("L1",), p95=16.6), test, "L1") is True
        assert verdict(canned(only=("L1",), p95=16.8), test, "L1") is False
    assert verdict(canned(only=("L2",)), "Containment", "L2") is True
    bad = rep(hang=0.4)
    assert verdict(canned(only=("L2",), contain=bad), "Containment", "L2") is False
    no_restart = rep()
    no_restart["crash_restart_s"] = None
    assert verdict(canned(only=("L1",), contain=no_restart), "Containment", "L1") is False


def test_a_run_without_lean_cells_has_no_lean_rows_and_an_unmeasured_one_is_none() -> None:
    assert not [r for r in h.verdicts(canned()) if r.cell in ("L1", "L2")]
    assert verdict(canned(only=("L1",), postures="A,L1,L2"), "Start", "L2") is None


def test_a_lean_run_has_no_b_or_c_rows_and_a_full_run_has_every_row() -> None:
    lean = canned(only=("L1", "L2"), postures="A,L1,L2")
    assert {r.cell for r in h.verdicts(lean)} == {"L1", "L2"}
    full = canned(only=("B1", "B2", "C1", "C2", "L1", "L2"), postures="A,B1,B2,C1,C2,L1,L2")
    assert {r.cell for r in h.verdicts(full)} == {"B1", "B2", "C1", "C2", "L1", "L2"}
    legacy = canned(postures="A,B1,B2,C1,C2")  # not asked for L: no L row, B and C as before
    assert {r.cell for r in h.verdicts(legacy)} == {"B1", "B2", "C1", "C2"}


def dec(**kwargs: Any) -> str:
    return " ".join(h.decision(h.verdicts(canned(**kwargs))))


OVER = h.MEMORY_EXTRA_MB + 0.5
ALL_CELLS = ("B1", "B2", "C1", "C2", "L1", "L2")


def test_when_b_fails_and_l_passes_the_shell_moves_to_l() -> None:
    """The first full measurement's numbers: B pays 372 MB (over 150), C and L stay within."""
    text = dec(only=ALL_CELLS, cells={"B1": {"pss": 372}, "B2": {"pss": 357}})
    assert "B fails a row and L passes every row (L1, L2): by the rule the shell moves to L" in text
    assert "C passes every row too (C1, C2)" in text and "moves to C" not in text


def test_l_at_the_memory_limit_passes_and_just_over_it_fails() -> None:
    b_fails = {"B1": {"pss": OVER}, "B2": {"pss": OVER}}
    at = dec(only=ALL_CELLS, cells={**b_fails, "L1": {"pss": h.MEMORY_EXTRA_MB}})
    assert "L passes every row (L1, L2)" in at
    over = dec(only=ALL_CELLS, cells={**b_fails, "L1": {"pss": OVER}, "L2": {"pss": OVER}})
    assert "moves to L" not in over and "moves to C" in over  # C passes: the rule falls to C
    one = dec(only=ALL_CELLS, cells={**b_fails, "L2": {"pss": OVER}})
    assert "L passes every row (L1)" in one  # one variant is enough, and only it is named


def test_b_passing_every_row_is_b_and_nothing_passing_is_a() -> None:
    assert "moves to B" in dec(only=ALL_CELLS)
    nothing = dec(only=ALL_CELLS, pss=OVER)
    assert "A stays" in nothing and "moves to" not in nothing
    # L fails too but C passes: the earlier rule is unchanged
    assert "moves to C" in dec(
        only=ALL_CELLS,
        cells={"B1": {"pss": OVER}, "B2": {"pss": OVER}, "L1": {"pss": OVER}, "L2": {"pss": OVER}},
    )


def test_a_lean_run_cannot_apply_the_first_step_and_says_what_l_gives() -> None:
    lean = {"only": ("L1", "L2"), "postures": "A,L1,L2"}
    ok = dec(**lean)
    assert "B was not measured in this run" in ok
    assert "L passes every row (L1, L2)" in ok and "moves to L" in ok and "moves to B" in ok
    bad = dec(**lean, cells={"L1": {"pss": OVER}})
    assert "L passes every row (L2)" in bad  # one variant passing is enough
    both = dec(**lean, cells={"L1": {"pss": OVER}, "L2": {"wake": 2.5}})
    assert "L1 fails Memory" in both and "L2 fails Wake-ups" in both
    assert "moves to L" not in both
    missing = dec(only=("L1",), postures="A,L1,L2")  # L2 was asked for and has no numbers
    assert "cannot be applied" in missing


def test_the_rule_of_a_run_without_l_is_what_it_was() -> None:
    assert "moves to B" in dec()
    assert "A stays" in dec(pss=OVER)
    assert "cannot be applied" in dec(only=("B1",))


# -- the harness: the report of a lean run -----------------------------------------------------


def full_results(res: dict[str, Any], kids: list[str], stay: list[str]) -> dict[str, Any]:
    """``canned`` numbers with every field the report reads, as a run writes them."""
    for key, got in res["start"].items():
        got.update(processes=[2 if key.startswith("A") else 21] * 3, load=[0.1] * 3)
    for key, reps in res["idle"].items():
        for r in reps:
            r.update(
                cpu_percent=0.05,
                rss_mb=220.0,
                processes=2 if key.startswith("A") else 21,
                threads=80,
                load=0.1,
                ready_ms=300.0,
                children=[] if key.startswith("A") else kids,
                in_shell=[] if key.startswith("A") else stay,
            )
    for reps in res["latency"].values():
        for r in reps:
            r.update(throughput=10000, steps=[{"p95": 0.3, "sent_per_s": 200}] * 2, load=0.1)
    for label, reps in res["contain"].items():
        for r in reps:
            r.update(
                base={"changed": 0.96, "max_gap_s": 0.03},
                hang_detect_s=2.9 if label != "A" else None,
                hang_returned_s=10.0,
                crash_log="module Victim: the module process ended",
                reload_s=0.3,
                load=0.1,
            )
    res["errors"] = []
    return res


def test_the_report_of_a_lean_run_has_the_rows_the_rule_and_the_module_counts() -> None:
    kids = sorted(DEFAULT_SHELL - STAYS["strict"])
    stay = sorted(STAYS["strict"])
    args = h.parse(list(h.LEAN_RUN))
    res = canned(only=("L1", "L2"), postures="A,L1,L2", cells={"L2": {"pss": 100}})
    res = full_results(res, kids, stay)
    res["args"] = {k: str(v) for k, v in vars(args).items()}
    res["elapsed_s"] = 600.0
    text = h.report(res, {"machine": "test"}, args, False)
    # the rows of L against A, the rule, the which-one comparison, the counts of the module files
    assert "| Memory | L1 | +0 MB | <= 150 MB | PASS |" in text
    assert "| Memory | L2 | +100 MB | <= 150 MB | PASS |" in text
    assert "B was not measured in this run" in text and "moves to L" in text
    assert "## Which lean B: L1 or L2" in text and "## Which B: B1 or B2" not in text
    assert "**This run used the rule `strict`**" in text
    assert "**23** module files: **19 run in a process** and **4 stay in the shell**" in text
    # the maintainer expected 13 staying and 9 in processes
    assert "this run gives 4 staying and 19 in processes" in text
    assert "`strict`: 19 in processes, 4 in the shell" in text
    assert "`validate`: 11 in processes, 12 in the shell" in text
    assert "| Menu | shell |" in text and "| Clock | process |" in text
    assert "### The lean B only" in text and "--postures=A,L1,L2" in text
    assert "Run time of this measurement: 10.0 minutes." in text
    assert "Containment | L1 | 1 of 1 repetitions" in text


def which(**cells: dict[str, Any]) -> str:
    res = canned(only=("L1", "L2"), postures="A,L1,L2", cells=cells)
    return h.better_variant(res, h.verdicts(res), "L1", "L2", "lean B")


def test_the_better_lean_variant_fails_fewer_rows_else_uses_less_memory() -> None:
    assert "**L2** is the better lean B (it passes more of them)" in which(L1={"pss": OVER})
    both_fail = which(L1={"pss": OVER, "wake": 2.5}, L2={"pss": OVER})
    assert "**L2** is the better lean B (it fails fewer of them" in both_fail
    assert "L1 fails Memory, Wake-ups; L2 fails Memory" in both_fail
    tie = which(L1={"pss": 40}, L2={"pss": 30})
    assert "pass the same rows; **L2** uses less memory (190 MB against 200 MB" in tie
    same_fail = which(L1={"pss": OVER + 10}, L2={"pss": OVER})
    assert "fail the same rows; **L2** uses less memory" in same_fail
    other_fail = which(L1={"pss": OVER}, L2={"wake": 2.5})
    assert "fail different rows (L1: Memory; L2: Wake-ups)" in other_fail
