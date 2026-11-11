"""What a block's converted tre properties still lack (the ``post`` of its table row).

A Circle and a Ring are tre paths: their path data follows from the diameter and the border, which
are two keys, so no one key's converter can write it. A Bitmap's ``Fit: NONE`` is the image at its
natural size, which tre (it has no natural size for an image) is told as ``width`` and ``height``.
Each function takes the properties converted so far and the typed block, and completes them in
place. The same functions run when a value of the block changes (``View.update``).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from tess_shell.binder.model import Enum, Node

Post = Callable[[dict[str, Any], Node], None]


def _fmt(x: float) -> str:
    return f"{x:.4f}".rstrip("0").rstrip(".")


def circle_data(diameter: float, stroke: float) -> str:
    """The path of a circle that fits a square of ``diameter`` pixels, its stroke inside it: a
    stroke is centred on the outline, so the outline is half a stroke inside the box."""
    radius = max((diameter - stroke) / 2, 0.01)
    c = diameter / 2
    r, left, right, centre = _fmt(radius), _fmt(c - radius), _fmt(c + radius), _fmt(c)
    return f"M{left},{centre} A{r},{r} 0 1 1 {right},{centre} A{r},{r} 0 1 1 {left},{centre} Z"


def _stroke(props: Mapping[str, Any]) -> float:
    """The stroke that is painted: a width with no colour paints nothing."""
    color = props.get("stroke_color")
    if color is None or (isinstance(color, tuple) and color[3] == 0):
        return 0.0
    return float(props.get("stroke_width", 0) or 0)


def _shape(props: dict[str, Any], ring: bool) -> None:
    d = float(props["width"])
    stroke = float(props.get("stroke_width", 0) or 0) if ring else _stroke(props)
    props["data"] = circle_data(d, stroke)
    props["view_box"] = (0, 0, _int(d), _int(d))


def _int(x: float) -> int | float:
    return int(x) if float(x).is_integer() else x


def circle(props: dict[str, Any], node: Node) -> None:
    _shape(props, ring=False)


def ring(props: dict[str, Any], node: Node) -> None:
    _shape(props, ring=True)


def bitmap(props: dict[str, Any], node: Node) -> None:
    """``Fit: NONE``: a side that is not given (or is AUTO) is the image's own number of pixels."""
    fit = node.props.get("Fit") or node.style.get("Fit")
    if not (isinstance(fit, Enum) and fit.name == "NONE"):
        return
    for side, pixels in (("width", "pixel_width"), ("height", "pixel_height")):
        if props.get(side) in (None, "auto") and pixels in props:
            props[side] = props[pixels]


POSTS: Mapping[str, Post] = {"circle": circle, "ring": ring, "bitmap": bitmap}
