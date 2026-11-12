"""The M5c KWin kit (``tests/kwin/prepare_m5c_gallery.py``): its config checks clean, the shell
starts it on a private sway with no error and no warning, and the fake NetworkManager and its helper
scripts work against a private bus: every ``network-set.sh`` and ``network-nm.sh`` command line the
checklist tells the maintainer to type is run, in order, against the real fake (nothing here
touches the real session or system bus or the real network)."""

from __future__ import annotations

import asyncio
import re
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
from tests.fake_nm import AC, AP, DEV, MANAGER_PATH, NM
from tests.kwin import prepare_m5c_gallery as g
from tests.sway import PrivateSway
from tests.test_run import Shell

PROPS = "org.freedesktop.DBus.Properties"


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


def test_the_checklist_numbers_every_line_in_one_list_and_names_what_it_writes() -> None:
    numbered = [x for x in g.CHECKLIST.splitlines() if x[:2].strip().isdigit()]
    assert [int(x[:2]) for x in numbered] == [*range(1, 8), *range(11, 25)]
    assert "writes nothing" in g.CHECKLIST and "private" in g.CHECKLIST
    assert "$color" not in g.CHECKLIST and "#" not in g.BODY  # theme tokens, never hex
    for light_dark in ("light", "dark"):
        assert light_dark in g.CHECKLIST


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


# -- the fake NetworkManager and the helper scripts ---------------------------------------------


async def _get_all(address: str, path: str, interface: str) -> dict[str, Any]:
    bus = await MessageBus(bus_address=address).connect()
    try:
        reply = await bus.call(
            Message(
                destination=NM,
                path=path,
                interface=PROPS,
                member="GetAll",
                signature="s",
                body=[interface],
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
                body=[NM],
            )
        )
        assert reply is not None
        return bool(reply.body[0])
    finally:
        bus.disconnect()


def manager(address: str) -> dict[str, Any]:
    return asyncio.run(_get_all(address, MANAGER_PATH, NM))


def commands() -> list[str]:
    """Every ``network-set.sh`` and ``network-nm.sh`` command line in the checklist, in order."""
    text = re.sub(r"\s+", " ", g.CHECKLIST)
    return re.findall(r"`(network-(?:set|nm)\.sh[^`]*)`", text)


REFUSED = ("network-set.sh bogus", "network-set.sh wired 50", "network-set.sh vpn none")


def test_the_checklist_has_the_command_lines_the_test_runs() -> None:
    found = commands()
    assert len(found) > 30 and all(r in found for r in REFUSED)
    assert "network-nm.sh away" in found and "network-nm.sh back" in found


@pytest.mark.skipif(
    not HAVE_DAEMON or shutil.which("busctl") is None, reason="needs dbus-daemon and busctl"
)
def test_the_fake_networkmanager_and_every_checklist_command_work_on_a_private_bus(
    tmp_path: Path,
) -> None:
    fake = subprocess.Popen(
        [sys.executable, str(g.REPO / "tests" / "kwin" / "fake_nm.py"), "--root", str(tmp_path)],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert wait_for(lambda: (tmp_path / "bus-address").is_file(), 10)
        address = (tmp_path / "bus-address").read_text()
        assert "tess-bus-" in address  # its own temporary daemon, not a real bus
        env = {"TESS_M5C_ROOT": str(tmp_path), "PATH": "/usr/bin:/bin"}
        for name, text in (("network-set.sh", g.NETWORK_SET), ("network-nm.sh", g.NETWORK_NM)):
            (tmp_path / name).write_text("#!/usr/bin/env bash\n" + text)
            (tmp_path / name).chmod(0o755)
        start = manager(address)
        assert (start["State"], start["Connectivity"], start["PrimaryConnection"]) == (
            70,
            4,
            AC["wired"],
        )

        def run(line: str) -> subprocess.CompletedProcess[str]:
            script, *words = line.split()
            return subprocess.run(
                [str(tmp_path / script), *words],
                env=env,
                capture_output=True,
                text=True,
                timeout=30,
            )

        for line in commands():
            before = manager(address) if line.startswith("network-set") else {}
            done = run(line)
            if line in REFUSED:
                assert done.returncode != 0, line
                assert "unknown word" in done.stdout or "needs" in done.stdout, done.stdout
                assert manager(address) == before, f"{line} changed something"
                continue
            assert done.returncode == 0, f"{line}: {done.stdout}{done.stderr}"
            if line == "network-nm.sh away":
                assert wait_for(lambda: not asyncio.run(_owned(address)), 10)
            if line == "network-nm.sh back":
                assert wait_for(lambda: asyncio.run(_owned(address)), 10)
        assert asyncio.run(_owned(address))
        # the last set of the checklist's order: wired, the strength words leave the rest alone
        assert manager(address)["PrimaryConnection"] in (AC["wired"], AC["wifi"], "/")
        # the scripts map their words to what NetworkManager reports
        expected = {
            "wired": (70, 4, AC["wired"], [AC["wired"]]),
            "wired limited": (70, 3, AC["wired"], [AC["wired"]]),
            "wired portal": (70, 2, AC["wired"], [AC["wired"]]),
            "wifi 60 local": (50, 3, AC["wifi"], [AC["wifi"]]),
            "wired connecting": (40, 4, AC["wired"], [AC["wired"]]),
            "none": (20, 1, "/", []),
            "none disabled": (10, 1, "/", []),
            "wifi 40 ap2 vpn": (70, 4, AC["wifi"], [AC["wifi"], AC["vpn"]]),
            "ap2 wifi 40": (70, 4, AC["wifi"], [AC["wifi"]]),  # the words in another order
        }
        for words, (state, conn, primary, active) in expected.items():
            done = run(f"network-set.sh {words}")
            assert done.returncode == 0, done.stdout + done.stderr
            got = manager(address)
            assert (got["State"], got["Connectivity"], got["PrimaryConnection"]) == (
                state,
                conn,
                primary,
            ), words
            assert got["ActiveConnections"] == active, words
        done = run("network-set.sh wifi 33 ap2")
        assert done.returncode == 0
        wireless = asyncio.run(_get_all(address, DEV["wlan"], NM + ".Device.Wireless"))
        point = asyncio.run(_get_all(address, AP["two"], NM + ".AccessPoint"))
        assert wireless["ActiveAccessPoint"] == AP["two"] and point["Strength"] == 33
        run("network-set.sh wifioff")
        assert manager(address)["WirelessEnabled"] is False
        run("network-set.sh wifion")
        assert manager(address)["WirelessEnabled"] is True
    finally:
        fake.send_signal(signal.SIGTERM)
        fake.wait(10)
    assert not (tmp_path / "bus-address").exists()  # it cleans up its daemon and its address file
