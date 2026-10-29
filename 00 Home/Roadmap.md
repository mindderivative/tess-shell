---
title: Roadmap
aliases: [Design Roadmap, Design Completeness Checklist]
type: moc
status: draft
owner: phil
created: 2026-10-27
updated: 2026-10-27
tags: [moc, roadmap]
related: ["[[Home]]", "[[Open Questions]]", "[[Risk Register]]", "[[AGENTS#12. Design completeness checklist]]"]
depends_on: []
---

# Roadmap

> [!summary]
> The design completeness checklist from [[AGENTS#12. Design completeness checklist]], with the notes that cover each area and what is missing. Coding starts only when every row is `stable` or explicitly deferred by an accepted ADR. Status is the lowest status of the notes in the row. Maintainer direction (2026-10-27): finish the specs before starting more module specs.

## Checklist

| Area | Notes | Status | Missing |
|---|---|---|---|
| Vision | [[10 Vision]]: [[Problem Statement]], [[Goals and Non-Goals]], [[Personas and Use Cases]], [[V1 Scope]] | stable | Nothing |
| Architecture | [[20 Architecture]]: [[System Context]], [[Layers and Components]], [[Process Model and Threading]], [[Data Flow]], [[Shell Structure]] | draft | A service layer note (shared D-Bus and time source) |
| Surfaces | [[Surfaces]]: [[Surface Types]], [[Bar]], [[Frame]], [[Panel]], [[Popup]] | review (Surface Types and Popup draft) | The Special Cases kinds (a Notification window, after v1) |
| Integration | None yet | not started | Wayland protocols, KWin (the fullscreen script, window rules), Plasma coexistence, the shared D-Bus service layer, portals, global shortcuts |
| Runtime | [[Runtime]]: [[Shell Start and Stop]], [[Config Discovery and Registry]], [[Validation and Errors]], [[Hot Reload]], [[IPC and CLI]], [[Expression Language Requirements]]; [[Settings File]], [[Shell File]], [[Module File]] (in `41`) | draft | Logging |
| Python API | [[42 Python API]]: [[Module Contract]], [[Module Context]], [[Value Types and Conversion]], [[Python Builder]] | draft | Service APIs, events, versioning and stability |
| YAML reference | [[41 YAML Reference]]: [[Common Keys and Conventions]], [[Shell File]], [[Module File]], [[Style, Theme and Stylesheet Files]], [[Style Schema]], [[Settings File]], [[JSON Schema and Editor Support]] | draft (Style Schema review) | A per-block property reference; surface-kind keys in one place; event and action keys |
| Design system | [[50 Design System]]: [[Building Blocks]], [[V1 Widgets]] | draft | Principles, tokens (colour, type, shape, space, elevation, motion), components, iconography, motion, light/dark, high contrast, reduced motion, following the desktop theme |
| Quality | None yet | not started | Performance budgets, accessibility, testing strategy, security model for user Python, crash recovery and the watchdog |
| Delivery | None yet | not started | Packaging, dependencies on tre, install, autostart and session integration, upgrades, licensing |
| Engine requests | [[80 Engine Requests]]: [[TRE-REQ-001 Layer Surface Window]] (released), [[TRE-REQ-005 Keep-Alive and Loop Stop]] (released), [[TRE-REQ-006 Repeating Gradients]] (draft, not filed) | stable | Nothing blocks the shell |
| Decisions | [[30 Decisions]]: ADR-0001, ADR-0003 to ADR-0012 accepted, ADR-0013 accepted, ADR-0002 superseded | accepted | Nothing proposed |

## Spec backlog (proposed order)

Recommendation: write the notes that other notes already point at first, then the areas with no notes. Each is a draft with recommendations; the maintainer decides ([[AGENTS#2. Hard rules]] rule 5).

| # | Note | Folder | Why now |
|---|---|---|---|
| 1 | Popup (written 2026-10-28, draft) | `40 Specifications/Surfaces/` | Completes Surfaces; Panel, Bar and the module contract already refer to it |
| 2 | Shell Start and Stop, Config Discovery and Registry, Validation and Errors, Hot Reload (written 2026-10-28, draft) | `40 Specifications/Runtime/` | The settings, schema and module notes depend on them |
| 3 | IPC and CLI (written 2026-10-28, draft; ADR-0013 accepted) | `40 Specifications/Runtime/` | ADR-0011 and ADR-0012 name commands (`schema`, the rule install and remove) |
| 4 | Logging | `40 Specifications/Runtime/` | Settings File sets the folder and file names; the research note is open |
| 5 | Wayland Protocols, KWin Integration, Plasma Coexistence, D-Bus Service Layer, Portals, Global Shortcuts | `40 Specifications/Integration/` | The Integration row is empty; ADR-0004, ADR-0005, ADR-0009 and ADR-0012 feed it |
| 6 | Design principles, tokens, components, iconography, motion, accessibility modes | `50 Design System/` | The Style Schema is accepted and needs the token values |
| 7 | Python API: service APIs, events, versioning | `42 Python API/` | After the runtime and integration notes exist |
| 8 | Performance budgets, Accessibility, Testing strategy, Security model, Crash recovery | `60 Quality/` | Most of the budgets are already named in the surface notes |
| 9 | Packaging, Install and Autostart, Upgrades and Versioning, Licensing | `70 Delivery/` | Last: depends on all of the above |

Module specs (Workspaces, Audio and the rest of the v1 list) wait until the specs above are done (maintainer, 2026-10-27).

## Links

- [[Home]] · [[Open Questions]] · [[Risk Register]] · [[Index]]
