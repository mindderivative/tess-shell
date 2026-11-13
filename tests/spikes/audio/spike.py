"""The audio spike harness (T-018): ``python -m tests.spikes.audio.spike`` (see README.md).

Starts a PRIVATE PipeWire stack (stack.py), proves it is private, then for each route (A to D)
runs the route in a child process (runner.py) and measures: events (volume, mute, default sink,
source mute, changed from the outside by ``pactl`` and ``wpctl``), the setters, the latency of 50
changes of each kind, the idle cost over ``--idle`` seconds, and the restart of the private
``pipewire-pulse``. The results go to a JSON file. Every client is guarded (guard.py); the harness
never reads the environment it was started with except to refuse a real display.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any

from tests.spikes.audio.guard import isolate_process, reexec_in_sandbox  # noqa: E402

if __name__ == "__main__":
    reexec_in_sandbox("tests.spikes.audio.spike")  # re-executes under bwrap; checks inside it
if os.environ.get("WAYLAND_DISPLAY") or os.environ.get("DISPLAY"):
    raise SystemExit("run with: env -u WAYLAND_DISPLAY -u DISPLAY python -m ...audio.spike")

from tests.spikes.audio.pulse_native import PulseClient  # noqa: E402
from tests.spikes.audio.runner import sample_pid  # noqa: E402
from tests.spikes.audio.stack import PrivateStack  # noqa: E402

PYTHON = sys.executable
SPEAKER, PHONES, MIC = "spike_speaker", "spike_phones", "spike_mic"


def reset_levels(stack: PrivateStack) -> None:
    """Defaults and levels back to a known start (the devices themselves are made by pipewire's
    own private config, see stack.py, so they outlive a restart of pipewire-pulse)."""
    stack.pactl("set-default-sink", SPEAKER)
    stack.pactl("set-default-source", MIC)
    for name in (SPEAKER, PHONES):
        stack.pactl("set-sink-volume", name, "100%")
        stack.pactl("set-sink-mute", name, "0")
    stack.pactl("set-source-mute", MIC, "0")


class Child:
    """A route's child process and what it has reported."""

    def __init__(self, stack: PrivateStack, route: str) -> None:
        self.stack, self.route = stack, route
        self.states: list[tuple[int, dict[str, Any]]] = []
        self.replies: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self.changed = asyncio.Event()
        self.proc: asyncio.subprocess.Process | None = None
        self._reader: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self.proc = await asyncio.create_subprocess_exec(
            PYTHON,
            "-m",
            "tests.spikes.audio.runner",
            self.route,
            env={**self.stack.env, "PYTHONPATH": str(Path.cwd())},  # private env + the repo
            cwd=str(Path.cwd()),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self._reader = asyncio.create_task(self._read())
        await self.replies.get()  # {"started": ...}

    async def _read(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        async for line in self.proc.stdout:
            msg = json.loads(line)
            if "state" in msg:
                self.states.append((msg["t"], msg["state"]))
                self.changed.set()
            else:
                await self.replies.put(msg)

    async def send(self, **cmd: Any) -> dict[str, Any]:
        assert self.proc is not None and self.proc.stdin is not None
        self.proc.stdin.write((json.dumps(cmd) + "\n").encode())
        await self.proc.stdin.drain()
        return await asyncio.wait_for(self.replies.get(), cmd.get("seconds", 0) + 30)

    async def wait_state(self, pred: Any, timeout: float = 3.0, since: int = 0) -> int | None:
        """The monotonic time of the first state after index ``since`` that satisfies ``pred``."""
        deadline = time.monotonic() + timeout
        seen = since
        while True:
            for i in range(seen, len(self.states)):
                if pred(self.states[i][1]):
                    return self.states[i][0]
            seen = len(self.states)
            left = deadline - time.monotonic()
            if left <= 0:
                return None
            self.changed.clear()
            if len(self.states) > seen:
                continue
            try:
                await asyncio.wait_for(self.changed.wait(), left)
            except TimeoutError:
                return None

    async def stop(self) -> None:
        assert self.proc is not None
        try:
            await self.send(cmd="quit")
        except TimeoutError, BrokenPipeError:
            pass
        try:
            await asyncio.wait_for(self.proc.wait(), 5)
        except TimeoutError:
            self.proc.kill()
        err = await self.proc.stderr.read() if self.proc.stderr else b""
        if err:
            print(f"[{self.route}] stderr: {err.decode()[-600:]}")


def sink_of(state: dict[str, Any]) -> str:
    return str((state["sink"] or {}).get("name", ""))


async def check_events(child: Child, stack: PrivateStack) -> dict[str, Any]:
    """Change things from the OUTSIDE (pactl and wpctl, as System Settings would) and see whether
    the route reports each, with no timer."""
    result: dict[str, Any] = {}

    async def seen(pred: Any) -> bool:
        return await child.wait_state(pred, since=n) is not None

    n = len(child.states)
    stack.pactl("set-sink-volume", SPEAKER, "31%")
    result["volume_pactl"] = await seen(lambda s: s["volume"] == 31)
    n = len(child.states)
    stack.tool(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", "0.47"])
    result["volume_wpctl"] = await seen(lambda s: s["volume"] != 31)
    result["volume_shown_for_wpctl_0.47"] = child.states[-1][1]["volume"]
    n = len(child.states)
    stack.pactl("set-sink-mute", SPEAKER, "1")
    result["mute"] = await seen(lambda s: s["muted"])
    n = len(child.states)
    stack.pactl("set-sink-mute", SPEAKER, "0")
    result["unmute"] = await seen(lambda s: not s["muted"])
    n = len(child.states)
    stack.pactl("set-default-sink", PHONES)
    result["default_sink"] = await seen(lambda s: sink_of(s) == PHONES)
    result["default_sink_form_factor"] = child.states[-1][1]["sink"]["form_factor"]
    n = len(child.states)
    stack.pactl("set-source-mute", MIC, "1")
    result["source_mute"] = await seen(lambda s: s["source_muted"])
    n = len(child.states)
    module = stack.add_null_sink("spike_extra", "hdmi")
    result["sink_added"] = await seen(lambda s: len(s["outputs"]) == 3)
    n = len(child.states)
    stack.pactl("unload-module", module)
    result["sink_removed"] = await seen(lambda s: len(s["outputs"]) == 2)
    return result


async def setters(child: Child, stack: PrivateStack) -> dict[str, Any]:
    """The route's own setters change the server (checked from the outside with pactl)."""
    out: dict[str, Any] = {}
    stack.pactl("set-default-sink", SPEAKER)
    await child.wait_state(lambda s: sink_of(s) == SPEAKER)
    await child.send(cmd="set_volume", v=42)
    out["set_volume"] = "42%" in stack.pactl("get-sink-volume", SPEAKER).stdout.replace(" ", "")
    await child.send(cmd="set_muted", v=True)
    out["set_muted"] = "yes" in stack.pactl("get-sink-mute", SPEAKER).stdout
    await child.send(cmd="set_muted", v=False)
    await child.send(cmd="set_default_output", v=PHONES)
    out["set_default_output"] = PHONES in stack.pactl("get-default-sink").stdout
    await child.send(cmd="set_default_output", v=SPEAKER)
    return out


async def latency(child: Child, driver: PulseClient, kind: str, count: int = 50) -> list[float]:
    """Milliseconds from the moment the driver sends a change to the moment the route's state in
    Python shows it. The driver is one fixed client (the native protocol), the same for every
    route."""
    values: list[float] = []
    for i in range(count):
        n = len(child.states)
        await asyncio.sleep(0.05)
        if kind == "volume":
            want = 10 + i
            t0 = time.monotonic_ns()
            await driver.set_sink_volume(await index_of(driver, SPEAKER), want, 2)
            t1 = await child.wait_state(lambda s, w=want: s["volume"] == w, since=n)
        elif kind == "mute":
            want_mute = i % 2 == 0
            t0 = time.monotonic_ns()
            await driver.set_sink_mute(await index_of(driver, SPEAKER), want_mute)
            t1 = await child.wait_state(lambda s, w=want_mute: s["muted"] == w, since=n)
        else:
            name = PHONES if i % 2 == 0 else SPEAKER
            t0 = time.monotonic_ns()
            await driver.set_default_sink(name)
            t1 = await child.wait_state(lambda s, w=name: sink_of(s) == w, since=n)
        if t1 is not None:
            values.append((t1 - t0) / 1e6)
    return values


async def index_of(driver: PulseClient, name: str) -> int:
    _info, sinks, _sources = await driver.snapshot()
    return next(d.index for d in sinks if d.name == name)


def server_sample(stack: PrivateStack) -> dict[str, dict[str, tuple[int, int, int, int]]]:
    return {n: sample_pid(stack.pid(n)) for n in ("pipewire", "wireplumber", "pipewire-pulse")}


def server_delta(
    before: dict[str, dict[str, tuple[int, int, int, int]]],
    after: dict[str, dict[str, tuple[int, int, int, int]]],
) -> dict[str, Any]:
    out = {}
    for name in before:
        b = sum(v[0] for v in before[name].values()), sum(v[1] for v in before[name].values())
        a = sum(v[0] for v in after[name].values()), sum(v[1] for v in after[name].values())
        out[name] = {"cpu_us": (a[0] - b[0]) / 1000, "timeslices": a[1] - b[1]}
    return out


async def restart_test(child: Child, stack: PrivateStack) -> dict[str, Any]:
    """Kill the PRIVATE pipewire-pulse, then start it again (the devices are pipewire's own and
    stay). Does the route notice, and do events and setters work again without a restart of the
    route?"""
    out: dict[str, Any] = {}
    n = len(child.states)
    t0 = time.monotonic_ns()
    stack.kill_pulse()
    lost = await child.wait_state(lambda s: s["sink"] is None, since=n, timeout=6)
    out["sees_loss"] = lost is not None
    out["loss_after_s"] = (lost - t0) / 1e9 if lost is not None else None
    await asyncio.sleep(1.0)
    n = len(child.states)
    t1 = time.monotonic_ns()
    stack.start_pulse()
    back = await child.wait_state(lambda s: s["sink"] is not None, since=n, timeout=45)
    out["state_back"] = back is not None or lost is None
    out["state_back_after_s"] = (back - t1) / 1e9 if back is not None else None
    await asyncio.sleep(1.0)
    n = len(child.states)
    stack.pactl("set-sink-volume", SPEAKER, "66%")
    out["event_after_restart"] = (
        await child.wait_state(lambda s: s["volume"] == 66, since=n) is not None
    )
    try:
        await child.send(cmd="set_volume", v=55)
        out["setter_after_restart"] = "55%" in stack.pactl(
            "get-sink-volume", SPEAKER
        ).stdout.replace(" ", "")
    except (TimeoutError, KeyError) as exc:
        out["setter_after_restart"] = f"failed: {exc!r}"
    return out


async def run_route(stack: PrivateStack, route: str, idle: float, restart: bool) -> dict[str, Any]:
    print(f"== route {route}", flush=True)
    reset_levels(stack)
    child = Child(stack, route)
    await child.start()
    result: dict[str, Any] = {"route": route}
    try:
        ok = await child.wait_state(lambda s: s["sink"] is not None, timeout=15)
        result["first_state"] = child.states[-1][1] if ok else None
        result["events"] = await check_events(child, stack)
        reset_levels(stack)
        await asyncio.sleep(1.0)
        result["setters"] = await setters(child, stack)
        driver = PulseClient(str(stack.socket))
        await driver.connect("spike-driver")
        try:
            lat: dict[str, Any] = {}
            for kind in ("volume", "mute", "default_sink"):
                vals = await latency(child, driver, kind)
                lat[kind] = {
                    "n": len(vals),
                    "median_ms": statistics.median(vals) if vals else None,
                    "worst_ms": max(vals) if vals else None,
                }
            result["latency"] = lat
        finally:
            driver.close()
        reset_levels(stack)
        await asyncio.sleep(2.0)
        before = server_sample(stack)
        result["idle"] = (await child.send(cmd="idle", seconds=idle))["idle"]
        result["idle_server"] = server_delta(before, server_sample(stack))
        if restart:
            result["restart"] = await restart_test(child, stack)
    finally:
        await child.stop()
    return result


async def baseline(stack: PrivateStack, idle: float) -> dict[str, Any]:
    print("== baseline (no route)", flush=True)
    reset_levels(stack)
    await asyncio.sleep(2.0)
    before = server_sample(stack)
    await asyncio.sleep(idle)
    return server_delta(before, server_sample(stack))


async def main(args: argparse.Namespace) -> None:
    results: dict[str, Any] = {}
    with PrivateStack() as stack:
        isolate_process(stack.env)  # from here on this process itself is private
        proof = stack.prove_isolation()
        print(proof, flush=True)
        results["isolation"] = proof
        results["stack_pids"] = {n: stack.pid(n) for n in stack.procs}
        results["baseline_server_idle"] = await baseline(stack, args.idle)
        for route in args.routes:
            results[route] = await run_route(stack, route, args.idle, not args.no_restart)
        Path(args.out).write_text(json.dumps(results, indent=2))
        print(f"wrote {args.out}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--routes", nargs="+", default=["a", "b", "c", "d"])
    parser.add_argument("--idle", type=float, default=60.0)
    parser.add_argument("--no-restart", action="store_true")
    parser.add_argument("--out", default="/tmp/frame-review/T018-results.json")
    asyncio.run(main(parser.parse_args()))
