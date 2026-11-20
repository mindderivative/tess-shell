"""The file watcher notices a shell file an ``Import:`` names even where no folder is watched."""

from __future__ import annotations

import threading
from pathlib import Path

from tess_shell.watch import Watcher, by_directory

DEBOUNCE = 0.15


class Rig:
    def __init__(self, tmp_path: Path) -> None:
        (tmp_path / "Shells").mkdir()
        (tmp_path / "Parts").mkdir()
        self.calls: list[set[Path]] = []
        self.event = threading.Event()
        self.watcher = Watcher([tmp_path / "Shells"], self._changed, debounce=DEBOUNCE)
        self.watcher.start()

    def _changed(self, paths: set[Path]) -> None:
        self.calls.append(paths)
        self.event.set()

    def saw(self, timeout: float = 3.0) -> bool:
        seen = self.event.wait(timeout)
        self.event.clear()
        return seen


def test_an_imported_file_outside_the_trees_is_noticed_only_once_it_is_named(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path)
    try:
        top, other = tmp_path / "Parts" / "Top_Shell.tdl", tmp_path / "Parts" / "Other_Shell.tdl"
        top.write_text("x")
        assert not rig.saw(0.5)  # nobody imports it: not watched
        rig.watcher.watch_files(by_directory([top]))
        top.write_text("y")
        assert rig.saw() and rig.calls == [{top}]
        other.write_text("x")
        assert not rig.saw(0.5)  # a neighbour that nothing imports stays quiet
        # a later reload imports the neighbour too: both are noticed now
        rig.watcher.watch_files(by_directory([other]))
        other.write_text("y")
        assert rig.saw()
        top.write_text("z")
        assert rig.saw() and rig.calls[-1] == {top}
    finally:
        rig.watcher.stop()


def test_naming_a_file_in_a_watched_tree_does_not_narrow_what_the_tree_reports(
    tmp_path: Path,
) -> None:
    rig = Rig(tmp_path)
    try:
        named, neighbour = tmp_path / "Shells" / "A_Shell.tdl", tmp_path / "Shells" / "B_Shell.tdl"
        rig.watcher.watch_files(by_directory([named]))
        neighbour.write_text("x")
        assert rig.saw() and rig.calls == [{neighbour}]
    finally:
        rig.watcher.stop()
