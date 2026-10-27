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
| Last change | Decided the blocks and standard modules, `block:` and calling a module by name, and the styling rules (theme, stylesheet, style, inline); updated the notes |
| Decided | [[ADR-0001 Shell Surface Strategy]], [[ADR-0003 Process Model]] to [[ADR-0009 D-Bus Client Library]] (8 accepted; ADR-0002 superseded) |
| Waiting on you | The exact form of a module call (`import:` or by name); names that are both a block and a module; how shipped modules get UIDs; a free-form Path block; update the flow diagram (Containers and Widgets groups become blocks); then path names for repeated uses, the params policy, popup caller and focus, `exclusive_zone` off `top` |
| Waiting on others | tre 0.5.9 release: `hit_shape="painted"` (#236, [[Hit Testing for Concave Corners]]) and `keep_alive`/`stop()` (#238, [[TRE-REQ-005 Keep-Alive and Loop Stop]]); built on local branches. The Frame uses the explicit-rectangle workaround, and the 1x1 window is the stopgap, until then |
| Next | The Clock module spec, the Panel spec, then `60 Quality` |
| Blocked | Nothing |
| Tracking | Tesserae is adding a matching version key to all its `.yaml` files (maintainer report); check the key name and release when published ([[ADR-0007 Shell UI Layer#File naming (2026-10-25)]]) |
| Deferred to testing | First KWin release with layer-shell, `org_kde_plasma_shell`, GNOME ([[ADR-0001 Shell Surface Strategy#Open items]]); how KWin presents mirrored outputs ([[V1 Scope#Multi-monitor]]) |

### Recent changes

Newest first. Keep the last 8. One line each.

| Date | Change |
|---|---|
| 2026-10-26 | Blocks, standard modules, `block:` calls and styling rules decided ([[ADR-0007 Shell UI Layer]], [[Building Blocks]]) |
| 2026-10-26 | Building blocks decided; [[Building Blocks]] written |
| 2026-10-26 | Structure answers recorded; Tesserae's widget model analysed; `modules:` replaced by `children:` |
| 2026-10-26 | Popup stays a kind, called by a module; Special Cases group noted ([[Surface Types#Special cases]]) |
| 2026-10-26 | Flow diagram v3: Layer 0 wallpapers only; Popup is a special case in a module ([[Shell Structure]]) |
| 2026-10-26 | Reserved space enforced to the `top` layer ([[Surface Types#Layers per kind]]) |
| 2026-10-26 | Updated flow diagram checked; [[Shell Structure]] rewritten |
| 2026-10-26 | Flow diagram read; [[Shell Structure]] written |

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
