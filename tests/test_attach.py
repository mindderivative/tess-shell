"""Attach_To: a Panel placed against another surface (Panel > Attachment Geometry)."""

from __future__ import annotations

import pytest
import tess_dl

from tess_shell.binder.model import Length
from tess_shell.model.expand import expand
from tess_shell.schema.findings import Finding
from tess_shell.schema.model import ShellDef
from tess_shell.schema.shell import read_module, read_shell
from tess_shell.surfaces.bar import Geometry, Rect, ZeroSize, body_rect
from tess_shell.surfaces.panel import PanelSpec, panel_geometry
from tests.shell_samples import HEADER, SVG
from tests.test_model_live import CLOCK, parse
from tests.test_panel import (
    OUT,
    manager,
    panel_errors,
    panel_of,
    read,
    surface,
)

TARGET = Rect(100, 200, 200, 32)  # a target well inside the 1000 x 800 output


def attached(attach: str, alignment: str, gap: float = 8, **kw: object) -> Geometry:
    spec = PanelSpec(
        (),
        (0, 0, 0, 0),
        Length(80),
        Length(60),
        attach=attach,
        gap=gap,
        alignment=alignment,
        **kw,  # type: ignore[arg-type]
    )
    return panel_geometry(spec, OUT, TARGET)


@pytest.mark.parametrize(
    ("attach", "alignment", "x", "y"),
    [
        ("BOTTOM", "START", 100, 240),
        ("BOTTOM", "CENTER", 160, 240),
        ("BOTTOM", "END", 220, 240),
        ("TOP", "START", 100, 132),
        ("TOP", "CENTER", 160, 132),
        ("TOP", "END", 220, 132),
        ("LEFT", "START", 12, 200),
        ("LEFT", "CENTER", 12, 186),
        ("LEFT", "END", 12, 172),
        ("RIGHT", "START", 308, 200),
        ("RIGHT", "CENTER", 308, 186),
        ("RIGHT", "END", 308, 172),
    ],
)
def test_the_panel_meets_the_named_edge_with_the_gap_and_slides_along_it(
    attach: str, alignment: str, x: int, y: int
) -> None:
    g = attached(attach, alignment)
    assert g.anchor == ("top", "left") and g.size == (80, 60)
    assert g.margin == (y, 0, 0, x)  # the body's top left corner from the output's top left
    assert g.exclusive_zone == -1  # placed from the output's edge, not from what the Bars leave


def test_a_shadow_grows_the_surface_and_the_body_still_meets_the_target() -> None:
    g = attached("BOTTOM", "START", bleed=(10, 20, 30, 40))
    assert g.size == (80 + 40 + 20, 60 + 10 + 30) and g.body_margin == (10, 20, 30, 40)
    # the body's corner is still at (100, 240): the surface starts by the bleed before it
    assert (g.margin[3] + 40, g.margin[0] + 10) == (100, 240)
    assert body_rect(g, OUT) == Rect(100, 240, 80, 60)


def test_a_panel_that_would_leave_the_output_is_moved_back_with_a_warning() -> None:
    spec = PanelSpec((), (0, 0, 0, 0), Length(80), Length(60), attach="TOP", gap=0)
    g = panel_geometry(spec, OUT, Rect(100, 20, 200, 32))  # 60 px of Panel above y = 20
    assert g.margin == (0, 0, 0, 160) and any("leave the output" in w for w in g.warnings)


def test_an_attached_panel_needs_a_size_and_a_target_place() -> None:
    with pytest.raises(ZeroSize):
        panel_geometry(
            PanelSpec((), (0, 0, 0, 0), Length(0), Length(60), attach="TOP"), OUT, TARGET
        )
    with pytest.raises(ZeroSize):
        panel_geometry(PanelSpec((), (0, 0, 0, 0), Length(9), Length(60), attach="TOP"), OUT, None)


def test_body_rect_follows_the_anchors_the_margins_and_the_transparent_margin() -> None:
    bar = Geometry(("top", "left", "right"), (0, 40), (8, 8, 0, 8), 48)
    assert body_rect(bar, OUT) == Rect(8, 8, 984, 40)
    corner = Geometry(("bottom", "right"), (200, 100), (0, 24, 30, 0), -1)
    assert body_rect(corner, OUT) == Rect(776, 670, 200, 100)
    centred = Geometry((), (200, 100), (0, 0, 0, 0), -1)
    assert body_rect(centred, OUT) == Rect(400, 350, 200, 100)
    shadowed = Geometry(("top", "left"), (200, 100), (10, 0, 0, 10), -1, body_margin=(4, 4, 4, 4))
    assert body_rect(shadowed, OUT) == Rect(14, 14, 192, 92)


# -- the keys ---------------------------------------------------------------------------------


def test_the_attach_keys_are_typed_and_alignment_defaults_to_centre() -> None:
    p = panel_of("Panel { Name: P, Width: 9, Height: 9, Attach_To: Top_Bar, Attach: BOTTOM }")
    assert (p.attach_to, p.attach, p.gap, p.alignment) == ("Top_Bar", "BOTTOM", 0, "CENTER")
    p = panel_of(
        "Panel { Name: P, Width: 9, Height: 9, Attach_To: Top_Bar, Attach: LEFT, Gap: 8, "
        "Alignment: END }"
    )
    assert (p.attach, p.gap, p.alignment) == ("LEFT", 8, "END")


@pytest.mark.parametrize(
    ("snippet", "rule"),
    [
        ("Panel { Name: P, Width: 9, Height: 9, Attach_To: Top_Bar }", "missing-key"),
        ("Panel { Name: P, Width: 9, Height: 9, Attach: LEFT }", "attach-orphan"),
        ("Panel { Name: P, Width: 9, Height: 9, Gap: 4 }", "attach-orphan"),
        (
            "Panel { Name: P, Width: 9, Height: 9, Attach_To: Top_Bar, Attach: LEFT, Anchor: TOP }",
            "attach-placed",
        ),
        (
            "Panel { Name: P, Width: 9, Height: 9, Attach_To: Top_Bar, Attach: LEFT, "
            "Inset: [1, 1, 1, 1] }",
            "attach-placed",
        ),
        (
            "Panel { Name: P, Width: 9, Height: 9, Attach_To: Top_Bar, Attach: MIDDLE }",
            "bad-value",
        ),
        (
            "Panel { Name: P, Width: 9, Height: 9, Attach_To: Nowhere, Attach: LEFT }",
            "attach-unknown",
        ),
        ("Panel { Name: P, Width: 9, Height: 9, Attach_To: P, Attach: LEFT }", "attach-self"),
        ("Panel { Name: P, Width: 9, Height: 9, Attach_To: 12, Attach: LEFT }", "bad-name"),
    ],
)
def test_a_bad_attachment_is_an_error_at_load(snippet: str, rule: str) -> None:
    assert any(f.rule == rule for f in panel_errors(snippet))


def test_a_target_has_one_panel_and_a_chain_must_end_at_a_placed_surface() -> None:
    two = (
        "Panel { Name: A, Width: 9, Height: 9, Attach_To: Top_Bar, Attach: BOTTOM }\n"
        "Panel { Name: B, Width: 9, Height: 9, Attach_To: Top_Bar, Attach: TOP }"
    )
    assert any(f.rule == "attach-duplicate" for f in panel_errors(two))
    circle = (
        "Panel { Name: A, Width: 9, Height: 9, Attach_To: B, Attach: BOTTOM }\n"
        "Panel { Name: B, Width: 9, Height: 9, Attach_To: A, Attach: RIGHT }"
    )
    assert any(f.rule == "attach-cycle" for f in panel_errors(circle))


def test_a_target_on_another_monitor_is_an_error() -> None:
    body = (
        "Shell {\n"
        " Monitor { Name: One, Index: 0, Children { Bar { Name: Bar_One, Edge: TOP, Width: EXPAND,"
        " Height: 32 } } }\n"
        " Monitor { Name: Two, Index: 1, Children { Panel { Name: P, Width: 9, Height: 9,"
        " Attach_To: Bar_One, Attach: BOTTOM } } }\n}\n"
    )
    shell, findings = read(body)
    assert shell is None and any(f.rule == "attach-other-monitor" for f in findings)


# -- placing and following the target ---------------------------------------------------------

MENU = (
    "Panel { Name: Menu, Layer: OVERLAY, Width: 120, Height: 90, Attach_To: Top_Bar, "
    "Attach: BOTTOM, Gap: 8, Alignment: START, Visible: false, Children { FlexBox { } } }\n"
    "Panel { Name: Side, Layer: OVERLAY, Width: 50, Height: 40, Attach_To: Menu, Attach: RIGHT, "
    "Gap: 4, Alignment: START, Visible: false, Children { FlexBox { } } }"
)


def test_an_attached_panel_is_placed_from_its_targets_rectangle_and_a_chain_in_order() -> None:
    m = manager(panel=MENU)
    menu, side = surface(m, "Menu"), surface(m, "Side")
    # the 1000 px Bar is at y 0..32: the Menu sits 8 below it, its left edge on the Bar's
    assert menu.geometry.margin == (40, 0, 0, 0)
    # the Side Panel is 4 right of the Menu (which is 120 wide) and level with its top
    assert side.geometry.margin == (40, 0, 0, 124)


def test_a_panel_opens_only_while_its_target_is_open_and_closes_with_it() -> None:
    m = manager(panel=MENU)
    menu, side = surface(m, "Menu"), surface(m, "Side")
    m.show(side)
    assert side.hidden is True  # the Menu it is attached to is hidden
    m.show(menu)
    m.show(side)
    assert menu.hidden is False and side.hidden is False
    m.hide(menu)
    assert menu.hidden is True and side.hidden is True


def test_a_panel_whose_target_was_not_created_is_not_created() -> None:
    odd = (
        "Panel { Name: Flat, Width: 0, Height: 9, Anchor: TOP, Visible: false }\n"
        "Panel { Name: Under, Width: 9, Height: 9, Attach_To: Flat, Attach: BOTTOM, "
        "Visible: false }"
    )
    m = manager(panel=odd)
    assert {s.name for s in m.surfaces} == {"Top_Bar"}


def test_a_shadow_on_the_attached_panel_does_not_move_its_body() -> None:
    shadowed = MENU.replace(
        "Visible: false, Children { FlexBox { } } }\nPanel",
        "Visible: false, Style { Elevation: 8% }, Children { FlexBox { } } }\nPanel",
        1,
    )
    m = manager(panel=shadowed)
    menu = surface(m, "Menu")
    assert menu.geometry.body_margin != (0, 0, 0, 0)  # the shadow made the surface larger
    assert body_rect(menu.geometry, OUT).x == 0 and body_rect(menu.geometry, OUT).y == 40


# -- a module in a Bar as the target ----------------------------------------------------------


def test_a_module_target_slides_along_the_module_and_clears_the_bar() -> None:
    bar = Rect(0, 0, 1000, 32)
    module = Rect(300, 4, 60, 20)
    spec = PanelSpec((), (0, 0, 0, 0), Length(80), Length(60), attach="BOTTOM", gap=8)
    start = PanelSpec(
        (), (0, 0, 0, 0), Length(80), Length(60), attach="BOTTOM", gap=8, alignment="START"
    )
    assert panel_geometry(start, OUT, module, bar).margin == (40, 0, 0, 300)  # Bar bottom + 8
    assert panel_geometry(spec, OUT, module, bar).margin == (40, 0, 0, 290)  # centred on it


def test_a_module_name_is_a_valid_target_only_in_a_bar_of_the_same_monitor() -> None:
    module, _ = read_module(parse(CLOCK, "Clock", "x"), "Clock_Module.tdl")
    assert module is not None

    def load(body: str) -> tuple[ShellDef | None, list[Finding]]:
        doc = tess_dl.parse(HEADER + body, path="S.tdl").document
        assert doc is not None
        return read_shell(doc, "S.tdl", lambda p: SVG, {"Clock": module})

    ok = (
        "Shell { Monitor { Name: M, Index: 0, Children {\n"
        " Bar { Name: B, Edge: TOP, Width: EXPAND, Height: 32,\n"
        "  Children { Clock { Name: Tick } } }\n"
        " Panel { Name: P, Width: 9, Height: 9, Attach_To: Tick, Attach: BOTTOM }\n} } }"
    )
    shell, findings = load(ok)
    assert shell is not None, findings
    bar = shell.monitors[0].surfaces[0]
    expanded = expand(
        bar.children,
        "S.M.B",
        {"Clock": module},
        lambda p: "u",
        "M",
        attach_targets=frozenset({"Tick"}),
    )
    assert expanded.targets == {"Tick": "Clock@u/#target"}
    unknown, findings = load(ok.replace("Attach_To: Tick", "Attach_To: Tock"))
    assert unknown is None and any(f.rule == "attach-unknown" for f in findings)
