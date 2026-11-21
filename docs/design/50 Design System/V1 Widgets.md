---
title: V1 Widgets
aliases: [Widget List, v1 Widget List, V1 Blocks and Modules]
type: design
status: accepted
owner: phil
created: 2026-10-25
updated: 2026-11-11
tags: [design, spec/widget]
---

# V1 Widgets

> [!NOTE]
> The blocks and standard modules a v1 shell needs, traced to the surfaces and modules in [V1 Scope](../10%20Vision/V1%20Scope.md). The word "widget" is no longer a key or a category: there are building blocks (called with `block:`) and modules (called by name) ([Building Blocks](Building%20Blocks.md), decided 2026-10-26). The note keeps its name so links hold. The rule from [ADR-0007 Shell UI Layer](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md) stands: add one only when a module or surface needs it. The properties, parts, states and events of each standard module are in [Standard Modules](Standard%20Modules.md); the accessibility rules every widget follows are in [Accessibility](../60%20Quality/Accessibility.md).

## Blocks Needed for V1

| Block                                  | Needed by                                                                     |
|----------------------------------------|-------------------------------------------------------------------------------|
| Box, FlexBox                           | Every surface and module                                                      |
| ScrollBox                              | List (Applications results, Tasks, Tray overflow)                             |
| Text                                   | Clock, Workspaces, Tasks, Battery, Network, Media, Applications, TextBox, Marquee text |
| TextField                              | TextInput, TextEditor (its multi-line form)                                   |
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
| TextBox        | V1 by the maintainer's decision, 2026-11-08: multi-line text, not editable |
| TextEditor     | V1 by the maintainer's decision, 2026-11-08: multi-line text, editable (TextField, multi-line) |
| Badge          | V1 by the maintainer's decision, 2026-11-08: a count or dot on an icon |
| Tooltip        | V1 by the maintainer's decision, 2026-11-08: hover text (the hover popup is built through `Popup`) |
| Toggle         | V1 by the maintainer's decision, 2026-11-08: a switch |
| Checkbox       | V1 by the maintainer's decision, 2026-11-08: a check box, separate from Toggle (an on or off value shown as a box and a check) |
| Marquee text   | V1 by the maintainer's decision, 2026-11-08: a long text scrolling in a small space |

Not yet v1 or needed: none of the maintainer's standard set remains outside v1 after his decision of 2026-11-08 (Checkbox was added the same day). The multi-line TextField is V1, with the wrapping options in [Block Reference > TextField](../41%20TDL%20Reference/Block%20Reference.md#textfield). Grid, Terminal and Canvas are blocks with no v1 use yet.

## Notes

- Shadows, elevation, transparency, animation and borders are style properties of containers and shapes, not blocks ([Surface Types](../40%20Specifications/Surfaces/Surface%20Types.md)).
- Accessibility roles, labels and states are set on every block and module; the shell passes them to tre ([TRE-REQ-001 Layer Surface Window > Delivered (tre #195 closed)](../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#delivered-tre-195-closed)).
- tre provides the nodes these are made from; it provides no widgets itself ([Vault Reference > The projects](../00%20Home/Vault%20Reference.md#the-projects)).

## Open Questions

- [x] Which of TextBox, TextEditor, Badge, Tooltip, Toggle, Marquee text and Checkbox are v1: all of them (maintainer, 2026-11-08).
- [x] Which text-input behaviour TextField needs for v1: single-line and multi-line (maintainer, 2026-11-08). Wrapping: `Wrap` means word wrapping for now and character wrapping comes later; a single-line field has horizontal scroll or an ellipsis, because wrapping a single line makes no sense; a multi-line field wraps by word or does not. The key names are proposed in [M4 Brief](../00%20Home/M4%20Brief.md) W3.
- [x] The properties and states of each: [Block Reference](../41%20TDL%20Reference/Block%20Reference.md); proposals R1 to R11 decided 2026-11-01. The v1 block set is R11.

## Questions After Testing

1. [x] Do composition and input methods work with a real input method on layer surfaces? The check was not performed and the maintainer does not care about it (2026-11-11); it stays untested.
2. [x] Does tre's `text_input` support each text-input behaviour (single-line scroll or ellipsis, multi-line word wrap or none)? Yes with tre 0.6.6 (TRE-REQ-016, verified headless by the code session, not repeated in the vault), and the maintainer's KWin check of the fields passed (M4a rows 15 to 20, 2026-11-11).

## Links

- [V1 Scope](../10%20Vision/V1%20Scope.md) · [Surface Types](../40%20Specifications/Surfaces/Surface%20Types.md) · [Building Blocks](Building%20Blocks.md) · [50 Design System](50%20Design%20System.md)
