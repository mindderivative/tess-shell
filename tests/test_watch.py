"""The file watcher: one callback per burst, atomic saves, ignored names, own writes."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from tess_shell.watch import OwnWrites, Watcher, ignored

DEBOUNCE = 0.15


class Rig:
    def __init__(self, root: Path, **kw: object) -> None:
        self.root = root
        self.calls: list[set[Path]] = []
        self.event = threading.Event()
        self.watcher = Watcher([root], self._changed, debounce=DEBOUNCE, **kw)  # type: ignore[arg-type]
        self.watcher.start()

    def _changed(self, paths: set[Path]) -> None:
        self.calls.append(paths)
        self.event.set()

    def wait(self, timeout: float = 3.0) -> bool:
        ok = self.event.wait(timeout)
        self.event.clear()
        return ok

    def quiet(self, seconds: float = 0.5) -> bool:
        return not self.event.wait(seconds)


@pytest.fixture
def rig(tmp_path: Path) -> Iterator[Rig]:
    (tmp_path / "Shells").mkdir()
    r = Rig(tmp_path)
    yield r
    r.watcher.stop()


def test_a_plain_write_is_one_callback_with_the_path(rig: Rig) -> None:
    target = rig.root / "Shells" / "A_Shell.tdl"
    target.write_text("x")
    assert rig.wait()
    assert rig.calls == [{target}]


def test_a_burst_of_writes_is_one_callback(rig: Rig) -> None:
    target = rig.root / "Shells" / "A_Shell.tdl"
    for i in range(10):
        target.write_text(str(i))
        time.sleep(0.01)
    assert rig.wait() and rig.quiet()
    assert len(rig.calls) == 1


def test_an_atomic_save_is_one_callback_for_the_real_name(rig: Rig) -> None:
    target = rig.root / "Shells" / "A_Shell.tdl"
    target.write_text("old")
    assert rig.wait()
    rig.calls.clear()
    tmp = rig.root / "Shells" / ".A_Shell.tdl.swp"
    tmp.write_text("new")
    os.replace(tmp, target)  # an editor's save: write a temporary file, rename it over the target
    assert rig.wait() and rig.quiet()
    assert rig.calls == [{target}]


def test_the_callback_waits_for_quiet(rig: Rig) -> None:
    target = rig.root / "Shells" / "A_Shell.tdl"
    target.write_text("1")
    time.sleep(DEBOUNCE * 0.6)
    assert not rig.event.is_set()  # still inside the debounce window
    assert rig.wait()


@pytest.mark.parametrize("name", [".hidden", "x~", "y.swp", "z.tmp", "w.bak"])
def test_editor_leftovers_and_hidden_files_are_ignored(rig: Rig, name: str) -> None:
    (rig.root / "Shells" / name).write_text("x")
    assert rig.quiet(0.5)
    assert ignored(name)


def test_a_deleted_file_is_reported(rig: Rig) -> None:
    target = rig.root / "Shells" / "A_Shell.tdl"
    target.write_text("x")
    rig.wait()
    rig.calls.clear()
    target.unlink()
    assert rig.wait() and rig.calls == [{target}]


def test_a_folder_created_later_is_watched(rig: Rig) -> None:
    folder = rig.root / "Modules" / "New"
    folder.mkdir(parents=True)
    rig.wait(0.5)  # the folder itself
    rig.calls.clear()
    time.sleep(0.2)
    (folder / "New_Module.tdl").write_text("x")
    assert rig.wait() and (folder / "New_Module.tdl") in rig.calls[0]


def test_logs_schemas_and_backups_are_not_watched(tmp_path: Path) -> None:
    for name in ("logs", "schemas", "backups", "Shells"):
        (tmp_path / name).mkdir()
    r = Rig(tmp_path)
    try:
        (tmp_path / "logs" / "log_2026-11-04.log").write_text("x")
        (tmp_path / "schemas" / "s.json").write_text("x")
        assert r.quiet(0.5)
        (tmp_path / "Shells" / "A_Shell.tdl").write_text("x")
        assert r.wait()
    finally:
        r.watcher.stop()


def test_only_the_named_files_of_a_directory_count(tmp_path: Path) -> None:
    calls: list[set[Path]] = []
    event = threading.Event()

    def got(paths: set[Path]) -> None:
        calls.append(paths)
        event.set()

    w = Watcher([], got, files={tmp_path: frozenset({"settings.tdl"})}, debounce=DEBOUNCE)
    w.start()
    try:
        (tmp_path / "registry.json").write_text("{}")
        assert not event.wait(0.5)
        (tmp_path / "settings.tdl").write_text("x")
        assert event.wait(3) and calls == [{tmp_path / "settings.tdl"}]
    finally:
        w.stop()


def test_a_write_the_shell_made_itself_is_dropped_and_anyone_elses_passes(tmp_path: Path) -> None:
    (tmp_path / "Shells").mkdir()
    own = OwnWrites()
    r = Rig(tmp_path, is_own=own.is_own)
    try:
        target = tmp_path / "Shells" / "A_Shell.tdl"
        content = b"UID: abc\n"
        target.write_bytes(content)
        own.wrote(target, content)
        assert r.quiet(0.6) and r.calls == []
        target.write_bytes(b"someone else\n")
        assert r.wait() and r.calls == [{target}]
    finally:
        r.watcher.stop()


def test_an_own_write_record_is_used_once_and_expires(tmp_path: Path) -> None:
    own = OwnWrites(ttl=0.3)
    target = tmp_path / "f.tdl"
    target.write_bytes(b"same")
    own.wrote(target, b"same")
    assert own.is_own(target) is True
    assert own.is_own(target) is False  # a later save with the same content is a change
    own.wrote(target, b"same")
    time.sleep(0.4)
    assert own.is_own(target) is False  # too old to be the write that caused this event
    own.wrote(target, b"same")
    own.clear()
    assert own.is_own(target) is False


def test_stop_ends_the_thread_and_an_idle_watcher_makes_no_callback(tmp_path: Path) -> None:
    r = Rig(tmp_path)
    assert r.quiet(0.4) and r.calls == []
    r.watcher.stop()
    assert not r.watcher._thread.is_alive()


def test_a_directory_that_cannot_be_watched_turns_ok_off_and_keeps_running(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from inotify_simple import INotify

    def refuse(self: INotify, path: str, mask: int) -> int:
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(INotify, "add_watch", refuse)
    w = Watcher([tmp_path], lambda _: None)
    w.start()
    try:
        assert w.ok is False
    finally:
        w.stop()
