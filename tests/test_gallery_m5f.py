"""The M5f KWin kit (``tests/kwin/prepare_m5f_gallery.py``): its config checks clean, the shell
starts it on a private sway against the kit's fake watcher and items with no error and no warning,
and the fakes and ``tray-set.sh`` work: every ``tray-set.sh`` command line the checklist tells the
maintainer to type is run, in order, against the real fakes on a private session bus (nothing here
touches the real session bus, a real watcher or a real item: the fakes' bus is a daemon of their own
in a temporary folder, and the scripts talk to it only)."""

from __future__ import annotations

import asyncio
import re
import shutil
import signal
import subprocess
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from dbus_fast import Message, MessageType
from dbus_fast.aio import MessageBus

from tests.fake_dbus import wait_for
from tests.kwin import prepare_m5f_gallery as g
from tests.sway import PrivateSway
from tests.test_run import Shell


@pytest.mark.parametrize("body", ["BODY", "BODY_OVERRIDE"])
def test_the_gallery_files_check_clean(tmp_path: Path, body: str) -> None:
    g.write_gallery(tmp_path, getattr(g, body))
    done = subprocess.run(
        [sys.executable, "-m", "tess_shell", "check", "--config-dir", str(tmp_path)],
        capture_output=True,
        text=True,
        env={"XDG_STATE_HOME": str(tmp_path / "state"), "PATH": "/usr/bin:/bin"},
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "error" not in (done.stdout + done.stderr).replace("no error", "")


def entries() -> list[str]:
    """The numbered entries of the checklist, each with its continuation lines."""
    out: list[str] = []
    for line in g.CHECKLIST.splitlines():
        if line[:2].strip().isdigit() and line[2:3] == " ":
            out.append(line)
        elif out and line.startswith("    "):
            out[-1] += " " + line.strip()
    return out


def test_the_checklist_numbers_every_line_in_one_list() -> None:
    assert [int(x[:2]) for x in entries()] == list(range(1, 31))
    assert "$color" not in g.CHECKLIST and "#" not in g.BODY  # theme tokens, never hex
    for light_dark in ("light", "dark"):
        assert light_dark in g.CHECKLIST


def test_part_1_says_plainly_which_lines_act_on_real_items_and_menus() -> None:
    text = g.CHECKLIST
    assert "THIS PART CALLS YOUR REAL APPLICATIONS" in text
    assert "do NOT click that entry" in text and "SECOND tray host" in text
    part1 = [x for x in entries() if int(x[:2]) <= 10]
    for line in part1:
        marks = ("[reads only]", "[ACTS on a real item]", "[ACTS through a real menu]")
        assert any(m in line for m in marks), f"line without a mark: {line[:70]}"
    acts = {3: "[ACTS on a real item]", 4: "[ACTS on a real item]", 6: "[ACTS through a real menu]"}
    for number, mark in acts.items():
        assert mark in next(x for x in part1 if int(x[:2]) == number), number
    assert next(x for x in part1 if int(x[:2]) == 1).startswith(" 1  [reads only]")
    flat = " ".join(text.split())
    assert "nothing here touches your real session bus or your real tray items" in flat
    assert not any("[ACTS" in x for x in entries() if int(x[:2]) >= 11)


def test_the_real_run_warns_and_the_fake_run_names_only_its_own_bus(tmp_path: Path) -> None:
    root = g.ROOT
    try:
        g.ROOT = tmp_path / "kit"
        g.CFG = g.ROOT / "gallery"
        g.main()
        run = (g.ROOT / "run.sh").read_text()
        fake = (g.ROOT / "run-fake.sh").read_text()
        assert "REAL session bus" in run and "[ACTS" in run
        assert "DBUS_SESSION_BUS_ADDRESS" not in run  # the real run follows the real environment
        assert 'export DBUS_SESSION_BUS_ADDRESS=$(cat "$ROOT/bus-address")' in fake
        override = (g.ROOT / "run-override.sh").read_text()
        assert str(g.CFG_OVERRIDE) in override and str(g.CFG) + "\n" not in override
        assert "Name: Tray_Menu" in (g.CFG_OVERRIDE / "Shells" / "Main_Shell.tdl").read_text()
        assert "Popup" not in (g.CFG / "Shells" / "Main_Shell.tdl").read_text()  # the shell's own
        for name in ("run.sh", "run-fake.sh", "run-override.sh", "check.sh", "tray-set.sh"):
            done = subprocess.run(
                ["bash", "-n", str(g.ROOT / name)], capture_output=True, text=True
            )
            assert done.returncode == 0, f"{name}: {done.stderr}"
        assert (g.ROOT / "checklist.txt").read_text() == g.CHECKLIST
    finally:
        g.ROOT, g.CFG = root, root / "gallery"


# -- the fakes and the helper script -----------------------------------------------------------


class Kit:
    """The fake watcher and items of the kit, with ``tray-set.sh``, on a short private path."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="m5f-", dir="/tmp"))
        self.env = {"TESS_M5F_ROOT": str(self.root), "PATH": "/usr/bin:/bin"}
        (self.root / "tray-set.sh").write_text("#!/usr/bin/env bash\n" + g.TRAY_SET)
        (self.root / "tray-set.sh").chmod(0o755)
        self.process = subprocess.Popen(
            [
                sys.executable,
                str(g.REPO / "tests" / "kwin" / "fake_tray.py"),
                "--root",
                str(self.root),
            ],
            stdout=subprocess.PIPE,
            text=True,
        )

    @property
    def address(self) -> str:
        return (self.root / "bus-address").read_text()

    @property
    def log(self) -> list[str]:
        return (self.root / "fake.log").read_text().splitlines()

    def run(self, line: str) -> subprocess.CompletedProcess[str]:
        script, *words = line.split()
        return subprocess.run(
            [str(self.root / script), *words],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def snapshot(self) -> dict[str, Any]:
        """What the fakes say now: the watcher's list and each listed item's status, title, icon
        and tooltip (read from the kit's private bus)."""

        async def ask(
            conn: MessageBus, name: str, path: str, interface: str
        ) -> dict[str, Any] | None:
            reply = await conn.call(
                Message(
                    destination=name,
                    path=path,
                    interface="org.freedesktop.DBus.Properties",
                    member="GetAll",
                    signature="s",
                    body=[interface],
                )
            )
            if reply is None or reply.message_type != MessageType.METHOD_RETURN:
                return None
            return {k: v.value for k, v in reply.body[0].items()}

        async def go() -> dict[str, Any]:
            conn = await MessageBus(bus_address=self.address).connect()
            try:
                watcher = await ask(
                    conn,
                    "org.kde.StatusNotifierWatcher",
                    "/StatusNotifierWatcher",
                    "org.kde.StatusNotifierWatcher",
                )
                out: dict[str, Any] = {
                    "watcher": None if watcher is None else watcher["RegisteredStatusNotifierItems"]
                }
                for role in ("mail", "chat", "sync", "update", "ghost"):
                    n = ("mail", "chat", "sync", "update", "ghost").index(role) + 1
                    props = await ask(
                        conn,
                        f"org.kde.StatusNotifierItem-{n}-1",
                        "/StatusNotifierItem",
                        "org.kde.StatusNotifierItem",
                    )
                    out[role] = (
                        None
                        if props is None
                        else (props["Status"], props["Title"], props["IconName"], props["ToolTip"])
                    )
                return out
            finally:
                conn.disconnect()

        return asyncio.run(go())

    def close(self) -> None:
        self.process.send_signal(signal.SIGTERM)
        self.process.wait(10)
        shutil.rmtree(self.root, ignore_errors=True)


@pytest.fixture
def kit() -> Iterator[Kit]:
    k = Kit()
    try:
        assert wait_for(lambda: (k.root / "bus-address").is_file(), 10)
        yield k
    finally:
        k.close()


def commands() -> list[str]:
    """Every ``tray-set.sh`` command line in the checklist, in order."""
    text = re.sub(r"\s+", " ", g.CHECKLIST)
    return re.findall(r"`(tray-set\.sh[^`]*)`", text)


REFUSED = (
    "tray-set.sh bogus",
    "tray-set.sh mail chat",
    "tray-set.sh active passive",
    "tray-set.sh away back",
)


def test_the_checklist_has_the_command_lines_the_test_runs() -> None:
    found = commands()
    assert len(found) > 18 and all(r in found for r in REFUSED)
    for needed in ("nowatcher", "watcher", "restart", "relabel", "sync attention"):
        assert any(needed in line.split()[1:] for line in found) or any(
            needed in line for line in found
        ), needed


def test_the_fakes_start_as_the_checklist_says_and_every_command_line_works(kit: Kit) -> None:
    start = kit.snapshot()
    assert len(start["watcher"]) == 5 and start["ghost"][0] == "Passive"
    assert start["mail"][2] == "mail-unread" and start["sync"][0] == "Active"
    for line in commands():
        before = kit.snapshot()
        done = kit.run(line)
        if line in REFUSED:
            assert done.returncode != 0, f"{line}: {done.stdout}"
            assert (
                "unknown word" in done.stdout
                or "say two things" in done.stdout
                or ("one item at a time" in done.stdout)
            ), done.stdout
            assert kit.snapshot() == before, f"{line} changed something"
            continue
        assert done.returncode == 0, f"{line}: {done.stdout}{done.stderr}"


def test_the_words_change_what_the_fakes_report_in_any_order(kit: Kit) -> None:
    def run(words: str) -> None:
        done = kit.run(f"tray-set.sh {words}")
        assert done.returncode == 0, done.stdout + done.stderr

    run("attention sync")  # the item word may come after
    assert kit.snapshot()["sync"][0] == "NeedsAttention"
    run("active sync")
    run("passive ghost retitle")
    snap = kit.snapshot()
    assert snap["ghost"][:2] == ("Passive", "Renamed") and snap["sync"][0] == "Active"
    run("swap chat")
    assert kit.snapshot()["chat"][2] == "tess-swap-a"  # the first swap: the green A
    run("chat swap")
    assert kit.snapshot()["chat"][2] == "tess-swap-b"  # the second: the purple B
    run("away update")
    assert kit.snapshot()["update"] is None  # off the bus: nothing answers
    run("update back")
    assert kit.snapshot()["update"] is not None
    run("unregister mail")
    assert not any(
        s.startswith("org.kde.StatusNotifierItem-1-1") for s in kit.snapshot()["watcher"]
    )
    run("register mail")
    assert kit.snapshot()["watcher"][-1].startswith("org.kde.StatusNotifierItem-1-1")
    run("nowatcher")
    assert wait_for(lambda: kit.snapshot()["watcher"] is None, 5)
    run("watcher")
    assert wait_for(lambda: kit.snapshot()["watcher"] is not None, 5)


# -- the shell on the kit's bus ------------------------------------------------------------------


@pytest.mark.tre
def test_the_gallery_starts_on_a_private_sway_against_the_fakes_and_follows_the_script(
    private_sway: PrivateSway, tmp_path: Path, kit: Kit
) -> None:
    """The way run-fake.sh starts the shell: ``DBUS_SESSION_BUS_ADDRESS`` names the fakes' bus."""
    g.write_gallery(tmp_path)
    env = {**private_sway.env, "DBUS_SESSION_BUS_ADDRESS": kit.address}
    shell = Shell(tmp_path, env)
    try:
        shell.wait_for("Bar Top_Bar on HEADLESS-1 configured")
        shell.wait_for("running")
        pid = shell.process.pid
        host = f"watcher RegisterStatusNotifierHost org.kde.StatusNotifierHost-{pid}"
        assert wait_for(lambda: sum(host in x for x in kit.log) == 1, 10), kit.log
        for words in (
            "sync attention",
            "chat away",
            "chat back",
            "mail unregister",
            "mail register",
        ):
            assert kit.run(f"tray-set.sh {words}").returncode == 0
        assert kit.run("tray-set.sh restart").returncode == 0
        assert wait_for(lambda: sum(host in x for x in kit.log) == 2, 10), kit.log
        shell.process.send_signal(signal.SIGTERM)
        assert shell.finish() == 0
    finally:
        if shell.process.poll() is None:
            shell.process.kill()
    bad = [x for x in shell.seen if "| ERROR " in x or "| WARNING " in x]
    allowed = (
        "the system bus is not reachable",
        "StatusNotifierWatcher left the session bus",
        "the Settings portal is not available",  # the fakes' bus has none
        "ms on the loop",  # machine load, not the kit
        "ms on the service thread",
    )
    assert [x for x in bad if not any(a in x for a in allowed)] == [], bad
