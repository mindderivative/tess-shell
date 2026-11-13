"""The child process of the spike: one route, measured in isolation.

Started by ``spike.py`` with the PRIVATE environment passed explicitly (nothing inherited):
``python -m tests.spikes.audio.runner <a|b|c|d>``. It talks to the parent over stdin/stdout, one
JSON object per line. It emits ``{"t": monotonic_ns, "state": {...}}`` for every state the route
reports, and answers commands: ``idle`` (measure the route's own cost for N seconds), the three
setters (``set_volume``, ``set_muted``, ``set_default_output``) and ``quit``.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from tests.spikes.audio.guard import require_private_env, require_sandbox
from tests.spikes.audio.model import AudioState, Route

LIBS = "/tmp/audio-spike-libs"  # pulsectl, installed outside the repo and the project venv


def make_route(name: str) -> Route:
    socket = Path(os.environ["PULSE_SERVER"].removeprefix("unix:"))
    if name == "a":
        from tests.spikes.audio.route_a import RouteA

        return RouteA(socket)
    if name == "b":
        sys.path.insert(0, LIBS)
        from tests.spikes.audio.route_b import RouteB

        return RouteB(socket)
    if name == "c":
        from tests.spikes.audio.route_c import RouteC

        return RouteC(dict(os.environ))
    if name == "d":
        from tests.spikes.audio.route_d import RouteD

        return RouteD(dict(os.environ))
    raise SystemExit(f"unknown route {name}")


def sample_pid(pid: int) -> dict[str, tuple[int, int, int, int]]:
    """Per thread of ``pid``: (cpu ns, timeslices, voluntary switches, involuntary switches)."""
    out: dict[str, tuple[int, int, int, int]] = {}
    for task in Path(f"/proc/{pid}/task").iterdir():
        try:
            cpu, _wait, slices = (int(x) for x in (task / "schedstat").read_text().split())
            comm = (task / "comm").read_text().strip()
            vol = invol = 0
            for line in (task / "status").read_text().splitlines():
                if line.startswith("voluntary_ctxt_switches"):
                    vol = int(line.split()[1])
                elif line.startswith("nonvoluntary_ctxt_switches"):
                    invol = int(line.split()[1])
        except FileNotFoundError, ProcessLookupError:
            continue
        out[f"{pid}:{task.name}:{comm}"] = (cpu, slices, vol, invol)
    return out


def sample_all(route: Route) -> dict[str, tuple[int, int, int, int]]:
    merged = sample_pid(os.getpid())
    for pid in route.child_pids():
        merged.update(sample_pid(pid))
    return merged


def delta(
    before: dict[str, tuple[int, int, int, int]], after: dict[str, tuple[int, int, int, int]]
) -> dict[str, Any]:
    threads = {}
    for key, new in after.items():
        old = before.get(key, (0, 0, 0, 0))
        threads[key] = [new[i] - old[i] for i in range(4)]
    total = [sum(t[i] for t in threads.values()) for i in range(4)]
    return {
        "cpu_us": total[0] / 1000,
        "timeslices": total[1],
        "voluntary": total[2],
        "involuntary": total[3],
        "threads": {k: v for k, v in threads.items() if any(v)},
    }


async def main(name: str) -> None:
    require_sandbox()  # first: abort outside the bwrap sandbox
    require_private_env(os.environ)  # and unless the environment is the private one
    route = make_route(name)
    loop = asyncio.get_running_loop()

    def emit(obj: dict[str, Any]) -> None:
        sys.stdout.write(json.dumps(obj) + "\n")
        sys.stdout.flush()

    def on_state(state: AudioState) -> None:
        emit({"t": time.monotonic_ns(), "state": dataclasses.asdict(state)})

    await route.start(on_state)
    reader = asyncio.StreamReader()
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(reader), sys.stdin)
    emit({"started": True, "pid": os.getpid()})
    while line := await reader.readline():
        cmd = json.loads(line)
        what = cmd["cmd"]
        if what == "idle":
            before = sample_all(route)
            started = time.monotonic()
            await asyncio.sleep(cmd["seconds"])
            result = delta(before, sample_all(route))
            result["window_s"] = time.monotonic() - started
            result["child_pids"] = route.child_pids()
            emit({"idle": result})
        elif what == "set_volume":
            await route.set_volume(cmd["v"])
            emit({"done": what})
        elif what == "set_muted":
            await route.set_muted(cmd["v"])
            emit({"done": what})
        elif what == "set_default_output":
            await route.set_default_output(cmd["v"])
            emit({"done": what})
        elif what == "quit":
            break
    await route.stop()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
