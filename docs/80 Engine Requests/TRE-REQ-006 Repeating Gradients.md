---
title: TRE-REQ-006 Repeating Gradients
aliases: [TRE-REQ-006, tre Gradient Repeat, Tiling Gradient]
type: engine-request
status: draft
owner: phil
created: 2026-10-27
updated: 2026-10-27
tags: [engine-request, needs-verification]
---

# TRE-REQ-006: Repeating Gradients

> [!NOTE]
> Let a `tre.Gradient` repeat its ramp a set number of times across the node's bounds, so a gradient border or fill can tile (stripes, repeated colour cycles around a ring). The underlying graphics library already supports a repeat mode; tre does not expose it. Written for the future: the maintainer will carry it to tre later, and the shell works without it.

> [!NOTE]
> **Not to be filed now**
> The maintainer asked for this request to be written and kept (2026-10-27). It is not filed from this vault, and the `tre` session has not been told (AGENTS > 6. Engine requests (tre / Tesserae)).

## Shell Need

The Frame's border colour can be a gradient, and tiling it is an opt-in (`border_tile`, [Frame > Thickness, radii, border, colours](../40%20Specifications/Surfaces/Frame.md#thickness-radii-border-colours)). "Tiling" is read here as: the ramp repeats along the gradient, instead of stretching once across the shape. Uses:

| Use                                               | Gradient                       | What repeats                             |
|---------------------------------------------------|--------------------------------|------------------------------------------|
| A striped or cycling border around the whole ring | sweep around the screen centre | The ramp repeats N times around the ring |
| A banded fill or border across a bar              | linear                         | The ramp repeats N times along its line  |
| A concentric pattern                              | radial                         | The ramp repeats N times outward         |

## What Tre Does Today

| Fact                                                                                                                                                                                    | Source                                                                               |
|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------|
| `Gradient` has three constructors, `linear(stops, angle)`, `radial(stops, center, radius)` and `sweep(stops, center, start)`; stops are colours or `(offset, colour)` pairs from 0 to 1 | [paint reference](https://mindderivative.github.io/tre/reference/paint/), `python/tre/_core.pyi` (read 2026-10-27) |
| A gradient spans the node's own bounds; for a path's stroke, the stroke's bounds                                                                                                        | [paint reference](https://mindderivative.github.io/tre/reference/paint/)                                           |
| The Python `Gradient` has no spread, extend or repeat option                                                                                                                            | `Gradient` docstring, `dir(tre.Gradient)` on tre 0.5.8                               |
| `Gradient::resolve` builds the `peniko` gradient from the shape and stops and sets no extend mode                                                                                       | `crates/engine-core/src/gradient.rs` (read 2026-10-27)                               |
| The SVG path converts an SVG spread method (pad, reflect, repeat) to `peniko::Extend`, so the graphics library supports it                                                              | `crates/engine-core/src/svg.rs` lines 239 to 244                                     |
| `peniko` 0.6.1, the version tre depends on, has an `extend` field on its `Gradient`                                                                                                     | `peniko-0.6.1/src/gradient.rs` line 305 (read 2026-10-27)                            |
| Animating `fill` between gradients works only for the same kind and the same number of stops                                                                                            | [paint reference](https://mindderivative.github.io/tre/reference/paint/), `Gradient::animates_to`                  |

## Why it Belongs in the Engine

It is paint mechanism: how a ramp is laid across a shape. The shell can imitate it by repeating the stops itself, but then a gradient with N repeats has N times the stops, an animated gradient must keep the same count, and the shape's repeat count is baked into the stop list. A native repeat keeps the stop list small and lets a repeat count animate.

## Proposed API

> [!CAUTION]
> **Proposal, not existing API**
> Names are mine and tre may choose others.

```python
Gradient.sweep(stops, center=(0.5, 0.5), start=0, repeat=1.0)
Gradient.linear(stops, angle=180, repeat=1.0)
Gradient.radial(stops, center=(0.5, 0.5), radius=1.0, repeat=1.0)
```

- `repeat` is the number of times the ramp repeats across its span (1.0 is today's behaviour). A fraction is allowed. It must be positive.
- Spread mode: tiling by `peniko`'s repeat extend, with an optional `spread="repeat"` or `"reflect"` for a mirrored ramp. Minimal request: `repeat` alone.
- A sweep's span is a full turn; a linear's is its line; a radial's is its radius.
- Animating `repeat` interpolates it (it is a number), like `angle` today. #needs-verification that this fits `animates_to`.

## Alternatives

| Alternative                         | Verdict                                                                                            |
|-------------------------------------|----------------------------------------------------------------------------------------------------|
| The shell repeats stops in the list | Works today with no engine change; costs stop-count and fixes the repeat count                     |
| A node pattern or tiled image       | A different feature, for images; not a gradient                                                    |
| An SVG with a repeat spread method  | tre draws it, but an SVG is not a node's `fill` or `stroke_color`, so it cannot be a ring's border |

## If Declined

The shell builds the repeat from stops: it expands a ramp N times into one stop list, with offsets scaled to 0 to 1. The result looks the same; it only costs more stops and the repeat count cannot animate smoothly. The Frame's `border_tile` option stays.

## Size

Small, by reading the code: a field on the core `Gradient`, one extra argument on the three Python constructors, and `resolve` setting the extend mode and scaling the line, radius or sweep angle. Not measured.

## Links

[Frame](../40%20Specifications/Surfaces/Frame.md) · [Style Schema](../41%20TDL%20Reference/Style%20Schema.md) · [80 Engine Requests](80%20Engine%20Requests.md)
