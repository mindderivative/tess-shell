"""Regenerate the M5e Audio KWin check in /tmp/tess-kwin-m5e (not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m5e_gallery.py``. It writes a scratch
config and scripts under ``/tmp/tess-kwin-m5e`` and starts nothing. The Bar shows four Audio modules
(the icon only; with the percent; with the percent and a slider; with ``show_mic: false``) and the
Clock, all coloured by theme tokens, so it follows Plasma's light and dark. The shell file writes NO
Popup: the shell provides ``Audio_Outputs``, the outputs menu that a secondary click opens.
``run-override.sh`` is the fake run with a Popup of that name written in the shell file, which
replaces the shipped one.

* ``run.sh``: the shell on YOUR REAL sound server (and the real session bus). The Audio module reads
  it, and **the lines of the checklist marked [CHANGES ...] change your real volume, mute, default
  output or microphone mute**: note them first and restore them at the end (the checklist says how).
* ``run-fake.sh``: the shell on a PRIVATE FAKE sound server (``tests/kwin/fake_pulse_server.py``: its
  own socket under ``/tmp/tess-kwin-m5e/run``; the shell is told that socket with ``PULSE_SERVER`` and
  nothing else, so it cannot reach your real server). ``audio-set.sh`` changes the fake (any words,
  in any order; an unknown word is refused) and ``audio-server.sh away|back`` makes the fake server
  leave and return. Every setter the shell calls on the fake is written to ``fake.log``.
* ``run-override.sh``: ``run-fake.sh`` with an ``Audio_Outputs`` Popup of the user's own in the shell
  file (a primary-coloured menu with sharp corners, 12 px below the Bar).
* ``check.sh``: ``tesserae-shell check`` on the config.
* ``checklist.txt``: every line to check, in one list.

The state directory is ``/tmp/tess-kwin-m5e/state``, never the real one. Part 2 and the fake server
never touch your real sound server.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.shell_samples import write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m5e")
CFG = ROOT / "gallery"
CFG_OVERRIDE = ROOT / "gallery-override"
BIN = Path.home() / "Projects/pyDev/pyEnvs/tess-shell/bin"
SETTINGS = (
    "---\nTDL: 0.1\nName: Settings\n---\nSettings {\n  Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default], Follow_Desktop: true }\n}\n"
)

BODY_TEMPLATE = """
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
                            Audio { }
                            Audio { show_percent: true }
                            Audio { show_percent: true, show_slider: true }
                            Audio { show_mic: false }
                            Clock { }
                        }
                    }
                }
            }
%s        }
    }
}
"""

# the shell file writes NO Popup: the shell provides Audio_Outputs
BODY = BODY_TEMPLATE % ""
# the variant that overrides the shipped Audio_Outputs with a Popup of the same name (a different
# look: primary colour, square corners, opening above the row at 12 px)
BODY_OVERRIDE = (
    BODY_TEMPLATE
    % """            Popup {
                Name: Audio_Outputs
                Attach: BOTTOM
                Gap: 12
                Style { Background: $color.primary, Corner_Radius: 2 }
                Children { Audio_Outputs { } }
            }
"""
)

CHECKLIST = """M5e Audio: one list, every line to run.  Do it in light and in dark (Plasma's colour
scheme; every colour is a theme token).  The Bar shows, at the right: four Audio modules (the first the
icon only; the second with the volume's number; the third with the number and a slider; the fourth
with `show_mic: false`) and the Clock.

An icon: a loudspeaker with no waves is volume 0; with one, two, three waves it is low, medium and high
(1 to 33, 34 to 66, 67 and above); a loudspeaker with a cross is muted (and so is the muted colour:
grey-blue); headphones are headphones (crossed when muted); the Bluetooth symbol with sound waves is a
Bluetooth output; a small crossed microphone appears beside the icon while the default microphone is
muted (not on the fourth module).

PART 1: on this desktop, your REAL sound server  (start with /tmp/tess-kwin-m5e/run.sh)
THIS PART CHANGES YOUR REAL SOUND STATE.  Every line is marked: [reads only] changes nothing;
[CHANGES your real volume], [CHANGES your real mute], [CHANGES your real default output] and
[CHANGES your real microphone mute] change what they say, on your real server.  BEFORE you start,
write down: the default output (its name), its volume in percent, whether it is muted, and whether the
microphone is muted (look in Plasma's audio applet: reading is safe).  Line 9 puts them back.  Lower
your speakers or put headphones on before line 5 and line 6: the volume really moves.

 1  [reads only] At start the four Audio modules show the speaker icon that matches your volume (as
    the table above); the second and third show the percent you wrote down; the third's slider handle
    is there; point at any module: a tooltip opens with "<your output's name>, <volume> %".  The log
    has no WARNING or ERROR line (`grep -E "WARNING|ERROR"` on the shell's output).
 2  [CHANGES your real volume] Change the volume in Plasma's applet or with the volume keys: all four
    icons step with it (the icon changes at 33 and 66 and 67), the number follows, the slider handle
    follows, within a moment, with nothing else on the Bar moving.
 3  [CHANGES your real mute] Mute in the applet: all four icons turn to the crossed loudspeaker in the
    muted colour, the tooltip reads "<name>, muted".  Unmute: they return.
 4  [CHANGES your real mute] Click the icon of the first module: your sound is muted and the applet
    shows it; click again: unmuted.  Click the icon of the third module: the same.
 5  [CHANGES your real volume] Scroll up over any icon, one notch: the volume rises by 5 percent (the
    applet agrees); scroll down: it falls by 5.  A quick flick of several notches adds up (none is
    lost).  Scroll up past 100: it stops at 100.
 6  [CHANGES your real volume] Drag the third module's slider: the volume follows your hand while you
    drag, the number follows, the handle does not jump back while you hold it; let go: the volume is
    the value you let go at and the applet shows the same.  Click on the middle of the track: the
    volume jumps there.
 7  [CHANGES your real default output] Click the first module's icon with the RIGHT button: a menu opens
    under it listing your outputs, each with its icon (loudspeaker, headphones, HDMI) and a dot on the
    one that is the default.  Click another output: the menu closes, the default output changes in
    Plasma's applet too, the icon and the name in the tooltip change at once.  Then pick yours again.
    (The sound moves to that device while you do this.)
 8  [CHANGES your real microphone mute] Mute your microphone in the applet: the first, second and third
    modules show the small crossed microphone, the fourth does not.  Unmute: it goes.
 9  [CHANGES your real volume, mute, default output and microphone mute] Put it back: your values as
    you wrote them down (the applet shows them).
10  [reads only] The log has no ERROR line after all of the above; no WARNING either.

PART 2: a fake sound server  (stop part 1; start /tmp/tess-kwin-m5e/run-fake.sh; in a second terminal
use /tmp/tess-kwin-m5e/audio-set.sh)
The fake sound server is a program of ours on its own private socket: nothing here touches your real
sound server or the real sound.  The shell still reads your real session bus (only for light and
dark).  It has five outputs: speakers (the default, 45 %), headphones, hdmi, bluetooth and usb (it
exists after `usbplug`), and a microphone.  audio-set.sh takes its words in any order: speakers |
headphones | hdmi | bluetooth | usb (the default output), a number 0 to 100 (the default output's
volume), loud (130 %), mute | unmute, micmute | micunmute, mic | nomic (a microphone exists or not),
usbplug | usbunplug, balance (left 80 %, right 40 %).  Every word it does not know, and every
contradiction, is refused with a message and changes nothing.  Every setter the shell calls is written
to /tmp/tess-kwin-m5e/fake.log (`tail -f` it).

11  At start the fake is on the speakers at 45 %, not muted, the microphone not muted: the medium
    loudspeaker in all four; the second and third show "45 %"; the tooltip "Speakers, 45 %".
12  The steps: `audio-set.sh 0` loudspeaker with no waves, "0 %"; `audio-set.sh 1` one wave;
    `audio-set.sh 33` one wave; `audio-set.sh 34` two waves; `audio-set.sh 66` two waves;
    `audio-set.sh 67` three waves; `audio-set.sh 100` three waves.  The number and the slider handle
    follow each time; nothing on the Bar jumps.
13  Mute: `audio-set.sh mute` the crossed loudspeaker in the muted colour, the tooltip "Speakers,
    muted" and the number still shows the level; `audio-set.sh unmute` back.
14  Kinds: `audio-set.sh headphones` the headphones icon and the tooltip "Headphones, 60 %";
    `audio-set.sh headphones mute` the crossed headphones; `audio-set.sh hdmi unmute` the loudspeaker
    ("HDMI Output, 60 %"); `audio-set.sh bluetooth` the Bluetooth sound icon ("Bluetooth Headset,
    60 %"); `audio-set.sh speakers` back.
15  Above 100: `audio-set.sh loud` the number shows 130 % and the slider handle is at the end; scroll
    down one notch on any icon: 100 % (a setter never goes above 100).
16  Scroll: scroll up one notch: 5 more percent; down: 5 less; flick several notches quickly: all of
    them count.  The fake.log shows `set_sink_volume` lines.
17  Slider: drag the third module's slider slowly across the track: fake.log gets `set_sink_volume`
    lines at most 20 a second while you drag (look at the timestamps: at least 50 ms apart) and one
    more when you let go; the handle never jumps back while you hold it.
18  Click on an icon: `set_sink_mute` in fake.log and the icons change after the fake's answer, not
    before; click again: back.
19  The outputs menu: right-click an icon: a menu with Speakers (dotted), Headphones, HDMI Output and
    Bluetooth Headset, each with its icon.  `audio-set.sh usbplug` while it is open: nothing in the
    open menu changes (it is the list as it was when you opened it); close it (click outside) and
    open it again: USB DAC is there.  Click it: the default becomes the USB DAC (tooltip "USB DAC, 70
    %"), `set_default_sink` in fake.log.
20  Plug and unplug: `audio-set.sh usbunplug` while the USB DAC is the default: the fake names another
    default and the modules follow without a gap or a flicker.  `audio-set.sh usb usbplug` plugs it
    again and makes it the default (the words work in any order).
21  The microphone: `audio-set.sh micmute` the crossed microphone beside the first, second and third
    icons, not the fourth; `audio-set.sh micunmute` it goes; `audio-set.sh nomic` no mark, nothing
    breaks; `audio-set.sh mic` the microphone is back.
22  Balance: `audio-set.sh balance` the number reads 60 %; scroll up one notch: 65 %; the fake's
    channels stay in the same proportion (fake.log shows two levels, the left twice the right).
23  The server leaves: `audio-server.sh away`: all four Audio modules vanish with no placeholder and
    no gap (the Clock moves right by their width and the Spacing beside them) and no WARNING appears
    in the log (only an INFO line, "the sound server went away").  `audio-server.sh back`: they
    return at once with the state they had.  Run away and back a second time: the same.
24  `audio-set.sh bogus`: a message that names the word and lists the words; nothing changes.
    `audio-set.sh mute unmute`, `audio-set.sh 150` and `audio-set.sh headphones hdmi` are refused
    too, and change nothing.  `audio-set.sh usbunplug` and then `audio-set.sh usb`: the second is
    refused (no USB DAC is plugged) and changes nothing.
25  Log: no ERROR line; no WARNING line.  `top -p $(pgrep -f 'tesserae-shell run')` shows the shell
    idle (0 % CPU) when you stop touching it.
26  The shell's own Popup: in every run above the config writes no Popup, and the outputs menu of
    lines 7 and 19 is the shell's (dark raised background, rounded corners).  Stop the run; start
    /tmp/tess-kwin-m5e/run-override.sh (the same fake; the shell file now writes a Popup named
    Audio_Outputs): right-click an icon: the menu is the user's (primary colour, square corners,
    12 px below the Bar) and picking an output still works.
"""

AUDIO_SET = """# audio-set.sh WORD...  (the words in any order; every other word is refused)
#   speakers | headphones | hdmi | bluetooth | usb     the default output (usb after usbplug)
#   a number 0 to 100                                  the default output's volume
#   loud                                               the default output's volume to 130 %
#   mute | unmute                                      the default output's mute
#   micmute | micunmute                                the microphone's mute
#   mic | nomic                                        the microphone exists or not
#   usbplug | usbunplug                                the USB output exists or not
#   balance                                            left 80 %, right 40 % on the default output
# Talks to the fake sound server only.
ROOT=${TESS_M5E_ROOT:-/tmp/tess-kwin-m5e}
CTL="$ROOT/control"
WORDS="speakers, headphones, hdmi, bluetooth, usb, a number from 0 to 100, loud, mute, unmute, micmute, micunmute, mic, nomic, usbplug, usbunplug, balance"
[ -S "$CTL" ] || { echo "run-fake.sh is not running"; exit 1; }
[ $# -gt 0 ] || { echo "words: $WORDS"; exit 1; }
DEFAULT=; VOLUME=; MUTE=; MIC=; HASMIC=; USB=; BALANCE=
once() {  # VARIABLE VALUE WORD: a word that clashes with one already given is refused
  local have=${!1}
  [ -z "$have" ] || [ "$have" = "$2" ] || { echo "'$3' contradicts what the words before it ask for"; exit 1; }
  printf -v "$1" %s "$2"
}
for word in "$@"; do
  case $word in
    speakers|headphones|hdmi|bluetooth|usb) once DEFAULT $word $word ;;
    loud) once VOLUME 130 $word ;;
    mute) once MUTE 1 $word ;;
    unmute) once MUTE 0 $word ;;
    micmute) once MIC 1 $word ;;
    micunmute) once MIC 0 $word ;;
    mic) once HASMIC 1 $word ;;
    nomic) once HASMIC 0 $word ;;
    usbplug) once USB plug $word ;;
    usbunplug) once USB unplug $word ;;
    balance) BALANCE=1 ;;
    ''|*[!0-9]*) echo "unknown word '$word'; the words: $WORDS"; exit 1 ;;
    *) [ "$word" -le 100 ] || { echo "a volume is 0 to 100, not $word"; exit 1; }
       once VOLUME $word $word ;;
  esac
done
[ -z "$BALANCE" ] || [ -z "$VOLUME" ] || { echo "balance and a volume contradict each other"; exit 1; }
REQUEST=
[ -z "$USB" ] || REQUEST="$REQUEST usb=$USB"
[ -z "$HASMIC" ] || REQUEST="$REQUEST hasmic=$HASMIC"
[ -z "$DEFAULT" ] || REQUEST="$REQUEST default=$DEFAULT"
[ -z "$VOLUME" ] || REQUEST="$REQUEST volume=$VOLUME"
[ -z "$BALANCE" ] || REQUEST="$REQUEST balance=1"
[ -z "$MUTE" ] || REQUEST="$REQUEST mute=$MUTE"
[ -z "$MIC" ] || REQUEST="$REQUEST mic=$MIC"
exec python3 AUDIO_CTL "$CTL" $REQUEST
"""

AUDIO_SERVER = """# audio-server.sh away|back: the fake sound server goes away (its socket is removed, its connections
# close), or comes back with the state it had.
ROOT=${TESS_M5E_ROOT:-/tmp/tess-kwin-m5e}
PID=$(cat "$ROOT/fake.pid" 2>/dev/null) || { echo "run-fake.sh is not running"; exit 1; }
case ${1:-} in
  away) kill -USR1 "$PID"; echo "sound server away" ;;
  back) kill -USR2 "$PID"; echo "sound server back" ;;
  *) echo "usage: audio-server.sh away|back"; exit 1 ;;
esac
"""

REAL_WARNING = (
    'echo "REAL sound server: the lines of the checklist marked [CHANGES ...] change your real '
    'volume, mute, default output or microphone mute. Note them first (checklist, part 1)." >&2\n'
)


def script(name: str, text: str) -> None:
    path = ROOT / name
    path.write_text("#!/usr/bin/env bash\n" + text)
    path.chmod(0o755)


def audio_set_text() -> str:
    return AUDIO_SET.replace("AUDIO_CTL", str(REPO / "tests" / "kwin" / "audio_ctl.py"))


def run_fake(cfg: Path) -> str:
    """``run-fake.sh``: the fake sound server on a private socket, and the shell told that socket."""
    return (
        f"export XDG_STATE_HOME={ROOT}/state\n"
        + f"ROOT={ROOT}\n"
        + 'rm -f "$ROOT/control" "$ROOT/fake.pid" "$ROOT/server-socket"\n'
        + f'{BIN}/python {REPO}/tests/kwin/fake_pulse_server.py --root "$ROOT" &\n'
        + "FAKE=$!\n"
        + "trap 'kill \"$FAKE\" 2>/dev/null' EXIT\n"
        + 'for _ in $(seq 100); do [ -s "$ROOT/server-socket" ] && break; sleep 0.1; done\n'
        + '[ -s "$ROOT/server-socket" ] || { echo "the fake sound server did not start"; exit 1; }\n'
        + "# the shell is told this socket and nothing else: it cannot reach the real server\n"
        + "unset PULSE_RUNTIME_PATH PULSE_COOKIE PULSE_SINK PULSE_SOURCE\n"
        + 'export PULSE_SERVER="unix:$(cat "$ROOT/server-socket")"\n'
        + 'echo "sound server (private fake): $PULSE_SERVER"\n'
        + f"{BIN}/tesserae-shell run --config-dir {cfg}\n"
    )


def write_gallery(cfg: Path, body: str = BODY) -> None:
    shutil.rmtree(cfg, ignore_errors=True)
    write_example(cfg, body)
    (cfg / "settings.tdl").write_text(SETTINGS)


def main() -> None:
    ROOT.mkdir(exist_ok=True)
    write_gallery(CFG)
    write_gallery(CFG_OVERRIDE, BODY_OVERRIDE)
    (ROOT / "checklist.txt").write_text(CHECKLIST)
    state = f"export XDG_STATE_HOME={ROOT}/state\n"
    script("run.sh", state + REAL_WARNING + f"exec {BIN}/tesserae-shell run --config-dir {CFG}\n")
    script("check.sh", state + f"{BIN}/tesserae-shell check --config-dir {CFG}\n")
    script("run-fake.sh", run_fake(CFG))
    # the same private fake server, with a Popup of the user's own that overrides the shipped one
    script("run-override.sh", run_fake(CFG_OVERRIDE))
    script("audio-set.sh", audio_set_text())
    script("audio-server.sh", AUDIO_SERVER)
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
