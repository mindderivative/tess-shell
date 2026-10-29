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

# Hit Testing for Concave Corners

> [!summary]
> A Frame draws a ring with rounded convex and concave corners. Clicks on the ring must reach the shell; clicks in the interior, and in the concave notch of a corner, must pass to the window below. tre 0.5.8 cannot do that for a path node. The maintainer confirmed that tre will provide a path forward. A workaround works today.

## What Tre Does Today

Answer from the `tre` session over the mailbox (2026-10-25), checked against the tre source at `main` commit `aeabb46` (`crates/engine-core/src/tree/region.rs`). PyPI's latest is 0.5.8; `main` is ahead of it.

| Question                                           | Finding                                                                                                                                                                                                                                   |
|----------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Does `input_region="auto"` use a path node's fill? | No. A path node counts as its layout box, with `corner_radius` if set. The source comment reads "A path's own shape is not decomposed (yet): its box covers it". A concave notch is covered, so clicks in it do not pass through.         |
| How is a path node hit for node events?            | By its box (`shape_contains`: the box with rounded corners). The fill is ignored.                                                                                                                                                         |
| What is shape-aware today?                         | A canvas with `set_hit_test_circle` is exact for node events and region. A canvas with `set_hit_test_path` is hit within `tolerance` of the path's outline for node events, a stroke and not a filled region; for `"auto"` it is its box. |
| Would a real polygon fix `"auto"`?                 | Not alone. `bands()` keeps one `[min, max]` x-span per polygon per horizontal band (`strip_extent`), so a ring's left and right sides in one band become one span across the hole.                                                        |

## The Path forward

The maintainer confirmed (2026-10-25) that tre will provide a way for unfilled parts of concave and convex corners to pass clicks through. tre described two changes, not a commitment and not a filed issue:

1. **Hit testing for path nodes by fill** (the path's fill rule and the node transform), for node events and as the polygon for the region. It changes which clicks a path node takes, so tre would make it a property (`hit_shape`: `box` or `fill`, default `box`).
2. **True scanline interval unions per band** in the region builder, rounded outward so the region never loses a drawn pixel, keeping the 256-rectangle cap and the coarser-step fallback.

tre's estimate: medium effort in the engine core plus tests, risk low to medium. Ring bands with curved corners may need steps above 2 px to stay under 256 rectangles at 4K.

## Released in Tre 0.5.9 (2026-10-27)

`tesserae-engine` 0.5.9 is on PyPI (uploaded 2026-10-27, checked). Its migration notes list `hit_shape` on a `path` node (#236): `"box"` (the default, as before) or `"painted"`. A painted path is hit by its fill region and its stroke, not its box, so a click in a ring's hole or a concave notch passes to what is behind it, for pointer events and for a layer window's `input_region="auto"` alike. The region builder now handles shapes with holes and concave corners. tre says it is what a screen frame needs: a path with convex outer corners and concave inner fillets, clickable only on the ring. tre live-tested a rounded frame on sway and KWin before release (the earlier report). I have not run it. tre lists what it did not check: a 4K frame with many joins and output hot-plug on KWin with a real unplug. The explicit-rectangle workaround below is no longer needed for v1; keep it only as a fallback.

## Tre Issue #236

`tre` scoped the work as [tre #236](https://github.com/mindderivative/tre/issues/236), read 2026-10-25: OPEN, Backlog, not approved, nothing started. Three stages, each shippable:

1. True scanline spans in `bands()`, so a region can have holes. No API change; pure engine tests.
2. `hit_shape` on a path node: `"box"` (today, the default) or `"painted"` (the fill region united with the stroke outline), used by node events and by `input_region="auto"`.
3. **A live test of the shell's frame** on headless sway and KWin, plus docs.

Measured cost for a 3840 x 2160 ring, 48 px thick, outer radius 32, inner radius 24: 66 rectangles at 2 px bands (40 at 4 px, 22 at 8 px), under the 256 cap. A frame with ten fillet joins might reach the cap, where the existing fallback uses 4 or 8 px bands. Accuracy contract: a click up to about one band (2 px) inside the unfilled side of a curve may still be taken.

Decisions in #236 for the maintainer (tre's, not the shell's): the default of `hit_shape` (recommended: opt-in), that `auto` follows it, what is out of scope (`svg` nodes, a fill-based canvas hit path), and the accuracy contract.

## Workaround that Works Today

- `input_region` set to an explicit list of `(x, y, w, h)` rectangles built from the shell's own ring geometry. Up to 256 rectangles; live through `set()`.
- For node events on a constant-width ring: a canvas with `set_hit_test_path(centerline, tolerance=half the thickness)`.

This costs the shell the geometry code, and the 256-rectangle cap limits the curve detail.

## Also Noticed

tre 0.5.9 shares one GPU device and one renderer among windows (#235). Five small windows hold the video memory one does (31 MiB, was 83 MiB, on AMD RADV), and fifty small windows hold 98 MiB of process memory, not 310 or 532 ([migration notes](https://mindderivative.github.io/tre/migrating-0.5/)). That helps a Frame, which is five windows per monitor ([[Goals and Non-Goals]] G5). Measured by tre on one AMD GPU; not run here.

## Open

- [x] When tre ships shape-aware hit testing, update the Frame mapping in [[Surface Types]]: done (tre 0.5.9 shipped it).
- [x] Superseded by tre 0.5.9: `hit_shape="painted"` with `input_region="auto"` replaces the explicit-rectangle workaround (the maintainer had accepted the workaround for v1 on 2026-10-25; 4K was not a concern).
- [x] The first tre release that includes #236: 0.5.9 (2026-10-27).

## Links

- [[Surface Types]] · [[TRE-REQ-001 Layer Surface Window]] · [[90 Research]]
