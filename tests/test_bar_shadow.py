"""A Bar's shadow, rendered the way the surface manager builds it (ADR-0010, route B)."""

from __future__ import annotations

from tess_re import LayerWindow

from tess_shell.binder import convert
from tess_shell.binder.model import Length, Percent
from tess_shell.binder.shadow import style_bleed, style_shadows
from tess_shell.surfaces.bar import BarSpec, bar_geometry
from tess_shell.surfaces.manager import _body_style  # the one builder the manager uses


def render(style: dict, gap: int = 0, out: tuple[int, int] = (200, 400)):  # type: ignore[no-untyped-def]
    from tess_shell.binder.model import Expand

    shadows = style_shadows(style)
    spec = BarSpec("TOP", Expand(), Length(32), gap=gap, bleed=style_bleed(style, shadows))
    geometry = bar_geometry(spec, out)
    window = LayerWindow("t", anchor=geometry.anchor, size=geometry.size, margin=geometry.margin)
    window.resize(out[0], geometry.size[1])
    body = window.create(
        "box",
        flex_grow=1,
        align_self="stretch",
        **_body_style(
            geometry,
            (31, 31, 31, 255),
            convert.shadows(shadows, ("shadows",))["shadows"],
        ),
    )
    window.root.add_child(body)
    data, width, height = window.snapshot()
    return geometry, (lambda x, y: data[(y * width + x) * 4 + 3]), width, height


def test_the_shadow_is_fully_inside_the_surface_and_the_body_is_where_it_was() -> None:
    style = {"Elevation": Percent(100)}
    g, alpha, w, h = render(style)
    assert alpha(100, 0) == 255 and alpha(100, 31) == 255  # the body: 32 px at the top
    assert 0 < alpha(100, 32 + 4) < 255  # the shadow starts under the body
    assert alpha(100, h - 1) == 0  # and has faded out before the surface ends: nothing is cut


def test_no_elevation_leaves_a_plain_bar() -> None:
    g, alpha, w, h = render({})
    assert g.size == (0, 32) and g.body_margin == (0, 0, 0, 0)
    assert alpha(100, 31) == 255 and h == 32


def test_the_gap_shows_the_shadow_above_the_body() -> None:
    g, alpha, w, h = render({"Elevation": Percent(100)}, gap=8)
    assert g.body_margin[0] == 8
    assert 0 < alpha(100, 3) < 255  # in the gap above the body, in the transparent margin
    assert alpha(100, 8 + 10) == 255  # the body starts after the gap


def test_an_explicit_shadow_bleed_wins_over_the_computed_one() -> None:
    style = {"Elevation": Percent(100), "Shadow_Bleed": Length(10)}
    g, alpha, w, h = render(style)
    assert g.body_margin == (0, 0, 10, 0) and h == 32 + 10
