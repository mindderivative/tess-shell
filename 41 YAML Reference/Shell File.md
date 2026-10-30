---
title: Shell File
aliases: [_Shell.yaml, Main_Shell.yaml, Shell YAML, _Shell.tdl, Main_Shell.tdl, Shell TDL]
type: yaml-ref
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-29
tags: [yaml-ref, spec/surface, needs-verification]
related: ["[[41 YAML Reference]]", "[[TDL Language]]", "[[Common Keys and Conventions]]", "[[Surface Types]]", "[[Module File]]", "[[ADR-0014 Shell File Language]]"]
depends_on: ["[[Common Keys and Conventions]]", "[[Surface Types]]"]
---

# Shell File

> [!summary]
> A shell file (file-type key `Shell: v1`, suffix `_Shell.tdl`, written in TDL, [[ADR-0014 Shell File Language]]) defines the surfaces on one or more monitors and places modules in them. The whole shell is one such file, or a `Main_Shell.tdl` that imports others. The metadata block, the registry and the monitor selectors are in [[TDL Language]]; this note lists the `Monitor` block and the surface keys. Decided keys come from [[ADR-0007 Shell UI Layer]] and the 2026-10-29 layout rules ([[ADR-0014 Shell File Language#Layout Rules]]); the surface property names mirror tre's `LayerWindow` settings ([[TRE-REQ-001 Layer Surface Window]]) and were accepted by the maintainer on 2026-10-29. Examples are illustrations.

## Structure

```
---
TDL: 0.1
Shell: v1
---

Monitor {
    Name: dp1
    Connector: DP-1
    Children {
        # one file, or a list
        Import: TopBar_Shell.tdl
        Bar {
            Name: top_bar
            Style: Dock_Style.tdl
            # a module is called by its name; Import embeds a module file
            Children {
                Import: [Clock_Module.tdl, Audio_Module.tdl]
            }
        }
        Panel {
            Name: launcher
            Layer: overlay
            Keyboard: exclusive
            Children {
                Import: Applications_Module.tdl
            }
        }
    }
}
```

- A file is the metadata block, then top-level blocks ([[TDL Language#A File]]). The only top-level block of a shell file is `Monitor`.
- `Monitor` holds one monitor's tree. `Name:` is its unique name; a selector binds it to a monitor; `Children` is a block.
- A child is a surface: a block whose head is its type (`Bar`, `Frame`, `Panel`, `Popup`), with a unique `Name:`. `Import:` inside `Children` pulls in surfaces from another `_Shell.tdl`; an imported file takes the importing Monitor's monitor.
- Surfaces are siblings and never nest ([[Common Keys and Conventions#Names and References]]).

## Monitor Keys

| Key                                    | Meaning                                                                                                                                  | Status                                 |
|----------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------|
| `Name`                                 | Required; unique across the shell (full path for repeated uses, see [[ADR-0007 Shell UI Layer#Open items]])                              | Decided (the rule); path form proposed |
| `Index`, `Connector`, `Description`    | The selectors. The meaning of each, `Index: default`, and the rule for a Monitor with no selector are in [[TDL Language#Monitors]]       | Decided (2026-10-29)                   |
| `Children`                             | Surfaces and imports                                                                                                                     | Decided                                |

## Surface Keys

A surface is one of four block types. The head is the type; there is no `Kind:` or `Type:` on it.

| Head    | Surface                         |
|---------|---------------------------------|
| `Bar`   | A surface on one edge           |
| `Frame` | A surface on all four edges     |
| `Panel` | Attached to another surface, or floating |
| `Popup` | A surface hung off another one  |

The details of each are in [[Surface Types]].

| Key              | Meaning                                                                                                                                                                                                                                                       | Applies to        | Status                                                  |
|------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------|---------------------------------------------------------|
| `Name`           | Required; the surface's unique name                                                                                                                                                                                                                           | All               | Decided (2026-10-29)                                    |
| `Layer`          | `background`, `bottom`, `top`, `overlay`                                                                                                                                                                                                                      | All               | Decided (the key)                                       |
| `Style`          | A style file or an inline `Style { }` block                                                                                                                                                                                                                   | All               | Decided                                                 |
| `Children`       | The surface's contents: blocks (containers included) and module uses. `Children` is the only holder; `modules:` is gone (maintainer, 2026-10-26). A module use is written with the module's name as the head ([[Module File#Using a Module]]) | All               | Decided                                                 |
| `Anchor`         | Edges to attach to: `top`, `bottom`, `left`, `right` (one or a list)                                                                                                                                                                                          | Bar, Panel        | Decided (key name accepted 2026-10-29)                  |
| `Size`           | `[width, height]`; `0` stretches between two anchored edges                                                                                                                                                                                                   | Bar, Panel, Popup | Decided (key name accepted 2026-10-29)                  |
| `Exclusive_Zone` | Space reserved along the anchored edge, in pixels. Only allowed on `Layer: top`; on any other layer it is a load error (maintainer, 2026-10-26)                                                                                                              | Bar, Panel, Frame | Rule decided; key accepted 2026-10-29                   |
| `Margin`         | Four-sided offset from the anchored edges                                                                                                                                                                                                                     | Bar, Panel        | Decided (key name accepted 2026-10-29)                  |
| `Keyboard`       | `none`, `on_demand`, `exclusive`                                                                                                                                                                                                                              | All               | Decided (key name accepted 2026-10-29) (`exclusive` used for the launcher) |
| `Input_Region`   | Where input lands: the whole surface, nothing, rectangles, or `auto`                                                                                                                                                                                          | All               | Decided (key name accepted 2026-10-29)                  |
| `Movable`        | A Panel the mouse can move; its position is saved                                                                                                                                                                                                             | Panel             | Decided (key name accepted 2026-10-29)                  |
| `Hidden`         | Start hidden                                                                                                                                                                                                                                                  | All               | Decided (key name accepted 2026-10-29)                  |
| `Attach_To`      | The name of the surface a Panel attaches to                                                                                                                                                                                                                   | Panel             | Decided (key name accepted 2026-10-29) (decided: attachment is by naming the surface) |
| `Anchor_To`      | The name of the surface a Popup hangs off; optional, because the caller's surface is the parent ([[Popup#Parent and anchor]])                                                                                                                                 | Popup             | Decided (key name accepted 2026-10-29)                  |

Tre's names are lowercase (`exclusive_zone`); the shell maps the Capitalised keys to them ([[TDL Language#Names and the Registry]]). Per-type keys (a Frame's side thicknesses and corner shapes, a Bar's span, a Popup's gravity) are listed in the per-type specs once written ([[Surface Types]]).

## Monitors

- A shell file holds one `Monitor` block per monitor, and several may appear in one file (decided 2026-10-29). A monitor no block names gets the `Index: default` block if there is one, and nothing otherwise.
- A surface set for one monitor can be shared by several `Monitor` blocks by importing the same `_Shell.tdl`.
- A Popup opens only on the monitor of the surface that called it ([[Surface Types#Open questions]]).
- `Index:` is a position, not a stable name; `Connector:` and `Description:` are the stable selectors ([[Risk Register]] R-21).

## Errors Specific to Shell Files

- A surface or Monitor with no `Name`, or two with the same name: error, both places named.
- Two `Monitor` blocks that name the same monitor: error, both places named.
- A block head that is not in the registry: error with the list of surface types and block names that fit at that place.
- A file-type key that disagrees with the suffix (`Shell: v1` in `Clock_Module.tdl`): error naming both.
- A module use whose file is not found: error with the search paths tried.
- An `Attach_To` or `Anchor_To` that never resolves: error at load; a target that disappears while running: warning, the surface stays hidden.
- A module with no matching `.py`: error naming both files.

## Open

- [x] Several `root` blocks in one file: now several `Monitor` blocks, allowed (decided 2026-10-29, [[ADR-0014 Shell File Language#Layout Rules]], item 9).
- [x] Where shell files live: `$HOME/.config/tesserae-shell/Shells/`, or the directory `settings.tdl` names (decided 2026-10-27, [[Settings File]]).
- [ ] Which shell file is the top-level one when `Shells/` holds several: proposed `main_shell` in `settings.tdl`, default `Main_Shell.tdl`.
- [x] The names of the surface keys: accepted by the maintainer on 2026-10-29. Their types follow the per-type specs.
- [ ] How a surface lays out its modules (order, spacing, alignment): a surface layout key, or the surface being a container widget.
- [ ] The keys each surface type adds ([[Surface Types]]).
- [x] Whether a surface is named by the word before the brace or by a key: the head is the type and `Name:` is the unique name (ADR-0014, item 6).
- [ ] The order in which the shell tries several monitor selectors on one block (`Connector`, `Description`, `Index` is proposed, ADR-0014 item 15).
- [ ] What an imported `_Shell.tdl` contains: surface blocks that take the importing Monitor, or its own `Monitor` blocks. This note assumes the first, as before 2026-10-29; the maintainer has not said.

## Links

- [[41 YAML Reference]] · [[TDL Language]] · [[Common Keys and Conventions]] · [[Module File]] · [[Surface Types]]
