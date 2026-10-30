---
title: Home
aliases:
  - Dashboard
  - Project Dashboard
type: moc
status: draft
owner: phil
created: 2026-10-18
updated: 2026-10-29
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

|                     |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
|---------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Phase               | Design only. No code.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| Updated             | 2026-10-29                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| Last change         | [[ADR-0014 Shell File Language]] proposed: TDL, a structure-only data language in place of YAML |
| Decided             | [[ADR-0001 Shell Surface Strategy]], [[ADR-0003 Process Model]] to [[ADR-0013 Control Interface]] (12 accepted; ADR-0002 superseded)                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| Waiting on you      | Accept, change or reject [[ADR-0014 Shell File Language]] (TDL); its first open items are the file extension, the expression slot and the comparison of one shell in YAML, TDL and KDL |
| Next                | Plasma coexistence, the D-Bus service layer, portals, global shortcuts ([[Roadmap#Spec backlog (proposed order)]]) |
| Blocked             | Nothing                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| Tracking            | Tesserae is adding a matching version key to all its `.yaml` files (maintainer report); check the key name and release when published ([[ADR-0007 Shell UI Layer#File naming (2026-10-25)]])                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
| Deferred to testing | Which global settings belong in `settings.yaml` ([[Settings File]]); First KWin release with layer-shell, `org_kde_plasma_shell`, GNOME ([[ADR-0001 Shell Surface Strategy#Open items]]); how KWin presents mirrored outputs ([[V1 Scope#Multi-monitor]]); the four reservers plus the painter on KWin and a 4K Frame with many joins ([[Frame]]); fractional scale at 1.5x ([[Frame]]); fullscreen stacking and detection ([[Surface Types#Fullscreen and maximised windows (decided 2026-10-27)]]); Bar over a Plasma panel ([[Bar]]) |

### Recent Changes

Newest first. Keep the last 8. One line each.

| Date       | Change                                                                                            |
|------------|---------------------------------------------------------------------------------------------------|
| 2026-10-29 | [[ADR-0014 Shell File Language]] proposed: Tesserae Data Language (TDL) in place of YAML |
| 2026-10-29 | Proposed key names accepted across the specs; namespace `tesserae-shell.<kind>.<name>` decided |
| 2026-10-29 | [[KWin Integration]] answers applied; KWin script test run |
| 2026-10-29 | [[KWin Integration]] drafted |
| 2026-10-29 | tre's clipboard test exists (#243); the maintainer wants it filed ([[Wayland Protocols]]) |
| 2026-10-28 | tre answered the clipboard questions ([[Wayland Protocols]]) |
| 2026-10-28 | [[Wayland Protocols]] answers applied; tre asked about clipboard |
| 2026-10-28 | [[Wayland Protocols]] drafted; Integration started |

## Go to

| Track             | Notes                                                                                                                                                                                                                                                                                                                                                                                           |
|-------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Project           | [[Index]] · [[Roadmap]] · [[Glossary]] · [[AGENTS]]                                                                                                                                                                                                                        |
| Unknowns and risk | [[Open Questions]] · [[Risk Register]]                                                                                                                                                                                                                                                                                                              |
| Decisions         | [[30 Decisions]]                                                                                                                                                                                                                                                                                                                                                         |
| Research          | [[90 Research]]: [[Prior Art - Linux Shell Surfaces]], [[Shadows on Layer Surfaces]], [[Hit Testing for Concave Corners]], [[D-Bus Libraries for Python]], [[Logging with Loguru]], [[Expression Languages for YAML]]                                                                                                   |
| Design areas      | [[10 Vision]] · [[20 Architecture]] · [[40 Specifications]] · [[41 YAML Reference]] · [[42 Python API]] · [[50 Design System]] · [[60 Quality]] · [[70 Delivery]] · [[80 Engine Requests]] |

## Current

![[Index#Current focus]]

> [!warning] Critical path
> tre 0.5.8 has layer surfaces ([[ADR-0001 Shell Surface Strategy]]). The shell's own view layer on tre is the largest piece to design ([[ADR-0007 Shell UI Layer]]).

## Decisions

![[Home.base#Decisions]]

Only the maintainer moves an ADR from `proposed` to `accepted`.

## Needs Verification

Claims tagged `#needs-verification`. Each must be sourced or listed in [[Open Questions]].

![[Home.base#Needs verification]]

## Recently Updated

![[Home.base#Recently updated]]

## Coverage

Which design areas have notes, and how mature they are. A folder missing from the list has not been started.

![[Home.base#By folder]]

![[Home.base#By status]]

## Upstream Baselines

![[Index#Upstream projects]]

## Session Routine

1. Read [[AGENTS]], [[Index]], [[Open Questions]] and [[Roadmap]].
2. Extend an existing note before creating a new one.
3. Record decisions as `proposed` ADRs, unknowns in [[Open Questions]], risks in [[Risk Register]].
4. Commit locally after each task. Never push without an explicit instruction.
