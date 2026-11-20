"""A module host with module processes, for the tests (not collected by pytest): the real
``ModuleHost``, ``ValueStore`` and ``ModuleProcesses``, real child processes, and the main thread
standing in for the shell's loop (``pump`` runs what ``call_soon`` queued)."""

from __future__ import annotations

import queue
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from tess_shell.model.store import ValueStore
from tess_shell.modproc.supervisor import ModuleProcesses, Timing
from tess_shell.modules.host import LoadedModule, ModuleHost
from tess_shell.modules.ticks import TimeSource
from tess_shell.schema.findings import Finding
from tests.test_module_host import definition, use

FAST = Timing(stall=0.4, kill=1.2, poll=0.1, gate=3.0, stop=1.5)


class ProcRig:
    def __init__(
        self,
        tmp_path: Path,
        timing: Timing = FAST,
        enabled: bool = True,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.tmp = tmp_path
        self.store = ValueStore()
        self.ticks = TimeSource()
        self.host = ModuleHost(self.store, self.ticks, tmp_path, clock)
        self.queue: queue.SimpleQueue[Callable[[], None]] = queue.SimpleQueue()
        self.host.call_soon = self.queue.put
        self.store.attach_loop(self.queue.put)
        self.processes = ModuleProcesses(
            self.host, lambda path: False, timing=timing, enabled=enabled
        )
        self.host.processes = self.processes
        self.ticks.start(self.queue.put)

    def load(
        self, name: str, code: str | None, uses: int = 1, params: dict[str, Any] | None = None
    ) -> tuple[LoadedModule | None, list[Finding]]:
        py = self.tmp / f"{name}_Module.py"
        if code is not None:
            py.write_text(code)
        us = [use(name, i + 1) for i in range(uses)]
        for u in us:
            self.store.add_use(name, u.key)
        return self.host.load(definition(name), py, f"uid-{name}", us)

    def pump(
        self, until: Callable[[], bool], timeout: float = 20.0, restarts: bool = False
    ) -> None:
        """Run what the shell's loop would run until ``until()`` holds. ``restarts``: also start
        the modules whose back-off is over (the shell's time source does, each second)."""
        end = time.monotonic() + timeout
        while not until():
            if restarts:
                self.host.restart_due()
            left = end - time.monotonic()
            assert left > 0, "timed out waiting"
            try:
                self.queue.get(timeout=min(0.05, left))()
            except queue.Empty:
                pass

    def value(self, use_key: str, key: str) -> Any:
        return self.store.values.get(use_key, {}).get(key)

    def wait_value(self, use_key: str, key: str, expect: Any = None, timeout: float = 20.0) -> Any:
        self.pump(
            lambda: (
                self.value(use_key, key) is not None
                if expect is None
                else self.value(use_key, key) == expect
            ),
            timeout,
        )
        return self.value(use_key, key)

    def close(self) -> None:
        self.host.stop_all()
        for handle in list(self.processes.handles):
            handle.kill()
            handle.process.wait(5)
            handle.dispose()
        self.ticks.close()


def new_rig(tmp_path: Path) -> Iterator[ProcRig]:
    """The body of a ``rig`` fixture (a test module declares it with ``@pytest.fixture``)."""
    r = ProcRig(tmp_path)
    try:
        yield r
    finally:
        r.close()
