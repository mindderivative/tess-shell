"""The order of the shell's surfaces for keyboard focus (Focus and Keyboard > Tab Order).

The shell has one order for its surfaces, one for the blocks inside each surface (the binder's,
``View.reindex``). This is the first: the Bars, Panels, Frames and strips of a ``ShellDef`` by
``Focus_Order``, held in memory by the surface manager and made again when the shell is planned
(at load and at every hot reload). Nothing here is written to a file. Moving focus *between*
surfaces is the shortcut mode of M6c and M6d; M6a keeps the order as data, and says which surface
is next when the one that has focus closes.
"""

from __future__ import annotations

from collections.abc import Sequence

from tess_shell.schema.model import ShellDef, surface_names


def surface_order(shell: ShellDef) -> list[str]:
    """The ``Name`` of every surface of ``shell`` in the order focus moves between them: the names
    of ``Focus_Order`` that exist, in that order, then the others in the order of the file. A strip
    of a Frame is named ``<Frame>.<side>`` (``Screen_Frame.top``); a name that a Monitor block
    repeats for several outputs counts once."""
    names = surface_names(shell.monitors)
    first = [n for n in shell.focus_order if n in names]
    return [*first, *(n for n in names if n not in first)]


def next_surface(order: Sequence[str], gone: str) -> str | None:
    """Where focus goes when the surface ``gone`` closes: the surface after it in ``order`` (the
    first one after the last), or ``None`` when no other surface is left (Failure Modes: Focus is
    on a surface that closes)."""
    if gone not in order:
        return order[0] if order else None
    rest = [*order[order.index(gone) + 1 :], *order[: order.index(gone)]]
    return rest[0] if rest else None
