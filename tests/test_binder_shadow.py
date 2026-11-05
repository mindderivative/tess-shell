"""Elevation and shadow margins (Style Schema > Shadow Keys), against tre's real rendering."""

from __future__ import annotations

import pytest
from tess_re import LayerWindow

from tess_shell.binder.model import Color, Origin, Shadow, Shadows
from tess_shell.binder.shadow import DEFAULT_MAX, bleed, scale

BLACK = Color(0, 0, 0, 255)
HERE = Origin("t.tdl", 1, 1)


def test_the_default_max_reaches_64_pixels() -> None:
    assert max(bleed(DEFAULT_MAX)) == 65  # 64 and one pixel for the blur tail


def test_zero_elevation_is_no_shadow_and_a_half_halves_every_number() -> None:
    assert scale(DEFAULT_MAX, 0, HERE).items == ()
    (half,) = scale(DEFAULT_MAX, 50, HERE).items
    assert (half.x, half.y, half.blur, half.spread) == (0, 8, 24, 0)
    assert half.color == DEFAULT_MAX.items[0].color


def test_bleed_follows_the_offset_per_side() -> None:
    shadows = Shadows((Shadow(BLACK, 0, 16, 48, 0),))
    assert bleed(shadows) == (33, 49, 65, 49)  # top, right, bottom, left
    assert bleed(Shadows(())) == (0, 0, 0, 0)
    far = Shadows((Shadow(BLACK, 40, 0, 4, 0),))  # a shadow far to one side
    assert bleed(far) == (5, 45, 5, 0)


def _alpha_reach(shadows: list[tuple[object, ...]]) -> tuple[int, int, int, int]:
    """Pixels beyond a 100x40 body (centred in a 120 px margin) where the alpha is at least 1."""
    margin, body_w, body_h = 120, 100, 40
    w, h = body_w + 2 * margin, body_h + 2 * margin
    win = LayerWindow("shadow-probe", anchor=("top", "left"), size=(w, h))
    win.resize(w, h)
    win.root.set(fill=(0, 0, 0, 0))
    box = win.create(
        "box",
        width=body_w,
        height=body_h,
        margin_left=margin,
        margin_top=margin,
        fill=(255, 255, 255, 255),
        corner_radius=8,
        shadows=shadows,
    )
    win.root.add_child(box)
    data, width, _height = win.snapshot()

    def alpha(x: int, y: int) -> int:
        return int(data[(y * width + x) * 4 + 3])

    cx, cy = margin + body_w // 2, margin + body_h // 2
    left = right = top = bottom = 0
    for d in range(margin):
        left = d + 1 if alpha(margin - 1 - d, cy) else left
        right = d + 1 if alpha(margin + body_w + d, cy) else right
        top = d + 1 if alpha(cx, margin - 1 - d) else top
        bottom = d + 1 if alpha(cx, margin + body_h + d) else bottom
    return top, right, bottom, left


@pytest.mark.parametrize(
    "shadow",
    [
        Shadow(BLACK, 0, 0, 8, 0),
        Shadow(BLACK, 0, 16, 48, 0),
        Shadow(BLACK, 0, 0, 8, 4),
        Shadow(BLACK, 12, -6, 20, 2),
    ],
)
def test_the_computed_bleed_holds_everything_tre_draws(shadow: Shadow) -> None:
    drawn = _alpha_reach([((0, 0, 0, 255), shadow.x, shadow.y, shadow.blur, shadow.spread)])
    needed = bleed(Shadows((shadow,)))
    assert all(d <= n for d, n in zip(drawn, needed, strict=True)), (drawn, needed)
    assert max(n - d for d, n in zip(drawn, needed, strict=True)) <= 12  # and is not wasteful
