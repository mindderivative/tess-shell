"""The look on real surfaces: tokens resolve into what is drawn, and a new desktop look rebuilds
the surface (headless: no compositor; the shell's manager over a stub ``App``)."""

from __future__ import annotations

import tess_dl

from tess_shell.appearance import Appearance
from tess_shell.binder.model import Expand, Length, Node, Percent, Text, TokenRef
from tess_shell.model.look import make_look
from tess_shell.model.store import ValueStore
from tess_shell.schema.look import read_stylesheet, read_theme
from tess_shell.schema.model import BarDef, MonitorDef, ShellDef
from tess_shell.surfaces.manager import SurfaceManager
from tests.test_look import THEME


class Out(str):
    width = 400
    height = 300

    @property
    def name(self) -> str:
        return str(self)


class StubApp:
    def __init__(self) -> None:
        self.windows: list[object] = []

    def outputs(self) -> list[Out]:
        return [Out("HDMI-A-1")]

    def add_window(self, window: object) -> None:
        self.windows.append(window)


def themed(**style: object) -> SurfaceManager:
    doc = tess_dl.parse(THEME, path="T_Theme.tdl").document
    assert doc is not None
    theme, _ = read_theme(doc, "T_Theme.tdl")
    assert theme is not None
    sheet_doc = tess_dl.parse(
        '---\nTDL: 0.1\nName: S\n---\nStylesheet { Rule { Selector: "Text", '
        "Foreground: $color.on_surface } }",
        path="S_Stylesheet.tdl",
    ).document
    assert sheet_doc is not None
    sheet, _ = read_stylesheet(sheet_doc, "S_Stylesheet.tdl", set())
    assert sheet is not None
    look = make_look(theme, [sheet], Appearance(scheme="dark"))
    bar = BarDef(
        "Top_Bar",
        origin=Text("x").origin,
        edge="TOP",
        width=Expand(),
        height=Length(32),
        style={"Fill": TokenRef("color.surface", "color"), **style},  # type: ignore[arg-type]
        children=(Node("Text", name="Label", props={"Text": Text("hi")}),),
    )
    shell = ShellDef("S", "S", (MonitorDef("M", bar.origin, 0, None, None, (bar,)),))
    manager = SurfaceManager(StubApp(), {}, lambda key: key, ValueStore(), look)  # type: ignore[arg-type]
    manager.plan(shell)
    manager.build()
    return manager


def test_a_themed_bar_and_the_stylesheet_reach_the_nodes() -> None:
    manager = themed()
    (surface,) = manager.surfaces
    assert surface.fill == (0x10, 0x10, 0x10, 255)  # $color.surface, dark
    label = surface.view.nodes["Label"]  # type: ignore[union-attr]
    assert label.get("fill") == (0xEE, 0xEE, 0xEE, 255)  # the stylesheet's $color.on_surface


def test_a_new_desktop_look_changes_the_bar_and_its_text_without_a_restart() -> None:
    manager = themed()
    (surface,) = manager.surfaces
    assert surface.view is not None
    label = surface.view.nodes["Label"]
    manager.set_look(manager.look.with_appearance(Appearance(scheme="light")))
    assert surface.fill == (0xFF, 0xFF, 0xFF, 255)
    assert label.get("fill") == (0x11, 0x11, 0x11, 255)
    assert (
        surface.view is not None and surface.view.nodes["Label"] is label
    )  # the same node: a diff, not a rebuild from scratch
    manager.set_look(manager.look.with_appearance(Appearance(scheme="dark")))
    assert surface.fill == (0x10, 0x10, 0x10, 255) and label.get("fill") == (0xEE, 0xEE, 0xEE, 255)


def test_an_elevation_from_the_themes_max_sizes_the_surface_and_follows_the_theme() -> None:
    manager = themed(Elevation=Percent(100))
    (surface,) = manager.surfaces
    # the theme's Max: Y 10, Blur 20 -> below the body 31 px (+1 for the blur tail), none above
    assert surface.geometry.body_margin == (0, 0, 31, 0)
    assert surface.geometry.size == (0, 32 + 31) and surface.geometry.exclusive_zone == 32


def test_a_bad_token_in_the_bars_style_is_dropped_with_a_warning_not_a_crash() -> None:
    manager = themed(Fill=TokenRef("color.nope", "color"))
    (surface,) = manager.surfaces
    assert surface.fill is None  # no fill: the key kept its default
    assert surface.view is not None  # the Bar still shows


def test_a_click_on_a_bars_block_reaches_the_managers_sink() -> None:
    from tess_shell.binder.model import Handler

    manager = themed()
    seen: list[str] = []
    manager.sink = lambda handler, key, raw: seen.append(f"{key}:{handler.action}")
    (surface,) = manager.surfaces
    assert surface.view is not None
    box = Node(
        "Rectangle",
        name="Hit",
        props={"Width": Length(10), "Height": Length(10)},
        handlers={"On_Click": Handler("go")},
    )
    surface.view.rebuild([*[e.typed for e in surface.view.entries], box])
    surface.view.window.simulate("click", node=surface.view.nodes["Hit"])
    assert seen == ["On_Click:go"]


def test_the_shadow_margin_takes_no_pointer_input_and_a_removed_shadow_gives_it_back() -> None:
    manager = themed(Elevation=Percent(100))
    (surface,) = manager.surfaces
    # the theme's Max (Y 10, Blur 20): a 31 px margin below the 32 px body of a 400 px output
    assert surface.window.get("input_region") == [(0, 0, 400, 32)]
    plain = themed()
    (flat,) = plain.surfaces
    assert flat.window.get("input_region") is None
    # the same surface with the elevation removed (what a reload does): the whole surface again
    assert flat.planned is not None
    manager._sync_body(surface, flat.planned.bar, flat.geometry, "test")
    assert surface.window.get("input_region") is None
    assert surface.window.get("size") == (0, 32)


# -- state selectors on a real Bar ------------------------------------------------------------


def hoverable(appearance: Appearance) -> SurfaceManager:
    """A Bar with a FlexBox named Btn; the sheet gives it a hovered and a pressed colour."""
    doc = tess_dl.parse(THEME, path="T_Theme.tdl").document
    assert doc is not None
    theme, _ = read_theme(doc, "T_Theme.tdl")
    sheet_doc = tess_dl.parse(
        "---\nTDL: 0.1\nName: S\n---\nStylesheet {\n"
        '  Rule { Selector: "FlexBox", Background: $color.surface }\n'
        '  Rule { Selector: "#Btn:hovered", Background: $color.primary }\n'
        '  Rule { Selector: "#Btn:pressed", Background: $color.on_surface }\n}',
        path="S_Stylesheet.tdl",
    ).document
    assert doc is not None and sheet_doc is not None
    sheet, findings = read_stylesheet(sheet_doc, "S_Stylesheet.tdl", set())
    assert sheet is not None and findings == [] and theme is not None
    bar = BarDef(
        "Top_Bar",
        origin=Text("x").origin,
        edge="TOP",
        width=Expand(),
        height=Length(32),
        children=(Node("FlexBox", name="Btn", props={"Width": Length(20), "Height": Length(20)}),),
    )
    shell = ShellDef("S", "S", (MonitorDef("M", bar.origin, 0, None, None, (bar,)),))
    look = make_look(theme, [sheet], appearance)
    manager = SurfaceManager(StubApp(), {}, lambda key: key, ValueStore(), look)  # type: ignore[arg-type]
    manager.plan(shell)
    manager.build()
    return manager


def test_a_hover_and_press_rule_from_a_stylesheet_colours_a_block_of_a_bar() -> None:
    manager = hoverable(Appearance(scheme="dark"))
    (surface,) = manager.surfaces
    assert surface.view is not None
    btn, window = surface.view.nodes["Btn"], surface.view.window
    assert btn.get("fill") == (0x10, 0x10, 0x10, 255)  # $color.surface
    window.simulate("pointer_enter", node=btn)
    assert btn.get("fill") == (0x67, 0x50, 0xA4, 255)  # $color.primary
    window.simulate("pointer_down", node=btn)
    assert btn.get("fill") == (0xEE, 0xEE, 0xEE, 255)  # $color.on_surface
    window.simulate("pointer_up", node=btn)
    assert btn.get("fill") == (0x67, 0x50, 0xA4, 255)
    window.simulate("pointer_leave")
    assert btn.get("fill") == (0x10, 0x10, 0x10, 255)


def test_a_new_desktop_look_restyles_a_block_that_is_hovered() -> None:
    manager = hoverable(Appearance(scheme="dark"))
    (surface,) = manager.surfaces
    assert surface.view is not None
    btn, window = surface.view.nodes["Btn"], surface.view.window
    window.simulate("pointer_enter", node=btn)
    manager.set_look(manager.look.with_appearance(Appearance(scheme="light")))
    assert surface.view.nodes["Btn"] is btn  # a diff, not a new node
    assert btn.get("fill") == (0x67, 0x50, 0xA4, 255)  # hovered still; Primary is the same
    window.simulate("pointer_leave")
    assert btn.get("fill") == (0xFF, 0xFF, 0xFF, 255)  # the light $color.surface, not the dark one
