"""Regenerate the M5f Tray KWin check in /tmp/tess-kwin-m5f (not collected by pytest).

Run from the repo root: ``uv run python tests/kwin/prepare_m5f_gallery.py``. It writes a scratch
config and scripts under ``/tmp/tess-kwin-m5f`` and starts nothing. The Bar shows the Tray (the
icons of every application that registers a StatusNotifierItem) and the Clock, all coloured by
theme tokens, so it follows Plasma's light and dark. The shell file writes NO Popup: the
shell provides ``Tray_Menu``, ``Tray_Menu_2`` and ``Tray_Menu_3`` (an item's menu and its two
levels of submenu; ``Max_Height: 60%``). ``run-override.sh`` is the fake run with a Popup of the
same name written in the shell file, which replaces the shipped ``Tray_Menu``.

* ``run.sh``: the shell on YOUR REAL session bus. The Tray reads the real watcher and shows your real
  tray items beside Plasma's own tray (the shell is a second host). **A click on an icon calls the
  application's own method (``Activate``, ``SecondaryActivate``, ``Scroll``, ``ContextMenu``), and a
  click on an entry of its menu runs that entry in the application**: the checklist marks every line
  that does, and says which lines to leave alone.
* ``run-fake.sh``: the shell on a PRIVATE session bus (``tests/kwin/fake_tray.py``: its own daemon
  on a socket under ``/tmp/tess-kwin-m5f/run``; the shell is told that bus with
  ``DBUS_SESSION_BUS_ADDRESS`` and nothing else, so it cannot reach your real bus or your real
  items). A fake watcher and five fake items; every call the shell makes on them is written to
  ``fake.log``. ``tray-set.sh`` changes the fakes (any words, in any order; an unknown word is
  refused).
* ``run-override.sh``: ``run-fake.sh`` with a ``Tray_Menu`` Popup of the user's own in the shell file
  (a primary-coloured menu with sharp corners, 180 px at most, 12 px below the Bar).
* ``check.sh``: ``tesserae-shell check`` on the config.
* ``checklist.txt``: every line to check, in one list.

The state directory is ``/tmp/tess-kwin-m5f/state``, never the real one. Part 2 and the fakes never
touch your real session bus or your real tray items.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from tests.shell_samples import write_example  # noqa: E402

ROOT = Path("/tmp/tess-kwin-m5f")
CFG = ROOT / "gallery"
CFG_OVERRIDE = ROOT / "gallery-override"
BIN = Path.home() / "Projects/pyDev/pyEnvs/tess-shell/bin"
SETTINGS = (
    "---\nTDL: 0.1\nName: Settings\n---\nSettings {\n  Logging { Level: DEBUG }\n"
    "  Appearance { Stylesheets: [Default], Follow_Desktop: true }\n}\n"
)
BAR = """
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
                            Tray { icon_size: 20 }
                            Clock { }
                        }
                    }
                }
            }
%s        }
    }
}
"""
# the shell file writes NO Popup: the shell provides Tray_Menu, Tray_Menu_2 and Tray_Menu_3
BODY = BAR % ""
# the variant that overrides the shipped Tray_Menu with a Popup of the same name (Max_Height in
# pixels, opening above the Bar's row): the two other Popups stay the shipped ones
OVERRIDE = """            Popup {
                Name: Tray_Menu
                Attach: BOTTOM
                Gap: 12
                Max_Height: 180
                Style { Background: $color.primary, Corner_Radius: 2 }
                Children { Tray_Menu { Level: 1 } }
            }
"""
BODY_OVERRIDE = BAR % OVERRIDE

CHECKLIST = """M5f Tray: one list, every line to run.  Do it in light and in dark (Plasma's colour scheme;
every colour is a theme token).  The Bar shows, at the right: the Tray (one icon for each application
that registers a StatusNotifierItem) and the Clock.  The shell is a SECOND tray host: Plasma's own
tray keeps working beside it, and an application may be activated from either.

PART 1: on this desktop, your REAL session bus and your REAL tray items  (start with
/tmp/tess-kwin-m5f/run.sh)
THIS PART CALLS YOUR REAL APPLICATIONS.  Every line is marked: [reads only] touches nothing;
[ACTS on a real item] sends the application a real call (Activate, SecondaryActivate, Scroll or
ContextMenu: it may open a window, toggle something or change a setting, as a click on its icon in
Plasma's tray does); [ACTS through a real menu] a click on an entry of the application's own menu RUNS
that entry in the application (a "Quit" quits it).  Pick an item you can afford to poke (the item you
read on 2026-11-13, Cachy-Update, opens its update window on a click and its menu has an entry that
starts an update: do NOT click that entry).  Lines 3 to 6 name no application: use the same harmless
one throughout, and leave every menu entry alone except where a line says to click one.

 1  [reads only] The Tray shows one icon for each item Plasma's tray shows (not the hidden passive
    ones), in the order they registered, with the right pictures (your theme's icons, or the
    application's own pixmap; a plain outline of a window is the fallback for an icon nobody can
    find); point at one: a tooltip opens with its title and text.  The Clock is at the right of it.
 2  [reads only] `grep -E "WARNING|ERROR"` on the shell's output: no line.  `busctl --user list |
    grep StatusNotifierHost` shows two hosts: plasmashell's and `org.kde.StatusNotifierHost-<the
    shell's pid>`.
 3  [ACTS on a real item] Left-click an icon: the application's own action (Activate) happens, once,
    as from Plasma's tray.  (If the application's icon marks "item is a menu", the click opens its
    menu instead: line 5.)
 4  [ACTS on a real item] Middle-click it: SecondaryActivate (many applications do nothing or toggle
    something).  Scroll one notch over it: Scroll (an audio or media application may change volume).
 5  [reads only] Right-click an icon (or left-click a menu item): the SHELL's own menu opens below the
    row, drawn in the shell's look from the application's menu: the labels, the separators, a check
    mark or a radio dot where the application has them, the key hints, a disabled entry greyed.
    Choose nothing: click outside the menu, or press Escape; it closes.  An application with no menu
    gets its own menu from the application instead (ContextMenu).
 6  [ACTS through a real menu] Click ONE harmless entry of an application's menu: the menu closes and
    the application does what the entry says.  Open the same menu again: it is as the application
    has it now.
 7  [reads only] Open a menu that has a submenu: click or rest the pointer on its row: the submenu
    opens beside it (and a third level beside that); a menu longer than the screen scrolls.
 8  [reads only] While a menu is open, start or quit another tray application: nothing breaks; an
    application that quits while its own menu is open closes the menu.
 9  [reads only] Quit one tray application: its icon goes (no gap, no placeholder).  Start it again:
    its icon returns, last.
10  [reads only] The log has no ERROR line after all of the above.

PART 2: a fake watcher and fake items on a private session bus  (stop part 1; start
/tmp/tess-kwin-m5f/run-fake.sh; in a second terminal use /tmp/tess-kwin-m5f/tray-set.sh)
The fakes are programs of ours on their own private bus: nothing here touches your real session bus
or your real tray items.  The shell reads that private bus only, which has no Settings portal: the
look is the Default theme's dark, and the log has one WARNING about it at start.  Five items: `mail`
(a theme icon; a menu with every kind of entry), `chat` (a picture only, no menu), `sync` (its own icon folder, an attention icon, ItemIsMenu),
`update` (a menu with a submenu of 95 entries) and `ghost` (Passive: hidden).  tray-set.sh takes its
words in any order: mail | chat | sync | update | ghost (the item the other words are about; mail
when none), active | passive | attention (its status), retitle, retip, swap (its icon), relabel (its
menu's first entry), away | back (it leaves the bus without unregistering, or returns),
unregister | register, and, about the watcher, nowatcher | watcher | restart.  Every word it does not
know, and every contradiction, is refused with a message and changes nothing.  Every call the shell
makes on the fakes is written to /tmp/tess-kwin-m5f/fake.log (`tail -f` it).

11  At start the Bar shows four icons: Mail (your theme's mail icon, or the window outline), Chat (a
    22 by 22 picture, red to blue, with its top left corner clear), Sync (a blue disc with an S) and
    Update; Ghost is not shown.  fake.log has ONE line `watcher RegisterStatusNotifierHost
    org.kde.StatusNotifierHost-<the shell's pid>`.  `busctl --address=$(cat
    /tmp/tess-kwin-m5f/bus-address) list | grep StatusNotifierHost` shows that name.
12  Point at each icon: a tooltip with its title and its text ("Mail" "3 unread messages", "Chat",
    "Sync" "Up to date", "Update" "95 updates").  Move to the next icon: the first tooltip closes.
13  Left-click Mail: fake.log gets `mail Activate X Y` once, X and Y near where you clicked.  Middle
    click: `mail SecondaryActivate X Y`.  Scroll one notch down over it: `mail Scroll -120 vertical`;
    one notch up: `mail Scroll 120 vertical`.
14  Left-click Sync (it is a menu): no Activate in fake.log; the Popup opens with "Sync now" and
    "Pause" (a check box, not checked).  Click "Pause": `sync menu Event 2 clicked` once and the
    menu closes.
15  Right-click Chat (no menu): fake.log gets `chat ContextMenu X Y`; no Popup opens.
16  Right-click Mail: the menu opens below the row: "Open Window" (the mnemonic's underscore is not
    shown), a thin rule, "Disabled" (greyed), "Checked" with a check mark, "Radio on" with a filled
    dot, "Radio off" with an empty one, "Quit" with the key hint "Ctrl+Q" and its icon (if your theme
    has it), and "More" with an arrow.  The entry the fake marks invisible is not there.  fake.log
    shows `mail menu AboutToShow 0` and `mail menu GetLayout 0 -1` before the menu appeared.  Click
    "Disabled": nothing, no line in fake.log.  Click "Quit": `mail menu Event 7 clicked` once and the
    menu closes.
17  Right-click Mail, click "More": a submenu opens beside the row with "First" and "Deeper"; click
    "Deeper": a third level opens with "Level three" and no arrow; the fake's fourth level ("Level
    four") is not shown.  Click "Level three": `mail menu Event 12 clicked`, and all three levels
    close.  Clicking a row that opens a submenu sends no Event.
18  Right-click Update: the menu shows "95 updates available" and "All (95)"; the submenu of 95
    entries scrolls (wheel) and stays inside the screen; click "package-07": `update menu Event 16
    clicked`.
19  `tray-set.sh relabel`: with Mail's menu CLOSED nothing happens on the Bar.  Open Mail's menu and
    in the second terminal `tray-set.sh relabel`: the menu is drawn again with "Changed label" first
    (it may blink once); run it again: "Back".  Close the menu: a later `tray-set.sh relabel` opens
    nothing.
20  `tray-set.sh sync attention`: Sync's icon turns to the orange disc with "!" and gets the warning
    colour outline; its tooltip is as before.  `tray-set.sh sync active`: the blue disc again.
21  `tray-set.sh ghost active`: Ghost appears (an outline icon or your theme's information icon), last
    in the row; `tray-set.sh ghost passive`: it goes again.
22  `tray-set.sh mail retitle retip`: the tooltip of Mail now reads "Renamed" with "Renamed:
    changed".  `tray-set.sh sync swap`: Sync's icon is a green disc with A; again: a purple disc
    with B.  The row does not jump.
23  `tray-set.sh chat away`: Chat disappears at once (it left the bus without unregistering) with no
    gap.  `tray-set.sh chat back`: it returns, last.
24  `tray-set.sh mail unregister`: Mail disappears.  `tray-set.sh mail register`: it returns, last.
25  Open Update's menu, then in the second terminal `tray-set.sh update away`: the open menu closes
    and the icon goes.  `tray-set.sh update back`: the icon returns.
26  `tray-set.sh nowatcher`: the whole Tray disappears with no placeholder and no gap (the Clock moves
    right); the log has one WARNING "StatusNotifierWatcher left the session bus" (expected).
    `tray-set.sh watcher`: the icons return and fake.log has a SECOND `RegisterStatusNotifierHost`
    line.  `tray-set.sh restart`: the same again (a third line).
27  `tray-set.sh bogus`: a message that names the word and lists the words; nothing changes.
    `tray-set.sh mail chat` (two items), `tray-set.sh active passive` and `tray-set.sh away back`
    are refused too, and change nothing.
28  Log: no ERROR line; the only WARNING lines are the one "portal: the Settings portal is not
    available" at start (the private bus has none: the look is the Default theme's dark) and the
    "left the session bus" ones of line 26 (at most one a minute).  `top -p $(pgrep -f 'tesserae-shell
    run')` shows the shell idle (0 % CPU) when you stop touching it.
29  The shell's own Popups: in every run above the config writes no Popup, and the menus of lines 14
    to 18 are the shell's: dark raised background, rounded corners, a long menu (line 18) stops at
    60 % of the screen's height and scrolls.  Each menu opens below the CLICKED icon (its left edge
    at the icon's left edge), not under the whole row.  Stop the run; start
    /tmp/tess-kwin-m5f/run-override.sh (the same fakes; the shell file now writes a Popup named
    Tray_Menu): right-click Mail: the menu is the user's (primary colour, square corners, 12 px
    below the Bar, at most 180 px high: scroll it) and its submenu ("More") is still the shell's.
30  The clicks name the icon's centre: left-click Mail near its edge: fake.log gets `mail Activate X
    Y` with X and Y the centre of the icon on the screen, the same numbers wherever on the icon you
    click.
"""

TRAY_SET = """# tray-set.sh WORD...  (the words in any order; every other word is refused)
#   mail | chat | sync | update | ghost   the item the other words are about (default mail)
#   active | passive | attention          its status
#   retitle | retip                       its title, its tooltip
#   swap                                  its icon (from the kit's own icon folder)
#   relabel                               the first entry of its menu
#   away | back                           it leaves the bus without unregistering, or returns
#   unregister | register                 it tells the watcher
#   nowatcher | watcher | restart         the watcher leaves, returns, or restarts
# Talks to the fake watcher and items only.
ROOT=${TESS_M5F_ROOT:-/tmp/tess-kwin-m5f}
ADDR=$(cat "$ROOT/bus-address" 2>/dev/null) || { echo "run-fake.sh is not running"; exit 1; }
WORDS="mail, chat, sync, update, ghost, active, passive, attention, retitle, retip, swap, relabel, away, back, unregister, register, nowatcher, watcher, restart"
ITEM=mail; ITEM_WORD=; STATE=; TITLE=; TIP=; SWAP=; RELABEL=; PRESENCE=; WATCHER=
[ $# -gt 0 ] || { echo "words: $WORDS"; exit 1; }
put() {  # VARIABLE VALUE WORD: one word for each thing
  eval "current=\\$$1"
  [ -z "$current" ] || [ "$current" = "$2" ] || { echo "'$3' and the word before it say two things about the same thing"; exit 1; }
  eval "$1=\\$2"
}
for word in "$@"; do
  case $word in
    mail|chat|sync|update|ghost) [ -z "$ITEM_WORD" ] || [ "$ITEM_WORD" = "$word" ] || { echo "one item at a time, not '$ITEM_WORD' and '$word'"; exit 1; }
                                 ITEM_WORD=$word; ITEM=$word ;;
    active|passive|attention) put STATE "$word" "$word" ;;
    retitle) TITLE=1 ;;
    retip) TIP=1 ;;
    swap) SWAP=1 ;;
    relabel) RELABEL=1 ;;
    away|back|unregister|register) put PRESENCE "$word" "$word" ;;
    nowatcher|watcher|restart) put WATCHER "$word" "$word" ;;
    *) echo "unknown word '$word'; the words: $WORDS"; exit 1 ;;
  esac
done
call() {  # METHOD SIGNATURE ARGUMENT...
  local method=$1 signature=$2; shift 2
  busctl --address="$ADDR" call org.tess.FakeTray /org/tess/Fake org.tess.FakeTray.Control \\
    "$method" "$signature" "$@" >/dev/null || exit 1
}
case $WATCHER in
  watcher) call Watcher s back ;;
  restart) call Watcher s restart ;;
esac
case $PRESENCE in back|register) call Item ss "$ITEM" "$PRESENCE" ;; esac
case $STATE in active) call State ss "$ITEM" Active ;; passive) call State ss "$ITEM" Passive ;; attention) call State ss "$ITEM" NeedsAttention ;; esac
[ -z "$TITLE" ] || call Text sss "$ITEM" title Renamed
[ -z "$TIP" ] || call Text sss "$ITEM" tip Renamed
[ -z "$SWAP" ] || call Swap s "$ITEM"
[ -z "$RELABEL" ] || call Relabel s "$ITEM"
case $PRESENCE in away|unregister) call Item ss "$ITEM" "$PRESENCE" ;; esac
[ "$WATCHER" != nowatcher ] || call Watcher s away
echo "fake tray $ITEM: $*"
"""

REAL_WARNING = (
    'echo "REAL session bus: a click on an icon CALLS your real application, and a click on an entry '
    'of its menu RUNS that entry (checklist, part 1: the lines marked [ACTS ...])." >&2\n'
)


def script(name: str, text: str) -> None:
    path = ROOT / name
    path.write_text("#!/usr/bin/env bash\n" + text)
    path.chmod(0o755)


def run_fake(cfg: Path) -> str:
    """``run-fake.sh``: the fakes on a private bus, and the shell on that bus and no other."""
    return (
        f"export XDG_STATE_HOME={ROOT}/state\n"
        + f"ROOT={ROOT}\n"
        + 'rm -f "$ROOT/bus-address" "$ROOT/fake.pid"\n'
        + f'{BIN}/python {REPO}/tests/kwin/fake_tray.py --root "$ROOT" &\n'
        + "FAKE=$!\n"
        + "trap 'kill \"$FAKE\" 2>/dev/null' EXIT\n"
        + 'for _ in $(seq 100); do [ -s "$ROOT/bus-address" ] && break; sleep 0.1; done\n'
        + '[ -s "$ROOT/bus-address" ] || { echo "the fake tray did not start"; exit 1; }\n'
        + "# the shell is told this bus and nothing else: it cannot reach the real session bus\n"
        + 'export DBUS_SESSION_BUS_ADDRESS=$(cat "$ROOT/bus-address")\n'
        + 'echo "session bus (private): $DBUS_SESSION_BUS_ADDRESS"\n'
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
    # the same private fake bus, with a Popup of the user's own that overrides the shipped one
    script("run-override.sh", run_fake(CFG_OVERRIDE))
    script("tray-set.sh", TRAY_SET)
    print(f"wrote {ROOT}")


if __name__ == "__main__":
    main()
