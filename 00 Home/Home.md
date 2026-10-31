---
title: Home
aliases:
  - Dashboard
  - Project Dashboard
type: moc
status: draft
owner: phil
created: 2026-10-18
updated: 2026-10-30
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
| Updated             | 2026-10-30 |
| Last change         | Third TDL rewrite pass done: root block as file type, version pins, upper-case enums, Left-Top-Right-Bottom order, Bar `Edge`/`Width`/`Height`/`Gap`/`Offset`, Panel `Offset`/`Margin`, Frame `Margin` |
| Decided             | [[ADR-0001 Shell Surface Strategy]], [[ADR-0003 Process Model]] to [[ADR-0014 Shell File Language]] (13 accepted; ADR-0002 superseded)                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |
| Waiting on you      | The proposed TDL error list ([[TDL Language#Errors]]); the open items from the third pass in [[ADR-0014 Shell File Language#Open Items]] (how Bar `Alignment`, `Offset` and `Gap` map to tre, `Alignment` values, the `Meld` key, settings enum values); carry T17 to T20 to the TEL project |
| Next                | Plasma coexistence, the D-Bus service layer, portals, global shortcuts ([[Roadmap#Spec backlog (proposed order)]]) |
| Blocked             | Nothing                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |
| Tracking            | Nothing. Tesserae's own version key no longer matters to the shell: the `.tdl` extension and the metadata block tell the files apart ([[ADR-0014 Shell File Language]]) |
| Deferred to testing | Which global settings belong in `settings.tdl` ([[Settings File]]); First KWin release with layer-shell, `org_kde_plasma_shell`, GNOME ([[ADR-0001 Shell Surface Strategy#Open items]]); how KWin presents mirrored outputs ([[V1 Scope#Multi-monitor]]); the four reservers plus the painter on KWin and a 4K Frame with many joins ([[Frame]]); fractional scale at 1.5x ([[Frame]]); fullscreen stacking and detection ([[Surface Types#Fullscreen and maximised windows (decided 2026-10-27)]]); Bar over a Plasma panel ([[Bar]]) |

### Recent Changes

Newest first. Keep the last 8. One line each.

| Date       | Change                                                                                            |
|------------|---------------------------------------------------------------------------------------------------|
| 2026-10-30 | Third TDL rewrite pass over the vault; fourth-round decisions D49 to D51 in [[ADR-0014 Shell File Language]] |
| 2026-10-30 | Third-round decisions D37 to D48 in [[ADR-0014 Shell File Language]]; proposed TDL error list in [[TDL Language]]; T20 proposed |
| 2026-10-30 | Second-sketch decisions D25 to D36 (TDL its own project, root block as file type, upper-case enums, name rules); [[TDL Language]] rewritten |
| 2026-10-30 | [[ADR-0014 Shell File Language]] open items decided (D1 to D24); `41 YAML Reference` renamed `41 TDL Reference`; decisions applied to the notes |
| 2026-10-29 | Second TDL pass over the vault; [[TDL Language]] added; `?:` conditional proposed as T19 |
| 2026-10-29 | [[ADR-0014 Shell File Language]] layout rules decided: `---` metadata, file-type key, block head as type, `Monitor` with `Index:` |
| 2026-10-29 | TDL rewrite pass, levels 0 to 2: AGENTS, Home, Vision, Architecture, Decisions, 41 reference, 42 Python API, 40 Specifications |
| 2026-10-29 | [[ADR-0014 Shell File Language]] grammar answers recorded: `.tdl`, `50%`, `rgba(0 0 0 0)`, repeated names, TextMate grammar |

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
