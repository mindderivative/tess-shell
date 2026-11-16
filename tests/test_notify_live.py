"""A real shell on a private headless sway tells systemd (Shell Start and Stop, Telling Systemd):
``READY=1`` once it runs, ``STOPPING=1`` when it begins to stop, and nothing without
``NOTIFY_SOCKET``. The socket is a datagram socket of the test, never a real ``$NOTIFY_SOCKET``."""

from __future__ import annotations

import shutil
import signal
import socket
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.sway import PrivateSway
from tests.test_run import Shell

pytestmark = pytest.mark.tre


@pytest.fixture
def notify_socket() -> Iterator[tuple[socket.socket, str]]:
    """A bound datagram socket on a short path (a unix socket path is at most 107 bytes)."""
    folder = Path(tempfile.mkdtemp(prefix="ns-", dir="/tmp"))
    path = str(folder / "notify")
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    sock.bind(path)
    sock.settimeout(30)
    try:
        yield sock, path
    finally:
        sock.close()
        shutil.rmtree(folder, ignore_errors=True)


def drain(sock: socket.socket) -> list[bytes]:
    """What is queued now, without waiting."""
    sock.settimeout(0.3)
    got: list[bytes] = []
    try:
        while True:
            got.append(sock.recv(256))
    except TimeoutError:
        return got


def test_ready_comes_once_the_shell_runs_and_stopping_when_it_begins_to_stop(
    private_sway: PrivateSway, notify_socket: tuple[socket.socket, str], tmp_path: Path
) -> None:
    sock, path = notify_socket
    shell = Shell(tmp_path / "cfg", {**private_sway.env, "NOTIFY_SOCKET": path})
    try:
        assert sock.recv(256) == b"READY=1"
        shell.wait_for("running")
        assert drain(sock) == []  # READY=1 once, and nothing else while it runs
        shell.process.send_signal(signal.SIGTERM)
        sock.settimeout(30)
        assert sock.recv(256) == b"STOPPING=1"
        assert shell.finish() == 0
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
            shell.process.wait()
    assert drain(sock) == []


def test_a_shell_with_no_notify_socket_sends_nothing_and_runs(
    private_sway: PrivateSway, notify_socket: tuple[socket.socket, str], tmp_path: Path
) -> None:
    """The socket exists but the environment does not name it: the shell must not find it."""
    sock, _ = notify_socket
    env = {k: v for k, v in private_sway.env.items() if k != "NOTIFY_SOCKET"}
    shell = Shell(tmp_path / "cfg", env)
    try:
        shell.wait_for("running")
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
            shell.process.wait()
    assert drain(sock) == []
