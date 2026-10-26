---
title: Home
aliases:
  - Dashboard
  - Project Dashboard
type: moc
status: draft
owner: phil
created: 2026-10-18
updated: 2026-10-25
tags:
  - moc
related:
  - "[[Index]]"
  - "[[Roadmap]]"
  - "[[Open Questions]]"
  - "[[Risk Register]]"
depends_on: []
---

# Tesserae Shell

> [!important] Phase: design only
> A tool for building desktop shells (bars, panels, docks, launchers, OSDs, widgets) that run alongside KDE Plasma on Wayland. Built on the **tre** engine with Python logic and a YAML front-end. No code is written until the [[Roadmap]] checklist is `stable` or deferred by an ADR.

## Status

<!-- Maintained by the agent after every change (AGENTS.md section 11). Replace the values; do not append. -->

| | |
|---|---|
| Phase | Design only. No code. |
| Updated | 2026-10-25 |
| Last change | Maintainer confirmed [[10 Vision]]; its five notes are `stable` |
| Decided | [[ADR-0001 Shell Surface Strategy]] to [[ADR-0005 Global Shortcuts]] (5 accepted) |
| Waiting on you | Decide mirrored outputs and `output_updated` ([[V1 Scope#Multi-monitor]]); confirm [[TRE-REQ-001 Layer Surface Window]] against the shell |
| Next | Write the Tesserae request for layer and popup windows ([[ADR-0002 Relationship to Tesserae UI#Consequences]]); start `20 Architecture` |
| Blocked | Nothing in tre. Tesserae cannot yet open a layer window from a view. |
| Deferred to testing | First KWin release with layer-shell, `org_kde_plasma_shell`, GNOME ([[ADR-0001 Shell Surface Strategy#Open items]]) |

### Recent changes

Newest first. Keep the last 8. One line each.

| Date | Change |
|---|---|
| 2026-10-25 | [[10 Vision]] confirmed and set to `stable` |
| 2026-10-25 | Added ADR-0002 to ADR-0005; multi-monitor decisions in [[V1 Scope]] |
| 2026-10-25 | Multi-monitor requirement added to [[10 Vision]] |
| 2026-10-25 | Wrote [[10 Vision]]: problem, goals, personas, v1 scope |
| 2026-10-25 | Accepted [[ADR-0001 Shell Surface Strategy]]; deferred its three testing-phase checks |
| 2026-10-25 | Matched the vault to tre 0.5.8 ([[TRE-REQ-001 Layer Surface Window]]) |

## Go to

| Track | Notes |
|---|---|
| Project | [[Index]] · [[Roadmap]] · [[Glossary]] · [[AGENTS]] |
| Unknowns and risk | [[Open Questions]] · [[Risk Register]] |
| Decisions | [[30 Decisions]] |
| Research | [[Prior Art - Linux Shell Surfaces]] |
| Design areas | [[10 Vision]] · [[20 Architecture]] · [[40 Specifications]] · [[41 YAML Reference]] · [[42 Python API]] · [[50 Design System]] · [[60 Quality]] · [[70 Delivery]] · [[80 Engine Requests]] |

## Current

![[Index#Current focus]]

> [!warning] Critical path
> tre 0.5.8 has layer surfaces ([[ADR-0001 Shell Surface Strategy]]). The open dependency is Tesserae: it must open a `LayerWindow` and `PopupWindow` from a view ([[ADR-0002 Relationship to Tesserae UI#Consequences]]).

## Decisions

![[Home.base#Decisions]]

Only the maintainer moves an ADR from `proposed` to `accepted`.

## Needs verification

Claims tagged `#needs-verification`. Each must be sourced or listed in [[Open Questions]].

![[Home.base#Needs verification]]

## Recently updated

![[Home.base#Recently updated]]

## Coverage

Which design areas have notes, and how mature they are. A folder missing from the list has not been started.

![[Home.base#By folder]]

![[Home.base#By status]]

## Upstream baselines

![[Index#Upstream projects]]

## Session routine

1. Read [[AGENTS]], [[Index]], [[Open Questions]] and [[Roadmap]].
2. Extend an existing note before creating a new one.
3. Record decisions as `proposed` ADRs, unknowns in [[Open Questions]], risks in [[Risk Register]].
4. Commit locally after each task. Never push without an explicit instruction.
