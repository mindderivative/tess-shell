"""What a module author imports: ``from tess_shell import Module, action`` (Module Contract).

Standard library only. The shell sets ``self.ctx`` before :meth:`Module.start`; there are no
constructor arguments.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tess_shell.modules.context import ModuleContext, UseRecord


@dataclass(frozen=True, slots=True)
class Event:
    """What an ``@action`` receives (Events and Actions > Python Contract): the event, where it
    happened and when, the handler's named arguments and, for a click, the pointer position."""

    name: str  # "click"
    use: str  # the key of the module use whose block raised it
    args: Mapping[str, object] = field(default_factory=dict)
    time: float = field(default_factory=time.monotonic)
    x: float | None = None  # pointer position in the window
    y: float | None = None
    button: str | None = None  # "primary", "secondary", ...


class Module:
    """Base class of a module's Python. One instance serves every use of the module."""

    ctx: ModuleContext

    def start(self) -> None:
        """Called once, after the model is built, on the loop thread. Return quickly."""

    def stop(self) -> None:
        """Called on quit or before a code reload. Stop threads and close connections."""

    def reload(self) -> None:
        """The module's TDL file changed and the Python did not; re-read ``self.ctx.config``."""

    def validate_use(self, use: UseRecord) -> None:
        """Raise ``ValueError`` with a message to reject a use's params."""

    def use_added(self, use: UseRecord) -> None:
        """A surface showing this module appeared."""

    def use_removed(self, use: UseRecord) -> None:
        """A surface showing this module went away."""


def action[F: Callable[..., Any]](fn: F) -> F:
    """Mark a method as an action: ``On_Click: name`` calls it with an :class:`Event`."""
    fn.__tess_action__ = True  # type: ignore[attr-defined]
    return fn
