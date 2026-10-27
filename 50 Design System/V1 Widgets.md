---
title: V1 Widgets
aliases: [Widget List, v1 Widget List, V1 Blocks and Modules]
type: design
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-26
tags: [design, spec/widget]
related: ["[[V1 Scope]]", "[[ADR-0007 Shell UI Layer]]", "[[Surface Types]]", "[[50 Design System]]", "[[Building Blocks]]"]
depends_on: ["[[V1 Scope]]", "[[Building Blocks]]"]
---

# V1 widgets

> [!summary]
> The blocks and standard modules a v1 shell needs, traced to the surfaces and modules in [[V1 Scope]]. The word "widget" is no longer a key or a category: there are building blocks (called with `block:`) and modules (called by name) ([[Building Blocks]], decided 2026-10-26). The note keeps its name so links hold. The rule from [[ADR-0007 Shell UI Layer]] stands: add one only when a module or surface needs it.

## Blocks needed for v1

| Block | Needed by |
|---|---|
| Box, FlexBox | Every surface and module |
| Text | Clock, Workspaces, Tasks, Battery, Network, Media, Applications |
| TextField | TextInput, and TextBox through its multi-line variant |
| Bitmap, SVG | Tray, Audio, Network, Battery, Media, Tasks, Applications (icons and artwork) |
| Shapes (Rectangle, Circle, Ring, Path) | Frame ring and corners, Panel joins (Path), Toggle, Badge |

## Standard modules needed for v1

| Module | Needed by |
|---|---|
| Label | Clock, Workspaces, Tasks, Battery, Network |
| TextInput | Applications (launcher search) |
| Icon | Tray, Audio, Network, Battery, Media, Tasks, Applications |
| Image | Media (artwork) |
| Button | Workspaces, Tasks, Tray, Audio (mute), Media (controls), Applications |
| Slider | Audio (volume), Media (seek) |
| ProgressBar | Battery |
| List | Applications (results), Tasks, Tray overflow |
| Menu, MenuItem | Tray menus, Audio (device list), Network (network list) |
| Spacer | Bar layout (left, centre and right groups) |
| Revealer | A must have (maintainer, 2026-10-26): hover-to-reveal and auto-hide |

Also in the maintainer's standard set but not yet needed by a v1 module: TextBox (multi-line text, not editable), TextEditor (multi-line, editable), Stack, Badge, Tooltip, Toggle, Marquee text. Grid, the multi-line TextField, Terminal and Canvas are blocks with no v1 use yet.

## Notes

- Shadows, elevation, transparency, animation and borders are style properties of containers and shapes, not blocks ([[Surface Types]]).
- Accessibility roles, labels and states are set on every block and module; the shell passes them to tre ([[TRE-REQ-001 Layer Surface Window#Delivered (tre #195 closed)]]).
- tre provides the nodes these are made from; it provides no widgets itself ([[AGENTS#1. What Tesserae Shell is]]).

## Open questions

- [ ] Which of TextBox, TextEditor, Stack, Badge, Tooltip, Toggle and Marquee text are v1.
- [ ] Which text-input behaviour TextField needs for v1 (composition and input methods work on layer surfaces in tre 0.5.8; no real input method was tested).
- [ ] The properties and states of each, once the view format is written ([[Building Blocks]]).

## Links

- [[V1 Scope]] · [[Surface Types]] · [[Building Blocks]] · [[50 Design System]]
