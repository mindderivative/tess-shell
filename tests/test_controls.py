# ruff: noqa: E501
"""The M4c interactive widgets headless: Button, Toggle, Checkbox (Standard Modules > Pointer and
Input Controls) and what they stand on, the controls of ``binder.controls``."""

from __future__ import annotations

from typing import Any

from tess_shell.appearance import Appearance
from tests.widgets_live import Widgets, running

CLICK = 'On_Click { Action: Call, Target: "Driver.pressed" }'
RELEASED = 'On_Released { Action: Call, Target: "Driver.released" }'
CHANGED = 'On_Changed { Action: Call, Target: "Driver.changed" }'


def seen(w: Widgets) -> list[Any]:
    return w.host.loaded["Driver"].instance.seen  # type: ignore[no-any-return,attr-defined]


# -- Button ------------------------------------------------------------------------------------


def test_button_has_a_role_a_name_and_shows_its_text() -> None:
    with running(f'Button {{ Text: "Save", {CLICK} }}') as w:
        assert w.warnings() == [], w.warnings()
        root = w.of_use("Button", "Root")
        assert root.get("role") == "button" and root.get("label") == "Save"
        assert w.of_use("Button", "Words").get("text") == "Save"


def test_button_states_hover_pressed_and_disabled_show() -> None:
    with running(f'Button {{ Text: "Go", {CLICK} }}') as w:
        root = w.of_use("Button", "Root")
        base = root.get("stroke_color")
        w.window.simulate("pointer_enter", node=root)
        assert root.get("stroke_color") == (91, 151, 201, 255) != base  # primary
        w.window.simulate("pointer_down", node=root)
        assert root.get("fill") == (85, 101, 122, 255)  # outline
        w.window.simulate("pointer_up", node=root)
        assert root.get("fill") != (85, 101, 122, 255)
    with running(f'Button {{ Text: "Go", Enabled: false, {CLICK} }}') as w:
        root = w.of_use("Button", "Root")
        assert root.get("disabled") is True and root.get("opacity") == 0.5


def test_button_click_runs_the_action_and_a_disabled_button_ignores_it() -> None:
    with running(f"Button {{ Text: Go, {CLICK} }}") as w:
        root = w.of_use("Button", "Root")
        w.window.simulate("click", node=root)
        assert len(seen(w)) == 1
    with running(f"Button {{ Text: Go, Enabled: false, {CLICK} }}") as w:
        w.window.simulate("click", node=w.of_use("Button", "Root"))
        assert seen(w) == []


def test_button_with_an_icon_and_a_label_places_the_icon_at_either_end() -> None:
    with running('Button { Text: "Open", Icon: "mdi:home" }') as w:
        glyph = w.of_use("Button", "Glyph")
        assert glyph.get("left") == 10 and glyph.get("top") == 8
        assert w.of_use("Button", "Root").get("padding_left") == 36
    with running('Button { Text: "Open", Icon: "mdi:home", Icon_Position: END }') as w:
        glyph = w.of_use("Button", "Glyph")
        assert glyph.get("right") == 10
        root = w.of_use("Button", "Root")
        assert root.get("padding_right") == 36 and root.get("padding_left") == 12


def test_an_icon_only_button_warns_without_a_label_and_names_itself_with_one() -> None:
    with running('Button { Icon: "mdi:home" }') as w:
        assert any("needs a Label" in x for x in w.warnings())
    with running('Button { Icon: "mdi:home", Label: "Home" }') as w:
        assert w.warnings() == []
        assert w.of_use("Button", "Root").get("label") == "Home"


# -- Toggle and Checkbox -----------------------------------------------------------------------


def test_toggle_click_flips_it_and_raises_on_changed_once() -> None:
    with running(f'Toggle {{ Label: "Wi-Fi", {CHANGED} }}') as w:
        assert w.warnings() == [], w.warnings()
        root = w.of_use("Toggle", "Root")
        assert root.get("role") == "switch" and root.get("checked") is False
        thumb = w.of_use("Toggle", "Thumb")
        assert thumb.get("margin_left") == 3
        w.window.simulate("click", node=root)
        w.advance(500)
        assert root.get("checked") is True
        assert seen(w) == [("changed", seen(w)[0][1], False, True, True)]
        assert thumb.get("margin_left") == 21  # the :checked margin, eased
        assert w.of_use("Toggle", "Track").get("fill") == (91, 151, 201, 255)
        w.window.simulate("click", node=root)
        w.advance(500)
        assert (
            root.get("checked") is False and len(seen(w)) == 2 and seen(w)[1][3:] == (False, False)
        )
        assert thumb.get("margin_left") == 3


def test_toggle_thumb_eases_and_switches_at_once_under_reduced_motion() -> None:
    with running("Toggle { }") as w:
        root = w.of_use("Toggle", "Root")
        thumb = w.of_use("Toggle", "Thumb")
        w.window.simulate("click", node=root)
        w.advance(60)
        assert 3 < thumb.get("margin_left") < 21  # on its way
        w.advance(500)
        assert thumb.get("margin_left") == 21
    with running("Toggle { }", appearance=Appearance(reduced_motion=True)) as w:
        w.window.simulate("click", node=w.of_use("Toggle", "Root"))
        w.advance(16)
        assert w.of_use("Toggle", "Thumb").get("margin_left") == 21


def test_toggle_set_from_a_param_moves_without_the_event_and_the_user_keeps_their_edit() -> None:
    driver = "Module { FlexBox { Children { Toggle { Name: T, Checked: {{ on }}, On_Changed: changed } } } }"
    code = "from tess_shell import Module, action\nclass Driver(Module):\n    def __init__(self):\n        self.seen = []\n    def start(self):\n        self.ctx.send('on', False)\n    @action\n    def changed(self, event):\n        self.seen.append(event.value)\n"
    with running("Driver { }", driver=driver, driver_py=code) as w:
        root = w.of_use("Toggle", "Root")
        w.send("on", True)
        w.advance(16)
        assert root.get("checked") is True and seen(w) == []
        w.window.simulate("click", node=root)  # the user turns it off
        assert root.get("checked") is False and seen(w) == [False]
        w.send("on", True)  # no change of the param value (still True): the user's edit stays
        assert root.get("checked") is False
        w.send("on", False)  # the module sets a different value
        w.advance(16)
        assert root.get("checked") is False and seen(w) == [False]
        w.send("on", True)
        w.advance(16)
        assert root.get("checked") is True and seen(w) == [False]


def test_a_disabled_toggle_ignores_the_pointer_and_shows_disabled() -> None:
    with running(f"Toggle {{ Enabled: false, {CHANGED} }}") as w:
        root = w.of_use("Toggle", "Root")
        w.window.simulate("click", node=root)
        assert root.get("checked") is False and seen(w) == []
        assert root.get("disabled") is True and root.get("opacity") == 0.5


def test_checkbox_flips_by_the_box_and_by_the_label_and_draws_a_mark() -> None:
    with running(f'Checkbox {{ Text: "Remember me", {CHANGED} }}') as w:
        assert w.warnings() == [], w.warnings()
        root = w.of_use("Checkbox", "Root")
        assert root.get("role") == "checkbox" and root.get("label") == "Remember me"
        mark = w.of_use("Checkbox", "Mark")
        assert mark.get("opacity") == 0
        w.window.simulate("click", node=w.of_use("Checkbox", "Words"))
        w.advance(500)
        assert root.get("checked") is True and mark.get("opacity") == 1
        assert w.of_use("Checkbox", "Box").get("fill") == (91, 151, 201, 255)
        w.window.simulate("click", node=w.of_use("Checkbox", "Box"))
        w.advance(500)
        assert root.get("checked") is False and mark.get("opacity") == 0
        assert [x[4] for x in seen(w)] == [True, False]


def test_on_changed_on_a_module_that_is_not_a_control_is_an_error() -> None:
    with running(f"Label {{ Text: x, {CHANGED} }}") as w:
        assert any("Label does not raise On_Changed" in x for x in w.lines)


# -- Slider ------------------------------------------------------------------------------------


def press(w: Widgets, node: Any, x: float, y: float = 10) -> None:
    w.window.simulate("pointer_down", node=node, x=x, y=y)


def test_slider_role_value_range_and_parts() -> None:
    with running("Slider { Value: 25, Min: 0, Max: 50, Step: 5, Label: Volume }") as w:
        assert w.warnings() == [], w.warnings()
        root = w.of_use("Slider", "Root")
        assert root.get("role") == "slider" and root.get("label") == "Volume"
        assert (root.get("value"), root.get("value_min"), root.get("value_max")) == (25, 0, 50)
        assert root.get("value_step") == 5
        handle = w.of_use("Slider", "Handle")
        fill = w.of_use("Slider", "Fill")
        # 160 wide, a 16 handle: half way is 72 px of travel
        assert handle.get("translate_x") == 72
        assert fill.get("width") == 72 + 8
        assert handle.get("fill") == (91, 151, 201, 255)


def test_slider_drag_moves_the_value_in_steps_and_the_handle_follows() -> None:
    with running(f"Slider {{ Value: 0, Step: 10, {CHANGED} }}") as w:
        root = w.of_use("Slider", "Root")
        handle = w.of_use("Slider", "Handle")
        press(w, root, 8)  # the handle's centre at the left end: 0
        assert root.get("value") == 0 and seen(w) == []
        w.window.simulate("pointer_move", node=root, x=84, y=10)  # 76/144 of the travel: 52.8 -> 50
        assert root.get("value") == 50 and handle.get("translate_x") == 72
        w.window.simulate("pointer_move", node=root, x=84 + 14.4, y=10)  # 60
        w.window.simulate("pointer_move", node=root, x=84 + 15, y=10)  # still 60: nothing new
        w.window.simulate("pointer_move", node=root, x=500, y=10)  # beyond the end: 100
        w.window.simulate("pointer_up", node=root, x=500, y=10)
        assert root.get("value") == 100
        assert [x[4] for x in seen(w)] == [50, 60, 100] and seen(w)[0][2] == 0
        w.window.simulate("pointer_move", node=root, x=20, y=10)  # no button: no drag
        assert root.get("value") == 100


def test_slider_click_on_the_track_jumps_the_handle_and_raises_once() -> None:
    with running(f"Slider {{ Value: 0, Min: 0, Max: 100, {CHANGED} }}") as w:
        root = w.of_use("Slider", "Root")
        press(w, root, 80)
        w.window.simulate("pointer_up", node=root, x=80, y=10)
        assert root.get("value") == 50 and len(seen(w)) == 1 and seen(w)[0][3] == 50


def test_slider_handle_shows_hovered_pressed_and_released() -> None:
    with running("Slider { Value: 50 }") as w:
        root = w.of_use("Slider", "Root")
        handle = w.of_use("Slider", "Handle")
        base = handle.get("stroke_width")
        press(w, root, 30)  # the pointer is on the track, not on the handle: still pressed
        assert handle.get("stroke_width") == 3 != base
        w.window.simulate("pointer_up", node=root, x=30, y=10)
        assert handle.get("stroke_width") == base


def test_slider_value_set_from_a_param_moves_without_the_event_and_the_users_value_stays() -> None:
    driver = "Module { FlexBox { Children { Slider { Name: S, Value: {{ v }}, On_Changed: changed } } } }"
    code = "from tess_shell import Module, action\nclass Driver(Module):\n    def __init__(self):\n        self.seen = []\n    def start(self):\n        self.ctx.send('v', 10)\n    @action\n    def changed(self, event):\n        self.seen.append(event.value)\n"
    with running("Driver { }", driver=driver, driver_py=code) as w:
        root = w.of_use("Slider", "Root")
        assert root.get("value") == 10
        w.send("v", 40)
        assert root.get("value") == 40 and seen(w) == []
        press(w, root, 8 + 144)  # the user drags to the end
        w.window.simulate("pointer_up", node=root, x=152, y=10)
        assert root.get("value") == 100 and seen(w) == [100]
        w.send("v", 40)  # the param keeps its value: the user's stays
        assert root.get("value") == 100
        w.send("v", 20)
        assert root.get("value") == 20 and seen(w) == [100]


def test_a_disabled_slider_ignores_the_pointer_and_shows_disabled() -> None:
    with running(f"Slider {{ Value: 10, Enabled: false, {CHANGED} }}") as w:
        root = w.of_use("Slider", "Root")
        press(w, root, 100)
        w.window.simulate("pointer_up", node=root, x=100, y=10)
        assert root.get("value") == 10 and seen(w) == []
        assert w.of_use("Slider", "Handle").get("fill") == (159, 174, 191, 255)  # on_surface_muted


def test_vertical_slider_runs_upwards() -> None:
    with running(f"Slider {{ Orientation: VERTICAL, Value: 0, {CHANGED} }}") as w:
        root = w.of_use("Slider", "Root")
        assert root.get("layout_height") == 160 and root.get("layout_width") == 20
        press(w, root, 10, 8)  # the top end: the maximum
        assert root.get("value") == 100
        w.window.simulate(
            "pointer_move",
            node=root,
            x=10,
            y=80,
        )
        assert root.get("value") == 50
        w.window.simulate("pointer_up", node=root, x=10, y=80)
        assert w.of_use("Slider", "Handle").get("translate_y") == 72


def test_a_slider_range_that_is_wrong_is_reported() -> None:
    with running("Slider { Min: 5, Max: 5 }") as w:
        assert any(
            "Max (5) must be above Min (5)" in x
            for x in w.log().splitlines() + [str(p) for p in w.problems]
        )


# -- ScrollBox and List ------------------------------------------------------------------------

ENTRIES = " ".join(
    f'FlexBox {{ Class: list_item, Key: k{i}, Height: 30, Children {{ Text {{ Text: "Entry {i}", Width: AUTO, Height: AUTO }} }} }}'
    for i in range(1, 13)
)


def test_scrollbox_scrolls_its_one_child_by_the_wheel() -> None:
    body = (
        "ScrollBox { Name: S, Width: 100, Height: 60, Children { FlexBox { Flex: VERTICAL, Children { "
        + ENTRIES.replace("Class: list_item,", "")
        + " } } } }"
    )
    driver = f"Module {{ FlexBox {{ Children {{ {body} }} }} }}"
    with running("Driver { }", driver=driver) as w:
        view = w.node("S")
        assert view.get("orientation") == "vertical" and view.get("scroll_offset") == 0
        w.window.simulate("wheel", node=view, delta_y=50)
        w.advance(300)
        assert view.get("scroll_offset") > 0


def test_scrollbox_with_two_children_is_an_error() -> None:
    driver = "Module { FlexBox { Children { ScrollBox { Children { Box { } Box { } } } } } }"
    with running("Driver { }", driver=driver) as w:
        assert any("a ScrollBox scrolls one child" in x for x in w.lines)


def test_list_scrolls_by_the_wheel_chooses_by_a_click_and_marks_the_entry() -> None:
    with running(f"List {{ Height: 90, Label: Files, {CHANGED}, Children {{ {ENTRIES} }} }}") as w:
        assert w.warnings() == [], w.warnings()
        root = w.of_use("List", "Root")
        assert root.get("role") == "list" and root.get("label") == "Files"
        entries = [n for k, n in w.view.nodes.items() if k.endswith("/Items")]
        assert len(entries) == 1
        items = entries[0].children()
        assert len(items) == 12 and items[0].get("role") == "listitem"
        assert items[0].get("selected") is False
        w.window.simulate("wheel", node=root, delta_y=60)
        w.advance(300)
        assert root.get("scroll_offset") > 0
        w.window.simulate("click", node=items[2])
        assert items[2].get("selected") is True and items[0].get("selected") is False
        assert [(x[2], x[3]) for x in seen(w)] == [("", "k3")]
        # the :selected look: a primary ring
        assert (
            items[2].get("stroke_color") == (91, 151, 201, 255)
            and items[2].get("stroke_width") == 2
        )
        w.window.simulate("click", node=items[2])  # again: nothing new
        w.window.simulate("click", node=items[4])
        assert items[2].get("selected") is False and items[4].get("selected") is True
        assert len(seen(w)) == 2 and seen(w)[1][2:4] == ("k3", "k5")
        # a click on the text of an entry chooses the entry
        w.window.simulate("click", node=items[0].children()[0])
        assert items[0].get("selected") is True


def test_list_selected_from_a_param_marks_without_the_event() -> None:
    driver = (
        "Module { FlexBox { Children { List { Name: L, Selected: {{ pick }}, On_Changed: changed, "
        f"Children {{ {ENTRIES} }} }} }} }} }}"
    )
    code = "from tess_shell import Module, action\nclass Driver(Module):\n    def __init__(self):\n        self.seen = []\n    def start(self):\n        self.ctx.send('pick', 'k2')\n    @action\n    def changed(self, event):\n        self.seen.append(event.value)\n"
    with running("Driver { }", driver=driver, driver_py=code) as w:
        items = [n for k, n in w.view.nodes.items() if k.endswith("/Items")][0].children()
        assert items[1].get("selected") is True
        w.send("pick", "k4")
        assert items[1].get("selected") is False and items[3].get("selected") is True
        assert seen(w) == []
        w.window.simulate("click", node=items[0])
        assert items[0].get("selected") is True and seen(w) == ["k1"]


def test_list_with_selection_none_takes_no_choice_and_a_disabled_entry_is_skipped() -> None:
    with running(f"List {{ Selection: NONE, {CHANGED}, Children {{ {ENTRIES} }} }}") as w:
        items = [n for k, n in w.view.nodes.items() if k.endswith("/Items")][0].children()
        w.window.simulate("click", node=items[1])
        assert not items[1].get("selected") and seen(w) == []
    entries = ENTRIES.replace("Key: k2,", "Key: k2, Enabled: false,")
    with running(f"List {{ {CHANGED}, Children {{ {entries} }} }}") as w:
        items = [n for k, n in w.view.nodes.items() if k.endswith("/Items")][0].children()
        w.window.simulate("click", node=items[1])
        assert items[1].get("selected") is False and seen(w) == []


def test_a_for_entry_is_chosen_by_its_repeater_key() -> None:
    driver = (
        "Module { FlexBox { Children { List { Name: L, On_Changed: changed, Children { "
        "For w In {{ rows }} Key {{ w.id }} { FlexBox { Class: list_item, Height: 30, "
        "Children { Text { Text: {{ w.name }}, Width: AUTO, Height: AUTO } } } } } } } } }"
    )
    code = "from tess_shell import Module, action\nclass Driver(Module):\n    def __init__(self):\n        self.seen = []\n    def start(self):\n        self.ctx.send('rows', [{'id': 'a', 'name': 'Alpha'}, {'id': 'b', 'name': 'Beta'}])\n    @action\n    def changed(self, event):\n        self.seen.append(event.value)\n"
    with running("Driver { }", driver=driver, driver_py=code) as w:
        items = [n for k, n in w.view.nodes.items() if k.endswith("/Items")][0].children()
        assert len(items) == 2
        w.window.simulate("click", node=items[1])
        assert seen(w) == ["b"] and items[1].get("selected") is True


def test_a_controls_state_survives_a_rebuild_of_its_surface() -> None:
    driver = (
        "Module { FlexBox { Children { Toggle { Name: T, Checked: {{ on }}, On_Changed: changed } "
        "If {{ extra }} { Text { Text: more, Width: AUTO, Height: AUTO } } "
        "Slider { Name: S, Value: {{ v }} } } } }"
    )
    code = (
        "from tess_shell import Module, action\n"
        "class Driver(Module):\n    def __init__(self):\n        self.seen = []\n"
        "    def start(self):\n        self.ctx.send('on', False)\n        self.ctx.send('extra', False)\n"
        "        self.ctx.send('v', 20)\n"
        "    @action\n    def changed(self, event):\n        self.seen.append(event.value)\n"
    )
    with running("Driver { }", driver=driver, driver_py=code) as w:
        toggle = w.of_use("Toggle", "Root")
        slider = w.of_use("Slider", "Root")
        w.window.simulate("click", node=toggle)
        w.window.simulate("pointer_down", node=slider, x=152, y=10)
        w.window.simulate("pointer_up", node=slider, x=152, y=10)
        assert toggle.get("checked") is True and slider.get("value") == 100
        w.send("extra", True)  # the If shows a Text: the surface is rebuilt by the keyed diff
        w.advance(16)
        assert w.of_use("Toggle", "Root") == toggle  # the same node
        assert toggle.get("checked") is True and slider.get("value") == 100
        assert seen(w) == [True]
        w.window.simulate("click", node=toggle)
        assert toggle.get("checked") is False and seen(w) == [True, False]


# -- Slider On_Released ------------------------------------------------------------------------


def kinds(w: Widgets) -> list[str]:
    return [x[0] for x in seen(w)]


def test_released_fires_once_after_a_drag_released_inside_with_the_final_value() -> None:
    with running(f"Slider {{ Value: 0, Step: 10, {CHANGED}, {RELEASED} }}") as w:
        root = w.of_use("Slider", "Root")
        press(w, root, 8)
        w.window.simulate("pointer_move", node=root, x=84, y=10)  # 50
        w.window.simulate("pointer_move", node=root, x=84 + 14.4, y=10)  # 60
        assert kinds(w) == ["changed", "changed"]  # nothing released while it moves
        w.window.simulate("pointer_up", node=root, x=84 + 14.4, y=10)
        assert kinds(w) == ["changed", "changed", "released"]
        _, _, old, new, value = seen(w)[-1]
        assert (old, new, value) == (0, 60, 60)
        w.window.simulate("pointer_up", node=root, x=84, y=10)  # no press: nothing more
        assert kinds(w).count("released") == 1


def test_released_fires_when_the_button_is_let_go_outside_the_slider() -> None:
    with running(f"Slider {{ Value: 0, {CHANGED}, {RELEASED} }}") as w:
        root = w.of_use("Slider", "Root")
        press(w, root, 8)
        w.window.simulate("pointer_move", node=root, x=900, y=300)  # far outside: captured
        w.window.simulate("pointer_up", node=root, x=900, y=300)
        assert kinds(w) == ["changed", "released"] and seen(w)[-1][4] == 100
        assert not root.get("disabled")


def test_released_fires_after_a_click_on_the_track_and_after_a_press_that_moved_nothing() -> None:
    with running(f"Slider {{ Value: 0, {CHANGED}, {RELEASED} }}") as w:
        root = w.of_use("Slider", "Root")
        press(w, root, 80)
        w.window.simulate("pointer_up", node=root, x=80, y=10)
        assert kinds(w) == ["changed", "released"] and seen(w)[-1][4] == 50
        press(w, root, 80)  # on the value it has: no change, still a release with that value
        w.window.simulate("pointer_up", node=root, x=80, y=10)
        assert kinds(w) == ["changed", "released", "released"]
        assert seen(w)[-1][2:] == (50, 50, 50)


def test_on_changed_is_raised_as_many_times_as_before_released_adds_none() -> None:
    with running(f"Slider {{ Value: 0, Step: 10, {CHANGED} }}") as w:
        root = w.of_use("Slider", "Root")
        press(w, root, 8)
        for x in (84, 98.4, 500):
            w.window.simulate("pointer_move", node=root, x=x, y=10)
        w.window.simulate("pointer_up", node=root, x=500, y=10)
        assert kinds(w) == ["changed"] * 3  # no On_Released written: none raised
    with running(f"Slider {{ Value: 0, Step: 10, {CHANGED}, {RELEASED} }}") as w:
        root = w.of_use("Slider", "Root")
        press(w, root, 8)
        for x in (84, 98.4, 500):
            w.window.simulate("pointer_move", node=root, x=x, y=10)
        w.window.simulate("pointer_up", node=root, x=500, y=10)
        assert kinds(w) == ["changed"] * 3 + ["released"]


def test_a_disabled_slider_raises_no_released_and_one_disabled_mid_drag_ends_it_once() -> None:
    with running(f"Slider {{ Value: 10, Enabled: false, {RELEASED} }}") as w:
        root = w.of_use("Slider", "Root")
        press(w, root, 100)
        w.window.simulate("pointer_up", node=root, x=100, y=10)
        assert seen(w) == []
    driver = f"Module {{ FlexBox {{ Children {{ Slider {{ Name: S, Enabled: {{{{ on }}}}, {RELEASED} }} }} }} }}"
    code = (
        "from tess_shell import Module, action\nclass Driver(Module):\n"
        "    def __init__(self):\n        self.seen = []\n"
        "    def start(self):\n        self.ctx.send('on', True)\n"
        "    @action\n    def released(self, event):\n        self.seen.append(event.value)\n"
    )
    with running("Driver { }", driver=driver, driver_py=code) as w:
        root = w.of_use("Slider", "Root")
        press(w, root, 80)
        w.send("on", False)  # the slider is disabled while the button is down
        assert seen(w) == [50]
        w.window.simulate("pointer_up", node=root, x=80, y=10)
        assert seen(w) == [50]  # the release is not a second one


def test_on_released_is_an_error_on_a_plain_block_and_on_a_module_that_is_not_a_slider() -> None:
    with running(f"Toggle {{ {RELEASED} }}") as w:
        assert any("Toggle does not raise On_Released" in x for x in w.lines)
    with running(f"Label {{ Text: x, {RELEASED} }}") as w:
        assert any("Label does not raise On_Released" in x for x in w.lines)


def test_a_call_to_released_with_an_unknown_argument_is_still_checked() -> None:
    code = (
        "from tess_shell import Module, action\nclass Driver(Module):\n"
        "    def __init__(self):\n        self.seen = []\n"
        "    @action\n    def released(self, event, position):\n"
        "        self.seen.append(position)\n"
    )
    good = 'On_Released { Action: Call, Target: "Driver.released", position: {{ event.value }} }'
    with running(f"Slider {{ Value: 0, {good} }}", driver_py=code) as w:
        assert w.problems == []
        root = w.of_use("Slider", "Root")
        press(w, root, 80)
        w.window.simulate("pointer_up", node=root, x=80, y=10)
        assert seen(w) == [50]  # the argument is the final value
    bad = 'On_Released { Action: Call, Target: "Driver.released", Nope: 1 }'
    with running(f"Slider {{ {bad} }}", driver_py=code) as w:
        assert any("has no argument Nope" in p.message for p in w.problems), w.problems
