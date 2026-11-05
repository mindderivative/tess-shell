"""What a shadow costs: the surface buffer and the process memory (ADR-0010, Performance Budgets).

Not collected by pytest. Run from the repo root: ``uv run python tests/perf/measure_shadow.py``.
Starts a private headless sway and the shell with the example Bar at no shadow, 20 % and 100 %
``Elevation`` (the built-in 64 px ``Max``) on a 1280 px output, waits for the Bar to settle and
reads the shell's resident memory from ``/proc``. Writes ``tests/perf/shadow-results.md``.
Reported, not enforced. The sway renderer is pixman: GPU memory is not measured.
"""

from __future__ import annotations

import datetime
import platform
import re
import signal
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from tests.shell_samples import BODY, write_example  # noqa: E402
from tests.sway import PrivateSway  # noqa: E402

CASES = [("none", ""), ("20 %", ", Elevation: 20%"), ("100 %", ", Elevation: 100%")]


def rss_kib(pid: int) -> int:
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1])
    return 0


def run_case(sway: PrivateSway, extra: str) -> tuple[int, str]:
    config = Path(tempfile.mkdtemp(prefix="tsh-shadow-"))
    write_example(
        config, BODY.replace('Style { Fill: "#1f1f1f" }', f'Style {{ Fill: "#1f1f1f"{extra} }}')
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "tess_shell", "run", "--config-dir", str(config)],
        env=sway.env,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert process.stderr is not None
    lines: list[str] = []
    threading.Thread(target=lambda: lines.extend(process.stderr or []), daemon=True).start()
    try:
        deadline = time.monotonic() + 20
        while not any("configured" in x for x in lines) and time.monotonic() < deadline:
            time.sleep(0.05)
        time.sleep(3)  # let the first frames and the allocator settle
        size = next((re.search(r"size \((\d+), (\d+)\)", x) for x in lines if "size (" in x), None)
        return rss_kib(process.pid), size.group(0) if size else "?"
    finally:
        process.send_signal(signal.SIGTERM)
        process.wait(10)


def main() -> int:
    sway = PrivateSway().start()
    try:
        rows = []
        for label, extra in CASES:
            samples = [run_case(sway, extra) for _ in range(3)]
            rss = sorted(s[0] for s in samples)[1]
            rows.append((label, samples[0][1], rss))
    finally:
        sway.stop()
    base = rows[0][2]
    out = [
        "# Shadow cost (measure_shadow.py)",
        "",
        f"{datetime.date.today()}, {platform.node()}, headless sway (pixman), 1280 px output, "
        "median of 3 starts, resident memory after 3 s.",
        "",
        "| Elevation | Surface size | Resident memory | Over no shadow |",
        "|---|---|---|---|",
    ]
    for label, size, rss in rows:
        out.append(f"| {label} | {size} | {rss / 1024:.1f} MiB | {(rss - base) / 1024:+.1f} MiB |")
    (HERE / "shadow-results.md").write_text("\n".join(out) + "\n")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
