# ruff: noqa: E501
"""Focus through the real shell (M6a, T-041): the shipped modules built by a real module host in a
real surface manager, keys simulated on the real windows, the layout hot-reloaded through the
manager. ``tests/test_focus.py`` covers the model on a bare ``View``; this is what the user's shell
does with it: which widgets are Tab stops (exactly once each), what hides a stop, what a reload
keeps, and what each kind of surface asks the compositor for (the ``Keyboard`` word)."""

from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

import pytest
import tess_dl
from loguru import logger

from tess_shell.appearance import Appearance
from tess_shell.model.look import make_look
from tess_shell.model.store import ValueStore
from tess_shell.schema.look import read_theme
from tess_shell.schema.shell import read_shell
from tess_shell.surfaces.manager import Surface, SurfaceManager
from tests.shell_samples import HEADER, SVG
from tests.test_focus import ring_of
from tests.test_look import THEME
from tests.test_panel import StubApp
from tests.widgets_live import Widgets, running


@pytest.fixture
def lines() -> Iterator[list[str]]:
    """What the shell logs at WARNING or above while a test runs."""
    out: list[str] = []
    sink = logger.add(lambda message: out.append(str(message)), level="WARNING")
    yield out
    logger.remove(sink)


# -- helpers -----------------------------------------------------------------------------------


def who(key: str) -> str:
    """The short name of a node id: the Name of the module use (``Button@...Top_Bar.Save/Root`` ->
    ``Save``), or the id itself."""
    found = re.search(r"@[\w.]*?\.(\w+)/", key)
    return found.group(1) if found else key


def focused(view: Any) -> list[str]:
    return [who(k) for k, n in view.nodes.items() if n.get("focused")]


def tab(window: Any, view: Any, shift: bool = False) -> str | None:
    window.simulate("key_down", key="tab", shift=shift)
    found = focused(view)
    assert len(found) <= 1, found
    return found[0] if found else None


def cycle(window: Any, view: Any, shift: bool = False) -> list[str | None]:
    """What Tab reaches, once round: press Tab until the first stop comes again."""
    seen: list[str | None] = []
    for _ in range(40):
        stop = tab(window, view, shift)
        if seen and stop == seen[0]:
            return seen
        seen.append(stop)
    raise AssertionError(f"Tab never came round: {seen}")


def rotated(got: list[str | None], want: list[str]) -> bool:
    """``got`` is ``want`` going round, from wherever the focus was when Tab was first pressed."""
    return len(got) == len(want) and any(got == want[i:] + want[:i] for i in range(len(want)))


def ring_on(view: Any, node: Any, look: Any) -> bool:
    """Whether ``node`` or a block above it (a text field's box) shows the focus ring."""
    cur = node
    while cur is not None:
        if list(cur.get("shadows")) == ring_of(look):
            return True
        cur = cur.parent()
    return False


def surface(w: Widgets, name: str) -> Surface:
    return next(s for s in w.manager.surfaces if s.name == name)


# -- the shipped widgets in the Tab order ------------------------------------------------------

# (call written with %s where a key may go, the module whose root takes the stop)
STOPS = {
    "Button": 'Button { %s Name: X, Text: "Go" }',
    "Button, icon only": 'Button { %s Name: X, Icon: "mdi:plus", Label: Add }',
    "Toggle": "Toggle { %s Name: X, Label: Mute }",
    "Checkbox, with a label": 'Checkbox { %s Name: X, Text: "Remember me" }',
    "Slider": "Slider { %s Name: X, Label: Volume }",
    "Slider, upright": "Slider { %s Name: X, Orientation: VERTICAL, Label: Volume }",
    "TextInput": "TextInput { %s Name: X }",
    "TextEditor": "TextEditor { %s Name: X }",
    "List": 'List { %s Name: X, Children { Label { Key: a, Text: "a" } Label { Key: b, Text: "b" } } }',
    "Menu": "Menu { %s Name: X, Children { MenuItem { Text: a } MenuItem { Separator: true } MenuItem { Text: b } } }",
    "Tray_Item": "Tray_Item { %s Name: X, label: Mail }",
}
DECORATION = {
    "Label": 'Label { %s Name: X, Text: "hello" }',
    "TextBox": 'TextBox { %s Name: X, Text: "hello" }',
    "TextBox that can be selected": 'TextBox { %s Name: X, Text: "hello", Selectable: true }',
    "Badge": "Badge { %s Name: X, Count: 3 }",
    "Icon": 'Icon { %s Name: X, Icon: "mdi:plus" }',
    "ProgressBar": "ProgressBar { %s Name: X, Value: 20 }",
    "Marquee_Text": 'Marquee_Text { %s Name: X, Text: "hello" }',
}


@pytest.mark.parametrize("call", STOPS.values(), ids=STOPS.keys())
def test_an_interactive_widget_is_one_tab_stop_and_shows_the_ring_for_the_keyboard(
    call: str,
) -> None:
    with running(
        f"Label {{ Name: Before, Text: a }} {call % ''} Label {{ Name: After, Text: z }}"
    ) as w:
        assert w.warnings() == [], w.warnings()
        assert rotated(
            cycle(w.window, w.view), ["X"]
        )  # once, however many nodes the widget is made of
        node = next(n for k, n in w.view.nodes.items() if n.get("focused"))
        assert ring_on(w.view, node, w.manager.look)


@pytest.mark.parametrize("call", STOPS.values(), ids=STOPS.keys())
def test_a_disabled_widget_is_no_tab_stop(call: str) -> None:
    with running(call % "Enabled: false,") as w:
        assert w.view.tab_stops() == []
        assert cycle_or_none(w) == []


def cycle_or_none(w: Widgets) -> list[str]:
    window, view = w.window, w.view
    window.simulate("key_down", key="tab")
    window.simulate("key_down", key="tab", shift=True)
    return focused(view)


@pytest.mark.parametrize("call", DECORATION.values(), ids=DECORATION.keys())
def test_decoration_takes_no_focus(call: str) -> None:
    with running(call % "") as w:
        assert w.view.tab_stops() == []
        assert cycle_or_none(w) == []


def test_a_click_on_a_widget_focuses_it_without_a_ring_and_the_keyboard_moves_on_with_one() -> None:
    with running('Button { Name: One, Text: "1" } Toggle { Name: Two, Label: t }') as w:
        one, two = (w.of_use("Button", "Root"), w.of_use("Toggle", "Root"))
        w.window.simulate("click", node=one)
        assert focused(w.view) == ["One"] and not ring_on(w.view, one, w.manager.look)
        assert tab(w.window, w.view) == "Two" and ring_on(w.view, two, w.manager.look)
        assert not ring_on(w.view, one, w.manager.look)


def test_the_tab_index_of_a_module_call_orders_the_stops_of_the_real_shell() -> None:
    body = (
        'Button { Name: Last, Text: "l" } Toggle { Name: Second, Label: s, Tab_Index: 2 } '
        "Checkbox { Name: First, Text: f, Tab_Index: 1 } Slider { Name: Third, Tab_Index: 2 } "
        'Button { Name: Also_Last, Text: "a" }'
    )
    with running(body) as w:
        order = ["First", "Second", "Third", "Last", "Also_Last"]
        assert cycle(w.window, w.view) == order  # from a fresh window: the first stop first
        # the cycle ended on its first stop again: it wrapped
        assert tab(w.window, w.view, shift=True) == "Also_Last"  # Shift+Tab wraps backwards too
        assert tab(w.window, w.view, shift=True) == "Last"


def test_a_single_line_text_input_gives_tab_to_the_next_stop_and_takes_no_tab_character() -> None:
    with running('TextInput { Name: Ed, Text: "abc" } Button { Name: Go, Text: "g" }') as w:
        assert tab(w.window, w.view) == "Ed"
        assert tab(w.window, w.view) == "Go"
        assert tab(w.window, w.view, shift=True) == "Ed"
        field = next(n for k, n in w.view.nodes.items() if who(k) == "Ed" and n.get("focused"))
        assert field.get("text") == "abc"


def test_a_closed_expander_hides_its_content_from_tab_and_an_open_one_shows_it() -> None:
    driver = (
        "Module { FlexBox { Children { Button { Name: Before, Text: b } "
        "Expander { Expanded: <| open |>, Children { Button { Name: Inside, Text: i } TextInput { Name: Typed } } } "
        "Button { Name: After, Text: a } } } }"
    )
    code = "from tess_shell import Module\nclass Driver(Module):\n    def start(self):\n        self.ctx.send('open', False)\n"
    with running("Driver { }", driver=driver, driver_py=code) as w:
        assert rotated(cycle(w.window, w.view), ["Before", "After"])
        assert [who(k) for k, n in w.view.nodes.items() if n in w.view.tab_stops()] == [
            "Before",
            "After",
        ]
        w.send("open", True)
        w.advance(100)  # on its way: the content is on screen and takes Tab
        assert rotated(cycle(w.window, w.view), ["Before", "Inside", "Typed", "After"])
        w.advance(600)
        assert rotated(cycle(w.window, w.view), ["Before", "Inside", "Typed", "After"])
        w.send("open", False)
        w.advance(100)  # closing: still on screen
        assert "Inside" in cycle(w.window, w.view)
        w.advance(600)
        assert rotated(cycle(w.window, w.view), ["Before", "After"])
        w.send("open", True)  # and opened again
        w.advance(600)
        assert rotated(cycle(w.window, w.view), ["Before", "Inside", "Typed", "After"])


def test_an_expander_that_starts_open_and_one_reversed_half_way_keep_the_right_stops() -> None:
    body = "Expander { Expanded: true, Children { Button { Name: Inside, Text: i } } } Button { Name: After, Text: a }"
    with running(body) as w:
        assert rotated(cycle(w.window, w.view), ["Inside", "After"])
    driver = "Module { FlexBox { Children { Expander { Expanded: <| open |>, Children { Button { Name: Inside, Text: i } } } } } }"
    code = "from tess_shell import Module\nclass Driver(Module):\n    def start(self):\n        self.ctx.send('open', False)\n"
    with running("Driver { }", driver=driver, driver_py=code) as w:
        w.send("open", True)
        w.advance(80)
        w.send("open", False)
        w.advance(80)
        w.send("open", True)
        w.advance(600)
        assert rotated(cycle(w.window, w.view), ["Inside"])
        w.send("open", False)
        w.advance(600)
        assert w.view.tab_stops() == []


def test_focus_inside_an_expander_that_closes_is_taken_out_so_no_key_reaches_the_hidden_field() -> (
    None
):
    driver = (
        "Module { FlexBox { Children { Button { Name: Before, Text: b } "
        "Expander { Expanded: <| open |>, Children { TextInput { Name: Typed, Text: abc } } } } } }"
    )
    code = "from tess_shell import Module\nclass Driver(Module):\n    def start(self):\n        self.ctx.send('open', True)\n"
    with running("Driver { }", driver=driver, driver_py=code) as w:
        w.advance(600)
        assert tab(w.window, w.view) == "Before"
        assert tab(w.window, w.view) == "Typed"
        field = next(n for k, n in w.view.nodes.items() if who(k) == "Typed" and n.get("focused"))
        w.window.simulate("input", text="x")
        assert field.get("text") == "abcx"  # typed into while it is on screen
        w.send("open", False)
        w.advance(600)
        assert not field.get("focused")  # the field is hidden: it no longer has the keys
        assert "Typed" not in focused(w.view)  # focus is on the Expander's own block
        w.window.simulate("input", text="y")
        assert field.get("text") == "abcx"
        assert tab(w.window, w.view) == "Before"  # Tab starts again at the first stop


def test_a_block_that_is_not_visible_and_everything_in_it_is_no_stop() -> None:
    body = (
        "Button { Name: Gone, Text: g, Visible: false } Button { Name: Shown, Text: s } "
        "Expander { Expanded: true, Visible: false, Children { Button { Name: In_Hidden, Text: h } } }"
    )
    with running(body) as w:
        assert rotated(cycle(w.window, w.view), ["Shown"])
        assert [who(k) for k, n in w.view.nodes.items() if n in w.view.tab_stops()] == ["Shown"]


# -- reload and keyed lists --------------------------------------------------------------------

LIST_DRIVER = "Module { FlexBox { Children { For it In <| items |> Key <| it |> { Button { Text: <| it |>, Label: <| it |> } } } } }"
LIST_PY = "from tess_shell import Module\nclass Driver(Module):\n    def start(self):\n        self.ctx.send('items', ['a', 'b', 'c'])\n"


def labels(w: Widgets) -> list[str]:
    return [
        n.get("label") for k, n in w.view.nodes.items() if k.endswith("/Root") and "Button@" in k
    ]


def has_focus(w: Widgets) -> list[str]:
    return [
        n.get("label") for k, n in w.view.nodes.items() if k.endswith("/Root") and n.get("focused")
    ]


def test_a_for_list_that_reorders_keeps_focus_on_the_block_and_tab_follows_the_new_order() -> None:
    with running("Driver { }", driver=LIST_DRIVER, driver_py=LIST_PY) as w:
        assert labels(w) == ["a", "b", "c"]
        tab(w.window, w.view)
        tab(w.window, w.view)
        assert has_focus(w) == ["b"]
        w.send("items", ["c", "b", "a"])
        w.advance(16)
        assert labels(w) == ["c", "b", "a"]  # the same blocks, moved
        assert has_focus(w) == ["b"]  # focus stays on the block, not on the position
        tab(w.window, w.view)
        assert has_focus(w) == ["a"]  # and Tab walks the order as it is now
        tab(w.window, w.view)
        assert has_focus(w) == ["c"]


def test_a_list_that_loses_the_focused_entry_leaves_nothing_focused_and_tab_starts_again() -> None:
    with running("Driver { }", driver=LIST_DRIVER, driver_py=LIST_PY) as w:
        tab(w.window, w.view)
        tab(w.window, w.view)
        assert has_focus(w) == ["b"]
        w.send("items", ["a", "c"])
        w.advance(16)
        assert has_focus(w) == []  # the block is gone, focus is not left on a removed node
        assert tab(w.window, w.view) is not None and has_focus(w) == ["a"]  # Tab: the first stop
    with running("Driver { }", driver=LIST_DRIVER, driver_py=LIST_PY) as w:
        tab(w.window, w.view)
        tab(w.window, w.view)
        w.send("items", ["a", "c"])
        w.advance(16)
        tab(w.window, w.view, shift=True)
        assert has_focus(w) == ["c"]  # Shift+Tab: the last


def test_a_new_entry_in_a_list_takes_its_place_in_the_order_without_moving_focus() -> None:
    with running("Driver { }", driver=LIST_DRIVER, driver_py=LIST_PY) as w:
        tab(w.window, w.view)
        w.send("items", ["a", "x", "b", "c"])
        w.advance(16)
        assert has_focus(w) == ["a"]
        assert [tab(w.window, w.view) and has_focus(w)[0] for _ in range(3)] == ["x", "b", "c"]


# -- the whole shell: hot reload ---------------------------------------------------------------


def reloaded(text: str) -> Any:
    result = tess_dl.parse(HEADER + text, path="Shells/Main_Shell.tdl")
    assert not result.errors and result.document is not None
    shell, findings = read_shell(result.document, "Shells/Main_Shell.tdl", lambda p: SVG)
    assert shell is not None, findings
    return shell


def surfaces_text(
    bar_keys: str = "", bar_body: str = "", panel_keys: str = "", panel_body: str = ""
) -> str:
    button = "Rectangle {{ Name: {}, Width: 20, Height: 20, Role: BUTTON {} }}"
    bar_inner = bar_body or (
        button.format("A", "") + button.format("B", "") + button.format("C", "")
    )
    panel_inner = panel_body or (button.format("P1", "") + button.format("P2", ""))
    return (
        "Shell { Monitor { Name: Main, Index: 0, Children {\n"
        f"  Bar {{ Name: Top_Bar, Edge: TOP, Width: EXPAND, Height: 32, {bar_keys} Children {{ {bar_inner} }} }}\n"
        f"  Panel {{ Name: Dock, Width: 100, Height: 100, {panel_keys} Children {{ FlexBox {{ Name: In, Children {{ {panel_inner} }} }} }} }}\n"
        "} } }\n"
    )


def started(text: str, hide_mode: str = "KEEP") -> SurfaceManager:
    doc = tess_dl.parse(THEME, path="T_Theme.tdl").document
    assert doc is not None
    theme, _ = read_theme(doc, "T_Theme.tdl")
    assert theme is not None
    manager = SurfaceManager(
        StubApp(),  # type: ignore[arg-type]
        {},
        lambda key: key,
        ValueStore(),
        make_look(theme, [], Appearance()),
        hide_mode=hide_mode,
    )
    manager.plan(reloaded(text))
    manager.build()
    for s in manager.surfaces:
        assert s.window is not None
        s.window.advance(16)
    return manager


def reload(manager: SurfaceManager, text: str) -> None:
    checked = manager.check(reloaded(text), {})
    assert checked is not None
    manager.apply(checked[0], {}, checked[1])
    for s in manager.surfaces:
        if s.window is not None:
            s.window.advance(16)


def named(manager: SurfaceManager, name: str) -> Surface:
    return next(s for s in manager.surfaces if s.name == name)


def test_a_hot_reload_keeps_focus_on_the_block_that_is_still_there_and_reorders_by_the_new_indices() -> (
    None
):
    manager = started(surfaces_text())
    s = named(manager, "Top_Bar")
    assert s.window is not None and s.view is not None
    tab(s.window, s.view)  # A
    tab(s.window, s.view)  # B
    assert focused(s.view) == ["B"]
    button = "Rectangle {{ Name: {}, Width: 20, Height: 20, Role: BUTTON, Tab_Index: {} }}"
    reload(
        manager,
        surfaces_text(
            bar_body=button.format("A", 3) + button.format("B", 2) + button.format("C", 1)
        ),
    )
    s = named(manager, "Top_Bar")
    assert focused(s.view) == ["B"]  # the same block, by its Name
    assert tab(s.window, s.view) == "A"  # C, B, A is the order now: after B comes A
    assert tab(s.window, s.view) == "C"


def test_a_hot_reload_that_removes_the_focused_block_leaves_none_focused() -> None:
    manager = started(surfaces_text())
    s = named(manager, "Top_Bar")
    tab(s.window, s.view)
    tab(s.window, s.view)
    assert focused(s.view) == ["B"]
    button = "Rectangle {{ Name: {}, Width: 20, Height: 20, Role: BUTTON }}"
    reload(manager, surfaces_text(bar_body=button.format("A") + button.format("C")))
    s = named(manager, "Top_Bar")
    assert focused(s.view) == []
    assert tab(s.window, s.view) == "A"  # the first stop
    assert tab(s.window, s.view, shift=True) == "C"  # and the last the other way


# -- the Keyboard mode of each kind of surface --------------------------------------------------


def keyboard(manager: SurfaceManager) -> dict[str, str]:
    return {s.name: s.window.get("keyboard") for s in manager.surfaces if s.window is not None}


@pytest.mark.parametrize(
    ("bar_keys", "panel_keys", "bar", "panel"),
    [
        ("", "", "none", "none"),
        ("Keyboard: NONE,", "Keyboard: NONE,", "none", "none"),
        ("Keyboard: ON_DEMAND,", "Keyboard: ON_DEMAND,", "on_demand", "on_demand"),
        ("", "Keyboard: EXCLUSIVE,", "none", "exclusive"),
    ],
)
def test_the_keyboard_mode_of_a_bar_and_a_panel_reaches_the_window(
    bar_keys: str, panel_keys: str, bar: str, panel: str
) -> None:
    manager = started(surfaces_text(bar_keys, panel_keys=panel_keys))
    assert keyboard(manager) == {"Top_Bar": bar, "Dock": panel}


def test_a_surface_with_a_text_field_takes_on_demand_whatever_it_says_and_a_written_none_warns_once(
    lines: list[str],
) -> None:
    manager = started(
        surfaces_text(
            "Keyboard: NONE,",
            bar_body="TextField { Name: F1, Width: 100, Height: 20 }",
            panel_keys="Keyboard: NONE,",
            panel_body="TextField { Name: F2, Width: 100, Height: 20 }",
        )
    )
    assert keyboard(manager) == {"Top_Bar": "on_demand", "Dock": "on_demand"}
    assert sum("Keyboard: NONE is written" in x for x in lines) == 2  # one warning each, no more
    manager = started(surfaces_text(bar_body="TextField { Name: F1, Width: 100, Height: 20 }"))
    assert keyboard(manager)["Top_Bar"] == "on_demand"


def test_a_hidden_panel_takes_no_keyboard_and_shows_it_asks_for_again() -> None:
    manager = started(surfaces_text(panel_keys="Keyboard: EXCLUSIVE, Visible: false,"))
    dock = named(manager, "Dock")
    assert dock.window is not None and dock.window.get("keyboard") == "none"
    manager.show(dock)
    assert dock.window.get("keyboard") == "exclusive"
    manager.hide(dock)
    assert dock.window.get("keyboard") == "none"


def test_a_reload_that_changes_a_surfaces_keyboard_reaches_the_live_window() -> None:
    manager = started(surfaces_text())
    assert keyboard(manager) == {"Top_Bar": "none", "Dock": "none"}
    reload(manager, surfaces_text("Keyboard: ON_DEMAND,", panel_keys="Keyboard: EXCLUSIVE,"))
    assert keyboard(manager) == {"Top_Bar": "on_demand", "Dock": "exclusive"}
    reload(manager, surfaces_text())
    assert keyboard(manager) == {"Top_Bar": "none", "Dock": "none"}


def test_a_reload_that_adds_or_drops_a_text_field_changes_the_keyboard_word() -> None:
    manager = started(surfaces_text())
    reload(
        manager,
        surfaces_text(
            bar_body="TextField { Name: F1, Width: 100, Height: 20 }",
            panel_body="TextField { Name: F2, Width: 100, Height: 20 }",
        ),
    )
    assert keyboard(manager) == {"Top_Bar": "on_demand", "Dock": "on_demand"}
    reload(manager, surfaces_text())
    assert keyboard(manager) == {"Top_Bar": "none", "Dock": "none"}


def test_the_buttons_in_a_frame_strip_are_tab_stops_of_its_painter_when_the_frame_takes_the_keyboard() -> (
    None
):
    from tests.test_frame import only
    from tests.test_frame_strips import started as frame_started

    strip = (
        "Edges { Left { Children { Rectangle { Name: A, Width: 10, Height: 20, Role: BUTTON } "
        "Rectangle { Name: B, Width: 10, Height: 20, Role: BUTTON } } } }"
    )
    manager, _, _ = frame_started(
        f"Frame {{ Name: F, Thickness: 30, Keyboard: ON_DEMAND, {strip} }}"
    )
    painter = only(manager).painter
    assert painter.get("keyboard") == "on_demand"

    def where() -> list[float]:
        found: list[float] = []

        def walk(node: Any) -> None:
            if node.get("focused"):
                assert list(node.get("shadows")), "keyboard focus without a ring"
                found.append(node.get("layout_y"))
            for child in node.children():
                walk(child)

        walk(painter.root)
        return found

    seen = []
    for _ in range(3):
        painter.simulate("key_down", key="tab")
        seen.append(where())
    assert seen[0] != seen[1] and seen[0] == seen[2] and all(len(s) == 1 for s in seen)  # A, B, A


def test_a_reload_does_not_wake_the_keyboard_of_a_hidden_panel() -> None:
    manager = started(surfaces_text(panel_keys="Visible: false,"))
    reload(manager, surfaces_text(panel_keys="Visible: false, Keyboard: EXCLUSIVE,"))
    dock = named(manager, "Dock")
    assert dock.window is not None and dock.window.get("keyboard") == "none"
    manager.show(dock)
    assert dock.window.get("keyboard") == "exclusive"


def test_tab_walks_a_panel_of_the_real_shell_and_skips_what_is_disabled_or_hidden() -> None:
    inner = (
        "Rectangle { Name: P1, Width: 20, Height: 20, Role: BUTTON } "
        "Rectangle { Name: Off, Width: 20, Height: 20, Role: BUTTON, Enabled: false } "
        "Rectangle { Name: Gone, Width: 20, Height: 20, Role: BUTTON, Visible: false } "
        "Rectangle { Name: P2, Width: 20, Height: 20, Role: BUTTON }"
    )
    manager = started(surfaces_text(panel_keys="Keyboard: ON_DEMAND,", panel_body=inner))
    dock = named(manager, "Dock")
    assert dock.window is not None and dock.view is not None
    assert rotated(cycle(dock.window, dock.view), ["P1", "P2"])
    assert rotated(cycle(dock.window, dock.view, shift=True), ["P2", "P1"])
    # the Bar is a window of its own: its Tab does not reach the Panel's blocks
    bar = named(manager, "Top_Bar")
    assert bar.window is not None and bar.view is not None
    assert rotated(cycle(bar.window, bar.view), ["A", "B", "C"])


# -- a Popup with a real Menu --------------------------------------------------------------------

MENU_POPUP = """
Popup {
    Name: File_Menu
    Attach: BOTTOM
    Children { Menu { Children { MenuItem { Text: "New" } MenuItem { Text: "Open" } } } }
}
"""
OPENERS = (
    'Button { Name: Opener, Text: "File", On_Click { Action: Show, Target: File_Menu } } '
    'Button { Name: Other, Text: "Other" }'
)


def test_a_menu_opened_from_a_focused_button_takes_focus_with_a_ring_and_gives_it_back() -> None:
    with running(OPENERS, popups=MENU_POPUP) as w:
        assert w.warnings() == [], w.warnings()
        assert tab(w.window, w.view) == "Opener"
        w.manager.popups.call("Button", w.uses[0], "File_Menu", None)
        op = w.manager.popups.current
        assert op is not None
        menu = next(n for n in op.view.nodes.values() if n.get("role") == "menu")
        assert menu.get("focused") and list(menu.get("shadows")) == ring_of(w.manager.look)
        assert [n.get("role") for n in op.view.tab_stops()] == ["menu"]  # the Menu is one stop
        w.manager.popups.close(op, "escape")
        assert focused(w.view) == ["Opener"] and ring_on(
            w.view, w.of_use("Button", "Root"), w.manager.look
        )


def test_a_menu_opened_by_a_click_takes_no_focus_and_the_opener_gets_none_back_with_a_ring() -> (
    None
):
    with running(OPENERS, popups=MENU_POPUP) as w:
        opener = w.of_use("Button", "Root")
        w.window.simulate("click", node=opener)
        op = w.manager.popups.current
        assert op is not None
        menu = next(n for n in op.view.nodes.values() if n.get("role") == "menu")
        assert not menu.get("focused")
        w.manager.popups.close(op, "escape")
        assert focused(w.view) == ["Opener"] and not ring_on(w.view, opener, w.manager.look)
