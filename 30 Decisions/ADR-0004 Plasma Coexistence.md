---
title: ADR-0004 Plasma Coexistence
aliases: [ADR-0004, Plasmashell Coexistence]
type: adr
status: accepted
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [adr, integration/dbus, needs-verification]
related: ["[[V1 Scope]]", "[[ADR-0003 Process Model]]"]
depends_on: []
---

# ADR-0004: Coexistence with plasmashell

> [!summary]
> Tesserae Shell coexists with plasmashell by default: it does not take a D-Bus name or a role that plasmashell holds. A service may replace plasmashell's role only after its own ADR.

## Context

Tesserae Shell runs beside an installed Plasma session and does not replace it ([[AGENTS#1. What Tesserae Shell is]]). Some D-Bus names and roles can belong to only one process (the notification server, StatusNotifierWatcher). Which names plasmashell holds on a running session has not been checked. #needs-verification: list the owned names on a live Plasma 6 session (for example with `busctl --user list`) before the first service spec.

## Options

### Option A — Coexist by default; replace per service with an ADR (chosen)

For each service, the spec records one of three modes: **coexist** (use the service as a client or second host), **proxy** (forward to plasmashell's), or **replace** (own the name). Replace needs its own ADR.

- **For:** the Plasma session keeps working whatever the shell does; stopping the shell restores nothing because nothing was taken.
- **Against:** a feature that needs ownership (a notification centre) cannot ship until its ADR exists.

### Option B — Replace plasmashell's services wholesale

- **Against:** needs plasmashell stopped or its names displaced, which breaks the "supplement, not replace" rule. Rejected.

## Decision

Accepted 2026-10-25 by the maintainer in chat ("as recommended"): **Option A**.

## Consequences

- Every integration spec under `40 Specifications/Integration/` has a coexistence row: owner of the name today, mode chosen, and what happens when the shell starts before or after plasmashell.
- The notification centre is outside v1 ([[V1 Scope#After v1]]).
- The tray module acts as a client of the tray protocol and does not own StatusNotifierWatcher unless a later ADR says so. #needs-verification.
- Starting and stopping the shell must leave the Plasma session usable ([[Goals and Non-Goals]] G3).

## Links

- [[ADR-0003 Process Model]] · [[V1 Scope#Decisions to take]]
