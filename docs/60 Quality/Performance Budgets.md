---
title: Performance Budgets
aliases: [Budgets, Performance Budget Ledger]
type: quality
status: draft
owner: phil
created: 2026-11-02
updated: 2026-11-02
tags: [quality, performance]
---

# Performance Budgets

> [!NOTE]
> A ledger of every performance number in the design on 2026-11-02, gathered from the specs by a read-only sweep and checked against the notes it names. It does not restate each number: the spec that owns a number keeps it, and this note links to it (one source of truth). It adds three things the specs cannot: the numbers still missing, proposed values for them, and the places where two notes disagree. Nothing here is decided; the maintainer decides (AGENTS > 2. Hard Rules rule 5).

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
| Animated icons | [TRE-REQ-008 SMIL Animation in SVG Nodes > Built in tre (Reported 2026-11-02)](../80%20Requests/TRE-REQ-008%20SMIL%20Animation%20in%20SVG%20Nodes.md#built-in-tre-reported-2026-11-02) | Measured by tre |
| Config load and validation | [JSON Schema and Editor Support](../41%20TDL%20Reference/JSON%20Schema%20and%20Editor%20Support.md), [Validation and Errors](../40%20Specifications/Runtime/Validation%20and%20Errors.md) | Measured on YAML; TDL parse not measured |
| Logging | [Logging > Threads and Speed](../40%20Specifications/Runtime/Logging.md#threads-and-speed) | Measured |
| CLI start | [ADR-0013 Control Interface > Context](../30%20Decisions/ADR-0013%20Control%20Interface.md#context) | Measured |
| Clock | [Clock Module > Performance Budget](../40%20Specifications/Modules/Clock%20Module.md#performance-budget) | Proposed |

## Proposed Values for the Missing Numbers

Recommendations, each with its reason. None is measured on the shell, because the shell does not exist; they are the numbers the first build is tested against, and the first build may change them.

| Budget | Proposed | Reason |
|---|---|---|
| Idle CPU, shell running, nothing animating | At most 0.5% of one core, averaged over 60 s | tre measured 0.0% idle for a window and 0.01 s in 5 s with none ([TRE-REQ-008 SMIL Animation in SVG Nodes > Built in tre (Reported 2026-11-02)](../80%20Requests/TRE-REQ-008%20SMIL%20Animation%20in%20SVG%20Nodes.md#built-in-tre-reported-2026-11-02), [Process Model and Threading > Performance Notes](../20%20Architecture/Process%20Model%20and%20Threading.md#performance-notes)); the Python threads and one timer per second add the rest |
| Idle wake-ups | At most 5 per second | tre reports about 2 per second from its OS-preference watcher; the Clock adds 1 per second; the D-Bus layer adds 0 without signals |
| Time to first surface | Under 1.0 s from the process start on a warm cache | Steps 1 to 11 of the start sequence run before the surfaces open ([Shell Start and Stop > Start Sequence](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md#start-sequence)); a warm schema cache avoids importing `jsonschema` ([JSON Schema and Editor Support](../41%20TDL%20Reference/JSON%20Schema%20and%20Editor%20Support.md)) |
| Time to ready | Under 2.0 s | Modules start at step 12 |
| Hot reload apply, after the 200 ms debounce | Under 100 ms for a shell of 10 surfaces | The debounce is decided at 200 ms and "about 300 ms end to end" is the spec's acceptance ([Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md)) |
| Resident memory of the default shell | To be set after the first build | The measured parts are per window (18 MiB for a bar, 177 MiB for a 4K overlay, 0.5.8); a total needs the real surface count |
| Looping icons at once | At most 2 per output, none on hidden surfaces | One looping icon cost about 30% of a core on software drawing ([Risk Register](../00%20Home/Risk%20Register.md) R-24); applies only when `mli` ships |
| Module callback on the loop | Under 4 ms | A 60 Hz frame is 16.7 ms; leaves room for paint ([Process Model and Threading > Performance Notes](../20%20Architecture/Process%20Model%20and%20Threading.md#performance-notes)) |
| Watchdog | A stall of 2 s logs; 10 s restarts the loop (to confirm with the supervisor design, R-01) | No number exists; the stop timeout is 10 s |
| Motion durations | `Duration.Short` 100 ms, `Medium` 200 ms, `Long` 400 ms | The Panel example uses 200 ms and the fade-out test 400 ms ([Style Schema](../41%20TDL%20Reference/Style%20Schema.md) names the tokens with no values) |

## Disagreements to Reconcile

These are inconsistencies between notes, found by the sweep. I have not edited the notes; each fix is small and waits for the maintainer.

| # | Disagreement | Suggested fix |
|---|---|---|
| 1 | G4 says the loop wakes only for its own timers and the D-Bus layer targets 0 wake-ups, but tre reports about 2 per second from its OS-preference watcher | State the floor as "at most 5 per second" and say 2 of them are tre's |
| 2 | Memory baselines mix tre versions: the Bar and Panel use 0.5.8, the Frame uses 0.5.9 shared-device numbers, and [ADR-0001 Shell Surface Strategy](../30%20Decisions/ADR-0001%20Shell%20Surface%20Strategy.md) still says one shared device is open | Name the tre version beside every memory number |
| 3 | [Surface Types](../40%20Specifications/Surfaces/Surface%20Types.md) calls 177 MiB "before later changes" but uses it as the budget | Re-measure on 0.5.9 before it is a budget |
| 4 | The `jeepney` one-call cost is 20.0 ms in one place and 21.0 ms in others | Use one measured figure and say "about 20 ms" |
| 5 | The `jsonschema` import costs 43 ms in one note and 57.5 ms in another | Two measurements; say which is which |
| 6 | [TRE-REQ-008 SMIL Animation in SVG Nodes](../80%20Requests/TRE-REQ-008%20SMIL%20Animation%20in%20SVG%20Nodes.md) says 30 Hz sampling suits the shell, but tre built none (display rate, no cap) | Already recorded; keep R-24 open until tre adds a cap |
| 7 | Stop timeouts (3 s, 10 s) are decided but `Stop_Timeout` and `Module_Stop_Timeout` are only proposed | Accept the keys with the timeouts |
| 8 | The KWin silent-script warning (5 s) is "proposed" in the body and decided in the list | Mark it decided |
| 9 | The auto-hide delay is "1000 ms proposed" in one place and "open" in another | Accept 1000 ms or leave it open in both |
| 10 | Several specs point at `[[60 Quality]]` for budgets; the folder now exists but holds only this ledger | This note is the target |

## Open Questions

1. [ ] Accept the proposed values above, or change them.
2. [ ] Whether the budgets are checked in automated tests (a headless idle-CPU test) or only measured by hand in v1; AGENTS > 12. Design Completeness Checklist lists testing through `window.simulate`.
3. [ ] Which machine counts as the reference (the maintainer's AMD desktop, or a slower laptop).

## Acceptance Criteria

- [ ] Every "set in 60 Quality" line in the specs links to this note.
- [ ] Every proposed value above is accepted, changed or removed.
- [ ] Each disagreement in the table is fixed in its notes.
- [ ] Each budget has a test named in the testing strategy (not yet written).

## Links

- [60 Quality](60%20Quality.md) · [Goals and Non-Goals](../10%20Vision/Goals%20and%20Non-Goals.md) · [Risk Register](../00%20Home/Risk%20Register.md) · [Roadmap](../00%20Home/Roadmap.md)
