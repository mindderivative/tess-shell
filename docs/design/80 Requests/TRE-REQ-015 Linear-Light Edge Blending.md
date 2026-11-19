---
title: TRE-REQ-015 Linear-Light Edge Blending
aliases: [TRE-REQ-015, Linear Light Blend, sRGB Edge Blend]
type: engine-request
status: stable
owner: phil
created: 2026-11-07
updated: 2026-11-13
tags: [engine-request, design/rendering, needs-verification]
---

# TRE-REQ-015: Linear-Light Edge Blending

> [!NOTE]
> An opt-in way for tre to blend anti-aliased edges (paths, box corners, text) in linear light, for example a window option `blend="linear"` with the default `"srgb"` unchanged. Drafted by the code session (`tests/kwin/TRE-REQ-015-draft.md` in the tess-shell repository, 2026-11-07) at the maintainer's request; the maintainer carries it to tre (AGENTS section 6). Raised by the Frame's inner border looking thinner on curves ([Frame > KWin Retests and the Join Choice (maintainer, 2026-11-07)](../40%20Specifications/Surfaces/Frame.md#kwin-retests-and-the-join-choice-maintainer-2026-11-07), [Risk Register](../00%20Home/Risk%20Register.md) R-31).

## Shell Need

On a Frame the inner border (a 2 px light band, `#89b4fa`, on a dark ring `#1e1e2e`) "looks slightly thinner during the rounding than on the straight portions, like it is off by one pixel" (maintainer, KWin 6.8.2, 2026-11-07). It looks good otherwise.

## Findings (code session, not checked in the vault)

Measured on tesserae-engine 0.6.4, headless snapshots at scale 1.0, 1.25 and 1.5 ([M3 Build Log](../00%20Home/M3%20Build%20Log.md) D97; repro `tests/kwin/repro_srgb_edge_blend.py`, `tess_re` only):

| Quantity | Result |
|---|---|
| Geometry | Exact: the band's inner contour is 2.000 to 2.001 px from its outer contour all round |
| Coverage | Exact: summed border coverage averages 2.00 px on curves and straights (within 0.8 % of a supersampled band at 1.25x and 1.5x, 1.9 % at 1x) |
| Blend | An edge pixel is `dark + a * (light - dark)` in 8-bit sRGB. In linear light a half-covered pixel is 0.31 of the light colour, not 0.5 |
| Summed linear brightness across the band | 2.00 on a straight, 1.70 on curves at 1x, 1.80 at 1.5x: about 15 % (1x) or 10 % (1.5x) thinner to the eye |

A straight border on the pixel grid has whole pixels and no edge pixels; a curve has edge pixels on both sides, so only curves are dimmed. tre's `docs/design/gaps.md` says colours and the surface format are 8-bit sRGB throughout (the code session's reading). #needs-verification

## Proposed Change

An opt-in blend in linear light, for example `blend="linear"` on the window (default `"srgb"`, today's look), so that a coverage `a` gives `a` of the light colour in linear light. A per-node option is wanted less than a window option, unless it is cheap.

It changes every edge (light on dark gets slightly bolder, dark on light slightly lighter), so it must be an option. The shell would turn it on for the Frame and compare on KWin.

## Alternatives

- Leave it: the geometry is right and the difference is a perception of 10 to 15 % on curves.
- A shell workaround, such as a slightly wider band on curves: a compensation tuned to one colour pair, not wanted.

## Response from tre (2026-11-08, pasted by the maintainer; tre's measurements, not checked in the vault)

tre says it is possible, but a bigger job than the request's wording suggests. A throwaway headless test (llvmpipe, no windows, since deleted) proved the core mechanism. Nothing was committed or filed.

| Finding | Result |
|---|---|
| The shell's finding | Reproduces: a 2 px light-on-dark ring with the Frame's colours sums to 1.69 to 1.70 at scale 1.0 |
| A mechanism that works | vello_gpu's render target format is configurable and its main pass uses fixed-function blending. An sRGB-format target fed linear colours blends in linear light: the ring sums to 1.97, 1.98, 1.98 at three radii against an ideal 2.00; black on white, grey on grey and mid grey with yellow are within 1.2 %, inside the request's 2 % |
| A catch | vello stores paint colours as 8-bit linear, so very dark colours shift: `#1e1e2e` came out as (28, 28, 46) and `#101010` as `#0d0d0d`. A few levels on dark themes and banding in dark gradients; not fixable without patching vello |

Why it is more than a flag: a pipeline cannot mix colour spaces, so every colour input into a linear window must be converted. Solid colours (about 33 `set_paint` sites in `engine-render`) are mechanical. Images and shader passes (8-bit premultiplied sRGB today), gradients (interpolated in 8-bit sRGB inside vello), opacity layers and blend modes (8-bit intermediates, sRGB assumptions) need real work. Transparent windows matter most for the shell: a compositor expects premultiplied alpha in encoded space, so a linear mode needs a final convert pass and an extra full-size texture. The shared vello renderer is keyed by format, so linear windows get their own and use more memory. The default `blend="srgb"` stays pixel-identical.

tre's three options:
1. A staged build (its recommendation): a window option for solid colours, text and shadows first, with the transparent-window convert pass and the Frame acceptance test; then images, shaders and gradients, raising `ValueError` until they land. Cost: about the size of the TRE-REQ-013 stack.
2. A cheap interim with no engine change: the shell draws the Frame band with a fill shader that blends in linear light against its known ring colour, to check on KWin that linear blending fixes the perception before any engine-wide commit.
3. Decline.

**Maintainer's choice (2026-11-08): option 2**, and tre is to pass its recipe to the shell with no tests. He agreed with tre's recommendation to do it this way first.

### The option 2 recipe (from tre, untested)

A shader's output is stored as encoded sRGB bytes. If the shader blends the edge in linear light itself and writes the encoded result, the pixels are right with no engine change, with no colour quantisation (the texture holds exact bytes) and anti-aliasing from `sd_coverage` on a distance in physical pixels. It needs tesserae-engine 0.6.4 or later.

Conditions and limits, as tre gave them:

- It is exact only where the shader paints both colours itself, so the node must paint the ring and the band together as an opaque box. An edge against something the shader does not know (the window outside the node, a transparent area) stays blended in sRGB.
- It corrects only this shape. Text and other anti-aliased shapes stay sRGB-blended.
- The join's concave fillet is not done by the engine here; use `sd_round_union` for the corner shape. Animate the blend radius with `shader.animate`; `hit_path` gives the node the right hit shape.
- Names to avoid in the shader: the reserved `sd_*`, `Pixel`, `Frame`, `u`, `frame`, `content`.
- The uniforms are the ring and band colours as sRGB vec4 in 0 to 1, and a half width in logical pixels (1.0 for a 2 px band).

The WGSL sketch (tre's, unverified): `to_lin` and `to_srgb` convert between sRGB and linear; `shade(p)` takes `d_band = abs(d_centre) - half_width * frame.scale` (physical pixels), `a = sd_coverage(d_band)`, `lin = mix(to_lin(ring), to_lin(band), a)`, and returns `to_srgb(lin)` with alpha 1.0. The `d_centre` signed distance comes from the `sd_*` helpers. The code session holds the full text; the vault does not copy an unverified shader.

How to judge it: compare it with the current build on KWin at scale 1.0 and 1.5; the band should read as 2 px on curves as on straights. tre measured linear blending taking a curved 2 px band from 1.70 to 1.98 of the ideal 2.00. If the shell judges the shader good, tell tre, and that would justify the engine-wide `blend="linear"` option, staged as solid colours and text first, then images, shaders and gradients.

## Status

Stable (2026-11-13). Earlier: review, with the engine-wide option parked: the maintainer chose the shader interim (option 2). On 2026-11-10 he said `tess-shell` will build it right after releasing tess-utils `v0.1.1`. The shell tries it on the Frame band and the maintainer judges it on KWin. Only if he judges it good does the request return for the engine-wide option (option 1).

## Option 2 built (code session's report, 2026-11-10)

The shell built the interim as `Debug { Frame_Blend: SRGB | LINEAR }` with `SRGB` as the default (tess-shell commit `f34bcd9`, M3 Build Log D112). Reported measurements, on a private sway at the border's exact width of 2.000 px, not on KWin and not repeated by the vault:

| Case | Scale 1.0 | Scale 1.5 |
|---|---|---|
| The repro shape: path blend against shader | 1.686 against 1.994 | 1.790 against 2.005 |
| The real Frame over a dark desktop: path blend against shader | 1.686 against 1.879 | 1.790 against 1.926 |

Why the real Frame is not exact: the border's outer edge (against the ring) is exact because the shader paints both colours, but its inner edge is against the opening, and the compositor blends that edge in sRGB whatever the shader writes. The shader recovers about 60 to 65 % of the deficit. The code session expects an engine-wide linear blend would have the same inner-edge residual (sway only). So the result on a transparent opening is a partial fix, which is the limit tre named ("an edge against something the shader does not know stays blended in sRGB", [The option 2 recipe (from tre, untested)](#the-option-2-recipe-from-tre-untested)).

Two tre findings, not sent: a change of shader uniforms alone draws no frame in an otherwise still window; `Shader.animate(name, v, 0)` applies but wakes nothing. They are for the maintainer to carry to tre if he wants them filed.

The maintainer judges the result on KWin at scale 1.0 and 1.5.

The code session reports (peer message, 2026-11-11, not confirmed here) that `Frame_Blend: LINEAR` is now the default, that the maintainer confirmed the borders and the peek hover, click and drag on KWin, and that two bugs were fixed on the way: the peek input region (the painter needs a drawn node, commit `c8637b9`) and drag lag (a seek used `animate`, which continuous moves starved; it now uses `Shader.set`, commit `b43dd94`), recorded as D114 and D115 in the [M3 Build Log](../00%20Home/M3%20Build%20Log.md). Nothing is pushed. The maintainer judged it on KWin on 2026-11-12 and says the work was tested and completed: the borders are "great with LINEAR on all tests and variants, exactly what I wanted", and peek hover, click and drag are good under LINEAR (build log D114 and D115, [M3 Build Log](../00%20Home/M3%20Build%20Log.md)). `Frame_Blend: LINEAR` is the shell's default and `SRGB` stays selectable. He confirmed in chat on 2026-11-13: `Frame_Blend: LINEAR` "is awesome and works as I was hoping"; he judged it at both scale 1.0 and 1.5 and it passes on both; `LINEAR` is the permanent solution and the default ("it looks good and works efficiently"); and the Frame look "all looks good now". The engine-wide blend (option 1) is therefore not pursued. The request is `stable` ([Risk Register](../00%20Home/Risk%20Register.md) R-31 is closed).

## If Declined

The Frame keeps the sRGB look. Nothing in the shell is blocked.

## Acceptance

The repro's band at scale 1.0 and 1.5 with `blend="linear"`: the summed linear-light brightness across the band is within 2 % of 2.00 on the 45 degree ray and over the whole corner; default output is pixel-identical to today's.

## Links

[Frame](../40%20Specifications/Surfaces/Frame.md) · [Risk Register](../00%20Home/Risk%20Register.md) · [TRE-REQ-013 Structure-Preserving Path Morph](TRE-REQ-013%20Structure-Preserving%20Path%20Morph.md) · [80 Requests](80%20Requests.md)
