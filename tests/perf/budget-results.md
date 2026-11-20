# Budget readings

Produced by `tests/perf/read_budgets.py` (the method of each budget is in `tests/perf/budgets.md`). A verdict compares the reading with the number the vault states, and says by how much a budget is missed; it changes no budget: the maintainer decides. `RECORDED` rows are numbers the vault gives no limit for. Wake-ups are context switches of every thread of the shell (voluntary and involuntary), as the earlier idle measures counted them.



> **Read on 2026-11-19 against the budgets of that day.** The four misses (B02, B12, B14, B18) were then decided by the maintainer: B02 is now at most 6 per second (read 5.16), B12 at most 2 ms p99 (read 1.75), B14 two `setShortcutKeys` per action (read 2); B18 stays 15 ms as a target (read 34.4 ms) and is open work. The verdicts below are the ones the harness printed at the time.

| | |
|---|---|
| Date | 2026-11-19T10:07:55-08:00 |
| Mode | FULL |
| Duration | 22.4 min |
| Load average at the start | 0.23 0.12 0.17 (1, 5, 15 min) |
| Load average at the end | 0.81 0.77 0.58 |
| Busiest processes at the start | 93.7 54772 python; 10.6 355492 orca-ide; 2.4 838676 omp; 2.3 515212 orca-ide; 1.8 200692 orca-ide; 1.0 608488 omp |
| Machine | Linux 7.3.5-1-cachyos x86_64 |
| CPU | AMD Ryzen AI 9 HX 370 w/ Radeon 890M, 24 threads, governor performance |
| Memory | 46.7 GiB |
| Python | 3.14.10 (with the GIL) |
| tess_re (tesserae-engine) | 0.6.9 |
| tess_dl / tess_el | 0.2.0 / 0.2.0 |
| tess-shell | 0.1.2 at aea8553 |
| Compositor | private headless sway (sway version 1.12), pixman renderer, no GPU |
| Command | python -m tests.perf.read_budgets |

## Verdicts

| Budget | Verdict | Where it fails |
|---|---|---|
| B01 Idle CPU | PASS |  |
| B02 Idle wake-ups | FAIL | one Bar with a Clock (minute) and a Text, 60 s window after 5 s of settling:...: misses by 0.1649 per s, 3 % |
| B03 Time to first surface | PASS |  |
| B04 Time to ready | PASS |  |
| B05 Stop time | PASS |  |
| B06 Hot reload apply | PASS |  |
| B07 Resident memory of the default shell | RECORDED |  |
| B08 Looping icons at once | NOT MEASURED |  |
| B09 Module callback on the loop | PASS |  |
| B10 Watchdog | PASS |  |
| B11 Motion durations | PASS |  |
| B12 Control interface | FAIL | loop callback of a `toggle Launcher` (108 toggles): ShellCommands.surface: misses by 0.745 ms, 75 % |
| B13 D-Bus layer | PASS |  |
| B14 Global shortcuts | FAIL | setShortcutKeys calls per action: misses by 1 calls, 100 % |
| B15 Portals | PASS |  |
| B16 Popup | PASS (part not measured) |  |
| B17 Per-surface video memory | PASS |  |
| B18 Binding and tre call cost | FAIL | bind of a typed tree of 3,101 nodes (build + attach + dispose): misses by 19.43 ms, 130 % |
| B19 Config load and validation | RECORDED |  |
| B20 Logging | PASS |  |
| B21 CLI start | RECORDED |  |
| B22 Clock tick | PASS |  |
| B23 Hot reload watcher idle | PASS |  |
| B24 Callback record cost | PASS |  |
| B25 Heartbeat and watchdog wake-ups | RECORDED |  |
| B26 Frame time | PASS |  |

## Readings

### B01 Idle CPU

Budget: At most 0.5 % of one core, averaged over 60 s, shell running, nothing animating. Source: Performance Budgets > Proposed Values.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| no surface (no main shell), 60 s window after 5 s of settling | 0 % of one core (median) | 0 to 0 (n=2) | at most 0.5 % of one core | **PASS** | utime + stime of every thread; the clock tick is 10 ms, so a 60 s window reads in steps of 0.017 % |
| one Bar with a Clock (minute) and a Text, 60 s window after 5 s of settling | 0.158 % of one core (median) | 0.05 to 0.267 (n=2) | at most 0.5 % of one core | **PASS** | utime + stime of every thread; the clock tick is 10 ms, so a 60 s window reads in steps of 0.017 % |
| the default shell: eight modules and the Launcher, 60 s window after 5 s of settling | 0.0333 % of one core (median) | 0.0167 to 0.0333 (n=3) | at most 0.5 % of one core | **PASS** | utime + stime of every thread; the clock tick is 10 ms, so a 60 s window reads in steps of 0.017 % |
| the default shell under systemd's watchdog (WATCHDOG_USEC=15 s, as the unit sets it), 60 s window after 5 s of settling | 0.025 % of one core (median) | 0.0167 to 0.0333 (n=2) | at most 0.5 % of one core | **PASS** | utime + stime of every thread; the clock tick is 10 ms, so a 60 s window reads in steps of 0.017 % |
| the default shell with the watchdog's times scaled by 1000 (the thread never wakes), 60 s window after 5 s of settling | 0 % of one core (median) | 0 to 0 (n=2) | at most 0.5 % of one core | **PASS** | utime + stime of every thread; the clock tick is 10 ms, so a 60 s window reads in steps of 0.017 % |
| the default shell with the watchdog's times doubled (tick 2 s, warn 4 s, restart 20 s): the heartbeat slowed to every 2 s, 60 s window after 5 s of settling | 0.0167 % of one core (median) | 0.0167 to 0.0167 (n=2) | at most 0.5 % of one core | **PASS** | utime + stime of every thread; the clock tick is 10 ms, so a 60 s window reads in steps of 0.017 % |
| the default shell with the Clock showing seconds (a tick every second), 60 s window after 5 s of settling | 0.4 % of one core (median) | 0.4 to 0.4 (n=2) | at most 0.5 % of one core | **PASS** | utime + stime of every thread; the clock tick is 10 ms, so a 60 s window reads in steps of 0.017 % |

### B02 Idle wake-ups

Budget: At most 5 per second (context switches), the shell idle; for a module that ticks the budget is read between ticks (D19). Source: Performance Budgets > Proposed Values; M2 Build Log D19.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| no surface (no main shell), 60 s window after 5 s of settling: between ticks (bins around the minute tick left out) | 2.03 per s (median) | 2.02 to 2.04 (n=2) | at most 5 per s | **PASS** | voluntary and involuntary switches of every thread; 5 s of the window left out |
| no surface (no main shell), 60 s window after 5 s of settling: the whole window, tick included (information: D19 reads between ticks) | 2.02 per s (median) | 2 to 2.03 (n=2) | - | **RECORDED** | threads: 16 |
| one Bar with a Clock (minute) and a Text, 60 s window after 5 s of settling: between ticks (bins around the minute tick left out) | 5.16 per s (median) | 4.13 to 6.2 (n=2) | at most 5 per s | **FAIL** | misses by 0.1649 per s, 3 %. voluntary and involuntary switches of every thread; 5 s of the window left out |
| one Bar with a Clock (minute) and a Text, 60 s window after 5 s of settling: the whole window, tick included (information: D19 reads between ticks) | 16.1 per s (median) | 14.9 to 17.3 (n=2) | - | **RECORDED** | threads: 77, 78 |
| the default shell: eight modules and the Launcher, 60 s window after 5 s of settling: between ticks (bins around the minute tick left out) | 4.07 per s (median) | 4.07 to 4.18 (n=3) | at most 5 per s | **PASS** | voluntary and involuntary switches of every thread; 5 s of the window left out |
| the default shell: eight modules and the Launcher, 60 s window after 5 s of settling: the whole window, tick included (information: D19 reads between ticks) | 9.75 per s (median) | 9.73 to 10.2 (n=3) | - | **RECORDED** | threads: 80 |
| the default shell under systemd's watchdog (WATCHDOG_USEC=15 s, as the unit sets it), 60 s window after 5 s of settling: between ticks (bins around the minute tick left out) | 4.51 per s (median) | 4.51 to 4.51 (n=2) | at most 5 per s | **PASS** | voluntary and involuntary switches of every thread; 5 s of the window left out |
| the default shell under systemd's watchdog (WATCHDOG_USEC=15 s, as the unit sets it), 60 s window after 5 s of settling: the whole window, tick included (information: D19 reads between ticks) | 10.2 per s (median) | 10.1 to 10.3 (n=2) | - | **RECORDED** | threads: 80 |
| the default shell with the watchdog's times scaled by 1000 (the thread never wakes), 60 s window after 5 s of settling: between ticks (bins around the minute tick left out) | 2.02 per s (median) | 2.02 to 2.02 (n=2) | at most 5 per s | **PASS** | voluntary and involuntary switches of every thread; 5 s of the window left out |
| the default shell with the watchdog's times scaled by 1000 (the thread never wakes), 60 s window after 5 s of settling: the whole window, tick included (information: D19 reads between ticks) | 8.03 per s (median) | 7.93 to 8.13 (n=2) | - | **RECORDED** | threads: 80 |
| the default shell with the watchdog's times doubled (tick 2 s, warn 4 s, restart 20 s): the heartbeat slowed to every 2 s, 60 s window after 5 s of settling: between ticks (bins around the minute tick left out) | 3.11 per s (median) | 3.09 to 3.14 (n=2) | at most 5 per s | **PASS** | voluntary and involuntary switches of every thread; 5 s of the window left out |
| the default shell with the watchdog's times doubled (tick 2 s, warn 4 s, restart 20 s): the heartbeat slowed to every 2 s, 60 s window after 5 s of settling: the whole window, tick included (information: D19 reads between ticks) | 9.02 per s (median) | 9.02 to 9.03 (n=2) | - | **RECORDED** | threads: 80 |
| the default shell with the Clock showing seconds (a tick every second), 60 s window after 5 s of settling: between ticks (bins around the minute tick left out) | 366 per s (median) | 363 to 369 (n=2) | - | **RECORDED** | a tick every second: there is no 'between ticks', so no verdict. voluntary and involuntary switches of every thread; 5 s of the window left out |
| the default shell with the Clock showing seconds (a tick every second), 60 s window after 5 s of settling: the whole window, tick included (information: D19 reads between ticks) | 367 per s (median) | 365 to 368 (n=2) | - | **RECORDED** | threads: 80 |
| default shell, between ticks: the loop (main thread) | 1.05 per s (median) | 1.04 to 1.13 (n=3) | - | **RECORDED** | where the wake-ups are (context switches by thread group) |
| default shell, between ticks: the watchdog | 1.02 per s (median) | 1.02 to 1.05 (n=3) | - | **RECORDED** | where the wake-ups are (context switches by thread group) |
| default shell, between ticks: the tre helpers | 2 per s (median) | 2 to 2.02 (n=3) | - | **RECORDED** | where the wake-ups are (context switches by thread group) |

### B03 Time to first surface

Budget: Under 1.0 s from the process start, warm cache. Source: Performance Budgets > Proposed Values.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| default shell: Popen to the first surface configured by the compositor | 0.368 s (median) | 0.329 to 0.398 (n=10) | at most 1 s | **PASS** | 10 starts after one discarded cold start (warm cache); the first surface is the first 'configured' line |
| step of the start: 'starting tesserae-shell': the process printed its first line (interpreter and imports) | 0.175 s (median) | 0.154 to 0.194 (n=10) | - | **RECORDED** | seconds from Popen; the log's own steps |
| step of the start: 'loaded ': settings and shell files read and validated | 0.208 s (median) | 0.185 to 0.227 (n=10) | - | **RECORDED** | seconds from Popen; the log's own steps |
| step of the start: 'step 10 (model)': the model of uses and modules | 0.251 s (median) | 0.228 to 0.272 (n=10) | - | **RECORDED** | seconds from Popen; the log's own steps |
| step of the start: 'step 11 (surfaces)': the surfaces created | 0.255 s (median) | 0.23 to 0.276 (n=10) | - | **RECORDED** | seconds from Popen; the log's own steps |
| step of the start: 'step 12 (modules)': the modules started | 0.256 s (median) | 0.231 to 0.277 (n=10) | - | **RECORDED** | seconds from Popen; the log's own steps |
| step of the start: 'running': the shell reports running | 0.264 s (median) | 0.237 to 0.288 (n=10) | - | **RECORDED** | seconds from Popen; the log's own steps |

### B04 Time to ready

Budget: Under 2.0 s from the process start (READY=1; modules start at step 12). Source: Performance Budgets > Proposed Values.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| default shell: Popen to READY=1 on NOTIFY_SOCKET | 0.264 s (median) | 0.237 to 0.289 (n=10) | at most 2 s | **PASS** | READY=1 follows step 12, the modules started |

### B05 Stop time

Budget: Bounded: 10 s in total, 3 s per module (decided). Source: Shell Start and Stop > Stop Sequence.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| default shell: SIGTERM to the process gone | 0.114 s (max) | 0.0634 to 0.114 (n=10) | at most 10.0 s | **PASS** | exit codes: 0 |

### B06 Hot reload apply

Budget: Under 100 ms after the 200 ms debounce for a shell of 10 surfaces; about 300 ms from the save to the change. Source: Performance Budgets > Proposed Values; Hot Reload.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| 10 surfaces (a Bar and 9 shown Panels): the reload's own time after the debounce | 41.0 ms (median) | 37.0 to 57.0 (n=20) | at most 100 ms | **PASS** | validate, diff and set, from the log line 'reloaded (...) in N ms'; whole milliseconds, so a 0.4 ms reload reads 0 |
| 10 surfaces: from the save to the 'reloaded' line (debounce 200 ms included) | 243 ms (median) | 240 to 260 (n=20) | at most 300 ms | **PASS** | the spec's acceptance is 'about 300 ms from the save to the change'; the log line is when the shell finished applying, the compositor's reflow follows |

### B07 Resident memory of the default shell

Budget: To be set after the first build (no number); per-surface figures are video memory. Source: Performance Budgets > Proposed Values.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| resident memory, no surface (no main shell) | 64.0 MiB RSS (median) | 62.0 to 66.1 (n=2) | - | **RECORDED** | read at the end of the idle window; includes the engine, the software Vulkan driver and its render threads |
| proportional memory (PSS), no surface (no main shell) | 49.7 MiB PSS (median) | 47.6 to 51.7 (n=2) | - | **RECORDED** | PSS splits the pages shared with other processes (the driver libraries) |
| resident memory, one Bar with a Clock (minute) and a Text | 209 MiB RSS (median) | 196 to 221 (n=2) | - | **RECORDED** | read at the end of the idle window; includes the engine, the software Vulkan driver and its render threads |
| proportional memory (PSS), one Bar with a Clock (minute) and a Text | 141 MiB PSS (median) | 128 to 153 (n=2) | - | **RECORDED** | PSS splits the pages shared with other processes (the driver libraries) |
| resident memory, the default shell: eight modules and the Launcher | 209 MiB RSS (median) | 209 to 209 (n=3) | - | **RECORDED** | read at the end of the idle window; includes the engine, the software Vulkan driver and its render threads |
| proportional memory (PSS), the default shell: eight modules and the Launcher | 141 MiB PSS (median) | 141 to 141 (n=3) | - | **RECORDED** | PSS splits the pages shared with other processes (the driver libraries) |
| resident memory, the default shell under systemd's watchdog (WATCHDOG_USEC=15 s, as the unit sets it) | 209 MiB RSS (median) | 209 to 210 (n=2) | - | **RECORDED** | read at the end of the idle window; includes the engine, the software Vulkan driver and its render threads |
| proportional memory (PSS), the default shell under systemd's watchdog (WATCHDOG_USEC=15 s, as the unit sets it) | 141 MiB PSS (median) | 141 to 141 (n=2) | - | **RECORDED** | PSS splits the pages shared with other processes (the driver libraries) |
| resident memory of one tre process with a full-screen surface at 3840 x 2160 (4K) and nothing else | 219 MiB RSS (median) | 219 to 219 (n=3) | - | **RECORDED** | the engine's floor for one window |

### B08 Looping icons at once

Budget: At most 2 per output, none on hidden surfaces; applies only when `mli` ships. Source: Performance Budgets > Proposed Values; Risk Register R-24.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| looping icons at once | - | - | - | NOT MEASURED | applies only when the `mli` icon format ships; no module of the shell loops an icon today (Risk Register R-24 is open until tre adds a sampling cap), so there is nothing to count; the idle wake-up and frame counts above cover the rest |

### B09 Module callback on the loop

Budget: Under 4 ms. Source: Performance Budgets > Proposed Values; Process Model and Threading.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| the default shell with a Clock showing seconds, 379 module callbacks after 'running' (108 rounds of battery, desktop, toggle and call): 99th percentile | 0.843 ms (p99) | 8.1e-05 to 1.27 (n=379) | at most 4 ms | **PASS** | heaviest: Applications.Applications.list_changed 1.3 ms, Applications.Applications.shown 1.2 ms, Tray.stop 0.4 ms |
| the default shell with a Clock showing seconds, 379 module callbacks after 'running' (108 rounds of battery, desktop, toggle and call): the slowest | 1.27 ms (max) | 8.1e-05 to 1.27 (n=379) | at most 4 ms | **PASS** | a single callback preempted by another process counts here |
| the 92 callbacks of the start (import, __init__, start of every module, at step 12): the slowest | 3.38 ms (max) | 0.00013 to 3.38 (n=92) | at most 4 ms | **PASS** | heaviest: Media.start 3.4 ms, Clock.import 0.9 ms, Tray.import 0.9 ms; the loop is held while a module starts |
| module callbacks on the loop in steady state (p99) | 0.216 ms (p99) | 0.0148 to 0.547 (n=500) | at most 4 ms | **PASS** | 500 callbacks of Battery, Workspaces and Clock; heaviest: Clock.Clock.tick 0.55 ms, Workspaces.switch 0.35 ms, Clock.show 0.06 ms |
| module callbacks on the loop in steady state (max) | 0.547 ms (max) | 0.0148 to 0.547 (n=500) | at most 4 ms | **PASS** | the budget is a p99: the max is for the record |
| share of steady-state callbacks over 4 ms | 0 % (median) | 0 to 0 (n=1) | - | **RECORDED** | regression test: under 2 % |
| start-up callbacks (15: import, __init__, start) | 0.0149 ms (median) | 0.000932 to 0.189 (n=15) | - | **RECORDED** | heaviest: Battery.start 0.19 ms, Battery.import 0.14 ms, Workspaces.start 0.07 ms |

### B10 Watchdog

Budget: A stall of 2 s logs; 10 s asks systemd for a restart (WATCHDOG=trigger). Source: Performance Budgets > Proposed Values; Crash Recovery and Watchdog.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| first log line after the loop was blocked | 1.9 s (max) | 1.35 to 1.9 (n=3) | at most 3 s | **PASS** | the budget is 'a stall of 2 s logs'; the limit is 2 s plus one heartbeat period (1 s), the watchdog's own resolution, as the last beat was up to 1 s before the block began |
| WATCHDOG=trigger sent after the loop was blocked | 9.91 s (max) | 9.36 to 9.91 (n=3) | at most 11.0 s | **PASS** | the budget is 'a stall of 10 s asks for the restart'; the limit is 10 s plus one heartbeat period |

### B11 Motion durations

Budget: Duration.Short 100 ms, Medium 200 ms, Long 400 ms. Source: Performance Budgets > Proposed Values.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| Duration.Short of the shipped Default theme (at most) | 100 ms (max) | 100 to 100 (n=1) | at most 100 ms | **PASS** |  |
| Duration.Short of the shipped Default theme (at least) | 100 ms (max) | 100 to 100 (n=1) | at least 100 ms | **PASS** |  |
| Duration.Medium of the shipped Default theme (at most) | 200 ms (max) | 200 to 200 (n=1) | at most 200 ms | **PASS** |  |
| Duration.Medium of the shipped Default theme (at least) | 200 ms (max) | 200 to 200 (n=1) | at least 200 ms | **PASS** |  |
| Duration.Long of the shipped Default theme (at most) | 400 ms (max) | 400 to 400 (n=1) | at most 400 ms | **PASS** |  |
| Duration.Long of the shipped Default theme (at least) | 400 ms (max) | 400 to 400 (n=1) | at least 400 ms | **PASS** |  |

### B12 Control interface

Budget: `toggle` under 100 ms end to end (client about 20 ms); one loop callback under 1 ms; an idle shell receives no calls and wakes for none. Source: IPC and CLI > Performance Budget; ADR-0013.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| loop callback of a `toggle Launcher` (108 toggles): ShellCommands.surface | 1.75 ms (p99) | 0.319 to 1.92 (n=108) | at most 1 ms | **FAIL** | misses by 0.745 ms, 75 %. shows or hides the Launcher Panel (one lookup and the tre calls) |
| `tesserae-shell toggle Launcher` end to end, start to exit (30 calls) | 57.9 ms (median) | 53.4 to 71.7 (n=30) | at most 100 ms | **PASS** | python -m tess_shell, the thin client, against the running default shell |
| one toggle command's callback on the loop, 200 runs | 0.0843 ms (p99) | 0.0261 to 0.293 (n=200) | at most 1 ms | **PASS** | ShellCommands.surface('Toggle', 'Dock') on the real manager, headless; the CLI end to end is the lead's |

### B13 D-Bus layer

Budget: Idle: no timer, 0 wake-ups per second with no signal traffic; one connection per bus. Source: D-Bus Service Layer > Performance Budget.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| dbus service thread of the default shell, voluntary switches in the 60 s idle window | 0 switches (max) | 0 to 0 (n=3) | at most 0 switches | **PASS** | fake buses with no signal traffic; the thread also serves Audio, the tray host, the control interface and the shortcuts |
| loop iterations per second (dbus thread, 2 modules with property + signal subscriptions, 60 s idle) | 0 per s (max) | 0 to 0 (n=2) | at most 0 per s | **PASS** | idle test of tests/test_dbus_idle.py; the 5 s run is collected by default |
| kernel timeslices per second (dbus thread, 2 modules with property + signal subscriptions, 60 s idle) | 0 per s (max) | 0 to 0 (n=2) | at most 0 per s | **PASS** |  |
| voluntary context switches per second (dbus thread, 2 modules with property + signal subscriptions, 60 s idle) | 0 per s (max) | 0 to 0 (n=2) | at most 0 per s | **PASS** |  |
| shell connections on the two fake buses, 1 module vs 8 modules (one per bus: 2) | 2 connections (max) | 2 to 2 (n=2) | at most 2 connections | **PASS** | connects counted by the layer: 1 module 1+1, 8 modules 1+1 |

### B14 Global shortcuts

Budget: Registration: one doRegister and one setShortcut per action, under 50 ms for 10 actions; a key press to the state change under one frame; idle: no timer. Source: Global Shortcuts > Performance Budget.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| 10 actions registered (fake kglobalaccel) | 3.81 ms (median) | 2.53 to 4.27 (n=20) | at most 50.0 ms | **PASS** | wall time of ShortcutService.start on the dbus thread, fake kglobalaccel |
| doRegister calls per action | 1 calls (max) | 1 to 1 (n=20) | at most 1 calls | **PASS** |  |
| setShortcutKeys calls per action | 2 calls (max) | 2 to 2 (n=20) | at most 1 calls | **FAIL** | misses by 1 calls, 100 %. the vault says one setShortcut per action; the shell sends two setShortcutKeys (flags (2, 8): present, default) like the client library: Decision to confirm |
| isGlobalShortcutAvailable calls per action (one chord each) | 1 calls (median) | 1 to 1 (n=20) | - | **RECORDED** | not in the vault's budget: recorded |
| key press (fake.press) to the callback on the loop thread, 50 presses | 0.409 ms (p95) | 0.0633 to 0.411 (n=50) | at most 16.7 ms | **PASS** | one frame = 16.7 ms; includes the fake daemon's hop and the dbus thread |

### B15 Portals

Budget: One ReadAll at start, under 20 ms of service-thread time; idle: no timer. Source: Portals > Performance Budget.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| service-thread time of the first read (Register + ReadAll, fake portal) | 0.459 ms (median) | 0.208 to 0.638 (n=12) | at most 20.0 ms | **PASS** | includes the Register call the reader makes first |
| ReadAll calls at start | 1 calls (max) | 1 to 1 (n=12) | at most 1 calls | **PASS** |  |
| portal calls over 3 s idle (no polling) | 0 calls (max) | 0 to 0 (n=12) | at most 0 calls | **PASS** |  |

### B16 Popup

Budget: A menu on screen within one or two frames of the click (to be measured); a closed Popup holds nothing; an open one draws no frames while nothing changes. Source: Popup > Performance Budget.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| open of a Popup, loop-thread time of popups.call on a headless tre PopupWindow | 0.269 ms (median) | 0.249 to 2.35 (n=200) | at most 33.3 ms | **PASS** | no compositor: the time to a configured, drawn popup needs a live sway and the whole shell process; this is the loop-thread share of the click to the open; limit = two frames (33.3 ms), the vault says one or two |
| close of a Popup, loop-thread time of popups.call on a headless tre PopupWindow | 0.0208 ms (median) | 0.019 to 0.0817 (n=200) | - | **RECORDED** |  |
| an open Popup draws no frames while nothing changes | - | - | - | NOT MEASURED | headless windows draw no frames: Window.frame_stats records only after App.run() opens the window, which needs a compositor; the in-process rig has none. Not measured (no invented counter) |
| closed Popup holds nothing: growth of threads | 0 count (max) | 0 to 0 (n=1) | at most 0 count | **PASS** | after 200 open/close cycles, headless |
| closed Popup holds nothing: growth of fds | 0 count (max) | 0 to 0 (n=1) | at most 0 count | **PASS** | after 200 open/close cycles, headless |
| closed Popup holds nothing: growth of bar_nodes | 0 count (max) | 0 to 0 (n=1) | at most 0 count | **PASS** | after 200 open/close cycles, headless |
| closed Popup holds nothing: growth of open_popups | 0 count (max) | 0 to 0 (n=1) | at most 0 count | **PASS** | after 200 open/close cycles, headless |
| closed Popup holds nothing: growth of popup_windows | 0 count (max) | 0 to 0 (n=1) | at most 0 count | **PASS** | after 200 open/close cycles, headless |
| closed Popup holds nothing: growth of live_trees | 0 count (max) | 0 to 0 (n=1) | at most 0 count | **PASS** | after 200 open/close cycles, headless |
| closed Popup holds nothing: Python blocks left per cycle | 4 blocks (median) | 4 to 4 (n=1) | - | **RECORDED** | tre holds handler wrappers of a closed headless window (about 20 per open) |

### B17 Per-surface video memory

Budget: A 1280 x 32 bar about 18 MiB, a small window about 31 MiB, a 4K full-screen surface about 177 MiB (tre 0.5.8); the budget is set in 60 Quality. Source: Surface Types > Performance Budget; Goals G5.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| video memory, a 1280 x 32 Bar | 1.47 MiB (median) | 1.47 to 1.47 (n=3) | - | **RECORDED** | tre's frame_stats()['memory'] of the process's one shared device, one window open; the first window carries the device's fixed buffers; the vault has about 18 MiB for this on tre 0.5.8 |
| frames drawn in 1 s of idling, a 1280 x 32 Bar | 0 frames (max) | 0 to 0 (n=3) | at most 0 frames | **PASS** | an idle surface draws no frames (Goals G4) |
| video memory, a 200 x 100 window | 1.39 MiB (median) | 1.39 to 1.39 (n=3) | - | **RECORDED** | tre's frame_stats()['memory'] of the process's one shared device, one window open; the first window carries the device's fixed buffers; the vault has about 31 MiB for this on tre 0.5.8 |
| frames drawn in 1 s of idling, a 200 x 100 window | 0 frames (max) | 0 to 0 (n=3) | at most 0 frames | **PASS** | an idle surface draws no frames (Goals G4) |
| video memory, a full-screen surface at 1280 x 720 | 4.83 MiB (median) | 4.83 to 4.83 (n=3) | - | **RECORDED** | tre's frame_stats()['memory'] of the process's one shared device, one window open; the first window carries the device's fixed buffers |
| frames drawn in 1 s of idling, a full-screen surface at 1280 x 720 | 0 frames (max) | 0 to 0 (n=3) | at most 0 frames | **PASS** | an idle surface draws no frames (Goals G4) |
| video memory, a full-screen surface at 3840 x 2160 (4K) | 33.0 MiB (median) | 33.0 to 33.0 (n=3) | - | **RECORDED** | tre's frame_stats()['memory'] of the process's one shared device, one window open; the first window carries the device's fixed buffers; the vault has about 177 MiB for this on tre 0.5.8 |
| frames drawn in 1 s of idling, a full-screen surface at 3840 x 2160 (4K) | 0 frames (max) | 0 to 0 (n=3) | at most 0 frames | **PASS** | an idle surface draws no frames (Goals G4) |
| video memory, a 3840 x 32 Bar at 4K | 1.78 MiB (median) | 1.78 to 1.78 (n=3) | - | **RECORDED** | tre's frame_stats()['memory'] of the process's one shared device, one window open; the first window carries the device's fixed buffers |
| frames drawn in 1 s of idling, a 3840 x 32 Bar at 4K | 0 frames (max) | 0 to 0 (n=3) | at most 0 frames | **PASS** | an idle surface draws no frames (Goals G4) |

### B18 Binding and tre call cost

Budget: Bind of a 3,101-node tree under 15 ms (D12, D18); tre call costs are reference figures. Source: M1 Build Log D12 and D18; TRE-REQ-009.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| bind of a typed tree of 3,101 nodes (build + attach + dispose) | 34.4 ms (median) | 32.1 to 112 (n=60) | at most 15.0 ms | **FAIL** | misses by 19.43 ms, 130 %. as tests/perf/measure_bind.py, headless window |
| bind of the M1 example (5 nodes) | 0.0824 ms (median) | 0.0777 to 0.772 (n=200) | - | **RECORDED** |  |
| tre calls the binder makes for the 3,101-node tree | 34.0 calls (median) | 34.0 to 34.0 (n=1) | - | **RECORDED** | Node.add_child x1, Node.children x32, Window.build x1 |
| tre calls the binder makes for the M1 example | 3 calls (median) | 3 to 3 (n=1) | - | **RECORDED** | Node.add_child x1, Node.children x1, Window.build x1 |
| tre Window.create('box') per call | 0.463 us (median) | 0.441 to 0.915 (n=30) | - | **RECORDED** | tess_re called directly on a headless Window, per call, batches of 500 |
| tre Window.create('text') per call | 0.715 us (median) | 0.7 to 0.829 (n=30) | - | **RECORDED** | tess_re called directly on a headless Window, per call, batches of 500 |
| tre Node.set(width=...) per call | 0.534 us (median) | 0.525 to 0.559 (n=30) | - | **RECORDED** | tess_re called directly on a headless Window, per call, batches of 500 |
| tre Node.add_child per call | 0.0906 us (median) | 0.0891 to 0.101 (n=30) | - | **RECORDED** | tess_re called directly on a headless Window, per call, batches of 500 |

### B19 Config load and validation

Budget: Milliseconds at most for a shell of a few hundred entries (no number). Source: Validation and Errors > Performance Budget.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| tess_dl.parse of the shell file | 2.76 ms (median) | 2.75 to 2.85 (n=40) | - | **RECORDED** | generated shell of about 407 entries (blocks), shipped modules |
| parse + read_shell (typed, modules resolved) | 7.34 ms (median) | 6.93 to 33.5 (n=40) | - | **RECORDED** | generated shell of about 407 entries (blocks), shipped modules |
| scan of the whole config folder (every shipped module and the shell) | 36.8 ms (median) | 35.0 to 59.6 (n=40) | - | **RECORDED** | generated shell of about 407 entries (blocks), shipped modules; the vault states no number: recorded |

### B20 Logging

Budget: A record about 27 us on the calling thread with enqueue=True; below the level 0.13 us; one writer thread that sleeps until a record arrives. Source: Logging > Performance Budget.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| logging writer threads, voluntary switches in the 60 s idle window | 0 switches (max) | 0 to 0 (n=3) | at most 0 switches | **PASS** | no record is written at idle: the writers sleep until one arrives |
| one record on the calling thread (enqueue=True file sink) | 17.2 us (median) | 14.8 to 658 (n=5000) | - | **RECORDED** | the vault's reference is about 27 us |
| one record below the sink's level | 0.23 us (median) | 0.18 to 3.21 (n=5000) | - | **RECORDED** | the vault's reference is 0.13 us |
| threads the logging setup adds | 2 threads (median) | 2 to 2 (n=1) | - | **RECORDED** | the vault says one writer thread; the shell also starts the Timer thread of the midnight file swap (threading.Timer in logging.py): Decision to confirm |
| voluntary context switches of the logging threads over 5 s idle | 0 switches (max) | 0 to 0 (n=1) | at most 0 switches | **PASS** |  |

### B21 CLI start

Budget: A client that makes one call takes about 20 ms (the thin client imports no engine). Source: ADR-0013 > Context.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| `tesserae-shell status`, client start to exit (30 calls) | 56.0 ms (median) | 50.6 to 66.7 (n=30) | - | **RECORDED** | the vault says about 20 ms for a client that makes one call |
| reference: `python -c pass` | 8.23 ms (median) | 6.3 to 10.1 (n=30) | - | **RECORDED** | the interpreter's own start on this machine (the vault measured 7.6 ms) |

### B22 Clock tick

Budget: One timer for all uses; under 1 ms per tick on the loop thread; no timer faster than the shown unit. Source: Clock Module > Performance Budget.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| time-source thread with the Clock showing seconds: voluntary switches per second | 1 per s (median) | 1 to 1 (n=2) | - | **RECORDED** | the Clock's tick is one a second: the time source must not wake faster than the finest unit shown (one wake-up per tick is expected) |
| time-source thread, voluntary switches in the 60 s idle window (a Clock showing minutes) | 1 switches (median) | 1 to 1 (n=3) | - | **RECORDED** | a Clock with %H:%M subscribes to the minute: a 60 s window holds one tick (a few switches); the time source never wakes faster than the finest unit shown |
| Clock tick callbacks on the loop (48 ticks, seconds and minutes) | 0.267 ms (p99) | 0.0148 to 0.267 (n=48) | at most 1 ms | **PASS** | the Clock's tick and tick_seconds entry points |
| one Clock tick on the loop: show + flush + a frame, 200 ticks | 0.173 ms (p99) | 0.0667 to 0.323 (n=200) | at most 1 ms | **PASS** | the shipped Clock in a headless Bar; each tick shows a new minute |

### B23 Hot reload watcher idle

Budget: Blocks in a read and wakes only on a file event. Source: Hot Reload > Performance Budget; Goals G4.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| file watcher threads, voluntary switches in the 60 s idle window | 0 switches (max) | 0 to 0 (n=3) | at most 0 switches | **PASS** | the watchers block in select and wake on a file event only |

### B24 Callback record cost

Budget: Keep the record unless it costs over 1 % of the 4 ms callback budget (40 us). Source: Security Model > Questions After Testing 1.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| enter + leave per callback beyond the bare call | 125 ns (median) | 124 to 148 (n=7) | - | **RECORDED** | 200,000 calls per repeat; the bare call loop is subtracted |
| run() of a trivial callable per callback beyond the bare call | 156 ns (median) | 155 to 164 (n=7) | - | **RECORDED** | 200,000 calls per repeat; the bare call loop is subtracted |
| enter + leave as a share of the 4 ms callback budget | 0.00312 % of 4 ms (median) | 0.0031 to 0.00371 (n=7) | at most 1 % of 4 ms | **PASS** | the vault's keep-it line: 1 % = 40 us |
| run() as a share of the 4 ms callback budget | 0.0039 % of 4 ms (median) | 0.00388 to 0.00409 (n=7) | at most 1 % of 4 ms | **PASS** |  |

### B25 Heartbeat and watchdog wake-ups

Budget: About 2 wake-ups per second of their own against the idle budget of 5; slow the heartbeat to 2 s if the budget is at risk. Source: Crash Recovery and Watchdog > Performance budget, Open Question 3.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| watchdog thread, default shell, between ticks | 1.02 per s (median) | 1.02 to 1.05 (n=3) | - | **RECORDED** | the thread wakes once per tick (1 s) |
| loop thread, default shell, between ticks | 1.05 per s (median) | 1.04 to 1.13 (n=3) | - | **RECORDED** | the loop is woken by the heartbeat's call_soon: it is the loop thread's share. tre's own helper threads (blocking-N: the OS-preference watcher) are a floor the shell does not control |
| loop thread, watchdog off, between ticks | 0 per s (median) | 0 to 0 (n=2) | - | **RECORDED** | the same shell with the watchdog's times scaled by 1000 |
| whole shell with the watchdog minus whole shell without it | 2.06 per s (median) | 2.06 to 2.06 (n=2) | - | **RECORDED** | the heartbeat and the watchdog's own cost in wake-ups: loop plus thread plus whatever tre wakes for the queued call (one paired difference per run without) |
| whole shell with the heartbeat slowed to every 2 s (the watchdog's times doubled) | 3.11 per s (median) | 3.09 to 3.14 (n=2) | - | **RECORDED** | what the slowing would leave: the same default shell, TESS_SHELL_TEST_WATCHDOG_SCALE=2; the stall warning would come at 4 s and the restart at 20 s, so this is the wake-up saving only: a real change keeps 2 s and 10 s |
| wake-ups saved per second by a 2 s heartbeat (default minus slowed) | 0.96 per s (median) | 0.938 to 0.982 (n=2) | - | **RECORDED** | paired with the median of the default runs |
| whole shell under the systemd watchdog (WATCHDOG_USEC 15 s), between ticks | 4.51 per s (median) | 4.51 to 4.51 (n=2) | - | **RECORDED** | the unit's setting; the same heartbeat plus a datagram every 7.5 s |
| WATCHDOG=1 datagrams per second (supervised) | 0.133 per s (median) | 0.133 to 0.133 (n=2) | - | **RECORDED** | the vault says one every WatchdogSec / 2 = 7.5 s (0.133 per s) |

### B26 Frame time

Budget: A frame at 60 Hz is about 16.7 ms and callbacks, layout and paint share it; an idle surface draws no frames (G4). Source: Process Model and Threading > Performance Notes; Goals G4.

| What | Value | Spread (min to max) | Limit | Verdict | Note |
|---|---|---|---|---|---|
| time of a frame while a node moves every 16 ms (p95 of the last 240) | 1.63 ms (median) | 1.51 to 1.92 (n=3) | at most 16.7 ms | **PASS** | a 1280 x 32 Bar on the software Vulkan driver (llvmpipe), a pessimistic stand-in for a GPU; one frame at 60 Hz is 16.7 ms |
| time of a frame while a node moves every 16 ms (worst of the last 240) | 11.5 ms (median) | 9.68 to 170 (n=3) | - | **RECORDED** | a 1280 x 32 Bar on the software Vulkan driver (llvmpipe), a pessimistic stand-in for a GPU; one frame at 60 Hz is 16.7 ms |
| CPU time of a frame while a node moves every 16 ms (mean) | 0.399 ms (median) | 0.398 to 0.42 (n=3) | - | **RECORDED** | tre's own account of the CPU part of the frame |

## What ran

| Measure | Result | Time |
|---|---|---|
| idle | 45 readings | 982 s (load 0.23 at start) |
| start | 9 readings | 16 s (load 0.78 at start) |
| reload | 2 readings | 16 s (load 0.98 at start) |
| callbacks | 5 readings | 48 s (load 0.91 at start) |
| control | 3 readings | 8 s (load 1.59 at start) |
| watchdog | 2 readings | 45 s (load 1.55 at start) |
| surfaces | 14 readings | 55 s (load 0.96 at start) |
| inproc | 53 readings | 174 s (load 0.73 at start) |
