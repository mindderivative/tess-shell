"""Budget regressions of the Popup (Performance Budgets B16): a closed Popup holds nothing, on
real headless tre windows (no compositor). "An open Popup draws no frames" cannot be measured
here: a headless window draws none and ``frame_stats`` records only after ``App.run()``."""

from __future__ import annotations

import statistics

from tests.perf.budget_inproc_ui import FRAME_MS, open_costs, popup_residue


def test_a_closed_popup_holds_no_thread_descriptor_node_or_object() -> None:
    """After 20 open/close cycles: no thread, file descriptor, Bar node, ``OpenPopup``,
    ``PopupWindow`` or live content tree is left, and the Python blocks left per cycle stay
    far under a leaked view (about 20 today; the guard is 100) (about 1 s)."""
    res = popup_residue(20)
    assert {k: v for k, v in res.items() if k != "blocks_per_cycle"} == {
        "threads": 0,
        "fds": 0,
        "bar_nodes": 0,
        "open_popups": 0,
        "popup_windows": 0,
        "live_trees": 0,
    }
    assert res["blocks_per_cycle"] < 100, res


def test_opening_a_popup_takes_the_loop_well_under_two_frames() -> None:
    """The loop-thread time of the open call, median of 20: under 3 times the vault's two
    frames (100 ms); about 0.3 ms today (about 1 s)."""
    opens, _closes = open_costs(20)
    assert statistics.median(opens) < 6 * FRAME_MS
