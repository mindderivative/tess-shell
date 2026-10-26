---
title: Problem Statement
aliases: [Why Tesserae Shell, Vision Problem]
type: vision
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [vision]
related: ["[[10 Vision]]", "[[Goals and Non-Goals]]", "[[Personas and Use Cases]]", "[[Prior Art - Linux Shell Surfaces]]"]
depends_on: []
---

# Problem statement

> [!summary]
> People who want a custom desktop shell on Linux (a bar, a dock, OSDs, a launcher, desktop widgets) today choose between a toolkit-specific shell framework written in QML or GTK, or a fixed set of Plasma panels. Tesserae Shell offers a third way: describe surfaces in YAML, put logic in Python, and render everything with the tre GPU engine, alongside an unchanged KDE Plasma session.

## The gap

[[Prior Art - Linux Shell Surfaces]] surveys the shells and libraries people use today. Four things stand out:

| Observation | Source |
|---|---|
| Every shell surveyed places its surfaces on `wlr-layer-shell`; none uses compositor rules or KDE's own panel protocol. | [[Prior Art - Linux Shell Surfaces#Patterns]] |
| The surveyed shells are built on a UI toolkit chosen by their authors: QML on Qt (Quickshell, Caelestia, DankMaterialShell), GTK (Fabric, Wayle, HyprPanel, Waybar, eww). Customising one means learning that toolkit's language and widget set. | [[Prior Art - Linux Shell Surfaces#Survey]] |
| Most target Hyprland, Sway or niri. Several state a hard requirement for one compositor (Caelestia: Hyprland). | [[Prior Art - Linux Shell Surfaces#Survey]] |
| Fabric is the one surveyed shell with a Python API, and it draws with GTK. | [[Prior Art - Linux Shell Surfaces#Survey]] |

> [!question] Unverified
> This note does not claim what Plasma's built-in panels can or cannot customise; no source has been read for that. #needs-verification

## The opportunity

tre 0.5.8 can now create the surfaces a shell needs: `LayerWindow`, `PopupWindow` and an output API ([[TRE-REQ-001 Layer Surface Window#Delivered (tre #195 closed)]]). Tesserae (`tesserae-ui`) already provides a declarative YAML view language, Python ViewModels, reactive `Signal`/`Computed`/`Effect`, Material Design 3 components, themes and hot reload ([Tesserae overview](https://mindderivative.github.io/tesserae/)). A shell built from those two layers has these properties no surveyed shell combines:

- One rendering path in Rust, with Python only in callbacks ([[AGENTS#3. Layering principle]]).
- A declarative front-end that a non-programmer can read, edit and hot-reload.
- Python for logic, so module authors do not need a second language.
- A design system (MD3 tokens, light and dark, high contrast, reduced motion) shared with Tesserae apps.

## What Tesserae Shell is for

A single sentence: **build a desktop shell from YAML and Python, run it next to Plasma, and change it live.**

It is a tool for building shells, not one fixed shell. It ships a default shell as a reference and as the test target for the tool ([[V1 Scope]]).

## Constraints that shape the problem

| Constraint | Consequence |
|---|---|
| It runs beside an installed desktop environment (primary target KDE Plasma on Wayland); it does not replace the compositor, session or window manager. | Shell services such as the notification server and tray watcher are shared D-Bus names with plasmashell; each needs a coexist, replace or proxy decision ([[AGENTS#4. Known constraints and gaps (seed list)]]). |
| tre owns every frame; Python owns intent. | A design that needs per-frame Python is rejected. |
| The design is complete before code is written. | Every area in the checklist in [[AGENTS#12. Design completeness checklist]] needs a note first. |

## Links

- [[Goals and Non-Goals]] · [[Personas and Use Cases]] · [[V1 Scope]] · [[10 Vision]]
- [[ADR-0001 Shell Surface Strategy]]
