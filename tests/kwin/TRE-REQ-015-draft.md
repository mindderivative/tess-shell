# TRE-REQ-015 (draft): blend anti-aliased edges in linear light (option)

Draft by the tess-shell code session, 2026-11-07. The maintainer asked for it to be created; the vault
session writes the note in `80 Requests`. Not sent to tre by the code session.

## What the maintainer sees (KWin 6.8.2, 2026-11-07)

On a Frame, the inner border (a 2 px light band, `#89b4fa`, on a dark ring `#1e1e2e`) "looks slightly
thinner during the rounding than on the straight portions, like it is off by one pixel". It looks good
otherwise.

## What was measured (tesserae-engine 0.6.4, headless snapshots at scale 1.0, 1.25, 1.5)

- Geometry is exact: the band's inner contour is 2.000 to 2.001 px from its outer contour all round.
- Coverage is exact: the sum of border coverage across the band averages 2.00 px on curves and on
  straights (window sums within 0.8 % of an exact supersampled band at 1.25x and 1.5x, 1.9 % at 1x).
- What differs is the blend. An anti-aliased edge pixel is `dark + a * (light - dark)` in 8-bit sRGB.
  In linear light a half-covered pixel is 0.31 of the light colour, not 0.5. A straight border on the
  pixel grid has whole pixels and no edge pixels; a curve has edge pixels on both sides. Summed
  linear-light brightness across the band is 2.00 on a straight and 1.70 on the curves at 1x (1.80 at
  1.5x): about 15 % (1x) or 10 % (1.5x) thinner to the eye with the coverage exactly right.
- Repro (tess_re only): `tests/kwin/repro_srgb_edge_blend.py`. tre's `docs/design/gaps.md` says colours
  and the surface format are 8-bit sRGB throughout.

## Ask

An opt-in way to blend anti-aliased edges (path, box corners, text) in linear light, for example a
window option `blend="linear"` (default `"srgb"`, today's look), so that a coverage `a` gives `a` of the
light colour in linear light. If it is cheap, a per-node option is wanted less than a window one.

## Why it would fix the look

With the coverage exact, linear-light blending makes the summed brightness across the band equal on
curves and straights (2.00 in the repro), which is what the eye reads as width. It changes every edge
(light on dark gets slightly bolder, dark on light slightly lighter), so it must be an option; the shell
would turn it on for the Frame and compare on KWin.

## Acceptance

The repro's band at scale 1.0 and 1.5 with `blend="linear"`: the summed linear-light brightness across
the band is within 2 % of 2.00 on the 45 degree ray and over the whole corner; default output is
pixel-identical to today's.
