"""Recorded outputs of the command line, for tools that never run the real shell (the tess-ui
configuration application builds its tests on them).

``tests/fixtures/cli/`` holds what ``schema --json``, ``check --json`` and ``version --json`` print,
for a clean folder and for a folder with a finding, and what ``status --json`` prints: of a REAL
shell (``status_running.json``: a shell on a private headless sway and a private session bus, the
control interface answering) and with no shell (``status_not_running.json``: exit code 3, the
object ``{"ok": false, "error": ..., "exit": 3}``). ``tests/test_cli_fixtures.py`` proves each file
still equals what the command prints now, so a fixture cannot go stale. Values that change with the
machine or a release (the folder, the versions, the output names) are replaced by a ``<...>``
placeholder on both sides. Rewrite the files after a deliberate change with

    env -u WAYLAND_DISPLAY -u DISPLAY python -m tests.cli_fixtures

The running one needs ``sway`` and ``dbus-daemon``; the test skips without them.
"""

from __future__ import annotations

import contextlib
import io
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from tess_shell.cli import main

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "cli"
CLEAN = FIXTURES / "config_clean"
FINDINGS = FIXTURES / "config_findings"


def run(*argv: str) -> tuple[int, str]:
    """``tesserae-shell ARGV`` in this process: the exit code and what it printed."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(list(argv))
    return code, out.getvalue()


def _scrub(value: Any, folder: Path) -> Any:
    """The machine- and release-dependent values of a command's JSON, as placeholders."""
    if isinstance(value, dict):
        out = {}
        for key, item in value.items():
            if key == "config_dir" and item == str(folder):
                out[key] = "<config_dir>"
            elif key in ("shell", "tess_re", "tess_el", "tess_dl", "python", "shell_version"):
                out[key] = f"<{key}>"
            elif key == "output" and isinstance(item, str):
                out[key] = "<output>"  # the compositor's name for the monitor
            else:
                out[key] = _scrub(item, folder)
        return out
    if isinstance(value, list):
        return [_scrub(item, folder) for item in value]
    return value


def _command(*argv: str, folder: Path, code: int) -> Callable[[], str]:
    def render() -> str:
        got, text = run(*argv, "--config-dir", str(folder))
        assert got == code, f"{argv} exited {got}, expected {code}"
        return json.dumps(_scrub(json.loads(text), folder), indent=2) + "\n"

    return render


@contextlib.contextmanager
def _session_bus(address: str) -> Iterator[None]:
    """``DBUS_SESSION_BUS_ADDRESS`` set to ``address`` for the client run in this process."""
    old = os.environ.get("DBUS_SESSION_BUS_ADDRESS")
    os.environ["DBUS_SESSION_BUS_ADDRESS"] = address
    try:
        yield
    finally:
        if old is None:
            del os.environ["DBUS_SESSION_BUS_ADDRESS"]
        else:
            os.environ["DBUS_SESSION_BUS_ADDRESS"] = old


def _not_running() -> str:
    """``status --json`` on a private session bus that nobody owns the shell's name on."""
    from tests.fake_dbus import fake_bus

    with fake_bus() as bus, _session_bus(bus.address):
        code, text = run("status", "--json")
    assert code == 3, f"status exited {code}, expected 3"
    return json.dumps(json.loads(text), indent=2) + "\n"


def _running_config(cfg: Path) -> None:
    """A folder with one Bar, one hidden Panel and a shipped module: what a status has to show."""
    from tests.shell_samples import BODY, write_example

    launcher = (
        "Panel { Name: Launcher, Layer: OVERLAY, Keyboard: EXCLUSIVE, Width: 600, Height: 400, "
        "Visible: false }"
    )
    body = BODY.replace("            Bar {", f"            {launcher}\n            Bar {{", 1)
    body = body.replace(
        'Text { Text: "14:05", Font_Size: 14, Foreground: "#ffffff" }',
        'Clock { format: "%H:%M" }',
    )
    write_example(cfg, body)


def _running() -> str:
    """``status --json`` of a real shell: ``tesserae-shell run`` on a private headless sway and a
    private session bus, asked through the real client."""
    from tests.fake_dbus import FakeBus
    from tests.sway import PrivateSway, SwayUnavailable

    sway = PrivateSway()
    try:
        sway.start()
    except SwayUnavailable as exc:
        raise RecordingUnavailable(str(exc)) from exc
    bus = FakeBus()
    folder = Path(tempfile.mkdtemp(prefix="tess-status-"))
    process: subprocess.Popen[str] | None = None
    try:
        cfg = folder / "cfg"
        _running_config(cfg)
        env = {**sway.env, "DBUS_SESSION_BUS_ADDRESS": bus.address}
        process = subprocess.Popen(
            [sys.executable, "-m", "tess_shell", "run", "--config-dir", str(cfg)],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        deadline = time.monotonic() + 30
        while True:
            got = subprocess.run(
                [sys.executable, "-m", "tess_shell", "status", "--json"],
                env=env,
                capture_output=True,
                text=True,
            )
            if got.returncode == 0 and json.loads(got.stdout).get("state") == "running":
                break
            assert time.monotonic() < deadline, f"no running shell: {got.stdout}{got.stderr}"
            assert process.poll() is None, "the shell ended"
            time.sleep(0.1)
        status = json.loads(got.stdout)
        return json.dumps(_scrub(status, cfg), indent=2) + "\n"
    finally:
        if process is not None and process.poll() is None:
            process.send_signal(signal.SIGTERM)
            try:
                process.wait(10)
            except subprocess.TimeoutExpired:
                process.kill()
        bus.close()
        sway.stop()
        shutil.rmtree(folder, ignore_errors=True)


class RecordingUnavailable(RuntimeError):
    """The tools a fixture is recorded with (sway, dbus-daemon) are not installed."""


def available() -> bool:
    """Whether the running shell can be recorded here."""
    return all(shutil.which(tool) for tool in ("sway", "swaymsg", "dbus-daemon"))


# fixture file -> (the command's exit code, how to print it)
RECORDED: dict[str, Callable[[], str]] = {
    "schema.json": lambda: (
        json.dumps(_scrub(json.loads(run("schema", "--json")[1]), CLEAN), indent=2) + "\n"
    ),
    "check_clean.json": _command("check", "--json", folder=CLEAN, code=0),
    "check_findings.json": _command("check", "--json", folder=FINDINGS, code=1),
    "version.json": _command("version", "--json", folder=CLEAN, code=0),
    "status_running.json": _running,
    "status_not_running.json": _not_running,
}


def write() -> None:
    for name, render in RECORDED.items():
        (FIXTURES / name).write_text(render(), encoding="utf-8")
        print(f"wrote {FIXTURES / name}")


if __name__ == "__main__":
    write()
