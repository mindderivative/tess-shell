"""A user module's Python saved while the shell runs: the new process imports beside the old one,
the old one stops only when the new one imported, a bad new file keeps the old module running, and
nothing of the old process's memory comes over. Real processes; the main thread is the loop."""

from __future__ import annotations

import os
import signal
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tess_shell.binder.model import Handler
from tess_shell.modules.host import ModuleSource
from tess_shell.schema.findings import Finding
from tests.modproc_rig import ProcRig, new_rig
from tests.test_module_host import definition, use


def versioned(version: int, *, import_sleep: float = 0.0, extra: str = "", body: str = "") -> str:
    return f"""
import os, time
from tess_shell import Module, action

LOG = os.path.join(os.path.dirname(__file__), "events.log")

def note(text):
    with open(LOG, "a") as f:
        f.write(text + "\\n")

note("import {version}")
time.sleep({import_sleep})
{body}

class Ver(Module):
    def start(self):
        note("start {version}")
        self.state = {version}
        self.ctx.send("version", {version})
        self.ctx.send("pid", os.getpid())
        self.ctx.send("uses", sorted(self.ctx.uses))

    def stop(self):
        note("stop {version}")

    def reload(self):
        self.ctx.send("reloaded", True)

    def use_added(self, use):
        self.ctx.send("uses", sorted(self.ctx.uses))

    @action
    def who(self, event):
        self.ctx.send("who", {version})
{extra}
"""


class Reloads:
    def __init__(self, rig: ProcRig) -> None:
        self.rig = rig
        self.py = rig.tmp / "Ver_Module.py"
        self.log = rig.tmp / "events.log"
        self.uses = [use("Ver", 1)]
        rig.store.add_use("Ver", "Ver@u1")

    def events(self) -> list[str]:
        return self.log.read_text().split() if self.log.exists() else []

    def first(self, version: int = 1) -> Any:
        self.py.write_text(versioned(version))
        loaded, problems = self.rig.host.load(
            definition("Ver"), self.py, "uid-Ver", list(self.uses)
        )
        assert loaded is not None and problems == [], problems
        self.rig.host.start(loaded)
        self.rig.wait_value("Ver@u1", "version", version)
        return loaded

    def save(self, code: str, *, uses: list[Any] | None = None, tdl: bool = False) -> list[Finding]:
        """The module's file was saved: what ``Reloader`` does with ``host.sync``."""
        self.py.write_text(code)
        if uses is not None:
            self.uses = uses
        src = ModuleSource(
            definition("Ver"), self.py, "uid-Ver", frozenset({self.rig.tmp / "x.tdl"})
        )
        changed = {self.rig.tmp / "x.tdl"} if tdl else {self.py}
        return self.rig.host.sync({"Ver": src}, {"Ver": list(self.uses)}, changed)


@pytest.fixture(name="rig")
def rig_fixture(tmp_path: Path) -> Iterator[ProcRig]:
    yield from new_rig(tmp_path)


def test_the_new_process_imports_beside_the_old_one_and_the_old_stops_only_then(
    rig: ProcRig,
) -> None:
    r = Reloads(rig)
    old = r.first(1)
    old_pid = rig.value("Ver@u1", "pid")
    assert r.save(versioned(2, import_sleep=0.4)) == []
    assert rig.host.loaded["Ver"] is old, "the old module runs until the new one imported"
    rig.host.dispatch(Handler("who", use="Ver@u1"), "On_Click", None)
    assert rig.wait_value("Ver@u1", "who") == 1, "an event in that time goes to the old module"
    rig.wait_value("Ver@u1", "version", 2)
    assert r.events() == ["import", "1", "start", "1", "import", "2", "stop", "1", "start", "2"]
    assert rig.value("Ver@u1", "pid") != old_pid
    assert rig.host.loaded["Ver"] is not old and old.state == "stopped"
    assert old.remote.process.poll() is not None or old.remote.process.wait(5) is not None  # type: ignore[attr-defined]


def test_a_file_that_does_not_parse_is_refused_at_once_and_the_old_module_runs_on(
    rig: ProcRig,
) -> None:
    r = Reloads(rig)
    old = r.first(1)
    problems = r.save("from tess_shell import Module\nclass V(Module:\n")
    assert [p.rule for p in problems] == ["module-import"] and problems[0].line == 2
    assert rig.host.loaded["Ver"] is old and old.state == "running"
    assert r.events() == ["import", "1", "start", "1"], "no process was started for it"


def test_an_error_only_the_import_finds_keeps_the_old_module_and_is_reported_when_it_arrives(
    rig: ProcRig,
) -> None:
    from loguru import logger

    seen: list[str] = []
    sink = logger.add(lambda m: seen.append(m.record["message"]), level="ERROR")
    try:
        r = Reloads(rig)
        old = r.first(1)
        assert r.save(versioned(2, body="raise RuntimeError('broken at import')")) == []
        rig.pump(lambda: any("broken at import" in m for m in seen))
        assert any(
            "Ver_Module.py:" in m and "module-import" not in m or "importing" in m for m in seen
        )
    finally:
        logger.remove(sink)
    assert rig.host.loaded["Ver"] is old and old.state == "running", "the old module keeps running"
    assert "stop" not in r.events() and not rig.host._pending
    rig.host.dispatch(Handler("who", use="Ver@u1"), "On_Click", None)
    assert rig.wait_value("Ver@u1", "who") == 1


def test_a_second_save_replaces_the_one_that_has_not_finished(rig: ProcRig) -> None:
    r = Reloads(rig)
    r.first(1)
    r.save(versioned(2, import_sleep=1.5))
    first_process = rig.host._pending["Ver"].remote.process  # type: ignore[union-attr]
    r.save(versioned(3))
    rig.wait_value("Ver@u1", "version", 3)
    time.sleep(0.3)
    assert first_process.wait(5) is not None, "the process of the replaced save was ended"
    events = r.events()
    assert events[-2:] == ["start", "3"]
    assert ("start", "2") not in list(zip(events, events[1:], strict=False)), (
        "the replaced save started"
    )


def test_a_call_added_in_the_same_save_is_checked_against_the_new_file(rig: ProcRig) -> None:
    r = Reloads(rig)
    r.first(1)
    call = Handler("newone", module="Ver", use="X@1")
    assert [f.rule for f in rig.host.check_calls([call])] == ["unknown-action"]
    extra = "\n    @action\n    def newone(self, event):\n        self.ctx.send('newone', True)\n"
    r.save(versioned(2, extra=extra))
    assert rig.host.check_calls([call]) == [], "checked against the file being brought in"
    rig.wait_value("Ver@u1", "version", 2)
    rig.host.dispatch(Handler("newone", use="Ver@u1"), "On_Click", None)
    assert rig.wait_value("Ver@u1", "newone") is True


def test_the_uses_the_old_module_has_when_the_new_one_starts_are_given_to_it(rig: ProcRig) -> None:
    r = Reloads(rig)
    r.first(1)
    r.save(versioned(2, import_sleep=0.6))
    both = [use("Ver", 1), use("Ver", 2)]
    rig.store.add_use("Ver", "Ver@u2")
    rig.host.sync(
        {"Ver": ModuleSource(definition("Ver"), r.py, "uid-Ver", frozenset())}, {"Ver": both}, set()
    )
    rig.wait_value("Ver@u1", "version", 2)
    assert rig.wait_value("Ver@u1", "uses") == ["Ver@u1", "Ver@u2"]


def test_a_module_that_failed_is_replaced_by_a_save_at_once(rig: ProcRig) -> None:
    r = Reloads(rig)
    old = r.first(1)
    os.kill(old.remote.pid, signal.SIGKILL)  # type: ignore[attr-defined]
    rig.pump(lambda: old.state == "failed")
    r.save(versioned(2))
    rig.wait_value("Ver@u1", "version", 2)
    assert rig.host.loaded["Ver"].state == "running"
    assert rig.host.restarts.tries("Ver") == 0, "a reload gives a module its five tries again"


def test_a_change_to_the_layout_only_tells_the_module_to_reload_and_keeps_the_process(
    rig: ProcRig,
) -> None:
    r = Reloads(rig)
    old = r.first(1)
    pid = rig.value("Ver@u1", "pid")
    assert r.save(versioned(1), tdl=True) == []
    assert rig.wait_value("Ver@u1", "reloaded") is True
    assert rig.host.loaded["Ver"] is old and rig.value("Ver@u1", "pid") == pid


def test_a_late_failure_of_a_replaced_process_does_not_fail_the_module_that_replaced_it(
    rig: ProcRig,
) -> None:
    r = Reloads(rig)
    old = r.first(1)
    stale = old.remote
    r.save(versioned(2))
    rig.wait_value("Ver@u1", "version", 2)
    current = rig.host.loaded["Ver"]
    assert current is not old and current.state == "running"
    finding = Finding("x", 1, 1, "error", "module-start", "late")
    rig.host.process_failed("Ver", stale, finding)  # type: ignore[arg-type]
    rig.host.process_ended("Ver", stale, 1, "exit code 1")  # type: ignore[arg-type]
    assert current.state == "running" and rig.host.restarts.tries("Ver") == 0
