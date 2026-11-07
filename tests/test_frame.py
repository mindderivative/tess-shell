"""The Frame's windows: a painter and one reserver per side, kept and changed live on reload
(headless: the shell's manager over a stub ``App``; the windows are real tre windows)."""

from __future__ import annotations

from typing import Any

import tess_dl

from tess_shell.appearance import Appearance
from tess_shell.binder.model import Handler
from tess_shell.model.look import make_look
from tess_shell.model.store import ValueStore
from tess_shell.schema.look import read_theme
from tess_shell.schema.model import ShellDef
from tess_shell.surfaces.manager import SurfaceManager
from tests.test_look import THEME
from tests.test_schema_shell import read


class Out(str):
    width = 400
    height = 300

    @property
    def name(self) -> str:
        return str(self)


class StubApp:
    def __init__(self) -> None:
        self.windows: list[Any] = []
        self.size: tuple[int, int] = (400, 300)

    def outputs(self) -> list[Any]:
        out = Out("HDMI-A-1")
        out.width, out.height = self.size  # type: ignore[misc]
        return [out]

    def add_window(self, window: object) -> None:
        self.windows.append(window)


def shell_of(frame: str) -> ShellDef:
    body = f"Shell {{ Monitor {{ Name: Main, Index: 0, Children {{ {frame} }} }} }}"
    shell, findings = read(body)
    assert shell is not None, findings
    return shell


def look() -> Any:
    doc = tess_dl.parse(THEME, path="T_Theme.tdl").document
    assert doc is not None
    theme, _ = read_theme(doc, "T_Theme.tdl")
    assert theme is not None
    return make_look(theme, [], Appearance(scheme="dark"))


def started(frame: str, app: StubApp | None = None) -> tuple[SurfaceManager, StubApp]:
    app = app or StubApp()
    manager = SurfaceManager(app, {}, lambda key: key, ValueStore(), look())  # type: ignore[arg-type]
    manager.plan(shell_of(frame))
    manager.build()
    return manager, app


def reload(manager: SurfaceManager, frame: str) -> None:
    checked = manager.check(shell_of(frame), {})
    assert checked is not None
    manager.apply(checked[0], {}, checked[1])


def only(manager: SurfaceManager) -> Any:
    (state,) = manager.frames.states.values()
    return state


FRAME = (
    "Frame { Name: F, Thickness: [10, 20, 30, 40], Margin: 5,"
    ' Inner_Border { Width: 2, Color: "#00ff00" },'
    ' Style { Background: "#0000ff" } }'
)


def test_a_painter_and_a_reserver_per_side_open_with_the_spec_settings() -> None:
    manager, app = started(FRAME)
    state = only(manager)
    painter = state.painter
    assert painter.get("layer") == "top" and set(painter.get("anchor")) == {
        "top",
        "right",
        "bottom",
        "left",
    }
    assert painter.get("size") == (0, 0) and painter.get("exclusive_zone") == -1
    assert painter.get("input_region") == "auto" and painter.get("keyboard") == "none"
    expected = {
        "left": ({"left", "top", "bottom"}, (1, 0), 17),  # 10 + margin 5 + border 2
        "top": ({"top", "left", "right"}, (0, 1), 27),
        "right": ({"right", "top", "bottom"}, (1, 0), 37),
        "bottom": ({"bottom", "left", "right"}, (0, 1), 47),
    }
    assert set(state.reservers) == set(expected)
    for side, (anchors, size, zone) in expected.items():
        window = state.reservers[side]
        assert set(window.get("anchor")) == anchors and window.get("size") == size
        assert window.get("exclusive_zone") == zone and window.get("layer") == "top"
        assert window.get("input_region") == [] and window.get("keyboard") == "none"
    assert len(app.windows) == 5
    assert all(n.get("a11y_hidden") and n.get("hit_shape") == "painted" for n in state.nodes)


def test_a_side_with_no_thickness_has_no_reserver() -> None:
    manager, app = started("Frame { Name: F, Thickness { Top: 12, Left: 12 } }")
    assert set(only(manager).reservers) == {"left", "top"} and len(app.windows) == 3


def test_a_frame_that_is_not_visible_opens_no_window_until_it_is_shown() -> None:
    manager, app = started("Frame { Name: F, Thickness: 8, Visible: false }")
    assert app.windows == [] and only(manager).painter is None
    manager.run_builtin(Handler("Show", {"Target": "F"}, builtin=True))
    assert len(app.windows) == 5 and only(manager).painter is not None


def test_hide_closes_every_window_and_show_opens_them_again() -> None:
    manager, app = started('Frame { Name: F, Thickness: 8, Style { Background: "#000000" } }')
    state = only(manager)
    windows = list(app.windows)
    manager.run_builtin(Handler("Hide", {"Target": "F"}, builtin=True))
    assert state.painter is None and state.reservers == {}  # the zones are released
    manager.run_builtin(Handler("Toggle", {"Target": "F"}, builtin=True))
    assert state.painter is not None and len(state.reservers) == 4
    assert len(app.windows) == 10 and state.painter is not windows[0]


def test_a_reload_changes_zones_radii_and_colours_without_making_the_painter_again() -> None:
    manager, app = started(
        'Frame { Name: F, Thickness: 10, Inner_Radius: 8, Style { Background: "#0000ff" } }'
    )
    state = only(manager)
    painter, fill = state.painter, state.nodes[1]
    before = fill.get("data")
    top = state.reservers["top"]
    reload(
        manager,
        "Frame { Name: F, Thickness: [10, 24, 10, 10], Inner_Radius: 16,"
        ' Style { Background: "#ff0000" } }',
    )
    assert only(manager) is state and state.painter is painter and state.nodes[1] is fill
    assert state.reservers["top"] is top and top.get("exclusive_zone") == 24
    assert fill.get("data") != before and fill.get("fill") == (255, 0, 0, 255)
    assert len(app.windows) == 5  # nothing was opened


def test_a_reload_adds_and_removes_reservers_with_the_sides_thickness() -> None:
    manager, app = started("Frame { Name: F, Thickness { Top: 12 } }")
    state = only(manager)
    assert set(state.reservers) == {"top"}
    reload(manager, "Frame { Name: F, Thickness { Left: 6, Bottom: 6 } }")
    assert set(state.reservers) == {"left", "bottom"}
    assert state.reservers["left"].get("exclusive_zone") == 6
    assert len(app.windows) == 1 + 1 + 2


def test_a_reload_that_drops_the_frame_closes_all_its_windows() -> None:
    manager, _ = started("Frame { Name: F, Thickness: 8 }")
    state = only(manager)
    reload(manager, "Frame { Name: G, Thickness: 8 }")
    assert state.painter is None and state.reservers == {}  # the old Frame is closed
    assert [s.plan.frame.name for s in manager.frames.states.values()] == ["G"]


def test_a_frame_hidden_at_run_time_stays_hidden_over_a_reload_that_did_not_change_visible() -> (
    None
):
    manager, _ = started("Frame { Name: F, Thickness: 8 }")
    manager.run_builtin(Handler("Hide", {"Target": "F"}, builtin=True))
    reload(manager, "Frame { Name: F, Thickness: 9 }")
    assert only(manager).painter is None
    reload(manager, "Frame { Name: F, Thickness: 9, Visible: false }")
    assert only(manager).painter is None
    reload(manager, "Frame { Name: F, Thickness: 9, Visible: true }")
    assert only(manager).painter is not None


def test_tokens_in_the_frame_follow_the_themes_light_and_dark() -> None:
    manager, _ = started(
        "Frame { Name: F, Thickness: 8, Inner_Border { Width: 1, Color: $color.on_surface },"
        " Style { Background: $color.surface } }"
    )
    state = only(manager)
    outer, fill, inner = state.nodes
    assert fill.get("fill") == (0x10, 0x10, 0x10, 255) and inner.get("fill") == (0xEE,) * 3 + (255,)
    manager.set_look(manager.look.with_appearance(Appearance(scheme="light")))
    assert fill.get("fill") == (0xFF, 0xFF, 0xFF, 255)
    assert inner.get("fill") == (0x11, 0x11, 0x11, 255)
    assert state.nodes == [outer, fill, inner]  # redrawn in place


def test_a_frame_with_no_background_draws_nothing_and_no_border_hides_its_band() -> None:
    manager, _ = started("Frame { Name: F, Thickness: 8 }")
    outer, fill, inner = only(manager).nodes
    assert not fill.get("visible") and not outer.get("visible") and not inner.get("visible")


def test_the_ring_is_drawn_for_the_new_size_of_the_output() -> None:
    app = StubApp()
    manager, _ = started('Frame { Name: F, Thickness: 8, Style { Background: "#000000" } }', app)
    state = only(manager)
    fill = state.nodes[1]
    assert (fill.get("width"), fill.get("height")) == (400, 300)
    app.size = (640, 480)
    checked = manager.check(
        shell_of('Frame { Name: F, Thickness: 8, Style { Background: "#000000" } }'), {}
    )
    assert checked is not None
    manager.apply(checked[0], {}, checked[1])
    assert (fill.get("width"), fill.get("height")) == (640, 480) and "640" in fill.get("data")
    assert state.painter is not None


def test_opacity_applies_to_the_ring() -> None:
    manager, _ = started(
        'Frame { Name: F, Thickness: 8, Style { Background: "#000000", Opacity: 0.5 } }'
    )
    assert only(manager).nodes[1].get("opacity") == 0.5


def test_a_show_for_a_name_that_is_no_frame_is_left_to_the_panels() -> None:
    manager, _ = started("Frame { Name: F, Thickness: 8 }")
    assert manager.frames.run("Show", "Nope") is False


def test_the_painters_keyboard_is_none_by_default_and_on_demand_when_the_frame_asks() -> None:
    manager, _ = started("Frame { Name: F, Thickness: 8 }")
    assert only(manager).painter.get("keyboard") == "none"
    manager, _ = started("Frame { Name: F, Thickness: 8, Keyboard: ON_DEMAND }")
    assert only(manager).painter.get("keyboard") == "on_demand"
    assert only(manager).painter.get("input_region") == "auto"


def test_a_reload_changes_the_painters_keyboard_live_without_a_new_painter() -> None:
    manager, app = started("Frame { Name: F, Thickness: 8 }")
    painter = only(manager).painter
    reload(manager, "Frame { Name: F, Thickness: 8, Keyboard: ON_DEMAND }")
    assert only(manager).painter is painter and painter.get("keyboard") == "on_demand"
    reload(manager, "Frame { Name: F, Thickness: 8 }")
    assert painter.get("keyboard") == "none" and len(app.windows) == 5


def test_keys_the_painter_receives_are_logged_at_debug() -> None:
    from loguru import logger

    seen: list[str] = []
    sink = logger.add(lambda m: seen.append(str(m)), level="DEBUG")
    try:
        manager, _ = started("Frame { Name: F, Thickness: 8, Keyboard: ON_DEMAND }")
        only(manager).painter.simulate("key_down", key="a")
    finally:
        logger.remove(sink)
    assert any("painter key" in line and "'a'" in line for line in seen)


def test_an_opaque_border_is_sealed_to_the_fill_and_a_translucent_one_is_not() -> None:
    from tess_shell.surfaces.frame import Paint, ring_spec
    from tests.test_frame_schema import frame_of

    frame = frame_of("Frame { Name: F, Thickness: 8 }")
    opaque = Paint(fill=(0, 0, 0, 255), inner=(255, 255, 255, 255), outer=(255, 0, 0, 255))
    spec = ring_spec(frame, (), opaque)
    assert spec.seal_inner and spec.seal_outer
    soft = Paint(fill=(0, 0, 0, 255), inner=(255, 255, 255, 0x22), outer=(255, 0, 0, 255))
    assert not ring_spec(frame, (), soft).seal_inner  # the fill would show under half the border
    fading = Paint(fill=(0, 0, 0, 255), inner=(255, 255, 255, 255), opacity=0.5)
    assert not ring_spec(frame, (), fading).seal_inner  # and under a Frame that is translucent
    assert not ring_spec(frame).seal_inner
