---
title: ADR-0010 Surface Shadows
aliases: [ADR-0010, Shadow Route Decision]
type: adr
status: accepted
owner: phil
created: 2026-10-27
updated: 2026-10-27
tags: [adr, spec/surface]
related: ["[[Shadows on Layer Surfaces]]", "[[Surface Types]]", "[[Bar]]", "[[Panel]]", "[[Frame]]", "[[ADR-0001 Shell Surface Strategy]]", "[[ADR-0007 Shell UI Layer]]"]
depends_on: ["[[ADR-0001 Shell Surface Strategy]]"]
---

# ADR-0010: Surface Shadows

> [!summary]
> Shadows are drawn inside the surface, with tre's `shadows` node property, in a transparent margin around the body (route B). The compositor shadow protocol is not used.

## Context

Every surface can have a shadow with elevation and colour ([[Surface Types]]). A layer surface cannot draw outside its own bounds, so there are two routes ([[Shadows on Layer Surfaces]]): the compositor draws the shadow (`org_kde_kwin_shadow`, route A), or the shell draws it inside a larger transparent surface (route B). Tests on KWin 6.8.1 (2026-10-27) show both work and neither costs anything measurable at Bar and Panel size ([[Shadows on Layer Surfaces#Performance test, route A against route B (2026-10-27)]]).

## Options

### Option A — Compositor-drawn Shadow

- **For:** no margin, no input-region handling; the shadow is outside the exclusive zone by construction.
- **Against:** tre must expose the surface or attach the shadow, which is an engine request that does not exist; the shadow cannot animate with the node (only by replacing tiles); KWin-specific, so other compositors need route B anyway.

### Option B — In-surface Shadow (Chosen)

- **For:** works with tre 0.5.8 today, uses the same node tree as the rest of the surface, animates with the node (`shadows` is animatable), and behaves the same on any compositor with layer-shell.
- **Against:** every surface with a shadow is larger than its body; the margin costs buffer memory (134 KB per buffer for a 32 px margin on a 320x140 body) and needs the exclusive zone and input region set to the body.

## Decision

Option B (maintainer, 2026-10-27: it has the features wanted and fits a shell made of tre windows). Option A is not planned. If a later need appears, it would be an engine request and a new ADR.

## Consequences

- A surface with a shadow gets a transparent margin on each side, sized from the shadow's offset, blur and spread. The shell computes it; the exclusive zone covers the body only and the input region follows the body ([[Panel#Input region]]). Key names for the margin and the shadow tokens are proposed, not decided.
- The margin counts in the surface's size and memory; a Frame-sized margin is not measured and goes to the testing phase.
- The Frame needs no margin: its painter already covers the output ([[Frame#Shadows]]).
- Open: whether tre's painted hit shape excludes the `shadows` property (a test for the testing phase).

## Links

[[Shadows on Layer Surfaces]] · [[Surface Types]] · [[Bar]] · [[Panel]] · [[Frame]] · [[30 Decisions]]
