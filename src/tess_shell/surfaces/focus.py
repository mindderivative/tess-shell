"""The order of the shell's surfaces for keyboard focus (Focus and Keyboard > Tab Order).

The shell has one order for its surfaces, one for the blocks inside each surface (the binder's,
``View.reindex``). This is the first: the Bars, Panels, Frames and strips of a ``ShellDef`` by
``Tab_Index``, held in memory by the surface manager and made again when the shell is planned
(at load and at every hot reload). Nothing here is written to a file. Moving focus *between*
surfaces is the shortcut mode of M6c and M6d; M6a keeps the order as data, and says which surface
is next when the one that has focus closes.
"""

from __future__ import annotations

from collections.abc import Sequence

from tess_shell.binder.focus import tab_order
from tess_shell.schema.model import ShellDef


def surface_order(shell: ShellDef) -> list[str]:
    """The ``Name`` of every surface of ``shell`` in Tab order: ascending ``Tab_Index``, equal
    indices in document order, surfaces with no ``Tab_Index`` after all the others. A strip of a
    Frame is named ``<Frame>.<side>`` (``Screen_Frame.top``); a strip has a place of its own only
    when it holds children. A name that a Monitor block repeats for several outputs counts once."""
    names: list[str] = []
    indices: list[int | None] = []
    for monitor in shell.monitors:
        for surface in monitor.surfaces:
            names.append(surface.name)
            indices.append(surface.tab_index)
        for frame in monitor.frames:
            names.append(frame.name)
            indices.append(frame.tab_index)
            for side, edge in frame.edges.items():
                if edge.children:
                    names.append(f"{frame.name}.{side}")
                    indices.append(edge.tab_index)
    seen: set[str] = set()
    out: list[str] = []
    for pos in tab_order(indices):
        if names[pos] not in seen:
            seen.add(names[pos])
            out.append(names[pos])
    return out


def next_surface(order: Sequence[str], gone: str) -> str | None:
    """Where focus goes when the surface ``gone`` closes: the surface after it in ``order`` (the
    first one after the last), or ``None`` when no other surface is left (Failure Modes: Focus is
    on a surface that closes)."""
    if gone not in order:
        return order[0] if order else None
    rest = [*order[order.index(gone) + 1 :], *order[: order.index(gone)]]
    return rest[0] if rest else None
