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
| Last change | Recorded `tre`'s hit-testing answer and the path forward in [[Hit Testing for Concave Corners]] |
| Decided | [[ADR-0001 Shell Surface Strategy]], [[ADR-0003 Process Model]] to [[ADR-0007 Shell UI Layer]] (6 accepted; ADR-0002 superseded) |
| Waiting on you | How a Panel's attachment to another surface is written (to explore, [[Surface Types#Open questions]]); how the shell writes the UID into a user's file ([[ADR-0007 Shell UI Layer#Open items]]); TEL's repository, licence and syntax ([[Expression Language Requirements#Open questions]]) |
| Waiting on others | `tre` to deliver shape-aware hit testing for concave and convex corners ([[Hit Testing for Concave Corners]]); the Frame uses an explicit-rectangle workaround until then |
| Next | Start `20 Architecture`, including the UI layer; then the module and runtime specs |
| Blocked | Nothing |
| Tracking | Tesserae is adding a matching version key to all its `.yaml` files (maintainer report); check the key name and release when published ([[ADR-0007 Shell UI Layer#File naming (2026-10-25)]]) |
| Deferred to testing | First KWin release with layer-shell, `org_kde_plasma_shell`, GNOME ([[ADR-0001 Shell Surface Strategy#Open items]]); how KWin presents mirrored outputs ([[V1 Scope#Multi-monitor]]) |

### Recent changes

Newest first. Keep the last 8. One line each.

| Date | Change |
|---|---|
| 2026-10-25 | `tre` answered the hit-testing question; path forward confirmed ([[Hit Testing for Concave Corners]]) |
| 2026-10-25 | TEL details, Frame in v1, surface mapping, [[V1 Widgets]], [[Glossary]]; `tre` asked about hit testing |
| 2026-10-25 | [[ADR-0008 Tesserae Expression Language]] accepted; requirements written ([[Expression Language Requirements]]) |
| 2026-10-25 | Expression engine survey written ([[Expression Languages for YAML]]) |
| 2026-10-25 | Expression language, `monitor` matching, module Python contract, config directory and registry identity decided ([[ADR-0007 Shell UI Layer]]) |
| 2026-10-25 | `type:`/`kind:`, UID registry and module data hand-off decided ([[ADR-0007 Shell UI Layer]]) |
| 2026-10-25 | Surface Types corrected; shadows research written ([[Shadows on Layer Surfaces]]) |
| 2026-10-25 | [[Surface Types]] written; module, import, monitor, name and error rules decided ([[ADR-0007 Shell UI Layer]]) |

## Go to

| Track | Notes |
|---|---|
| Project | [[Index]] · [[Roadmap]] · [[Glossary]] · [[AGENTS]] |
| Unknowns and risk | [[Open Questions]] · [[Risk Register]] |
| Decisions | [[30 Decisions]] |
| Research | [[90 Research]]: [[Prior Art - Linux Shell Surfaces]], [[Shadows on Layer Surfaces]], [[Hit Testing for Concave Corners]], [[Expression Languages for YAML]] |
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
