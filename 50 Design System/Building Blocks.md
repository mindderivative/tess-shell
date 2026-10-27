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
depends_on: ["[[ADR-0007 Shell UI Layer]]"]
---

# Building blocks

> [!summary]
> The shell has its own set of building blocks: the primitives that every module is composed from. The maintainer chose the concept on 2026-10-26 (look at how Tesserae builds widgets, look at what tre allows, make blocks geared for a shell) and then gave the set. A block is built in and called with `block:`. A module is composed in YAML from blocks and other modules, and is called by its unique name. The set below is decided; how each block is built on tre, and its properties, are proposals.

## The blocks (decided, maintainer, 2026-10-26)

| Group | Blocks | Built on (proposed) |
|---|---|---|
| Containers | Box, FlexBox, Grid | tre `box`; FlexBox with flex layout; Grid needs checking against tre's layout #needs-verification |
| Typography | Text, TextField, a multi-line variant of TextField | `text`, `text_input` |
| Graphics | Bitmap (a rasterized bitmap), SVG (a vector graphic) | `image`, `svg` |
| Shapes | Square, Rectangle, Triangle, Hexagon, Circle, Ellipse, Ring | `path` and `box` with corner radius; hit shape per [[Hit Testing for Concave Corners]] |
| Other | Terminal, Canvas | `terminal`, `canvas` |

- A block needs no name or UID. Calling one from YAML (`block: Text`) makes the shell's Python build it.
- A container is a block (`block: FlexBox`), not a module and not a separate key. This replaces the earlier idea of a key of its own for containers.
- Blocks are fixed by the shell. Whether a module author can add a block is open.

## The modules built from them (the maintainer's list)

Composed in YAML, called by name, optionally with Python. The standard set the maintainer sees:

| Module | What it is | Built mainly from |
|---|---|---|
| Spacer | Flexible empty space | Box |
| Label | A single line of text, no wrap | Text |
| Text | Multi-line text that wraps | Text |
| Button | A pressable control with states | Box, Text, Icon |
| Icon | A named or file icon | SVG, Bitmap |
| Image | An image from png, jpeg, gif or webp | Bitmap |
| List | A scrolling list, the usual target of a repeater | Box, FlexBox |
| Slider | A draggable value | Box, shapes |
| ProgressBar | A read-only bar | Box |
| Menu, MenuItem | Menu content for a popup | FlexBox, Button |
| Revealer | Show or hide children with an animation. A must have | Box |
| Stack | Layered children in one cell | Box |
| Badge | A count or dot on an icon | Circle, Text |
| Tooltip | Hover text | Box, Text |
| Toggle | A switch | Box, Circle |
| Marquee text | Scrolling a long text in a small space | Text |

These ship with the shell as a standard set; the shell's own modules are open to being overridden ([[ADR-0007 Shell UI Layer#Open items]]). Which are needed for v1 is in [[V1 Widgets]].

## Names that appear in both lists

Text, and the pairs Image with Bitmap and Icon with SVG, appear as a block and as a module. The key tells them apart: `block: Text` is the block; the module is called by its name. Both exist because the module adds behaviour (wrapping, a variant, a fallback). The registry holds the module name `Text`, so no other module can use it.

## What tre offers

From `reference/properties.md`, read 2026-10-26. tre's node kinds: `box`, `text`, `text_input`, `image`, `path`, `svg`, `canvas`, `scroll_view`, `virtual_list`, `terminal`. A canvas's `draw` callback runs when it is created, when its `draw` is set and on `redraw()`, not every frame. tre also has colour, gradients, shadows, corner radii, animation (including layout properties and springs), hit-testing options, accessibility properties and the layer-surface types. It has no widgets and no theme ([[AGENTS#1. What Tesserae Shell is]]).

## What Tesserae does

From Tesserae's design (`yaml-language.md` sections 3 and 16), local clone commit `0eda3fe`, read 2026-10-26:

- A built-in widget is a Python class that declares its properties (type, default, choices, required, doc), its parts a stylesheet can address (a slider's `track` and `handle`) and the style extras it accepts. An unknown property is an error with a suggestion.
- State is properties (`value`, `selected`, `checked`, `disabled`, `open`); some are `model` properties that the user edits.
- Its built-in list is about sixty provisional widgets that follow Material Design 3 for applications. Most are application UI; a shell needs a smaller, compact, icon-first set.

The shell's blocks keep the declared-properties idea and drop the application widgets.

## Properties, parts and states

Following Tesserae's idea, each block declares:

- Properties: type, default, allowed values, one line of doc. An unknown property is an error that names the closest ones ([[Common Keys and Conventions]]).
- Parts a style can address (a Slider's `track` and `handle`).
- States (`hovered`, `pressed`, `focused`, `disabled`) that a style can target. Reduced motion and high contrast are handled by the theme ([[Goals and Non-Goals]] G7).
- Events, which the shell handles and TEL does not ([[ADR-0008 Tesserae Expression Language]]).

## Styling a block

Decided by the maintainer (2026-10-26); the full rules are in [[Style, Theme and Stylesheet Files#Rules]].

- A block is styled by a stylesheet, a style file, or inline `style:`.
- Customising a block means referencing another file or writing inline `style:`. A custom style changes only what it names; it is not a full replacement.
- Priority, lowest to highest: theme, stylesheet, style, inline `style:`.

## Open

- [ ] Whether a module author can add a block (in Python, shipped with a module), or blocks are fixed.
- [ ] A free-form Path block, for the Frame's concave corners and Panel joins ([[ADR-0007 Shell UI Layer#Open items]]).
- [ ] Whether the listed modules can be built from the listed blocks: Revealer and Marquee need animated layout and translate properties; Stack needs layered children; Slider, Toggle and Button need pointer and drag events from the blocks.
- [ ] Grid: what it offers against tre's layout.
- [ ] How icons are found (a theme icon set, files, both).
- [ ] The state model: whether input blocks have properties the user edits (Tesserae's `model`) and how that reaches a module.
- [ ] Accessibility defaults for each block (roles, labels, keyboard operation) ([[Goals and Non-Goals]] G7).

## Links

- [[50 Design System]] · [[V1 Widgets]] · [[Shell Structure]] · [[Module File]]
