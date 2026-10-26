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
| Updated | 2026-10-26 |
| Last change | `tre` reviewed [[TRE-REQ-005 Keep-Alive and Loop Stop]] and is building it as #238; recorded its four corrections and the quit-signal path |
| Decided | [[ADR-0001 Shell Surface Strategy]], [[ADR-0003 Process Model]] to [[ADR-0009 D-Bus Client Library]] (8 accepted; ADR-0002 superseded) |
| Waiting on you | Nothing blocking. Optional: confirm tre's D1 to D4 choices for #238 in the tre project |
| Waiting on others | `tre` #236, shape-aware hit testing for concave and convex corners (Backlog, not approved; [[Hit Testing for Concave Corners]]). The Frame uses the explicit-rectangle workaround, enough for v1 |
| Waiting on others (2) | `tre` #238, keep-alive and `LoopHandle.stop()` (approved, in build; [[TRE-REQ-005 Keep-Alive and Loop Stop]]); stopgap: a 1x1 window |
| Next | Module specs (Clock first), `42 Python API`, `41 YAML Reference`, the Panel spec |
| Blocked | Nothing |
| Tracking | Tesserae is adding a matching version key to all its `.yaml` files (maintainer report); check the key name and release when published ([[ADR-0007 Shell UI Layer#File naming (2026-10-25)]]) |
| Deferred to testing | First KWin release with layer-shell, `org_kde_plasma_shell`, GNOME ([[ADR-0001 Shell Surface Strategy#Open items]]); how KWin presents mirrored outputs ([[V1 Scope#Multi-monitor]]) |

### Recent changes

Newest first. Keep the last 8. One line each.

| Date | Change |
|---|---|
| 2026-10-26 | `tre` accepted TRE-REQ-005 (#238); four corrections recorded |
| 2026-10-26 | [[TRE-REQ-005 Keep-Alive and Loop Stop]] written; `tre` pointed to it |
| 2026-10-26 | TEL scope settled: expression language only; events are the shell's |
| 2026-10-26 | ADR-0009 accepted; `tre` answered the no-windows question; `tess-el` reports a TEL scope conflict |
| 2026-10-26 | Stay idle, events are the shell's, module reload decided; D-Bus survey ([[D-Bus Libraries for Python]]); `tre` and `tess-el` messaged |
| 2026-10-26 | D-Bus names observed on Plasma 6.8.1 recorded ([[System Context]]) |
| 2026-10-25 | [[20 Architecture]] drafted (four notes) |
| 2026-10-25 | TEL brief written and moved to `tess-el/docs` (not kept in the vault) |

## Go to

| Track | Notes |
|---|---|
| Project | [[Index]] · [[Roadmap]] · [[Glossary]] · [[AGENTS]] |
| Unknowns and risk | [[Open Questions]] · [[Risk Register]] |
| Decisions | [[30 Decisions]] |
| Research | [[90 Research]]: [[Prior Art - Linux Shell Surfaces]], [[Shadows on Layer Surfaces]], [[Hit Testing for Concave Corners]], [[D-Bus Libraries for Python]], [[Logging with Loguru]], [[Expression Languages for YAML]] |
| Design areas | [[10 Vision]] · [[20 Architecture]] · [[40 Specifications]] · [[41 YAML Reference]] · [[42 Python API]] · [[50 Design System]] · [[60 Quality]] · [[70 Delivery]] · [[80 Engine Requests]] |

## Current

![[Index#Current focus]]

> [!warning] Critical path
> tre 0.5.8 has layer surfaces ([[ADR-0001 Shell Surface Strategy]]). The shell's own view layer on tre is the largest piece to design ([[ADR-0007 Shell UI Layer]]).

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
