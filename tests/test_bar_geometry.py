"""Bar > Mapping to tre: the worked examples on a 1920 px wide output, and the rules around them."""

from __future__ import annotations

import pytest

from tess_shell.binder.model import Auto, Expand, Length, Percent
from tess_shell.surfaces.bar import BarSpec, Geometry, ZeroSize, bar_geometry

OUT = (1920, 1080)


def geo(spec: BarSpec, content: tuple[float, float] = (0, 0)) -> Geometry:
    return bar_geometry(spec, OUT, content)


@pytest.mark.parametrize(
    ("spec", "anchor", "size", "margin", "zone", "edge"),
    [
        # Edge: TOP, Width: EXPAND, Height: 32
        (
            BarSpec("TOP", Expand(), Length(32)),
            ("top", "left", "right"),
            (0, 32),
            (0, 0, 0, 0),
            32,
            None,
        ),
        # ... Gap: 8
        (
            BarSpec("TOP", Expand(), Length(32), gap=8),
            ("top", "left", "right"),
            (0, 32),
            (8, 0, 0, 0),
            40,
            None,
        ),
        # Edge: BOTTOM, Width: 560, Height: 64, Alignment: CENTER (zone 64 only if Layer is TOP)
        (
            BarSpec("BOTTOM", Length(560), Length(64), alignment="CENTER"),
            ("bottom",),
            (560, 64),
            (0, 0, 0, 0),
            64,
            None,
        ),
        # Edge: TOP, Width: 400, Height: 32, Alignment: START, Offset: 200
        (
            BarSpec("TOP", Length(400), Length(32), alignment="START", offset=200),
            ("top", "left"),
            (400, 32),
            (0, 0, 0, 200),
            32,
            "top",
        ),
        # ... Alignment: END, Offset: 40
        (
            BarSpec("TOP", Length(400), Length(32), alignment="END", offset=40),
            ("top", "right"),
            (400, 32),
            (0, -40, 0, 0),
            32,
            "top",
        ),
    ],
)
def test_worked_examples(
    spec: BarSpec,
    anchor: tuple[str, ...],
    size: tuple[int, int],
    margin: tuple[int, int, int, int],
    zone: int,
    edge: str | None,
) -> None:
    g = geo(spec)
    assert (g.anchor, g.size, g.margin, g.exclusive_zone, g.exclusive_edge) == (
        anchor,
        size,
        margin,
        zone,
        edge,
    )
    assert g.warnings == ()


def test_the_dock_reserves_its_height_plus_its_gap() -> None:
    g = geo(BarSpec("BOTTOM", Length(560), Length(64), alignment="CENTER", gap=8, layer="TOP"))
    assert g.exclusive_zone == 72 and g.margin == (0, 0, 8, 0)


@pytest.mark.parametrize(
    "spec",
    [
        BarSpec("BOTTOM", Length(560), Length(64), layer="BOTTOM"),
        BarSpec("TOP", Expand(), Length(32), layer="OVERLAY"),
        BarSpec("TOP", Expand(), Length(32), reserve=False),
    ],
)
def test_no_zone_unless_top_layer_and_reserve(spec: BarSpec) -> None:
    assert geo(spec).exclusive_zone == 0


def test_center_with_offset_anchors_to_the_start_side() -> None:
    g = geo(BarSpec("TOP", Length(400), Length(32), alignment="CENTER", offset=50))
    assert g.anchor == ("top", "left")
    assert g.margin == (0, 0, 0, (1920 - 400) // 2 + 50)
    assert g.exclusive_edge == "top"


def test_default_alignment_is_center() -> None:
    assert geo(BarSpec("TOP", Length(400), Length(32))).anchor == ("top",)


def test_expand_along_warns_when_alignment_or_offset_is_written() -> None:
    assert geo(BarSpec("TOP", Expand(), Length(32), alignment="START")).warnings
    assert geo(BarSpec("TOP", Expand(), Length(32), offset=3)).warnings
    assert geo(BarSpec("TOP", Expand(), Length(32), offset=3)).margin == (0, 0, 0, 0)


def test_left_and_right_bars_swap_the_axes() -> None:
    g = geo(BarSpec("LEFT", Length(48), Expand()))
    assert (g.anchor, g.size, g.exclusive_zone) == (("left", "top", "bottom"), (48, 0), 48)
    g = geo(BarSpec("RIGHT", Length(48), Length(400), alignment="END", offset=10, gap=4))
    assert g.anchor == ("right", "bottom")
    assert g.size == (48, 400)
    assert g.margin == (0, 4, -10, 0)  # gap on the edge's own side, -offset on the end side
    assert g.exclusive_zone == 52


def test_percent_resolves_against_the_output_on_that_axis() -> None:
    g = geo(BarSpec("TOP", Percent(50), Percent(5)))
    assert g.size == (960, 54)
    g = geo(BarSpec("LEFT", Percent(5), Percent(50)))
    assert g.size == (96, 540)


def test_auto_is_the_content_size_and_bounds_clamp() -> None:
    g = geo(BarSpec("TOP", Auto(), Auto()), content=(300, 28))
    assert g.size == (300, 28)
    g = geo(BarSpec("TOP", Auto(), Length(10), min_height=32, max_width=200), content=(300, 28))
    assert g.size == (200, 32)


def test_expand_across_is_max_then_min_then_zero() -> None:
    assert geo(BarSpec("TOP", Expand(), Expand(), max_height=40, min_height=20)).size == (0, 40)
    assert geo(BarSpec("TOP", Expand(), Expand(), min_height=20)).size == (0, 20)
    with pytest.raises(ZeroSize, match="Min_Height"):
        geo(BarSpec("TOP", Expand(), Expand()))


@pytest.mark.parametrize(
    "spec",
    [
        BarSpec("TOP", Expand(), Length(0)),
        BarSpec("TOP", Length(0), Length(32)),
        BarSpec("LEFT", Length(0), Expand()),
        BarSpec("TOP", Auto(), Length(32)),  # AUTO with no content
    ],
)
def test_zero_size_is_not_created(spec: BarSpec) -> None:
    with pytest.raises(ZeroSize):
        geo(spec)


@pytest.mark.parametrize(
    "spec",
    [
        BarSpec("TOP", Expand(), Length(32)),
        BarSpec("TOP", Expand(), Length(32), gap=8),
        BarSpec("BOTTOM", Length(560), Length(64), alignment="CENTER"),
        BarSpec("TOP", Length(400), Length(32), alignment="START", offset=200),
        BarSpec("TOP", Length(400), Length(32), alignment="END", offset=40),
        BarSpec("TOP", Length(400), Length(32), alignment="CENTER", offset=50),
        BarSpec("LEFT", Length(48), Expand()),
        BarSpec("RIGHT", Length(48), Length(400), alignment="END", offset=10, gap=4),
    ],
)
def test_the_engine_accepts_the_geometry(spec: BarSpec) -> None:
    """A protocol-level refusal (invalid size, a zone on the wrong anchors) fails here."""
    from tess_re import LayerWindow

    g = geo(spec)
    window = LayerWindow(
        "tesserae-shell.bar.test",
        layer="top",
        anchor=g.anchor,
        size=g.size,
        margin=g.margin,
        exclusive_zone=g.exclusive_zone,
        exclusive_edge=g.exclusive_edge,  # type: ignore[arg-type]
    )
    assert set(window.get("anchor")) == set(g.anchor)  # tre keeps its own order
    assert tuple(window.get("size")) == g.size
    assert tuple(window.get("margin")) == g.margin
    assert window.get("exclusive_zone") == g.exclusive_zone
    assert window.get("exclusive_edge") == g.exclusive_edge
