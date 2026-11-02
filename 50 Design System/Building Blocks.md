---
title: Building Blocks
aliases: [Shell Building Blocks, Blocks]
type: design
status: draft
owner: phil
created: 2026-10-26
updated: 2026-11-01
tags: [design, needs-verification]
related: ["[[50 Design System]]", "[[V1 Widgets]]", "[[Shell Structure]]", "[[Module File]]", "[[ADR-0007 Shell UI Layer]]"]
depends_on: ["[[ADR-0007 Shell UI Layer]]"]
---

# Building Blocks

> [!summary]
> The shell has its own set of building blocks: the primitives that every module is composed from. The maintainer chose the concept on 2026-10-26 (look at how Tesserae builds widgets, look at what tre allows, make blocks geared for a shell) and then gave the set. A block is built in and called by its name as the head of a block (`Text { }`). A module is composed in TDL from blocks and other modules, and is called by its name the same way (`Clock { }`). The names of blocks, surface types and modules are in one registry ([[TDL Language#Names and the Registry]]). The set below is decided; how each block is built on tre, and its properties, are proposals.

## The Blocks (Decided, Maintainer, 2026-10-26)

| Group      | Blocks                                                            | Built on (proposed)                                                                                                                                                                    |
|------------|-------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Containers | Box, FlexBox, Grid, ScrollBox                                     | tre `box` (a Box is a one-cell grid, a FlexBox a flex container, a Grid a grid container); ScrollBox is `scroll_view` (added 2026-11-01); `virtual_list` later ([[Block Reference]]) |
| Typography | Text, TextField, a multi-line variant of TextField                | `text`, `text_input`                                                                                                                                                                   |
| Graphics   | Bitmap (a rasterized bitmap), SVG (a vector graphic)              | `image`, `svg`                                                                                                                                                                         |
| Shapes     | Square, Rectangle, Triangle, Hexagon, Circle, Ellipse, Ring, Path | `path` and `box` with corner radius; Path is a free-form path, added 2026-10-26 for the Frame's concave corners and Panel joins; hit shape per [[Hit Testing for Concave Corners]] |
| Other      | Terminal, Canvas                                                  | `terminal`, `canvas`                                                                                                                                                                   |

- A block needs no name or UID. Calling one from TDL (`Text { }`) makes the shell's Python build it. A `Name:` is optional and gives the block its own unique name (`Text { Name: title }`).
- A block can be placed anywhere: on a surface, in a container or in a module. It is most commonly used inside a module (maintainer, 2026-10-27).
- A container is a block (`FlexBox { }`), not a module and not a separate key. This replaces the earlier idea of a key of its own for containers.
- Blocks are fixed by the shell. Whether a module author can add a block is open.

## Layout, Padding and Margin

A surface or a module passes layout properties to its layout block (`Box`, `FlexBox` or `Grid`) (D35, with `Gap` renamed by D49; [[ADR-0014 Shell File Language#Fourth-Round Decisions (2026-10-30)]]):

| Property  | Value                                      | Meaning                                                                            |
|-----------|--------------------------------------------|------------------------------------------------------------------------------------|
| `Flex`    | `VERTICAL`, `HORIZONTAL`, `NONE`           | How the children are stacked. `NONE` leaves the layout to `Columns` and `Rows`     |
| `Columns` | A whole number                             | The number of columns of a `Grid`                                                  |
| `Rows`    | A whole number                             | The number of rows of a `Grid`                                                     |
| `Spacing` | A whole number of pixels                   | The space between the children of the layout. It is not `Gap`, which is the distance from a surface to what it is attached to |

- `Padding` (four-sided, left, top, right, bottom) exists on every block that has `Children`: transparent space between its children and its four sides (D42). Blocks without `Children` (`Text`, `Bitmap`, `SVG`, the shapes, `Terminal`, `Canvas`) have none.
- `Margin` (four-sided, left, top, right, bottom) is transparent space around the block itself, outside it (D41 to D45). A Bar has none (D41).
- The property set per block is written in [[Block Reference]] (proposed, 2026-11-01).

## The Modules Built from Them (The Maintainer's List)

Composed in TDL, called by name, optionally with Python. The standard set the maintainer sees:

| Module         | What it is                                                                                                                                       | Built mainly from             |
|----------------|--------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------|
| Spacer         | Flexible empty space                                                                                                                             | Box                           |
| Label          | A single line of text, no wrap, not editable                                                                                                     | Text                          |
| TextBox        | Multi-line text, not editable (clarified 2026-10-26)                                                                                             | Text                          |
| TextInput      | A single-line text field, editable                                                                                                               | TextField                     |
| TextEditor     | A multi-line text field, editable (the multi-line TextField variant)                                                                             | TextField, multi-line variant |
| Button         | A pressable control with states                                                                                                                  | Box, Text, Icon               |
| Icon           | A named or file icon                                                                                                                             | SVG, Bitmap                   |
| Image          | An image from png, jpeg, gif or webp                                                                                                             | Bitmap                        |
| List           | A scrolling list, the usual target of a repeater                                                                                                 | Box, FlexBox                  |
| Slider         | A draggable value                                                                                                                                | Box, shapes                   |
| ProgressBar    | A read-only bar                                                                                                                                  | Box                           |
| Menu, MenuItem | Menu content for a popup                                                                                                                         | FlexBox, Button               |
| Expander       | Show or hide children with an animation. A must have (renamed from Revealer, maintainer 2026-11-01)                                                                                             | Box                           |
| Stack          | Layered children in one cell. A Box already does this (R1 of [[Block Reference]]); recommended to drop. Not decided | Box                           |
| Badge          | A count or dot on an icon                                                                                                                        | Circle, Text                  |
| Tooltip        | Hover text                                                                                                                                       | Box, Text                     |
| Toggle         | A switch                                                                                                                                         | Box, Circle                   |
| Checkbox       | A check box. Separate from Toggle: both give an on or off value, but a Toggle is a switch and a Checkbox is a check box (maintainer, 2026-10-27) | Box, Path                     |
| Marquee text   | Scrolling a long text in a small space                                                                                                           | Text                          |

These ship with the shell as a standard set; the shell's own modules are open to being overridden ([[ADR-0007 Shell UI Layer#Open items]]). Which are needed for v1 is in [[V1 Widgets]].

## Names

The module `Text` was a mistake and is now TextBox, so no name is both a block and a module. Image and Icon (modules) sit on Bitmap and SVG (blocks). Label and TextBox are bodies of the Text block and are not editable; TextInput and TextEditor are modules over the TextField block and its multi-line variant and are editable. A block and a module are both called by their name as the block head, and a name registered twice is a load error, except that a user module overrides a shipped one ([[ADR-0014 Shell File Language#File Layout (Decided 2026-10-29)]], [[ADR-0007 Shell UI Layer#Module call, shipped modules and Path (2026-10-26)]]).

## What Tre Offers

From `reference/properties.md`, read 2026-10-26. tre's node kinds: `box`, `text`, `text_input`, `image`, `path`, `svg`, `canvas`, `scroll_view`, `virtual_list`, `terminal`. A canvas's `draw` callback runs when it is created, when its `draw` is set and on `redraw()`, not every frame. tre also has colour, gradients, shadows, corner radii, animation (including layout properties and springs), hit-testing options, accessibility properties and the layer-surface types. It has no widgets and no theme ([[AGENTS#1. What Tesserae Shell is]]).

## What Tesserae Does

From Tesserae's design (`yaml-language.md` sections 3 and 16), local clone commit `0eda3fe`, read 2026-10-26:

- A built-in widget is a Python class that declares its properties (type, default, choices, required, doc), its parts a stylesheet can address (a slider's `track` and `handle`) and the style extras it accepts. An unknown property is an error with a suggestion.
- State is properties (`value`, `selected`, `checked`, `disabled`, `open`); some are `model` properties that the user edits.
- Its built-in list is about sixty provisional widgets that follow Material Design 3 for applications. Most are application UI; a shell needs a smaller, compact, icon-first set.

The shell's blocks keep the declared-properties idea and drop the application widgets.

## Properties, Parts and States

Following Tesserae's idea, each block declares:

- Properties: type, default, allowed values, one line of doc. An unknown property is an error that names the closest ones ([[Common Keys and Conventions]]).
- Parts a style can address (a Slider's `track` and `handle`).
- States (`hovered`, `pressed`, `focused`, `disabled`) that a style can target. Reduced motion and high contrast are handled by the theme ([[Goals and Non-Goals]] G7).
- Events, which the shell handles and TEL does not ([[ADR-0008 Tesserae Expression Language]]).

## Styling a Block

Decided by the maintainer (2026-10-26); the full rules are in [[Style, Theme and Stylesheet Files#Rules]].

- A block is styled by a stylesheet, a style file, or inline `Style`.
- Customising a block means referencing another file or writing inline `Style`. A custom style changes only what it names; it is not a full replacement.
- Priority, lowest to highest: theme, stylesheet, style, inline `Style`.

## Open

- [x] A module author can add a block, in Python, shipped with the module (maintainer, 2026-11-01). The mechanism is a proposal in [[Block Reference#Custom Blocks (R12)]].
- [x] A free-form Path block: added (2026-10-26).
- [x] Whether the listed modules can be built from the listed blocks: the maintainer reports yes, tested on Tesserae (2026-10-26). Expander and Marquee need animated layout and translate properties; Stack needs layered children; Slider, Toggle and Button need pointer and drag events from the blocks.
- [x] Grid: tre has a grid (`display: "grid"`, `grid_template_columns`, `grid_template_rows`, `row_gap`, `column_gap`); the mapping of `Columns`, `Rows` and `Spacing` is in [[Block Reference#Grid]]. Open: the text form of tre's track template.
- [x] The default hit shape of Path and the shape blocks: `painted` (maintainer, 2026-10-27): the reason to use a shape is for the look and for the hit box to be the painted shape. tre 0.5.9 has `hit_shape` `box` (its default) or `painted`; the shell's shape blocks set `painted`. SVG and Canvas are not covered by `hit_shape` ([[Hit Testing for Concave Corners]]).
- [x] How icons are found: the shipped SVG set (a JSON file), then the freedesktop icon theme, then the config `Icons` folder, then the locations a developer lists in the settings file (maintainer, 2026-11-01; [[Block Reference#Icons (R7)]]).
- [x] The state model: data in through `Text` and edits out through `On_Change`, with no two-way binding (R6, maintainer, 2026-11-01).
- [x] Accessibility defaults for each block (roles, labels, keyboard operation) ([[Goals and Non-Goals]] G7): as in [[Block Reference#Accessibility Defaults]] (maintainer, 2026-11-01).

## Links

- [[50 Design System]] · [[V1 Widgets]] · [[Shell Structure]] · [[Module File]]
