"""A Bar that starts hidden, and Show, Hide and Toggle on a Bar (UX TSH-051)."""

from __future__ import annotations

from tests.test_panel import manager, surface

SIDE = (
    "Bar { Name: Side, Edge: LEFT, Width: 40, Height: EXPAND, Visible: false, Children {\n"
    "  Rectangle { Name: Dot, Width: 10, Height: 10 } } }"
)


def zone(s: object) -> int:
    return s.window.get("exclusive_zone")  # type: ignore[attr-defined, no-any-return]


def test_a_bar_with_visible_false_starts_hidden_and_reserves_no_space() -> None:
    m = manager(panel=SIDE, hide_mode="KEEP")
    s = surface(m, "Side")
    assert s.hidden is True and s.window is not None
    assert zone(s) == 0 and s.window.root.get("visible") is False
    assert zone(surface(m, "Top_Bar")) == 32


def test_show_gives_the_space_back_and_hide_takes_it_again() -> None:
    m = manager(panel=SIDE, hide_mode="KEEP")
    s = surface(m, "Side")
    m.show(s)
    assert s.hidden is False and zone(s) == 40 and s.window.root.get("visible") is True
    m.hide(s)
    assert s.hidden is True and zone(s) == 0


def test_a_click_handler_toggles_a_bar_by_its_name() -> None:
    m = manager("On_Click { Action: Toggle, Target: Side }", panel=SIDE, hide_mode="KEEP")
    m.sink = lambda handler, key, raw: m.run_builtin(handler)
    top, side = surface(m, "Top_Bar"), surface(m, "Side")
    assert top.view is not None
    top.view.window.simulate("click", node=top.view.nodes["Btn"])
    assert side.hidden is False and zone(side) == 40
    top.view.window.simulate("click", node=top.view.nodes["Btn"])
    assert side.hidden is True and zone(side) == 0
