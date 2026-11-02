---
title: TRE-REQ-008 SMIL Animation in SVG Nodes
aliases: [TRE-REQ-008, SMIL in tre, Animated SVG Icons]
type: engine-request
status: draft
owner: phil
created: 2026-11-01
updated: 2026-11-01
tags: [engine-request, design, needs-verification]
related: ["[[Block Reference]]", "[[Building Blocks]]", "[[80 Engine Requests]]", "[[Risk Register]]"]
depends_on: []
---

# TRE-REQ-008: SMIL Animation in SVG Nodes

> [!summary]
> Let tre's `svg` node play the SMIL animation (`<animate>`, `<set>`, `<animateTransform>`) that an SVG document carries, so that animated icons such as the Material Line Icons set draw and move as their authors made them. Today tre draws such a document as one static frame. The request is for a time-sampled render of the document, driven by tre's own frame clock. It is not needed to ship v1.

> [!info] Not to be filed now
> Written 2026-11-01 at the maintainer's instruction ("A and C"), after the animated-icon test in [[Block Reference#The Icon Set Files (2026-11-01)]]. Not filed from this vault, and the `tre` session has not been told ([[AGENTS#6. Engine requests (tre / Tesserae)]]). The maintainer carries it. On 2026-11-01, at the maintainer's instruction, the shell session sent the `tre` session one mailbox message: a status question (is SMIL playback planned or rejected, which approach, would a time-sampled `svg_time` fit) with the path to this note. The message asks for answers only; it files nothing. A reply is information, checked against tre's docs before use.

> [!success] Not blocking v1
> The shell ships only the static Material Design Icons set (`mdi`) in v1 (decided 2026-11-01). Nothing in the specs waits on this request.

## Shell Need

The maintainer's icon sets include Material Line Icons (`mli`, MIT, by Vjacheslav Trushkin): 1,218 line icons, 1,216 of them animated with SMIL, among them loading spinners, alert pulses and draw-on intros. They would let a shell show a battery that charges, a spinner while the network connects or an alert that pulses, with no Python in the loop. Without SMIL support the same icons look unfinished (the `account` icon draws only its torso, because its strokes begin hidden). The shell cannot play SMIL itself: Python never runs per frame ([[AGENTS#3. Layering principle]]).

## What tre Does Today

| Fact                                                                                                                                                                                        | Source                                                                                                                        |
|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|
| An `svg` node takes a document in `svg` (str or bytes), a colour for `currentColor` in `svg_color`, pixels for `<image>` in `svg_images`; it scales the document uniformly and centres it                  | [Paint reference](https://mindderivative.github.io/tre/reference/paint/), read 2026-11-01                                       |
| tre parses SVG with `usvg` 0.47 (default features off, feature `text`)                                                                                                                       | `crates/engine-core/Cargo.toml`, line 34, local tre source at git `0fd1e7e`, read 2026-11-01                                   |
| `resvg`, the renderer `usvg` belongs to, supports only static SVG: "No animations" and "There are no plans on implementing them either"                                                       | [resvg README](https://github.com/linebender/resvg), read 2026-11-01. It does not say whether `usvg` differs                    |
| An SVG `<mask>` is drawn (luminance and alpha masks)                                                                                                                                        | tre `tests/test_svg.py`; and the test below                                                                                    |
| tre draws a SMIL document as one static frame, at every time: the painted pixels and the images were identical at the start, after `advance(500)`, at `snapshot(time=2.0)` and after `advance(2500)` for seven icons | Test of 2026-11-01, offscreen with `Window.snapshot()` on the local tre source (0.5.9); details in [[Block Reference#The Icon Set Files (2026-11-01)]] |
| tre animates node properties itself, in Rust, on its frame clock: `animate(...)` on `translate_x`, `opacity`, `scale`, `rotation_deg`, `trim_start`, `trim_end`, margins and more                       | [Properties reference](https://mindderivative.github.io/tre/reference/properties/), [Paint reference](https://mindderivative.github.io/tre/reference/paint/) |

## Why it Belongs in the Engine

The frame clock, the renderer and the SVG parser are tre's. The shell can swap a document string, but only from Python and only per frame, which the layering principle rules out ("Rust owns every frame; Python owns intent"). Playing an animation is mechanism: it decides what to draw at a time. The meaning, which icon plays when, stays in the shell.

## What the Icons Need

Measured on `material-line-icons.json` on 2026-11-01 (1,218 icons). This is the smallest subset that plays the whole set:

| Feature                                    | Use in the set                                                                                                                         |
|--------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------|
| Elements                                   | `<animate>` (1,215 icons, 5,031 instances), `<set>` (281, 525), `<animateTransform>` (104, 192). No `<animateMotion>`, no CSS `<style>`, no `<clipPath>` |
| Attributes                                 | `attributeName`, `fill` (always `freeze`), `dur`, `begin` (4,214, all plain clock offsets; no sync-base), `to`, `values`, `repeatCount` (448, always `indefinite`), `keyTimes`, `type` |
| `animateTransform` types                   | `rotate` (173), `translate` (10), `scale` (9)                                                                                           |
| Animated attributes                        | `stroke-dashoffset` (3,165), `opacity` (754), `fill-opacity` (723), `d` (678, a path morph), `r` (202), `transform` (192), `stroke-width` (20), `cx` (10), `y` (2), `cy` (2) |
| Durations                                  | 0.1 s to 30 s, median 0.4 s                                                                                                             |
| Not used                                   | `calcMode`, `keySplines`, `additive`, `by`, `from`, `end`, `restart`, `min`, `max`, `animateMotion`                                       |
| Loops                                      | 172 icons loop forever (`repeatCount="indefinite"`); 164 names end in `-loop`                                                           |

The hardest of these is the `d` morph (678 uses): interpolating between path strings of equal command structure.

## Proposed API

> [!danger] Proposal, not existing API
> Names are mine and tre may choose others.

```python
node = window.create("svg", svg=document, svg_color=(255, 255, 255, 255))

node.set(svg_time=0.4)              # the document, with SMIL evaluated at 0.4 s
node.animate("svg_time", to=2.0, duration_ms=2000)   # tre's own animation clock drives it
node.get("svg_duration")            # seconds the document runs, or None if it loops forever
```

- `svg_time` is a number of seconds, default `0.0`, animatable like other properties. The document is drawn as SMIL says it looks at that time. At `0.0` it is the first frame; with no SMIL in the document it changes nothing, so today's behaviour is the default.
- `svg_duration` is read-only: the time after which nothing changes, or `None` when an element repeats `indefinite`.
- The host (the shell) starts, stops and restarts by setting `svg_time` and using tre's existing `animate`, which runs in Rust. For a looping icon it repeats the animation.
- Optional, as a convenience: `svg_play` (bool) to let tre advance `svg_time` itself, looping when the document says so.
- `Window.snapshot(time=...)` could use the same clock, which makes tests deterministic.
- The subset above is the target. Unsupported SMIL (`animateMotion`, sync-base `begin`, `calcMode`) is ignored, not an error, so documents that use it still draw their first frame as today.

How tre does it is its own choice. One way, given that `resvg` and so `usvg` have no animation: read the SMIL elements in a pre-pass, evaluate their values at the time, write them into the attributes of a static copy of the document, and give that to `usvg`. Re-parsing a few-hundred-byte icon per sample may be cheap enough; this is not measured.

## Alternatives

| Alternative                                                                                                 | Verdict                                                                                                                                      |
|-------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------|
| The shell sets a new `svg` string every frame from Python                                                    | Rejected: per-frame Python.                                                                                                                  |
| The shell renders frames to bitmaps and swaps them                                                           | Rejected: Python per frame and memory for every frame.                                                                                        |
| An offline converter turns each icon into a tree of tre `path` nodes animated with tre's own animation       | Possible, but each icon becomes a node tree, the converter has to carry SMIL's rules, and `d` morphs have no tre counterpart.                  |
| A static end-state export of the line set (the shell's option B)                                             | No engine change, correct drawing, no motion. A fallback, not a substitute.                                                                    |

## If Declined

The shell ships only the static `mdi` set (decided 2026-11-01). It may later add a static export of the line set, with each icon in its end state and the animation tags removed, which tre draws correctly. Icons do not move; a spinner is not available as an icon, and a shell that wants one draws it with tre's `path` node and `trim_end`, or with a module's Canvas ([[Block Reference#Other]]).

## Size

Not measured. By reading the data: the elements and attributes in the table above are a small, regular subset, and the harder parts are the `d` morph and the timing model (`begin` offsets, `keyTimes`, `freeze`, indefinite repeats). The request does not ask for the whole of SMIL.

## Open Questions

- [ ] Whether tre prefers a pre-pass over `usvg`, a different SVG library or its own SMIL evaluator.
- [ ] Whether `usvg` already drops SMIL elements or fails on them (it drew the test icons without error).
- [ ] The cost of re-parsing a small document per sample, and of drawing 20 or 30 animated icons at once on a shell with several bars.
- [ ] Whether `svg_time` should be animatable by tre's easing, or driven only linearly.

## Links

[[Block Reference]] · [[Building Blocks]] · [[80 Engine Requests]] · [[Risk Register]]
