"""What the shell does for its control interface (``services/control.py``): the loop-side half.

``ShellCommands`` holds the manager, the module host and the reloader. ``status``, ``surface``,
``close_popup``, ``call`` and ``set_log_level`` run on the loop thread (the interface queues them
with ``call_soon``); ``reload_validate`` runs on a worker thread, ``quit`` on any.
"""

from __future__ import annotations

import difflib
import sys
from collections.abc import Callable
from typing import Any

from tess_shell import __version__
from tess_shell.config.settings import LEVELS
from tess_shell.logging import set_level
from tess_shell.modules.host import ActionError, ModuleHost
from tess_shell.reloader import Outcome, Reloader
from tess_shell.services.control import CommandError
from tess_shell.surfaces.manager import SurfaceManager


def versions() -> dict[str, str]:
    """The versions of the shell and what it stands on (the ``version`` command's keys)."""
    from importlib.metadata import version

    import tess_dl
    import tess_el

    return {
        "shell": __version__,
        "tess_re": version("tesserae-engine"),
        "tess_el": tess_el.__version__,
        "tess_dl": tess_dl.__version__,
        "python": ".".join(map(str, sys.version_info[:3])),
    }


class ShellCommands:
    """The shell's side of the control interface."""

    def __init__(
        self,
        manager: SurfaceManager,
        host: ModuleHost,
        reloader: Reloader,
        stop: Callable[[], None],
        errors: Callable[[], list[dict[str, Any]]],
    ) -> None:
        self.manager = manager
        self.host = host
        self.reloader = reloader
        self._stop = stop
        self._errors = errors

    # -- loop thread ------------------------------------------------------------------------------

    def status(self) -> dict[str, Any]:
        """The state of the shell: versions, monitors, surfaces, module names, last errors. Names,
        kinds and flags only: never the value of a param and never a line of the log."""
        infos = self.manager.surface_infos()
        monitors: dict[tuple[str, str], None] = {}
        for i in infos:
            monitors[(i.monitor, i.output)] = None
        return {
            "version": versions(),
            "monitors": [{"name": m, "output": o} for m, o in monitors],
            "surfaces": [
                {"name": i.name, "kind": i.kind, "shown": i.shown, "output": i.output}
                for i in infos
            ],
            "modules": sorted(self.host.loaded),
            "errors": self._errors(),
        }

    def surface(self, action: str, name: str) -> tuple[bool, str]:
        return self.manager.control_surface(action, name)

    def close_popup(self) -> None:
        self.manager.popups.close_named()

    def call(self, module: str, action: str, values: list[Any]) -> Any:
        try:
            return self.host.call_action(module, action, values)
        except ActionError as exc:
            raise CommandError(str(exc), "ActionFailed") from exc

    def set_log_level(self, level: str) -> None:
        name = level.upper()
        if name not in LEVELS:
            close = difflib.get_close_matches(name, LEVELS, n=2)
            hint = f" (did you mean {' or '.join(close)}?)" if close else ""
            raise CommandError(
                f"no log level {level}{hint}; the levels: {', '.join(LEVELS)}", "BadArguments"
            )
        if not set_level(name):
            raise CommandError("logging is not configured", "Failed")

    def reload_apply(self, ticket: Any) -> tuple[bool, str]:
        outcome = self.reloader.apply_for_control(ticket)
        return outcome.ok, outcome.message

    # -- any other thread -------------------------------------------------------------------------

    def reload_validate(self) -> Any:
        """Check the files (this blocks on them). A refusal is ``(False, errors)``; else the
        ticket ``reload_apply`` applies."""
        got = self.reloader.validate_for_control()
        if isinstance(got, Outcome):
            return (got.ok, got.message)
        return got

    def quit(self) -> None:
        self._stop()
