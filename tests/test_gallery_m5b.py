"""The M5b KWin kit (``tests/kwin/prepare_m5b_gallery.py``): its config checks clean, the shell
starts it on a private sway with no error and no warning, and the fake UPower and its helper
scripts work against a private bus (nothing here touches the real session or system bus)."""

from __future__ import annotations

import asyncio
import shutil
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from dbus_fast import Message, MessageType
from dbus_fast.aio import MessageBus

from tests.fake_dbus import HAVE_DAEMON, wait_for
from tests.kwin import prepare_m5b_gallery as g
from tests.sway import PrivateSway
from tests.test_run import Shell

UPOWER = "org.freedesktop.UPower"
DEVICE = "/org/freedesktop/UPower/devices/DisplayDevice"


def test_the_gallery_files_check_clean(tmp_path: Path) -> None:
    g.write_gallery(tmp_path)
    done = subprocess.run(
        [sys.executable, "-m", "tess_shell", "check", "--config-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        env={"XDG_STATE_HOME": str(tmp_path / "state"), "PATH": "/usr/bin:/bin"},
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "error" not in (done.stdout + done.stderr).replace("no error", "")


def test_the_checklist_numbers_every_line_in_one_list() -> None:
    numbered = [x for x in g.CHECKLIST.splitlines() if x[:2].strip().isdigit()]
    assert [int(x[:2]) for x in numbered] == list(range(1, 22))
    assert "writes" in g.CHECKLIST and "real" in g.CHECKLIST  # the one write is named
    assert "$color" not in g.CHECKLIST and "#" not in g.BODY  # theme tokens, never hex


@pytest.mark.tre
def test_the_gallery_starts_on_a_private_sway(private_sway: PrivateSway, tmp_path: Path) -> None:
    g.write_gallery(tmp_path)
    shell = Shell(tmp_path, private_sway.env)  # no session bus, an absent system bus
    try:
        shell.wait_for("Bar Top_Bar on HEADLESS-1 configured")
        shell.wait_for("running")
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
    bad = [line for line in shell.seen if "| ERROR " in line or "| WARNING " in line]
    assert [x for x in bad if "the session bus is not reachable" not in x] == []


# -- the fake UPower and the helper scripts -----------------------------------------------------


async def _read(address: str) -> dict[str, Any]:
    bus = await MessageBus(bus_address=address).connect()
    try:
        reply = await bus.call(
            Message(
                destination=UPOWER,
                path=DEVICE,
                interface="org.freedesktop.DBus.Properties",
                member="GetAll",
                signature="s",
                body=["org.freedesktop.UPower.Device"],
            )
        )
        assert reply is not None and reply.message_type == MessageType.METHOD_RETURN, reply
        return {k: v.value for k, v in reply.body[0].items()}
    finally:
        bus.disconnect()


async def _owned(address: str) -> bool:
    bus = await MessageBus(bus_address=address).connect()
    try:
        reply = await bus.call(
            Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member="NameHasOwner",
                signature="s",
                body=[UPOWER],
            )
        )
        assert reply is not None
        return bool(reply.body[0])
    finally:
        bus.disconnect()


@pytest.mark.skipif(
    not HAVE_DAEMON or shutil.which("busctl") is None, reason="needs dbus-daemon and busctl"
)
def test_the_fake_upower_and_its_scripts_drive_a_private_bus(tmp_path: Path) -> None:
    fake = subprocess.Popen(
        [
            sys.executable,
            str(g.REPO / "tests" / "kwin" / "fake_upower.py"),
            "--root",
            str(tmp_path),
        ],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert wait_for(lambda: (tmp_path / "bus-address").is_file(), 10)
        address = (tmp_path / "bus-address").read_text()
        assert "tess-bus-" in address  # its own temporary daemon, not a real bus
        env = {"TESS_M5B_ROOT": str(tmp_path), "PATH": "/usr/bin:/bin"}

        def run(script: str, text: str, *args: str) -> subprocess.CompletedProcess[str]:
            path = tmp_path / script
            path.write_text("#!/usr/bin/env bash\n" + text)
            path.chmod(0o755)
            return subprocess.run(
                [str(path), *args], env=env, capture_output=True, text=True, timeout=20
            )

        start = asyncio.run(_read(address))
        assert (start["Percentage"], start["State"], start["IsPresent"]) == (82.0, 2, True)
        done = run("battery-set.sh", g.BATTERY_SET, "15", "discharging", "present", "low")
        assert done.returncode == 0, done.stdout + done.stderr
        got = asyncio.run(_read(address))
        assert (got["Percentage"], got["State"], got["WarningLevel"]) == (15.0, 2, 3)
        assert got["TimeToEmpty"] == 15 * 98 and got["TimeToFull"] == 0 and got["IsPresent"] is True
        run("battery-set.sh", g.BATTERY_SET, "40", "charging", "present", "normal")
        got = asyncio.run(_read(address))
        assert (got["State"], got["WarningLevel"], got["TimeToFull"]) == (1, 1, 6000)
        run("battery-set.sh", g.BATTERY_SET, "0", "unknown", "absent", "normal")
        assert asyncio.run(_read(address))["IsPresent"] is False
        assert run("battery-set.sh", g.BATTERY_SET, "5", "nonsense").returncode != 0
        away = run("battery-upower.sh", g.BATTERY_UPOWER, "away")
        assert away.returncode == 0, away.stderr
        assert wait_for(lambda: not asyncio.run(_owned(address)), 10)
        run("battery-upower.sh", g.BATTERY_UPOWER, "back")
        assert wait_for(lambda: asyncio.run(_owned(address)), 10)
    finally:
        fake.send_signal(signal.SIGTERM)
        fake.wait(10)
    assert not (tmp_path / "bus-address").exists()  # it cleans up its daemon and its address file
