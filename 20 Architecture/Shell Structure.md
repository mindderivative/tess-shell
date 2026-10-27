---
title: Shell Structure
aliases: [Shell Flow Diagram, Structure Diagram]
type: architecture
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-26
tags: [architecture, needs-verification]
related: ["[[20 Architecture]]", "[[Surface Types]]", "[[Module File]]", "[[Common Keys and Conventions]]", "[[V1 Widgets]]"]
depends_on: []
---

# Shell structure

> [!summary]
> The maintainer's flow diagram ([[Shell Flow Diagram.canvas]], third version, 2026-10-26) shows what a shell is made of, from the desktop environment down to widgets. This note puts it in words, checks it against the rest of the vault and the layer-shell protocol, and lists what does not yet match. The diagram is the maintainer's design; the points below are questions, not corrections.

![[Shell Flow Diagram.canvas]]

## What the diagram shows

```mermaid
flowchart TB
    wall[Wallpapers] --> l0[Layer 0 Background]
    l0 --> l1[Layer 1 Bottom]
    l1 --> l2[Layer 2 Top]
    l2 --> l3[Layer 3 Overlay]
    res[Reserved Space] --> l2
    kwin[KWin between Layer 1 and Layer 2]
    shell[Shell] --> layers[Layer surface]
    layers --> lw[Layer windows: Panel, Bar, Frame]
    lw --> mod1[Module]
    lw --> cont[Containers: Box, FlexBox]
    cont -->|can nest| cont2[Container]
    cont --> mod1
    mod1 -->|can nest| mod2[Module]
    mod2 --> widgets[Widgets: Text, Button]
    mod2 --> cont
    mod2 -->|calls| pop[Special case: Popup, drawn above parent]
    pop --> cont
    pop --> mod2
```

| Group | Contents | Relation |
|---|---|---|
| Desktop Environment | The layer surface, KWin, Wallpapers | The compositor owns the four layers. Wallpapers on Layer 0; KWin's windows between Layer 1 and Layer 2; Reserved Space on Layer 2 |
| Layer Surface | Layer 0 Background, Layer 1 Bottom, Layer 2 Top, Layer 3 Overlay | The Shell attaches to these |
| Layer Windows | Panel (Bottom/Top/Overlay), Bar (Bottom/Top/Overlay), Frame (Top) | Each kind with the layers it may use |
| Containers | Box, FlexBox | "Can nest": a container holds containers |
| Module | Module | "Can nest": a module holds modules |
| Widgets | Text, Button | Reached from a module |
| Special Cases | Popup, "drawn above parent" | A module calls it (the "Calls" edge); it holds containers and modules. A place for future popup-like kinds, such as a Notification window |

Reading the arrows: a layer window holds modules directly, or containers; containers hold modules; a module holds containers, widgets (through its inner module) and, as a special case, a popup. A module calls a popup, which holds containers and modules and is drawn above its parent.

## Checked against the vault and the protocol

| Diagram | Check | Result |
|---|---|---|
| Four layers numbered 0 to 3 | The layer-shell protocol's four layers, "ordered by z depth, bottom-most first" ([protocol](https://wayland.app/protocols/wlr-layer-shell-unstable-v1)) | Matches exactly ([[Common Keys and Conventions]]) |
| KWin "between Layer 1 and Layer 2" | The protocol: ordinary windows are rendered between the bottom and top layers | Matches exactly |
| Reserved Space on Layer 2 | Enforced by the shell as its own rule | Decided ([[Surface Types#Layers per kind]]) |
| Panel, Bar, Frame as layer windows with the layers shown | [[Surface Types#Layers per kind]] | Matches |
| Popup "drawn above parent" | `xdg_popup` parented to a layer surface: the compositor draws it above its parent | Matches the protocol's idea. The protocol page does not describe the stacking itself; it points to the xdg_popup rules |
| Layer 0 wallpapers only | Wallpaper is later in [[V1 Scope]] | Consistent |
| Modules nest, containers nest | Was open ([[Module File#Open]]) | Confirmed by the diagram |

## Decided from the diagram

- **Layer 0 is for wallpapers only, for now** (maintainer, 2026-10-26). No kind uses `layer: background`. The maintainer can see it used later for window tiling, or as a base layer for a desktop dashboard.
- **Frame is Top only.** Its strips move to `top` ([[Surface Types]]). Top suits the painter, which must be above windows to be seen; the strips are invisible so any layer works, and Top-layer reservation is the case known to work on KWin.
- The shell enforces `top` as the only layer that reserves space. The protocol ties exclusive zones to no layer, so this is the shell's rule, chosen to reduce confusion. Handling proposed: an `exclusive_zone` off `top` is a load error.
- **KWin is "between Layer 1 and Layer 2",** as the protocol says.

## What does not match, or needs a decision

1. ~~Popup: a kind or declared inside a module?~~ Decided (maintainer, 2026-10-26): Popup stays as it is, a `kind: popup` entry in the shell file. The diagram's edge is **"Calls"**: a module can *call* a popup, and the popup can hold modules and containers. It is not declared inside the module. The Special Cases group exists because the maintainer can see other surfaces that behave like a popup but need their own kind, such as a **Notification window**. Not v1 ([[V1 Scope#After v1]]); recorded in [[Surface Types#Special cases]].
2. **Widgets only through a module.** Answered by the new model: a block can be placed wherever `children:` is allowed, in a surface, a module or a container. Nothing stops a block from sitting directly on a surface.
3. **Containers and widgets share a key?** Decided: containers are building blocks, called with `block:` (Box, FlexBox, Grid). `widget:` no longer exists.
4. **How a surface holds modules and containers.** Decided: `children:` only; `modules:` goes away (maintainer, 2026-10-26). The way a module use is written inside `children:` waits for the widget and module decision.
5. **Nested modules, names and UIDs.** **Decided: anything with a unique name gets a UID; names are unique across the shell and reachable from anywhere through the registry.** Open: how repeated uses of one definition get unique names (path names, proposed in [[ADR-0007 Shell UI Layer#Open items]]) and the params policy ([[Module File#Params down the tree]]).
6. **Popup focus.** **Decided: opt-in.** An open popup marked as taking focus takes keyboard and mouse itself. See [[Surface Types#Special cases]].

## Blocks and modules (decided 2026-10-26)

The maintainer looked at how Tesserae builds widgets and chose the shell's own **building blocks** ([[Building Blocks]]). The diagram's "Containers" and "Widgets" groups are therefore blocks now, and the "Module" boxes are composed units:

| In the diagram | Now |
|---|---|
| Containers: Box, FlexBox | Building blocks, called with `block:`; also Grid |
| Widgets: Text, Button | Text is a block; Button is a module built from blocks |
| Module | Composed in YAML from blocks and other modules; called by its unique `name:`; Python optional |
| Special Cases: Popup | Unchanged; a module calls it |

What Tesserae does, for reference (design `yaml-language.md` section 3 and guide `components.md`, local clone commit `0eda3fe`, read 2026-10-26): a widget is either built in (Python) or a view (a file with `params:`), both called the same way, and a called view has no ViewModel of its own. The shell kept the declared-properties idea and made two kinds, with different keys (`block:` for built-ins, a name for modules). The full decision, calling rules and styling rules are in [[ADR-0007 Shell UI Layer#Blocks, modules and styling (2026-10-26)]].

The diagram needs updating to match: the Containers and Widgets groups become a Building Blocks group, and Button and its relatives move to Modules.

## Open

- [ ] The points above.
- [ ] Whether the diagram is the single reference for the structure, with other notes linking to it.

## Links

- [[20 Architecture]] · [[Surface Types]] · [[Module File]] · [[Shell File]] · [[Layers and Components]]
