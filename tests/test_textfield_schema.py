"""The TextField block as a shell file reads it (Block Reference > TextField): its keys and their
kinds, ``Wrap`` and ``Overflow`` with their words, the keys that mean nothing to a form of the
field, the events, and the handlers written on a module call (Standard Modules > TextInput)."""

from __future__ import annotations

from typing import Any

import tess_dl

from tess_shell.binder import model as m
from tess_shell.schema.findings import Finding
from tess_shell.schema.look import read_stylesheet
from tess_shell.schema.shell import read_module
from tests.test_call import known
from tests.test_popup import SHELL, read

HEAD = "---\nTDL: 0.1\nName: Fld\n---\n"


def field(body: str) -> tuple[m.Node | None, list[Finding]]:
    """The one TextField written in a Bar, and every finding."""
    shell, findings = read(SHELL % (f"TextField {{ {body} }}", ""))
    if shell is None:
        return None, findings
    (node,) = shell.monitors[0].surfaces[0].children
    assert isinstance(node, m.Node)
    return node, findings


def errors(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == "error"]


def warnings(findings: list[Finding]) -> list[Finding]:
    return [f for f in findings if f.severity == "warning"]


def module(body: str, **modules: Any) -> tuple[Any, list[Finding]]:
    result = tess_dl.parse(HEAD + body, path="Modules/Fld_Module.tdl")
    assert result.document is not None
    return read_module(result.document, "Modules/Fld_Module.tdl", known("Fld", *modules))


# -- the keys -----------------------------------------------------------------------------------


def test_every_key_of_the_block_is_read_with_its_kind() -> None:
    node, findings = field(
        'Text: "hi", Placeholder: "Name", Multiline: true, Selection: [1, 2], '
        "Show_Whitespace: true, Padding: 4, Wrap: NONE, Lines: 5, Read_Only: true, "
        "Max_Length: 12, Label: Name, Width: 200"
    )
    assert node is not None and errors(findings) == [], findings
    props = node.props
    assert props["Text"] == m.Text("hi") and props["Placeholder"] == m.Text("Name")
    assert props["Multiline"] == m.Bool(True) and props["Read_Only"] == m.Bool(True)
    assert isinstance(props["Selection"], m.Seq)
    assert [i.value for i in props["Selection"].items if isinstance(i, m.Number)] == [1, 2]
    assert props["Wrap"] == m.Enum("NONE") and props["Lines"] == m.Number(5)
    assert props["Max_Length"] == m.Number(12) and props["Show_Whitespace"] == m.Bool(True)


def test_password_is_read_on_a_single_line_field() -> None:
    node, findings = field("Password: true")
    assert node is not None and errors(findings) == [] and warnings(findings) == []
    assert node.props["Password"] == m.Bool(True)


def test_the_style_keys_of_the_text_and_the_box_are_read() -> None:
    node, findings = field(
        'Style { Foreground: "#112233", Font_Size: 15, Font_Weight: 500, Overflow: ELLIPSIS, '
        'Background: "#000000", Border_Width: 2, Border_Color: "#ffffff", Corner_Radius: 6, '
        'Placeholder_Foreground: "#888888" }'
    )
    assert node is not None and errors(findings) == [], findings
    assert set(node.style) == {
        "Foreground",
        "Font_Size",
        "Font_Weight",
        "Overflow",
        "Background",
        "Border_Width",
        "Border_Color",
        "Corner_Radius",
        "Placeholder_Foreground",
    }
    assert node.style["Overflow"] == m.Enum("ELLIPSIS")


def test_overflow_takes_scroll_ellipsis_and_clip_and_nothing_else() -> None:
    for word in ("SCROLL", "ELLIPSIS", "CLIP"):
        node, findings = field(f"Style {{ Overflow: {word} }}")
        assert node is not None and errors(findings) == [], (word, findings)
    node, findings = field("Style { Overflow: WORD }")
    assert node is None
    (f,) = errors(findings)
    assert "WORD" in f.message and "SCROLL" in f.message


def test_a_text_still_has_clip_and_ellipsis_only() -> None:
    shell, findings = read(SHELL % ("Text { Text: x, Overflow: SCROLL }", ""))
    assert shell is None and any("SCROLL" in f.message for f in errors(findings))


def test_wrap_takes_word_and_none() -> None:
    for word in ("WORD", "NONE"):
        node, findings = field(f"Multiline: true, Wrap: {word}")
        assert node is not None and errors(findings) == [] and warnings(findings) == []


def test_wrap_char_is_not_built() -> None:
    node, findings = field("Multiline: true, Wrap: CHAR")
    assert node is None  # an error: the shell file does not load
    (f,) = errors(findings)
    assert f.rule == "not-built" and "CHAR" in f.message and "not built" in f.message


def test_a_misspelt_wrap_names_the_choices() -> None:
    node, findings = field("Multiline: true, Wrap: WORDS")
    assert node is None
    (f,) = errors(findings)
    assert "WORD" in f.hint and "NONE" in f.message


def test_multiline_is_fixed_when_the_field_is_built_so_a_slot_is_refused() -> None:
    result = tess_dl.parse(
        HEAD + "Module { Params { p { Type: boolean, Default: true } }\n"
        "TextField { Multiline: {{ params.p }} } }",
        path="Modules/Fld_Module.tdl",
    )
    assert result.document is not None
    found, findings = read_module(result.document, "Modules/Fld_Module.tdl", known("Fld"))
    assert found is None
    (f,) = errors(findings)
    assert "Multiline" in f.message and "slot" in f.message


def test_wrong_values_are_errors_at_the_key() -> None:
    for body, word in (
        ("Max_Length: -1", "Max_Length"),
        ("Max_Length: 1.5", "Max_Length"),
        ("Selection: [1]", "Selection"),
        ("Selection: [-1, 2]", "Selection"),
        ("Multiline: true, Lines: 0", "Lines"),
        ("Read_Only: yes", "Read_Only"),
    ):
        node, findings = field(body)
        assert node is None, body
        assert any(word in f.message for f in errors(findings)), (body, findings)


def test_a_key_the_block_does_not_have_names_the_nearest() -> None:
    node, findings = field("Placeholdr: x")
    assert node is None
    assert "Placeholder" in errors(findings)[0].hint


def test_a_textfield_has_no_children() -> None:
    shell, findings = read(SHELL % ("TextField { Children { Text { Text: x } } }", ""))
    assert shell is None and any("cannot have children" in f.message for f in errors(findings))


# -- the keys that mean nothing to a form of the field -------------------------------------------


def test_wrap_and_lines_on_a_single_line_field_are_warnings_and_have_no_effect() -> None:
    node, findings = field("Wrap: NONE, Lines: 3")
    assert node is not None and errors(findings) == []
    assert {f.rule for f in warnings(findings)} == {"key-not-applied"}
    assert sorted(f.message.split()[0] for f in warnings(findings)) == ["Lines", "Wrap"]
    assert all("single-line" in f.message for f in warnings(findings))


def test_overflow_and_password_on_a_multi_line_field_are_warnings() -> None:
    node, findings = field("Multiline: true, Password: true, Style { Overflow: CLIP }")
    assert node is not None and errors(findings) == []
    assert sorted(f.message.split()[0] for f in warnings(findings)) == ["Overflow", "Password"]
    assert all("multi-line" in f.message for f in warnings(findings))


def test_on_submit_on_a_multi_line_field_is_a_warning_and_the_handler_is_dropped() -> None:
    result = tess_dl.parse(
        HEAD + "Module { TextField { Multiline: true, On_Submit: go, On_Changed: seen } }",
        path="Modules/Fld_Module.tdl",
    )
    assert result.document is not None
    found, findings = read_module(result.document, "Modules/Fld_Module.tdl", known("Fld"))
    assert found is not None and errors(findings) == []
    (w,) = warnings(findings)
    assert "On_Submit" in w.message and "new line" in w.message
    assert set(found.children[0].handlers) == {"On_Changed"}  # type: ignore[union-attr]


def test_on_submit_on_a_single_line_field_is_kept() -> None:
    result = tess_dl.parse(
        HEAD + "Module { TextField { On_Submit: go } }", path="Modules/Fld_Module.tdl"
    )
    assert result.document is not None
    found, findings = read_module(result.document, "Modules/Fld_Module.tdl", known("Fld"))
    assert found is not None and findings == []
    assert set(found.children[0].handlers) == {"On_Submit"}  # type: ignore[union-attr]


# -- the events -----------------------------------------------------------------------------------


def test_the_three_text_events_are_raised_by_a_field_and_a_box_raises_none_of_them() -> None:
    calls = (
        'On_Changed { Action: Call, Target: "Fld.a" }, '
        'On_Submit { Action: Call, Target: "Fld.a" }, '
        'On_Text_Commit { Action: Call, Target: "Fld.a" }'
    )
    shell, findings = read(SHELL % (f"TextField {{ {calls} }}", ""), known("Fld"))
    assert shell is not None and errors(findings) == [], findings
    (node,) = shell.monitors[0].surfaces[0].children
    assert isinstance(node, m.Node)
    assert set(node.handlers) == {"On_Changed", "On_Submit", "On_Text_Commit"}
    assert node.handlers["On_Changed"].module == "Fld"
    shell, findings = read(SHELL % ('Box { On_Changed { Action: Call, Target: "Fld.a" } }', ""))
    assert shell is None and any(f.rule == "event-not-raised" for f in findings)


# -- handlers on a module call --------------------------------------------------------------------


def test_a_call_may_carry_the_text_events_and_the_model_checks_them_later() -> None:
    found, findings = module(
        "Module { FlexBox { Children { Fld { On_Changed: seen, On_Submit { Action: go } } } } }"
    )
    assert found is not None and errors(findings) == [], findings
    (box,) = found.children
    (call,) = box.children  # type: ignore[union-attr]
    assert isinstance(call, m.UseNode) and set(call.handlers) == {"On_Changed", "On_Submit"}
    assert call.handlers["On_Changed"].action == "seen"


def test_style_and_class_on_a_module_call_are_still_not_built() -> None:
    found, findings = module("Module { FlexBox { Children { Fld { Class: x } } } }")
    assert found is None and any(f.rule == "not-built" for f in errors(findings))


def test_an_unknown_event_on_a_call_is_an_error() -> None:
    found, findings = module("Module { FlexBox { Children { Fld { On_Chnaged: seen } } } }")
    assert found is None and any("On_Changed" in f.hint for f in errors(findings))


# -- stylesheet rules -----------------------------------------------------------------------------


def sheet(rule: str) -> tuple[Any, list[Finding]]:
    doc = tess_dl.parse(
        f"---\nTDL: 0.1\nName: S\n---\nStylesheet {{ {rule} }}", path="S_Stylesheet.tdl"
    ).document
    assert doc is not None
    return read_stylesheet(doc, "S_Stylesheet.tdl", {"TextInput"})


def test_a_rule_may_set_overflow_and_the_placeholder_colour_of_a_module() -> None:
    parsed, findings = sheet(
        'Rule { Selector: "TextField", Overflow: ELLIPSIS }\n'
        'Rule { Selector: "TextInput::placeholder", Foreground: "#999999" }\n'
        'Rule { Selector: "TextInput::placeholder:disabled", Foreground: "#444444" }'
    )
    assert parsed is not None and errors(findings) == [], findings
    assert [r.part for r in parsed.rules] == ["", "placeholder", "placeholder"]
    assert parsed.rules[0].values["Overflow"] == m.Enum("ELLIPSIS")


def test_a_rule_names_overflow_words_no_block_has() -> None:
    parsed, findings = sheet('Rule { Selector: "TextField", Overflow: SIDEWAYS }')
    assert parsed is None and any("SCROLL" in f.message for f in errors(findings))
