---
title: Shadows on Layer Surfaces
aliases: [Surface Shadows, Shadow Research]
type: research
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [research, spec/surface, integration/wayland, needs-verification]
related: ["[[Surface Types]]", "[[Prior Art - Linux Shell Surfaces]]", "[[TRE-REQ-001 Layer Surface Window]]"]
depends_on: []
---

# Shadows on layer surfaces

> [!summary]
> Every shell surface can have a shadow with elevation and colour. There are two ways to get one: draw it inside the surface (a larger, transparent surface), or ask the compositor to draw it. KDE has a protocol for the second. This note records what is known and what to research. Nothing here is tested.

Maintainer position (2026-10-25): KDE does shadows, so all surfaces can do shadows; the open job is to find out how other shells and desktops do it.

## Two routes

| Route | How | What it needs |
|---|---|---|
| A. Compositor-drawn | The client attaches shadow tiles to its surface with `org_kde_kwin_shadow`, and KWin draws them outside the surface | The shell, through tre, must bind the shadow manager on the surface's connection and attach buffers. tre 0.5.8 does not document this. It would be an engine request. |
| B. In-surface | The surface is larger than the visible body; the shadow is drawn in the transparent margin, and the exclusive zone covers the body only | tre's `shadows` node property; a larger transparent buffer; `input_region="auto"` so clicks pass through the margin |

## What is known

- **The protocol.** `org_kde_kwin_shadow_manager` (version 2) creates an `org_kde_kwin_shadow` for a `wl_surface`: eight requests attach a `wl_buffer` to the top-left, top, top-right, right, bottom-right, bottom, bottom-left and left tiles; four offsets; `commit`; `unset`. The page does not say which surface roles it applies to. KWin 6.7 is listed at version 2; other compositors are listed but the support marker is undefined on the page ([wayland.app](https://wayland.app/protocols/kde-shadow)).
- **KWin's handler does not check the role.** `create` fails only when the `wl_surface` is unknown to KWin (`"Invalid  surface"`); it does not look at toplevel, popup or layer role ([shadow.cpp](https://lxr.kde.org/source/plasma/kwin/src/wayland/shadow.cpp)). #needs-verification: whether KWin's scene then draws the shadow for a layer-shell surface. The file does not show it.
- **KDE's client API.** `KWindowShadow` in KWindowSystem wraps the protocol on Wayland and uses shared-memory buffers for the tiles ([windowshadow.cpp](https://codebrowser.dev/kde/kwindowsystem/src/platforms/wayland/windowshadow.cpp.html), [API](https://api.kde.org/frameworks/kwindowsystem/html/windowshadow_8h_source.html)). KWin's `Shadow::createShadow` tries the window's decoration, then the Wayland shadow interface, then X11, then internal windows ([shadow.cpp](https://lxr.kde.org/source/plasma/kwin/src/shadow.cpp?v=kf5-qt5)).
- **Quickshell.** Its `PanelWindow` and `WlrLayershell` are decorationless layer surfaces, so a shadow is drawn inside the window's own surface ([PanelWindow](https://quickshell.org/docs/v0.2.0/types/Quickshell/PanelWindow)). That is route B. The usual way, from general knowledge and not from these pages, is a window larger than the bar with a transparent margin and an exclusive zone for the visible size.
- **Plasma 6.8** adds server-side shadows for undecorated apps, with settings in KWin ([linuxiac](https://linuxiac.com/kde-plasma-6-8-adds-server-side-shadows-for-undecorated-apps/), [webpronews](https://www.webpronews.com/kde-plasma-6-8-brings-server-side-drop-shadows-to-tame-inconsistent-windows/)). #needs-verification: whether it covers layer surfaces. The reports describe windows.
- **Hyprland.** Layer surfaces take layer rules by namespace (for example blur); the pages found do not show a shadow rule for layers ([Hyprland wiki](https://wiki.hypr.land/0.27.1/Useful-Utilities/Status-Bars)).
- **Not found:** how plasma-framework's panel and dialog code applies shadows (a 2020 review mentions a planned port only); how Waybar, eww, Fabric and the others do it.

## The maintainer's earlier work

The `myShell` repository ([README](file:///home/phil/Projects/pyDev/projects/myShell/README.md)) holds the Edge Shell design spec, plan and shell specs, not the code. The maintainer reports a working Fabric version with shadows, animated panels and bars moving out of the frame (2026-10-25). The documents show the approach:

- A frame of four edge strips and four corner surfaces per monitor, and one surface per panel, allocated once at its fully extended size, so KWin never resizes a layer surface during an animation; animation redraws and moves the input region ([design spec §5.1](file:///home/phil/Projects/pyDev/projects/myShell/docs/superpowers/specs/2026-10-11-edge-shell-design.md)).
- Panels and frame share one colour, panels are drawn with cairo as one path with curved joins, and panels repaint the frame strip beneath them to avoid hairline seams. A fallback is one click-through full-screen canvas per monitor (§3, §5.1, §10).
- The shell specs list `frame_shadow`, `frame_shadow_elevation` and `frame_shadow_color` ([Shell_Specs](file:///home/phil/Projects/pyDev/projects/myShell/docs/Shell_Specs.md)). How the shadow is drawn is not in the documents read. #needs-verification

This supports the maintainer's point that a visual meld works: it is one colour, drawn joins and repainting, not one shared surface.

## To research

- [ ] Whether KWin draws an `org_kde_kwin_shadow` shadow for a `wlr-layer-shell` surface (try it on KWin 6.8.1 with a test client).
- [ ] How Plasma's own panels get their shadow (plasma-framework / plasma-workspace source).
- [ ] How Waybar, eww, Fabric, AGS/Astal, Quickshell shells and COSMIC do shadows.
- [ ] How the Edge Shell prototype drew its shadows.
- [ ] Whether tre can expose the surface for route A, and whether the engine accepts a shadow request ([[AGENTS#6. Engine requests (tre / Tesserae)]]). Ask the `tre` session before writing a request.
- [ ] The memory cost of the larger transparent buffer for route B, per [[Surface Types#Performance budget]].

## Links

- [[Surface Types]] · [[Prior Art - Linux Shell Surfaces]] · [[TRE-REQ-001 Layer Surface Window]]
