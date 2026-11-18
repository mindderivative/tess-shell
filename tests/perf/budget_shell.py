"""``tesserae-shell`` with a stopwatch on every callback the loop runs, for the budget harness.

    TESS_BUDGET_CALLBACKS_OUT=/path/file.json python -m tests.perf.budget_shell run --config-dir D

It is the shell, unchanged, started through the same ``tess_shell.cli.main``; before it starts,
two run-time patches (this process only, nothing in ``src/``) record, with ``time.monotonic()``:

* every module callback the loop runs: ``CallbackRecord.leave`` notes the module, the entry point,
  the time it began and how long it ran (the record the shell keeps for its watchdog, so this
  reads exactly the callbacks that Performance Budgets calls "a module callback on the loop");
* every control command the loop runs (``ShellCommands.surface``, ``call``, ``status``, ``press``),
  under the module name ``command``.

At exit the list is written to the file as JSON: ``[[module, entry, began, seconds], ...]``. A
stopwatch costs a list append (well under a microsecond), against a 4 ms budget. Not collected by
pytest.
"""

from __future__ import annotations

import atexit
import functools
import json
import os
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

OUT = "TESS_BUDGET_CALLBACKS_OUT"

samples: list[tuple[str, str, float, float]] = []


def install() -> None:
    from tess_shell.commands import ShellCommands
    from tess_shell.modules.running import CallbackRecord

    clock = time.monotonic
    leave = CallbackRecord.leave

    def timed_leave(self: CallbackRecord, previous: Any) -> None:
        current = self._current
        if current is not None:
            samples.append((current[0], current[1], current[2], clock() - current[2]))
        leave(self, previous)

    CallbackRecord.leave = timed_leave  # type: ignore[method-assign]

    def wrap(name: str, method: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(method)
        def timed(*args: Any, **kwargs: Any) -> Any:
            began = clock()
            try:
                return method(*args, **kwargs)
            finally:
                samples.append(("command", name, began, clock() - began))

        return timed

    for name in ("surface", "call", "status", "press"):
        setattr(ShellCommands, name, wrap(name, getattr(ShellCommands, name)))


def dump() -> None:
    target = os.environ.get(OUT)
    if target:
        Path(target).write_text(json.dumps(samples))


def main() -> int:
    install()
    atexit.register(dump)
    from tess_shell.cli import main as cli_main

    return cli_main()


if __name__ == "__main__":
    raise SystemExit(main())
