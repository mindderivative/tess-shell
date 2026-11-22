"""``Receives { On_Changed: Field }`` in a module (Module File > Receives): the events a call writes
go to the named block of the layout, not to the root. Checked once when the module is read."""

from __future__ import annotations

import pytest
import tess_dl

from tess_shell.schema.shell import read_module
from tests.field_live import running
from tests.test_textfield_modules import bad, click

PAIR = (
    "---\nTDL: 0.2\nName: Pair\n---\n"
    "Module {\n"
    '  Params { Text { Type: string, Default: "" } }\n'
    "  Receives { On_Changed: Field, On_Submit: Field }\n"
    "  FlexBox { Name: Root, Children {\n"
    '    Text { Name: Title, Text: "t" }\n'
    "    TextField { Name: Field, Text: <| params.Text |> }\n"
    "  } }\n"
    "}\n"
)
CODE = {"Pair": "from tess_shell import Module\nclass Pair(Module): pass\n"}
EVENTS = (
    'On_Changed { Action: Call, Target: "Host.changed" }, '
    'On_Submit { Action: Call, Target: "Host.submit" }'
)


def read(body: str) -> list[str]:
    """The errors of a module file whose body (after the header) is ``body``."""
    doc = tess_dl.parse("---\nTDL: 0.2\nName: M\n---\n" + body, path="M_Module.tdl").document
    assert doc is not None
    module, findings = read_module(doc, "M_Module.tdl")
    return [f"{f.rule}: {f.message}" for f in findings if f.severity == "error"]


def test_a_call_event_reaches_the_inner_field_not_the_flexbox_root() -> None:
    with running(
        f'Pair {{ Name: P, Text: "ab", {EVENTS} }}', extra={"Pair": PAIR}, extra_code=CODE
    ) as r:
        assert r.problems == [] and bad(r) == [], (r.problems, bad(r))
        (f,) = r.fields()
        click(r, f.inp)
        r.window.simulate("input", text="c")
        r.window.simulate("key_down", key="enter")
        assert [(e[0], e[2], e[3]) for e in r.seen] == [
            ("changed", "ab", "abc"),
            ("submit", None, None),
        ]


def test_an_event_the_module_does_not_name_still_goes_to_the_root_and_is_checked_there() -> None:
    with running(
        'Pair { Name: P, On_Text_Commit { Action: Call, Target: "Host.commit" } }',
        extra={"Pair": PAIR},
        extra_code=CODE,
    ) as r:
        said = [x for x in r.lines if "does not raise On_Text_Commit" in x]
        assert said and "its root block is a FlexBox" in said[0]


def test_two_calls_of_the_module_keep_their_own_events() -> None:
    with running(
        f'Pair {{ Name: A, Text: "a", {EVENTS} }}\nPair {{ Name: B, Text: "b", {EVENTS} }}',
        extra={"Pair": PAIR},
        extra_code=CODE,
    ) as r:
        a, b = r.fields()
        click(r, b.inp)
        r.window.simulate("input", text="!")
        assert [e[2:4] for e in r.seen if e[0] == "changed"] == [("b", "b!")]
        assert a.inp.get("text") == "a"


@pytest.mark.parametrize(
    ("receives", "layout", "rule"),
    [
        ("On_Changed: Nowhere", "TextField { Name: Field }", "receives-unknown"),
        (
            "On_Changed: Field",
            "FlexBox { Children { Text { Name: Field, Text: x } } }",
            "receives-event",
        ),
        ("Changed: Field", "TextField { Name: Field }", "bad-key"),
    ],
)
def test_a_receives_that_cannot_work_is_refused_when_the_module_is_read(
    receives: str, layout: str, rule: str
) -> None:
    errors = read(f"Module {{ Receives {{ {receives} }} {layout} }}")
    assert any(e.startswith(rule) for e in errors), errors


def test_a_block_in_an_if_or_a_for_may_be_the_target() -> None:
    body = (
        "Module { Params { show { Type: boolean, Default: true } } "
        "Receives { On_Changed: Field } "
        "FlexBox { Children { If <| params.show |> { TextField { Name: Field } } } } }"
    )
    assert read(body) == []


def test_without_receives_nothing_changes() -> None:
    assert read("Module { TextField { Name: Field } }") == []
