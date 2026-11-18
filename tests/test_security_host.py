"""The module host's controls of the Security Model: the module is imported by path, the callback
that is running is recorded and named, a callback over its budget is logged and a flooding module is
warned about once a minute, a failed module comes back with a back-off and gives up after five
tries, and a module with many threads of its own is warned about once.

Time is injected: the host's clock is a fake the tests move, the restart waits on the (unstarted)
time source whose callbacks the tests call, and nothing sleeps."""

from __future__ import annotations

import sys
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest
from loguru import logger

from tess_shell.binder.model import Handler
from tess_shell.logging import finding_sinks
from tess_shell.modules.host import LoadedModule, ModuleHost, ModuleSource
from tess_shell.modules.supervise import MANY_THREADS, MAX_TRIES, delay_before
from tess_shell.schema.findings import Finding
from tests.test_module_host import Rig as BaseRig
from tests.test_module_host import definition, use


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


# what the test modules below reach through ``from tests.test_security_host import ...``
CLOCK = FakeClock()
ENTERED = threading.Event()
GATE = threading.Event()
STOP = threading.Event()


@dataclass
class Heard:
    lines: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    def rule(self, rule: str) -> list[Finding]:
        return [f for f in self.findings if f.rule == rule]


@pytest.fixture
def heard() -> Iterator[Heard]:
    got = Heard()
    sink = logger.add(lambda message: got.lines.append(str(message)), level="DEBUG")
    finding_sinks.append(got.findings.append)
    yield got
    finding_sinks.remove(got.findings.append)
    logger.remove(sink)


@pytest.fixture(autouse=True)
def fresh_clock() -> Iterator[FakeClock]:
    CLOCK.now = 1000.0
    ENTERED.clear()
    GATE.clear()
    STOP.clear()
    yield CLOCK
    GATE.set()  # never leave a worker of one test waiting for the next
    STOP.set()


class Rig(BaseRig):
    """The module host of ``test_module_host`` with the fake clock; modules live in their own
    ``Modules/<Name>/`` folder as a user's do."""

    def __init__(self, tmp_path: Path) -> None:
        super().__init__(tmp_path)
        self.host = ModuleHost(self.store, self.ticks, tmp_path, clock=CLOCK)

    def add(self, name: str, code: str, uses: int = 1) -> LoadedModule:
        folder = self.tmp / "Modules" / name
        folder.mkdir(parents=True, exist_ok=True)
        py = folder / f"{name}_Module.py"
        py.write_text(code)
        us = [use(name, i + 1) for i in range(uses)]
        for u in us:
            self.store.add_use(name, u.key)
        loaded, findings = self.host.load(definition(name), py, f"uid-{name}", us)
        assert loaded is not None, findings
        return loaded

    def source(self, loaded: LoadedModule) -> ModuleSource:
        """What a reload hands the host for ``loaded``: the same files, read again."""
        return ModuleSource(
            loaded.definition, loaded.py_path, loaded.ctx.uid, frozenset({loaded.py_path})
        )

    def click(self, name: str, action: str, n: int = 1) -> None:
        for _ in range(n):
            self.host.dispatch(Handler(action, use=f"{name}@u1"), "On_Click", object())


# -- control 1: loaded by path from the module's folder ------------------------------------------

SHADOW = """
from tess_shell import Module
import json, sys

class Shadow(Module):
    def start(self):
        self.json_file = json.__file__
        self.path = list(sys.path)
"""


def test_a_module_is_imported_by_file_path_and_its_folder_is_never_on_sys_path(
    tmp_path: Path,
) -> None:
    """A file named like a standard-library module beside a module's Python would replace that
    library for the module if its folder (or the configuration folder) were on ``sys.path``."""
    before = list(sys.path)
    rig = Rig(tmp_path)
    folder = tmp_path / "Modules" / "Shadow"
    folder.mkdir(parents=True)
    (folder / "json.py").write_text("raise RuntimeError('this file must never be imported')\n")
    (tmp_path / "json.py").write_text("raise RuntimeError('nor this one')\n")
    loaded = rig.add("Shadow", SHADOW)
    assert rig.host.start(loaded) == [] and loaded.state == "running"
    assert loaded.instance.json_file != str(folder / "json.py")  # type: ignore[attr-defined]
    assert sys.path == before and loaded.instance.path == before  # type: ignore[attr-defined]
    assert not [p for p in sys.path if str(tmp_path) in p]
    imported = sys.modules["tess_shell_user_modules.Shadow"]
    assert imported.__file__ == str(folder / "Shadow_Module.py")  # by its own path
    assert loaded.py_path == folder / "Shadow_Module.py"


# -- control 5: the running callback -------------------------------------------------------------

SLEEPER = """
from tess_shell import Module, action
from tests.test_security_host import ENTERED, GATE

class Sleeper(Module):
    @action
    def nap(self, event):
        ENTERED.set()
        GATE.wait(10)        # a callback that does not return

    def start(self):
        self.ctx.on_tick("second", self.doze)

    def doze(self):
        ENTERED.set()
        GATE.wait(10)
"""


def test_a_module_that_sleeps_in_a_callback_is_named_by_the_record_from_another_thread(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path)
    loaded = rig.add("Sleeper", SLEEPER)
    rig.host.start(loaded)
    assert rig.host.callbacks.running() is None  # idle: nothing is running
    worker = threading.Thread(target=rig.click, args=("Sleeper", "nap"))
    worker.start()
    assert ENTERED.wait(10)
    seen = rig.host.callbacks.running()  # read from this thread, the loop's being stuck in nap
    assert seen is not None
    assert (seen.module, seen.entry) == ("Sleeper", "nap")
    assert seen.started == CLOCK.now  # when it began, on the host's clock
    GATE.set()
    worker.join(10)
    assert not worker.is_alive() and rig.host.callbacks.running() is None


def test_a_tick_callback_is_named_by_its_own_name(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    loaded = rig.add("Sleeper", SLEEPER)
    rig.host.start(loaded)
    (sub,) = rig.ticks._subs  # what the loop runs each second
    worker = threading.Thread(target=sub.fn)
    worker.start()
    assert ENTERED.wait(10)
    seen = rig.host.callbacks.running()
    assert seen is not None and (seen.module, seen.entry) == ("Sleeper", "Sleeper.doze")
    GATE.set()
    worker.join(10)
    assert rig.host.callbacks.running() is None


def test_a_callback_that_raises_leaves_nothing_running(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    code = (
        "from tess_shell import Module, action\n"
        "class Bad(Module):\n"
        "    @action\n"
        "    def boom(self, event):\n"
        "        raise ValueError('x')\n"
    )
    rig.host.start(rig.add("Bad", code))
    rig.click("Bad", "boom")
    assert rig.host.callbacks.running() is None


def test_a_callback_inside_a_callback_gives_the_outer_one_back(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    record = rig.host.callbacks
    seen = []

    def inner() -> None:
        seen.append(record.running())

    def outer() -> None:
        record.run("B", "inner", inner)
        seen.append(record.running())

    record.run("A", "outer", outer)
    assert [(r.module, r.entry) for r in seen if r] == [("B", "inner"), ("A", "outer")]
    assert record.running() is None


# -- control 5: over the budget, and the slow-module warning -------------------------------------

BUSY = """
from tess_shell import Module, action
from tests.test_security_host import CLOCK

class Busy(Module):
    @action
    def work(self, event):
        CLOCK.advance(0.005)      # 5 ms on the loop: over the 4 ms budget

    @action
    def other(self, event):
        CLOCK.advance(0.005)

    @action
    def quick(self, event):
        CLOCK.advance(0.003)      # inside the budget
"""


def test_a_callback_over_four_milliseconds_is_logged_at_debug_with_the_module_name(
    tmp_path: Path, heard: Heard
) -> None:
    rig = Rig(tmp_path)
    rig.host.start(rig.add("Busy", BUSY))
    rig.click("Busy", "quick")
    assert not [ln for ln in heard.lines if "took" in ln and "Busy" in ln]
    rig.click("Busy", "work")
    (line,) = [ln for ln in heard.lines if "module Busy: work took" in ln]
    assert line.lstrip().startswith("DEBUG") or "DEBUG" in line
    assert "5.0 ms" in line and "budget 4 ms" in line


def test_more_than_a_hundred_slow_callbacks_in_a_minute_warn_once_naming_the_entry_point(
    tmp_path: Path, heard: Heard
) -> None:
    rig = Rig(tmp_path)
    rig.host.start(rig.add("Busy", BUSY))
    rig.click("Busy", "work", 60)
    rig.click("Busy", "other", 40)
    assert heard.rule("slow-module") == []  # a hundred is not more than a hundred
    rig.click("Busy", "work")  # the 101st
    (warning,) = heard.rule("slow-module")
    assert warning.severity == "warning" and getattr(warning, "module", "") == "Busy"
    assert "Busy" in warning.message and "100" in warning.message and "work" in warning.message
    assert "other" not in warning.message  # the entry point most often over its budget
    rig.click("Busy", "work", 150)  # still the same minute
    assert len(heard.rule("slow-module")) == 1
    CLOCK.advance(61)  # a minute later the flood is still on: one more
    rig.click("Busy", "other", 101)
    again = heard.rule("slow-module")
    assert len(again) == 2 and "other" in again[1].message


def test_slow_callbacks_spread_over_minutes_or_inside_the_budget_do_not_warn(
    tmp_path: Path, heard: Heard
) -> None:
    rig = Rig(tmp_path)
    rig.host.start(rig.add("Busy", BUSY))
    for _ in range(300):  # five slow callbacks a second: 100 a minute at the most... then less
        rig.click("Busy", "work")
        CLOCK.advance(1.0)
    rig.click("Busy", "quick", 500)
    assert heard.rule("slow-module") == []


def test_one_module_flooding_does_not_blame_another(tmp_path: Path, heard: Heard) -> None:
    rig = Rig(tmp_path)
    rig.host.start(rig.add("Busy", BUSY))
    rig.host.start(rig.add("Calm", BUSY.replace("class Busy", "class Calm")))
    for _ in range(60):
        rig.click("Busy", "work")
        rig.click("Calm", "work")
    assert heard.rule("slow-module") == []  # 60 each, 120 together
    rig.click("Busy", "work", 41)
    assert [getattr(f, "module", "") for f in heard.rule("slow-module")] == ["Busy"]


# -- control 6: a failed module restarts with a back-off -----------------------------------------

FLAKY = """
from pathlib import Path
from tess_shell import Module

COUNT = Path({count!r})
FAIL_UNTIL = {fail_until}

class Flaky(Module):
    def start(self):
        n = int(COUNT.read_text()) + 1 if COUNT.exists() else 1
        COUNT.write_text(str(n))
        if n < FAIL_UNTIL:
            raise RuntimeError(f"not yet ({{n}})")
        self.ctx.send("time", f"up after {{n}}")

    def use_added(self, use):
        if use.key.endswith("u9"):
            raise RuntimeError("late")
"""


def flaky(rig: Rig, fail_until: int) -> tuple[Path, LoadedModule]:
    count = rig.tmp / "count.txt"
    loaded = rig.add("Flaky", FLAKY.format(count=str(count), fail_until=fail_until))
    return count, loaded


def starts(count: Path) -> int:
    return int(count.read_text()) if count.exists() else 0


def tick(rig: Rig) -> None:
    """What the loop does each second while a restart waits."""
    for sub in list(rig.ticks._subs):
        sub.fn()


def test_a_failed_module_alone_is_marked_failed_and_the_others_run_on(
    tmp_path: Path, heard: Heard
) -> None:
    rig = Rig(tmp_path)
    count, bad = flaky(rig, fail_until=99)
    good = rig.add("Busy", BUSY)
    findings = rig.host.start_all()
    assert [f.rule for f in findings] == ["module-start"]
    assert "UID uid-Flaky" in findings[0].hint  # logged with the module's name and UID
    assert bad.state == "failed" and good.state == "running"
    rig.click("Busy", "quick")  # the others are still served
    assert starts(count) == 1


def test_the_back_off_is_one_two_four_eight_sixteen_seconds_then_it_gives_up(
    tmp_path: Path, heard: Heard
) -> None:
    rig = Rig(tmp_path)
    count, bad = flaky(rig, fail_until=99)
    rig.host.start_all()
    assert [delay_before(n) for n in range(1, 8)] == [1, 2, 4, 8, 16, 32, 60]  # capped at a minute
    assert MAX_TRIES == 5
    assert len(rig.ticks._subs) == 1  # one wait on the time source, while a restart is due
    for tries, wait in enumerate((1, 2, 4, 8, 16), start=1):
        CLOCK.advance(wait - 0.5)
        tick(rig)
        assert starts(count) == tries, f"restarted before {wait} s"
        CLOCK.advance(0.5)
        tick(rig)
        assert starts(count) == tries + 1
    assert starts(count) == 1 + MAX_TRIES  # the first start and five restarts
    assert rig.ticks._subs == []  # nothing waits any more
    CLOCK.advance(10_000)
    tick(rig)
    assert starts(count) == 1 + MAX_TRIES and rig.host.loaded["Flaky"].state == "failed"
    assert any("stays failed until a reload" in ln for ln in heard.lines)
    assert any("restart 1 of 5 in 1 s" in ln for ln in heard.lines)


def test_a_restart_that_works_brings_the_module_back_and_stops_the_waiting(
    tmp_path: Path, heard: Heard
) -> None:
    rig = Rig(tmp_path)
    count, _ = flaky(rig, fail_until=3)  # the third start is the first that works
    rig.host.start_all()
    CLOCK.advance(1)
    tick(rig)
    CLOCK.advance(2)
    tick(rig)
    up = rig.host.loaded["Flaky"]
    assert up.state == "running" and starts(count) == 3
    assert rig.ticks._subs == []
    rig.store.flush()
    assert rig.store.values["Flaky@u1"]["time"] == "up after 3"
    CLOCK.advance(10_000)
    tick(rig)
    assert starts(count) == 3  # nothing starts it again


def test_a_reload_gives_a_module_that_gave_up_five_new_tries(tmp_path: Path) -> None:
    rig = Rig(tmp_path)
    count, bad = flaky(rig, fail_until=99)
    rig.host.start_all()
    for wait in (1, 2, 4, 8, 16):
        CLOCK.advance(wait)
        tick(rig)
    assert starts(count) == 6 and rig.ticks._subs == []
    src = rig.source(bad)
    findings = rig.host.sync({"Flaky": src}, {"Flaky": bad.uses}, {src.py_path})
    assert [f.rule for f in findings] == ["module-start"]  # a reload tries it again
    assert starts(count) == 7
    CLOCK.advance(1)  # and its back-off starts from one second again
    tick(rig)
    assert starts(count) == 8


def test_a_module_that_ran_for_a_minute_and_fails_again_starts_a_new_run_of_tries(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path)
    count, _ = flaky(rig, fail_until=2)
    rig.host.start_all()
    CLOCK.advance(1)
    tick(rig)  # the first restart works
    assert rig.host.loaded["Flaky"].state == "running" and rig.ticks._subs == []
    CLOCK.advance(120)  # a quiet two minutes, then a new use whose use_added raises
    rig.host.dynamic([use("Flaky", 9)], [])
    assert rig.host.loaded["Flaky"].state == "failed"
    CLOCK.advance(1)
    tick(rig)  # a wait of one second again, not two: the count started over
    assert rig.host.loaded["Flaky"].state == "running" and starts(count) == 3


# -- control 6: many threads ---------------------------------------------------------------------

THREADS = """
import threading
from tess_shell import Module
from tests.test_security_host import STOP

def worker():
    STOP.wait(30)

class Threads(Module):
    COUNT = {count}

    def start(self):
        self.pool = [threading.Thread(target=worker, daemon=True) for _ in range(self.COUNT)]
        for thread in self.pool:
            thread.start()
"""


def a_minute_later(rig: Rig) -> None:
    """The first callback after a minute runs the check that needs no timer."""
    CLOCK.advance(61)
    rig.host.callbacks.run("Other", "anything", lambda: None)


def test_a_module_with_more_than_sixteen_threads_of_its_own_is_warned_about_once(
    tmp_path: Path, heard: Heard
) -> None:
    rig = Rig(tmp_path)
    rig.host.start(rig.add("Threads", THREADS.format(count=MANY_THREADS + 1)))
    stranger = [threading.Thread(target=STOP.wait, args=(30,), daemon=True) for _ in range(40)]
    for thread in stranger:  # threads that run no module's code belong to no module
        thread.start()
    a_minute_later(rig)
    (warning,) = heard.rule("many-threads")
    assert warning.severity == "warning" and getattr(warning, "module", "") == "Threads"
    assert "Threads" in warning.message and "17 live threads" in warning.message
    a_minute_later(rig)
    a_minute_later(rig)
    assert len(heard.rule("many-threads")) == 1  # once


def test_sixteen_threads_are_not_many_and_another_modules_threads_are_not_counted(
    tmp_path: Path, heard: Heard
) -> None:
    rig = Rig(tmp_path)
    rig.host.start(rig.add("Threads", THREADS.format(count=MANY_THREADS)))
    rig.host.start(rig.add("More", THREADS.format(count=10).replace("Threads", "More")))
    a_minute_later(rig)
    assert heard.rule("many-threads") == []  # 16 and 10; together 26, but not one module's


def test_a_reload_of_the_module_may_warn_again(tmp_path: Path, heard: Heard) -> None:
    rig = Rig(tmp_path)
    loaded = rig.add("Threads", THREADS.format(count=MANY_THREADS + 1))
    rig.host.start(loaded)
    a_minute_later(rig)
    assert len(heard.rule("many-threads")) == 1
    src = rig.source(loaded)
    rig.host.sync({"Threads": src}, {"Threads": loaded.uses}, {src.py_path})
    a_minute_later(rig)
    assert len(heard.rule("many-threads")) == 2  # the new instance started its own threads
