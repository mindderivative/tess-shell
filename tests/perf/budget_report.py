"""The ledger of budgets, one reading of a budget, and the report (``tests/perf/read_budgets.py``).

A :class:`Budget` is a line of the vault's Performance Budgets note (or of the owner note it names);
this module does not decide any value: ``Reading.limit`` is the number the vault states, and a
budget that states no number is ``RECORDED`` (a number is shown, no verdict). A measure function
returns :class:`Reading` objects; :func:`render` writes them as the report.
"""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

PASS = "PASS"
FAIL = "FAIL"
RECORDED = "RECORDED"  # the vault states no limit: the number is shown, no verdict
NOT_MEASURED = "NOT MEASURED"  # no headless method, or not applicable: the reason is in the note


@dataclass(frozen=True, slots=True)
class Budget:
    id: str
    name: str
    text: str  # the budget as the vault states it
    source: str  # the note it comes from


BUDGETS: tuple[Budget, ...] = (
    Budget(
        "B01",
        "Idle CPU",
        "At most 0.5 % of one core, averaged over 60 s, shell running, nothing animating",
        "Performance Budgets > Proposed Values",
    ),
    Budget(
        "B02",
        "Idle wake-ups",
        "At most 5 per second (context switches), the shell idle; for a module that ticks the "
        "budget is read between ticks (D19)",
        "Performance Budgets > Proposed Values; M2 Build Log D19",
    ),
    Budget(
        "B03",
        "Time to first surface",
        "Under 1.0 s from the process start, warm cache",
        "Performance Budgets > Proposed Values",
    ),
    Budget(
        "B04",
        "Time to ready",
        "Under 2.0 s from the process start (READY=1; modules start at step 12)",
        "Performance Budgets > Proposed Values",
    ),
    Budget(
        "B05",
        "Stop time",
        "Bounded: 10 s in total, 3 s per module (decided)",
        "Shell Start and Stop > Stop Sequence",
    ),
    Budget(
        "B06",
        "Hot reload apply",
        "Under 100 ms after the 200 ms debounce for a shell of 10 surfaces; about 300 ms from "
        "the save to the change",
        "Performance Budgets > Proposed Values; Hot Reload",
    ),
    Budget(
        "B07",
        "Resident memory of the default shell",
        "To be set after the first build (no number); per-surface figures are video memory",
        "Performance Budgets > Proposed Values",
    ),
    Budget(
        "B08",
        "Looping icons at once",
        "At most 2 per output, none on hidden surfaces; applies only when `mli` ships",
        "Performance Budgets > Proposed Values; Risk Register R-24",
    ),
    Budget(
        "B09",
        "Module callback on the loop",
        "Under 4 ms",
        "Performance Budgets > Proposed Values; Process Model and Threading",
    ),
    Budget(
        "B10",
        "Watchdog",
        "A stall of 2 s logs; 10 s asks systemd for a restart (WATCHDOG=trigger)",
        "Performance Budgets > Proposed Values; Crash Recovery and Watchdog",
    ),
    Budget(
        "B11",
        "Motion durations",
        "Duration.Short 100 ms, Medium 200 ms, Long 400 ms",
        "Performance Budgets > Proposed Values",
    ),
    Budget(
        "B12",
        "Control interface",
        "`toggle` under 100 ms end to end (client about 20 ms); one loop callback under 1 ms; "
        "an idle shell receives no calls and wakes for none",
        "IPC and CLI > Performance Budget; ADR-0013",
    ),
    Budget(
        "B13",
        "D-Bus layer",
        "Idle: no timer, 0 wake-ups per second with no signal traffic; one connection per bus",
        "D-Bus Service Layer > Performance Budget",
    ),
    Budget(
        "B14",
        "Global shortcuts",
        "Registration: one doRegister and one setShortcut per action, under 50 ms for 10 actions; "
        "a key press to the state change under one frame; idle: no timer",
        "Global Shortcuts > Performance Budget",
    ),
    Budget(
        "B15",
        "Portals",
        "One ReadAll at start, under 20 ms of service-thread time; idle: no timer",
        "Portals > Performance Budget",
    ),
    Budget(
        "B16",
        "Popup",
        "A menu on screen within one or two frames of the click (to be measured); a closed "
        "Popup holds nothing; an open one draws no frames while nothing changes",
        "Popup > Performance Budget",
    ),
    Budget(
        "B17",
        "Per-surface video memory",
        "A 1280 x 32 bar about 18 MiB, a small window about 31 MiB, a 4K full-screen surface "
        "about 177 MiB (tre 0.5.8); the budget is set in 60 Quality",
        "Surface Types > Performance Budget; Goals G5",
    ),
    Budget(
        "B18",
        "Binding and tre call cost",
        "Bind of a 3,101-node tree under 15 ms (D12, D18); tre call costs are reference figures",
        "M1 Build Log D12 and D18; TRE-REQ-009",
    ),
    Budget(
        "B19",
        "Config load and validation",
        "Milliseconds at most for a shell of a few hundred entries (no number)",
        "Validation and Errors > Performance Budget",
    ),
    Budget(
        "B20",
        "Logging",
        "A record about 27 us on the calling thread with enqueue=True; below the level 0.13 us; "
        "one writer thread that sleeps until a record arrives",
        "Logging > Performance Budget",
    ),
    Budget(
        "B21",
        "CLI start",
        "A client that makes one call takes about 20 ms (the thin client imports no engine)",
        "ADR-0013 > Context",
    ),
    Budget(
        "B22",
        "Clock tick",
        "One timer for all uses; under 1 ms per tick on the loop thread; no timer faster than "
        "the shown unit",
        "Clock Module > Performance Budget",
    ),
    Budget(
        "B23",
        "Hot reload watcher idle",
        "Blocks in a read and wakes only on a file event",
        "Hot Reload > Performance Budget; Goals G4",
    ),
    Budget(
        "B24",
        "Callback record cost",
        "Keep the record unless it costs over 1 % of the 4 ms callback budget (40 us)",
        "Security Model > Questions After Testing 1",
    ),
    Budget(
        "B25",
        "Heartbeat and watchdog wake-ups",
        "About 2 wake-ups per second of their own against the idle budget of 5; slow the "
        "heartbeat to 2 s if the budget is at risk",
        "Crash Recovery and Watchdog > Performance budget, Open Question 3",
    ),
    Budget(
        "B26",
        "Frame time",
        "A frame at 60 Hz is about 16.7 ms and callbacks, layout and paint share it; an idle "
        "surface draws no frames (G4)",
        "Process Model and Threading > Performance Notes; Goals G4",
    ),
)

BY_ID = {b.id: b for b in BUDGETS}


@dataclass(slots=True)
class Reading:
    """What was measured for a budget. ``samples`` are one value per run (or per observation),
    ``stat`` how they are judged against ``limit`` (``median``, ``max``, ``min``, ``p95``, ``p99``)
    and ``limit`` is the vault's number in ``unit`` (``None``: the vault states none, so the row is
    ``RECORDED``). ``reason`` is set for a budget that was not measured. A limit that is a
    minimum (``at_least=True``) fails below it."""

    budget: str
    what: str
    samples: list[float]
    unit: str
    limit: float | None = None
    stat: str = "median"
    at_least: bool = False
    note: str = ""
    reason: str = ""
    extra: dict[str, float] = field(default_factory=dict)

    @classmethod
    def not_measured(cls, budget: str, what: str, reason: str) -> Reading:
        return cls(budget, what, [], "", reason=reason)

    @property
    def value(self) -> float | None:
        return stat_of(self.samples, self.stat)

    @property
    def status(self) -> str:
        if not self.samples:
            return NOT_MEASURED
        if self.limit is None:
            return RECORDED
        value = self.value
        assert value is not None
        ok = value >= self.limit if self.at_least else value <= self.limit
        return PASS if ok else FAIL

    def misses_by(self) -> str:
        """For a FAIL: by how much the budget is missed."""
        value = self.value
        if self.status != FAIL or value is None or self.limit is None:
            return ""
        gap = abs(value - self.limit)
        percent = f", {100 * gap / self.limit:.0f} %" if self.limit else ""
        return f"misses by {gap:.4g} {self.unit}{percent}"


def stat_of(samples: Sequence[float], stat: str) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples)
    if stat == "median":
        return statistics.median(ordered)
    if stat == "max":
        return ordered[-1]
    if stat == "min":
        return ordered[0]
    if stat in ("p95", "p99"):
        return percentile(ordered, int(stat[1:]))
    raise ValueError(f"unknown stat {stat!r}")


def percentile(ordered: Sequence[float], percent: float) -> float:
    """The nearest-rank percentile of an ascending sequence (no interpolation: with a few
    samples the figure is a value that was seen)."""
    if not ordered:
        raise ValueError("no samples")
    rank = max(1, -(-int(percent * len(ordered)) // 100))
    return ordered[min(rank, len(ordered)) - 1]


def number(value: float | None) -> str:
    if value is None:
        return "-"
    if value == 0:
        return "0"
    if abs(value) >= 100:
        return f"{value:,.0f}"
    if abs(value) >= 10:
        return f"{value:.1f}"
    return f"{value:.3g}"


def spread(reading: Reading) -> str:
    if not reading.samples:
        return "-"
    low, high = min(reading.samples), max(reading.samples)
    return f"{number(low)} to {number(high)} (n={len(reading.samples)})"


def render_row(reading: Reading) -> str:
    if reading.status == NOT_MEASURED:
        return f"| {reading.what} | - | - | - | NOT MEASURED | {reading.reason} |"
    limit = "-"
    if reading.limit is not None:
        bound = "at least" if reading.at_least else "at most"
        limit = f"{bound} {number(reading.limit)} {reading.unit}"
    verdict = reading.status
    note = reading.note
    if verdict == FAIL:
        note = f"{reading.misses_by()}. {note}".strip()
    return (
        f"| {reading.what} | {number(reading.value)} {reading.unit} ({reading.stat}) "
        f"| {spread(reading)} | {limit} | **{verdict}** | {note} |"
    )


def section(budget: Budget, readings: Iterable[Reading]) -> str:
    rows = [render_row(r) for r in readings]
    lines = [
        f"### {budget.id} {budget.name}",
        "",
        f"Budget: {budget.text}. Source: {budget.source}.",
        "",
    ]
    if not rows:
        lines += ["No reading was taken in this run.", ""]
        return "\n".join(lines)
    lines += [
        "| What | Value | Spread (min to max) | Limit | Verdict | Note |",
        "|---|---|---|---|---|---|",
        *rows,
        "",
    ]
    return "\n".join(lines)


def short(text: str, limit: int = 80) -> str:
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


def summary(readings: Sequence[Reading]) -> list[str]:
    """One line per budget: its worst verdict."""
    lines = ["| Budget | Verdict | Where it fails |", "|---|---|---|"]
    for budget in BUDGETS:
        mine = [r for r in readings if r.budget == budget.id]
        statuses = {r.status for r in mine}
        if not mine:
            verdict = "NO READING"
        elif FAIL in statuses:
            verdict = FAIL
        elif PASS in statuses:
            verdict = PASS if NOT_MEASURED not in statuses else "PASS (part not measured)"
        elif RECORDED in statuses:
            verdict = RECORDED
        else:
            verdict = NOT_MEASURED
        where = "; ".join(f"{short(r.what)}: {r.misses_by()}" for r in mine if r.status == FAIL)
        lines.append(f"| {budget.id} {budget.name} | {verdict} | {where} |")
    return lines


def render(
    readings: Sequence[Reading], header: Sequence[tuple[str, str]], intro: str, tail: str = ""
) -> str:
    """The whole report: ``header`` is the table of facts about the run."""
    parts = ["# Budget readings", "", intro, "", "| | |", "|---|---|"]
    parts += [f"| {k} | {v} |" for k, v in header]
    parts += ["", "## Verdicts", "", *summary(readings), "", "## Readings", ""]
    for budget in BUDGETS:
        parts.append(section(budget, [r for r in readings if r.budget == budget.id]))
    if tail:
        parts += [tail, ""]
    return "\n".join(parts)
