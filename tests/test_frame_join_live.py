"""Every way of drawing a melded Panel's join, on a private headless sway: the Frame slides the
Panel in and out for a second with it, and once it is still the painter draws no frame. The
measurement is ``tests/kwin/compare_join.py`` (one process per option)."""

from __future__ import annotations

import pytest

from tess_shell.surfaces.join import JOINS
from tests.kwin.compare_join import live_run
from tests.sway import PrivateSway

pytestmark = pytest.mark.tre


def test_every_join_animates_and_then_draws_nothing_at_idle(private_sway: PrivateSway) -> None:
    results = live_run(list(JOINS), private_sway.output_names()[0], 1.0, private_sway.env, 0.7)
    assert [r["join"] for r in results] == list(JOINS), "an option did not report"
    for r in results:
        assert r["frames"] >= 15, f"{r['join']}: the slide drew {r['frames']} frames"
        assert r["idle_frames"] == 0, f"{r['join']}: {r['idle_frames']} frames drawn at idle"
