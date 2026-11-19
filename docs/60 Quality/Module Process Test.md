---
title: Module Process Test
aliases: [Posture Test, Process Per Module Test, M7a2]
type: quality
status: accepted
owner: phil
created: 2026-11-17
updated: 2026-11-19
tags: [quality, security, performance]
---

# Module Process Test

> [!NOTE]
> **Accepted by the maintainer on 2026-11-17**
> Sent to `tess-shell` by the vault session the same day, on the maintainer's standing order; accepted by him afterwards. Open questions below are answered as recommended unless a line says otherwise.

> [!NOTE]
> A test plan, not a feature. It measures the shell with every module in the shell's process (posture A, how it is built today) against the shell with one process per module (posture B) and a mixed form (posture C), on the same default shell, and applies the maintainer's rule of 2026-11-17: if the cost of a process per module is insignificant, the shell moves to it before 1.0. The test also measures the benefit, which is what the posture buys: a hung or crashed module no longer freezes the surfaces. M7a2 of [M7 Brief](../00%20Home/M7%20Brief.md). The code session builds a prototype of B good enough to measure and reports the numbers; the maintainer decides.

## Purpose and scope

- In: the three postures, a prototype for B and C, what is measured and how, the decision rule, and the report.
- Out: a finished process-per-module feature, and security isolation (a child process as the same user is fault containment, not a sandbox: [Security Model > Posture B and What It Does and Does Not Give](Security%20Model.md#posture-b-and-what-it-does-and-does-not-give)).

## The Postures

| | A, in process | B, a process per module | C, shipped in process, user modules in a process |
|---|---|---|---|
| Where a module's Python runs | The shell's process, loop and threads | A child process for every module use of a file (one instance per module file, as today) | Shipped modules as A; each user module as B |
| A hung callback | Freezes every surface until the watchdog restarts the shell | Only that module stops; the shell keeps painting; the module is killed and restarted | As B for user modules; as A for shipped ones |
| What it costs | Nothing extra | A Python process per module, a hop per value | One process per user module only; the default shell has none |
| State of the code | Built | A prototype | A prototype on top of B |

## The Prototype

The prototype stays behind the existing module contract ([Module Contract](../42%20Python%20API/Module%20Contract.md)) and changes how the host runs a module, not what a module is.

- The child runs the module's `Module` class with a proxy `ctx`: `ctx.send` writes to the pipe; `ctx.every`, `ctx.after` and `ctx.on_tick` run in the child's own timers; `ctx.thread` threads live in the child.
- The parent receives values on a reader thread, keeps its coalescing map per module and key, and hands one flush to the loop with `call_soon`, exactly as for A ([Process Model and Threading > Handing a Value to the Loop (Proposed)](../20%20Architecture/Process%20Model%20and%20Threading.md#handing-a-value-to-the-loop-proposed)).
- Actions, `ctx.uses` and `ctx.config` cross the pipe as plain data (JSON lines or a framed binary format, the code session's choice; record which).
- Services (`ctx.dbus`, `ctx.audio`, `ctx.apps`, `ctx.windows`, `ctx.icons`) need a decision the prototype makes and reports, because they hold shared connections today:
  - B1: each child opens its own connections (a D-Bus connection per module, a PulseAudio native-protocol connection for Audio);
  - B2: the parent keeps the connections and proxies calls and signals over the pipe.
  Both are measured where they differ materially; the report says which is the better B.
- The prototype need not support every context member. It must run the eight default modules (Clock, Workspaces, Tasks, Tray, Audio, Network, Battery, Media) and the Launcher, since they are what the default shell loads.

## What Is Measured

All numbers for the whole process tree (the shell and every child), the same default shell configuration, the same machine.

| Measure | How | Why |
|---|---|---|
| Start time | Process start to `READY=1`, 20 runs, median and p95 | The budget is under 2.0 s to ready ([Performance Budgets](Performance%20Budgets.md)) |
| Idle CPU | 60 s, percent of one core, nothing animating | At most 0.5% |
| Idle wake-ups | 60 s, context switches per second, summed over the tree | At most 5 per second |
| Memory | PSS and RSS summed over the tree, after 60 s idle | A total is not set yet; this sets it |
| Value to screen | `ctx.send` in a module to the node property set, 1000 single updates and a burst of 200 per second, p50, p95, p99 | Frame budget 16.7 ms; a callback is under 4 ms |
| Throughput | Values per second the path sustains before p95 passes 16 ms | The Audio and Media modules send often |
| Hang containment | A module whose callback sleeps 10 s: do the surfaces keep painting (frames per second of a test node), how long to detect, how long to recover | The benefit of B and C |
| Crash containment | A module process killed with SIGKILL: surfaces keep, time to restart, the log line | The benefit of B and C |
| Reload | A module's Python file saved: time until the new instance runs | [Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md) |

Posture C is measured in two forms: the default shell (no user module, so C should equal A) and the default shell plus three hand-written user modules.

## Conditions

- An idle machine (D-045): nothing else running that the user started, load average under 0.5 at the start of each run. The report records the machine, kernel, CPU, memory, Python, engine and shell versions.
- A private headless sway and private buses, as the self-running kits use, so nothing touches the maintainer's session ([Hand Checks](../00%20Home/Hand%20Checks.md)).
- Each measure: at least 3 full repetitions, the median reported, the spread shown.

## Decision Rule

Applied by the maintainer to the report. The numbers are his to set ([M7 Brief > Open Questions](../00%20Home/M7%20Brief.md#open-questions) 6); the starting values, proposed on 2026-11-17, are:

| Test | Passes when |
|---|---|
| Start | The whole default shell reaches ready no more than 300 ms later than A |
| Wake-ups | No more than 2 per second above A for the default shell |
| Value to screen | p95 within one frame (16.7 ms) for single updates and for the 200-per-second burst |
| Memory | The whole tree grows by no more than 150 MB over A |
| Containment | A 10 s hang and a killed module leave the surfaces painting, and the module restarts |

If B passes every row, the shell moves to B before 1.0. If B fails on cost but C passes, the shell moves to C. If neither passes, A stays and the vault records why, with the numbers. The rule is applied to the numbers as measured, not to how the prototype looks.

## Report

The code session writes the report in the shell repository (`tests/perf/module-process-results.md`) and a build-log entry; the vault session folds the table into this note under "Results" and into [Performance Budgets](Performance%20Budgets.md). The report contains: the machine, every number above with its spread, which services variant (B1 or B2) was used, what the prototype does not support, and the cost in code of the move (lines changed, the `ctx` members that needed a different design).

## Results

The full measurement has not run. The prototype and harness are merged (code session's report of `tess-shell` PR #71, 2026-11-17, CI green; not run in the vault), and the numbers wait for a run alone on an idle machine (about 80 minutes) once the other merges are done.

### The full measurement (code session's report, 2026-11-19; not run in the vault)

Run 10:38 to 11:21 (about 43 minutes) on a private sway, load 0.35 at the start; the harness's own earlier cells raised the load (median 1-minute load 0.91, highest 4.96). Cells: A, B1, B2, C1, C2; 3 repetitions, 20 start runs. The file is `/tmp/m7/module-process-results-real.md` (284 lines), not committed. The lean B is not in this run: it started before the decision reached the code session and cannot be changed mid-run.

By the rule of this note, B fails one row (memory) and C passes every row, so the shell moves to C. You decide.

| Row (default shell, against A in the same run) | Limit | B1 | B2 | C1 | C2 |
|---|---|---|---|---|---|
| Start | +300 ms | +226 ms | +173 ms | +8 ms | |
| Start with 3 user modules | +300 ms | | | +62 ms | +47 ms |
| Wake-ups per second | +2 | +0.75 | +0.98 | -0.17 | |
| Wake-ups with 3 user modules | +2 | | | +1.18 | +1.10 |
| Memory (PSS of the tree) | +150 MB | **+372 MB, FAIL** | **+357 MB, FAIL** | -2 MB | |
| Memory with 3 user modules | +150 MB | | | +51 MB | +49 MB |

- **Value to screen** (limit p95 16.7 ms), single value and burst: A 0.37 and 0.25 ms; B1 0.53 and 0.55; B2 0.52 and 0.65; C1 1.04 and 1.12; C2 0.54 and 0.70. Every cell passes by a factor of 15 or more. Throughput reaches 10,000 values per second in every cell at p95 under 1 ms (the top of the ladder).
- **Hang containment:** in A a 10 s hang freezes the picture for the whole 10.00 s (0% of captures changed) and there is no watchdog in A (the shell-wide one is M7b). In B and C the test node kept painting in 100% of captures (longest stop 0.03 s); the stall was named after 2.9 s, the process killed at 5 s, and a new instance was running 8.06 s after the hang began.
- **A killed module process (SIGKILL):** surfaces keep painting (99%), the module restarts in 1.09 to 1.31 s, with the log line "the module process (pid N) ended: exit code -9; its surfaces keep their last values".
- **Reload** (file saved to the new instance running): A 0.239 s, B 0.30 s.
- **B1 against B2:** B2 uses less memory (508 against 523 MB PSS) and starts faster (423 against 475 ms), but needs 162 lines of proxies and brokers against about 22 for B1. Both pass the same rows.
- **Where the memory goes:** the process count. 22 module files become 22 children of about 17 to 19 MB PSS each (a bare interpreter is 5.2 MB; an interpreter with a module context 19.2 MB): 24 processes and 225 threads against 2 and 81 in A.
- **Idle CPU:** 0.03 to 0.05% in every cell. The wake-up counts here (about 10 per second even in A) are not comparable with M7c's 4.07: this harness counts context switches of every thread, including the engine's software-renderer threads, so only the differences to A matter.
- **C means** shipped modules in the shell and only user module files in processes. It costs nothing for the default shell, which has no user module.
- **Caveats:** the paint measure is taken from outside, so it says "painting", not the engine's frame rate; fakes only, no real hardware, KWin's window script is off so Tasks shows no windows. The prototype is not a product: it leaves out `ctx.focus`, `Event.stop()`, the result of an `@action` through `Call` (a module in a process returns null to the CLI), actions inherited from another user class, `check`'s load-time findings for module processes, the `many-threads` and `slow-module` warnings, and JSON's loss of tuples. A real B needs a reply path (an RPC with a timeout) for `update_popup`, `is_popup_open`, `surface.*`, `apps.search` and `Call`, and `READY=1` that waits for the children without blocking the loop.
- **Lean B, not yet measured:** 22 files minus the 13 TDL-only ones leaves about 9 processes, about 9 x 18 = 160 MB PSS above A, a little over the +150 MB limit. The code session builds a lean B only delta (start, idle memory, latency, containment), about 15 to 20 minutes on the same harness, and sends it as a separate table. Close to the limit, so measure, do not guess.

### What was built

- Everything is new under `tests/` and no `src/` file was touched. `tests/perf/proto/` is a prototype of posture B (a Python child process per module file; JSON lines over a socketpair, recorded as the wire format; B1: each child opens its own D-Bus and PulseAudio connections; B2: the parent keeps the connections and proxies calls and signals) and of C (shipped modules in process, each user module as B). It runs the default shell's 22 module files (the eight default modules, Applications, and the widget and popup modules they use) in B, and a user module in a child in C, verified against the fakes including real pointer clicks and the Tray menu in B1 and B2.
- `tests/perf/module_process_test.py` measures A, B and C (start, idle CPU, wake-ups, PSS and RSS over the tree, value to screen with p50, p95 and p99, throughput, hang and crash containment, reload). It refuses to start above a load of 0.5 unless `--allow-load`, runs on a private sway and private buses with private data folders, and writes `tests/perf/module-process-results.md` with a computed verdict table against the starting thresholds, kept as named constants. It states that the maintainer decides. 19 collected tests (18 s) and 6 perf-marked end-to-end ones (2 minutes).

### A smoke run (indicative only, not a result)

B costs about 360 MB more PSS (22 processes of about 17 MB each, which is where the memory goes), a start 180 to 270 ms later, a latency from under a millisecond to 1 ms at p95, and a hung and a killed module are contained and restarted. C with the default shell equals A. Against the thresholds of this note: memory fails (150 MB allowed), start passes (300 ms), latency passes, containment passes.

### Where the prototype departs from this note (code session's list)

1. JSON lines, not a framed binary format (not needed for the numbers).
2. A hung module process is killed at 5 s (the stall is logged at 2 s), not at the shell-wide 10 s, because only that module restarts; the 1 s poll adds about 1 wake-up per second (an adaptive watchdog is possible).
3. B hosts every module file, including the 13 small widget and popup modules: the literal reading of one process per module file, and where the memory goes. A "lean B", where modules with no code of their own stay in the shell, is not measured; C is the nearest measured form.
4. The first `start()` blocks the loop until the child answers, so `READY=1` means the modules ran `start`; a real design needs `READY=1` to wait for the children without blocking the loop.
5. The paint measure is taken from outside (a screenshot of the Bar), so it says "painting", not the engine's frame rate.
6. Memory is PSS summed over the tree; wake-ups are context switches over all threads, an over-count (the engine's software-renderer threads add a burst after the start, hence a 10 s settle).
- Not built in the prototype: `ctx.focus`, `Event.stop()`, the result of an `@action` through a process, and the `many-threads` and `slow-module` warnings for module processes. A candidate for tre: a frame counter readable from another thread (the code session notes `Window.frame_stats()` is documented as thread safe) would let the hang test read the engine's own frames.


## Open Questions

1. [x] Is a process per module one process per module file, or per use? Context: today one instance serves every use of a file (`ctx.uses`). Recommendation: per module file, as today, so the memory is the lowest and the contract is the same. Accepted as recommended by the maintainer on 2026-11-17, with his acceptance of the note.
2. [x] Are the thresholds above the maintainer's? That is [M7 Brief > Open Questions](../00%20Home/M7%20Brief.md#open-questions) 6, open there. Accepted as recommended by the maintainer on 2026-11-17, with his acceptance of the note.

3. [x] Should the measurement include a lean B before the verdict? Context: as built, B puts 22 module files in 22 processes, including 13 small widget and popup modules that have no Python of their own, which is where the memory goes (about 360 MB, over the 150 MB threshold). A lean B keeps the modules with no code of their own in the shell and runs only modules with Python in children (nine for the default shell), which is the form a real design would take. The code session proposes deciding this before the verdict, since the full run takes about 80 minutes. Recommendation: yes, add a lean B (B1 and B2 if the cost allows) to the same run. Answered by the maintainer on 2026-11-19: yes, add a lean B to the same run, with B1 and B2 if the cost allows.

## Acceptance criteria

- [x] The prototype runs the eight default modules and the Launcher in B, and C runs a user module in a child with the shipped ones in process (merged, PR #71).
- [ ] Every measure above has a number for A, B and C with its spread and the machine description.
- [ ] The 10 s hang and the killed module are measured for A (the watchdog restart of [Crash Recovery and Watchdog](Crash%20Recovery%20and%20Watchdog.md)), B and C.
- [ ] The report names the B1 or B2 services variant and what the prototype leaves out.
- [ ] The maintainer's decision and the numbers behind it are recorded here under "Results" and in the build log.

## Links

[Security Model](Security%20Model.md) · [Crash Recovery and Watchdog](Crash%20Recovery%20and%20Watchdog.md) · [Performance Budgets](Performance%20Budgets.md) · [Process Model and Threading](../20%20Architecture/Process%20Model%20and%20Threading.md) · [Module Contract](../42%20Python%20API/Module%20Contract.md) · [M7 Brief](../00%20Home/M7%20Brief.md) · [60 Quality](60%20Quality.md)
