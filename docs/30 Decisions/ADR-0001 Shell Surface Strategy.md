---
title: ADR-0001 Shell Surface Strategy
aliases: [ADR-0001, Shell Surface Options, Layer Surface Strategy]
type: adr
status: accepted
owner: phil
created: 2026-10-18
updated: 2026-10-25
tags: [adr, spec/surface, integration/wayland, needs-verification]
---

# ADR-0001: Shell Surface Strategy

> [!NOTE]
> A shell needs surfaces that anchor to screen edges, reserve space, sit on a stacking layer, and control keyboard focus. tre up to 0.5.7 opened only `winit` windows (xdg-toplevel on Wayland) and had none of these; 0.5.8 adds them. This ADR compares four ways to close the gap and recommends adding a layer-surface type to tre.

> [!CAUTION]
> **Blocks the design**
> Without edge anchoring and exclusive zones there is no bar, panel or dock. Every note under `40 Specifications/Surfaces/` depends on this decision.

> [!TIP]
> **Option A is released in tre 0.5.8 (2026-10-25)**
> tre closed [#195](https://github.com/mindderivative/tre/issues/195) and released it in 0.5.8 (`tesserae-engine==0.5.8`): `LayerWindow`, `PopupWindow`, outputs, `input_region`, margin animation and drag, `exclusive_edge`, IME and screen-reader support. Window GPU memory is much lower by default (a bar about 18 MiB, was 198; one shared device is still open as tre #220). Gaps and what was tested: [TRE-REQ-001 Layer Surface Window > Delivered (tre #195 closed)](../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#delivered-tre-195-closed). Accepted by the maintainer on 2026-10-25.

## Context

**What a shell surface needs.** From `zwlr_layer_shell_v1` ([protocol page](https://wayland.app/protocols/wlr-layer-shell-unstable-v1)):

| Need                 | Protocol mechanism                                                                                                                                                                                                                                                                                                     |
|----------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Stacking layer       | `layer`: background, bottom, top, overlay                                                                                                                                                                                                                                                                              |
| Edge placement       | `anchor` bitfield: top 1, bottom 2, left 4, right 8                                                                                                                                                                                                                                                                    |
| Reserved space       | `exclusive_zone`: positive = pixels reserved, 0 = move out of the way, -1 = ignore others and extend to anchored edges                                                                                                                                                                                                 |
| Keyboard focus       | `keyboard_interactivity`: `none` (default), `exclusive`, `on_demand` (since version 4)                                                                                                                                                                                                                                 |
| Per-output placement | The surface is created for a specific `wl_output`                                                                                                                                                                                                                                                                      |
| Popups               | Menus, tray menus and flyouts must open relative to a shell surface. gtk-layer-shell routes GTK popups through the protocol; Quickshell positions its `PopupWindow` with `anchor.window` and `anchor.rect`. tre had no popup type before 0.5.8, which adds `PopupWindow` (an `xdg_popup` parented to a layer surface). |

**What tre provided before 0.5.8.** The [custom windowing page](https://mindderivative.github.io/tre/design/custom-windowing/) documents `Window(width, height, title, decorations=False)`, runtime `decorations` toggling, drag, resize, `minimize/maximize/restore/close`, and `window.get("platform")`. It does not mention layer-shell, anchoring, exclusive zones, popups or raw Wayland handles; tre #195 confirmed the absences in the source. 0.5.8 adds the layer-surface types: [LayerWindow reference](https://mindderivative.github.io/tre/reference/layer-window/).

**What KWin provides.** The wayland.app registry lists KWin 6.7 with `zwlr_layer_shell_v1` version 5. It lists no earlier KWin releases. #needs-verification: find the first KWin version that exposes the protocol, and whether Plasma on the target distro ships it. GNOME's Mutter and Weston do not support the protocol, so a layer-shell design is KDE/wlroots-family only. This matches the Linux/Wayland-only scope in AGENTS §4.

**Prior art.** Fabric, Quickshell, Wayle, Caelestia and DankMaterialShell all place their surfaces on `wlr-layer-shell`. None uses KWin rules or the Plasma shell protocol. GTK shells attach the layer role with `gtk-layer-shell` or `gtk4-layer-shell`; Quickshell has a built-in `WlrLayershell` behind a platform-neutral `PanelWindow`. Fabric exposes `layer`, `anchor`, `exclusivity`, `keyboard_mode`, `margin` and `monitor` to Python. Compositor-specific code (Hyprland, Niri, Sway) covers workspace and window state, not the surface. Details and gaps: [Prior Art - Linux Shell Surfaces](../90%20Research/Prior%20Art%20-%20Linux%20Shell%20Surfaces.md).

**Constraint from the layering principle.** Mechanism belongs in the engine; meaning belongs in the shell (AGENTS > 3. Layering principle). Surface roles are windowing mechanism. The shell decides what a bar contains, not how a compositor places it.

## Options

### Option A — Layer Surfaces in Tre (Recommended)

tre gains a layer-surface window type. Sketch, not existing API:

```python
# Illustrative only. Not part of tre today.
win = LayerWindow(layer="top", anchor=("top", "left", "right"),
                  exclusive_zone=32, keyboard="none", output=output)
```

A platform-neutral variant is also possible: a `PanelWindow`-style type whose layer properties apply on Wayland and are ignored elsewhere, as in Quickshell. Decide this in `TRE-REQ-001`.

- **For:** matches the layering principle. One rendering path (tre owns every frame). Python only sets surface properties, as in Fabric. Every toolkit surveyed attaches the layer role at its own boundary. Other tre users benefit.
- **Against:** implementation cost. `winit` has no layer-shell role of its own, so tre needs a platform-specific path beside it, and that path must reproduce input, text input, scale, clipboard and accessibility handling that `winit` supplies today. Scheduling is not a risk: tre and Tesserae Shell share a maintainer.
- **If infeasible:** fall back to Option B.
- **Status:** built and released in tre 0.5.8 ([TRE-REQ-001 Layer Surface Window](../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md), `stable`). It specifies the window type, outputs and popups, and records the implementation candidates.

### Option B — Shell-created Surface, Tre Renders into it

> [!NOTE]
> **Rejected unless Option A proves infeasible**
> With a shared maintainer there is no schedule reason to prefer B. Keep the option documented; write `TRE-REQ-002` only if the investigation in [TRE-REQ-001 Layer Surface Window > Implementation candidates](../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#implementation-candidates) rules out Option A.

The shell runtime creates the layer-shell surface itself (a Wayland client binding in Python or a small Rust helper) and hands tre a native surface or window handle to render into.

- **For:** the shell controls its own surface lifecycle and is not blocked on layer-shell work in tre.
- **Against:** tre must accept an external surface. The docs reviewed show no such API, so this is still an engine request, though a smaller one. The shell now owns Wayland event handling (configure, resize, scale, output hot-plug) that `winit` normally hides. Input routing between two event sources is a design risk.
- **Needs:** `TRE-REQ-002`, an external-surface or raw-handle request. Not written. #needs-verification

### Option C — Plain Xdg-toplevel plus KWin-specific Placement

Use ordinary tre windows. Position and stack them with KWin window rules or a KWin script (skip taskbar, keep above, fixed geometry).

- **For:** works with tre as it is. No engine request.
- **Against:** no protocol-level exclusive zone, so maximised windows can cover the bar unless KWin scripting reserves space reliably. Placement on Wayland is up to the compositor, so behaviour depends on KWin internals and can break across versions. Rules and scripts must be installed or injected into the user's session, which widens the security surface. It is also KDE-only, with no path to other compositors.
- **Use:** prototyping only. None of the shells surveyed in [Prior Art - Linux Shell Surfaces](../90%20Research/Prior%20Art%20-%20Linux%20Shell%20Surfaces.md) uses this approach. #needs-verification for every KWin scripting claim here.

### Option D — KDE Plasma Shell Protocol

Use KDE's own surface-role protocol (`org_kde_plasma_shell`) instead of `wlr-layer-shell`, with the same hand-off problem as Option B.

- **For:** designed for Plasma panels, so integration with Plasma behaviour is closest.
- **Against:** KDE-only, and less documented than `wlr-layer-shell`. #needs-verification: protocol name, version, and whether KWin still supports it for third-party clients.
- **Use:** research item. None of the shells surveyed uses it, and KDE's own `LayerShellQt` targets `wl-layer-shell`. Do not choose it before the protocol list is verified.

## Comparison

|                            | A: tre layer type   | B: external surface | C: xdg + KWin rules | D: plasma-shell |
|----------------------------|---------------------|---------------------|---------------------|-----------------|
| Edge anchoring             | Yes                 | Yes                 | Approximate         | Yes             |
| Exclusive zone             | Yes                 | Yes                 | Unreliable          | Yes             |
| Layers                     | Yes                 | Yes                 | Partial             | Partial         |
| Engine change              | Large               | Medium              | None                | Medium          |
| Shell complexity           | Low                 | High                | Medium              | High            |
| Compositors                | KDE, wlroots family | KDE, wlroots family | KWin only           | KWin only       |
| Matches layering principle | Yes                 | Partly              | Partly              | Partly          |

## Decision

Accepted 2026-10-25 by the maintainer: **Option A**, layer surfaces in tre. The shell builds its bars, panels, docks, OSDs and popups on `LayerWindow` and `PopupWindow` from `tesserae-engine` 0.5.8 or later ([TRE-REQ-001 Layer Surface Window](../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md)). Options B, C and D are not pursued; `TRE-REQ-002` stays unwritten unless a later ADR supersedes this one.

## Consequences

Option A is accepted, so:

- [TRE-REQ-001 Layer Surface Window](../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md) carries the API, alternatives and fallback.
- tre 0.5.8 has shipped it, so surface specs list [TRE-REQ-001 Layer Surface Window](../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md) in `depends_on` but carry no `Blocked by` callout. A spec names any untested gap from the request that affects it (for example `PopupWindow` Escape dismissal, Orca, input methods).
- The Option C prototype is no longer needed: layout and design-system work can run on `LayerWindow` directly.

## Open Items

- [x] Confirm tre has no layer-shell or external-surface API (Window reference, source). Confirmed in tre #195, now superseded by the build.
- [ ] Find the first KWin release exposing `zwlr_layer_shell_v1`; record the version. Deferred to the testing phase (maintainer, 2026-10-25): Tesserae Shell tests it once a build exists. The design assumes KWin 6.8.1, where tre tested.
- [ ] Verify `org_kde_plasma_shell` status for third-party clients. Deferred to the testing phase (maintainer, 2026-10-25). Option D is not pursued, so nothing in the design depends on it.
- [ ] Decide whether non-layer-shell compositors (GNOME) are explicitly out of scope for v1. Deferred to the testing phase (maintainer, 2026-10-25). Until then the design targets KWin and wlroots compositors; `LayerWindow` raises `UnsupportedPlatform` elsewhere.
- [x] Specify popup behaviour (parenting, grabs, dismissal) in `TRE-REQ-001`. Built as `PopupWindow` in tre 0.5.8; see [TRE-REQ-001 Layer Surface Window > Popups](../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#popups).
- [x] Choose the backend path for layer surfaces: I2 built, a second event queue on `winit`'s `wl_display`; tre binds layer-shell v5 itself. See [TRE-REQ-001 Layer Surface Window > Implementation candidates](../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#implementation-candidates).
- [ ] Read the gtk-layer-shell and Quickshell source to see how they attach a layer role to a toolkit surface; this informs Option B.

## Links

- [wlr-layer-shell-unstable-v1](https://wayland.app/protocols/wlr-layer-shell-unstable-v1)
- [tre: custom windowing](https://mindderivative.github.io/tre/design/custom-windowing/)
- [tre: architecture](https://mindderivative.github.io/tre/architecture/)
- [TRE-REQ-001 Layer Surface Window](../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md)
- [Prior Art - Linux Shell Surfaces](../90%20Research/Prior%20Art%20-%20Linux%20Shell%20Surfaces.md)
- [Open Questions](../00%20Home/Open%20Questions.md) · [Risk Register](../00%20Home/Risk%20Register.md) · [Index](../00%20Home/Index.md)
