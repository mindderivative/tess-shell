"""The single instance lock: ``$XDG_RUNTIME_DIR/tesserae-shell/lock`` (Shell Start and Stop)."""

from __future__ import annotations

import fcntl
import os
import stat
import time
from pathlib import Path

from tess_shell.exit_codes import AlreadyRunning


class InstanceLock:
    def __init__(self) -> None:
        self.fd: int | None = None
        self.sticky_refused = False

    def acquire(self, runtime_dir: Path) -> None:
        directory = runtime_dir / "tesserae-shell"
        directory.mkdir(mode=0o700, exist_ok=True)
        path = directory / "lock"
        fd = os.open(path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            # Sticky bit: systemd-tmpfiles-style cleaners leave the file alone. The kernel may
            # refuse it on some file systems; that is reported, not fatal.
            try:
                os.chmod(path, 0o1600)
            except OSError:
                pass
            self.sticky_refused = not (os.fstat(fd).st_mode & stat.S_ISVTX)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise AlreadyRunning(_read_pid(fd)) from None
            os.ftruncate(fd, 0)
            os.write(fd, f"{os.getpid()}\n".encode())
        except BaseException:
            os.close(fd)
            raise
        self.fd = fd

    def release(self) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


def _read_pid(fd: int) -> int | None:
    for _ in range(5):
        text = os.pread(fd, 32, 0).decode(errors="replace").strip()
        if text.isdigit():
            return int(text)
        time.sleep(0.05)
    return None
