"""Budget regression of the binder (Performance Budgets B18): the number of tre calls it makes,
which does not depend on time. A tree of 3,101 nodes is built with one ``Window.build`` call; a
call per node would be a regression 100 times over."""

from __future__ import annotations

import statistics
import time

from tess_re import Window

from tess_shell.binder.build import build
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


def test_the_big_tree_is_bound_in_a_third_of_the_old_time_at_most() -> None:
    """B18 asks 20 ms for the 3,101-node tree. This bound is three times that (a loaded CI machine
    must not flake) and still catches a binder that goes back to a Python object per node: the
    median of 15 binds, headless window, build + attach + dispose. About 0.3 s."""
    tree = big_tree()
    window_size = (1000, 400)
    samples: list[float] = []
    for _ in range(15):
        window = Window(*window_size)
        started = time.perf_counter()
        build(tree, window).dispose()  # type: ignore[arg-type]
        samples.append((time.perf_counter() - started) * 1000)
    assert statistics.median(samples) < 60.0, samples


def test_a_tree_of_plain_blocks_gets_no_wire_and_no_control() -> None:
    """A block that listens for nothing, has no name and no state style needs no ``Wire`` (the
    object that holds its pointer state): 3,069 of the 3,101 nodes. A wire per node was most of
    the cost of the old bind."""
    view = build(big_tree(), Window(1000, 400))  # type: ignore[arg-type]
    try:
        flat = view._flat()
        assert len(flat) == 3101
        assert all(entry.wire is None for entry in flat)
        assert not view.controls and not view.runners
    finally:
        view.dispose()
