"""One tre surface of a given size, and what it costs in video memory (Surface Types > Performance
Budget). Run as a child of the budget harness, inside its private sway; never against a real
compositor; not collected by pytest.

    python -m tests.perf.budget_surfaces bar|small|big [extra] [--animate]

Opens a ``LayerWindow`` of that kind (``bar``: 1280 x 32 at the top, ``small``: 200 x 100 floating,
``big``: the whole output), plus ``extra`` more windows of the same kind, waits for the first frame
of each, and prints one JSON line: tre's ``frame_stats()['memory']`` (the shared device's allocated
and reserved bytes: the GPU memory of every window of the process), the resident memory and the
proportional share of the process, and the frames the first window drew in the second after it
settled (an idle surface draws none).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import tess_re

KINDS: dict[str, dict[str, Any]] = {
    "bar": {"size": (0, 32), "anchor": ("top", "left", "right"), "exclusive_zone": 32},
    "small": {"size": (200, 100), "anchor": ()},
    "big": {"size": (0, 0), "anchor": ("top", "left", "right", "bottom"), "exclusive_zone": -1},
}
SETTLE_MS = 1500
IDLE_MS = 1000
ANIMATE_MS = 3000


def proc_kib(field: str) -> int:
    for line in Path("/proc/self/smaps_rollup").read_text().splitlines():
        if line.startswith(field + ":"):
            return int(line.split()[1])
    return 0


def main() -> None:
    kind = sys.argv[1]
    args = [a for a in sys.argv[2:] if not a.startswith("--")]
    animate = "--animate" in sys.argv
    extra = int(args[0]) if args else 0
    app = tess_re.App()
    output = app.outputs()[0]
    windows = []
    for n in range(1 + extra):
        window = tess_re.LayerWindow(
            f"tess-shell.budget.{kind}.{n}", layer="top", keyboard="none", **KINDS[kind]
        )
        window.root.add_child(window.create("text", text="budget"))
        app.add_window(window)
        windows.append(window)
    first = windows[0]
    result: dict[str, Any] = {
        "kind": kind,
        "windows": len(windows),
        "output": [output.width, output.height],
    }
    handle = app.thread_handle()

    def settled() -> None:
        result["frames_at_rest"] = first.frame_stats()["frames"]
        first.after(IDLE_MS, idle_done)

    def idle_done() -> None:
        stats = first.frame_stats()
        memory = stats.get("memory") or {}
        result["allocated_bytes"] = memory.get("allocated_bytes")
        result["reserved_bytes"] = memory.get("reserved_bytes")
        result["largest"] = memory.get("largest", [])[:3]
        result["idle_frames"] = stats["frames"] - result["frames_at_rest"]
        result["rss_kib"] = proc_kib("Rss")
        result["pss_kib"] = proc_kib("Pss")
        if animate:
            animation()
            return
        finish()

    def animation() -> None:
        node = first.create("text", text="moving", position="absolute", left=0, top=0)
        first.root.add_child(node)
        step = [0]

        def move() -> None:
            step[0] += 1
            node.set(left=step[0] % 200)

        timer = first.every(16, move)
        first.frame_stats(reset=True)

        def stopped() -> None:
            timer.cancel()
            recent = first.frame_stats()["recent"]
            result["recent"] = {
                key: recent.get(key) for key in ("fps", "total_ms", "cpu_ms", "stage_ms", "redraws")
            }
            finish()

        first.after(ANIMATE_MS, stopped)

    def finish() -> None:
        print(json.dumps(result), flush=True)
        handle.stop()

    first.after(SETTLE_MS, settled)
    app.run()


if __name__ == "__main__":
    main()
