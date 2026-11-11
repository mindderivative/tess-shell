"""The M4a gallery on a private headless sway: the files check clean, the shell starts, opens the
Gallery Panel and stops with no error or warning in the log. The private sway has no pointer, so
the states are the headless ``tests/test_gallery.py`` and the maintainer's KWin checklist."""

from __future__ import annotations

import signal
import subprocess
import sys
from pathlib import Path

import pytest

from tests.kwin.prepare_m4a_gallery import write_gallery
from tests.sway import PrivateSway
from tests.test_run import Shell

pytestmark = pytest.mark.tre


def test_the_gallery_files_check_clean(tmp_path: Path) -> None:
    write_gallery(tmp_path)
    done = subprocess.run(
        [sys.executable, "-m", "tess_shell", "check", "--config-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        env={"XDG_STATE_HOME": str(tmp_path / "state"), "PATH": "/usr/bin:/bin"},
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "ok" in done.stdout and "error" not in done.stdout + done.stderr


def test_the_gallery_starts_clean_on_a_private_sway(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    write_gallery(tmp_path)
    shell = Shell(tmp_path, private_sway.env)
    try:
        shell.wait_for("Panel Gallery on HEADLESS-1 configured")
        shell.wait_for("running")
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
    bad = [line for line in shell.seen if "| ERROR " in line or "| WARNING " in line]
    # the private sway has no session bus: that one portal warning is the environment's
    bad = [line for line in bad if "the session bus is not reachable" not in line]
    assert bad == []
    assert "step 10 (model)" in shell.stderr
