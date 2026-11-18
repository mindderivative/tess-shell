import json
import os
import stat
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path

import pytest

from tess_shell.config import registry as registry_module
from tess_shell.config.registry import Registry, RegistryError


def test_missing_file_is_created(tmp_path: Path) -> None:
    reg = Registry.open(tmp_path / "registry.json")
    assert json.loads((tmp_path / "registry.json").read_text()) == {"registry": 1, "entries": {}}
    assert stat.S_IMODE((tmp_path / "registry.json").stat().st_mode) == 0o600
    assert reg.data["entries"] == {}


def test_a_registry_from_a_newer_shell_is_refused_and_left_untouched(tmp_path: Path) -> None:
    """A downgrade must not throw a newer shell's registry away."""
    path = tmp_path / "registry.json"
    text = '{"registry": 2, "entries": {}}'
    path.write_text(text)
    with pytest.raises(RegistryError) as info:
        Registry.open(path)
    assert info.value.finding.rule == "registry-too-new"
    assert path.read_text() == text


@pytest.mark.parametrize(
    "text",
    [
        '{"registry": 1,\n "entries": }',
        "[]",
        '{"registry": "1", "entries": {}}',
        '{"registry": 1, "entries": []}',
        "\xff\xfe not text",
    ],
)
def test_a_corrupt_registry_is_moved_aside_whole_and_rebuilt(tmp_path: Path, text: str) -> None:
    """Crash Recovery and Watchdog, failure modes: the registry is rebuilt from the UIDs in the
    files (the shell does that by reading each file's UID), the saved positions are lost, and the
    unreadable file is kept next to it, never overwritten."""
    path = tmp_path / "registry.json"
    path.write_bytes(text.encode("latin-1"))
    reg = Registry.open(path)
    assert reg.recovered is not None and "registry.json.corrupt-" in reg.recovered
    assert reg.data == {"registry": 1, "entries": {}}
    assert json.loads(path.read_text()) == {"registry": 1, "entries": {}}  # a usable file again
    (kept,) = [p for p in tmp_path.iterdir() if ".corrupt-" in p.name]
    assert kept.read_bytes() == text.encode("latin-1")


def test_a_leftover_temporary_file_of_a_killed_write_is_removed(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    Registry.open(path).save()
    stray = tmp_path / ".registry.json.abc123"
    stray.write_text("half a regis")
    Registry.open(path)
    assert not stray.exists()


def test_save_keeps_old_file_whole_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reg = Registry.open(tmp_path / "registry.json")
    before = (tmp_path / "registry.json").read_text()
    reg.data["entries"]["x"] = {"a": 1}

    def boom(*_: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="disk full"):
        reg.save()
    assert (tmp_path / "registry.json").read_text() == before
    assert [p.name for p in tmp_path.iterdir()] == ["registry.json"]


def test_save_roundtrip_and_preserves_mode(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    reg = Registry.open(path)
    path.chmod(0o640)
    reg.data["entries"]["x"] = {"a": 1}
    reg.save()
    assert Registry.open(path).data["entries"] == {"x": {"a": 1}}
    assert stat.S_IMODE(path.stat().st_mode) == 0o640


# -- written within a second of any change, off the loop (Crash Recovery and Watchdog) -----------

MOVER = """
import sys, time
from pathlib import Path
from tess_shell.config.registry import Registry

registry = Registry.open(Path(sys.argv[1]))
registry.set_position("Main.Dock", {"left": 40.0, "top": 12.0})
print("moved", flush=True)
time.sleep(120)
"""


def wait_until(predicate: Callable[[], bool], timeout: float) -> float | None:
    """Seconds until ``predicate`` was true, or ``None`` when it never was in ``timeout``."""
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        if predicate():
            return time.monotonic() - started
        time.sleep(0.01)
    return None


def test_a_moved_panels_position_is_on_disk_within_a_second_and_survives_sigkill(
    tmp_path: Path,
) -> None:
    path = tmp_path / "registry.json"
    mover = subprocess.Popen(
        [sys.executable, "-c", MOVER, str(path)], stdout=subprocess.PIPE, text=True
    )
    try:
        assert mover.stdout is not None and mover.stdout.readline().strip() == "moved"
        took = wait_until(
            lambda: "position" in json.dumps(json.loads(path.read_text())["entries"]), 1.0
        )
        assert took is not None, "the position was not in registry.json within 1 s of the move"
    finally:
        mover.kill()  # SIGKILL: nothing at stop runs
        mover.wait()
    assert Registry.open(path).position("Main.Dock") == {"left": 40.0, "top": 12.0}


def test_a_new_uid_is_on_disk_without_waiting_for_the_stop(tmp_path: Path) -> None:
    path = tmp_path / "registry.json"
    reg = Registry.open(path)
    uid = reg.uid_for("module:Clock", "module")
    assert wait_until(lambda: "module:Clock" in path.read_text(), 1.0) is not None
    assert Registry.open(path).uid_for("module:Clock", "module") == uid


def test_many_changes_make_a_few_writes_not_one_each(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reg = Registry.open(tmp_path / "registry.json")
    writes: list[int] = []
    real = os.replace

    def counting(src: object, dst: object) -> None:
        writes.append(1)
        real(src, dst)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "replace", counting)
    for n in range(30):
        reg.uid_for(f"use:{n}")
    assert wait_until(lambda: "use:29" in (tmp_path / "registry.json").read_text(), 2.0) is not None
    assert 1 <= len(writes) <= 3


def test_a_write_that_fails_keeps_the_old_file_and_is_tried_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "registry.json"
    reg = Registry.open(path)
    before = path.read_text()
    monkeypatch.setattr(registry_module, "DEBOUNCE", 3600.0)  # the timer never runs by itself
    reg.uid_for("use:a")
    calls = {"n": 0}
    real = os.replace

    def flaky(src: object, dst: object) -> None:
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("disk full")
        real(src, dst)  # type: ignore[arg-type]

    monkeypatch.setattr(os, "replace", flaky)
    reg._flush()  # the timer's job, run now: it fails
    assert path.read_text() == before
    assert [p.name for p in tmp_path.iterdir()] == ["registry.json"]  # no temporary file left
    reg._flush()  # the failed write left the registry marked unsaved: the next write has it
    assert "use:a" in path.read_text()
    reg.save()  # cancels the pending timer
