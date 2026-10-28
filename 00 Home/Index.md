---
title: Index
aliases: [Tesserae Shell Index, MOC]
type: moc
status: draft
owner: phil
created: 2026-10-18
updated: 2026-10-25
tags: [moc]
related: ["[[AGENTS]]"]
depends_on: []
---

# Tesserae Shell: Design Vault

> [!summary]
> Tesserae Shell is a tool for building desktop shell environments (bars, panels, docks, launchers, OSDs, notification centres, widgets) that run alongside KDE Plasma on Wayland. It is built on the **tre** rendering engine, with Python logic and a YAML front-end. This vault holds the complete design. No code is written until the checklist in [[Roadmap]] is `stable` or deferred by an ADR.

Operating rules for agents: [[AGENTS]].

## Start here

| Note | Purpose |
|---|---|
| [[Home]] | Live dashboard: decisions, verification backlog, coverage |
| [[Roadmap]] | Design completeness checklist and phase status |
| [[Open Questions]] | Unknowns and `#needs-verification` items |
| [[Risk Register]] | Technical debt and design hazards |
| [[Glossary]] | Canonical terms |

## Folders

| Folder | Index | Contents |
|---|---|---|
| `00 Home` | [[00 Home]] | This note, Glossary, Roadmap, Open Questions, Risk Register |
| `10 Vision` | [[10 Vision]] | Problem statement, goals, non-goals, personas, use cases |
| `20 Architecture` | [[20 Architecture]] | System context, process model, data flow, threading |
| `30 Decisions` | [[30 Decisions]] | ADRs |
| `40 Specifications` | [[40 Specifications]] | Surfaces, modules, runtime, integration |
| `41 YAML Reference` | [[41 YAML Reference]] | Schema for every config key and file type |
| `42 Python API` | [[42 Python API]] | Module and ViewModel contracts, services, events |
| `50 Design System` | [[50 Design System]] | Tokens, components, iconography, motion |
| `60 Quality` | [[60 Quality]] | Budgets, accessibility, testing, security, recovery |
| `70 Delivery` | [[70 Delivery]] | Packaging, install, session integration, release |
| `80 Engine Requests` | [[80 Engine Requests]] | Scoped requests for tre and Tesserae |
| `90 Research` | [[90 Research]] | Prior art, protocol notes, spikes |

> [!warning] Folder indexes pending
> Only `00 Home`, `10 Vision`, `20 Architecture`, `30 Decisions`, `40 Specifications`, `41 YAML Reference`, `42 Python API`, `50 Design System`, `80 Engine Requests` and `90 Research` have content so far. [[80 Engine Requests]], [[10 Vision]], [[20 Architecture]], [[30 Decisions]], [[40 Specifications]], [[41 YAML Reference]], [[42 Python API]], [[50 Design System]] and [[90 Research]] have their folder index; the others do not exist yet, so their links are unresolved. Create each when its folder gets its first note.

## Decisions

| ADR | Status | Blocks |
|---|---|---|
| [[ADR-0001 Shell Surface Strategy]] | accepted (2026-10-25) | All surface specs |
| [[ADR-0002 Relationship to Tesserae UI]] | superseded by ADR-0006 | none |
| [[ADR-0006 Shell Independent of Tesserae UI]] | accepted (2026-10-25) | Architecture, packaging |
| [[ADR-0007 Shell UI Layer]] | accepted (2026-10-25) | View, YAML and Python API specs |
| [[ADR-0008 Tesserae Expression Language]] | accepted (2026-10-25) | Expression language, YAML reference |
| [[ADR-0009 D-Bus Client Library]] | accepted (2026-10-26) | Module and integration specs |
| [[ADR-0010 Surface Shadows]] | accepted (2026-10-27) | Bar, Panel and Frame specs, design tokens |
| [[ADR-0011 JSON Schema for Shell Files]] | accepted (2026-10-27) | YAML reference, runtime validation, tooling |
| [[ADR-0012 Keeping the Shell Above Plasma Panels]] | accepted (2026-10-27) | Bar, Frame, KWin integration, delivery |
| [[ADR-0003 Process Model]] | accepted (2026-10-25) | Architecture, runtime, quality |
| [[ADR-0004 Plasma Coexistence]] | accepted (2026-10-25) | Integration specs |
| [[ADR-0005 Global Shortcuts]] | accepted (2026-10-25) | Launcher, integration specs |

Vision: [[10 Vision]]

Research: [[Prior Art - Linux Shell Surfaces]]; [[Shadows on Layer Surfaces]]

Engine requests: [[TRE-REQ-001 Layer Surface Window]] (stable; released in tre 0.5.8); [[TRE-REQ-004 Tesserae Layer and Popup Windows]] (superseded; withdrawn); [[TRE-REQ-005 Keep-Alive and Loop Stop]] (stable; released in tre 0.5.9)

Planned, not yet written:
- `60 Quality`, `70 Delivery`, the module and integration specs

## Upstream projects

| Project | Role | Docs | Baseline |
|---|---|---|---|
| tre | Rendering engine (Rust, Python module `tre`) | [docs](https://mindderivative.github.io/tre/) | 0.5.9 |
| Tesserae | Separate project: declarative app framework (`tesserae-ui`). Reference only, not a dependency ([[ADR-0006 Shell Independent of Tesserae UI]]). | [docs](https://mindderivative.github.io/tesserae/) | 0.5.1 |

Versions drift. If the live docs disagree with this table, the docs win; update the table.

## Current focus

1. [[10 Vision]] is confirmed (`stable`); confirm the draft [[20 Architecture]] notes, then module and integration specs.
2. Seed [[Open Questions]] from the known gaps in [[AGENTS]] §4.
