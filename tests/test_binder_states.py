"""Style states (Style Schema > Stylesheet Selectors): a block with ``:hovered`` and ``:pressed``
styles shows them while the pointer is over it or presses it, and what it had before after."""

from __future__ import annotations

from typing import Any

import pytest
from tess_re import Window

from tess_shell.binder.build import View, build
from tess_shell.binder.model import (
    BindFailed,
    Color,
    Handler,
    Length,
    Node,
    Number,
    Shadows,
    Sides,
    Text,
)

BASE = Color(10, 20, 30, 255)
HOVER = Color(40, 50, 60, 255)
PRESS = Color(70, 80, 90, 255)
SIZE = {"Width": Length(40), "Height": Length(40)}


def rgba(c: Color) -> tuple[int, int, int, int]:
    return (c.r, c.g, c.b, c.a)


def button(
    hover: dict[str, Any] | None = None,
    press: dict[str, Any] | None = None,
    base: dict[str, Any] | None = None,
    **extra: Any,
) -> Node:
    states: dict[str, dict[str, Any]] = {}
    if hover is not None:
        states["hovered"] = hover
    if press is not None:
        states["pressed"] = press
    return Node(
        "FlexBox",
        name="B",
        props=SIZE,
        style={"Background": BASE, **(base or {})},
        states=states,
        **extra,
    )


def shown(view: View, prop: str = "fill") -> Any:
    return view.nodes["B"].get(prop)


def test_hovered_shows_while_the_pointer_is_over_and_the_base_returns_exactly() -> None:
    window = Window(width=100, height=100)
    view = build([button(hover={"Background": HOVER})], window)
    assert shown(view) == rgba(BASE)
    window.simulate("pointer_enter", node=view.nodes["B"])
    assert shown(view) == rgba(HOVER)
    window.simulate("pointer_leave")
    assert shown(view) == rgba(BASE)


def test_pressed_beats_hovered_and_the_remaining_state_applies_when_one_ends() -> None:
    window = Window(width=100, height=100)
    view = build([button({"Background": HOVER}, {"Background": PRESS})], window)
    node = view.nodes["B"]
    window.simulate("pointer_enter", node=node)
    window.simulate("pointer_down", node=node)
    assert shown(view) == rgba(PRESS)
    window.simulate("pointer_up", node=node)
    assert shown(view) == rgba(HOVER)  # still over it
    window.simulate("pointer_down", node=node)
    window.simulate("pointer_leave")
    assert shown(view) == rgba(BASE)  # leaving ends the press too


def test_pressed_keeps_the_hover_values_it_does_not_replace() -> None:
    window = Window(width=100, height=100)
    view = build(
        [button({"Background": HOVER, "Border_Width": Number(3)}, {"Background": PRESS})], window
    )
    node = view.nodes["B"]
    window.simulate("pointer_enter", node=node)
    window.simulate("pointer_down", node=node)
    assert shown(view) == rgba(PRESS) and shown(view, "stroke_width") == 3
    window.simulate("pointer_leave")
    assert shown(view, "stroke_width") == 0  # a key the base never set goes back to tre's value


def test_a_cancelled_press_ends_but_the_pointer_still_hovers() -> None:
    window = Window(width=100, height=100)
    view = build([button({"Background": HOVER}, {"Background": PRESS})], window)
    window.simulate("pointer_down", node=view.nodes["B"])
    view.entries[0].wire.cancel()  # type: ignore[union-attr]  # simulate cannot send pointer_cancel
    assert shown(view) == rgba(HOVER)


def test_a_state_style_converts_like_the_base_style() -> None:
    window = Window(width=100, height=100)
    view = build([button({"Padding": Sides(4, 5, 6, 7)})], window)  # left, top, right, bottom
    window.simulate("pointer_enter", node=view.nodes["B"])
    assert [shown(view, f"padding_{s}") for s in ("left", "top", "right", "bottom")] == [4, 5, 6, 7]
    window.simulate("pointer_leave")
    assert shown(view, "padding_left") == 0


def test_a_click_still_reaches_on_click_and_the_state_goes_on() -> None:
    window = Window(width=100, height=100)
    seen: list[str] = []
    node = button({"Background": HOVER}, handlers={"On_Click": Handler("go")})
    view = build([node], window)
    view.sink = lambda h, key, raw: seen.append(h.action)
    window.simulate("pointer_enter", node=view.nodes["B"])
    window.simulate("click", node=view.nodes["B"])
    assert seen == ["go"] and shown(view) == rgba(HOVER)


def test_a_state_listener_does_not_stop_the_event() -> None:
    window = Window(width=100, height=100)
    outer = Node(
        "FlexBox",
        name="O",
        props=SIZE,
        style={"Background": BASE},
        states={"pressed": {"Background": PRESS}},
        children=(button({"Background": HOVER}),),
    )
    view = build([outer], window)
    window.simulate("pointer_down", node=view.nodes["B"])
    assert view.nodes["O"].get("fill") == rgba(PRESS)  # the press bubbled past the inner block
    window.simulate("pointer_up", node=view.nodes["B"])
    assert view.nodes["O"].get("fill") == rgba(BASE)


def test_a_block_with_no_state_style_takes_no_pointer_listener() -> None:
    window = Window(width=100, height=100)
    view = build([button()], window)
    wire = view.entries[0].wire
    assert wire is not None and not any(k.startswith("state:") for k in wire.wired)


def test_a_text_with_a_state_style_builds_and_is_never_listened_to() -> None:
    window = Window(width=100, height=100)
    states = {"hovered": {"Foreground": HOVER}}
    text = Node("Text", name="B", props={"Text": Text("x")}, states=states)
    view = build([text], window)
    wire = view.entries[0].wire
    assert wire is not None and wire.states == {} and "state:pointer_enter" not in wire.wired


def test_a_state_style_with_a_key_the_block_lacks_is_a_bind_error() -> None:
    with pytest.raises(BindFailed) as failed:
        build([button({"Foreground": HOVER})], Window(width=100, height=100))
    assert "Foreground" in str(failed.value.errors[0]) and "hovered" in str(failed.value.errors[0])


# -- reload and update ------------------------------------------------------------------------


def test_a_rebuild_restyles_a_node_that_is_hovered() -> None:
    window = Window(width=100, height=100)
    view = build([button({"Background": HOVER})], window)
    window.simulate("pointer_enter", node=view.nodes["B"])
    other = Color(1, 2, 3, 255)
    view.rebuild([button({"Background": other})])
    assert shown(view) == rgba(other)  # the new hover look, the pointer is still over it
    window.simulate("pointer_leave")
    assert shown(view) == rgba(BASE)


def test_a_rebuild_that_drops_the_state_style_puts_the_base_back() -> None:
    window = Window(width=100, height=100)
    view = build([button({"Background": HOVER})], window)
    window.simulate("pointer_enter", node=view.nodes["B"])
    view.rebuild([button()])
    assert shown(view) == rgba(BASE)
    window.simulate("pointer_enter", node=view.nodes["B"])
    assert shown(view) == rgba(BASE)  # the old listeners find no state any more


def test_a_rebuild_gives_a_state_style_to_a_node_that_had_none() -> None:
    window = Window(width=100, height=100)
    view = build([button()], window)
    view.rebuild([button({"Background": HOVER})])
    window.simulate("pointer_enter", node=view.nodes["B"])
    assert shown(view) == rgba(HOVER)


def test_a_rebuild_that_changes_the_base_under_a_state_does_not_show_through() -> None:
    window = Window(width=100, height=100)
    view = build([button({"Background": HOVER})], window)
    window.simulate("pointer_enter", node=view.nodes["B"])
    fresh = Color(5, 5, 5, 255)
    view.rebuild([button({"Background": HOVER}, base={"Background": fresh})])
    assert shown(view) == rgba(HOVER)  # the state still holds the colour
    window.simulate("pointer_leave")
    assert shown(view) == rgba(fresh)  # and the node ends on the new base


def test_an_update_of_a_property_a_state_holds_waits_for_the_state_to_end() -> None:
    window = Window(width=100, height=100)
    view = build([button({"Background": HOVER})], window)
    window.simulate("pointer_enter", node=view.nodes["B"])
    fresh = Color(5, 6, 7, 255)
    assert view.update([("B", "Background", fresh)]) == []
    assert shown(view) == rgba(HOVER)
    window.simulate("pointer_leave")
    assert shown(view) == rgba(fresh)


def test_an_update_of_another_property_applies_at_once() -> None:
    window = Window(width=100, height=100)
    view = build([button({"Background": HOVER})], window)
    window.simulate("pointer_enter", node=view.nodes["B"])
    assert view.update([("B", "Opacity", Number(0.5))]) == []
    assert shown(view, "opacity") == 0.5 and shown(view) == rgba(HOVER)


def test_shadows_are_a_state_value_like_any_other() -> None:
    window = Window(width=100, height=100)
    view = build([button({"Shadows": Shadows(())})], window)
    window.simulate("pointer_enter", node=view.nodes["B"])
    assert shown(view, "shadows") == []


# -- hooks for another feature on the same node ------------------------------------------------


def test_a_hook_runs_after_the_state_changes_and_shares_the_listener() -> None:
    window = Window(width=100, height=100)
    view = build([button({"Background": HOVER})], window)
    wire = view.entries[0].wire
    assert wire is not None
    seen: list[tuple[str, Any]] = []
    wire.add_hook("enter", lambda: seen.append(("enter", shown(view))))
    wire.add_hook("leave", lambda: seen.append(("leave", shown(view))))
    window.simulate("pointer_enter", node=view.nodes["B"])
    window.simulate("pointer_leave")
    assert seen == [("enter", rgba(HOVER)), ("leave", rgba(BASE))]
