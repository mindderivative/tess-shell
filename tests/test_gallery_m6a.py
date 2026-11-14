"""The M6a KWin kit (``tests/kwin/prepare_m6a_gallery.py``): its config checks clean and its
checklist is one numbered list in theme tokens only. ``check.sh`` is run against the config
(``run.sh`` starts the shell on the real desktop, so it is only read, never run)."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tests.kwin import prepare_m6a_gallery as g


def test_the_gallery_files_check_clean(tmp_path: Path) -> None:
    g.write_gallery(tmp_path)
    done = subprocess.run(
        [sys.executable, "-m", "tess_shell", "check", "--config-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        env={"XDG_STATE_HOME": str(tmp_path / "state"), "PATH": "/usr/bin:/bin"},
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "error" not in (done.stdout + done.stderr).replace("no error", "")


def test_the_checklist_numbers_every_line_in_one_list_and_the_body_uses_tokens_only() -> None:
    numbers = [
        int(line[:2])
        for line in g.CHECKLIST.splitlines()
        if line[:2].strip().isdigit() and line[2:3] == " "
    ]
    assert numbers == list(range(1, 8))
    assert '"#' not in g.BODY  # no hex colour: theme tokens only
    for word in ("light", "dark"):
        assert word in g.CHECKLIST


def test_the_scripts_are_written_and_run_the_shell_with_a_private_state_directory(
    tmp_path: Path, monkeypatch: object
) -> None:
    root = tmp_path / "kit"
    monkeypatch.setattr(g, "ROOT", root)  # type: ignore[attr-defined]
    monkeypatch.setattr(g, "CFG", root / "gallery")  # type: ignore[attr-defined]
    g.main()
    run = (root / "run.sh").read_text()
    assert f"XDG_STATE_HOME={root}/state" in run and "tesserae-shell run" in run
    assert (root / "checklist.txt").read_text() == g.CHECKLIST
    check = subprocess.run([str(root / "check.sh")], capture_output=True, text=True)
    assert "error" not in check.stdout.lower().replace("no error", "") or check.returncode == 0
