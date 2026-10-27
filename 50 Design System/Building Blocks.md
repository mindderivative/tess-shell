---
title: Building Blocks
aliases: [Shell Building Blocks, Blocks]
type: design
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-26
tags: [design, needs-verification]
related: ["[[50 Design System]]", "[[V1 Widgets]]", "[[Shell Structure]]", "[[Module File]]", "[[ADR-0007 Shell UI Layer]]"]
depends_on: ["[[V1 Widgets]]"]
---

# Building blocks

> [!summary]
> The shell has its own set of building blocks: the primitive pieces every module is composed from. The maintainer chose this on 2026-10-26: look at how Tesserae builds widgets, look at what tre allows, and make blocks geared for a shell instead of an application UI. This note records what tre offers, what Tesserae does, and a proposed set of blocks. The concept is decided; the set, the key name and the properties are proposals.

## What the concept means

- A **building block** is a primitive the shell provides, built on tre nodes. A user does not write one. Containers are blocks with children (`Box`, `FlexBox`) and have their own key (decided).
- A **module** is a composed piece: a YAML file that arranges blocks and other modules, with params and an optional Python file ([[ADR-0007 Shell UI Layer#What a module is (2026-10-26)]]).
- Whether the call syntax is one key for both blocks and modules, and whether the word "widget" stays, is open ([[Shell Structure#Widgets, modules and building blocks]]).

## What tre offers

From the tre reference (`reference/properties.md`, read 2026-10-26). Every node is created with `window.create(kind, ...)`. The kinds:

| tre kind | What it is |
|---|---|
| `box` | A layout container with optional fill, stroke, corners and shadows |
| `text` | Shaped, non-editable text |
| `text_input` | Editable text: selection, clipboard, IME, syntax spans, folding, obscuring |
| `image` | Decoded RGBA8 pixels (video is repeated sets) |
| `path` | A vector path |
| `svg` | A whole SVG document |
| `canvas` | Immediate-mode drawing through a painter. The `draw` callback runs when the canvas is created, when its `draw` is set, and on each `redraw()`, not every frame |
| `scroll_view` | Clips and scrolls one child |
| `virtual_list` | Builds only the rows its viewport shows |
| `terminal` | A PTY-backed terminal emulator |

tre also provides colour, gradients, shadows, corner radii, animation (including layout properties and springs), hit-testing options, accessibility properties, and the layer-surface types. It has no widgets and no theme ([[AGENTS#1. What Tesserae Shell is]]).

## What Tesserae does

From Tesserae's design (`yaml-language.md` sections 3 and 16) and guides, local clone commit `0eda3fe`, read 2026-10-26:

- A built-in widget is a Python class that declares its **properties** (type, default, choices, required, doc), its **parts** a stylesheet can address (a slider has a `track` and a `handle`), and the **style extras** it accepts. An unknown property is an error with a suggestion.
- State is properties (`value`, `selected`, `checked`, `disabled`, `open`, ...). Some properties are `model` properties: the user edits them (a field's `value`, a switch's `checked`).
- The built-in list is about sixty provisional widgets that follow Material Design 3 for applications: containers, text, icons, many button variants, cards, lists, trees, navigation rails and drawers, app bars, tabs, chips, date and time pickers, dialogs, sheets, snackbars, carousels and more.

Most of that is application UI. A shell needs a small, compact, icon-first subset with different defaults.

## Proposed v1 blocks

Taken from [[V1 Widgets]] (derived from the surfaces and modules in [[V1 Scope]]), with the tre node each is built from. Names are working names.

| Block | Built from | Needed by | Notes |
|---|---|---|---|
| Box | `box` | Every surface and module | Basic container, no auto-stacking; invisible if unstyled |
| FlexBox | `box` with flex layout | Every surface and module | Auto-stacking, `alignment` vertical or horizontal |
| Spacer | `box` | Bar layout | Flexible empty space |
| Text | `text` | Clock, Workspaces, Tasks, Battery, Network, Media, Applications | Typography from the theme; ellipsis for long text |
| Icon | `svg` or `image` | Tray, Audio, Network, Battery, Media, Tasks, Applications | A named theme icon or a file, tinted by a colour |
| Image | `image` | Media (artwork) | |
| Button | `box` with `text` and icon, states | Workspaces, Tasks, Tray, Audio, Media, Applications | Hover, pressed, focus and disabled states; toggle |
| Slider | `box` composition, pointer handling | Audio (volume), Media (seek) | Parts: track, handle |
| ProgressBar | `box` composition | Battery | Read-only |
| TextField | `text_input` | Applications (search) | |
| List | `virtual_list` or `scroll_view` | Applications, Tasks, Tray overflow | The usual target of a repeater |
| MenuItem, Menu | `box` rows inside a popup | Tray menus, Audio and Network lists | Menu content for popups ([[Surface Types#Special cases]]) |
| Shape | `path` or `svg` | Frame ring, corners, joins, Panel joins | Declarative; hit shape per [[Hit Testing for Concave Corners]] |

## Candidates geared for a shell (not v1 unless a module needs them)

Ideas from what bars, docks and panels do, not from application UIs:

| Candidate | Why a shell wants it |
|---|---|
| Revealer | Show or hide children with an animation, for hover-to-reveal and auto-hide |
| Stack (layered children) | A badge over an icon |
| Badge | A count or dot on an icon (unread, charging) |
| Tooltip | Hover text on a tray or task icon |
| Toggle | A switch in a settings panel |
| Marquee text | Scrolling a long media title in a small space |
| Meter | A battery or volume level, linear or arc |
| Canvas | Custom drawing from a module, called on redraw, not per frame |
| Terminal | tre has a `terminal` kind; a terminal panel is a possible later feature |

## Properties, parts and states

Following Tesserae's idea, each block declares:

- **Properties:** type, default, allowed values, a one-line doc. An unknown property is an error that names the closest properties ([[Common Keys and Conventions]]).
- **Parts** a style can address (a Slider's `track` and `handle`).
- **States** (`hovered`, `pressed`, `focused`, `disabled`) that a style can target, with reduced-motion and high-contrast handled by the theme ([[Goals and Non-Goals]] G7).
- **Events** the shell handles, not TEL ([[ADR-0008 Tesserae Expression Language]]).

## Open

- [ ] The key for blocks and modules: `widget:` for both, or `block:` for blocks ([[Shell Structure#Widgets, modules and building blocks]]).
- [ ] The final v1 set and names; whether any candidate is v1.
- [ ] Whether a user or a module author can add a block (in Python, packaged with a module), or blocks are fixed by the shell.
- [ ] How icons are found (a theme icon set, files, both).
- [ ] The state model: whether input blocks have properties the user edits (Tesserae's `model`) and how that reaches a module.
- [ ] How a block's parts and states appear in a style file ([[Style, Theme and Stylesheet Files]]).
- [ ] Which blocks are accessible by default (roles, labels, keyboard operation) ([[Goals and Non-Goals]] G7).

## Links

- [[50 Design System]] · [[V1 Widgets]] · [[Shell Structure]] · [[Module File]]
