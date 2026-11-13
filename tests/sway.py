"""A private headless sway for tests that need a Wayland compositor with layer-shell.

It has its own temporary ``XDG_RUNTIME_DIR``, so its socket and the shell's instance lock never
touch the real session. Recipe from tre's ``tools/sway_live.sh``.
"""

from __future__ import annotations

import json
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
        env.pop("JOURNAL_STREAM", None)  # under systemd the console drops its timestamps
        # never the real session bus: the shell reads the desktop's settings portal from it
        env.pop("DBUS_SESSION_BUS_ADDRESS", None)
        # nor the real sound server (a shell on this compositor finds one only if a test names it)
        for name in ("PULSE_SERVER", "PULSE_RUNTIME_PATH", "PULSE_COOKIE", "PIPEWIRE_REMOTE"):
            env.pop(name, None)
        # nor the real system bus (UPower, NetworkManager): a socket that is not there, until a test
        # gives the shell a private one
        env["DBUS_SYSTEM_BUS_ADDRESS"] = f"unix:path={self.runtime}/no-system-bus"
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
        env.pop("DBUS_SESSION_BUS_ADDRESS", None)  # sway itself never reaches the real session bus
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

    def msg(self, *args: str) -> str:
        """Run ``swaymsg`` against this compositor and return its stdout."""
        done = subprocess.run(
            ["swaymsg", *args], env=self.env, capture_output=True, text=True, check=True
        )
        return done.stdout

    def output_names(self) -> list[str]:
        return [o["name"] for o in json.loads(self.msg("-t", "get_outputs", "-r"))]

    def create_output(self) -> str:
        """Plug in a headless output (1920x1080, to the right of the others); returns its name."""
        before = set(self.output_names())
        self.msg("create_output")
        (name,) = set(self.output_names()) - before
        return name

    def unplug(self, name: str) -> None:
        self.msg("output", name, "unplug")

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
