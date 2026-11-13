"""A PRIVATE PipeWire stack for the audio spike (T-018). Nothing here touches the real server.

``pipewire``, ``wireplumber`` and ``pipewire-pulse`` run with a private ``XDG_RUNTIME_DIR`` (a short
directory under /tmp, mode 0700), private config/state/cache/data/home directories, a private
session bus (``dbus-daemon``), a system bus address that does not exist, and no real device: the
private WirePlumber config disables its ALSA, Bluetooth and V4L2 monitors. The sinks are null sinks
made inside the private server. The environment of every process and client is built from scratch
(:func:`clean_env`): nothing is inherited from the parent.

Run as a script to bring the stack up, print the isolation proof and stop it:
``env -u WAYLAND_DISPLAY -u DISPLAY python -m tests.spikes.audio.stack``
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from tests.spikes.audio.guard import (
    checked_env,
    reexec_in_sandbox,
    require_private_env,
    require_sandbox,
)

WP_CONFIG = """\
wireplumber.profiles = {
  main = {
    hardware.audio = disabled
    hardware.bluetooth = disabled
    hardware.video-capture = disabled
  }
}
"""

# The "devices": null sinks and a virtual source made by pipewire itself (object.linger), so they
# stay when pipewire-pulse restarts, as a hardware device would. No real device is ever opened.
PW_CONFIG = """\
context.properties = {
  module.x11.bell = false
  module.jackdbus-detect = false
  module.portal = false
}
context.objects = [
  { factory = adapter
    args = { factory.name = support.null-audio-sink node.name = spike_speaker
             node.description = "Spike Speaker" media.class = Audio/Sink
             audio.position = [ FL FR ] device.form_factor = speaker
             device.bus = usb object.linger = true monitor.channel-volumes = true } }
  { factory = adapter
    args = { factory.name = support.null-audio-sink node.name = spike_phones
             node.description = "Spike Headphones" media.class = Audio/Sink
             audio.position = [ FL FR ] device.form_factor = headphone
             device.bus = bluetooth object.linger = true monitor.channel-volumes = true } }
  { factory = adapter
    args = { factory.name = support.null-audio-sink node.name = spike_mic
             node.description = "Spike Microphone" media.class = Audio/Source/Virtual
             audio.position = [ FL FR ] device.form_factor = microphone
             object.linger = true monitor.channel-volumes = true } }
]
"""


class StackError(RuntimeError):
    pass


class PrivateStack:
    def __init__(self) -> None:
        require_sandbox()  # physical barrier first: never outside the bwrap sandbox
        self.root = Path(tempfile.mkdtemp(prefix="asp-", dir="/tmp"))
        self.root.chmod(0o700)
        self.run = self.root / "run"
        self.run.mkdir(mode=0o700)
        for sub in ("home", "config", "state", "cache", "data", "log"):
            (self.root / sub).mkdir(mode=0o700)
        wp = self.root / "config" / "wireplumber" / "wireplumber.conf.d"
        wp.mkdir(parents=True)
        (wp / "90-spike.conf").write_text(WP_CONFIG)
        pw = self.root / "config" / "pipewire" / "pipewire.conf.d"
        pw.mkdir(parents=True)
        (pw / "90-spike.conf").write_text(PW_CONFIG)
        self.procs: dict[str, subprocess.Popen[bytes]] = {}
        self.env = clean_env(self.root)
        require_private_env(self.env)

    # the three servers -------------------------------------------------------------------
    @property
    def socket(self) -> Path:
        return self.run / "pulse" / "native"

    def _spawn(self, name: str, argv: list[str]) -> None:
        log = open(self.root / "log" / f"{name}.log", "wb")  # noqa: SIM115 (lives with the child)
        self.procs[name] = subprocess.Popen(
            argv, env=checked_env(self.env), stdout=log, stderr=log, stdin=subprocess.DEVNULL
        )

    def start(self) -> None:
        self._spawn(
            "dbus",
            [
                "dbus-daemon",
                "--session",
                f"--address=unix:path={self.root}/bus",
                "--nofork",
                "--nopidfile",
            ],
        )
        self._wait_path(self.root / "bus")
        self._spawn("pipewire", ["pipewire"])
        self._wait_path(self.run / "pipewire-0")
        self._spawn("wireplumber", ["wireplumber"])
        self.start_pulse()

    def start_pulse(self) -> None:
        self._spawn("pipewire-pulse", ["pipewire-pulse"])
        self._wait_path(self.socket)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if self.pactl("info", check=False).returncode == 0:
                return
            time.sleep(0.1)
        raise StackError("pipewire-pulse did not answer pactl info; see log/")

    def stop_pulse(self) -> None:
        self._terminate("pipewire-pulse")

    def kill_pulse(self) -> None:
        proc = self.procs.get("pipewire-pulse")
        if proc is not None and proc.poll() is None:
            proc.kill()
            proc.wait(5)

    def restart_pipewire(self) -> None:
        """Kill ``pipewire`` itself (``wireplumber`` and ``pipewire-pulse`` lose their server and
        are stopped), then start all three again: the devices (made by pipewire's own config) and
        the pulse socket come back. A stale socket file of the killed ``pipewire-pulse`` stays until
        the new one replaces it, as after a crash."""
        proc = self.procs["pipewire"]
        proc.kill()
        proc.wait(5)
        for name in ("pipewire-pulse", "wireplumber"):
            self._terminate(name)
        self._spawn("pipewire", ["pipewire"])
        self._wait_path(self.run / "pipewire-0")
        self._spawn("wireplumber", ["wireplumber"])
        self.start_pulse()

    def pid(self, name: str) -> int:
        return self.procs[name].pid

    @staticmethod
    def _wait_path(path: Path, timeout: float = 10.0) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if path.exists():
                return
            time.sleep(0.05)
        raise StackError(f"{path} did not appear")

    def _terminate(self, name: str) -> None:
        proc = self.procs.get(name)
        if proc is None or proc.poll() is not None:
            return
        proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(5)

    def stop(self) -> None:
        for name in ("pipewire-pulse", "wireplumber", "pipewire", "dbus"):
            self._terminate(name)
        shutil.rmtree(self.root, ignore_errors=True)

    def __enter__(self) -> PrivateStack:
        try:
            self.start()
        except BaseException:
            self.stop()
            raise
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.stop()

    # clients (always with the private environment) ----------------------------------------
    def tool(self, argv: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            argv, env=checked_env(self.env), capture_output=True, text=True, timeout=20, check=check
        )

    def pactl(self, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return self.tool(["pactl", *args], check)

    def prove_isolation(self) -> str:
        """The facts that show the private server is not the real one. Raises if they do not."""
        info = self.pactl("info").stdout
        sinks = self.pactl("list", "short", "sinks").stdout
        sources = self.pactl("list", "short", "sources").stdout
        socket_line = f"PULSE_SERVER={self.env['PULSE_SERVER']}"
        real = f"/run/user/{os.getuid()}"
        if real in self.env["PULSE_SERVER"] or real in self.env["XDG_RUNTIME_DIR"]:
            raise StackError("the private environment names the real runtime dir")
        names = {line.split("\t")[1] for line in sinks.splitlines() if line.strip()}
        if names - {"auto_null", "spike_speaker", "spike_phones"}:
            raise StackError(f"unexpected sinks in the private server: {sinks}")
        return (
            f"{socket_line}\nXDG_RUNTIME_DIR={self.env['XDG_RUNTIME_DIR']}\n"
            f"pactl info (private):\n{info}\nsinks:\n{sinks}\nsources:\n{sources}"
        )

    def add_null_sink(self, name: str, form_factor: str = "speaker") -> str:
        """A null sink INSIDE the private server (never anywhere else); returns the module id."""
        props = f"device.description={name} device.form_factor={form_factor}"
        out = self.pactl(
            "load-module", "module-null-sink", f"sink_name={name}", f"sink_properties='{props}'"
        )
        return out.stdout.strip()


def clean_env(root: Path) -> dict[str, str]:
    """The environment of every process and client of the spike, built from nothing."""
    run = root / "run"
    return {
        "PATH": "/usr/bin:/bin",
        "LANG": "C.UTF-8",
        "HOME": str(root / "home"),
        "TESS_SPIKE_SANDBOX": "1",  # the children are inside the same sandbox
        "XDG_RUNTIME_DIR": str(run),
        "XDG_CONFIG_HOME": str(root / "config"),
        "XDG_STATE_HOME": str(root / "state"),
        "XDG_CACHE_HOME": str(root / "cache"),
        "XDG_DATA_HOME": str(root / "data"),
        "PIPEWIRE_RUNTIME_DIR": str(run),
        "PULSE_RUNTIME_PATH": str(run / "pulse"),
        "PULSE_SERVER": f"unix:{run}/pulse/native",
        "PULSE_STATE_PATH": str(root / "state"),
        "DBUS_SESSION_BUS_ADDRESS": f"unix:path={root}/bus",
        "DBUS_SYSTEM_BUS_ADDRESS": f"unix:path={root}/no-system-bus",
    }


if __name__ == "__main__":
    reexec_in_sandbox("tests.spikes.audio.stack")
    with PrivateStack() as stack:
        print(stack.prove_isolation())
