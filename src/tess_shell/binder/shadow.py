"""Shadows from an elevation, and the margin a shadow needs (Style Schema > Shadow Keys).

Pure functions over :mod:`tess_shell.binder.model`. ``Elevation`` is a percentage: ``0%`` is no
shadow and ``100%`` is the theme's ``Max`` shadow list, with the offset, blur and spread of every
shadow scaled by the percentage (the colour is kept). The default ``Max`` reaches 64 px, the
figure in the maintainer's tests (D88).

The reach was measured on tre 0.6.1 (``tests/test_binder_shadow.py``): a shadow shows up to
``blur + spread`` pixels beyond the body, shifted by its offset, so a side needs
``blur + spread +/- offset`` pixels of transparent margin, plus one pixel for the blur tail.
"""

from __future__ import annotations

import math

from tess_shell.binder.model import Color, Origin, Shadow, Shadows

DEFAULT_MAX = Shadows((Shadow(Color(0, 0, 0, 0x40), 0, 16, 48, 0),))


def scale(max_shadows: Shadows, percent: float, origin: Origin) -> Shadows:
    """The shadows at ``percent`` (0 to 100) of ``max_shadows``."""
    if percent <= 0:
        return Shadows((), origin=origin)
    f = percent / 100
    return Shadows(
        tuple(
            Shadow(s.color, s.x * f, s.y * f, s.blur * f, s.spread * f, origin=origin)
            for s in max_shadows.items
        ),
        origin=origin,
    )


def bleed(shadows: Shadows) -> tuple[int, int, int, int]:
    """The margin a body needs for ``shadows``, in tre's order: top, right, bottom, left."""
    top = right = bottom = left = 0.0
    for s in shadows.items:
        reach = max(s.blur + s.spread, 0)
        top = max(top, reach - s.y)
        bottom = max(bottom, reach + s.y)
        left = max(left, reach - s.x)
        right = max(right, reach + s.x)
    # +1 pixel: tre's blur tail ends one pixel beyond ``blur`` on the long axis (measured)
    sides = tuple(math.ceil(side) + 1 if side > 0 else 0 for side in (top, right, bottom, left))
    return sides  # type: ignore[return-value]
