"""``Call`` checks its arguments against the ``@action`` method (Events and Actions > Call, M4 Brief
question 14, decided 2026-11-13): the parameters after ``event`` are the arguments; an unknown name
or a missing required one is a load finding at the handler; an action with only ``event`` or with
``**kwargs`` takes any names; the declared arguments arrive as keywords and in ``event.args``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tests.test_call import Live, running

OTHER_PY = """
from tess_shell import Module, action

class Other(Module):
    def __init__(self):
        self.seen = []

    @action
    def go(self, event, Id, Mode="a"):
        self.seen.append(("go", Id, Mode, dict(event.args)))

    @action
    def free(self, event):
        self.seen.append(("free", dict(event.args)))

    @action
    def anything(self, event, **rest):
        self.seen.append(("anything", rest, dict(event.args)))

    @action
    def mixed(self, event, Id, **rest):
        self.seen.append(("mixed", Id, rest))

    @action
    def only_default(self, event, Mode="a"):
        self.seen.append(("only_default", Mode))
"""
OTHER = "Module { FlexBox { Name: Root, Width: 10, Height: 10 } }"


def call(target: str, args: str) -> str:
    sep = ", " if args else ""
    return f'On_Click {{ Action: Call, Target: "Other.{target}"{sep}{args} }}'


def shell_box(handler: str) -> str:
    box = "FlexBox { Name: Shell_Box, Width: 30, Height: 10, "
    return "Other { Name: Other_One } " + box + handler + " }"


def problems(tmp_path: Path, handler: str) -> list[Any]:
    r = running(
        tmp_path,
        children=shell_box(handler),
        layouts={"Other": OTHER},
        code={"Other": OTHER_PY},
    )
    return r.problems


def test_a_call_from_a_shell_file_with_a_misspelt_argument_names_it_and_the_nearest(
    tmp_path: Path,
) -> None:
    (f,) = problems(tmp_path, call("go", "Id: 1, Moed: 2"))
    assert f.severity == "error" and f.rule == "unknown-argument"
    assert "Other.go has no argument Moed" in f.message and "Mode" in f.hint
    assert f.file == "Shells/Main_Shell.tdl" and f.line > 0  # at the handler in the shell file


def test_an_argument_that_is_nothing_like_a_name_lists_the_arguments(tmp_path: Path) -> None:
    (f,) = problems(tmp_path, call("go", "Id: 1, Zzzzzz: 2"))
    assert f.rule == "unknown-argument" and f.hint == "its arguments: Id, Mode"


def test_a_missing_required_argument_is_an_error_naming_it(tmp_path: Path) -> None:
    (f,) = problems(tmp_path, call("go", "Mode: 1"))
    assert f.rule == "missing-argument" and "Other.go needs the argument Id" in f.message
    (f,) = problems(tmp_path, call("go", ""))
    assert f.rule == "missing-argument"


def test_both_errors_are_reported_and_an_optional_one_may_be_left_out(tmp_path: Path) -> None:
    rules = sorted(f.rule for f in problems(tmp_path, call("go", "Bad: 1")))
    assert rules == ["missing-argument", "unknown-argument"]
    assert problems(tmp_path, call("go", "Id: 1")) == []
    assert problems(tmp_path, call("go", "Id: 1, Mode: 2")) == []


def test_a_slot_argument_is_checked_by_its_name_only(tmp_path: Path) -> None:
    assert problems(tmp_path, call("go", "Id: {{ event.name }}")) == []
    (f,) = problems(tmp_path, call("go", "Id: 1, Mod: {{ event.name }}"))
    assert f.rule == "unknown-argument" and "Mod" in f.message
    (f,) = problems(tmp_path, call("go", "Mode: {{ event.name }}"))
    assert f.rule == "missing-argument"  # a slot named Mode does not give Id


def test_an_action_with_only_event_or_with_kwargs_takes_any_names(tmp_path: Path) -> None:
    assert problems(tmp_path, call("free", "A: 1, B: 2")) == []
    assert problems(tmp_path, call("free", "")) == []
    assert problems(tmp_path, call("anything", "A: 1, B: {{ event.name }}")) == []
    assert problems(tmp_path, call("anything", "")) == []


def test_an_action_with_named_parameters_and_kwargs_needs_the_required_ones_only(
    tmp_path: Path,
) -> None:
    assert problems(tmp_path, call("mixed", "Id: 1, Whatever: 2")) == []
    (f,) = problems(tmp_path, call("mixed", "Whatever: 2"))
    assert f.rule == "missing-argument" and "Id" in f.message


def test_an_action_whose_parameters_all_have_defaults_is_still_checked(tmp_path: Path) -> None:
    assert problems(tmp_path, call("only_default", "")) == []
    (f,) = problems(tmp_path, call("only_default", "Mod: 1"))
    assert f.rule == "unknown-argument" and "Mode" in f.hint


def test_a_call_in_a_module_layout_in_a_for_and_in_a_popup_is_checked_too(tmp_path: Path) -> None:
    layouts = {
        "Other": OTHER,
        "Btn": (
            "Module { FlexBox { Name: Root, Flex: VERTICAL, Children {\n"
            "For item In {{ items }} Key {{ item.id }} {\n"
            "FlexBox { Width: 40, Height: 10, "
            + call("go", "Id: {{ item.id }}, Moed: {{ item.id }}")
            + " }\n} } } }"
        ),
    }
    popups = (
        "Popup { Name: Menu, Children { FlexBox { Name: In_Popup, Width: 20, Height: 10, "
        + call("go", "Mode: 1")
        + " } } }"
    )
    r = running(
        tmp_path,
        children="Btn { Name: Btn_One } Other { Name: Other_One }",
        popups=popups,
        layouts=layouts,
        code={"Other": OTHER_PY},
    )
    found = sorted((f.rule, f.file) for f in r.problems)
    assert found == [
        ("missing-argument", "Shells/Main_Shell.tdl"),  # the Popup's: no Id
        ("unknown-argument", "x.tdl"),  # the For entry's: Moed, once however many entries
    ]


def test_a_bare_action_in_a_modules_own_layout_is_checked_once_per_handler(
    tmp_path: Path,
) -> None:
    layouts = {
        "Other": (
            "Module { FlexBox { Name: Root, Width: 10, Height: 10, "
            "On_Click { Action: go, Id: 1, Moed: 2 } } }"
        )
    }
    r = running(
        tmp_path,
        children="Other { Name: One } Other { Name: Two }",
        layouts=layouts,
        code={"Other": OTHER_PY},
    )
    (f,) = r.problems  # two uses of the module, one handler in the file
    assert f.rule == "unknown-argument" and "Moed" in f.message


def click_shell(r: Live) -> None:
    r.click("Shell_Box")


def test_the_declared_arguments_arrive_as_keywords_and_event_args_stays_whole(
    tmp_path: Path,
) -> None:
    r = running(
        tmp_path,
        children=shell_box(call("go", "Id: {{ event.name }}")),
        layouts={"Other": OTHER},
        code={"Other": OTHER_PY},
    )
    assert r.problems == []
    click_shell(r)
    assert r.action_seen("Other") == [("go", "click", "a", {"Id": "click"})]


def test_an_action_with_only_event_gets_event_args_and_kwargs_gets_them_as_keywords(
    tmp_path: Path,
) -> None:
    r = running(
        tmp_path,
        children=(
            "Other { Name: Other_One } "
            "FlexBox { Name: A, Width: 30, Height: 10, " + call("free", "X: 1, Y: 2") + " } "
            "FlexBox { Name: B, Width: 30, Height: 10, " + call("anything", "X: 1, Y: 2") + " } "
            "FlexBox { Name: C, Width: 30, Height: 10, " + call("mixed", "Id: 3, X: 4") + " }"
        ),
        layouts={"Other": OTHER},
        code={"Other": OTHER_PY},
    )
    assert r.problems == []
    for node in ("A", "B", "C"):
        r.click(node)
    assert r.action_seen("Other") == [
        ("free", {"X": 1, "Y": 2}),
        ("anything", {"X": 1, "Y": 2}, {"X": 1, "Y": 2}),
        ("mixed", 3, {"X": 4}),
    ]
