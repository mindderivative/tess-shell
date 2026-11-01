---
title: Home
aliases:
  - Dashboard
  - Project Dashboard
type: moc
status: draft
owner: phil
created: 2026-10-18
updated: 2026-11-01
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
> A tool for building desktop shells (bars, panels, docks, launchers, OSDs, widgets) that run alongside KDE Plasma on Wayland. Built on the **tre** engine with Python logic and a front-end in TDL, the Tesserae Data Language. No code is written until the [[Roadmap]] checklist is `stable` or deferred by an ADR.

## Status

<!-- Maintained by the agent after every change (AGENTS.md section 11). Replace the values; do not append. -->

|                     |                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |
|---------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Phase               | Design only. No code.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| Updated             | 2026-11-01 |
| Last change         | `For` entries use TEL's counter names, `<name>_0001` (D65, [[ADR-0014 Shell File Language]]) |
| Decided             | [[ADR-0001 Shell Surface Strategy]], [[ADR-0003 Process Model]] to [[ADR-0014 Shell File Language]] (13 accepted; ADR-0002 superseded)                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| Waiting on you      | Confirm the base name of a `For` entry (the `For` block's `Name:`, else its child's head) in [[ADR-0014 Shell File Language#Eighth-Round Notes (2026-11-01)]]; the TEL release number to pin as `TEL:`; the building-blocks reference is next |
| Next                | Building Blocks reference (gates the shipped modules); then the missing Integration notes ([[Roadmap#Spec backlog (proposed order)]]) |
| Blocked             | Nothing                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| Tracking            | Nothing. Tesserae's own version key no longer matters to the shell: the `.tdl` extension and the metadata block tell the files apart ([[ADR-0014 Shell File Language]]) |
| Deferred to testing | Which global settings belong in `settings.tdl` ([[Settings File]]); First KWin release with layer-shell, `org_kde_plasma_shell`, GNOME ([[ADR-0001 Shell Surface Strategy#Open items]]); how KWin presents mirrored outputs ([[V1 Scope#Multi-monitor]]); the four reservers plus the painter on KWin and a 4K Frame with many joins ([[Frame]]); fractional scale at 1.5x ([[Frame]]); fullscreen stacking and detection ([[Surface Types#Fullscreen and maximised windows (decided 2026-10-27)]]); Bar over a Plasma panel ([[Bar]]) |

### Recent Changes

Newest first. Keep the last 8. One line each.

| Date       | Change                                                                                            |
|------------|---------------------------------------------------------------------------------------------------|
| 2026-11-01 | `For` entries use TEL's counter names (D65) ([[ADR-0014 Shell File Language]]) |
| 2026-11-01 | TEL accepted and built `?:`; TEL step 5 (conditions, repeater reconciliation) recorded ([[Expression Language Requirements]]) |
| 2026-10-31 | `Meld` restored (confirmed); `?:` cost test results recorded ([[Expression Language Requirements]]) |
| 2026-10-31 | P1 accepted (D61); Bar `Gap` decides its meld (D62); Panel `Meld` restored (D56 corrected) ([[ADR-0014 Shell File Language]]) |
| 2026-10-31 | P2 to P7 decided (D55 to D60); Panel `Meld` removed ([[ADR-0014 Shell File Language]]) |
| 2026-10-31 | Proposed answers P1 to P7 and the Bar-to-tre mapping ([[Bar]], [[ADR-0014 Shell File Language]]) |
| 2026-10-31 | TEL built path tracking (T20); name-tree dependency question settled ([[Expression Language Requirements]]) |
| 2026-10-31 | `tess-el` answered the T17 to T20 questions ([[Expression Language Requirements]]) |

## Go to

| Track             | Notes                                                                                                                                                                                                                                                                                                                                                                                           |
|-------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Project           | [[Index]] · [[Roadmap]] · [[Glossary]] · [[AGENTS]]                                                                                                                                                                                                                        |
| Unknowns and risk | [[Open Questions]] · [[Risk Register]]                                                                                                                                                                                                                                                                                                              |
| Decisions         | [[30 Decisions]]                                                                                                                                                                                                                                                                                                                                                         |
| Research          | [[90 Research]]: [[Prior Art - Linux Shell Surfaces]], [[Shadows on Layer Surfaces]], [[Hit Testing for Concave Corners]], [[D-Bus Libraries for Python]], [[Logging with Loguru]], [[Expression Languages for YAML]], [[Shell File Syntax Comparison]]                                                                                                   |
| Design areas      | [[10 Vision]] · [[20 Architecture]] · [[40 Specifications]] · [[41 TDL Reference]] · [[42 Python API]] · [[50 Design System]] · [[60 Quality]] · [[70 Delivery]] · [[80 Engine Requests]] |

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
