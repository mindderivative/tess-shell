"""The suite never reaches the real desktop session (tests/conftest.py)."""

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_the_process_has_no_real_session_bus_and_private_directories() -> None:
    assert "DBUS_SESSION_BUS_ADDRESS" not in os.environ
    system = os.environ["DBUS_SYSTEM_BUS_ADDRESS"]
    assert system.startswith("unix:path=") and not Path(system.removeprefix("unix:path=")).exists()
    for name in ("XDG_RUNTIME_DIR", "XDG_STATE_HOME", "XDG_CONFIG_HOME"):
        assert Path(os.environ[name]).name in ("run", "state", "config")
        assert "tess-tests-" in os.environ[name]


def _bare_run(**extra: str) -> subprocess.CompletedProcess[str]:
    env = {k: v for k, v in os.environ.items() if k not in ("WAYLAND_DISPLAY", "DISPLAY")}
    env.update(extra)
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--collect-only", "-p", "no:cacheprovider",
         "tests/test_session_guard.py"],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
    )  # fmt: skip


def test_a_run_with_a_real_display_is_refused() -> None:
    for name in ("WAYLAND_DISPLAY", "DISPLAY"):
        done = _bare_run(**{name: "not-a-real-display"})
        assert done.returncode == 3, done.stdout + done.stderr
        assert "refusing to run" in done.stdout + done.stderr


def test_the_variable_lets_a_run_that_knows_what_it_does_through() -> None:
    done = _bare_run(WAYLAND_DISPLAY="not-a-real-display", TESS_SHELL_TESTS_REAL_SESSION="1")
    assert done.returncode == 0, done.stdout + done.stderr
