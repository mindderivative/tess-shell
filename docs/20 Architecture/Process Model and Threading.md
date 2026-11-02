---
title: Process Model and Threading
aliases: [Threading, Event Loop Model]
type: architecture
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-26
tags: [architecture, needs-verification]
related: ["[[20 Architecture]]", "[[ADR-0003 Process Model]]", "[[Layers and Components]]", "[[Data Flow]]"]
depends_on: ["[[ADR-0003 Process Model]]"]
---

# Process Model and Threading

> [!summary]
> One process, one tre event loop on the main thread ([[ADR-0003 Process Model]]). Everything that touches a window or node, every TEL evaluation and every module callback runs there, between frames. Everything that waits (D-Bus, files, sockets, timers of module work) runs on other threads and hands finished values back with `LoopHandle.call_soon`. Decided: the single process and the thread rule. Proposed in this note: the thread inventory, coalescing, the watchdog and the lifecycle.

## What Tre Guarantees

From the [tre threading guide](https://mindderivative.github.io/tre/guide/threading/) (read 2026-10-25):

- tre runs on the one thread that created the `App`. Its windows, nodes, listeners, animation completions and draw callbacks live and run there once `App.run()` starts.
- `App.thread_handle()` returns a `LoopHandle`, the one tre object any thread may use. `call_soon(fn)` queues `fn` for the loop thread and wakes the loop, even when idle.
- Callbacks run in the order queued, at the top of the next frame, where they can touch windows and nodes as a listener can. One that raises is logged and does not stop the loop or the callbacks after it.
- `window.after(ms, fn)` and `window.every(ms, fn)` run something later on the loop thread; `call_soon` has no delay.
- A `call_soon` callback runs between frames, so it should only apply a finished result.
- `App.run()` raises `RuntimeError` when no window is registered, and ends when every window has closed ([App reference](https://mindderivative.github.io/tre/reference/app/)).

## Threads

| Thread         | Runs                                                                                                                                                                                                                                                                                            | Touches nodes | Crosses into the loop by                                      |
|----------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|---------------|---------------------------------------------------------------|
| Loop (main)    | tre `App.run()`; surface manager; shell model; TEL evaluation; module host calls (`start`, `stop`, `reload`); registry updates                                                                                                                                                                  | Yes           | n/a                                                           |
| Module threads | A module's blocking work: D-Bus, sockets, polling, files, decoding                                                                                                                                                                                                                              | Never         | The shell's send entry point, which uses `call_soon`          |
| Config watcher | Waiting for file changes; reading and parsing a changed file                                                                                                                                                                                                                                    | Never         | `call_soon` with a finished result                            |
| Service thread | An `asyncio` event loop, shared by modules, holding the session and system bus connections (`dbus-fast`, [[ADR-0009 D-Bus Client Library]]); it also receives calls on the shell's own D-Bus interface ([[IPC and CLI#Threading]], [[ADR-0013 Control Interface]]) | Never         | The same send entry point                                     |
| Signal watcher | Reads a socketpair fed by `signal.set_wakeup_fd` and calls `handle.stop()` on SIGTERM or SIGINT                                                                                                                                                                                                 | Never         | `LoopHandle.stop()` ([[TRE-REQ-005 Keep-Alive and Loop Stop]]) |
| Watchdog       | Checks that the loop is still ticking                                                                                                                                                                                                                                                           | Never         | Logs, and asks the supervisor to restart if the loop is stuck |

tre also runs its own threads internally (the layer surface connection, for example). They are tre's concern; the shell sees only the loop thread and its callbacks.

## The Rules

1. **Nothing blocking on the loop.** No D-Bus call, file read, subprocess or network call on the loop thread ([[ADR-0003 Process Model]]).
2. **Only the loop touches nodes.** A thread that wants a change sends a value; it never holds a node.
3. **Only finished data crosses.** A worker reads, parses or decodes; the loop applies.
4. **Python is never in layout or paint** ([[AGENTS#3. Layering principle]]). TEL expressions and module callbacks run in callbacks between frames and are short.
5. **Every module spec states its thread** and how it crosses into the loop ([[AGENTS#3. Layering principle]]).

## Handing a Value to the Loop (Proposed)

A module thread calls the shell's send entry point (the hand-off decided in [[ADR-0007 Shell UI Layer#Module data reaches the view through shell entry points (2026-10-25)]]). The entry point must be safe from any thread. Proposed behaviour:

- **Coalesce.** The entry point writes the value into a pending map keyed by module and key, then queues one `call_soon` flush if none is queued. A module that sends the volume 200 times a second leaves only the latest in the map, and the loop applies it once per turn.
- **Order.** Values from one module keep their order per key. Across keys, the flush applies them together in one turn, so a view never shows half an update.
- **No blocking.** The send never waits for the loop.
- **Conversion** (HEX to RGBA and the like) happens in the flush on the loop, or in the send on the module thread if it is pure; decide in the Python API spec.

```mermaid
sequenceDiagram
    participant M as Module thread
    participant S as Send entry point
    participant L as Loop thread
    participant T as TEL scope
    participant R as tre
    M->>S: send("time", "14:05")
    S->>S: store in pending map
    S->>L: call_soon(flush) if none queued
    L->>S: flush at top of next frame
    L->>T: update names that changed
    T->>L: re-evaluate affected expressions
    L->>R: node.set(text=...)
    R->>R: draw frame
```

## Lifecycle (Proposed)

```mermaid
stateDiagram-v2
    [*] --> Loading: process starts
    Loading --> Running: model built, windows open, modules started
    Loading --> Failed: shell file refused
    Running --> Reloading: file changed
    Reloading --> Running: applied (or old state kept on error)
    Running --> Stopping: quit or signal
    Stopping --> [*]: modules stopped, windows closed, registry written
    Failed --> [*]
```

- **Loading.** Read the config directory, parse, validate, follow imports, check or write the registry, resolve references, read outputs, build the model. Errors stop here with `file:line:column`.
- **Running.** Modules start after the model is built, so a value that arrives before its surface exists is kept in the store.
- **Reloading.** A watcher thread reads and parses a changed file; the loop applies it. A bad file leaves the old state and logs an error ([[Data Flow#Hot reload]]).
- **Stopping.** A quit signal reaches a watcher thread through `signal.set_wakeup_fd`, which calls `LoopHandle.stop()`. `stop()` closes every window without a veto (each hears `closed` with reason `"stopped"`) and `run()` returns. The shell then calls each module's `stop`, joins its threads with a timeout, and writes the registry, on the main thread. Python signal handlers do not run on an idle loop, which is why the wakeup-fd path is used ([[TRE-REQ-005 Keep-Alive and Loop Stop]]). Until that ships, ending the loop means closing every window.
- **No windows: stay idle** (decided 2026-10-26). If every monitor is set to "none", or no output is present, the shell does not exit; it waits and reacts when an output is added ([[Data Flow#Monitor hot-plug]]). What tre can do is in [No windows: what tre offers](#no-windows-what-tre-offers).

## No Windows: what Tre Offers

The `tre` session answered over the mailbox on 2026-10-26, from the 0.5.8 source and runs on a headless sway (information only; no issue filed). A peer's claim is a lead; the first two facts match tre's documentation that `run()` raises with zero windows.

| Finding                          | Detail                                                                                                                                                                                                                                                                                                                                                        |
|----------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| No keep-alive mode               | `App.run()` raises `RuntimeError` with zero registered windows, and the platform loop ends when no window and no layer surface is left                                                                                                                                                                                                                        |
| Re-running works, but not asleep | Calling `run()` again after it returned works. Output events do not fire while `run()` is not active, and an output plugged in between runs is not reported as `output_added`; it is just the starting state. A restart-on-demand design must diff `App.outputs()` (works any time) against what it knew                                                      |
| A hidden layer surface fails     | A 1x1 `LayerWindow` (background layer, no anchor, input region `[]`, keyboard none) keeps the loop alive, but it is bound to an output. When that output is unplugged it closes with reason `output_removed` and the run ends in the same turn, even if a listener adds a new one. It fails exactly when the last or current output is removed                |
| A 1x1 ordinary window survives   | An ordinary toplevel `Window(width=1, height=1)` survived unplugging its output, then the last output, then plugging a new one: output events and `call_soon` kept working with zero outputs. Cost: it is a visible 1x1 toplevel (a task-list entry, space on a tiling compositor). Hiding it (`Window.minimize()`) is untested; not tested on KWin           |
| Suggested engine addition        | An opt-in keep-alive, for example `App.run(keep_alive=True)`: no error with zero windows, no exit when empty, output watch started at loop start. It needs a way to end the loop. A `LoopHandle` stop does not exist today; the loop ends only when every window closes. Rough size: about 60 to 100 lines plus tests and docs, low risk because it is opt-in |

> [!warning] Blocked by [[TRE-REQ-005 Keep-Alive and Loop Stop]]
> Option A was chosen by the maintainer on 2026-10-26: the opt-in keep-alive and a `LoopHandle` stop. `tre` released it in 0.5.9 on 2026-10-27 as `App.run(keep_alive=True)` and `LoopHandle.stop()` ([[TRE-REQ-005 Keep-Alive and Loop Stop]]). The stopgap B is no longer needed.

Options for the shell:

| Option                                                       | Description                                              | Verdict                                          |
|--------------------------------------------------------------|----------------------------------------------------------|--------------------------------------------------|
| A. Ask tre for the opt-in keep-alive and a `LoopHandle` stop | The clean answer; the stop is needed for shutdown anyway | **Recommended.** Small, opt-in, low risk         |
| B. A hidden 1x1 ordinary window as a stopgap                 | Worked today (not on KWin)                               | No longer needed: option A shipped in tre 0.5.9  |
| C. Restart on demand, diffing `App.outputs()`                | Cannot wake on a hot-plug                                | Not suitable for "react when an output is added" |

The shell also needs a clean way to **end the loop** on quit. Today that means closing every window, which is not possible with zero windows. A `LoopHandle` stop would cover both ([[Process Model and Threading#Lifecycle (proposed)]]).

## Failure and Recovery

| Failure                                  | Effect                                                          | Handling (proposed)                                                                                    |
|------------------------------------------|-----------------------------------------------------------------|--------------------------------------------------------------------------------------------------------|
| A module raises in `start` or a callback | That module is marked failed                                    | Log with the module name and UID; surfaces keep their last values or fall back; other modules continue |
| A module thread dies                     | No more values from it                                          | The module host sees no heartbeat or a thread helper reports the exception; log; optional restart      |
| A module blocks the loop                 | Every surface freezes ([[ADR-0003 Process Model#Consequences]]) | Watchdog sees no ticks; logs the stall; with a supervisor, restart the process                         |
| Wayland connection lost                  | tre windows close                                               | Process exits; supervisor restarts it                                                                  |
| A bad shell file on reload               | New state refused                                               | Keep the old state; log an error with position                                                         |
| A bad module `.py` on reload             | New code refused                                                | Keep the old instance running; log the error ([[ADR-0007 Shell UI Layer#Events and module reload (2026-10-26)]])                 |

The loop cannot interrupt itself, so detecting a blocked loop needs a separate watchdog thread that reads a counter the loop bumps from a timer (`window.every`). A supervisor outside the process is the only way to recover from a hard hang. Both are proposals; [[60 Quality]] owns the final design.

> [!danger] Single point of failure
> One hung Python callback blocks every surface ([[ADR-0003 Process Model]]). The mitigation is conventions (rule 1), tooling (the send entry point, thread helpers), a watchdog and a supervisor. None of those is built.

## Performance Notes

- A frame at 60 Hz is about 16.7 ms. `call_soon` callbacks and TEL evaluations share that time with layout and paint. Budgets are set in [[60 Quality]].
- tre documents that an idle surface draws no frames and wakes the loop only for its own timers ([[TRE-REQ-001 Layer Surface Window]]). On the unreleased keep-alive branch, `tre` measured 0.01 s of CPU in 5 s with zero windows, and reports one wake source it does not control: the D-Bus library's worker, about 2 wake-ups a second, behind the OS-preference watcher every tre app has. The shell's own D-Bus service thread ([[ADR-0009 D-Bus Client Library]]) adds its own idle cost, so the idle goal ([[Goals and Non-Goals]] G4) should be measured with the service thread running. #needs-verification The shell must not add a timer that wakes the loop without a reason: a clock updates once a second, not every frame.
- The shared GIL means a CPU-heavy module thread slows the loop. Heavy work belongs in a subprocess or native code; the module contract says so ([[42 Python API]], to write).

## Open Questions

- [ ] **Module threads: who owns them?** Options. **A.** Each module starts and owns its threads; the shell gives a helper that catches and logs thread exceptions (flexible, simple contract; recommended). **B.** The shell runs a shared `asyncio` thread for services and modules are coroutines (less thread code, forces async on module authors). **C.** A shell thread pool for module work. Recommendation A, with B available as an optional shared service thread for D-Bus.
- [x] **D-Bus client library.** `dbus-fast` on a shared asyncio service thread, `jeepney` as the fallback (maintainer, 2026-10-26, [[ADR-0009 D-Bus Client Library]]).
- [ ] **Registry I/O and the UID write** on the loop or a single writer thread ([[ADR-0007 Shell UI Layer#Open items]]). Proposed in [[Config Discovery and Registry#The registry file]]: one writer thread, one write per 500 ms.
- [ ] **Supervisor** in v1 or later.
- [x] **No windows** policy: stay idle (maintainer, 2026-10-26).
- [x] **No windows mechanism.** Option A, chosen 2026-10-26 and released in tre 0.5.9 on 2026-10-27: `App.run(keep_alive=True)` and `LoopHandle.stop()` ([[TRE-REQ-005 Keep-Alive and Loop Stop]]). The shell requires tre 0.5.9 or later.
- [ ] **Where conversions run** (send or flush).

## Links

- [[20 Architecture]] · [[ADR-0003 Process Model]] · [[Layers and Components]] · [[Data Flow]] · [[System Context]]
