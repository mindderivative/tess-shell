---
title: ADR-0009 D-Bus Client Library
aliases: [ADR-0009, dbus-fast Decision]
type: adr
status: accepted
owner: phil
created: 2026-10-26
updated: 2026-10-26
tags: [adr, integration/dbus, needs-verification]
related: ["[[D-Bus Libraries for Python]]", "[[Process Model and Threading]]", "[[System Context]]", "[[ADR-0003 Process Model]]"]
depends_on: ["[[ADR-0003 Process Model]]"]
---

# ADR-0009: D-Bus Client Library

> [!summary]
> The shell uses `dbus-fast` for D-Bus, on one asyncio service thread that the shell provides and shares among modules. `jeepney` is the fallback. Modules may still import other libraries.

## Context

The shell and its modules read properties, watch signals and call methods on the session and system buses (UPower, NetworkManager, MPRIS, KWin, the tray, global shortcuts). Blocking work never runs on the loop thread ([[ADR-0003 Process Model]]). [[D-Bus Libraries for Python]] compares the options with data from PyPI and GitHub (2026-10-26).

## Options

### Option A — `dbus-fast` on a Shared Asyncio Service Thread (Chosen)

- **For:** MIT, no dependencies, pure Python with an optional Cython extension, release 5.2.0 on 2026-10-02, classifiers for Python 3.13 to 3.15, proxy objects, signals, and `bus.export` plus name requests for later services. One thread and one connection per bus for all modules.
- **Against:** a slow callback on the service thread delays every D-Bus module. Binary wheels add a packaging concern (the pure-Python build is the escape hatch).

### Option B — `jeepney` in Module Threads

- **For:** pure Python, no hidden loop, explicit.
- **Against:** low-level, so more code per module; one connection per module. Last release 2025-02-27.

### Option C — Sd-bus (`sdbus`) or a GLib-based Library

- **Against:** a system library at build time, or a second event loop beside tre's.

## Decision

Accepted 2026-10-26 by the maintainer in chat ("as recommended"): **Option A**.

- The shell uses `dbus-fast`.
- The shell provides one shared asyncio service thread that holds the session and system bus connections, and a helper for modules (name not decided; `ctx.dbus` in the survey). A subscription callback runs on the service thread and calls the module's send entry point, which crosses to the loop with `call_soon`.
- `jeepney` is the fallback if the Cython wheels or the helper cause trouble.
- A module may import any other library it prefers.

## Consequences

- The service thread joins the thread inventory ([[Process Model and Threading#Threads]]).
- The module contract says callbacks on the service thread are short and never block; exceptions are caught and logged with the module's name ([[Logging with Loguru]]).
- A spike checks, on Python 3.14: UPower's battery percentage, a `PropertiesChanged` signal, KWin's `/VirtualDesktopManager`, and the idle cost. #needs-verification until it runs.
- The PipeWire access path is a separate survey ([[D-Bus Libraries for Python#Open]]).
- The helper's name and shape belong to `42 Python API/`.

## Update 2026-10-28

Exporting an object and requesting a bus name, listed above as later work, is v1 work, because [[ADR-0013 Control Interface]] was accepted 2026-10-28: the shell exports its own interface for the command line and the KWin script ([[IPC and CLI]]).

## Links

- [[D-Bus Libraries for Python]] · [[Process Model and Threading]] · [[System Context]]
