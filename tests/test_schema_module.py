"""Schema stage for ``*_Module.tdl``, slots in values, and module calls in a shell file."""

from __future__ import annotations

import tess_dl

from tess_shell.binder import model as m
from tess_shell.schema.findings import Finding
from tess_shell.schema.model import ModuleDef
from tess_shell.schema.shell import read_module, read_shell

HEAD = "---\nTDL: 0.1\nName: {name}\n---\n"

CLOCK = """
Module {
    Params {
        format { Type: string, Default: "%H:%M" }
        zone { Type: string, Default: "" }
        size { Type: number, Default: 14 }
        bold { Type: boolean, Default: false }
    }
    Children {
        Text {
            Name: Face
            Text: {{ time }}
            Width: Now {{ params.size }}
            Style { Foreground: "#ffffff" }
        }
    }
}
"""


def parse(text: str, file: str) -> tess_dl.Document:
    result = tess_dl.parse(text, path=file)
    assert not result.errors and result.document is not None, result.errors
    return result.document


def module(body: str = CLOCK, name: str = "Clock") -> tuple[ModuleDef | None, list[Finding]]:
    doc = parse(HEAD.format(name=name) + body, "Modules/Clock/Clock_Module.tdl")
    return read_module(doc, "Modules/Clock/Clock_Module.tdl")


def clock() -> ModuleDef:
    found, findings = module()
    assert found is not None and findings == []
    return found


def test_a_module_file_is_typed() -> None:
    mod = clock()
    assert mod.name == "Clock"
    assert {p.name: (p.type, p.default) for p in mod.params.values()} == {
        "format": ("string", m.Text("%H:%M")),
        "zone": ("string", m.Text("")),
        "size": ("number", m.Number(14)),
        "bold": ("boolean", m.Bool(False)),
    }
    (face,) = mod.children
    assert isinstance(face, m.Node) and face.kind == "Text" and face.name == "Face"


def test_a_slot_keeps_its_text_and_the_origin_of_the_text_not_the_braces() -> None:
    mod = clock()
    face = mod.children[0]
    assert isinstance(face, m.Node)
    slot = face.props["Text"]
    assert isinstance(slot, m.SlotValue) and slot.single
    (part,) = slot.parts
    assert isinstance(part, m.SlotPart) and part.text == " time "
    lines = (HEAD.format(name="Clock") + CLOCK).splitlines()
    text = lines[part.origin.line - 1]
    assert text[part.origin.column - 1 :].startswith(" time }}")  # the text, not the braces
    assert "Text: {{" in text


def test_a_template_has_literal_and_slot_parts() -> None:
    face = clock().children[0]
    assert isinstance(face, m.Node)
    width = face.props["Width"]
    assert isinstance(width, m.SlotValue) and not width.single
    assert width.parts[0] == "Now " and isinstance(width.parts[1], m.SlotPart)


def test_a_single_layout_block_may_be_written_without_children() -> None:
    body = "Module {\n    Text { Text: hello }\n}\n"
    found, findings = module(body)
    assert findings == [] and found is not None and len(found.children) == 1


def test_module_errors_are_located() -> None:
    bad_type = CLOCK.replace("Type: number", "Type: numbr")
    found, findings = module(bad_type)
    assert found is None
    (f,) = [x for x in findings if x.severity == "error"]
    assert f.rule == "bad-value" and "string, number, boolean" in f.message
    found, findings = module("Shell {\n}\n")
    assert found is None and findings[0].rule == "module-root"
    found, findings = module("Module {\n    Text { }\n    Text { }\n}\n")
    assert found is None and findings[0].rule == "missing-key"


def test_a_module_style_file_is_refused_until_m2b() -> None:
    found, findings = module(CLOCK.replace("Module {", "Module {\n    Style: Clock_Style.tdl", 1))
    assert found is None and findings[0].rule == "not-built"


SHELL = """
Shell {
    Monitor {
        Name: Main
        Index: 0
        Children {
            Bar {
                Name: Top
                Edge: TOP
                Width: EXPAND
                Height: 32
                Children {
                    Clock { format: "%H:%M:%S", Name: Local }
                    Clock { }
                }
            }
        }
    }
}
"""


def shell(body: str = SHELL) -> tuple[object, list[Finding]]:
    doc = parse(HEAD.format(name="Main_Shell") + body, "Shells/Main_Shell.tdl")
    return read_shell(doc, "Shells/Main_Shell.tdl", lambda _: "", {"Clock": clock()})


def test_a_module_call_is_a_use_node_with_typed_params() -> None:
    result, findings = shell()
    assert findings == []
    bar = result.monitors[0].surfaces[0]  # type: ignore[attr-defined]
    first, second = bar.children
    assert isinstance(first, m.UseNode) and first.module == "Clock" and first.name == "Local"
    assert first.params == {"format": m.Text("%H:%M:%S")}
    assert isinstance(second, m.UseNode) and second.params == {}


def test_param_errors_name_the_param_and_suggest() -> None:
    result, findings = shell(SHELL.replace('format: "%H:%M:%S"', "formt: x"))
    assert result is None
    (f,) = [x for x in findings if x.severity == "error"]
    assert f.rule == "unknown-key" and "format" in f.hint
    result, findings = shell(SHELL.replace('format: "%H:%M:%S"', "size: big"))
    assert result is None and findings[0].rule == "bad-value" and "size" in findings[0].message


def test_a_param_without_a_default_must_be_passed() -> None:
    needy = CLOCK.replace('format { Type: string, Default: "%H:%M" }', "format { Type: string }")
    found, _ = module(needy)
    assert found is not None
    doc = parse(HEAD.format(name="Main_Shell") + SHELL, "Shells/Main_Shell.tdl")
    result, findings = read_shell(doc, "Shells/Main_Shell.tdl", lambda _: "", {"Clock": found})
    assert result is None
    (f,) = [x for x in findings if x.rule == "missing-key"]
    assert "format" in f.message


def test_an_unknown_head_lists_modules_among_the_names_that_fit() -> None:
    result, findings = shell(SHELL.replace("Clock { }", "Clok { }"))
    assert result is None
    assert "Clock" in findings[0].hint


def test_a_slot_in_a_param_is_kept_for_the_model() -> None:
    """The schema keeps the slot; the model evaluates it in the scope of the call's place (a module,
    or a Popup); a slot in a shell file's own block is refused there (tests/test_param_slots.py)."""
    result, findings = shell(SHELL.replace('format: "%H:%M:%S"', "format: {{ x }}"))
    assert result is not None and findings == []
