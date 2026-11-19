"""A reload keeps nothing of the surfaces it closed (SHELL-REQ-001).

A real ``Reloader`` and ``SurfaceManager`` over a real (never run) ``tess_re.App``, in this
process (``tests/reload_rig.py``): a Bar and nine shown Panels, reloaded 30 times with the Panels
taken away and brought back at every second reload. The count of live ``Surface``, ``View`` and
node trees and the size of the Python heap (``tracemalloc``) are read after reload 6 and after
reload 30, both with the nine Panels shown.

Before the fix each cycle kept the nine closed Panels: tre's ``App`` never lets go of a window it
was given, and the window's listeners held the ``Surface``, the ``View`` and through them the
tree (about 5 MiB of Python heap and 13,000 objects per cycle, 9 ``Surface``s and 142 nodes more
live at every cycle). The bounds are far under one cycle's worth, above what Python's own caches
settle to.
"""

from __future__ import annotations

import gc
import tracemalloc
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

from tests.reload_rig import ReloadRig, count_objects, private_session, step

BASE, LAST = 6, 30  # reload 6 and 30 both have the nine Panels (the shape repeats every two)
TYPES = ("Surface", "View", "LiveTree", "LayerWindow")


@dataclass
class Reading:
    counts: dict[str, int]
    heap: int  # tracemalloc's traced bytes


def read() -> Reading:
    counts = count_objects(*TYPES)
    return Reading(counts, tracemalloc.get_traced_memory()[0])


def run(root: Path, *, panels: bool) -> tuple[Reading, Reading]:
    with private_session(root):
        rig = ReloadRig(root)
        tracemalloc.start()
        try:
            for index in range(1, BASE + 1):
                step(rig, index, panels=panels)
            before = read()
            for index in range(BASE + 1, LAST + 1):
                step(rig, index, panels=panels)
            return before, read()
        finally:
            tracemalloc.stop()
            gc.collect()


@pytest.fixture(scope="module")
def panels_closed_and_opened(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[tuple[Reading, Reading]]:
    yield run(tmp_path_factory.mktemp("leak-panels"), panels=True)


@pytest.fixture(scope="module")
def style_only(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[Reading, Reading]]:
    yield run(tmp_path_factory.mktemp("leak-style"), panels=False)


def test_the_panels_a_reload_closes_leave_no_surface_view_or_tree_behind(
    panels_closed_and_opened: tuple[Reading, Reading],
) -> None:
    before, after = panels_closed_and_opened
    for name in ("Surface", "View", "LiveTree"):
        # a leak keeps 9 per cycle, 108 over these 12; 9 is the slack of one stale set
        assert after.counts[name] - before.counts[name] <= 9, (name, before.counts, after.counts)


def test_the_python_heap_does_not_grow_with_the_panels_a_reload_closes(
    panels_closed_and_opened: tuple[Reading, Reading],
) -> None:
    before, after = panels_closed_and_opened
    grown = after.heap - before.heap
    # a leak keeps about 5 MiB per cycle (60 MiB here); tre's stub of each closed window is a few
    # hundred bytes of Python heap (108 windows)
    assert grown <= 512 * 1024, (
        f"{grown / 1024:.0f} KiB more Python heap after {LAST - BASE} reloads"
    )


@pytest.mark.xfail(
    strict=True,
    reason="tre's App keeps every window it was given, closed or not (candidate tre request): "
    "the Python object of each closed window stays, 9 per cycle",
)
def test_tre_lets_go_of_a_closed_window(
    panels_closed_and_opened: tuple[Reading, Reading],
) -> None:
    before, after = panels_closed_and_opened
    assert after.counts["LayerWindow"] - before.counts["LayerWindow"] <= 9


def test_a_reload_that_changes_only_a_style_opens_and_closes_no_window(
    style_only: tuple[Reading, Reading],
) -> None:
    before, after = style_only
    assert after.counts == before.counts == {name: before.counts[name] for name in TYPES}
    assert after.counts["LayerWindow"] == 10  # the Bar and the nine Panels, as at the start
    assert after.heap - before.heap <= 256 * 1024
