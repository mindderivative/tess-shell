---
title: ADR-0002 Relationship to Tesserae UI
aliases: [ADR-0002, Tesserae UI Dependency]
type: adr
status: superseded
owner: phil
created: 2026-10-25
updated: 2026-11-03
tags: [adr, architecture]
---

# ADR-0002: Relationship to Tesserae UI

> [!WARNING]
> **Superseded by [ADR-0006 Shell Independent of Tesserae UI](ADR-0006%20Shell%20Independent%20of%20Tesserae%20UI.md) (2026-10-25)**
> The maintainer decided Tesserae stays a separate project and the shell is built on tre alone. The record below is kept as written.

> [!NOTE]
> Tesserae Shell depends on `tesserae-ui` for its view language, reactivity, themes, stylesheets and hot reload, and does not define a second YAML dialect. Tesserae today opens only plain windows, so it must gain a way to open layer and popup windows. That work is a Tesserae request, not yet written.

## Context

AGENTS > 4. Known constraints and gaps (seed list) asks whether to depend on `tesserae-ui` or build a smaller layer directly on `tre`. Two YAML dialects for the same view concepts would diverge ([Goals and Non-Goals](../10%20Vision/Goals%20and%20Non-Goals.md) N8).

What the Tesserae source does today (local clone at `~/Projects/pyDev/projects/tesserae`, commit `6e22100`, read 2026-10-25):

- `pyproject.toml` pins `tesserae-engine==0.5.8`.
- `src/tesserae/app.py` creates its windows as plain `Window(...)` (the main window at line 318, extra windows through `open_window` at line 944) and passes them to `tre.App.add_window`.
- The source contains no `LayerWindow`, `PopupWindow` or `outputs()` use.

So Tesserae can run on the tre that has `LayerWindow` but cannot yet ask for one from a view. #needs-verification: confirm against the published `tesserae-ui` release and docs; the clone may be ahead of PyPI.

## Options

### Option A — Depend on `tesserae-ui` (Recommended, Chosen)

Reuse the view language, `Signal`/`Computed`/`Effect`, MD3 components, themes, stylesheets and hot reload.

- **For:** one YAML dialect, one reactivity model, one design system. Shell views and app views share components and themes.
- **Against:** Tesserae is shaped around an application with a main window. A shell has many surfaces, some with no title, size or focus in the app sense. Tesserae must grow a surface concept.

### Option B — Build a Smaller Layer Directly on `tre`

- **For:** shaped for shells from the start.
- **Against:** a second view language, second reactivity and second theme system to design, document and keep in step. Rejected by [Goals and Non-Goals](../10%20Vision/Goals%20and%20Non-Goals.md) N8.

## Decision

Accepted 2026-10-25 by the maintainer in chat ("as recommended"): **Option A**. Tesserae Shell depends on `tesserae-ui`. Superseded the same day by [ADR-0006 Shell Independent of Tesserae UI](ADR-0006%20Shell%20Independent%20of%20Tesserae%20UI.md).

## Consequences

- Tesserae needs a way to open a `LayerWindow` and a `PopupWindow` from a view and bind them to an `Output`. This is a request to the Tesserae project, carried upstream by the maintainer (AGENTS > 6. Requests Between Projects). Written as [TRE-REQ-004 Tesserae Layer and Popup Windows](../80%20Requests/TRE-REQ-004%20Tesserae%20Layer%20and%20Popup%20Windows.md) (`draft`).
- The Tesserae version is pinned together with the tre version (70 Delivery, to write).
- Shell-only file types (a shell layout, a module manifest) get their own suffix in `41 TDL Reference/` (AGENTS > 9. Naming in the designed system).

## Links

- [Tesserae overview](https://mindderivative.github.io/tess-ui/) · [View language](https://mindderivative.github.io/tess-ui/guide/view-language/)
- [ADR-0001 Shell Surface Strategy](ADR-0001%20Shell%20Surface%20Strategy.md) · [ADR-0003 Process Model](ADR-0003%20Process%20Model.md) · [V1 Scope > Decisions to take](../10%20Vision/V1%20Scope.md#decisions-to-take)
