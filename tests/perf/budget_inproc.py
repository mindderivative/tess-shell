"""The in-process budget measures (M7c): everything that can be measured without a separate shell
process. ``measure(quick)`` runs every ``measure_bNN`` below in order and returns the readings;
a function that raises does not stop the others (it becomes a NOT MEASURED reading naming the
exception). Run on a quiet machine for ``quick=False``; ``quick=True`` is a smoke.

Safety: private ``dbus-daemon`` buses, headless tre windows, a temp directory; run with
``env -u WAYLAND_DISPLAY -u DISPLAY``. Nothing here touches the real session.
"""

from __future__ import annotations

import sys
import traceback
from collections.abc import Callable

from loguru import logger
from tests.perf import budget_inproc_dbus as dbus
from tests.perf import budget_inproc_mod as mod
from tests.perf import budget_inproc_ui as ui
from tests.perf.budget_report import Reading

# seconds, measured on a loaded machine (quick 11 s, full 198 s): the whole module
ESTIMATE_QUICK_S = 15
ESTIMATE_FULL_S = 240

STEPS: tuple[tuple[str, Callable[[bool], list[Reading]]], ...] = (
    ("B13", dbus.measure_b13),
    ("B14", dbus.measure_b14),
    ("B15", dbus.measure_b15),
    ("B16", ui.measure_b16),
    ("B16", ui.measure_b16_closed),
    ("B18", ui.measure_b18),
    ("B19", ui.measure_b19),
    ("B20", mod.measure_b20),
    ("B11", ui.measure_b11),
    ("B22", mod.measure_b22),
    ("B09", mod.measure_b09),
    ("B12", mod.measure_b12),
    ("B24", mod.measure_b24),
)


def measure(quick: bool) -> list[Reading]:
    logger.remove()
    logger.add(sys.stderr, level="WARNING")
    readings: list[Reading] = []
    for budget, step in STEPS:
        try:
            readings.extend(step(quick))
        except Exception as exc:
            traceback.print_exc()
            readings.append(
                Reading.not_measured(
                    budget, step.__name__, f"the measure raised {type(exc).__name__}: {exc}"
                )
            )
    return readings
