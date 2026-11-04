"""What a module author imports: ``from tess_shell import Module, action`` (Module Contract).

Standard library only. The shell sets ``self.ctx`` before :meth:`Module.start`; there are no
constructor arguments.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from tess_shell.modules.context import ModuleContext, UseRecord


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
    """Mark a method as callable from a shell file (events arrive with M3)."""
    fn.__tess_action__ = True  # type: ignore[attr-defined]
    return fn
