"""``Call`` on a module in a process: the control interface waits for the process's answer without
holding the loop, an action that raises is the same ``ActionFailed`` error, a module that does not
answer is a ``Timeout`` that says so, and ``status`` shows the processes."""

from __future__ import annotations

import concurrent.futures
import json
import threading
from typing import Any

import pytest

from tess_shell.client import text_status
from tess_shell.modules.host import ActionError
from tess_shell.services.control import ERROR, CommandError
from tests.fake_dbus import HAVE_DAEMON
from tests.test_control import rig

pytestmark = pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed")


def test_a_call_waits_for_the_future_and_returns_its_value_as_json_and_errors_as_ever() -> None:
    with rig(loop_timeout=0.8) as r:
        c = r.client()
        later: dict[str, concurrent.futures.Future[Any]] = {}

        def call(module: str, action: str, values: list[Any]) -> Any:
            future: concurrent.futures.Future[Any] = concurrent.futures.Future()
            later[module] = future
            if module == "Ok":
                threading.Timer(0.1, future.set_result, [{"echo": values}]).start()
            elif module == "Bad":
                threading.Timer(
                    0.1, future.set_exception, [CommandError("Bad.go: it broke", "ActionFailed")]
                ).start()
            return future  # "Never": nothing completes it

        r.commands.call = call  # type: ignore[method-assign]
        (out,) = c.ok("Call", "sss", ["Ok", "go", json.dumps([1, "two"])])
        assert json.loads(out) == {"echo": [1, "two"]}
        err = c.error("Call", "sss", ["Bad", "go", "[]"])
        assert err.error_name == ERROR + "ActionFailed" and err.body[0] == "Bad.go: it broke"
        late = c.error("Call", "sss", ["Never", "go", "[]"])
        assert late.error_name == ERROR + "Timeout"
        assert "the module's process did not answer within 0.8 s" in late.body[0]
        assert c.ok("Status")  # the loop thread was never held


def test_an_action_error_from_a_process_becomes_the_command_error_of_a_failed_call() -> None:
    from tess_shell.commands import _as_command_result

    failing: concurrent.futures.Future[Any] = concurrent.futures.Future()
    mapped = _as_command_result(failing)
    failing.set_exception(ActionError("Mod.go raised ValueError: nope"))
    with pytest.raises(CommandError, match="Mod.go raised ValueError: nope") as info:
        mapped.result(1)
    assert info.value.name == "ActionFailed"
    fine: concurrent.futures.Future[Any] = concurrent.futures.Future()
    ok = _as_command_result(fine)
    fine.set_result([1])
    assert ok.result(1) == [1]


def test_the_status_text_names_the_module_processes_when_there_are_some() -> None:
    base = {"state": "running", "version": {}, "modules": ["Q"], "errors": []}
    plain = text_status(base)
    assert "module processes" not in plain
    shown = text_status(
        {
            **base,
            "module_processes": [
                {"module": "Q", "pid": 42, "state": "running", "tries": 0},
                {"module": "R", "pid": 43, "state": "failed", "tries": 2},
            ],
        }
    )
    assert "module processes: Q (pid 42, running), R (pid 43, failed, restart 2 of 5)" in shown
