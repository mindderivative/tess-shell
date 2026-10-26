---
title: TRE-REQ-005 Keep-Alive and Loop Stop
aliases: [TRE-REQ-005, tre Keep-Alive Request, LoopHandle stop]
type: engine-request
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-26
tags: [engine-request, integration/wayland, needs-verification]
related: ["[[Process Model and Threading]]", "[[ADR-0003 Process Model]]", "[[TRE-REQ-001 Layer Surface Window]]", "[[80 Engine Requests]]"]
depends_on: []
---

# TRE-REQ-005: Keep-alive and loop stop

> [!summary]
> Add to tre an opt-in keep-alive, so `App.run()` can stay alive with zero windows and keep delivering output events and `call_soon` callbacks, and a way to end the loop from outside: a `LoopHandle` stop. Today the loop ends only when every window has closed, and `run()` refuses to start with none. A desktop shell must stay up with no windows when every monitor is configured to show nothing or the last output is unplugged, and must shut down cleanly on quit.

> [!warning] Blocks one shell behaviour
> [[Process Model and Threading#No windows: what tre offers]] depends on this request. The shell's decision is "stay idle with no windows" (maintainer, 2026-10-26). Option A there (this request) was chosen; the maintainer follows up with tre to confirm. A stopgap exists (see [If declined](#if-declined)).

This note is carried to the tre project by the maintainer ([[AGENTS#6. Engine requests (tre / Tesserae)]]). It is not filed from this vault. The `tre` session was told over the mailbox on 2026-10-26 where to find it.

## Shell need

| Need | Why |
|---|---|
| Run with zero windows | Every monitor can be set to show none of the shell, or the last output can be unplugged ([[V1 Scope#Multi-monitor]]). The shell must not exit; it waits for an output to come back. |
| Output events with zero windows | `output_added`, `output_removed` and `output_updated` must keep arriving, so the shell can create surfaces when a monitor appears. |
| `call_soon` with zero windows | Module threads hand values to the loop; the registry and watchers use it too ([[Process Model and Threading]]). |
| End the loop from outside | Quit, signal and "stopping" ([[Process Model and Threading#Lifecycle (proposed)]]) need to end `run()`. Today the loop ends only when every window closes, which is not possible with zero windows. |

## Why it belongs in the engine

It is event-loop mechanism: when the loop runs and when it ends. The shell cannot decide it from outside: the exit decision is inside tre's platform loop, and the output watch runs on tre's layer thread only while the loop runs. This is mechanism, not meaning ([[AGENTS#3. Layering principle]]).

## What tre does today

Findings from the `tre` session over the mailbox (2026-10-26, from the 0.5.8 source and runs on a headless sway), with the points I checked in the source on the same day at commit `abd71f5`:

| Fact | Checked in source |
|---|---|
| `App.run()` raises `RuntimeError` with zero registered windows | Yes: `engine-py/src/app.rs:1009` ("App.run() called with no windows -- call add_window() at least once first"); also in [App reference](https://mindderivative.github.io/tre/reference/app/) |
| The platform loop ends when no window and no layer surface is left | Yes: `engine-platform/src/layer_loop.rs`, `exit_if_empty` (exits when `windows` and `layers` are empty) |
| `LoopHandle` has only `call_soon` | Yes: `engine-py/src/thread_handle.rs` (one method in the `#[pymethods]` block) |
| Calling `run()` again after it returned works | From `tre`'s test run; not checked by me |
| Output events do not fire while `run()` is not active; an output plugged in between runs is not reported as `output_added` | From `tre`'s test run; the layer thread runs only inside the loop |
| A hidden 1x1 `LayerWindow` keeps the loop alive but closes with reason `"output_removed"` when its output is unplugged, and the run ends in the same turn | From `tre`'s test run |
| An ordinary 1x1 `Window` survived unplugging its output, then the last output, then plugging a new one; events and `call_soon` kept working | From `tre`'s test run; not tested on KWin; hiding it (`minimize()`) untested |

## Proposed API

> [!danger] Proposal, not existing API
> `tre` suggested the shape. Names are the tre project's to choose.

```python
app = App()
app.add_window(...)             # optional: zero windows is allowed with keep_alive
app.run(keep_alive=True)        # or App(keep_alive=True)

handle = app.thread_handle()
handle.stop()                   # any thread; asks the loop to end
```

Behaviour:

1. **`keep_alive`** is opt-in. With it set, `run()` does not raise with zero windows, and `exit_if_empty` does nothing, so the loop continues until stopped.
2. **The output watch starts at loop start** (it already starts when output listeners exist) so `output_added`, `output_removed` and `output_updated` arrive with zero windows.
3. **`call_soon`** callbacks run with zero windows.
4. **`LoopHandle.stop()`** is safe from any thread and asks the loop to end. It works with or without `keep_alive`. What happens to open windows (closed with a `closed` reason, or `close_requested` first) is a tre design question.
5. Without `keep_alive`, behaviour is unchanged.

`tre`'s rough size: about 60 to 100 lines in `engine-py` and `engine-platform`, plus tests and docs; low risk because it is opt-in. The one design question is how the loop is stopped.

## Alternatives

| Alternative | Verdict |
|---|---|
| A hidden 1x1 `LayerWindow` | Fails when its output is unplugged: it closes and the run ends ([above](#what-tre-does-today)). |
| An ordinary 1x1 `Window` | Works with zero outputs, but it is a real toplevel: a task-list entry and space on a tiling compositor. Hiding it is untested; untested on KWin. Interim only. |
| Restart `run()` on demand, diffing `App.outputs()` | `run()` can be called again, but output events do not fire between runs, so the shell cannot wake on a hot-plug. Not suitable. |
| The shell runs its own wait loop outside tre | Same problem: tre's output watch only runs inside `run()`. |

## If declined

1. Use the ordinary 1x1 `Window` as a keep-alive, verified on KWin and hidden if possible (`minimize()`), as an interim and not shippable without that check.
2. End the loop by closing every window including the keep-alive window, since no `LoopHandle.stop()` exists.
3. Record the limits in [[Process Model and Threading]] and add a Risk Register entry (visible window; task-list entry).

## Open questions

- [ ] What `stop()` does to open windows (close them with a reason, or require none).
- [ ] Whether `keep_alive` is an `App` option or a `run()` argument.
- [ ] Whether the keep-alive loop wakes only for events and `call_soon` (idle cost): the shell requires zero idle frames and no timers ([[Process Model and Threading#Performance notes]]).
- [ ] Behaviour on a non-Wayland session, where there are no outputs to watch.
- [ ] Whether KWin behaves the same as sway.

## Acceptance criteria

- [ ] `run(keep_alive=True)` with zero windows does not raise and does not return.
- [ ] With zero windows, plugging and unplugging an output fires `output_added` and `output_removed`; unplugging the last output and plugging a new one still fires.
- [ ] `call_soon` from another thread runs with zero windows.
- [ ] `handle.stop()` from another thread ends `run()`, with and without windows open.
- [ ] Idle cost with zero windows: no frames, no wake-ups beyond events.
- [ ] Without `keep_alive`, `run()` still raises with zero windows and ends when the last window closes.
- [ ] Tested on a headless sway and on KWin.

## Links

- [[Process Model and Threading]] · [[ADR-0003 Process Model]] · [[TRE-REQ-001 Layer Surface Window]] · [[80 Engine Requests]]
- [tre App reference](https://mindderivative.github.io/tre/reference/app/) · [Outputs](https://mindderivative.github.io/tre/reference/outputs/) · [Threading](https://mindderivative.github.io/tre/guide/threading/)
