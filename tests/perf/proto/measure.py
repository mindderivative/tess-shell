"""The measurements of ``tests/perf/module_process_test.py``, one function each, on a running shell of
:mod:`tests.perf.proto.rig`. Every time is ``time.monotonic()`` (``CLOCK_MONOTONIC``), which the
shell and the module processes read too, so a time written by a module and a time read here are one
clock. Not collected by pytest.
"""

from __future__ import annotations

import bisect
import contextlib
import math
import os
import shutil
import signal
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import zlib
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tests.perf.proto import rig as R

HZ = os.sysconf("SC_CLK_TCK")
BAR_REGION = "0,0 1280x34"  # the Bar of the test shells: where the scrolling test node is


@dataclass(frozen=True, slots=True)
class Cell:
    """One posture of the process test: ``posture`` is ``A``, ``B`` or ``C``; ``services`` ``B1`` or
    ``B2`` (for A it means nothing); ``label`` is what the report calls it."""

    label: str
    posture: str
    services: str = "B1"

    @property
    def plain(self) -> bool:
        """Posture A without the probe is the product's own command, not the wrapper."""
        return self.posture == "A"


A = Cell("A", "A")
B1 = Cell("B1", "B", "B1")
B2 = Cell("B2", "B", "B2")
C1 = Cell("C1", "C", "B1")
C2 = Cell("C2", "C", "B2")
ALL = {c.label: c for c in (A, B1, B2, C1, C2)}


@dataclass(frozen=True, slots=True)
class Stat:
    median: float
    p95: float
    lo: float
    hi: float
    n: int

    def __format__(self, spec: str) -> str:
        return f"{self.median:{spec or '.1f'}}"


def percentile(values: Sequence[float], q: float) -> float:
    """Nearest rank: the smallest value with at least ``q`` of the values at or below it."""
    ordered = sorted(values)
    if not ordered:
        return math.nan
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[min(rank, len(ordered)) - 1]


def stat(values: Sequence[float]) -> Stat:
    if not values:
        return Stat(math.nan, math.nan, math.nan, math.nan, 0)
    return Stat(
        statistics.median(values), percentile(values, 0.95), min(values), max(values), len(values)
    )


# -- the process tree -----------------------------------------------------------------------------


@dataclass(slots=True)
class PidSample:
    ticks: int = 0  # utime + stime
    switches: int = 0  # voluntary + involuntary context switches, every thread
    threads: int = 0
    pss_kb: int = 0
    rss_kb: int = 0


def sample_pid(pid: int) -> PidSample | None:
    out = PidSample()
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        out.ticks = int(fields[11]) + int(fields[12])
        for task in Path(f"/proc/{pid}/task").iterdir():
            out.threads += 1
            try:
                for line in (task / "status").read_text().splitlines():
                    if "ctxt_switches" in line:
                        out.switches += int(line.split()[1])
            except OSError:
                continue
        for line in Path(f"/proc/{pid}/smaps_rollup").read_text().splitlines():
            if line.startswith("Pss:"):
                out.pss_kb = int(line.split()[1])
            elif line.startswith("Rss:"):
                out.rss_kb = int(line.split()[1])
    except OSError, IndexError, ValueError:
        return None
    return out


@dataclass(slots=True)
class TreeSample:
    when: float
    pids: dict[int, PidSample] = field(default_factory=dict)

    @property
    def pss_mb(self) -> float:
        return sum(p.pss_kb for p in self.pids.values()) / 1024

    @property
    def rss_mb(self) -> float:
        return sum(p.rss_kb for p in self.pids.values()) / 1024

    @property
    def threads(self) -> int:
        return sum(p.threads for p in self.pids.values())


def sample_tree(root: int) -> TreeSample:
    got = TreeSample(time.monotonic())
    for pid in R.tree_pids(root):
        one = sample_pid(pid)
        if one is not None:
            got.pids[pid] = one
    return got


def tree_rates(a: TreeSample, b: TreeSample) -> tuple[float, float]:
    """``(CPU percent of one core, context switches a second)`` between two samples, over the
    processes of both."""
    elapsed = b.when - a.when
    ticks = sum(b.pids[p].ticks - a.pids[p].ticks for p in a.pids if p in b.pids)
    switches = sum(b.pids[p].switches - a.pids[p].switches for p in a.pids if p in b.pids)
    return 100 * ticks / HZ / elapsed, switches / elapsed


# -- running shells ------------------------------------------------------------------------------


@contextlib.contextmanager
def scratch() -> Iterator[Path]:
    root = Path(tempfile.mkdtemp(prefix="tmp-proc-run-"))
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


@contextlib.contextmanager
def running(
    rig: R.Rig,
    cell: Cell,
    kind: str,
    *,
    probe: bool = False,
    probe_dir: Path | None = None,
    stall: float | None = None,
    kill: float | None = None,
    watch: float | None = None,
) -> Iterator[tuple[R.Shell, float, Path]]:
    """A shell of ``kind`` in ``cell`` that has said ``READY=1``: ``(shell, seconds to ready,
    scratch folder)``."""
    with scratch() as root:
        cfg = R.write_config(root, kind)
        out = root / "probe-out.log" if probe else None
        shell = R.Shell(
            rig,
            cfg,
            posture=cell.posture,
            services=cell.services,
            wrapper=not cell.plain,
            probe_out=out,
            probe_dir=probe_dir,
            stall=stall,
            kill=kill,
            watch=watch,
        )
        try:
            yield shell, shell.wait_ready(), root
        finally:
            shell.stop()


def load1() -> float:
    return os.getloadavg()[0]


# -- start, idle, memory ---------------------------------------------------------------------


def measure_start(rig: R.Rig, cell: Cell, kind: str, runs: int) -> dict[str, Any]:
    """Process start to ``READY=1``, ``runs`` times (the shell is stopped between runs)."""
    seconds: list[float] = []
    procs: list[int] = []
    loads: list[float] = []
    for _ in range(runs):
        loads.append(load1())
        with running(rig, cell, kind) as (shell, ready, _):
            seconds.append(ready)
            time.sleep(0.2)
            procs.append(len(R.tree_pids(shell.pid)))
    return {"ready_ms": [s * 1000 for s in seconds], "processes": procs, "load": loads}


def measure_idle(
    rig: R.Rig, cell: Cell, kind: str, seconds: float, settle: float
) -> dict[str, Any]:
    """Idle CPU, wake-ups and memory of the whole tree over ``seconds``, after ``settle`` seconds
    with nothing happening."""
    load = load1()
    with running(rig, cell, kind) as (shell, ready, _):
        time.sleep(settle)
        first = sample_tree(shell.pid)
        time.sleep(seconds)
        last = sample_tree(shell.pid)
        cpu, wakeups = tree_rates(first, last)
        return {
            "ready_ms": ready * 1000,
            "cpu_percent": cpu,
            "wakeups_per_s": wakeups,
            "pss_mb": last.pss_mb,
            "rss_mb": last.rss_mb,
            "processes": len(last.pids),
            "threads": last.threads,
            "load": load,
        }


def measure_floor() -> dict[str, float]:
    """What one idle Python process costs by itself (PSS in MB): the bare interpreter, and the
    interpreter with the imports every module process has (the context, the services' API, loguru).
    The floor of a process per module: 22 module files cannot cost less than 22 times the second."""
    out: dict[str, float] = {}
    code = {
        "interpreter": "import time; time.sleep(30)",
        "interpreter + module context": (
            "import time\n"
            "from tess_shell.modules.context import ModuleContext\n"
            "from tess_shell.module import Module\n"
            "time.sleep(30)"
        ),
    }
    for name, source in code.items():
        proc = subprocess.Popen(
            [sys.executable, "-c", source], cwd=R.REPO, stdout=subprocess.DEVNULL
        )
        try:
            time.sleep(1.5)
            got = sample_pid(proc.pid)
            out[name] = got.pss_kb / 1024 if got else math.nan
        finally:
            proc.kill()
            proc.wait()
    return out


# -- value to screen ----------------------------------------------------------------------------


def read_sent(path: Path) -> dict[int, int]:
    out: dict[int, int] = {}
    for row in path.read_text().splitlines():
        if row.strip():
            seq, ns = row.split()
            out[int(seq)] = int(ns)
    return out


def read_seen(path: Path) -> list[tuple[int, int]]:
    """``(ns after the property set, seq)`` for each flush that showed a new probe value."""
    seen: list[tuple[int, int]] = []
    if not path.exists():
        return seen
    for row in path.read_text().splitlines():
        parts = row.split()
        if len(parts) == 2 and ":" in parts[1]:
            seen.append((int(parts[0]), int(parts[1].split(":")[0])))
    return seen


def latencies_ms(sent: dict[int, int], seen: list[tuple[int, int]]) -> list[float]:
    """For each value sent: the milliseconds from ``ctx.send`` to the first property set that showed
    that value or a later one (a value another overtook inside one flush counts to that flush)."""
    seqs = [s for _, s in seen]
    out: list[float] = []
    for seq, t_send in sorted(sent.items()):
        i = bisect.bisect_left(seqs, seq)
        if i < len(seen):
            out.append((seen[i][0] - t_send) / 1e6)
    return out


class Probe:
    """Drives the Probe module through its FIFO and reads both ends."""

    def __init__(self, root: Path, folder: Path) -> None:
        self.out = root / "probe-out.log"
        self.folder = folder
        self.commands = 0

    def command(self, text: str, expect: float, timeout: float | None = None) -> dict[int, int]:
        """Send one command; return the send log once the module wrote it and the last value was
        seen on the surface's side."""
        self.commands += 1
        with open(self.folder / "probe.fifo", "w") as fifo:
            fifo.write(text + "\n")
        log = self.folder / f"probe-sent-{self.commands}.log"
        deadline = time.monotonic() + (timeout or expect + 20)
        while not log.exists():
            if time.monotonic() > deadline:
                raise TimeoutError(f"the probe did not finish {text!r}")
            time.sleep(0.05)
        sent = read_sent(log)
        last = max(sent) if sent else 0
        while time.monotonic() < deadline:
            seen = read_seen(self.out)
            if seen and seen[-1][1] >= last:
                break
            time.sleep(0.02)
        return sent


def measure_latency(
    rig: R.Rig,
    cell: Cell,
    *,
    singles: int,
    gap_ms: int,
    burst_rate: float,
    burst_seconds: float,
    ladder: Sequence[float],
    ladder_seconds: float,
    frame_ms: float,
) -> dict[str, Any]:
    """Value to screen: ``singles`` isolated values, a burst, and a ladder of rates."""
    load = load1()
    with scratch() as folder_root:
        folder = folder_root / "probe"
        folder.mkdir()
        os.mkfifo(folder / "probe.fifo")
        with running(rig, cell, "probe", probe=True, probe_dir=folder) as (shell, ready, root):
            time.sleep(1.0)
            probe = Probe(root, folder)
            res: dict[str, Any] = {"ready_ms": ready * 1000, "load": load}
            sent = probe.command(f"single {singles} {gap_ms}", singles * gap_ms / 1000)
            res["single_ms"] = latencies_ms(sent, read_seen(probe.out))
            sent = probe.command(f"rate {burst_rate} {burst_seconds}", burst_seconds)
            res["burst_ms"] = latencies_ms(sent, read_seen(probe.out))
            res["burst_sent"] = len(sent)
            steps: list[dict[str, float]] = []
            for rate in ladder:
                sent = probe.command(f"rate {rate} {ladder_seconds}", ladder_seconds)
                lat = latencies_ms(sent, read_seen(probe.out))
                steps.append(
                    {
                        "rate": rate,
                        "sent_per_s": len(sent) / ladder_seconds,
                        "p50": percentile(lat, 0.5),
                        "p95": percentile(lat, 0.95),
                        "p99": percentile(lat, 0.99),
                    }
                )
            res["steps"] = steps
            res["throughput"] = sustained(steps, frame_ms)
            return res


def sustained(steps: Sequence[dict[str, float]], frame_ms: float) -> float:
    """The highest rate of the ladder whose p95 stayed within ``frame_ms`` and that was really sent
    (at least 90 % of it), before the first rate that failed either."""
    best = 0.0
    for step in steps:
        if step["p95"] <= frame_ms and step["sent_per_s"] >= 0.9 * step["rate"]:
            best = step["rate"]
        else:
            break
    return best


# -- painting, hangs, crashes, reloads ------------------------------------------------------------


class Paint:
    """Watches a test node paint: ``grim`` captures a strip of the compositor's output over and over
    and each capture is hashed; the frames a second are the number of times the picture changed.
    This sees what the user sees, from outside the shell, with no help from it. A capture takes
    about as long as a frame, so the rate is capped at about 30 a second: it says "painting" or "not
    painting", not the engine's own frame rate."""

    def __init__(self, rig: R.Rig, region: str = BAR_REGION) -> None:
        self._env = rig.sway.env
        self._region = region
        self.samples: list[tuple[float, int]] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="paint", daemon=True)

    def start(self) -> Paint:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(10)

    def _run(self) -> None:
        while not self._stop.is_set():
            done = subprocess.run(
                ["grim", "-t", "ppm", "-g", self._region, "-"],
                env=self._env,
                capture_output=True,
                check=False,
            )
            if done.returncode == 0:
                self.samples.append((time.monotonic(), zlib.crc32(done.stdout)))
            else:
                time.sleep(0.05)

    def window(self, t0: float, t1: float) -> dict[str, float]:
        """Frames a second and the longest wait between two changes inside ``[t0, t1]``."""
        inside = [(t, h) for t, h in self.samples if t0 <= t <= t1]
        changes = [t0]
        for (_, a), (t, b) in zip(inside, inside[1:], strict=False):
            if a != b:
                changes.append(t)
        changes.append(t1)
        gaps = [b - a for a, b in zip(changes, changes[1:], strict=False)]
        # the share of the intervals between two captures in which the picture changed: about 1 for
        # a node that paints all the time whatever the capture rate (which varies with the load),
        # about 0 for a frozen one
        intervals = max(len(inside) - 1, 1)
        return {
            "fps": (len(changes) - 2) / (t1 - t0) if t1 > t0 else 0.0,
            "changed": min((len(changes) - 2) / intervals, 1.0),
            "max_gap_s": max(gaps) if gaps else math.inf,
            "captures": float(len(inside)),
        }


def read_log(path: Path) -> list[tuple[str, float, int, int]]:
    """``(what, seconds, pid, version)`` for each line the Victim wrote."""
    rows: list[tuple[str, float, int, int]] = []
    if path.exists():
        for line in path.read_text().splitlines():
            parts = line.split()
            if len(parts) == 4:
                rows.append((parts[0], int(parts[1]) / 1e9, int(parts[2]), int(parts[3])))
    return rows


def wait_for(predicate: Any, timeout: float, what: str, interval: float = 0.02) -> Any:
    deadline = time.monotonic() + timeout
    while True:
        value = predicate()
        if value:
            return value
        if time.monotonic() > deadline:
            raise TimeoutError(f"timed out after {timeout:g} s waiting for {what}")
        time.sleep(interval)


def measure_containment(
    rig: R.Rig,
    cell: Cell,
    *,
    hang_seconds: float,
    stall: float,
    kill: float,
    baseline: float,
    reload: bool = True,
) -> dict[str, Any]:
    """On one shell: a reload of the Victim's file (unless ``reload`` is False: the fast test skips
    it), a SIGKILL of its process, a hang of its tick callback of ``hang_seconds``; the paint of the
    test node around each."""
    load = load1()
    with scratch() as folder_root:
        folder = folder_root / "probe"
        folder.mkdir()
        log = folder / "Victim.log"
        with running(rig, cell, "contain", probe_dir=folder, stall=stall, kill=kill) as (
            shell,
            ready,
            root,
        ):
            paint = Paint(rig).start()
            res: dict[str, Any] = {"ready_ms": ready * 1000, "load": load}
            try:
                wait_for(lambda: read_log(log), 20, "the Victim's start")
                time.sleep(baseline)
                now = time.monotonic()
                res["base"] = paint.window(now - baseline, now)
                # -- reload: a file saved, the new instance running
                if reload:
                    py = shell.cfg / "Modules" / "Victim" / "Victim_Module.py"
                    version = 2
                    text = py.read_text().replace("VERSION = 1", f"VERSION = {version}")
                    t_save = time.monotonic()
                    py.write_text(text)
                    row = wait_for(
                        lambda: next(
                            (r for r in read_log(log) if r[0] == "start" and r[3] == version), None
                        ),
                        30,
                        "the reloaded instance",
                    )
                    res["reload_s"] = row[1] - t_save
                    time.sleep(1.5)
                # -- crash: SIGKILL the module's own process
                if cell.posture != "A":
                    starts = [r for r in read_log(log) if r[0] == "start"]
                    pid = starts[-1][2]
                    t_kill = time.monotonic()
                    os.kill(pid, signal.SIGKILL)
                    row = wait_for(
                        lambda: next(
                            (
                                r
                                for r in read_log(log)
                                if r[0] == "start" and r[2] != pid and r[1] > t_kill
                            ),
                            None,
                        ),
                        30,
                        "the restarted instance",
                    )
                    res["crash_restart_s"] = row[1] - t_kill
                    t_end = row[1] + 1.0  # watch the second after the restart too
                    time.sleep(max(0.0, t_end + 0.3 - time.monotonic()))
                    res["crash_paint"] = paint.window(t_kill, t_end)
                    line = next(
                        (
                            ln
                            for when, ln in shell.lines
                            if when >= t_kill and "module Victim" in ln and "ended" in ln
                        ),
                        "",
                    )
                    res["crash_log"] = line.strip()
                    time.sleep(2.0)
                else:
                    res["crash_restart_s"] = None
                    res["crash_log"] = "n/a: a module is not a process in A"
                # -- hang: the tick callback sleeps
                latest = [r for r in read_log(log) if r[0] == "start"][-1]
                (folder / "hang").write_text("")
                begin = wait_for(
                    lambda: next(
                        (
                            r
                            for r in read_log(log)
                            if r[0] == "hang-begin" and r[1] > latest[1] and r[2] == latest[2]
                        ),
                        None,
                    ),
                    10,
                    "the hang to begin",
                )
                t0 = begin[1]
                time.sleep(max(0.0, t0 + hang_seconds + 0.5 - time.monotonic()))
                res["hang_paint"] = paint.window(t0, t0 + hang_seconds)
                stalled = shell.find("has run for", t0 - 0.5)
                res["hang_detect_s"] = None if stalled is None else stalled - t0
                if cell.posture == "A":
                    end = wait_for(
                        lambda: next(
                            (r for r in read_log(log) if r[0] == "hang-end" and r[1] >= t0), None
                        ),
                        hang_seconds + 10,
                        "the hang to end",
                    )
                    res["hang_recover_s"] = None
                    res["hang_returned_s"] = end[1] - t0
                else:
                    again = wait_for(
                        lambda: next(
                            (
                                r
                                for r in read_log(log)
                                if r[0] == "start" and r[1] > t0 and r[2] != begin[2]
                            ),
                            None,
                        ),
                        hang_seconds + 20,
                        "the module to come back after the hang",
                    )
                    res["hang_recover_s"] = again[1] - t0
                    res["hang_returned_s"] = None
                    line = next(
                        (ln for when, ln in shell.lines if when >= t0 and "did not return" in ln),
                        "",
                    )
                    res["hang_log"] = line.strip()
                time.sleep(1.0)
            finally:
                paint.stop()
            return res
