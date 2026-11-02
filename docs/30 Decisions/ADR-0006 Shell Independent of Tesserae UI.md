---
title: ADR-0006 Shell Independent of Tesserae UI
aliases: [ADR-0006, Independent Shell]
type: adr
status: accepted
owner: phil
created: 2026-10-25
updated: 2026-10-29
tags: [adr, architecture]
related: ["[[ADR-0002 Relationship to Tesserae UI]]", "[[ADR-0007 Shell UI Layer]]", "[[ADR-0001 Shell Surface Strategy]]", "[[ADR-0003 Process Model]]"]
depends_on: []
---

# ADR-0006: Shell Independent of Tesserae UI

> [!summary]
> Tesserae Shell is its own project, built on tre. It does not depend on `tesserae-ui` and asks Tesserae for nothing. Tesserae stays an application framework; shell rendering is not added to it.

> [!note] Update 2026-10-29
> The shell's view format is now TDL, not YAML ([[ADR-0014 Shell File Language]]), so the "second YAML dialect" below is a second file language. The remark about keeping `<Name>_View.yaml` names was superseded by [[ADR-0007 Shell UI Layer#File Naming (2026-10-25)]] before this update. The decision stands.

## Context

[[ADR-0002 Relationship to Tesserae UI]] chose to depend on `tesserae-ui` and found that Tesserae opens only plain windows, so it needed a request to open layer and popup windows ([[TRE-REQ-004 Tesserae Layer and Popup Windows]]). The maintainer then decided Tesserae is a large project of its own and should not take on shell rendering on top of its current scope (2026-10-25, in chat).

## Options

### Option A — Separate Project on Tre (Chosen)

The shell depends on `tesserae-engine` (tre) only. It owns its view layer, theme and widgets ([[ADR-0007 Shell UI Layer]]).

- **For:** Tesserae keeps its scope. The shell is free to shape its API around surfaces and monitors. No Tesserae release gates the shell, and no tre or Tesserae pin has to move together.
- **Against:** the shell must build what Tesserae already has: a view language, reactivity, theme and widgets. This is more work for one maintainer who owns both projects, and it is the second YAML dialect that [[ADR-0002 Relationship to Tesserae UI]] avoided.

### Option B — Depend on `tesserae-ui`, Extended for the Shell

The choice of [[ADR-0002 Relationship to Tesserae UI]]. Superseded by this ADR.

## Decision

Accepted 2026-10-25 by the maintainer in chat: **Option A**. Tesserae Shell is a separate project that builds directly on tre. It does not import `tesserae-ui` and does not change it.

## Consequences

- [[ADR-0002 Relationship to Tesserae UI]] is `superseded` by this ADR.
- [[TRE-REQ-004 Tesserae Layer and Popup Windows]] is `superseded`. Nothing was carried to Tesserae. Its requirements (no main window, a view opened per monitor, popup parenting, live reload of surface keys) move into the shell's own design.
- Engine needs go to tre only ([[AGENTS#6. Engine requests (tre / Tesserae)]]).
- The shell now needs its own view language, reactivity, theme and widgets. How is open: [[ADR-0007 Shell UI Layer]] (`proposed`).
- [[Goals and Non-Goals]] G1, G2 and N8, [[Problem Statement]] and [[V1 Scope]] are updated to match.
- Tesserae remains prior art and a naming reference. Its docs stay in [[AGENTS#13. Reference links]]. The shell may keep similar file names (`<Name>_View.yaml`) for familiarity; that is decided in `41 TDL Reference`.
- Amended by [[ADR-0008 Tesserae Expression Language]]: the shell also uses TEL, a separate library that does not depend on Tesserae UI. Independence from Tesserae UI stands.
- Lower risk for [[ADR-0003 Process Model]]: the single event loop is a plain tre `App`, with no framework layer above it.

> [!danger] Scope risk
> The shell now includes a UI toolkit layer. Without a decision on its size, it can grow without limit. [[ADR-0007 Shell UI Layer]] keeps it to what bars, popups, OSDs and widgets need.

## Links

- [[ADR-0002 Relationship to Tesserae UI]] · [[ADR-0007 Shell UI Layer]] · [[ADR-0003 Process Model]]
