---
title: Performance Budgets
aliases: [Budgets, Performance Budget Ledger]
type: quality
status: review
owner: phil
created: 2026-11-02
updated: 2026-11-19
tags: [quality, performance]
---

# Performance Budgets

> [!NOTE]
> A ledger of every performance number in the design on 2026-11-02, gathered from the specs by a read-only sweep and checked against the notes it names. It does not restate each number: the spec that owns a number keeps it, and this note links to it (one source of truth). It adds three things the specs cannot: the numbers still missing, proposed values for them, and the places where two notes disagree. Nothing here is decided; the maintainer decides (AGENTS > Hard rules rule 5).

## How to Read the Ledger

| Status | Meaning |
|---|---|
| Decided | The maintainer accepted it |
| Proposed | Written in a spec as a target, not accepted, not measured |
| Measured | A number from a test; the row says what was tested and where |
| Missing | The spec implies a budget but gives no number |

A measured number from tre is a tre fact on one machine (an AMD GPU with RADV, a headless sway, or `llvmpipe`), not a promise for the shell.

## Where the Numbers Live

| Area | Owner note (its Performance Budget section) | State |
|---|---|---|
| Idle and frames, goals G4 and G5 | [Goals and Non-Goals](../10%20Vision/Goals%20and%20Non-Goals.md) | Goal text, no limit |
| Threads, loop rules, wake-ups | [Process Model and Threading > Performance Notes](../20%20Architecture/Process%20Model%20and%20Threading.md#performance-notes) | Measured by tre |
| Start, stop and timeouts | [Shell Start and Stop > Stop Sequence](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md#stop-sequence), [Shell Start and Stop > Performance Budget](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md#performance-budget) | Stop decided; start missing |
| Hot reload | [Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md) | Debounce decided; apply time missing |
| Control interface | [IPC and CLI > Performance Budget](../40%20Specifications/Runtime/IPC%20and%20CLI.md#performance-budget) | Proposed |
| D-Bus layer | [D-Bus Service Layer > Performance Budget](../40%20Specifications/Integration/D-Bus%20Service%20Layer.md#performance-budget) | Proposed |
| Shortcuts | [Global Shortcuts > Performance Budget](../40%20Specifications/Integration/Global%20Shortcuts.md#performance-budget) | Proposed |
| Portals | [Portals > Performance Budget](../40%20Specifications/Integration/Portals.md#performance-budget) | Proposed |
| Popups | [Popup > Performance Budget](../40%20Specifications/Surfaces/Popup.md#performance-budget) | Proposed |
| Surfaces and memory | [Surface Types > Performance Budget](../40%20Specifications/Surfaces/Surface%20Types.md#performance-budget), [Bar > Integration](../40%20Specifications/Surfaces/Bar.md#integration), [Frame > Integration](../40%20Specifications/Surfaces/Frame.md#integration), [Panel](../40%20Specifications/Surfaces/Panel.md) | Measured by tre on 0.5.8 and 0.5.9 |
| tre call cost (create, set, add_child, a 3,100-node tree) | [TRE-REQ-009 Batch and Tree Building > Measured Cost Today (2026-11-02)](../80%20Requests/TRE-REQ-009%20Batch%20and%20Tree%20Building.md#measured-cost-today-2026-11-02) | Measured here, single runs, no layout |
| The Clock shown (M2a: idle with a module that ticks) | [M2 Build Log](../00%20Home/M2%20Build%20Log.md), `tests/perf/idle-results-clock.md` in `tess-shell` | Measured by `tess-shell`: 0.017 % CPU; 8.07 wake-ups per second over a 60 s window with one minute tick on the software renderer, 2 per second between ticks (tre's own thread); the 5-per-second budget is read as "between ticks" for a module that ticks (D19, accepted 2026-11-04); the burst at a tick is measured separately on a real GPU |
| The Clock and the file watcher (M2b: idle) | [M2 Build Log](../00%20Home/M2%20Build%20Log.md) | Measured by `tess-shell`: 0.000 % CPU, 7.75 wake-ups per second over a 60 s window with one tick on the software renderer |
| Binder and Bar (M1: bind time of a 3,100-node tree, idle with a Bar shown) | [M1 Build Log](../00%20Home/M1%20Build%20Log.md), `tests/perf/bind-results.md` and `idle-results-bar.md` in `tess-shell` | Measured by `tess-shell`: 12.6 ms bind; idle 0.000 % CPU, 2.65 wake-ups/s |
| Animated icons | [TRE-REQ-008 SMIL Animation in SVG Nodes > Built in tre (Reported 2026-11-02)](../80%20Requests/TRE-REQ-008%20SMIL%20Animation%20in%20SVG%20Nodes.md#built-in-tre-reported-2026-11-02) | Measured by tre |
| Config load and validation | [JSON Schema and Editor Support](../41%20TDL%20Reference/JSON%20Schema%20and%20Editor%20Support.md), [Validation and Errors](../40%20Specifications/Runtime/Validation%20and%20Errors.md) | Measured on YAML; TDL parse not measured |
| Logging | [Logging > Threads and Speed](../40%20Specifications/Runtime/Logging.md#threads-and-speed) | Measured |
| CLI start | [ADR-0013 Control Interface > Context](../30%20Decisions/ADR-0013%20Control%20Interface.md#context) | Measured |
| Clock | [Clock Module > Performance Budget](../40%20Specifications/Modules/Clock%20Module.md#performance-budget) | Proposed |

## Proposed Values for the Missing Numbers

Recommendations, each with its reason. None is measured on the shell, because the shell does not exist; they are the numbers the first build is tested against, and the first build may change them.

| Budget | Proposed | Reason |
|---|---|---|
| Idle CPU, shell running, nothing animating | At most 0.5% of one core, averaged over 60 s. Measured at M0 (headless sway, no windows): 0.017 % ([M0 Brief > Result (2026-11-03)](../00%20Home/M0%20Brief.md#result-2026-11-03)) | tre measured 0.0% idle for a window and 0.01 s in 5 s with none ([TRE-REQ-008 SMIL Animation in SVG Nodes > Built in tre (Reported 2026-11-02)](../80%20Requests/TRE-REQ-008%20SMIL%20Animation%20in%20SVG%20Nodes.md#built-in-tre-reported-2026-11-02), [Process Model and Threading > Performance Notes](../20%20Architecture/Process%20Model%20and%20Threading.md#performance-notes)); the Python threads and one timer per second add the rest |
| Idle wake-ups | At most 5 per second. Measured at M0: about 2.0 per second, counted as context switches | tre reports about 2 per second from its OS-preference watcher; the Clock adds 1 per second; the D-Bus layer adds 0 without signals |
| Time to first surface | Under 1.0 s from the process start on a warm cache | Steps 1 to 11 of the start sequence run before the surfaces open ([Shell Start and Stop > Start Sequence](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md#start-sequence)); validation is in code and loads no JSON Schema library ([ADR-0020 Validation in Code](../30%20Decisions/ADR-0020%20Validation%20in%20Code.md)) |
| Time to ready | Under 2.0 s | Modules start at step 12 |
| Hot reload apply, after the 200 ms debounce | Under 100 ms for a shell of 10 surfaces. Measured at M2b: a saved `Height` applied a median of 206 ms after the save, about 5 ms of it validate, diff and set ([M2 Build Log](../00%20Home/M2%20Build%20Log.md)) | The debounce is decided at 200 ms and "about 300 ms end to end" is the spec's acceptance ([Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md)) |
| Resident memory of the default shell | To be set after the first build | The measured parts are per window (18 MiB for a bar, 177 MiB for a 4K overlay, 0.5.8); a total needs the real surface count |
| Looping icons at once | At most 2 per output, none on hidden surfaces | One looping icon cost about 30% of a core on software drawing ([Risk Register](../00%20Home/Risk%20Register.md) R-24); applies only when `mli` ships |
| Module callback on the loop | Under 4 ms | A 60 Hz frame is 16.7 ms; leaves room for paint ([Process Model and Threading > Performance Notes](../20%20Architecture/Process%20Model%20and%20Threading.md#performance-notes)) |
| Watchdog | A stall of 2 s logs; 10 s restarts the shell by `WATCHDOG=trigger` under systemd with `WatchdogSec=15` ([Crash Recovery and Watchdog](Crash%20Recovery%20and%20Watchdog.md), draft 2026-11-17; R-01) | No number exists; the stop timeout is 10 s |
| Motion durations | `Duration.Short` 100 ms, `Medium` 200 ms, `Long` 400 ms | The Panel example uses 200 ms and the fade-out test 400 ms ([Style Schema](../41%20TDL%20Reference/Style%20Schema.md) names the tokens with no values) |

## Disagreements to Reconcile

These are inconsistencies between notes, found by the sweep. I have not edited the notes; each fix is small and waits for the maintainer.

| # | Disagreement | Suggested fix |
|---|---|---|
| 1 | G4 says the loop wakes only for its own timers and the D-Bus layer targets 0 wake-ups, but tre reports about 2 per second from its OS-preference watcher | State the floor as "at most 5 per second" and say 2 of them are tre's |
| 2 | Memory baselines mix tre versions: the Bar and Panel use 0.5.8, the Frame uses 0.5.9 shared-device numbers, and [ADR-0001 Shell Surface Strategy](../30%20Decisions/ADR-0001%20Shell%20Surface%20Strategy.md) still says one shared device is open | Name the tre version beside every memory number |
| 3 | [Surface Types](../40%20Specifications/Surfaces/Surface%20Types.md) calls 177 MiB "before later changes" but uses it as the budget | Re-measure on 0.5.9 before it is a budget |
| 4 | The `jeepney` one-call cost is 20.0 ms in one place and 21.0 ms in others | Use one measured figure and say "about 20 ms" |
| 5 | The `jsonschema` import cost was 43 ms in one note and 57.5 ms in another | Moot: `jsonschema` is no longer a run-time dependency ([ADR-0020 Validation in Code](../30%20Decisions/ADR-0020%20Validation%20in%20Code.md)) |
| 6 | [TRE-REQ-008 SMIL Animation in SVG Nodes](../80%20Requests/TRE-REQ-008%20SMIL%20Animation%20in%20SVG%20Nodes.md) says 30 Hz sampling suits the shell, but tre built none (display rate, no cap) | Already recorded; keep R-24 open until tre adds a cap |
| 7 | Stop timeouts (3 s, 10 s) are decided but `Stop_Timeout` and `Module_Stop_Timeout` are only proposed | Accept the keys with the timeouts |
| 8 | The KWin silent-script warning (5 s) is "proposed" in the body and decided in the list | Mark it decided |
| 9 | The auto-hide delay is "1000 ms proposed" in one place and "open" in another | Accept 1000 ms or leave it open in both |
| 10 | Several specs point at `[[60 Quality]]` for budgets; the folder now exists but holds only this ledger | This note is the target |

## M7c Reading (code session's report, 2026-11-19; not run in the vault)

Full mode, 22.4 minutes, a private sway and private buses with fakes, load 0.23 at the start. The file is `tests/perf/budget-results.md` in the harness's worktree (a copy at `/tmp/m7/budget-results-real.md`); committing it needs a PR, which the code session asks you to say yes to. 26 budgets: 17 pass, 4 recorded, 1 not measured (B08: `mli` is not shipped), 4 fail.

| Budget | Reading | Limit | Result |
|---|---|---|---|
| B02 idle wake-ups, one Bar with a minute Clock and a Text | 5.16 per s between ticks (spread 4.13 to 6.2 over 2 runs); the default shell reads 4.07, 4.51 under the systemd watchdog; no surface 2.03 | at most 5 | Fails by 0.16 (3%) |
| B12 loop callback of toggling the Launcher | 1.75 ms p99 (the CLI end to end is 57.9 ms median, passes 100 ms; the plain Dock Panel toggle is 0.08 ms) | at most 1 ms | Fails |
| B14 `setShortcutKeys` calls per action | 2 (the shell sends two like the client library, flags 2 and 8); `doRegister` 1 passes; 10 actions in 3.8 ms; key press to callback 0.41 ms p95 | 1 | Fails; the note's 1 may be wrong rather than the code |
| B18 bind of a typed tree of 3,101 nodes | 34.4 ms median (spread 32 to 112), 34 tre calls; the 5-node example binds in 0.08 ms | 15 ms | Fails |

Merged (code session's report, `tess-shell` PR #79, 2026-11-19, CI green; not run in the vault): `tests/perf/budget-results.md` (the first real reading, with a note that its four verdicts were read against the old limits) and your decisions in the harness, `budgets.md` and the report text: B02 at most 6 per second, B12 at most 2 ms p99, B14 two `setShortcutKeys` per action. B18 stays 15 ms as a target (34.4 ms read); the bind cost work starts now (maintainer, 2026-11-19). The leak look ([SHELL-REQ-001 Reload Memory Retention](../80%20Requests/SHELL-REQ-001%20Reload%20Memory%20Retention.md)) is running.

Recorded: default shell memory 209 MiB RSS, 141 MiB PSS (one Bar also 141 PSS; no surface 64 RSS, 50 PSS); idle CPU 0.03% of one core (limit 0.5); time to ready 0.264 s median (limit 2 s); the callback record costs about 0.14 microseconds per callback, so it stays.

Reload retention (code session's report, `tess-shell` PR #83, merged 2026-11-19; not run in the vault): confirmed as a real, linear leak, fixed in the shell ([SHELL-REQ-001 Reload Memory Retention](../80%20Requests/SHELL-REQ-001%20Reload%20Memory%20Retention.md)). What stays is tre's closed window objects ([TRE-REQ-028 App Drops Closed Windows](../80%20Requests/TRE-REQ-028%20App%20Drops%20Closed%20Windows.md), draft). Four decisions for the maintainer from the build:

1. The same retention exists elsewhere and is not fixed: Popups (100 open and close cycles keep 100 `OpenPopup` and 100 `PopupWindow`, about 5.7 KiB each), Frame painters, and Panels with `Panel_Hide: CLOSE` (the default `KEEP` never closes the window). Fix in the shell now with the same `free_window` idea, or wait for tre's `remove_window`? Recommendation: fix Popups now (they are the most used), leave the rest for tre's answer. Answered by the maintainer on 2026-11-19: as recommended (fix Popups now).
2. Keep the strict expected failure in the collected suite? Recommendation: yes; it turns red the day tre fixes it, which is the point. Answered by the maintainer on 2026-11-19: as recommended (keep it).
3. The heap limits (512 KiB in the test, 16 KiB per cycle in B16) are the code session's; this note gives none. Recommendation: accept them. Answered by the maintainer on 2026-11-19: as recommended (accept).
4. `window.after` timers pending on a closed Panel are not cancelled, because tre gives no list; one closure each until tre drops the window. Recommendation: accept, and it is in the request to tre. Answered by the maintainer on 2026-11-19: as recommended (accept).

Later the same day (code session's report; not run in the vault):

- **B18 bind cost** (`tess-shell` PR #88, merged): the 3,101-node typed tree binds in about 16 ms, down from 34.4, measured under shared load (load 1.3 to 2.7; `measure_bind` 15.1 to 15.5), so B18 needs a re-read on an idle machine against the 15 ms target. Where the time went: plan 11.6 ms, tre `Window.build` 5.5, entries and attach 5.9, wires 4.8, `_sync` 4.1, controls 1.5, dispose 1.1. The gains: no position paths or property index built up front (34.4 to 27.9), a block gets a `Wire` only when something needs one (to 17.8), one index pass (to 16.9), and small type changes (about 1.5). The 100 ms garbage-collector spikes are gone, and a golden test compares the produced tre node properties with a record made from the old code. The floor is about 7.5 ms. A candidate for tre, unverified: `Window.build` returning the nodes in spec order would remove the 1.6 ms of wrappers.
- **Popup retention fixed** (PR #86, merged): with a real `App`, 100 open and close cycles kept 100 `OpenPopup` and `LiveTree` objects (about 5 KiB each) on every path; the counts are now flat on six paths. What stays is tre's `App.windows` (one `PopupWindow`, about 1 KiB each; part of [TRE-REQ-028 App Drops Closed Windows](../80%20Requests/TRE-REQ-028%20App%20Drops%20Closed%20Windows.md)). B16 now runs on a real `App`. Frame painters and `Panel_Hide: CLOSE` are untouched, as decided.
- **Test fixes:** PR #89 (no absolute `LayerWindow` count in the reload test) and #90 (`test_budget_logging` bound widened to 1 ms; a hosted CI runner read 90 and 98 microseconds against 81, about 22 locally).

Findings not fixed (the first is now answered above): a reload that removes and re-adds nine Panels retains about 7 MiB per cycle in Python objects, a possible leak that needs a separate look (unconfirmed: the builder's report is lost, see [SHELL-REQ-001 Reload Memory Retention](../80%20Requests/SHELL-REQ-001%20Reload%20Memory%20Retention.md)); logging adds two threads where [Crash Recovery and Watchdog](Crash%20Recovery%20and%20Watchdog.md) says one.

## Open Questions

1. [ ] Do you accept the proposed values above, or change them? Context: see [Proposed Values for the Missing Numbers](#proposed-values-for-the-missing-numbers). Recommendation: accept them as the v1 starting values and revise after the first measurements.
2. [ ] Are the budgets checked in automated tests (a headless idle-CPU test) or only measured by hand in v1? Context: [Vault Reference > Design completeness checklist](../00%20Home/Vault%20Reference.md#design-completeness-checklist) lists testing through `window.simulate`. Recommendation: measure by hand in v1 and add the headless idle-CPU test once the budgets have held through one milestone.
3. [ ] Which machine counts as the reference: the maintainer's AMD desktop, or a slower laptop? Context: the budgets are only meaningful against one machine. Recommendation: the AMD desktop sets the numbers; spot-check on a slower laptop before release.
4. [x] For the four misses, do you change the budget or ask for a fix? Context: see [M7c Reading (code session's report, 2026-11-19; not run in the vault)](#m7c-reading-code-sessions-report-2026-11-19-not-run-in-the-vault). Recommendation: B02 raise to 6 (it misses by 3% in one artificial Bar, and the default shell reads 4.07); B12 change to 2 ms p99 (the CLI end to end is 58 ms against 100); B14 change to 2 calls, because the shell matches the client library; B18 keep 15 ms as a target and ask the code session for a fix or a cheaper bind of large trees. Separately, ask for a look at the 7 MiB reload retention. Answered by the maintainer on 2026-11-19: use the recommendation. B02 is now at most 6 wake-ups per second, B12 at most 2 ms p99, B14 2 calls per action, B18 stays 15 ms as a target with a fix requested, and the reload retention gets a look.

## Acceptance Criteria

- [ ] Every "set in 60 Quality" line in the specs links to this note.
- [ ] Every proposed value above is accepted, changed or removed.
- [ ] Each disagreement in the table is fixed in its notes.
- [ ] Each budget has a test named in the testing strategy (not yet written).

## Links

- [60 Quality](60%20Quality.md) · [Goals and Non-Goals](../10%20Vision/Goals%20and%20Non-Goals.md) · [Risk Register](../00%20Home/Risk%20Register.md) · [Roadmap](../00%20Home/Roadmap.md)
