"""Reload time: from saving a shell file to the Bar showing it (Hot Reload, Performance Budget).

Not collected by pytest. Run from the repo root: ``uv run python tests/perf/measure_reload.py``.
Starts a private headless sway and the shell with the example Bar and a Clock, saves a changed
``Height`` ten times and reads the time of each ``reloaded`` log line. Writes
``tests/perf/reload-results.md``. Reported, not enforced (target: about 300 ms, 200 of them the
debounce).
"""

from __future__ import annotations

import datetime
import platform
import re
import signal
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

import subprocess  # noqa: E402

from tests.shell_samples import BODY, write_example  # noqa: E402
from tests.sway import PrivateSway  # noqa: E402

RUNS = 10


def stamp(line: str) -> float:
    match = re.match(r"(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3})", line)
    assert match, line
    return datetime.datetime.fromisoformat(match.group(1)).timestamp()


def main() -> int:
    sway = PrivateSway().start()
    config = Path(tempfile.mkdtemp(prefix="tsh-reload-"))
    body = BODY.replace(
        'Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }', 'Clock { format: "%H:%M" }'
    )
    shell_file = write_example(config, body)
    (config / "settings.tdl").write_text(
        "---\nTDL: 0.1\nName: Settings\n---\nSettings { Logging { Level: INFO } }\n"
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
        while not any("running" in x for x in lines) and time.monotonic() < deadline:
            time.sleep(0.1)
        time.sleep(1.0)
        wall: list[float] = []
        apply_ms: list[float] = []
        for i in range(RUNS):
            before = sum("reloaded (" in x for x in lines)
            height = 40 if i % 2 == 0 else 32
            text = shell_file.read_text()
            saved = time.time()
            shell_file.write_text(re.sub(r"Height: \d+\n", f"Height: {height}\n", text, count=1))
            deadline = time.monotonic() + 5
            while sum("reloaded (" in x for x in lines) <= before and time.monotonic() < deadline:
                time.sleep(0.01)
            line = [x for x in lines if "reloaded (" in x][-1]
            wall.append((stamp(line) - saved) * 1000)
            apply_ms.append(float(re.search(r"in (\d+) ms", line).group(1)))  # type: ignore[union-attr]
            time.sleep(0.5)
    finally:
        process.send_signal(signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
        sway.stop()
    uname = platform.uname()
    wall_row = f"{statistics.median(wall):.0f} ms | {min(wall):.0f} ms | {max(wall):.0f} ms"
    apply_row = (
        f"{statistics.median(apply_ms):.0f} ms | {min(apply_ms):.0f} ms | {max(apply_ms):.0f} ms"
    )
    text = f"""# Reload time

Reported, not enforced. Produced by `tests/perf/measure_reload.py`.

| | |
|---|---|
| Date | {datetime.datetime.now().astimezone().isoformat(timespec="seconds")} |
| Machine | {uname.system} {uname.release} {uname.machine} |
| Python | {platform.python_version()} |
| Compositor | private headless sway, pixman renderer, the example Bar with a Clock |
| Change | `Height` of the Bar, {RUNS} saves, 32 and 40 alternating |

| What | Median | Best | Worst |
|---|---|---|---|
| Save to the Bar changed (log time of `reloaded`) | {wall_row} |
| From the end of the 200 ms debounce to the apply (validate, diff, set) | {apply_row} |

The target is a change on screen within about 300 ms of the save, 200 ms of which is the debounce.
The log time is when the shell finished applying; the compositor's own reflow follows it.
"""
    (HERE / "reload-results.md").write_text(text)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
