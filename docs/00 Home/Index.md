---
title: Index
aliases: [Tesserae Shell Index, MOC]
type: moc
status: draft
owner: phil
created: 2026-10-18
updated: 2026-11-03
tags: [moc]
---

# Tesserae Shell: Design Vault

> [!NOTE]
> Tesserae Shell is a tool for building desktop shell environments (bars, panels, docks, launchers, OSDs, notification centres, widgets) that run alongside KDE Plasma on Wayland. It is built on the **tre** rendering engine, with Python logic and a front-end in TDL, the Tesserae Data Language. This vault holds the complete design. No code is written until the checklist in [Roadmap](Roadmap.md) is `stable` or deferred by an ADR.

Operating rules for agents: AGENTS.

## Start here

| Note                                    | Purpose                                                   |
|-----------------------------------------|-----------------------------------------------------------|
| [Home](Home.md) | Live dashboard: decisions, verification backlog, coverage |
| [Roadmap](Roadmap.md) | Design completeness checklist and phase status            |
| [Open Questions](Open%20Questions.md) | Unknowns and `#needs-verification` items                  |
| [Risk Register](Risk%20Register.md) | Technical debt and design hazards                         |
| [Glossary](Glossary.md) | Canonical terms                                           |

## Folders

| Folder               | Index                                   | Contents                                                    |
|----------------------|-----------------------------------------|-------------------------------------------------------------|
| `00 Home`            | 00 Home | This note, Glossary, Roadmap, Open Questions, Risk Register |
| `10 Vision`          | [10 Vision](../10%20Vision/10%20Vision.md) | Problem statement, goals, non-goals, personas, use cases    |
| `20 Architecture`    | [20 Architecture](../20%20Architecture/20%20Architecture.md) | System context, process model, data flow, threading         |
| `30 Decisions`       | [30 Decisions](../30%20Decisions/30%20Decisions.md) | ADRs                                                        |
| `40 Specifications`  | [40 Specifications](../40%20Specifications/40%20Specifications.md) | Surfaces, modules, runtime, integration                     |
| `41 TDL Reference`  | [41 TDL Reference](../41%20TDL%20Reference/41%20TDL%20Reference.md) | TDL reference: every config key and file type |
| `42 Python API`      | [42 Python API](../42%20Python%20API/42%20Python%20API.md) | Module and ViewModel contracts, services, events            |
| `50 Design System`   | [50 Design System](../50%20Design%20System/50%20Design%20System.md) | Tokens, components, iconography, motion                     |
| `60 Quality`         | [60 Quality](../60%20Quality/60%20Quality.md) | Budgets, accessibility, testing, security, recovery         |
| `70 Delivery`        | 70 Delivery | Packaging, install, session integration, release            |
| `80 Requests` | [80 Requests](../80%20Requests/80%20Requests.md) | Scoped requests for tre and Tesserae                        |
| `90 Research`        | [90 Research](../90%20Research/90%20Research.md) | Prior art, protocol notes, spikes                           |

> [!WARNING]
> **Folder indexes pending**
> Only `00 Home`, `10 Vision`, `20 Architecture`, `30 Decisions`, `40 Specifications`, `41 TDL Reference`, `42 Python API`, `50 Design System`, `80 Requests` and `90 Research` have content so far. [80 Requests](../80%20Requests/80%20Requests.md), [10 Vision](../10%20Vision/10%20Vision.md), [20 Architecture](../20%20Architecture/20%20Architecture.md), [30 Decisions](../30%20Decisions/30%20Decisions.md), [40 Specifications](../40%20Specifications/40%20Specifications.md), [41 TDL Reference](../41%20TDL%20Reference/41%20TDL%20Reference.md), [42 Python API](../42%20Python%20API/42%20Python%20API.md), [50 Design System](../50%20Design%20System/50%20Design%20System.md) and [90 Research](../90%20Research/90%20Research.md) have their folder index; the others do not exist yet, so their links are unresolved. Create each when its folder gets its first note.

## Decisions

| ADR                                     | Status                 | Blocks                                             |
|-----------------------------------------|------------------------|----------------------------------------------------|
| [ADR-0001 Shell Surface Strategy](../30%20Decisions/ADR-0001%20Shell%20Surface%20Strategy.md) | accepted (2026-10-25)  | All surface specs                                  |
| [ADR-0002 Relationship to Tesserae UI](../30%20Decisions/ADR-0002%20Relationship%20to%20Tesserae%20UI.md) | superseded by ADR-0006 | none                                               |
| [ADR-0006 Shell Independent of Tesserae UI](../30%20Decisions/ADR-0006%20Shell%20Independent%20of%20Tesserae%20UI.md) | accepted (2026-10-25)  | Architecture, packaging                            |
| [ADR-0007 Shell UI Layer](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md) | accepted (2026-10-25)  | View, TDL reference and Python API specs           |
| [ADR-0008 Tesserae Expression Language](../30%20Decisions/ADR-0008%20Tesserae%20Expression%20Language.md) | accepted (2026-10-25)  | Expression language, TDL reference                 |
| [ADR-0009 D-Bus Client Library](../30%20Decisions/ADR-0009%20D-Bus%20Client%20Library.md) | accepted (2026-10-26)  | Module and integration specs                       |
| [ADR-0010 Surface Shadows](../30%20Decisions/ADR-0010%20Surface%20Shadows.md) | accepted (2026-10-27)  | Bar, Panel and Frame specs, design tokens          |
| [ADR-0011 JSON Schema for Shell Files](../30%20Decisions/ADR-0011%20JSON%20Schema%20for%20Shell%20Files.md) | accepted (2026-10-27)  | TDL reference, runtime validation, tooling (under review) |
| [ADR-0012 Keeping the Shell Above Plasma Panels](../30%20Decisions/ADR-0012%20Keeping%20the%20Shell%20Above%20Plasma%20Panels.md) | accepted (2026-10-27)  | Bar, Frame, KWin integration, delivery             |
| [ADR-0013 Control Interface](../30%20Decisions/ADR-0013%20Control%20Interface.md) | accepted (2026-10-28)  | IPC and CLI, the KWin script, Shell Start and Stop |
| [ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md) | accepted (2026-10-29)  | TDL reference, Python Builder, JSON Schema tooling  |
| [ADR-0015 Render Binder](../30%20Decisions/ADR-0015%20Render%20Binder.md) | accepted (2026-11-02) | Layers and components, data flow, the binder |
| [ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md) | accepted (2026-11-02) | Roadmap, development readiness |
| [ADR-0003 Process Model](../30%20Decisions/ADR-0003%20Process%20Model.md) | accepted (2026-10-25)  | Architecture, runtime, quality                     |
| [ADR-0004 Plasma Coexistence](../30%20Decisions/ADR-0004%20Plasma%20Coexistence.md) | accepted (2026-10-25)  | Integration specs                                  |
| [ADR-0005 Global Shortcuts](../30%20Decisions/ADR-0005%20Global%20Shortcuts.md) | accepted (2026-10-25)  | Launcher, integration specs                        |

Vision: [10 Vision](../10%20Vision/10%20Vision.md)

Research: [Prior Art - Linux Shell Surfaces](../90%20Research/Prior%20Art%20-%20Linux%20Shell%20Surfaces.md); [Shadows on Layer Surfaces](../90%20Research/Shadows%20on%20Layer%20Surfaces.md)

Engine requests: [TRE-REQ-001 Layer Surface Window](../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md) (stable; released in tre 0.5.8); [TRE-REQ-004 Tesserae Layer and Popup Windows](../80%20Requests/TRE-REQ-004%20Tesserae%20Layer%20and%20Popup%20Windows.md) (superseded; withdrawn); [TRE-REQ-005 Keep-Alive and Loop Stop](../80%20Requests/TRE-REQ-005%20Keep-Alive%20and%20Loop%20Stop.md) (stable; released in tre 0.5.9)

Planned, not yet written:

- `60 Quality`, `70 Delivery`, the module and integration specs

## Upstream Projects

| Project  | Role                                                                                                                                     | Docs                                       | Baseline |
|----------|------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------|----------|
| tre      | Rendering engine (Rust, Python module `tess_re`)                                                                                             | [docs](https://mindderivative.github.io/tre/) | 0.5.9    |
| Tesserae | Separate project: declarative app framework (`tesserae-ui`). Reference only, not a dependency ([ADR-0006 Shell Independent of Tesserae UI](../30%20Decisions/ADR-0006%20Shell%20Independent%20of%20Tesserae%20UI.md)). | [docs](https://mindderivative.github.io/tess-ui/) | 0.5.1    |

Versions drift. If the live docs disagree with this table, the docs win; update the table.

## Current Focus

1. [10 Vision](../10%20Vision/10%20Vision.md) is confirmed (`stable`); confirm the draft [20 Architecture](../20%20Architecture/20%20Architecture.md) notes, then module and integration specs.
2. Seed [Open Questions](Open%20Questions.md) from the known gaps in AGENTS §4.
