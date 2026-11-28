"""A user module in a process, through the real module host: the stub, the messages, the actions,
the failures that mark one module failed. Real child processes (about 100 ms each); the main
thread plays the shell's loop (``ProcRig.pump``). Nothing here touches a session."""

from __future__ import annotations

import os
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from loguru import logger

from tess_shell.binder.model import Handler
from tess_shell.modules.host import ActionError
from tess_shell.schema.findings import Finding
from tests.modproc_rig import ProcRig, new_rig

GOOD = """
import os
from tess_shell import Module, action

class Good(Module):
    def __init__(self):
        self.seen_uses = []

    def start(self):
        self.ctx.send("pid", os.getpid())
        self.ctx.send("time", "12:00")

    def stop(self):
        with open(os.path.join(os.path.dirname(__file__), "stopped.txt"), "w") as f:
            f.write("stopped")

    @action
    def greet(self, event, who="nobody", times=1):
        self.ctx.send("greeting", f"hi {who} x{times}")
        return {"who": who, "caller": self.ctx.caller.key if self.ctx.caller else None}

    @action
    def boom(self, event):
        raise ValueError("it broke")

    def use_added(self, use):
        self.seen_uses.append(use.key)
        self.ctx.send("uses", sorted(self.ctx.uses))

    def use_removed(self, use):
        self.ctx.send("uses", sorted(self.ctx.uses))
"""


@pytest.fixture(name="rig")
def rig_fixture(tmp_path: Path) -> Iterator[ProcRig]:
    yield from new_rig(tmp_path)


@pytest.fixture
def logs() -> Iterator[list[tuple[str, str, str]]]:
    """(level, source, message) of every line the shell logs."""
    lines: list[tuple[str, str, str]] = []

    def sink(message: Any) -> None:
        r = message.record
        lines.append((r["level"].name, str(r["extra"].get("source", "")), r["message"]))

    sink_id = logger.add(sink, level="DEBUG")
    try:
        yield lines
    finally:
        logger.remove(sink_id)


def started(rig: ProcRig, name: str = "Good", uses: int = 1, code: str = GOOD) -> Any:
    loaded, findings = rig.load(name, code, uses=uses)
    assert loaded is not None and findings == [], findings
    assert rig.host.start(loaded) == []
    return loaded


def test_the_modules_python_runs_in_a_process_of_its_own_and_its_values_reach_the_store(
    rig: ProcRig,
) -> None:
    loaded = started(rig)
    assert loaded.remote is not None and loaded.state == "running"
    pid = rig.wait_value("Good@u1", "pid")
    assert pid != os.getpid() and pid == loaded.remote.pid  # type: ignore[attr-defined]
    assert rig.wait_value("Good@u1", "time") == "12:00"


def test_nothing_of_the_file_runs_in_the_shell_and_a_syntax_error_starts_no_process(
    rig: ProcRig, tmp_path: Path
) -> None:
    marker = tmp_path / "ran.txt"
    code = (
        f"from tess_shell import Module\nopen({str(marker)!r}, 'w').write('x')\n"
        "class A(Module): pass\n"
    )
    loaded, findings = rig.load("Marked", code)
    assert loaded is not None and findings == []
    assert not marker.exists(), "the shell must not run a user module's file"
    rig.host.start(loaded)
    rig.pump(lambda: marker.exists())  # the process runs it
    before = len(rig.processes.handles)
    bad, findings = rig.load("Syn", "from tess_shell import Module\nclass A(Module:\n")
    assert bad is None and [f.rule for f in findings] == ["module-import"]
    assert findings[0].line == 2 and "Syn_Module.py" in findings[0].file
    assert len(rig.processes.handles) == before, "a file that does not parse starts no process"


def test_a_missing_file_and_a_wrong_class_count_are_the_hosts_findings(rig: ProcRig) -> None:
    loaded, findings = rig.load("Gone", None)
    assert loaded is None and findings[0].rule == "module-no-python"
    loaded, findings = rig.load("Two", GOOD + "\nclass Other(Module):\n    pass\n")
    assert loaded is None and findings[0].rule == "module-classes"
    assert "2 classes" in findings[0].message and "Good, Other" in findings[0].message


def test_an_action_runs_in_the_process_with_its_arguments_and_the_caller(rig: ProcRig) -> None:
    loaded = started(rig, uses=2)
    rig.wait_value("Good@u1", "time")
    handler = Handler("greet", {"who": "Ann", "times": 3}, use="Good@u2")
    rig.host.dispatch(handler, "On_Click", None)
    assert rig.wait_value("Good@u1", "greeting") == "hi Ann x3"
    assert loaded.ctx.caller is None  # only while the handler runs


def test_a_control_call_returns_what_the_action_returned_and_a_failing_one_names_the_module(
    rig: ProcRig,
) -> None:
    started(rig)
    result = rig.host.call_action("Good", "greet", ["Bob", 2])
    rig.pump(result.done)
    assert result.result() == {"who": "Bob", "caller": None}
    failing = rig.host.call_action("Good", "boom", [])
    rig.pump(failing.done)
    with pytest.raises(ActionError, match="Good.boom raised ValueError: it broke"):
        failing.result()


def test_an_action_the_file_does_not_have_is_unknown_before_anything_runs(rig: ProcRig) -> None:
    started(rig)
    found = rig.host.check_calls([Handler("nothing", module="Good", use="X@1")])
    assert [f.rule for f in found] == ["unknown-action"]
    ok = rig.host.check_calls([Handler("greet", {"who": "x"}, module="Good", use="X@1")])
    assert ok == []
    bad_arg = rig.host.check_calls([Handler("greet", {"whom": "x"}, module="Good", use="X@1")])
    assert [f.rule for f in bad_arg] == ["unknown-argument"]


def test_event_fields_cross_and_event_stop_says_it_does_nothing_once(
    rig: ProcRig, logs: list[tuple[str, str, str]]
) -> None:
    code = """
from tess_shell import Module, action

class Ev(Module):
    @action
    def click(self, event):
        event.stop()
        event.stop()
        kind = type(event.rect).__name__
        seen = [event.name, event.button, list(event.rect), kind, event.x, event.use]
        self.ctx.send("seen", seen)
"""
    started(rig, "Ev", code=code)
    raw = type("Raw", (), {"window_x": 4.5, "button": "primary", "rect": (1.0, 2.0, 3.0, 4.0)})()
    rig.host.dispatch(Handler("click", use="Ev@u1"), "On_Click", raw)
    assert rig.wait_value("Ev@u1", "seen") == [
        "click",
        "primary",
        [1.0, 2.0, 3.0, 4.0],
        "tuple",
        4.5,
        "Ev@u1",
    ]
    rig.pump(lambda: any("Event.stop() has no effect" in m for _, _, m in logs))
    assert sum("Event.stop() has no effect" in m for _, _, m in logs) == 1


def test_the_uses_are_mirrored_in_order_with_the_hooks(rig: ProcRig) -> None:
    from tests.test_module_host import use as make_use

    loaded = started(rig, uses=1)
    rig.wait_value("Good@u1", "time")
    new = [*loaded.uses, make_use("Good", 2)]
    rig.store.add_use("Good", "Good@u2")
    rig.host._sync_uses(loaded, new)
    assert rig.wait_value("Good@u1", "uses") == ["Good@u1", "Good@u2"]
    rig.host._sync_uses(loaded, new[:1])
    rig.pump(lambda: rig.value("Good@u1", "uses") == ["Good@u1"])


def test_the_modules_log_lines_come_out_of_the_shell_under_its_name(
    rig: ProcRig, logs: list[tuple[str, str, str]]
) -> None:
    code = """
from tess_shell import Module

class Lg(Module):
    def start(self):
        self.ctx.log.warning("a warning from the module")
        self.ctx.log.debug("a debug line")
        try:
            1 / 0
        except ZeroDivisionError:
            self.ctx.log.opt(exception=True).error("with a traceback")
"""
    started(rig, "Lg", code=code)
    rig.pump(lambda: any("with a traceback" in m for _, _, m in logs))
    mine = [(lvl, src, m) for lvl, src, m in logs if src == "module:Lg"]
    assert ("WARNING", "module:Lg", "a warning from the module") in mine
    assert any("ZeroDivisionError" in m and lvl == "ERROR" for lvl, _, m in mine)


def test_a_value_for_another_modules_use_is_refused(
    rig: ProcRig, logs: list[tuple[str, str, str]]
) -> None:
    code = """
from tess_shell import Module

class Sn(Module):
    def start(self):
        self.ctx.send("stolen", "x", use="Other@u1")
        self.ctx.send("mine", "y")
"""
    rig.store.add_use("Other", "Other@u1")
    started(rig, "Sn", code=code)
    rig.wait_value("Sn@u1", "mine")
    assert rig.value("Other@u1", "stolen") is None
    assert any("not its use" in m for _, _, m in logs)


def test_a_value_that_is_not_plain_data_is_logged_and_dropped_in_the_process(
    rig: ProcRig, logs: list[tuple[str, str, str]]
) -> None:
    code = (
        "from tess_shell import Module\nclass P(Module):\n    def start(self):\n"
        "        self.ctx.send('bad', object())\n        self.ctx.send('ok', (1, 2))\n"
    )
    started(rig, "P", code=code)
    assert rig.wait_value("P@u1", "ok") == [1, 2]
    assert rig.value("P@u1", "bad") is None
    assert any("not a string, number" in m for _, src, m in logs if src == "module:P")


# -- failures --------------------------------------------------------------------------------


def run_failure(rig: ProcRig, name: str, code: str, rule: str) -> Finding:
    """Load ``code`` (it loads: the failure is in the process), start it and return the finding the
    shell reports for it; the module is then failed and a restart is planned."""
    seen: list[str] = []

    def sink(message: Any) -> None:
        seen.append(message.record["message"])

    sink_id = logger.add(sink, level="ERROR")
    try:
        loaded, findings = rig.load(name, code)
        assert loaded is not None, findings
        rig.host.start(loaded)
        rig.pump(lambda: loaded.state == "failed")
        rig.pump(lambda: any(rule in m or name in m for m in seen))
    finally:
        logger.remove(sink_id)
    text = " | ".join(seen)
    return Finding("", 0, 0, "error", rule, text)


def test_a_start_that_raises_fails_only_that_module_and_plans_the_restart(rig: ProcRig) -> None:
    bad = (
        "from tess_shell import Module\nclass Bad(Module):\n    def start(self):\n"
        "        raise ValueError('no clock')\n"
    )
    fine = started(rig)
    rig.wait_value("Good@u1", "time")
    f = run_failure(rig, "Bad", bad, "start")
    assert "Bad: start() raised ValueError: no clock" in f.message
    assert "Bad_Module.py:4" in f.message  # the line in the module's own file
    assert fine.state == "running"
    assert rig.host.restarts.tries("Bad") == 1, "the M7a back-off is planned"


def test_an_error_at_import_and_in_init_are_findings_with_their_line(rig: ProcRig) -> None:
    boom = (
        "from tess_shell import Module\n\nraise RuntimeError('at import')\nclass B(Module): pass\n"
    )
    f = run_failure(rig, "Imp", boom, "module-import")
    assert "importing the Python failed: RuntimeError: at import" in f.message
    assert "Imp_Module.py:3" in f.message
    init = (
        "from tess_shell import Module\nclass I(Module):\n    def __init__(self):\n"
        "        raise KeyError('x')\n"
    )
    f = run_failure(rig, "Ini", init, "module-init")
    assert "KeyError" in f.message and "Ini_Module.py:4" in f.message


def test_a_use_the_module_rejects_is_a_finding_and_the_module_still_starts(
    rig: ProcRig, logs: list[tuple[str, str, str]]
) -> None:
    code = GOOD + "\n    def validate_use(self, use):\n        raise ValueError('format: bad')\n"
    started(rig, code=code)
    assert rig.wait_value("Good@u1", "time") == "12:00"
    rig.pump(lambda: any("format: bad" in m for _, _, m in logs))


def test_stop_runs_the_modules_stop_and_the_process_ends(rig: ProcRig, tmp_path: Path) -> None:
    loaded = started(rig)
    rig.wait_value("Good@u1", "time")
    process = loaded.remote.process  # type: ignore[attr-defined]
    rig.host.stop_all()
    assert (tmp_path / "stopped.txt").read_text() == "stopped"
    assert process.poll() is not None, "stop_all waits for the processes to end"
    assert loaded.state == "stopped"


def test_an_action_the_files_text_does_not_show_is_learned_and_warned_about(
    rig: ProcRig, logs: list[tuple[str, str, str]]
) -> None:
    """An action added by ``setattr`` cannot be read from the syntax tree: the process says what it
    found, the shell warns (``module-actions``) and the action works from then on."""
    code = """
from tess_shell import Module, action

class Dyn(Module):
    pass

def late(self, event, n=1):
    self.ctx.send("late", n)

Dyn.late = action(late)
"""
    started(rig, "Dyn", code=code)
    rig.pump(lambda: any("module-actions" in m or "does not show: late" in m for _, _, m in logs))
    rig.host.dispatch(Handler("late", {"n": 5}, use="Dyn@u1"), "On_Click", None)
    assert rig.wait_value("Dyn@u1", "late") == 5


def test_a_request_made_while_the_shell_stops_is_answered_at_once_with_the_reason(
    rig: ProcRig, tmp_path: Path
) -> None:
    """The loop has ended when the shell stops the modules: a request that needs it (a ``loop``
    request) is refused with a reason and never waits for the 2 s of a timeout."""
    code = """
import os
from tess_shell import Module

class Bye(Module):
    def start(self):
        self.ctx.send("up", True)

    def stop(self):
        try:
            self.ctx.is_popup_open("menu")
        except Exception as exc:
            text = str(exc)
        else:
            text = "no error"
        with open(os.path.join(os.path.dirname(__file__), "bye.txt"), "w") as f:
            f.write(text)
"""
    started(rig, "Bye", code=code)
    rig.wait_value("Bye@u1", "up")
    began = time.monotonic()
    rig.host.stop_all()
    took = time.monotonic() - began
    bye = tmp_path / "bye.txt"
    deadline = time.monotonic() + 5  # the module process writes it as it stops
    while not bye.exists() and time.monotonic() < deadline:
        time.sleep(0.02)
    assert "the shell is stopping" in bye.read_text()
    assert took < 1.5, took
