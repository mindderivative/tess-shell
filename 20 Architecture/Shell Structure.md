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
    mod2 --> pop[Special case: Popup, drawn above parent]
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
| Special Cases | Popup, "drawn above parent" | Reached from a module; holds containers and modules |

Reading the arrows: a layer window holds modules directly, or containers; containers hold modules; a module holds containers, widgets (through its inner module) and, as a special case, a popup. A popup holds containers and modules and is drawn above its parent.

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
- **The shell enforces `top` as the only layer that reserves space.** The protocol ties exclusive zones to no layer, so this is the shell's rule, chosen to reduce confusion. Handling proposed: an `exclusive_zone` off `top` is a load error.
- **KWin is "between Layer 1 and Layer 2",** as the protocol says.

## What does not match, or needs a decision

1. **Popup is now a special case inside a module, not a layer window.** In the first diagram Popup sat in Layer Windows, next to Panel, Bar and Frame. Now it is a "Special Case" reached from a Module, "drawn above parent", holding containers and modules. The vault has Popup as a surface kind in its own entry that names the surface it hangs off ([[Surface Types]], [[Shell File]]). Which is meant? **A.** Popup stays a `kind: popup` entry in the shell file, as today. **B.** A popup is declared inside the module that opens it (for example a tray module with its menu), parented to the surface the module is in. B fits the diagram and needs no reference by name, because the parent is the surface holding the module. It also makes "popups are exclusive to the monitor they are called on" automatic. Recommendation B, if popups are only opened from modules; keep A as well if a surface itself (not a module) must open one.
2. **Widgets only through a module.** The Widgets group is reached only from a module; no arrow runs from Containers to Widgets. In the Label example a `FlexBox` holds an `Icon` and a `Text`. Can a container on a surface, outside any module, hold widgets directly?
3. **Containers and widgets share a key?** The diagram keeps Containers and Widgets as separate groups. In the Label example `FlexBox:` is written like `Text:`. Same key (`widget: FlexBox` / `FlexBox:`) or its own?
4. **How a surface holds modules and containers.** `modules:` is a key on a surface today; the diagram shows modules and containers both under a layer window. Option **A:** `children:` holds containers and module uses; **B:** keep `modules:` and add a container key. Recommendation A.
5. **Nested modules.** What a nested module means for params, names, UIDs and the Python (one instance per file, nested uses) needs spelling out.
6. **Popup placement of keyboard focus.** A popup inherits its parent's keyboard setting ([protocol](https://wayland.app/protocols/wlr-layer-shell-unstable-v1)): a bar with `keyboard: none` cannot give a popup focus. Whether the module sets the parent to `on_demand` while a popup is open is for the module spec.

## Open

- [ ] The points above.
- [ ] Whether the diagram is the single reference for the structure, with other notes linking to it.

## Links

- [[20 Architecture]] · [[Surface Types]] · [[Module File]] · [[Shell File]] · [[Layers and Components]]
