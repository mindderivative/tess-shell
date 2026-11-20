---
title: TRE-REQ-011 Drain call_soon at Loop Start
aliases: [TRE-REQ-011, call_soon before run]
type: engine-request
status: review
owner: phil
created: 2026-11-03
updated: 2026-11-19
tags: [engine-request, design, needs-verification]
---

# TRE-REQ-011: Drain call_soon at Loop Start

> [!NOTE]
> **On 2026-11-19 the maintainer said tre is building this for 0.6.10. Built by tre (2026-11-19, PR #311, merged to main, unreleased, ships in 0.6.10): with no window the loop is now woken once at start, so callbacks queued before `App.run` run when the loop starts, in queue order. Reproduced first on 0.6.9 (ran at 1.0 s); after the fix 0.006 s. A `stop()` before `run()` still queues nothing. Not verified on macOS or Windows. The shell's 50 ms retry of `stop()` can go once it runs on 0.6.10.**
> A callback queued with `LoopHandle.call_soon` before `App.run()` starts is not run when the loop starts; it waits until something else wakes the loop. Reported by the `tess-shell` code session while building M0 and checked by the vault session on 2026-11-03. Draft for the maintainer to carry to the tre project; nothing is filed from this vault (AGENTS > 6. Requests Between Projects).

> [!TIP]
> **Not blocking**
> The shell works around it: its signal handling retries `stop()` every 50 ms after a stop request, so a signal that arrives before the loop starts still stops it.

## Shell Need

The shell installs its signal handling and may queue work before `App.run(keep_alive=True)` is called, for example a stop request from a signal that arrives during start. A queued callback must run once the loop is running, without the shell having to wake the loop by another route.

## What tre Does Today

Tested on `tesserae-engine` 0.6.0 (`tess_re`), Python 3.14, on the maintainer's machine under a Wayland session, no windows:

1. `h = app.thread_handle()`; `h.call_soon(f)` before `app.run(keep_alive=True)`.
2. A second thread calls `h.call_soon(g)` 1.0 s after the run starts and `h.stop()` 0.3 s later.
3. Result: `f` ran at 1.001 s, the same moment as `g`, not at the start of the run. The loop did not run `f` until another call woke it.

The `tess-shell` session reports the same on 0.6.0 and 0.6.1 with `keep_alive` and no windows (re-checked on 0.6.1 on 2026-11-04).

## Why it Belongs in the Engine

Whether a queue is drained at loop start is a property of the loop, which only tre owns. A caller cannot know whether the loop has started, so it cannot reliably wake it.

## Proposed Change

When `App.run()` starts its loop (including with `keep_alive` and no windows), drain the `call_soon` queue once before it waits for events. No API change.

## Alternatives

| Option | Against |
|---|---|
| The shell retries or wakes the loop itself (today) | A timer or extra thread for something the loop should do |
| A documented rule that `call_soon` is valid only after the loop starts | The shell would need a loop-started signal to know when |

## If Declined

The shell keeps the 50 ms stop retry ([Shell Start and Stop](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md)).

## Open Questions

1. [ ] Should the request present this as a bug in tre or as a change to documented behaviour? Context: a callback queued with `call_soon` before `run()` waits until something else wakes the loop; the shell works around it with a 50 ms stop retry. Recommendation: present it as a bug, with the fix "drain the queue once at loop start" and no API change, and let tre reclassify it.

## Questions After Testing

1. [ ] Does the same hold with windows open and without `keep_alive`? Context: tested only with `keep_alive` and no windows. Recommendation: run the repro with one open window before sending, and widen the request if it also fails. Answered by: the repro run with a window open and no `keep_alive`.

## Acceptance Criteria

- [ ] A callback queued before `run()` runs within one loop turn of the start, with no other wake-up.

## Links

- [80 Requests](80%20Requests.md) · [Shell Start and Stop](../40%20Specifications/Runtime/Shell%20Start%20and%20Stop.md) · [M0 Brief](../00%20Home/M0%20Brief.md) · [TRE-REQ-005 Keep-Alive and Loop Stop](TRE-REQ-005%20Keep-Alive%20and%20Loop%20Stop.md)
