"""The Panel: its keys in a shell file, its geometry, and show, hide and toggle (Panel; D44)."""

from __future__ import annotations

import pytest
import tess_dl

from tess_shell.appearance import Appearance
from tess_shell.binder.model import Length, Percent
from tess_shell.model.look import make_look
from tess_shell.model.store import ValueStore
from tess_shell.schema.findings import Finding
from tess_shell.schema.look import read_theme
from tess_shell.schema.model import PanelDef, ShellDef
from tess_shell.schema.shell import read_shell
from tess_shell.surfaces.bar import ZeroSize, input_region
from tess_shell.surfaces.manager import Surface, SurfaceManager
from tess_shell.surfaces.panel import PanelSpec, panel_geometry
from tests.shell_samples import HEADER, SVG
from tests.test_look import THEME

OUT = (1000, 800)

SHELL = (
    "Shell { Monitor { Name: Main, Index: 0, Children {\n"
    "  Bar { Name: Top_Bar, Edge: TOP, Width: EXPAND, Height: 32, Children {\n"
    "    Rectangle { Name: Btn, Width: 20, Height: 20, %s } } }\n"
    "  %s\n"
    "} } }\n"
)
LAUNCHER = (
    "Panel { Name: Launcher, Layer: OVERLAY, Keyboard: EXCLUSIVE, Width: 600, Height: 400, "
    "Visible: false, Children { FlexBox { Name: Inside } } }"
)


def read(body: str) -> tuple[ShellDef | None, list[Finding]]:
    result = tess_dl.parse(HEADER + body, path="Shells/Main_Shell.tdl")
    assert not result.errors and result.document is not None
    return read_shell(result.document, "Shells/Main_Shell.tdl", lambda p: SVG)


def panel_of(snippet: str) -> PanelDef:
    shell, findings = read(SHELL % ("", snippet))
    assert shell is not None, findings
    (panel,) = [s for s in shell.monitors[0].surfaces if isinstance(s, PanelDef)]
    return panel


def panel_errors(snippet: str) -> list[Finding]:
    shell, findings = read(SHELL % ("", snippet))
    assert shell is None
    return [f for f in findings if f.severity == "error"]


# -- the keys ---------------------------------------------------------------------------------


def test_every_built_panel_key_is_typed() -> None:
    p = panel_of(
        "Panel { Name: P, Layer: OVERLAY, Anchor: [TOP, RIGHT], Inset: [1, 2, 3, 4], Width: 300, "
        "Height: 50%, Keyboard: ON_DEMAND, Input_Region: [], Visible: false, Hide_After: 1500, "
        'Style { Fill: "#102030", Elevation: 20% } }'
    )
    assert (p.name, p.layer, p.anchor, p.inset) == ("P", "OVERLAY", ("TOP", "RIGHT"), (1, 2, 3, 4))
    assert p.width == Length(300) and p.height == Percent(50)
    assert (p.keyboard, p.input, p.visible, p.hide_after) == ("ON_DEMAND", "NONE", False, 1500)
    assert "Fill" in p.style and "Elevation" in p.style


def test_the_defaults_are_the_top_layer_no_keyboard_whole_surface_shown() -> None:
    p = panel_of("Panel { Name: P, Width: 10, Height: 10 }")
    assert (p.layer, p.anchor, p.keyboard, p.input, p.visible, p.hide_after) == (
        "TOP",
        (),
        "NONE",
        "WHOLE",
        True,
        None,
    )


@pytest.mark.parametrize(
    ("snippet", "rule", "needle"),
    [
        ("Panel { Width: 10, Height: 10 }", "missing-key", "Name"),
        ("Panel { Name: P, Height: 10 }", "missing-key", "Width"),
        ("Panel { Name: P, Width: 10, Height: 10, Layer: MIDDLE }", "bad-value", "BOTTOM"),
        ("Panel { Name: P, Width: 10, Height: 10, Keyboard: ALWAYS }", "bad-value", "EXCLUSIVE"),
        ("Panel { Name: P, Width: 10, Height: 10, Anchor: [TOP, TOP] }", "bad-value", "twice"),
        ("Panel { Name: P, Width: 10, Height: 10, Anchor: MIDDLE }", "bad-value", "TOP, BOTTOM"),
        ("Panel { Name: P, Width: AUTO, Height: 10 }", "not-built", "AUTO"),
        ("Panel { Name: P, Width: 10, Height: 10, Attach_To: Top_Bar }", "not-built", "Attach_To"),
        ("Panel { Name: P, Width: 10, Height: 10, Movable: true }", "not-built", "Movable"),
        ("Panel { Name: P, Width: 10, Height: 10, Exclusive_Zone: 4 }", "not-built", "Exclusive"),
        (
            "Panel { Name: P, Width: 10, Height: 10, Input_Region: [[0, 0, 4, 4]] }",
            "not-built",
            "rect",
        ),
        ("Panel { Name: P, Width: 10, Height: 10, Colour: 1 }", "unknown-key", "Panel"),
        ("Panel { Name: P, Width: 10, Height: 10, Hide_Aftr: 5 }", "unknown-key", "Hide_After"),
    ],
)
def test_a_bad_panel_is_reported_at_its_key(snippet: str, rule: str, needle: str) -> None:
    found = panel_errors(snippet)
    assert any(f.rule == rule and needle in f.message + f.hint for f in found), found
    assert all(f.line > 0 for f in found)


def test_a_cosmetic_key_not_built_is_a_warning_not_an_error() -> None:
    shell, findings = read(SHELL % ("", "Panel { Name: P, Width: 10, Height: 10, Animation { } }"))
    assert shell is not None
    assert [f.severity for f in findings] == ["warning"]


# -- geometry ---------------------------------------------------------------------------------


def spec(**kw: object) -> PanelSpec:
    base: dict[str, object] = {
        "anchor": (),
        "inset": (0, 0, 0, 0),
        "width": Length(300),
        "height": Length(200),
    }
    return PanelSpec(**{**base, **kw})  # type: ignore[arg-type]


def test_an_anchored_panel_takes_its_inset_as_tres_margin_in_tres_order() -> None:
    g = panel_geometry(spec(anchor=("TOP", "RIGHT"), inset=(1, 40, 24, 3)), OUT)
    assert g.anchor == ("top", "right") and g.size == (300, 200)
    assert g.margin == (40, 24, 0, 0)  # top, right, bottom, left; unanchored sides give none
    assert g.exclusive_zone == 0 and g.body_margin == (0, 0, 0, 0)


def test_an_inset_on_a_side_with_no_anchor_is_ignored_with_a_warning() -> None:
    g = panel_geometry(spec(anchor=("TOP",), inset=(9, 4, 0, 0)), OUT)
    assert g.margin == (4, 0, 0, 0) and any("left" in w for w in g.warnings)


def test_a_floating_panel_has_no_anchor_and_a_percentage_is_of_the_output() -> None:
    g = panel_geometry(spec(width=Percent(50), height=Percent(25)), OUT)
    assert g.anchor == () and g.size == (500, 200) and g.margin == (0, 0, 0, 0)


def test_a_size_of_zero_stretches_between_two_opposite_anchors_and_is_refused_otherwise() -> None:
    g = panel_geometry(spec(anchor=("LEFT", "RIGHT"), width=Length(0), inset=(10, 0, 10, 0)), OUT)
    assert g.size == (0, 200) and g.margin[1] == 10 and g.margin[3] == 10
    with pytest.raises(ZeroSize, match="width"):
        panel_geometry(spec(anchor=("LEFT",), width=Length(0)), OUT)


def test_a_shadow_grows_the_surface_and_the_body_keeps_its_place() -> None:
    g = panel_geometry(
        spec(anchor=("TOP", "RIGHT"), inset=(0, 40, 24, 0), bleed=(20, 20, 30, 20)), OUT
    )
    assert g.size == (300 + 20 + 20, 200 + 20 + 30)
    assert g.margin == (40 - 20, 24 - 20, 0, 0)  # the body is still 40 px down and 24 px in
    assert g.body_margin == (20, 20, 30, 20)
    assert input_region(g, OUT) == [(20, 20, 300, 200)]  # the shadow takes no pointer


def test_a_floating_panel_gets_the_same_margin_on_both_sides_so_it_stays_centred() -> None:
    g = panel_geometry(spec(bleed=(10, 30, 50, 20)), OUT)
    assert g.body_margin == (50, 30, 50, 30) and g.size == (300 + 60, 200 + 100)


# -- show, hide and toggle on a real window (headless) ----------------------------------------


class Out(str):
    width, height = OUT

    @property
    def name(self) -> str:
        return str(self)


class StubApp:
    def outputs(self) -> list[Out]:
        return [Out("HDMI-A-1")]

    def add_window(self, window: object) -> None:
        pass


def manager(handlers: str = "", panel: str = LAUNCHER) -> SurfaceManager:
    shell, findings = read(SHELL % (handlers, panel))
    assert shell is not None, findings
    doc = tess_dl.parse(THEME, path="T_Theme.tdl").document
    assert doc is not None
    theme, _ = read_theme(doc, "T_Theme.tdl")
    assert theme is not None
    look = make_look(theme, [], Appearance())
    m = SurfaceManager(StubApp(), {}, lambda key: key, ValueStore(), look)  # type: ignore[arg-type]
    m.plan(shell)
    m.build()
    return m


def surface(m: SurfaceManager, name: str) -> Surface:
    return next(s for s in m.surfaces if s.name == name)


def test_a_panel_with_visible_false_opens_hidden_and_takes_nothing() -> None:
    s = surface(manager(), "Launcher")
    assert s.hidden is True
    assert s.window.get("input_region") == [] and s.window.get("keyboard") == "none"
    assert s.window.get("layer") == "overlay"


def test_show_gives_back_the_keyboard_and_the_surface_and_hide_takes_them_away() -> None:
    m = manager()
    s = surface(m, "Launcher")
    m.show(s)
    assert s.hidden is False
    assert s.window.get("keyboard") == "exclusive" and s.window.get("input_region") is None
    assert s.view is not None and "Inside" in s.view.nodes  # the same tree, nothing rebuilt
    m.hide(s)
    assert s.hidden is True and s.window.get("keyboard") == "none"
    assert s.window.get("input_region") == []
    assert "Inside" in s.view.nodes  # hidden is not closed: the tree is kept


def test_an_osd_with_an_empty_input_region_passes_clicks_even_when_shown() -> None:
    m = manager(panel="Panel { Name: Osd, Width: 100, Height: 40, Input_Region: [] }")
    s = surface(m, "Osd")
    assert s.hidden is False and s.window.get("input_region") == []
    m.hide(s)
    m.show(s)
    assert s.window.get("input_region") == []  # shown again: still click-through


def test_a_click_on_a_blocks_show_hide_and_toggle_handler_reaches_the_panel() -> None:
    handlers = "On_Click { Action: Toggle, Target: Launcher }"
    m = manager(handlers)
    m.sink = lambda handler, key, raw: m.run_builtin(handler)
    bar = surface(m, "Top_Bar")
    assert bar.view is not None
    launcher = surface(m, "Launcher")
    assert launcher.hidden
    bar.view.window.simulate("click", node=bar.view.nodes["Btn"])
    assert launcher.hidden is False
    bar.view.window.simulate("click", node=bar.view.nodes["Btn"])
    assert launcher.hidden is True


def test_an_action_naming_no_panel_is_an_error_with_the_nearest_names() -> None:
    m = manager("On_Click { Action: Show, Target: Launchr }")
    bar = surface(m, "Top_Bar")
    assert bar.view is None  # the Bar did not bind: the handler is wrong
    (planned,) = [p for p in m._planned if p.bar.name == "Top_Bar"]
    (error,) = planned.expanded.errors
    assert "no Panel named Launchr" in error.message and "Launcher" in error.hint


def test_escape_hides_a_panel_that_takes_the_keyboard_and_not_one_that_does_not() -> None:
    m = manager()
    s = surface(m, "Launcher")
    m.show(s)
    s.window.simulate("key_down", node=s.window.root, key="escape")
    assert s.hidden is True
    m2 = manager(panel="Panel { Name: Quiet, Width: 100, Height: 40 }")
    q = surface(m2, "Quiet")
    q.window.simulate("key_down", node=q.window.root, key="escape")
    assert q.hidden is False  # Keyboard: NONE never sees the key


def test_hide_and_show_are_idempotent() -> None:
    m = manager()
    s = surface(m, "Launcher")
    m.hide(s)
    m.hide(s)
    m.show(s)
    m.show(s)
    assert s.hidden is False
