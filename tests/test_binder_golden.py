"""The binder builds what it built before the bind cost work (Performance Budgets B18): the entries
of a built view and what tre says about each node, for the standard modules in a real headless Bar
and for typed trees with states, motion, handlers, hidden blocks and a Tab_Index, equal to a record
made from the binder as it was (``tests/fixtures/binder_golden.json``). A cheaper binder must not
change one property, listener, control or Tab rank."""

from __future__ import annotations

import json
from typing import Any

import pytest

from tess_shell.binder.build import build
from tests.binder_golden import GOLDEN, LAYOUTS, direct_trees, dump_view, window_for
from tests.widgets_live import running

EXPECTED: dict[str, Any] = json.loads(GOLDEN.read_text())


@pytest.mark.parametrize("name", sorted(LAYOUTS))
def test_a_layout_builds_what_it_built_before(name: str) -> None:
    with running(LAYOUTS[name]) as w:
        built = dump_view(w.view)
    assert built == EXPECTED[f"layout:{name}"]


@pytest.mark.parametrize("name", sorted(direct_trees()))
def test_a_typed_tree_builds_what_it_built_before(name: str) -> None:
    view = build(direct_trees()[name], window_for())
    try:
        assert dump_view(view) == EXPECTED[f"direct:{name}"]
    finally:
        view.dispose()


def test_the_record_holds_every_fixture() -> None:
    assert set(EXPECTED) == {f"layout:{n}" for n in LAYOUTS} | {
        f"direct:{n}" for n in direct_trees()
    }
