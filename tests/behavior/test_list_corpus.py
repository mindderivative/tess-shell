"""The ``list`` corpus (the Selection behavior) of the Tesserae behavior standard, run on the
shell's multi-select ``List`` (see ``list_host.py``). A gap that gets fixed must be removed from its
table, or the test fails. Skipped without the ``tesserae-behavior`` package
(``tests/behavior/requirements.txt``: a private repository until its first release; CI does not
install it and the job is not gating).

Three runs. Strict: every expectation; only the two accessibility tree cases pass (see
``KNOWN_GAPS``). A diagnostic with ``events``, ``focus``, ``tree`` and ``active`` ignored (NOT a
conformance run): what the engine's selection gives the shell (the set, the Shift and Ctrl
rules, Ctrl+A, Escape, a click on empty space) matches the standard; what differs is listed
with its reason. The tree cases with only ``events`` and ``focus`` ignored: they pass (listbox
and option, AC-LST-01).
"""

from __future__ import annotations

from typing import Any

import pytest

pytest.importorskip("tess_behavior")
from tess_behavior.corpus import FAIL, NOT_RUN, PASS, behaviour_cases, corpus_root, run_case  # noqa: E402

from tests.behavior.list_host import ListHost  # noqa: E402

CASES = {
    c.name.removesuffix(".case.json"): c
    for c in behaviour_cases(corpus_root())
    if c.parent.name == "list"
}

#: Why a case is not run on the shell's List: the host cannot express its option.
NOT_RUN_WHY = {
    "select-all-key-off": "a List always has Ctrl+A (no select_all_key option)",
    "single-select-on-focus": "a List never selects on focus (no select_on_focus option)",
    "single-select-on-focus-active-descendant": "a List never selects on focus",
    "unselectable-arrow-lands-on-row-active-descendant": "no unselectable row",
    "unselectable-arrow-lands-on-row": "no unselectable row (only disabled, or no Key)",
    "unselectable-row-skipped-by-range": "no unselectable row",
    "unselectable-select-all-skips": "no unselectable row",
    "unselectable-set-from-code-ignores-row": "no unselectable row",
    "unselectable-space-selects-nothing": "no unselectable row",
}

#: The cases that pass strict: the accessibility tree (AC-LST-01: listbox, option, multiselectable).
STRICT_PASS = {"a11y-tree-multiple", "a11y-tree-single"}

#: Why a case fails strict (the first difference is the focus, or the anchor of a single list: the
#: shell's rows take no focus, the engine keeps it on the list, and the shell reports no events).
KNOWN_GAPS = (
    "rows take no keyboard focus (the List is one Tab stop and the engine keeps focus on it: the "
    "standard's `active_descendant` focus model fits, its variants run, but the engine's cursor "
    "row is not readable, so `active` is never seen and the roving `focus: option#X` neither); "
    "the shell reports no selection_change (On_Changed says the chosen keys), so those "
    "events are never seen; the shell's SINGLE keeps no anchor; the announcement is read from "
    "a real AT-SPI bus (tests/test_multiselect_atspi.py), not headless"
)

#: Diagnostic (events, focus and tree ignored): what is not a pass, with its reason.
DIAGNOSTIC: dict[str, tuple[str, str]] = {
    "announce-clear": (NOT_RUN, "the announcement cannot be read headless"),
    "announce-once-after-300ms": (NOT_RUN, "the announcement cannot be read headless"),
    "announce-range": (NOT_RUN, "the announcement cannot be read headless"),
    "announce-select-all": (NOT_RUN, "the announcement cannot be read headless"),
    "announce-single-none": (FAIL, "the shell's SINGLE keeps no anchor"),
    "api-set-is-not-announced": (NOT_RUN, "the announcement cannot be read headless"),
    "ctrl-arrow-moves-focus-space-toggles": (
        FAIL,
        "`consumed` is inferred from the set, the anchor and the focus; the focus move of "
        "Ctrl+Arrow is not observable (adapter limit)",
    ),
    "disabled-row-skipped": (FAIL, "`consumed` of a focus move is not observable (adapter limit)"),
    # the active_descendant model fits the shell's List (the list takes the focus and the engine
    # moves its own cursor row); the cursor row is not readable, so `active` is never seen and a
    # cursor-only key reads as not consumed
    "ctrl-arrow-moves-focus-space-toggles-active-descendant": (
        FAIL,
        "the engine's cursor row is not readable: a Ctrl+Arrow reads as not consumed",
    ),
    "disabled-row-skipped-active-descendant": (
        FAIL,
        "the engine's cursor row is not readable: a move reads as not consumed",
    ),
    "single-mode-keeps-before-change": (FAIL, "the shell's SINGLE keeps no anchor"),
    "single-space-chooses": (FAIL, "the shell's SINGLE keeps no anchor"),
    **{name: (NOT_RUN, why) for name, why in NOT_RUN_WHY.items()},
}


def _host(
    spec: Any, options: Any, controlled: Any, responses: Any, focus_model: str = "roving"
) -> ListHost:
    host = ListHost(spec, options, controlled, responses, focus_model)
    _HOSTS.append(host)
    return host


_HOSTS: list[ListHost] = []


@pytest.fixture(autouse=True)
def _close_hosts() -> Any:
    yield
    while _HOSTS:
        _HOSTS.pop().close()


def test_the_corpus_has_the_list_cases() -> None:
    assert len(CASES) == 36


@pytest.mark.parametrize("name", sorted(CASES))
def test_strict_a_case_gives_the_result_recorded_for_the_list(name: str) -> None:
    result = run_case(CASES[name], _host)
    expected = NOT_RUN if name in NOT_RUN_WHY else PASS if name in STRICT_PASS else FAIL
    assert result.status == expected, f"{name}: {result.status} {result.detail}"


@pytest.mark.parametrize("name", sorted(CASES))
def test_behaviour_without_events_focus_and_tree_what_the_engine_gives_conforms(name: str) -> None:
    result = run_case(CASES[name], _host, ignore=("events", "focus", "tree", "active"))
    expected = DIAGNOSTIC.get(name, (PASS, ""))[0]
    assert result.status == expected, f"{name}: {result.status} {result.detail}"


@pytest.mark.parametrize("name", ["a11y-tree-multiple", "a11y-tree-single"])
def test_the_accessibility_tree_conforms_with_only_events_and_focus_ignored(name: str) -> None:
    """AC-LST-01: listbox and option, `multiselectable`, `selected`, the names."""
    result = run_case(CASES[name], _host, ignore=("events", "focus"))
    assert result.status == PASS, result.detail
