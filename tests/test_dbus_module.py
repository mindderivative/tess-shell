"""A module on the service layer: its hooks through ``ModuleHost``, and the ``available`` key
through an ``If`` (D-Bus Service Layer; M5 Brief, A4 and A5; the empty-state convention G2)."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tess_shell.modules.context import ModuleContext
from tess_shell.modules.ticks import TimeSource
from tess_shell.services.bus import ServiceThread
from tess_shell.services.layer import Layer
from tests.fake_dbus import HAVE_DAEMON, FakeBus, FakeObject, FakeService, fake_bus, wait_for
from tests.test_dbus_layer import Pump
from tests.test_model_structure import Rig as StructureRig
from tests.test_module_host import Rig as HostRig

pytestmark = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")

NAME = "org.test.Battery"
PATH = "/org/test/Battery"
IFACE = "org.test.Battery"


class World:
    """A private bus with a fake battery, the service thread, the layer and a pump for the loop."""

    def __init__(self, bus: FakeBus) -> None:
        self.bus = bus
        self.fake: FakeService = bus.service(NAME)
        self.obj: FakeObject = self.fake.add(
            PATH,
            IFACE,
            properties={"Percentage": ("d", 50.0)},
            methods={"Ping": ([], "", lambda: None)},
        )
        self.fake.up()
        self.service = ServiceThread(bus.address)
        self.service.start()
        self.pump = Pump()
        self.layer = Layer(self.service, self.pump.call_soon)


@pytest.fixture
def world() -> Iterator[World]:
    with fake_bus() as bus:
        w = World(bus)
        try:
            yield w
        finally:
            w.service.stop()


BATTERY = """
from tess_shell import Module

class Battery(Module):
    def __init__(self):
        self.lost, self.found, self.threads = [], [], []

    def start(self):
        proxy = self.ctx.dbus.session().proxy("org.test.Battery", "/org/test/Battery",
                                              "org.test.Battery")
        proxy.on_property_changed(self.changed)

    def changed(self, values):
        if "Percentage" in values:
            self.ctx.send("time", f"{values['Percentage']:.0f}%")

    def on_service_lost(self, name):
        self.lost.append(name)
        self.threads.append(threading.get_ident())
        self.ctx.send("time", "n/a")

    def on_service_found(self, name):
        self.found.append(name)
        self.threads.append(threading.get_ident())
"""


def test_a_module_gets_its_hooks_and_the_available_key_through_the_host(
    world: World, tmp_path: Path
) -> None:
    rig = HostRig(tmp_path)
    rig.host.dbus = world.layer
    code = "import threading\n" + BATTERY
    loaded, findings = rig.load("Battery", code)
    assert loaded is not None and findings == []
    assert rig.host.start(loaded) == []
    use = "Battery@u1"

    def values() -> dict[str, Any]:
        rig.store.flush()
        return dict(rig.store.values[use])

    assert wait_for(lambda: values().get("time") == "50%")
    assert values()["available"] is True  # the layer sent it: the convention of G2
    world.fake.down()
    instance: Any = loaded.instance
    assert world.pump.wait(lambda: instance.lost)
    assert instance.lost == [NAME] and instance.threads == [threading.get_ident()]
    assert values()["available"] is False and values()["time"] == "n/a"
    world.obj.silent_set("Percentage", 80.0)
    world.fake.up()
    assert world.pump.wait(lambda: instance.found)
    assert instance.found == [NAME]
    assert wait_for(lambda: values().get("time") == "80%" and values()["available"] is True)
    # the module stops: its subscriptions and its watch go with it
    rig.host.stop_all()
    assert wait_for(lambda: not world.layer._services and not world.layer._caches)


def test_a_hook_that_raises_is_logged_and_the_module_keeps_running(
    world: World, tmp_path: Path
) -> None:
    from loguru import logger

    rig = HostRig(tmp_path)
    rig.host.dbus = world.layer
    code = "import threading\n" + BATTERY.replace(
        "self.lost.append(name)", "self.lost.append(name)\n        raise RuntimeError('hook')"
    )
    loaded, _ = rig.load("Battery", code)
    assert loaded is not None
    rig.host.start(loaded)
    errors: list[str] = []
    sink = logger.add(lambda m: errors.append(m.record["message"]), level="ERROR")
    try:
        assert wait_for(lambda: world.layer._services)
        time.sleep(0.1)
        world.fake.down()
        assert world.pump.wait(lambda: any("on_service_lost" in e for e in errors))
    finally:
        logger.remove(sink)
    assert loaded.state == "running"
    rig.host.stop_all()


class AvailableRig(StructureRig):
    """The structure rig of the ``If`` tests, with a module whose block is hidden by ``available``
    and a context whose ``dbus`` is the layer."""

    LAYOUT = """
Module {
    FlexBox {
        Name: Row
        Children {
            Text { Name: Clock, Text: {{ time }} }
            If {{ available }} {
                Text { Name: Shown, Text: shown }
            }
        }
    }
}
"""

    def __init__(self, layer: Layer) -> None:
        super().__init__(self.LAYOUT)
        self.ctx = ModuleContext(
            "Todo",
            "uid",
            {},
            {},
            lambda use, key, value: self.store.send("Todo", use, key, value),
            TimeSource(),
            dbus=lambda: layer,
        )

    def send_many(self, **values: object) -> None:
        values.setdefault("available", False)  # before the layer says anything: hidden
        super().send_many(**values)


def test_a_module_hides_and_shows_through_if_when_its_service_leaves_and_returns(
    world: World,
) -> None:
    rig = AvailableRig(world.layer)
    assert rig.texts() == ["10:00"]  # no service state yet: hidden
    seen: list[object] = []
    proxy = rig.ctx.dbus.session().proxy(NAME, PATH, IFACE)
    proxy.on_property_changed(lambda values: seen.append(values))

    def settled(texts: list[str]) -> bool:
        rig.turn()
        return rig.texts() == texts

    assert wait_for(lambda: settled(["10:00", "shown"]))  # the layer sent available true
    world.fake.down()
    assert wait_for(lambda: settled(["10:00"]))  # false: the If hides the block
    world.fake.up()
    assert wait_for(lambda: settled(["10:00", "shown"]))  # and it is back, without a rebuild call
    rig.ctx.close()


def test_the_layer_never_touches_a_node_or_the_loop_from_its_thread(world: World) -> None:
    """A callback on the service thread only calls ``ctx.send``; a hook crosses with call_soon."""
    threads: list[int] = []
    rig = AvailableRig(world.layer)
    rig.ctx.set_service_hooks(
        lambda name: threads.append(threading.get_ident()),
        lambda name: threads.append(threading.get_ident()),
    )
    rig.ctx.dbus.session().proxy(NAME, PATH, IFACE)
    assert wait_for(lambda: rig.ctx.dbus.available)
    world.fake.down()
    assert world.pump.wait(lambda: threads)
    assert threads == [threading.get_ident()] and threading.get_ident() != world.service.thread_id
    rig.ctx.close()


def test_callback_cost_with_ctx_send_and_signal_latency(
    world: World, capsys: pytest.CaptureFixture[str]
) -> None:
    """What a real callback costs on the service thread (``ctx.send`` into the value store), and
    how long a property change takes from the fake service to the callback."""
    rig = AvailableRig(world.layer)
    arrivals: list[float] = []

    def changed(values: Any) -> None:
        rig.ctx.send("time", f"{values['Percentage']:.0f}%")
        arrivals.append(time.perf_counter())

    rig.ctx.dbus.session().proxy(NAME, PATH, IFACE).on_property_changed(changed)
    assert wait_for(lambda: arrivals)
    latencies: list[float] = []
    for i in range(200):
        before = len(arrivals)
        sent = time.perf_counter()
        world.obj.set("Percentage", float(i))
        assert wait_for(lambda n=before: len(arrivals) > n)
        latencies.append(arrivals[before] - sent)
    count, p50, p99, worst = world.layer.callback_summary("Todo")
    ordered = sorted(latencies)
    with capsys.disabled():
        print(
            f"\ncallback with ctx.send: n={count} p50={p50 * 1e6:.1f} us p99={p99 * 1e6:.1f} us "
            f"max={worst * 1e6:.1f} us; set() to callback: p50={ordered[100] * 1e3:.2f} ms "
            f"p99={ordered[197] * 1e3:.2f} ms max={ordered[-1] * 1e3:.2f} ms"
        )
    assert p99 < 0.001  # the 1 ms budget of a callback's own work
    assert ordered[197] < 0.1  # the 100 ms budget, signal to callback
    rig.ctx.close()
