---
title: ADR-0003 Process Model
aliases: [ADR-0003, Single Process Model]
type: adr
status: accepted
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [adr, architecture]
related: ["[[V1 Scope]]", "[[ADR-0006 Shell Independent of Tesserae UI]]", "[[ADR-0001 Shell Surface Strategy]]"]
depends_on: []
---

# ADR-0003: Process model

> [!summary]
> One process owns every surface on every monitor and runs one tre event loop. Background work runs on other threads and hands results to the loop with `LoopHandle.call_soon`.

## Context

tre runs on one thread, the one that created the `App`; every window, event handler and Python callback runs there once `App.run()` starts. Any thread may use `App.thread_handle()` and `call_soon(fn)` to queue work on the loop ([tre threading guide](https://mindderivative.github.io/tre/guide/threading/)). One `App` can hold many windows, including layer windows on several outputs ([Outputs](https://mindderivative.github.io/tre/reference/outputs/)). [[AGENTS#3. Layering principle]] already fixes that Python never runs in layout or paint.

## Options

### Option A — One process, one event loop (chosen)

- **For:** one configuration, one theme, one set of services shared by all surfaces; hot reload and monitor hot-plug act in one place; the cost of tre's GPU device per window is the only duplication.
- **Against:** a hang or crash in one module stops every surface. Python modules share one GIL, so a slow module delays frames for all monitors.

### Option B — One process per surface or per monitor

- **For:** a failure stays inside one surface.
- **Against:** shared state (theme, services, config) needs inter-process messaging; every process pays its own runtime and GPU memory; a bar and its popups must cooperate across processes.

## Decision

Accepted 2026-10-25 by the maintainer in chat: **Option A**, one process owning all surfaces and one event loop.

## Consequences

- Every service spec states its thread and how it crosses into the loop ([[AGENTS#3. Layering principle]]). Blocking work (D-Bus, sockets, polling, disk) never runs on the loop thread.
- A module that blocks the loop freezes all surfaces. [[60 Quality]] must define a watchdog and crash recovery (restart the process, restore surfaces from configuration). #tech-debt until written.
- The shell may run under a small supervisor that restarts it. Whether it is part of v1 is open.
- No isolation between user modules ([[Goals and Non-Goals]] N7).

> [!danger] Single point of failure
> One hung Python callback blocks every bar, OSD and widget. Add to [[Risk Register]] when it exists.

## Links

- [[ADR-0006 Shell Independent of Tesserae UI]] · [[V1 Scope#Decisions to take]]
