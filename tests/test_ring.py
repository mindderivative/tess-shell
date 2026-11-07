"""The Frame's ring: what each side reserves, and the contours as tre draws and hit-tests them."""

from __future__ import annotations

import pytest
import tess_re

from tess_shell.surfaces.ring import MeldSpec, RingSpec, ring, totals

W, H = 400, 300
RED, BLUE, GREEN = (255, 0, 0, 255), (0, 0, 255, 255), (0, 255, 0, 255)
NONE = (0, 0, 0, 0)
Pixel = tuple[int, int, int, int]


class Drawn:
    """A ring in a headless layer window: pixels and node hits."""

    def __init__(self, spec: RingSpec, size: tuple[int, int] = (W, H)) -> None:
        self.ring = ring(spec, size)
        self.window = tess_re.LayerWindow(
            "test.frame",
            layer="top",
            anchor=("top", "right", "bottom", "left"),
            size=(0, 0),
            exclusive_zone=-1,
            input_region="auto",
        )
        self.window.resize(*size)
        self.hits: list[str] = []
        for name, data, colour in (
            ("outer", self.ring.outer_border, RED),
            ("fill", self.ring.fill, BLUE),
            ("inner", self.ring.inner_border, GREEN),
        ):
            if not data:
                continue
            node = self.window.create(
                "path",
                data=data,
                fill=colour,
                hit_shape="painted",
                position="absolute",
                left=0,
                top=0,
                width=size[0],
                height=size[1],
            )
            self.window.root.add_child(node)
            node.on("pointer_down", lambda e, name=name: self.hits.append(name))
        self._rgba, self._w, _ = self.window.snapshot()

    def px(self, x: int, y: int) -> Pixel:
        i = (y * self._w + x) * 4
        return tuple(self._rgba[i : i + 4])  # type: ignore[return-value]

    def click(self, x: int, y: int) -> list[str]:
        self.hits.clear()
        self.window.simulate("pointer_down", x=x, y=y)
        return list(self.hits)


def test_a_side_reserves_thickness_both_borders_and_margin() -> None:
    assert totals(RingSpec(thickness=(10, 10, 10, 10), inner_border=2)) == (12, 12, 12, 12)
    both = RingSpec(thickness=(10, 10, 10, 10), inner_border=2, outer_border=2)
    assert totals(both) == (14, 14, 14, 14)
    margin = RingSpec(thickness=(10, 10, 10, 10), margin=(5, 5, 5, 5), inner_border=2)
    assert totals(margin) == (17, 17, 17, 17)


def test_sides_reserve_separately_and_a_side_of_zero_has_nothing() -> None:
    spec = RingSpec(thickness=(8, 24, 0, 8), margin=(3, 3, 3, 3), inner_border=1)
    assert totals(spec) == (12, 28, 0, 12)
    assert ring(spec, (W, H)).totals == (12, 28, 0, 12)


def test_fractional_pixels_are_rounded_to_whole_ones() -> None:
    assert totals(RingSpec(thickness=(9.6, 10.4, 0.4, 7.5))) == (10, 10, 0, 8)


def test_the_bands_sit_where_the_totals_say() -> None:
    spec = RingSpec(thickness=(10, 20, 30, 40), margin=(4, 4, 4, 4), outer_border=1, inner_border=2)
    d = Drawn(spec)
    y = H // 2
    # left: margin 4, outer border 1, fill 10, inner border 2, then the opening
    assert [d.px(x, y) for x in (3, 4, 5, 14, 15, 16, 17)] == [
        NONE,
        RED,
        BLUE,
        BLUE,
        GREEN,
        GREEN,
        NONE,
    ]
    # right: the same from the right edge, 30 thick
    assert [d.px(W - 1 - x, y) for x in (3, 4, 5, 34, 35, 36, 37)] == [
        NONE,
        RED,
        BLUE,
        BLUE,
        GREEN,
        GREEN,
        NONE,
    ]
    x = W // 2
    assert d.px(x, 3) == NONE and d.px(x, 4) == RED and d.px(x, 5) == BLUE
    assert d.px(x, 4 + 1 + 20 + 1) == GREEN and d.px(x, 4 + 1 + 20 + 2) == NONE
    # bottom: margin 4, outer border 1, fill 40, inner border 2
    assert d.px(x, H - 1 - 4) == RED and d.px(x, H - 1 - 5) == BLUE
    assert d.px(x, H - 1 - 44) == BLUE and d.px(x, H - 1 - 45) == GREEN
    assert d.px(x, H - 1 - 46) == GREEN and d.px(x, H - 1 - 47) == NONE
    assert d.px(W // 2, H // 2) == NONE


def test_the_opening_is_a_hole_and_the_ring_takes_clicks_only_where_it_is_painted() -> None:
    d = Drawn(RingSpec(thickness=(10, 10, 10, 10), inner_radius=(20, 20, 20, 20)))
    assert d.px(W // 2, H // 2) == NONE
    assert d.click(W // 2, H // 2) == []  # the opening passes the click on
    assert d.click(5, H // 2) == ["fill"]
    assert d.click(W // 2, 3) == ["fill"]


def test_outer_corners_are_square_by_default_and_round_with_a_radius() -> None:
    assert Drawn(RingSpec(thickness=(10, 10, 10, 10))).px(0, 0) == BLUE
    round_ = Drawn(RingSpec(thickness=(30, 30, 30, 30), outer_radius=(24, 24, 24, 24)))
    for x, y in ((0, 0), (W - 1, 0), (0, H - 1), (W - 1, H - 1)):
        assert round_.px(x, y) == NONE  # the screen corner is cut off
        assert round_.click(x, y) == []
    assert round_.px(24, 24) == BLUE and round_.px(W // 2, 0) == BLUE


def test_inner_corners_are_concave_fillets_that_pass_clicks_only_in_the_opening() -> None:
    d = Drawn(RingSpec(thickness=(10, 10, 10, 10), inner_radius=(20, 20, 20, 20)))
    # the opening's corner is at (10, 10); the fillet fills the notch between it and the arc
    assert d.px(11, 11) == BLUE and d.px(10, 10) == BLUE
    assert d.click(11, 11) == ["fill"]
    # the arc passes (10 + 20 - 14.1) = 15.9 on the diagonal: 19 is more than 3 px inside
    assert d.px(19, 19) == NONE
    assert d.click(19, 19) == []
    for x, y in ((W - 12, 11), (11, H - 12), (W - 12, H - 12)):
        assert d.px(x, y) == BLUE and d.click(x, y) == ["fill"]


def test_a_border_follows_the_corner_it_is_on() -> None:
    d = Drawn(RingSpec(thickness=(20, 20, 20, 20), inner_radius=(16, 16, 16, 16), inner_border=3))
    # along the left side the border is 3 wide, next to the opening
    assert d.px(19, H // 2) == BLUE and d.px(20, H // 2) == GREEN
    assert d.px(22, H // 2) == GREEN and d.px(23, H // 2) == NONE
    assert d.click(21, H // 2) == ["inner"]


def test_a_radius_is_reduced_when_the_ring_cannot_hold_it_and_the_hole_stays() -> None:
    spec = RingSpec(
        thickness=(10, 10, 10, 10),
        outer_radius=(200, 200, 200, 200),
        inner_radius=(500, 500, 500, 500),
    )
    d = Drawn(spec)
    assert any(w.startswith("Corner_Radius") for w in d.ring.warnings)
    assert any(w.startswith("Inner_Radius") for w in d.ring.warnings)
    assert d.px(W // 2, H // 2) == NONE  # the middle is open, the middle of each side painted
    for x, y in ((W // 2, 5), (W // 2, H - 6), (5, H // 2), (W - 6, H // 2)):
        assert d.px(x, y) == BLUE


def test_an_outer_radius_that_would_cut_through_the_opening_is_reduced() -> None:
    # thickness 8 with outer radius 60: a sharp opening corner would poke out of the arc
    d = Drawn(RingSpec(thickness=(8, 8, 8, 8), outer_radius=(60, 60, 60, 60)))
    (warning,) = d.ring.warnings
    assert warning.startswith("Corner_Radius")
    assert d.px(W // 2, H // 2) == NONE and d.px(0, 0) == NONE
    assert all(d.px(x, 4) == BLUE for x in range(40, W - 40))  # the band stays whole


def test_a_radius_within_the_ring_is_kept_without_a_warning() -> None:
    d = Drawn(RingSpec(thickness=(14, 14, 14, 14), inner_radius=(14, 14, 14, 14)))
    assert d.ring.warnings == ()


@pytest.mark.parametrize("open_side", [0, 1, 2, 3])
def test_an_open_side_has_no_band_and_the_opening_reaches_the_edge(open_side: int) -> None:
    thickness = tuple(0 if i == open_side else 10 for i in range(4))
    d = Drawn(
        RingSpec(
            thickness=thickness,  # type: ignore[arg-type]
            margin=(6, 6, 6, 6),
            outer_border=1,
            inner_border=1,
        )
    )
    centre = {0: (0, H // 2), 1: (W // 2, 0), 2: (W - 1, H // 2), 3: (W // 2, H - 1)}
    step = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}
    for side, (x, y) in centre.items():
        dx, dy = step[side]
        if side == open_side:
            # no band, no margin: from the edge on the opening is open
            assert all(d.px(x + dx * k, y + dy * k) == NONE for k in range(30))
            assert d.ring.totals[side] == 0
        else:
            # margin 6, outer border 1, fill 10, inner border 1: 18 in total
            assert d.px(x + dx * 5, y + dy * 5) == NONE
            assert d.px(x + dx * 6, y + dy * 6) == RED
            assert d.px(x + dx * 17, y + dy * 17) == GREEN
            assert d.px(x + dx * 18, y + dy * 18) == NONE
            assert d.ring.totals[side] == 18


def test_a_frame_that_leaves_no_opening_is_a_solid_fill() -> None:
    d = Drawn(RingSpec(thickness=(250, 250, 250, 250)))
    assert d.px(W // 2, H // 2) == BLUE


def test_mirrored_specs_draw_mirrored_pixels() -> None:
    left = Drawn(RingSpec(thickness=(30, 10, 10, 10), inner_radius=(12, 0, 0, 12)))
    right = Drawn(RingSpec(thickness=(10, 10, 30, 10), inner_radius=(0, 12, 12, 0)))
    for y in range(0, H, 7):
        for x in range(W):
            assert left.px(x, y) == right.px(W - 1 - x, y)


# -- melded bodies (hosted melding) ----------------------------------------------------------------


def melded(*melds: MeldSpec, **kw: object) -> Drawn:
    spec = RingSpec(
        thickness=(20, 20, 20, 20),
        inner_radius=(10, 10, 10, 10),
        melds=melds,
        **kw,  # type: ignore[arg-type]
    )
    return Drawn(spec)


def test_a_meld_grows_a_body_out_of_the_ring_into_the_opening() -> None:
    d = melded(MeldSpec("top", 100, 40, "CENTER"))
    assert d.ring.bodies[0] is not None
    body = d.ring.bodies[0]
    assert (body.x0, body.y0, body.x1, body.y1) == (150, 20, 250, 60)
    assert d.px(200, 40) == BLUE and d.px(200, 59) == BLUE  # the body is part of the ring
    assert d.px(200, 61) == NONE and d.px(140, 40) == NONE  # the opening is round it
    assert d.click(200, 40) == ["fill"]
    assert d.click(200, 90) == [] and d.click(120, 40) == []


def test_the_join_is_a_fillet_with_the_inner_radius_and_no_seam() -> None:
    d = melded(MeldSpec("top", 100, 40, "CENTER"))
    # the arc's centre is (140, 30), radius 10: the corner of the notch (149, 21) is filled
    assert d.px(149, 21) == BLUE and d.px(145, 25) == NONE  # the corner is filled, the arc round
    assert d.px(140, 30) == NONE and d.px(135, 35) == NONE
    # the fill is one piece: the band above the join and the body below it are all painted
    assert all(d.px(x, 19) == BLUE for x in range(W))
    assert all(d.px(x, 45) == BLUE for x in range(150, 250))


def test_the_bodys_own_corners_take_its_radius_and_the_corners_on_the_frame_do_not() -> None:
    d = melded(MeldSpec("top", 100, 40, "CENTER", radius=(0, 0, 8, 8)))
    assert d.px(150, 59) == NONE and d.px(249, 59) == NONE  # rounded off
    assert d.px(158, 59) == BLUE and d.px(241, 59) == BLUE
    assert d.px(150, 21) == BLUE  # the join stays whole


def test_a_body_flush_with_a_corner_removes_that_corner_of_the_opening() -> None:
    d = melded(MeldSpec("top", 100, 40, "START"))
    body = d.ring.bodies[0]
    assert body is not None and (body.x0, body.x1) == (20, 120)
    assert d.px(21, 21) == BLUE and d.px(21, 59) == BLUE  # no notch beside the body
    assert d.px(21, 61) == BLUE  # the opening's new corner, below the body, is rounded
    assert d.px(40, 80) == NONE and d.px(19, 100) == BLUE  # the left side of the ring goes on
    end = melded(MeldSpec("top", 100, 40, "END")).ring.bodies[0]
    assert end is not None and (end.x0, end.x1) == (280, 380)


@pytest.mark.parametrize(
    ("side", "probe", "outside"),
    [
        ("right", (370, 150), (330, 150)),
        ("bottom", (200, 270), (200, 220)),
        ("left", (30, 150), (70, 150)),
    ],
)
def test_a_body_grows_from_each_side(
    side: str, probe: tuple[int, int], outside: tuple[int, int]
) -> None:
    d = melded(MeldSpec(side, 40, 40, "CENTER"))
    assert d.px(*probe) == BLUE and d.px(*outside) == NONE


def test_the_inner_border_follows_the_body() -> None:
    d = melded(MeldSpec("top", 100, 40, "CENTER"), inner_border=2)
    assert d.px(200, 59) == BLUE and d.px(200, 60) == GREEN and d.px(200, 61) == GREEN
    assert d.px(200, 62) == NONE
    assert d.px(148, 40) == GREEN and d.px(147, 40) == NONE  # beside the body
    assert d.px(149, 40) == GREEN
    assert d.click(200, 61) == ["inner"]


def test_a_gap_too_narrow_for_the_border_leaves_the_border_out_with_a_warning() -> None:
    d = melded(MeldSpec("top", 357, 40, "CENTER"), inner_border=2)  # 2 px of opening each side
    assert any("too narrow" in w for w in d.ring.warnings)
    assert d.px(200, 40) == BLUE


def test_a_second_body_that_overlaps_the_first_is_not_drawn() -> None:
    d = melded(MeldSpec("top", 100, 80, "START"), MeldSpec("left", 80, 100, "START"))
    first, second = d.ring.bodies
    assert first is not None and second is None
    assert any("overlaps" in w for w in d.ring.warnings)


def test_two_bodies_on_different_sides_both_grow() -> None:
    d = melded(MeldSpec("top", 100, 40, "CENTER"), MeldSpec("bottom", 100, 40, "CENTER"))
    assert all(b is not None for b in d.ring.bodies)
    assert d.px(200, 40) == BLUE and d.px(200, 260) == BLUE and d.px(200, 150) == NONE


def test_a_body_on_a_side_with_no_thickness_is_not_drawn() -> None:
    spec = RingSpec(thickness=(20, 0, 20, 20), melds=(MeldSpec("top", 100, 40),))
    shaped = ring(spec, (W, H))
    assert shaped.bodies == (None,) and any("no thickness" in w for w in shaped.warnings)


def test_a_body_larger_than_the_opening_is_clamped_to_it() -> None:
    d = melded(MeldSpec("top", 1000, 1000, "CENTER"))
    body = d.ring.bodies[0]
    assert body is not None and (body.x0, body.x1, body.y1) == (20, 380, 280)


def test_the_reserved_zones_do_not_change_with_a_meld() -> None:
    plain = ring(RingSpec(thickness=(20, 20, 20, 20)), (W, H)).totals
    with_meld = ring(
        RingSpec(thickness=(20, 20, 20, 20), melds=(MeldSpec("top", 100, 40),)), (W, H)
    ).totals
    assert plain == with_meld == (20, 20, 20, 20)


# -- strips: where the bands are -----------------------------------------------------------------


def test_top_and_bottom_bands_own_the_corners_and_the_sides_run_between_them() -> None:
    shaped = ring(RingSpec(thickness=(10, 20, 30, 40), margin=(4, 4, 4, 4)), (W, H))
    left, top, right, bottom = shaped.bands
    assert (top.x0, top.y0, top.x1, top.y1) == (4, 4, W - 4, 24)  # the full width
    assert (bottom.x0, bottom.y0, bottom.x1, bottom.y1) == (4, H - 44, W - 4, H - 4)
    assert (left.x0, left.y0, left.x1, left.y1) == (4, 24, 14, H - 44)  # between them
    assert (right.x0, right.y0, right.x1, right.y1) == (W - 34, 24, W - 4, H - 44)


def test_a_strips_padding_is_taken_off_its_band() -> None:
    from tess_shell.surfaces.ring import padded

    shaped = ring(RingSpec(thickness=(10, 20, 30, 40)), (W, H))
    inner = padded(shaped.bands[1], (3, 4, 5, 6))
    assert (inner.x0, inner.y0, inner.x1, inner.y1) == (3, 4, W - 5, 14)
    assert padded(shaped.bands[1], (0, 30, 0, 0)).height == 0  # never negative
