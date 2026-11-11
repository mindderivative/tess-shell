"""Strips and melded Panels hosted in the Frame's painter: where they sit, that module uses in
them get live values, and that reload, the look and a new output size reach them (headless: the
shell's manager over a stub ``App``; the painter is a real tre window)."""

from __future__ import annotations

from typing import Any

import tess_dl

from tess_shell.appearance import Appearance
from tess_shell.binder.model import Handler
from tess_shell.model.expand import Expanded
from tess_shell.model.look import make_look
from tess_shell.model.store import ValueStore
from tess_shell.schema.look import read_theme
from tess_shell.schema.model import ModuleDef, ShellDef
from tess_shell.schema.shell import read_module, read_shell
from tess_shell.surfaces.frame import wants_keyboard
from tess_shell.surfaces.manager import SurfaceManager
from tests.shell_samples import HEADER
from tests.test_frame import StubApp, only
from tests.test_look import THEME

BLUE, RED, GREEN, NONE = (0, 0, 255, 255), (255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 0, 0)

LABEL = """
Module {
    Params { size { Type: number, Default: 14 } }
    FlexBox {
        Children {
            Rectangle { Name: Dot, Width: 10, Height: 10, Fill: "#ff0000" }
            Text { Name: Face, Text: {{ time }}, Style { Foreground: "#ffffff" } }
        }
    }
}
"""


def module() -> dict[str, ModuleDef]:
    result = tess_dl.parse("---\nTDL: 0.1\nName: Label\n---\n" + LABEL, path="Label_Module.tdl")
    assert result.document is not None
    found, findings = read_module(result.document, "Label_Module.tdl")
    assert found is not None, findings
    return {"Label": found}


def shell_of(frame: str, extra: str = "") -> ShellDef:
    body = f"Shell {{ Monitor {{ Name: Main, Index: 0, Children {{ {frame} {extra} }} }} }}"
    result = tess_dl.parse(HEADER + body, path="Shells/Main_Shell.tdl")
    assert result.document is not None and not result.errors
    shell, findings = read_shell(result.document, "Shells/Main_Shell.tdl", lambda _: "", module())
    assert shell is not None, findings
    return shell


def look() -> Any:
    doc = tess_dl.parse(THEME, path="T_Theme.tdl").document
    assert doc is not None
    theme, _ = read_theme(doc, "T_Theme.tdl")
    assert theme is not None
    return make_look(theme, [], Appearance(scheme="dark"))


def started(frame: str, extra: str = "") -> tuple[SurfaceManager, StubApp, ValueStore]:
    app, store = StubApp(), ValueStore()
    manager = SurfaceManager(app, module(), lambda key: key[-1], store, look(), blend_mode="SRGB")  # type: ignore[arg-type]
    for use in manager.plan(shell_of(frame, extra)):
        store.add_use(use.module, use.key)
    manager.build()
    painter = only(manager).painter
    painter.resize(*app.size)
    return manager, app, store


def reload(manager: SurfaceManager, frame: str, extra: str = "") -> None:
    checked = manager.check(shell_of(frame, extra), module())
    assert checked is not None
    manager.apply(checked[0], module(), checked[1])


def pixels(manager: SurfaceManager) -> Any:
    state = only(manager)
    state.painter.resize(*(int(v) for v in state.size))
    rgba, w, _ = state.painter.snapshot()

    def px(x: int, y: int) -> tuple[int, ...]:
        i = (y * w + x) * 4
        return tuple(rgba[i : i + 4])

    return px


def box(manager: SurfaceManager, name: str) -> tuple[float, float, float, float]:
    host = next(h for h in only(manager).hosts.values() if h.plan.name == name)
    c = host.container
    dx, dy = (host.clip.get("left"), host.clip.get("top")) if host.clip is not None else (0, 0)
    return (c.get("left") + dx, c.get("top") + dy, c.get("width"), c.get("height"))


BG = 'Style { Background: "#0000ff" }'
STRIPS = (
    f"Frame {{ Name: F, Thickness: [20, 30, 20, 20], Margin: 4, {BG}, Edges {{ "
    "Top { Padding: [6, 2, 6, 2], Children { "
    'Rectangle { Name: TopDot, Width: 50, Height: 10, Fill: "#ff0000" } } }, '
    'Left { Children { Rectangle { Name: A, Width: 10, Height: 20, Fill: "#ff0000" }, '
    'Rectangle { Name: B, Width: 10, Height: 20, Fill: "#00ff00" } } } } }'
)


def test_the_top_strip_owns_the_corners_and_the_left_strip_runs_between_the_bands() -> None:
    manager, _, _ = started(STRIPS)
    # the top band: the full width (inside the 4 px margin), 30 high; padding 6, 2, 6, 2
    assert box(manager, "F.Top") == (4 + 6, 4 + 2, 400 - 8 - 12, 30 - 4)
    # the left band: 20 wide, from below the top band to the bottom band (20 high)
    assert box(manager, "F.Left") == (4, 4 + 30, 20, 300 - 8 - 30 - 20)


def test_a_strips_children_are_drawn_in_its_band_and_a_side_strip_stacks_them_vertically() -> None:
    manager, _, _ = started(STRIPS)
    px = pixels(manager)
    assert px(10, 6) == RED and px(59, 15) == RED and px(61, 15) == BLUE  # the top strip's dot
    # left strip: two 20 px high children one below the other, from y = 34
    assert px(5, 40) == RED and px(5, 60) == GREEN and px(5, 80) == BLUE
    assert px(15, 40) == BLUE  # only 10 px wide


def test_every_strip_is_a_surface_of_the_painter_with_its_own_key() -> None:
    manager, _, _ = started(STRIPS)
    hosted = manager.every_surface()[len(manager.surfaces) :]
    assert sorted(s.name for s in hosted) == ["F.Left", "F.Top"]
    painter = only(manager).painter
    assert all(s.window is painter and s.view is not None and not s.hidden for s in hosted)
    assert sorted(s.key for s in hosted) == ["Main_Shell.Main.F.Left", "Main_Shell.Main.F.Top"]


def test_a_module_use_in_a_strip_gets_live_values() -> None:
    manager, _, store = started(
        f"Frame {{ Name: F, Thickness: 30, {BG}, "
        "Edges { Top { Children { Label { Name: L } } } } }"
    )
    (key,) = [k for k in store.values]
    assert key == "Label@L"
    host = only(manager).hosts["Main_Shell.Main.F.Top"].surface
    assert host.view is not None
    face = host.view.nodes["Label@L/Face"]
    store.send("Label", key, "time", "10:00")
    manager.on_change(store.flush())
    assert face.get("text") == "10:00"
    store.send("Label", key, "time", "10:01")
    manager.on_change(store.flush())
    assert face.get("text") == "10:01" and host.view.nodes["Label@L/Face"] is face


def test_a_reload_keeps_the_painter_and_the_strip_nodes_and_changes_what_differs() -> None:
    manager, app, _ = started(STRIPS)
    state = only(manager)
    painter = state.painter
    top = state.hosts["Main_Shell.Main.F.Top"]
    dot = top.surface.view.nodes["TopDot"]
    reload(
        manager,
        STRIPS.replace("Width: 50", "Width: 70").replace(
            "Thickness: [20, 30, 20, 20]", "Thickness: [20, 40, 20, 20]"
        ),
    )
    assert only(manager) is state and state.painter is painter and len(app.windows) == 5
    assert state.hosts["Main_Shell.Main.F.Top"] is top and top.surface.view.nodes["TopDot"] is dot
    assert dot.get("width") == 70
    assert box(manager, "F.Top")[3] == 40 - 4  # the thicker band, less the padding
    assert state.reservers["top"].get("exclusive_zone") == 40 + 4


def test_a_reload_adds_and_removes_strips() -> None:
    manager, _, _ = started(STRIPS)
    state = only(manager)
    assert set(state.hosts) == {"Main_Shell.Main.F.Top", "Main_Shell.Main.F.Left"}
    only_bottom = (
        f"Frame {{ Name: F, Thickness: 20, {BG}, "
        "Edges { Bottom { Children { Spacer { } } } } }"
    )
    reload(manager, only_bottom)
    assert set(state.hosts) == {"Main_Shell.Main.F.Bottom"}
    assert [s.name for s in manager.every_surface()[len(manager.surfaces) :]] == ["F.Bottom"]
    reload(manager, "Frame { Name: F, Thickness: 20 }")
    assert state.hosts == {} and manager.frames.host_surfaces() == []


def test_a_new_look_rebuilds_the_strips_by_the_keyed_diff() -> None:
    frame = (
        "Frame { Name: F, Thickness: 30, Style { Background: $color.surface }, Edges { Top { "
        "Children { Rectangle { Name: Dot, Width: 20, Height: 10, Fill: $color.on_surface } } } } }"
    )
    manager, _, _ = started(frame)
    dot = only(manager).hosts["Main_Shell.Main.F.Top"].surface.view.nodes["Dot"]
    assert dot.get("fill") == (0xEE, 0xEE, 0xEE, 255)
    manager.set_look(manager.look.with_appearance(Appearance(scheme="light")))
    assert dot.get("fill") == (0x11, 0x11, 0x11, 255)
    assert only(manager).hosts["Main_Shell.Main.F.Top"].surface.view.nodes["Dot"] is dot


def test_a_new_output_size_places_the_strips_again() -> None:
    manager, app, _ = started(STRIPS)
    app.size = (640, 480)
    reload(manager, STRIPS)
    assert box(manager, "F.Top")[2] == 640 - 8 - 12
    assert box(manager, "F.Left")[3] == 480 - 8 - 30 - 20


def test_hiding_the_frame_drops_the_strips_and_showing_builds_them_again() -> None:
    manager, _, _ = started(STRIPS)
    state = only(manager)
    manager.run_builtin(Handler("Hide", {"Target": "F"}, builtin=True))
    assert state.hosts == {} and manager.every_surface() == manager.surfaces
    manager.run_builtin(Handler("Show", {"Target": "F"}, builtin=True))
    assert set(state.hosts) == {"Main_Shell.Main.F.Top", "Main_Shell.Main.F.Left"}
    assert pixels(manager)(10, 6) == RED


def test_a_strip_with_a_module_use_starts_the_module_through_the_planned_uses() -> None:
    app, store = StubApp(), ValueStore()
    manager = SurfaceManager(app, module(), lambda key: key[-1], store, look(), blend_mode="SRGB")  # type: ignore[arg-type]
    uses = manager.plan(
        shell_of(
            "Frame { Name: F, Thickness: 30, Edges { Left { Children { Label { Name: A } } } } }"
        )
    )
    assert [u.key for u in uses] == ["Label@A"]


def test_the_painters_keyboard_is_none_unless_a_hosted_tree_holds_a_text_input() -> None:
    manager, _, _ = started(STRIPS)
    assert only(manager).painter.get("keyboard") == "none"
    from tess_shell.binder.model import Node

    assert not wants_keyboard(Expanded(nodes=[Node("Box", children=(Node("Text"),))]))
    assert wants_keyboard(Expanded(nodes=[Node("Box", children=(Node("TextField"),))]))


# -- melded Panels --------------------------------------------------------------------------------

TAB = (
    "Panel { Name: Tab, Meld: true, Attach_To: F, Attach: TOP, Alignment: START, Length: 120, "
    'Depth: 40, Children { Rectangle { Name: Dot, Width: 20, Height: 20, Fill: "#ff0000" } } }'
)
RING = f"Frame {{ Name: F, Thickness: 20, Inner_Radius: 8, {BG} }}"


def test_a_melded_panel_is_a_body_of_the_ring_with_its_content_in_it() -> None:
    manager, app, _ = started(RING, TAB)
    assert len(app.windows) == 5  # no window of its own
    assert box(manager, "Tab") == (20, 20, 120, 40)
    px = pixels(manager)
    assert px(100, 50) == BLUE and px(25, 25) == RED  # the body is in the ring's colour
    assert px(100, 70) == NONE and px(200, 100) == NONE  # the opening is round it
    # the Panel's Surface is the painter's, for popups and the manager's change paths
    tab = next(s for s in manager.every_surface() if s.name == "Tab")
    assert tab.window is only(manager).painter and not tab.hidden and tab.view is not None


def test_a_melded_panel_hides_and_shows_with_the_shells_actions() -> None:
    manager, _, _ = started(RING, TAB)
    px = pixels(manager)
    assert px(100, 50) == BLUE
    manager.run_builtin(Handler("Hide", {"Target": "Tab"}, builtin=True))
    px = pixels(manager)
    assert px(100, 50) == NONE and px(100, 25) == NONE  # the ring closes up under the band
    assert px(100, 10) == BLUE
    tab = next(s for s in manager.every_surface() if s.name == "Tab")
    assert tab.hidden
    manager.run_builtin(Handler("Toggle", {"Target": "Tab"}, builtin=True))
    assert pixels(manager)(100, 50) == BLUE and not tab.hidden


def test_a_melded_panel_with_visible_false_starts_hidden_and_a_reload_keeps_a_hide() -> None:
    manager, _, _ = started(RING, TAB.replace("Meld: true,", "Meld: true, Visible: false,"))
    assert pixels(manager)(100, 50) == NONE
    manager.run_builtin(Handler("Show", {"Target": "Tab"}, builtin=True))
    assert pixels(manager)(100, 50) == BLUE
    reload(manager, RING, TAB.replace("Meld: true,", "Meld: true, Visible: false,"))
    assert (
        pixels(manager)(100, 50) == BLUE
    )  # the file did not change Visible: the run-time state stands
    reload(manager, RING, TAB)
    assert pixels(manager)(100, 50) == BLUE


def test_a_reload_changes_a_melded_panels_size_and_side_without_a_new_painter() -> None:
    manager, app, _ = started(RING, TAB)
    painter = only(manager).painter
    reload(
        manager,
        RING,
        TAB.replace("Depth: 40", "Depth: 80").replace("Attach: TOP", "Attach: LEFT"),
    )
    assert only(manager).painter is painter and len(app.windows) == 5
    assert box(manager, "Tab") == (
        20,
        20,
        80,
        120,
    )  # on the left: Depth 80 across, Length 120 along


def test_the_hosted_content_of_a_melded_panel_follows_the_look() -> None:
    manager, _, _ = started(
        "Frame { Name: F, Thickness: 20, Style { Background: $color.surface } }",
        TAB.replace('Fill: "#ff0000"', "Fill: $color.on_surface"),
    )
    dot = next(h for h in only(manager).hosts.values() if h.plan.name == "Tab").surface.view.nodes[
        "Dot"
    ]
    assert dot.get("fill") == (0xEE, 0xEE, 0xEE, 255)
    manager.set_look(manager.look.with_appearance(Appearance(scheme="light")))
    assert dot.get("fill") == (0x11, 0x11, 0x11, 255)


def test_an_unknown_show_target_is_still_left_to_the_panels() -> None:
    manager, _, _ = started(RING, TAB)
    assert manager.frames.run("Hide", "Nope") is False
    assert manager.frames.names() == {"F", "Tab"}


def test_a_click_on_a_block_in_a_strip_toggles_the_melded_panel() -> None:
    strips = RING.replace(
        "Inner_Radius: 8,",
        "Inner_Radius: 8, Edges { Top { Children { Rectangle { Name: Btn, Width: 30, Height: 10,"
        " On_Click { Action: Toggle, Target: Tab } } } } },",
    )
    manager, _, _ = started(strips, TAB)
    manager.sink = lambda handler, key, raw: manager.run_builtin(handler)
    state = only(manager)
    btn = state.hosts["Main_Shell.Main.F.Top"].surface.view.nodes["Btn"]
    assert pixels(manager)(100, 50) == BLUE
    state.painter.simulate("click", node=btn)
    assert pixels(manager)(100, 50) == NONE
    state.painter.simulate("click", node=btn)
    assert pixels(manager)(100, 50) == BLUE


def test_an_action_in_a_strip_that_names_no_panel_or_frame_refuses_the_reload() -> None:
    manager, _, _ = started(RING, TAB)
    bad = RING.replace(
        "Inner_Radius: 8,",
        "Inner_Radius: 8, Edges { Top { Children { Rectangle { Name: Btn, Width: 30, Height: 10,"
        " On_Click { Action: Toggle, Target: Nope } } } } },",
    )
    assert manager.check(shell_of(bad, TAB), module()) is None
    good = bad.replace("Target: Nope", "Target: Tab")
    assert manager.check(shell_of(good, TAB), module()) is not None
