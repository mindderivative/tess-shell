"""The Bar geometry: TDL placement keys to tre's ``anchor``, ``size``, ``margin`` and
``exclusive_zone`` (Bar > Mapping to tre, accepted 2026-10-31). A pure function: no engine, no
I/O, so every row of the worked-examples table is a test.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from tess_shell.binder.model import Auto, Expand, Length, Percent

Edge = Literal["TOP", "BOTTOM", "LEFT", "RIGHT"]
Alignment = Literal["START", "CENTER", "END"]
Layer = Literal["BOTTOM", "TOP", "OVERLAY"]
Size = Length | Percent | Auto | Expand

_ORDER = ("top", "right", "bottom", "left")  # tre's margin order


class ZeroSize(ValueError):
    """The Bar resolves to 0 on an axis it is attached along; it is not created (D46)."""


@dataclass(frozen=True, slots=True)
class BarSpec:
    """The placement keys of one Bar. ``None`` means the key was not written."""

    edge: Edge
    width: Size
    height: Size
    alignment: Alignment | None = None
    offset: float | None = None
    gap: float = 0
    layer: Layer = "TOP"
    reserve: bool = True
    min_width: float | None = None
    min_height: float | None = None
    max_width: float | None = None
    max_height: float | None = None
    bleed: tuple[int, int, int, int] = (
        0,
        0,
        0,
        0,
    )  # shadow margin wanted: top, right, bottom, left


@dataclass(frozen=True, slots=True)
class Geometry:
    anchor: tuple[str, ...]  # edge names in tre's lower case
    size: tuple[int, int]  # (width, height), 0 stretches between two anchored edges
    margin: tuple[int, int, int, int]  # top, right, bottom, left
    exclusive_zone: int
    exclusive_edge: str | None = None
    warnings: tuple[str, ...] = ()
    body_margin: tuple[int, int, int, int] = (
        0,
        0,
        0,
        0,
    )  # the transparent margin, top right bottom left


def _clamp(value: float, low: float | None, high: float | None) -> float:
    if high is not None:
        value = min(value, high)
    if low is not None:
        value = max(value, low)
    return value


def _resolve(
    size: Size,
    *,
    output: int,
    content: float,
    low: float | None,
    high: float | None,
    along: bool,
) -> float | None:
    """A size in pixels along one axis; ``None`` for ``EXPAND`` along the Edge."""
    match size:
        case Length(px=px):
            value = px
        case Percent(value=p):
            value = output * p / 100
        case Auto():
            value = content
        case Expand():
            if along:
                return None
            value = high if high is not None else (low if low is not None else 0)
    return _clamp(value, low, high)


def bar_geometry(
    spec: BarSpec, output: tuple[int, int], content: tuple[float, float] = (0, 0)
) -> Geometry:
    """Compute the tre settings for ``spec`` on an output of ``output`` logical pixels.

    ``content`` is the content's size, used only for ``AUTO``. Raises :class:`ZeroSize`.
    """
    edge = spec.edge.lower()
    horizontal = edge in ("top", "bottom")  # the Edge runs along x
    out_w, out_h = output
    width = _resolve(
        spec.width,
        output=out_w,
        content=content[0],
        low=spec.min_width,
        high=spec.max_width,
        along=horizontal,
    )
    height = _resolve(
        spec.height,
        output=out_h,
        content=content[1],
        low=spec.min_height,
        high=spec.max_height,
        along=not horizontal,
    )
    length, thickness = (width, height) if horizontal else (height, width)
    out_along = out_w if horizontal else out_h
    start, end = ("left", "right") if horizontal else ("top", "bottom")

    if thickness is None or thickness <= 0:
        raise ZeroSize(
            f"the Bar's size across its edge is 0; set a Min_{'Height' if horizontal else 'Width'}"
        )
    if length is not None and length <= 0:
        raise ZeroSize(
            f"the Bar's length along its edge is 0; set a Min_{'Width' if horizontal else 'Height'}"
        )
    thick = round(thickness)
    gap = round(spec.gap)
    # The shadow margin (ADR-0010): the surface grows by it and the body keeps its place. A side
    # flush with the screen shows no shadow: the Edge side gets at most the Gap, and an EXPAND
    # length none along the Edge. A floating bar gets the same margin on both ends, so the
    # compositor's centring still centres the body.
    top, right, bottom, left = spec.bleed
    want = {"top": top, "right": right, "bottom": bottom, "left": left}
    inner = {"top": "bottom", "bottom": "top", "left": "right", "right": "left"}[edge]
    eb = {side: 0 for side in _ORDER}
    eb[edge] = min(want[edge], gap)
    eb[inner] = want[inner]
    if length is not None:
        eb[start] = eb[end] = max(want[start], want[end])
    margins = {side: 0 for side in _ORDER}
    margins[edge] = gap - eb[edge]
    warnings: list[str] = []
    exclusive_edge: str | None = None

    anchor: tuple[str, ...]
    if length is None:  # EXPAND along: both perpendicular edges, size 0 along
        anchor = (edge, start, end)
        along_size = 0
        if spec.alignment is not None or spec.offset is not None:
            warnings.append("Alignment and Offset have no effect on an EXPAND length")
    else:
        along_size = round(length) + eb[start] + eb[end]
        alignment = spec.alignment or "CENTER"
        offset = spec.offset or 0
        if alignment == "START":
            anchor = (edge, start)
            margins[start] = round(offset) - eb[start]
            exclusive_edge = edge
        elif alignment == "END":
            anchor = (edge, end)
            margins[end] = round(-offset) - eb[end]
            exclusive_edge = edge
        elif offset == 0:
            anchor = (edge,)
        else:
            anchor = (edge, start)
            margins[start] = round((out_along - along_size) / 2 + offset)
            exclusive_edge = edge

    reserves = spec.layer == "TOP" and spec.reserve
    # The compositor reserves the zone plus the Edge margin; the margin shrank by ``eb[edge]`` and
    # the zone grows by it, so the reserved space is the same with or without a shadow.
    zone = thick + gap + eb[edge] if reserves else 0
    across = thick + eb[edge] + eb[inner]
    size = (along_size, across) if horizontal else (across, along_size)
    return Geometry(
        anchor=anchor,
        size=size,
        margin=(margins["top"], margins["right"], margins["bottom"], margins["left"]),
        exclusive_zone=zone,
        exclusive_edge=exclusive_edge,
        warnings=tuple(warnings),
        body_margin=(eb["top"], eb["right"], eb["bottom"], eb["left"]),
    )
