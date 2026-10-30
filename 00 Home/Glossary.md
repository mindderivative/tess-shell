---
title: Glossary
aliases: [Terms]
type: moc
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-29
tags: [moc]
related: ["[[Index]]", "[[Home]]"]
depends_on: []
---

# Glossary

Each term is defined here in a line and linked to the note that owns it.

| Term                  | Meaning                                                                                                                                                                                                                        | Owner note                              |
|-----------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------|
| Bar                   | A surface attached to an edge that reserves space (a dock, top bar or side bar)                                                                                                                                                | [[Surface Types]] |
| Frame                 | A surface around the whole screen that reserves space on every side                                                                                                                                                            | [[Surface Types]] |
| Edge                  | An edge of the screen, however thick, starting at the screen edge; the Frame's `edges` key. Not a "side", which would suggest the half of the screen past the middle                                                           | [[Frame]] |
| Panel                 | The multi-purpose surface: attached to a frame, a bar or another surface, or floating                                                                                                                                          | [[Surface Types]] |
| Popup                 | A surface anchored to a shell surface and rendered like an overlay; a menu or flyout                                                                                                                                           | [[Surface Types]] |
| OSD                   | On-screen display: a small overlay that appears briefly to confirm an action, such as a volume bar when a volume key is pressed, then disappears on its own. Built as a Panel                                                  | [[V1 Scope]] |
| Layer surface         | A Wayland surface placed by the compositor on a stacking layer, with edges, margins and reserved space (`zwlr_layer_shell_v1`)                                                                                                 | [[TRE-REQ-001 Layer Surface Window]] |
| Layer (stacking)      | background, bottom, top or overlay: where a layer surface sits among windows                                                                                                                                                   | [[TRE-REQ-001 Layer Surface Window]] |
| Layer (tre in-window) | A node drawn over a window's own content with `show_layer`; a different thing from the stacking layer                                                                                                                          | [[TRE-REQ-001 Layer Surface Window]] |
| Exclusive zone        | Screen space a surface reserves so maximised windows stop short of it                                                                                                                                                          | [[TRE-REQ-001 Layer Surface Window]] |
| Output, monitor       | A screen the compositor reports; matched by connector name (`DP-1`)                                                                                                                                                            | [[V1 Scope]] |
| Module                | A composed piece of the shell: a layout file in TDL (blocks, other modules and expressions, with `params:`), a style file, and optionally a Python file for its logic. Called by its unique name; the word survives as `type: Module` |                                         |
| Building block        | A built-in primitive the shell provides (Box, FlexBox, Grid, Text, TextField, Bitmap, SVG, shapes, Terminal, Canvas), called with `block:`; needs no name or UID                                                               | [[ADR-0007 Shell UI Layer]] |
| Shell file            | A `.tdl` file with the required first keys `TDL:` and `shell:`, and a `type:`                                                                                                                                                                       | [[ADR-0007 Shell UI Layer]] |
| UID                   | A shell-wide UUIDv7 written into an entry-point file and kept in the registry                                                                                                                                                  | [[ADR-0007 Shell UI Layer]] |
| Registry              | `registry.json` in the shell's config directory, mapping UIDs to entries                                                                                                                                                       | [[ADR-0007 Shell UI Layer]] |
| tre                   | The Tesserae Rendering Engine: Rust, GPU, mechanism only                                                                                                                                                                       | [[AGENTS]] |
| Tesserae              | The separate declarative UI framework; not a dependency of the shell                                                                                                                                                           | [[ADR-0006 Shell Independent of Tesserae UI]] |
| TEL                   | Tesserae Expression Language: a separate Python library for expressions in configuration files and Python (the shell's TDL slots)                                                                                                                                  | [[ADR-0008 Tesserae Expression Language]] |
| TDL                   | Tesserae Data Language: the structure-only data language for shell files (blocks, lists, imports, expression slots), in place of YAML. Expressions in it are TEL's                                                                                          | [[ADR-0014 Shell File Language]] |
