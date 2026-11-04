"""A private headless sway for tests that need a Wayland compositor with layer-shell.

It has its own temporary ``XDG_RUNTIME_DIR``, so its socket and the shell's instance lock never
touch the real session. Recipe from tre's ``tools/sway_live.sh``.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path


class SwayUnavailable(RuntimeError):
    pass


class PrivateSway:
    def __init__(self) -> None:
        self.runtime = Path(tempfile.mkdtemp(prefix="tsw-"))
        self.process: subprocess.Popen[bytes] | None = None
        self.display = ""

    @property
    def env(self) -> dict[str, str]:
        """An environment for a child process that should use this compositor."""
        env = {k: v for k, v in os.environ.items() if k not in ("WAYLAND_DISPLAY", "DISPLAY")}
        env["XDG_RUNTIME_DIR"] = str(self.runtime)
        # the shell writes backups under the state directory: keep them out of the real one
        env["XDG_STATE_HOME"] = str(self.runtime / "state")
        env["WAYLAND_DISPLAY"] = self.display
        env["SWAYSOCK"] = str(self.sock)
        return env

    @property
    def sock(self) -> Path:
        assert self.process is not None
        return self.runtime / f"sway-ipc.{os.getuid()}.{self.process.pid}.sock"

    def start(self) -> PrivateSway:
        if not (shutil.which("sway") and shutil.which("swaymsg")):
            raise SwayUnavailable("sway and swaymsg are not installed")
        display_file = self.runtime / "display"
        config = self.runtime / "config"
        config.write_text(f"exec sh -c 'echo $WAYLAND_DISPLAY > {display_file}'\n")
        env = {k: v for k, v in os.environ.items() if k not in ("WAYLAND_DISPLAY", "DISPLAY")}
        env.update(
            XDG_RUNTIME_DIR=str(self.runtime),
            WLR_BACKENDS="headless",
            WLR_LIBINPUT_NO_DEVICES="1",
            WLR_RENDERER="pixman",
        )
        log = open(self.runtime / "sway.log", "wb")  # noqa: SIM115 - lives as long as sway
        self.process = subprocess.Popen(
            ["sway", "-c", str(config)], env=env, stdout=log, stderr=log
        )
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                break
            if display_file.exists() and display_file.read_text().strip() and self.sock.exists():
                ready = subprocess.run(
                    ["swaymsg", "-t", "get_version"],
                    env={**env, "SWAYSOCK": str(self.sock)},
                    capture_output=True,
                )
                if ready.returncode == 0:
                    self.display = display_file.read_text().strip()
                    return self
            time.sleep(0.1)
        tail = (self.runtime / "sway.log").read_text(errors="replace")[-500:]
        self.stop()
        raise SwayUnavailable(f"sway did not start: {tail}")

    def stop(self) -> None:
        proc = self.process
        if proc is not None and proc.poll() is None:
            try:
                subprocess.run(
                    ["swaymsg", "exit"],
                    env={
                        **os.environ,
                        "SWAYSOCK": str(self.sock),
                        "XDG_RUNTIME_DIR": str(self.runtime),
                    },
                    capture_output=True,
                    timeout=5,
                )
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired, OSError:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
        shutil.rmtree(self.runtime, ignore_errors=True)
