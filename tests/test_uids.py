"""The file UID write (Config Discovery and Registry > Identity and UIDs)."""

from __future__ import annotations

import os
import stat
from datetime import datetime
from pathlib import Path

import tess_dl

from tess_shell.config.paths import state_dir
from tess_shell.config.registry import Registry
from tess_shell.config.uids import assign_uids

TEXT = (
    "---\n"
    "TDL: 0.1   # the language\n"
    "Shell: 0.1\n"
    "Name: Main_Shell\n"
    "---\n"
    "\n"
    "Shell {  # no change here\r\n"
    "}\n"
)


def make(tmp_path: Path) -> tuple[Path, Path, Path]:
    config = tmp_path / "cfg"
    (config / "Shells").mkdir(parents=True)
    path = config / "Shells" / "Main_Shell.tdl"
    path.write_bytes(TEXT.encode())
    return config, path, tmp_path / "state" / "backups"


def test_one_line_is_added_after_the_version_lines_and_no_other_byte_changes(
    tmp_path: Path,
) -> None:
    config, path, backups = make(tmp_path)
    uids, findings = assign_uids([path], config, lambda key: "UID-1", backups)
    assert findings == [] and uids == {path: "UID-1"}
    after = path.read_bytes().decode()
    assert after.replace("UID: UID-1\n", "", 1) == TEXT
    assert after.index("UID: UID-1") > after.index("Shell: 0.1")
    document = tess_dl.parse(after).document
    assert document is not None and document.metadata["UID"].text == "UID-1"


def test_a_backup_is_made_first_outside_the_config_folder(tmp_path: Path) -> None:
    config, path, backups = make(tmp_path)
    assign_uids([path], config, lambda key: "u", backups, now=datetime(2026, 11, 4, 9, 30, 5))
    (copy,) = list(backups.rglob("*.20261104T093005"))
    assert copy.read_bytes() == TEXT.encode()
    assert config not in copy.parents
    assert copy.relative_to(backups) == Path("Shells/Main_Shell.tdl.20261104T093005")


def test_a_file_with_a_uid_is_left_alone_and_nothing_is_asked_of_the_registry(
    tmp_path: Path,
) -> None:
    config, path, backups = make(tmp_path)
    assign_uids([path], config, lambda key: "first", backups)
    written = path.read_bytes()

    def forbidden(key: str) -> str:
        raise AssertionError("the registry was asked for a file that has a UID")

    uids, findings = assign_uids([path], config, forbidden, backups)
    assert uids == {path: "first"} and findings == []
    assert path.read_bytes() == written
    assert len(list(backups.rglob("*"))) == 2  # one dir, one backup: the second run made none


def test_the_mode_of_the_file_is_kept(tmp_path: Path) -> None:
    config, path, backups = make(tmp_path)
    path.chmod(0o640)
    assign_uids([path], config, lambda key: "u", backups)
    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_an_unwritable_file_keeps_its_registry_uid_and_is_reported(tmp_path: Path) -> None:
    config, path, backups = make(tmp_path)
    config_dir = path.parent
    config_dir.chmod(0o500)  # the file cannot be replaced
    try:
        if os.access(config_dir, os.W_OK):  # running as root
            return
        uids, findings = assign_uids([path], config, lambda key: "kept", backups)
    finally:
        config_dir.chmod(0o700)
    assert uids == {path: "kept"}
    (f,) = findings
    assert f.severity == "warning" and f.rule == "uid-write"
    assert path.read_bytes() == TEXT.encode()


def test_the_registry_hands_out_one_uid_per_key_and_keeps_it(tmp_path: Path) -> None:
    registry = Registry.open(tmp_path / "registry.json")
    first = registry.uid_for("file:Shells/Main_Shell.tdl", "file")
    assert registry.uid_for("file:Shells/Main_Shell.tdl", "file") == first
    assert registry.uid_for("S.M.Top.Clock_1") != first
    registry.save()
    again = Registry.open(tmp_path / "registry.json")
    assert again.uid_for("file:Shells/Main_Shell.tdl") == first
    assert len(first) == 36 and first[14] == "7"  # a UUIDv7


def test_the_state_directory_follows_xdg_state_home(monkeypatch: object) -> None:
    assert state_dir({"XDG_STATE_HOME": "/x/state"}) == Path("/x/state/tesserae-shell")
    assert state_dir({"XDG_STATE_HOME": "relative"}) == Path.home() / ".local/state/tesserae-shell"
    assert state_dir({}) == Path.home() / ".local/state/tesserae-shell"
