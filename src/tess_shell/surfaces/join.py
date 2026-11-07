"""How a melded Panel's join animates: what the Frame calls, and the SMIL build (option a).

At rest a shown body is part of the ring's one contour. While it slides in or out, a *join* draws
the body with its fillets growing out of the band, on tre's own clock (no Python per frame); the
Frame draws the ring without the body and, when the join says so (``ghost``), at alpha 1 so the
ring still takes clicks. The way the join is drawn is chosen by ``Debug { Frame_Join: ... }`` in
``settings.tdl`` and is one of these modules, each small and with the same four calls:

* ``SMIL`` (here): the contour written at depth 0 and at full depth in an ``svg`` node, morphed by
  ``<animate attributeName="d">`` sampled at ``svg_time``.
* ``CONCAVE`` (``join_concave``): boxes with ``corner_style="concave"``, ``scale`` and
  ``transform_origin``.
* ``SHADER`` (``join_shader``): a shader node with ``sd_round_union``, its uniform animated by tre.
* ``STRUCTURE`` (``join_structure``): path ``data`` with ``morph="structure"``.
* ``PARAM`` (``join_param``): a path template with ``{expression}`` holes and ``animate_param``.

At the end of the animation the Frame draws the ring with the body in it again and calls
:meth:`Join.stop`, so every option ends in the same pixels: the ring's single contour.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar, Protocol

from tess_shell.surfaces.ring import Ring

if TYPE_CHECKING:
    from tess_re import LayerWindow
    from tess_re import Node as TreNode

RGBA = tuple[int, int, int, int]
Easing = tuple[float, float, float, float]
JOINS = ("SMIL", "CONCAVE", "SHADER", "STRUCTURE", "PARAM")
_EMPTY_SVG = '<svg xmlns="http://www.w3.org/2000/svg" width="1" height="1"/>'


@dataclass(frozen=True, slots=True)
class JoinRun:
    """What a join needs to start drawing one body's slide or fade."""

    kind: str  # SLIDE or FADE
    show: bool  # coming out (True) or going back (False)
    size: tuple[float, float]  # the painter, in logical pixels
    ring: Ring  # the ring with this body in it (the other bodies that animate are at 0)
    index: int  # this body's index in the ring's ``bodies`` and ``geometry``
    others: Mapping[int, float]  # the other bodies that animate, each at 0: they draw their own
    fill: RGBA | None  # the colours of the fill band and the inner border; None is not drawn
    border: RGBA | None
    opacity: float  # the Frame's own opacity

    def morph(self, s: float, radius: float | None = None) -> tuple[str, str]:
        """The fill band's and the inner border's path data with this body at ``s``."""
        assert self.ring.morph is not None
        grow = None if radius is None else {self.index: radius, **dict.fromkeys(self.others, 0.0)}
        return self.ring.morph({**self.others, self.index: s}, grow)


class Join(Protocol):
    """One way of drawing the join of a melded body while it animates."""

    # the Frame draws its ring nodes at alpha 1 (their hit shape only) while the join runs
    ghost: ClassVar[bool]

    def begin(self, run: JoinRun) -> bool:
        """Draw the start state (the body hidden for a show, fully out for a hide). ``False`` when
        this build cannot draw this body: the Frame then shows or hides it at once."""
        ...

    def play(self, show: bool, ms: int, easing: Easing, done: Callable[[], None]) -> None:
        """Start the animation to the end state, or turn round to it from where it is; ``done``
        is called once when it ends (not when it is replaced by another)."""
        ...

    def stop(self) -> None:
        """Draw nothing: the body is at rest (or gone), the ring draws it."""
        ...

    def destroy(self) -> None:
        """Remove the join's nodes."""
        ...


def make_join(name: str, painter: LayerWindow, z_index: int) -> Join:
    """The join named ``name`` (one of ``JOINS``), its nodes added to ``painter`` at ``z_index``."""
    if name == "CONCAVE":
        from tess_shell.surfaces.join_concave import ConcaveJoin

        return ConcaveJoin(painter, z_index)
    if name == "SHADER":
        from tess_shell.surfaces.join_shader import ShaderJoin

        return ShaderJoin(painter, z_index)
    if name == "STRUCTURE":
        from tess_shell.surfaces.join_structure import StructureJoin

        return StructureJoin(painter, z_index)
    if name == "PARAM":
        from tess_shell.surfaces.join_param import ParamJoin

        return ParamJoin(painter, z_index)
    return SmilJoin(painter, z_index)


def nodes_of(join: Join) -> list[TreNode]:
    """The nodes a join drew (for tests and the comparison script)."""
    found: list[TreNode] = getattr(join, "nodes", [])
    return found


class SmilJoin:
    """Option a: the ring's contour at depth 0 and at full depth in an ``svg`` node, morphed by an
    ``<animate attributeName="d">`` that tre samples at ``svg_time`` (eased by ``animate``). Every
    coordinate of the contour is linear in the depth, so the two documents have the same commands
    and each frame is their exact blend (see :mod:`tess_shell.surfaces.outline`). The svg takes no
    input (``hit_testable=False``: an svg has no ``hit_shape``), so the ring nodes keep the ring's
    click shape at alpha 1 (``ghost``)."""

    ghost: ClassVar[bool] = True

    def __init__(self, painter: LayerWindow, z_index: int) -> None:
        self.svg: TreNode = painter.create(
            "svg",
            svg=_EMPTY_SVG,
            position="absolute",
            left=0,
            top=0,
            width=1,
            height=1,
            visible=False,
            hit_testable=False,
            a11y_hidden=True,
            z_index=z_index,
        )
        painter.root.add_child(self.svg)
        self.nodes = [self.svg]
        self._kind = "SLIDE"
        self._opacity = 1.0

    def _document(self, run: JoinRun) -> str:
        end, start = run.morph(1.0), run.morph(0.0)
        w, h = run.size
        parts: list[str] = []
        for (d1, color), d0 in zip(
            ((end[0], run.fill), (end[1], run.border)), (start[0], start[1]), strict=True
        ):
            if not d1 or color is None:
                continue
            fill = f"rgb({color[0]},{color[1]},{color[2]})"
            alpha = f' fill-opacity="{color[3] / 255:.4f}"' if color[3] != 255 else ""
            if run.kind == "SLIDE":
                body = f'<animate attributeName="d" values="{d0};{d1}" dur="1s" fill="freeze"/>'
                parts.append(f'<path fill="{fill}"{alpha} d="{d0}">{body}</path>')
            else:
                parts.append(f'<path fill="{fill}"{alpha} d="{d1}"/>')
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:g}" height="{h:g}" '
            f'viewBox="0 0 {w:g} {h:g}">{"".join(parts)}</svg>'
        )

    def begin(self, run: JoinRun) -> bool:
        self._kind, self._opacity = run.kind, run.opacity
        props: dict[str, Any] = {
            "svg": self._document(run),
            "left": 0,
            "top": 0,
            "width": run.size[0],
            "height": run.size[1],
            "visible": True,
        }
        if run.kind == "SLIDE":
            props.update(svg_time=0.0 if run.show else 1.0, opacity=run.opacity)
        else:
            props["opacity"] = 0.0 if run.show else run.opacity
        self.svg.set(**props)
        return True

    def play(self, show: bool, ms: int, easing: Easing, done: Callable[[], None]) -> None:
        if self._kind == "SLIDE":
            self.svg.animate("svg_time", 1.0 if show else 0.0, ms, easing, done)
        else:
            self.svg.animate("opacity", self._opacity if show else 0.0, ms, easing, done)

    def stop(self) -> None:
        self.svg.set(visible=False, opacity=1.0)

    def destroy(self) -> None:
        self.svg.destroy()
