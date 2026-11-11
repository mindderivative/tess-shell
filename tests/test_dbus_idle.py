"""With a connected layer, subscriptions and no signal traffic, the ``dbus`` thread does not wake
(D-Bus Service Layer > Performance Budget; M5 Brief, A7).

Measured three ways on the service thread: the iterations of its asyncio loop (``_run_once``), the
timeslices the kernel gave the thread (``/proc/<pid>/task/<tid>/schedstat``, third field) and its
voluntary context switches (``/proc/<pid>/task/<tid>/status``). A thread that waits in ``epoll``
and is never woken shows zero in all three. ``test_idle_wakeups_5_s`` runs with the suite; the 60
second run of the Brief is marked ``perf`` (``pytest -m perf tests/test_dbus_idle.py``).
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from tess_shell.services.bus import ServiceThread
from tess_shell.services.layer import Layer
from tests.fake_dbus import HAVE_DAEMON, fake_bus, wait_for
from tests.test_dbus_layer import Hooks, Pump, _HookPort

NAME = "org.test.Battery"
PATH = "/org/test/Battery"
IFACE = "org.test.Battery"


@dataclass(frozen=True)
class ThreadCounters:
    loop_iterations: int
    timeslices: int
    voluntary_switches: int
    cpu_ns: int


def read_counters(tid: int, iterations: list[int]) -> ThreadCounters:
    task = Path(f"/proc/{os.getpid()}/task/{tid}")
    cpu_ns, _delay, slices = (int(x) for x in (task / "schedstat").read_text().split())
    voluntary = 0
    for line in (task / "status").read_text().splitlines():
        if line.startswith("voluntary_ctxt_switches"):
            voluntary = int(line.split()[1])
    return ThreadCounters(iterations[0], slices, voluntary, cpu_ns)


def measure_idle(
    seconds: float,
) -> tuple[ThreadCounters, ThreadCounters, float, ThreadCounters]:
    """Connect the layer, subscribe two modules to properties and a signal, let it settle, then
    count what the service thread does for ``seconds`` seconds. Returns the counters before and
    after, the length of the window and the counters after one deliberate wake-up (a control)."""
    with fake_bus() as bus:
        fake = bus.service(NAME)
        fake.add(
            PATH,
            IFACE,
            properties={"Percentage": ("d", 50.0), "State": ("u", 1)},
            signals={"Ping": "s"},
        )
        fake.up()
        service = ServiceThread(bus.address)
        service.start()
        layer = Layer(service, Pump().call_soon)
        try:
            for module in ("A", "B"):
                dbus = layer.for_module(module, lambda k, v: None, _HookPort(Hooks()))
                proxy = dbus.session().proxy(NAME, PATH, IFACE)
                proxy.on_property_changed(lambda values: None)
                proxy.on_signal("Ping", lambda *a: None)
            assert wait_for(
                lambda: (
                    len(layer._caches) == 1 and layer._caches[("session", NAME, PATH, IFACE)].loaded
                )
            )
            assert wait_for(lambda: len(service.session.rules) == 3)  # one rule each, shared
            iterations = [0]
            loop: Any = service._loop
            original = loop._run_once

            def counting() -> None:
                iterations[0] += 1
                original()

            loop._run_once = counting
            tid = service.submit(_native_id()).result(5)
            time.sleep(0.5)  # whatever the last subscription left behind has run by now
            before = read_counters(tid, iterations)
            started = time.monotonic()
            time.sleep(seconds)
            after = read_counters(tid, iterations)
            window = time.monotonic() - started
            service.post(lambda: None)  # a control: one wake-up, which the counters must see
            time.sleep(0.2)
            return before, after, window, read_counters(tid, iterations)
        finally:
            service.stop()


async def _native_id() -> int:
    return threading.get_native_id()


def report(before: ThreadCounters, after: ThreadCounters, window: float) -> str:
    return (
        f"idle {window:.1f} s: loop iterations {after.loop_iterations - before.loop_iterations}, "
        f"timeslices {after.timeslices - before.timeslices}, "
        f"voluntary context switches {after.voluntary_switches - before.voluntary_switches}, "
        f"cpu {(after.cpu_ns - before.cpu_ns) / 1000:.0f} us"
    )


@pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")
@pytest.mark.skipif(not Path("/proc/self/task").is_dir(), reason="needs /proc")
def test_idle_wakeups_5_s(capsys: pytest.CaptureFixture[str]) -> None:
    before, after, window, control = measure_idle(5.0)
    with capsys.disabled():
        print("\n" + report(before, after, window))
    check(before, after, control)


def check(before: ThreadCounters, after: ThreadCounters, control: ThreadCounters) -> None:
    assert after.loop_iterations == before.loop_iterations
    assert after.timeslices == before.timeslices
    assert after.voluntary_switches == before.voluntary_switches
    # the instruments work: one function posted to the thread moves all three
    assert control.loop_iterations > after.loop_iterations
    assert control.timeslices > after.timeslices
    assert control.voluntary_switches > after.voluntary_switches


@pytest.mark.perf
@pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")
def test_idle_wakeups_60_s(capsys: pytest.CaptureFixture[str]) -> None:
    before, after, window, control = measure_idle(60.0)
    with capsys.disabled():
        print("\n" + report(before, after, window))
    check(before, after, control)
