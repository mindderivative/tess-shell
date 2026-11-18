"""Read every performance budget of the vault's Performance Budgets note (M7c, D-045).

    env -u WAYLAND_DISPLAY -u DISPLAY uv run --no-sync python -m tests.perf.read_budgets [options]

The reading is only worth taking on an IDLE machine: nothing else running (no builds, no CI, no
other shell, no browser playing a video), the machine plugged in. The harness refuses to start when
the one-minute load average is above 0.5 (``--allow-load`` overrides it; the report then says it
was loaded and its numbers are a smoke, not a reading). ``--quick`` runs every measure for a few
seconds (a smoke test of the harness, not of the budgets). The report goes to
``tests/perf/budget-results.md`` (``--out`` changes that).

It starts a private headless sway and private buses with fakes (``budget_rig``), runs the shell as
a child there and reads ``/proc``, the shell's log and its ``NOTIFY_SOCKET``; the in-process
measures (``budget_inproc``) use their own private buses and compositor. The real session is never
touched. The method of every budget is in ``tests/perf/budgets.md``. Not collected by pytest.
"""

from __future__ import annotations

import argparse
import datetime
import os
import sys
import time
import traceback
from collections.abc import Callable
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from tests.perf import budget_process as bp  # noqa: E402
from tests.perf import budget_rig as br  # noqa: E402
from tests.perf.budget_report import FAIL, Reading, render  # noqa: E402

LOAD_LIMIT = 0.5
DEFAULT_OUT = HERE / "budget-results.md"
PROCESS_MEASURES: dict[str, Callable[[bp.Plan, br.Rig], list[Reading]]] = {
    "idle": bp.measure_idle,
    "start": bp.measure_start_stop,
    "reload": bp.measure_reload,
    "callbacks": bp.measure_callbacks,
    "control": bp.measure_control,
    "watchdog": bp.measure_watchdog,
    "surfaces": bp.measure_surfaces,
}
INPROC = "inproc"


def inproc_module() -> object | None:
    try:
        from tests.perf import budget_inproc
    except ImportError:
        return None
    return budget_inproc


def estimates(plan_quick: bp.Plan, plan_full: bp.Plan) -> str:
    module = inproc_module()
    quick_in = getattr(module, "ESTIMATE_QUICK_S", 0)
    full_in = getattr(module, "ESTIMATE_FULL_S", 0)
    quick = plan_quick.estimate + quick_in
    full = plan_full.estimate + full_in
    return (
        f"estimated run time: --quick about {quick / 60:.0f} min "
        f"({plan_quick.estimate / 60:.0f} min process-level, {quick_in / 60:.0f} min in-process); "
        f"full about {full / 60:.0f} min "
        f"({plan_full.estimate / 60:.0f} min process-level, {full_in / 60:.0f} min in-process)"
    )


def parse(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Read every budget of Performance Budgets on this machine.",
        epilog="Run it on an idle machine; see the module's docstring.",
    )
    parser.add_argument("--quick", action="store_true", help="a smoke run: short windows, few runs")
    parser.add_argument(
        "--allow-load",
        action="store_true",
        help=f"start although the 1-minute load average is above {LOAD_LIMIT} "
        "(the report says it was loaded)",
    )
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="the report's path")
    parser.add_argument(
        "--only",
        default="",
        metavar="NAMES",
        help="comma-separated measures to run: " + ", ".join([*PROCESS_MEASURES, INPROC]),
    )
    parser.add_argument("--estimate", action="store_true", help="print the run time and stop")
    return parser.parse_args(argv)


def run_one(
    name: str, fn: Callable[[], list[Reading]], readings: list[Reading], log: list[str]
) -> None:
    began = time.monotonic()
    load = os.getloadavg()[0]
    print(f"[{name}] ...", flush=True)
    try:
        got = fn()
    except Exception as exc:
        got = []
        log.append(f"| {name} | FAILED: {type(exc).__name__}: {exc} | - |")
        traceback.print_exc()
    took = time.monotonic() - began
    readings.extend(got)
    if not log or not log[-1].startswith(f"| {name} |"):
        log.append(f"| {name} | {len(got)} readings | {took:.0f} s (load {load:.2f} at start) |")
    print(f"[{name}] {len(got)} readings in {took:.0f} s", flush=True)


def main(argv: list[str] | None = None) -> int:
    args = parse(argv)
    quick, full = bp.Plan.make(True), bp.Plan.make(False)
    print(estimates(quick, full))
    if args.estimate:
        return 0
    load = br.load_average()
    if load[0] > LOAD_LIMIT and not args.allow_load:
        print(
            f"refusing to start: the 1-minute load average is {load[0]:.2f}, above {LOAD_LIMIT}. "
            "A budget read on a busy machine is not a reading: stop what is running (builds, CI, "
            "other shells, video) and wait for the load to fall, or pass --allow-load for a "
            "smoke run (the report then says it was loaded).",
            file=sys.stderr,
        )
        return 2
    loaded = load[0] > LOAD_LIMIT
    plan = quick if args.quick else full
    wanted = [n for n in args.only.split(",") if n] or [*PROCESS_MEASURES, INPROC]
    unknown = [n for n in wanted if n not in (*PROCESS_MEASURES, INPROC)]
    if unknown:
        print(f"unknown measure: {', '.join(unknown)}", file=sys.stderr)
        return 2
    started = datetime.datetime.now().astimezone()
    busiest = br.busiest_processes()
    readings: list[Reading] = []
    log: list[str] = ["| Measure | Result | Time |", "|---|---|---|"]
    if any(n in PROCESS_MEASURES for n in wanted):
        with br.rig() as rig:
            for name, fn in PROCESS_MEASURES.items():
                if name in wanted:
                    run_one(name, lambda fn=fn: fn(plan, rig), readings, log)  # type: ignore[misc]
    if INPROC in wanted:
        module = inproc_module()
        if module is None:
            log.append(f"| {INPROC} | tests/perf/budget_inproc.py is not there | - |")
        else:
            run_one(INPROC, lambda: module.measure(args.quick), readings, log)  # type: ignore[attr-defined]
    readings.extend(bp.not_measured())
    finished = datetime.datetime.now().astimezone()
    load_end = br.load_average()
    mode = "QUICK (a smoke of the harness)" if args.quick else "FULL"
    banner = ""
    if loaded or args.quick:
        why = []
        if loaded:
            why.append(f"the machine was LOADED (1-minute load average {load[0]:.2f} at the start)")
        if args.quick:
            why.append("the run was --quick: short windows and few repeats")
        banner = (
            f"> **SMOKE, NOT A READING.** {'; '.join(why).capitalize()}. Do not decide a "
            "budget on these numbers. The reading is the full run on an idle machine: "
            "`env -u WAYLAND_DISPLAY -u DISPLAY uv run --no-sync python -m "
            "tests.perf.read_budgets` with nothing else running.\n"
        )
    header = [
        ("Date", started.isoformat(timespec="seconds")),
        ("Mode", mode + (" and LOADED" if loaded else "")),
        ("Duration", f"{(finished - started).total_seconds() / 60:.1f} min"),
        (
            "Load average at the start",
            f"{load[0]:.2f} {load[1]:.2f} {load[2]:.2f} (1, 5, 15 min)"
            + (" (above the 0.5 limit: --allow-load)" if loaded else ""),
        ),
        ("Load average at the end", f"{load_end[0]:.2f} {load_end[1]:.2f} {load_end[2]:.2f}"),
        ("Busiest processes at the start", "; ".join(busiest) or "-"),
        *br.machine_facts(),
        ("Command", " ".join(["python -m tests.perf.read_budgets", *(argv or sys.argv[1:])])),
    ]
    intro = (
        "Produced by `tests/perf/read_budgets.py` (the method of each budget is in "
        "`tests/perf/budgets.md`). A verdict compares the reading with the number the vault "
        "states, and says by how much a budget is missed; it changes no budget: the maintainer "
        "decides. `RECORDED` rows are numbers the vault gives no limit for. Wake-ups are context "
        "switches of every thread of the shell (voluntary and involuntary), as the earlier "
        "idle measures counted them.\n\n" + banner
    )
    tail = "## What ran\n\n" + "\n".join(log)
    text = render(readings, header, intro, tail)
    args.out.write_text(text)
    print(f"wrote {args.out}")
    fails = [r for r in readings if r.status == FAIL]
    for r in fails:
        print(f"FAIL {r.budget} {r.what}: {r.misses_by()}")
    failed_measures = [row for row in log if "FAILED" in row]
    for row in failed_measures:
        print(row)
    return 1 if failed_measures else 0


if __name__ == "__main__":
    raise SystemExit(main())
