"""Budget regression of the binder (Performance Budgets B18): the number of tre calls it makes,
which does not depend on time. A tree of 3,101 nodes is built with one ``Window.build`` call; a
call per node would be a regression 100 times over."""

from __future__ import annotations

from tests.perf.budget_inproc_ui import big_tree, count_nodes, example_tree, tre_calls


def test_a_tree_of_3101_nodes_is_bound_with_one_build_and_a_handful_of_calls() -> None:
    """Today: Window.build x1, Node.add_child x1 and Node.children x32 (one per row, when the
    entries are indexed). The bound is 40 calls (about 1 s)."""
    tree = big_tree()
    assert count_nodes(tree) == 3101
    calls = tre_calls(tree)
    assert calls["Window.build"] == 1
    assert calls["Node.add_child"] == 1
    assert sum(calls.values()) <= 40, calls


def test_the_example_is_bound_with_one_build_and_an_attach() -> None:
    calls = tre_calls(example_tree())
    assert calls["Window.build"] == 1 and calls["Node.add_child"] == 1
    assert sum(calls.values()) <= 6, calls
