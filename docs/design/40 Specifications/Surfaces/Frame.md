---
title: Frame
aliases: [Frame Surface, kind frame, Screen Frame]
type: spec
status: stable
owner: phil
created: 2026-10-27
updated: 2026-11-13
tags: [spec/surface, needs-verification]
---

# Frame

> [!NOTE]
> The Frame (the `Frame` block) is a ring around the screen, attached to all four edges and corners, that reserves space on every side. Its thickness is the same on every side or differs by side. A four-sided `Margin` adds transparent space between the ring and the display edge. Its inner corners are rounded (concave); its outer corners are square by default and can be rounded (convex). It has inner and outer borders, a background, border colours (solid or gradient) and shadows. Panels and Bars can be visually melded into it with rounded joins, so they look as if they grow out of the frame; this is a visual effect on separate surfaces, not one shared surface. The Frame is Top layer only. On tre it is a full-screen painter `LayerWindow` plus up to four thin space-reserving windows, using the path hit shape released in tre 0.5.9. The decisions are the maintainer's ([Surface Types](Surface%20Types.md)); the key names were accepted by the maintainer on 2026-10-29. The examples are TDL illustrations ([ADR-0014 Shell File Language](../../30%20Decisions/ADR-0014%20Shell%20File%20Language.md)).

## Purpose and Scope

- Draw a continuous frame with rounded corners around each monitor, reserve its thickness as space so maximised windows stay inside it, and let clicks pass through the interior to the desktop.
- v1: in scope (decided, 2026-10-26, [V1 Scope > Surfaces](../../10%20Vision/V1%20Scope.md#surfaces)).
- Not in this note: the Panels and Bars that attach to it ([Panel](Panel.md), [Bar](Bar.md)), the Path block ([Building Blocks](../../50%20Design%20System/Building%20Blocks.md)), and shadows beyond the notes here ([Shadows on Layer Surfaces](../../90%20Research/Shadows%20on%20Layer%20Surfaces.md)).

## Behaviour

### Parts on Tre

The layout from [TRE-REQ-001 Layer Surface Window > Use case: screen frame](../../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#use-case-screen-frame), moved to the Top layer and updated for tre 0.5.9. Eight surfaces (four edges, four corners) were rejected: more surfaces, and seams between neighbours.

| Part     | Count                                                      | `LayerWindow` settings                                                                                                                                   | Draws                                                          |
|----------|------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------|
| Painter  | 1 per monitor                                              | `layer="top"`, anchored to all four edges, `size=(0, 0)`, `exclusive_zone=-1`, `input_region="auto"`                                                     | The ring, its corners, border, and background, as `path` nodes |
| Reserver | Up to 4 per monitor, one per side with a thickness above 0 | `layer="top"`, anchored to that edge and both edges across it, 1 px on the short axis, `exclusive_zone` equal to the side's thickness, `input_region=[]` | Nothing (transparent)                                          |

- The painter extends to every edge and ignores other zones (`exclusive_zone=-1`). The painter draws the ring inset by the Frame's `Margin`; the margin area stays transparent, and each reserver's `exclusive_zone` is the side's total (thickness, borders and margin). The reservers push maximised windows inside the frame. A side with different thickness is a different reserver zone.
- Both kinds are on `top` because the Frame is Top only and `top` is the layer where reserving is allowed ([Surface Types > Layers per kind](Surface%20Types.md#layers-per-kind)).
- A change to a thickness is a change of `exclusive_zone` on one reserver, a step change (each is a configure round trip and windows reflow once), so thickness is not animated ([TRE-REQ-001 Layer Surface Window > Animation](../../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#animation)).

### The Ring and Its Corners

- The ring is a `path` node with a `fill`: an outer contour (the screen rectangle, with rounded corners for the convex outer corners) and an inner contour wound the other way (the opening, with rounded corners for the concave inner corners). With tre's non-zero fill rule, the opposite winding makes the hole ([paint reference](https://mindderivative.github.io/tre/reference/paint/)).
- `hit_shape="painted"` on the ring (tre 0.5.9) makes the ring take clicks only where it is painted: its fill region and its stroke. A click in the opening, or in the notch of a concave corner, passes to what is behind it. The same shape drives `input_region="auto"`, so the compositor and tre agree.
- Limit from tre: a click up to about 2 px inside the unfilled side of a curve may still be taken; tests use points 3 px or more inside the unfilled area.
- The ring must be a Path block. `hit_shape` does not cover `svg` and `canvas` nodes ([Hit Testing for Concave Corners](../../90%20Research/Hit%20Testing%20for%20Concave%20Corners.md)).
- The Path block therefore exposes `hit_shape`; the shape blocks (Circle, Ring and the like) default it to `painted` (decided 2026-10-27, [Building Blocks](../../50%20Design%20System/Building%20Blocks.md)).

### The Frame's Layer (Decided 2026-10-27)

Decided by the maintainer on 2026-10-27: the Frame stays on `top`, and melded Bars and Panels are hosted in the Frame's own surface (hosted melding), which removes the layer-order concern and keeps the Overlay layer free. The analysis that led there is kept below.

The Frame is on `top` in the diagram. The maintainer is unsure (2026-10-27): if a melded Bar or Panel has to sit on top of the Frame, maybe the Frame should sit on Background and be the exception for reserved space. The facts:

- **The protocol** orders the four layers and leaves the order of surfaces on one layer undefined ([protocol](https://wayland.app/protocols/wlr-layer-shell-unstable-v1)). Two surfaces on `top` can be drawn in either order.
- **KWin** maps Background to its desktop layer, Bottom to its below layer, Top to its above layer and Overlay to its overlay layer (`LayerShellV1Window::belongsToLayer`, read 2026-10-27, [KWin source](https://invent.kde.org/plasma/kwin/-/raw/master/src/layershellv1window.cpp)). A layer-shell window reports a strut whenever its exclusive zone is above 0, and that file does not look at the layer. Whether KWin's work-area code filters struts by layer is outside that file and not checked. #needs-verification KWin's full layer order, and that a dock window shares the Above layer with `top` surfaces, are in [Surface Types > Fullscreen and maximised windows (decided 2026-10-27)](Surface%20Types.md#fullscreen-and-maximised-windows-decided-2026-10-27).
- **plasmashell's desktop** (the wallpaper) is also in KWin's desktop layer, which is where Background surfaces go. The stacking order between it and a Background Frame is KWin's, not ours. #needs-verification
- **The reservers are invisible.** Where they sit changes nothing you see; only where the painter sits changes the look.

| Option                                                | Painter      | Reservers | For                                                                                                                                                                                                                                     | Against                                                                                                                                                                                                                                 |
|-------------------------------------------------------|--------------|-----------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 1. Top (the diagram)                                  | `top`        | `top`     | The ring and strips are drawn above windows, like a bezel: a window dragged over the edge is tucked under it. Keeps "only Top reserves" and "Frame is Top only". Strips hosted in the painter are always visible                        | A standalone Bar melded to the Frame is on the same layer, so the draw order is undefined. A melded Panel works on `overlay`. A thick edge (a strip) replaces the melded Bar, so the problem is limited to Bars placed beside the Frame |
| 2. Painter on `bottom`, reservers on `top`            | `bottom`     | `top`     | Everything melded sits above the ring on a defined layer, Bars on `top`, Panels on `top` or `overlay`. Keeps "only Top reserves" (the reservers are the reserving surfaces, and they are on `top`). Above the wallpaper in KWin's order | The Frame is a composite over two layers. The ring and any strips it hosts sit below windows, so a window that overlaps the edge covers them, and a strip stops acting like a bar above windows                                         |
| 3. Painter on `background` (the maintainer's thought) | `background` | `top`     | The same as option 2                                                                                                                                                                                                                    | The same as option 2, plus it shares KWin's desktop layer with the wallpaper, so the ring could be drawn behind it; the layer name suggests it, and it is the layer kept for wallpapers ([Surface Types > Layers per kind](Surface%20Types.md#layers-per-kind))       |

Recommendation: option 1 (keep `top`) together with hosted melding (option 4) for melded Bars and Panels, because it matches the bezel look, keeps the rules as they are, and the melding problem only exists for standalone Bars: a thick edge covers the bar case, and Panels use `overlay`. Option 2 is the alternative if melded standalone Bars matter more than the strips being above windows. Option 3 adds an uncertainty (the wallpaper) without a benefit over option 2. The maintainer's Edge Shell used `top` for its frame ([Shadows on Layer Surfaces > The maintainer's earlier work](../../90%20Research/Shadows%20on%20Layer%20Surfaces.md#the-maintainers-earlier-work)).

**The maintainer's question (2026-10-27): five layers, where 4 is overlay and 3 is melds?** The layer-shell protocol has exactly four layers (`background`, `bottom`, `top`, `overlay`) and cannot take a fifth, so the shell cannot add one. What it can do is give "melds" a place without a layer:

| Option                                            | Mapping                                                                                                                                                                                                       |
|---------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| 4. Host melds in the painter (see Hosted melding) | Layers 0 to 3 as in the diagram; melds are drawn inside the Frame's own surface on `top`; `overlay` is left for real overlays. Recommended                                                                    |
| 2 (above)                                         | Layer 1 (`bottom`) is the Frame's ring, layer 2 (`top`) is the melds, bars and strips-as-bars, layer 3 (`overlay`) is real overlays. Gives melds their own layer, at the cost of the ring being under windows |

So the answer to "can we have a layer for melds" is: not as a fifth layer; use hosted melding on one surface (option 4) or the bottom/top split (option 2).

The test of three layers against the wallpaper is no longer needed.

### Thickness, Radii, Border, Colours

| Property            | Form                                                                                                                                         | Notes                                                                                                                                        |
|---------------------|----------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------|
| Thickness           | One number, a list of four (left, top, right, bottom), or a block of named sides (`Thickness { Top: 8, Left: 24 }`, D7)                      | The fill band of a side. Borders and the `Margin` add to it (below). A side of 0 has no reserver                                             |
| Margin              | One number, a list of four (left, top, right, bottom) or named sides: transparent space between the Frame's outer sides and the display edge | Optional; adds to the total size (below)                                                                                                     |
| Padding             | Four-sided (left, top, right, bottom): space between a strip's children and the strip's sides                                                | Applies only to a side used as a strip (a side whose `Children` are enabled)                                                                 |
| Outer corner radius | Four-sided: rounds the screen corners (convex)                                                                                               | Default 0 (decided 2026-10-27): the Frame's outer corners usually touch the monitor's own corners, and a rounded outer corner would look odd |
| Inner corner radius | Four-sided: rounds the opening (concave fillets)                                                                                             |                                                                                                                                              |
| Inner border        | Width and colour on the edge facing the desktop                                                                                              | Optional                                                                                                                                     |
| Outer border        | Width and colour on the edge at the screen edge                                                                                              | Optional; having both is allowed (maintainer, 2026-10-27)                                                                                    |
| Background          | A colour or a gradient                                                                                                                       | tre has linear, radial and sweep gradients                                                                                                   |
| Border colour       | A colour, a token or a gradient                                                                                                              | A gradient border is decided; tiling it is opt-in (below)                                                                                    |

**Thickness plus borders (decided 2026-10-27).** A border takes layout space (2026-11-02), so the border `Width` adds to the Frame's overall thickness: a Frame with a thickness of 10 px and a 2 px border is 12 px in total, and the reserver's zone for that side is 12. With both an inner and an outer border the total is the thickness plus both. The same rule gives the strip's total thickness.

**Margin adds to the total (decided 2026-10-30, D41 to D45).** The `Margin` is transparent space between the Frame's outer sides and the display edge, and it is added to the Frame's total size. A `Thickness` of 10 with `Margin: [5, 5, 5, 5]` is 15 on every side, and a 2 px border makes 17 (10 + 5 + 2). The reserved zone is the total, 17. A Frame has no `Gap`, since a Frame is not attached to anything. The shell computes the zone and the painted bands; a stroke in tre is centred on its path ([paint reference](https://mindderivative.github.io/tre/reference/paint/)), so the shell offsets the contours by half a border.

**Gradient borders and tiling (decided 2026-10-27 that a gradient is allowed and tiling is opt-in).** A border colour can be a gradient. What "tiling" repeats is not settled here: the likely meaning is that the gradient repeats along the ring instead of stretching once across it, with `Border_Tile` off by default (proposed key). tre's `Gradient` offers linear, radial and sweep, with positions relative to the box, and no spread or repeat option in its Python API ([tre Gradient](https://mindderivative.github.io/tre/reference/paint/)); only SVG gradients have a spread method. So a tiled gradient is built from repeated stops by the shell today, and a native repeat is written up as [TRE-REQ-006 Repeating Gradients](../../80%20Requests/TRE-REQ-006%20Repeating%20Gradients.md) (draft, for the future, not filed).

### Melding

A Panel or Bar attached to the Frame looks as if it grows out of it, with rounded connections and borders. The maintainer's earlier Edge Shell design shows how: the surfaces stay separate, share one colour, draw their own rounded joins with curves, and repaint the frame strip beneath them so no seam shows ([Shadows on Layer Surfaces > The maintainer's earlier work](../../90%20Research/Shadows%20on%20Layer%20Surfaces.md#the-maintainers-earlier-work)).

- The joining surface draws the join shapes (Path blocks) in its own surface, over the frame.
- **A margin on a Panel stops the meld (decided 2026-10-30, D41 to D45).** A Panel attached to the Frame with a `Margin` on the sides that face the Frame does not meld: the Frame edge continues straight and the Panel's corners round as a floating Panel's do. With no `Margin` on those sides they meld as above. A Bar attached to the Frame decides the same way with its `Gap`: a `Gap` of 0 on the Frame-facing side melds, a `Gap` above 0 does not, and a Bar melds only when a Frame is present (D62; [Bar](Bar.md)).
- **Layer order.** The Frame is on `top`, and the protocol leaves the order of surfaces on one layer undefined. A Panel that must draw over the Frame is therefore on the `overlay` layer (a Bar that melds is on `top` and relies on drawing outside the frame band, or must not overlap it). #needs-verification on KWin.
- **Seams.** At idle there should be none. While either surface moves or animates there can be up to one frame of difference, because Wayland cannot commit two surfaces together ([TRE-REQ-001 Layer Surface Window > Animation](../../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#animation)). The width of the seam is to be measured in the testing phase.

### Shadows

The painter covers the whole output, so a shadow cast from the ring onto the desktop is drawn inside the same surface; no oversize surface is needed, unlike a Bar or Panel ([Shadows on Layer Surfaces](../../90%20Research/Shadows%20on%20Layer%20Surfaces.md)). tre's painted hit shape is the fill and the stroke, so a shadow does not take clicks. Decided 2026-10-27: all shadows, on every surface and block, are excluded from the hit shape and the input region. #needs-verification that tre's `shadows` property is not part of the painted hit shape; if it is, that is an engine request (AGENTS > 6. Requests Between Projects).

### What a Frame Holds (Decided 2026-10-27)

A Frame can be one of three things, and a single Frame can mix them:

1. A plain frame: just the ring.
2. A frame with melding Bars or Panels attached to it (see Melding above).
3. A frame with one or more thicker edges, where a thicker edge acts as a bar: a strip along that side that holds modules, containers and blocks. All four edges can have a strip, or none.

A strip is part of the Frame, not a separate Bar. Its thickness is the side's thickness, so it is reserved space like any side.

Decided by the maintainer on 2026-10-27:

- A Frame with a built-in strip can still have melded Bars and Panels, including on the strip.
- A strip can expand, contract or peek, edge to edge, like a full-width bar. (See Strip: expand, contract, peek.)

**How it is built on tre (decided 2026-11-04: Option A).** The painter, which is full-screen and already draws the ring, also hosts the strips' contents. Each strip is a container placed in its side's band, laid out inside the painter's surface. Why this and not separate Bar windows for the strips:

| Option                          | Description                                                                 | Verdict                                                                                                                                                                                                                                                                                           |
|---------------------------------|-----------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| A. The painter hosts the strips | One surface for the ring and its content; the reservers stay thin and empty | Recommended. Ring and content share one surface and one colour, so there is no seam and no layer-order question (the protocol leaves the order of surfaces on one layer undefined). `input_region="auto"` already follows what is drawn, so the strips take clicks and the opening passes through |
| B. Each strip is its own window | The reserver for that side is sized to the strip and holds the content      | A second surface on the same layer as the painter: undefined order, a possible seam, and more windows. It would be a Bar attached to the Frame, which is what Melding already covers                                                                                                              |

In option A the keyboard mode of the painter is `on_demand` if any strip holds a text input; otherwise `none`. The painter then takes pointer input over the strips and ring (by `auto`) and nothing in the opening.

### Strip Corners, Direction and Joins (Decided 2026-11-06)

Decided by the maintainer on 2026-11-06, as recommended; they answer the three points the build left open ([M3 Build Log](../../00%20Home/M3%20Build%20Log.md), D73).

| Point | Rule |
|---|---|
| Who owns a corner | The top and bottom strips own the corner squares and run the full width of the output. The left and right strips run between them. A corner is laid out with the horizontal strip that reaches it. This is how a Bar spans its edge |
| Direction of side strips | A strip on the left or right side lays its children out vertically. Text is not rotated in v1; a strip that needs rotated text is a later item |
| How a hosted join is drawn | The painter draws the ring and every hosted meld as one path contour, with a fillet at each join that uses the Frame's inner corner radius. The first build measures the cost of the path and of the input region (the spec's existing `#needs-verification`) |
| The painter's keyboard mode | Already decided above (Option A): `on_demand` if any strip holds a text input, otherwise `none`. The build log listed it as open in error |

### Strip: Expand, Contract, Peek

A strip can grow, shrink or peek out from its edge, along the whole side (edge to edge). Space is reserved in steps, so the two things are separate (a reserver's zone changes in one step, a configure round trip, and tre does not animate it):

| State      | What you see                                                          | Reserved space                                |
|------------|-----------------------------------------------------------------------|-----------------------------------------------|
| Contracted | The side at its base thickness (the ring)                             | The base thickness                            |
| Expanded   | The strip at full thickness                                           | The full thickness                            |
| Peek       | The strip pushed out over the windows for a moment, as a hover reveal | The base thickness (it does not push windows) |

- The visual extent is animated inside the painter, which is full-screen and can draw anywhere; that is a node animation, not a window resize.
- To expand: set the reserver's zone first, then animate the strip out. To contract: animate it in, then set the zone. Windows reflow once, not on every frame. This is the auto-hide pattern from the tre request ([TRE-REQ-001 Layer Surface Window > Shell patterns](../../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#shell-patterns)).
- A peek reserves nothing and draws over windows, which works because the painter is on `top`. A peek that reaches into a window's area is a hover reveal, so a keyboard way to open it is needed.
- Reduced motion: the states switch instantly ([Goals and Non-Goals](../../10%20Vision/Goals%20and%20Non-Goals.md) G7).

### Strips and Bars on One Edge (Decided 2026-10-27)

A strip and a Bar can share an edge, with different jobs:

- A strip, say 34 px thick, holds icons. Clicking an icon expands a Bar from the strip's inner edge: a sub-bar full of items related to that icon.
- Or the strip holds the user's most used items, and a Bar is added beside it for the others they need quick access to.
- A strip has every ability a Bar has: hidden, collapsed, peeking, animated, expanded and contracted, on its own ([Bar > Auto-hide (decided 2026-10-27)](Bar.md#auto-hide-decided-2026-10-27)). It can be hidden without hiding the Frame. The Bar's zero-size rule applies at creation only and does not stop a strip from hiding, peeking, expanding or contracting ([Bar > Geometry](Bar.md#geometry)).
- The sub-bar is a Bar attached to the strip (`Attach_To` the Frame, hosted in the painter when melded). How an icon names the Bar it opens, and how the two surfaces animate together, is open.

### Hidden and Shown at Runtime (Decided 2026-10-27)

The whole Frame can be hidden and shown at will during runtime. While hidden, the reservers go away (their zones are released, so windows use the full screen); when shown they return. The change is a step: zones change once and windows reflow once, the same as a strip's expand and contract. A fullscreen window hides all shell elements by the rule in [Surface Types > Fullscreen and maximised windows (decided 2026-10-27)](Surface%20Types.md#fullscreen-and-maximised-windows-decided-2026-10-27).

### Hosted Melding (Decided 2026-10-27)

The painter is a full-screen surface, so a Bar or Panel melded to the Frame can be drawn **inside the painter** instead of in a window of its own. The entry stays a sibling in the file and names its target (`Attach_To`), as before; a flag such as `Meld: true` tells the shell to host it in the Frame's surface.

|                         | Separate window (melding as in Melding above)                  | Hosted in the painter                             |
|-------------------------|----------------------------------------------------------------|---------------------------------------------------|
| Layers used             | Frame on `top`, the melded entry on a higher layer (`overlay`) | One surface, no extra layer                       |
| Order against the Frame | Defined only across layers                                     | Not an issue: one surface                         |
| Seam while moving       | Up to one frame of difference                                  | None: one node tree                               |
| Joins                   | Drawn in two surfaces with a shared colour                     | One path                                          |
| Content                 | Its own window                                                 | Nodes in the painter's tree                       |
| Input                   | Its own input region                                           | The painter's `auto` region follows what is drawn |
| Cost                    | A window per melded entry                                      | None, but the painter's tree and region grow      |

It is the fallback the Edge Shell design named: four invisible reserving strips plus one click-through full-screen canvas per monitor that draws the frame, corners and panels in one path ([Shadows on Layer Surfaces > The maintainer's earlier work](../../90%20Research/Shadows%20on%20Layer%20Surfaces.md#the-maintainers-earlier-work), design spec section 5.1). The same approach lets the Overlay layer stay free for real overlays (a launcher, a dimming layer) instead of being used for melds.

Limits: a hosted entry cannot move to another monitor or be a free-floating, draggable window (it grows out of its target); a panel that must float can still be its own window. Not tested on tre. #needs-verification: the cost of a large tree and region in the painter, and the one-frame skew between the painter and the reservers (the reservers are separate windows).

### Measured on KWin (maintainer, 2026-11-06)

`measure.sh` on KWin 6.8.2, HDMI-A-1 at 1920 by 1080 logical, scale 1.0, thickness 24, tesserae-engine 0.6.1. Three runs; the idle figures were identical in all three. This answers G8 of [M4 Brief](../../00%20Home/M4%20Brief.md) and the Frame row of [M3 Brief](../../00%20Home/M3%20Brief.md) for a 1080p output; 4K and many joins are not measured.

| Windows | RSS added | Pss added | tre video memory allocated (reserved) | Idle CPU in 5 s | Frames in 3 s idle |
|---|---|---|---|---|---|
| Painter and four reservers | +78.7 MiB (103.8 total) | +34.6 MiB | 10.5 MiB (32.0) | 0 ms | 0 on every window |
| Painter only | +76.9 MiB | +25.0 MiB | 10.2 MiB (32.0) | 0 ms | 0 |
| Four reservers only | +77.4 MiB | +26.1 MiB | 1.0 MiB (16.0) | 0 ms | 0 on every window |

Reading (the vault session's inference, not measured): the first window of a process costs about 77 MiB RSS whatever it holds, so the Frame's own cost is the difference between runs: the four reservers add about 1.8 MiB RSS and 9.6 MiB Pss to the painter, and the painter adds about 9.5 MiB of video memory (its persistent target is 8.5 MiB of that). A static ring draws no frames and uses no CPU. The 177 MiB figure for a 4K overlay in [Performance Budgets](../../60%20Quality/Performance%20Budgets.md) was measured on tre 0.5.8 and is not comparable. #needs-verification at 4K.

### Painter With Melds, Measured on KWin (maintainer, 2026-11-06)

`measure.sh --only=painter --melds=N`, the same machine and output. The painter holds the ring and N hosted melds as one path.

| Melds | Path data | Build | Layout | Draw | Frame total | RSS added | Video memory | Idle frames in 3 s | Input-region warnings |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 597 characters | 0.17 ms | 0.25 ms | 0.92 ms | 1.4 ms | +76.8 MiB | 10.2 MiB | 0 | none |
| 4 | 1,456 characters | 0.46 ms | 0.43 ms | 1.42 ms | 2.3 ms | +76.8 MiB | 10.2 MiB | 0 | none |
| 8 | 2,741 characters | 0.67 ms | 1.03 ms | 1.69 ms | 3.2 ms | +76.9 MiB | 10.2 MiB | 0 | none |

Melds are cheap: memory does not move, idle stays at 0 frames and 0 ms CPU, and the first full frame takes 3.2 ms with eight. 1080p only; 4K is not measured.

### Found on KWin: the look is not good enough (maintainer, 2026-11-06)

> [!CAUTION]
> **M3c passes its checklists and fails the maintainer's look test**
> Strips and melding, the animated melded Panel and the Frame keyboard all pass their checklist lines (the keyboard works on a click with variant B). The maintainer's verdict on how it looks: "It is not nearly as good looking ... I think it is clear we are not even close to being done." What was seen:
> 1. A melded Panel's join has no animation: while it slides, the join shows a 90 degree angle, then a chamfer appears. This is the known limit in [M3 Build Log](../../00%20Home/M3%20Build%20Log.md) D84 and D85: tre resamples an animated path into 48-point polylines, so the build draws the ring without its body and slides a layer, and the fillets arrive last instead of growing.
> 2. The rounded or chamfered join edge is not smooth; it looks slightly pixelated.
> 3. In variant B the dock overlays the Right edge button while it opens and closes.
> 4. The text in the buttons and on the Panels is not centred: it sits top and left. The maintainer notes it can be much better.
> 5. There is no peek. This is known and deferred (D87).
>
> The vault session has not verified causes. Items 2 to 4 are not explained by D84 and D85 and need the code session to look (pixelation may be the polyline or the path's anti-aliasing; centring may be a missing default or the test file). Item 1 needs a design: a join that grows with the slide, built from parts tre can animate. Open: whether it needs a TRE-REQ for path interpolation that keeps arcs. [Risk Register](../../00%20Home/Risk%20Register.md) R-31.

### Comparing the Join Options (Plan)

tre 0.6.4 (PyPI, 2026-11-07) ships the four mechanisms of [TRE-REQ-013 Structure-Preserving Path Morph](../../80%20Requests/TRE-REQ-013%20Structure-Preserving%20Path%20Morph.md), on top of the SMIL `d` morph in an `svg` node that was already there. The maintainer wants them all, to compare, because one may look better or cost less. The melded join can now be built five ways:

| # | Way | tre feature | State |
|---|---|---|---|
| a | SMIL contour morph in an `svg` node | `svg_time` animated in the engine (0.5.10) | Built (the code session, [M3 Build Log](../../00%20Home/M3%20Build%20Log.md) D84, D88 to D91): smooth, about 0.50 ms CPU per frame in its spike; no easing in SMIL (easing is driven through `animate(svg_time, easing=...)`), no `hit_shape` on an svg (the morph is `hit_testable=False`), arc flags not interpolated (use cubics) |
| b | Small closed join pieces by path data | path `data` morph, today's resampling | Spiked: 0.75 ms, smooth, the border needs more pieces |
| c | Box pieces with `scale`, `corner_radius` and (now) `transform_origin` and `corner_style="concave"` | Mechanism 1 (#269) | Spiked before 0.6.4 with masked boxes: 0.47 ms, worse (hairlines, hard mask edges). Not tried with a concave corner |
| d | A shader with `sd_round_union` and `Shader.animate` | Mechanism 2 (#270) | Not tried |
| e | A structure-preserving path morph of the whole contour | `morph="structure"` (#271) | Not tried |
| f | A parametric path driven by `animate_param` | Mechanism 4 (#272) | Not tried |

Rows c to f are the new work. The comparison, on KWin and sway at scale 1.0 and 1.5: how the edge looks (smoothness, seams, chamfer, the fillets growing with the slide), `total_ms` per frame while animating, memory (RSS and video), frames drawn at idle (must be 0), the hit shape (clicks through the notches), easing, and how much shell code each needs. The result goes in this section as a table and the maintainer chooses (AGENTS > 2. Hard Rules rule 5): one, or a different way for a different case. Not decided; the build is the code session's, and the choice is the maintainer's.

### KWin Retests and the Join Choice (maintainer, 2026-11-07)

The maintainer's records, as given. The numbered lines are the checklist lines of [M3 Build Log](../../00%20Home/M3%20Build%20Log.md) (the code session holds the wording; the vault records only the outcome).

| Test | Result |
|---|---|
| M3c, second look: smoothness, morph, overlap, centring | Four lines pass. Of the look he says: "It looks good, much better." |
| KWin retest on tre 0.6.3, no wake | All four lines pass. |
| M3c, join options | All five options tested at 100% and at 150% scale (output in `/tmp/tess-kwin-m3c/strips/logs/compare-join-output.log`) |

> [!NOTE]
> **One remaining look fault**
> "The border looks slightly thinner during the rounding than the straight portions, like it is off by one pixel, or stretched almost." The code session measured it ([M3 Build Log](../../00%20Home/M3%20Build%20Log.md) D97): the geometry and coverage are exact (2.00 px everywhere), and tre blends anti-aliased edges in sRGB, so the summed linear-light brightness is 1.70 on curves against 2.00 on straights at 1x. The proposed fix is an opt-in linear-light blend in tre: [TRE-REQ-015 Linear-Light Edge Blending](../../80%20Requests/TRE-REQ-015%20Linear-Light%20Edge%20Blending.md). These figures are the code session's and not checked in the vault. #needs-verification

The maintainer's order of the five join options, best first:

| Scale | 1st | 2nd | 3rd | 4th | 5th |
|---|---|---|---|---|---|
| 100% | PARAM | SMIL | SHADER | STRUCTURE | CONCAVE |
| 150% | PARAM | SMIL | STRUCTURE | SHADER | CONCAVE |
| His choice | PARAM | SMIL | STRUCTURE | SHADER | CONCAVE |

> [!IMPORTANT]
> **Decision (maintainer, 2026-11-07)**
> PARAM (row f, a parametric path driven by `animate_param`) is the default melded join, per [M3 Build Log](../../00%20Home/M3%20Build%20Log.md) D95; SMIL (row a) is second. The other options stay selectable through `Debug { Frame_Join }` for now. This answers the comparison above and the open question of which mechanism to use. R-31 stays open for the thin-rounded-border fault and until the code session has built PARAM as the default.

The cost figures behind the order (KWin, HDMI-A-1, 1920 by 1080) are in D95: total_ms mean 1.3 to 1.7 for all five, 0 idle frames, SMIL keeps more video memory after a slide (10.6 to 19.0 MiB against 0 to 1.1 MiB for the others), and SHADER is the only option that redraws part of the frame.

### Peek on KWin and the Handle Design (maintainer, 2026-11-07)

Retest of the peek build ([M3 Build Log](../../00%20Home/M3%20Build%20Log.md) D100, checklist "M3c, peek and popup input region"). Every line he could test passes: the Panel tab at rest, hover out, leave, reserved space unchanged, strip peek, and popup shadows passing clicks through ([TRE-REQ-014 Popup Input Region](../../80%20Requests/TRE-REQ-014%20Popup%20Input%20Region.md)). The strip that peeks in the demo is the left strip, not the top (the checklist wording was wrong).

> [!NOTE]
> **Keyboard way in: not testable**
> Clicking the buttons works, but Tab and Enter did nothing and nothing in the demo focuses the Frame without the mouse, so the keyboard could not be tested. This is the keyboard way that [Frame > Strip: Expand, Contract, Peek](#strip-expand-contract-peek) says a peek needs. The code session's reading ([M3 Build Log](../../00%20Home/M3%20Build%20Log.md) D53): no block can take focus yet, and an `on_demand` layer surface is focused by the compositor only on a click. A keyboard-only way in needs a global shortcut ([Global Shortcuts](../Integration/Global%20Shortcuts.md), not built). #needs-verification

His verdict on the look: "It looks very similar" to his Fabric version. What is missing, as he listed it:

1. **Click to open.** A click on the tab or sliver opens it, as well as hover.
2. **Click and hold, then drag.** Dragging pulls a Panel or Bar open, following the pointer.
3. **Handle icons.** The Fabric version drew three kinds of handle, each telling the user what the handle does:

| Handle | Shape (his words) | Means |
|---|---|---|
| Hover | Three dots side by side (maintainer, 2026-11-07: dots, not bars) | Opens on hover |
| Drag | A bar | Opens by dragging |
| Click | A chevron | Opens on click |

   - The default handle follows the open option that is set, and the developer can hide it.
   - A handle is hidden automatically when the Frame is too thin to show it, or when the peek is too thin.
   - The chevron points away from the Frame while the Panel or Bar is collapsed and morphs to point towards the Frame once it is open. The morph runs during the slide animation.
4. **Corner panels choose their edge.** A Panel in a corner (his example: top right) can be told which edge it slides out from. The handle and its icon sit on that edge: slid out from the top, they are on the top edge; slid out from the right, on the right edge.

> [!NOTE]
> **Designed 2026-11-07**
> The maintainer accepted the code session's keys (`Trigger`, `Handle`, `Slide_From`) and said the hover handle is three dots, not three bars. The design is the next section, [Frame > Peek Triggers and Handles (Decided 2026-11-07)](#peek-triggers-and-handles-decided-2026-11-07). The keyboard way in is still open (D102) and is in Open Questions.

### Peek Triggers and Handles (Decided 2026-11-07)

A melded Panel or an `Edges` strip that peeks says how it opens and what its handle looks like in its `Peek { }` block. `Size`, `Enter_Delay` and `Exit_Delay` are built ([M3 Build Log](../../00%20Home/M3%20Build%20Log.md) D100); `Trigger`, `Handle` and `Slide_From` are new (maintainer, 2026-11-07: keys accepted as proposed in D101).

```tdl
Peek { Size: 24, Enter_Delay: 150, Exit_Delay: 300, Trigger: HOVER, Handle: AUTO }
```

| Key | Values | Default | Meaning |
|---|---|---|---|
| `Size` | Pixels | 24 | The tab or sliver left at rest (built) |
| `Enter_Delay`, `Exit_Delay` | Milliseconds | 150, 300 | Hover delays; apply to `HOVER` only (built) |
| `Trigger` | `HOVER`, `CLICK`, `DRAG`, or a list of them (`[HOVER, DRAG]`) | `HOVER` | What opens it (below). With a list every named trigger works; the first build may take one value |
| `Handle` | `AUTO`, `NONE`, `DOTS`, `BAR`, `CHEVRON` | `AUTO` | The icon drawn on the tab or sliver |
| `Slide_From` | An edge name | The edge the Panel is attached to | Only for a Panel in a Frame corner: which of the two edges it slides out of |

**Triggers**

| Trigger | Behaviour |
|---|---|
| `HOVER` | The pointer on the tab for `Enter_Delay` brings it out along the contour; off it for `Exit_Delay` sends it back (as built) |
| `CLICK` | A click on the tab or sliver opens it fully; a click on the handle again closes it. No hover action |
| `DRAG` | A press on the tab or sliver, then a move: the body follows the pointer along its slide axis. Released at 50 % of the full depth or more it opens; below, it returns. A press that moves under 4 px counts as a click and toggles it |

The 4 px and the 50 % are the Edge Shell's values ([Panel > Collapsed Handle (Decided 2026-10-27: Use the Edge Shell as the Example)](Panel.md#collapsed-handle-decided-2026-10-27-use-the-edge-shell-as-the-example)); the build may tune them on KWin. The reserved space stays the base thickness in every state, as for a hover peek.

**Handles.** `AUTO` picks the icon from the trigger; naming one forces it; `NONE` hides it.

| `Handle` | Drawn as | `AUTO` for |
|---|---|---|
| `DOTS` | Three dots side by side: the maintainer's `tess_shell_dots.svg` (below); the colour changes on hover | `HOVER` |
| `BAR` | A short rounded bar: the maintainer's `tess_shell_bar.svg` (below) | `DRAG` |
| `CHEVRON` | A wedge that changes direction: the maintainer's `tess_shell_chevron.svg` (below) | `CLICK` |

- The chevron points away from the Frame while the Panel or strip is collapsed and points towards the Frame once it is open. It changes direction during the slide, driven by the slide's progress, not by a separate timer. The mechanism is tre 0.6.4's parametric path (`animate_param`, driven by the slide's progress); the code session spikes it first and falls back to a half-turn of the chevron if the spike looks poor (maintainer, 2026-11-07, as recommended).
- A handle is not drawn when it does not fit: when the side's thickness or the peek `Size` is too thin for it. Minimums: 8 px for `DOTS`, `BAR` and `CHEVRON`, tuned on KWin (maintainer, 2026-11-08: his handle box is 24 by 8 px, so the chevron's minimum is 8 px, not the 12 px recommended before). A hidden handle is not a load error and logs nothing above DEBUG.
- **The three handle icons are the maintainer's own SVGs** (2026-11-08). The vault holds copies in `_attachments/Handle Icons/` as the design reference, identical to the originals in `~/Pictures/CustomIcons/` when copied; the shell ships its own copies in its repository. All three have a hard-coded `#ffffff` fill that must take the shell's colour (a token; the dots change colour on hover) and an Inkscape `transform` or `translate` to flatten. The previews below are white and show only on a dark theme. Read from the files on 2026-11-08; not rendered in tre. #needs-verification

| File | Preview | Box | What it holds |
|---|---|---|---|
| `tess_shell_dots.svg` | [tess_shell_dots.svg | 24 by 8 px (`viewBox` 0 0 6.35 2.12) | Three circles side by side; about 6 px across, centres 4, 12 and 20 px along, so 2 px gaps |
| `tess_shell_bar.svg` | [tess_shell_bar.svg | 22 by 4 px (`viewBox` 0 0 5.82 1.06) | One rounded bar (corner radius about 1.5 px) made of four arcs; centred in a 24 by 8 px handle it leaves 1 px at each end and 2 px above and below |
| `tess_shell_chevron.svg` | [tess_shell_chevron.svg | 24 by 8 px (`viewBox` 0 0 6.35 2.12) | One closed three-point path, a filled wedge with its apex at the top as drawn |

  - The handle's box is 24 by 8 px, which is why every handle's minimum thickness is 8 px.
  - The chevron changes direction by moving its apex from the top to the bottom: one path with the same command sequence in both states (SMIL `d` morph, or `animate_param`). As drawn it points up, so on each edge it is rotated to point away from or towards the Frame.
  - The bar is not animated by its shape; its arc commands need no morph.
- The handle is part of the contour's painter, not a separate window or a click target of its own: the tab is the target.
- Reduced motion: the chevron switches direction at once with the state ([Goals and Non-Goals](../../10%20Vision/Goals%20and%20Non-Goals.md) G7).

**Corners.** A Panel melded in a corner touches two edges. `Slide_From` names one of them (`TOP`, `RIGHT`, `BOTTOM` or `LEFT`, as in [Common Keys and Conventions](../../41%20TDL%20Reference/Common%20Keys%20and%20Conventions.md)); the Panel slides out of that edge and its handle and icon sit on it. A top-right Panel with `Slide_From: TOP` slides down from the top edge and has its handle on the top edge; with `Slide_From: RIGHT` it slides in from the right edge and has its handle there. An edge the Panel does not touch is a load error.

**Accessibility.** The handle should be a focusable button with an accessible name such as "Expand dock" (the Edge Shell's rule). That needs a focus model that does not exist yet (D53, D102): see Open Questions. Until then the `Show`, `Hide` and `Toggle` actions are the only non-pointer way to open it.

### M3 Final Pass: Peek Findings (maintainer, 2026-11-08)

The peek triggers and handles pass on KWin: dots, click, chevron, drag, strip drag and `Slide_From`. The middle of the chevron's turn is not visible, so the blink of [M3 Build Log](../../00%20Home/M3%20Build%20Log.md) D106 stays as built. "Everything implemented looks good." Two lines could not be tested, because the demo has no knob for the peek `Size` and no button inside a panel body; those are gaps in the test config, not found faults.

Two additions he asked for. Both are proposals with a recommendation, not yet accepted:

1. **Handle brightness is adjustable.** The dots rest at 60 % and he finds that "more than visible", but a developer should be able to change it. Recommended: `Peek { Handle_Opacity: 0.6 }`, a number from 0 to 1, default 0.6, for the handle at rest; hover raises it as now.
2. **Content fades with the slide.** In Fabric the content inside a bar or panel faded in as it grew and out as it shrank; he says it is what made the Frame, peek and sliding feel polished. Recommended: the content's opacity follows the slide's progress (0 collapsed, 1 fully out) with the same duration and easing as the slide, for Panels, strips and Bars that slide, peek, expand or contract; on by default; `Content_Fade: false` turns it off. The mechanism is the code session's to spike (a per-node opacity driven by the slide's progress, as the chevron is). Reduced motion: no fade, the content switches with the state.

> [!IMPORTANT]
> **Decided (maintainer, 2026-11-08: "Recommendation accepted")**
> Both proposals are accepted as recommended: `Handle_Opacity` (0 to 1, default 0.6) and the content fade, on by default, with `Content_Fade: false` as the opt-out. The fade also applies to a plain show and hide (maintainer's answer to the open point). The code session's three questions are settled by my recommendation, which he accepted: the fade starts at progress 0 and ends at 1 with the contour, content stays hidden in the tab, and a strip's children fade with their strip. `Handle_Color` is left out until a theme needs it. [Frame > Open Questions](#open-questions)

### Multi-monitor

One Frame per monitor, independent: each is a complete ring with its own thickness and corners, as in the maintainer's Edge Shell design. Whatever lies between stacked monitors is left alone. A monitor with no Frame gets none ([Shell File > Monitors](../../41%20TDL%20Reference/Shell%20File.md#monitors)).

## Configuration

| Key                            | Meaning                                                                                                                                                                                                                                                                        | Status                                                                                             |
|--------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------|
| `Frame` (the head)             | The type; there is no `Kind:` key                                                                                                                                                                                                                                              | Decided                                                                                            |
| `Layer`                        | `TOP` only                                                                                                                                                                                                                                                                     | Decided                                                                                            |
| `Thickness`                    | Number, list of four (left, top, right, bottom), or named sides                                                                                                                                                                                                                | Decided (key name accepted 2026-10-29); the forms are decided                                      |
| `Corner_Radius`                | Outer (convex) corners, four-sided; default 0                                                                                                                                                                                                                                  | Default decided (2026-10-27); key accepted 2026-10-29                                              |
| `Inner_Radius`                 | Inner (concave) corners, four-sided                                                                                                                                                                                                                                            | Decided (key name accepted 2026-10-29)                                                             |
| `Inner_Border`, `Outer_Border` | Each a block with `Width` and `Color` (a colour, token or gradient); a `Border { Width, Color }` block, or the flat `Border_Width` and `Border_Color`, in `Style` is shorthand for the inner border. Each border takes layout space: its `Width` adds to the side's total      | Both decided as allowed (2026-10-27); key accepted 2026-10-29                                      |
| `Border_Tile`                  | Repeat a gradient border along the ring; default off                                                                                                                                                                                                                           | Opt-in decided (2026-10-27); key name and mechanism proposed                                       |
| `Margin`                       | Transparent space between the Frame's outer sides and the display edge; four-sided (left, top, right, bottom) or named sides. It adds to the total size, and the reserved zone is the total (10 + 5 + 2 = 17 in the example above)                                             | Decided (D41 to D45)                                                                               |
| `Padding`                      | Space between a strip's children and its sides; four-sided (left, top, right, bottom). Applies only to a side used as a strip. A Frame has no `Gap`                                                                                                                            | Decided (D41 to D45)                                                                               |
| `Visible`                      | `true` (the default) shows the Frame at start; `false` hides it at start. Shown and hidden at runtime by a shell action                                                                                                                                                        | Decided that it can be hidden and shown; key accepted 2026-10-29, renamed from `Hidden` 2026-11-02 |
| `Style`                        | Background, border, shadow, opacity                                                                                                                                                                                                                                            | Decided (the key); property names accepted 2026-10-29                                              |
| `Meld`                         | On a Bar or Panel entry that has `Attach_To` the Frame and no `Gap` (Bar) or `Margin` (Panel) on the Frame-facing side: `true` draws it inside the Frame's surface instead of in a window of its own. The `Gap` or `Margin` decides whether it melds at all (D56 amended, D62) | Decided (key name accepted 2026-10-29); the mechanism is decided (2026-10-27)                      |
| `Edges`                        | Per-edge overrides: `Left`, `Top`, `Right`, `Bottom`, each with its own `Thickness` and `Children` (the strip). An edge is the edge of the screen, however thick it is, and it starts at that edge; it is not a "side" of the screen that reaches past the halfway point       | Decided (maintainer, 2026-10-27: `Edges`, not `Sides`)                                             |
| `Children`                     | Blocks, containers and modules on the Frame itself                                                                                                                                                                                                                             | Decided that a layer window has them; for a Frame the content goes in a side's strip               |

```
Frame {
    Name: Screen_Frame
    Layer: TOP
    Thickness: [8, 8, 8, 8]          # or 8, or a block: Thickness { Top: 8, Left: 24 }
    Margin: [5, 5, 5, 5]             # transparent, to the display edge; the total per side is 13 (8 + 5)
    Corner_Radius: 0                 # the default; the outer corners are square
    Inner_Radius: 14
    Inner_Border { Width: 1, Color: "#ffffff22" }
    Style {
        Background: "#0b0c0d"
    }
    # optional: a thicker edge acts as a bar
    Edges {
        Top {
            Thickness: 32
            Children {
                Workspaces { }
                Spacer { }
                Clock { }
            }
        }
    }
}
```

An illustration only. `Thickness`, `Corner_Radius`, `Inner_Radius` and `Edges` are proposals; `Margin` and `Padding` are decided (D41 to D45). `Inner_Border`, `Outer_Border` and `Edges` are nested blocks, and `Edges` holds `Left`, `Top`, `Right` and `Bottom` blocks (D21, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)); a four-sided value is one number, a list of four or a block of named sides (D7). With no `Edges`, the Frame is just the ring, and Bars and Panels can be melded to it. A module use (`Workspaces { }`) is written with the module's name as the head ([Module File > Using a Module](../../41%20TDL%20Reference/Module%20File.md#using-a-module)).

## Python Contract

The Frame has no Python of its own. The shell builds the painter and reservers from the configuration and recomputes them on an output change. A module can show or hide the Frame through shell actions. Modules placed in a Frame's strips receive `use` records like any other ([Module Context > Uses](../../42%20Python%20API/Module%20Context.md#uses)).

## Integration

- tre 0.5.9 or later: `path` with `hit_shape="painted"`, `input_region="auto"`, `LayerWindow` with `layer`, `anchor`, `size`, `exclusive_zone` (live through `set()`) ([Hit Testing for Concave Corners](../../90%20Research/Hit%20Testing%20for%20Concave%20Corners.md), [TRE-REQ-001 Layer Surface Window](../../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md)). `namespace` and `output` are constructor-only.
- Region size: for a 3840 x 2160 ring, 48 px thick, outer radius 32 and inner radius 24, tre measured 66 rectangles at 2 px bands, under the 256 cap. A frame with ten fillet joins may reach the cap, where tre uses 4 or 8 px bands, covering up to a band more at the curves and never less ([tre issue 236](https://github.com/mindderivative/tre/issues/236), read 2026-10-26).
- Output changes: `output_updated` keeps the surfaces; the shell recomputes the ring and the reserver zones for the new size and scale ([V1 Scope > Multi-monitor](../../10%20Vision/V1%20Scope.md#multi-monitor)).
- Memory: five windows per monitor. tre 0.5.9 shares one GPU device and renderer among windows, so five small windows hold what one does (31 MiB, was 83 MiB, on AMD RADV); the painter is full-screen and costs more per pixel ([migration notes](https://mindderivative.github.io/tre/migrating-0.5/)). Not measured for a Frame on this machine.
- Coexistence with the Plasma panel: both reserve space; on one edge the compositor orders the zones. A Frame is usually drawn inside the Plasma panel on that edge or the panel is hidden on that monitor. #needs-verification.

## Design

- Colours, border and radii are style properties; light, dark and high contrast come from the theme ([Style, Theme and Stylesheet Files > Rules](../../41%20TDL%20Reference/Style%2C%20Theme%20and%20Stylesheet%20Files.md#rules)). The Frame's colour is the colour that joining surfaces repeat.
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
| A fullscreen window on the monitor                  | The Frame and its reservers hide until it leaves fullscreen ([Surface Types > Fullscreen and maximised windows (decided 2026-10-27)](Surface%20Types.md#fullscreen-and-maximised-windows-decided-2026-10-27)) |
| tre older than 0.5.9                                | `hit_shape` unknown: error at start naming the required version (the shell requires 0.5.9 or later)   |
| The monitor is removed                              | All of the Frame's windows close (`output_removed`); recreated when it returns                        |
| Scale or mode change                                | The ring and the reserver zones are recomputed                                                        |
| The painter and a reserver disagree for a frame     | Up to one frame of difference on screen; no data lost                                                 |
| A Panel joined to the Frame on the same layer       | Draw order undefined; the Panel uses `overlay`                                                        |
| The input region reaches the 256-rectangle cap      | tre coarsens the bands; clicks near curves may be taken by up to a band                               |

## Handle_Opacity and Content_Fade as Built (code session's report, 2026-11-13, not run in the vault)

Built in `dd2af58` (`feat/frame-fade`, merged to `main`; suite 3612 passed).

- `Peek { Handle_Opacity }` is 0 to 1, default 0.6; hover raises the handle to full; a reload changes it in place; a value outside 0 to 1 is a load error.
- The content's opacity is the slide's progress, with the contour's duration and easing, for a peek slide and drag, a plain show and hide of a melded Panel, and strip children with their strip; none under reduced motion. `Content_Fade: false` is written on a melded `Panel` and on an `Edges` entry.
- A Panel in its own window already fades its whole surface, so `Content_Fade` on one is a load warning; its opt-out is `Animation { Type: NONE }` (orchestrator, 2026-11-13).
- Faint content can still be clicked during a slide, because tre delivers pointer events to a node at opacity 0; this stays until a mis-mapped click is seen (orchestrator, 2026-11-13).
- `Handle_Opacity` does not change while the handle travels (orchestrator, 2026-11-13).

## Open Questions

- [x] What a Frame holds: a plain ring, melding Bars and Panels, or thicker edges that act as bars, all four edges or none (maintainer, 2026-10-27). The key is `Edges` (maintainer, 2026-10-27). The painter hosting the strips (option A) is accepted with the strips (maintainer review, 2026-10-27).
- [x] The Frame's layer: `top`, with melded Bars and Panels hosted in the Frame's surface (maintainer, 2026-10-27). The join is drawn as one path with fillets (decided 2026-11-06, above). Open: the cost of a large tree and region in the painter (to measure).
- [x] The four reservers plus the painter tested together on KWin, and a 4K frame with many joins: after the v1 build, in the testing phase (maintainer, 2026-10-27).
- [x] Fractional scale: wanted (maintainer, 2026-10-27). tre's docs say layer windows lay out in logical pixels and follow fractional scaling, and round a node's offset to a whole device pixel ([layer window reference](https://mindderivative.github.io/tre/reference/layer-window/), [window reference](https://mindderivative.github.io/tre/reference/window/)). Open: how a 1 px reserver and the ring edge look at 1.5x, tested with the rest. #needs-verification
- [x] A fullscreen window covers all shell elements and a maximised window does not ([Surface Types > Fullscreen and maximised windows (decided 2026-10-27)](Surface%20Types.md#fullscreen-and-maximised-windows-decided-2026-10-27)). Open: how KWin stacks them and how the shell detects fullscreen.
- [x] Inner border, outer border, or both: both are allowed (maintainer, 2026-10-27).
- [x] A strip against a Bar attached to the Frame, and hiding a strip on its own: a strip and a Bar can share an edge, and a strip has all a Bar's abilities (maintainer, 2026-10-27). Open: the icon-to-Bar link.
- [x] The Frame hidden or shown at runtime: yes; the reservers go while hidden and return when shown (maintainer, 2026-10-27).
- [x] Shadows are excluded from the hit shape, for all shadows (maintainer, 2026-10-27). Open: whether tre already does this. #needs-verification
- [x] A gradient border's tiling: the shell repeats stops; a native repeat is [TRE-REQ-006 Repeating Gradients](../../80%20Requests/TRE-REQ-006%20Repeating%20Gradients.md), kept for the future (maintainer, 2026-10-27).
- [x] Named sides for `Thickness`: a block of named sides, `Thickness { Top: 8, Left: 24 }` (D7, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)).
- [x] `Inner_Border`, `Outer_Border`, `Edges` and the edge names are nested blocks; `Edges` holds `Top`, `Right`, `Bottom`, `Left` blocks (D21, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)).
- [x] Shadow tokens: `Elevation`, `Shadow` and `Shadow_Bleed` are accepted ([Style Schema > Shadow keys](../../41%20TDL%20Reference/Style%20Schema.md#shadow-keys)); the Frame needs no bleed margin because the painter covers the output.
- [x] The hover handle is three dots, and the keys `Trigger`, `Handle` and `Slide_From` (maintainer, 2026-11-07; [Frame > Peek Triggers and Handles (Decided 2026-11-07)](#peek-triggers-and-handles-decided-2026-11-07)).
- [x] Combining triggers: `Trigger` takes one value or a list (`[HOVER, DRAG]`), and `AUTO` takes the icon of the first; the first build may take one value (maintainer, 2026-11-07, as recommended).
- [x] The chevron's change of direction: tre 0.6.4's `animate_param`, driven by the slide progress, with a half-turn of the chevron as the fallback if the spike is poor (maintainer, 2026-11-07, as recommended).
- [x] Minimum thickness for a handle: 8 px for `DOTS`, `BAR` and `CHEVRON`, tuned on KWin (maintainer, 2026-11-07, as recommended; the chevron lowered from 12 to 8 px on 2026-11-08 because his icon is 24 by 8 px).
- [x] The default `Slide_From` for a corner Panel is the edge it is attached to (maintainer, 2026-11-07, as recommended).
- [x] A keyboard way into the Frame and focusable handles (M3 Build Log D102). Decided by the maintainer on 2026-11-10: shortcut mode. `Enter_Shortcut_Mode` puts the Frame in `Shortcut_Mode: true` with the initial focus, and in that mode every peek of the Frame shows at the same time, if they can render together; `Next_Focus` and `Previous_Focus` cycle through its panels, peeks, bars and strips by `Tab_Index` ([Focus and Keyboard](../Integration/Focus%20and%20Keyboard.md)). Built in M6 ([M6 Brief](../../00%20Home/M6%20Brief.md)). Open there: how mode keys are delivered.
- [x] Handle brightness: `Peek { Handle_Opacity: 0.6 }`, 0 to 1, default 0.6 (maintainer, 2026-11-08, recommendation accepted).
- [x] Content fade: on by default, content opacity following the slide's progress with the slide's duration and easing, `Content_Fade: false` to opt out, for Panels, strips and Bars that slide, peek, expand or contract, and also for a plain show and hide (maintainer, 2026-11-08, recommendation accepted, "yes it also applies to a plain show and hide, with an opt-out option"). It also applies to an Expander's content (maintainer, 2026-11-08), with the same opt-out ([M4 Brief](../../00%20Home/M4%20Brief.md) W8). A module that appears or disappears through `If` does not fade, so the empty-state convention does not flicker as services come and go (maintainer, 2026-11-12, [M5 Brief](../../00%20Home/M5%20Brief.md) question 8).

## Acceptance Criteria

- [ ] On KWin a maximised window stops inside the ring on all four sides, and a side with a larger thickness reserves more.
- [ ] A click on the ring is taken by the shell; a click in the opening and in the notch of a concave corner passes to the desktop (points 3 px or more inside the unfilled area).
- [ ] The ring shows convex outer corners and concave inner corners at the configured radii, with the border and background.
- [ ] A Panel on the overlay layer joined to the Frame shows no seam at idle.
- [ ] Two monitors each have their own Frame; unplugging one removes only its windows, and plugging it back recreates them.
- [ ] A Frame with a thickness of 10 and a 2 px border reserves 12 px on that side; with an inner and an outer border of 2 px each it reserves 14.
- [ ] A Frame with a `Thickness` of 10, `Margin: [5, 5, 5, 5]` and a 2 px border reserves 17 px on every side.
- [ ] A Panel attached to the Frame with a `Margin` on the sides facing the Frame does not meld; with none it melds.
- [ ] A Frame strip that has contracted to a size of 0 can still expand; the Bar's zero-size check does not stop it.
- [ ] A hidden Frame releases all its reserved space and a shown one restores it, with one reflow each.
- [ ] A shadow around the ring takes no clicks.
- [ ] A fullscreen window covers the Frame; a maximised window stops inside it.
- [ ] Idle: the Frame draws no frames.
- [ ] With tre older than 0.5.9 the shell stops with a message naming the version.
- [ ] `Peek { Trigger: CLICK }` opens on a click and not on hover; `Trigger: DRAG` follows the pointer and, released at 50 % of the depth or more, opens, below that, returns; a press that moves under 4 px toggles it.
- [ ] `Handle: AUTO` draws three dots for `HOVER`, a bar for `DRAG` and a chevron for `CLICK`; `NONE` draws nothing; a side or peek `Size` thinner than the handle's minimum draws none and raises no error.
- [ ] The chevron points away from the Frame when collapsed and towards it when open, changing during the slide.
- [ ] A corner Panel with `Slide_From` slides out of that edge and has its handle there; an edge it does not touch is a load error.
- [ ] `Handle_Opacity` sets the handle's rest brightness; the default 0.6 matches today.
- [ ] Content inside a Panel, strip or Bar fades in as it grows and out as it shrinks, with the contour's duration and easing, also on a plain show and hide; `Content_Fade: false` turns it off; with reduced motion there is no fade.

## Links

- [Surfaces](Surfaces.md) · [Surface Types](Surface%20Types.md) · [Bar](Bar.md) · [Panel](Panel.md) · [Hit Testing for Concave Corners](../../90%20Research/Hit%20Testing%20for%20Concave%20Corners.md) · [Building Blocks](../../50%20Design%20System/Building%20Blocks.md)
