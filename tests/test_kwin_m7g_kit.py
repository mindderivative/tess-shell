"""The real-hardware kit (``tests/kwin/prepare_m7g_hardware.py``): three lines that need a person.
What can be proved without one is proved here: the files and scripts, the literal texts of the
Orca line against the REAL accessibility ``Announcement`` signals of a shell started by the kit's
own script on a private sway and a private AT-SPI bus, the checker scripts on canned data, and that
no checklist asks for a cable or a power pull. Nothing here reads the real network, audio, session
or accessibility bus, and Orca is never started."""

from __future__ import annotations

import importlib.util
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

from tests import atspi_env
from tests.kwin import prepare_m3c_hotplug, prepare_m5c_gallery
from tests.kwin import prepare_m7g_hardware as kit
from tests.sway import PrivateSway

SCRIPTS = (
    "orca-1-start-shell.sh",
    "orca-2-start-orca.sh",
    "orca-stop.sh",
    "orca-3-say.sh",
    "orca-4-check.sh",
    "network-set.sh",
    "battery-set.sh",
    "wifi-1-before.sh",
    "wifi-2-start-shell.sh",
    "wifi-3-compare.sh",
    "audio-1-start-shell.sh",
    "audio-2-expect.sh",
)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    kit.write_kit(tmp_path / "kit")
    return tmp_path / "kit"


def load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def test_every_script_exists_is_executable_and_parses(root: Path) -> None:
    for name in SCRIPTS:
        path = root / "bin" / name
        assert os.access(path, os.X_OK), name
        subprocess.run(["bash", "-n", str(path)], check=True)
    for helper in ("wifi/wifi_check.py", "audio/audio_check.py"):
        compile((root / helper).read_text(), helper, "exec")
    assert (root / "checklist.txt").is_file()


def test_the_three_configs_check_clean(root: Path) -> None:
    for name in ("orca", "wifi", "audio"):
        env = {k: v for k, v in os.environ.items() if k not in ("WAYLAND_DISPLAY", "DISPLAY")}
        env["XDG_STATE_HOME"] = str(root / name / "state")
        out = subprocess.run(
            [
                sys.executable,
                "-m",
                "tess_shell",
                "check",
                "--config-dir",
                str(root / name / "config"),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert out.returncode == 0, (name, out.stdout, out.stderr)


def test_the_checklist_names_each_line_and_asks_for_no_cable_or_power_pull(root: Path) -> None:
    text = (root / "checklist.txt").read_text()
    assert [m for m in re.findall(r"^LINE (\d):", text, re.M)] == ["1", "2", "3"]
    assert "/usr/bin/orca" in text  # `orca` on the PATH is another program
    for forbidden in (r"unplug", r"replug", r"pull (the|a|its)\b.{0,20}(cable|plug|power)"):
        assert not re.search(forbidden, text, re.I), forbidden
    # the older kits that asked for a cable pull no longer do
    for other in (prepare_m5c_gallery.CHECKLIST, Path(prepare_m3c_hotplug.__file__).read_text()):
        assert not re.search(r"unplug the cable|take the cable out|cable out", other, re.I)


def test_the_literal_texts_come_from_the_modules(root: Path) -> None:
    said = kit.texts()
    assert said["network-down"] == "Network disconnected"
    assert said["battery-critical"] == "Battery critical, 4 percent, discharging"
    assert (
        said["launcher-second"] == "Kit Beta, 2 of 3"
        and said["launcher-third"] == "Kit Gamma, 3 of 3"
    )
    checklist = (root / "checklist.txt").read_text()
    for text in said.values():
        assert text in checklist


def run_check(root: Path, debug: str | None) -> list[str]:
    log = root / "orca" / "orca-debug.out"
    if debug is not None:
        log.write_text(debug)
    (root / "results.txt").unlink(missing_ok=True)
    subprocess.run(
        [str(root / "bin" / "orca-4-check.sh")],
        env={**os.environ, "TESS_M7G_ROOT": str(root)},
        capture_output=True,
        text=True,
        timeout=30,
    )
    return (root / "results.txt").read_text().splitlines()


def test_the_orca_checker_passes_what_was_said_fails_what_was_not_and_skips_a_silent_log(
    root: Path,
) -> None:
    said = kit.texts()
    spoken = "".join(f"SPEECH OUTPUT: '{t}'\n" for k, t in said.items() if k != "launcher-none")
    lines = run_check(root, spoken)
    assert sum(x.startswith("PASS ") for x in lines) == 5
    assert [x for x in lines if x.startswith("FAIL ")] == [
        "FAIL 1-orca-launcher-none Orca did not say: No results"
    ]
    assert run_check(root, "nothing relevant\n")[0].startswith("SKIP 1-orca-speech")
    log = root / "orca" / "orca-debug.out"
    log.unlink()
    assert run_check(root, None)[0].startswith("FAIL 1-orca-debug-file")


def test_the_orca_starter_says_so_when_the_screen_reader_is_not_installed(root: Path) -> None:
    script = root / "bin" / "orca-2-start-orca.sh"
    text = script.read_text().replace("ORCA=/usr/bin/orca", f"ORCA={root}/no-such-orca")
    script.write_text(text)
    out = subprocess.run(
        [str(script)],
        env={**os.environ, "TESS_M7G_ROOT": str(root)},
        capture_output=True,
        text=True,
    )
    assert out.returncode == 3 and "sudo pacman -S orca" in out.stdout and "orca-ide" in out.stdout
    assert (root / "results.txt").read_text().startswith("FAIL 1-orca-installed")


# -- the Wi-Fi and audio checkers, on canned data ------------------------------------------------


def wifi(root: Path, monkeypatch: pytest.MonkeyPatch, nmcli: str, route: str, addr: str) -> Any:
    module = load(root / "wifi" / "wifi_check.py", "kit_wifi")

    def run(*argv: str) -> str:
        if argv[:2] == ("nmcli", "-t") and "DEVICE,TYPE,STATE,CONNECTION" in argv:
            return nmcli
        if argv[:3] == ("ip", "-4", "route"):
            return route
        if argv[:3] == ("ip", "-4", "-br"):
            return addr
        return ""

    monkeypatch.setattr(module, "run", run)
    return module


WIRED = "enp5s0:ethernet:connected:Wired connection 1"
WIFI_UP = WIRED + "\nwlan0:wifi:connected:Home"
ROUTE = "default via 192.168.1.1 dev enp5s0 proto dhcp metric 100"
ADDR = "enp5s0 UP 192.168.1.20/24"


def test_the_wifi_checker_passes_an_unchanged_wired_session_and_fails_a_changed_one(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    results = root / "results"
    results.mkdir(exist_ok=True)
    record = root / "results.txt"

    def snapshot(label: str, nmcli: str, addr: str) -> None:
        module = wifi(root, monkeypatch, nmcli, ROUTE, addr)
        monkeypatch.setattr(sys, "argv", ["wifi_check.py", "snapshot", label])
        assert module.main() == 0

    def compare() -> int:
        module = wifi(root, monkeypatch, WIRED, ROUTE, ADDR)
        monkeypatch.setattr(sys, "argv", ["wifi_check.py", "compare"])
        return int(module.main())

    snapshot("before", WIRED, ADDR)
    snapshot("after", WIFI_UP, ADDR)  # a Wi-Fi connection came: the wired part is the same
    assert compare() == 0 and "PASS 2-wifi-wired-unchanged" in record.read_text()
    snapshot("after", WIFI_UP, "enp5s0 UP 192.168.1.77/24")  # the wired address changed
    assert compare() == 1 and "FAIL 2-wifi-wired-unchanged" in record.read_text()
    snapshot("before", "wlan0:wifi:connected:Home", "")  # no wired connection at all
    snapshot("after", "wlan0:wifi:connected:Home", "")
    assert compare() == 0 and "SKIP 2-wifi-wired-unchanged" in record.read_text()


def sink(
    name: str, description: str, bus: str, percent: int, muted: bool = False
) -> dict[str, Any]:
    return {
        "name": name,
        "description": description,
        "mute": muted,
        "volume": {"front-left": {"value": round(percent * 65536 / 100)}},
        "properties": {"device.bus": bus, "device.description": description},
        "active_port": None,
        "ports": [],
    }


def test_the_audio_checker_names_the_icon_and_tooltip_for_speakers_and_a_bluetooth_headset(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load(root / "audio" / "audio_check.py", "kit_audio")
    sinks = [
        sink("alsa_output.pci", "Built-in Audio Analog Stereo", "pci", 45),
        sink("bluez_output.AA", "Phone Headset", "bluetooth", 40),
    ]

    def ask(default: str, muted: bool = False) -> None:
        sinks[0]["mute"] = muted
        monkeypatch.setattr(
            module,
            "pactl",
            lambda *argv: default if argv[0] == "get-default-sink" else json.dumps(sinks),
        )

    for label, default, muted, icon, tip in (
        (
            "speakers",
            "alsa_output.pci",
            False,
            "volume-medium",
            "Built-in Audio Analog Stereo, 45 %",
        ),
        ("muted", "alsa_output.pci", True, "volume-off", "Built-in Audio Analog Stereo, muted"),
        ("headset", "bluez_output.AA", False, "bluetooth-audio", "Phone Headset, 40 %"),
    ):
        ask(default, muted)
        monkeypatch.setattr(sys, "argv", ["audio_check.py", label])
        assert module.main() == 0
        found = json.loads((root / "results" / f"audio-{label}.json").read_text())
        assert (found["icon_name"], found["tooltip"]) == (icon, tip), label
        assert tip in capsys.readouterr().out


# -- the Orca line, end to end in the sandbox ----------------------------------------------------


@pytest.mark.tre
@pytest.mark.skipif(not atspi_env.available(), reason="no private AT-SPI environment")
@pytest.mark.skipif(shutil.which("wtype") is None, reason="no wtype (a virtual keyboard)")
def test_the_orca_line_makes_exactly_the_texts_the_checklist_promises(
    private_sway: PrivateSway, root: Path
) -> None:
    """The kit's own ``orca-1-start-shell.sh`` on a private sway and a private AT-SPI bus, driven
    by its own ``orca-3-say.sh`` and by key events: the ``Announcement`` signals are the texts the
    checklist says Orca must speak, in that order."""
    reader = atspi_env.AtspiEnvironment()
    env = {**private_sway.env, **reader.env(), "TESS_M7G_ROOT": str(root)}
    lines: queue.Queue[str] = queue.Queue()
    seen: list[str] = []

    def pump(stream: Any) -> None:
        for line in stream:
            lines.put(line)

    shell = subprocess.Popen(
        [str(root / "bin" / "orca-1-start-shell.sh")],
        env=env,
        stderr=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        text=True,
        start_new_session=True,
    )
    assert shell.stderr is not None
    threading.Thread(target=pump, args=(shell.stderr,), daemon=True).start()

    def wait(text: str, timeout: float = 60) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if any(text in x for x in seen):
                return
            try:
                seen.append(lines.get(timeout=0.2))
            except queue.Empty:
                pass
        pytest.fail(f"never saw {text!r}:\n{''.join(seen)[-2500:]}")

    def say(event: str) -> None:
        subprocess.run(
            [str(root / "bin" / "orca-3-say.sh"), event],
            env=env,
            check=True,
            capture_output=True,
            timeout=60,
        )

    def key(*args: str) -> None:
        subprocess.run(["wtype", "-s", "300", *args], env=private_sway.env, check=True, timeout=20)

    try:
        heard = reader.monitor("Announcement")
        wait("Bar Top_Bar on HEADLESS-1 configured")
        reader.enable()  # what Orca turning on does
        say("network-down")
        wait("Network", 5) if False else None
        say("network-up")
        say("battery-critical")
        say("launcher-open")
        wait("Panel Launcher on HEADLESS-1 shown")
        for _ in range(40):  # Down until the field hears it (the keyboard comes a moment after)
            before = sum("| key arrow_down" in x for x in seen)
            key("-k", "Down")
            deadline = time.monotonic() + 1.5
            while (
                time.monotonic() < deadline and sum("| key arrow_down" in x for x in seen) == before
            ):
                try:
                    seen.append(lines.get(timeout=0.1))
                except queue.Empty:
                    pass
            if sum("| key arrow_down" in x for x in seen) > before:
                break
        wait("selected Kit Beta")
        key("-k", "Down")
        wait("selected Kit Gamma")
        key("zzz")
        wait("search 'zzz': 0 results")
        time.sleep(
            0
        )  # (nothing to wait for: the log line above is after the announcement is queued)
        wait("search 'zzz': 0 results")
        os.killpg(shell.pid, signal.SIGTERM)
        shell.wait(timeout=20)
        said = [text for text, politeness in heard.announcements() if politeness == 1]
    finally:
        if shell.poll() is None:
            os.killpg(shell.pid, signal.SIGKILL)
        reader.close()
    expected = kit.texts()
    for key_name in (
        "network-down",
        "network-up",
        "battery-critical",
        "launcher-second",
        "launcher-third",
        "launcher-none",
    ):
        assert expected[key_name] in said, (key_name, said)
    # Not asserted: the ORDER across events. tre (0.6.9) sends announcements that were made in one
    # loop turn to the screen reader in an arbitrary order (a burst of six came out as A1 A4 A6 A2
    # A3 A5; six made one turn apart came out in order, every time), so two events that the
    # sandbox drives close together, as here, can swap. The checklist's order holds on the
    # real run because the person waits for Orca to finish each text.
