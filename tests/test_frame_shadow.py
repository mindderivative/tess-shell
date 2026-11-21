"""The Frame's shadow (Frame > Elevation, TSH-054): ``Elevation`` or ``Shadows`` in its ``Style``
make the ring shader paint a shadow that falls from the ring's inner edge into the opening."""

from __future__ import annotations

from tests.test_frame_linear import pixel, snap, started

FRAME = 'Frame { Name: F, Thickness: 24, Inner_Radius: 14, Style { Background: "#1e1e2e", %s } }'
W, H = 400, 300


def opening_row(manager, y: int = 150) -> list[tuple[int, ...]]:  # type: ignore[no-untyped-def]
    shot = snap(manager)
    return [pixel(shot, x, y) for x in range(24, 124)]  # from the opening on


def test_a_frame_with_no_shadow_leaves_the_opening_clear() -> None:
    manager = started(FRAME % "Opacity: 1")
    assert all(p[3] == 0 for p in opening_row(manager))


def test_a_shadow_falls_into_the_opening_and_fades_with_distance() -> None:
    shadows = 'Shadows { Shadow { Color: "#000000FF", X: 0, Y: 0, Blur: 16, Spread: 0 } }'
    manager = started(FRAME % shadows)
    row = opening_row(manager)
    edge = row[1]  # one pixel inside the opening (the band is 24 px)
    mid, far = row[8], row[40]
    assert edge[3] > 60  # about half at the edge of the ring (a blur of 16 spans 16 px)
    assert 0 < mid[3] < edge[3]  # and fades
    assert far[3] == 0  # and is gone well outside the blur


def test_the_spread_grows_the_ring_and_a_shadow_never_covers_the_ring_itself() -> None:
    plain = 'Shadows { Shadow { Color: "#000000FF", X: 0, Y: 0, Blur: 8, Spread: 0 } }'
    spread = 'Shadows { Shadow { Color: "#000000FF", X: 0, Y: 0, Blur: 8, Spread: 10 } }'
    a, b = opening_row(started(FRAME % plain)), opening_row(started(FRAME % spread))
    i = 10
    assert b[i][3] > a[i][3]
    ring = pixel(snap(started(FRAME % spread)), 5, 150)
    assert ring[:3] == (0x1E, 0x1E, 0x2E) and ring[3] == 255  # the band keeps its own colour


def test_an_elevation_percentage_scales_the_themes_maximum() -> None:
    manager = started(FRAME % "Elevation: 100%")
    row = opening_row(manager)
    assert row[2][3] > 0 and row[2][:3] == (0, 0, 0)


def test_a_frame_that_needs_no_shader_draws_no_shadow() -> None:
    manager = started(FRAME % "Elevation: 100%", blend="PATH")
    assert all(p[3] == 0 for p in opening_row(manager))
