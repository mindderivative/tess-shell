"""T-029 measurements of the sound service against the PRIVATE stack, inside the bwrap sandbox:
the cost of each module callback (p50, p99), the latency from another client's change to the state
in Python, and the idle cost of the ``dbus`` service thread over ``--idle`` seconds.

``env -u WAYLAND_DISPLAY -u DISPLAY python -m tests.spikes.audio.measure_service [--idle 60]``
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
import threading
import time
from pathlib import Path

from tests.spikes.audio.guard import reexec_in_sandbox

if __name__ == "__main__":
    reexec_in_sandbox("tests.spikes.audio.measure_service")

from tess_shell.services.api import AudioState  # noqa: E402
from tess_shell.services.audio import AudioService  # noqa: E402
from tess_shell.services.bus import ServiceThread  # noqa: E402
from tess_shell.services.pulse_native import NORM, PulseClient  # noqa: E402
from tests.spikes.audio.runner import sample_pid  # noqa: E402
from tests.spikes.audio.stack import PrivateStack  # noqa: E402


async def thread_id() -> int:
    return threading.get_native_id()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--idle", type=float, default=60.0)
    args = parser.parse_args()
    with PrivateStack() as stack:
        print(stack.prove_isolation())
        thread = ServiceThread()
        thread.start()
        audio = AudioService(thread, Path(stack.socket), env={})
        helper = audio.for_module("Measure")
        seen: list[tuple[int, AudioState | None]] = []
        helper.on_changed(lambda s: seen.append((time.monotonic_ns(), s)))
        deadline = time.monotonic() + 10
        while not seen and time.monotonic() < deadline:
            time.sleep(0.01)

        async def latency() -> list[float]:
            driver = PulseClient(stack.socket)
            await driver.connect("t029-measure")
            _i, sinks, _s = await driver.snapshot()
            index = next(d.index for d in sinks if d.name == "spike_speaker")
            out: list[float] = []
            for i in range(50):
                await asyncio.sleep(0.03)
                want = 10 + i
                n = len(seen)
                t0 = time.monotonic_ns()
                await driver.set_sink_volume(index, [round(want * NORM / 100)] * 2)
                for _ in range(2000):
                    hit = [t for t, s in seen[n:] if s is not None and s.volume == want]
                    if hit:
                        out.append((hit[0] - t0) / 1e6)
                        break
                    await asyncio.sleep(0.0005)
            driver.close()
            return out

        values = asyncio.run(latency())
        count, p50, p99, worst = audio.callback_summary("Measure")
        print(
            f"latency 50 changes: median {statistics.median(values):.2f} ms, worst "
            f"{max(values):.2f} ms (n={len(values)})"
        )
        print(
            f"callbacks: n={count} p50 {p50 * 1e6:.1f} us p99 {p99 * 1e6:.1f} us "
            f"max {worst * 1e6:.1f} us"
        )
        tid = thread.submit(thread_id()).result(5)
        time.sleep(0.5)
        import os

        key = f"{os.getpid()}:{tid}"
        before = {k: v for k, v in sample_pid(os.getpid()).items() if k.startswith(key)}
        time.sleep(args.idle)
        after = {k: v for k, v in sample_pid(os.getpid()).items() if k.startswith(key)}
        for k, new in after.items():
            old = before.get(k, (0, 0, 0, 0))
            print(
                f"idle {args.idle:.0f} s, service thread: cpu {(new[0] - old[0]) / 1000:.0f} us, "
                f"timeslices {new[1] - old[1]}, voluntary {new[2] - old[2]}, "
                f"involuntary {new[3] - old[3]}"
            )
        helper.close()
        thread.stop()


if __name__ == "__main__":
    main()
