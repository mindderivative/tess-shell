"""``tesserae-shell run`` as a process, against a private headless sway."""

from __future__ import annotations

import os
import queue
import signal
import subprocess
import sys
import threading
import time
from collections.abc import Iterator
from pathlib import Path

import pytest

from tests.sway import PrivateSway

pytestmark = pytest.mark.tre


class Shell:
    """A running ``tesserae-shell run`` with its stderr read by a thread."""

    def __init__(self, config: Path, env: dict[str, str], *extra: str) -> None:
        self.config = config
        self.process = subprocess.Popen(
            [sys.executable, "-m", "tess_shell", "run", "--config-dir", str(config), *extra],
            env=env,
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )
        self.lines: queue.Queue[str] = queue.Queue()
        self.seen: list[str] = []
        assert self.process.stderr is not None
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self.lines.put(line)

    def wait_for(self, text: str, timeout: float = 20) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if any(text in line for line in self.seen):
                return
            try:
                self.seen.append(self.lines.get(timeout=0.1))
            except queue.Empty:
                if self.process.poll() is not None and self.lines.empty():
                    break
        pytest.fail(f"never saw {text!r}; stderr so far:\n{''.join(self.seen)}")

    def finish(self, timeout: float = 10) -> int:
        code = self.process.wait(timeout=timeout)
        time.sleep(0.2)
        while not self.lines.empty():
            self.seen.append(self.lines.get())
        return code

    @property
    def stderr(self) -> str:
        return "".join(self.seen)

    def log_text(self) -> str:
        (log,) = sorted((self.config / "logs").glob("log_*.log"))
        return log.read_text()


@pytest.fixture
def shell_factory(private_sway: PrivateSway) -> Iterator[object]:
    started: list[Shell] = []

    def make(config: Path, env: dict[str, str] | None = None, *extra: str) -> Shell:
        shell = Shell(config, env or private_sway.env, *extra)
        started.append(shell)
        return shell

    yield make
    for shell in started:
        if shell.process.poll() is None:
            shell.process.kill()
            shell.process.wait()


def test_sigterm_stops_cleanly(shell_factory, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    cfg = tmp_path / "cfg"
    shell = shell_factory(cfg)
    shell.wait_for("running")
    shell.process.send_signal(signal.SIGTERM)
    assert shell.finish() == 0
    log = shell.log_text()
    positions = [log.index(word) for word in ("starting", "running", "stopping", "stopped")]
    assert positions == sorted(positions)
    assert (cfg / "registry.json").exists()


def test_sigint_stops_cleanly(shell_factory, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    shell = shell_factory(tmp_path / "cfg")
    shell.wait_for("running")
    shell.process.send_signal(signal.SIGINT)
    assert shell.finish() == 0
    assert "stopped" in shell.log_text()


def test_second_instance_exits_4_naming_the_first(  # type: ignore[no-untyped-def]
    shell_factory, private_sway: PrivateSway, tmp_path: Path
) -> None:
    first = shell_factory(tmp_path / "one")
    first.wait_for("running")
    second = shell_factory(tmp_path / "two")
    assert second.finish() == 4
    assert f"(pid {first.process.pid})" in second.stderr
    first.process.send_signal(signal.SIGTERM)
    assert first.finish() == 0


def test_two_signals_end_the_process(shell_factory, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    shell = shell_factory(tmp_path / "cfg")
    shell.wait_for("running")
    shell.process.send_signal(signal.SIGTERM)
    shell.process.send_signal(signal.SIGTERM)
    assert shell.finish() in (0, 130)


def test_signal_right_after_starting_still_stops(shell_factory, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    shell = shell_factory(tmp_path / "cfg")
    shell.wait_for("starting")
    time.sleep(0.05)  # in practice this lands before or while the loop starts
    shell.process.send_signal(signal.SIGTERM)
    code = shell.finish()
    assert code in (0, 130)
    if code == 0:
        assert "stopped" in shell.log_text()


def test_invalid_settings_exit_1_with_position(shell_factory, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    cfg = tmp_path / "cfg"
    cfg.mkdir()
    (cfg / "settings.tdl").write_text("---\nTDL: 0.1\nName: Settings\n---\nSettings {\n")
    shell = shell_factory(cfg)
    assert shell.finish() == 1
    assert "settings.tdl:5:" in shell.stderr
    assert list((cfg / "logs").glob("log_*.log"))


def test_unset_runtime_dir_exit_2(private_sway: PrivateSway, tmp_path: Path) -> None:
    env = {k: v for k, v in private_sway.env.items() if k != "XDG_RUNTIME_DIR"}
    done = subprocess.run(
        [sys.executable, "-m", "tess_shell", "run", "--config-dir", str(tmp_path / "c")],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert done.returncode == 2
    assert "XDG_RUNTIME_DIR" in done.stderr


def test_no_compositor_exit_2(tmp_path: Path) -> None:
    runtime = tmp_path / "rt"
    runtime.mkdir(mode=0o700)
    env = {k: v for k, v in os.environ.items() if k not in ("WAYLAND_DISPLAY", "DISPLAY")}
    env["XDG_RUNTIME_DIR"] = str(runtime)
    done = subprocess.run(
        [sys.executable, "-m", "tess_shell", "run", "--config-dir", str(tmp_path / "c")],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert done.returncode == 2
    assert "layer-shell" in done.stderr


def test_bad_shell_file_stops_run_with_exit_1(shell_factory, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    cfg = tmp_path / "cfg"
    (cfg / "Shells").mkdir(parents=True)
    (cfg / "Shells" / "Bad_Shell.tdl").write_text("---\nTDL: 0.1\nName: B\n---\nShell {\n")
    shell = shell_factory(cfg)
    assert shell.finish() == 1
    assert "Shells/Bad_Shell.tdl:5:7" in shell.stderr
