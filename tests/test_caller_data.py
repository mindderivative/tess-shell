"""``caller`` and ``caller.data`` in a Popup's content (Events and Actions > caller.data; Popup >
What the Popup Knows): a module passes ``data`` to ``ctx.popup``, the Popup's slots read it."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tess_shell.model.expand import expand
from tests.test_call import _remove_log_sinks as _remove_call_sinks  # noqa: F401
from tests.test_call import running
from tests.test_popup import SHELL, read, rig
from tests.test_popup import _remove_log_sinks as _remove_popup_sinks  # noqa: F401

FROM_CALLER = (
    "Popup { Name: Menu, Gap: 4, Children { FlexBox { Name: Card, Padding: 6, Children { "
    "Text { Name: Heading, Text: {{ caller.data.Title }}, Width: AUTO, Height: AUTO, "
    "Font_Size: 14 } } } } }"
)

ITEM = (
    "Popup { Name: Menu, Children { FlexBox { Name: Item, Width: 50, Height: 20, "
    'On_Click { Action: Call, Target: "Btn.picked", Id: {{ caller.data.Id }}, '
    "Who: {{ caller.use.params.label }} } } } }"
)


def test_a_slot_in_the_content_reads_the_data_the_module_passed() -> None:
    (r,) = list(rig(FROM_CALLER))
    op = r.call(data={"Title": "Hello", "items": ["a", "b"]})
    assert op is not None and "not read yet" not in r.log()
    assert op.view.nodes["Heading"].get("text") == "Hello"


def test_with_no_data_caller_data_is_empty_and_a_missing_key_warns_but_opens() -> None:
    (r,) = list(rig(FROM_CALLER))
    op = r.call()
    assert op is not None and op.record is not None and op.record["data"] == {}
    assert op.view.nodes["Heading"].get("text") == ""
    warnings = [x for x in r.lines if "WARNING" in x and "Title" in x]
    assert len(warnings) == 1  # a runtime warning, not a load error


def test_the_caller_record_has_the_module_the_use_the_rectangle_and_the_source() -> None:
    (r,) = list(rig(FROM_CALLER))
    op = r.call(data={"Title": "t"})
    rec = op.record
    assert rec["module"] == "Btn" and rec["data"] == {"Title": "t"}
    assert rec["use"]["key"] == r.use and rec["use"]["uid"] == r.use.split("@", 1)[1]
    assert rec["use"]["name"].endswith("Btn_One") and rec["use"]["monitor"]
    assert rec["rect"]["width"] > 0 and rec["rect"]["height"] > 0
    assert rec["source"] == op.caller.block != ""


def test_the_data_is_a_copy_that_does_not_follow_the_callers_object() -> None:
    (r,) = list(rig(FROM_CALLER))
    data: dict[str, Any] = {"Title": "one", "list": [1, (2, 3)]}
    op = r.call(data=data)
    data["Title"] = "two"
    data["list"].append(4)
    assert op.record["data"] == {"Title": "one", "list": [1, [2, 3]]}
    assert op.view.nodes["Heading"].get("text") == "one"


def test_data_that_is_not_plain_is_an_error_and_the_popup_is_not_opened() -> None:
    (r,) = list(rig(FROM_CALLER))
    assert r.call(data={"Title": object()}) is None
    errors = [x for x in r.lines if "ERROR" in x]
    assert len(errors) == 1 and "data.Title" in errors[0] and "not plain data" in errors[0]


def test_a_popup_is_built_fresh_on_each_open_and_sees_the_data_of_that_call() -> None:
    (r,) = list(rig(FROM_CALLER))
    first = r.call(data={"Title": "first"})
    assert r.call(data={"Title": "again"}) is None  # the same use again: it toggles closed
    second = r.call(data={"Title": "second"})
    assert first.view is None or first.closing
    assert second.view.nodes["Heading"].get("text") == "second"


def test_a_block_of_the_popup_can_hand_caller_data_to_a_modules_action(tmp_path: Path) -> None:
    r = running(tmp_path, popups=ITEM)
    assert r.problems == []
    r.manager.popups.call("Btn", r.uses[0], "Menu", {"Id": 7})
    op = r.manager.popups.current
    assert op is not None
    op.window.simulate("click", op.view.nodes["Item"])
    ((use, args),) = r.action_seen()
    assert use == "" and args == {"Id": 7, "Who": "L"}  # a shell-file block has no use


def test_a_module_used_in_the_popup_reads_caller_in_its_layout(tmp_path: Path) -> None:
    layouts = {
        "Card": "Module { FlexBox { Children { Text { Name: Heading, "
        "Text: {{ caller.data.Title }}, Width: AUTO, Height: AUTO } } } }"
    }
    popups = "Popup { Name: Menu, Children { Card { Name: C } } }"
    r = running(tmp_path, popups=popups, layouts=layouts)
    r.manager.popups.call("Btn", r.uses[0], "Menu", {"Title": "in a module"})
    op = r.manager.popups.current
    assert op is not None
    (heading,) = [n for k, n in op.view.nodes.items() if k.endswith("/Heading")]
    assert heading.get("text") == "in a module"


# -- where a slot is allowed --------------------------------------------------------------------


def test_a_slot_in_a_shell_file_block_outside_a_popup_is_still_an_error() -> None:
    shell, findings = read(SHELL % ("Text { Text: {{ caller.data.x }} }", ""))
    assert shell is not None, findings
    out = expand(shell.monitors[0].surfaces[0].children, "S.M.B", {}, lambda k: k, "Main")
    assert [e.message for e in out.errors] == ["a slot outside a module is not built yet"]


def test_a_slot_in_a_popup_or_a_tooltip_of_a_shell_file_is_allowed() -> None:
    popup = "Popup { Name: P, Children { Text { Text: {{ caller.data.x }} } } }"
    tip = (
        "FlexBox { Width: 10, Height: 10, Tooltip { Children { Text { Text: {{ caller.source }} "
        "} } } }"
    )
    shell, findings = read(SHELL % (tip, popup))
    assert shell is not None, findings
    bar, popups = shell.monitors[0].surfaces[0], shell.monitors[0].popups
    assert not expand(bar.children, "S.M.B", {}, lambda k: k, "Main").errors
    assert not expand(popups[0].children, "S.M.P", {}, lambda k: k, "Main", in_popup=True).errors
    out = expand(popups[0].children, "S.M.P", {}, lambda k: k, "Main")  # not told it is a popup
    assert out.errors
