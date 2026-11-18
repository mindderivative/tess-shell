"""Regenerate the real-hardware kit in /tmp/tess-kwin-m7g (not collected by pytest).

Run from the repo root, with the kit environment's python (a NON-editable install, so removing a
worktree cannot break the scripts): ``python tests/kwin/prepare_m7g_hardware.py``. It writes the
kit and starts nothing. Everything else is checked by the self-running kits in their sandboxes
(``run-all.sh`` of each kit); these three lines need a physical device or a real screen reader, so
they are the maintainer's, each written as exact steps (M7 Brief, M7g):

1. Orca: the real screen reader reads what the shell announces (Network, Battery critical, the
   Launcher's selected row). The shell runs on the real session with FAKE devices on a private
   system bus, so each event is one command; Orca's own debug file is what the checker reads.
2. Real Wi-Fi: join a Wi-Fi network while the wired connection stays up, then leave it, and check
   that the wired session did not change at all. Nothing in it takes the wired connection down.
3. Real audio: switch the output between the system speakers and a Bluetooth headset and change the
   volume; the checker prints what the Audio module must show for the output now selected.

No hot-plug line: a cable or power is never pulled (Risk Register R-33); multi-monitor and hot-plug
are tested on virtual outputs in the sandbox. Every script that changes something on the real
machine says so in its first lines, and none runs by itself: ``checklist.txt`` is the order.

The scripts write what they find to ``results/`` and one line each to ``results.txt``
(``PASS``, ``FAIL`` or ``SKIP`` and why), so nothing is copied from a terminal: the person who
runs them says "line 1 pass" or "line 2 fail" and the session reads the files.
"""

from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from pathlib import Path
from types import ModuleType

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.kwin import prepare_m5b_gallery as m5b  # noqa: E402
from tests.kwin import prepare_m5c_gallery as m5c  # noqa: E402
from tests.shell_samples import write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m7g")
BIN = Path(sys.executable).parent
SHIPPED = REPO / "src" / "tess_shell" / "shipped"
ORCA = "/usr/bin/orca"  # the screen reader; `orca` on the PATH may be another program
HEAD = "---\nTDL: 0.2\nName: Settings\n---\n"
KEY = "Ctrl+Alt+Shift+F9"  # only names the Launcher; no key is registered (Global_Shortcuts: false)

APPS = ("Kit Alpha", "Kit Beta", "Kit Gamma")  # an empty query lists them by name

BAR = """
Shell {{
    Monitor {{
        Name: Main
        Index: 0
        Children {{
            Bar {{
                Name: Top_Bar
                Edge: TOP
                Width: EXPAND
                Height: 36
                Style {{ Background: $color.surface }}
                Children {{
                    FlexBox {{
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Spacing: 12
                        Padding: [8, 4, 8, 4]
                        Align_Items: CENTER
                        Children {{ {uses} }}
                    }}
                }}
            }}
        }}
    }}
}}
"""


def module(name: str) -> ModuleType:
    """A shipped module's file, read as it is, so the literal texts below come from the code."""
    spec = importlib.util.spec_from_file_location(
        f"kit_{name}", SHIPPED / name / f"{name}_Module.py"
    )
    assert spec is not None and spec.loader is not None
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


def texts() -> dict[str, str]:
    """The literal words each event must make a screen reader say."""
    network, battery = module("Network"), module("Battery")
    return {
        "network-down": network.announcement_text("NONE", "DISCONNECTED", "", None),
        "network-up": network.announcement_text(
            "ETHERNET", "CONNECTED", "Wired connection 1", None
        ),
        "battery-critical": battery.announcement_text(4, "DISCHARGING"),
        "launcher-second": f"{APPS[1]}, 2 of {len(APPS)}",
        "launcher-third": f"{APPS[2]}, 3 of {len(APPS)}",
        "launcher-none": "No results",
    }


def settings(shortcuts: bool = False) -> str:
    extra = (
        f'  Global_Shortcuts: false\n  Shortcuts {{ Toggle_Launcher: "{KEY}" }}\n'
        if shortcuts
        else ""
    )
    return f"{HEAD}Settings {{\n  Logging {{ Level: DEBUG }}\n{extra}}}\n"


def entries(root: Path) -> dict[str, str]:
    out = {}
    for name in APPS:
        slug = name.lower().replace(" ", "-")
        out[f"{slug}.desktop"] = (
            f"[Desktop Entry]\nType=Application\nName={name}\nExec=/bin/true\nNoDisplay=false\n"
        )
    return out


def share_without_applications(share: Path) -> None:
    """A folder of links to everything the real ``XDG_DATA_DIRS`` hold EXCEPT their ``applications``
    folders. The graphics stack finds its drivers through ``XDG_DATA_DIRS`` (``vulkan/icd.d``), so the
    shell needs them; the Launcher must list only the three made-up applications."""
    real = os.environ.get("XDG_DATA_DIRS") or "/usr/local/share:/usr/share"
    shutil.rmtree(share, ignore_errors=True)
    share.mkdir(parents=True)
    for directory in (Path(d) for d in real.split(":") if d):
        if not directory.is_dir():
            continue
        for entry in directory.iterdir():
            link = share / entry.name
            if entry.name != "applications" and not link.exists() and not link.is_symlink():
                link.symlink_to(entry)
    assert not (share / "applications").exists()


def script(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("#!/usr/bin/env bash\n" + text)
    path.chmod(0o755)


COMMON = f"""ROOT=${{TESS_M7G_ROOT:-{ROOT}}}
BIN={BIN}
mkdir -p "$ROOT/results"
record() {{  # record PASS|FAIL|SKIP ID TEXT: one line in results.txt
  echo "$1 $2 $3" >> "$ROOT/results.txt"; echo "$1 $2 $3"
}}
"""


def write_orca(root: Path) -> None:
    said = texts()
    cfg = root / "orca" / "config"
    shutil.rmtree(root / "orca" / "config", ignore_errors=True)
    shutil.rmtree(root / "orca" / "data", ignore_errors=True)
    write_example(cfg, BAR.format(uses="Network { }  Battery { }  Clock { }"))
    (cfg / "settings.tdl").write_text(settings(shortcuts=True))
    apps = root / "orca" / "data" / "applications"
    apps.mkdir(parents=True)
    for name, body in entries(root).items():
        (apps / name).write_text(body)
    share_without_applications(root / "orca" / "share")
    fake = 'FAKE="$ROOT/orca/fake"\n'
    script(
        root / "bin" / "orca-1-start-shell.sh",
        "# Line 1, step 1. Starts the shell on YOUR session (a Bar on your top edge) with FAKE\n"
        "# NetworkManager and UPower on a PRIVATE system bus and a private list of three made-up\n"
        "# applications. It reads and writes nothing of your real network, battery or applications.\n"
        "# Leave it running; Ctrl+C stops it and the fakes.\n"
        + COMMON
        + fake
        + 'rm -rf "$FAKE"; mkdir -p "$FAKE"\n'
        + f'{BIN}/python {REPO}/tests/kwin/fake_hardware.py --root "$FAKE" &\n'
        + "FAKEPID=$!\n"
        + "trap 'kill \"$FAKEPID\" 2>/dev/null' EXIT\n"
        + 'for _ in $(seq 100); do [ -s "$FAKE/bus-address" ] && break; sleep 0.1; done\n'
        + '[ -s "$FAKE/bus-address" ] || { echo "the fakes did not start"; exit 1; }\n'
        + 'export DBUS_SYSTEM_BUS_ADDRESS=$(cat "$FAKE/bus-address")\n'
        + 'export XDG_STATE_HOME="$ROOT/orca/state" XDG_DATA_HOME="$ROOT/orca/data" XDG_DATA_DIRS="$ROOT/orca/data:$ROOT/orca/share"\n'
        + 'mkdir -p "$XDG_STATE_HOME"\n'
        + '"$BIN/tesserae-shell" run --config-dir "$ROOT/orca/config"\n',
    )
    script(
        root / "bin" / "orca-2-start-orca.sh",
        "# Line 1, step 2. Starts the Orca screen reader on YOUR session, with its debug file, so\n"
        "# that the checker can read what Orca said. Orca then reads your desktop aloud until\n"
        "# orca-stop.sh. Insert (or CapsLock) is Orca's own key; Insert+Q quits it too.\n"
        + COMMON
        + f"ORCA={ORCA}\n"
        + '[ -x "$ORCA" ] || {\n'
        '  record FAIL 1-orca-installed "the Orca screen reader is not at $ORCA. Install it first: sudo pacman -S orca. '
        '(The command `orca` on your PATH is another program, an AppImage called orca-ide, not the screen reader.)"\n'
        "  exit 3\n}\n"
        + 'rm -f "$ROOT/orca/orca-debug.out"\n'
        + 'nohup "$ORCA" --replace --debug-file="$ROOT/orca/orca-debug.out" >/dev/null 2>&1 &\n'
        + 'echo "Orca started (pid $!). Wait until it speaks, then go on with orca-3-say.sh."\n',
    )
    script(
        root / "bin" / "orca-stop.sh",
        "# Stops Orca (the one at /usr/bin/orca). Safe to run twice.\n"
        + COMMON
        + f"{ORCA} --quit 2>/dev/null || pkill -x orca\n"
        + 'echo "Orca stopped"\n',
    )
    nset = m5c.NETWORK_SET.replace(
        "ROOT=${TESS_M5C_ROOT:-/tmp/tess-kwin-m5c}",
        "ROOT=${TESS_M7G_ROOT:-" + str(ROOT) + "}/orca/fake",
    )
    bset = m5b.BATTERY_SET.replace(
        "ROOT=${TESS_M5B_ROOT:-/tmp/tess-kwin-m5b}",
        "ROOT=${TESS_M7G_ROOT:-" + str(ROOT) + "}/orca/fake",
    )
    assert nset != m5c.NETWORK_SET and bset != m5b.BATTERY_SET
    # the percentage first, the warning level last: the module announces a level that becomes
    # critical with the percentage it knows at that moment, and a real battery has the new
    # percentage already (the M5b script sets the warning level first)
    level, percent = "set_p WarningLevel u $LEVEL\n", 'set_p Percentage d "$PERCENT"\n'
    assert bset.count(level) == 1 and bset.count(percent) == 1
    bset = bset.replace(level, "").replace(percent, percent + level)
    script(root / "bin" / "network-set.sh", nset)
    script(root / "bin" / "battery-set.sh", bset)
    script(
        root / "bin" / "orca-3-say.sh",
        "# Line 1, step 3: ONE event for Orca to say. Changes the FAKE devices only.\n"
        "#   network-down | network-up | battery-critical | battery-normal | launcher-open | launcher-close\n"
        + COMMON
        + 'export XDG_STATE_HOME="$ROOT/orca/state"\n'
        + "case ${1:-} in\n"
        + '  network-down) "$ROOT/bin/network-set.sh" none ;;\n'
        + '  network-up) "$ROOT/bin/network-set.sh" wired ;;\n'
        + '  battery-critical) "$ROOT/bin/battery-set.sh" 4 discharging critical ;;\n'
        + '  battery-normal) "$ROOT/bin/battery-set.sh" 82 discharging ;;\n'
        + '  launcher-open) "$BIN/tesserae-shell" --config-dir "$ROOT/orca/config" show Launcher ;;\n'
        + '  launcher-close) "$BIN/tesserae-shell" --config-dir "$ROOT/orca/config" hide Launcher ;;\n'
        + '  *) echo "network-down | network-up | battery-critical | battery-normal | launcher-open | launcher-close"; exit 1 ;;\n'
        + "esac\n",
    )
    checks = "".join(
        f"check {key} {text!r}\n"
        for key, text in (
            ("network-down", said["network-down"]),
            ("network-up", said["network-up"]),
            ("battery-critical", said["battery-critical"]),
            ("launcher-second", said["launcher-second"]),
            ("launcher-third", said["launcher-third"]),
            ("launcher-none", said["launcher-none"]),
        )
    )
    script(
        root / "bin" / "orca-4-check.sh",
        "# Line 1, last step: reads Orca's debug file and records, for each text the shell announced,\n"
        "# whether Orca said it. Reads one file of this kit; changes nothing.\n"
        + COMMON
        + 'LOG="$ROOT/orca/orca-debug.out"\n'
        + '[ -s "$LOG" ] || { record FAIL 1-orca-debug-file "no Orca debug file at $LOG: Orca was not started with orca-2-start-orca.sh"; exit 1; }\n'
        + 'grep -qi "speech" "$LOG" || { record SKIP 1-orca-speech "Orca\'s debug file has no speech lines in this version: listen instead and say what you heard"; exit 0; }\n'
        + "check() {\n"
        '  if grep -qF -- "$2" "$LOG"; then record PASS "1-orca-$1" "$2"; else record FAIL "1-orca-$1" "Orca did not say: $2"; fi\n'
        "}\n" + checks,
    )


def write_wifi(root: Path) -> None:
    cfg = root / "wifi" / "config"
    shutil.rmtree(cfg, ignore_errors=True)
    write_example(cfg, BAR.format(uses="Network { }  Clock { }"))
    (cfg / "settings.tdl").write_text(settings())
    helper = root / "wifi" / "wifi_check.py"
    helper.write_text(WIFI_CHECK.replace("@ROOT@", str(root)))
    script(
        root / "bin" / "wifi-1-before.sh",
        "# Line 2, step 1. READ ONLY: writes what NetworkManager and the routes say now to\n"
        "# results/wifi-before.json. Changes nothing.\n"
        + COMMON
        + '"$BIN/python" "$ROOT/wifi/wifi_check.py" snapshot before\n',
    )
    script(
        root / "bin" / "wifi-2-start-shell.sh",
        "# Line 2, step 2. Starts the shell on YOUR session with a Network module. It READS your\n"
        "# NetworkManager and writes nothing. Ctrl+C stops it.\n"
        + COMMON
        + 'export XDG_STATE_HOME="$ROOT/wifi/state"; mkdir -p "$XDG_STATE_HOME"\n'
        + '"$BIN/tesserae-shell" run --config-dir "$ROOT/wifi/config"\n',
    )
    script(
        root / "bin" / "wifi-3-compare.sh",
        "# Line 2, last step. READ ONLY: takes the same snapshot as step 1 and records whether your\n"
        "# wired connection is exactly as before (device, connection, address, default route).\n"
        + COMMON
        + '"$BIN/python" "$ROOT/wifi/wifi_check.py" snapshot after\n'
        + '"$BIN/python" "$ROOT/wifi/wifi_check.py" compare\n',
    )


WIFI_CHECK = '''"""Snapshots of the wired session and the comparison (READ ONLY: nmcli and ip, no writes)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("@ROOT@")
RESULTS = ROOT / "results"


def run(*argv: str) -> str:
    out = subprocess.run(argv, capture_output=True, text=True, timeout=20)
    return out.stdout.strip()


def wired() -> dict[str, object]:
    devices = [
        line.split(":")
        for line in run("nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "device").splitlines()
    ]
    ethernet = [d for d in devices if len(d) >= 4 and d[1] == "ethernet" and d[2] == "connected"]
    names = [d[0] for d in ethernet]
    routes = [
        line
        for line in run("ip", "-4", "route", "show", "default").splitlines()
        if any(f" dev {n} " in line + " " for n in names)
    ]
    return {
        "devices": ethernet,
        "addresses": [run("ip", "-4", "-br", "addr", "show", "dev", n) for n in names],
        "default_routes": routes,
    }


def everything() -> dict[str, object]:
    return {
        "wired": wired(),
        "wifi_radio": run("nmcli", "radio", "wifi"),
        "active": run("nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"),
        "primary": run("nmcli", "-t", "-g", "GENERAL.CONNECTION", "device", "show"),
    }


def main() -> int:
    RESULTS.mkdir(parents=True, exist_ok=True)
    record = ROOT / "results.txt"

    def say(verdict: str, ident: str, text: str) -> None:
        with record.open("a") as f:
            f.write(f"{verdict} {ident} {text}\\n")
        print(verdict, ident, text)

    if sys.argv[1] == "snapshot":
        data = everything()
        (RESULTS / f"wifi-{sys.argv[2]}.json").write_text(json.dumps(data, indent=2))
        wired_now = data["wired"]
        assert isinstance(wired_now, dict)
        if not wired_now["devices"]:
            say("SKIP", f"2-wifi-{sys.argv[2]}", "no connected wired device: this line assumes your wired connection")
            return 0
        print("snapshot", sys.argv[2], "written; wired:", wired_now["devices"])
        return 0
    before = json.loads((RESULTS / "wifi-before.json").read_text())
    after = json.loads((RESULTS / "wifi-after.json").read_text())
    if not before["wired"]["devices"]:
        say("SKIP", "2-wifi-wired-unchanged", "there was no wired connection before: nothing to compare")
        return 0
    same = before["wired"] == after["wired"]
    say(
        "PASS" if same else "FAIL",
        "2-wifi-wired-unchanged",
        "the wired device, connection, address and default route are exactly as before"
        if same
        else "the wired session CHANGED: see results/wifi-before.json and results/wifi-after.json",
    )
    return 0 if same else 1


if __name__ == "__main__":
    raise SystemExit(main())
'''


def write_audio(root: Path) -> None:
    cfg = root / "audio" / "config"
    shutil.rmtree(cfg, ignore_errors=True)
    write_example(cfg, BAR.format(uses="Audio { show_slider: true }  Clock { }"))
    (cfg / "settings.tdl").write_text(settings())
    (root / "audio" / "audio_check.py").write_text(
        AUDIO_CHECK.replace("@ROOT@", str(root)).replace("@SHIPPED@", str(SHIPPED))
    )
    script(
        root / "bin" / "audio-1-start-shell.sh",
        "# Line 3, step 1. Starts the shell on YOUR session with an Audio module (icon and slider).\n"
        "# It reads PipeWire/PulseAudio; it changes the volume or the output only when YOU scroll,\n"
        "# click or drag on it. Ctrl+C stops it.\n"
        + COMMON
        + 'export XDG_STATE_HOME="$ROOT/audio/state"; mkdir -p "$XDG_STATE_HOME"\n'
        + '"$BIN/tesserae-shell" run --config-dir "$ROOT/audio/config"\n',
    )
    script(
        root / "bin" / "audio-2-expect.sh",
        "# Line 3, after each change of output or volume. READ ONLY: asks PulseAudio what the default\n"
        "# output is now and prints, with the shell's own functions, the icon and the tooltip the\n"
        "# Audio module must show for it. Usage: audio-2-expect.sh LABEL   (any word: speakers,\n"
        "# headset...). Writes results/audio-LABEL.json and one line in results.txt.\n"
        + COMMON
        + '"$BIN/python" "$ROOT/audio/audio_check.py" "${1:?a label, e.g. speakers or headset}"\n',
    )


AUDIO_CHECK = '''"""What the Audio module must show for the default output now (READ ONLY: pactl)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path("@ROOT@")
SHIPPED = Path("@SHIPPED@")


def pactl(*argv: str) -> str:
    return subprocess.run(["pactl", *argv], capture_output=True, text=True, timeout=20).stdout


def main() -> int:
    label = sys.argv[1]
    default = pactl("get-default-sink").strip()
    sinks = json.loads(pactl("--format=json", "list", "sinks") or "[]")
    sink = next((s for s in sinks if s.get("name") == default), None)
    record = ROOT / "results.txt"
    if sink is None:
        text = f"no default output found (pactl says {default!r})"
        record.open("a").write(f"FAIL 3-audio-{label} {text}\\n")
        print("FAIL", text)
        return 1
    from tess_shell.services.audio import output_kind

    spec = importlib.util.spec_from_file_location("kit_audio", SHIPPED / "Audio" / "Audio_Module.py")
    assert spec is not None and spec.loader is not None
    audio = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audio)
    props = sink.get("properties", {})
    active = sink.get("active_port")
    port_type = next((p.get("type", "") for p in sink.get("ports", []) if p.get("name") == active), "")
    volumes = [c["value"] for c in sink.get("volume", {}).values()]
    percent = round(sum(volumes) / len(volumes) * 100 / 65536) if volumes else 0
    muted = bool(sink.get("mute"))
    kind = output_kind(props, port_type)
    name = sink.get("description") or props.get("device.description") or sink["name"]
    icon = audio.level_icon(kind, percent, muted)
    tooltip = audio.tooltip_text(name, percent, muted)
    out = {"label": label, "sink": sink["name"], "kind": kind, "volume_percent": percent, "muted": muted,
           "icon_name": icon, "tooltip": tooltip, "bus": props.get("device.bus"),
           "form_factor": props.get("device.form_factor"), "port_type": port_type}
    (ROOT / "results" / f"audio-{label}.json").write_text(json.dumps(out, indent=2))
    print(f"The Audio module must show: icon '{icon}' (mdi), tooltip (point at it) exactly: {tooltip}")
    print(f"  kind {kind}; volume {percent} %; muted {muted}")
    record.open("a").write(f"SKIP 3-audio-{label} expected icon {icon}, tooltip: {tooltip} (what the module shows is read by a person)\\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


def checklist(root: Path) -> str:
    said = texts()
    return f"""Real-hardware kit ({root}). Three lines; nothing here pulls a cable or power.
Scripts: {root}/bin.  Each script writes to {root}/results and one line to {root}/results.txt.
The session reads those files: say only "line 1 pass", "line 2 fail" and what you saw.

Why these three need you: a screen reader and its real speech (1), a real Wi-Fi network and your
own wired session (2), real speakers and a Bluetooth headset (3). No session can be those.

LINE 1: Orca (the screen reader) reads the shell's announcements
  Before: Orca must be installed. `/usr/bin/orca --version` must print a version. If it does not:
  `sudo pacman -S orca`.  Careful: the command `orca` on your PATH is NOT the screen reader (it is
  the AppImage orca-ide); the scripts call /usr/bin/orca.
  Stop everything with Ctrl+C in each terminal and `{root}/bin/orca-stop.sh`.
  1. Terminal A:  {root}/bin/orca-1-start-shell.sh      (a Bar appears at the top edge; fake devices)
  2. Terminal B:  {root}/bin/orca-2-start-orca.sh       (Orca starts talking; wait until it is quiet)
  3. Terminal B, in this order, waiting until Orca has finished each time:
       {root}/bin/orca-3-say.sh network-down       Orca must say: {said["network-down"]}
       {root}/bin/orca-3-say.sh network-up         Orca must say: {said["network-up"]}
       {root}/bin/orca-3-say.sh battery-critical   Orca must say: {said["battery-critical"]}
       {root}/bin/orca-3-say.sh launcher-open      Orca says the dialog's name, "Launcher" (not checked)
     Then press the Down key ONCE on your keyboard:  Orca must say: {said["launcher-second"]}
     Press Down once more:                            Orca must say: {said["launcher-third"]}
     Type  zzz :                                      Orca must say: {said["launcher-none"]}
     Press Escape twice (clears, then closes the Launcher).
  4. Terminal B:  {root}/bin/orca-4-check.sh      (records PASS or FAIL for each text from Orca's own debug file)
  5. Stop: {root}/bin/orca-stop.sh, then Ctrl+C in terminal A.
  Pass: orca-4-check.sh printed PASS for every text. If it printed SKIP (this Orca's debug file has
  no speech lines), say what you heard for each of the six texts instead.

LINE 2: Real Wi-Fi, with your wired connection staying up (never taken down)
  What this checks: joining a Wi-Fi network and leaving it does not disturb the Network module or
  your wired session. It cannot show the Wi-Fi bars on your machine: with the cable in, wired stays
  the main connection and the module rightly keeps showing it; showing Wi-Fi as the main connection
  would mean taking the wired connection down, which this kit never does. The Wi-Fi states themselves
  are shown by the fake in the M5c kit (PART 2). A captive-portal network (a login page) is the same
  limit: only run it if you have one, and expect the module still to show the wired connection.
  1. {root}/bin/wifi-1-before.sh                (read only: saves your wired state)
  2. Terminal A:  {root}/bin/wifi-2-start-shell.sh   (a Bar with the Network module)
  3. Look at the Network module: the plug icon; point at it: the tooltip must read exactly
       "<your wired connection's name>, ethernet, connected"   (for a connection called
       Wired connection 1:  Wired connection 1, ethernet, connected).
  4. In Plasma's network applet join your Wi-Fi network (type the password if asked).
     The module must NOT change: still the plug icon, the same tooltip, no flicker.
  5. Wait one minute, then in the applet disconnect the Wi-Fi network (the wired one stays).
     The module must still not change.
  6. {root}/bin/wifi-3-compare.sh           (read only: records PASS if your wired connection is exactly
     as in step 1)
  7. Ctrl+C in terminal A.
  Pass: PASS 2-wifi-wired-unchanged, and the module did not change in steps 4 and 5.

LINE 3: Real audio: the system speakers and the Bluetooth headset
  1. Connect your Bluetooth headset in Plasma's applet, then make the SPEAKERS the output.
  2. Terminal A:  {root}/bin/audio-1-start-shell.sh      (a Bar with the Audio module and a slider)
  3. {root}/bin/audio-2-expect.sh speakers   prints the icon and the tooltip the module must show.
     Look at the module and point at it: the icon and the tooltip must be exactly what it printed.
  4. Scroll up on the module once: the volume goes up by one step; run audio-2-expect.sh speakers2
     again and look again: the tooltip's number follows. Click the module: it mutes, the icon
     becomes volume-off and the tooltip ends ", muted"; click again to unmute.
  5. In Plasma's applet make the BLUETOOTH HEADSET the output. Run {root}/bin/audio-2-expect.sh headset
     and look: icon bluetooth-audio (a Bluetooth glyph), tooltip exactly as printed (the
     headset's own name and its volume).  Change the volume with the slider: the tooltip follows.
  6. Switch back to the speakers (the module follows in a moment: the icon and tooltip are the
     speakers' again). Ctrl+C in terminal A.
  Pass: the icon and the tooltip matched what audio-2-expect.sh printed in each of the three
  states (speakers, headset, speakers again), and the module followed every switch.
"""


def write_kit(root: Path = ROOT) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "results").mkdir(exist_ok=True)
    (root / "results.txt").unlink(missing_ok=True)
    write_orca(root)
    write_wifi(root)
    write_audio(root)
    (root / "checklist.txt").write_text(checklist(root))


def main() -> None:
    write_kit()
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
