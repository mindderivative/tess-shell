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
| Updated | 2026-10-27 |
| Last change | Tested `dbus-fast` 5.2.0 for the control interface: it exports methods, a property and a signal; as a client `jeepney` is faster ([[ADR-0013 Control Interface#Context]]) |
| Decided | [[ADR-0001 Shell Surface Strategy]], [[ADR-0003 Process Model]] to [[ADR-0012 Keeping the Shell Above Plasma Panels]] (11 accepted; ADR-0013 proposed; ADR-0002 superseded) |
| Waiting on you | Accept or change [[ADR-0013 Control Interface]]; the twelve [[IPC and CLI#Open questions]]; key names the specs mark proposed |
| Next | Logging, then the Integration specs ([[Roadmap#Spec backlog (proposed order)]]) |
| Blocked | Nothing |
| Tracking | Tesserae is adding a matching version key to all its `.yaml` files (maintainer report); check the key name and release when published ([[ADR-0007 Shell UI Layer#File naming (2026-10-25)]]) |
| Deferred to testing | Which global settings belong in `settings.yaml` ([[Settings File]]); First KWin release with layer-shell, `org_kde_plasma_shell`, GNOME ([[ADR-0001 Shell Surface Strategy#Open items]]); how KWin presents mirrored outputs ([[V1 Scope#Multi-monitor]]); the four reservers plus the painter on KWin and a 4K Frame with many joins ([[Frame]]); fractional scale at 1.5x ([[Frame]]); fullscreen stacking and detection ([[Surface Types#Fullscreen and maximised windows (decided 2026-10-27)]]); Bar over a Plasma panel ([[Bar]]) |

### Recent changes

Newest first. Keep the last 8. One line each.

| Date | Change |
|---|---|
| 2026-10-28 | `dbus-fast` export and client cost tested ([[ADR-0013 Control Interface]]) |
| 2026-10-28 | [[IPC and CLI]] written; [[ADR-0013 Control Interface]] proposed |
| 2026-10-28 | [[Shell Start and Stop]]: `XDG_RUNTIME_DIR` rule decided |
| 2026-10-28 | Runtime specs: all questions answered, in review |
| 2026-10-28 | [[Popup]] tooltip delays decided (500 and 200 ms) |
| 2026-10-28 | Four Runtime specs written (start and stop, discovery and registry, validation and errors, hot reload) |
| 2026-10-28 | [[Popup]] answers applied; [[TRE-REQ-007 Popup Body Geometry]] written |
| 2026-10-28 | [[Popup]] spec drafted |

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
