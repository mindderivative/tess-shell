---
title: Hit Testing for Concave Corners
aliases: [Frame Hit Testing, Concave Corner Pass-through]
type: research
status: draft
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [research, spec/surface, integration/wayland, needs-verification]
related: ["[[Surface Types]]", "[[TRE-REQ-001 Layer Surface Window]]", "[[Shadows on Layer Surfaces]]"]
depends_on: []
---

# Hit testing for concave corners

> [!summary]
> A Frame draws a ring with rounded convex and concave corners. Clicks on the ring must reach the shell; clicks in the interior, and in the concave notch of a corner, must pass to the window below. tre 0.5.8 cannot do that for a path node. The maintainer confirmed that tre will provide a path forward. A workaround works today.

## What tre does today

Answer from the `tre` session over the mailbox (2026-10-25), checked against the tre source at `main` commit `aeabb46` (`crates/engine-core/src/tree/region.rs`). PyPI's latest is 0.5.8; `main` is ahead of it.

| Question | Finding |
|---|---|
| Does `input_region="auto"` use a path node's fill? | No. A path node counts as its layout box, with `corner_radius` if set. The source comment reads "A path's own shape is not decomposed (yet): its box covers it". A concave notch is covered, so clicks in it do not pass through. |
| How is a path node hit for node events? | By its box (`shape_contains`: the box with rounded corners). The fill is ignored. |
| What is shape-aware today? | A canvas with `set_hit_test_circle` is exact for node events and region. A canvas with `set_hit_test_path` is hit within `tolerance` of the path's outline for node events, a stroke and not a filled region; for `"auto"` it is its box. |
| Would a real polygon fix `"auto"`? | Not alone. `bands()` keeps one `[min, max]` x-span per polygon per horizontal band (`strip_extent`), so a ring's left and right sides in one band become one span across the hole. |

## The path forward

The maintainer confirmed (2026-10-25) that tre will provide a way for unfilled parts of concave and convex corners to pass clicks through. tre described two changes, not a commitment and not a filed issue:

1. **Hit testing for path nodes by fill** (the path's fill rule and the node transform), for node events and as the polygon for the region. It changes which clicks a path node takes, so tre would make it a property (`hit_shape`: `box` or `fill`, default `box`).
2. **True scanline interval unions per band** in the region builder, rounded outward so the region never loses a drawn pixel, keeping the 256-rectangle cap and the coarser-step fallback.

tre's estimate: medium effort in the engine core plus tests, risk low to medium. Ring bands with curved corners may need steps above 2 px to stay under 256 rectangles at 4K.

## Workaround that works today

- `input_region` set to an explicit list of `(x, y, w, h)` rectangles built from the shell's own ring geometry. Up to 256 rectangles; live through `set()`.
- For node events on a constant-width ring: a canvas with `set_hit_test_path(centerline, tolerance=half the thickness)`.

This costs the shell the geometry code, and the 256-rectangle cap limits the curve detail.

## Also noticed

tre `main` is already at 0.5.9 development: its latest commit says windows share one renderer and the bundled fonts, so 50 windows hold 98 MiB, not 310 (#235). That bears on the memory budget of a Frame on several monitors ([[Goals and Non-Goals]] G5). Unreleased; confirm when published. #needs-verification

## Open

- [ ] When tre ships shape-aware hit testing, update the Frame mapping in [[Surface Types]] to use it.
- [ ] Whether the explicit-rectangle workaround is enough for v1 Frame, given the 256 cap and 4K.
- [ ] The first tre release that includes it.

## Links

- [[Surface Types]] · [[TRE-REQ-001 Layer Surface Window]] · [[90 Research]]
