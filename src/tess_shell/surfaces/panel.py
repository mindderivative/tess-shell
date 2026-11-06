"""The Panel geometry: TDL placement keys to tre's ``anchor``, ``size`` and ``margin``
(Panel > Position and Attachment).

Pure functions over :mod:`tess_shell.binder.model`. A Panel is anchored (to an edge or a corner,
placed by ``Inset``) or floating (no anchor: the compositor centres it). A shadow makes the
surface larger than the body by a transparent margin (ADR-0010): the body keeps the place the
``Inset`` gives it, so each anchored side's margin shrinks by the bleed there.
"""

from __future__ import annotations

from dataclasses import dataclass

from tess_shell.binder.model import Length, Percent, Value
from tess_shell.surfaces.bar import Geometry, ZeroSize

_ORDER = ("top", "right", "bottom", "left")  # tre's margin order


@dataclass(frozen=True, slots=True)
class PanelSpec:
    anchor: tuple[str, ...]  # TOP, BOTTOM, LEFT, RIGHT
    inset: tuple[float, float, float, float]  # left, top, right, bottom
    width: Value
    height: Value
    bleed: tuple[int, int, int, int] = (0, 0, 0, 0)  # top, right, bottom, left


def _size(value: Value, output: int) -> float:
    if isinstance(value, Length):
        return value.px
    if isinstance(value, Percent):
        return output * value.value / 100
    raise ValueError(f"a Panel size is pixels or a percentage, not {type(value).__name__}")


def panel_geometry(spec: PanelSpec, output: tuple[int, int]) -> Geometry:
    """The tre settings for ``spec`` on an output of ``output`` logical pixels. Raises
    :class:`ZeroSize` for a size of 0 on an axis not stretched between two opposite anchors."""
    anchors = {a.lower() for a in spec.anchor}
    left_in, top_in, right_in, bottom_in = spec.inset
    inset = {"top": top_in, "right": right_in, "bottom": bottom_in, "left": left_in}
    top, right, bottom, left = spec.bleed
    want = {"top": top, "right": right, "bottom": bottom, "left": left}
    warnings: list[str] = []
    size: list[int] = []
    body = {side: 0 for side in _ORDER}
    margin = {side: 0 for side in _ORDER}
    for axis, (low, high), value, out in (
        ("width", ("left", "right"), spec.width, output[0]),
        ("height", ("top", "bottom"), spec.height, output[1]),
    ):
        length = _size(value, out)
        stretched = low in anchors and high in anchors
        if length <= 0 and not stretched:
            raise ZeroSize(
                f"the Panel's {axis} is 0 and it is not anchored to both {low} and {high}; "
                f"give a {axis} or anchor both"
            )
        if stretched:
            body[low], body[high] = want[low], want[high]
            size.append(0 if length <= 0 else round(length) + want[low] + want[high])
        elif low in anchors or high in anchors:
            body[low], body[high] = want[low], want[high]
            size.append(round(length) + want[low] + want[high])
        else:  # centred by the compositor: the same margin both sides keeps it centred
            both = max(want[low], want[high])
            body[low] = body[high] = both
            size.append(round(length) + 2 * both)
        for side in (low, high):
            if side in anchors:
                margin[side] = round(inset[side]) - body[side]
            elif inset[side]:
                warnings.append(f"Inset {side} has no effect: the Panel is not anchored to {side}")
    return Geometry(
        anchor=tuple(a for a in ("top", "right", "bottom", "left") if a in anchors),
        size=(size[0], size[1]),
        margin=(margin["top"], margin["right"], margin["bottom"], margin["left"]),
        exclusive_zone=0,
        exclusive_edge=None,
        warnings=tuple(warnings),
        body_margin=(body["top"], body["right"], body["bottom"], body["left"]),
    )
