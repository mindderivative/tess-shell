"""In-process budget measures for the D-Bus layer, the shortcut service and the portal reader
(B13, B14, B15). Everything runs against fakes on private ``dbus-daemon`` buses
(``tests/fake_dbus.py``); nothing touches the real session."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from tests.fake_dbus import FakeBus, fake_bus, wait_for
from tests.fake_kglobalaccel import FakeKGlobalAccel
from tests.fake_portal import fake_portal
from tests.perf.budget_report import Reading
from tests.test_control import FakeLoop
from tests.test_dbus_idle import measure_idle
from tests.test_dbus_layer import Hooks, Pump, _HookPort

from tess_shell.schema.keys import parse_chord
from tess_shell.services.bus import ServiceThread
from tess_shell.services.layer import Layer
from tess_shell.services.portal import PortalReader
from tess_shell.services.shortcuts import Action, ShortcutService

NAME = "org.test.Battery"
PATH = "/org/test/Battery"
IFACE = "org.test.Battery"
DAEMON = "org.freedesktop.DBus"

FRAME_MS = 1000 / 60  # one frame at 60 Hz: the vault's 16.7 ms


# -- B13 ----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Connections:
    """What the layer opened on one fake daemon, with ``modules`` modules using it."""

    modules: int
    session_connects: int
    system_connects: int
    shell_names: int  # unique names on the two daemons that are not a fake service's


async def _unique_names(service: ServiceThread, kind: str) -> list[str]:
    bus = service.session if kind == "session" else service.system
    reply = await bus.call(DAEMON, "/org/freedesktop/DBus", DAEMON, "ListNames", "", [])
    return [str(n) for n in reply[0] if str(n).startswith(":")]


def connections_for(modules: int) -> Connections:
    """Open the layer with ``modules`` modules, each using a proxy on both buses, and count the
    connections on the two private daemons that belong to the shell."""
    with fake_bus() as session, fake_bus() as system:
        fakes: list[FakeBus] = [session, system]
        for bus in fakes:
            fake = bus.service(NAME)
            fake.add(PATH, IFACE, properties={"Percentage": ("d", 50.0)}, signals={"Ping": "s"})
            fake.up()
        service = ServiceThread(session.address, system.address)
        service.start()
        layer = Layer(service, Pump().call_soon)
        try:
            for n in range(modules):
                dbus = layer.for_module(f"M{n}", lambda k, v: None, _HookPort(Hooks()))
                for port in (dbus.session(), dbus.system()):
                    proxy = port.proxy(NAME, PATH, IFACE)
                    proxy.on_property_changed(lambda values: None)
                    proxy.on_signal("Ping", lambda *a: None)
            assert wait_for(lambda: len(layer._caches) == 2 and service.session.connected)
            assert wait_for(lambda: service.system.connected)
            names = 0
            for kind, bus in (("session", session), ("system", system)):
                have = service.submit(_unique_names(service, kind)).result(5)
                fake_names = {s.unique_name for s in bus.services}
                names += len([n for n in have if n not in fake_names])
            return Connections(modules, service.session.connects, service.system.connects, names)
        finally:
            service.stop()


def measure_b13(quick: bool) -> list[Reading]:
    seconds, runs = (3.0, 1) if quick else (60.0, 2)
    loops: list[float] = []
    slices: list[float] = []
    switches: list[float] = []
    for _ in range(runs):
        before, after, window, _control = measure_idle(seconds)
        loops.append((after.loop_iterations - before.loop_iterations) / window)
        slices.append((after.timeslices - before.timeslices) / window)
        switches.append((after.voluntary_switches - before.voluntary_switches) / window)
    where = f"dbus thread, 2 modules with property + signal subscriptions, {seconds:.0f} s idle"
    note = "idle test of tests/test_dbus_idle.py; the 5 s run is collected by default"
    out = [
        Reading("B13", f"loop iterations per second ({where})", loops, "per s", 0.0, "max",
                note=note),
        Reading("B13", f"kernel timeslices per second ({where})", slices, "per s", 0.0, "max"),
        Reading("B13", f"voluntary context switches per second ({where})", switches, "per s",
                0.0, "max"),
    ]  # fmt: skip
    one = connections_for(1)
    many = connections_for(8)
    out.append(
        Reading(
            "B13",
            "shell connections on the two fake buses, 1 module vs 8 modules (one per bus: 2)",
            [float(one.shell_names), float(many.shell_names)],
            "connections",
            2.0,
            "max",
            note=f"connects counted by the layer: 1 module {one.session_connects}+"
            f"{one.system_connects}, 8 modules {many.session_connects}+{many.system_connects}",
        )
    )
    return out


# -- B14 ----------------------------------------------------------------------------------------

ACTION_IDS = [f"Toggle_{n}" for n in range(10)]


def ten_actions() -> list[Action]:
    chords = ["Meta+Space", "Ctrl+Alt+B", "Ctrl+Alt+F", "Ctrl+Alt+G", "Ctrl+Alt+H",
              "Ctrl+Alt+J", "Ctrl+Alt+K", "Ctrl+Alt+L", "Ctrl+Alt+M", "Ctrl+Alt+N"]  # fmt: skip
    return [
        Action(id_, id_.replace("_", " "), "toggle", f"S{n}", (parse_chord(chords[n]),))
        for n, id_ in enumerate(ACTION_IDS)
    ]


@dataclass(frozen=True)
class Registration:
    ms: float
    do_register: int
    set_keys: int
    set_keys_flags: tuple[int, ...]
    available: int
    registered: int


def register_ten() -> Registration:
    """``ShortcutService.start`` with ten actions on a fresh fake: the time on the service thread
    and the calls the fake received."""
    with fake_bus() as bus:
        fake = FakeKGlobalAccel(bus)
        fake.start()
        service = ServiceThread(bus.address)
        service.start()
        loop = FakeLoop()
        shortcuts = ShortcutService(service, loop.call_soon, lambda a: None)
        try:

            async def timed() -> float:
                started = time.perf_counter()
                await shortcuts.start(ten_actions(), True)
                return (time.perf_counter() - started) * 1000

            ms = service.submit(timed()).result(10)
            sets = fake.of("setShortcutKeys")
            return Registration(
                ms,
                len(fake.of("doRegister")),
                len(sets),
                tuple(sorted({int(c.flags or 0) for c in sets})),
                len(fake.of("isGlobalShortcutAvailable")),
                len(shortcuts.registered),
            )
        finally:
            service.stop()
            loop.close()


def press_latencies(presses: int) -> list[float]:
    """Milliseconds from ``fake.press`` to the callback running on the loop thread."""
    with fake_bus() as bus:
        fake = FakeKGlobalAccel(bus)
        fake.start()
        service = ServiceThread(bus.address)
        service.start()
        loop = FakeLoop()
        arrived: list[float] = []
        shortcuts = ShortcutService(
            service, loop.call_soon, lambda a: arrived.append(time.perf_counter())
        )
        try:
            service.submit(shortcuts.start(ten_actions(), True)).result(10)
            out: list[float] = []
            for n in range(presses):
                started = time.perf_counter()
                fake.press(ACTION_IDS[n % 10])
                assert wait_for(lambda n=n: len(arrived) == n + 1)
                out.append((arrived[n] - started) * 1000)
            return out
        finally:
            service.stop()
            loop.close()


def measure_b14(quick: bool) -> list[Reading]:
    runs, presses = (3, 20) if quick else (20, 50)
    got = [register_ten() for _ in range(runs)]
    note = "wall time of ShortcutService.start on the dbus thread, fake kglobalaccel"
    out = [
        Reading("B14", "10 actions registered (fake kglobalaccel)", [g.ms for g in got], "ms",
                50.0, "median", note=note),
        Reading("B14", "doRegister calls per action", [g.do_register / 10 for g in got], "calls",
                1.0, "max"),
        Reading("B14", "setShortcutKeys calls per action", [g.set_keys / 10 for g in got], "calls",
                1.0, "max",
                note="the vault says one setShortcut per action; the shell sends two "
                f"setShortcutKeys (flags {got[0].set_keys_flags}: present, default) like the "
                "client library: Decision to confirm"),
        Reading("B14", "isGlobalShortcutAvailable calls per action (one chord each)",
                [g.available / 10 for g in got], "calls",
                note="not in the vault's budget: recorded"),
    ]  # fmt: skip
    latencies = press_latencies(presses)
    out.append(
        Reading(
            "B14",
            f"key press (fake.press) to the callback on the loop thread, {presses} presses",
            latencies,
            "ms",
            FRAME_MS,
            "p95",
            note="one frame = 16.7 ms; includes the fake daemon's hop and the dbus thread",
        )
    )
    return out


# -- B15 ----------------------------------------------------------------------------------------


def read_portal(idle_s: float) -> tuple[float, int, int, int]:
    """Start a ``PortalReader`` on a fake portal: the service-thread time of its first read, the
    ReadAll and Register calls at start, and the calls added over ``idle_s`` seconds."""
    with fake_portal() as (address, portal):
        service = ServiceThread(address)
        service.start()
        reader = PortalReader(service, lambda a: None)
        took: list[float] = []
        original: Any = reader._read

        async def timed(*, first: bool) -> None:
            started = time.perf_counter()
            await original(first=first)
            took.append((time.perf_counter() - started) * 1000)

        reader._read = timed  # type: ignore[method-assign]
        try:
            reader.start()
            reader.first(5.0)
            assert wait_for(lambda: len(took) == 1)
            at_start = len(portal.calls)
            time.sleep(idle_s)
            return (
                took[0],
                portal.calls.count("ReadAll"),
                portal.calls.count("Register"),
                (len(portal.calls) - at_start),
            )
        finally:
            reader.stop()
            service.stop()


def measure_b15(quick: bool) -> list[Reading]:
    runs, idle = (3, 1.0) if quick else (12, 3.0)
    got = [read_portal(idle) for _ in range(runs)]
    return [
        Reading("B15", "service-thread time of the first read (Register + ReadAll, fake portal)",
                [g[0] for g in got], "ms", 20.0, "median",
                note="includes the Register call the reader makes first"),
        Reading("B15", "ReadAll calls at start", [float(g[1]) for g in got], "calls", 1.0, "max"),
        Reading("B15", f"portal calls over {idle:.0f} s idle (no polling)",
                [float(g[3]) for g in got], "calls", 0.0, "max"),
    ]  # fmt: skip
