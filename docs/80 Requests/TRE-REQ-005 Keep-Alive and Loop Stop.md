---
title: TRE-REQ-005 Keep-Alive and Loop Stop
aliases: [TRE-REQ-005, tre Keep-Alive Request, LoopHandle stop]
type: engine-request
status: stable
owner: phil
created: 2026-10-26
updated: 2026-10-27
tags: [engine-request, integration/wayland, needs-verification]
---

# TRE-REQ-005: Keep-alive and Loop Stop

> [!NOTE]
> Add to tre an opt-in keep-alive, so `App.run()` can stay alive with zero windows and keep delivering output events and `call_soon` callbacks, and a way to end the loop from outside: a `LoopHandle` stop. Today the loop ends only when every window has closed, and `run()` refuses to start with none. A desktop shell must stay up with no windows when every monitor is configured to show nothing or the last output is unplugged, and must shut down cleanly on quit.

> [!TIP]
> **Taken up by tre (2026-10-26)**
> The maintainer approved the work and `tre` is building it as [tre #238](https://github.com/mindderivative/tre/issues/238), with the corner pass-through as [#236](https://github.com/mindderivative/tre/issues/236). `tre` reviewed this request, found it accurate and added four points, recorded below.

> [!TIP]
> **Released in tre 0.5.9 (2026-10-27)**
> `tesserae-engine` 0.5.9 is on PyPI (uploaded 2026-10-27, checked) and its migration notes list `App.run(keep_alive=True)` and `LoopHandle.stop()` (#238), with `hit_shape` (#236) in the same release ([migration notes](https://mindderivative.github.io/tre/migrating-0.5/), `docs/reference/app.md` section "Staying up with no window"). `keep_alive` keeps the loop running with nothing open (output events and `call_soon` still arrive, and windows can be added from them); `stop()` ends any loop from a thread and closes every window without a `close_requested`, reason `"stopped"`. Without `keep_alive` nothing changes. The behaviour described below is what shipped, per tre's release notes; I have not run it. tre lists what it did not check on real hardware: a second GPU, non-AMD GPUs, a 4K frame with many joins, output hot-plug on KWin with a real monitor unplug, Windows and macOS.

> [!NOTE]
> **Was blocking one shell behaviour**
> [Process Model and Threading > No windows: what tre offers](../20%20Architecture/Process%20Model%20and%20Threading.md#no-windows-what-tre-offers) depended on this request. The shell can now stay idle with no windows by using `run(keep_alive=True)` (tre 0.5.9). The stopgap (a 1x1 window) is no longer needed.

This note is carried to the tre project by the maintainer (AGENTS > 6. Requests Between Projects). It is not filed from this vault. The `tre` session was told over the mailbox on 2026-10-26 where to find it.

## Shell Need

| Need                            | Why                                                                                                                                                                                              |
|---------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Run with zero windows           | Every monitor can be set to show none of the shell, or the last output can be unplugged ([V1 Scope > Multi-monitor](../10%20Vision/V1%20Scope.md#multi-monitor)). The shell must not exit; it waits for an output to come back. |
| Output events with zero windows | `output_added`, `output_removed` and `output_updated` must keep arriving, so the shell can create surfaces when a monitor appears.                                                               |
| `call_soon` with zero windows   | Module threads hand values to the loop; the registry and watchers use it too ([Process Model and Threading](../20%20Architecture/Process%20Model%20and%20Threading.md)).                                                                          |
| End the loop from outside       | Quit, signal and "stopping" ([Process Model and Threading > Lifecycle (proposed)](../20%20Architecture/Process%20Model%20and%20Threading.md#lifecycle-proposed)) need to end `run()`. Today the loop ends only when every window closes, which is not possible with zero windows.           |

## Why it Belongs in the Engine

It is event-loop mechanism: when the loop runs and when it ends. The shell cannot decide it from outside: the exit decision is inside tre's platform loop, and the output watch runs on tre's layer thread only while the loop runs. This is mechanism, not meaning (AGENTS > 3. Layering principle).

## What Tre Does Today

Findings from the `tre` session over the mailbox (2026-10-26, from the 0.5.8 source and runs on a headless sway), with the points I checked in the source on the same day at commit `abd71f5`:

| Fact                                                                                                                                                      | Checked in source                                                                                                                                                               |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `App.run()` raises `RuntimeError` with zero registered windows                                                                                            | Yes: `engine-py/src/app.rs:1009` ("App.run() called with no windows -- call add_window() at least once first"); also in [App reference](https://mindderivative.github.io/tre/reference/app/)              |
| The platform loop ends when no window and no layer surface is left                                                                                        | Yes: `engine-platform/src/layer_loop.rs`, `exit_if_empty` (exits when `windows` and `layers` are empty)                                                                         |
| `LoopHandle` has only `call_soon`                                                                                                                         | Yes: `engine-py/src/thread_handle.rs` (one method in the `#[pymethods]` block)                                                                                                  |
| `call_soon` does not run with zero windows (correcting the earlier experiments, which all had a window)                                                   | From `tre`'s review: the queue is drained inside a window's frame callback and the `Wake` event only requests redraws of windows and layers, so a queued callback waits forever |
| **Python signal handlers do not run on an idle loop**                                                                                                     | Measured by `tre`: a `SIGUSR1` handler ran 2 s late, only when a `call_soon` gave the main thread Python work. Ctrl-C and SIGTERM cannot stop an idle shell today               |
| **The loop has eight exit points**, not one                                                                                                               | Five `exit_if_empty` sites in `layer_loop.rs` and three more `event_loop.exit()` sites in `engine-platform/src/lib.rs` (close, close requested, `max_frames`)                   |
| Calling `run()` again after it returned works                                                                                                             | From `tre`'s test run; not checked by me                                                                                                                                        |
| Output events do not fire while `run()` is not active; an output plugged in between runs is not reported as `output_added`                                | From `tre`'s test run; the layer thread runs only inside the loop                                                                                                               |
| A hidden 1x1 `LayerWindow` keeps the loop alive but closes with reason `"output_removed"` when its output is unplugged, and the run ends in the same turn | From `tre`'s test run                                                                                                                                                           |
| An ordinary 1x1 `Window` survived unplugging its output, then the last output, then plugging a new one; events and `call_soon` kept working               | From `tre`'s test run; not tested on KWin; hiding it (`minimize()`) untested                                                                                                    |

## Proposed API

> [!CAUTION]
> **Proposal, not existing API**
> `tre` is building this as #238. The shape below is what `tre` described on 2026-10-26; the names are the tre project's.

```python
app = App()
app.run(keep_alive=True)        # an argument of run(), not of App

handle = app.thread_handle()
ok = handle.stop()              # any thread; returns False outside a running loop
```

Behaviour `tre` is building:

1. `run(keep_alive=True)` belongs to one run. With it set, `run()` does not raise with zero windows, and every exit point is a no-op, so the loop continues until stopped. Without it nothing changes.
2. `call_soon` and `stop()` are drained without a window. The engine gets a window-less drain.
3. **The output watch starts at loop start**, so `output_added`, `output_removed` and `output_updated` arrive with zero windows.
4. `LoopHandle.stop() -> bool` is safe from any thread, with or without `keep_alive`, and applies to a **running loop only**. It returns `False` before or after a run, so a stop queued early cannot end the next run.
5. `stop()` closes every open window unconditionally: `close_requested` is skipped, so a shutdown cannot be vetoed. Each window hears `closed` (reason `"app"` or a new `"stopped"`), then `run()` returns normally.
6. With `keep_alive`, closing the last window does not end the run, including a bar closed with reason `"output_removed"`. The shell can add a `LayerWindow` from an `output_added` handler.
7. **Non-Wayland sessions:** `keep_alive` works (an idle loop, `call_soon`, `stop()`); there are no output events and no error.

**Size.** About 100 to 150 lines of code in `engine-py` and `engine-platform` and about as many in tests, the stub and docs (revised up from 60 to 100 after the eight exit points and the window-less drain were found).

**Open decisions in tre (D1 to D4, #238):** `run(keep_alive=)` against `App(keep_alive=)` (recommended: `run`); `stop()` closing unconditionally (recommended); the `closed` reason for a stop (`"app"` or a new `"stopped"`, recommended); whether to also check signals on `Wake` or leave them to the application's wakeup-fd recipe (recommended: the recipe for now).

### How the Shell Uses it

- **Quit path.** `signal.set_wakeup_fd` on a socketpair, plus a watcher thread that reads it and calls `handle.stop()`. `tre` tested the watcher: it saw SIGTERM at once on an idle loop. The shell's quit path is planned that way ([Process Model and Threading > Lifecycle (proposed)](../20%20Architecture/Process%20Model%20and%20Threading.md#lifecycle-proposed)). If `stop()` returns `False` (the loop is not running yet), the watcher retries until the loop is up or the quit flag is set.
- **Order on quit.** `stop()` closes the windows and `run()` returns; then the shell stops modules, joins their threads and writes the registry, on the same main thread. `closed` with reason `"app"` or `"stopped"` during shutdown must not make the surface manager recreate a window.
- **Hot-plug.** With `keep_alive`, an `output_added` handler adds windows, as in [Data Flow > Monitor hot-plug](../20%20Architecture/Data%20Flow.md#monitor-hot-plug).
- Nothing in these semantics breaks the shell (`tre` asked).

## Alternatives

| Alternative                                        | Verdict                                                                                                                                                        |
|----------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| A hidden 1x1 `LayerWindow`                         | Fails when its output is unplugged: it closes and the run ends ([above](#what-tre-does-today)).                                                   |
| An ordinary 1x1 `Window`                           | Works with zero outputs, but it is a real toplevel: a task-list entry and space on a tiling compositor. Hiding it is untested; untested on KWin. Interim only. |
| Restart `run()` on demand, diffing `App.outputs()` | `run()` can be called again, but output events do not fire between runs, so the shell cannot wake on a hot-plug. Not suitable.                                 |
| The shell runs its own wait loop outside tre       | Same problem: tre's output watch only runs inside `run()`.                                                                                                     |

## If Declined

1. Use the ordinary 1x1 `Window` as a keep-alive, verified on KWin and hidden if possible (`minimize()`), as an interim and not shippable without that check.
2. End the loop by closing every window including the keep-alive window, since no `LoopHandle.stop()` exists.
3. Record the limits in [Process Model and Threading](../20%20Architecture/Process%20Model%20and%20Threading.md) and add a Risk Register entry (visible window; task-list entry).

## Open Questions

- [x] What `stop()` does to open windows: closes them all unconditionally, each hears `closed`, then `run()` returns (`tre`).
- [x] `keep_alive` is an argument of `run()`, not of `App` (`tre`).
- [x] Non-Wayland: `keep_alive` works, with no output events and no error (`tre`).
- [x] The `closed` reason for a stop: `"stopped"`, on ordinary windows too (as built, per `tre`).
- [ ] Idle cost with zero windows: `tre` checks CPU ticks and wake-ups over 5 s ([Process Model and Threading > Performance notes](../20%20Architecture/Process%20Model%20and%20Threading.md#performance-notes)).
- [ ] Whether KWin behaves the same as sway.

## Acceptance Criteria

- [ ] `run(keep_alive=True)` with zero windows does not raise and does not return.
- [ ] With zero windows, plugging and unplugging an output fires `output_added` and `output_removed`; unplugging the last output and plugging a new one still fires.
- [ ] `call_soon` from another thread runs with zero windows (it does not today).
- [ ] A `LayerWindow` added from an `output_added` handler opens, with zero windows before it.
- [ ] The wakeup-fd recipe ends an idle zero-window loop on SIGTERM (a test and a docs example).
- [ ] `handle.stop()` from another thread ends `run()`, with and without windows open, and returns `False` outside a run.
- [ ] Idle cost with zero windows: no frames and no wake-ups beyond events; CPU ticks over 5 s at 0 on sway and KWin.
- [ ] Without `keep_alive`, `run()` still raises with zero windows and ends when the last window closes.
- [ ] Tested on a headless sway and on KWin.

## Links

- [Process Model and Threading](../20%20Architecture/Process%20Model%20and%20Threading.md) · [ADR-0003 Process Model](../30%20Decisions/ADR-0003%20Process%20Model.md) · [TRE-REQ-001 Layer Surface Window](TRE-REQ-001%20Layer%20Surface%20Window.md) · [80 Requests](80%20Requests.md)
- [tre App reference](https://mindderivative.github.io/tre/reference/app/) · [Outputs](https://mindderivative.github.io/tre/reference/outputs/) · [Threading](https://mindderivative.github.io/tre/guide/threading/)
