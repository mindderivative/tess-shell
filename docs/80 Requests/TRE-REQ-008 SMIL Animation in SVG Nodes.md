---
title: TRE-REQ-008 SMIL Animation in SVG Nodes
aliases: [TRE-REQ-008, SMIL in tre, Animated SVG Icons]
type: engine-request
status: review
owner: phil
created: 2026-11-01
updated: 2026-11-02
tags: [engine-request, design, needs-verification]
---

# TRE-REQ-008: SMIL Animation in SVG Nodes

> [!NOTE]
> Let tre's `svg` node play the SMIL animation (`<animate>`, `<set>`, `<animateTransform>`) that an SVG document carries, so that animated icons such as the Material Line Icons set draw and move as their authors made them. Today tre draws such a document as one static frame. The request is for a time-sampled render of the document, driven by tre's own frame clock. It is not needed to ship v1.

> [!TIP]
> **Taken up by tre (2026-11-01) and built on a local branch (2026-11-02)**
> The maintainer gave the `tre` session the go-ahead to plan, scope and start on this request. tre scoped it and filed [tre issue #245](https://github.com/mindderivative/tre/issues/245), now in Ready and not started; work waits for the shell's answers (sent 2026-11-01) or the maintainer's go. The vault copy below is the shell's statement of the need and stays a draft. History: a status question went to `tre` first (it found no issue, no design note and no mention in its live code; the maintainer then gave the go-ahead); the shell sent the prior art found in tre's own `archive/` (below) and, after tre's three questions, the measurements under "tre's Scope and the Shell's Answers". Replies are information, checked against tre's docs and source before use.

> [!TIP]
> **Not blocking v1**
> The shell ships only the static Material Design Icons set (`mdi`) in v1 (decided 2026-11-01). Nothing in the specs waits on this request.

## Shell Need

The maintainer's icon sets include Material Line Icons (`mli`, MIT, by Vjacheslav Trushkin): 1,218 line icons, 1,216 of them animated with SMIL, among them loading spinners, alert pulses and draw-on intros. They would let a shell show a battery that charges, a spinner while the network connects or an alert that pulses, with no Python in the loop. Without SMIL support the same icons look unfinished (the `account` icon draws only its torso, because its strokes begin hidden). The shell cannot play SMIL itself: Python never runs per frame (AGENTS > 3. Layering principle).

## What tre Does Today

| Fact                                                                                                                                                                                        | Source                                                                                                                        |
|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------|
| An `svg` node takes a document in `svg` (str or bytes), a colour for `currentColor` in `svg_color`, pixels for `<image>` in `svg_images`; it scales the document uniformly and centres it                  | [Paint reference](https://mindderivative.github.io/tre/reference/paint/), read 2026-11-01                                       |
| tre parses SVG with `usvg` 0.47 (default features off, feature `text`)                                                                                                                       | `crates/engine-core/Cargo.toml`, line 34, local tre source at git `0fd1e7e`, read 2026-11-01                                   |
| `resvg`, the renderer `usvg` belongs to, supports only static SVG: "No animations" and "There are no plans on implementing them either"                                                       | [resvg README](https://github.com/linebender/resvg), read 2026-11-01. It does not say whether `usvg` differs                    |
| An SVG `<mask>` is drawn (luminance and alpha masks)                                                                                                                                        | tre `tests/test_svg.py`; and the test below                                                                                    |
| tre draws a SMIL document as one static frame, at every time: the painted pixels and the images were identical at the start, after `advance(500)`, at `snapshot(time=2.0)` and after `advance(2500)` for seven icons | Test of 2026-11-01, offscreen with `Window.snapshot()` on the local tre source (0.5.9); details in [Block Reference > The Icon Set Files (2026-11-01)](../41%20TDL%20Reference/Block%20Reference.md#the-icon-set-files-2026-11-01) |
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

> [!CAUTION]
> **Proposal, not existing API**
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

## Prior Art in tre's Own Repository

`archive/crates/tre-svg/src/smil.rs` in the tre repository (the archived v0.1.0 engine, 408 lines, read 2026-11-01): its header says `usvg` does not process SMIL animation elements at all, confirmed there by reading `usvg`'s source, so it parsed the raw document in a separate `roxmltree` pass and drove the extracted keyframes through the engine's tween machinery. Its scope was `<animate>` (one scalar attribute, `values` or `from`/`to`), `<animateTransform type="translate">` and `dur`; its stated gaps were `begin`, `repeatCount`, `calcMode`, `rotate`, `scale` and `animateMotion`. The archived README also lists "keyframe morphing". The live engine has no SMIL code.

## tre's Scope and the Shell's Answers (2026-11-01)

tre's scope for issue #245, as the `tre` session reported it: `svg_time` (seconds, default 0, animatable with the existing `animate`) and a read-only `svg_duration` (`None` if any `repeatCount` is indefinite); no `svg_play` (the host loops with `animate`). Mechanism: a pre-pass over `usvg` (parse the source with `roxmltree`, evaluate SMIL at the time, write the values into a static copy of the XML, then the existing `SvgDocument` parse). Subset: `animate`, `set`, `animateTransform` (`rotate`, `translate`, `scale`), `dur`, `begin` as plain clock offsets, `to`, `values`, `keyTimes`, `repeatCount`, `fill` freeze or remove; a `d` morph only when both strings share one command sequence (else the first value is held); everything else ignored, with the first frame drawn as today. tre's cost target: 30 animated icons re-sampled every frame in under 4 ms, falling back to 30 Hz sampling.

The shell's answers (measured on the 1,218 line icons, 5,748 timing elements):

| tre's question                       | Shell's answer                                                                                                                                                                                                                                                              |
|--------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `fill` defaults to remove            | Acceptable. 5,300 elements write `freeze`; the other 448 have no `fill` and all repeat forever, so the default never shows.                                                                                                                                                  |
| Anything beyond the subset?          | No, but to-animation is the main form: 3,072 of 5,223 `animate` and `animateTransform` elements have `to` and no `from` and no `values`, starting from the attribute on the parent element. `from` is never used. `begin`: 4,214 elements, all plain seconds (no lists, no negatives, no `ms`); 1,534 have none. `dur` is always in seconds; all 525 `set` elements are `opacity` with `to`. `keyTimes`: 446, always with `values`. `d` morphs: 549 with `values` and 129 `to`-only, and in all of them the command sequence is the same, so the hold-first fallback never triggers. Not used: `by`, `calcMode`, `keySplines`, `additive`, `accumulate`, `repeatDur`, `end`, `restart`, `href`. |
| Is the cost target enough?           | More than enough: a handful of looping icons at a time (172 of the 1,218 loop forever) and short intros of 0.1 to 0.6 s on a state change. An expectation only; no shell UI exists yet.                                                                                      |

tre's reply (2026-11-01): it recorded the answers on #245. (The build and its measured idle cost are under "Built in tre" below.) To-animation, with the start value read from the parent element's attribute, is now explicit stage-1 scope; the `fill` default of remove, `begin` as plain seconds and 30 Hz sampling for loops are kept. It has not verified what tre does while only an `svg_time` animation runs (frame rate, wake-ups) or whether hidden, occluded or minimised windows pause, and its documentation does not say; it added an acceptance item to #245 (measure idle CPU with one looping icon and document the result) and will not guess a number. #245 stays in Ready, not started.

A caution the shell sent with the answers: a looping icon keeps its window redrawing, and the shell has an idle-CPU budget (AGENTS > 12. Design Completeness Checklist, Quality). The shell asked what tre does while only an `svg_time` animation runs (frame rate and wake-ups) and whether it pauses for a hidden or occluded window. 30 Hz sampling for loops suits the shell.

## Built in tre (Reported 2026-11-02)

The `tre` session reported that #245 is built and In review on the local branch `svg-smil-245`, not pushed or merged, so in no release. Checked on 2026-11-02 in tre's repository: one commit, `f788434` ("SMIL animation in svg nodes: svg_time and svg_duration, sampled from the document's own timeline (#245)"), the API described in `python/tre/_core.pyi` under version 0.5.10, `main` unchanged at `0fd1e7e`.

| What                                       | As built, per tre                                                                                                                                                               |
|--------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `svg_time`                                 | Seconds into the document's SMIL animation, animatable with `animate`; `set(svg=...)` restarts it at 0                                                                           |
| `svg_duration`                             | Read-only; `None` for an indefinite repeat, `0.0` for a document without animation                                                                                              |
| Subset                                     | As scoped, including to-only animation from the parent attribute, `values` and `keyTimes`, and `d` morphs; unsupported SMIL is ignored                                           |
| Sampling cost                              | 30 looping icons re-sampled per frame took 0.22 ms                                                                                                                              |
| Idle                                       | An idle window uses 0.0% CPU                                                                                                                                                    |
| While `svg_time` animates                  | The window redraws every frame at the display rate, with no 30 Hz cap, and tre has no occlusion handling, so a hidden window keeps redrawing                                    |
| One looping icon on `llvmpipe` (software)  | About 30% of one core. A GPU was not measured                                                                                                                                   |
| Follow-up                                  | A lower sample rate would be a follow-up issue in tre, if the shell's idle budget needs it                                                                                       |

Occlusion (tre issue #246, reported 2026-11-02, information only from the `tre` session): on sway a window hidden on another workspace stalled the whole application loop, because its swapchain acquire blocked; a second visible window stopped animating and Python threads starved. The fix is built and In review on the local branch `occlusion-246`, not pushed or released. On Wayland a hidden window (other workspace, minimized, or a `LayerWindow` under a fullscreen window) stops drawing and costs about 0% CPU. It adds a window state and event `occluded` (X11 and macOS signal only, unverified) and a window property `pause_when_occluded` (default true). It was verified only on headless sway with `llvmpipe`; KWin, a real GPU, macOS and Windows were not run. #needs-verification The shell runs many surfaces in one process ([ADR-0003 Process Model](../30%20Decisions/ADR-0003%20Process%20Model.md)), so this stall would have frozen every other surface; check it on KWin, with layer surfaces, before relying on it.

Overnight results from the `tre` session (2026-11-02, information only; the shell has not re-measured). #245, still In review on the local branch `svg-smil-245`, not pushed or released: on KWin 6.8 with an AMD RADV GPU, one looping icon used 4.0% of a core against 3.2% for a plain rotation animation, 30 icons 6.8% against 5.2%, and an idle window 0.0%. It now also reads `from=`, a negative `begin` and files with a DOCTYPE. Not played: `style=` or CSS overriding an animated attribute, and `href` targets. #246: on KWin the hidden-window freeze does not reproduce (KWin keeps frame callbacks for minimized windows and for a bar under a fullscreen window); a window on another virtual desktop falls to about 0.5% CPU with the fix against 3.1% before; on sway the freeze stopped the whole app and the fix cures it. Read the state with `Window.get('occluded')`; the property is `pause_when_occluded`. Known gap, filed by tre as #247: while every Wayland window is hidden, timers and `call_soon` wait. The shell's timers and the D-Bus hand-off (`call_soon`) would stall in that state, which needs a design answer. #needs-verification

tre 0.5.10 (reported 2026-11-02, information only) carries `svg_time` and `occluded`. It was tagged and built, pulled back by tre so that TRE-REQ-009 could go in first, then published to PyPI as `tesserae-engine` 0.5.10 on 2026-11-02 with `Window.build`, `Window.apply` and `Node.set_children`. #247 and #248 stay open in tre.

Consequences for the shell: v1 ships only static `mdi` icons, so nothing in v1 loops. Before `mli` ships, a looping icon must not run in a hidden or collapsed surface (the shell knows when a Bar is hidden), and the shell needs a rule on how many loops may run at once; the follow-up in tre (a sample-rate cap, pause when occluded) is the shell's to ask for if it wants them. [Risk Register](../00%20Home/Risk%20Register.md) R-24.

## Alternatives

| Alternative                                                                                                 | Verdict                                                                                                                                      |
|-------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------|
| The shell sets a new `svg` string every frame from Python                                                    | Rejected: per-frame Python.                                                                                                                  |
| The shell renders frames to bitmaps and swaps them                                                           | Rejected: Python per frame and memory for every frame.                                                                                        |
| An offline converter turns each icon into a tree of tre `path` nodes animated with tre's own animation       | Possible, but each icon becomes a node tree, the converter has to carry SMIL's rules, and `d` morphs have no tre counterpart.                  |
| A static end-state export of the line set (the shell's option B)                                             | No engine change, correct drawing, no motion. A fallback, not a substitute.                                                                    |

## If Declined

The shell ships only the static `mdi` set (decided 2026-11-01). It may later add a static export of the line set, with each icon in its end state and the animation tags removed, which tre draws correctly. Icons do not move; a spinner is not available as an icon, and a shell that wants one draws it with tre's `path` node and `trim_end`, or with a module's Canvas ([Block Reference > Other](../41%20TDL%20Reference/Block%20Reference.md#other)).

## Size

Not measured. By reading the data: the elements and attributes in the table above are a small, regular subset, and the harder parts are the `d` morph and the timing model (`begin` offsets, `keyTimes`, `freeze`, indefinite repeats). The request does not ask for the whole of SMIL.

## Open Questions

- [x] Whether tre prefers a pre-pass over `usvg`, a different SVG library or its own SMIL evaluator: a pre-pass over `usvg` (tre, issue #245).
- [ ] Whether `usvg` already drops SMIL elements or fails on them (it drew the test icons without error).
- [ ] The cost of re-parsing a small document per sample: tre's target is 30 icons per frame in under 4 ms, to be measured in issue #245. What tre does while only an `svg_time` animation runs (wake-ups, hidden or occluded windows) was unverified on 2026-11-01; tre measured it on 2026-11-02 (see "Built in tre").
- [x] Whether `svg_time` is animatable: yes, with the existing `animate` (tre, issue #245).

## Links

[Block Reference](../41%20TDL%20Reference/Block%20Reference.md) · [Building Blocks](../50%20Design%20System/Building%20Blocks.md) · [80 Requests](80%20Requests.md) · [Risk Register](../00%20Home/Risk%20Register.md)
