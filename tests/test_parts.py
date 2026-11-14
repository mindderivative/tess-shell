"""``Part:`` and ``Module::part`` selectors (Style Schema > Stylesheet Selectors, Standard Modules >
Rules That Hold for Every Module): a module's layout names blocks as parts, a stylesheet addresses
them as ``Slider::track`` and ``Slider::handle:hovered``."""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest
import tess_dl
from tess_re import Window

from tess_shell.binder import model as m
from tess_shell.binder.build import build
from tess_shell.model.expand import expand
from tess_shell.model.look import apply_rules, check_parts, make_look
from tess_shell.schema.look import read_stylesheet
from tess_shell.schema.model import ModuleDef, Rule
from tess_shell.schema.shell import read_module
from tests.shell_samples import HEADER

SLIDER = """---
TDL: 0.1
Name: Slider
---
Module {
    FlexBox {
        Name: Root
        Children {
            Rectangle { Name: Track, Part: track, Width: 100, Height: 4 }
            Rectangle { Name: Handle, Part: handle, Width: 10, Height: 10 }
            Rectangle { Name: Plain, Width: 5, Height: 5 }
        }
    }
}
"""

SHEET = """
Stylesheet {
    Rule { Selector: "Slider::track", Border_Width: 1 }
    Rule { Selector: "Slider::handle", Border_Width: 2 }
    Rule { Selector: "Slider::handle:hovered", Fill: "#aa0000" }
    Rule { Selector: "Slider::handle:disabled", Fill: "#888888" }
    Rule { Selector: "Rectangle", Corner_Radius: 3, Border_Width: 9 }
}
"""


def module(text: str = SLIDER) -> ModuleDef:
    result = tess_dl.parse(text, path="Modules/Slider_Module.tdl")
    assert result.document is not None
    found, findings = read_module(result.document, "Modules/Slider_Module.tdl")
    assert found is not None, findings
    return found


def sheet(text: str = SHEET, modules: set[str] | None = None) -> tuple[Any, list[Any]]:
    result = tess_dl.parse(HEADER + text, path="S_Stylesheet.tdl")
    assert result.document is not None
    return read_stylesheet(
        result.document, "S_Stylesheet.tdl", {"Slider"} if modules is None else modules
    )


def rules(text: str = SHEET) -> tuple[Rule, ...]:
    s, findings = sheet(text)
    assert s is not None and findings == [], findings
    return s.rules


def by_name(nodes: Any) -> dict[str, m.Node]:
    out: dict[str, m.Node] = {}

    def walk(n: Any) -> None:
        if isinstance(n, m.Node):
            if n.name:
                out[n.name.rsplit("/", 1)[-1]] = n
            for c in n.children:
                walk(c)

    for n in nodes:
        walk(n)
    return out


# -- the layout -------------------------------------------------------------------------------


def test_a_layout_declares_parts_and_the_module_lists_them_in_order() -> None:
    defn = module()
    assert defn.parts == ("track", "handle")
    (root,) = defn.children
    assert [c.part for c in root.children] == ["track", "handle", None]  # type: ignore[union-attr]


@pytest.mark.parametrize(
    ("body", "rule", "needle"),
    [
        (
            "Module { FlexBox { Part: a, Children { Spacer { Part: a } } } }",
            "part-duplicate",
            "declared twice",
        ),
        ("Module { FlexBox { Part: 5x } }", "bad-name", "Part must be"),
        ("Module { FlexBox { Part: [a, b] } }", "bad-name", "Part must be"),
    ],
)
def test_a_bad_part_is_an_error_at_its_key(body: str, rule: str, needle: str) -> None:
    result = tess_dl.parse("---\nTDL: 0.1\nName: Slider\n---\n" + body, path="M.tdl")
    assert result.document is not None
    found, findings = read_module(result.document, "M.tdl")
    assert found is None
    assert any(f.rule == rule and needle in f.message for f in findings), findings
    assert all(f.line > 0 for f in findings)


def test_a_part_outside_a_module_is_an_error_that_says_where_it_belongs() -> None:
    from tess_shell.schema.shell import read_shell

    body = (
        "Shell { Monitor { Name: Main, Index: 0, Children { Bar { Name: B, Edge: TOP, "
        "Width: EXPAND, Height: 20, Children { FlexBox { Part: track } } } } } }\n"
    )
    result = tess_dl.parse(HEADER + body, path="Shells/Main_Shell.tdl")
    assert result.document is not None
    shell, findings = read_shell(result.document, "Shells/Main_Shell.tdl", lambda p: "")
    assert shell is None
    (f,) = [x for x in findings if x.severity == "error"]
    assert f.rule == "part-outside-module" and "Module::part" in f.hint


# -- the selectors ----------------------------------------------------------------------------


def test_a_part_selector_reads_the_module_the_part_and_the_state() -> None:
    rs = rules()
    got = [(r.kind, r.target, r.part, r.state) for r in rs]
    assert got == [
        ("module", "Slider", "track", ""),
        ("module", "Slider", "handle", ""),
        ("module", "Slider", "handle", "hovered"),
        ("module", "Slider", "handle", "disabled"),
        ("type", "Rectangle", "", ""),
    ]


@pytest.mark.parametrize(
    ("selector", "rule", "needle"),
    [
        ("Rectangle::track", "bad-selector", "no module"),
        ("Slidr::track", "bad-selector", "Slider"),
    ],
)
def test_a_part_of_something_that_is_not_a_module_is_an_error(
    selector: str, rule: str, needle: str
) -> None:
    s, findings = sheet(f'Stylesheet {{ Rule {{ Selector: "{selector}", Border_Width: 1 }} }}')
    assert s is None
    assert any(f.rule == rule and needle in f.message + f.hint for f in findings), findings


@pytest.mark.parametrize("selector", [".card::track", "#vol::track"])
def test_a_part_after_a_class_or_a_name_is_skipped_with_a_warning(selector: str) -> None:
    s, findings = sheet(f'Stylesheet {{ Rule {{ Selector: "{selector}", Border_Width: 1 }} }}')
    assert s is not None and s.rules == ()
    (f,) = findings
    assert f.severity == "warning" and f.rule == "not-built" and "module's name" in f.message


def test_a_part_selector_takes_the_focused_state() -> None:
    s, findings = sheet(
        'Stylesheet { Rule { Selector: "Slider::track:focused", Border_Width: 1 } }'
    )
    assert s is not None and findings == []
    assert [(r.part, r.state) for r in s.rules] == [("track", "focused")]


# -- folding into a layout ---------------------------------------------------------------------


def folded(rs: tuple[Rule, ...]) -> ModuleDef:
    defn = module()
    return dataclasses.replace(defn, children=apply_rules(defn.children, rs, "Slider"))


def test_a_part_rule_reaches_its_part_and_no_other_block() -> None:
    nodes = by_name(folded(rules()).children)
    assert nodes["Track"].style["Border_Width"] == m.Number(1)
    assert nodes["Handle"].style["Border_Width"] == m.Number(2)
    # an inner block that is no part is styled by its type alone
    assert nodes["Plain"].style["Border_Width"] == m.Number(9)
    assert nodes["Root"].style == {}


def test_a_state_adds_to_the_base_rule_of_the_part() -> None:
    handle = by_name(folded(rules()).children)["Handle"]
    assert handle.style["Border_Width"] == m.Number(2)  # the base rule is there
    assert handle.states["hovered"] == {"Fill": m.Color(170, 0, 0, 255)}
    assert handle.states["disabled"] == {"Fill": m.Color(136, 136, 136, 255)}
    assert "hovered" not in by_name(folded(rules()).children)["Track"].states


def test_a_part_rule_beats_a_type_and_a_class_rule_on_the_block_and_a_name_rule_beats_it() -> None:
    rs = rules(
        'Stylesheet { Rule { Selector: "Rectangle", Border_Width: 9, Corner_Radius: 3 }\n'
        'Rule { Selector: ".knob", Border_Width: 5, Corner_Radius: 4 }\n'
        'Rule { Selector: "Slider::handle", Border_Width: 2 }\n'
        'Rule { Selector: "#Handle", Corner_Radius: 7 } }'
    )
    handle = m.Node("Rectangle", name="Handle", part="handle", classes=("knob",))
    (out,) = apply_rules((handle,), rs, "Slider")
    assert isinstance(out, m.Node)
    assert out.style["Border_Width"] == m.Number(2)  # the part rule, over the class and the type
    assert out.style["Corner_Radius"] == m.Length(7)  # #Handle, over the class
    # the same block of another module takes no Slider rule
    (other,) = apply_rules((handle,), rs, "Other")
    assert isinstance(other, m.Node) and other.style["Border_Width"] == m.Number(5)


def test_the_blocks_own_style_wins_over_a_part_rule() -> None:
    rs = rules(
        'Stylesheet { Rule { Selector: "Slider::track", Border_Width: 1, Corner_Radius: 3 } }'
    )
    track = m.Node("Rectangle", part="track", style={"Border_Width": m.Number(6)})
    (out,) = apply_rules((track,), rs, "Slider")
    assert isinstance(out, m.Node)
    assert out.style["Border_Width"] == m.Number(6)  # its own key stays
    assert out.style["Corner_Radius"] == m.Length(3)  # the rule's other key is below it


def test_a_part_rule_does_not_reach_a_block_of_the_shell_file_or_a_module_root() -> None:
    rs = rules()
    (out,) = apply_rules((m.Node("Rectangle", part="track"),), rs)  # no module: no part rules
    assert isinstance(out, m.Node) and "Border_Width" in out.style  # only the Rectangle rule
    assert out.style["Border_Width"] == m.Number(9)


# -- expansion: every use of the module ---------------------------------------------------------


def test_every_use_of_the_module_gets_the_part_styles_on_its_own_nodes() -> None:
    defs = {"Slider": folded(rules())}
    uses = (m.UseNode("Slider", name="A"), m.UseNode("Slider", name="B"))
    out = expand(uses, "S.M.Bar", defs, lambda k: k, "Main", rules())
    assert len(out.uses) == 2
    tracks = [n for n in _walk(out.nodes) if n.part == "track"]
    assert len(tracks) == 2 and len({t.name for t in tracks}) == 2
    assert all(t.style["Border_Width"] == m.Number(1) for t in tracks)


def _walk(nodes: Any) -> list[m.Node]:
    found: list[m.Node] = []
    for n in nodes:
        if isinstance(n, m.Node):
            found.append(n)
            found.extend(_walk(n.children))
    return found


# -- the check ---------------------------------------------------------------------------------


def test_a_rule_that_names_a_part_the_module_lacks_is_an_error_with_the_nearest_parts() -> None:
    rs = rules('Stylesheet { Rule { Selector: "Slider::handel", Border_Width: 1 } }')
    (f,) = check_parts({"Slider": module()}, rs)
    assert f.severity == "error" and f.rule == "unknown-part"
    assert "Slider has no part handel" in f.message and "handle" in f.hint
    assert check_parts({"Slider": module()}, rules()) == []


# -- the binder: states of a part ---------------------------------------------------------------

BASE = m.Color(1, 2, 3, 255)
HOVER = m.Color(40, 50, 60, 255)
OFF = m.Color(9, 9, 9, 255)
SIZE = {"Width": m.Length(30), "Height": m.Length(30)}


def widget(enabled: bool = True) -> m.Node:
    """A module's layout: a root that can be disabled and a ``handle`` part with its states."""
    handle = m.Node(
        "FlexBox",
        name="Handle",
        part="handle",
        props=SIZE,
        style={"Background": BASE},
        states={"hovered": {"Background": HOVER}, "disabled": {"Background": OFF}},
    )
    return m.Node(
        "FlexBox",
        name="Root",
        props={**SIZE, "Enabled": m.Bool(enabled)},
        children=(handle,),
    )


def test_a_part_shows_its_hover_and_its_module_s_disabled_state() -> None:
    window = Window(width=100, height=100)
    view = build([widget()], window)
    handle = view.nodes["Handle"]
    window.simulate("pointer_enter", node=handle)
    assert handle.get("fill") == (40, 50, 60, 255)  # Slider::handle:hovered
    window.simulate("pointer_leave")
    assert view.update([("Root", "Enabled", m.Bool(False))]) == []
    assert handle.get("fill") == (9, 9, 9, 255)  # the root is disabled: the part looks it
    window.simulate("pointer_enter", node=handle)
    assert handle.get("fill") == (9, 9, 9, 255)  # and takes no hover
    view.update([("Root", "Enabled", m.Bool(True))])
    assert handle.get("fill") == (1, 2, 3, 255)


def test_a_block_that_is_not_a_part_does_not_take_its_parents_disabled_look() -> None:
    plain = m.Node(
        "FlexBox",
        name="Plain",
        props=SIZE,
        style={"Background": BASE},
        states={"disabled": {"Background": OFF}},
    )
    window = Window(width=100, height=100)
    view = build(
        [m.Node("FlexBox", name="Root", props={"Enabled": m.Bool(False)}, children=(plain,))],
        window,
    )
    assert view.nodes["Plain"].get("fill") == (1, 2, 3, 255)  # blocked, but not styled as disabled


def test_make_look_keeps_part_rules_with_the_look() -> None:
    from tess_shell.appearance import Appearance

    theme = _theme()
    look = make_look(theme, [dataclasses.replace(_sheet(), rules=rules())], Appearance())
    assert [r.part for r in look.rules if r.part] == ["track", "handle", "handle", "handle"]


def _sheet() -> Any:
    s, _ = sheet()
    return s


def _theme() -> Any:
    from tess_shell.schema.look import read_theme
    from tests.test_look import THEME

    doc = tess_dl.parse(THEME, path="T_Theme.tdl").document
    assert doc is not None
    theme, _ = read_theme(doc, "T_Theme.tdl")
    return theme
