"""A module's code that raises also reaches the control interface: ``ErrorReported(rule, file, line,
message)`` once for each distinct error a minute (IPC and CLI > Interface; D-039). The log line is
still written every time. A private bus and a headless Bar only."""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Any

import pytest

from tess_shell.logging import (
    MODULE_ERROR_EVERY,
    _module_errors,
    finding_sinks,
    note_module_error,
)
from tess_shell.schema.findings import Finding
from tess_shell.services.layer import Layer
from tests.fake_dbus import HAVE_DAEMON, wait_for
from tests.test_control import Listener, rig
from tests.widgets_live import running

DRIVER = (
    "Module { FlexBox { Name: Root, Width: 40, Height: 20, "
    "On_Click { Action: boom, n: {{ 1 }} } } }"
)
DRIVER_PY = """
from tess_shell import Module, action

class Driver(Module):
    @action
    def boom(self, event, n=0):
        raise RuntimeError("boom on purpose")
"""


@pytest.fixture(autouse=True)
def fresh() -> Iterator[None]:
    _module_errors.clear()
    yield
    _module_errors.clear()


@contextmanager
def sink() -> Iterator[list[Finding]]:
    seen: list[Finding] = []
    finding_sinks.append(seen.append)
    try:
        yield seen
    finally:
        finding_sinks.remove(seen.append)


def divide(name: str) -> None:
    raise ZeroDivisionError("division by zero")


def raised() -> RuntimeError:
    try:
        raise RuntimeError("it broke")
    except RuntimeError as exc:
        return exc


def test_one_finding_for_each_distinct_error_a_minute_and_again_after_it() -> None:
    now = [100.0]
    with sink() as seen:
        for _ in range(3):
            note_module_error("Tray", "Tray.activate", raised(), clock=lambda: now[0])
        note_module_error("Tray", "Tray.menu", raised(), clock=lambda: now[0])  # another place
        note_module_error(
            "Clock", "Tray.activate", raised(), clock=lambda: now[0]
        )  # another module
        assert len(seen) == 3
        now[0] += MODULE_ERROR_EVERY + 1
        note_module_error("Tray", "Tray.activate", raised(), clock=lambda: now[0])
        assert len(seen) == 4
    first = seen[0]
    assert (first.severity, first.rule) == ("error", "module-exception")
    assert first.message == "Tray: Tray.activate raised RuntimeError: it broke"
    assert first.file.endswith("test_module_error.py") and first.line > 1  # where it was raised


def test_an_action_that_raises_is_logged_every_time_and_reported_once() -> None:
    lines: list[str] = []
    with sink() as seen, running("Driver { }", driver=DRIVER, driver_py=DRIVER_PY) as w:
        for _ in range(3):
            w.window.simulate("click", node=w.of_use("Driver", "Root"))
        lines = [x for x in w.lines if "Driver.boom raised" in x]
    assert len(lines) == 3  # the log is not rate limited
    assert len(seen) == 1 and seen[0].rule == "module-exception"
    assert seen[0].message == "Driver: Driver.boom raised RuntimeError: boom on purpose"
    assert seen[0].file.endswith("Driver_Module.py") and seen[0].line == 7


def test_a_raising_service_hook_and_call_soon_callback_are_reported() -> None:
    with sink() as seen, running("Driver { }", driver=DRIVER, driver_py=DRIVER_PY) as w:
        ctx = w.host.loaded["Driver"].instance.ctx
        ctx.set_service_hooks(divide, lambda n: None)
        ctx.lost("org.x")
        ctx.close()
    assert [f.message for f in seen] == [
        "Driver: on_service_lost raised ZeroDivisionError: division by zero"
    ]


def test_a_d_bus_callback_that_raises_is_reported_through_the_layer() -> None:
    told: list[tuple[str, str, str]] = []
    layer = Layer.__new__(Layer)
    layer.callback_times = {}
    layer.on_module_error = lambda m, w, e: told.append((m, w, type(e).__name__))
    helper = SimpleNamespace(
        module="Tray", log=SimpleNamespace(opt=lambda **k: SimpleNamespace(error=lambda msg: None))
    )

    def bad() -> None:
        raise ValueError("x")

    layer.timed(helper, bad)  # type: ignore[arg-type]
    assert told == [("Tray", "a D-Bus callback", "ValueError")]


@pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")
def test_the_control_interface_emits_error_reported_for_a_module_exception() -> None:
    with rig() as r:
        listener = Listener(r.bus)
        listener.start()
        finding_sinks.append(r.control.error_reported)  # what the app does when it owns the name
        try:
            with running("Driver { }", driver=DRIVER, driver_py=DRIVER_PY) as w:
                for _ in range(3):
                    w.window.simulate("click", node=w.of_use("Driver", "Root"))
            seen: list[Any] = []
            assert wait_for(lambda: any(n == "ErrorReported" for n, _ in listener.seen), 5)
            time.sleep(0.3)
            seen = [b for n, b in listener.seen if n == "ErrorReported"]
        finally:
            finding_sinks.remove(r.control.error_reported)
            listener.stop()
    assert len(seen) == 1  # once, though it raised three times
    rule, file, line, message = seen[0]
    assert rule == "module-exception" and file.endswith("Driver_Module.py") and line == 7
    assert message == "Driver: Driver.boom raised RuntimeError: boom on purpose"
    assert r.control.errors.last()[0]["rule"] == "module-exception"  # and Status keeps it
