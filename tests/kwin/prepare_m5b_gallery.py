"""Regenerate the M5b Battery and Workspaces KWin check in /tmp/tess-kwin-m5b (not collected by
pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m5b_gallery.py``. It writes a scratch
config and scripts under ``/tmp/tess-kwin-m5b`` and starts nothing. The Bar shows two Workspaces
(names and numbers), two Batteries (with and without the number) and the Clock, all coloured by theme
tokens, so it follows Plasma's light and dark.

* ``run.sh``: the shell on your real session bus and real system bus. Workspaces reads KWin; **a
  click on a button writes KWin's ``current`` (it switches your real desktop)**. The Battery reads
  UPower, which on this desktop has no battery: it must stay hidden.
* ``run-battery-fake.sh``: the shell on your real session bus (Workspaces) and a PRIVATE system bus
  with a fake UPower (``tests/kwin/fake_upower.py``), so every Battery state can be shown.
  ``battery-set.sh PERCENT STATE [present|absent] [normal|low|critical]`` changes it and
  ``battery-upower.sh away|back`` makes the fake UPower leave and return.
* ``check.sh``: ``tesserae-shell check`` on the config.
* ``checklist.txt``: every line to check, in one list.

The state directory is ``/tmp/tess-kwin-m5b/state``, never the real one. Nothing here changes the
real desktop except the Workspaces click named above.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.shell_samples import write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m5b")
CFG = ROOT / "gallery"
BIN = Path.home() / "Projects/pyDev/pyEnvs/tess-shell/bin"
SETTINGS = (
    "---\nTDL: 0.1\nName: Settings\n---\nSettings {\n  Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default], Follow_Desktop: true }\n}\n"
)

BODY = """
Shell {
    Monitor {
        Name: Main
        Index: 0
        Children {
            Bar {
                Name: Top_Bar
                Edge: TOP
                Width: EXPAND
                Height: 36
                Style { Background: $color.surface }
                Children {
                    FlexBox {
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Spacing: 16
                        Padding: [8, 4, 8, 4]
                        Align_Items: CENTER
                        Children {
                            Workspaces { }
                            Workspaces { label: number }
                            Spacer { }
                            Battery { }
                            Battery { show_percent: false }
                            Clock { }
                        }
                    }
                }
            }
        }
    }
}
"""

CHECKLIST = """M5b Battery and Workspaces: one list, every line to run.  Do it in light and in dark
(Plasma's colour scheme; every colour is a theme token).  The Bar shows, from the left: Workspaces
with names, Workspaces with numbers, then at the right Battery with the number, Battery with the
icon only, and the Clock.

PART 1: on this desktop, real buses  (start with /tmp/tess-kwin-m5b/run.sh)
Reads your real session bus and real system bus.  ONLY line 5 writes anything: it switches your
real virtual desktop.

 1  Battery: no battery here, so neither Battery shows: no icon, no placeholder, and
    no gap where they would be: the Clock is 16 px (the Bar's Spacing) from the Workspaces, not 48.
    The log has no WARNING or ERROR line about the Battery or UPower
    (`grep -E "WARNING|ERROR"` on the shell's output; the `dbus: org.freedesktop.UPower.PowerProfiles`
    line, if you see it, is DEBUG).
 2  Workspaces with names: one button per virtual desktop, in KWin's order, labelled with each
    desktop's name; the current desktop's button is raised and outlined in the primary colour.
 3  Workspaces with numbers: the same buttons labelled 1, 2, 3 ...; the same one is marked.
 4  Switch desktop with the keyboard (Ctrl+F2 or your shortcut) and with Plasma's pager: the mark
    moves to the new desktop in both rows within a frame, the old one loses it.  No flicker of the
    other buttons.
 5  Click a desktop that is not the current one, in the names row: KWin switches to that desktop,
    and the mark follows.  Click the current one: nothing happens.  Click one in the numbers row:
    the same.  (This writes KWin's `current`: your real desktop changes.)
 6  Point at a button: its background lightens (a hover look); the pointer leaves: it goes back.
 7  System Settings, Virtual Desktops: rename a desktop: only that button's text changes, in both
    rows (an empty name shows its number in the names row).  Add a desktop: a button appears at the
    end of both rows and nothing else moves.  Remove a desktop: its button goes, the others stay.
 8  Move the mouse over each Workspaces button: the cursor is the normal arrow (the buttons are
    not text).
 9  Log: no ERROR line after all of the above; the only WARNING allowed is none.
10  OPTIONAL, disruptive, skip it if you do not want to risk your session: restart KWin.  The
    Workspaces rows disappear while it is gone, one `dbus: org.kde.KWin left the session bus`
    WARNING appears, and when KWin is back they return with the current desktop marked, with no
    shell restart.  (The fake-service test covers this; do it only if you want the real thing.)

PART 2: fake battery on a private system bus  (stop part 1; start /tmp/tess-kwin-m5b/run-battery-fake.sh;
in a second terminal use /tmp/tess-kwin-m5b/battery-set.sh)
The fake UPower is on its own private bus: nothing here touches your real system bus.  The
Workspaces still read your real KWin (the same reads as part 1; do not click for this part).

11  At start the fake says 82 %, discharging: both Batteries show the 80 % icon (a battery drawn
    four fifths full); the first also shows "82 %".  Point at either Battery: a tooltip opens with
    "82 %, discharging, 2 h 13 min left" (about).
12  `battery-set.sh 82 charging`: the icon changes to the charging one (a bolt), within a frame; the
    tooltip reads "82 %, charging, ... until full".
13  `battery-set.sh 100 full`: the plain full battery, the tooltip "100 %, fully charged".
14  `battery-set.sh 55 discharging`: the 50 % icon and "55 %".  `battery-set.sh 24 discharging`:
    the 20 % icon.  `battery-set.sh 9 discharging`: the alert icon (an exclamation mark).
15  `battery-set.sh 15 discharging low`: the number is the theme's warning colour (amber) and the
    icon is amber, and a round amber dot sits right of the battery drawing (the dot is part of the
    icon's own picture); the icon-only Battery shows the amber icon with the dot too, and its
    tooltip still opens when you point at it.  (If the icon is missing here: run the probe
    /tmp/tess-kwin-m5b-dot/run.sh and report which letters lose the icon.)
16  `battery-set.sh 5 discharging critical`: the number, the icon and the dot are the error colour
    (red-ish); the icon is the alert one.  `battery-set.sh 15 discharging low` again: back to amber.
    `battery-set.sh 60 discharging`: no dot, normal colour, the icon is drawn.
17  `battery-set.sh 0 empty`: the outlined alert battery, "0 %, empty".
18  `battery-set.sh 0 unknown absent`: both Batteries vanish with no placeholder and no gap (as in
    line 1; the Clock moves right by the Batteries' width and the Spacing beside them).  `battery-set.sh 64 discharging present`: they come back.
19  `battery-upower.sh away`: both Batteries vanish and exactly one WARNING appears in the log
    (`dbus: org.freedesktop.UPower left the system bus`).  `battery-upower.sh back`: they return
    at once with the value they had.  Run `away` and `back` a second time inside a minute: still
    one warning.
20  Change the number 5 times quickly with `battery-set.sh`: no flicker of the Clock or the
    Workspaces, and `top -p $(pgrep -f 'tesserae-shell run')` shows the shell idle (0 % CPU)
    when you stop.
21  Log: no ERROR line; the only WARNING is the one of line 19.
"""


def script(name: str, text: str) -> None:
    path = ROOT / name
    path.write_text("#!/usr/bin/env bash\n" + text)
    path.chmod(0o755)


def write_gallery(cfg: Path) -> None:
    shutil.rmtree(cfg, ignore_errors=True)
    write_example(cfg, BODY)
    (cfg / "settings.tdl").write_text(SETTINGS)


BATTERY_SET = """# battery-set.sh PERCENT STATE [present|absent] [normal|low|critical]  (the last two in any order)
# STATE: charging, discharging, full, empty, unknown.  Talks to the fake UPower only.
ROOT=${TESS_M5B_ROOT:-/tmp/tess-kwin-m5b}
ADDR=$(cat "$ROOT/bus-address" 2>/dev/null) || { echo "run-battery-fake.sh is not running"; exit 1; }
PERCENT=${1:?percent}
STATE=${2:?state}
PRESENT=present
WARNING=normal
shift 2
for word in "$@"; do  # the rest, in any order: present|absent and normal|low|critical
  case $word in
    present|absent) PRESENT=$word ;;
    normal|low|critical) WARNING=$word ;;
    *) echo "after the state: present, absent, normal, low or critical (not '$word')"; exit 1 ;;
  esac
done
case $STATE in
  unknown) CODE=0 ;; charging) CODE=1 ;; discharging) CODE=2 ;; empty) CODE=3 ;; full) CODE=4 ;;
  *) echo "state: charging, discharging, full, empty or unknown"; exit 1 ;;
esac
case $WARNING in normal) LEVEL=1 ;; low) LEVEL=3 ;; critical) LEVEL=4 ;; *) echo "warning: normal, low or critical"; exit 1 ;; esac
[ "$PRESENT" = present ] && IS=true || IS=false
TTE=0; TTF=0
[ "$STATE" = discharging ] && TTE=$((PERCENT * 98))
[ "$STATE" = charging ] && TTF=$(((100 - PERCENT) * 100))
set_p() {
  busctl --address="$ADDR" set-property org.freedesktop.UPower \\
    /org/freedesktop/UPower/devices/DisplayDevice org.freedesktop.UPower.Device "$@"
}
set_p IsPresent b $IS
set_p TimeToEmpty x $TTE
set_p TimeToFull x $TTF
set_p WarningLevel u $LEVEL
set_p State u $CODE
set_p Percentage d "$PERCENT"
echo "fake battery: $PERCENT % $STATE $PRESENT $WARNING"
"""

BATTERY_UPOWER = """# battery-upower.sh away|back: the fake UPower leaves the private system bus, or returns.
ROOT=${TESS_M5B_ROOT:-/tmp/tess-kwin-m5b}
PID=$(cat "$ROOT/fake.pid" 2>/dev/null) || { echo "run-battery-fake.sh is not running"; exit 1; }
case ${1:-} in
  away) kill -USR1 "$PID"; echo "UPower away" ;;
  back) kill -USR2 "$PID"; echo "UPower back" ;;
  *) echo "usage: battery-upower.sh away|back"; exit 1 ;;
esac
"""


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    write_gallery(CFG)
    (ROOT / "checklist.txt").write_text(CHECKLIST)
    state = "export XDG_STATE_HOME=/tmp/tess-kwin-m5b/state\n"
    script("run.sh", state + f"exec {BIN}/tesserae-shell run --config-dir {CFG}\n")
    script("check.sh", state + f"{BIN}/tesserae-shell check --config-dir {CFG}\n")
    script(
        "run-battery-fake.sh",
        state
        + "ROOT=/tmp/tess-kwin-m5b\n"
        + 'rm -f "$ROOT/bus-address" "$ROOT/fake.pid"\n'
        + f'{BIN}/python {REPO}/tests/kwin/fake_upower.py --root "$ROOT" &\n'
        + "FAKE=$!\n"
        + "trap 'kill \"$FAKE\" 2>/dev/null' EXIT\n"
        + 'for _ in $(seq 100); do [ -s "$ROOT/bus-address" ] && break; sleep 0.1; done\n'
        + '[ -s "$ROOT/bus-address" ] || { echo "the fake UPower did not start"; exit 1; }\n'
        + 'export DBUS_SYSTEM_BUS_ADDRESS=$(cat "$ROOT/bus-address")\n'
        + 'echo "system bus (private): $DBUS_SYSTEM_BUS_ADDRESS"\n'
        + f"{BIN}/tesserae-shell run --config-dir {CFG}\n",
    )
    script("battery-set.sh", BATTERY_SET)
    script("battery-upower.sh", BATTERY_UPOWER)
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
