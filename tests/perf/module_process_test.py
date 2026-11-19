"""The module process test (M7a2; ``60 Quality/Module Process Test.md``): the shell with every module
in its process (A), with one process per module file (B), with only the user's modules in
processes (C) and with a lean B, only the module files that have Python of their own in processes
(L), on the same default shell, on one machine.

Not collected by pytest (``tests/perf/conftest.py``). The smoke test of the harness is
``tests/test_module_process_smoke.py``. Run from the repository root, on an IDLE machine:

    env -u WAYLAND_DISPLAY -u DISPLAY uv run python tests/perf/module_process_test.py

That is the full measurement (about 80 minutes; see the report for what must not be running). A short
run that only proves the harness works:

    env -u WAYLAND_DISPLAY -u DISPLAY uv run python tests/perf/module_process_test.py --smoke \\
        --out /tmp/module-process-smoke.md

The lean B only (A as the baseline; every flag of the full run applies; ``--out`` keeps the default
report as it is; ``--lean-rule=validate`` also keeps the widget modules whose Python is only a
``validate_use`` check in the shell, see ``has_own_code`` in ``tests/perf/proto/parent.py``):

    env -u WAYLAND_DISPLAY -u DISPLAY uv run python tests/perf/module_process_test.py \\
        --postures=A,L1,L2 --reps=3 --latency-reps=1 --contain-reps=2 --start-runs=15 \\
        --out tests/perf/module-process-results-lean.md

Everything runs on a private headless sway and private buses (``tests/perf/proto/rig.py``), never
the user's session. The 1-minute load average must be 0.5 or less at the start, or the harness
refuses (``--allow-load`` overrides it, and the report then says it was loaded). The report is
``tests/perf/module-process-results.md`` with the raw numbers in the ``.json`` beside it. The harness
computes the verdict table of the decision rule from the thresholds below; the maintainer decides.
"""

from __future__ import annotations

import argparse
import datetime
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
import time
import traceback
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO))

from tests.perf.proto import measure as M  # noqa: E402
from tests.perf.proto import rig as R  # noqa: E402
from tests.perf.proto.parent import RULES, SHIPPED, has_own_code  # noqa: E402

# -- the decision rule's starting thresholds (Module Process Test > Decision Rule): change them HERE
START_EXTRA_MS = 300.0  # the whole default shell ready no more than this much later than A
WAKEUPS_EXTRA_PER_S = 2.0  # no more than this many context switches a second above A
LATENCY_P95_MS = 16.7  # value to screen: p95 within one frame, single updates and the burst
MEMORY_EXTRA_MB = 150.0  # the whole tree (PSS) grows by no more than this over A
CONTAIN_MIN_FPS_RATIO = 0.5  # while a module hangs or dies the test node paints at least this share
CONTAIN_MAX_GAP_S = 1.0  # ... and never stops for longer than this
# -- the budgets of Performance Budgets, shown beside the rule (informational rows)
BUDGET_IDLE_CPU_PERCENT = 0.5
BUDGET_WAKEUPS_PER_S = 5.0
BUDGET_READY_S = 2.0
LOAD_LIMIT = 0.5  # the 1-minute load average the harness starts under

LEGACY_CELLS = ("B1", "B2", "C1", "C2")  # the cells of the first full measurement
LEAN_CELLS = ("L1", "L2")  # lean B: the module files with Python of their own in processes
DEFAULT_CELLS = ("A", "B1", "B2", "C1", "L1", "L2")  # the default shell
PLUS3_CELLS = ("A", "C1", "C2")  # the default shell and three user modules
# the latency probe and the containment victim
PROBE_CELLS = ("A", "B1", "B2", "C1", "C2", "L1", "L2")
ALL_MEASURES = ("start", "idle", "latency", "contain")
# the lean B run of the lead: A as the baseline and L1, L2; three repetitions of start and idle, fewer
# of latency and containment (a report of its own: the default file keeps the full run)
LEAN_RUN = (
    "--postures=A,L1,L2",
    "--reps=3",
    "--latency-reps=1",
    "--contain-reps=2",
    "--start-runs=15",
    "--out=tests/perf/module-process-results-lean.md",
)
# the same with the rule `validate` (the widget modules whose Python is only the check of their
# parameters stay in the shell too): a report of its own
LEAN_RUN_VALIDATE = (
    *LEAN_RUN[:-1],
    "--lean-rule=validate",
    "--out=tests/perf/module-process-results-lean-validate.md",
)
# what a step costs beyond its own window, in seconds (measured on the machine: a start to READY=1
# and its stop about 1.5 s; an idle repetition of 60 s + 10 s settle took 70.7 s; a latency repetition
# at the default flags 45.0 s for 43 s of windows; a containment repetition 22.8 s in L1 and 17.0 s in
# A against 13 s of baseline and hang); only for the "expected duration" of the report
EST_START_RUN_S = 1.5
EST_IDLE_EXTRA_S = 1.5
EST_LATENCY_EXTRA_S = 2.0
EST_CONTAIN_EXTRA_S = 10.0

SMOKE = dict(
    start_runs=2,
    reps=1,
    idle=3.0,
    settle=1.0,
    singles=20,
    gap_ms=10,
    burst_rate=200.0,
    burst_seconds=1.0,
    ladder="200,1000",
    ladder_seconds=1.0,
    hang=3.0,
    stall=0.5,
    kill=1.5,
    baseline=1.5,
)


def parse(argv: Sequence[str] | None) -> argparse.Namespace:
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--smoke", action="store_true")
    known, _ = pre.parse_known_args(argv)
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--smoke", action="store_true", help="short durations: proves the harness works")
    p.add_argument(
        "--postures",
        default="A,B1,B2,C1,C2",
        help="cells to run (default: A,B1,B2,C1,C2; the lean B is L1,L2, e.g. A,L1,L2)",
    )
    p.add_argument("--measures", default=",".join(ALL_MEASURES), help="start,idle,latency,contain")
    p.add_argument("--reps", type=int, default=3, help="repetitions of idle, latency, containment")
    p.add_argument("--start-runs", type=int, default=20, help="starts for the start time")
    p.add_argument("--latency-reps", type=int, default=None, help="repetitions of latency (--reps)")
    p.add_argument("--contain-reps", type=int, default=None, help="repetitions of containment")
    p.add_argument("--idle", type=float, default=60.0, help="seconds of the idle window")
    p.add_argument("--settle", type=float, default=10.0, help="seconds of rest before the window")
    p.add_argument("--singles", type=int, default=1000, help="single updates for the latency")
    p.add_argument("--gap-ms", type=int, default=20, help="milliseconds between single updates")
    p.add_argument("--burst-rate", type=float, default=200.0, help="values a second in the burst")
    p.add_argument("--burst-seconds", type=float, default=5.0, help="seconds of the burst")
    p.add_argument("--ladder", default="200,500,1000,2000,5000,10000", help="rates for throughput")
    p.add_argument("--ladder-seconds", type=float, default=3.0, help="seconds at each rate")
    p.add_argument("--hang", type=float, default=10.0, help="seconds the callback sleeps")
    p.add_argument("--stall", type=float, default=2.0, help="B/C watchdog: seconds to log a stall")
    p.add_argument("--kill", type=float, default=5.0, help="B/C watchdog: seconds to kill")
    p.add_argument("--baseline", type=float, default=3.0, help="seconds of paint before the tests")
    p.add_argument("--allow-load", action="store_true", help="start although the load is above 0.5")
    p.add_argument(
        "--lean-rule",
        choices=RULES,
        default="strict",
        help="L1, L2: which module files have Python of their own (strict: no class body but pass; "
        "validate: also a literal constant and a validate_use method)",
    )
    p.add_argument("--out", type=Path, default=HERE / "module-process-results.md")
    if known.smoke:
        p.set_defaults(**SMOKE)
    return p.parse_args(argv)


# -- the machine -------------------------------------------------------------------------------


def sh(*argv: str) -> str:
    try:
        return subprocess.run(
            argv, cwd=REPO, capture_output=True, text=True, check=False, timeout=20
        ).stdout.strip()
    except OSError, subprocess.TimeoutExpired:
        return ""


def machine() -> dict[str, str]:
    cpu = next(
        (
            line.split(":", 1)[1].strip()
            for line in Path("/proc/cpuinfo").read_text().splitlines()
            if line.startswith("model name")
        ),
        "?",
    )
    mem = next(
        (
            line.split()[1]
            for line in Path("/proc/meminfo").read_text().splitlines()
            if line.startswith("MemTotal")
        ),
        "0",
    )
    import tess_shell

    gil = "with the GIL" if getattr(sys, "_is_gil_enabled", lambda: True)() else "free-threaded"
    return {
        "machine": f"{platform.uname().node} ({platform.uname().machine})",
        "kernel": platform.uname().release,
        "cpu": f"{cpu}, {os.cpu_count()} threads",
        "memory": f"{int(mem) / 1024 / 1024:.1f} GiB",
        "python": f"{platform.python_version()} ({gil})",
        "tesserae-engine": importlib.metadata.version("tesserae-engine"),
        "tesserae-shell": tess_shell.__version__,
        "git": f"{sh('git', 'rev-parse', '--short', 'HEAD')} on {sh('git', 'branch', '--show-current')}",
        "load average at the start": " ".join(f"{x:.2f}" for x in os.getloadavg()),
        "date": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "compositor": "private headless sway, pixman renderer, 1280x720",
    }


def refuse_when_loaded(allow: bool) -> bool:
    """True when the harness goes on loaded; exits with a message when it must not."""
    load = os.getloadavg()[0]
    if load <= LOAD_LIMIT:
        return False
    if allow:
        print(f"WARNING: load average {load:.2f} is above {LOAD_LIMIT}; --allow-load: going on")
        return True
    sys.exit(
        f"refusing to start: the 1-minute load average is {load:.2f} (the limit is {LOAD_LIMIT}). "
        "The numbers of a loaded machine mean nothing. Stop what is running (builds, CI jobs, "
        "browsers, other agents) and try again, or pass --allow-load to measure anyway (the report "
        "will say it was loaded)."
    )


# -- running -----------------------------------------------------------------------------------


@dataclass
class Plan:
    start: list[tuple[str, str]]
    idle: list[tuple[str, str]]
    probe: list[str]


def plan(args: argparse.Namespace) -> Plan:
    wanted = [c for c in args.postures.split(",") if c]
    for c in wanted:
        if c not in M.ALL:
            sys.exit(f"unknown posture {c!r}: use {', '.join(M.ALL)}")
    cells = [(c, "default") for c in DEFAULT_CELLS if c in wanted]
    plus3 = [c for c in PLUS3_CELLS if c in wanted]
    if any(c != "A" for c in plus3):  # A alone has no use there: it is the base of C's rows
        cells += [(c, "plus3") for c in plus3]
    return Plan(cells, cells, [c for c in PROBE_CELLS if c in wanted])


def say(text: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {text}", flush=True)


def run(args: argparse.Namespace) -> dict[str, Any]:
    wanted = set(args.measures.split(","))
    latency_reps = args.latency_reps or args.reps
    contain_reps = args.contain_reps or args.reps
    todo = plan(args)
    os.environ["TESS_PROTO_LEAN_RULE"] = args.lean_rule  # read by the shell (rig.Shell passes it)
    res: dict[str, Any] = {
        "args": {k: str(v) for k, v in vars(args).items()},
        "start": {},
        "idle": {},
        "latency": {},
        "contain": {},
        "errors": [],
    }

    def attempt(label: str, fn: Any, *a: Any, **kw: Any) -> Any:
        say(label)
        try:
            return fn(*a, **kw)
        except Exception as exc:
            res["errors"].append(f"{label}: {type(exc).__name__}: {exc}")
            say(f"FAILED {label}: {exc}\n{traceback.format_exc(limit=4)}")
            return None

    if "idle" in wanted:
        res["floor"] = attempt("floor of an idle Python process", M.measure_floor)
    with R.rig() as rig:
        if "start" in wanted:
            for label, kind in todo.start:
                got = attempt(
                    f"start {label}/{kind} x{args.start_runs}",
                    M.measure_start,
                    rig,
                    M.ALL[label],
                    kind,
                    args.start_runs,
                )
                if got is not None:
                    res["start"][f"{label}/{kind}"] = got
        if "idle" in wanted:
            for label, kind in todo.idle:
                reps = []
                for n in range(args.reps):
                    got = attempt(
                        f"idle {label}/{kind} rep {n + 1}/{args.reps} ({args.idle:g} s)",
                        M.measure_idle,
                        rig,
                        M.ALL[label],
                        kind,
                        args.idle,
                        args.settle,
                    )
                    if got is not None:
                        reps.append(got)
                res["idle"][f"{label}/{kind}"] = reps
        if "latency" in wanted:
            ladder = [float(x) for x in args.ladder.split(",") if x]
            for label in todo.probe:
                reps = []
                for n in range(latency_reps):
                    got = attempt(
                        f"latency {label} rep {n + 1}/{latency_reps}",
                        M.measure_latency,
                        rig,
                        M.ALL[label],
                        singles=args.singles,
                        gap_ms=args.gap_ms,
                        burst_rate=args.burst_rate,
                        burst_seconds=args.burst_seconds,
                        ladder=ladder,
                        ladder_seconds=args.ladder_seconds,
                        frame_ms=LATENCY_P95_MS,
                    )
                    if got is not None:
                        reps.append(got)
                res["latency"][label] = reps
        if "contain" in wanted:
            for label in todo.probe:
                reps = []
                for n in range(contain_reps):
                    got = attempt(
                        f"containment {label} rep {n + 1}/{contain_reps}",
                        M.measure_containment,
                        rig,
                        M.ALL[label],
                        hang_seconds=args.hang,
                        stall=args.stall,
                        kill=args.kill,
                        baseline=args.baseline,
                    )
                    if got is not None:
                        reps.append(got)
                res["contain"][label] = reps
    return res


def estimate_parts(args: argparse.Namespace) -> dict[str, float]:
    """Seconds each measure of the run takes, from the flags and the step times above."""
    wanted = set(args.measures.split(","))
    todo = plan(args)
    ladder = [x for x in args.ladder.split(",") if x]
    parts = {
        "start": len(todo.start) * args.start_runs * EST_START_RUN_S if "start" in wanted else 0,
        "idle": len(todo.idle)
        * args.reps
        * (args.settle + args.idle + EST_IDLE_EXTRA_S)
        * ("idle" in wanted),
        "latency": len(todo.probe)
        * (args.latency_reps or args.reps)
        * (
            EST_LATENCY_EXTRA_S
            + args.singles * args.gap_ms / 1000
            + args.burst_seconds
            + len(ladder) * args.ladder_seconds
        )
        * ("latency" in wanted),
        "containment": len(todo.probe)
        * (args.contain_reps or args.reps)
        * (EST_CONTAIN_EXTRA_S + args.baseline + args.hang)
        * ("contain" in wanted),
    }
    return parts


def estimate_minutes(args: argparse.Namespace) -> float:
    return sum(estimate_parts(args).values()) / 60


def estimate_text(args: argparse.Namespace) -> str:
    return ", ".join(f"{k} {v / 60:.1f}" for k, v in estimate_parts(args).items()) + " minutes"


# -- numbers -----------------------------------------------------------------------------------


def span(values: Sequence[float], digits: int = 1) -> str:
    """``median (min to max)`` of the values."""
    clean = [v for v in values if v is not None and not math.isnan(v)]
    if not clean:
        return "-"
    s = M.stat(clean)
    if s.n == 1:
        return f"{s.median:.{digits}f}"
    return f"{s.median:.{digits}f} ({s.lo:.{digits}f} to {s.hi:.{digits}f})"


def med(values: Sequence[float]) -> float:
    clean = [v for v in values if v is not None and not math.isnan(v)]
    return M.stat(clean).median if clean else math.nan


def idle_values(res: dict[str, Any], key: str, field: str) -> list[float]:
    return [r[field] for r in res["idle"].get(key, [])]


def lat_pool(res: dict[str, Any], label: str, field: str, q: float) -> list[float]:
    """The ``q`` percentile of each repetition's latencies."""
    return [M.percentile(r[field], q) for r in res["latency"].get(label, []) if r.get(field)]


def contain_pass(rep: dict[str, Any], posture: str) -> tuple[bool, str]:
    """Did the surfaces keep painting and did the module come back, in one repetition?"""
    base = rep["base"]["changed"] or 1e-9
    notes: list[str] = []
    ok = True
    hang = rep["hang_paint"]
    if hang["changed"] < CONTAIN_MIN_FPS_RATIO * base or hang["max_gap_s"] > CONTAIN_MAX_GAP_S:
        ok = False
        notes.append(
            f"hang: picture changed in {hang['changed']:.0%} of the captures, "
            f"longest stop {hang['max_gap_s']:.1f} s"
        )
    if rep.get("hang_recover_s") is None:
        ok = False
        notes.append("hang: no restart")
    if posture != "A":
        crash = rep.get("crash_paint")
        if crash is None or rep.get("crash_restart_s") is None:
            ok = False
            notes.append("crash: no restart")
        elif (
            crash["changed"] < CONTAIN_MIN_FPS_RATIO * base
            or crash["max_gap_s"] > CONTAIN_MAX_GAP_S
        ):
            ok = False
            notes.append(
                f"crash: picture changed in {crash['changed']:.0%} of the captures, "
                f"longest stop {crash['max_gap_s']:.1f} s"
            )
    return ok, "; ".join(notes)


@dataclass
class Row:
    test: str
    cell: str
    measured: str
    threshold: str
    ok: bool | None  # None: not measured


def cost_rows(res: dict[str, Any], label: str, kind: str, base: str, note: str) -> list[Row]:
    """Start, wake-ups and memory of ``label`` on the shell ``kind`` against ``base`` (A on the same
    shell), as the three rows of the decision rule."""
    key = f"{label}/{kind}"
    start_a = med(res["start"].get(base, {}).get("ready_ms", []))
    wake_a = med(idle_values(res, base, "wakeups_per_s"))
    pss_a = med(idle_values(res, base, "pss_mb"))
    out: list[Row] = []
    ready = res["start"].get(key, {}).get("ready_ms", [])
    wake = idle_values(res, key, "wakeups_per_s")
    pss = idle_values(res, key, "pss_mb")
    for name, mine, ref, limit, unit, digits in (
        ("Start", [x for x in ready], start_a, START_EXTRA_MS, "ms", 0),
        ("Wake-ups", wake, wake_a, WAKEUPS_EXTRA_PER_S, "per s", 2),
        ("Memory", pss, pss_a, MEMORY_EXTRA_MB, "MB", 0),
    ):
        passes = f"<= {limit:g} {unit}"
        if mine and not math.isnan(ref):
            extra = med(mine) - ref
            out.append(
                Row(name + note, label, f"{extra:+.{digits}f} {unit}", passes, extra <= limit)
            )
        else:
            out.append(Row(name + note, label, "not measured", passes, None))
    return out


def asked(res: dict[str, Any]) -> set[str] | None:
    """The cells the run was asked for (``--postures``); None for results that do not say."""
    got = res.get("args", {}).get("postures")
    return {c for c in str(got).split(",") if c} if got else None


def has_rows(res: dict[str, Any], label: str) -> bool:
    """Does ``label`` have rows in the verdict table? The cells of the first full measurement
    always do (a cell that was not measured shows ``not measured``), except in a lean run (the
    lean cells and no other): B and C were not asked for there. A lean cell has rows when it was
    asked for, or, when the results do not say, when any of its numbers is there."""
    want = asked(res)
    if label in LEAN_CELLS:
        if want is not None:
            return label in want
        return any(
            f"{label}/default" in res[s] if s in ("start", "idle") else label in res[s]
            for s in ("start", "idle", "latency", "contain")
        )
    lean_run = want is not None and bool(want & set(LEAN_CELLS)) and not want & set(LEGACY_CELLS)
    return not lean_run


def verdicts(res: dict[str, Any]) -> list[Row]:
    rows: list[Row] = []
    for label in ("B1", "B2", "C1", "L1", "L2"):
        if has_rows(res, label):
            rows += cost_rows(res, label, "default", "A/default", "")
    for label in ("C1", "C2"):
        if has_rows(res, label):
            rows += cost_rows(res, label, "plus3", "A/plus3", " (+3 user modules)")
    for label in ("B1", "B2", "C1", "C2", "L1", "L2"):
        if not has_rows(res, label):
            continue
        for name, field in (
            ("Value to screen, single", "single_ms"),
            ("Value to screen, burst", "burst_ms"),
        ):
            p95 = lat_pool(res, label, field, 0.95)
            if p95:
                rows.append(
                    Row(
                        name,
                        label,
                        f"p95 {med(p95):.2f} ms",
                        f"<= {LATENCY_P95_MS:g} ms",
                        med(p95) <= LATENCY_P95_MS,
                    )
                )
            else:
                rows.append(Row(name, label, "not measured", f"<= {LATENCY_P95_MS:g} ms", None))
        reps = res["contain"].get(label, [])
        if reps:
            outcomes = [contain_pass(r, label[0]) for r in reps]
            ok = all(o for o, _ in outcomes)
            notes = "; ".join(n for _, n in outcomes if n)
            rows.append(
                Row(
                    "Containment",
                    label,
                    f"{sum(o for o, _ in outcomes)} of {len(outcomes)} repetitions"
                    + (f" ({notes})" if notes else ""),
                    "hang and kill: surfaces paint, module restarts",
                    ok,
                )
            )
        else:
            rows.append(
                Row("Containment", label, "not measured", "hang and kill: surfaces paint", None)
            )
    return rows


def decision(rows: list[Row]) -> list[str]:
    """What the decision rule gives for the numbers, as a computed sentence; the maintainer decides.

    The rule: B passes every row: B. B fails a row and L (lean B: only the files with Python of
    their own in processes) passes every row: L. B fails and C passes: C. None passes: A stays. A
    run that has no B rows (a lean run) cannot apply the first step: it says what L gives and what
    follows from B's result in the other run."""
    out: list[str] = []
    by_cell: dict[str, list[Row]] = {}
    for r in rows:
        by_cell.setdefault(r.cell, []).append(r)

    def passes(cell: str) -> bool | None:
        got = by_cell.get(cell, [])
        if not got or any(r.ok is None for r in got):
            return None
        return all(bool(r.ok) for r in got)

    def failed(cell: str) -> str:
        names = sorted({r.test for r in by_cell.get(cell, []) if r.ok is False})
        return f"{cell} fails {', '.join(names)}"

    got = {k: passes(k) for k in ("B1", "B2", "C1", "C2", "L1", "L2") if k in by_cell}
    if any(v is None for v in got.values()):
        out.append("Some rows were not measured in this run, so the rule cannot be applied.")
        return out
    b = {k: v for k, v in got.items() if k[0] == "B"}
    c = {k: v for k, v in got.items() if k[0] == "C"}
    lean = {k: v for k, v in got.items() if k[0] == "L"}
    pass_l = ", ".join(k for k, v in lean.items() if v)
    pass_c = ", ".join(k for k, v in c.items() if v)
    if not b and lean:
        if pass_l:
            out.append(
                f"B was not measured in this run, so the rule's first step is not applied here. "
                f"L passes every row ({pass_l}): if B fails a row (see the B rows of the full "
                "measurement), by the rule the shell moves to L; if B passes every row, it moves "
                "to B."
            )
        else:
            out.append(
                "B was not measured in this run. L does not pass every row "
                f"({'; '.join(failed(k) for k in lean)}): by the rule L is not the answer to a B "
                "that fails; C (not measured here) or A follows."
            )
        return out
    if any(b.values()):
        which = ", ".join(k for k, v in b.items() if v)
        out.append(f"B passes every row ({which}): by the rule the shell moves to B before 1.0.")
    elif pass_l:
        out.append(
            f"B fails a row and L passes every row ({pass_l}): by the rule the shell moves to L."
        )
        if pass_c:
            out.append(
                f"C passes every row too ({pass_c}). The rule as written gives L when B fails and L "
                "passes; the maintainer chooses between L (every module with Python of its own "
                "in a process) and C (only the user's modules)."
            )
    elif any(c.values()):
        out.append(
            f"B fails a row and C passes every row ({pass_c}): by the rule the shell moves to C."
        )
    elif lean:
        out.append(
            "No form passes every row: by the rule A stays and the vault records why "
            f"({'; '.join(failed(k) for k in lean)})."
        )
    else:
        out.append(
            "Neither B nor C passes every row: by the rule A stays and the vault records why."
        )
    return out


# -- the report --------------------------------------------------------------------------------

LEFT_OUT = """\
The prototype runs the eight default modules, the Launcher's Applications and the widget modules they
use (22 module files in the default shell), and the three user modules of the test. It does not
support, and the report does not claim:

- `ctx.focus` (shortcut mode): not offered in a module process, `ctx.focus` raises.
- `Event.stop()`: the event is delivered to the process after the handler of the shell has returned,
  so a module cannot stop it; none of the shipped modules does. A real B needs a declared stop (a
  property of the handler) or a synchronous reply.
- The result of an `@action` (`Call` from the CLI or the control interface): the stub returns
  `None`, so `tesserae-shell call` prints `null` for a module in a process. A real B needs a reply
  (an RPC with a timeout) on that path.
- Actions that a module inherits from another user class, and classes that do not extend `Module`
  directly: the stub class is made from the file's syntax tree (nothing is imported in the shell), so
  it sees the `@action` methods of classes that extend `Module` themselves.
- Import and `__init__` errors of a module are reported when the process starts it, as the log
  line and a finding of `module-import`, not as the load-time findings of `check`. `tesserae-shell
  check` is not made aware of the patch (it would start the processes).
- `many-threads` and `slow-module` (M7a controls 5 and 6) for module processes: the shell's record
  of the running callback is replaced by a shared-memory record read by a watchdog that only knows
  "this callback has run for N seconds".
- The differences JSON makes: a tuple arrives as a list and an integer dictionary key as text. The
  prototype restores the one tuple that matters (the several results of a D-Bus `call`: the Tray
  tests `isinstance(reply, tuple)` on `GetLayout`, which the first B2 run broke), tags bytes as
  base64 (a tray icon's pixmap), and leaves every other tuple a list. A user module that tells the two
  apart would break the same way.
- Several uses of `ctx.send` ordering across modules, a module's `threading` objects shared with
  another module, and anything that reads a module's `sys.modules` entry from the shell.
- Real hardware: the test runs against the fakes (NetworkManager, UPower, MPRIS, StatusNotifier,
  KWin virtual desktops, PulseAudio) on private buses; KWin's window script is off, so Tasks shows no
  windows (its `ctx.windows` proxy ran, and its list stayed empty).
"""

CTX_TABLE = """\
| `ctx` member | In A | In the prototype | Needed a different design? |
|---|---|---|---|
| `name`, `uid`, `config`, `uses` | plain data in the shell | sent once at start; every change of `ctx.uses` is mirrored in order | no (data) |
| `log` | loguru in the shell | loguru in the process; each record is one line to the shell, which logs it under `module:<name>` | no |
| `send` | `ValueStore.send` on any thread, coalesced per use and key, one flush per loop turn | one JSON line (queued, a writer thread joins them); the shell's reader thread calls the same `ValueStore.send`, so coalescing and the one `call_soon` flush are unchanged | no (a hop and an encode) |
| `on_tick` | the shell's one time source | each process that subscribes has its own time-source thread (a Clock wakes its own process) | yes: either one wake-up per ticking process, or the shell sends tick messages |
| `call_soon` | the shell's loop thread | the module process's own loop (its main thread) | yes: "the loop" is now the module's |
| `popup`, `close_popup` | loop thread, no result | a message; the shell opens it on its loop | no |
| `update_popup`, `is_popup_open` | loop thread, return a bool at once | a request that waits for the shell (read: any thread; update: the shell's loop) | yes: a synchronous answer across a pipe, 5 s timeout |
| `surface` (`hide`, `focus`, `on_shown`), `announce` | loop thread, bool results | messages and requests; `on_shown` pushes | yes: as above |
| `apps` | memory reads of the shell's index | requests (`search`, `get`, `ready`); the index stays in the shell | yes: a round trip per `search` |
| `icons` | files read, pixels registered with the engine | requests; only the text references come back; pixmap and png bytes go as base64 | yes: the registry is the engine's, so B2-style by necessity |
| `windows` | loop-thread list, `activate` and so on return futures | the shell pushes a copy of the list on each change; the actions return futures completed by the reply | yes: a pushed snapshot |
| `dbus` | one `Layer` and one service thread for all modules | B1: a `Layer` and service thread in each process that uses it; B2: proxies, `get` and `call` are awaited coroutines on a proxy thread, the shell runs them on its layer and pushes the subscriptions' callbacks | B1 no; B2 yes (`Bus.run(coro)` runs in the process) |
| `audio` | one `AudioService` (one connection) | B1: one PulseAudio connection per process that uses it (Audio and Audio_Outputs are two files, so two); B2: the shell's connection, pushed state and futures | B1 no; B2 yes |
| `tray` | one `TrayService`, one host name | B1: the process owns a host name of its own; B2: the shell's | B1 no; B2 yes |
| `Module` hooks (`start`, `stop`, `reload`, `use_added`, ...) | direct calls on the loop | `start` (first time only) and `stop` wait for the process; the rest are messages | yes: `start()` of a restart or a reload no longer blocks the loop |
"""


def fmt_cell(res: dict[str, Any], section: str, key: str, field: str, digits: int = 1) -> str:
    if section == "start":
        got = res["start"].get(key)
        return span(got[field], digits) if got else "-"
    return span(idle_values(res, key, field), digits)


def md_table(head: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    lines += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(lines) + "\n"


def b2_lines(name: str, marker: str) -> int:
    """Non-blank lines of ``name`` from the line that holds ``marker`` to the end (the B2-only part)."""
    text = (HERE / "proto" / name).read_text().splitlines()
    start = next(i for i, line in enumerate(text) if marker in line)
    return sum(1 for line in text[start:] if line.strip())


def b1_lines() -> int:
    """Lines of ``child.py`` that build the process's own services."""
    text = (HERE / "proto" / "child.py").read_text().splitlines()
    start = next(i for i, line in enumerate(text) if "# -- services of this process (B1)" in line)
    end = next(i for i, line in enumerate(text) if "# -- the module ---" in line)
    return sum(1 for line in text[start:end] if line.strip())


MOVE = ("wire.py", "child.py", "parent.py", "brokers.py", "proxies.py")  # what a real B needs


def code_cost() -> tuple[str, str]:
    files = sorted((HERE / "proto").glob("*.py"))
    rows = []
    total = {"move": 0, "harness": 0}
    for f in files:
        count = sum(1 for line in f.read_text().splitlines() if line.strip())
        kind = "move" if f.name in MOVE else "harness"
        total[kind] += count
        what = "the move" if kind == "move" else "rig, fakes and measurements"
        rows.append([f"`tests/perf/proto/{f.name}`", str(count), what])
    rows.append(["**the move**", f"**{total['move']}**", "wire, child, parent, brokers, proxies"])
    rows.append(["**the harness**", f"**{total['harness']}**", "not part of a product"])
    table = md_table(["File of the prototype", "Lines (not blank)", "What it is"], rows)
    product = sh("git", "status", "--porcelain", "--", "src", "uv.lock")
    touched = product.splitlines() if product else []
    text = (
        "Product files (`src/`) changed by the prototype: "
        + (", ".join(touched) if touched else "none")
        + ". The prototype patches `ModuleHost._import` at run time "
        "(`tests/perf/proto/parent.py: install`) and reads its switches only in "
        "`tests/perf/proto/run_shell.py` and `parent.py`. Outside `tests/perf` and the smoke test, "
        "`pyproject.toml` (a long-line exemption for the report's markdown) and `CHANGELOG.md` are "
        "edited. A real move would change the shell by about the lines of **the move** (the launcher "
        "with its stub and watchdog, the child, the broker and the proxies), plus the hooks it needs "
        "in `ModuleHost` (an asynchronous `load` and `start`, a reply path for `call_action`, "
        "`Event.stop`)."
    )
    return table, text


def variant_table(res: dict[str, Any], labels: Sequence[str]) -> str:
    """Start, wake-ups, memory, processes and single-update latency of the cells on the default
    shell, one row each."""
    rows = []
    for label in labels:
        k = f"{label}/default"
        rows.append(
            [
                label,
                fmt_cell(res, "start", k, "ready_ms", 0),
                span(idle_values(res, k, "wakeups_per_s"), 2),
                span(idle_values(res, k, "pss_mb"), 0),
                span(idle_values(res, k, "processes"), 0),
                span(lat_pool(res, label, "single_ms", 0.95), 2),
            ]
        )
    return md_table(
        ["Variant", "Start ms", "Wake-ups / s", "PSS MB", "Processes", "Single p95 ms"], rows
    )


def better_variant(res: dict[str, Any], rows: list[Row], a: str, b: str, noun: str) -> str:
    """Which of the two services variants (``a``, ``b``) is better on this run: the one that passes
    more rows, else the one with less memory; empty when one of them has no rows."""
    ok = {
        c: all(bool(r.ok) for r in rows if r.cell == c)
        for c in (a, b)
        if any(r.cell == c for r in rows)
    }
    if len(ok) != 2:
        return ""
    pa = med(idle_values(res, f"{a}/default", "pss_mb"))
    pb = med(idle_values(res, f"{b}/default", "pss_mb"))
    if ok[a] != ok[b]:
        return f"By the rows above **{a if ok[a] else b}** is the better {noun} (it passes more of them).\n"
    fails = {c: sorted({r.test for r in rows if r.cell == c and r.ok is False}) for c in ok}
    if len(fails[a]) != len(fails[b]):
        fewer = a if len(fails[a]) < len(fails[b]) else b
        return (
            f"By the rows above **{fewer}** is the better {noun} (it fails fewer of them: "
            f"{a} fails {', '.join(fails[a])}; {b} fails {', '.join(fails[b])}).\n"
        )
    if math.isnan(pa) or math.isnan(pb):
        return ""
    same = (
        "pass the same rows"
        if not fails[a]
        else "fail the same rows"
        if fails[a] == fails[b]
        else f"fail different rows ({a}: {', '.join(fails[a])}; {b}: {', '.join(fails[b])})"
    )
    return (
        f"The two variants {same}; **{a if pa < pb else b}** uses less memory "
        f"({min(pa, pb):.0f} MB against {max(pa, pb):.0f} MB of PSS) and is the better {noun} "
        "on this run.\n"
    )


def own_lines(name: str) -> str:
    """Non-blank lines of the Python of a shipped module file (``-``: a user's file)."""
    path = SHIPPED / name / f"{name}_Module.py"
    if not path.is_file():
        return "-"
    return str(sum(1 for line in path.read_text().splitlines() if line.strip()))


def lean_split(res: dict[str, Any]) -> tuple[list[str], list[str]] | None:
    """``(module files in processes, module files in the shell)`` of the lean cells, as the
    posture decided them in the first idle repetition."""
    for label in LEAN_CELLS:
        for rep in res["idle"].get(f"{label}/default", []):
            if rep.get("children") is not None:
                return rep["children"], rep["in_shell"]
    return None


def lean_counts(names: Sequence[str]) -> dict[str, tuple[int, int]]:
    """``{rule: (module files in processes, module files in the shell)}`` for the shipped module
    files among ``names``, by each rule of ``has_own_code``."""
    out: dict[str, tuple[int, int]] = {}
    for rule in RULES:
        own = [
            has_own_code(SHIPPED / n / f"{n}_Module.py", rule)
            for n in names
            if (SHIPPED / n / f"{n}_Module.py").is_file()
        ]
        out[rule] = (sum(own), len(own) - sum(own))
    return out


def lean_section(res: dict[str, Any]) -> str:
    got = lean_split(res)
    if got is None:
        return ""
    kids, stay = got
    total = len(kids) + len(stay)
    rule = res.get("args", {}).get("lean_rule", "strict")
    counts = lean_counts([*kids, *stay])
    text = (
        "## Lean B: which module files run in a process\n\n"
        "**How a file is told to have Python of its own** (`has_own_code` in "
        "`tests/perf/proto/parent.py`, read from the file's syntax tree, nothing runs). Rule "
        "`strict`: a file has none when every top-level statement is an import (also under "
        "`if TYPE_CHECKING:`), a docstring, `pass`, or a class extending `Module` whose body is only "
        "`pass`, a docstring or `...`; a missing file has none (the product refuses a module with no "
        "Python file, so it cannot occur for a shipped module). Anything else (a method such as "
        "`validate_use`, a constant, a function) is Python of its own and the file runs in a "
        "process, as in B. Rule `validate`: as `strict`, and a literal constant and a "
        "`validate_use` method are no Python of its own either (the widget modules whose Python is "
        "only the check of their parameters); that check then runs in the shell when a use is "
        "added, as it does in A. A file that does not parse runs in a process, which reports the "
        "error as in B. **This run used the rule `" + rule + "`** (`--lean-rule`).\n\n"
        f"The default shell loads **{total}** module files: **{len(kids)} run in a process** and "
        f"**{len(stay)} stay in the shell**. The maintainer's expectation (Module Process Test, open "
        "question 3) was 13 TDL-only files staying and 9 in processes"
        + (
            "; the count of this run is the same.\n\n"
            if len(stay) == 13
            else f"; this run gives {len(stay)} staying and {len(kids)} in processes.\n\n"
        )
        + "The same module files by each rule (the shipped ones): "
        + "; ".join(f"`{r}`: {k} in processes, {s} in the shell" for r, (k, s) in counts.items())
        + ".\n\n"
    )
    rows = [[n, "process", own_lines(n)] for n in kids] + [[n, "shell", own_lines(n)] for n in stay]
    return text + md_table(["Module file", "Runs in", "Python lines (not blank)"], rows)


def forms_table(res: dict[str, Any]) -> str:
    cells = [
        label
        for label in ("A", "B1", "B2", "C1", "L1", "L2")
        if res["idle"].get(f"{label}/default")
    ]
    return variant_table(res, cells) if len(cells) > 1 else ""


def report(
    res: dict[str, Any], info: dict[str, str], args: argparse.Namespace, loaded: bool
) -> str:
    rows = verdicts(res)
    out: list[str] = []
    w = out.append
    smoke = bool(args.smoke)
    w("# Module process test: results\n")
    if smoke:
        w(
            "> **SMOKE RUN.** The durations were cut to prove the harness works (flags below). "
            "These numbers are not for the decision rule: 2 starts, 1 repetition, a 3 s idle window. "
            "Run the full measurement on an idle machine (see the last section).\n"
        )
    if loaded:
        w(
            "> **LOADED.** The 1-minute load average was above "
            f"{LOAD_LIMIT} at the start and `--allow-load` was given. The numbers are not for the "
            "decision rule.\n"
        )
    w(
        "Reported, not decided. Produced by `tests/perf/module_process_test.py` (M7a2 of the M7 brief; "
        "`60 Quality/Module Process Test.md`). **The maintainer decides**; the VERDICT TABLE only "
        "applies the starting thresholds of the spec to the numbers measured, and the thresholds are "
        "named constants at the top of the harness.\n"
    )
    w("## Machine and run\n")
    w(md_table(["", ""], [[k, v] for k, v in info.items()]))
    w(
        f"\nCommand flags: `{' '.join(f'--{k.replace(chr(95), chr(45))}={v}' for k, v in res['args'].items() if k not in ('out',))}`\n"
    )
    if res.get("elapsed_s"):
        w(f"Run time of this measurement: {res['elapsed_s'] / 60:.1f} minutes.\n")
    loads = [
        v
        for section in (
            res["start"].values(),
            *res["idle"].values(),
            *res["latency"].values(),
            *res["contain"].values(),
        )
        for v in (
            [x for x in section["load"]]
            if isinstance(section, dict) and isinstance(section.get("load"), list)
            else [section["load"]]
            if isinstance(section, dict) and "load" in section
            else [x["load"] for x in section]
            if isinstance(section, list)
            else []
        )
    ]
    if loads:
        w(
            f"1-minute load average at the start of each run: median {med(loads):.2f}, highest "
            f"{max(loads):.2f} (the harness's own earlier runs add to it; only the check at the very "
            "start is a refusal).\n"
        )
    if res["errors"]:
        w("### Runs that failed\n")
        for e in res["errors"]:
            w(f"- {e}")
        w("")
    w("## The postures\n")
    w(
        "- **A**, in process: the product as it is (the harness runs plain `python -m tess_shell run` for "
        "the start, idle and memory of A; the wrapper only where the probe needs it).\n"
        "- **B**, a process per module FILE (the maintainer's answer to open question 1): every file the "
        "default shell loads, 22 of them, runs its `Module` in a child; the shell holds a stub class "
        "built from the file's syntax tree, so no module code runs in the shell.\n"
        "- **C**: the shipped modules stay in the shell, each USER module file runs as in B.\n"
        "- **L**, lean B: a module file whose Python has code of its own (a method, a constant, a "
        "function: see the section on the lean B) runs in a child as in B; a file with none (a class "
        "that is only `pass`: the TDL-only widget and popup modules) stays in the shell and is imported "
        "there by the product's own code. `L1` and `L2` are L with the processes on B1 or B2.\n"
        "- **Services.** `B1`: each process opens its own connections (a D-Bus connection and service "
        "thread when it uses `ctx.dbus`, a PulseAudio connection for `ctx.audio`, a tray host name). `B2`: "
        "the shell keeps the connections and the process proxies calls and signals over the pipe. In "
        "both, popups, surfaces, windows, the application index and the icon registry stay in the shell "
        "(they are tre's or the shell's state, not connections): that is B2 by necessity. `C1` and `C2` "
        "are C with the user modules on B1 or B2.\n"
        "- **Pipe.** JSON lines over one `AF_UNIX` socketpair per process (reasons in "
        "`tests/perf/proto/wire.py`: the payloads are small and plain, a line is readable in a failure, "
        "and a closed peer is noticed at once as end of file). `ctx.send` queues one line; a writer thread "
        "joins what is queued into one `sendall`, so a burst is one syscall and an idle process wakes for "
        "nothing. The shell's reader thread calls the same `ValueStore.send`, so the per-key coalescing and "
        "the one `call_soon` flush are exactly A's.\n"
        "- **Watchdog (B, C and L).** The process records the callback it runs in shared memory (a memfd the "
        f"shell passes in: two stores per callback); a watchdog thread of the shell reads it every "
        f"{os.environ.get('TESS_PROTO_WATCH', '1.0')} s, logs a stall at {args.stall:g} s and kills the "
        f"process at {args.kill:g} s; the existing back-off then restarts the module (first try after 1 s). "
        "The 10 s kill of Crash Recovery would let a 10 s sleep end by itself, and only one module restarts, "
        "so the prototype kills earlier (a decision to confirm). A (this base has no M7b watchdog) has no "
        "recovery: the shell stays frozen until the callback returns.\n"
    )
    w("## Start time (process start to `READY=1`, milliseconds)\n")
    w(
        md_table(
            [
                "Cell",
                "Median (min to max)",
                "p95",
                "Processes after start",
                f"Budget < {BUDGET_READY_S:g} s",
            ],
            [
                [
                    f"{k.replace('/', ' / ')}",
                    span(v["ready_ms"], 0),
                    f"{M.percentile(v['ready_ms'], 0.95):.0f}",
                    span(v["processes"], 0),
                    "within"
                    if M.percentile(v["ready_ms"], 0.95) <= BUDGET_READY_S * 1000
                    else "OVER",
                ]
                for k, v in res["start"].items()
            ],
        )
    )
    w(
        f"Runs per cell: {args.start_runs}. `default` is the default shell; `plus3` adds three user modules.\n"
    )
    w(
        "## Idle: CPU, wake-ups, memory (default shell; after the settle time, window of the flags)\n"
    )
    cells = [k for k in res["idle"] if res["idle"][k]]
    w(
        md_table(
            [
                "Cell",
                "CPU % of one core",
                "Wake-ups / s (context switches)",
                "PSS MB",
                "RSS MB",
                "Processes",
                "Threads",
            ],
            [
                [
                    k.replace("/", " / "),
                    span(idle_values(res, k, "cpu_percent"), 3),
                    span(idle_values(res, k, "wakeups_per_s"), 2),
                    span(idle_values(res, k, "pss_mb"), 0),
                    span(idle_values(res, k, "rss_mb"), 0),
                    span(idle_values(res, k, "processes"), 0),
                    span(idle_values(res, k, "threads"), 0),
                ]
                for k in cells
            ],
        )
    )
    if res.get("floor"):
        w(
            "The floor of a process per module file: "
            + ", ".join(f"{k} {v:.1f} MB PSS" for k, v in res["floor"].items())
            + " (one idle process, measured by itself).\n"
        )
    w(
        f"Budgets (informational): CPU at most {BUDGET_IDLE_CPU_PERCENT} %, wake-ups at most "
        f"{BUDGET_WAKEUPS_PER_S:g} a second. Wake-ups are counted as context switches summed over every "
        "thread of every process of the tree (`/proc/PID/task/*/status`), which over-counts (the engine's "
        "software-renderer threads, `llvmpipe`, add a burst when the surfaces repaint in the first seconds "
        "after the start: the settle time and the median of the repetitions guard against it, a 1 s "
        "settle as in the smoke run does not). PSS and RSS "
        f"are summed over the tree after the idle window. Window: {args.idle:g} s, repetitions: {args.reps}.\n"
    )
    w("## Value to screen (`ctx.send` in a module to the node's property set)\n")
    w(
        "Both ends are stamped with `CLOCK_MONOTONIC`, which the shell and its module processes share: "
        "the probe module writes `<seq>:<monotonic ns>` as its value and logs every send; a wrapper "
        "around `ValueStore._turn` (the flush and the surfaces' property set, `on_change`) logs the time "
        "after the set and the value it showed. A value that another overtook inside one flush counts to "
        "that flush. The probe runs in the shell's process in A and in a module process in B, C and L. "
        "Single updates are isolated "
        f"({args.singles} values, {args.gap_ms} ms apart); the burst is {args.burst_rate:g} values a second "
        f"for {args.burst_seconds:g} s.\n"
    )
    lat_rows = []
    for label in res["latency"]:
        if not res["latency"][label]:
            continue
        lat_rows.append(
            [
                label,
                span(lat_pool(res, label, "single_ms", 0.5), 2),
                span(lat_pool(res, label, "single_ms", 0.95), 2),
                span(lat_pool(res, label, "single_ms", 0.99), 2),
                span(lat_pool(res, label, "burst_ms", 0.5), 2),
                span(lat_pool(res, label, "burst_ms", 0.95), 2),
                span(lat_pool(res, label, "burst_ms", 0.99), 2),
            ]
        )
    w(
        md_table(
            [
                "Cell",
                "Single p50 ms",
                "Single p95",
                "Single p99",
                "Burst p50",
                "Burst p95",
                "Burst p99",
            ],
            lat_rows,
        )
    )
    w("## Throughput (values a second sustained before p95 passes one frame)\n")
    tp_rows = []
    for label in res["latency"]:
        reps = res["latency"][label]
        if not reps:
            continue
        tp_rows.append([label, span([r["throughput"] for r in reps], 0)])
    w(md_table(["Cell", "Values / s, median (min to max)"], tp_rows))
    w(
        f"Frame = {LATENCY_P95_MS:g} ms; a rate counts only if at least 90 % of it was really sent. Ladder: {args.ladder}; {args.ladder_seconds:g} s each.\n"
    )
    ladder_rows = []
    for label in res["latency"]:
        reps = res["latency"][label]
        if not reps:
            continue
        for i, rate in enumerate(float(x) for x in args.ladder.split(",") if x):
            p95s = [r["steps"][i]["p95"] for r in reps if i < len(r["steps"])]
            sent = [r["steps"][i]["sent_per_s"] for r in reps if i < len(r["steps"])]
            ladder_rows.append([label, f"{rate:g}", span(sent, 0), span(p95s, 2)])
    w(md_table(["Cell", "Rate asked", "Sent / s", "p95 ms"], ladder_rows))
    w("## Hang, crash, reload\n")
    w(
        "The test node is a `Marquee_Text` that scrolls all the time in the Bar. `grim` captures the Bar "
        "from the compositor as fast as it can (20 to 50 times a second, depending on the load) and each "
        "capture is hashed; the share of the captures that differ from the one before is about 100 % for "
        "a node that paints all the time and 0 % for a frozen one, and the longest stop is the longest "
        "wait between two changes "
        "(`Paint` in `tests/perf/proto/measure.py`). It says whether the shell is painting, not the "
        "engine's own frame rate. The Victim module's tick callback sleeps "
        f"{args.hang:g} s on a trigger; a crash is SIGKILL of the module's own process; a reload is the "
        "module's file saved with a new `VERSION` (the shell's file watcher, 200 ms debounce).\n"
    )
    rows3 = []
    for label in res["contain"]:
        reps = res["contain"][label]
        if not reps:
            continue
        rows3.append(
            [
                label,
                span([100 * r["base"]["changed"] for r in reps], 0),
                span([100 * r["hang_paint"]["changed"] for r in reps], 0),
                span([r["hang_paint"]["max_gap_s"] for r in reps], 2),
                span([r["hang_detect_s"] for r in reps if r.get("hang_detect_s") is not None], 2)
                if any(r.get("hang_detect_s") is not None for r in reps)
                else "none (no watchdog in A)",
                span([r["hang_recover_s"] for r in reps if r.get("hang_recover_s") is not None], 2)
                if any(r.get("hang_recover_s") is not None for r in reps)
                else f"none: returned by itself after {span([r['hang_returned_s'] for r in reps], 2)}",
            ]
        )
    w("### Hang\n")
    w(
        md_table(
            [
                "Cell",
                "Picture changed before (% of captures)",
                "Picture changed during the hang (%)",
                "Longest stop (s)",
                "Time to detect (s, stall log)",
                "Time to recover (s, new instance running)",
            ],
            rows3,
        )
    )
    rows4 = []
    for label in res["contain"]:
        reps = res["contain"][label]
        if not reps:
            continue
        if label == "A":
            rows4.append(
                [label, "n/a", "n/a", "n/a", "a module is not a process in A: nothing to kill"]
            )
            continue
        rows4.append(
            [
                label,
                span([100 * r["crash_paint"]["changed"] for r in reps if r.get("crash_paint")], 0),
                span([r["crash_paint"]["max_gap_s"] for r in reps if r.get("crash_paint")], 2),
                span(
                    [r["crash_restart_s"] for r in reps if r.get("crash_restart_s") is not None], 2
                ),
                f"`{next((r['crash_log'] for r in reps if r.get('crash_log')), '')}`",
            ]
        )
    w("### Crash (SIGKILL of the module's process)\n")
    w(
        md_table(
            [
                "Cell",
                "Picture changed after the kill (%)",
                "Longest stop (s)",
                "Time to restart (s)",
                "The log line",
            ],
            rows4,
        )
    )
    rows5 = [
        [label, span([r["reload_s"] for r in res["contain"][label] if "reload_s" in r], 3)]
        for label in res["contain"]
        if res["contain"][label]
    ]
    w("### Reload (file saved to the new instance running, seconds)\n")
    w(md_table(["Cell", "Median (min to max)"], rows5))
    w("## Verdict table (the decision rule of the spec, computed; the maintainer decides)\n")
    w(
        "Thresholds (constants at the top of `tests/perf/module_process_test.py`): "
        f"start +{START_EXTRA_MS:g} ms; wake-ups +{WAKEUPS_EXTRA_PER_S:g} a second; value to screen p95 "
        f"{LATENCY_P95_MS:g} ms; memory +{MEMORY_EXTRA_MB:g} MB (PSS of the tree); containment: the test "
        f"node paints at least {CONTAIN_MIN_FPS_RATIO:g} of its normal rate and never stops for more than "
        f"{CONTAIN_MAX_GAP_S:g} s while a module hangs or is killed, and the module restarts.\n"
    )
    w(
        md_table(
            ["Test", "Cell", "Measured", "Passes when", "Verdict"],
            [
                [
                    r.test,
                    r.cell,
                    r.measured,
                    r.threshold,
                    "not measured" if r.ok is None else ("PASS" if r.ok else "FAIL"),
                ]
                for r in rows
            ],
        )
    )
    for line in decision(rows):
        w(f"**Rule applied to these numbers:** {line}\n")
    w(
        "Rows compare with A as measured in this run (start, wake-ups and memory on the default shell, "
        "C1 being C with no user module). B1/B2, C1/C2 and L1/L2 are the services variants. "
        "The rule is applied to the numbers as measured, not to how the prototype looks.\n"
    )
    if any(f"{label}/default" in res["idle"] for label in ("B1", "B2")):
        w("## Which B: B1 or B2\n")
        w(variant_table(res, ("B1", "B2")))
        w(better_variant(res, rows, "B1", "B2", "B"))
    if any(f"{label}/default" in res["idle"] for label in LEAN_CELLS):
        w("## Which lean B: L1 or L2\n")
        w(variant_table(res, LEAN_CELLS))
        w(better_variant(res, rows, "L1", "L2", "lean B"))
    side = forms_table(res)
    if side:
        w("## The forms side by side (default shell)\n")
        w(side)
    w(lean_section(res))
    w(
        "What each costs to build: "
        f"**B1** needs nothing new for the three services (the shell's own `Layer`, `AudioService` and "
        f"`TrayService` run in the process, about {b1_lines()} lines in `child.py`); **B2** needs "
        f"proxies for them ({b2_lines('proxies.py', '# -- the sound server (B2)')} lines in "
        f"`proxies.py`) and brokers in the shell ({b2_lines('brokers.py', '# -- the sound server and the tray host (B2)')} "
        "lines in `brokers.py`), and its `Bus.run(coro)` runs the module's coroutine in the process "
        "while `get` and `call` are answered by the shell. B1 opens one connection per process that "
        "uses a service (Audio and Audio_Outputs are two files, so two PulseAudio connections; each of "
        "the six D-Bus modules has its own `dbus` thread and socket); B2 keeps one of each in the shell "
        "and a process that uses none imports no D-Bus code.\n"
    )
    w("## What the prototype leaves out\n")
    w(LEFT_OUT)
    w("## The cost in code of the move\n")
    table, product = code_cost()
    w(table)
    w(
        product
        + " The module host's own code (`load`, `check_calls`, `dispatch`, `start`, `sync`, "
        "`_replace`, the back-off) ran unchanged on the stub.\n"
    )
    w(CTX_TABLE)
    w("## How the lead runs the full measurement\n")
    w(
        "On an idle machine: nothing the user started, no build, no CI job, no browser or agent doing "
        "work, 1-minute load average at or below 0.5 (the harness refuses otherwise). From the "
        "repository root (the worktree with this branch), with the project's own environment:\n\n"
        "```\n"
        "unset VIRTUAL_ENV; export UV_PROJECT_ENVIRONMENT=$HOME/Projects/pyDev/pyEnvs/tess-shell-m7a2\n"
        "env -u WAYLAND_DISPLAY -u DISPLAY uv run --no-sync python tests/perf/module_process_test.py\n"
        "```\n\n"
        "Expected duration about 80 minutes (start: 7 cells of 20 runs; idle: 7 cells of 3 times 75 s; "
        "latency: 5 cells of 3 times about 70 s; containment: 5 cells of 3 times about 45 s). It writes "
        "this file and `module-process-results.json`. Do not touch the machine while it runs; the "
        "headless sway and the fakes are private and are removed at the end (also on failure; a killed "
        "run leaves `tmp-proc-*` folders and processes whose environment names the private runtime "
        "directory).\n"
    )
    lean = parse(LEAN_RUN)
    plus_lean = parse(["--postures=A,B1,B2,C1,C2,L1,L2"])
    w("### The lean B only (A as the baseline)\n")
    w(
        "The first full measurement already has A, B and C; the lean B needs only A beside it. This "
        "runs A, L1 and L2 (the default shell only: no user modules) and writes a report of its own, "
        "so the report of the full run stays as it is. Three repetitions of start and idle, which "
        "carry the memory and the wake-ups, and fewer of latency and containment, which the rows "
        "pass by a wide margin or fail outright:\n\n"
        "```\n"
        "unset VIRTUAL_ENV; export UV_PROJECT_ENVIRONMENT=$HOME/Projects/pyDev/pyEnvs/tess-shell-lean\n"
        "env -u WAYLAND_DISPLAY -u DISPLAY uv run --no-sync python tests/perf/module_process_test.py "
        + " ".join(LEAN_RUN)
        + "\n```\n\n"
        "With the rule `validate` (the module files whose only Python is a `validate_use` check "
        "and literal constants stay in the shell too; see the section on the lean B for the counts "
        "of each rule), the same run and its own report file:\n\n"
        "```\n"
        "env -u WAYLAND_DISPLAY -u DISPLAY uv run --no-sync python tests/perf/module_process_test.py "
        + " ".join(LEAN_RUN_VALIDATE)
        + "\n```\n\n"
        f"Expected duration about {estimate_minutes(lean):.0f} minutes (an estimate from the step "
        "times measured on this machine: "
        + estimate_text(lean)
        + "). The same cells with three repetitions of everything take about "
        f"{estimate_minutes(parse([*LEAN_RUN, '--latency-reps=3', '--contain-reps=3'])):.0f} minutes. "
        "Adding L1 and L2 to the full run (`--postures=A,B1,B2,C1,C2,L1,L2`) adds about "
        f"{estimate_minutes(plus_lean) - estimate_minutes(parse([])):.0f} minutes to it.\n"
    )
    return "\n".join(out)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse(argv)
    loaded = refuse_when_loaded(args.allow_load)
    info = machine()
    began = time.monotonic()
    res = run(args)
    res["elapsed_s"] = time.monotonic() - began
    text = report(res, info, args, loaded)
    args.out.write_text(text)
    args.out.with_suffix(".json").write_text(json.dumps({"machine": info, **res}, indent=1))
    say(f"wrote {args.out}")
    return 1 if res["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
