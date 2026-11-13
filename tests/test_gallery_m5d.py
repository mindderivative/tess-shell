"""The M5d KWin kit (``tests/kwin/prepare_m5d_gallery.py``): its config checks clean, the shell
starts it on a private sway with no error and no warning, and the fake players and their helper
script work against a private bus: every ``media-set.sh`` command line the checklist tells the
maintainer to type is run, in order, against the real fake process with the real ``busctl``
(nothing here touches the real session or system bus or a real player)."""

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
from dbus_fast import Message, MessageType, Variant
from dbus_fast.aio import MessageBus

from tests.fake_dbus import HAVE_DAEMON, wait_for
from tests.fake_mpris import PATH, PLAYER, PREFIX
from tests.kwin import prepare_m5d_gallery as g
from tests.sway import PrivateSway
from tests.test_run import Shell

PROPS = "org.freedesktop.DBus.Properties"
NAMES = {
    "alpha": PREFIX + "alpha",
    "beta": PREFIX + "beta",
    "chrome": PREFIX + "chromium.instance1",
    "integration": PREFIX + "plasma-browser-integration",
}


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
    assert [int(x[:2]) for x in numbered] == [*range(1, 10), *range(11, 24)]
    assert "YOUR REAL PLAYER" in g.CHECKLIST and "private" in g.CHECKLIST
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
    assert [x for x in bad if "bus is not reachable" not in x] == []


# -- the fake players and the helper script -------------------------------------------------------


async def _call(
    address: str, destination: str, interface: str, member: str, sig: str, *body: Any
) -> Any:
    bus = await MessageBus(bus_address=address).connect()
    try:
        reply = await bus.call(
            Message(
                destination=destination,
                path=PATH,
                interface=interface,
                member=member,
                signature=sig,
                body=list(body),
            )
        )
        assert reply is not None and reply.message_type == MessageType.METHOD_RETURN, reply
        return reply.body
    finally:
        bus.disconnect()


def plain(value: Any) -> Any:
    """A ``Variant`` replaced by what it holds, at any depth."""
    if isinstance(value, Variant):
        return plain(value.value)
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [plain(v) for v in value]
    return value


def props(address: str, role: str) -> dict[str, Any]:
    body = asyncio.run(_call(address, NAMES[role], PROPS, "GetAll", "s", PLAYER))
    return {k: plain(v) for k, v in body[0].items()}


def present(address: str, role: str) -> bool:
    return bool(asyncio.run(_bus_call(address, "NameHasOwner", "s", NAMES[role]))[0])


async def _bus_call(address: str, member: str, sig: str, *body: Any) -> Any:
    bus = await MessageBus(bus_address=address).connect()
    try:
        reply = await bus.call(
            Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member=member,
                signature=sig,
                body=list(body),
            )
        )
        assert reply is not None
        return reply.body
    finally:
        bus.disconnect()


def commands() -> list[str]:
    """Every ``media-set.sh`` command line in the checklist, in order."""
    text = re.sub(r"\s+", " ", g.CHECKLIST)
    return re.findall(r"`(media-set\.sh[^`]*)`", text)


REFUSED = ("media-set.sh bogus", "media-set.sh alpha beta", "media-set.sh playing paused")


def test_the_checklist_has_the_command_lines_the_test_runs() -> None:
    found = commands()
    assert len(found) > 30 and all(r in found for r in REFUSED), found
    assert "media-set.sh alpha away" in found and "media-set.sh beta back" in found


@pytest.mark.skipif(
    not HAVE_DAEMON or shutil.which("busctl") is None, reason="needs dbus-daemon and busctl"
)
def test_the_fake_players_and_every_checklist_command_work_on_a_private_bus(tmp_path: Path) -> None:
    fake = subprocess.Popen(
        [sys.executable, str(g.REPO / "tests" / "kwin" / "fake_mpris.py"), "--root", str(tmp_path)],
        stdout=subprocess.PIPE,
        text=True,
    )
    try:
        assert wait_for(lambda: (tmp_path / "bus-address").is_file(), 10)
        address = (tmp_path / "bus-address").read_text()
        assert "tess-bus-" in address  # its own temporary daemon, not a real bus
        assert (tmp_path / "cover.png").is_file()
        env = {"TESS_M5D_ROOT": str(tmp_path), "PATH": "/usr/bin:/bin"}
        script = tmp_path / "media-set.sh"
        script.write_text("#!/usr/bin/env bash\n" + g.MEDIA_SET)
        script.chmod(0o755)

        def run(line: str) -> subprocess.CompletedProcess[str]:
            _, *words = line.split()
            return subprocess.run(
                [str(script), *words], env=env, capture_output=True, text=True, timeout=30
            )

        start = props(address, "alpha")
        assert (start["PlaybackStatus"], start["CanGoNext"]) == ("Playing", True)
        assert props(address, "beta")["PlaybackStatus"] == "Paused"
        assert present(address, "alpha") and not present(address, "chrome")

        for line in commands():
            done = run(line)
            if line in REFUSED:
                assert done.returncode != 0, line
                assert (
                    "unknown word" in done.stdout
                    or "one player" in done.stdout
                    or "two things" in done.stdout
                )
                continue
            assert done.returncode == 0, f"{line}: {done.stdout}{done.stderr}"

        def say(words: str) -> None:
            done = run(f"media-set.sh {words}")
            assert done.returncode == 0, f"{words}: {done.stdout}{done.stderr}"

        # the words, in any order, do what they say
        say("alpha back")
        say("playing seek control alpha next previous art track1 normal")
        a = props(address, "alpha")
        assert (a["PlaybackStatus"], a["CanSeek"], a["CanControl"], a["Rate"]) == (
            "Playing",
            True,
            True,
            1.0,
        )
        say("paused nonext beta")
        b = props(address, "beta")
        assert (b["PlaybackStatus"], b["CanGoNext"]) == ("Paused", False)
        say("beta next playing")
        assert props(address, "beta")["CanGoNext"] is True
        assert props(address, "beta")["PlaybackStatus"] == "Playing"
        say("alpha notitle fast")
        a = props(address, "alpha")
        assert "xesam:title" not in a["Metadata"] and a["Rate"] == 2.0
        say("track2 httpart alpha")
        meta = props(address, "alpha")["Metadata"]
        assert meta["xesam:title"].startswith("Second Song")
        assert meta["mpris:artUrl"].startswith("https://")
        say("120 alpha")
        assert props(address, "alpha")["Position"] == 120_000_000
        say("chrome back")
        assert present(address, "chrome")
        say("chrome away")
        assert not present(address, "chrome")
        # the fake players behave like real ones: a control call moves their own state
        before = props(address, "beta")["PlaybackStatus"]
        asyncio.run(_call(address, NAMES["beta"], PLAYER, "PlayPause", ""))
        assert wait_for(lambda: props(address, "beta")["PlaybackStatus"] != before, 3)
        asyncio.run(_call(address, NAMES["beta"], PLAYER, "Next", ""))
        title = props(address, "beta")["Metadata"].get("xesam:title")
        asyncio.run(_call(address, NAMES["beta"], PLAYER, "Next", ""))
        assert props(address, "beta")["Metadata"].get("xesam:title") != title
        track = props(address, "beta")["Metadata"]["mpris:trackid"]
        asyncio.run(_call(address, NAMES["beta"], PLAYER, "SetPosition", "ox", track, 5_000_000))
        assert wait_for(lambda: props(address, "beta")["Position"] == 5_000_000, 3)
    finally:
        fake.send_signal(signal.SIGTERM)
        fake.wait(10)
    assert not (tmp_path / "bus-address").exists()  # it cleans up its daemon and its address file
