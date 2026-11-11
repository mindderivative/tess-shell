"""The M4c gallery (``tests/kwin/prepare_m4c_gallery.py``): its files check clean and the shell
starts it on a private sway with no error and no warning."""

from __future__ import annotations

import signal
import subprocess
import sys
from pathlib import Path

import pytest

from tests.kwin.prepare_m4c_gallery import write_gallery
from tests.sway import PrivateSway
from tests.test_run import Shell


def test_the_gallery_files_check_clean(tmp_path: Path) -> None:
    write_gallery(tmp_path)
    done = subprocess.run(
        [sys.executable, "-m", "tess_shell", "check", "--config-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        env={"XDG_STATE_HOME": str(tmp_path / "state"), "PATH": "/usr/bin:/bin"},
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "error" not in (done.stdout + done.stderr).replace("no error", "")


@pytest.mark.tre
def test_the_gallery_starts_on_a_private_sway(private_sway: PrivateSway, tmp_path: Path) -> None:
    write_gallery(tmp_path)
    shell = Shell(tmp_path, private_sway.env)
    try:
        shell.wait_for("Panel Controls on HEADLESS-1 configured")
        shell.wait_for("Panel Lists on HEADLESS-1 configured")
        shell.wait_for("running")
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
    bad = [line for line in shell.seen if "| ERROR " in line or "| WARNING " in line]
    assert [x for x in bad if "the session bus is not reachable" not in x] == []
