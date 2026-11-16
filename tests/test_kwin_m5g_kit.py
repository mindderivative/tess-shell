"""The M5g KWin kit (``tests/kwin/prepare_m5g_kwin.py``): it writes only under its own folder,
starts nothing, and its configs check clean."""

from __future__ import annotations

import runpy
from pathlib import Path

import pytest

from tess_shell.app import check
from tess_shell.options import Options

KIT = Path(__file__).parent / "kwin" / "prepare_m5g_kwin.py"


def test_the_kit_writes_its_files_and_its_configs_check_clean(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    module = runpy.run_path(str(KIT), run_name="kit")
    root = tmp_path / "kit"
    module["main"].__globals__["ROOT"] = root
    module["main"]()
    assert (root / "checklist.txt").is_file() and (root / "introspect.sh").is_file()
    assert "busctl --user introspect" in (root / "introspect.sh").read_text()
    for name in ("cfg", "cfg-off"):
        assert check(Options(config_dir=root / name)) == 0


def test_running_the_generator_again_keeps_the_backup_the_maintainer_made(tmp_path: Path) -> None:
    """``backup.sh`` copies the real ``kwinrc`` and ``kwinrulesrc`` into the kit's folder before the
    check; the generator once removed the whole folder, and with it the way to undo the check."""
    module = runpy.run_path(str(KIT), run_name="kit")
    root = tmp_path / "kit"
    module["main"].__globals__["ROOT"] = root
    module["main"]()
    (root / "backup").mkdir()
    (root / "backup" / "kwinrulesrc").write_text("[General]\ncount=1\n")
    (root / "cfg" / "stale.txt").write_text("left by an earlier run")
    module["main"]()
    assert (root / "backup" / "kwinrulesrc").read_text() == "[General]\ncount=1\n"
    assert not (root / "cfg" / "stale.txt").exists()  # the rest is made again
