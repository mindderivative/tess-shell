"""The handle of a peek: the icon on its tab or sliver (Frame > Peek Triggers and Handles).

Three kinds, each telling what the tab does: ``DOTS`` (three dots side by side: it opens on
hover), ``BAR`` (a short bar: it opens by dragging) and ``CHEVRON`` (it opens on a click). They are
drawn by the Frame's painter as plain tre nodes in a holder that is never a click target
(``hit_testable=False``): the tab is the target, the handle only draws. The holder sits at the
middle of the visible tab (``Size`` px deep, centred along the edge) and moves with the far edge of
the contour while it slides: the Frame animates the holder's ``translate`` and, for a chevron, the
parameter ``p`` of its path on the same clock and easing as the join, so there is no Python per
frame.

The chevron is one path template, ``p`` from 0 (collapsed: the apex points *away* from the Frame,
into the opening) to 1 (out: the apex points *towards* the Frame); each coordinate is linear in
``p``, so the change of direction runs with the slide's progress, as the contour's own does.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tess_re import LayerWindow
    from tess_re import Node as TreNode

RGBA = tuple[int, int, int, int]
Easing = tuple[float, float, float, float]

# the thinnest tab (and side) that draws each handle, in pixels (maintainer, 2026-11-07, as
# recommended; to be tuned on KWin)
MIN_THICKNESS = {"DOTS": 8.0, "BAR": 8.0, "CHEVRON": 8.0}
DOT = 3.0  # a dot's diameter and the gap between two (the Edge Shell's 3 px dots with 3 px gaps)
DOT_GAP = 3.0
BAR_LENGTH = 24.0  # along the edge
BAR_THICKNESS = 3.0
# the maintainer's chevron (tess_shell_chevron.svg, 2026-11-08): a filled triangle 22 px wide and
# 6.73 px high, its Inkscape transform flattened: base (1.0, 7.37)-(23.0, 7.37), apex (12.0, 0.63)
CHEVRON_HALF = 11.0  # half the chevron's width along the edge
CHEVRON_RISE = 3.365  # half its height: the apex is this far from the midline, away or towards
PAD = 2.0  # room round the drawing inside the holder, so its anti-aliased edge is not clipped
REST_OPACITY = 0.6  # a handle is dimmer than its colour until the pointer is on the tab
# the direction into the opening from each side, in the painter's pixels
TOWARD = {"top": (0.0, 1.0), "bottom": (0.0, -1.0), "left": (1.0, 0.0), "right": (-1.0, 0.0)}


def fits(kind: str, size: float, side_thickness: float) -> bool:
    """Whether a handle of ``kind`` fits a tab of ``size`` px on a side ``side_thickness`` thick."""
    need = MIN_THICKNESS[kind]
    return size >= need and side_thickness >= need


def resolve(handle: str, trigger: str) -> str | None:
    """The kind of handle drawn: ``AUTO`` follows the trigger, ``NONE`` is none."""
    if handle == "NONE":
        return None
    if handle != "AUTO":
        return handle
    return {"HOVER": "DOTS", "DRAG": "BAR", "CLICK": "CHEVRON"}[trigger]


def _num(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-0") else "0"


def _hole(base: float, slope: float) -> str:
    """``{base + p*slope}``, or the plain number when it does not move."""
    if abs(slope) < 5e-4:
        return _num(base)
    return f"{{{_num(base)} {'-' if slope < 0 else '+'} p*{_num(abs(slope))}}}"


def chevron_data(side: str, width: float, height: float) -> str:
    """The chevron's path template in a ``width`` x ``height`` holder on ``side``: three points,
    each coordinate a hole in ``p``. At ``p`` = 0 the apex is ``CHEVRON_RISE`` into the opening and
    the ends that far back; at 1 it is mirrored."""
    nx, ny = TOWARD[side]
    ux, uy = abs(ny), abs(nx)  # along the edge
    cx, cy = width / 2, height / 2
    spec = (
        (-CHEVRON_HALF, -CHEVRON_RISE),
        (0.0, CHEVRON_RISE),
        (CHEVRON_HALF, -CHEVRON_RISE),
    )  # (along, depth) at p = 0
    points = []
    for along, depth in spec:
        x0, y0 = cx + along * ux + depth * nx, cy + along * uy + depth * ny
        points.append(f"{_hole(x0, -2 * depth * nx)},{_hole(y0, -2 * depth * ny)}")
    return f"M{points[0]} L{points[1]} L{points[2]} Z"


def size_of(kind: str, side: str) -> tuple[float, float]:
    """The holder's width and height for ``kind`` on ``side`` (the drawing and ``PAD`` round it)."""
    if kind == "DOTS":
        length, thick = 3 * DOT + 2 * DOT_GAP, DOT
    elif kind == "BAR":
        length, thick = BAR_LENGTH, BAR_THICKNESS
    else:
        length, thick = 2 * CHEVRON_HALF, 2 * CHEVRON_RISE
    length, thick = length + 2 * PAD, thick + 2 * PAD
    return (length, thick) if side in ("top", "bottom") else (thick, length)


@dataclass(slots=True)
class Handle:
    """The nodes of one handle: a ``holder`` box (never a click target) and its drawing."""

    kind: str
    side: str
    holder: TreNode
    parts: list[TreNode]
    chevron: TreNode | None
    width: float
    height: float
    colour: RGBA

    def place(self, cx: float, cy: float) -> None:
        """Put the holder's centre at the painter's point (``cx``, ``cy``)."""
        self.holder.set(left=cx - self.width / 2, top=cy - self.height / 2)

    def paint(self, colour: RGBA) -> None:
        if colour == self.colour:
            return
        self.colour = colour
        for node in self.parts:
            node.set(fill=colour)

    def seek(self, p: float, dx: float, dy: float) -> None:
        """At once: the chevron at ``p``, the holder ``(dx, dy)`` from where it was placed."""
        self.holder.set(translate_x=dx, translate_y=dy)
        if self.chevron is not None:
            self.chevron.set(params={"p": p})

    def animate(self, p: float, dx: float, dy: float, ms: int, easing: Easing) -> None:
        """Move to ``(dx, dy)`` and the chevron to ``p`` on tre's clock."""
        self.holder.animate("translate_x", dx, ms, easing)
        self.holder.animate("translate_y", dy, ms, easing)
        if self.chevron is not None:
            self.chevron.animate_param("p", p, ms, easing)

    def hover(self, on: bool, ms: int = 120) -> None:
        self.holder.animate("opacity", 1.0 if on else REST_OPACITY, ms)

    def destroy(self) -> None:
        try:
            self.holder.destroy()
        except Exception:  # the window is gone: so are its nodes
            pass


def make(painter: LayerWindow, kind: str, side: str, z_index: int, colour: RGBA) -> Handle:
    """The nodes of a ``kind`` handle on ``side``, added to ``painter`` at ``z_index``, hidden."""
    width, height = size_of(kind, side)
    holder = painter.create(
        "box",
        position="absolute",
        left=0,
        top=0,
        width=width,
        height=height,
        visible=False,
        hit_testable=False,
        a11y_hidden=True,
        opacity=REST_OPACITY,
        z_index=z_index,
    )
    painter.root.add_child(holder)
    parts: list[TreNode] = []
    chevron = None
    if kind == "CHEVRON":
        chevron = painter.create(
            "path",
            data=chevron_data(side, width, height),
            params={"p": 0.0},
            fill=colour,
            position="absolute",
            left=0,
            top=0,
            width=width,
            height=height,
            hit_testable=False,
            a11y_hidden=True,
        )
        parts.append(chevron)
    else:
        along = side in ("top", "bottom")
        count = 3 if kind == "DOTS" else 1
        length, thick = (DOT, DOT) if kind == "DOTS" else (BAR_LENGTH, BAR_THICKNESS)
        for i in range(count):
            offset = PAD + i * (DOT + DOT_GAP)
            w, h = (length, thick) if along else (thick, length)
            parts.append(
                painter.create(
                    "box",
                    position="absolute",
                    left=offset if along else PAD,
                    top=PAD if along else offset,
                    width=w,
                    height=h,
                    fill=colour,
                    corner_radius=min(w, h) / 2,
                    hit_testable=False,
                    a11y_hidden=True,
                )
            )
    for node in parts:
        holder.add_child(node)
    return Handle(kind, side, holder, parts, chevron, width, height, colour)
