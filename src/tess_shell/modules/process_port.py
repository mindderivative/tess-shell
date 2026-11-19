"""What the module host needs of the module processes (``tess_shell.modproc``), as protocols, so the
host imports nothing of the package that runs them: the app makes the object and sets
``host.processes``, as it sets ``host.popups`` and the other ports.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any, Protocol

from tess_shell.schema.findings import Finding
from tess_shell.schema.model import ModuleDef


class RemoteModule(Protocol):
    """The process behind a module that runs in one (``instance._process`` of its stub)."""

    def when_imported(self, fn: Callable[[Finding | None], None]) -> None:
        """Call ``fn(None)`` on the loop thread when the process has imported the module's Python
        and made the instance, or ``fn(finding)`` when that failed. A process that ends before it
        answers is a failure."""

    def stop_then(self, fn: Callable[[], None]) -> None:
        """Ask the module to ``stop()`` and call ``fn()`` on the loop thread when it did (or after
        the contract's 3 s, when the process is killed). Never blocks."""

    def cancel(self) -> None:
        """End the process without telling anyone it failed (a reload that was replaced)."""


class ProcessPort(Protocol):
    def wants(self, py_path: Path) -> bool:
        """Does the module whose Python is ``py_path`` run in a process (a user module)?"""

    def stub(
        self, definition: ModuleDef, py_path: Path
    ) -> tuple[ModuleType | None, Finding | None]:
        """In place of importing ``py_path``: a module object holding a stub class for the file's
        ``Module`` class (nothing of the file runs), or the finding that says why not."""

    def status(self) -> list[dict[str, Any]]:
        """One record for each module process: ``module``, ``pid``, ``state`` and ``tries`` (the
        restarts used)."""

    def set_level(self, level: str) -> None:
        """The shell's log level changed: the module processes log at it too."""

    def wait_all(self) -> None:
        """The shell is stopping: wait for every module process to end (they were all told to
        stop and to leave; a module gets 3 s, the contract's limit, and they wait together), then
        kill the rest."""
