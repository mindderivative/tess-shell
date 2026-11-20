"""The launcher's idle cost (Applications Module > Performance Budget): with the list built and
nothing changing, no wake-ups. Counted as ``tests/test_tasks_idle.py`` counts: what the loop is
handed (``call_soon``), the time source, and, for the two threads the launcher owns (the
application service's worker and the inotify watcher of the folders), the kernel timeslices and the
voluntary context switches. A 3 second run is in the suite; the 60 seconds of the spec are marked
``perf`` (``pytest -m perf tests/test_launcher_idle.py``)."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path

import pytest

from tests.launcher_rig import launcher_desk, write_entry

pytestmark = pytest.mark.skipif(not Path("/proc/self/task").is_dir(), reason="needs /proc")


def counters(thread: threading.Thread) -> tuple[int, int]:
    task = Path(f"/proc/{os.getpid()}/task/{thread.native_id}")
    slices = int((task / "schedstat").read_text().split()[2])
    voluntary = 0
    for line in (task / "status").read_text().splitlines():
        if line.startswith("voluntary_ctxt_switches"):
            voluntary = int(line.split()[1])
    return slices, voluntary


def measure(tmp_path: Path, seconds: float) -> None:
    with launcher_desk(tmp_path, {"One": {"Exec": "fake-app"}, "Two": {"Exec": "fake-app"}}) as d:
        before_threads = set(threading.enumerate())
        d.apps.index.watch(debounce=0.05)  # the folder watch, as the shell runs it
        try:
            d.toggle()
            d.type("o")
            watcher = next(iter(set(threading.enumerate()) - before_threads))
            workers = [t for t in threading.enumerate() if t.name.startswith("apps")]
            assert workers and watcher.is_alive()
            wakes: list[int] = []
            d.w.host.ticks.start(lambda cb: wakes.append(1))  # the real time source
            try:
                d.settle(lambda: False, 0.3)  # everything the last keystroke started has ended
                queued = [0]
                real = d.loop.call_soon

                def counting(fn: object) -> None:
                    queued[0] += 1
                    real(fn)  # type: ignore[arg-type]

                d.apps._call_soon = counting
                watched = [watcher, *workers]
                before = [counters(t) for t in watched]
                time.sleep(seconds)
                after = [counters(t) for t in watched]
                assert after == before, (before, after)
                assert queued[0] == 0 and wakes == []  # no loop work, no timer
                # the control: a change of an entry file wakes the watcher, so the counters work
                write_entry(d.folder, "Three", Exec="fake-app")
                assert d.settle(lambda: len(d.apps.search("")) == 3)
                assert [counters(t) for t in watched] != before
            finally:
                d.w.host.ticks.close()
        finally:
            d.apps.index.unwatch()


def test_no_wakeups_in_3_s_with_the_list_built_the_panel_open_and_nothing_changing(
    tmp_path: Path,
) -> None:
    measure(tmp_path, 3.0)


@pytest.mark.perf
def test_no_wakeups_in_60_s(tmp_path: Path) -> None:
    measure(tmp_path, 60.0)
