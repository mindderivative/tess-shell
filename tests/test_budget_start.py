"""The start and stop budgets, read from the steps of the log (Performance Budgets: the first
surface within 1.0 s of the process start, ready within 2.0 s; Shell Start and Stop: a stop is
bounded, 10 s in total).

A real shell with one Bar on a private headless sway and a private session bus. Its log says when
each step of the start sequence ended (``starting``, ``loaded``, ``step 10``, ``step 11``,
``step 12``, ``running``) and the compositor's answer for each surface (``configured``). A step that
starts to wait on something (a socket, a portal, a file) shows as a gap between two lines, which
no fast machine hides. The limits are three times the vault's numbers (a loaded CI machine is
slower than the maintainer's idle one; a sleep or a blocking read is seconds): the first surface
3.0 s, running 6.0 s, no step more than 1.0 s, a stop 5.0 s. The test takes under a second;
the harness (``python -m tests.perf.read_budgets``) reads the same numbers with the limits at the
vault's values.
"""

from __future__ import annotations

import datetime
import re
import time
from pathlib import Path

import pytest

from tests.fake_dbus import HAVE_DAEMON, FakeBus
from tests.shell_samples import write_example
from tests.sway import PrivateSway
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed"),
]

STEPS = (
    "starting tesserae-shell",
    "loaded ",
    "step 10 (model)",
    "step 11 (surfaces)",
    "step 12 (modules)",
    "running",
)
STAMP = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d{3})")


def stamp(line: str) -> float:
    match = STAMP.match(line)
    assert match, line
    return datetime.datetime.fromisoformat(match.group(1)).timestamp()


def first(lines: list[str], text: str) -> float:
    for line in lines:
        if text in line and STAMP.match(line):
            return stamp(line)
    raise AssertionError(f"no line with {text!r}:\n" + "".join(lines))


def test_the_steps_of_the_start_come_in_order_and_none_waits(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    config = tmp_path / "cfg"
    write_example(config)
    bus = FakeBus()
    spawned = time.time()
    shell = Shell(config, {**private_sway.env, "DBUS_SESSION_BUS_ADDRESS": bus.address})
    try:
        shell.wait_for("running")
        shell.wait_for("configured")
        stopping = time.monotonic()
        shell.process.terminate()
        code = shell.finish(timeout=15)
        stop_took = time.monotonic() - stopping
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
        bus.close()
    assert code == 0
    lines = shell.stderr.splitlines(keepends=True)
    when = [first(lines, text) for text in STEPS]
    assert when == sorted(when), dict(zip(STEPS, when, strict=True))
    gaps = {text: b - a for text, a, b in zip(STEPS[1:], when, when[1:], strict=False)}
    assert max(gaps.values()) <= 1.0, gaps
    assert first(lines, "configured") - spawned <= 3.0, "the first surface"
    assert when[-1] - spawned <= 6.0, "running"
    assert stop_took <= 5.0, stop_took
