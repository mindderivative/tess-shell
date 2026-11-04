import os
import stat
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tess_shell.config.lock import InstanceLock
from tess_shell.config.paths import check_runtime_dir
from tess_shell.exit_codes import AlreadyRunning, EnvironmentFailure, ExitCode


def test_lock_dir_mode_and_pid(tmp_path: Path) -> None:
    lock = InstanceLock()
    lock.acquire(tmp_path)
    try:
        d = tmp_path / "tesserae-shell"
        assert stat.S_IMODE(d.stat().st_mode) == 0o700
        assert (d / "lock").read_text().strip() == str(os.getpid())
        mode = (d / "lock").stat().st_mode
        # the sticky bit is requested; where the file system refuses it the lock reports that
        assert bool(mode & stat.S_ISVTX) != lock.sticky_refused
        assert stat.S_IMODE(mode) & 0o777 == 0o600
    finally:
        lock.release()


def test_second_holder_is_refused_with_first_pid_then_free_after_release(tmp_path: Path) -> None:
    code = textwrap.dedent(
        """
        import sys, os
        from pathlib import Path
        from tess_shell.config.lock import InstanceLock
        l = InstanceLock(); l.acquire(Path(sys.argv[1]))
        print(os.getpid(), flush=True)
        sys.stdin.readline()
        """
    )
    child = subprocess.Popen(
        [sys.executable, "-c", code, str(tmp_path)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
    )
    assert child.stdout and child.stdin
    pid = int(child.stdout.readline())
    second = InstanceLock()
    with pytest.raises(AlreadyRunning) as info:
        second.acquire(tmp_path)
    assert info.value.pid == pid
    assert info.value.exit_code == ExitCode.ALREADY_RUNNING
    assert f"(pid {pid})" in str(info.value)
    child.stdin.write("\n")
    child.stdin.flush()
    child.wait(timeout=10)
    second.acquire(tmp_path)
    second.release()


@pytest.mark.parametrize(
    ("env", "needle"),
    [
        ({}, "not set"),
        ({"XDG_RUNTIME_DIR": ""}, "not set"),
        ({"XDG_RUNTIME_DIR": "run/user"}, "absolute"),
        ({"XDG_RUNTIME_DIR": "/nonexistent/xdg"}, "cannot be used"),
    ],
)
def test_bad_runtime_dir(env: dict[str, str], needle: str) -> None:
    with pytest.raises(EnvironmentFailure, match=needle) as info:
        check_runtime_dir(env)
    assert "XDG_RUNTIME_DIR" in str(info.value)
    assert info.value.exit_code == 2


def test_runtime_dir_other_owner(tmp_path: Path) -> None:
    with pytest.raises(EnvironmentFailure, match="not owned"):
        check_runtime_dir({"XDG_RUNTIME_DIR": str(tmp_path)}, uid=os.getuid() + 1)


def test_runtime_dir_loose_mode_warns_only(tmp_path: Path) -> None:
    tmp_path.chmod(0o755)
    assert check_runtime_dir({"XDG_RUNTIME_DIR": str(tmp_path)}) == (tmp_path, True)
    tmp_path.chmod(0o700)
    assert check_runtime_dir({"XDG_RUNTIME_DIR": str(tmp_path)}) == (tmp_path, False)
