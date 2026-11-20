"""The hot reload budget (Performance Budgets: under 100 ms after the 200 ms debounce for a shell
of 10 surfaces, about 300 ms from the save to the change) and what a reload leaves behind.

A real shell with a Bar and nine shown Panels (10 surfaces) on a private headless sway. The file's
``Height`` is saved again and again; the reloader logs ``reloaded (Main_Shell.tdl) in N ms``.

* ``test_a_reload_of_ten_surfaces...`` checks N and the time from the save to the line against
  three times the vault's numbers (300 ms and 900 ms: a loaded machine is slower, a reload that
  rebuilds every surface or waits for a frame is far more). About 6 s.
* ``test_reloads_leave_no_thread_no_descriptor...`` (marked ``perf``, about 9 s) saves 12 more
  times, taking the nine Panels away and back at every third save, and compares the shell's
  thread count and open file descriptors with the third reload's (a watcher, a surface or a
  window left behind at every reload shows as growth) and its resident memory (growth under
  40 MiB: the allocator's noise is a few MiB, a leaked window or tree is tens).
"""

from __future__ import annotations

import os
import re
import time
from pathlib import Path

import pytest

from tests.fake_dbus import HAVE_DAEMON, FakeBus
from tests.perf.budget_rig import memory_kib, shell_text, surfaces_panels
from tests.sway import PrivateSway
from tests.test_run import Shell

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not HAVE_DAEMON, reason="dbus-daemon is not installed"),
]

RELOADED = re.compile(r"reloaded[^(]*\(([^)]*)\) in (\d+) ms")
BAR = 'Text { Text: "Tesserae", Font_Size: 14 }'


class Ten:
    """A running shell of 10 surfaces and the means to save its file and wait for the reload."""

    def __init__(self, sway: PrivateSway, tmp_path: Path) -> None:
        self.config = tmp_path / "cfg"
        (self.config / "Shells").mkdir(parents=True)
        self.file = self.config / "Shells" / "Main_Shell.tdl"
        self.panels = surfaces_panels(9)
        self.write(34, self.panels)
        self.bus = FakeBus()
        self.shell = Shell(self.config, {**sway.env, "DBUS_SESSION_BUS_ADDRESS": self.bus.address})
        self.shell.wait_for("running")
        deadline = time.monotonic() + 20
        while self.configured() < 10 and time.monotonic() < deadline:
            time.sleep(0.1)
            self.drain()
        assert self.configured() == 10, self.shell.stderr
        self.height = 34

    def write(self, height: int, panels: str) -> None:
        text = shell_text(BAR, panels=panels).replace("Height: 34,", f"Height: {height},")
        self.file.write_text(text)

    def drain(self) -> None:
        while not self.shell.lines.empty():
            self.shell.seen.append(self.shell.lines.get())

    def configured(self) -> int:
        self.drain()
        return sum("configured" in line for line in self.shell.seen)

    def reloads(self) -> list[re.Match[str]]:
        self.drain()
        return [m for line in self.shell.seen if (m := RELOADED.search(line))]

    def save(self, panels: str | None = None) -> tuple[float, float]:
        """Save a changed Height (and ``panels``), wait for the reload: the milliseconds the log
        gives and the seconds from the save to the line."""
        before = len(self.reloads())
        self.height = 36 if self.height == 34 else 34
        saved = time.monotonic()
        self.write(self.height, self.panels if panels is None else panels)
        deadline = time.monotonic() + 10
        while len(self.reloads()) <= before and time.monotonic() < deadline:
            time.sleep(0.005)
        found = self.reloads()
        assert len(found) > before, "no reload line:\n" + self.shell.stderr
        return float(found[before].group(2)), time.monotonic() - saved

    def stop(self) -> None:
        if self.shell.process.poll() is None:
            self.shell.process.terminate()
            self.shell.process.wait(timeout=15)
        self.bus.close()


def test_a_reload_of_ten_surfaces_applies_within_three_times_the_budget(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    ten = Ten(private_sway, tmp_path)
    try:
        applied, end_to_end = [], []
        for _ in range(4):
            ms, took = ten.save()
            applied.append(ms)
            end_to_end.append(took * 1000)
            time.sleep(0.3)
    finally:
        ten.stop()
    assert max(applied) <= 300, applied  # the vault: under 100 ms
    assert max(end_to_end) <= 900, end_to_end  # the vault: about 300 ms with the 200 ms debounce


def descriptors(pid: int) -> int:
    return len(os.listdir(f"/proc/{pid}/fd"))


def threads(pid: int) -> int:
    return len(os.listdir(f"/proc/{pid}/task"))


@pytest.mark.perf
def test_reloads_leave_no_thread_no_descriptor_and_little_memory_behind(
    private_sway: PrivateSway, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    ten = Ten(private_sway, tmp_path)
    pid = ten.shell.process.pid
    try:
        for _ in range(3):
            ten.save()
            time.sleep(0.3)
        base = (threads(pid), descriptors(pid), memory_kib(pid)[0])
        for index in range(12):
            ten.save(panels="" if index % 3 == 0 else None)
            time.sleep(0.3)
        after = (threads(pid), descriptors(pid), memory_kib(pid)[0])
    finally:
        ten.stop()
    with capsys.disabled():
        print(f"\nafter 12 reloads: threads, descriptors, RSS KiB {base} -> {after}")
    assert after[0] <= base[0] + 1, ("threads", base, after)
    assert after[1] <= base[1] + 3, ("descriptors", base, after)
    assert after[2] - base[2] <= 40 * 1024, ("rss KiB", base, after)
