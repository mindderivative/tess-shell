# Module process test: results

Reported, not decided. Produced by `tests/perf/module_process_test.py` (M7a2 of the M7 brief; `60 Quality/Module Process Test.md`). **The maintainer decides**; the VERDICT TABLE only applies the starting thresholds of the spec to the numbers measured, and the thresholds are named constants at the top of the harness.

> **The product, posture C as built (PR #91), measured on 2026-11-19, 20:08 to 20:29, on an idle machine (load 0.27 at the start).** A and P only. P passes every row of the decision table: the default shell equals A; with three user modules start +128 ms, wake-ups +0.32 per second, memory +51 MB (about 17 MB per module); value to screen p95 0.66 ms; a hung and a killed module are contained and restarted. The prototype's C numbers hold for the shell as shipped.

## Machine and run

|  |  |
|---|---|
| machine | hive-worker (x86_64) |
| kernel | 7.3.5-1-cachyos |
| cpu | AMD Ryzen AI 9 HX 370 w/ Radeon 890M, 24 threads |
| memory | 46.7 GiB |
| python | 3.14.10 (with the GIL) |
| tesserae-engine | 0.6.9 |
| tesserae-shell | 0.1.2 |
| git | e3b48b1 on p-cell |
| load average at the start | 0.27 0.37 0.37 |
| date | 2026-11-19T20:08:17-08:00 |
| compositor | private headless sway, pixman renderer, 1280x720 |


Command flags: `--smoke=False --postures=A,P --measures=start,idle,latency,contain --reps=3 --start-runs=20 --latency-reps=None --contain-reps=None --idle=60.0 --settle=10.0 --singles=1000 --gap-ms=20 --burst-rate=200.0 --burst-seconds=5.0 --ladder=200,500,1000,2000,5000,10000 --ladder-seconds=3.0 --hang=10.0 --stall=2.0 --kill=5.0 --baseline=3.0 --allow-load=False --lean-rule=strict --out=/tmp/m7/p-real.md`

Run time of this measurement: 21.3 minutes.

1-minute load average at the start of each run: median 0.64, highest 1.23 (the harness's own earlier runs add to it; only the check at the very start is a refusal).

## The postures

- **A**, in process: the product as it is (the harness runs plain `python -m tess_shell run` for the start, idle and memory of A; the wrapper only where the probe needs it).
- **B**, a process per module FILE (the maintainer's answer to open question 1): every file the default shell loads, 22 of them, runs its `Module` in a child; the shell holds a stub class built from the file's syntax tree, so no module code runs in the shell.
- **C**: the shipped modules stay in the shell, each USER module file runs as in B.
- **L**, lean B: a module file whose Python has code of its own (a method, a constant, a function: see the section on the lean B) runs in a child as in B; a file with none (a class that is only `pass`: the TDL-only widget and popup modules) stays in the shell and is imported there by the product's own code. `L1` and `L2` are L with the processes on B1 or B2.
- **Services.** `B1`: each process opens its own connections (a D-Bus connection and service thread when it uses `ctx.dbus`, a PulseAudio connection for `ctx.audio`, a tray host name). `B2`: the shell keeps the connections and the process proxies calls and signals over the pipe. In both, popups, surfaces, windows, the application index and the icon registry stay in the shell (they are tre's or the shell's state, not connections): that is B2 by necessity. `C1` and `C2` are C with the user modules on B1 or B2.
- **Pipe.** JSON lines over one `AF_UNIX` socketpair per process (reasons in `tests/perf/proto/wire.py`: the payloads are small and plain, a line is readable in a failure, and a closed peer is noticed at once as end of file). `ctx.send` queues one line; a writer thread joins what is queued into one `sendall`, so a burst is one syscall and an idle process wakes for nothing. The shell's reader thread calls the same `ValueStore.send`, so the per-key coalescing and the one `call_soon` flush are exactly A's.
- **Watchdog (B, C and L).** The process records the callback it runs in shared memory (a memfd the shell passes in: two stores per callback); a watchdog thread of the shell reads it every 1.0 s, logs a stall at 2 s and kills the process at 5 s; the existing back-off then restarts the module (first try after 1 s). The 10 s kill of Crash Recovery would let a 10 s sleep end by itself, and only one module restarts, so the prototype kills earlier (a decision to confirm). A (this base has no M7b watchdog) has no recovery: the shell stays frozen until the callback returns.

## Start time (process start to `READY=1`, milliseconds)

| Cell | Median (min to max) | p95 | Processes after start | Budget < 2 s |
|---|---|---|---|---|
| A / default | 263 (237 to 278) | 271 | 2 (2 to 2) | within |
| P / default | 251 (242 to 262) | 261 | 2 (2 to 2) | within |
| A / plus3 | 250 (238 to 274) | 273 | 2 (2 to 2) | within |
| P / plus3 | 379 (365 to 403) | 390 | 5 (5 to 5) | within |

Runs per cell: 20. `default` is the default shell; `plus3` adds three user modules.

## Idle: CPU, wake-ups, memory (default shell; after the settle time, window of the flags)

| Cell | CPU % of one core | Wake-ups / s (context switches) | PSS MB | RSS MB | Processes | Threads |
|---|---|---|---|---|---|---|
| A / default | 0.050 (0.033 to 0.050) | 10.03 (9.95 to 10.23) | 151 (150 to 151) | 224 (224 to 224) | 2 (2 to 2) | 81 (81 to 81) |
| P / default | 0.033 (0.033 to 0.033) | 9.73 (9.71 to 9.90) | 151 (151 to 151) | 224 (224 to 224) | 2 (2 to 2) | 81 (81 to 81) |
| A / plus3 | 0.033 (0.033 to 0.033) | 9.78 (9.76 to 10.28) | 151 (151 to 151) | 224 (224 to 224) | 2 (2 to 2) | 82 (82 to 82) |
| P / plus3 | 0.033 (0.033 to 0.050) | 10.10 (9.93 to 10.43) | 203 (203 to 203) | 307 (307 to 307) | 5 (5 to 5) | 98 (98 to 98) |

The floor of a process per module file: interpreter 4.6 MB PSS, interpreter + module context 17.2 MB PSS (one idle process, measured by itself).

Budgets (informational): CPU at most 0.5 %, wake-ups at most 5 a second. Wake-ups are counted as context switches summed over every thread of every process of the tree (`/proc/PID/task/*/status`), which over-counts (the engine's software-renderer threads, `llvmpipe`, add a burst when the surfaces repaint in the first seconds after the start: the settle time and the median of the repetitions guard against it, a 1 s settle as in the smoke run does not). PSS and RSS are summed over the tree after the idle window. Window: 60 s, repetitions: 3.

## Value to screen (`ctx.send` in a module to the node's property set)

Both ends are stamped with `CLOCK_MONOTONIC`, which the shell and its module processes share: the probe module writes `<seq>:<monotonic ns>` as its value and logs every send; a wrapper around `ValueStore._turn` (the flush and the surfaces' property set, `on_change`) logs the time after the set and the value it showed. A value that another overtook inside one flush counts to that flush. The probe runs in the shell's process in A and in a module process in B, C and L. Single updates are isolated (1000 values, 20 ms apart); the burst is 200 values a second for 5 s.

| Cell | Single p50 ms | Single p95 | Single p99 | Burst p50 | Burst p95 | Burst p99 |
|---|---|---|---|---|---|---|
| A | 0.36 (0.20 to 0.51) | 0.85 (0.36 to 0.92) | 1.09 (0.56 to 1.13) | 0.10 (0.06 to 0.11) | 0.20 (0.17 to 0.36) | 0.34 (0.20 to 0.89) |
| P | 0.33 (0.32 to 0.35) | 0.66 (0.51 to 0.86) | 0.84 (0.74 to 1.10) | 0.11 (0.11 to 0.13) | 0.61 (0.43 to 0.64) | 1.23 (1.09 to 1.46) |

## Throughput (values a second sustained before p95 passes one frame)

| Cell | Values / s, median (min to max) |
|---|---|
| A | 10000 (10000 to 10000) |
| P | 10000 (10000 to 10000) |

Frame = 16.7 ms; a rate counts only if at least 90 % of it was really sent. Ladder: 200,500,1000,2000,5000,10000; 3 s each.

| Cell | Rate asked | Sent / s | p95 ms |
|---|---|---|---|
| A | 200 | 200 (200 to 200) | 0.22 (0.18 to 0.64) |
| A | 500 | 500 (500 to 500) | 0.17 (0.12 to 0.18) |
| A | 1000 | 1000 (1000 to 1000) | 0.07 (0.07 to 0.11) |
| A | 2000 | 2000 (2000 to 2000) | 0.07 (0.06 to 0.08) |
| A | 5000 | 5000 (5000 to 5000) | 0.06 (0.06 to 0.10) |
| A | 10000 | 10000 (10000 to 10000) | 0.06 (0.06 to 0.09) |
| P | 200 | 200 (200 to 200) | 0.64 (0.63 to 0.73) |
| P | 500 | 500 (500 to 500) | 0.45 (0.35 to 0.60) |
| P | 1000 | 1000 (1000 to 1000) | 0.40 (0.35 to 0.54) |
| P | 2000 | 2000 (2000 to 2000) | 0.36 (0.35 to 0.52) |
| P | 5000 | 5000 (5000 to 5000) | 0.48 (0.46 to 0.52) |
| P | 10000 | 10000 (10000 to 10000) | 0.58 (0.55 to 0.64) |

## Hang, crash, reload

The test node is a `Marquee_Text` that scrolls all the time in the Bar. `grim` captures the Bar from the compositor as fast as it can (20 to 50 times a second, depending on the load) and each capture is hashed; the share of the captures that differ from the one before is about 100 % for a node that paints all the time and 0 % for a frozen one, and the longest stop is the longest wait between two changes (`Paint` in `tests/perf/proto/measure.py`). It says whether the shell is painting, not the engine's own frame rate. The Victim module's tick callback sleeps 10 s on a trigger; a crash is SIGKILL of the module's own process; a reload is the module's file saved with a new `VERSION` (the shell's file watcher, 200 ms debounce).

### Hang

| Cell | Picture changed before (% of captures) | Picture changed during the hang (%) | Longest stop (s) | Time to detect (s, stall log) | Time to recover (s, new instance running) |
|---|---|---|---|---|---|
| A | 96 (96 to 96) | 0 (0 to 0) | 10.00 (10.00 to 10.00) | none (no watchdog in A) | none: returned by itself after 10.00 (10.00 to 10.00) |
| P | 100 (100 to 100) | 100 (100 to 100) | 0.03 (0.03 to 0.03) | 2.01 (2.00 to 2.04) | 8.06 (8.06 to 8.07) |

### Crash (SIGKILL of the module's process)

| Cell | Picture changed after the kill (%) | Longest stop (s) | Time to restart (s) | The log line |
|---|---|---|---|---|
| A | n/a | n/a | n/a | a module is not a process in A: nothing to kill |
| P | 99 (99 to 99) | 0.03 (0.03 to 0.03) | 1.23 (1.22 to 1.25) | `2026-11-19 20:28:36.819 | ERROR    | shell | - | /tmp/tmp-proc-run-927yu0ip/cfg/Modules/Victim/Victim_Module.py:1:1: module Victim (UID 01a1f736-94d5-74f8-a761-3f85981427d8): the module process (pid 615476) ended: exit code -9 (killed by SIGKILL); its surfaces keep their last values` |

### Reload (file saved to the new instance running, seconds)

| Cell | Median (min to max) |
|---|---|
| A | 0.247 (0.246 to 0.260) |
| P | 0.310 (0.308 to 0.316) |

## Verdict table (the decision rule of the spec, computed; the maintainer decides)

Thresholds (constants at the top of `tests/perf/module_process_test.py`): start +300 ms; wake-ups +2 a second; value to screen p95 16.7 ms; memory +150 MB (PSS of the tree); containment: the test node paints at least 0.5 of its normal rate and never stops for more than 1 s while a module hangs or is killed, and the module restarts.

| Test | Cell | Measured | Passes when | Verdict |
|---|---|---|---|---|
| Start | P | -12 ms | <= 300 ms | PASS |
| Wake-ups | P | -0.30 per s | <= 2 per s | PASS |
| Memory | P | +0 MB | <= 150 MB | PASS |
| Start (+3 user modules) | P | +128 ms | <= 300 ms | PASS |
| Wake-ups (+3 user modules) | P | +0.32 per s | <= 2 per s | PASS |
| Memory (+3 user modules) | P | +51 MB | <= 150 MB | PASS |
| Value to screen, single | P | p95 0.66 ms | <= 16.7 ms | PASS |
| Value to screen, burst | P | p95 0.61 ms | <= 16.7 ms | PASS |
| Containment | P | 3 of 3 repetitions | hang and kill: surfaces paint, module restarts | PASS |

**Rule applied to these numbers:** P, the product (posture C as built), passes every row: the numbers of the prototype's C hold for the shell as shipped.

Rows compare with A as measured in this run (start, wake-ups and memory on the default shell, C1 being C with no user module). B1/B2, C1/C2 and L1/L2 are the services variants. The rule is applied to the numbers as measured, not to how the prototype looks.

## Which C: the product (P) against the prototype's C1 and C2

| Cell | Start ms | Wake-ups / s | PSS MB | Processes |
|---|---|---|---|---|
| A / default | 263 (237 to 278) | 10.03 (9.95 to 10.23) | 151 (150 to 151) | 2 (2 to 2) |
| P / default | 251 (242 to 262) | 9.73 (9.71 to 9.90) | 151 (151 to 151) | 2 (2 to 2) |
| A / plus3 | 250 (238 to 274) | 9.78 (9.76 to 10.28) | 151 (151 to 151) | 2 (2 to 2) |
| P / plus3 | 379 (365 to 403) | 10.10 (9.93 to 10.43) | 203 (203 to 203) | 5 (5 to 5) |
The default shell has no user module, so P equals A there; the +3 user modules rows are where P differs from A (one process each). Latency, hang, crash and reload for P are in their tables above.

## The forms side by side (default shell)

| Variant | Start ms | Wake-ups / s | PSS MB | Processes | Single p95 ms |
|---|---|---|---|---|---|
| A | 263 (237 to 278) | 10.03 (9.95 to 10.23) | 151 (150 to 151) | 2 (2 to 2) | 0.85 (0.36 to 0.92) |
| P | 251 (242 to 262) | 9.73 (9.71 to 9.90) | 151 (151 to 151) | 2 (2 to 2) | 0.66 (0.51 to 0.86) |


What each costs to build: **B1** needs nothing new for the three services (the shell's own `Layer`, `AudioService` and `TrayService` run in the process, about 22 lines in `child.py`); **B2** needs proxies for them (162 lines in `proxies.py`) and brokers in the shell (139 lines in `brokers.py`), and its `Bus.run(coro)` runs the module's coroutine in the process while `get` and `call` are answered by the shell. B1 opens one connection per process that uses a service (Audio and Audio_Outputs are two files, so two PulseAudio connections; each of the six D-Bus modules has its own `dbus` thread and socket); B2 keeps one of each in the shell and a process that uses none imports no D-Bus code.

## What the prototype leaves out

The prototype runs the eight default modules, the Launcher's Applications and the widget modules they
use (22 module files in the default shell), and the three user modules of the test. It does not
support, and the report does not claim:

- `ctx.focus` (shortcut mode): not offered in a module process, `ctx.focus` raises.
- `Event.stop()`: the event is delivered to the process after the handler of the shell has returned,
  so a module cannot stop it; none of the shipped modules does. A real B needs a declared stop (a
  property of the handler) or a synchronous reply.
- The result of an `@action` (`Call` from the CLI or the control interface): the stub returns
  `None`, so `tesserae-shell call` prints `null` for a module in a process. A real B needs a reply
  (an RPC with a timeout) on that path.
- Actions that a module inherits from another user class, and classes that do not extend `Module`
  directly: the stub class is made from the file's syntax tree (nothing is imported in the shell), so
  it sees the `@action` methods of classes that extend `Module` themselves.
- Import and `__init__` errors of a module are reported when the process starts it, as the log
  line and a finding of `module-import`, not as the load-time findings of `check`. `tesserae-shell
  check` is not made aware of the patch (it would start the processes).
- `many-threads` and `slow-module` (M7a controls 5 and 6) for module processes: the shell's record
  of the running callback is replaced by a shared-memory record read by a watchdog that only knows
  "this callback has run for N seconds".
- The differences JSON makes: a tuple arrives as a list and an integer dictionary key as text. The
  prototype restores the one tuple that matters (the several results of a D-Bus `call`: the Tray
  tests `isinstance(reply, tuple)` on `GetLayout`, which the first B2 run broke), tags bytes as
  base64 (a tray icon's pixmap), and leaves every other tuple a list. A user module that tells the two
  apart would break the same way.
- Several uses of `ctx.send` ordering across modules, a module's `threading` objects shared with
  another module, and anything that reads a module's `sys.modules` entry from the shell.
- Real hardware: the test runs against the fakes (NetworkManager, UPower, MPRIS, StatusNotifier,
  KWin virtual desktops, PulseAudio) on private buses; KWin's window script is off, so Tasks shows no
  windows (its `ctx.windows` proxy ran, and its list stayed empty).

## The cost in code of the move

| File of the prototype | Lines (not blank) | What it is |
|---|---|---|
| `tests/perf/proto/__init__.py` | 0 | rig, fakes and measurements |
| `tests/perf/proto/brokers.py` | 265 | the move |
| `tests/perf/proto/child.py` | 499 | the move |
| `tests/perf/proto/fake_session.py` | 88 | rig, fakes and measurements |
| `tests/perf/proto/measure.py` | 555 | rig, fakes and measurements |
| `tests/perf/proto/parent.py` | 648 | the move |
| `tests/perf/proto/proxies.py` | 347 | the move |
| `tests/perf/proto/rig.py` | 365 | rig, fakes and measurements |
| `tests/perf/proto/run_shell.py` | 49 | rig, fakes and measurements |
| `tests/perf/proto/wire.py` | 116 | the move |
| **the move** | **1875** | wire, child, parent, brokers, proxies |
| **the harness** | **1057** | not part of a product |

Product files (`src/`) changed by the prototype: none. The prototype patches `ModuleHost._import` at run time (`tests/perf/proto/parent.py: install`) and reads its switches only in `tests/perf/proto/run_shell.py` and `parent.py`. Outside `tests/perf` and the smoke test, `pyproject.toml` (a long-line exemption for the report's markdown) and `CHANGELOG.md` are edited. A real move would change the shell by about the lines of **the move** (the launcher with its stub and watchdog, the child, the broker and the proxies), plus the hooks it needs in `ModuleHost` (an asynchronous `load` and `start`, a reply path for `call_action`, `Event.stop`). The module host's own code (`load`, `check_calls`, `dispatch`, `start`, `sync`, `_replace`, the back-off) ran unchanged on the stub.

| `ctx` member | In A | In the prototype | Needed a different design? |
|---|---|---|---|
| `name`, `uid`, `config`, `uses` | plain data in the shell | sent once at start; every change of `ctx.uses` is mirrored in order | no (data) |
| `log` | loguru in the shell | loguru in the process; each record is one line to the shell, which logs it under `module:<name>` | no |
| `send` | `ValueStore.send` on any thread, coalesced per use and key, one flush per loop turn | one JSON line (queued, a writer thread joins them); the shell's reader thread calls the same `ValueStore.send`, so coalescing and the one `call_soon` flush are unchanged | no (a hop and an encode) |
| `on_tick` | the shell's one time source | each process that subscribes has its own time-source thread (a Clock wakes its own process) | yes: either one wake-up per ticking process, or the shell sends tick messages |
| `call_soon` | the shell's loop thread | the module process's own loop (its main thread) | yes: "the loop" is now the module's |
| `popup`, `close_popup` | loop thread, no result | a message; the shell opens it on its loop | no |
| `update_popup`, `is_popup_open` | loop thread, return a bool at once | a request that waits for the shell (read: any thread; update: the shell's loop) | yes: a synchronous answer across a pipe, 5 s timeout |
| `surface` (`hide`, `focus`, `on_shown`), `announce` | loop thread, bool results | messages and requests; `on_shown` pushes | yes: as above |
| `apps` | memory reads of the shell's index | requests (`search`, `get`, `ready`); the index stays in the shell | yes: a round trip per `search` |
| `icons` | files read, pixels registered with the engine | requests; only the text references come back; pixmap and png bytes go as base64 | yes: the registry is the engine's, so B2-style by necessity |
| `windows` | loop-thread list, `activate` and so on return futures | the shell pushes a copy of the list on each change; the actions return futures completed by the reply | yes: a pushed snapshot |
| `dbus` | one `Layer` and one service thread for all modules | B1: a `Layer` and service thread in each process that uses it; B2: proxies, `get` and `call` are awaited coroutines on a proxy thread, the shell runs them on its layer and pushes the subscriptions' callbacks | B1 no; B2 yes (`Bus.run(coro)` runs in the process) |
| `audio` | one `AudioService` (one connection) | B1: one PulseAudio connection per process that uses it (Audio and Audio_Outputs are two files, so two); B2: the shell's connection, pushed state and futures | B1 no; B2 yes |
| `tray` | one `TrayService`, one host name | B1: the process owns a host name of its own; B2: the shell's | B1 no; B2 yes |
| `Module` hooks (`start`, `stop`, `reload`, `use_added`, ...) | direct calls on the loop | `start` (first time only) and `stop` wait for the process; the rest are messages | yes: `start()` of a restart or a reload no longer blocks the loop |

## How the lead runs the full measurement

On an idle machine: nothing the user started, no build, no CI job, no browser or agent doing work, 1-minute load average at or below 0.5 (the harness refuses otherwise). From the repository root (the worktree with this branch), with the project's own environment:

```
unset VIRTUAL_ENV; export UV_PROJECT_ENVIRONMENT=$HOME/Projects/pyDev/pyEnvs/tess-shell-m7a2
env -u WAYLAND_DISPLAY -u DISPLAY uv run --no-sync python tests/perf/module_process_test.py
```

Expected duration about 80 minutes (start: 7 cells of 20 runs; idle: 7 cells of 3 times 75 s; latency: 5 cells of 3 times about 70 s; containment: 5 cells of 3 times about 45 s). It writes this file and `module-process-results.json`. Do not touch the machine while it runs; the headless sway and the fakes are private and are removed at the end (also on failure; a killed run leaves `tmp-proc-*` folders and processes whose environment names the private runtime directory).

### The product only (cell P, A as the baseline)

P is the shell as built: posture C, a process per user module, nothing patched. This runs A and P on the default shell, on the shell with three user modules, and with the latency probe and the containment victim, and writes a report of its own:

```
unset VIRTUAL_ENV; export UV_PROJECT_ENVIRONMENT=$HOME/Projects/pyDev/pyEnvs/tess-shell-pc
env -u WAYLAND_DISPLAY -u DISPLAY uv run --no-sync python tests/perf/module_process_test.py --postures=A,P --out=tests/perf/module-process-results-product.md
```

Expected duration about 23 minutes (start 2.0, idle 14.3, latency 4.5, containment 2.3 minutes).

### The lean B only (A as the baseline)

The first full measurement already has A, B and C; the lean B needs only A beside it. This runs A, L1 and L2 (the default shell only: no user modules) and writes a report of its own, so the report of the full run stays as it is. Three repetitions of start and idle, which carry the memory and the wake-ups, and fewer of latency and containment, which the rows pass by a wide margin or fail outright:

```
unset VIRTUAL_ENV; export UV_PROJECT_ENVIRONMENT=$HOME/Projects/pyDev/pyEnvs/tess-shell-lean
env -u WAYLAND_DISPLAY -u DISPLAY uv run --no-sync python tests/perf/module_process_test.py --postures=A,L1,L2 --reps=3 --latency-reps=1 --contain-reps=2 --start-runs=15 --out=tests/perf/module-process-results-lean.md
```

With the rule `validate` (the module files whose only Python is a `validate_use` check and literal constants stay in the shell too; see the section on the lean B for the counts of each rule), the same run and its own report file:

```
env -u WAYLAND_DISPLAY -u DISPLAY uv run --no-sync python tests/perf/module_process_test.py --postures=A,L1,L2 --reps=3 --latency-reps=1 --contain-reps=2 --start-runs=15 --lean-rule=validate --out=tests/perf/module-process-results-lean-validate.md
```

Expected duration about 16 minutes (an estimate from the step times measured on this machine: start 1.1, idle 10.7, latency 2.2, containment 2.3 minutes). The same cells with three repetitions of everything take about 22 minutes. Adding L1 and L2 to the full run (`--postures=A,B1,B2,C1,C2,L1,L2`) adds about 15 minutes to it.
