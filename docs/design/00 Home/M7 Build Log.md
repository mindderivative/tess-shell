---
title: M7 Build Log
aliases: [M7 Log]
type: moc
status: draft
owner: phil
created: 2026-11-20
updated: 2026-11-21
tags: [moc, build-log]
---

# M7 Build Log

> [!NOTE]
> The log of the M7 parts built by the `tess-shell` code sessions ([M7 Brief](M7%20Brief.md)). The code session `tess-shell` (an Orca bot) owns this note ([Build Logs](Build%20Logs.md)). The earlier M7 parts (M7a to M7h) were reported in the [M7 Brief](M7%20Brief.md) Progress table by the vault session and have no entries here; this note starts with M7k and was created by the code session because none existed (2026-11-20).

## Tasks

| Task | State | Commit | Note |
|---|---|---|---|
| M7k click-away for the Launcher | Built and VERIFIED by the maintainer on the real KWin (2026-11-21, fixed-height Launcher): first build #108 reverted (#111), fix-forward #113 merged | `66dfab3` (#113) |
| M7i content-sized Panels, Launcher on Height AUTO | Merged (#116, schema 1.14); VERIFIED by the maintainer on the real KWin (2026-11-21): the Launcher resized to fit its content, no jump or flicker reported | #116 |
| M7j announcements through one window, TextInput Active_Descendant (ADR-0023) | Merged (#117, schema 1.15); AT-SPI conformance test in PR #118; Orca not run | #117 |

## Measurements

M7k (2026-11-20, the maintainer's machine, headless): `ruff check` and `ruff format --check` clean, `mypy` clean (166 files). Live test `tests/test_launcher_live.py::test_a_click_on_the_desktop_closes_the_launcher_every_time_it_was_shown` passes on the private sway (the Launcher is shown twice and each time a virtual-pointer click on the empty desktop hides it); the unit test `tests/test_launcher.py::test_a_launcher_that_had_the_keyboard_closes_when_another_surface_of_the_shell_takes_it` passes. The full suite result is in the PR description.

M7k KWin hand check (2026-11-20, the maintainer's real KWin, HDMI-A-1, a throwaway config): FAILED. The maintainer could not type into the Launcher's field, and clicks that were not on the field closed it. The code session's first reading of the log ("8 of 8 outside clicks worked") missed this and is withdrawn. Reproduced the same day in the private KWin of the existing launcher kit (`tests/test_kwin_launcher_kit.py`) on main with M7k: the Launcher gets "keyboard gained" and 5 ms later "keyboard lost" at every show, and the kit steps that type into the field fail (2 to 6 and 8). Cause (diagnosis, not yet proved by removing the catcher alone): the click catcher, a `PopupWindow(grab=True)`, takes the keyboard on KWin, as an xdg_popup grab does; tre's own test of the recipe ran on sway only, where the panel kept the keyboard. The text was black on dark because the throwaway config had no `Appearance { Stylesheets: [Default] }` (the default is no stylesheet), not because of M7k.

M7k verification (2026-11-21, relayed by the Orchestrator from the maintainer's hand check on the real KWin, fixed-height Launcher): typing works, a click outside closes it, a row click closes it, Escape closes it, the search narrows as typed, clicks on the field and around it do not close it. M7i (AUTO) was confirmed by the maintainer on the real KWin the same day (the panel resized to fit its content, no jump or flicker reported). M7j (the screen-reader contract) is not confirmed by the maintainer; its proof is the AT-SPI test of PR #118. The M7 measurements (M7a2 cell P, M7c re-read) remain for an attended machine.

## Differences from the Specs

[Applications Module > Opening](../40%20Specifications/Modules/Applications%20Module.md#opening) says the click-away uses tre's `active` event (keyboard taken away) and the popup grab. Built as follows, and the first differs:

- The popup grab as tre's recipe says: a transparent 1 by 1 `PopupWindow(grab=True)` made at each show; `closed` with reason `dismissed` hides the Panel.
- `active` is used only when another surface of the shell gains the keyboard after the Launcher had it. A keyboard that is only lost closes nothing, because the compositor also sends a leave when the seat's last keyboard device goes (the `wtype` virtual keyboard of every live test ends after each key, and a real KVM switch or unplugged keyboard does the same): closing on that made the existing Launcher live tests fail (the Launcher closed between two typed keys). Reported for the spec: the verified case in tre's test (a second exclusive surface) is covered; another client's exclusive surface (a lock screen) does not close the Launcher.
- Scope: only a Panel with `Keyboard: EXCLUSIVE` that holds a use of the Applications module (the shipped `Launcher` or a user's own Panel with the module). A user's other exclusive Panel is unchanged; no TDL key was added. If the maintainer wants it for every exclusive Panel, or as a Panel key, that is a design change.

## Facts About tre, TEL and tess_dl

tesserae-engine 0.6.9, 2026-11-20, a private sway (headless): the catcher `PopupWindow(window, size=(1, 1), anchor_rect=(0, 0, 1, 1), grab=True)` made right after a Panel is shown (surface kept) is accepted and a virtual-pointer click on the empty desktop dismisses it with reason `dismissed`; the Panel keeps the keyboard until the shell hides it. A second exclusive Panel of the shell does NOT take the keyboard from the first on sway (the first keeps it), unlike tre's own test where the second surface was created later and gained it; so the keyboard-taken path is unit-tested, not driven live. The click is swallowed by the dismissal, as tre said.

## Decisions Needed

1. Is the scope right (the Launcher only, found by the Applications module on an exclusive Panel), or should every `Keyboard: EXCLUSIVE` Panel close on a click away? Recommendation: keep it to the Launcher until a second user of it exists; a general rule would be a Panel key and a schema change.
2. KWin: the popup-grab recipe of TRE-REQ-024 does not work for the Launcher on KWin (it takes the keyboard). Recommendation: keep it reverted (PR #111) and ask tre for a real `outside_press`, or try `Keyboard: ON_DEMAND` on KWin, where a click elsewhere moves focus and `active` goes false; ON_DEMAND is the maintainer's earlier decision to revisit.
3. Should a shell with no `Stylesheets` key fall back to `Default`? Without it every shipped widget (Button, Toggle, Checkbox, Slider, ProgressBar, Badge, list rows, the text colour of fields) is unstyled, so the shipped Launcher is unreadable on a dark desktop.

## For the Vault Session

- [Applications Module](../40%20Specifications/Modules/Applications%20Module.md) Opening, the click-away bullet: change "The shell builds click-away with it" to say what is built (above), including that the keyboard rule needs another shell surface to gain it.
- The guide page `docs/guide/keyboard.md` and `CHANGELOG.md` (new `Unreleased` heading) carry the user-facing text.
- Not done and needs the maintainer's attended machine (not run by the code session): the M7a2 product cell P re-reading and the M7c budget re-read (B18 and B01 on an idle machine). Commands are in the PR description.

## Links

- [Build Logs](Build%20Logs.md) · [M7 Brief](M7%20Brief.md) · [M6 Build Log](M6%20Build%20Log.md) · [Applications Module](../40%20Specifications/Modules/Applications%20Module.md)
