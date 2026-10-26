---
title: V1 Widgets
aliases: [Widget List, v1 Widget List]
type: design
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [design, spec/widget]
related: ["[[V1 Scope]]", "[[ADR-0007 Shell UI Layer]]", "[[Surface Types]]", "[[50 Design System]]"]
depends_on: ["[[V1 Scope]]"]
---

# v1 widgets

> [!summary]
> The widgets a v1 view can use, taken from the surfaces and modules in [[V1 Scope]]. A widget is here only if a module or surface needs it ([[ADR-0007 Shell UI Layer]]). Names are working names; the final names and keys are set in `41 YAML Reference/`. Repeaters and conditions are not widgets: they belong to the expression language ([[ADR-0008 Tesserae Expression Language]]).

## The list

Widgets are used inside a module's layout YAML (a module brings its own widgets) and in a surface's own layout. Containers are `Box` (no auto-stacking) and `FlexBox` (auto-stacking, `alignment` vertical or horizontal), decided by the maintainer on 2026-10-26 ([[ADR-0007 Shell UI Layer#Keys that say what a thing is (2026-10-26)]]). A widget is written `Text:` or `widget: Text`.

| Widget | What it is | Needed by |
|---|---|---|
| Box | A basic container with no auto-stacking: unstyled it is invisible, fully styled it has background, border, corner radius, shadow and opacity | Every surface: Bar, Panel, Popup, widget groups |
| FlexBox | A container that stacks its children automatically, `alignment` vertical or horizontal, with gap and alignment | Every surface and module |
| Spacer | Flexible empty space that pushes siblings apart | Bar layout (left, centre, right groups) |
| Text | A line or block of text, with a typography token | Clock, Workspaces, Tasks, Battery, Network, Media, Applications |
| Icon | A named or file icon, tinted by a colour token | Tray, Audio, Network, Battery, Media, Tasks, Applications |
| Image | A bitmap | Media (artwork) |
| Button | A pressable control with hover and focus states | Workspaces, Tasks, Tray, Audio (mute), Media (controls), Applications |
| Slider | A draggable value in a range | Audio (volume), Media (seek) |
| ProgressBar | A read-only bar for a value in a range | Battery |
| TextField | Editable single-line text with caret and clipboard | Applications (launcher search) |
| List | A scrolling column of items; the usual target of a repeater | Applications (results), Tasks, Tray overflow |
| Menu, MenuItem, MenuSeparator | A popup menu and its entries, with submenus | Tray menus, Audio (device list), Network (network list) |
| Shape | A drawn path: fill, stroke, concave and convex curves | Frame (ring, corners, joins), Panel joins |

## Not yet needed

No module needs these today. Add one only when a module does.

| Candidate | Would serve |
|---|---|
| Stack (children layered in one cell) | A badge over an icon |
| Tooltip | Hover text on a tray icon |
| Toggle | A switch in a settings panel |
| Chart, Calendar, Video | A system monitor, a date picker, a media view |
| Divider | A visual rule between groups (a Box can do it today) |

## Notes

- Shadows, elevation, transparency, animation and borders are properties of Box and Shape, not separate widgets ([[Surface Types]]).
- Accessibility roles, labels and states are set on every widget; the shell passes them to tre ([[TRE-REQ-001 Layer Surface Window#Delivered (tre #195 closed)]]).
- tre provides the nodes these widgets are made from; it provides no widgets itself ([[AGENTS#1. What Tesserae Shell is]]).

## Open questions

- [ ] Whether Menu is a widget or a Popup content template.
- [ ] Which text-input behaviour TextField needs for v1 (composition and input methods work on layer surfaces in tre 0.5.8; no real input method was tested).
- [ ] The widget keys and states, once the view format is written.

## Links

- [[V1 Scope]] · [[Surface Types]] · [[ADR-0007 Shell UI Layer]] · [[50 Design System]]
