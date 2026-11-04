"""Idle cost of ``tesserae-shell run`` (Performance Budgets: idle CPU and wake-ups).

Not collected by pytest. Run from the repo root:

    uv run python tests/perf/measure_idle.py [seconds]

Starts a private headless sway, starts the shell, waits for ``running``, samples CPU time and
context switches of the whole process (all threads) over the window, and writes
``tests/perf/idle-results.md``. The budgets are reported, not enforced.
"""

from __future__ import annotations

import datetime
import os
import platform
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from tests.sway import PrivateSway  # noqa: E402

BUDGET_CPU_PERCENT = 0.5
BUDGET_WAKEUPS = 5.0


def cpu_ticks(pid: int) -> int:
    fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
    return int(fields[11]) + int(fields[12])  # utime + stime (fields 14 and 15)


def switches(pid: int) -> int:
    total = 0
    for task in Path(f"/proc/{pid}/task").iterdir():
        for line in (task / "status").read_text().splitlines():
            if "ctxt_switches" in line:
                total += int(line.split()[1])
    return total


def threads(pid: int) -> int:
    return len(list(Path(f"/proc/{pid}/task").iterdir()))


def main() -> int:
    duration = int(sys.argv[1]) if len(sys.argv) > 1 else 60
    sway = PrivateSway().start()
    config = Path(tempfile.mkdtemp(prefix="tsh-cfg-"))
    process = subprocess.Popen(
        [sys.executable, "-m", "tess_shell", "run", "--config-dir", str(config)],
        env=sway.env,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stderr is not None
    ready = threading.Event()

    def pump() -> None:
        assert process.stderr is not None
        for line in process.stderr:
            if "running" in line:
                ready.set()

    threading.Thread(target=pump, daemon=True).start()
    try:
        if not ready.wait(30):
            print("the shell never reported running", file=sys.stderr)
            return 1
        time.sleep(3)  # let start-up settle
        hz = os.sysconf("SC_CLK_TCK")
        t0, c0, s0 = time.monotonic(), cpu_ticks(process.pid), switches(process.pid)
        time.sleep(duration)
        t1, c1, s1 = time.monotonic(), cpu_ticks(process.pid), switches(process.pid)
        n_threads = threads(process.pid)
    finally:
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        sway.stop()
    elapsed = t1 - t0
    cpu_seconds = (c1 - c0) / hz
    percent = 100 * cpu_seconds / elapsed
    wakeups = (s1 - s0) / elapsed
    ok = percent <= BUDGET_CPU_PERCENT and wakeups <= BUDGET_WAKEUPS
    uname = platform.uname()
    gil = "with the GIL" if getattr(sys, "_is_gil_enabled", lambda: True)() else "free-threaded"
    text = f"""# Idle measurement of `tesserae-shell run`

Reported, not enforced. Produced by `tests/perf/measure_idle.py`.

| | |
|---|---|
| Date | {datetime.datetime.now().astimezone().isoformat(timespec="seconds")} |
| Machine | {uname.system} {uname.release} {uname.machine} |
| Python | {platform.python_version()} ({gil}) |
| Compositor | private headless sway, pixman renderer, no windows |
| Window | {elapsed:.1f} s after 3 s of settling |
| Threads | {n_threads} |
| CPU time | {cpu_seconds:.2f} s |
| CPU | {percent:.3f} % of one core (budget at most {BUDGET_CPU_PERCENT} %) |
| Context switches | {s1 - s0} voluntary plus involuntary, all threads |
| Wake-ups | {wakeups:.2f} per second (budget at most {BUDGET_WAKEUPS:g}) |

Result against the budgets: **{"within" if ok else "OVER"}** (reported, not enforced).

Wake-ups are counted as context switches, which over-counts (an involuntary switch is not a
wake-up) and includes the Python signal-watcher and logging threads.
"""
    (HERE / "idle-results.md").write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
