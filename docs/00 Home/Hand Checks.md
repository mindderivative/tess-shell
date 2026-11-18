---
title: Hand Checks
aliases: [Maintainer Checks, KWin Checks, Checklists]
type: quality
status: review
owner: phil
created: 2026-11-16
updated: 2026-11-17
tags: [quality, process, needs-verification]
---

# Hand Checks

> [!NOTE]
> Every check only the maintainer can run, in one place: what it proves, how it is set up, what to do and what to expect. None of them gates a merge; the automated suites do ([Testing Strategy](../60%20Quality/Testing%20Strategy.md)). A check that runs on the real session is set up by a kit that the code session generates (`tests/kwin/prepare_*.py` in the `tess-shell` repository, which writes under `/tmp/tess-kwin-*` and starts nothing). `/tmp` is emptied by a reboot, so the kit is made again with the command in the table. Written on 2026-11-16 after the maintainer asked where the checklist for the tre 0.6.8 checks is. The vault session reads the kit scripts' headers but has not run any kit.

## How a kit is used

1. In the `tess-shell` checkout, from the repository root, run the generator named in the table (`uv run python tests/kwin/prepare_<name>.py`, with `env -u WAYLAND_DISPLAY -u DISPLAY` in front for the ones that say so). It writes the kit folder and starts nothing.
2. In the kit folder: `check.sh` checks the configuration, `run.sh` starts the shell on your session, and `checklist.txt` lists every line to check.
3. A kit that registers shortcuts with the real service has a `backup.sh`: run it first.

## The rule for checks (maintainer, 2026-11-16)

> [!IMPORTANT]
> **A check that a session can run and verify is the session's, not yours**
> The maintainer wrote this after running the `install-session` kit by hand, where most lines were copying terminal output into a file for a session to read. A kit line that a script can run and judge is run and judged by the code session, with the output kept in a file the session reads. What is left for the maintainer is only what no session can do: looking at the screen, pressing physical keys, logging out and in, real hardware. If a session needs permission to run something on his real session, to use his terminal or to start a process outside its sandbox, it says so in his chat and asks once for that named action; with his yes it runs it itself and reports pass or fail. It never turns a verifiable step into a paste for him.

What this means for a kit, and what the code session did on 2026-11-16 (`tess-shell` PR #44, reported; not run in the vault): every script writes its result (command, output, exit code, pass or fail) to a file under the kit folder; one `run-all.sh` runs every line that can be run unattended, compares the output with what the checklist expects and writes `results.txt`; `checklist.txt` keeps only the lines that need the maintainer, each saying why a session cannot do it. The earlier rule that no session touches the real session without leave ([Orchestration Log](Orchestration%20Log.md) D-019) stands as the default: the grant is the maintainer's yes in chat, for the named action.

> [!CAUTION]
> **Never a physical hot-plug (maintainer, 2026-11-17)**
> No kit, checklist or session asks the maintainer to plug or pull a monitor cable or a monitor's power. There is a real risk of an electrical surge ruining a monitor. Multi-monitor and hot-plug are tested on virtual outputs in the sandbox ([Risk Register](Risk%20Register.md) R-33). The maintainer's own real tests (monitors switched off and on, monitor power removed and restored) worked as expected on 2026-11-17: the shell came back each time.

## State of the kits (code session's reports, 2026-11-16)

- The kits are converted. A shared `tests/kitlib.py` runs steps in private sandboxes (a private session bus and runtime dir; a real KWin 6.8.2 started as `kwin_wayland --virtual` with its own `kglobalaccel`; a real systemd user manager as `systemd --user`; a private sway). Each `run-all.sh` writes `results.txt`; install-session 8 PASS, tre068 4 PASS and 4 SKIP, m5g 6 PASS and 5 SKIP, m6c 6 PASS and 4 SKIP, the launcher 4 PASS and 3 SKIP, 0 FAIL, the real session untouched.
- The tre 0.6.8 lines were asserted by the session: Tab order TextEditor, TextInput, Button with a ring (from the shell's focus log driven by key events); a popup opened and closed in one turn leaves no `xdg_popup` in the protocol trace, once and 20 times (the trace is proven to catch a popup left open); the activation token reaches a fake program as `XDG_ACTIVATION_TOKEN`. Still the maintainer's: the focus ring and a stuck popup by eye, and a real application taking focus.
- Real-session checks run by the code session with the maintainer's yes in chat (backed up, undone, the real file identical afterwards): the taken-key warning on `Ctrl+Alt+Delete` (Plasma's Log Out) passes on the real daemon; the Launcher from a global key gets the keyboard at once with `EXCLUSIVE`, and `ON_DEMAND` was not tried; the portal accepts `Register` once the desktop file is installed.
- The maintainer ran the M5g kit: lines 0 to 18 pass. Line 13 of m6c stays manual or covered by the fake, because KWin 6.8.2 hosts `org.kde.kglobalaccel` itself and the shortcut service cannot be restarted alone.
- A private KWin tests the shell's KWin protocol (script, window list, actions, input, shortcuts), not how the real KWin stacks or classifies things: where it contradicts the maintainer's own observation, the sandbox is wrong (the rule-layer claim was withdrawn).

## The M7g Kit (code session's report, 2026-11-17, not run in the vault)

- **Line 1, Orca:** the shell runs on the real session with a fake NetworkManager and a fake UPower on one private system bus (so nothing real is touched), with three battery and network states and a Launcher list (Kit Alpha, Beta, Gamma). One command per event (`orca-3-say.sh network-down`, `network-up`, `battery-critical`, `launcher-open`). The literal texts come from the modules' own functions: "Network disconnected", "Network connected, ethernet Wired connection 1", "Battery critical, 4 percent, discharging", "Kit Beta, 2 of 3", "Kit Gamma, 3 of 3", "No results". A checker reads Orca's own debug file (`orca --debug-file`) and records PASS or FAIL per text, or SKIP if that Orca writes no speech lines, and then the maintainer says what he heard. The texts are proved in the sandbox against real AT-SPI announcement signals; that run found and fixed two kit bugs.
- **Orca is not installed on the maintainer's machine** (finding): `pacman -Q orca` is empty, there is no `/usr/bin/orca`, and the `orca` command on his PATH is a shim to an unrelated AppImage (`orca-ide`). The kit calls `/usr/bin/orca` and says to install it with `sudo pacman -S orca`. Installing a package is his action.
- The Orca line's texts are asserted in the sandbox without their order across events: tre 0.6.9 scrambles the order of announcements made in one loop turn ([TRE-REQ-027 Announce Keeps Call Order](../80%20Requests/TRE-REQ-027%20Announce%20Keeps%20Call%20Order.md)), and the sandbox drives events close together. On the real run you wait for Orca between events, so the order in the checklist holds.
- **Line 2, real Wi-Fi:** his wired connection is kept. The kit takes read-only snapshots (`nmcli`, `ip`) before and after joining and leaving Wi-Fi and passes only if the wired device, connection, address and default route are exactly as before. With the cable in, wired stays the main connection, so the Wi-Fi bars and a captive portal cannot be shown on his machine without taking wired down, which the kit never does; the fake covers those states (the M5c kit).
- **Line 3, real audio:** speakers and a Bluetooth headset. `audio-2-expect.sh` prints, from the real default output and the shell's own functions, the icon and tooltip the Audio module must show (for example `bluetooth-audio` and "Phone Headset, 40 %").
- **No hot-plug line.** No kit asks for a cable or power pull any more: the M5c lines that asked to unplug the Ethernet cable now point at the fake, the M3c hot-plug check says a monitor is switched off and on, never unplugged, and a test scans the checklists for it.

## The checks

| Kit | Generator | Checks | State |
|---|---|---|---|
| `/tmp/tess-kwin-m5c` to `m5f` | `prepare_m5c_gallery.py` to `prepare_m5f_gallery.py` | Network, Media, Audio and Tray on the real session; `m5f` has a fake-tray run on a private bus beside the real one | Optional; no result reported to the vault |
| `/tmp/tess-kwin-m6a` | `prepare_m6a_gallery.py` | Focus: Tab order, `Tab_Index`, a Panel's TextInput and Checkbox | Optional; no result reported to the vault |
| `/tmp/tess-kwin-m6c` | `prepare_m6c_shortcuts.py` | Global shortcuts with the real `kglobalaccel` (copy of `kglobalshortcutsrc` first) | Run 2026-11-15: lines 1 to 10, 12 and 14 passed; 13 not run; line 11 found a real gap, fixed in `tess-shell` PR #18 |
| `/tmp/tess-kwin-m6d` | `prepare_m6d_mode.py` | Shortcut mode: the enter key, which keyboard mode KWin needs (`EXCLUSIVE` or `ON_DEMAND`) | No result reported to the vault |
| `/tmp/tess-kwin-install-session` | `prepare_install_session.py` (name from the kit's folder; not read) | `install-session`: files, verify, stale unit, enable, start, stop, log out and in, undo | Run by the maintainer 2026-11-15, lines 0 to 4 and 6 to 10 reported passing; line 5's output matches the spec, no verdict reported ([Packaging and Session Start](../70%20Delivery/Packaging%20and%20Session%20Start.md)) |
| `/tmp/tess-kwin-m5g` | `prepare_m5g_*` (not read) | The KWin script in the real KWin, the rule file, names the code could not confirm from files | Exists; no result reported |
| `/tmp/tess-kwin-launcher` | `prepare_m6d_launcher*` (not read) | The Launcher on KWin: open, search, start, focus; `real-start.sh` needs no desktop | Exists; no result reported |
| `/tmp/tess-kwin-m7g` | `tests/kwin/prepare_m7g_hardware.py` (starts nothing) | The three real-hardware lines: Orca, real Wi-Fi with the wired connection kept, real audio with speakers and a Bluetooth headset. Every script writes to `results/` and one line to `results.txt`; no copying from a terminal | Merged 2026-11-17 (`tess-shell` PR #57), not run by the maintainer yet. Orca is not installed on his machine (see below) |
| `/tmp/tess-kwin-tre068` | `prepare_tre068.py` | The three tre 0.6.8 checks below (`run-tab.sh`, `run-popup.sh`, `run-token.sh`, `check.sh`) | Exists (written by the code session); no result reported |

## tre 0.6.8 checks

The kit `/tmp/tess-kwin-tre068` exists (found on 2026-11-16; its `checklist.txt` matches the three parts below). Under the rule above, the lines a session can judge from the log or the accessibility tree should be run by it; the lines that need your eyes are the focus ring, a popup left on screen, and the application window taking focus:

### 1. Tab leaves a multi-line TextEditor ([TRE-REQ-018 Tab Leaves a Multi-Line Text Input](../80%20Requests/TRE-REQ-018%20Tab%20Leaves%20a%20Multi-Line%20Text%20Input.md))

Setup in the kit: a Panel with `Keyboard: ON_DEMAND` holding a `TextEditor`, a single-line `TextInput` and a Button after it, in that order.

| Step | Expect |
|---|---|
| Click into the TextEditor and type two lines | The text appears; Enter makes a new line |
| Press Tab | Focus moves to the next control (the TextInput shows its focus ring); no tab character was typed into the TextEditor |
| Press Shift+Tab | Focus returns to the TextEditor with its text and caret unchanged |
| Press Tab in the single-line TextInput | Focus moves on, as before |
| Press Tab from the last control | Focus wraps or leaves as the focus rules say ([Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md)) |

### 2. A popup closed before it is placed ([TRE-REQ-019 Popup Close Before Placement](../80%20Requests/TRE-REQ-019%20Popup%20Close%20Before%20Placement.md))

Setup in the kit: a Bar with a Button whose handler opens a Popup and closes it in the same turn, and a second Button that does this 20 times in a row; plus the existing tray or tooltip popups for the manual version.

| Step | Expect |
|---|---|
| Click the single open-and-close Button | No popup is left on screen; the log has no warning about a popup that stayed |
| Click the 20-times Button | Nothing is left on screen afterwards, and the compositor shows no flash that stays |
| Open and dismiss a tray menu with the keyboard (Escape straight after the click) 20 times | No menu stays on screen |

### 3. The activation token ([Applications Module](../40%20Specifications/Modules/Applications%20Module.md))

The shell's launcher (task T-049) is not built, so the shell does not yet call `Window.request_activation_token`. Until it is, the kit carries a throwaway tre-only script: a Bar with one button that asks for a token and starts an installed Wayland application with `XDG_ACTIVATION_TOKEN` set to it.

| Step | Expect |
|---|---|
| Click the button | The started application's window takes focus (its title bar active), not only appears behind the current window |
| Start the same application from a terminal for comparison | Without a token KWin may leave the new window unfocused (focus-stealing prevention); this is the difference the token fixes |
| Note the callback | The token is a non-empty string; if `None`, the compositor did not offer `xdg_activation_v1` |

When the launcher exists, this check moves into the launcher's kit: open the Launcher with its shortcut, pick an application, and expect the same.

## What to report back

Pass or fail per line, with the kit's log file if a line fails. The vault then marks [TRE-REQ-018 Tab Leaves a Multi-Line Text Input](../80%20Requests/TRE-REQ-018%20Tab%20Leaves%20a%20Multi-Line%20Text%20Input.md) and [TRE-REQ-019 Popup Close Before Placement](../80%20Requests/TRE-REQ-019%20Popup%20Close%20Before%20Placement.md) `stable` when their lines pass. Nothing else is needed from you.

## Questions After Testing

1. [ ] Which keyboard mode does shortcut mode need on KWin, `EXCLUSIVE` or `ON_DEMAND`? Context: decided to keep `EXCLUSIVE` until a check says otherwise ([Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md)). Recommendation: run the `m6d` kit with `Debug { Mode_Keyboard: ON_DEMAND }` and report whether keys still arrive. Answered by: the `m6d` kit.

## Links

[Home](Home.md) · [Testing Strategy](../60%20Quality/Testing%20Strategy.md) · [Global Shortcuts](../40%20Specifications/Integration/Global%20Shortcuts.md) · [Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md)
