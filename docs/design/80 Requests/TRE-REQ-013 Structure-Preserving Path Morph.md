---
title: TRE-REQ-013 Structure-Preserving Path Morph
aliases: [TRE-REQ-013, Melded Join Animation Mechanisms, join animation, path morph]
type: engine-request
status: stable
owner: phil
created: 2026-11-06
updated: 2026-11-10
tags: [engine-request, needs-verification]
---

# TRE-REQ-013: Structure-Preserving Path Morph

> [!NOTE]
> Four mechanisms for animating a join that grows out of a shape, all asked of tre so the shell can build the join each way and keep the one that looks best or costs least, or more than one. They are not alternatives to pick between in this request; each is wanted on its own. They are numbered in the order tre is asked to build them ([Build Order](#build-order)): (1) transform and corner pieces, (2) shader joins with engine-animated uniforms, (3) a corner-preserving path morph, which gives the note its title, (4) an engine-evaluated parametric path. The maintainer's instruction (2026-11-06): build all four in tre to give the shell options, because one may look better or be more performant. Draft for the maintainer to carry to tre; not filed.

> [!TIP]
> **Released in tre 0.6.4 (PyPI, 2026-11-07): all four mechanisms**
> Read by the vault session on 2026-11-07 in the local tre checkout (`LOG.md`, tag `v0.6.4`, PyPI `tesserae-engine 0.6.4` listed). The maintainer carried the request; tre filed it as four issues, built in the build order below, and all four are Done: #269 (step 1), #270 (step 2), #271 (step 3), #272 (step 4). tre's tests ran headless on Linux; KWin, a real GPU and a 1.5 scale on a compositor are not checked by tre and are the shell's and the maintainer's to check.
>
> | Step | What shipped | Where it differs from this request |
> |---|---|---|
> | 1 | `Node.set(transform_origin=(x, y))`, fractions of the box, default `(0.5, 0.5)`; `corner_style="round"` or `"concave"`, or a 4-tuple, with the radius from `corner_radius`, which animates | The origin is not animated. A concave corner drawn by a shadow still takes the rounded corners only |
> | 2 | `Shader.animate(name, to, duration_ms, easing)`; `hit_path` on a node; the helpers `sd_circle`, `sd_box`, `sd_round_box`, `sd_round_union` (an exact circular fillet), `sd_smooth_union`, `sd_coverage`; `frame.scale` | Hit testing follows a path (`hit_path`, in the node's pixels, not animated: a body that slides must set it again), not `hit_shape="painted"` by alpha, because reading alpha back each pointer move is no option. A shader may not declare a function named like a helper: one breaking change (`docs/migrating-0.6.md`, `## 0.6.4`) |
> | 3 | `morph="structure"` or `"strict"` on a path. With equal command sequences every point is interpolated, so an arc between two radii is exactly the arc of the lerped radius | Different command sequences: `structure` resamples, `strict` raises from `animate`. A different start point or winding is the caller's to match. The default stays `resample` |
> | 4 | A path whose `data` has `{expression}` holes (numbers, names, `+ - * ( )` and signs) and a `params` dict; `Node.animate_param(name, to, duration_ms, easing)` | `animate("data")` on a template raises; `set(data=plain)` ends the template; `animate_param` has no `on_complete` |
>
> Also answered from the source: `MORPH_SAMPLES` is 96; and the SMIL `d` morph in an `svg` node already interpolates equal command sequences, so an svg node keeps its arcs (which the code session found and built on). tre also fixed a bug found while measuring #272: an animation started by a timer on a live window drew no frames (it now counts animations started since the tick); a regression test in tre went from 0 to 26 frames. Not checked by tre: whether versions before 0.6.4 had it, KWin, and the per-frame cost of a join shader.
> The two other requests that this work depended on were released earlier: TRE-REQ-012 in 0.6.2 and TRE-REQ-007 in 0.6.3 ([80 Requests](80%20Requests.md)).

> [!WARNING]
> **Evidence is partly the code session's, partly read from tre's source**
> What tre has today was read by the vault session on 2026-11-06 in the local checkout `~/Projects/rustDev/projects/tre` (0.6.3, commit `55b63ac0`): `docs/guide/animation.md`, `docs/guide/shaders.md`, `docs/reference/shader.md`, `docs/reference/paint.md` and `crates/engine-core/src/path.rs`. What the shell saw on KWin comes from [M3 Build Log](../00%20Home/M3%20Build%20Log.md) D84 and D85 and the maintainer's look test; the vault session has not reproduced it. The code session should add a repro under `tests/kwin/` before this is carried. An earlier version of this note said tre had no path morph and animated only `translate` and `opacity`. Both were wrong, and are corrected below.

## Shell Need

A Panel melded to a Frame looks as if it grows out of the ring ([Frame > Melding](../40%20Specifications/Surfaces/Frame.md#melding)). At rest the ring and body are one contour with rounded fillets where they meet. While the Panel slides in or out, the fillets should grow with it and the edge should stay smooth at every frame. On KWin (maintainer, 2026-11-06) the join shows a 90 degree angle while sliding and then a chamfer, and the edge looks slightly pixelated ([Frame > Found on KWin: the look is not good enough (maintainer, 2026-11-06)](../40%20Specifications/Surfaces/Frame.md#found-on-kwin-the-look-is-not-good-enough-maintainer-2026-11-06)). Python must not run per frame ([Vault Reference > Layering principle](../00%20Home/Vault%20Reference.md#layering-principle)).

## What tre Does Today

| Capability | State |
|---|---|
| Animating a path's `data` | Exists. Both paths are resampled by arc length and aligned at the best starting point; two closed shapes, or two open lines, morph smoothly; different subpath counts, or open against closed, switch at the halfway point; mid-frames are polygons of `MORPH_SAMPLES` points per subpath (96 in the source since v0.3.4; the code session reported 48); the last frame is exactly the target ([Sources](#sources)) |
| Natively animated properties | `fill`, `stroke_color`, `stroke_width`, `opacity`, `corner_radius` (a number or four corners), `shadows`, `translate_x`, `translate_y`, `scale`, `rotation_deg`, `data`, `trim_start`, `trim_end`, `svg_time`, and the layout properties (`width`, `height`, `x`, `y`, `padding`, `margin`, `gap` and so on, 0.5.6) |
| Shaders | Exist (0.5.1): WGSL as a `fill` or an `effect`, uniforms set with `shader.set(uniforms=...)`, an `animated` flag that repaints every frame from `frame.time`; a change to a uniform repaints only the node's box |
| Hit testing | `hit_shape="painted"` on a `path` node (0.5.9) |
| Per-frame Python | `window.on("frame", ...)` exists, and a handler can `set` a node's `data` each frame. This is allowed by tre and rejected by the shell's layering rule, so it is not one of the four |

So the engine already has pieces of mechanisms 1 and 2, and a path morph (mechanism 3) that does not keep corners. The mechanisms below fill the gaps, in build order.

## Build Order

The number of a mechanism is its place in the build order. Step 1 is built first. The order is a recommendation; the maintainer and tre decide it. Each step is a finished, useful feature on its own, so stopping after any step leaves tre better and the shell with that many ways to build the join.

| Step | Mechanism | What tre adds | Why it comes here (proposed) |
|---|---|---|---|
| 1 | Transform and corner pieces | A transform origin for `scale` and `rotation_deg`; a concave corner on a box | Smallest and most general; the engine already animates `scale` and `corner_radius`, so most of the machinery exists |
| 2 | Shader joins | Engine-animated shader uniforms; painted hit testing on a shader node; a helper library for rounded shapes and smooth unions | Shaders exist today; this adds the animation and the input rules |
| 3 | Corner-preserving path morph | An opt-in morph mode that keeps lines, arcs and curves | A change to the morph core; useful beyond joins, and larger than steps 1 and 2 |
| 4 | Engine-evaluated parametric path | A path template with named parameters that the engine animates and redraws | A new concept (a template language for paths), so it comes last |

## The Four Mechanisms

Each stands on its own, so each has its own need, change, acceptance criteria and fallback. They are listed in build order. A mechanism with parts (Part A, Part B) is built in the order of its parts.

### 1. Transform and Corner Pieces

- **Need.** Build the join from simple pieces tre already animates: a fillet is a small node that grows from the corner it touches, the body is a rounded box that translates.
- **Gap.** `scale` and `rotation_deg` have no stated origin, so a piece cannot grow from one corner; a box cannot draw a concave (inverse) corner, so the fillet is a path, and a path's edges are only as smooth as a path's.
- **Change.** Part A: a transform origin for `scale` and `rotation_deg` (a fraction of the box or a point in pixels, default the centre as today). Part B: a per-corner concave radius on a box, for example `corner_style` with `round` or `concave` per corner, so a fillet is one box node whose `corner_radius` the engine already animates, drawn as an exact analytic arc like every box corner.
- **Acceptance.** A box with a concave corner of radius 12 draws a smooth arc at scale 1.0 and 1.5; `corner_radius` animates from 0 to 12 on it; a piece scaled about its corner stays attached to that corner; clicks in a concave notch fall through (`hit_shape="painted"` or the box's own shape).
- **If declined.** The shell uses the other mechanisms; without Parts A and B the pieces are paths.

### 2. Shader Joins With Engine-Animated Uniforms

- **Need.** Draw the ring and the body as one shape in a shader, joined by a smooth union whose blend radius is a uniform, so the fillet is exact at any scale and grows with the slide. The body's position and the blend radius should be animated by the engine, with no Python per frame.
- **Gap.** Shader uniforms are set by `shader.set(...)`, not animated by the engine; `animated=True` makes the node repaint every frame from time, not from a tween. Whether a shader node can be clipped, hit-tested as painted, and used inside an `input_region="auto"` is not stated.
- **Change.** Part A: a shader uniform can be animated like a node property: `shader.animate("radius", 12, 200, easing=...)` for a number and for a `vec2`, `vec3` or `vec4`, interrupted and retargeted like other animations, repainting only while it runs. Part B: a shader node can take `hit_shape="painted"` by alpha, or be given a shape to hit-test. Part C: a documented shader helper library for rounded shapes (signed distance functions and a smooth union) so a shell does not write its own.
- **Acceptance.** A shader draws a body joined to a band with a blend radius animated from 0 to 12 px, with smooth edges at scale 1.0 and 1.5, with no frames drawn once the animation has finished (an idle surface draws nothing), and with clicks passing through the notches.
- **If declined.** The shell uses the other mechanisms; the shader route is dropped.

### 3. Corner-Preserving Path Morph

- **Need.** Morph a whole shape, a ring with a notch and fillets, to another without smearing its corners or turning arcs into polygons.
- **Gap.** The morph resamples by arc length, so corners are cut and mid-frames are polygons.
- **Change.** When both paths have the same sequence of commands, animate each command's numbers (coordinates, radii) directly and keep lines, arcs and curves as such, so every mid-frame is an exact, anti-aliased path. Offer it as an opt-in mode (for example `morph="structure"` on the node, or a rule on the path-data change) that keeps today's resampling as the default, and say which paths qualify; when the sequences differ, fall back to resampling or raise a clear error the caller can choose.
- **Acceptance.** Two paths with the same command sequence animate with no corner chamfer at t=0 and no smearing, in a repro; a mid-frame of a rounded rectangle morph keeps its arcs; the last frame is the exact target.
- **If declined.** The shell uses the other mechanisms.

### 4. Engine-Evaluated Parametric Path

- **Need.** Describe the whole ring and its join once, with a few named parameters (the body's offset, the fillet radius, the corner radius), and let the engine redraw the exact path each frame as those parameters animate, with no Python.
- **Gap.** A path's data is a fixed string. Changing the shape each frame needs the caller to set a new string, which is the per-frame Python route the shell rejects.
- **Change.** A path node takes a template with named parameters, for example `path.set(data="M ... A {r} {r} ... ", params={"r": 0, "dx": 40})`, and `path.animate_param("r", 12, 200, easing=...)`. The engine evaluates the template in Rust each frame, flattens arcs and curves to the device scale as it does for any path, and repaints only the node's box. Parameters are numbers in path commands (coordinates, radii) and simple sums and products of them; nothing else is evaluated.
- **Acceptance.** A ring with a notch and fillets, driven by `r` and `dx`, animates from collapsed to open with exact arcs at every frame, with no Python per frame, and ends equal to the same shape written as plain path data.
- **If declined.** The shell uses the other mechanisms.

## Why It Belongs in the Engine

Interpolating, evaluating and rasterising a shape is geometry and painting: mechanism, not meaning ([Vault Reference > Layering principle](../00%20Home/Vault%20Reference.md#layering-principle)). A caller cannot do any of it without Python per frame. Other callers would use these too: icon and shape morphs, soft unions, concave corners (a tab strip, a notch, a speech tail), parametric shapes.

## What the Shell Does With All Four

When tre has them, the shell builds the melded join each way behind one switch and compares them on KWin and sway: how the edge looks at scale 1.0 and 1.5 (smoothness, seams, chamfer), the cost per frame (the painter's `total_ms` while animating), memory (video and RSS), frames drawn at idle (must be 0), and how much shell code each needs. The maintainer chooses (AGENTS > Hard rules rule 5): one, or a different mechanism for a different case. The comparison table goes into [Frame](../40%20Specifications/Surfaces/Frame.md).

Until tre has them, the shell keeps the current build (the ring without its body, a layer slid over it, the fillets arriving last, D84 and D85) and tries what tre has now: small closed join pieces morphed with today's path morph ([Frame > A Join Built From Small Morphing Shapes (Proposed)](../40%20Specifications/Surfaces/Frame.md)) and box pieces using `scale` and `corner_radius`.

## Open Questions

1. [ ] Should tre keep the build order in [Build Order](#build-order), and may it build two steps in parallel? Context: the order is a recommendation. Recommendation: keep the order, and accept parallel work on steps that do not share code.

## Questions After Testing

1. [ ] Is the morph sample count 96 (`path.rs`) or 48 (the code session's figure) for the build it ran? Context: the code session ran tesserae-engine 0.6.1 in its venv; 0.6.3 is released. Recommendation: use the figure measured on the released 0.6.3. Answered by: reading `MORPH_SAMPLES` or measuring on 0.6.3.
2. [ ] Can a shader node be hit-tested and clipped today? Context: the docs read do not say. Recommendation: keep the request for Part B of mechanism 2 until a test shows it works. Answered by: a test shader node with `hit_shape` and a clip.
3. [ ] Does the SMIL `d` morph the code session is probing already keep arcs and curves ([TRE-REQ-008 SMIL Animation in SVG Nodes](TRE-REQ-008%20SMIL%20Animation%20in%20SVG%20Nodes.md))? Context: if it does, mechanism 3 is partly covered. Recommendation: wait for the probe before changing mechanism 3. Answered by: the code session's probe.

## Sources

- tre `docs/guide/animation.md` ("What animates", "Morphing paths"), `docs/guide/shaders.md`, `docs/reference/shader.md`, `docs/reference/paint.md` ("Hit testing a path"), `crates/engine-core/src/path.rs` (module comment and `MORPH_SAMPLES`), read 2026-11-06 in the local checkout at 0.6.3. #needs-verification against the released docs, which were not reachable from the vault session (404 on 2026-11-06).

## Links

- [80 Requests](80%20Requests.md) · [Frame](../40%20Specifications/Surfaces/Frame.md) · [M3 Build Log](../00%20Home/M3%20Build%20Log.md) · [Risk Register](../00%20Home/Risk%20Register.md) · [TRE-REQ-008 SMIL Animation in SVG Nodes](TRE-REQ-008%20SMIL%20Animation%20in%20SVG%20Nodes.md)
