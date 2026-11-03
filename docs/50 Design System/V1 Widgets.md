---
title: V1 Widgets
aliases: [Widget List, v1 Widget List, V1 Blocks and Modules]
type: design
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-26
tags: [design, spec/widget]
---

# V1 Widgets

> [!NOTE]
> The blocks and standard modules a v1 shell needs, traced to the surfaces and modules in [V1 Scope](../10%20Vision/V1%20Scope.md). The word "widget" is no longer a key or a category: there are building blocks (called with `block:`) and modules (called by name) ([Building Blocks](Building%20Blocks.md), decided 2026-10-26). The note keeps its name so links hold. The rule from [ADR-0007 Shell UI Layer](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md) stands: add one only when a module or surface needs it.

## Blocks Needed for V1

| Block                                  | Needed by                                                                     |
|----------------------------------------|-------------------------------------------------------------------------------|
| Box, FlexBox                           | Every surface and module                                                      |
| ScrollBox                              | List (Applications results, Tasks, Tray overflow)                             |
| Text                                   | Clock, Workspaces, Tasks, Battery, Network, Media, Applications               |
| TextField                              | TextInput, and TextBox through its multi-line variant                         |
| Bitmap, SVG                            | Tray, Audio, Network, Battery, Media, Tasks, Applications (icons and artwork) |
| Shapes (Rectangle, Circle, Ring, Path) | Frame ring and corners, Panel joins (Path), Toggle, Badge                     |

## Standard Modules Needed for V1

| Module         | Needed by                                                             |
|----------------|-----------------------------------------------------------------------|
| Label          | Clock, Workspaces, Tasks, Battery, Network                            |
| TextInput      | Applications (launcher search)                                        |
| Icon           | Tray, Audio, Network, Battery, Media, Tasks, Applications             |
| Image          | Media (artwork)                                                       |
| Button         | Workspaces, Tasks, Tray, Audio (mute), Media (controls), Applications |
| Slider         | Audio (volume), Media (seek)                                          |
| ProgressBar    | Battery                                                               |
| List           | Applications (results), Tasks, Tray overflow                          |
| Menu, MenuItem | Tray menus, Audio (device list), Network (network list)               |
| Spacer         | Bar layout (left, centre and right groups)                            |
| Expander       | A must have (maintainer, 2026-10-26; renamed from Revealer 2026-11-01): hover-to-reveal and auto-hide |

Also in the maintainer's standard set but not yet needed by a v1 module: TextBox (multi-line text, not editable), TextEditor (multi-line, editable), Checkbox, Badge, Tooltip, Toggle, Marquee text. Grid, the multi-line TextField, Terminal and Canvas are blocks with no v1 use yet.

## Notes

- Shadows, elevation, transparency, animation and borders are style properties of containers and shapes, not blocks ([Surface Types](../40%20Specifications/Surfaces/Surface%20Types.md)).
- Accessibility roles, labels and states are set on every block and module; the shell passes them to tre ([TRE-REQ-001 Layer Surface Window > Delivered (tre #195 closed)](../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#delivered-tre-195-closed)).
- tre provides the nodes these are made from; it provides no widgets itself (AGENTS > 1. What Tesserae Shell is).

## Open Questions

- [ ] Which of TextBox, TextEditor, Badge, Tooltip, Toggle and Marquee text are v1.
- [ ] Which text-input behaviour TextField needs for v1 (composition and input methods work on layer surfaces in tre 0.5.8; no real input method was tested).
- [x] The properties and states of each: [Block Reference](../41%20TDL%20Reference/Block%20Reference.md); proposals R1 to R11 decided 2026-11-01. The v1 block set is R11.

## Links

- [V1 Scope](../10%20Vision/V1%20Scope.md) · [Surface Types](../40%20Specifications/Surfaces/Surface%20Types.md) · [Building Blocks](Building%20Blocks.md) · [50 Design System](50%20Design%20System.md)
