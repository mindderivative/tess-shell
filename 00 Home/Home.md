---
title: Home
aliases:
  - Dashboard
  - Project Dashboard
type: moc
status: draft
owner: phil
created: 2026-10-18
updated: 2026-10-31
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
| Updated             | 2026-10-31 |
| Last change         | TEL built full-path tracking (T20), local and unreleased; the shell uses `reads` for name-tree dependencies ([[Expression Language Requirements]]) |
| Decided             | [[ADR-0001 Shell Surface Strategy]], [[ADR-0003 Process Model]] to [[ADR-0014 Shell File Language]] (13 accepted; ADR-0002 superseded)                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| Waiting on you      | The open items from the third pass in [[ADR-0014 Shell File Language#Open Items]] (how Bar `Alignment`, `Offset` and `Gap` map to tre, `Alignment` values, the `Meld` key, settings enum values); the TEL release number to pin as `TEL:` once path tracking ships |
| Next                | Plasma coexistence, the D-Bus service layer, portals, global shortcuts ([[Roadmap#Spec backlog (proposed order)]]) |
| Blocked             | Nothing                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| Tracking            | Nothing. Tesserae's own version key no longer matters to the shell: the `.tdl` extension and the metadata block tell the files apart ([[ADR-0014 Shell File Language]]) |
| Deferred to testing | Which global settings belong in `settings.tdl` ([[Settings File]]); First KWin release with layer-shell, `org_kde_plasma_shell`, GNOME ([[ADR-0001 Shell Surface Strategy#Open items]]); how KWin presents mirrored outputs ([[V1 Scope#Multi-monitor]]); the four reservers plus the painter on KWin and a 4K Frame with many joins ([[Frame]]); fractional scale at 1.5x ([[Frame]]); fullscreen stacking and detection ([[Surface Types#Fullscreen and maximised windows (decided 2026-10-27)]]); Bar over a Plasma panel ([[Bar]]) |

### Recent Changes

Newest first. Keep the last 8. One line each.

| Date       | Change                                                                                            |
|------------|---------------------------------------------------------------------------------------------------|
| 2026-10-31 | TEL built path tracking (T20); name-tree dependency question settled ([[Expression Language Requirements]]) |
| 2026-10-31 | `tess-el` answered the T17 to T20 questions ([[Expression Language Requirements]]) |
| 2026-10-31 | Slot-end rule accepted (D54) in [[ADR-0014 Shell File Language]] and [[TDL Language]] |
| 2026-10-31 | Questions on T17 to T20 sent to `tess-el` ([[Expression Language Requirements]]) |
| 2026-10-31 | TEL requests T17 to T20 accepted ([[Expression Language Requirements]]) |
| 2026-10-31 | Slot-end rule proposed (ADR-0014 open item) after the question on TDL and TEL sharing slots |
| 2026-10-31 | TDL error list accepted (D52); corner-radius order accepted (D53); TEL requests T17 to T20 explained |
| 2026-10-30 | Third TDL rewrite pass over the vault; fourth-round decisions D49 to D51 in [[ADR-0014 Shell File Language]] |

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
