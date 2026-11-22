"""The ``search_field`` corpus of the Tesserae behavior standard, run on the shell's Launcher query
field (see ``search_field_host.py``). A gap that gets fixed must be removed from its table, or the
test fails. Skipped without the ``tesserae-behavior`` package (``tests/behavior/requirements.txt``:
a private repository until its first release; CI does not install it and this job is not gating).

Two runs: strict (every expectation) and a diagnostic with ``events`` and ``parts`` ignored (NOT a
conformance run), which shows that what the shell does have (typing sets the value, Escape clears
it, the same text is no change) matches the standard."""

from __future__ import annotations

import pytest

pytest.importorskip("tess_behavior")
from tess_behavior.corpus import FAIL, NOT_RUN, PASS, behaviour_cases, corpus_root, run_case  # noqa: E402

from tests.behavior.search_field_host import SearchFieldHost  # noqa: E402

CASES = {
    c.name.removesuffix(".case.json"): c
    for c in behaviour_cases(corpus_root())
    if c.parent.name == "search_field"
}

#: Strict run: case -> (status, why). Not listed: pass (none does).
STRICT: dict[str, tuple[str, str]] = {
    "a11y-tree": (NOT_RUN, "the standard's option clear_label does not exist in the Launcher"),
    "clear-press-keyboard-returns-focus": (NOT_RUN, "the Launcher has no clear button"),
    "clear-press-returns-focus": (NOT_RUN, "the Launcher has no clear button"),
    "controlled-reject": (NOT_RUN, "the query is not a controlled value (no cancelable change)"),
    "disabled": (NOT_RUN, "the Launcher's field has no disabled option"),
    "escape-clears": (FAIL, "the clear button part is absent (and no before_change/change events)"),
    "focus-none-part-via-pointer": (NOT_RUN, "the Launcher has no clear button"),
    "type-same-value": (FAIL, "the clear button part is absent"),
    "type-updates-value": (FAIL, "no before_change/change events with reason and detail"),
}
#: Diagnostic run (events and parts ignored): the cases that cannot run; the rest pass.
NOT_RUN_ALWAYS = {name for name, (status, _) in STRICT.items() if status == NOT_RUN}


def _host(spec, options, controlled, responses):  # type: ignore[no-untyped-def]
    return SearchFieldHost(spec, options, controlled, responses)


def test_the_corpus_has_the_search_field_cases() -> None:
    assert len(CASES) == 9


@pytest.mark.parametrize("name", sorted(CASES))
def test_strict_a_case_gives_the_result_recorded_for_the_launchers_field(name: str) -> None:
    result = run_case(CASES[name], _host)
    assert result.status == STRICT[name][0], f"{name}: {result.status} {result.detail}"


@pytest.mark.parametrize("name", sorted(CASES))
def test_behaviour_without_events_and_parts_what_the_field_has_conforms(name: str) -> None:
    result = run_case(CASES[name], _host, ignore=("events", "parts"))
    expected = NOT_RUN if name in NOT_RUN_ALWAYS else PASS
    assert result.status == expected, f"{name}: {result.status} {result.detail}"
