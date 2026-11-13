"""The control interface on a private bus (IPC and CLI > The Interface, Threading; ADR-0013): the
object a client sees, the loop handoff, the name, the reconnect, the signals. The shell's own
commands are replaced by a fake that records the thread each ran on."""

from __future__ import annotations

import json
import queue
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any

import pytest
from dbus_fast import BusType, Message, MessageType, Variant
from dbus_fast.aio import MessageBus

from tess_shell.schema.findings import Finding
from tess_shell.services.bus import ServiceThread
from tess_shell.services.control import (
    API_VERSION,
    INTERFACE,
    NAME,
    PATH,
    CommandError,
    ControlService,
)
from tests.fake_dbus import HAVE_DAEMON, FakeBus, fake_bus, wait_for

pytestmark = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")

ERROR = INTERFACE + ".Error."


class FakeLoop:
    """What ``LoopHandle.call_soon`` is: a thread that runs what it is given, one at a time."""

    def __init__(self) -> None:
        self.jobs: queue.Queue[Callable[[], None] | None] = queue.Queue()
        self.stuck = threading.Event()
        self.thread = threading.Thread(target=self._run, name="fake-loop", daemon=True)
        self.thread.start()

    def _run(self) -> None:
        while (job := self.jobs.get()) is not None:
            job()

    def call_soon(self, fn: Callable[[], None]) -> None:
        if not self.stuck.is_set():
            self.jobs.put(fn)

    def close(self) -> None:
        self.jobs.put(None)
        self.thread.join(5)


@dataclass
class FakeCommands:
    """Records the thread of each command; answers like the shell would."""

    threads: dict[str, str] = field(default_factory=dict)
    stopped: int = 0
    refuse: bool = False

    def _note(self, what: str) -> None:
        self.threads[what] = threading.current_thread().name

    def status(self) -> dict[str, Any]:
        self._note("status")
        return {"version": {"shell": "x"}, "monitors": [], "surfaces": [], "modules": []}

    def surface(self, action: str, name: str) -> tuple[bool, str]:
        self._note("surface")
        if name == "Nope":
            return False, "no surface named Nope"
        return True, f"{name} {action}"

    def close_popup(self) -> None:
        self._note("close_popup")

    def call(self, module: str, action: str, values: list[Any]) -> Any:
        self._note("call")
        if module == "Boom":
            raise CommandError("Boom.go: it failed", "ActionFailed")
        if module == "Bug":
            raise RuntimeError("secret internals")
        if module == "Odd":
            return object()
        return {"module": module, "action": action, "values": values}

    def set_log_level(self, level: str) -> None:
        self._note("set_log_level")

    def reload_validate(self) -> Any:
        self._note("reload_validate")
        if self.refuse:
            return (False, "reload refused (1 errors)")
        return "ticket"

    def reload_apply(self, ticket: Any) -> tuple[bool, str]:
        self._note("reload_apply")
        return True, f"reloaded {ticket}"

    def quit(self) -> None:
        self._note("quit")
        self.stopped += 1


@dataclass
class Rig:
    bus: FakeBus
    service: ServiceThread
    loop: FakeLoop
    commands: FakeCommands
    control: ControlService

    def client(self) -> Client:
        return Client(self.bus)


class Client:
    """A dbus-fast client of the private bus, on the fake thread."""

    def __init__(self, bus: FakeBus) -> None:
        self.bus = bus

    def call(
        self,
        member: str,
        signature: str = "",
        body: list[Any] | None = None,
        *,
        interface: str = INTERFACE,
        path: str = PATH,
        destination: str = NAME,
        timeout: float = 8.0,
    ) -> Message:
        async def go() -> Message:
            conn = await MessageBus(
                bus_address=self.bus.address, bus_type=BusType.SESSION
            ).connect()
            try:
                reply = await conn.call(
                    Message(
                        destination=destination,
                        path=path,
                        interface=interface,
                        member=member,
                        signature=signature,
                        body=body or [],
                    )
                )
                assert reply is not None
                return reply
            finally:
                conn.disconnect()

        return self.bus.thread.run(go(), timeout)

    def ok(self, member: str, signature: str = "", body: list[Any] | None = None) -> list[Any]:
        reply = self.call(member, signature, body)
        assert reply.message_type == MessageType.METHOD_RETURN, (reply.error_name, reply.body)
        return list(reply.body)

    def error(self, member: str, signature: str = "", body: list[Any] | None = None) -> Message:
        reply = self.call(member, signature, body)
        assert reply.message_type == MessageType.ERROR, reply.body
        return reply

    def prop(self, name: str) -> Any:
        reply = self.call(
            "Get",
            "ss",
            [INTERFACE, name],
            interface="org.freedesktop.DBus.Properties",
        )
        assert reply.message_type == MessageType.METHOD_RETURN, reply.body
        variant: Variant = reply.body[0]
        return variant.value

    def owner(self) -> str | None:
        reply = self.call(
            "GetNameOwner",
            "s",
            [NAME],
            interface="org.freedesktop.DBus",
            path="/org/freedesktop/DBus",
            destination="org.freedesktop.DBus",
        )
        return str(reply.body[0]) if reply.message_type == MessageType.METHOD_RETURN else None


@contextmanager
def rig(
    *, state: str | None = "running", refuse: bool = False, loop_timeout: float = 5.0
) -> Iterator[Rig]:
    with fake_bus() as bus:
        service = ServiceThread(bus.address)
        service.start()
        loop = FakeLoop()
        commands = FakeCommands(refuse=refuse)
        control = ControlService(
            service, loop.call_soon, commands, "9.9.9", loop_timeout=loop_timeout
        )
        try:
            assert service.submit(control.start()).result(8) is True
            if state:
                control.set_state(state)
            yield Rig(bus, service, loop, commands, control)
        finally:
            try:
                service.submit(control.stop()).result(5)
            finally:
                service.stop()
                loop.close()


def test_the_name_object_and_interface_are_the_documented_ones() -> None:
    assert NAME == "io.github.mindderivative.TesseraeShell"
    assert PATH == "/io/github/mindderivative/TesseraeShell"
    assert INTERFACE == "io.github.mindderivative.TesseraeShell1"


def test_the_client_repeats_the_same_names() -> None:
    from tess_shell import client

    assert (client.NAME, client.PATH, client.INTERFACE) == (NAME, PATH, INTERFACE)


def test_introspection_lists_the_methods_properties_and_signals() -> None:
    with rig() as r:
        reply = r.client().call("Introspect", interface="org.freedesktop.DBus.Introspectable")
    xml = reply.body[0]
    from xml.etree import ElementTree

    root = ElementTree.fromstring(xml)
    (iface,) = [i for i in root.findall("interface") if i.get("name") == INTERFACE]
    methods = {m.get("name") for m in iface.findall("method")}
    props = {p.get("name") for p in iface.findall("property")}
    signals = {s.get("name") for s in iface.findall("signal")}
    assert methods == {
        "Reload",
        "Quit",
        "Status",
        "Show",
        "Hide",
        "Toggle",
        "ClosePopup",
        "Call",
        "SetLogLevel",
    }
    assert props == {"State", "Version", "ApiVersion"}
    assert signals == {"Reloaded", "ErrorReported", "SurfaceChanged"}
    # not the methods the spec leaves out: no FullscreenState, no events, no kwin
    assert not {"FullscreenState", "Events", "Kwin", "KWin"} & (methods | props | signals)
    signatures = {
        m.get("name"): "".join(a.get("type", "") for a in m) for m in iface.findall("method")
    }
    assert signatures["Call"] == "sssas".replace("as", "s")  # three strings in, one out
    assert signatures["Show"] == "sbs"  # the name in, (ok, message) out
    assert signatures["Reload"] == "bs"


def test_the_properties_are_the_state_the_version_and_the_api_version() -> None:
    with rig(state=None) as r:
        c = r.client()
        assert c.prop("State") == "starting"
        r.control.set_state("running")
        assert wait_for(lambda: c.prop("State") == "running")
        assert c.prop("Version") == "9.9.9"
        assert c.prop("ApiVersion") == API_VERSION == 1


def test_a_command_is_handed_to_the_loop_and_never_runs_on_the_dbus_thread() -> None:
    with rig() as r:
        c = r.client()
        c.ok("Status")
        assert c.ok("Show", "s", ["Launcher"]) == [True, "Launcher Show"]
        assert c.ok("Hide", "s", ["Launcher"]) == [True, "Launcher Hide"]
        assert c.ok("Toggle", "s", ["Launcher"]) == [True, "Launcher Toggle"]
        c.ok("ClosePopup")
        c.ok("SetLogLevel", "s", ["DEBUG"])
        assert c.ok("Reload") == [True, "reloaded ticket"]
        threads = dict(r.commands.threads)
    loop_side = {"status", "surface", "close_popup", "set_log_level", "reload_apply"}
    assert {k: threads[k] for k in loop_side} == dict.fromkeys(loop_side, "fake-loop")
    # the files are read on a worker thread, never on the dbus thread and never on the loop
    assert threads["reload_validate"] not in ("dbus", "fake-loop")


def test_a_refused_reload_is_answered_without_touching_the_loop() -> None:
    with rig(refuse=True) as r:
        assert r.client().ok("Reload") == [False, "reload refused (1 errors)"]
        assert "reload_apply" not in r.commands.threads


def test_a_stuck_loop_gives_a_timeout_error_and_the_next_command_still_works() -> None:
    with rig(loop_timeout=0.4) as r:
        c = r.client()
        r.loop.stuck.set()
        started = time.monotonic()
        reply = c.error("Status")
        assert reply.error_name == ERROR + "Timeout"
        assert 0.35 < time.monotonic() - started < 3
        assert "0.4 s" in reply.body[0]
        r.loop.stuck.clear()
        c.ok("Status")  # the dbus thread was never stuck


def test_a_command_error_names_what_failed_and_internal_errors_hide_nothing_but_the_type() -> None:
    with rig() as r:
        c = r.client()
        err = c.error("Call", "sss", ["Boom", "go", "[]"])
        assert err.error_name == ERROR + "ActionFailed"
        assert err.body[0] == "Boom.go: it failed"
        bug = c.error("Call", "sss", ["Bug", "go", "[]"])
        assert bug.error_name == ERROR + "Failed"
        assert "RuntimeError" in bug.body[0]
        assert c.ok("Status")  # the thread survived


def test_call_carries_json_in_and_json_out() -> None:
    with rig() as r:
        c = r.client()
        (out,) = c.ok("Call", "sss", ["Mod", "act", json.dumps([1, "two", {"k": [3]}])])
        assert json.loads(out) == {
            "module": "Mod",
            "action": "act",
            "values": [1, "two", {"k": [3]}],
        }
        assert c.ok("Call", "sss", ["Odd", "x", "[]"]) == ["null"]  # not plain data
        assert c.error("Call", "sss", ["M", "a", "not json"]).error_name == ERROR + "BadArguments"
        assert c.error("Call", "sss", ["M", "a", '{"a": 1}']).error_name == ERROR + "BadArguments"


def test_commands_are_refused_while_the_shell_is_not_running() -> None:
    with rig(state="starting") as r:
        c = r.client()
        for member, sig, body in (
            ("Show", "s", ["A"]),
            ("Reload", "", []),
            ("Call", "sss", ["M", "a", "[]"]),
            ("Quit", "", []),
        ):
            assert c.error(member, sig, body).error_name == ERROR + "NotRunning"
        (status,) = c.ok("Status")  # status answers in every state, from the dbus thread
        assert json.loads(status)["state"] == "starting"
        assert r.commands.threads == {}


def test_quit_stops_the_engine_from_the_service_thread() -> None:
    with rig() as r:
        c = r.client()
        c.ok("Quit")
        assert r.commands.stopped == 1
        assert r.commands.threads["quit"] == "dbus"  # LoopHandle.stop may be called from any thread
        assert r.control.state == "stopping"
        assert c.error("Quit").error_name == ERROR + "NotRunning"


def test_a_name_that_is_owned_means_another_shell_runs() -> None:
    with fake_bus() as bus:
        first = ServiceThread(bus.address)
        second = ServiceThread(bus.address)
        first.start()
        second.start()
        loop = FakeLoop()
        try:
            a = ControlService(first, loop.call_soon, FakeCommands(), "1")
            b = ControlService(second, loop.call_soon, FakeCommands(), "2")
            assert first.submit(a.start()).result(8) is True and a.owned
            assert second.submit(b.start()).result(8) is False and not b.owned
            owner = Client(bus).owner()
            assert owner is not None
            # the first one is still served: the second took nothing
            a.set_state("running")
            assert wait_for(lambda: Client(bus).prop("Version") == "1")
        finally:
            first.stop()
            second.stop()
            loop.close()


def test_the_name_and_the_object_come_back_after_the_bus_restarts() -> None:
    with rig() as r:
        c = r.client()
        before = c.owner()
        assert before is not None
        r.bus.daemon.restart(pause=0.2)
        assert wait_for(lambda: _safe(c.owner) is not None, timeout=20)
        assert r.control.exported >= 2
        assert wait_for(lambda: _safe(lambda: c.prop("Version")) == "9.9.9", timeout=10)
        assert c.ok("Show", "s", ["Launcher"]) == [True, "Launcher Show"]


def _safe(fn: Callable[[], Any]) -> Any:
    try:
        return fn()
    except Exception:
        return None


def test_stopping_gives_the_name_up() -> None:
    with rig() as r:
        c = r.client()
        assert c.owner() is not None
        r.service.submit(r.control.stop()).result(5)
        assert c.owner() is None
        assert not r.control.owned


class Listener:
    """Collects the signals of the interface on a connection of its own."""

    def __init__(self, bus: FakeBus) -> None:
        self.seen: list[tuple[str, list[Any]]] = []
        self.bus = bus
        self.conn: MessageBus | None = None

    def start(self) -> None:
        async def go() -> None:
            conn = await MessageBus(bus_address=self.bus.address).connect()
            await conn.call(
                Message(
                    destination="org.freedesktop.DBus",
                    path="/org/freedesktop/DBus",
                    interface="org.freedesktop.DBus",
                    member="AddMatch",
                    signature="s",
                    body=[f"type='signal',sender='{NAME}'"],
                )
            )

            def on(message: Message) -> None:
                if message.message_type == MessageType.SIGNAL:
                    self.seen.append((message.member or "", list(message.body)))

            conn.add_message_handler(on)
            self.conn = conn

        self.bus.thread.run(go())

    def stop(self) -> None:
        if self.conn is not None:
            self.conn.disconnect()


def test_the_signals_are_emitted_when_something_happened() -> None:
    with rig(state=None) as r:
        listener = Listener(r.bus)
        listener.start()
        try:
            r.control.set_state("running")
            r.control.reloaded(True, "reloaded (a.tdl) in 12 ms")
            r.control.error_reported(Finding("a.tdl", 3, 1, "error", "unknown-key", "no key X"))
            r.control.error_reported(Finding("a.tdl", 4, 1, "warning", "note", "just a warning"))
            r.control.surface_changed("Launcher", "shown")
            assert wait_for(lambda: len(listener.seen) >= 4)
            time.sleep(0.2)
        finally:
            listener.stop()
    by_name = {name: body for name, body in listener.seen}
    assert by_name["Reloaded"] == [True, "reloaded (a.tdl) in 12 ms"]
    assert by_name["ErrorReported"] == ["unknown-key", "a.tdl", 3, "no key X"]
    assert by_name["SurfaceChanged"] == ["Launcher", "shown"]
    names = [n for n, _ in listener.seen]
    assert names.count("ErrorReported") == 1  # a warning is no error
    changed = [b for n, b in listener.seen if n == "PropertiesChanged"]
    assert any("State" in b[1] for b in changed)


def test_the_last_errors_are_kept_without_their_log_lines() -> None:
    with rig() as r:
        r.control.error_reported(Finding("f.tdl", 1, 1, "error", "r", "m"))
        assert r.control.errors.last() == [
            {"rule": "r", "file": "f.tdl", "line": 1, "message": "m"}
        ]


def test_a_burst_of_calls_costs_the_dbus_thread_little() -> None:
    """The time the handler itself takes on the dbus thread (not the loop's): p50 and p99."""
    with rig() as r:
        c = r.client()
        times: list[float] = []
        original = r.control.on_loop

        async def timed(fn: Callable[[], Any]) -> Any:
            started = time.perf_counter()
            try:
                return await original(fn)
            finally:
                times.append(time.perf_counter() - started)

        r.control.on_loop = timed  # type: ignore[method-assign]
        for _ in range(200):
            c.ok("Show", "s", ["Launcher"])
    times.sort()
    p50, p99 = times[len(times) // 2], times[int(len(times) * 0.99)]
    print(
        f"\ncontrol handler round trip to the loop and back: p50 {p50 * 1e3:.2f} ms, "
        f"p99 {p99 * 1e3:.2f} ms over {len(times)} calls"
    )
    assert p99 < 0.05
