---
title: Problem Statement
aliases: [Why Tesserae Shell, Vision Problem]
type: vision
status: stable
owner: phil
created: 2026-10-25
updated: 2026-10-29
tags: [vision]
---

# Problem Statement

> [!NOTE]
> People who want a custom desktop shell on Linux (a bar, a dock, OSDs, a launcher, desktop widgets) today choose between a toolkit-specific shell framework written in QML or GTK, or a fixed set of Plasma panels. Tesserae Shell offers a third way: describe surfaces in TDL (the Tesserae Data Language, [ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md)), put logic in Python, and render everything with the tre GPU engine, alongside an unchanged KDE Plasma session.

## The Gap

[Prior Art - Linux Shell Surfaces](../90%20Research/Prior%20Art%20-%20Linux%20Shell%20Surfaces.md) surveys the shells and libraries people use today. Four things stand out:

| Observation                                                                                                                                                                                                                                      | Source                                  |
|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------|
| Every shell surveyed places its surfaces on `wlr-layer-shell`; none uses compositor rules or KDE's own panel protocol.                                                                                                                           | [Prior Art - Linux Shell Surfaces > Patterns](../90%20Research/Prior%20Art%20-%20Linux%20Shell%20Surfaces.md#patterns) |
| The surveyed shells are built on a UI toolkit chosen by their authors: QML on Qt (Quickshell, Caelestia, DankMaterialShell), GTK (Fabric, Wayle, HyprPanel, Waybar, eww). Customising one means learning that toolkit's language and widget set. | [Prior Art - Linux Shell Surfaces > Survey](../90%20Research/Prior%20Art%20-%20Linux%20Shell%20Surfaces.md#survey) |
| Most target Hyprland, Sway or niri. Several state a hard requirement for one compositor (Caelestia: Hyprland).                                                                                                                                   | [Prior Art - Linux Shell Surfaces > Survey](../90%20Research/Prior%20Art%20-%20Linux%20Shell%20Surfaces.md#survey) |
| Fabric is the one surveyed shell with a Python API, and it draws with GTK.                                                                                                                                                                       | [Prior Art - Linux Shell Surfaces > Survey](../90%20Research/Prior%20Art%20-%20Linux%20Shell%20Surfaces.md#survey) |

> [!NOTE]
> **Unverified**
> This note does not claim what Plasma's built-in panels can or cannot customise; no source has been read for that. #needs-verification

## The Opportunity

tre 0.5.8 can now create the surfaces a shell needs: `LayerWindow`, `PopupWindow` and an output API ([TRE-REQ-001 Layer Surface Window > Delivered (tre #195 closed)](../80%20Engine%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#delivered-tre-195-closed)). tre gives mechanism only: no widgets, no theme and no file formats (AGENTS > 3. Layering principle). A shell that supplies those itself, as its own project on tre, has properties no surveyed shell combines:

- One rendering path in Rust, with Python only in callbacks (AGENTS > 3. Layering principle).
- A declarative front-end that a non-programmer can read, edit and hot-reload.
- Python for logic, so module authors do not need a second language.
- A design system (tokens, light and dark, high contrast, reduced motion) made for surfaces.

Tesserae, the maintainer's application framework on the same engine, is a separate project and not a dependency ([ADR-0006 Shell Independent of Tesserae UI](../30%20Decisions/ADR-0006%20Shell%20Independent%20of%20Tesserae%20UI.md)).

## What Tesserae Shell is for

A single sentence: **build a desktop shell from TDL and Python, run it next to Plasma, and change it live.**

It is a tool for building shells, not one fixed shell. It ships a default shell as a reference and as the test target for the tool ([V1 Scope](V1%20Scope.md)).

## Constraints that Shape the Problem

| Constraint                                                                                                                                             | Consequence                                                                                                                                                                                         |
|--------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| It runs beside an installed desktop environment (primary target KDE Plasma on Wayland); it does not replace the compositor, session or window manager. | Shell services such as the notification server and tray watcher are shared D-Bus names with plasmashell; each needs a coexist, replace or proxy decision (AGENTS > 4. Known constraints and gaps (seed list)). |
| tre owns every frame; Python owns intent.                                                                                                              | A design that needs per-frame Python is rejected.                                                                                                                                                   |
| The design is complete before code is written.                                                                                                         | Every area in the checklist in AGENTS > 12. Design completeness checklist needs a note first.                                                                                                          |

## Links

- [Goals and Non-Goals](Goals%20and%20Non-Goals.md) · [Personas and Use Cases](Personas%20and%20Use%20Cases.md) · [V1 Scope](V1%20Scope.md) · [10 Vision](10%20Vision.md)
- [ADR-0001 Shell Surface Strategy](../30%20Decisions/ADR-0001%20Shell%20Surface%20Strategy.md)
