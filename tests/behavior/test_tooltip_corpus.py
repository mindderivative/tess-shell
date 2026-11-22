"""The ``tooltip`` corpus of the Tesserae behavior standard, run on tess-shell's real tooltip (see
``tooltip_host.py``). The result of each case is a fact about the shell. A gap that gets fixed must
be removed from its table, or the test fails. Skipped without the ``tesserae-behavior`` package
(``tests/behavior/requirements.txt``: a private repository until its first release, so CI does not
install it and this job is not gating).

Two runs, both honest:

* strict: every expectation checked. The shell has no cancelable change request (``before_change``),
  so every case that opens or closes the tooltip by input fails on that one event;
* behaviour: the same cases with ``events`` ignored (a diagnostic, NOT a conformance run), so the
  other differences (state, focus, parts, tree, consumed) show. These are the genuine gaps."""

from __future__ import annotations

import pytest

pytest.importorskip("tess_behavior")
from tess_behavior.corpus import FAIL, NOT_RUN, PASS, behaviour_cases, corpus_root, run_case  # noqa: E402

from tests.behavior.tooltip_host import TooltipHost  # noqa: E402

CASES = {
    c.name.removesuffix(".case.json"): c
    for c in behaviour_cases(corpus_root())
    if c.parent.name == "tooltip"
}

#: Strict run: the cases that pass; every other case fails on the missing ``before_change`` (and
#: ``pointer-focus-shows-no-tooltip`` is not run).
STRICT_PASS = {"a11y-tree-closed", "leave-before-delay", "pointer-press-before-delay-shows-nothing"}
NO_BEFORE_CHANGE = (
    "the shell has no cancelable change request: a tooltip opens and closes without a "
    "before_change event (its `change` is the tooltip_log entry, reason and detail included)"
)

#: Behaviour run (events ignored): case -> (status, why). Not listed: pass.
GAPS: dict[str, tuple[str, str]] = {
    "blur-closes": (FAIL, "keyboard focus leaving the block does not close its tooltip"),
    "escape-closes-and-stays-closed": (
        FAIL,
        "`consumed` is not observable by the adapter (it reports false): adapter limit",
    ),
    "grace-enter-tip-keeps-open": (
        NOT_RUN,
        "the adapter does not drive the pointer onto the open tip (the shell supports it: "
        "_popup_enter): adapter limit, to do",
    ),
    "key-enter-closes": (FAIL, "Enter on the focused trigger does not close its tooltip"),
    "key-space-closes": (FAIL, "Space on the focused trigger does not close its tooltip"),
    "pointer-focus-shows-no-tooltip": (
        NOT_RUN,
        "a focus by pointer without a press cannot be driven: a pointer on the block presses it",
    ),
    "window-focus-loss-closes": (FAIL, "the window losing focus does not close the tooltip"),
}


def _host(spec, options, controlled, responses):  # type: ignore[no-untyped-def]
    return TooltipHost(spec, options, controlled, responses)


def test_the_corpus_has_the_tooltip_cases() -> None:
    assert len(CASES) == 17


@pytest.mark.parametrize("name", sorted(CASES))
def test_strict_a_case_gives_the_result_recorded_for_the_shells_tooltip(name: str) -> None:
    expected = (
        PASS
        if name in STRICT_PASS
        else NOT_RUN
        if name == "pointer-focus-shows-no-tooltip"
        else FAIL
    )
    result = run_case(CASES[name], _host)
    assert result.status == expected, f"{name}: {result.status} {result.detail}"
    if expected == FAIL:
        assert (
            result.name
        )  # failing on the missing before_change is the strict reason: NO_BEFORE_CHANGE


@pytest.mark.parametrize("name", sorted(CASES))
def test_behaviour_without_events_a_case_gives_the_result_recorded(name: str) -> None:
    result = run_case(CASES[name], _host, ignore=("events",))
    assert result.status == GAPS.get(name, (PASS, ""))[0], (
        f"{name}: {result.status} {result.detail}"
    )
