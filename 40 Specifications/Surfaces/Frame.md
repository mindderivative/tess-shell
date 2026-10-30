---
title: Frame
aliases: [Frame Surface, kind frame, Screen Frame]
type: spec
status: review
owner: phil
created: 2026-10-27
updated: 2026-10-29
tags: [spec/surface, needs-verification]
related: ["[[Surfaces]]", "[[Surface Types]]", "[[Bar]]", "[[Panel]]", "[[Hit Testing for Concave Corners]]", "[[TRE-REQ-001 Layer Surface Window]]"]
depends_on: ["[[Surface Types]]", "[[TRE-REQ-001 Layer Surface Window]]", "[[Hit Testing for Concave Corners]]"]
---

# Frame

> [!summary]
> The Frame (`kind: frame`) is a ring around the screen, attached to all four edges and corners, that reserves space on every side. Its thickness is the same on every side or differs by side. Its inner corners are rounded (concave); its outer corners are square by default and can be rounded (convex). It has inner and outer borders, a background, border colours (solid or gradient) and shadows. Panels and Bars can be visually melded into it with rounded joins, so they look as if they grow out of the frame; this is a visual effect on separate surfaces, not one shared surface. The Frame is Top layer only. On tre it is a full-screen painter `LayerWindow` plus up to four thin space-reserving windows, using the path hit shape released in tre 0.5.9. The decisions are the maintainer's ([[Surface Types]]); the key names were accepted by the maintainer on 2026-10-29. The examples are TDL illustrations ([[ADR-0014 Shell File Language]]).

## Purpose and Scope

- Draw a continuous frame with rounded corners around each monitor, reserve its thickness as space so maximised windows stay inside it, and let clicks pass through the interior to the desktop.
- v1: in scope (decided, 2026-10-26, [[V1 Scope#Surfaces]]).
- Not in this note: the Panels and Bars that attach to it ([[Panel]], [[Bar]]), the Path block ([[Building Blocks]]), and shadows beyond the notes here ([[Shadows on Layer Surfaces]]).

## Behaviour

### Parts on Tre

The layout from [[TRE-REQ-001 Layer Surface Window#Use case: screen frame]], moved to the Top layer and updated for tre 0.5.9. Eight surfaces (four edges, four corners) were rejected: more surfaces, and seams between neighbours.

| Part     | Count                                                      | `LayerWindow` settings                                                                                                                                   | Draws                                                          |
|----------|------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------|
| Painter  | 1 per monitor                                              | `layer="top"`, anchored to all four edges, `size=(0, 0)`, `exclusive_zone=-1`, `input_region="auto"`                                                     | The ring, its corners, border, and background, as `path` nodes |
| Reserver | Up to 4 per monitor, one per side with a thickness above 0 | `layer="top"`, anchored to that edge and both edges across it, 1 px on the short axis, `exclusive_zone` equal to the side's thickness, `input_region=[]` | Nothing (transparent)                                          |

- The painter extends to every edge and ignores other zones (`exclusive_zone=-1`). The reservers push maximised windows inside the frame. A side with different thickness is a different reserver zone.
- Both kinds are on `top` because the Frame is Top only and `top` is the layer where reserving is allowed ([[Surface Types#Layers per kind]]).
- A change to a thickness is a change of `exclusive_zone` on one reserver, a step change (each is a configure round trip and windows reflow once), so thickness is not animated ([[TRE-REQ-001 Layer Surface Window#Animation]]).

### The Ring and Its Corners

- The ring is a `path` node with a `fill`: an outer contour (the screen rectangle, with rounded corners for the convex outer corners) and an inner contour wound the other way (the opening, with rounded corners for the concave inner corners). With tre's non-zero fill rule, the opposite winding makes the hole ([paint reference](https://mindderivative.github.io/tre/reference/paint/)).
- `hit_shape="painted"` on the ring (tre 0.5.9) makes the ring take clicks only where it is painted: its fill region and its stroke. A click in the opening, or in the notch of a concave corner, passes to what is behind it. The same shape drives `input_region="auto"`, so the compositor and tre agree.
- Limit from tre: a click up to about 2 px inside the unfilled side of a curve may still be taken; tests use points 3 px or more inside the unfilled area.
- The ring must be a Path block. `hit_shape` does not cover `svg` and `canvas` nodes ([[Hit Testing for Concave Corners]]).
- The Path block therefore exposes `hit_shape`; the shape blocks (Circle, Ring and the like) default it to `painted` (decided 2026-10-27, [[Building Blocks]]).

### The Frame's Layer (Decided 2026-10-27)

Decided by the maintainer on 2026-10-27: the Frame stays on `top`, and melded Bars and Panels are hosted in the Frame's own surface (hosted melding), which removes the layer-order concern and keeps the Overlay layer free. The analysis that led there is kept below.

The Frame is on `top` in the diagram. The maintainer is unsure (2026-10-27): if a melded Bar or Panel has to sit on top of the Frame, maybe the Frame should sit on Background and be the exception for reserved space. The facts:

- **The protocol** orders the four layers and leaves the order of surfaces on one layer undefined ([protocol](https://wayland.app/protocols/wlr-layer-shell-unstable-v1)). Two surfaces on `top` can be drawn in either order.
- **KWin** maps Background to its desktop layer, Bottom to its below layer, Top to its above layer and Overlay to its overlay layer (`LayerShellV1Window::belongsToLayer`, read 2026-10-27, [KWin source](https://invent.kde.org/plasma/kwin/-/raw/master/src/layershellv1window.cpp)). A layer-shell window reports a strut whenever its exclusive zone is above 0, and that file does not look at the layer. Whether KWin's work-area code filters struts by layer is outside that file and not checked. #needs-verification KWin's full layer order, and that a dock window shares the Above layer with `top` surfaces, are in [[Surface Types#Fullscreen and maximised windows (decided 2026-10-27)]].
- **plasmashell's desktop** (the wallpaper) is also in KWin's desktop layer, which is where Background surfaces go. The stacking order between it and a Background Frame is KWin's, not ours. #needs-verification
- **The reservers are invisible.** Where they sit changes nothing you see; only where the painter sits changes the look.

| Option                                                | Painter      | Reservers | For                                                                                                                                                                                                                                     | Against                                                                                                                                                                                                                                 |
|-------------------------------------------------------|--------------|-----------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1. Top (the diagram)                                  | `top`        | `top`     | The ring and strips are drawn above windows, like a bezel: a window dragged over the edge is tucked under it. Keeps "only Top reserves" and "Frame is Top only". Strips hosted in the painter are always visible                        | A standalone Bar melded to the Frame is on the same layer, so the draw order is undefined. A melded Panel works on `overlay`. A thick edge (a strip) replaces the melded Bar, so the problem is limited to Bars placed beside the Frame |
| 2. Painter on `bottom`, reservers on `top`            | `bottom`     | `top`     | Everything melded sits above the ring on a defined layer, Bars on `top`, Panels on `top` or `overlay`. Keeps "only Top reserves" (the reservers are the reserving surfaces, and they are on `top`). Above the wallpaper in KWin's order | The Frame is a composite over two layers. The ring and any strips it hosts sit below windows, so a window that overlaps the edge covers them, and a strip stops acting like a bar above windows                                         |
| 3. Painter on `background` (the maintainer's thought) | `background` | `top`     | The same as option 2                                                                                                                                                                                                                    | The same as option 2, plus it shares KWin's desktop layer with the wallpaper, so the ring could be drawn behind it; the layer name suggests it, and it is the layer kept for wallpapers ([[Surface Types#Layers per kind]])       |

Recommendation: option 1 (keep `top`) together with hosted melding (option 4) for melded Bars and Panels, because it matches the bezel look, keeps the rules as they are, and the melding problem only exists for standalone Bars: a thick edge covers the bar case, and Panels use `overlay`. Option 2 is the alternative if melded standalone Bars matter more than the strips being above windows. Option 3 adds an uncertainty (the wallpaper) without a benefit over option 2. The maintainer's Edge Shell used `top` for its frame ([[Shadows on Layer Surfaces#The maintainer's earlier work]]).

**The maintainer's question (2026-10-27): five layers, where 4 is overlay and 3 is melds?** The layer-shell protocol has exactly four layers (`background`, `bottom`, `top`, `overlay`) and cannot take a fifth, so the shell cannot add one. What it can do is give "melds" a place without a layer:

| Option                                            | Mapping                                                                                                                                                                                                       |
|---------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 4. Host melds in the painter (see Hosted melding) | Layers 0 to 3 as in the diagram; melds are drawn inside the Frame's own surface on `top`; `overlay` is left for real overlays. Recommended                                                                    |
| 2 (above)                                         | Layer 1 (`bottom`) is the Frame's ring, layer 2 (`top`) is the melds, bars and strips-as-bars, layer 3 (`overlay`) is real overlays. Gives melds their own layer, at the cost of the ring being under windows |

So the answer to "can we have a layer for melds" is: not as a fifth layer; use hosted melding on one surface (option 4) or the bottom/top split (option 2).

The test of three layers against the wallpaper is no longer needed.

### Thickness, Radii, Border, Colours

| Property            | Form                                                              | Notes                                                                                                                                        |
|---------------------|-------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------|
| Thickness           | One number, a list of four clockwise from the top, or named sides | The fill band of a side. Borders add to it (below). A side of 0 has no reserver                                                              |
| Outer corner radius | Four-sided: rounds the screen corners (convex)                    | Default 0 (decided 2026-10-27): the Frame's outer corners usually touch the monitor's own corners, and a rounded outer corner would look odd |
| Inner corner radius | Four-sided: rounds the opening (concave fillets)                  |                                                                                                                                              |
| Inner border        | Thickness and colour on the edge facing the desktop               | Optional                                                                                                                                     |
| Outer border        | Thickness and colour on the edge at the screen edge               | Optional; having both is allowed (maintainer, 2026-10-27)                                                                                    |
| Background          | A colour or a gradient                                            | tre has linear, radial and sweep gradients                                                                                                   |
| Border colour       | A colour, a token or a gradient                                   | A gradient border is decided; tiling it is opt-in (below)                                                                                    |

**Thickness plus borders (decided 2026-10-27).** The border thickness adds to the Frame's overall thickness: a Frame with a thickness of 10 px and a 2 px border is 12 px in total, and the reserver's zone for that side is 12. With both an inner and an outer border the total is the thickness plus both. The same rule gives the strip's total thickness. The shell computes the zone and the painted bands; a stroke in tre is centred on its path ([paint reference](https://mindderivative.github.io/tre/reference/paint/)), so the shell offsets the contours by half a border.

**Gradient borders and tiling (decided 2026-10-27 that a gradient is allowed and tiling is opt-in).** A border colour can be a gradient. What "tiling" repeats is not settled here: the likely meaning is that the gradient repeats along the ring instead of stretching once across it, with `border_tile` off by default (proposed key). tre's `Gradient` offers linear, radial and sweep, with positions relative to the box, and no spread or repeat option in its Python API ([tre Gradient](https://mindderivative.github.io/tre/reference/paint/)); only SVG gradients have a spread method. So a tiled gradient is built from repeated stops by the shell today, and a native repeat is written up as [[TRE-REQ-006 Repeating Gradients]] (draft, for the future, not filed).

### Melding

A Panel or Bar attached to the Frame looks as if it grows out of it, with rounded connections and borders. The maintainer's earlier Edge Shell design shows how: the surfaces stay separate, share one colour, draw their own rounded joins with curves, and repaint the frame strip beneath them so no seam shows ([[Shadows on Layer Surfaces#The maintainer's earlier work]]).

- The joining surface draws the join shapes (Path blocks) in its own surface, over the frame.
- **Layer order.** The Frame is on `top`, and the protocol leaves the order of surfaces on one layer undefined. A Panel that must draw over the Frame is therefore on the `overlay` layer (a Bar that melds is on `top` and relies on drawing outside the frame band, or must not overlap it). #needs-verification on KWin.
- **Seams.** At idle there should be none. While either surface moves or animates there can be up to one frame of difference, because Wayland cannot commit two surfaces together ([[TRE-REQ-001 Layer Surface Window#Animation]]). The width of the seam is to be measured in the testing phase.

### Shadows

The painter covers the whole output, so a shadow cast from the ring onto the desktop is drawn inside the same surface; no oversize surface is needed, unlike a Bar or Panel ([[Shadows on Layer Surfaces]]). tre's painted hit shape is the fill and the stroke, so a shadow does not take clicks. Decided 2026-10-27: all shadows, on every surface and block, are excluded from the hit shape and the input region. #needs-verification that tre's `shadows` property is not part of the painted hit shape; if it is, that is an engine request ([[AGENTS#6. Engine requests (tre / Tesserae)]]).

### What a Frame Holds (Decided 2026-10-27)

A Frame can be one of three things, and a single Frame can mix them:

1. A plain frame: just the ring.
2. A frame with melding Bars or Panels attached to it (see Melding above).
3. A frame with one or more thicker edges, where a thicker edge acts as a bar: a strip along that side that holds modules, containers and blocks. All four edges can have a strip, or none.

A strip is part of the Frame, not a separate Bar. Its thickness is the side's thickness, so it is reserved space like any side.

Decided by the maintainer on 2026-10-27:

- A Frame with a built-in strip can still have melded Bars and Panels, including on the strip.
- A strip can expand, contract or peek, edge to edge, like a full-width bar. (See Strip: expand, contract, peek.)

**How it is built on tre (proposed).** The painter, which is full-screen and already draws the ring, also hosts the strips' contents. Each strip is a container placed in its side's band, laid out inside the painter's surface. Why this and not separate Bar windows for the strips:

| Option                          | Description                                                                 | Verdict                                                                                                                                                                                                                                                                                           |
|---------------------------------|-----------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| A. The painter hosts the strips | One surface for the ring and its content; the reservers stay thin and empty | Recommended. Ring and content share one surface and one colour, so there is no seam and no layer-order question (the protocol leaves the order of surfaces on one layer undefined). `input_region="auto"` already follows what is drawn, so the strips take clicks and the opening passes through |
| B. Each strip is its own window | The reserver for that side is sized to the strip and holds the content      | A second surface on the same layer as the painter: undefined order, a possible seam, and more windows. It would be a Bar attached to the Frame, which is what Melding already covers                                                                                                              |

In option A the keyboard mode of the painter is `on_demand` if any strip holds a text input; otherwise `none`. The painter then takes pointer input over the strips and ring (by `auto`) and nothing in the opening.

### Strip: Expand, Contract, Peek

A strip can grow, shrink or peek out from its edge, along the whole side (edge to edge). Space is reserved in steps, so the two things are separate (a reserver's zone changes in one step, a configure round trip, and tre does not animate it):

| State      | What you see                                                          | Reserved space                                |
|------------|-----------------------------------------------------------------------|-----------------------------------------------|
| Contracted | The side at its base thickness (the ring)                             | The base thickness                            |
| Expanded   | The strip at full thickness                                           | The full thickness                            |
| Peek       | The strip pushed out over the windows for a moment, as a hover reveal | The base thickness (it does not push windows) |

- The visual extent is animated inside the painter, which is full-screen and can draw anywhere; that is a node animation, not a window resize.
- To expand: set the reserver's zone first, then animate the strip out. To contract: animate it in, then set the zone. Windows reflow once, not on every frame. This is the auto-hide pattern from the tre request ([[TRE-REQ-001 Layer Surface Window#Shell patterns]]).
- A peek reserves nothing and draws over windows, which works because the painter is on `top`. A peek that reaches into a window's area is a hover reveal, so a keyboard way to open it is needed.
- Reduced motion: the states switch instantly ([[Goals and Non-Goals]] G7).

### Strips and Bars on One Edge (Decided 2026-10-27)

A strip and a Bar can share an edge, with different jobs:

- A strip, say 34 px thick, holds icons. Clicking an icon expands a Bar from the strip's inner edge: a sub-bar full of items related to that icon.
- Or the strip holds the user's most used items, and a Bar is added beside it for the others they need quick access to.
- A strip has every ability a Bar has: hidden, collapsed, peeking, animated, expanded and contracted, on its own ([[Bar#Auto-hide (decided 2026-10-27)]]). It can be hidden without hiding the Frame.
- The sub-bar is a Bar attached to the strip (`attach_to` the Frame, hosted in the painter when melded). How an icon names the Bar it opens, and how the two surfaces animate together, is open.

### Hidden and Shown at Runtime (Decided 2026-10-27)

The whole Frame can be hidden and shown at will during runtime. While hidden, the reservers go away (their zones are released, so windows use the full screen); when shown they return. The change is a step: zones change once and windows reflow once, the same as a strip's expand and contract. A fullscreen window hides all shell elements by the rule in [[Surface Types#Fullscreen and maximised windows (decided 2026-10-27)]].

### Hosted Melding (Decided 2026-10-27)

The painter is a full-screen surface, so a Bar or Panel melded to the Frame can be drawn **inside the painter** instead of in a window of its own. The entry stays a sibling in the file and names its target (`attach_to`), as before; a flag such as `meld: true` tells the shell to host it in the Frame's surface.

|                         | Separate window (melding as in Melding above)                  | Hosted in the painter                             |
|-------------------------|----------------------------------------------------------------|---------------------------------------------------|
| Layers used             | Frame on `top`, the melded entry on a higher layer (`overlay`) | One surface, no extra layer                       |
| Order against the Frame | Defined only across layers                                     | Not an issue: one surface                         |
| Seam while moving       | Up to one frame of difference                                  | None: one node tree                               |
| Joins                   | Drawn in two surfaces with a shared colour                     | One path                                          |
| Content                 | Its own window                                                 | Nodes in the painter's tree                       |
| Input                   | Its own input region                                           | The painter's `auto` region follows what is drawn |
| Cost                    | A window per melded entry                                      | None, but the painter's tree and region grow      |

It is the fallback the Edge Shell design named: four invisible reserving strips plus one click-through full-screen canvas per monitor that draws the frame, corners and panels in one path ([[Shadows on Layer Surfaces#The maintainer's earlier work]], design spec section 5.1). The same approach lets the Overlay layer stay free for real overlays (a launcher, a dimming layer) instead of being used for melds.

Limits: a hosted entry cannot move to another monitor or be a free-floating, draggable window (it grows out of its target); a panel that must float can still be its own window. Not tested on tre. #needs-verification: the cost of a large tree and region in the painter, and the one-frame skew between the painter and the reservers (the reservers are separate windows).

### Multi-monitor

One Frame per monitor, independent: each is a complete ring with its own thickness and corners, as in the maintainer's Edge Shell design. Whatever lies between stacked monitors is left alone. A monitor with no Frame gets none ([[Shell File]]).

## Configuration

| Key                            | Meaning                                                                                                                                                                                                                                                                  | Status                                                                               |
|--------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
| `kind: frame`                  | The kind                                                                                                                                                                                                                                                                 | Decided                                                                              |
| `layer`                        | `top` only                                                                                                                                                                                                                                                               | Decided                                                                              |
| `thickness`                    | Number, list of four clockwise from the top, or named sides                                                                                                                                                                                                              | Decided (key name accepted 2026-10-29); the forms are decided                       |
| `corner_radius`                | Outer (convex) corners, four-sided; default 0                                                                                                                                                                                                                            | Default decided (2026-10-27); key accepted 2026-10-29                               |
| `inner_radius`                 | Inner (concave) corners, four-sided                                                                                                                                                                                                                                      | Decided (key name accepted 2026-10-29)                                              |
| `inner_border`, `outer_border` | Each a block with `thickness` and `color` (a colour, token or gradient); `border`, `border_thickness` and `border_color` in `style` are shorthand for the inner border                                                                                                 | Both decided as allowed (2026-10-27); key accepted 2026-10-29                       |
| `border_tile`                  | Repeat a gradient border along the ring; default off                                                                                                                                                                                                                     | Opt-in decided (2026-10-27); key name and mechanism proposed                         |
| `hidden`                       | Hide the Frame at start; shown and hidden at runtime by a shell action                                                                                                                                                                                                   | Decided that it can be hidden and shown; key accepted 2026-10-29                    |
| `style`                        | Background, border, shadow, opacity                                                                                                                                                                                                                                      | Decided (the key); property names accepted 2026-10-29                                 |
| `meld`                         | On a Bar or Panel entry that has `attach_to` the Frame: draw it inside the Frame's surface instead of in a window of its own                                                                                                                                             | Decided (key name accepted 2026-10-29); the mechanism is decided (2026-10-27)       |
| `edges`                        | Per-edge overrides: `top`, `right`, `bottom`, `left`, each with its own `thickness` and `children` (the strip). An edge is the edge of the screen, however thick it is, and it starts at that edge; it is not a "side" of the screen that reaches past the halfway point | Decided (maintainer, 2026-10-27: `edges`, not `sides`)                               |
| `children`                     | Blocks, containers and modules on the Frame itself                                                                                                                                                                                                                       | Decided that a layer window has them; for a Frame the content goes in a side's strip |

```
screen_frame {
    kind: frame
    layer: top
    thickness: [8, 8, 8, 8]          # or 8, or named sides (the form is open, see below)
    corner_radius: 0                 # the default; the outer corners are square
    inner_radius: 14
    inner_border { thickness: 1, color: "#ffffff22" }
    style {
        background: "#0b0c0d"
    }
    # optional: a thicker edge acts as a bar
    edges {
        top {
            thickness: 32
            children {
                Workspaces { }
                Spacer { }
                Clock { }
            }
        }
    }
}
```

An illustration only. `thickness`, `corner_radius`, `inner_radius` and `edges` are proposals. With no `edges`, the Frame is just the ring, and Bars and Panels can be melded to it. The module uses (`Workspaces { }`) follow the pending module-use syntax of [[Shell File]].

## Python Contract

The Frame has no Python of its own. The shell builds the painter and reservers from the configuration and recomputes them on an output change. A module can show or hide the Frame through shell actions. Modules placed in a Frame's strips receive `use` records like any other ([[Module Context#Uses]]).

## Integration

- tre 0.5.9 or later: `path` with `hit_shape="painted"`, `input_region="auto"`, `LayerWindow` with `layer`, `anchor`, `size`, `exclusive_zone` (live through `set()`) ([[Hit Testing for Concave Corners]], [[TRE-REQ-001 Layer Surface Window]]). `namespace` and `output` are constructor-only.
- Region size: for a 3840 x 2160 ring, 48 px thick, outer radius 32 and inner radius 24, tre measured 66 rectangles at 2 px bands, under the 256 cap. A frame with ten fillet joins may reach the cap, where tre uses 4 or 8 px bands, covering up to a band more at the curves and never less ([tre issue 236](https://github.com/mindderivative/tre/issues/236), read 2026-10-26).
- Output changes: `output_updated` keeps the surfaces; the shell recomputes the ring and the reserver zones for the new size and scale ([[V1 Scope#Multi-monitor]]).
- Memory: five windows per monitor. tre 0.5.9 shares one GPU device and renderer among windows, so five small windows hold what one does (31 MiB, was 83 MiB, on AMD RADV); the painter is full-screen and costs more per pixel ([migration notes](https://mindderivative.github.io/tre/migrating-0.5/)). Not measured for a Frame on this machine.
- Coexistence with the Plasma panel: both reserve space; on one edge the compositor orders the zones. A Frame is usually drawn inside the Plasma panel on that edge or the panel is hidden on that monitor. #needs-verification.

## Design

- Colours, border and radii are style properties; light, dark and high contrast come from the theme ([[Style, Theme and Stylesheet Files#Rules]]). The Frame's colour is the colour that joining surfaces repeat.
- Elevation shadows follow the shadow tokens of the design system (`50 Design System/`, not started).

## Accessibility

- The Frame is decoration. The painter's nodes are hidden from the accessibility tree (tre has an accessibility-hidden property) and are not focusable. The reserving windows are empty.
- High contrast: the border colour and background come from the theme's high-contrast tokens.
- Content in a Frame's strips is reachable by keyboard like any module; the ring itself is hidden from the accessibility tree.

## Performance Budget

- A static ring draws no frames at idle. It redraws when the monitor, scale or configuration changes.
- Five windows per monitor, one full-screen. Budgets are set in `60 Quality/`; the 4K case is the one tre did not measure with many joins.
- Changing a thickness reflows windows; do it rarely.

## Failure Modes and Recovery

| Failure                                             | Result                                                                                                |
|-----------------------------------------------------|-------------------------------------------------------------------------------------------------------|
| A thickness of 0 on a side                          | No reserver for that side                                                                             |
| A radius larger than half the thickness or the band | Clamped; a warning names the property                                                                 |
| A fullscreen window on the monitor                  | The Frame and its reservers hide until it leaves fullscreen ([[Surface Types#Fullscreen and maximised windows (decided 2026-10-27)]]) |
| tre older than 0.5.9                                | `hit_shape` unknown: error at start naming the required version (the shell requires 0.5.9 or later)   |
| The monitor is removed                              | All of the Frame's windows close (`output_removed`); recreated when it returns                        |
| Scale or mode change                                | The ring and the reserver zones are recomputed                                                        |
| The painter and a reserver disagree for a frame     | Up to one frame of difference on screen; no data lost                                                 |
| A Panel joined to the Frame on the same layer       | Draw order undefined; the Panel uses `overlay`                                                        |
| The input region reaches the 256-rectangle cap      | tre coarsens the bands; clicks near curves may be taken by up to a band                               |

## Open Questions

- [x] What a Frame holds: a plain ring, melding Bars and Panels, or thicker edges that act as bars, all four edges or none (maintainer, 2026-10-27). The key is `edges` (maintainer, 2026-10-27). The painter hosting the strips (option A) is accepted with the strips (maintainer review, 2026-10-27).
- [x] The Frame's layer: `top`, with melded Bars and Panels hosted in the Frame's surface (maintainer, 2026-10-27). Open: how the join is drawn in the painter, and the cost of a large tree and region in the painter (to measure).
- [x] The four reservers plus the painter tested together on KWin, and a 4K frame with many joins: after the v1 build, in the testing phase (maintainer, 2026-10-27).
- [x] Fractional scale: wanted (maintainer, 2026-10-27). tre's docs say layer windows lay out in logical pixels and follow fractional scaling, and round a node's offset to a whole device pixel ([layer window reference](https://mindderivative.github.io/tre/reference/layer-window/), [window reference](https://mindderivative.github.io/tre/reference/window/)). Open: how a 1 px reserver and the ring edge look at 1.5x, tested with the rest. #needs-verification
- [x] A fullscreen window covers all shell elements and a maximised window does not ([[Surface Types#Fullscreen and maximised windows (decided 2026-10-27)]]). Open: how KWin stacks them and how the shell detects fullscreen.
- [x] Inner border, outer border, or both: both are allowed (maintainer, 2026-10-27).
- [x] A strip against a Bar attached to the Frame, and hiding a strip on its own: a strip and a Bar can share an edge, and a strip has all a Bar's abilities (maintainer, 2026-10-27). Open: the icon-to-Bar link.
- [x] The Frame hidden or shown at runtime: yes; the reservers go while hidden and return when shown (maintainer, 2026-10-27).
- [x] Shadows are excluded from the hit shape, for all shadows (maintainer, 2026-10-27). Open: whether tre already does this. #needs-verification
- [x] A gradient border's tiling: the shell repeats stops; a native repeat is [[TRE-REQ-006 Repeating Gradients]], kept for the future (maintainer, 2026-10-27).
- [ ] Named sides for `thickness` (`top: 8, left: 24`): in TDL it needs a block or another form; ADR-0014 does not yet define it. Open for the maintainer.
- [x] Shadow tokens: `elevation`, `shadow` and `shadow_bleed` are accepted ([[Style Schema#Shadow keys]]); the Frame needs no bleed margin because the painter covers the output.

## Acceptance Criteria

- [ ] On KWin a maximised window stops inside the ring on all four sides, and a side with a larger thickness reserves more.
- [ ] A click on the ring is taken by the shell; a click in the opening and in the notch of a concave corner passes to the desktop (points 3 px or more inside the unfilled area).
- [ ] The ring shows convex outer corners and concave inner corners at the configured radii, with the border and background.
- [ ] A Panel on the overlay layer joined to the Frame shows no seam at idle.
- [ ] Two monitors each have their own Frame; unplugging one removes only its windows, and plugging it back recreates them.
- [ ] A Frame with a thickness of 10 and a 2 px border reserves 12 px on that side; with an inner and an outer border of 2 px each it reserves 14.
- [ ] A hidden Frame releases all its reserved space and a shown one restores it, with one reflow each.
- [ ] A shadow around the ring takes no clicks.
- [ ] A fullscreen window covers the Frame; a maximised window stops inside it.
- [ ] Idle: the Frame draws no frames.
- [ ] With tre older than 0.5.9 the shell stops with a message naming the version.

## Links

- [[Surfaces]] · [[Surface Types]] · [[Bar]] · [[Panel]] · [[Hit Testing for Concave Corners]] · [[Building Blocks]]
