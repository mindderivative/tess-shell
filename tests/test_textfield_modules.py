"""The shipped TextInput and TextEditor modules (Standard Modules > TextInput, TextEditor), through
the whole shell: found with no user config, their params reach tre, a call raises its text events
into a module's ``@action``, a stylesheet restyles them (``::placeholder`` too), the look follows
light and dark, and a surface that holds one takes the keyboard. ``simulate`` is the keyboard."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tess_shell.appearance import Appearance
from tess_shell.binder.model import NO_ORIGIN
from tess_shell.config.settings import load_settings
from tess_shell.scanner import scan
from tess_shell.schema.model import PanelDef
from tess_shell.surfaces.manager import _keyboard
from tests.field_live import DARK_THEME, Fields, look, running
from tests.shell_samples import write_example

CALLS = (
    'On_Changed { Action: Call, Target: "Host.changed" }, '
    'On_Submit { Action: Call, Target: "Host.submit" }, '
    'On_Text_Commit { Action: Call, Target: "Host.commit" }'
)


def click(r: Fields, inp: Any) -> None:
    r.window.simulate("pointer_down", node=inp)
    r.window.simulate("pointer_up", node=inp)


def bad(r: Fields) -> list[str]:
    return [x for x in r.lines if "| ERROR " in x or "| WARNING " in x]


# -- found with no config ----------------------------------------------------------------------


def test_the_shipped_modules_need_no_user_file(tmp_path: Path) -> None:
    body = (
        'TextInput { Name: One, Text: "a", Placeholder: "p", Read_Only: false, Max_Length: 8, '
        "Password: true, Enabled: true, Width: 180 }\n"
        'TextEditor { Name: Two, Text: "b", Wrap: NONE, Lines: 3, Max_Length: 40 }'
    )
    write_example(tmp_path, _bar(body))
    settings, _ = load_settings(tmp_path)
    assert settings is not None
    result = scan(settings, tmp_path)
    assert not result.errors and not [f for f in result.findings if f.severity == "warning"], (
        result.findings
    )
    assert result.modules["TextInput"].shipped and result.modules["TextEditor"].shipped
    for name in ("TextInput", "TextEditor"):
        assert "placeholder" in result.modules[name].definition.parts


def _bar(children: str) -> str:
    from tests.test_clock import BODY

    return BODY.replace('Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }', children)


def test_a_text_editor_call_may_not_name_a_param_the_module_has_not() -> None:
    with pytest.raises(AssertionError):  # the shell file does not read
        with running("TextInput { Name: One, Wrapp: NONE }"):
            pass


# -- the params reach the text input -----------------------------------------------------------


def test_the_params_of_a_text_input_reach_tre() -> None:
    with running(
        'TextInput { Text: "héllo", Placeholder: "Search", Max_Length: 12, Password: true, '
        "Read_Only: true, Width: 180 }"
    ) as r:
        assert r.problems == [] and bad(r) == []
        (f,) = r.fields()
        inp = f.inp
        assert inp.get("text") == "héllo" and inp.get("placeholder") == "Search"
        assert inp.get("max_length") == 12 and inp.get("obscured") is True
        assert inp.get("read_only") is True and inp.get("overflow") == "scroll"
        assert inp.get("multiline") is False and f.box.get("layout_width") == 180


def test_a_text_input_has_the_defaults_of_its_module() -> None:
    with running("TextInput { }") as r:
        (f,) = r.fields()
        inp = f.inp
        assert inp.get("text") == "" and inp.get("max_length") is None
        assert inp.get("read_only") is False and inp.get("obscured") is False
        assert f.box.get("layout_width") == 240 and f.box.get("disabled") is False


def test_a_text_editor_wraps_by_word_by_default_and_by_param() -> None:
    long = " ".join(["word"] * 60)
    with running(
        f'TextEditor {{ Name: A, Text: "{long}" }}\n'
        f'TextEditor {{ Name: B, Text: "{long}", Wrap: NONE, Lines: 6 }}'
    ) as r:
        assert r.problems == [] and bad(r) == []
        a, b = r.fields()
        assert a.inp.get("multiline") is True and a.inp.get("wrap") == "word"
        assert b.inp.get("wrap") == "none"
        assert len(a.inp.text_rects(0, len(long))) > 1 and len(b.inp.text_rects(0, len(long))) == 1
        line = r.window.measure_text("x", font_size=14, max_lines=1)[1]
        # the Bar is 32 high and clips the box; the size text is the lines (Lines: 4 and 6)
        assert a.size.get("layout_height") == pytest.approx(4 * line, abs=2)
        assert b.size.get("layout_height") == pytest.approx(6 * line, abs=2)
        assert a.box.get("layout_width") == 320


def test_a_text_editor_takes_enter_as_a_new_line_and_has_no_submit() -> None:
    with running(f"TextEditor {{ Text: x, {CALLS} }}") as r:
        # On_Submit is a warning on a multi-line field and is left out: the call is not an error
        (f,) = r.fields()
        click(r, f.inp)
        r.window.simulate("key_down", key="enter")
        r.window.simulate("input", text="y")
        assert f.inp.get("text") == "x\ny"
        assert [e[0] for e in r.seen] == ["changed", "commit", "changed"]
        assert [e[3] for e in r.seen if e[0] == "changed"] == ["x\n", "x\ny"]


def test_a_bad_param_is_a_finding_that_names_it() -> None:
    with running(
        "TextEditor { Name: A, Wrap: CHAR }\nTextEditor { Name: B, Lines: 0 }\n"
        "TextInput { Name: C, Max_Length: -3 }\nTextEditor { Name: D, Wrap: SIDEWAYS }"
    ) as r:
        said = " ".join(f.message for f in r.problems)
        assert "CHAR is not built" in said and "Lines is a whole number" in said
        assert "Max_Length is a whole number" in said and "WORD or NONE" in said


def test_a_disabled_module_takes_no_text() -> None:
    with running(f'TextInput {{ Text: "ab", Enabled: false, {CALLS} }}') as r:
        (f,) = r.fields()
        assert f.inp.get("disabled") is True and f.inp.get("hit_testable") is False
        assert f.box.get("opacity") == 0.5  # the default look of :disabled
        click(r, f.inp)
        r.window.simulate("input", text="z")
        assert f.inp.get("text") == "ab" and r.seen == []


# -- the events of a call ----------------------------------------------------------------------


def test_a_call_raises_changed_submit_and_commit_into_a_module_action() -> None:
    with running(f'TextInput {{ Name: One, Text: "ab", {CALLS} }}') as r:
        assert r.problems == [] and bad(r) == []
        (f,) = r.fields()
        click(r, f.inp)
        r.window.simulate("input", text="c")
        r.window.simulate("key_down", key="enter")
        assert r.seen == [
            ("commit", "", None, None, "c"),
            ("changed", "", "ab", "abc", None),
            ("submit", "", None, None, None),
        ]


def test_two_calls_keep_their_own_text_and_events() -> None:
    with running(
        f'TextInput {{ Name: A, Text: "a", {CALLS} }}\nTextInput {{ Name: B, Text: "b", {CALLS} }}'
    ) as r:
        a, b = r.fields()
        click(r, b.inp)
        r.window.simulate("input", text="!")
        assert (a.inp.get("text"), b.inp.get("text")) == ("a", "b!")
        assert [e[2:4] for e in r.seen if e[0] == "changed"] == [("b", "b!")]


def test_a_module_that_uses_a_text_input_names_its_own_actions() -> None:
    host = (
        "---\nTDL: 0.1\nName: Host\n---\n"
        "Module { FlexBox { Children { "
        'TextInput { Text: "q", On_Changed: changed, On_Submit: submit, On_Text_Commit: commit } '
        "} } }"
    )
    with running("Host { Name: H }", extra={"Host": host}) as r:
        assert r.problems == [] and bad(r) == [], (r.problems, bad(r))
        (f,) = r.fields()
        click(r, f.inp)
        r.window.simulate("input", text="r")
        ((kind, use, old, new, _),) = [e for e in r.seen if e[0] == "changed"]
        assert (kind, old, new) == ("changed", "q", "qr") and use.startswith("Host@")


def test_a_module_whose_root_cannot_raise_the_event_is_an_error_at_the_handler() -> None:
    plain = "---\nTDL: 0.1\nName: Plain\n---\nModule { FlexBox { Width: 10, Height: 10 } }"
    code = {"Plain": "from tess_shell import Module\nclass Plain(Module): pass\n"}
    with running(
        'Plain { On_Changed { Action: Call, Target: "Host.changed" } }',
        extra={"Plain": plain},
        extra_code=code,
    ) as r:
        said = [x for x in r.lines if "does not raise On_Changed" in x]
        assert said and "its root block is a FlexBox" in said[0]


# -- a stylesheet ------------------------------------------------------------------------------


def test_the_placeholder_part_colours_the_hint_and_its_disabled_state_does() -> None:
    sheet = (
        "---\nTDL: 0.1\nName: G\n---\nStylesheet {\n"
        '  Rule { Selector: "TextInput::placeholder", Foreground: "#102030" }\n'
        '  Rule { Selector: "TextInput::placeholder:disabled", Foreground: "#405060" }\n}\n'
    )
    with running(
        'TextInput { Name: A, Placeholder: "p" }\n'
        'TextInput { Name: B, Placeholder: "p", Enabled: false }',
        sheet=sheet,
    ) as r:
        assert r.problems == [] and bad(r) == []
        a, b = r.fields()
        assert a.inp.get("placeholder_fill") == (16, 32, 48, 255)
        assert b.inp.get("placeholder_fill") == (64, 80, 96, 255)  # the part's own disabled look
        assert a.inp.get("fill") == (228, 234, 241, 255)  # the text is not the hint


def test_a_rule_on_the_module_restyles_it_and_overflow_is_a_style_key() -> None:
    sheet = (
        "---\nTDL: 0.1\nName: G\n---\nStylesheet {\n"
        '  Rule { Selector: "TextInput", Overflow: ELLIPSIS, Background: "#0a0b0c", '
        'Foreground: "#ffeedd", Border_Width: 3 }\n'
        '  Rule { Selector: "TextEditor", Background: "#0c0b0a" }\n}\n'
    )
    with running("TextInput { Text: x }\nTextEditor { Text: y }", sheet=sheet) as r:
        assert r.problems == [] and bad(r) == []
        a, b = r.fields()
        assert a.inp.get("overflow") == "ellipsis" and a.box.get("fill") == (10, 11, 12, 255)
        assert a.inp.get("fill") == (255, 238, 221, 255) and a.box.get("stroke_width") == 3
        assert b.box.get("fill") == (12, 11, 10, 255) and b.inp.get("wrap") == "word"


def test_a_rule_on_the_block_reaches_both_modules() -> None:
    sheet = (
        "---\nTDL: 0.1\nName: G\n---\nStylesheet {\n"
        '  Rule { Selector: "TextField", Corner_Radius: 10, Padding: 2 }\n}\n'
    )
    with running("TextInput { Text: x }\nTextEditor { Text: y }", sheet=sheet) as r:
        for f in r.fields():
            assert f.box.get("corner_radius") in (10, (10, 10, 10, 10)), f.box.get("corner_radius")
            assert f.box.get("padding") == 2


# -- the look ----------------------------------------------------------------------------------


def test_a_change_of_light_or_dark_repaints_the_field_and_keeps_the_typed_text() -> None:
    with running('TextInput { Text: "ab", Placeholder: "p" }') as r:
        (f,) = r.fields()
        dark = (f.box.get("fill"), f.inp.get("fill"), f.box.get("stroke_color"))
        assert dark == ((27, 34, 43, 255), (228, 234, 241, 255), (85, 101, 122, 255))
        f.inp.focus()  # no pointer: a hovered field would show its hover look
        r.window.simulate("input", text="c")
        r.manager.set_look(look(DARK_THEME, scheme="light"))
        (g,) = r.fields()
        assert g.box.get("fill") == (255, 255, 255, 255)  # surface_raised, light
        assert g.inp.get("fill") == (22, 32, 43, 255) and g.box.get("stroke_color") == (
            122,
            136,
            150,
            255,
        )
        assert g.inp.get("text") == "abc" and g.inp == f.inp  # the same node: the typing is kept
        r.manager.set_look(look(DARK_THEME, scheme="dark"))
        assert r.fields()[0].box.get("fill") == dark[0]


def test_the_look_follows_a_mode_with_no_stylesheet_at_all() -> None:
    with running("TextEditor { Text: x }") as r:
        (f,) = r.fields()
        assert f.inp.get("fill") == (228, 234, 241, 255)
        r.manager.set_look(r.manager.look.with_appearance(Appearance(scheme="light")))
        assert r.fields()[0].inp.get("fill") == (22, 32, 43, 255)


# -- the keyboard ------------------------------------------------------------------------------


def test_a_bar_that_holds_a_field_takes_the_keyboard_on_demand_and_says_so() -> None:
    with running("TextInput { }") as r:
        assert r.window.get("keyboard") == "on_demand"
        assert any("keyboard on_demand, it holds a text field" in x for x in r.lines)
    with running("Host { }") as r:
        assert r.window.get("keyboard") == "none"


def panel(name: str, keyboard: str, body: str) -> str:
    return (
        f"Panel {{ Name: {name}, Layer: TOP, Width: 260, Height: 80, Keyboard: {keyboard}, "
        f"Children {{ {body} }} }}"
    )


def test_a_panel_takes_the_keyboard_on_demand_when_it_holds_a_field_and_has_none() -> None:
    panels = "\n".join(
        (
            panel("P_None", "NONE", "TextInput { }"),
            panel("P_Exclusive", "EXCLUSIVE", "TextEditor { }"),
            panel("P_Demand", "ON_DEMAND", "Host { }"),
            panel("P_Plain", "NONE", "Host { }"),
        )
    )
    with running("Host { }", popups=panels) as r:
        modes = {s.name: s.window.get("keyboard") for s in r.manager.surfaces}
        assert modes["P_None"] == "on_demand"  # no mode of its own: a field gets it on a click
        assert modes["P_Exclusive"] == "exclusive"  # only ever written
        assert modes["P_Demand"] == "on_demand" and modes["P_Plain"] == "none"
        assert any("Panel" in x and "P_None" in x and "on_demand" in x for x in r.lines)


def test_a_written_keyboard_none_on_a_surface_with_a_field_is_overridden_with_one_warning() -> None:
    """Q17: the override is said once, naming the surface and the field; a Panel that never wrote
    ``Keyboard`` gets the info line only."""
    unwritten = (
        "Panel { Name: P_Unwritten, Layer: TOP, Width: 260, Height: 80, "
        "Children { TextInput { } } }"
    )
    panels = "\n".join(
        (
            panel("P_None", "NONE", "TextInput { Name: Query }"),
            unwritten,
            panel("P_Plain", "NONE", "Host { }"),
            panel("P_Demand", "ON_DEMAND", "TextInput { }"),
        )
    )
    with running("Host { }", popups=panels) as r:
        modes = {s.name: s.window.get("keyboard") for s in r.manager.surfaces}
        assert modes["P_None"] == "on_demand" and modes["P_Unwritten"] == "on_demand"
        said = [x for x in r.lines if "| WARNING " in x and "Keyboard: NONE is written" in x]
        assert len(said) == 1, said
        assert "P_None" in said[0] and "TextInput" in said[0] and "on_demand" in said[0]
        assert not any("P_Unwritten" in x and "| WARNING " in x for x in r.lines)
        assert not any("P_Plain" in x and "| WARNING " in x for x in r.lines)


def test_the_keyboard_word_of_a_surface() -> None:
    def keyboard(mode: str) -> PanelDef:
        return PanelDef("P", NO_ORIGIN, keyboard=mode)

    assert _keyboard(keyboard("NONE")) == "none"
    assert _keyboard(keyboard("NONE"), False, True) == "on_demand"
    assert _keyboard(keyboard("EXCLUSIVE"), False, True) == "exclusive"
    assert _keyboard(keyboard("ON_DEMAND"), False, False) == "on_demand"
    assert _keyboard(keyboard("NONE"), True, True) == "none"  # a hidden panel takes none


def test_a_commit_that_max_length_refused_raises_no_on_text_commit() -> None:
    """tre raises ``input`` for an edit ``Max_Length`` refused, with the text as it was: the shell
    stays silent (Q20); ``On_Changed`` never fired for it either."""
    with running(f'TextInput {{ Name: One, Text: "abc", Max_Length: 3, {CALLS} }}') as r:
        assert r.problems == [] and bad(r) == []
        (f,) = r.fields()
        click(r, f.inp)
        r.window.simulate("input", text="d")
        assert f.inp.get("text") == "abc" and r.seen == []
        r.window.simulate("key_down", key="backspace")  # now there is room again
        assert f.inp.get("text") == "ab"
        r.seen.clear()
        r.window.simulate("input", text="c")  # the same text as before the edit before the last one
        assert f.inp.get("text") == "abc"
        assert [s[0] for s in r.seen] == ["commit", "changed"], r.seen
        r.seen.clear()
        r.window.simulate("input", text="x")  # full again: refused again
        assert r.seen == []
