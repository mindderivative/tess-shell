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
from tess_shell.surfaces.bar import Geometry, Rect, ZeroSize

_ORDER = ("top", "right", "bottom", "left")  # tre's margin order


@dataclass(frozen=True, slots=True)
class PanelSpec:
    anchor: tuple[str, ...]  # TOP, BOTTOM, LEFT, RIGHT
    inset: tuple[float, float, float, float]  # left, top, right, bottom
    width: Value
    height: Value
    bleed: tuple[int, int, int, int] = (0, 0, 0, 0)  # top, right, bottom, left
    attach: str | None = None  # LEFT, RIGHT, TOP, BOTTOM: the target's edge; None = not attached
    gap: float = 0
    alignment: str = "CENTER"


def _size(value: Value, output: int) -> float:
    if isinstance(value, Length):
        return value.px
    if isinstance(value, Percent):
        return output * value.value / 100
    raise ValueError(f"a Panel size is pixels or a percentage, not {type(value).__name__}")


def _along(alignment: str, start: float, length: float, size: float) -> float:
    """The start of a ``size`` body aligned to the span ``start``..``start + length``."""
    if alignment == "START":
        return start
    if alignment == "END":
        return start + length - size
    return start + (length - size) / 2


def attached_geometry(
    spec: PanelSpec, output: tuple[int, int], target: Rect, clearance: Rect | None = None
) -> tuple[Geometry, tuple[str, ...]]:
    """The geometry of a Panel attached to ``target`` (Panel > Attachment Geometry), and the
    warnings: ``Attach`` names the target's edge the Panel meets, ``Gap`` is the clear distance
    between the two bodies, ``Alignment`` slides it along the shared edge. A body that would leave
    the output is moved back onto it, with a warning. With a ``clearance`` (the Bar that holds a
    target module) the Panel meets the clearance's edge instead of the target's, so it never covers
    the Bar, and slides along the target."""
    edge = clearance or target
    width, height = _size(spec.width, output[0]), _size(spec.height, output[1])
    if width <= 0 or height <= 0:
        raise ZeroSize("an attached Panel needs a Width and a Height above 0")
    match spec.attach:
        case "LEFT":
            x, y = (
                edge.x - spec.gap - width,
                _along(spec.alignment, target.y, target.height, height),
            )
        case "RIGHT":
            x, y = edge.right + spec.gap, _along(spec.alignment, target.y, target.height, height)
        case "TOP":
            x, y = (
                _along(spec.alignment, target.x, target.width, width),
                edge.y - spec.gap - height,
            )
        case _:  # BOTTOM
            x, y = _along(spec.alignment, target.x, target.width, width), edge.bottom + spec.gap
    warnings: list[str] = []
    kept_x = min(max(x, 0), max(output[0] - width, 0))
    kept_y = min(max(y, 0), max(output[1] - height, 0))
    if (kept_x, kept_y) != (x, y):
        warnings.append(
            f"the attached Panel would leave the output at ({x:g}, {y:g}); "
            f"it is placed at ({kept_x:g}, {kept_y:g}) instead"
        )
    top, right, bottom, left = spec.bleed
    return (
        Geometry(
            anchor=("top", "left"),
            size=(round(width) + left + right, round(height) + top + bottom),
            margin=(round(kept_y) - top, 0, 0, round(kept_x) - left),
            exclusive_zone=-1,
            exclusive_edge=None,
            warnings=tuple(warnings),
            body_margin=(top, right, bottom, left),
        ),
        tuple(warnings),
    )


def panel_geometry(
    spec: PanelSpec,
    output: tuple[int, int],
    target: Rect | None = None,
    clearance: Rect | None = None,
) -> Geometry:
    """The tre settings for ``spec`` on an output of ``output`` logical pixels. Raises
    :class:`ZeroSize` for a size of 0 on an axis not stretched between two opposite anchors.
    A Panel with ``attach`` needs its target's rectangle in ``target``."""
    if spec.attach is not None:
        if target is None:
            raise ZeroSize("the target of this attached Panel has no place on this output")
        return attached_geometry(spec, output, target, clearance)[0]
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
        exclusive_zone=-1,
        exclusive_edge=None,
        warnings=tuple(warnings),
        body_margin=(body["top"], body["right"], body["bottom"], body["left"]),
    )
