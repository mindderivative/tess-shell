"""Monitors coming and going (Data Flow > Monitor Hot-plug, M3c C4), headless.

A fake ``App`` holds the outputs and delivers the three output events as tre does (on the loop
thread, with an ``Output``); the windows are real tre windows without a compositor.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any

import pytest
import tess_dl
from loguru import logger

from tess_shell.appearance import Appearance
from tess_shell.model.look import make_look
from tess_shell.model.store import ValueStore
from tess_shell.schema.look import read_theme
from tess_shell.surfaces.manager import SurfaceManager, is_default
from tests.test_look import THEME
from tests.test_panel_motion import Positions
from tests.test_popup import BTN, card, module, read


class Out(str):
    """An output: tre takes a connector name where it takes an ``Output``, so this is the name
    with the properties of an ``Output``."""

    width: int
    height: int
    x: int
    y: int
    description: str
    scale_factor: float
    transform: str

    def __new__(
        cls,
        name: str,
        width: int = 1000,
        height: int = 800,
        x: int = 0,
        y: int = 0,
        description: str = "",
        scale_factor: float = 1.0,
        transform: str = "normal",
    ) -> Out:
        out = super().__new__(cls, name)
        out.width, out.height, out.x, out.y = width, height, x, y
        out.description, out.scale_factor, out.transform = description, scale_factor, transform
        return out

    @property
    def name(self) -> str:
        return str(self)

    def but(self, **fields: Any) -> Out:
        """The same screen with other properties, as a new object (tre hands one over each time)."""
        kept = {k: getattr(self, k) for k in self.__dict__}
        return Out(str(self), **{**kept, **fields})


@dataclass
class FakeApp:
    """What tre gives the shell: the outputs, one handler per output event, ``add_window``."""

    current: list[Out]
    handlers: dict[str, Any] = field(default_factory=dict)
    windows: list[Any] = field(default_factory=list)

    def outputs(self) -> list[Out]:
        return sorted(self.current, key=lambda o: (o.y, o.x))

    def on(self, event: str, handler: Any) -> None:
        self.handlers[event] = handler

    def add_window(self, window: Any) -> None:
        self.windows.append(window)

    def plug(self, out: Out) -> None:
        self.current.append(out)
        self.handlers["output_added"](out)

    def unplug(self, name: str) -> None:
        (out,) = [o for o in self.current if o.name == name]
        self.current.remove(out)
        self.handlers["output_removed"](out)

    def update(self, name: str, **fields: Any) -> None:
        (old,) = [o for o in self.current if o.name == name]
        new = old.but(**fields)
        self.current[self.current.index(old)] = new
        self.handlers["output_updated"](new)


MAIN = (
    "Monitor {{ Name: Main, {selector}, Children {{\n"
    "  Bar {{ Name: Main_Bar, Edge: TOP, Width: EXPAND, Height: 32, "
    "Children {{ Btn {{ Name: One }} }} }}\n"
    "  Panel {{ Name: Dock, Anchor: [TOP, LEFT], Inset: [20, 40, 0, 0], Width: 200, "
    "Height: 100, Movable: true, Children {{ FlexBox {{ }} }} }}\n"
    "  Popup {{ Name: Menu, Children {{ {card} }} }}\n"
    "}} }}\n"
)
SIDE = (
    "Monitor {{ Name: Side, {selector}, Children {{\n"
    "  Bar {{ Name: Side_Bar, Edge: BOTTOM, Width: 50%, Height: 20%, "
    "Children {{ Btn {{ Name: Two }} }} }}\n"
    "  Panel {{ Name: Side_Dock, Anchor: [TOP, LEFT], Inset: [20, 40, 0, 0], Width: 100, "
    "Height: 50, Movable: true, Children {{ FlexBox {{ }} }} }}\n"
    "  Popup {{ Name: Side_Menu, Children {{ {card} }} }}\n"
    "}} }}\n"
)


def shell_text(main: str = "Connector: HDMI-A-1", side: str = "Index: 1") -> str:
    return (
        "Shell {\n"
        + MAIN.format(selector=main, card=card())
        + SIDE.format(selector=side, card=card("Side_Card"))
        + "}\n"
    )


@dataclass
class Rig:
    app: FakeApp
    manager: SurfaceManager
    positions: Positions
    store: ValueStore
    lines: list[str]
    synced: list[list[str]]
    closed: list[str]

    def names(self) -> dict[str, str]:
        return {s.name: s.output for s in self.manager.surfaces}

    def surface(self, name: str) -> Any:
        return next(s for s in self.manager.surfaces if s.name == name)

    def log(self) -> str:
        return "\n".join(self.lines)


_SINKS: list[int] = []


@pytest.fixture(autouse=True)
def _remove_log_sinks() -> Iterator[None]:
    yield
    while _SINKS:
        logger.remove(_SINKS.pop())


def make(
    text: str | None = None,
    outputs: list[Out] | None = None,
    positions: Positions | None = None,
) -> Rig:
    btn = module(BTN, "Btn")
    shell, findings = read(text or shell_text(), {"Btn": btn})
    assert shell is not None, findings
    doc = tess_dl.parse(THEME, path="T_Theme.tdl").document
    assert doc is not None
    theme, _ = read_theme(doc, "T_Theme.tdl")
    look = make_look(theme, [], Appearance())
    app = FakeApp(outputs or [Out("HDMI-A-1", 1000, 800), Out("DP-1", 600, 400, 0, 800)])
    store = ValueStore()
    saved = positions or Positions()
    manager = SurfaceManager(
        app,  # type: ignore[arg-type]
        {"Btn": btn},
        lambda k: k,
        store,
        look,
        positions=saved,  # type: ignore[arg-type]
    )
    lines: list[str] = []
    _SINKS.append(logger.add(lambda message: lines.append(str(message).rstrip()), level="INFO"))
    synced: list[list[str]] = []
    manager.sync_uses = lambda uses: synced.append(sorted(u.name for u in uses))
    manager.plan(shell)
    manager.build()
    closed: list[str] = []
    original = manager._close

    def spy(s: Any) -> None:
        closed.append(f"{s.name}@{s.output}")
        original(s)

    manager._close = spy  # type: ignore[method-assign]
    manager.hotplug.start()
    return Rig(app, manager, saved, store, lines, synced, closed)


def test_every_surface_opens_on_the_output_its_monitor_names() -> None:
    r = make()
    assert r.names() == {
        "Main_Bar": "HDMI-A-1",
        "Dock": "HDMI-A-1",
        "Side_Bar": "DP-1",
        "Side_Dock": "DP-1",
    }


def test_removing_an_output_closes_only_its_surfaces_and_leaves_the_others_untouched() -> None:
    r = make()
    main_bar, dock = r.surface("Main_Bar"), r.surface("Dock")
    windows, opened = (main_bar.window, dock.window), len(r.app.windows)
    r.app.unplug("DP-1")
    assert r.names() == {"Main_Bar": "HDMI-A-1", "Dock": "HDMI-A-1"}
    assert sorted(r.closed) == ["Side_Bar@DP-1", "Side_Dock@DP-1"]  # nothing of HDMI-A-1
    assert r.surface("Main_Bar") is main_bar and r.surface("Dock") is dock
    assert (main_bar.window, dock.window) == windows and len(r.app.windows) == opened
    assert "Bar Side_Bar on DP-1 closed" in r.log() and "Panel Side_Dock on DP-1 closed" in r.log()
    assert "Main_Bar on HDMI-A-1 closed" not in r.log()


def test_adding_an_output_opens_only_that_monitors_surfaces() -> None:
    r = make(outputs=[Out("HDMI-A-1", 1000, 800)])
    assert r.names() == {"Main_Bar": "HDMI-A-1", "Dock": "HDMI-A-1"}  # Index 1: no second screen
    main_bar = r.surface("Main_Bar")
    opened = len(r.app.windows)
    r.app.plug(Out("DP-2", 600, 400, 0, 800))
    assert r.names() == {
        "Main_Bar": "HDMI-A-1",
        "Dock": "HDMI-A-1",
        "Side_Bar": "DP-2",
        "Side_Dock": "DP-2",
    }
    assert r.surface("Main_Bar") is main_bar and r.closed == []
    assert len(r.app.windows) == opened + 2  # a Bar and a Panel, no new window for the first
    assert r.surface("Side_Bar").geometry.size == (300, 80)  # 50% x 20% of 600x400


def test_a_monitor_that_returns_gets_its_panel_back_saved_and_clamped_to_the_output() -> None:
    r = make()
    r.positions.set_position(
        "position:Main_Shell.Side@DP-1.Side_Dock", {"left": 300.0, "top": 90.0}
    )
    r.app.unplug("DP-1")
    assert "Side_Dock" not in r.names()
    r.app.plug(Out("DP-1", 600, 400, 0, 800))
    dock = r.surface("Side_Dock")
    assert dock.window is not None and dock.output == "DP-1"
    assert dock.geometry.margin == (90, 0, 0, 300)
    r.app.unplug("DP-1")
    r.app.plug(Out("DP-1", 350, 120, 0, 800))  # a smaller screen: the saved place is clamped
    assert r.surface("Side_Dock").geometry.margin == (70, 0, 0, 250)


def test_a_returning_panel_starts_as_its_visible_key_says() -> None:
    text = shell_text().replace("Height: 50, Movable", "Height: 50, Visible: false, Movable")
    r = make(text)
    assert r.surface("Side_Dock").hidden
    r.manager.show(r.surface("Side_Dock"))
    assert not r.surface("Side_Dock").hidden
    r.app.unplug("DP-1")
    r.app.plug(Out("DP-1", 600, 400, 0, 800))
    assert r.surface("Side_Dock").hidden  # a new window starts from the file, not the old state


def test_the_modules_follow_the_uses_on_the_output_that_came_or_went() -> None:
    r = make()
    r.synced.clear()
    r.store.add_use("Btn", "stale-use")
    r.app.unplug("DP-1")
    assert r.synced == [["Main_Shell.Main.Main_Bar.One"]]  # the host is told the uses left
    assert all("Two" not in k for k in r.manager._all_uses)
    assert "stale-use" not in r.store.values
    r.app.plug(Out("DP-1", 600, 400, 0, 800))
    assert r.synced[-1] == ["Main_Shell.Main.Main_Bar.One", "Main_Shell.Side.Side_Bar.Two"]


def test_an_updated_output_resizes_its_surfaces_without_new_windows() -> None:
    r = make()
    side, main = r.surface("Side_Bar"), r.surface("Main_Bar")
    window, opened = side.window, len(r.app.windows)
    main_geometry = main.geometry
    r.app.update("DP-1", width=1200, height=500)
    assert r.surface("Side_Bar") is side and side.window is window
    assert side.geometry.size == (600, 100)  # 50% x 20% of 1200x500
    assert tuple(window.get("size")) == (600, 100)
    assert len(r.app.windows) == opened and r.closed == []
    assert main.geometry == main_geometry  # the other screen is not touched


def test_an_update_that_changes_nothing_a_surface_depends_on_changes_nothing() -> None:
    r = make()
    side = r.surface("Side_Bar")
    r.app.update("DP-1", x=5)
    assert r.surface("Side_Bar") is side and r.closed == [] and "is now" not in r.log()


def test_a_saved_position_is_clamped_when_the_output_shrinks() -> None:
    saved = Positions({"position:Main_Shell.Side@DP-1.Side_Dock": {"left": 480.0, "top": 300.0}})
    r = make(positions=saved)
    assert r.surface("Side_Dock").geometry.margin == (300, 0, 0, 480)
    r.app.update("DP-1", width=400, height=200)
    assert r.surface("Side_Dock").geometry.margin == (150, 0, 0, 300)


def test_index_is_evaluated_again_when_the_order_of_the_outputs_changes() -> None:
    r = make(shell_text(main="Index: 0", side="Index: 1"))
    assert r.names()["Main_Bar"] == "HDMI-A-1" and r.names()["Side_Bar"] == "DP-1"
    r.app.plug(Out("DP-0", 800, 600, 0, -600))  # above everything: it is index 0 now
    assert r.names() == {
        "Main_Bar": "DP-0",
        "Dock": "DP-0",
        "Side_Bar": "HDMI-A-1",
        "Side_Dock": "HDMI-A-1",
    }
    assert sorted(r.closed) == [
        "Dock@HDMI-A-1",
        "Main_Bar@HDMI-A-1",
        "Side_Bar@DP-1",
        "Side_Dock@DP-1",
    ]
    r.app.unplug("DP-0")
    assert r.names()["Main_Bar"] == "HDMI-A-1" and r.names()["Side_Bar"] == "DP-1"


def test_a_connector_does_not_move_when_the_order_changes() -> None:
    r = make(shell_text(main="Connector: HDMI-A-1", side="Connector: DP-1"))
    main_bar = r.surface("Main_Bar")
    r.app.plug(Out("DP-0", 800, 600, 0, -600))
    assert r.surface("Main_Bar") is main_bar and r.closed == []
    assert r.names()["Side_Bar"] == "DP-1"


def test_a_block_naming_an_output_another_took_stays_without_it_as_outputs_change() -> None:
    r = make(shell_text(main="Index: 0", side="Connector: HDMI-A-1"))
    assert "Side_Bar" not in r.names()  # Main took HDMI-A-1 first
    assert "already took" in r.log()
    r.app.unplug("DP-1")
    r.app.plug(Out("DP-1", 600, 400, 0, 800))
    assert "Side_Bar" not in r.names() and r.names()["Main_Bar"] == "HDMI-A-1"


def test_default_monitors_keep_their_surfaces_when_a_second_screen_comes() -> None:
    text = "Shell {\n" + MAIN.format(selector="Index: default", card=card()) + "}\n"
    r = make(text, outputs=[Out("HDMI-A-1")])
    bar = r.surface("Main_Bar")
    key = bar.key
    r.app.plug(Out("DP-1", 600, 400, 0, 800))
    assert r.surface("Main_Bar") is bar and bar.key == key and r.closed == []
    assert sorted(s.output for s in r.manager.surfaces if s.name == "Main_Bar") == [
        "DP-1",
        "HDMI-A-1",
    ]
    assert "@HDMI-A-1" in key  # the output is always in a default monitor's path
    assert r.manager._shell is not None and is_default(r.manager._shell.monitors[0])


def test_a_popup_open_on_a_removed_output_closes_and_the_other_outputs_popup_stays() -> None:
    r = make()
    side, main = r.surface("Side_Bar"), r.surface("Main_Bar")
    side.window.advance(16)
    main.window.advance(16)
    popups = r.manager.popups
    popups.call("Btn", side.expanded.uses[0].key, "Side_Menu", None)
    op = popups.current
    assert op is not None and op.parent is side
    r.app.unplug("DP-1")
    assert popups.current is None and op.closing  # it closed with its parent
    assert ("Side@DP-1", "Side_Menu") not in popups.plans and (
        "Main@HDMI-A-1",
        "Menu",
    ) in popups.plans
    popups.call("Btn", main.expanded.uses[0].key, "Menu", None)
    assert popups.current is not None and popups.current.parent is main
    r.app.plug(Out("DP-1", 600, 400, 0, 800))
    assert popups.current is not None  # another screen coming does not close it
    assert ("Side@DP-1", "Side_Menu") in popups.plans  # the plan is back


def test_a_popup_on_a_surface_whose_output_changed_size_closes() -> None:
    r = make()
    side = r.surface("Side_Bar")
    side.window.advance(16)
    r.manager.popups.call("Btn", side.expanded.uses[0].key, "Side_Menu", None)
    assert r.manager.popups.current is not None
    r.app.update("DP-1", width=800)
    assert r.manager.popups.current is None


def test_a_hide_after_timer_of_a_panel_on_a_removed_output_is_cancelled() -> None:
    text = shell_text().replace("Height: 50, Movable", "Height: 50, Hide_After: 100, Movable")
    r = make(text)
    dock = r.surface("Side_Dock")
    assert dock.timer is not None
    r.app.unplug("DP-1")
    assert dock.timer is None


def test_removing_the_last_output_leaves_nothing_open_and_a_new_one_opens_the_shell() -> None:
    r = make(outputs=[Out("HDMI-A-1")])
    r.app.unplug("HDMI-A-1")
    assert r.manager.surfaces == [] and "no outputs" in r.log()
    r.app.plug(Out("HDMI-A-2"))
    assert r.names() == {}  # Connector: HDMI-A-1 is not there; Index: 1 has no second screen
    r.app.plug(Out("HDMI-A-1", 1000, 800, 0, 800))
    assert r.names()["Main_Bar"] == "HDMI-A-1"


def test_an_output_that_came_before_the_loop_ran_is_caught_up_at_start() -> None:
    r = make()
    r.app.current.append(Out("DP-9", 640, 480, 0, 1200))  # came after the plan, before start()
    r.manager.hotplug.start()
    assert "outputs changed while the shell started" in r.log()


def test_a_frame_follows_its_monitor_and_the_other_monitors_frame_is_untouched() -> None:
    text = (
        "Shell {\n"
        "Monitor { Name: Main, Connector: HDMI-A-1, Children { "
        "Frame { Name: Ring_A, Thickness: [6, 6, 6, 6] } } }\n"
        "Monitor { Name: Side, Index: 1, Children { "
        "Frame { Name: Ring_B, Thickness: [4, 4, 4, 4] } } }\n"
        "}\n"
    )
    r = make(text)
    frames = r.manager.frames
    assert sorted(frames.states) == ["Main_Shell.Main.Ring_A", "Main_Shell.Side.Ring_B"]
    first, opened = frames.states["Main_Shell.Main.Ring_A"], len(r.app.windows)
    r.app.unplug("DP-1")
    assert sorted(frames.states) == ["Main_Shell.Main.Ring_A"]
    assert frames.states["Main_Shell.Main.Ring_A"] is first and len(r.app.windows) == opened
    r.app.plug(Out("DP-1", 600, 400, 0, 800))
    assert sorted(frames.states) == ["Main_Shell.Main.Ring_A", "Main_Shell.Side.Ring_B"]
    assert frames.states["Main_Shell.Main.Ring_A"] is first
    assert frames.states["Main_Shell.Side.Ring_B"].plan.output.name == "DP-1"
    assert len(r.app.windows) > opened  # new windows for the returning monitor only
