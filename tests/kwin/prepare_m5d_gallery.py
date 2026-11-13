"""Regenerate the M5d Media KWin check in /tmp/tess-kwin-m5d (not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m5d_gallery.py``. It writes a scratch
config and scripts under ``/tmp/tess-kwin-m5d`` and starts nothing. The Bar shows three Media modules
(controls and title; artwork, controls, title and the position slider; the title alone) and the
Clock, all coloured by theme tokens, so it follows Plasma's light and dark.

* ``run.sh``: the shell on your real session bus. The Media reads your real MPRIS players
  (a browser, Elisa, VLC, mpv, Spotify...) and **its buttons and slider act on your real player**:
  play or pause, next, previous and a seek are sent to it. Nothing else is written. You start and
  stop the players yourself.
* ``run-fake.sh``: the shell on a PRIVATE session bus with fake players (``tests/kwin/fake_mpris.py``)
  that behave like real ones, so a click does something and every state can be shown.
  ``media-set.sh`` changes them (any words, in any order; an unknown word is refused).
* ``check.sh``: ``tesserae-shell check`` on the config.
* ``checklist.txt``: every line to check, in one list.

The state directory is ``/tmp/tess-kwin-m5d/state``, never the real one. Nothing here changes your
real players or your real session bus except the clicks named in part 1.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.shell_samples import write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m5d")
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
                        Spacing: 24
                        Padding: [8, 2, 8, 2]
                        Align_Items: CENTER
                        Children {
                            Media { }
                            Media { show_art: true, show_position: true, max_width: 140 }
                            Media { show_controls: false, max_width: 120 }
                            Spacer { }
                            Clock { }
                        }
                    }
                }
            }
        }
    }
}
"""

CHECKLIST = """M5d Media: one list, every line to run.  Do it in light and in dark (Plasma's colour
scheme; every colour is a theme token).  The Bar shows, from the left: three Media modules (the
first with the three buttons and the title; the second with the cover art, the three buttons, the
title and a position slider; the third with the title only) and, at the right, the Clock.

The buttons are, left to right, previous (a bar and a triangle), play (a triangle) or pause (two
bars) and next.  A button the player cannot do is grey (disabled).  The cover is a small square at
the left of the second module; with no cover it is a music note.

PART 1: on this desktop, real session bus  (start with /tmp/tess-kwin-m5d/run.sh)
READS your real players, and WRITES to them only when you click a button or release the slider:
those clicks play, pause, skip and seek YOUR REAL PLAYER.  Nothing else is written.

 1  With no player running (close browsers' media tabs, Elisa, VLC, mpv, Spotify): none of the three
    modules shows, no placeholder, and the Clock is at the right with no gap where they would be.
    The log has no WARNING or ERROR line (`grep -E "WARNING|ERROR"` on the shell's output).
 2  Start a player and play something (a video in the browser is enough): the three modules appear
    at once; the first two show the pause icon and the title; the third shows the title.  Point at
    any of them: a tooltip opens with "<title>, <artist> (<the player's name>), playing".
 3  Click the play/pause button of the first module: your player pauses, and the icon becomes play
    after the player has said so (a moment, not before).  Press the pause key or the player's own
    button: the icon follows in both directions.
 4  Click next and previous of the first module: your player changes track (if it has one) and the
    title follows.  A button your player cannot do is grey and a click on it does nothing.
 5  The second module's slider: while the player plays it moves forward by itself, about once a
    second (only then); pause the player: it stops.  Drag it to another place and let go: your
    player seeks there and the slider stays there and goes on from there.  (If your player does not
    support seeking the slider is grey.)  The seek is sent ONCE, when you let go (the slider's
    On_Released), also when you let go with the pointer far outside the slider; while you hold the
    handle the player does not move and the slider does not jump.
 6  The cover: a player that gives a cover as a file (Elisa, a browser through Plasma's
    integration) shows it in the second module; one that gives a web address shows the music note.
 7  Start a second player and play it: it is the one shown; pause it and play the first: the first
    is shown; close the one that is shown: the other is shown; close the last: all three vanish.
 8  A browser (Chrome or Firefox) with Plasma's browser integration shows ONE entry for its
    media, not two.
 9  Log: no ERROR line after all of the above; no WARNING either (a player leaving is an INFO).

PART 2: fake players on a private session bus  (stop part 1; start /tmp/tess-kwin-m5d/run-fake.sh;
in a second terminal use /tmp/tess-kwin-m5d/media-set.sh)
The fake players are on their own private bus: nothing here touches your real players.  They behave
like real ones: a click plays, pauses, skips and seeks, and the player says so.  media-set.sh takes
its words in any order: a player (alpha | beta | chrome | integration; default alpha), a state
(playing | paused | stopped), a track (track1 | track2 | notitle), a cover (art | noart | httpart |
missingart), what it can do (next | nonext | previous | noprevious | seek | noseek | control |
nocontrol), a speed (fast | normal), whether it is on the bus (away | back) and a number (seek to
that second).  Every word it does not know is refused with a message and changes nothing.  Alpha is
playing "First Song" and beta is paused with a long title; chrome and integration are away.

11  At start: alpha is shown (tooltip "First Song, Artist A (Alpha Player), playing"); the pause
    icon; the second module shows the cover (a blue and orange square) and a slider that moves.
12  `media-set.sh paused`: the icon becomes play within a frame and the slider stops.
    `media-set.sh playing`: the pause icon again and the slider moves on.
13  Click play/pause in the first module: alpha pauses and the icon follows; click it again: it
    plays.  Click next: the title becomes the long one ("Second Song with a rather long title ...")
    and, in the third module (120 px wide), it scrolls; click previous: "First Song" again.
14  Drag the second module's slider to the middle and let go (also try letting go well outside the
    slider, above or below the Bar): it stays there and moves on from there; the player gets one seek.  `media-set.sh 150`: the slider jumps to 150 s (a quarter of the way past the middle).
    `media-set.sh 10`: back near the start.
15  Two players: `media-set.sh beta playing`: beta is shown (tooltip "..., Beta Player, playing").
    `media-set.sh alpha playing`: alpha began later: alpha is shown.  `media-set.sh alpha paused`:
    beta (still playing) is shown.  `media-set.sh beta away`: alpha (paused) is shown.
    `media-set.sh alpha away`: all three modules vanish, with no gap.  `media-set.sh beta back`:
    they return, with beta.  `media-set.sh alpha back`: still beta (nothing changed its choice).
16  Controls: `media-set.sh nonext noprevious`: next and previous are grey and a click on them does
    nothing.  `media-set.sh next previous`: they work again.  `media-set.sh nocontrol`: all three
    buttons and the slider are grey and the title still shows.  `media-set.sh control`: back.
    `media-set.sh noseek`: only the slider is grey.  `media-set.sh seek`: back.
17  Cover: `media-set.sh noart`: the music note.  `media-set.sh art`: the cover again.
    `media-set.sh httpart`: the music note (a web address is never fetched).  `media-set.sh
    missingart`: the music note.  `media-set.sh art`: the cover.
18  `media-set.sh notitle`: the title is empty and the tooltip starts "No title".  `media-set.sh
    track1`: "First Song" again.
19  The duplicate rule: `media-set.sh chrome back`, then `media-set.sh integration back`: both
    browser names are on the bus and both play, and ONE entry is shown (the tooltip says "Google
    Chrome").  `media-set.sh integration away`: still one entry.  `media-set.sh chrome away`: back
    to beta.
20  Speed: `media-set.sh fast`: the slider moves twice as fast; `media-set.sh normal`: as before.
21  `media-set.sh bogus`: a message that names the word and lists the words; nothing changes.
    `media-set.sh alpha beta`: refused too (one player at a time).  `media-set.sh playing paused`:
    refused (two states).
22  Idle: `media-set.sh paused`, and `top -p $(pgrep -f 'tesserae-shell run')` shows the shell at 0 %
    CPU (nothing wakes while paused).  `media-set.sh playing`: about 0 to 1 % (one small wake-up a
    second for the slider).  Change the track five times quickly (click next five times): no
    flicker of the Clock.
23  Log: no ERROR line; no WARNING either (a player leaving is an INFO line).
"""

MEDIA_SET = """# media-set.sh WORD...  (the words in any order; every other word is refused)
#   alpha | beta | chrome | integration   the player the other words are about (default alpha)
#   playing | paused | stopped            its PlaybackStatus
#   track1 | track2 | notitle             its track (notitle: the same track with no title in it)
#   art | noart | httpart | missingart    its cover (a file, none, a web address, a file not there)
#   next | nonext | previous | noprevious | seek | noseek | control | nocontrol   what it can do
#   fast | normal                         its Rate (2 or 1)
#   away | back                           the player leaves the bus, or returns
#   a number                              seek to that second (the player says Seeked)
# Talks to the fake players only.
ROOT=${TESS_M5D_ROOT:-/tmp/tess-kwin-m5d}
ADDR=$(cat "$ROOT/bus-address" 2>/dev/null) || { echo "run-fake.sh is not running"; exit 1; }
WORDS="alpha, beta, chrome, integration, playing, paused, stopped, track1, track2, notitle, art, noart, httpart, missingart, next, nonext, previous, noprevious, seek, noseek, control, nocontrol, fast, normal, away, back, a number of seconds"
PLAYER=alpha; STATE=; TRACK=; ART=; NEXT=; PREVIOUS=; SEEK=; CONTROL=; RATE=; PRESENCE=; AT=
[ $# -gt 0 ] || { echo "words: $WORDS"; exit 1; }
PLAYER_WORD=
put() {  # VARIABLE VALUE WORD: one word for each thing
  eval "current=\\$$1"
  [ -z "$current" ] || [ "$current" = "$2" ] || { echo "'$3' and the word before it say two things about the same thing"; exit 1; }
  eval "$1=\\$2"
}
for word in "$@"; do
  case $word in
    alpha|beta|chrome|integration) [ -z "$PLAYER_WORD" ] || [ "$PLAYER_WORD" = "$word" ] || { echo "one player at a time, not '$PLAYER_WORD' and '$word'"; exit 1; }
                                   PLAYER_WORD=$word; PLAYER=$word ;;
    playing|paused|stopped) put STATE "$word" "$word" ;;
    track1|track2|notitle) put TRACK "$word" "$word" ;;
    art|noart|httpart|missingart) put ART "$word" "$word" ;;
    next|nonext) put NEXT "$word" "$word" ;;
    previous|noprevious) put PREVIOUS "$word" "$word" ;;
    seek|noseek) put SEEK "$word" "$word" ;;
    control|nocontrol) put CONTROL "$word" "$word" ;;
    fast|normal) put RATE "$word" "$word" ;;
    away|back) put PRESENCE "$word" "$word" ;;
    ''|*[!0-9]*) echo "unknown word '$word'; the words: $WORDS"; exit 1 ;;
    *) put AT "$word" "$word" ;;
  esac
done
call() {  # METHOD SIGNATURE ARGUMENT...
  local method=$1 signature=$2; shift 2
  busctl --address="$ADDR" call org.tess.FakeMpris /org/tess/Fake org.tess.FakeMpris.Control \\
    "$method" "$signature" "$@" >/dev/null || exit 1
}
[ "$PRESENCE" != back ] || call Presence ss "$PLAYER" back
[ -z "$TRACK" ] || call Track ss "$PLAYER" "$TRACK"
[ -z "$ART" ] || call Art ss "$PLAYER" "$ART"
case $NEXT in next) call Can ssb "$PLAYER" next true ;; nonext) call Can ssb "$PLAYER" next false ;; esac
case $PREVIOUS in previous) call Can ssb "$PLAYER" previous true ;; noprevious) call Can ssb "$PLAYER" previous false ;; esac
case $SEEK in seek) call Can ssb "$PLAYER" seek true ;; noseek) call Can ssb "$PLAYER" seek false ;; esac
case $CONTROL in control) call Can ssb "$PLAYER" control true ;; nocontrol) call Can ssb "$PLAYER" control false ;; esac
case $RATE in fast) call Rate sd "$PLAYER" 2 ;; normal) call Rate sd "$PLAYER" 1 ;; esac
[ -z "$STATE" ] || call State ss "$PLAYER" "$(echo "$STATE" | sed 's/^./\\U&/')"
[ -z "$AT" ] || call Seek sx "$PLAYER" "$AT"
[ "$PRESENCE" != away ] || call Presence ss "$PLAYER" away
echo "fake player $PLAYER: $*"
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
        + f'{BIN}/python {REPO}/tests/kwin/fake_mpris.py --root "$ROOT" &\n'
        + "FAKE=$!\n"
        + "trap 'kill \"$FAKE\" 2>/dev/null' EXIT\n"
        + 'for _ in $(seq 100); do [ -s "$ROOT/bus-address" ] && break; sleep 0.1; done\n'
        + '[ -s "$ROOT/bus-address" ] || { echo "the fake players did not start"; exit 1; }\n'
        + 'export DBUS_SESSION_BUS_ADDRESS=$(cat "$ROOT/bus-address")\n'
        + 'echo "session bus (private): $DBUS_SESSION_BUS_ADDRESS"\n'
        + f"{BIN}/tesserae-shell run --config-dir {CFG}\n",
    )
    script("media-set.sh", MEDIA_SET)
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
