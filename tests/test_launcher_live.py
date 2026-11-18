"""The whole launcher on a real compositor, the private headless sway only, by KEY EVENTS ONLY (M6d,
Applications Module > Acceptance Criteria): the toggle a shortcut runs (a press of the FAKE
``org.kde.kglobalaccel`` on a private bus), typing, Down, Enter and Escape.

Nothing here reaches the user's session: the shell's environment is ``PrivateSway.env`` plus the
private bus, its ``XDG_DATA_HOME`` and ``XDG_DATA_DIRS`` are one temporary folder of made-up
entries (the real ``/usr/share/applications`` is never read), and no application starts: a shell
that runs as a process cannot be handed a fake starter, so the real runner, which refuses while
``PYTEST_CURRENT_TEST`` is set (and the shell inherits it), appends what it WOULD have started to
the file named by ``TESS_SHELL_LAUNCH_RECORD`` (``services/apps.py``, Safety). That file is what
these tests read: the command line, the working folder and the environment.

The keys are ``wtype`` (a ``zwp_virtual_keyboard_v1`` of its own) aimed at the private sway, as
``tests/test_keys_live.py`` does it. The shell's DEBUG log says what happened (the module logs each
search, selection and Escape; the surface manager logs a Panel's keyboard)."""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import pytest

from tests import live_pointer
from tests.shell_samples import BODY, write_example
from tests.sway import PrivateSway
from tests.test_run import Shell
from tests.test_shortcuts_live import Desk, Make, desk  # noqa: F401  (the fixture)

pytestmark = [
    pytest.mark.tre,
    pytest.mark.skipif(not live_pointer.available(), reason="no pywayland (tre's virtual env)"),
    pytest.mark.skipif(shutil.which("wtype") is None, reason="no wtype (a virtual keyboard)"),
]

SETTINGS = '    Shortcuts { Toggle_Launcher: "Meta+Space" }'


def keys(private_sway: PrivateSway, *args: str) -> None:
    """Type with a virtual keyboard on the private compositor (``-s 300``: a fresh virtual
    keyboard sends its keymap first, and a key sent at once is lost)."""
    env = dict(private_sway.env)
    assert env["WAYLAND_DISPLAY"] == private_sway.display and private_sway.display
    subprocess.run(["wtype", "-s", "300", *args], env=env, timeout=20, check=True)


def count(shell: Shell, text: str) -> int:
    while True:
        try:
            shell.seen.append(shell.lines.get_nowait())
        except queue.Empty:
            break
    return sum(text in line for line in shell.seen)


def wait_n(shell: Shell, text: str, n: int = 1, timeout: float = 30) -> None:
    """Wait until ``text`` has been in the shell's output ``n`` times (not once before)."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if count(shell, text) >= n:
            return
        try:
            shell.seen.append(shell.lines.get(timeout=0.1))
        except queue.Empty:
            pass
    pytest.fail(f"{text!r} {n} times never seen; the log so far:\n{''.join(shell.seen)[-3000:]}")


def reach(private_sway: PrivateSway, shell: Shell, tries: int = 20) -> None:
    """Send Down (the module logs every key it hears) until the Panel's field hears one: the
    compositor gives an exclusive layer surface the keyboard some milliseconds after it shows, and
    a key sent before is lost. This is the observable, not a sleep."""
    for _ in range(tries):
        before = count(shell, "| key arrow_down")
        keys(private_sway, "-k", "Down")
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            if count(shell, "| key arrow_down") > before:
                return
            time.sleep(0.05)
    pytest.fail(f"no key ever reached the Launcher; the log so far:\n{''.join(shell.seen)[-3000:]}")


def share_without_applications(tmp_path: Path) -> Path:
    """A folder of links to everything the real ``XDG_DATA_DIRS`` hold EXCEPT their ``applications``
    folders. The graphics stack finds its drivers through ``XDG_DATA_DIRS`` (``vulkan/icd.d``), so
    the shell needs them, but the launcher must read no real desktop entry: with this folder in the
    variable the only ``applications`` folder the shell sees is the test's own."""
    real = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    share = tmp_path / "share"
    share.mkdir()
    for directory in (Path(d) for d in real.split(":") if d):
        if not directory.is_dir():
            continue
        for entry in directory.iterdir():
            link = share / entry.name
            if entry.name != "applications" and not link.exists() and not link.is_symlink():
                link.symlink_to(entry)
    assert not (share / "applications").exists()
    return share


def prepare(d: Desk, tmp_path: Path, *, systemd_run: bool) -> Path:
    """Made-up entries, a bin folder for the path (with a ``systemd-run`` placeholder when asked:
    it is looked up, never run), the recorder file and the shell's environment."""
    data = tmp_path / "data"
    apps = data / "applications"
    apps.mkdir(parents=True)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    program = bin_dir / "fake-app"
    program.write_text("#!/bin/sh\nexit 0\n")  # never run: the runner records and starts nothing
    program.chmod(0o755)
    if systemd_run:
        tool = bin_dir / "systemd-run"
        tool.write_text("#!/bin/sh\nexit 1\n")
        tool.chmod(0o755)
    entries = {
        "Fake One": f"{program} --one %U",
        "Fake Two": f"{program} --two %F",
        "Other": f"{program} --other",
    }
    for name, exec_line in entries.items():
        (apps / f"{name.lower().replace(' ', '-')}.desktop").write_text(
            f"[Desktop Entry]\nType=Application\nName={name}\nExec={exec_line}\nPath={tmp_path}\n"
        )
    record = tmp_path / "record.jsonl"
    d.env.update(
        {
            "XDG_DATA_HOME": str(data),
            "XDG_DATA_DIRS": f"{data}:{share_without_applications(tmp_path)}",
            "PATH": str(bin_dir),
            "TESS_SHELL_LAUNCH_RECORD": str(record),
            "HOME": str(tmp_path / "home"),
        }
    )
    (tmp_path / "home").mkdir()
    # a Bar only: the Launcher Panel is the shell's own, brought by the Shortcuts entry
    write_example(d.cfg, BODY)
    d.settings(SETTINGS)
    return record


def records(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text().splitlines()] if path.exists() else []


@pytest.mark.parametrize("systemd_run", [True, False], ids=["scope", "plain"])
def test_the_launchers_exclusive_keyboard_reaches_the_compositor_when_it_is_shown(
    desk: Make,  # noqa: F811 - the fixture
    private_sway: PrivateSway,
    tmp_path: Path,
    systemd_run: bool,
) -> None:
    """tre 0.6.9 applies a ``LayerWindow.set`` made before the surface exists once it does
    (TRE-REQ-020), so the shell no longer sends a Panel's keyboard a second time at its first
    ``configure``. ``WAYLAND_DEBUG`` shows the request on the wire (1 is exclusive)."""
    d = desk()
    prepare(d, tmp_path, systemd_run=systemd_run)
    d.env["WAYLAND_DEBUG"] = "1"  # the client side of the protocol, on the shell's stderr
    shell = d.start()
    d.fake.press("Toggle_Launcher")
    wait_n(shell, "Panel Launcher on HEADLESS-1 shown")
    wait_n(shell, ".set_keyboard_interactivity(1)")
    assert d.finish() == 0


@pytest.mark.parametrize("systemd_run", [True, False], ids=["scope", "plain"])
def test_the_launcher_opens_with_the_shortcut_searches_moves_starts_and_closes_by_keys_only(
    desk: Make,  # noqa: F811 - the fixture
    private_sway: PrivateSway,
    tmp_path: Path,
    systemd_run: bool,
) -> None:
    d = desk()
    record = prepare(d, tmp_path, systemd_run=systemd_run)
    shell = d.start()
    assert d.fake.names() == ["Toggle_Launcher"]  # the shipped Panel gave the key a target
    d.fake.press("Toggle_Launcher")  # open: the key comes from the (fake) desktop service
    wait_n(shell, "Panel Launcher on HEADLESS-1 shown")
    reach(private_sway, shell)  # sway hands the exclusive surface the keyboard
    keys(private_sway, "fake")  # type to search: two results
    wait_n(shell, "search 'fake': 2 results")
    moved = count(shell, "selected Fake Two")  # (the probe's own Down may have been one)
    keys(private_sway, "-k", "Down")  # the selection moves from the field: Fake Two
    wait_n(shell, "selected Fake Two", moved + 1)
    keys(private_sway, "-k", "Return")  # Enter starts it
    wait_n(shell, "Panel Launcher on HEADLESS-1 hidden")
    (made,) = records(record)
    program = str(tmp_path / "bin" / "fake-app")
    if systemd_run:
        assert made["argv"][:4] == ["systemd-run", "--user", "--scope", "--quiet"]
        assert made["argv"][-3:] == ["--", program, "--two"]  # %F removed
        assert made["scope"].startswith("app-fake-two-") and made["scope"].endswith(".scope")
    else:
        assert made["argv"] == [program, "--two"] and made["scope"] is None
    assert made["cwd"] == str(tmp_path)  # Path= of the entry
    assert "NOTIFY_SOCKET" not in made["env"] and "TESS_SHELL_LAUNCH_RECORD" not in made["env"]
    # the token: sway offers xdg_activation_v1, so one may come; if none did, none is passed
    log = "".join(shell.seen)
    assert "activation token:" in log
    assert (made["token"] is None) == ("activation token: none" in log)
    assert "XDG_ACTIVATION_TOKEN" not in made["env"] or made["env"]["XDG_ACTIVATION_TOKEN"]
    # Escape: with text it clears the field and the Panel stays, then it hides
    d.fake.press("Toggle_Launcher")
    wait_n(shell, "Panel Launcher on HEADLESS-1 shown", 2)
    reach(private_sway, shell)
    keys(private_sway, "x")
    wait_n(shell, "search 'x': 0 results")
    keys(private_sway, "-k", "Escape")
    wait_n(shell, "escape: the field is cleared")
    time.sleep(0.5)  # a negative: there is nothing to wait for when the Panel must NOT hide
    assert count(shell, "Panel Launcher on HEADLESS-1 hidden") == 1  # still open
    keys(private_sway, "-k", "Escape")
    wait_n(shell, "escape: the panel hides")
    wait_n(shell, "Panel Launcher on HEADLESS-1 hidden", 2)
    assert d.finish() == 0
    assert "| ERROR " not in "".join(shell.seen)
    assert len(records(record)) == 1  # nothing else was started
