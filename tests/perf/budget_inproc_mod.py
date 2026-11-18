"""In-process budget measures of the modules and the control interface on the loop (B09, B12, B20,
B22, B24): callback durations of the shipped modules, the cost of the callback record, a Clock
tick, one ``toggle`` command, and the shell's own logging."""

from __future__ import annotations

import gc
import os
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from loguru import logger
from tests.perf.budget_report import Reading

import tess_shell.modules.host as host_module
from tess_shell.config.settings import LoggingSettings
from tess_shell.logging import configure_logging, shutdown_logging
from tess_shell.modules.running import CallbackRecord

BUDGET_MS = 4.0  # a module callback on the loop (B09)


SHIPPED = Path(__file__).resolve().parent.parent.parent / "src" / "tess_shell" / "shipped"


def clock_module() -> dict[str, Any]:
    """The shipped Clock as the extra module of ``tests/widgets_live.running`` (its list of
    standard modules has no Clock)."""
    folder = SHIPPED / "Clock"
    return {
        "extra": {"Clock": (folder / "Clock_Module.tdl").read_text()},
        "extra_py": {"Clock": (folder / "Clock_Module.py").read_text()},
    }


# -- B24: the cost of the callback record ----------------------------------------------------


def _noop() -> None:
    return None


def record_cost_ns(calls: int) -> tuple[float, float, float]:
    """Nanoseconds per call: the bare call, ``enter`` + ``leave``, and ``run`` of a trivial
    function, over ``calls`` calls each (the loop's own cost is in all three)."""
    record = CallbackRecord(lambda module, rule, message: None)
    started = time.perf_counter_ns()
    for _ in range(calls):
        _noop()
    bare = (time.perf_counter_ns() - started) / calls
    started = time.perf_counter_ns()
    for _ in range(calls):
        previous = record.enter("Module", "entry")
        record.leave(previous)
    enter_leave = (time.perf_counter_ns() - started) / calls
    started = time.perf_counter_ns()
    for _ in range(calls):
        record.run("Module", "entry", _noop)
    run = (time.perf_counter_ns() - started) / calls
    return bare, enter_leave, run


def record_growth(calls: int) -> tuple[int, int]:
    """Allocated blocks and gc-tracked objects gained over ``calls`` callbacks (after a warm-up)."""
    record = CallbackRecord(lambda module, rule, message: None)
    for _ in range(1000):
        record.run("Module", "entry", _noop)
    gc.collect()
    blocks, objects = sys.getallocatedblocks(), len(gc.get_objects())
    for _ in range(calls):
        previous = record.enter("Module", "entry")
        record.leave(previous)
        record.run("Module", "entry", _noop)
    gc.collect()
    return sys.getallocatedblocks() - blocks, len(gc.get_objects()) - objects


def measure_b24(quick: bool) -> list[Reading]:
    calls = 20_000 if quick else 200_000
    repeats = 3 if quick else 7
    runs = [record_cost_ns(calls) for _ in range(repeats)]
    pair = [r[1] - r[0] for r in runs]  # enter + leave beyond the bare loop
    run = [r[2] - r[0] for r in runs]
    budget_ns = BUDGET_MS * 1e6
    note = f"{calls:,} calls per repeat; the bare call loop is subtracted"
    return [
        Reading("B24", "enter + leave per callback beyond the bare call", pair, "ns", note=note),
        Reading("B24", "run() of a trivial callable per callback beyond the bare call", run,
                "ns", note=note),
        Reading("B24", "enter + leave as a share of the 4 ms callback budget",
                [100 * v / budget_ns for v in pair], "% of 4 ms", 1.0, "median",
                note="the vault's keep-it line: 1 % = 40 us"),
        Reading("B24", "run() as a share of the 4 ms callback budget",
                [100 * v / budget_ns for v in run], "% of 4 ms", 1.0, "median"),
    ]  # fmt: skip


# -- B09: callbacks of the shipped modules ---------------------------------------------------


@dataclass
class Timings:
    """Every callback the host's record saw: (module, entry point, milliseconds)."""

    seen: list[tuple[str, str, float]] = field(default_factory=list)

    def durations(self) -> list[float]:
        return [ms for _, _, ms in self.seen]

    def over(self, limit_ms: float = BUDGET_MS) -> list[tuple[str, str, float]]:
        return [t for t in self.seen if t[2] > limit_ms]

    def heaviest(self, count: int = 5) -> list[str]:
        worst: dict[str, float] = {}
        for module, entry, ms in self.seen:
            key = f"{module}.{entry}"
            worst[key] = max(worst.get(key, 0.0), ms)
        top = sorted(worst.items(), key=lambda kv: -kv[1])[:count]
        return [f"{k} {v:.2f} ms" for k, v in top]


@contextmanager
def timed_callbacks() -> Iterator[Timings]:
    """The module host's ``CallbackRecord`` replaced by one that also times each callback: a
    callback is whatever the host runs through ``enter``/``leave`` (nested ones too)."""
    timings = Timings()

    class Timed(CallbackRecord):
        __slots__ = ("_stack",)

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._stack: list[tuple[str, str, int]] = []

        def enter(self, module: str, entry: str) -> Any:
            self._stack.append((module, entry, time.perf_counter_ns()))
            return super().enter(module, entry)

        def leave(self, previous: Any) -> None:
            super().leave(previous)
            module, entry, started = self._stack.pop()
            timings.seen.append((module, entry, (time.perf_counter_ns() - started) / 1e6))

    original = host_module.CallbackRecord
    host_module.CallbackRecord = Timed  # type: ignore[misc]
    try:
        yield timings
    finally:
        host_module.CallbackRecord = original  # type: ignore[misc]


def callback_timings(events: int) -> tuple[Timings, Timings]:
    """Run the shipped Battery, Workspaces and Clock in a headless Bar on private buses with
    ``events`` rounds of events (a battery change, a desktop switch, a click, a Clock tick each).
    Returns the callbacks of the start-up and the callbacks of the rounds."""
    from tests.modules_rig import desk, shell

    with timed_callbacks() as timings, desk() as d:
        battery_fake, battery = d.battery(percentage=82.0)
        battery_fake.up()
        kwin_fake, kwin, ids = d.kwin(("A", "B", "C"))
        kwin_fake.up()
        with shell(d, "Battery { } Workspaces { } Clock { }", **clock_module()) as w:
            clock = w.host.loaded["Clock"].instance
            workspaces = w.host.loaded["Workspaces"].instance
            assert d.settle(w, lambda: workspaces.sent.get("current") == ids[0]), w.log()
            use = next(k for k in w.uses if k.startswith("Battery"))
            assert d.settle(w, lambda: "82 %" in str(w.store.values.get(use, {}).get("tooltip")))
            startup = Timings(list(timings.seen))
            timings.seen.clear()
            buttons = [
                n
                for k, n in w.view.nodes.items()
                if n.get("role") == "button" and "Desktop" in str(n.get("label"))
            ]
            for k in range(events):
                percent = 80 - k % 60
                battery.set("Percentage", float(percent))
                assert d.settle(w, lambda p=percent: f"{p} %" in str(w.store.values[use]))
                kwin.set("current", ids[(k + 1) % 3])
                assert d.settle(w, lambda i=(k + 1) % 3: workspaces.sent["current"] == ids[i])
                for node in buttons:  # a click on each desktop button: Workspaces.switch
                    w.window.simulate("click", node=node)
                    d.settle(w, lambda: False, timeout=0.01)
                for sub in list(w.host.ticks._subs):
                    sub.fn()  # the time source's callback, as the loop runs it
                w.host.callbacks.run(
                    "Clock",
                    "show",
                    clock.show,
                    next(iter(clock.ctx.uses.values())),
                    datetime.now().astimezone() + timedelta(minutes=k),
                )
                w.flush()
                w.advance(16)
            return startup, Timings(list(timings.seen))


def measure_b09(quick: bool) -> list[Reading]:
    startup, steady = callback_timings(15 if quick else 100)
    ms = steady.durations()
    over = len(steady.over()) / max(len(ms), 1) * 100
    note = f"{len(ms)} callbacks of Battery, Workspaces and Clock; heaviest: " + ", ".join(
        steady.heaviest(3)
    )
    return [
        Reading("B09", "module callbacks on the loop in steady state (p99)", ms, "ms",
                BUDGET_MS, "p99", note=note),
        Reading("B09", "module callbacks on the loop in steady state (max)", ms, "ms",
                BUDGET_MS, "max", note="the budget is a p99: the max is for the record"),
        Reading("B09", "share of steady-state callbacks over 4 ms", [over], "%",
                note="regression test: under 2 %"),
        Reading("B09", f"start-up callbacks ({len(startup.seen)}: import, __init__, start)",
                startup.durations(), "ms", note="heaviest: " + ", ".join(startup.heaviest(3))),
    ]  # fmt: skip


# -- B22: a Clock tick -----------------------------------------------------------------------


def clock_tick_costs(ticks: int) -> list[float]:
    """Milliseconds on the loop of one tick of the shipped Clock: ``show`` for a new minute
    (the module's work), then the value store's flush and a frame (what the loop does after)."""
    from tests.modules_rig import desk, shell

    out: list[float] = []
    with desk() as d, shell(d, "Clock { }", **clock_module()) as w:
        clock = w.host.loaded["Clock"].instance
        use = next(iter(clock.ctx.uses.values()))
        base = datetime(2026, 11, 6, 14, 0, 0).astimezone()
        w.flush()
        for n in range(ticks):
            now = base + timedelta(minutes=n + 1)
            started = time.perf_counter_ns()
            w.host.callbacks.run("Clock", "tick", clock.show, use, now)
            w.flush()
            w.advance(16)
            out.append((time.perf_counter_ns() - started) / 1e6)
    return out


def measure_b22(quick: bool) -> list[Reading]:
    ticks = 40 if quick else 200
    return [
        Reading("B22", f"one Clock tick on the loop: show + flush + a frame, {ticks} ticks",
                clock_tick_costs(ticks), "ms", 1.0, "p99",
                note="the shipped Clock in a headless Bar; each tick shows a new minute"),
    ]  # fmt: skip


# -- B12: a toggle command on the loop -------------------------------------------------------


def toggle_costs(runs: int) -> list[float]:
    """Milliseconds of ``ShellCommands.surface('Toggle', 'Dock')`` on the loop (the callback the
    control interface hands over), alternately hiding and showing a Panel, on the real surface
    manager with headless tre windows."""
    from typing import cast

    from tests.mode_rig import rigs

    from tess_shell.commands import ShellCommands

    out: list[float] = []
    gen = rigs()
    make = next(gen)
    try:
        r = make()
        commands = ShellCommands(r.manager, cast(Any, None), cast(Any, None), lambda: None,
                                 lambda: [])  # fmt: skip
        for _ in range(runs):
            started = time.perf_counter_ns()
            ok, message = commands.surface("Toggle", "Dock")
            out.append((time.perf_counter_ns() - started) / 1e6)
            assert ok, message
            r.settle(50)
    finally:
        for _ in gen:
            pass
    return out


def measure_b12(quick: bool) -> list[Reading]:
    runs = 40 if quick else 200
    return [
        Reading("B12", f"one toggle command's callback on the loop, {runs} runs",
                toggle_costs(runs), "ms", 1.0, "p99",
                note="ShellCommands.surface('Toggle', 'Dock') on the real manager, headless; "
                "the CLI end to end is the lead's"),
    ]  # fmt: skip


# -- B20: logging ----------------------------------------------------------------------------


def task_ids() -> set[int]:
    return {int(t) for t in os.listdir("/proc/self/task")}


def voluntary_switches(tid: int) -> int:
    for line in Path(f"/proc/self/task/{tid}/status").read_text().splitlines():
        if line.startswith("voluntary_ctxt_switches"):
            return int(line.split()[1])
    raise AssertionError("no voluntary_ctxt_switches")


@dataclass(frozen=True)
class LogReading:
    record_us: list[float]
    below_us: list[float]
    new_threads: int
    idle_switches: int


def log_costs(records: int, idle_s: float) -> LogReading:
    """The shell's own logging (``configure_logging``: an ``enqueue=True`` file sink in a temp
    directory, no console): the cost of one record on the calling thread, of one below the sink's
    level, the threads the setup adds, and the voluntary context switches of those threads while
    idle."""
    before = task_ids()
    with tempfile.TemporaryDirectory() as tmp:
        configure_logging(
            LoggingSettings(level="INFO", directory=Path(tmp), console=False), quiet=True
        )
        try:
            added = task_ids() - before
            record_us: list[float] = []
            below_us: list[float] = []
            for _ in range(records):
                started = time.perf_counter_ns()
                logger.info("a record of the shell")
                record_us.append((time.perf_counter_ns() - started) / 1000)
                started = time.perf_counter_ns()
                logger.debug("a record below the level")
                below_us.append((time.perf_counter_ns() - started) / 1000)
            logger.complete()  # the writer has drained its queue
            time.sleep(0.3)
            start = {tid: voluntary_switches(tid) for tid in added}
            time.sleep(idle_s)
            idle = sum(voluntary_switches(tid) - start[tid] for tid in added)
            return LogReading(record_us, below_us, len(added), idle)
        finally:
            shutdown_logging()


def measure_b20(quick: bool) -> list[Reading]:
    records, idle = (500, 2.0) if quick else (5000, 5.0)
    got = log_costs(records, idle)
    return [
        Reading("B20", "one record on the calling thread (enqueue=True file sink)",
                got.record_us, "us", note="the vault's reference is about 27 us"),
        Reading("B20", "one record below the sink's level", got.below_us, "us",
                note="the vault's reference is 0.13 us"),
        Reading("B20", "threads the logging setup adds", [float(got.new_threads)], "threads",
                note="the vault says one writer thread; the shell also starts the Timer thread "
                "of the midnight file swap (threading.Timer in logging.py): Decision to confirm"),
        Reading("B20", f"voluntary context switches of the logging threads over {idle:.0f} s idle",
                [float(got.idle_switches)], "switches", 0.0, "max"),
    ]  # fmt: skip


# -- the clock's subscriptions (B22, "no timer faster than the shown unit") ------------------


def clock_units(fmt: str) -> list[str]:
    """The tick units a started Clock with format ``fmt`` subscribes to."""
    from loguru import logger
    from tests import test_clock

    # test_clock.clock() adds a log sink and records its id in a list that only test_clock's own
    # fixture empties: take the sink away again, or a later test_clock test removes a stale id
    kept = len(test_clock._SINKS)
    try:
        instance, _use, _sent, _lines = test_clock.clock({"format": fmt})
        instance.start()
        return sorted(s.unit for s in instance.ctx._ticks._subs)  # type: ignore[attr-defined]
    finally:
        while len(test_clock._SINKS) > kept:
            logger.remove(test_clock._SINKS.pop())
