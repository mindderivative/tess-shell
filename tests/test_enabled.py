"""``Enabled``, ``:disabled`` (Block Reference > State, Style Schema > Stylesheet Selectors,
Accessibility rule 5): the key, the style state, the pointer the shell stops itself, and a block
that is disabled or enabled while the shell runs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import pytest
import tess_dl
from loguru import logger
from tess_re import Window

from tess_shell.binder import model as m
from tess_shell.binder.build import View, build
from tess_shell.binder.model import Bool, Color, Handler, Length, Node, Text
from tess_shell.model.look import apply_rules
from tess_shell.schema.look import read_stylesheet
from tess_shell.schema.shell import read_module
from tests.shell_samples import HEADER

BASE = Color(10, 20, 30, 255)
HOVER = Color(40, 50, 60, 255)
PRESS = Color(70, 80, 90, 255)
OFF = Color(100, 110, 120, 255)
SIZE = {"Width": Length(40), "Height": Length(40)}
STATES = {
    "hovered": {"Background": HOVER},
    "pressed": {"Background": PRESS},
    "disabled": {"Background": OFF},
}


def rgba(c: Color) -> tuple[int, int, int, int]:
    return (c.r, c.g, c.b, c.a)


def block(
    name: str = "B",
    enabled: bool | None = None,
    handler: str | None = None,
    states: dict[str, dict[str, Any]] | None = None,
    children: tuple[Node, ...] = (),
) -> Node:
    props: dict[str, m.Value] = dict(SIZE)
    if enabled is not None:
        props["Enabled"] = Bool(enabled)
    return Node(
        "FlexBox",
        name=name,
        props=props,
        style={"Background": BASE},
        states=STATES if states is None else states,
        handlers={"On_Click": Handler(handler)} if handler else {},
        children=children,
    )


def fill(view: View, name: str = "B") -> Any:
    return view.nodes[name].get("fill")


def clicks(view: View) -> list[str]:
    seen: list[str] = []
    view.sink = lambda h, key, raw: seen.append(h.action)
    return seen


# -- the key ----------------------------------------------------------------------------------


def test_enabled_false_sets_tres_disabled_state_and_true_clears_it() -> None:
    window = Window(width=100, height=100)
    view = build([block(enabled=False)], window)
    assert view.nodes["B"].get("disabled") is True
    assert view.update([("B", "Enabled", Bool(True))]) == []
    assert view.nodes["B"].get("disabled") is False
    assert view.update([("B", "Enabled", Bool(False))]) == []
    assert view.nodes["B"].get("disabled") is True


def test_a_block_without_the_key_is_enabled() -> None:
    window = Window(width=100, height=100)
    view = build([block()], window)
    assert view.nodes["B"].get("disabled") is False


def test_a_text_can_be_disabled_and_shows_its_disabled_style() -> None:
    window = Window(width=100, height=100)
    states = {"disabled": {"Foreground": OFF}}
    node = Node(
        "Text",
        name="T",
        props={"Text": Text("x"), "Enabled": Bool(True)},
        style={"Foreground": BASE},
        states=states,
    )
    view = build([node], window)
    wire = view.entries[0].wire
    assert wire is not None and set(wire.states) == {"disabled"} and not wire.wired
    assert fill(view, "T") == rgba(BASE)
    assert view.update([("T", "Enabled", Bool(False))]) == []
    assert view.nodes["T"].get("disabled") is True and fill(view, "T") == rgba(OFF)
    assert view.update([("T", "Enabled", Bool(True))]) == []
    assert fill(view, "T") == rgba(BASE)


# -- the pointer ------------------------------------------------------------------------------


def test_a_disabled_block_runs_no_on_click_and_the_click_is_swallowed_at_the_block() -> None:
    window = Window(width=200, height=100)
    inner = block("Inner", enabled=False, handler="inner")
    outer = block("Outer", handler="outer", children=(inner,))
    view = build([outer], window)
    seen = clicks(view)
    window.simulate("click", node=view.nodes["Inner"])
    assert seen == []  # neither its own handler nor the block behind it
    view.update([("Inner", "Enabled", Bool(True))])
    window.simulate("click", node=view.nodes["Inner"])
    assert seen == ["inner"]  # enabled again: the normal behaviour


def test_a_disabled_block_with_no_handler_still_keeps_the_click_from_the_block_above() -> None:
    window = Window(width=200, height=100)
    plain = block("Plain", enabled=False)
    view = build([block("Outer", handler="outer", children=(plain,))], window)
    seen = clicks(view)
    window.simulate("click", node=view.nodes["Plain"])
    assert seen == []
    view.update([("Plain", "Enabled", Bool(True))])
    window.simulate("click", node=view.nodes["Plain"])
    assert seen == ["outer"]  # a block that is enabled lets the click bubble, as before


def test_the_blocks_under_a_disabled_block_take_no_pointer_either() -> None:
    window = Window(width=200, height=100)
    child = block("Child", handler="child")
    view = build([block("Parent", enabled=False, children=(child,))], window)
    seen = clicks(view)
    window.simulate("pointer_enter", node=view.nodes["Child"])
    assert fill(view, "Child") == rgba(BASE)  # no hovered under a disabled block
    window.simulate("click", node=view.nodes["Child"])
    assert seen == []
    view.update([("Parent", "Enabled", Bool(True))])
    window.simulate("click", node=view.nodes["Child"])
    assert seen == ["child"]


def test_a_disabled_block_is_never_hovered_or_pressed_and_shows_the_disabled_look() -> None:
    window = Window(width=100, height=100)
    view = build([block(enabled=False)], window)
    node = view.nodes["B"]
    assert fill(view) == rgba(OFF)
    window.simulate("pointer_enter", node=node)
    window.simulate("pointer_down", node=node)
    assert fill(view) == rgba(OFF)
    window.simulate("pointer_up", node=node)
    window.simulate("pointer_leave")
    assert fill(view) == rgba(OFF)


def test_disabling_a_hovered_block_clears_the_hover_and_enabling_restores_normal_behaviour() -> (
    None
):
    window = Window(width=100, height=100)
    view = build([block()], window)
    node = view.nodes["B"]
    window.simulate("pointer_enter", node=node)
    window.simulate("pointer_down", node=node)
    assert fill(view) == rgba(PRESS)
    assert view.update([("B", "Enabled", Bool(False))]) == []
    assert fill(view) == rgba(OFF)  # disabled beats pressed and hovered
    view.update([("B", "Enabled", Bool(True))])
    assert fill(view) == rgba(BASE)  # the base back, exactly, not the hover it was in
    window.simulate("pointer_leave")
    window.simulate("pointer_enter", node=node)
    assert fill(view) == rgba(HOVER)  # and the next pointer event works again
    window.simulate("pointer_down", node=node)
    assert fill(view) == rgba(PRESS)


def test_a_press_that_starts_on_a_block_enabled_again_takes_the_press() -> None:
    window = Window(width=100, height=100)
    view = build([block(enabled=False)], window)
    node = view.nodes["B"]
    view.update([("B", "Enabled", Bool(True))])
    window.simulate("pointer_down", node=node)  # no enter was seen: a press is over the node
    assert fill(view) == rgba(PRESS)


def test_hooks_do_not_run_over_a_disabled_block_and_leave_runs_when_it_becomes_one() -> None:
    window = Window(width=100, height=100)
    view = build([block(enabled=False)], window)
    wire = view.entries[0].wire
    assert wire is not None
    seen: list[str] = []

    def note(event: str) -> Callable[[], None]:
        return lambda: seen.append(event)

    for event in ("enter", "leave", "down", "up"):
        wire.add_hook(event, note(event))
    window.simulate("pointer_enter", node=view.nodes["B"])
    window.simulate("pointer_leave")
    assert seen == []  # a tooltip hangs on the enter hook: none opens over a disabled block
    view.update([("B", "Enabled", Bool(True))])
    window.simulate("pointer_enter", node=view.nodes["B"])
    assert seen == ["enter"]
    view.update([("B", "Enabled", Bool(False))])
    assert seen == ["enter", "leave"]  # told, so a pending tooltip is cancelled


# -- a reload ---------------------------------------------------------------------------------


def test_a_reload_that_flips_or_drops_enabled_updates_the_node_without_replacing_it() -> None:
    window = Window(width=100, height=100)
    view = build([block(enabled=True)], window)
    node = view.nodes["B"]
    stats = view.rebuild([block(enabled=False)])
    assert (stats.created, stats.removed) == (0, 0)
    assert view.nodes["B"] == node and node.get("disabled") is True and fill(view) == rgba(OFF)
    stats = view.rebuild([block()])  # the key is gone: enabled again, the same node
    assert (stats.created, stats.removed) == (0, 0)
    assert view.nodes["B"] == node and node.get("disabled") is False and fill(view) == rgba(BASE)


def test_a_reload_that_disables_a_hovered_block_clears_its_hover() -> None:
    window = Window(width=100, height=100)
    view = build([block()], window)
    window.simulate("pointer_enter", node=view.nodes["B"])
    view.rebuild([block(enabled=False)])
    assert fill(view) == rgba(OFF)
    view.rebuild([block(enabled=True)])
    assert fill(view) == rgba(BASE)


def test_a_reload_that_adds_a_handler_to_a_disabled_block_still_swallows() -> None:
    window = Window(width=200, height=100)
    view = build(
        [block("Outer", handler="outer", children=(block("Inner", enabled=False),))], window
    )
    seen = clicks(view)
    view.rebuild(
        [block("Outer", handler="outer", children=(block("Inner", enabled=False, handler="in"),))]
    )
    window.simulate("click", node=view.nodes["Inner"])
    assert seen == []


# -- the schema -------------------------------------------------------------------------------

HEAD = "---\nTDL: 0.1\nName: Btn\n---\n"


def read(body: str) -> tuple[Any, list[Any]]:
    result = tess_dl.parse(HEAD + body, path="Modules/Btn_Module.tdl")
    assert result.document is not None
    return read_module(result.document, "Modules/Btn_Module.tdl")


def test_enabled_is_read_on_a_block_as_a_value_and_as_a_slot() -> None:
    found, findings = read(
        "Module { Params { on { Type: boolean, Default: true } }\n"
        "FlexBox { Enabled: false, Children { Spacer { Enabled: {{ params.on }} } } } }"
    )
    assert found is not None and findings == []
    (root,) = found.children
    assert root.props["Enabled"] == Bool(False)
    (spacer,) = root.children
    assert isinstance(spacer.props["Enabled"], m.SlotValue)


def test_enabled_takes_true_or_false_and_names_the_position() -> None:
    found, findings = read("Module { FlexBox { Enabled: maybe } }")
    assert found is None
    (f,) = [x for x in findings if x.severity == "error"]
    assert f.line == 5 and "Enabled" in f.message and "true or false" in f.message


# -- the style state --------------------------------------------------------------------------

SHEET = """
Stylesheet {
    Rule { Selector: "FlexBox:disabled", Background: "#010101" }
    Rule { Selector: ".card:disabled", Background: "#0a0a0a", Border_Width: 2 }
    Rule { Selector: "#main:disabled", Background: "#646464" }
    Rule { Selector: "FlexBox:hovered", Background: "#020202" }
}
"""


def sheet(text: str, modules: set[str] | None = None) -> Any:
    result = tess_dl.parse(HEADER + text, path="S_Stylesheet.tdl")
    assert result.document is not None
    return read_stylesheet(result.document, "S_Stylesheet.tdl", modules or set())


def test_disabled_is_a_built_state_and_focused_is_still_skipped() -> None:
    s, findings = sheet(
        'Stylesheet { Rule { Selector: "FlexBox:disabled", Background: "#fff" }\n'
        'Rule { Selector: "FlexBox:focused", Background: "#fff" } }'
    )
    assert [r.state for r in s.rules] == ["disabled"]
    (f,) = findings
    assert f.severity == "warning" and ":focused" in f.message and "M6" in f.message


def test_a_disabled_rule_folds_in_by_the_precedence_of_the_other_states() -> None:
    s, findings = sheet(SHEET)
    assert findings == []
    box = m.Node("FlexBox", name="main", classes=("card",))
    (out,) = apply_rules((box,), s.rules)
    assert isinstance(out, m.Node)
    # a name beats a class beats a type; the class's other key stays
    assert out.states["disabled"]["Background"] == m.Color(100, 100, 100, 255)
    assert out.states["disabled"]["Border_Width"] == m.Number(2)
    assert out.states["hovered"]["Background"] == m.Color(2, 2, 2, 255)
    (other,) = apply_rules((m.Node("FlexBox", name="x", classes=("card",)),), s.rules)
    assert isinstance(other, m.Node)
    assert other.states["disabled"]["Background"] == m.Color(10, 10, 10, 255)


@pytest.mark.parametrize("state", ["hovered", "pressed", "disabled"])
def test_a_state_style_converts_like_the_base_style(state: str) -> None:
    window = Window(width=100, height=100)
    node = block(
        states={state: {"Border_Width": m.Number(3)}},
        enabled=False if state == "disabled" else None,
    )
    view = build([node], window)
    if state == "hovered":
        window.simulate("pointer_enter", node=view.nodes["B"])
    elif state == "pressed":
        window.simulate("pointer_down", node=view.nodes["B"])
    assert view.nodes["B"].get("stroke_width") == 3


# -- a tooltip -------------------------------------------------------------------------------


def test_a_tooltip_never_opens_over_a_disabled_block_and_opens_over_an_enabled_one() -> None:
    from tests.test_popup import _SINKS, rig

    tip = (
        "Popup { Name: Tip, Tooltip: true, "
        "Children { FlexBox { Name: Card, Width: 40, Height: 20 } } }"
    )
    for enabled, opens in (("Enabled: false, ", False), ("", True)):
        children = f"FlexBox {{ Name: Tipped, {enabled}Width: 30, Height: 20, Tooltip: Tip }}"
        (r,) = list(rig(tip, children))
        r.bar.window.simulate("pointer_enter", node=r.bar.view.nodes["Tipped"])
        assert (r.popups._enter_timer is not None) is opens
        r.advance(600)
        assert (r.popups.current is not None) is opens
        while _SINKS:  # the rig's log sink: tests/test_popup.py removes them in its own fixture
            logger.remove(_SINKS.pop())
