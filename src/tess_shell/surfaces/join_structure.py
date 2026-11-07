"""Option e: the join as path ``data`` morphed command by command (``morph="structure"``).

The ring's contour is written at depth 0 and at full depth with the same commands (see
:mod:`tess_shell.surfaces.outline`), so tre moves each number of one path to its partner: lines
stay lines, curves stay curves and every frame is the exact contour, not a resampled polygon.
``animate("data", ...)`` runs on tre's clock, eased like any property, and a turn-round retargets
from the numbers it is at. The path nodes are ``hit_shape="painted"``: what takes a click follows
the contour as it moves.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar

from tess_shell.surfaces.join import Easing, JoinRun

if TYPE_CHECKING:
    from tess_re import LayerWindow
    from tess_re import Node as TreNode


class StructureJoin:
    ghost: ClassVar[bool] = True

    def __init__(self, painter: LayerWindow, z_index: int) -> None:
        self.nodes: list[TreNode] = []
        for _ in range(2):  # the fill band, then the inner border
            node = painter.create(
                "path",
                data="M0,0 Z",
                morph="structure",
                hit_shape="painted",
                position="absolute",
                left=0,
                top=0,
                width=1,
                height=1,
                visible=False,
                a11y_hidden=True,
                z_index=z_index,
            )
            painter.root.add_child(node)
            self.nodes.append(node)
        self._ends: list[tuple[str, str]] = [("", "")] * 2  # per node: (collapsed, full) data
        self._kind = "SLIDE"
        self._opacity = 1.0

    def begin(self, run: JoinRun) -> bool:
        self._kind, self._opacity = run.kind, run.opacity
        collapsed, full = run.start(), run.morph(1.0)
        colours = (run.fill, run.border)
        self._ends = [(collapsed[i], full[i]) for i in range(2)]
        for node, (d0, d1), colour in zip(self.nodes, self._ends, colours, strict=True):
            if not d1 or colour is None:
                node.set(visible=False)
                continue
            props: dict[str, Any] = {
                "fill": colour,
                "width": run.size[0],
                "height": run.size[1],
                "visible": True,
            }
            if run.kind == "SLIDE":
                props.update(data=d0 if run.show else d1, opacity=run.opacity)
            else:
                props.update(data=d1, opacity=0.0 if run.show else run.opacity)
            node.set(**props)
        return True

    def play(self, show: bool, ms: int, easing: Easing, done: Callable[[], None]) -> None:
        first = True
        for node, (d0, d1) in zip(self.nodes, self._ends, strict=True):
            if not node.get("visible"):
                continue
            callback = done if first else None
            first = False
            if self._kind == "SLIDE":
                node.animate("data", d1 if show else d0, ms, easing, callback)
            else:
                node.animate("opacity", self._opacity if show else 0.0, ms, easing, callback)

    def stop(self) -> None:
        for node in self.nodes:
            node.set(visible=False, opacity=1.0)

    def destroy(self) -> None:
        for node in self.nodes:
            node.destroy()
