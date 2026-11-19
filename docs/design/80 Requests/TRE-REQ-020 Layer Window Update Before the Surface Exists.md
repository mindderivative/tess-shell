---
title: TRE-REQ-020 Layer Window Update Before the Surface Exists
aliases: [TRE-REQ-020, LayerWindow.set dropped, layer window set before created]
type: engine-request
status: accepted
owner: phil
created: 2026-11-16
updated: 2026-11-17
tags: [engine-request, spec/surface, needs-verification]
---

# TRE-REQ-020: A LayerWindow Update Made Before the Surface Exists Must Be Applied

> [!NOTE]
> `LayerWindow.set(...)` called before tre has told Python that the layer surface exists is stored and then dropped: the compositor never receives it. The shell lost the Launcher's keyboard request this way (2 of 10 runs under heavy CPU load, and once on a CI runner). The request: when the surface comes into being, tre applies the stored configuration if it differs from the one the surface was created with, or queues the update until the surface id is known, the way [TRE-REQ-019 Popup Close Before Placement](TRE-REQ-019%20Popup%20Close%20Before%20Placement.md) now remembers a close. Drafted on 2026-11-16 from the code session's report, at the maintainer's request; the maintainer carries it to tre.

## Built by tre 0.6.9 (tre's report, 2026-11-17)

The `tess-re` session reports `tesserae-engine` 0.6.9 on PyPI (tag `v0.6.9`; I read PyPI's version list for 0.6.8 and 0.6.9, not tre's code). The created hook now sends the stored configuration, in the order the `set` calls were made. It reproduced the bug first with `WAYLAND_DEBUG`: `get('keyboard')` said exclusive while the compositor received mode 0, and now it receives 1. It covers keyboard, input region, margin, anchor, size and exclusive zone, since they go through the same config. The shell's workaround (re-sending a shown Panel's keyboard and input region at the first configure) can be dropped. Not verified by tre on KWin. `tess-shell` PR #56 (merged 2026-11-17, by the code session's report) removed the first-configure workaround and measured the Launcher key test 20 runs under 48 busy loops: 20 passed, where 2 of 10 failed before the removal; a live test reads `set_keyboard_interactivity(1)` in `WAYLAND_DEBUG`. This note stays `accepted` until the maintainer has tested it and confirms it; then it becomes `stable`.

## Shell Need

The shell shows a Panel (the Launcher is the first) by creating its layer window and calling `set(...)` with the keyboard mode, input region, margins, anchors, size or exclusive zone straight away. If that call lands between the platform thread creating the surface and the loop thread running tre's created hook, the change is lost with no error and no event. The Launcher then opens without keyboard focus, and a user typing into it types into nothing. The shell works around it by sending a shown Panel's keyboard and input region again at its first configure event (`tess-shell` PR #35); every other user of `LayerWindow` would have to find the same gap.

## What Tre Does Today

Read by the vault session in the tre repository at `94e5e2ab` (0.6.8), 2026-11-16, and the code session's report:

| Fact | Source |
|---|---|
| `LayerWindow.set` stores the new configuration in `state.config` in every case, and sends it to the platform thread only inside `if let (Some(controller), Some(id)) = (state.controller…, state.id.get()) { controller.update(id, config.clone()); }` | `crates/engine-py/src/layer_window.rs`, lines 651 to 662 |
| tre's created hook sets `layer.id` and `layer.controller`, then runs `GpuState::new` (slow on a busy machine) | `crates/engine-py/src/app.rs`, from line 1160 (read to line 1176) |
| The hook does not send the stored configuration. The vault read only the start of the hook; whether it applies the stored configuration later is the code session's finding | The code session's report, 2026-11-16 |
| A `WAYLAND_DEBUG=1` trace of a failing Launcher run has no `zwlr_layer_surface_v1.set_keyboard_interactivity(1)` for the surface although the shell called `window.set(keyboard='exclusive')` at show time; a passing run sends it twice at show time. Reproduced 2 of 10 under 72 busy loops, and once on a CI runner | The code session's report |

#needs-verification: the trace and the reproduction are the code session's; the vault has not run tre.

## Proposed Change

tre implements one of these, at its choice:

1. When the created hook has set the id and the controller, it sends the stored configuration to the platform thread if it differs from the one the surface was created with.
2. `set` keeps the update in a queue while the id is unknown, and the created hook sends the queue.

Either way the order of several `set` calls is kept, and `get(...)` reads back what the compositor was given.

## Alternatives

None that needs less of tre: a caller cannot tell when the hook has run, because there is no event before `configure`.

## If Declined

The shell keeps its workaround (re-sending a shown Panel's keyboard and input region at the first configure).

## Acceptance

A test calls `set(keyboard='exclusive')` right after `add_window`, before the loop has run the created hook, and asserts that the surface ends up with exclusive keyboard interactivity (the request seen on a private sway) and that `LayerWindow.get('keyboard')` agrees; the same for an `input_region` change.

## Links

[TRE-REQ-019 Popup Close Before Placement](TRE-REQ-019%20Popup%20Close%20Before%20Placement.md) · [Applications Module](../40%20Specifications/Modules/Applications%20Module.md) · [Panel](../40%20Specifications/Surfaces/Panel.md) · [M5 Build Log](../00%20Home/M5%20Build%20Log.md) · [80 Requests](80%20Requests.md)
