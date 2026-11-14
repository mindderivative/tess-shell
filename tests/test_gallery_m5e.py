"""The M5e KWin kit (``tests/kwin/prepare_m5e_gallery.py``): its config checks clean, the shell
starts it on a private sway with no error and no warning (with no sound server), and
the fake sound server and its helper scripts work: every ``audio-set.sh`` and ``audio-server.sh``
command line the checklist tells the maintainer to type is run, in order, against the real fake
server on a private socket (nothing here touches a real sound server: the fake's socket is under a
temporary folder, and the scripts talk to it only)."""

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

import pytest

from tess_shell.services.pulse_native import NORM, PulseClient
from tests.fake_dbus import wait_for
from tests.kwin import prepare_m5e_gallery as g
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
    numbers = [int(x[:2]) for x in entries()]
    assert numbers == [*range(1, 11), *range(11, 27)]
    assert "$color" not in g.CHECKLIST and "#" not in g.BODY  # theme tokens, never hex
    for light_dark in ("light", "dark"):
        assert light_dark in g.CHECKLIST


def test_part_1_says_plainly_what_it_changes_on_the_real_sound_server() -> None:
    text = g.CHECKLIST
    assert "THIS PART CHANGES YOUR REAL SOUND STATE" in text
    assert "write down" in text and "Line 9 puts them back" in text
    part1 = [x for x in entries() if int(x[:2]) <= 10]
    for line in part1:
        marked = "[reads only]" in line or "[CHANGES your real " in line
        assert marked, f"line without a mark: {line[:70]}"
    changes = {
        2: "volume",
        3: "mute",
        4: "mute",
        5: "volume",
        6: "volume",
        7: "default output",
        8: "microphone mute",
    }
    for number, what in changes.items():
        line = next(x for x in part1 if int(x[:2]) == number)
        assert f"[CHANGES your real {what}]" in line, number
    assert next(x for x in part1 if int(x[:2]) == 1).startswith(" 1  [reads only]")
    # part 2 never changes the real server, and the checklist says so
    assert "nothing here touches your real sound server" in text.replace("\n", " ").replace(
        "  ", " "
    )
    assert not any("[CHANGES" in x for x in entries() if int(x[:2]) >= 11)


def test_the_real_run_warns_and_the_fake_run_names_only_its_own_socket(tmp_path: Path) -> None:
    root = g.ROOT
    try:
        g.ROOT = tmp_path / "kit"
        g.CFG = g.ROOT / "gallery"
        g.main()
        run = (g.ROOT / "run.sh").read_text()
        fake = (g.ROOT / "run-fake.sh").read_text()
        assert "REAL sound server" in run and "[CHANGES" in run
        assert "PULSE_SERVER" not in run  # the real run follows the real environment
        assert 'export PULSE_SERVER="unix:$(cat "$ROOT/server-socket")"' in fake
        assert "unset PULSE_RUNTIME_PATH PULSE_COOKIE" in fake
        assert "pactl" not in run + fake and "wpctl" not in run + fake
        override = (g.ROOT / "run-override.sh").read_text()
        assert str(g.CFG_OVERRIDE) in override and str(g.CFG) + "\n" not in override
        assert "Name: Audio_Outputs" in (g.CFG_OVERRIDE / "Shells" / "Main_Shell.tdl").read_text()
        assert "Popup" not in (g.CFG / "Shells" / "Main_Shell.tdl").read_text()  # the shell's own
        for name in (
            "run.sh",
            "run-fake.sh",
            "run-override.sh",
            "check.sh",
            "audio-set.sh",
            "audio-server.sh",
        ):
            done = subprocess.run(
                ["bash", "-n", str(g.ROOT / name)], capture_output=True, text=True
            )
            assert done.returncode == 0, f"{name}: {done.stderr}"
        assert (g.ROOT / "checklist.txt").read_text() == g.CHECKLIST
    finally:
        g.ROOT, g.CFG = root, root / "gallery"


@pytest.mark.tre
def test_the_gallery_starts_on_a_private_sway_with_no_sound_server(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    g.write_gallery(tmp_path)
    shell = Shell(tmp_path, private_sway.env)  # no sound server: no socket in the private runtime
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


@pytest.mark.tre
def test_the_gallery_connects_to_the_fake_server_it_is_told_and_only_that(
    private_sway: PrivateSway, tmp_path: Path
) -> None:
    """The way run-fake.sh starts the shell: ``PULSE_SERVER`` names the fake's socket."""
    kit = Kit()
    try:
        assert wait_for(lambda: (kit.root / "server-socket").is_file() and kit.socket.exists(), 10)
        g.write_gallery(tmp_path)
        env = {**private_sway.env, "PULSE_SERVER": f"unix:{kit.socket}"}
        shell = Shell(tmp_path, env)
        try:
            shell.wait_for("audio: connected to the sound server")
            shell.wait_for("running")
            default, *_ = kit.snapshot()
            assert default == "fake_speakers"
            assert kit.run("audio-set.sh 20 mute").returncode == 0
            shell.process.send_signal(signal.SIGTERM)
            assert shell.finish() == 0
        finally:
            if shell.process.poll() is None:
                shell.process.kill()
        bad = [x for x in shell.seen if "| ERROR " in x or "| WARNING " in x]
        assert [x for x in bad if "the session bus is not reachable" not in x] == []
    finally:
        kit.close()


# -- the fake sound server and the helper scripts ------------------------------------------


class Kit:
    """The fake sound server process of the kit, with its scripts, on a short private path."""

    def __init__(self) -> None:
        self.root = Path(tempfile.mkdtemp(prefix="m5e-", dir="/tmp"))
        self.env = {"TESS_M5E_ROOT": str(self.root), "PATH": "/usr/bin:/bin"}
        for name, text in (
            ("audio-set.sh", g.audio_set_text()),
            ("audio-server.sh", g.AUDIO_SERVER),
        ):
            (self.root / name).write_text("#!/usr/bin/env bash\n" + text)
            (self.root / name).chmod(0o755)
        self.process = subprocess.Popen(
            [
                sys.executable,
                str(g.REPO / "tests" / "kwin" / "fake_pulse_server.py"),
                "--root",
                str(self.root),
            ],
            stdout=subprocess.PIPE,
            text=True,
        )

    @property
    def socket(self) -> Path:
        return Path((self.root / "server-socket").read_text())

    def run(self, line: str) -> subprocess.CompletedProcess[str]:
        script, *words = line.split()
        return subprocess.run(
            [str(self.root / script), *words],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def snapshot(self) -> tuple[str, str, dict[str, tuple[float, bool]], list[str], bool]:
        """(default sink, default source, {description: (percent, muted)}, outputs, mic muted)."""

        async def go() -> tuple[str, str, dict[str, tuple[float, bool]], list[str], bool]:
            client = PulseClient(self.socket)
            await client.connect()
            try:
                server, sinks, sources = await client.snapshot()
            finally:
                client.close()
            mic = next((s.mute for s in sources if s.name == "fake_mic"), False)
            state = {
                s.description: (round(sum(s.volume) / len(s.volume) * 100 / NORM, 1), s.mute)
                for s in sinks
            }
            return server.default_sink, server.default_source, state, [s.name for s in sinks], mic

        return asyncio.run(go())

    def close(self) -> None:
        self.process.send_signal(signal.SIGTERM)
        self.process.wait(10)
        shutil.rmtree(self.root, ignore_errors=True)


@pytest.fixture
def kit() -> Iterator[Kit]:
    k = Kit()
    try:
        assert wait_for(lambda: (k.root / "server-socket").is_file() and k.socket.exists(), 10)
        yield k
    finally:
        k.close()


def commands() -> list[str]:
    """Every ``audio-set.sh`` and ``audio-server.sh`` command line in the checklist, in order."""
    text = re.sub(r"\s+", " ", g.CHECKLIST)
    return re.findall(r"`(audio-(?:set|server)\.sh[^`]*)`", text)


REFUSED = (
    "audio-set.sh bogus",
    "audio-set.sh mute unmute",
    "audio-set.sh 150",
    "audio-set.sh headphones hdmi",
)


def test_the_checklist_has_the_command_lines_the_test_runs() -> None:
    found = commands()
    assert len(found) > 25 and all(r in found for r in REFUSED)
    assert "audio-server.sh away" in found and "audio-server.sh back" in found
    assert "audio-set.sh usb" in found  # refused while no USB DAC is plugged


def test_the_fake_server_and_every_checklist_command_work_on_a_private_socket(kit: Kit) -> None:
    assert "m5e-" in str(kit.socket) and str(kit.socket).startswith("/tmp/m5e-")
    default, source, sinks, names, mic = kit.snapshot()
    assert default == "fake_speakers" and source == "fake_mic" and not mic
    assert sinks["Speakers"] == (45.0, False) and sinks["Headphones"] == (60.0, False)
    assert names == ["fake_speakers", "fake_headphones", "fake_hdmi", "fake_bluetooth"]
    seen_away = False
    unplugged = False
    for line in commands():
        before = kit.snapshot() if line.startswith("audio-set") else None
        done = kit.run(line)
        if line in REFUSED or (line == "audio-set.sh usb" and unplugged):
            assert done.returncode != 0, f"{line}: {done.stdout}"
            assert (
                "unknown word" in done.stdout
                or "contradict" in done.stdout
                or ("a volume is" in done.stdout or "no output usb" in done.stdout)
            ), done.stdout
            assert kit.snapshot() == before, f"{line} changed something"
            continue
        assert done.returncode == 0, f"{line}: {done.stdout}{done.stderr}"
        if line == "audio-set.sh usbunplug":
            unplugged = True
        if line == "audio-set.sh usbplug" or line == "audio-set.sh usb usbplug":
            unplugged = False
        if line == "audio-server.sh away":
            seen_away = True
            assert wait_for(lambda: not kit.socket.exists(), 10)
        if line == "audio-server.sh back":
            assert wait_for(lambda: kit.socket.exists(), 10)
    assert seen_away and kit.socket.exists()


def test_the_words_map_to_what_the_server_reports_in_any_order(kit: Kit) -> None:
    def run(words: str) -> None:
        done = kit.run(f"audio-set.sh {words}")
        assert done.returncode == 0, done.stdout + done.stderr

    run("45 speakers unmute micunmute")
    default, _source, sinks, _names, mic = kit.snapshot()
    assert default == "fake_speakers" and sinks["Speakers"] == (45.0, False) and not mic
    run("mute 30 headphones")  # the default changes first, then the volume and the mute
    default, _source, sinks, _names, _mic = kit.snapshot()
    assert default == "fake_headphones" and sinks["Headphones"] == (30.0, True)
    assert sinks["Speakers"] == (45.0, False)  # the other output is not touched
    run("loud")
    assert kit.snapshot()[2]["Headphones"][0] == 130.0
    run("micmute")
    assert kit.snapshot()[4] is True
    run("usbplug")
    assert "fake_usb" in kit.snapshot()[3]
    run("usb")
    assert kit.snapshot()[0] == "fake_usb"
    run("balance speakers")
    state = kit.snapshot()[2]
    assert state["Speakers"][0] == 60.0  # the mean of 80 and 40
    run("nomic")
    default, source, _sinks, _names, _mic = kit.snapshot()
    assert source == "fake_speakers.monitor"  # no microphone: the server names a monitor
    run("mic")
    assert kit.snapshot()[1] == "fake_mic"
    run("usbunplug")
    assert "fake_usb" not in kit.snapshot()[3]
    log = (kit.root / "fake.log").read_text() if (kit.root / "fake.log").exists() else ""
    assert log == "" or "set_sink_volume" not in log  # nothing but the helper changed the fake
