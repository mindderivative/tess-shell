"""Option f: the join as a path template with parameters (``animate_param``, tre 0.6.4).

The contour at depth 0 and at full depth have the same commands, and each number of the contour
is linear in two fractions: how far the body is out (``d``) and how far its fillets have grown
(``r``). So the whole contour is *one* path with a ``{expression}`` hole where a number moves,
``{c0 + d*c1 + r*c2}``, and the engine fills it in each tick as ``animate_param("d", ...)`` and
``animate_param("r", ...)`` run (no Python per frame). Every frame is the exact contour, and at the
ends it equals the plain data the ring draws at rest. ``animate_param`` has no ``on_complete``, so
the end is a timer of the painter.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any, ClassVar

from tess_shell.surfaces.join import Easing, JoinRun

if TYPE_CHECKING:
    from tess_re import LayerWindow
    from tess_re import Node as TreNode

_NUMBER = re.compile(r"-?\d+(?:\.\d+)?")


def _term(value: float, name: str) -> str:
    return f" {'-' if value < 0 else '+'} {name}*{_num(abs(value))}"


def _num(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def template(base: str, by_depth: str, by_radius: str) -> str:
    """The path of ``base`` (every parameter 0) with each number that moves written as an
    expression in ``d`` and ``r``: ``by_depth`` and ``by_radius`` are the same path with the depth
    or the radius fraction at 1."""
    a, b, c = (_NUMBER.findall(text) for text in (base, by_depth, by_radius))
    assert len(a) == len(b) == len(c)
    holes = iter(zip(a, b, c, strict=True))

    def fill(_: re.Match[str]) -> str:
        v0, v1, v2 = (float(x) for x in next(holes))
        dd, dr = v1 - v0, v2 - v0
        if abs(dd) < 5e-4 and abs(dr) < 5e-4:
            return _num(v0)
        expr = _num(v0)
        if abs(dd) >= 5e-4:
            expr += _term(dd, "d")
        if abs(dr) >= 5e-4:
            expr += _term(dr, "r")
        return "{" + expr + "}"

    return _NUMBER.sub(fill, base)


class ParamJoin:
    ghost: ClassVar[bool] = True

    def __init__(self, painter: LayerWindow, z_index: int) -> None:
        self._painter = painter
        self.nodes: list[TreNode] = []
        for _ in range(2):  # the fill band, then the inner border
            node = painter.create(
                "path",
                data="M0,0 Z",
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
        self._templated = [False, False]  # whether a node holds a template (else plain data)
        self._full = ["", ""]  # the plain data at full depth
        self._kind = "SLIDE"
        self._opacity = 1.0
        self._timer: Any = None

    def begin(self, run: JoinRun) -> bool:
        self._kind, self._opacity = run.kind, run.opacity
        if run.low is not None:
            # a peek blends two whole contours (the tab's and the body's, each with its own
            # fillets): the fillets are not a separate fraction
            base, deep, grown = run.low, run.morph(1.0), run.low
        else:
            base, deep, grown = run.morph(0.0, 0.0), run.morph(1.0, 0.0), run.morph(0.0, 1.0)
        full = run.morph(1.0)
        colours = (run.fill, run.border)
        for i, node in enumerate(self.nodes):
            self._full[i] = full[i]
            if not full[i] or colours[i] is None:
                node.set(visible=False)
                self._templated[i] = False
                continue
            props: dict[str, Any] = {
                "fill": colours[i],
                "width": run.size[0],
                "height": run.size[1],
                "visible": True,
            }
            if run.kind == "SLIDE":
                start = 0.0 if run.show else 1.0
                props.update(
                    data=template(base[i], deep[i], grown[i]),
                    params={"d": start, "r": start},
                    opacity=run.opacity,
                )
                self._templated[i] = True
            else:
                props.update(data=full[i], opacity=0.0 if run.show else run.opacity)
                self._templated[i] = False
            node.set(**props)
        return True

    def play(self, show: bool, ms: int, easing: Easing, done: Callable[[], None]) -> None:
        if self._timer is not None:
            self._timer.cancel()
        for i, node in enumerate(self.nodes):
            if not node.get("visible"):
                continue
            if self._templated[i]:
                target = 1.0 if show else 0.0
                node.animate_param("d", target, ms, easing)
                node.animate_param("r", target, ms, easing)
            else:
                node.animate("opacity", self._opacity if show else 0.0, ms, easing)
        self._timer = self._painter.after(ms, done)

    def seek(self, p: float) -> None:
        for i, node in enumerate(self.nodes):
            if node.get("visible") and self._templated[i]:
                node.set(params={"d": p, "r": p})

    def stop(self) -> None:
        if self._timer is not None:
            self._timer.cancel()
            self._timer = None
        for node in self.nodes:
            node.set(visible=False, opacity=1.0)

    def destroy(self) -> None:
        self.stop()
        for node in self.nodes:
            node.destroy()
