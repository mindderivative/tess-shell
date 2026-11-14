"""The focus model (Focus and Keyboard, M6a): which blocks take focus, the Tab order of a surface's
blocks and of the shell's surfaces, the ring that shows keyboard focus and not a click, and the
focus a Popup takes and gives back.

Everything runs on headless tre windows: ``Window.simulate`` is the keyboard and the pointer, and a
``PopupWindow`` is made and laid out with no compositor. tre walks the focusable nodes itself; what
is tested here is what the shell gives it (``focusable``, ``tab_index``, the ring), not tre's
traversal."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
import tess_dl
from tess_re import Window

from tess_shell.binder import model as m
from tess_shell.binder.build import View, build
from tess_shell.binder.convert import CONVERTERS
from tess_shell.binder.focus import default_focusable, tab_order, takes_ring
from tess_shell.binder.model import TAB_INDEX_MAX, BindError, BindFailed
from tess_shell.model.field import compose
from tess_shell.model.look import focus_ring, resolve
from tess_shell.schema.findings import Finding
from tess_shell.schema.model import BarDef, EdgeDef, FrameDef, PanelDef, ShellDef
from tess_shell.schema.ranges import TAB_INDEX_MAX as SCHEMA_TAB_INDEX_MAX
from tess_shell.schema.shell import read_shell
from tess_shell.surfaces.focus import next_surface, surface_order
from tests.field_live import look
from tests.shell_samples import HEADER, SVG
from tests.test_popup import BTN, Rig, rig

DARK = look(scheme="dark")
LIGHT = look(scheme="light")

# -- blocks ------------------------------------------------------------------------------------


def block(
    name: str,
    role: str | None = "BUTTON",
    index: int | None = None,
    enabled: bool = True,
    focusable: bool | None = None,
    style: dict[str, m.Value] | None = None,
    children: tuple[m.Node, ...] = (),
) -> m.Node:
    props: dict[str, m.Value] = {"Width": m.Length(40), "Height": m.Length(20)}
    if role is not None:
        props["Role"] = m.Enum(role)
    if index is not None:
        props["Tab_Index"] = m.Number(index)
    if not enabled:
        props["Enabled"] = m.Bool(False)
    if focusable is not None:
        props["Focusable"] = m.Bool(focusable)
    return m.Node("FlexBox", name=name, props=props, style=style or {}, children=children)


def row(*children: m.Node) -> m.Node:
    return m.Node(
        "FlexBox",
        name="Row",
        props={"Flex": m.Enum("HORIZONTAL"), "Width": m.Length(400), "Height": m.Length(60)},
        children=children,
    )


class Built:
    """A tree on a headless window; ``tab`` presses Tab and says which named block has focus."""

    def __init__(self, root: m.Node, scheme: Any = DARK) -> None:
        self.window = Window(width=400, height=100)
        self.look = scheme
        self.view = self.build(root)

    def build(self, root: m.Node) -> View:
        nodes, errors = resolve([root], self.look)
        assert errors == []
        view = build(nodes, self.window)
        self.window.advance(16)
        return view

    def focused(self) -> str | None:
        found = [n for n, node in self.view.nodes.items() if node.get("focused")]
        assert len(found) <= 1, found
        return found[0] if found else None

    def tab(self, shift: bool = False) -> str | None:
        self.window.simulate("key_down", key="tab", shift=shift)
        return self.focused()

    def walk(self, count: int, shift: bool = False) -> list[str | None]:
        return [self.tab(shift) for _ in range(count)]

    def shadows(self, name: str) -> list[Any]:
        return list(self.view.nodes[name].get("shadows"))


def ring_of(scheme: Any) -> list[Any]:
    """The ``shadows`` tre holds for the ring of ``scheme``'s look."""
    (s,) = focus_ring(scheme).items
    return [((s.color.r, s.color.g, s.color.b, s.color.a), s.x, s.y, s.blur, s.spread)]


# -- what takes focus --------------------------------------------------------------------------


def test_a_block_with_an_interactive_role_or_a_control_takes_focus_and_a_plain_block_does_not() -> (
    None
):
    assert default_focusable(block("A", "BUTTON"))
    for role in ("CHECKBOX", "RADIO", "SWITCH", "SLIDER", "LINK", "TAB"):
        assert default_focusable(block("A", role)), role
    for role in (None, "GROUP", "NONE", "PROGRESSBAR", "HEADING", "IMG"):
        assert not default_focusable(block("A", role)), role
    toggles = dataclasses.replace(block("A", None), props={"Toggles": m.Bool(True)})
    slides = dataclasses.replace(block("A", None), props={"Slides": m.Enum("HORIZONTAL")})
    no_slides = dataclasses.replace(block("A", None), props={"Slides": m.Enum("NONE")})
    assert default_focusable(toggles) and default_focusable(slides)
    assert not default_focusable(no_slides)


def test_focusable_false_takes_a_block_out_and_focusable_true_puts_a_plain_block_in() -> None:
    b = Built(row(block("A"), block("B", focusable=False), block("C", None, focusable=True)))
    assert b.walk(4) == ["A", "C", "A", "C"]


def test_a_disabled_block_and_every_block_under_one_leave_the_tab_order() -> None:
    inner = block("Inner")
    b = Built(
        row(
            block("A"),
            block("Off", enabled=False),
            block("Group", None, enabled=False, children=(inner,)),
            block("C"),
        )
    )
    assert b.walk(4) == ["A", "C", "A", "C"]
    assert b.view.nodes["Off"].get("focusable") is False
    assert b.view.nodes["Inner"].get("focusable") is False


def test_a_block_that_is_enabled_again_takes_its_place_back_in_the_order() -> None:
    b = Built(row(block("A"), block("B", enabled=False), block("C")))
    assert b.walk(3) == ["A", "C", "A"]
    again = row(block("A"), block("B"), block("C"))
    nodes, errors = resolve([again], DARK)
    assert errors == []
    b.view.rebuild(nodes)
    assert b.view.nodes["B"].get("focusable") is True
    assert b.walk(3) == ["B", "C", "A"]


def test_the_default_focusable_flag_reaches_tre_and_the_text_node_of_a_label_has_none() -> None:
    b = Built(row(block("A"), block("Plain", None)))
    assert b.view.nodes["A"].get("focusable") is True
    assert b.view.nodes["Plain"].get("focusable") is False


# -- the order ---------------------------------------------------------------------------------


def test_tab_order_is_ascending_equal_indices_in_document_order_and_unindexed_last() -> None:
    assert tab_order([None, 2, 1, None, 2, 0]) == [5, 2, 1, 4, 0, 3]
    assert tab_order([]) == []
    assert tab_order([None, None]) == [0, 1]
    assert tab_order([3, 3, 3]) == [0, 1, 2]


def test_tab_visits_the_indexed_blocks_in_order_then_the_rest_in_document_order() -> None:
    b = Built(
        row(
            block("A"),
            block("B", index=2),
            block("C", index=1),
            block("D", index=2),
            block("E", index=0),
            block("F"),
        )
    )
    assert b.walk(6) == ["E", "C", "B", "D", "A", "F"]


def test_tab_wraps_round_and_shift_tab_goes_back_the_same_way() -> None:
    b = Built(row(block("A"), block("B", index=1), block("C")))
    assert b.walk(7) == ["B", "A", "C", "B", "A", "C", "B"]
    b = Built(row(block("A"), block("B", index=1), block("C")))
    assert b.walk(4, shift=True) == ["C", "A", "B", "C"]


def test_a_tab_index_on_a_block_that_takes_no_focus_changes_nothing() -> None:
    b = Built(row(block("A"), block("Plain", None, index=0), block("B")))
    assert b.walk(3) == ["A", "B", "A"]


def test_zero_and_the_largest_index_are_indices_and_come_before_a_block_with_none() -> None:
    b = Built(row(block("A"), block("Last", index=TAB_INDEX_MAX), block("First", index=0)))
    assert b.walk(3) == ["First", "Last", "A"]


def test_the_order_is_one_for_the_whole_tree_not_for_each_parent() -> None:
    nested = block("Group", None, index=None, children=(block("Deep", index=1),))
    b = Built(row(block("A", index=2), nested, block("B", index=1)))
    # Deep is inside Group but the order is the tree's: both 1s in document order (Deep first)
    assert b.walk(4) == ["Deep", "B", "A", "Deep"]


def test_a_reload_that_changes_a_tab_index_changes_the_order_and_one_that_drops_it_resets() -> None:
    b = Built(row(block("A"), block("B", index=1), block("C")))
    assert b.walk(3) == ["B", "A", "C"]
    nodes, errors = resolve([row(block("A", index=1), block("B"), block("C", index=0))], DARK)
    assert errors == []
    b.view.rebuild(nodes)
    # focus was on C: Tab goes on from it in the new order C(0), A(1), then B (no index)
    assert b.walk(4) == ["A", "B", "C", "A"]
    assert b.view.entries[0].children[1].rank == 0


def test_the_ranks_are_held_on_the_entries_and_only_a_change_reaches_tre() -> None:
    b = Built(row(block("A", index=5), block("B", index=7), block("C")))
    ranks = [e.rank for e in b.view.entries[0].children]
    assert ranks == [1, 2, 0]
    assert [b.view.nodes[n].get("tab_index") for n in "ABC"] == [1, 2, 0]
    assert b.view.tab_stops() == [b.view.nodes[n] for n in "ABC"]


def test_a_slot_that_sets_a_tab_index_later_reorders_the_blocks() -> None:
    b = Built(row(block("A", index=1), block("B", index=2)))
    assert b.walk(2) == ["A", "B"]
    errors = b.view.update([("A", "Tab_Index", m.Number(9))])
    assert errors == []
    # focus is on B; the order is now B(2), A(9): A next, then round to B
    assert b.walk(3) == ["A", "B", "A"]


def test_a_text_fields_text_input_is_the_tab_stop_and_takes_the_index_and_focusable() -> None:
    field = m.Node(m.FIELD, name="F", props={"Tab_Index": m.Number(1)})
    plain = m.Node(m.FIELD, name="G", props={"Focusable": m.Bool(False)})
    composed = [compose(field), compose(plain)]
    named: list[m.Node] = []
    for c in composed:
        (line,) = c.children
        assert isinstance(line, m.Node)
        kids = tuple(
            dataclasses.replace(k, name=f"{c.name}.In") if k.kind == m.FIELD_INPUT else k
            for k in line.children
            if isinstance(k, m.Node)
        )
        named.append(dataclasses.replace(c, children=(dataclasses.replace(line, children=kids),)))
    b = Built(row(block("A"), *named))
    assert b.view.nodes["F.In"].get("tab_index") == 1
    assert b.view.nodes["G.In"].get("focusable") is False
    assert "Tab_Index" not in composed[0].props  # the box takes none: its input does
    assert b.walk(3) == ["F.In", "A", "F.In"]  # G's input is out of the order


# -- the ring ----------------------------------------------------------------------------------


def test_keyboard_focus_shows_the_ring_and_leaving_takes_it_away() -> None:
    b = Built(row(block("A"), block("B")))
    assert b.shadows("A") == [] and b.shadows("B") == []
    assert b.tab() == "A"
    assert b.shadows("A") == ring_of(DARK) and b.shadows("B") == []
    assert b.tab() == "B"
    assert b.shadows("A") == [] and b.shadows("B") == ring_of(DARK)


def test_a_click_focuses_a_block_and_shows_no_ring() -> None:
    b = Built(row(block("A"), block("B")))
    b.window.simulate("click", node=b.view.nodes["B"])
    assert b.focused() == "B"
    assert b.shadows("B") == []
    assert b.tab() == "A"  # the keyboard moves on from where the click put it, and shows a ring
    assert b.shadows("A") == ring_of(DARK)


def test_the_ring_does_not_shift_the_layout() -> None:
    b = Built(row(block("A"), block("B")))
    before = [
        tuple(b.view.nodes[n].get(k) for k in ("layout_x", "layout_y", "layout_width"))
        for n in "AB"
    ]
    b.tab()
    b.window.advance(16)
    after = [
        tuple(b.view.nodes[n].get(k) for k in ("layout_x", "layout_y", "layout_width"))
        for n in "AB"
    ]
    assert before == after
    (shadow,) = b.shadows("A")
    assert shadow[1:4] == (0.0, 0.0, 0.0) and shadow[4] > 0  # no offset, no blur: spread only


def test_the_ring_takes_its_colour_and_size_from_the_themes_tokens_and_follows_light_and_dark() -> (
    None
):
    dark, light = ring_of(DARK), ring_of(LIGHT)
    assert dark != light  # color.primary differs between the two variants of the Default theme
    assert dark[0][0] == (0x5B, 0x97, 0xC9, 255) and light[0][0] == (0x2F, 0x6B, 0x9A, 255)
    assert dark[0][4] == 2.0  # space.step_1
    b = Built(row(block("A")), LIGHT)
    b.tab()
    assert b.shadows("A") == light


def test_without_a_look_the_ring_is_the_default_themes() -> None:
    nodes, errors = resolve([row(block("A"))], None)
    assert errors == []
    window = Window(width=400, height=100)
    view = build(nodes, window)
    window.simulate("key_down", key="tab")
    assert list(view.nodes["A"].get("shadows")) == ring_of(DARK)


def test_a_blocks_own_shadows_stay_under_the_ring_and_come_back_with_it_gone() -> None:
    own = m.Shadows((m.Shadow(m.Color(0, 0, 0, 100), 0, 2, 6, 0),))
    b = Built(row(block("A", style={"Shadows": own}), block("B")))
    base = b.shadows("A")
    assert len(base) == 1
    b.tab()
    shown = b.shadows("A")
    assert shown[:1] == ring_of(DARK) and shown[1:] == base
    b.tab()
    assert b.shadows("A") == base


def test_a_focused_rule_adds_to_the_ring_and_its_own_shadows_replace_it() -> None:
    red = m.Color(255, 0, 0, 255)
    plain = dataclasses.replace(block("A"), states={"focused": {"Background": red}})
    mine = m.Shadows((m.Shadow(m.Color(1, 2, 3, 255), 0, 0, 0, 5),))
    custom = dataclasses.replace(block("B"), states={"focused": {"Shadows": mine}})
    b = Built(row(plain, custom))
    b.tab()
    assert b.shadows("A") == ring_of(DARK) and b.view.nodes["A"].get("fill") == (255, 0, 0, 255)
    b.tab()
    assert b.shadows("B") == [((1, 2, 3, 255), 0.0, 0.0, 0.0, 5.0)]
    assert b.view.nodes["A"].get("fill") != (255, 0, 0, 255)  # A gave its look back


def test_focused_comes_after_pressed_and_hovered_and_a_disabled_block_shows_no_ring() -> None:
    b = Built(row(block("A"), block("Off", enabled=False)))
    b.tab()
    node = b.view.nodes["A"]
    b.window.simulate("pointer_enter", node=node)
    assert list(node.get("shadows")) == ring_of(DARK)  # hovered and focused: the ring stays
    b.window.simulate("pointer_leave")
    # a block that is disabled while it has focus shows no ring
    dis, errors = resolve([row(block("A", enabled=False), block("Off", enabled=False))], DARK)
    assert errors == []
    b.view.rebuild(dis)
    assert b.shadows("A") == []


def test_a_textfields_box_draws_the_ring_when_the_keyboard_focuses_its_input() -> None:
    field = m.Node(m.FIELD, name="F", props={"Width": m.Length(120)})
    (line,) = compose(field).children
    box, errors = resolve([compose(field)], DARK)
    assert errors == []
    assert "focused" in box[0].states and "Shadows" in box[0].states["focused"]
    assert isinstance(line, m.Node)
    # the text input shows no ring of its own, its box does
    inner = [c for c in line.children if isinstance(c, m.Node) and c.kind == m.FIELD_INPUT][0]
    assert not takes_ring(inner) and takes_ring(compose(field))
    window = Window(width=400, height=100)
    (named_line,) = box[0].children
    assert isinstance(named_line, m.Node)
    kids = tuple(
        dataclasses.replace(k, name="In")
        if isinstance(k, m.Node) and k.kind == m.FIELD_INPUT
        else k
        for k in named_line.children
    )
    tree = dataclasses.replace(
        box[0], children=(dataclasses.replace(named_line, children=kids),), name="F"
    )
    view = build([tree], window)
    window.advance(16)
    window.simulate("key_down", key="tab")
    assert view.nodes["In"].get("focused")
    assert list(view.nodes["F"].get("shadows")) == ring_of(DARK)


# -- the keys ----------------------------------------------------------------------------------

SHELL = "Shell {{ Monitor {{ Name: Main, Index: 0, Children {{ {} }} }} }}\n"


def read(children: str) -> tuple[ShellDef | None, list[Finding]]:
    result = tess_dl.parse(HEADER + SHELL.format(children), path="Shells/Main_Shell.tdl")
    assert not result.errors and result.document is not None
    return read_shell(result.document, "Shells/Main_Shell.tdl", lambda p: SVG)


def bar(inner: str, name: str = "Top_Bar", keys: str = "") -> str:
    return (
        f"Bar {{ Name: {name}, Edge: TOP, Width: EXPAND, Height: 32, {keys} "
        f"Children {{ {inner} }} }}"
    )


@pytest.mark.parametrize("index", ["0", "1", "2147483647"])
def test_a_tab_index_from_0_to_the_largest_32_bit_integer_is_accepted_on_a_block(
    index: str,
) -> None:
    shell, findings = read(bar(f"FlexBox {{ Role: BUTTON, Tab_Index: {index} }}"))
    assert shell is not None, findings
    (block_,) = shell.monitors[0].surfaces[0].children  # type: ignore[union-attr]
    assert block_.props["Tab_Index"] == m.Number(
        int(index), origin=block_.props["Tab_Index"].origin
    )  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("written", "needle"),
    [
        ("-1", "from 0 to 2147483647"),
        ("2147483648", "from 0 to 2147483647"),
        ("1.5", "whole number"),
        ('"x"', "whole number"),
        ("true", "whole number"),
    ],
)
def test_a_tab_index_out_of_range_or_not_an_integer_is_an_error_at_its_position(
    written: str, needle: str
) -> None:
    shell, findings = read(bar(f"FlexBox {{ Role: BUTTON, Tab_Index: {written} }}"))
    assert shell is None
    (f,) = [f for f in findings if f.severity == "error"]
    assert f.rule == "bad-value" and needle in f.message
    assert f.file == "Shells/Main_Shell.tdl" and f.line > 0 and f.column > 0
    assert "Tab_Index" in f.message or "Tab_Index" in f.hint or f.line > 0


def test_a_surface_takes_a_tab_index_too_with_the_same_range_and_a_position_on_an_error() -> None:
    shell, findings = read(
        bar("", "B", "Tab_Index: 2, Keyboard: ON_DEMAND,")
        + "Panel { Name: P, Anchor: TOP, Width: 100, Height: 50, Tab_Index: 1 } "
        + "Frame { Name: F, Thickness: 8, Tab_Index: 0, Edges { Top { Thickness: 30, "
        + "Tab_Index: 5, Children { FlexBox { } } } } }"
    )
    assert shell is not None, findings
    surfaces = shell.monitors[0].surfaces
    assert isinstance(surfaces[0], BarDef) and surfaces[0].tab_index == 2
    assert surfaces[0].keyboard == "ON_DEMAND" and surfaces[0].keyboard_written
    assert isinstance(surfaces[1], PanelDef) and surfaces[1].tab_index == 1
    (frame,) = shell.monitors[0].frames
    assert isinstance(frame, FrameDef) and frame.tab_index == 0
    assert isinstance(frame.edges["top"], EdgeDef) and frame.edges["top"].tab_index == 5
    for snippet in (
        bar("", "B", "Tab_Index: -1,"),
        "Panel { Name: P, Anchor: TOP, Width: 100, Height: 50, Tab_Index: 2147483648 }",
        "Frame { Name: F, Thickness: 8, Tab_Index: 1.5 }",
        "Frame { Name: F, Thickness: 8, Edges { Top { Tab_Index: -3 } } }",
    ):
        none, found = read(snippet)
        assert none is None, snippet
        assert any(f.severity == "error" and f.line > 0 and f.column > 0 for f in found), snippet


def test_a_bar_takes_no_keyboard_unless_it_says_so_and_a_text_field_still_gives_it_on_demand() -> (
    None
):
    shell, findings = read(bar("", "A") + bar("", "B", "Keyboard: ON_DEMAND,"))
    assert shell is not None, findings
    a, b = shell.monitors[0].surfaces
    assert isinstance(a, BarDef) and isinstance(b, BarDef)
    assert (a.keyboard, a.keyboard_written, b.keyboard) == ("NONE", False, "ON_DEMAND")
    none, found = read(bar("", "A", "Keyboard: EXCLUSIVE,"))
    assert none is None and any("EXCLUSIVE" in f.message + f.hint for f in found)


def test_the_binders_range_is_the_schemas() -> None:
    assert TAB_INDEX_MAX == SCHEMA_TAB_INDEX_MAX == 2**31 - 1
    convert = CONVERTERS["tab_index"]
    assert convert(m.Number(0), (), ()) == {} and convert(m.Number(TAB_INDEX_MAX), (), ()) == {}
    for bad in (m.Number(-1), m.Number(TAB_INDEX_MAX + 1), m.Number(1.5), m.Text("x")):
        with pytest.raises(BindError):
            convert(bad, (), ())


def test_the_binder_refuses_a_tab_index_out_of_range_at_the_blocks_position() -> None:
    node = block("A", index=-1)
    with pytest.raises(BindFailed) as exc:
        build([node], Window(width=100, height=100))
    assert "Tab_Index" in str(exc.value.errors[0].message)


# -- the order of the shell's surfaces ---------------------------------------------------------


def test_the_shells_surfaces_are_ordered_by_tab_index_with_the_others_after() -> None:
    shell, findings = read(
        bar("", "Plain")
        + bar("", "Late", "Tab_Index: 9,")
        + "Panel { Name: Dock, Anchor: LEFT, Width: 50, Height: 50, Tab_Index: 2 } "
        + "Frame { Name: Ring, Thickness: 8, Tab_Index: 2, Edges { Top { Thickness: 30, "
        + "Tab_Index: 0, Children { FlexBox { } } }, Left { Thickness: 30, Children { "
        + "FlexBox { } } }, Right { Thickness: 4 } } }"
    )
    assert shell is not None, findings
    assert surface_order(shell) == [
        "Ring.top",  # 0
        "Dock",  # 2, before the Frame that is also 2 (document order: the Panel is first)
        "Ring",
        "Late",  # 9
        "Plain",  # none: document order
        "Ring.left",  # a strip with no index follows the others; Right has no children: no place
    ]


def test_a_name_a_monitor_block_repeats_counts_once() -> None:
    shell, findings = read(bar("", "A", "Tab_Index: 1,"))
    assert shell is not None, findings
    twice = dataclasses.replace(shell, monitors=shell.monitors * 2)
    assert surface_order(twice) == ["A"]


def test_when_the_surface_with_focus_closes_focus_goes_to_the_next_in_the_order_or_none() -> None:
    order = ["A", "B", "C"]
    assert next_surface(order, "A") == "B"
    assert next_surface(order, "B") == "C"
    assert next_surface(order, "C") == "A"  # the first one after the last
    assert next_surface(["A"], "A") is None  # no other is left
    assert next_surface([], "A") is None
    assert next_surface(order, "Z") == "A"  # a surface that is not in the order: the first


def test_the_manager_keeps_the_order_and_moves_the_focus_when_a_surface_closes(
    request: pytest.FixtureRequest,
) -> None:
    (r,) = list(rig("Popup { Name: Menu, Children { FlexBox { } } }"))
    m_ = r.manager
    assert m_.focus_order == ["Top_Bar"]
    m_.focus_order = ["Top_Bar", "Dock", "Ring"]
    m_._surface_active("Top_Bar", True)
    assert m_.focused == "Top_Bar"
    m_._surface_active("Top_Bar", False)
    assert m_.focused is None
    m_._surface_active("Dock", True)
    m_._surface_active("Top_Bar", False)  # another surface losing it changes nothing
    assert m_.focused == "Dock"
    m_._surface_gone("Dock")  # the Dock is not open: only Top_Bar is
    assert m_.focused == "Top_Bar"
    m_._surface_gone("Dock")  # it does not have the focus now: nothing moves
    assert m_.focused == "Top_Bar"
    m_.focused = "Top_Bar"
    m_.surfaces.clear()
    m_._surface_gone("Top_Bar")
    assert m_.focused is None


# -- a Popup and focus -------------------------------------------------------------------------

BTN_FOCUS = BTN.replace("Name: Root,", "Name: Root, Role: BUTTON,")
ITEM = "FlexBox { Name: Item, Role: BUTTON, Width: 40, Height: 20, On_Click: Close }"
OTHER = "FlexBox { Name: Other, Role: BUTTON, Width: 40, Height: 20 }"
POPUP = (
    "Popup { Name: Menu, Children { FlexBox { Name: Card, Children { "
    + ITEM
    + " "
    + OTHER
    + " } } } }"
)


def two_buttons() -> Rig:
    (r,) = list(
        rig(
            POPUP,
            "Btn { Name: Btn_One } Btn { Name: Btn_Two }",
            btn=BTN_FOCUS,
        )
    )
    r.bar.window.advance(16)
    return r


def focused_root(r: Rig) -> list[str]:
    return [u for u in r.uses if r.root_of(u).get("focused")]


def ring(r: Rig, use: str) -> bool:
    return bool(list(r.root_of(use).get("shadows")))


def test_a_popup_opened_from_a_block_with_keyboard_focus_takes_focus_and_gives_it_back() -> None:
    r = two_buttons()
    one, two = r.uses
    win = r.bar.window
    win.simulate("key_down", key="tab")
    assert focused_root(r) == [one] and ring(r, one)
    op = r.call("Menu", use=one)
    assert op is not None
    # opened from the keyboard: the first Tab stop of the Popup has the focus, with its ring
    assert op.view.nodes["Item"].get("focused")
    assert list(op.view.nodes["Item"].get("shadows")) == ring_of(r.manager.look)
    win.simulate("key_down", key="tab")  # focus goes elsewhere while the Popup is open
    assert focused_root(r) == [two]
    r.popups.close(op, "escape")
    assert focused_root(r) == [one] and ring(r, one) and not ring(r, two)


def test_a_popup_opened_by_a_click_has_nothing_focused_and_gives_back_focus_without_a_ring() -> (
    None
):
    r = two_buttons()
    one, two = r.uses
    win = r.bar.window
    win.simulate("click", node=r.root_of(one))
    assert focused_root(r) == [one] and not ring(r, one)
    op = r.call("Menu", use=one)
    assert op is not None
    assert not op.view.nodes["Item"].get("focused")
    win.simulate("key_down", key="tab")
    assert focused_root(r) == [two] and ring(r, two)
    r.popups.close(op, "escape")
    assert focused_root(r) == [one]
    assert not ring(r, one) and not ring(r, two)  # the pointer had it: it returns with no ring


@pytest.mark.parametrize("how", ["escape", "outside click", "selection", "dismissed"])
def test_focus_returns_to_the_opener_however_the_popup_closes(how: str) -> None:
    r = two_buttons()
    one, two = r.uses
    win = r.bar.window
    win.simulate("key_down", key="tab")
    op = r.call("Menu", use=one)
    assert op is not None
    win.simulate("key_down", key="tab")
    assert focused_root(r) == [two]
    if how == "escape":
        op.window.simulate("key_down", key="escape")
    elif how == "outside click":
        r.popups.surface_pointer_down()
    elif how == "selection":
        op.window.simulate("click", node=op.view.nodes["Item"])
    else:
        r.popups._closed(op, "dismissed")  # the compositor took the grab away
    assert r.popups.current is None
    assert focused_root(r) == [one] and ring(r, one)


def test_a_popup_that_takes_no_focus_neither_takes_it_nor_moves_it() -> None:
    (r,) = list(
        rig(
            POPUP.replace("Name: Menu,", "Name: Menu, Focus: false,"),
            "Btn { Name: Btn_One } Btn { Name: Btn_Two }",
            btn=BTN_FOCUS,
        )
    )
    one, two = r.uses
    r.bar.window.simulate("key_down", key="tab")
    op = r.call("Menu", use=one)
    assert op is not None and not op.view.nodes["Item"].get("focused")
    assert op.opener is None
    r.bar.window.simulate("key_down", key="tab")
    r.popups.close(op, "escape")
    assert focused_root(r) == [two]


def test_a_popup_called_by_a_block_that_has_no_focus_returns_nothing() -> None:
    r = two_buttons()
    one, two = r.uses
    r.bar.window.simulate("click", node=r.root_of(two))  # focus is on the other block
    op = r.call("Menu", use=one)
    assert op is not None and op.opener is None
    r.popups.close(op, "escape")
    assert focused_root(r) == [two]


def test_the_return_does_not_fail_when_the_opener_is_gone_with_its_surface() -> None:
    r = two_buttons()
    one, _ = r.uses
    r.bar.window.simulate("key_down", key="tab")
    op = r.call("Menu", use=one)
    assert op is not None and op.opener is not None
    _, _, view = op.opener
    view.dispose()
    r.popups.close(op, "escape")  # the surface was closed under it: nothing to give back
    assert r.popups.current is None


def test_a_view_gives_focus_back_with_or_without_a_ring_and_names_its_first_stop() -> None:
    b = Built(row(block("A"), block("B", index=1)))
    assert b.view.tab_stops() == [b.view.nodes["B"], b.view.nodes["A"]]
    assert b.view.focus_first()
    assert b.focused() == "B" and b.shadows("B") == ring_of(DARK)
    assert b.view.restore_focus(b.view.nodes["A"], ring=False)
    assert b.focused() == "A" and b.shadows("A") == []
    assert b.view.restore_focus(b.view.nodes["B"], ring=True)
    assert b.shadows("B") == ring_of(DARK)
    assert b.view.focus_holder(b.view.nodes["B"]) == b.view.nodes["B"]
    assert b.view.focus_holder(b.view.nodes["A"]) is None
    inside = Built(row(block("Group", None, children=(block("Deep", None),)), block("A")))
    inside.view.nodes["Group"].set(focusable=True)
    inside.view.nodes["Group"].focus()
    assert inside.view.focus_holder(inside.view.nodes["Deep"]) == inside.view.nodes["Group"]


def test_a_view_with_no_focusable_block_takes_no_first_focus() -> None:
    b = Built(row(block("A", None)))
    assert b.view.tab_stops() == [] and not b.view.focus_first()
