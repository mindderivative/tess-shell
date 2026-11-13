"""The safety guard of the audio spike (rule D-019/D-025). Nothing in this folder may reach the
real sound server, the real session bus or the real runtime directory.

* PHYSICAL barrier: every entry point re-executes itself once under ``bwrap`` (see
  :func:`reexec_in_sandbox`): the real ``/run`` (so ``/run/user/<uid>/pulse``, ``pipewire-0`` and
  the session bus), ``/sys`` (no ALSA card can be enumerated) and ``/dev`` (no ``/dev/snd``, no
  ``/dev/input``) are replaced by empty or minimal mounts, and the file system is read-only except
  ``/tmp``. :func:`require_sandbox` refuses to go on outside it. The checks below are the second
  line, not the first.
* Every script builds its environment from scratch (``stack.clean_env``) and passes it explicitly;
  nothing is inherited.
* Every client of the sound server (the native-protocol client, pulsectl, ``pactl``, ``wpctl``,
  ``pw-dump``, ``pw-cli``) is created through a function that calls one of the checks below first.
  A check aborts (``GuardError``) unless the target is a private instance: a socket or runtime
  directory under ``/tmp/asp-*`` (made by ``PrivateStack``), never under ``/run/user`` or ``$HOME``.
"""

from __future__ import annotations

import errno
import os
import shutil
import socket
import sys
from collections.abc import Mapping
from pathlib import Path

PREFIX = "/tmp/asp-"
# the variables that name a server, a bus or a runtime directory: every one must be private
_PRIVATE_KEYS = (
    "XDG_RUNTIME_DIR",
    "PIPEWIRE_RUNTIME_DIR",
    "PULSE_RUNTIME_PATH",
    "PULSE_SERVER",
    "DBUS_SESSION_BUS_ADDRESS",
)
_FORBIDDEN_KEYS = ("WAYLAND_DISPLAY", "DISPLAY", "PIPEWIRE_REMOTE", "PULSE_SINK", "PULSE_SOURCE")


class GuardError(SystemExit):
    """Aborts the script; it is a SystemExit so that no ``except Exception`` swallows it."""


def _private(value: str) -> bool:
    text = value.removeprefix("unix:").removeprefix("path=")
    text = text.removeprefix("unix:path=")
    return os.path.realpath(text).startswith(PREFIX) and "/run/user" not in os.path.realpath(text)


def require_private_path(path: str | Path) -> None:
    """``path`` (a socket or a directory) must be inside a private ``/tmp/asp-*`` stack."""
    if not _private(str(path)):
        raise GuardError(f"GUARD: {path} is not a private /tmp/asp-* path; refusing to connect")


def require_private_env(env: Mapping[str, str]) -> None:
    """``env`` (about to be given to a client or a child) must point only at the private stack."""
    for key in _PRIVATE_KEYS:
        value = env.get(key)
        if value is None:
            if key in ("XDG_RUNTIME_DIR", "PULSE_SERVER"):
                raise GuardError(f"GUARD: {key} is not set; the environment is not private")
            continue
        if not _private(value):
            raise GuardError(f"GUARD: {key}={value} is not private; refusing to run")
    for key in _FORBIDDEN_KEYS:
        if key in env:
            raise GuardError(f"GUARD: {key} must not be in the environment of the spike")


def checked_env(env: Mapping[str, str]) -> dict[str, str]:
    require_private_env(env)
    return dict(env)


def isolate_process(env: Mapping[str, str]) -> None:
    """Replace this process's whole environment with the private one (after checking it), so that
    a library that reads the environment (libpulse, ``PULSE_SERVER``) can only find the private
    server."""
    require_private_env(env)
    os.environ.clear()
    os.environ.update(env)
    require_private_env(os.environ)


SANDBOX_VAR = "TESS_SPIKE_SANDBOX"
BWRAP_ARGS = (
    "--ro-bind", "/", "/",  # everything read-only ...
    "--tmpfs", "/run",  # ... the real /run (and /run/user/<uid>: pulse, pipewire-0, bus) hidden
    "--tmpfs", "/sys",  # no ALSA card can be enumerated
    "--dev", "/dev",  # minimal /dev: no /dev/snd, no /dev/input, no /dev/uinput
    "--proc", "/proc",
    "--bind", "/tmp", "/tmp",  # ... except /tmp, where the private stack lives
    "--die-with-parent",
    "--unshare-ipc",
    "--unshare-pid",
    "--unshare-net",  # no abstract unix sockets of the host either
    "--setenv", SANDBOX_VAR, "1",
)  # fmt: skip


def reexec_in_sandbox(module: str) -> None:
    """Call first thing in an entry point: outside the sandbox, replace this process with
    ``bwrap ... python -m <module> <args>`` (a from-scratch environment; nothing is inherited);
    inside it, check it. Never returns outside the sandbox."""
    if os.environ.get(SANDBOX_VAR) == "1":
        require_sandbox()
        return
    bwrap = shutil.which("bwrap", path="/usr/bin:/bin")
    if bwrap is None:
        raise GuardError("GUARD: bwrap is not installed; the spike will not run unsandboxed")
    env = {"PATH": "/usr/bin:/bin", "HOME": "/tmp", "LANG": "C.UTF-8"}
    argv = [bwrap, *BWRAP_ARGS, "--chdir", os.getcwd(), "--"]
    os.execve(bwrap, [*argv, sys.executable, "-m", module, *sys.argv[1:]], env)


def require_sandbox() -> None:
    """Abort unless this process runs inside the bwrap sandbox: the marker is set, the real
    sound-server, bus and device paths are not there, and a connection to the real PulseAudio
    socket fails with ENOENT (it cannot reach anything: the path is absent)."""
    if os.environ.get(SANDBOX_VAR) != "1":
        raise GuardError(f"GUARD: {SANDBOX_VAR} is not 1: not running in the sandbox")
    run = f"/run/user/{os.getuid()}"
    for path in (
        f"{run}/pulse",
        f"{run}/pipewire-0",
        f"{run}/bus",
        "/dev/snd",
        "/dev/input",
        "/sys/class/sound",
    ):
        if os.path.exists(path):
            raise GuardError(f"GUARD: {path} exists: the sandbox is not hiding the real session")
    canary = socket.socket(socket.AF_UNIX)
    try:
        canary.connect(f"{run}/pulse/native")
    except OSError as exc:
        if exc.errno != errno.ENOENT:
            raise GuardError(f"GUARD: canary connect gave {exc!r}, not ENOENT") from exc
    else:
        raise GuardError("GUARD: the real pulse socket is reachable: the sandbox failed")
    finally:
        canary.close()
