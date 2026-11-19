"""The start of a shell with user modules in processes: the gate that ``READY=1`` waits behind (it
never holds the loop), safe start, the Debug setting that keeps user modules in the shell, and
``status``. The live shell is in ``tests/test_modproc_live.py``."""

from __future__ import annotations

import threading
import time
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from loguru import logger

from tess_shell.commands import ShellCommands
from tess_shell.modproc.supervisor import Timing
from tess_shell.module import Module
from tess_shell.modules.host import LoadedModule
from tests.modproc_rig import ProcRig, new_rig

HEAD = "import time\nfrom tess_shell import Module\n"
QUICK = HEAD + "class Q(Module):\n    def start(self):\n        self.ctx.send('up', True)\n"
SLOW_IMPORT = HEAD + "time.sleep(0.8)\n\nclass S(Module):\n    def start(self):\n        pass\n"
SLOW_START = HEAD + "class W(Module):\n    def start(self):\n        time.sleep(60)\n"
BAD_START = HEAD + "class B(Module):\n    def start(self):\n        raise RuntimeError('x')\n"


@pytest.fixture(name="rig")
def rig_fixture(tmp_path: Path) -> Iterator[ProcRig]:
    yield from new_rig(tmp_path)


def start(rig: ProcRig, name: str, code: str) -> LoadedModule:
    loaded, problems = rig.load(name, code)
    assert loaded is not None and problems == [], problems
    rig.host.start(loaded)
    return loaded


def test_with_no_module_process_the_gate_opens_at_once_where_it_is_called(rig: ProcRig) -> None:
    opened: list[int] = []
    rig.processes.when_settled(lambda: opened.append(1))
    assert opened == [1], "no waiting, no queue: the default shell's start is as it was"
    assert rig.queue.empty()


def test_the_gate_waits_for_the_module_while_the_loop_goes_on_running(rig: ProcRig) -> None:
    start(rig, "S", SLOW_IMPORT)
    opened: list[float] = []
    beats: list[float] = []
    stop = threading.Event()

    def beat() -> None:  # something that wants the loop, every 20 ms
        while not stop.is_set():
            rig.queue.put(lambda: beats.append(time.monotonic()))
            time.sleep(0.02)

    threading.Thread(target=beat, daemon=True).start()
    began = time.monotonic()
    rig.processes.when_settled(lambda: opened.append(time.monotonic()))
    assert not opened, "the module has not answered"
    rig.pump(lambda: bool(opened))
    stop.set()
    assert opened[0] - began >= 0.7, "READY waited for the module's import"
    assert opened[0] - began < rig.processes.timing.gate - 0.5, (
        "opened by the module, not the backstop"
    )
    assert sum(1 for b in beats if b < opened[0]) >= 10, "the loop ran while the gate waited"


def test_a_module_that_never_answers_opens_the_gate_after_the_backstop_with_a_warning(
    tmp_path: Path,
) -> None:
    seen: list[str] = []
    sink = logger.add(lambda m: seen.append(m.record["message"]), level="WARNING")
    rig = ProcRig(tmp_path, Timing(stall=50, kill=100, poll=1, gate=0.6, stop=1.5))
    try:
        start(rig, "W", SLOW_START)
        opened: list[float] = []
        began = time.monotonic()
        rig.processes.when_settled(lambda: opened.append(time.monotonic()))
        rig.pump(lambda: bool(opened))
        assert 0.5 <= opened[0] - began < 3
        assert any("module W is still starting; the shell is ready" in m for m in seen)
    finally:
        logger.remove(sink)
        rig.close()


def test_a_shell_that_stops_before_it_is_ready_never_says_ready(tmp_path: Path) -> None:
    rig = ProcRig(tmp_path, Timing(stall=50, kill=100, poll=1, gate=0.5, stop=1.0))
    try:
        start(rig, "W", SLOW_START)
        opened: list[int] = []
        rig.processes.when_settled(lambda: opened.append(1))
        rig.host.stop_all()
        time.sleep(0.8)  # past the backstop
        while not rig.queue.empty():
            rig.queue.get()()
        assert opened == []
    finally:
        rig.close()


def test_a_module_that_fails_to_start_opens_the_gate_at_the_failure(rig: ProcRig) -> None:
    loaded = start(rig, "B", BAD_START)
    opened: list[int] = []
    rig.processes.when_settled(lambda: opened.append(1))
    began = time.monotonic()
    rig.pump(lambda: bool(opened), timeout=10)
    assert loaded.state == "failed"
    assert time.monotonic() - began < rig.processes.timing.gate - 0.5, (
        "at the failure, not at the backstop"
    )


def test_safe_start_starts_no_process_for_a_user_module(rig: ProcRig) -> None:
    rig.host.safe_start = True
    rig.host.is_shipped = lambda path: False
    loaded, problems = rig.load("Q", QUICK)
    assert loaded is None and problems == []
    assert rig.host.safe_skipped == ["Q"] and not rig.processes.handles


def test_the_debug_setting_keeps_a_user_module_in_the_shell(tmp_path: Path) -> None:
    rig = ProcRig(tmp_path, enabled=False)
    try:
        loaded, problems = rig.load("Q", QUICK)
        assert loaded is not None and problems == []
        assert loaded.remote is None and isinstance(loaded.instance, Module)
        rig.host.start(loaded)
        rig.store.flush()
        assert rig.store.values["Q@u1"]["up"] is True, "it ran in this process"
        assert not rig.processes.handles
    finally:
        rig.close()


def test_a_shipped_module_is_never_given_a_process(tmp_path: Path) -> None:
    rig = ProcRig(tmp_path)
    rig.processes._is_shipped = lambda path: True
    try:
        loaded, _ = rig.load("Q", QUICK)
        assert loaded is not None and loaded.remote is None and not rig.processes.handles
    finally:
        rig.close()


def commands_for(rig: ProcRig) -> ShellCommands:
    manager: Any = SimpleNamespace(
        mode=SimpleNamespace(actions=lambda: {}), surface_infos=lambda: []
    )
    return ShellCommands(manager, rig.host, None, lambda: None, lambda: [])  # type: ignore[arg-type]


def test_status_lists_the_module_processes_and_a_shell_without_any_has_no_such_key(
    rig: ProcRig,
) -> None:
    commands = commands_for(rig)
    assert "module_processes" not in commands.status()
    loaded = start(rig, "Q", QUICK)
    rig.wait_value("Q@u1", "up")
    (entry,) = commands.status()["module_processes"]
    assert entry["module"] == "Q" and entry["state"] == "running" and entry["tries"] == 0
    assert entry["pid"] == loaded.remote.pid  # type: ignore[attr-defined]


def test_a_control_call_of_an_action_in_a_process_fails_as_a_command_error(rig: ProcRig) -> None:
    from tess_shell.services.control import CommandError

    code = (
        HEAD
        + "from tess_shell import action\nclass Z(Module):\n    @action\n"
        + "    def boom(self, event):\n        raise ValueError('nope')\n"
    )
    start(rig, "Z", code)
    future = commands_for(rig).call("Z", "boom", [])
    rig.pump(future.done)
    with pytest.raises(CommandError, match="Z.boom raised ValueError: nope"):
        future.result()


def test_status_says_starting_before_the_module_has_started(rig: ProcRig) -> None:
    start(rig, "S", SLOW_IMPORT)
    (entry,) = commands_for(rig).status()["module_processes"]
    assert entry["state"] == "starting"


# -- the Debug setting ------------------------------------------------------------------------


def settings_with(tmp_path: Path, body: str) -> Any:
    from tess_shell.config.settings import load_settings

    (tmp_path / "settings.tdl").write_text(f"---\nTDL: 0.2\nName: S\n---\nSettings {{ {body} }}\n")
    settings, findings = load_settings(tmp_path)
    return settings, findings


def test_user_modules_stay_in_a_process_unless_the_debug_setting_says_true(
    tmp_path: Path,
) -> None:
    settings, findings = settings_with(tmp_path, "")
    assert findings == [] and settings.debug.user_modules_in_process is False
    settings, findings = settings_with(tmp_path, "Debug { User_Modules_In_Process: true }")
    assert findings == [] and settings.debug.user_modules_in_process is True
    settings, findings = settings_with(tmp_path, "Debug { User_Modules_In_Process: sometimes }")
    assert settings is None and findings[0].severity == "error"


def test_the_schema_export_lists_the_setting_with_its_default() -> None:
    from tess_shell.schema.export import schema_dict

    key = schema_dict()["settings"]["Debug"]["User_Modules_In_Process"]
    assert key["default"] in (False, "false") and key["kind"] == "bool"
