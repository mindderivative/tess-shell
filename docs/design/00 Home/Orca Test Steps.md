---
title: Orca Test Steps
aliases: [Orca steps, M7g Orca line]
type: quality
status: draft
owner: phil
created: 2026-11-19
updated: 2026-11-19
tags: [quality/accessibility]
---

# Orca Test Steps

> [!NOTE]
> Step by step, from installing Orca to removing it, for line 1 of the M7g kit ([Hand Checks](Hand%20Checks.md)). Written 2026-11-19 from the kit generator in the code session's `tess-shell-m7r` worktree; the vault did not run the steps. Orca runs on your real session and reads your desktop aloud until you stop it; the shell runs against a fake NetworkManager and a fake UPower on a private system bus, so no real device is touched. Turn the volume up.

## 1. Install

1. Run `sudo pacman -S orca`. Version 51.1, about 5 MiB to download, 37 MiB installed. It pulls in `speech-dispatcher` (not installed yet) and several GNOME and Python libraries; `espeak-ng` is already there.
2. Check it: `/usr/bin/orca --version` must print a version.
3. The command `orca` on your PATH is another program (the `orca-ide` AppImage). Always type `/usr/bin/orca` when you check by hand.

## 2. Make the kit

1. Run `cd ~/Projects/pyDev/projects/tess-shell-m7r && uv run python tests/kwin/prepare_m7g_hardware.py`. It starts nothing and writes `/tmp/tess-kwin-m7g`.
2. Do not run it from `~/Projects/pyDev/projects/tess-shell`: that checkout is old and has no such script.

## 3. Run the test

1. Terminal A: `/tmp/tess-kwin-m7g/bin/orca-1-start-shell.sh`. A Bar appears at the top edge.
2. Terminal B: `/tmp/tess-kwin-m7g/bin/orca-2-start-orca.sh`. Wait until Orca is quiet.
3. In terminal B, one command at a time, waiting until Orca has finished each time:

| Command | Orca must say |
|---|---|
| `/tmp/tess-kwin-m7g/bin/orca-3-say.sh network-down` | Network disconnected |
| `/tmp/tess-kwin-m7g/bin/orca-3-say.sh network-up` | Network connected, ethernet Wired connection 1 |
| `/tmp/tess-kwin-m7g/bin/orca-3-say.sh battery-critical` | Battery critical, 4 percent, discharging |
| `/tmp/tess-kwin-m7g/bin/orca-3-say.sh launcher-open` | Launcher (the dialog's name, not checked) |

4. Press Down once on the keyboard: Orca must say "Kit Beta, 2 of 3". Press Down again: "Kit Gamma, 3 of 3". Type `zzz`: "No results".
5. Terminal B: `/tmp/tess-kwin-m7g/bin/orca-4-check.sh`. It reads Orca's own debug file and records PASS or FAIL for each text. SKIP means this Orca writes no speech lines: say what you heard instead.
6. The results are in `/tmp/tess-kwin-m7g/results.txt`.

Report anything odd: a delay, a text Orca did not read, or an announcement missed while the Bar was not focused. The last one is the open question of [Accessibility](../60%20Quality/Accessibility.md). Wait for Orca between events, as the table says: tre 0.6.9 scrambles announcements made in one loop turn ([TRE-REQ-027 Announce Keeps Call Order](../80%20Requests/TRE-REQ-027%20Announce%20Keeps%20Call%20Order.md)).

## 4. Stop and uninstall

1. Run `/tmp/tess-kwin-m7g/bin/orca-stop.sh`, then press Ctrl+C in terminal A.
2. Run `sudo pacman -Rns orca`. It removes Orca and the dependencies nothing else needs.
3. Run `pacman -Qdt` to list orphans and review it before removing anything.
4. `~/.local/share/orca` did not exist before the test; delete it if it appears. Leave `~/.config/orca`, which existed before.
5. Run `rm -r /tmp/tess-kwin-m7g` to remove the kit.

## Links

[Hand Checks](Hand%20Checks.md) · [Accessibility](../60%20Quality/Accessibility.md) · [M7 Brief](M7%20Brief.md)
