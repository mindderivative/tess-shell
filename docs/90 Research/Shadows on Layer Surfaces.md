---
title: Shadows on Layer Surfaces
aliases: [Surface Shadows, Shadow Research]
type: research
status: stable
owner: phil
created: 2026-10-25
updated: 2026-10-27
tags: [research, spec/surface, integration/wayland, needs-verification]
---

# Shadows on Layer Surfaces

> [!NOTE]
> Decided 2026-10-27: route B, in-surface ([ADR-0010 Surface Shadows](../30%20Decisions/ADR-0010%20Surface%20Shadows.md)).
> Every shell surface can have a shadow with elevation and colour. There are two ways to get one: draw it inside the surface (a larger, transparent surface), or ask the compositor to draw it. KDE has a protocol for the second. Live tests on KWin 6.8.1 (2026-10-27) show route A works for top and overlay layer surfaces, and that neither route has a measurable cost at Bar and Panel size. The rest is still to research.

Maintainer position (2026-10-25): KDE does shadows, so all surfaces can do shadows; the open job is to find out how other shells and desktops do it.

## Two Routes

| Route               | How                                                                                                                                     | What it needs                                                                                                                                                         |
|---------------------|-----------------------------------------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| A. Compositor-drawn | The client attaches shadow tiles to its surface with `org_kde_kwin_shadow`, and KWin draws them outside the surface                     | The shell, through tre, must bind the shadow manager on the surface's connection and attach buffers. tre 0.5.8 does not document this. It would be an engine request. |
| B. In-surface       | The surface is larger than the visible body; the shadow is drawn in the transparent margin, and the exclusive zone covers the body only | tre's `shadows` node property; a larger transparent buffer; `input_region="auto"` so clicks pass through the margin                                                   |

## What is Known

- **The protocol.** `org_kde_kwin_shadow_manager` (version 2) creates an `org_kde_kwin_shadow` for a `wl_surface`: eight requests attach a `wl_buffer` to the top-left, top, top-right, right, bottom-right, bottom, bottom-left and left tiles; four offsets; `commit`; `unset`. The page does not say which surface roles it applies to. KWin 6.7 is listed at version 2; other compositors are listed but the support marker is undefined on the page ([wayland.app](https://wayland.app/protocols/kde-shadow)).
- **KWin's handler does not check the role.** `create` fails only when the `wl_surface` is unknown to KWin (`"Invalid  surface"`); it does not look at toplevel, popup or layer role ([shadow.cpp](https://lxr.kde.org/source/plasma/kwin/src/wayland/shadow.cpp)). The live test below shows the scene does draw it.
- **KDE's client API.** `KWindowShadow` in KWindowSystem wraps the protocol on Wayland and uses shared-memory buffers for the tiles ([windowshadow.cpp](https://codebrowser.dev/kde/kwindowsystem/src/platforms/wayland/windowshadow.cpp.html), [API](https://api.kde.org/frameworks/kwindowsystem/html/windowshadow_8h_source.html)). KWin's `Shadow::createShadow` tries the window's decoration, then the Wayland shadow interface, then X11, then internal windows ([shadow.cpp](https://lxr.kde.org/source/plasma/kwin/src/shadow.cpp?v=kf5-qt5)).
- **Quickshell.** Its `PanelWindow` and `WlrLayershell` are decorationless layer surfaces, so a shadow is drawn inside the window's own surface ([PanelWindow](https://quickshell.org/docs/v0.2.0/types/Quickshell/PanelWindow)). That is route B. The usual way, from general knowledge and not from these pages, is a window larger than the bar with a transparent margin and an exclusive zone for the visible size.
- **Plasma 6.8** adds server-side shadows for undecorated apps, with settings in KWin ([linuxiac](https://linuxiac.com/kde-plasma-6-8-adds-server-side-shadows-for-undecorated-apps/), [webpronews](https://www.webpronews.com/kde-plasma-6-8-brings-server-side-drop-shadows-to-tame-inconsistent-windows/)). #needs-verification: whether it covers layer surfaces. The reports describe windows.
- **Hyprland.** Layer surfaces take layer rules by namespace (for example blur); the pages found do not show a shadow rule for layers ([Hyprland wiki](https://wiki.hypr.land/0.27.1/Useful-Utilities/Status-Bars)).
- **Not found:** how plasma-framework's panel and dialog code applies shadows (a 2020 review mentions a planned port only); how Waybar, eww, Fabric and the others do it.

## Live Test on KWin 6.8.1 (2026-10-27)

A scratch C client (not in the vault, in /tmp) created a 320x140 layer surface anchored to the centre, bound `org_kde_kwin_shadow_manager` (v2) and attached eight tiles (24 px, premultiplied black, peak alpha 170) with all four offsets set to one value. A flat pale surface on the top layer sat behind it so the shadow fell on a known colour. Screenshots with and without the shadow were compared pixel by pixel.

| Layer   | Offset | Result                                                                                                         |
|---------|--------|----------------------------------------------------------------------------------------------------------------|
| top     | 0      | No difference. The tiles sit under the body, so nothing shows.                                                 |
| overlay | 0      | No difference (same reason).                                                                                   |
| top     | 24     | A soft shadow appears around the body on all four sides.                                                       |
| overlay | 24     | Differences in the area around the body; shadow drawn (not viewed in a crop).                                  |
| bottom  | 24     | No difference, but the surface was hidden behind other windows and the test backdrop, so the run says nothing. |

- KWin 6.8.1 advertises `zwlr_layer_shell_v1` v5 and `org_kde_kwin_shadow_manager` v2.
- The shadow offsets decide how far the shadow extends past the surface edge; an offset of 0 hides it. A first reading of the offset-0 runs as "no shadow" was wrong.
- Not tested: the bottom and background layers on a visible area, shadows on a Frame-sized surface, popups, multi-output, and fractional scaling.
- The shadow is compositor-drawn, so it is outside the surface: it does not count in the exclusive zone and the client cannot clip or animate it except by replacing the tiles.

## Performance Test, Route A against Route B (2026-10-27)

Setup: KWin 6.8.1 on the live session, tre 0.5.8 (editable install), a 320x140 body with 12 px corners. Route B used a tre `LayerWindow` of 384x204 (a 32 px transparent margin) with a fill change every 16 ms so each frame redraws for 600 frames (about 10 s), read with `frame_stats()`; three repetitions per variant, means below. Route A used the scratch C client with static tiles (offset 24). KWin CPU is the `kwin_wayland` process time over the 10 s run. Scripts are in /tmp (not in the vault).

| Variant                                    | Surface | fps       | Client CPU per frame | Draw stage | GPU per frame | KWin CPU per 10 s                          |
|--------------------------------------------|---------|-----------|----------------------|------------|---------------|--------------------------------------------|
| B0: body only, no margin, no shadow        | 320x140 | 60.0      | 0.44 ms              | 0.38 ms    | 0.04 ms       | 0.58 s                                     |
| B1: margin, no shadow                      | 384x204 | 60.0      | 0.48 ms              | 0.41 ms    | 0.04 ms       | 0.56 s                                     |
| B2: margin, tre card shadow (two layers)   | 384x204 | 60.0      | 0.46 ms              | 0.40 ms    | 0.08 ms       | 0.59 s                                     |
| B3: margin, one wide soft shadow (blur 24) | 384x204 | 60.0      | 0.43 ms              | 0.37 ms    | 0.06 ms       | 0.59 s                                     |
| A: compositor shadow, static C client      | 320x140 | no frames | none                 | none       | none          | 0.53 to 0.66 s (no shadow: 0.51 to 0.59 s) |

Reading:

- Route B costs 0.00 to 0.04 ms of client CPU and 0.02 to 0.04 ms of GPU per frame over a margin without a shadow, well under the 16.7 ms budget. Frames stayed at 60 fps in every run.
- Video memory in tre was identical for all variants (524,528 bytes allocated in the shared device; the surface is too small to show up). The extra pixels of the margin cost 134,144 bytes per buffer (32 px on every side of this body), so a Frame-sized or Bar-sized margin must be computed, not assumed.
- Route A costs the client nothing per frame. Its tile buffers are small shared-memory buffers (the client's resident memory was 2.4 MB without and 2.6 MB with the shadow). KWin's CPU with and without the shadow differs by less than the run-to-run spread (about 0.1 s per 10 s), so the shadow adds no measurable compositor cost on this machine.
- Limits: route A was a static surface, route B was a redrawing one, so the rows measure different things and are not a like-for-like frame comparison. The test used one monitor, one small surface and a vsync-bound loop (the acquire stage holds about 16 ms of every frame, so CPU and GPU per frame are the figures to read, not total time). A large surface (Frame, a wide Bar with a margin) was not measured; route B's cost scales with its pixel area.
- Conclusion: performance does not separate the routes at Bar and Panel size. The choice rests on other factors: route A needs tre to expose the surface (an engine request), draws outside the surface (not in the exclusive zone, not animatable except by replacing tiles), and needs no transparent margin or input-region handling; route B works with tre 0.5.8 today and lets the shadow animate with the node, at the price of a margin that every surface must declare.

## The Maintainer's Earlier Work

The `myShell` repository ([README](file://~/Projects/pyDev/projects/myShell/README.md)) holds the Edge Shell design spec, plan and shell specs, not the code. The maintainer reports a working Fabric version with shadows, animated panels and bars moving out of the frame (2026-10-25). The documents show the approach:

- A frame of four edge strips and four corner surfaces per monitor, and one surface per panel, allocated once at its fully extended size, so KWin never resizes a layer surface during an animation; animation redraws and moves the input region ([design spec §5.1](file://~/Projects/pyDev/projects/myShell/docs/superpowers/specs/2026-10-11-edge-shell-design.md)).
- Panels and frame share one colour, panels are drawn with cairo as one path with curved joins, and panels repaint the frame strip beneath them to avoid hairline seams. A fallback is one click-through full-screen canvas per monitor (§3, §5.1, §10).
- The shell specs list `frame_shadow`, `frame_shadow_elevation` and `frame_shadow_color` ([Shell_Specs](file://~/Projects/pyDev/projects/myShell/docs/Shell_Specs.md)). How the shadow is drawn is not in the documents read. #needs-verification

This supports the maintainer's point that a visual meld works: it is one colour, drawn joins and repainting, not one shared surface.

## To Research

- [x] Whether KWin draws an `org_kde_kwin_shadow` shadow for a `wlr-layer-shell` surface: yes on top and overlay, KWin 6.8.1 (see the live test).
- [ ] Bottom and background layers, and how the shadow follows a surface that animates its size.
- [ ] How Plasma's own panels get their shadow (plasma-framework / plasma-workspace source).
- [ ] How Waybar, eww, Fabric, AGS/Astal, Quickshell shells and COSMIC do shadows.
- [ ] How the Edge Shell prototype drew its shadows.
- [ ] Whether tre can expose the surface for route A, and whether the engine accepts a shadow request (AGENTS > 6. Requests Between Projects). Ask the `tre` session before writing a request.
- [x] The memory cost of the larger transparent buffer for route B: 134 KB per buffer for a 32 px margin on a 320x140 body (see the performance test). Still to measure at Frame size, per [Surface Types > Performance budget](../40%20Specifications/Surfaces/Surface%20Types.md#performance-budget).

## Links

- [Surface Types](../40%20Specifications/Surfaces/Surface%20Types.md) · [Prior Art - Linux Shell Surfaces](Prior%20Art%20-%20Linux%20Shell%20Surfaces.md) · [TRE-REQ-001 Layer Surface Window](../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md)
