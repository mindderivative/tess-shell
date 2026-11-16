---
title: Hand Checks
aliases: [Maintainer Checks, KWin Checks, Checklists]
type: quality
status: review
owner: phil
created: 2026-11-16
updated: 2026-11-16
tags: [quality, process, needs-verification]
---

# Hand Checks

> [!NOTE]
> Every check only the maintainer can run, in one place: what it proves, how it is set up, what to do and what to expect. None of them gates a merge; the automated suites do ([Testing Strategy](../60%20Quality/Testing%20Strategy.md)). A check that runs on the real session is set up by a kit that the code session generates (`tests/kwin/prepare_*.py` in the `tess-shell` repository, which writes under `/tmp/tess-kwin-*` and starts nothing). `/tmp` is emptied by a reboot, so the kit is made again with the command in the table. Written on 2026-11-16 after the maintainer asked where the checklist for the tre 0.6.8 checks is. The vault session reads the kit scripts' headers but has not run any kit.

## How a kit is used

1. In the `tess-shell` checkout, from the repository root, run the generator named in the table (`uv run python tests/kwin/prepare_<name>.py`, with `env -u WAYLAND_DISPLAY -u DISPLAY` in front for the ones that say so). It writes the kit folder and starts nothing.
2. In the kit folder: `check.sh` checks the configuration, `run.sh` starts the shell on your session, and `checklist.txt` lists every line to check.
3. A kit that registers shortcuts with the real service has a `backup.sh`: run it first.

## The checks

| Kit | Generator | Checks | State |
|---|---|---|---|
| `/tmp/tess-kwin-m5c` to `m5f` | `prepare_m5c_gallery.py` to `prepare_m5f_gallery.py` | Network, Media, Audio and Tray on the real session; `m5f` has a fake-tray run on a private bus beside the real one | Optional; no result reported to the vault |
| `/tmp/tess-kwin-m6a` | `prepare_m6a_gallery.py` | Focus: Tab order, `Tab_Index`, a Panel's TextInput and Checkbox | Optional; no result reported to the vault |
| `/tmp/tess-kwin-m6c` | `prepare_m6c_shortcuts.py` | Global shortcuts with the real `kglobalaccel` (copy of `kglobalshortcutsrc` first) | Run 2026-11-15: lines 1 to 10, 12 and 14 passed; 13 not run; line 11 found a real gap, fixed in `tess-shell` PR #18 |
| `/tmp/tess-kwin-m6d` | `prepare_m6d_mode.py` | Shortcut mode: the enter key, which keyboard mode KWin needs (`EXCLUSIVE` or `ON_DEMAND`) | No result reported to the vault |
| tre 0.6.8 | `prepare_tre068.py`, **not written yet** (asked of the code session, 2026-11-16) | The three checks below | Waiting for the kit |

## tre 0.6.8 checks (the kit does not exist yet)

No existing kit covers these: the M6a kit has a single-line `TextInput`, not a `TextEditor`, and no kit opens and closes a popup in one turn. What the new kit must contain, and what you do with it:

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
