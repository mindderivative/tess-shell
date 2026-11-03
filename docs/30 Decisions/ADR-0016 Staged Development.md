---
title: ADR-0016 Staged Development
aliases: [ADR-0016, Staged Start, Start Development]
type: adr
status: accepted
owner: phil
created: 2026-11-02
updated: 2026-11-03
tags: [adr, process]
---

# ADR-0016: Staged Development

> [!NOTE]
> Coding starts in stages, not after every design row is stable. Each milestone of [Development Readiness](../00%20Home/Development%20Readiness.md) starts when the notes it needs have reached `review`; the rows it does not need are deferred to the milestone that does. M0 starts once the package layout and the testing strategy are written. Accepted by the maintainer in chat on 2026-11-02 ("agree").

## Context

AGENTS > 12. Design Completeness Checklist says coding starts only when every row is `stable` or deferred by an accepted ADR. On 2026-11-02 the vision is stable, the runtime, surface and integration specs are written, and `tess_dl` and tre 0.5.10 are available, but Delivery, most of Quality, the module list and the token values are not written. The maintainer's stance is that TEL, tre, TDL and the shell are developed together and the design stays open to change ([Roadmap > Working Mode: Fluid Dependencies](../00%20Home/Roadmap.md#working-mode-fluid-dependencies)).

## Options

### Option A — Staged Start (Chosen)

Defer the rows that a milestone does not need to the milestone that does.

- **For:** the design is tested by running code early; a wrong design is found at M1, not at the end; it matches the fluid stance.
- **Against:** some design work may be revised after code exists.

### Option B — Wait for Every Row to Be Stable

- **Against:** holds the skeleton for work it does not need (delivery, security, token values).

## Decision

Accepted 2026-11-02 by the maintainer in chat ("agree"): **Option A**.

| Row | Deferred to | Reason |
|---|---|---|
| Integration | M5 | The live tests need the running shell; the specs exist |
| Quality: accessibility, security model, crash recovery | M2 (accessibility, security), M6 (crash recovery) | The testing strategy is written before M0; the rest follow code |
| Delivery | M6 | Needs a working shell |
| Design system: token values, iconography | M1 and M2 | M1 needs the building blocks, not the values |
| Python API for Python-built shells | After M2 | Needs the module contract working |
| Surfaces: Popup | M3 | Not needed before the Bar works |

Not deferred: Vision, Architecture (the binder is accepted), Runtime (needed at M0), Engine requests. A milestone starts when its "Needs" notes in [Development Readiness](../00%20Home/Development%20Readiness.md) are at `review`. The first milestone, M0, starts when [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md) and [Testing Strategy](../60%20Quality/Testing%20Strategy.md) are written.

## Consequences

- AGENTS > 1. What Tesserae Shell is no longer says design only: it says design continues alongside staged development. The agent still writes code only inside the milestone in progress, and keeps the vault as the design record.
- Each milestone ends with an update to the notes it touched, and a list of design changes it forced.
- A design change found by code is a dated amendment or a new ADR, never silent ([Roadmap > Working Mode: Fluid Dependencies](../00%20Home/Roadmap.md#working-mode-fluid-dependencies)).
- Code lives in the `tess-shell` repository, under `src/tess_shell/` and `tests/`, with the docs export kept in `docs/` ([Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md)).

## Links

- [Development Readiness](../00%20Home/Development%20Readiness.md) · [Roadmap](../00%20Home/Roadmap.md) · [ADR-0015 Render Binder](ADR-0015%20Render%20Binder.md) · [30 Decisions](30%20Decisions.md)
