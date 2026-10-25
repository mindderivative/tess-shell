---
title: TRE-REQ-001 Layer Surface Window
aliases: [TRE-REQ-001, LayerWindow Request, Layer Surface Request]
type: engine-request
status: review
owner: phil
created: 2026-10-18
updated: 2026-10-25
tags: [engine-request, spec/surface, integration/wayland, needs-verification]
related: ["[[ADR-0001 Shell Surface Strategy]]", "[[Prior Art - Linux Shell Surfaces]]", "[[80 Engine Requests]]"]
depends_on: []
---

# TRE-REQ-001: Layer surface window

> [!summary]
> Add a `LayerWindow` type to tre. It is a `Window` whose Wayland role is `zwlr_layer_shell_v1` instead of xdg-toplevel, so it can anchor to screen edges, reserve space, sit on a stacking layer, take a chosen keyboard mode and bind to one output. A companion `PopupWindow` type opens menus and flyouts parented to a layer surface. A small output API lets the shell place one surface per monitor. An `input_region`, margin animation and margin drag cover non-rectangular shells, slide and fade motion, and movable widgets.

> [!success] Built in tre, unreleased (2026-10-25)
> [tre #195](https://github.com/mindderivative/tre/issues/195) is closed: all six phases and three follow-ups are merged to tre `main`, unreleased after 0.5.7. See [Delivered](#delivered-tre-195-closed). The request stays at `review` until the maintainer confirms it against the shell.

> [!danger] Blocks the shell until a tre release exists
> No bar, panel, dock, OSD or wallpaper can ship without this. Every note under `40 Specifications/Surfaces/` carries `> [!warning] Blocked by [[TRE-REQ-001 Layer Surface Window]]` until tre releases it. Decision record: [[ADR-0001 Shell Surface Strategy]] (Option A, `proposed`).

This note is carried to the tre project by the maintainer ([[AGENTS#6. Engine requests (tre / Tesserae)]]).

## Delivered (tre #195 closed)

Source: [tre #195](https://github.com/mindderivative/tre/issues/195) closing comment and `docs/design/layer-window-shell-handoff.md` in tre (PR #218), read 2026-10-25 with `gh`. Everything below is on tre `main` and unreleased; the next version number is not chosen.

| Part | tre issue | PR |
|---|---|---|
| Spike | [#196](https://github.com/mindderivative/tre/issues/196) | #197 |
| `LayerWindow` core | [#198](https://github.com/mindderivative/tre/issues/198) | #208 |
| Outputs | [#202](https://github.com/mindderivative/tre/issues/202) | #209 |
| Live checks (KWin, sway), deterministic `output=None` | [#203](https://github.com/mindderivative/tre/issues/203) | #210 |
| `input_region`, hit testing follows `corner_radius` | [#204](https://github.com/mindderivative/tre/issues/204) | #211 |
| Margin animation, `drag_margin` | [#205](https://github.com/mindderivative/tre/issues/205) | #212 |
| Menus from a bar (overlay route) | [#206](https://github.com/mindderivative/tre/issues/206) | #213 |
| KWin versions of the region, drag and menu tests | | #214 |
| `exclusive_edge` (tre binds layer-shell v5 itself) | [#201](https://github.com/mindderivative/tre/issues/201) | #215 |
| IME through `zwp_text_input_v3` | [#199](https://github.com/mindderivative/tre/issues/199) | #216 |
| AccessKit through `accesskit_unix` | [#200](https://github.com/mindderivative/tre/issues/200) | #217 |
| Hand-off note, live hot-plug test | | #218 |

**Differences from this request**

- No `PopupWindow` yet. Menus use the overlay route (stage 6b, `PopupWindow`, was approved on 2026-10-25 as [tre #223](https://github.com/mindderivative/tre/issues/223), In review, milestone Held, because a 4K overlay costs 177 MiB against about 18 MiB for a menu-sized surface): a transparent full-screen `overlay` `LayerWindow` with `input_region="auto"` and `keyboard="exclusive"`, created when a menu opens and closed on dismiss. An outside click is consumed and dismisses; Escape dismisses; menus flip at the output edge; submenus and tooltips work. The engine does not know other panels' reserved areas.
- `layer=` keeps its name (maintainer decision on #195). The shell uses `shell_layer=` on its own side if it needs a distinct name.
- `output=None` is the output at (0, 0), else first by name. The shell still passes an explicit `Output` per monitor.
- v1 targets KWin and wlroots-family compositors (maintainer decision on #195). Tested on KWin 6.8.1 and sway 1.12.
- Unsupported platforms raise `UnsupportedPlatform`. `animate` covers the four margins only.
- `set(exclusive_edge=None)` raises on a surface that has an edge: the protocol cannot clear one.
- Hit testing follows `corner_radius` for every window; masks and `clip_children` are still ignored.

> [!success] KWin supports corner reservation (maintainer report, 2026-10-25)
> tre reran the corner tests and showed that KWin reserves space for a corner surface with `exclusive_edge`. The earlier "no reservation" result ([tre #201](https://github.com/mindderivative/tre/issues/201)) was therefore not a KWin limit, and the earlier hypothesis that it was a KWin gap is withdrawn. This agrees with KWin's source ([layershell_v1.cpp](https://invent.kde.org/plasma/kwin/-/raw/master/src/wayland/layershell_v1.cpp) stores and uses an explicit edge). #needs-verification: tre has not posted the rerun to #201 or the hand-off note as of 2026-10-25, so the cause of the first result (tre's request, the test, or the KWin version) and the fix are not recorded here. Update this callout when tre posts it.

> [!warning] VRAM per window: cause found, fixes in tre Backlog
> [tre #207](https://github.com/mindderivative/tre/issues/207) research (2026-10-25): tre itself allocates under 1 MiB for a small window; `wgpu` reserves about 192 MiB per window device (default `MemoryHints::Performance`, blocks of 128 MiB or more), and tre makes one device per window. With `MemoryHints::MemoryUsage` a small window is 31 MiB (211 before), a bar 18 MiB, two windows 44 MiB (404), a 4K overlay 177 MiB (325), with no measured frame-time change. The remainder at 4K is the swapchain images plus tre's persistent target, about 19 bytes a pixel. One AMD RADV GPU only. Fixes filed in Backlog: [#219](https://github.com/mindderivative/tre/issues/219) small memory blocks, [#220](https://github.com/mindderivative/tre/issues/220) one device for all windows, [#221](https://github.com/mindderivative/tre/issues/221) per-pixel cost of full-screen surfaces, [#222](https://github.com/mindderivative/tre/issues/222) allocator totals in `frame_stats`. Until they land, plan the surface count against the old numbers. Record in [[Risk Register]] when it exists.

**Not tested anywhere:** touch; non-AMD GPUs; labwc and other wlroots compositors besides sway; GNOME (no layer shell); a real v4-only layer-shell compositor; a real input method (fcitx5, ibus); Orca; crispness at 1.5x; `reduced_motion` on a `LayerWindow`; frame callbacks under a fullscreen window; the four reservers plus painter together.

## Upstream status (as of 2026-10-23, superseded by Delivered)

Read from the tre issue tracker on 2026-10-19 with `gh`. The spike findings note is in [tre PR #197](https://github.com/mindderivative/tre/pull/197) (`docs/design/layer-surface-spike.md`, open); it was read in full and the figures below come from it.

| Item | State |
|---|---|
| Request | [tre #195](https://github.com/mindderivative/tre/issues/195), open, backlog. It records absences checked against the tre source (no layer-shell, `xdg_popup`, `smithay` or `wayland-client` in `crates/`; backend `winit` 0.30.13). |
| Spike (phase 1) | [tre #196](https://github.com/mindderivative/tre/issues/196), done, held at review. Verdict: go on I2, a layer surface on a second event queue of the `wl_display` that `winit` owns. |
| Phases | 1 spike ([#196](https://github.com/mindderivative/tre/issues/196)), 2 `LayerWindow` core and mock backend ([#198](https://github.com/mindderivative/tre/issues/198)), 3 outputs API ([#202](https://github.com/mindderivative/tre/issues/202)), 4 `input_region` ([#204](https://github.com/mindderivative/tre/issues/204)), 5 margin animation and `drag_margin` ([#205](https://github.com/mindderivative/tre/issues/205)), 6 popups ([#206](https://github.com/mindderivative/tre/issues/206)) |
| Phases 2 to 5 | Done (read from tre on 2026-10-23). Phases 4 and 5 are on local branches `input-region-204` and `margin-animation-205`, not pushed. See [Phase 5 as built](#phase-5-as-built-tre-205). |
| Phase 6 | Scoped, Backlog, awaiting the maintainer's approval and decisions. See [Phase 6 scope](#phase-6-scope). |
| Effort and risk (tre's estimate) | XL overall, spike M. Risk high: two input sources in one loop. |

Spike results that bear on this request:

- tre's own wgpu pipeline drew a real scene (container, rounded rect, text) on a layer surface. The renderer is already window-agnostic; only `GpuState::new` and `recreate_surface` assume a `winit` window.
- A `winit` window and a layer surface on one `wl_display` showed no deadlock and no lost events. Both seats deliver every surface's events, so each side must filter by surface.
- Pointer, scroll and keyboard reached `Tree::dispatch`. Keyboard modes none, on_demand and exclusive behaved per protocol.
- On KWin: the exclusive zone shortened a maximised window by 32 px; negative margins are accepted and honoured; a 1 px reserver with an empty input region keeps its zone; a full-output `-1` painter disturbed nothing; `wl_output` v4 gives output names. The compositor's own output choice varies, so bind outputs explicitly.
- Idle: 1 frame in 10 s and 0.0% CPU. Clock-driven animation (`tick_all(now)`) needs no frame callbacks, but the loop's wake-up must not depend on them.
- Fractional-scale and viewporter objects work on a layer surface (1x only).

### Phase 4 as built ([tre #204](https://github.com/mindderivative/tre/issues/204))

Source: the issue and its comments, read 2026-10-20 with `gh`.

- `input_region` takes `None`, `[]`, rectangles (tuples or lists, rounded outward, at most 256) or `"auto"`. The layer thread sets a `wl_region` and commits at once, so an idle surface needs no frame.
- `click_through` is an alias of `[]` on a `LayerWindow`. Giving both with different meanings raises. Ordinary windows are unchanged.
- `"auto"` is the union of drawn, hit-testable nodes (boxes, images, paths, svg, canvas, fields, selectable or linked text), recomputed after each layout. While anything animates it only grows, then snaps exact. Bands are at least 2 px; past 256 rectangles it coarsens, never below the drawn shape.
- **Behaviour change for every window:** hit testing now follows `corner_radius` and `corner_radii`. Masks and `clip_children` are still ignored. tre #204 answers the open question on box hit-testing: it followed neither before, and it follows rounded corners now.
- **Deviation from this note:** `"auto"` is its own commit right after layout, not the buffer's commit, so it can run up to one frame ahead of or behind the buffer. See [Input region](#input-region).
- Live checks on headless sway 1.12 with a virtual pointer: `None`, `[]`, an explicit rectangle, `"auto"` with a circle and the four-bar screen frame all route clicks as specified. Not run: touch, KWin (needs `/dev/uinput`, which moves the real pointer), labwc.

### Phase 5 as built ([tre #205](https://github.com/mindderivative/tre/issues/205))

Source: the issue and its comments, read 2026-10-23 with `gh`. State: Done, approved by the maintainer. Built on local branch `margin-animation-205` (off `input-region-204`), not pushed; `tools/verify.sh --cross` passes. The five decisions were taken as recommended: relative pointer with a fallback, `moved` on release only, `set(margin=...)` cancels and snaps, four names only, live drag tests on sway only.

- **5a, margin animation.** `LayerWindow.animate("margin_top"|"margin_right"|"margin_bottom"|"margin_left", to, duration_ms, easing, on_complete)`. Four `Animated<f64>` margins tick in the window's frame pass. A changed rounded margin goes to the layer thread as a margin-only command: one commit, no other property re-sent. Linear, bezier and spring easing; retarget starts from the current value; `animation_end` (`property`, `finished`) fires on the root; `set(margin=...)` cancels and snaps with no `on_complete`; `advance(ms)` runs it headless; a bad property or value raises.
- **One clock per loop turn.** Frame passes tick to `engine_platform::turn_instant`, the instant the loop turn began, so windows animating together read one time. This meets requirement 1 under [Animation](#requirements).
- **Wake-up.** The loop's alarm fires every 8 ms while a margin moves, with no spinning and no buffer drawn. Progress does not wait for frame callbacks.
- **5b, `window_region="drag_margin"`.** A primary press on such a node of a `LayerWindow` (same exclusions as `"drag"`) makes the layer thread follow the pointer using `zwp_relative_pointer_v1` deltas. Anchored edges' margins change, clamped to the output, one commit per input frame, no Python. On release `moved` fires once with `event.margin`. A running margin animation stops where it is. An axis anchored to both edges or to none does not move. `drag_margin` raises on an ordinary window; `"drag"` still raises on a layer window.
- **Live results (headless sway, `grim` readback and a virtual pointer).** A 0 to 300 px slide in 800 ms is smooth (about 6 px per 16 ms), monotonic, and `on_complete` lands on time. A drag follows the pointer within 2 px and stops at both output edges (660, 1080 for a 200x60 widget on 1280x720; 0 at the near edge).
- **Limits.** Wayland cannot commit two surfaces atomically, so surfaces animating together can differ by up to a frame on screen (documented in tre). Other surfaces' exclusive zones do not limit a drag.
- **Not run:** the surface-local fallback for a compositor without the relative-pointer protocol (it can overshoot a little by design); KWin; `reduced_motion` on a `LayerWindow`; frame callbacks to a surface covered by a fullscreen window; KWin map and unmap effects.

### Phase 6 scope

[tre #206](https://github.com/mindderivative/tre/issues/206).

Backlog, not approved. tre follows this note's advice and splits it:

- **6a, prototype the overlay route first, no new API.** A transparent `overlay` `LayerWindow` on all four edges, `input_region="auto"`, menus through `show_layer`. `"auto"` already walks `show_layer` overlays, so opening a menu extends the region. Checks: idle draw count and memory per output, dismissal on outside click and Escape, `keyboard` switched to `on_demand` while open, edge flipping, submenus, tooltips. The result is a recorded verdict plus a gap list. One known gap: a click outside a menu falls through to the window below, so the shell must also dismiss on it.
- **6b, `PopupWindow`, only if 6a falls short.** Large, risk medium to high: `xdg_wm_base` on the layer queue, `xdg_positioner`, `get_popup`, grab with the seat serial, a popup's fixed size at creation (growing content needs a reposition), nesting. `winit` has no popup support, so it would live on the layer thread.
- Open decisions in tre: start with 6a (recommended), `Window` subclass with keyboard focus inherited from the layer (recommended), and the 6a pass bar for idle cost (for example no idle frames, a few tens of MB per 4K output).

Not shown by the spike: frame callbacks under a fullscreen window, output removal, 1.5x scale, touch, key repeat, cursor shape, IME, AccessKit, and on-screen confirmation (evidence is a protocol trace, a first-frame readback, the shortened maximised window and pointer events).

### Coverage check against tre's plan

Compared on 2026-10-19: this request and its acceptance criteria against the phase plan in [tre PR #197](https://github.com/mindderivative/tre/pull/197). The plan covers the core of the request. These needs are not assigned to a phase or were not tested:

| Need | Why the shell needs it | State in tre's plan |
|---|---|---|
| Transparent rendering on a layer surface | Frame, rounded bars and OSDs need a transparent background | The surface reports alpha mode `PreMultiplied`, but a transparent scene was not drawn or checked. Add to phase 2. |
| Accessibility | Screen-reader access to the bar | Needs `accesskit_unix` directly (tre uses `accesskit_winit` today). Untested and in no phase. |
| Clipboard paste into a layer surface | Launcher search boxes | tre's clipboard goes through XWayland for every window. The spike did not test a paste, and a layer surface is not an X11 window. #needs-verification |
| Text input and IME | Launcher input in non-Latin scripts | `zwp_text_input_v3` is advertised; untested. Plain keys gave UTF-8 text. |
| Key repeat and cursor shape | Held keys in text fields, resize and pointer cursors | In phase 2, but tre needs its own repeat timer because `sctk` offers repeat only through `calloop`. |
| Touch | Touch screens | The test seat had no touch capability; nothing tested. |
| Output removal and hot-plug | Per-monitor bars | `closed` on removal was not tested. This is an acceptance criterion. |
| Fractional scale at 1.5x | Crisp bars on scaled displays | Objects bind; the 1.5x output was not available. |
| Other GPUs | Not only AMD RADV | The spike ran on one AMD GPU. Alpha and format support on other drivers is unchecked. #needs-verification |
| Layer state across threads | The second queue runs on a helper thread while the loop thread draws | The spike put it all on one thread. The note says a design must decide who owns what; this needs a short design before phase 2. |
| `PopupWindow` and the full-screen overlay alternative | Menus and flyouts | Phase 6, untouched. The spike expects the overlay route to be easier with a working layer surface. |

One request change came out of the spike: the compositor's own output choice alternated between runs, so `output=None` now means that tre picks an output deterministically. The shell passes an explicit output for every per-monitor surface.

## Shell need

| Need | Mechanism ([protocol](https://wayland.app/protocols/wlr-layer-shell-unstable-v1)) |
|---|---|
| Stacking layer | `set_layer`: background 0, bottom 1, top 2, overlay 3 |
| Edge placement | `set_anchor` bitfield: top 1, bottom 2, left 4, right 8 |
| Stretch along an edge | `set_size` with 0 on an axis, valid only when anchored to both opposite edges on that axis |
| Reserved space | `set_exclusive_zone`: positive pixels, 0, or -1. A positive value counts only for one edge, or one edge plus both perpendicular edges. |
| Corner exclusive zone | `set_exclusive_edge` (since v5) |
| Offsets | `set_margin` (top, right, bottom, left) |
| Keyboard focus | `set_keyboard_interactivity`: `none`, `exclusive`, `on_demand` (since v4) |
| Per-output placement | `get_layer_surface` takes a `wl_output`, or NULL to let the compositor choose |
| Popups | `get_popup` parents an `xdg_popup` to the layer surface |
| Compositor dismissal | `closed` event, for example when the output is removed |

## Why this belongs in the engine

Surface roles are windowing mechanism: they decide how the compositor places and stacks a window, not what the window contains. [[AGENTS#3. Layering principle]] puts mechanism in tre. If the shell created the surface (ADR-0001 Option B), it would own configure, scale, output hot-plug and input routing, which tre already owns for ordinary windows. Python sets properties and never touches a frame; `LayerWindow` keeps that split.

## What tre has today

Source: [Python API](https://mindderivative.github.io/tre/api/python/), [Custom windowing](https://mindderivative.github.io/tre/design/custom-windowing/), [Architecture](https://mindderivative.github.io/tre/architecture/), read 2026-10-18.

| Area | Present | Absent from the docs |
|---|---|---|
| Window | `Window(width, height, title, decorations)`; several windows via `App.add_window` then `App.run()` | Role selection, parent or transient windows |
| Platform | `window.get("platform")` returns `"wayland"`, `"x11"`, `"windows"` or `"macos"`; `scale_factor`; `center()` | Output enumeration, targeting an output |
| Overlays | `show_layer` / `hide_layer` draw nodes inside the window's own content | A separate OS surface for popups |
| Transparency and input | `transparent`, `blur_behind`, `click_through` | Input regions per area |
| Undocumented keys | `window.set(...)` accepts `x`, `y`, `always_on_top`, `skip_taskbar` but the property tables do not describe them | Whether they work on Wayland |
| Backend | `engine-platform` owns the `winit` loop, input translation and the AccessKit adapter | Surface creation details; `wgpu` and raw-window-handle use |
| Shapes | `corner_radius` (number or 4-tuple), path nodes (`data`, `view_box`, fill, stroke), canvas `Painter` (`fill_circle`, `stroke_path`), `clip_children` to the rounded box, `shader`, `shadows`. Canvas hit-testing can follow a circle or path (`set_hit_test_circle`, `set_hit_test_path`). | Concave corners, blend modes (#needs-verification). Whether box hit-testing respects rounded corners. Non-rectangular windows. Masks shipped in tre 0.5.6 ([tre #164](https://github.com/mindderivative/tre/issues/164)); the API page read for this note predates them. |
| Animation | `node.animate(property, to, duration_ms, easing, on_complete)`; easing `"linear"`, cubic bezier or spring; paint properties and, since 0.5.6, layout properties; `animation_end` event; `window.advance(ms)` for tests | Animating window-level properties. What drives the frame clock. Behaviour when frames stop. |
| Drag | `window_region="drag"` calls winit `drag_window()`; `resize_border` calls `drag_resize_window()` | Anything for surfaces the compositor places |

#needs-verification: confirm the absences in the tre source and `ARCHITECTURE.md`. The Window reference and Layers guide were not read in full.

> [!warning] Name collision
> tre already uses "layer" for in-window overlays (`show_layer`). The new type uses the protocol's term for a different thing. Keep `layer=` on `LayerWindow` to match the protocol and Fabric, and define both senses in the Glossary. See [Open items](#open-items).

## Proposed API

Illustrative only. None of this exists in tre.

```python
bar = LayerWindow(
    namespace="tesserae-shell.bar",   # protocol namespace, identifies the surface's purpose
    layer="top",                      # "background" | "bottom" | "top" | "overlay"
    anchor=("top", "left", "right"),
    size=(0, 32),                     # 0 stretches between opposite anchors
    exclusive_zone=32,                # int; 0; -1
    exclusive_edge=None,              # edge name; needed for corner anchors (compositor protocol v5)
    margin=(0, 0, 0, 0),              # top, right, bottom, left
    keyboard="none",                  # "none" | "on_demand" | "exclusive"
    input_region=None,                # None | "auto" | [] | [(x, y, w, h), ...]
    output=None,                      # Output | None (tre picks one deterministically)
)
app.add_window(bar)
```

### Type and inheritance

`LayerWindow` subclasses `Window`. `root`, `create`, `show_layer`, `after`, `every`, `on`, `simulate`, `advance` and `snapshot` behave as they do today, so the existing headless testing story applies unchanged.

Constructor-only: `namespace`, `output`. Live through `set()` (one atomic commit, like today's `set()` semantics): `layer`, `anchor`, `size`, `exclusive_zone`, `exclusive_edge`, `margin`, `keyboard`, `input_region`. Margins also animate: see [Animation](#animation).

Window keys with no meaning for a layer surface (`decorations`, `maximized`, `minimized`, `fullscreen`, `resize_border`, `system_menu`, `title`-as-title-bar) raise on `set()` rather than being ignored. A node with `window_region="drag"` on a `LayerWindow` raises when attached: `drag_window()` and `drag_resize_window()` move and resize an xdg-toplevel, and the compositor places a layer surface. Use `"drag_margin"` instead ([Margin drag](#margin-drag)).

`close()` works as on `Window`: it fires `close_requested` (cancellable), then destroys the surface and fires `closed` with reason `"app"`.

### Validation

The constructor and `set()` reject the protocol errors before any request goes to the compositor, so the shell sees a Python error with the offending key:

- `invalid_size`: a 0 dimension without anchors on both opposite edges.
- `invalid_anchor`: a bitfield outside the four edges.
- `invalid_exclusive_edge`: the edge is not among the anchors.
- `invalid_keyboard_interactivity`, `invalid_layer`: unknown name.
- A positive `exclusive_zone` with an anchor set the protocol treats as 0 produces a warning event, not an error, because the protocol accepts it.

### Lifecycle and events

| Event | Payload | Fires when |
|---|---|---|
| `configure` | `width`, `height` | The compositor assigns a size. tre acks and resizes the render target. Existing `resize` also fires. |
| `closed` | `reason`: `"compositor"` \| `"output_removed"` \| `"app"` | The compositor sends `closed`, or the app closes the window. |
| `output_changed` | `output` | The surface enters a different output or its scale changes. |

After `closed` with reason `"compositor"` or `"output_removed"` the window is dead (protocol: further changes are ignored). The shell creates a new `LayerWindow` for a new output.

A window must not attach a buffer before the first configure is acked ([protocol](https://wayland.app/protocols/wlr-layer-shell-unstable-v1)). tre owns that sequencing; `App.run()` opens a `LayerWindow` without any shell involvement.

### Outputs

```python
for out in app.outputs():          # list[Output]
    ...
app.on("output_added", fn)         # fn(output)
app.on("output_removed", fn)       # fn(output)
```

`Output` is a read-only value with: `name` (stable connector name such as `DP-1`), `description`, `x`, `y`, `width`, `height` in logical pixels, `scale_factor`, `transform`. The shell keys per-output surfaces on `name`.

#needs-verification: `wl_output` alone does not provide a stable name before version 4. Check whether `xdg-output-unstable-v1` or `wl_output` v4 is required, and what KWin 6.7 advertises.

### Capability query

```python
tre.supports("layer_shell")        # False on GNOME/Mutter, X11, Windows, macOS
```

`LayerWindow(...)` raises `UnsupportedPlatform` when the query is false. The request recommends raising, not silently degrading to a plain window as Quickshell's `PanelWindow` does on X11: a bar that quietly lacks an exclusive zone is a worse failure than a clear error. The shell runtime can build its own degraded fallback from `Window` (see [If declined or infeasible](#if-declined-or-infeasible)). The platform-neutral wrapper question from ADR-0001 is therefore settled here as a recommendation, for the maintainer to confirm.

### Popups

`show_layer` cannot serve tray menus or flyouts on a 32 px bar, because it draws inside the window's own bounds. Popups need their own surface.

```python
menu = PopupWindow(
    parent=bar,
    anchor_rect=(x, y, w, h),         # in the parent's coordinates
    anchor="bottom_left",             # point on the rect
    gravity="bottom_right",           # direction the popup extends
    constraint_adjustment=("flip_y", "slide_x"),
    grab=True,                        # dismiss on outside click / Escape
)
```

- Role: `xdg_popup`, parented through `zwlr_layer_surface_v1.get_popup`. The popup is created with a NULL xdg parent and attached before its initial commit (protocol requirement).
- Keyboard mode is inherited from the layer surface by the protocol. A bar with `keyboard="none"` cannot give a popup keyboard focus. The shell sets the bar to `on_demand` while a menu is open, or the request adds a popup-level override. #needs-verification: whether `xdg_popup.grab` gives keyboard focus independently of the parent's interactivity on KWin.
- `closed` fires with reason `"dismissed"` on outside click, Escape or parent destruction.
- Positioning uses `xdg_positioner`, so the compositor flips and slides the popup to stay on screen. The shell does not compute screen edges.
- Nested popups (submenus) take another `PopupWindow` as `parent`.

This part is separable. If the layer surface lands first, ship popups as a second milestone; the bar and OSD do not need them.

**Alternative: a full-screen overlay surface.** tre's own `show_layer` overlays draw above the whole window and may hang off its edges, so a transparent `LayerWindow` on the `overlay` layer, anchored to all four edges with `input_region="auto"`, could host menus with no `PopupWindow`. For: no `xdg_popup` work, and the existing `show_layer` placement, flipping, dismissal and focus scoping apply unchanged. Against: one full-screen surface per output, input-region upkeep as menus open, close and animate, and keyboard interactivity must switch to `on_demand` while a menu is open. Compare in the prototype before committing to `PopupWindow`.

### Input region

`input_region` controls where the compositor delivers pointer and touch input to the surface. Clicks elsewhere reach the window below. The compositor cannot route a click through a transparent pixel after the surface has received it, so the region must be set explicitly.

| Value | Meaning |
|---|---|
| `None` | The whole surface (protocol default) |
| `"auto"` | The union of the shapes of drawn, `hit_testable` nodes. Rounded boxes, circles and canvas hit-test paths contribute their real shape. |
| `[]` | Nothing. Equivalent to the existing `click_through`. |
| `[(x, y, w, h), ...]` | Explicit rectangles in surface-local logical pixels |

- Wayland regions are rectangle lists. tre decomposes a non-rectangular shape into scanline rectangles and caps the count. #needs-verification: cost, and compositor limits on region size.
- `"auto"` updates right after layout in its own commit, so an idle surface still updates. It can lead or trail the buffer by up to one frame ([tre #204](https://github.com/mindderivative/tre/issues/204)). This replaces the earlier same-commit requirement.
- tre caps regions at 256 rectangles in bands of at least 2 px, rounded outward, so the region is never smaller than the drawn shape.
- While a node animation runs, `"auto"` uses the union of the start and end shapes, then snaps to the exact region at `animation_end`. Input never lands outside a visible control; a click just inside the old edge of a shrinking shape may still hit.
- `click_through` stays as an alias for `input_region=[]`.

### Margin drag

Movable desktop widgets anchor to a corner and move by changing `margin`. Python must not sit in the pointer-move loop, so the engine does it:

- A node with `window_region="drag_margin"` starts a drag on primary press, unless the press lands on a focusable node, a node with a `click` listener, or a node holding pointer capture (the same exclusions as `"drag"`).
- tre updates the margins of the anchored edges by the pointer delta from the press point, clamped to the output, with one double-buffered commit per input frame. An axis anchored to both opposite edges does not move.
- The surface moves under the pointer, so a surface-local delta shifts as the compositor applies each commit, and adding it per event overshoots. tre uses `zwp_relative_pointer_v1` deltas, which do not depend on the surface (exact on sway), and falls back to a surface-local estimate where the protocol is missing ([Phase 5 as built](#phase-5-as-built-tre-205)).
- On release tre fires `moved` with the final `margin`. The shell persists it.
- Expect one frame of lag between pointer and surface. #needs-verification on KWin, including that KWin exposes the relative-pointer protocol.

## Animation

Source: [tre animation guide](https://mindderivative.github.io/tre/guide/animation/), read 2026-10-18.

Node animation runs inside a `LayerWindow` through the same pipeline as in `Window`, so `node.animate(...)`, springs, `on_complete` and `animation_end` work unchanged. The shell differs from an app in one way: some of what it wants to animate (where the bar sits, how big a notification is) is held by the compositor, not by a node.

| Target | Mechanism | Cost |
|---|---|---|
| Paint inside the surface: `fill`, `opacity`, `translate_x/y`, `scale`, `rotation_deg`, `corner_radius`, `shadows`, path `data`, `trim_start/end` | `node.animate` (exists) | Paint only. No layout, no protocol traffic. |
| Layout inside the surface: `width`, `height`, `padding`, `gap`, `x`, `y` | `node.animate` (exists, since 0.5.6) | Relayout up the tree each frame. No protocol traffic. |
| Surface position: `margin_top`, `margin_right`, `margin_bottom`, `margin_left` | **New:** `layer_window.animate(property, to, duration_ms, easing, on_complete)`, same signature and easing as `Node.animate` | One double-buffered commit per frame. No buffer reallocation. The compositor moves the surface. |
| Surface size | Not animated. Step change. | Each change is a configure round trip and a new buffer. |
| `exclusive_zone` | Not animated. Step change. | Each change reflows maximised windows. |
| Appearing and disappearing | Animate root `opacity` or `translate_*`; close on `animation_end` | Uses existing API. |

`LayerWindow.animate` is limited to margins on purpose. They are the one surface property where per-frame change is cheap and visibly useful (slide-in panels, auto-hide, movable widgets). The animation runs in Rust; Python starts it and receives the completion callback. #needs-verification: whether KWin accepts negative margins, which a slide off the screen edge needs.

### Shell patterns

| Pattern | How |
|---|---|
| Auto-hide bar | Hide: animate `translate_y` (or `margin_top` negative) to slide it out, then set `exclusive_zone=0` in `on_complete`. Reveal: set the zone first, then slide in. Windows reflow once, not per frame. |
| Notification or island that grows | Create the surface at its largest size. Animate the visible node's `width`, `height` and `corner_radius` inside it. `input_region="auto"` follows. Cost: a larger transparent buffer; damage tracking limits what is redrawn. |
| Close with a fade | Listener on `close_requested` calls `event.cancel()`, animates root `opacity` to 0, and calls `close()` from `animation_end`. |
| Open with a fade | Create the window with root `opacity=0`, then animate to 1 after the first configure. |
| Frame ring that thickens | Animate the ring's path `data` or `stroke_width` in the painter surface. Reservers step their `exclusive_zone` once. |

### Requirements

1. **One clock per loop turn, shared by every window.** The frame ring, the bar and a popup animating together read the same timestamp. Wayland cannot commit separate layer surfaces atomically, so up to one frame of skew between surfaces is possible. Document it; do not promise otherwise.
2. **Progress comes from the clock, not a frame count.** Frame callbacks can stop for an occluded surface or a powered-off output. A stalled surface must not keep the loop awake, and when frames resume, animations jump to the time-correct value. `on_complete` and `animation_end` still fire once the duration has elapsed (`finished=True`), not only after a presented frame. #needs-verification: what the existing loop does today, and which frame callbacks KWin sends to layer surfaces.
3. Reduced motion: `reduced_motion` (exists since 0.5.4 as a window key and event) is provided on `LayerWindow` too. tre only reports it; the shell decides what a reduced animation is. #needs-verification: where tre reads it on KDE Plasma, and whether it follows Plasma's animation speed setting.
4. **Compositor effects.** KWin may apply its own map and unmap effects to layer surfaces. The shell must not rely on either. #needs-verification.
5. **Headless.** `advance(ms)` also advances margin animations and fires their callbacks, so motion is testable with no compositor.
6. **Input region follows the animation** as described under [Input region](#input-region).

Motion tokens (durations, easings, spring bounce) are a design-system concern, not part of this request.

## Use case: screen frame

A frame around the screen edge needs one painter and up to four reservers. Corner zones are not required. The protocol gives a positive exclusive zone only to a surface anchored to one edge, or one edge plus both perpendicular edges, and treats other anchor sets as 0 ([protocol](https://wayland.app/protocols/wlr-layer-shell-unstable-v1)).

| Surface | Anchor | Size | Layer | Exclusive zone | Input region | Draws |
|---|---|---|---|---|---|---|
| Painter | top, bottom, left, right | `(0, 0)` | `top` | `-1` | `"auto"` (the ring only) | The ring, rounded screen corners, concave inner corners (path nodes) |
| Bar (reserver) | top, left, right | `(0, N)` | `top` | `N` | `"auto"` | The bar |
| Side and bottom reservers | one edge plus both perpendicular edges | 1 px on the short axis | `bottom` | `N` | `[]` | Nothing (transparent) |

- The painter extends to every edge and ignores other zones (`-1`). The reservers push maximised windows inside the frame.
- Rounded screen corners and concave inner corners are filled paths in the painter. They need no extra surfaces and no new tre shape features.
- Eight surfaces (four edges, four corners) are rejected: more surfaces, and seams between neighbours at fractional scales. #needs-verification.
- `exclusive_edge` stays in the request for corner-anchored surfaces that reserve one edge, such as a corner clock. The frame does not need it.
- #needs-verification on KWin 6.7: that a full-screen `-1` surface does not disturb the reservers' zones; that a 1 px reserver with an empty input region maps and keeps its zone; and that damage tracking keeps the mostly-transparent painter cheap at idle.

> [!question] Shape gaps for a later request
> Correction, 2026-10-19: tre 0.5.6 added masks ([tre #164](https://github.com/mindderivative/tre/issues/164), closed), so clipping a subtree to a non-rectangular shape exists; the property was not read for this note. Still unconfirmed: concave `corner_radius`, blend modes, and box hit-testing that follows rounded corners or a mask. The frame works without them because paths cover the geometry. Re-check the 0.5.7 docs before deciding whether `TRE-REQ-003` is needed. `TRE-REQ-002` stays reserved for ADR-0001 Option B.

## Required behaviour (non-API)

| Area | Requirement |
|---|---|
| Render | Same pipeline as `Window`: damage tracking, persistent target, no per-frame Python. Idle surfaces draw no frames. |
| Scale | Fractional scale and mixed-DPI outputs. Surface scale follows the output it is on. #needs-verification: `wp_fractional_scale_v1` and `wp_viewporter` on KWin. |
| Input | Pointer, touch, keyboard with key repeat and XKB layout, text input, scroll axes, cursor shape. Input matches `Window` as seen by `engine-core`. |
| Input region | `input_region` as specified above, so a transparent OSD or frame does not capture clicks. |
| Clipboard | `read_clipboard` / `write_clipboard` work from a layer surface that has keyboard focus. |
| Accessibility | The AccessKit tree is exposed for layer surfaces. #needs-verification: whether the current AccessKit adapter requires a `winit` window. |
| Transparency | `transparent` works so rounded or floating bars render without a background rectangle. |
| Threading | `LayerWindow` methods follow the existing rule: cross threads only through `LoopHandle.call_soon`. |
| Headless | `simulate`, `advance` and `snapshot` work without a compositor, using a mock backend for CI. |

## Implementation candidates

tre's backend is `winit` in `engine-platform`. `winit` has no layer-shell role. The design request leaves the choice to the maintainer; these are the candidates, none verified.

| | Approach | For | Against |
|---|---|---|---|
| I1 | Separate Wayland backend in `engine-platform` for `LayerWindow`, built on `smithay-client-toolkit` and driven from the same loop beside `winit`. The `wgpu` surface comes from the raw Wayland handles. | Contained. Ordinary windows are untouched. | Two input and event sources in one loop. Input, text input, clipboard and AccessKit are reimplemented for this path. |
| I2 | Same as I1, but share one `wl_display` connection with `winit`. | One seat, one clipboard, one focus owner. | Spike go ([tre #196](https://github.com/mindderivative/tre/issues/196)): a second event queue on `winit`'s `wl_display` ran beside a `winit` window with no deadlock or lost events. Each side must filter seat events by surface. |
| I3 | Replace `winit` with a native Wayland backend on Linux. | One path, no duplication. | Large. Regresses X11 unless `winit` stays for it. |

Recommendation: take I2. The spike found it workable; I1 is the fallback and I3 stays out of scope. Remaining I2 risks: two readers on one socket and the second input path (seat, focus, clipboard, AccessKit).

> [!danger] Two input sources
> I1 puts seat, focus and clipboard handling in two places. A shell where bar clicks work but the clipboard or focus behaves differently from a tre dialog is a defect users will see. Record in [[Risk Register]] when that note exists.

## Alternatives

| Alternative | Where it lives | Verdict |
|---|---|---|
| External surface: the shell creates the layer surface, tre renders into a handle | ADR-0001 Option B, `TRE-REQ-002` (not written) | Smaller engine change, but the shell inherits configure, scale, hot-plug and input routing. Rejected unless this request proves infeasible. |
| Plain `Window` plus `always_on_top`, `skip_taskbar`, `x`, `y` and KWin rules | ADR-0001 Option C | No exclusive zone, so maximised windows cover the bar. Prototype only. |
| `org_kde_plasma_shell` | ADR-0001 Option D | KDE-only, thinly documented, no prior art. #needs-verification |

## If declined or infeasible

1. Write `TRE-REQ-002` for an external-surface hand-off (ADR-0001 Option B) and re-score the ADR.
2. Until then, the shell runtime builds a throwaway prototype from `Window` with `decorations=False`, `always_on_top` and `skip_taskbar`, kept in `90 Research/` and labelled as not shippable. This lets layout and design-system work proceed.
3. A degraded `Window`-based mode for compositors without layer-shell is a separate product decision and stays out of v1 unless an ADR adds it.

## Acceptance criteria

- [x] On KWin 6.7 Wayland, `LayerWindow(layer="top", anchor=("top","left","right"), size=(0,32), exclusive_zone=32)` creates a bar; a maximised ordinary window does not overlap it. Met live on KWin 6.8.1 and sway (tre hand-off).
- [ ] Changing `exclusive_zone` or `anchor` through `set()` reaches the compositor in one commit with no intermediate configure at a wrong size. One commit by construction; the absence of a wrong-size configure was not measured.
- [x] A `(0, 32)` size without both left and right anchors raises a Python error naming `size` before any protocol request is sent. Met headless.
- [x] A surface bound to output `DP-1` stays on `DP-1`. Unplugging it fires `closed` with reason `"output_removed"`, and the app continues without crashing. Met on sway with a real unplug; KWin not run.
- [x] A `LayerWindow` with `output=None` binds the same output on every run. Met on KWin and sway.
- [x] A transparent `LayerWindow` renders with a transparent background over the desktop. Met on sway (pixels read back); KWin not run.
- [x] Pasting text into a focused `LayerWindow` text field inserts the current clipboard contents. Met on sway with no X server; KWin not run.
- [x] `app.outputs()` lists every connected output with a stable `name`; hot-plug fires `output_added` and `output_removed`. Met on KWin and sway for `outputs()`; added, updated and removed fire on sway.
- [x] A transparent `LayerWindow` with `input_region=[]` passes pointer clicks through to the window below. Met on headless sway (tre #204); KWin not run.
- [x] With `input_region="auto"` and a circular node, a click inside the circle reaches tre and a click in the bounding-box corner outside it reaches the window below. Met on headless sway (tre #204); KWin not run.
- [ ] Screen frame: a painter plus reservers (see [Use case: screen frame](#use-case-screen-frame)) keeps maximised windows inside the inner edge; a click on the ring reaches the shell and a click in the interior reaches the window below. The click routing on a four-bar ring is met on sway (tre #204); the maximised-window part and KWin remain. tre did not test the four reservers plus painter together.
- [x] `window_region="drag"` on a `LayerWindow` node raises when attached. `"drag_margin"` moves a corner-anchored widget, never past the output edge, and fires `moved` with the final margin on release. Met on headless sway (tre #205); KWin and the no-relative-pointer fallback not run.
- [x] `layer_window.animate("margin_top", to=-32, duration_ms=200)` runs with no Python callback until `on_complete`, commits once per frame, and `advance(200)` completes it with no compositor. Met (tre #205); the live check used a positive 0 to 300 px slide, and negative margins on KWin come from the spike.
- [x] Two `LayerWindow`s animating on the same loop turn read the same timestamp. Met by `turn_instant` and a headless test (tre #205).
- [ ] With frame callbacks stopped for a surface, its animation still fires `animation_end` with `finished=True` after the duration. Likely met by design (clock-driven, 8 ms alarm), but tre did not test a covered or occluded surface. Not tested by tre.
- [ ] A fade-out close (cancel `close_requested`, animate `opacity` to 0, `close()` on `animation_end`) keeps the surface mapped until the animation ends.
- [ ] With `reduced_motion` true, `LayerWindow.get("reduced_motion")` reports it and fires the `reduced_motion` event on change.
- [x] A `keyboard="on_demand"` surface receives key events when focused; a `"none"` surface never does. Met on KWin with injected keys.
- [x] A `PopupWindow` opens next to its `anchor_rect`, flips at a screen edge, and fires `closed` with reason `"dismissed"` on outside click and Escape. Replaced by the overlay route (see Delivered): dismissal on outside click and Escape met on KWin and sway; the flip at the bottom edge met on sway.
- [ ] A bar on a 1.0 scale output and a bar on a 1.5 scale output both render crisp text. The surface follows 1.5x on sway; crispness was not inspected.
- [x] `tre.supports("layer_shell")` is `False` on a compositor without the protocol, and `LayerWindow(...)` raises `UnsupportedPlatform` there. Met by the availability rule in headless tests; Mutter not run.
- [ ] `simulate`, `advance` and `snapshot` work on a `LayerWindow` in a CI run with no display.
- [ ] An idle bar draws zero frames and wakes the loop only for its own timers.
- [x] The AccessKit tree for a bar is visible to a screen reader. Verified through a private AT-SPI environment with `busctl` as the reader; Orca not run; the bar's window node has no accessible name yet.

## Open items

- [x] Confirm the absences listed under [What tre has today](#what-tre-has-today) in the tre source. Done in [tre #195](https://github.com/mindderivative/tre/issues/195).
- [x] Choose the implementation path (I1, I2, I3). Spike recommends I2 ([tre #196](https://github.com/mindderivative/tre/issues/196)); the maintainer confirms.
- [x] Check which of `wl_output` v4 and `xdg-output-unstable-v1` KWin exposes for stable output names. `wl_output` v4 gives names (spike).
- [ ] Check whether `window.set(x=, y=, always_on_top=, skip_taskbar=)` does anything on Wayland. tre #195 reads the source: they call `set_outer_position` and `set_window_level`, which `winit` documents as unsupported on Wayland, and `skip_taskbar` is Windows only. So Option C cannot place or stack a bar under KWin. A test on a live session is still pending.
- [x] Decide keyboard focus for popups under a `"none"` parent. Overlay route uses `keyboard="exclusive"` while a menu is open.
- [ ] Define "layer" in the Glossary in both senses (tre in-window overlay, protocol stacking layer) and decide whether `LayerWindow` should rename its `layer=` parameter. Rename declined: tre keeps `layer=`; the shell may use `shell_layer=`. The Glossary entry is still to write.
- [x] Decide whether `LayerWindow.animate` covers only margins or also size and `exclusive_zone` (the request recommends margins only). Margins only, as built.
- [x] Negative margins on KWin: accepted and honoured (spike).
- [ ] Frame-callback behaviour for covered surfaces and KWin's own map and unmap effects on layer surfaces. The spike did not test frame callbacks under a fullscreen window.
- [ ] Whether `reduced_motion` follows Plasma's animation speed. tre reads it from the settings portal (`org.freedesktop.appearance` `reduced-motion`); with Plasma 6.8 at speed factor 0.25 it reported 0, so it likely does not follow the factor. Unconfirmed.
- [x] Phase 5 ([#205](https://github.com/mindderivative/tre/issues/205)) reviewed against this note on 2026-10-23: met on sway, with the gaps listed under [Phase 5 as built](#phase-5-as-built-tre-205). [Margin drag](#margin-drag) is updated for the relative-pointer drag.
- [x] Review tre's scoping of phase 6 ([#206](https://github.com/mindderivative/tre/issues/206)): the three decisions listed there are the maintainer's. Resolved: 6a done, 6b not needed yet ([tre #206](https://github.com/mindderivative/tre/issues/206)).
- [ ] Margin drag ignores other surfaces' exclusive zones, so a widget can be dragged over a bar. Decide whether the shell clamps in the `moved` handler, or asks tre for an optional clamp to the usable area.
- [ ] `reduced_motion` on a `LayerWindow` was not checked in phase 5; the acceptance item above stays open.
- [ ] Mask-aware hit testing: tre #204 made hit testing follow `corner_radius` only; masks and `clip_children` stay ignored. Decide whether the shell needs more before `TRE-REQ-003`.
- [ ] Prototype the screen frame and the full-screen overlay popup alternative, then decide on `PopupWindow` and on `TRE-REQ-003`. tre phase 6a does the overlay half. The spike's `-1` painter and 1 px reserver results support the frame layout. tre did phase 6a; the shell-side frame prototype is still open, and `PopupWindow` is not needed yet.
- [x] tre's animation progress is clock-driven (`Tree::tick_all(now: Instant)`). What the loop does when frames stop is untested; requirement 2 still needs a test.
- [x] Check the 0.5.7 docs for the mask API, concave corners, blend modes and shape-aware box hit-testing. Hit testing follows `corner_radius`, not masks (tre #204).
- [ ] Find the first KWin release exposing `zwlr_layer_shell_v1` (shared with ADR-0001).
- [x] Decide whether v1 targets wlroots-family compositors as well as KWin, which affects which compositors the acceptance tests cover. Both KWin and wlroots (maintainer, tre #195). Only sway and KWin tested.

## Links

- [[ADR-0001 Shell Surface Strategy]]
- [[Prior Art - Linux Shell Surfaces]]
- [wlr-layer-shell-unstable-v1](https://wayland.app/protocols/wlr-layer-shell-unstable-v1)
- [tre Python API](https://mindderivative.github.io/tre/api/python/) · [Custom windowing](https://mindderivative.github.io/tre/design/custom-windowing/) · [Architecture](https://mindderivative.github.io/tre/architecture/)
- [[80 Engine Requests]] · [[Index]]
