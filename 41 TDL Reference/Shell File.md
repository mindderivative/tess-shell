---
title: Shell File
aliases: [_Shell.yaml, Main_Shell.yaml, Shell YAML, _Shell.tdl, Main_Shell.tdl, Shell TDL]
type: tdl-ref
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-30
tags: [tdl-ref, spec/surface, needs-verification]
related: ["[[41 TDL Reference]]", "[[TDL Language]]", "[[Common Keys and Conventions]]", "[[Surface Types]]", "[[Module File]]", "[[ADR-0014 Shell File Language]]"]
depends_on: ["[[Common Keys and Conventions]]", "[[Surface Types]]"]
---

# Shell File

> [!summary]
> A shell file (root block `Shell { }`, suffix `_Shell.tdl`, written in TDL, [[ADR-0014 Shell File Language]]) defines the surfaces on one or more monitors and places modules in them. The whole shell is one such file, or a `Main_Shell.tdl` that imports others. The metadata block, the registry and the monitor selectors are in [[TDL Language]]; this note lists the `Monitor` block and the surface keys. Decided keys come from [[ADR-0007 Shell UI Layer]] and the 2026-10-29 layout rules ([[ADR-0014 Shell File Language#Layout Rules]]); the surface property names mirror tre's `LayerWindow` settings ([[TRE-REQ-001 Layer Surface Window]]) and were accepted by the maintainer on 2026-10-29. Examples are illustrations.

## Structure

```
---
TDL: 0.1
TEL: 0.1
TRE: 0.5.9
Shell: 0.1
Name: Root_Shell
---

Shell {
    Monitor {
        Name: DP1
        Connector: DP-1
        Children {
            # one file, or a list
            Import: TopBar_Shell.tdl
            Bar {
                Name: Top_Bar
                Edge: TOP
                Width: EXPAND
                Height: 32
                Gap: 4
                Style: Dock_Style.tdl
                # a module is called by its name; Import embeds a module file
                Children {
                    Import: [Clock_Module.tdl, Audio_Module.tdl]
                }
            }
            Panel {
                Name: Launcher
                Layer: OVERLAY
                Keyboard: EXCLUSIVE
                Anchor: [TOP, LEFT]
                Offset: [24, 40, 0, 0]
                Padding: [8, 8, 8, 8]
                Children {
                    Import: Applications_Module.tdl
                }
            }
        }
    }
    Monitor {
        Name: Others
        Index: default
        Children {
            Import: TopBar_Shell.tdl
        }
    }
}
```

- A file is the metadata block, then one root block ([[TDL Language#A File]]). The root block of a shell file is `Shell { }`; it holds `Monitor` blocks. The metadata keys (`TDL`, the version pins, `Name`, `UID`) are in [[TDL Language#The Metadata Block]]. The `Name:` is the root of the dotted path (`Root_Shell.DP1.Top_Bar`).
- `Monitor` holds one monitor's tree. `Name:` is its unique name; a selector binds it to a monitor; `Children` is a block.
- The Panel's `Offset: [24, 40, 0, 0]` is left 24, top 40 (left, top, right, bottom). The shell passes tre `margin` in tre's order, top, right, bottom, left.
- A child is a surface: a block whose head is its type (`Bar`, `Frame`, `Panel`, `Popup`), with a unique `Name:`. `Import:` inside `Children` pulls in surfaces from another `_Shell.tdl`. An imported file holds surface blocks only, sits under a Monitor's `Children` and takes that Monitor's monitor (D22 in [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]).
- Surfaces are siblings and never nest ([[Common Keys and Conventions#Names and References]]).

## Monitor Keys

| Key                                    | Meaning                                                                                                                                  | Status                                 |
|----------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------|
| `Name`                                 | Required; unique across the shell (full path for repeated uses, see [[ADR-0007 Shell UI Layer#Open items]])                              | Decided (the rule); path form proposed |
| `Index`, `Connector`, `Description`    | The selectors. The meaning of each, `Index: default`, and the rule for a Monitor with no selector and the order in which several selectors are tried are in [[TDL Language#Monitors (Shell Schema)]]       | Decided (2026-10-29)                   |
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
| `Layer`          | `BACKGROUND`, `BOTTOM`, `TOP`, `OVERLAY`                                                                                                                                                                                                                      | All               | Decided (the key)                                       |
| `Style`          | A style file or an inline `Style { }` block                                                                                                                                                                                                                   | All               | Decided                                                 |
| `Children`       | The surface's contents: blocks (containers included) and module uses. `Children` is the only holder; `modules:` is gone (maintainer, 2026-10-26). A module use is written with the module's name as the head ([[Module File#Using a Module]]) | All               | Decided                                                 |
| `Edge`           | The edge a Bar attaches to: `TOP`, `BOTTOM`, `LEFT`, `RIGHT`                                                                                                                                                                                                  | Bar               | Decided (2026-10-30; replaces the raw `Anchor`)        |
| `Width`, `Height` | Pixels, `50%`, `AUTO` (shrink to content on that axis) or `EXPAND` (stretch edge to edge along the attached Edge). A top Bar with `Height: EXPAND` cannot stretch: it resolves to `Max_Height`, else `Min_Height`, else 0 px ([[TDL Language#Sizes (Shell Schema)]])                                                                  | Bar               | Decided (D34, D46)                                      |
| `Max_Width`, `Max_Height`, `Min_Width`, `Min_Height` | Bounds on the size, in pixels                                                                                                                                                                                                                 | Bar               | Decided (D34)                                           |
| `Alignment`      | Where the Bar sits along its Edge: `START`, `CENTER`, `END`                                                                                                                                                                                                   | Bar               | Decided (2026-10-30)                                    |
| `Offset`         | A Bar: one number that moves it along the Edge, positive or negative. A Panel: four-sided (left, top, right, bottom), positions it from its anchored edges; this replaces the Panel's old `Margin` (D51)                                                    | Bar, Panel        | Decided (D51)                                           |
| `Gap`            | The distance to what the surface is attached to. A Bar: one number, the space between the Edge and the Bar. A Popup: to its anchor. A Panel: to a target that is not a Frame (D49). Never a layout's child spacing, which is `Spacing`                       | Bar, Popup, Panel | Decided (D49)                                           |
| `Anchor`         | Edges a Panel attaches to when floating: `TOP`, `BOTTOM`, `LEFT`, `RIGHT` (one or a list)                                                                                                                                                                      | Panel             | Decided (key name accepted 2026-10-29)                  |
| `Size`           | `[width, height]` (a length is a whole number or `<int>%`, D6); `0` stretches between two anchored edges                                                                                                                                                       | Panel, Popup      | Decided (key name accepted 2026-10-29)                  |
| `Exclusive_Zone` | Space reserved along the attached edge, in pixels; a Bar's zone includes its `Gap`. Only allowed on `Layer: TOP`; on any other layer it is a load error (maintainer, 2026-10-26)                                                                               | Bar, Panel, Frame | Rule decided; key accepted 2026-10-29                   |
| `Auto_Hide`, `Auto_Hide_Delay`, `Reveal_Key`, `Reserve` | The Bar's hide and reserve behaviour; details in [[Surface Types]]                                                                                                                                                                             | Bar               | Kept from the earlier layout                            |
| `Margin`         | Transparent space around the element itself; four-sided (left, top, right, bottom), or named sides (`Margin { Top: 8, Left: 24 }`, D7). A Bar has no `Margin`. A Panel attached to a Frame: `Margin` on the sides facing the Frame separates the two, and with a margin there they do not meld (the Frame edge continues straight and the Panel's corners round as a floating Panel's do); with no margin they meld. A Frame: space between its outer sides and the display edge; it adds to the Frame's size (Thickness 10 with `Margin: [5, 5, 5, 5]` is 15 per side, 17 with a 2 px border, and the reserved zone is that total) | Panel, Frame      | Decided (D41 to D45)                                    |
| `Padding`        | Transparent space between the children and the element's four sides; four-sided (left, top, right, bottom). On every element that has `Children`. A Frame's `Padding` applies only to a side used as a strip (a side whose `Children` are enabled)         | Bar, Panel, Frame, Popup | Decided (D41 to D45)                              |
| `Attach_To`, `Attach`, `Align` | A Panel attached to a non-Frame target names it (`Attach_To`), the side (`Attach`: `TOP`, `BOTTOM`, `LEFT`, `RIGHT`) and the alignment along it (`Align`: `START`, `CENTER`, `END`). A Popup keeps `Attach`, `Align` and `Gap` (see `Gap`)         | Panel, Popup      | Decided (key names accepted 2026-10-29; D49)            |
| `Keyboard`       | `NONE`, `ON_DEMAND`, `EXCLUSIVE`                                                                                                                                                                                                                              | All               | Decided (key name accepted 2026-10-29) (`EXCLUSIVE` used for the launcher) |
| `Input_Region`   | Where input lands: the whole surface, nothing, rectangles, or `auto`                                                                                                                                                                                          | All               | Decided (key name accepted 2026-10-29)                  |
| `Movable`        | A Panel the mouse can move; its position is saved                                                                                                                                                                                                             | Panel             | Decided (key name accepted 2026-10-29)                  |
| `Hidden`         | Start hidden                                                                                                                                                                                                                                                  | All               | Decided (key name accepted 2026-10-29)                  |
| `Attach_To`      | The name of the surface a Panel attaches to (decided: attachment is by naming the surface); see also the row above                                                                                                                                            | Panel             | Decided (key name accepted 2026-10-29)                  |
| `Anchor_To`      | The name of the surface a Popup hangs off; optional, because the caller's surface is the parent ([[Popup#Parent and anchor]])                                                                                                                                 | Popup             | Decided (key name accepted 2026-10-29)                  |

A Bar with a resolved size of 0 on the axis it is attached along is not created: the shell warns, names the Bar and says to set `Min_Height` (or `Min_Width`). The check runs at creation only and does not stop hide, peek, expand or contract of a Bar or Frame strip (D46).

The shell maps the TDL keys to tre's `LayerWindow` settings (tre-side names, lowercase, in tre's order):

| TDL (this file)                                          | tre side                                                                                              |
|----------------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| `Edge`, `Width`, `Height`, `Alignment`, `Offset`, `Gap` (Bar) | `anchor`, `size` and `margin`; the exact mapping is open, like the Panel attachment geometry (#needs-verification) |
| `Offset` (Panel, left, top, right, bottom)               | `margin` (top, right, bottom, left); the shell reorders                                               |
| `Exclusive_Zone`                                         | `exclusive_zone`                                                                                      |
| `Layer`, `Keyboard` (`OVERLAY`, `EXCLUSIVE`)             | `layer`, `keyboard` (`overlay`, `exclusive`)                                          |

Per-type keys (a Frame's side thicknesses and corner shapes, a Popup's gravity) are listed in the per-type specs once written ([[Surface Types]]). Names are Capitalised here and lowercase in tre ([[TDL Language#Names and the Registry]]).

## Monitors

- A shell file holds one `Monitor` block per monitor, and several may appear in one file (decided 2026-10-29). A monitor no block names gets the `Index: default` block if there is one, and nothing otherwise.
- A surface set for one monitor can be shared by several `Monitor` blocks by importing the same `_Shell.tdl`, which holds surface blocks only (D22).
- A Popup opens only on the monitor of the surface that called it ([[Surface Types#Open questions]]).
- `Index:` is a position, not a stable name; `Connector:` and `Description:` are the stable selectors ([[Risk Register]] R-21).

## Errors Specific to Shell Files

- A surface or Monitor with no `Name`, or two with the same name: error, both places named.
- Two `Monitor` blocks that name the same monitor: error, both places named.
- A block head that is not in the registry: error with the list of surface types and block names that fit at that place.
- A root block that disagrees with the suffix (`Shell { }` in `Clock_Module.tdl`): error naming both.
- A module use whose file is not found: error with the search paths tried.
- An `Attach_To` or `Anchor_To` that never resolves: error at load; a target that disappears while running: warning, the surface stays hidden.
- A module with no matching `.py`: error naming both files.

## Open

- [x] Several `root` blocks in one file: now several `Monitor` blocks, allowed (decided 2026-10-29, [[ADR-0014 Shell File Language#Layout Rules]], item 9).
- [x] Where shell files live: `$HOME/.config/tesserae-shell/Shells/`, or the directory `settings.tdl` names (decided 2026-10-27, [[Settings File]]).
- [ ] Which shell file is the top-level one when `Shells/` holds several: proposed `Main_Shell` in `settings.tdl` ([[Settings File]]), default `Main_Shell.tdl`.
- [x] The names of the surface keys: accepted by the maintainer on 2026-10-29. Their types follow the per-type specs.
- [ ] How a surface lays out its modules (order, spacing, alignment): a surface layout key, or the surface being a container widget.
- [ ] The keys each surface type adds ([[Surface Types]]).
- [ ] How `Edge`, `Width`, `Height`, `Alignment`, `Offset` and `Gap` map to tre's `anchor`, `size` and margins, and how a collapsed Bar keeps a layer surface (#needs-verification; [[TDL Language#Open]]).
- [x] Whether a surface is named by the word before the brace or by a key: the head is the type and `Name:` is the unique name (ADR-0014, item 6).
- [x] The order in which the shell tries several monitor selectors on one block: `Connector`, then `Description`, then `Index` (ADR-0014 Layout Rules, item 15, decided 2026-10-30).
- [x] What an imported `_Shell.tdl` contains: surface blocks only, which take the importing Monitor's monitor (D22, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]).

## Links

- [[41 TDL Reference]] · [[TDL Language]] · [[Common Keys and Conventions]] · [[Module File]] · [[Surface Types]]
