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

# ADR-0004: Coexistence with Plasmashell

> [!summary]
> Tesserae Shell coexists with plasmashell by default: it does not take a D-Bus name or a role that plasmashell holds. A service may replace plasmashell's role only after its own ADR.

## Context

Tesserae Shell runs beside an installed Plasma session and does not replace it ([[AGENTS#1. What Tesserae Shell is]]). Some D-Bus names and roles can belong to only one process (the notification server, StatusNotifierWatcher). Which names plasmashell holds on a running session has not been checked. Observed on the maintainer's session on 2026-10-26 (plasmashell 6.8.1, KWin 6.8.1; `busctl --user list`): plasmashell holds `org.freedesktop.Notifications` and `org.kde.JobViewServer`; `kded6` holds `org.kde.StatusNotifierWatcher`, with plasmashell registered as one host; `kwin_wayland` holds `org.kde.kglobalaccel`. Full table: [[System Context#Observed D-Bus names]]. #needs-verification on other distributions.

## Options

### Option A — Coexist by Default; Replace per Service with an ADR (Chosen)

For each service, the spec records one of three modes: **coexist** (use the service as a client or second host), **proxy** (forward to plasmashell's), or **replace** (own the name). Replace needs its own ADR.

- **For:** the Plasma session keeps working whatever the shell does; stopping the shell restores nothing because nothing was taken.
- **Against:** a feature that needs ownership (a notification centre) cannot ship until its ADR exists.

### Option B — Replace Plasmashell's Services Wholesale

- **Against:** needs plasmashell stopped or its names displaced, which breaks the "supplement, not replace" rule. Rejected.

## Decision

Accepted 2026-10-25 by the maintainer in chat ("as recommended"): **Option A**.

## Consequences

- Every integration spec under `40 Specifications/Integration/` has a coexistence row: owner of the name today, mode chosen, and what happens when the shell starts before or after plasmashell.
- The notification centre is outside v1 ([[V1 Scope#After v1]]).
- The tray module acts as a client of the tray protocol and does not own StatusNotifierWatcher unless a later ADR says so. On the observed session the watcher belongs to `kded6`, not plasmashell, so a second host can register beside plasmashell's. #needs-verification on other distributions.
- Starting and stopping the shell must leave the Plasma session usable ([[Goals and Non-Goals]] G3).

## Links

- [[ADR-0003 Process Model]] · [[V1 Scope#Decisions to take]]
