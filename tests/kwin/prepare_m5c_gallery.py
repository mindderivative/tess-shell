"""Regenerate the M5c Network KWin check in /tmp/tess-kwin-m5c (not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m5c_gallery.py``. It writes a scratch
config and scripts under ``/tmp/tess-kwin-m5c`` and starts nothing. The Bar shows three Networks (the
icon only, with the connection's name, and with ``show_vpn: false``) and the Clock, all coloured by
theme tokens, so it follows Plasma's light and dark.

* ``run.sh``: the shell on your real session bus and real system bus. The Network reads
  NetworkManager and **writes nothing**; it shows what your machine does. You change the state
  yourself: unplug the cable, switch Wi-Fi off and on in Plasma's network applet, connect and
  disconnect a VPN there.
* ``run-fake.sh``: the shell on your real session bus (only the light/dark follow) and a PRIVATE
  system bus with a fake NetworkManager (``tests/kwin/fake_nm.py``), so every state can be shown.
  ``network-set.sh`` changes it (any words, in any order; an unknown word is refused) and
  ``network-nm.sh away|back`` makes the fake NetworkManager leave and return.
* ``check.sh``: ``tesserae-shell check`` on the config.
* ``checklist.txt``: every line to check, in one list.

The state directory is ``/tmp/tess-kwin-m5c/state``, never the real one. Nothing here changes the
real desktop or the real network.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.shell_samples import write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m5c")
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
                            Spacer { }
                            Network { }
                            Network { show_name: true }
                            Network { show_vpn: false }
                            Clock { }
                        }
                    }
                }
            }
        }
    }
}
"""

CHECKLIST = """M5c Network: one list, every line to run.  Do it in light and in dark (Plasma's colour
scheme; every colour is a theme token).  The Bar shows, at the right: three Network modules (the first
the icon only, the second with the connection's name beside the icon, the third with `show_vpn:
false`) and the Clock.

An icon: a plug is the cable; the Wi-Fi fan has four steps (one to four bars); an exclamation mark
or a broken link is "no internet"; a cross over the network is "disconnected"; a Wi-Fi fan with a
slash is "networking off"; a small shield-like "VPN" is the second icon.  The colour: the normal
text colour when connected, amber when there is no internet (or a sign-in is wanted), grey-blue
(muted) when disconnected or off.

PART 1: on this desktop, real buses  (start with /tmp/tess-kwin-m5c/run.sh)
Reads your real system bus; writes nothing.  YOU change the state, in the way each line says.

 1  Cable in, as on your desk now: all three Networks show the plug icon in the text colour; the
    second shows "Wired connection 1" beside it; there is no second (VPN) icon; point at any of
    them: a tooltip opens with "Wired connection 1, ethernet, connected".  The log has no WARNING
    or ERROR line (`grep -E "WARNING|ERROR"` on the shell's output).
 2  Unplug the cable: within a moment all three change to the cross-over-network icon in the muted
    colour, the second loses its name, and the tooltip reads "Disconnected".  The modules stay
    visible (they do not vanish).  Plug it in again: the plug icon and the tooltip return.
 3  Switch Wi-Fi on in Plasma's network applet and connect to a network (cable out, or in: with
    the cable in, wired stays the main connection; take the cable out to see the Wi-Fi): the Wi-Fi
    icon shows with one to four bars, the second Network shows the network's name, and the tooltip
    reads "<name>, Wi-Fi N %, connected" with N a multiple of 5.  Walk away from the router and
    back: the bars change in steps and the tooltip's percent follows; the icon does not flicker
    while the signal wobbles inside a step.
 4  Switch Wi-Fi off in the applet with the cable out: the cross-over-network icon, "Disconnected".
    Switch it on again: it reconnects and the Wi-Fi icon returns.
 5  OPTIONAL, disruptive, skip it if you do not want to risk your network: in the applet switch
    networking off (the applet's "Enable networking" or flight mode): the Wi-Fi-with-slash icon and
    the tooltip "Networking off"; switch it on: back to normal.
 6  Connect a VPN in the applet (any you have): the first and second Network show a second icon
    (VPN) beside the connection's icon, the third does not (`show_vpn: false`); the tooltip ends
    with ", VPN <the VPN's name>".  The connection icon stays the Wi-Fi or the plug: the VPN does not
    replace it.  Disconnect the VPN: the second icon goes, and nothing else moves.
 7  Log: no ERROR line after all of the above; no WARNING either.

PART 2: fake NetworkManager on a private system bus  (stop part 1; start
/tmp/tess-kwin-m5c/run-fake.sh; in a second terminal use /tmp/tess-kwin-m5c/network-set.sh)
The fake NetworkManager is on its own private bus: nothing here touches your real network.  The
shell still reads your real session bus (only for light and dark).  network-set.sh takes its words
in any order: wired | wifi | none, a number (the Wi-Fi strength, with wifi), vpn | novpn, online |
limited | portal | local | connecting | disabled, ap1 | ap2, wifioff | wifion.  Every word it does
not know is refused with a message and changes nothing.

11  At start the fake is wired and online: the plug icon in all three; the second shows "Wired
    connection 1"; the tooltip "Wired connection 1, ethernet, connected".
12  `network-set.sh wifi 72`: the Wi-Fi icon with three bars; the second shows "Home-WiFi"; the
    tooltip "Home-WiFi, Wi-Fi 70 %, connected".  `network-set.sh wifi 73` and `network-set.sh
    wifi 71`: nothing changes at all (same bars, same tooltip).
13  The four steps: `network-set.sh wifi 10` one bar, `network-set.sh wifi 30` two bars,
    `network-set.sh wifi 60` three bars, `network-set.sh wifi 90` four bars; the tooltip shows
    10, 30, 60 and 90 %.  `network-set.sh wifi 24` one bar, `network-set.sh wifi 25` two bars,
    `network-set.sh wifi 74` three bars, `network-set.sh wifi 75` four bars.
14  No internet: `network-set.sh wifi 60 limited`: the Wi-Fi icon with an exclamation mark, in
    amber; the tooltip "Home-WiFi, Wi-Fi 60 %, limited connectivity".  `network-set.sh wired limited`:
    the broken-link plug, amber, "Wired connection 1, ethernet, limited connectivity".
    `network-set.sh wifi 60 local`: the same as limited.
15  Sign-in wanted: `network-set.sh wired portal`: the broken-link plug, amber, "Wired connection 1,
    ethernet, sign-in required".  `network-set.sh wifi 60 portal`: the Wi-Fi alert icon, "..., sign-in
    required".  `network-set.sh wifi 60 online`: back to normal colour and bars.
16  Connecting: `network-set.sh wifi 60 connecting`: the spinning-arrows Wi-Fi icon, the tooltip
    "Home-WiFi, Wi-Fi 60 %, connecting".  `network-set.sh wired connecting`: the pending plug icon.
17  Cable unplugged and networking off: `network-set.sh none`: the cross-over-network icon, muted,
    "Disconnected"; the modules stay visible.  `network-set.sh none disabled`: the Wi-Fi-with-slash
    icon, muted, "Networking off".  `network-set.sh wired`: back to the plug.
18  Roaming: `network-set.sh wifi 60 ap1`, then `network-set.sh wifi 40 ap2`: the second Network's
    name changes to "Cafe-Mesh" and the bars to two; `network-set.sh wifi 100 ap1` and back: the
    name follows.  (The fake's two access points are Home-WiFi and Cafe-Mesh.)
19  VPN: `network-set.sh wired vpn`: the first and second Network show the second icon, the third
    does not; the tooltip ends ", VPN Work VPN"; the plug stays.  `network-set.sh wifi 60 vpn`: the
    Wi-Fi icon and the second icon.  `network-set.sh wifi 60 novpn`: the second icon goes.
20  Wi-Fi switch: `network-set.sh wifioff`: nothing changes (Wi-Fi off alone says nothing while the
    cable is in); `network-set.sh none wifioff`: the cross-over-network icon.  `network-set.sh wired
    wifion`: back.
21  `network-nm.sh away`: all three Networks vanish with no placeholder and no gap (the Clock moves
    right by their width and the Spacing beside them) and exactly one WARNING appears in the log
    (`dbus: org.freedesktop.NetworkManager left the system bus`).  `network-nm.sh back`: they
    return at once with the state they had.  Run `away` and `back` a second time inside a minute:
    still one warning.
22  `network-set.sh bogus`: a message that names the word and lists the words; nothing changes.
    `network-set.sh wired 50`: refused too (a strength needs wifi).  `network-set.sh vpn none`:
    refused (a VPN needs a connection).
23  Change the strength five times quickly (`network-set.sh wifi 20`, `... 40`, `... 60`, `... 80`,
    `... 20`): no flicker of the Clock, and `top -p $(pgrep -f 'tesserae-shell run')` shows the
    shell idle (0 % CPU) when you stop.
24  Log: no ERROR line; the only WARNING is the one of line 21.
"""

NETWORK_SET = """# network-set.sh WORD...  (the words in any order; every other word is refused)
#   wired | wifi | none          the primary connection (default wired)
#   a number 0 to 100            the Wi-Fi signal strength (with wifi; default 72)
#   vpn | novpn                  a VPN connection is active (needs wired or wifi; default novpn)
#   online | limited | portal | local | connecting | disabled
#                                what NetworkManager reports (default online)
#   ap1 | ap2                    the access point Wi-Fi is on (default ap1)
#   wifioff | wifion             the manager's WirelessEnabled switch (default: not changed)
# Talks to the fake NetworkManager only.
ROOT=${TESS_M5C_ROOT:-/tmp/tess-kwin-m5c}
ADDR=$(cat "$ROOT/bus-address" 2>/dev/null) || { echo "run-fake.sh is not running"; exit 1; }
WORDS="wired, wifi, none, a number from 0 to 100, vpn, novpn, online, limited, portal, local, connecting, disabled, ap1, ap2, wifioff, wifion"
KIND=wired; STRENGTH=; VPN=novpn; COND=online; AP=ap1; WIRELESS=
[ $# -gt 0 ] || { echo "words: $WORDS"; exit 1; }
for word in "$@"; do
  case $word in
    wired|wifi|none) KIND=$word ;;
    vpn|novpn) VPN=$word ;;
    online|limited|portal|local|connecting|disabled) COND=$word ;;
    ap1|ap2) AP=$word ;;
    wifioff) WIRELESS=false ;;
    wifion) WIRELESS=true ;;
    ''|*[!0-9]*) echo "unknown word '$word'; the words: $WORDS"; exit 1 ;;
    *) [ "$word" -le 100 ] || { echo "a strength is 0 to 100, not $word"; exit 1; }; STRENGTH=$word ;;
  esac
done
[ -z "$STRENGTH" ] || [ "$KIND" = wifi ] || { echo "a strength needs wifi"; exit 1; }
[ "$VPN" = novpn ] || [ "$KIND" != none ] || { echo "a VPN needs wired or wifi, not none"; exit 1; }
[ -n "$STRENGTH" ] || STRENGTH=72
case $COND in
  online) STATE=70; CONN=4 ;; limited) STATE=70; CONN=3 ;; portal) STATE=70; CONN=2 ;;
  local) STATE=50; CONN=3 ;; connecting) STATE=40; CONN=4 ;; disabled) STATE=10; CONN=1 ;;
esac
P=/org/freedesktop/NetworkManager
case $KIND in
  wired) PRIMARY=$P/ActiveConnection/1; LIST="1 $PRIMARY" ;;
  wifi) PRIMARY=$P/ActiveConnection/2; LIST="1 $PRIMARY" ;;
  none) PRIMARY=/; LIST="0"
        # no link: NetworkManager is disconnected unless it was told to be off
        [ "$COND" = disabled ] || { STATE=20; CONN=1; } ;;
esac
[ "$VPN" = vpn ] && LIST="2 $PRIMARY $P/ActiveConnection/3"
set_p() {  # OBJECT INTERFACE PROPERTY TYPE VALUE...
  local object=$1 interface=$2; shift 2
  busctl --address="$ADDR" set-property org.freedesktop.NetworkManager "$object" "$interface" "$@" || exit 1
}
M=org.freedesktop.NetworkManager
[ "$KIND" != wifi ] || {
  set_p $P/AccessPoint/${AP#ap} $M.AccessPoint Strength y "$STRENGTH"
  set_p $P/Devices/3 $M.Device.Wireless ActiveAccessPoint o $P/AccessPoint/${AP#ap}
}
[ -z "$WIRELESS" ] || set_p $P $M WirelessEnabled b $WIRELESS
set_p $P $M ActiveConnections ao $LIST
set_p $P $M PrimaryConnection o "$PRIMARY"
set_p $P $M Connectivity u $CONN
set_p $P $M State u $STATE
echo "fake network: $KIND $COND vpn=$VPN${WIRELESS:+ wireless=$WIRELESS}$([ "$KIND" = wifi ] && echo " strength=$STRENGTH $AP")"
"""

NETWORK_NM = """# network-nm.sh away|back: the fake NetworkManager leaves the private system bus, or returns.
ROOT=${TESS_M5C_ROOT:-/tmp/tess-kwin-m5c}
PID=$(cat "$ROOT/fake.pid" 2>/dev/null) || { echo "run-fake.sh is not running"; exit 1; }
case ${1:-} in
  away) kill -USR1 "$PID"; echo "NetworkManager away" ;;
  back) kill -USR2 "$PID"; echo "NetworkManager back" ;;
  *) echo "usage: network-nm.sh away|back"; exit 1 ;;
esac
"""


def script(name: str, text: str) -> None:
    path = ROOT / name
    path.write_text("#!/usr/bin/env bash\n" + text)
    path.chmod(0o755)


def write_gallery(cfg: Path) -> None:
    shutil.rmtree(cfg, ignore_errors=True)
    write_example(cfg, BODY)
    (cfg / "settings.tdl").write_text(SETTINGS)


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    write_gallery(CFG)
    (ROOT / "checklist.txt").write_text(CHECKLIST)
    state = f"export XDG_STATE_HOME={ROOT}/state\n"
    script("run.sh", state + f"exec {BIN}/tesserae-shell run --config-dir {CFG}\n")
    script("check.sh", state + f"{BIN}/tesserae-shell check --config-dir {CFG}\n")
    script(
        "run-fake.sh",
        state
        + f"ROOT={ROOT}\n"
        + 'rm -f "$ROOT/bus-address" "$ROOT/fake.pid"\n'
        + f'{BIN}/python {REPO}/tests/kwin/fake_nm.py --root "$ROOT" &\n'
        + "FAKE=$!\n"
        + "trap 'kill \"$FAKE\" 2>/dev/null' EXIT\n"
        + 'for _ in $(seq 100); do [ -s "$ROOT/bus-address" ] && break; sleep 0.1; done\n'
        + '[ -s "$ROOT/bus-address" ] || { echo "the fake NetworkManager did not start"; exit 1; }\n'
        + 'export DBUS_SYSTEM_BUS_ADDRESS=$(cat "$ROOT/bus-address")\n'
        + 'echo "system bus (private): $DBUS_SYSTEM_BUS_ADDRESS"\n'
        + f"{BIN}/tesserae-shell run --config-dir {CFG}\n",
    )
    script("network-set.sh", NETWORK_SET)
    script("network-nm.sh", NETWORK_NM)
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
