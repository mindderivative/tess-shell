---
title: TRE-REQ-022 Content-Sized Layer Surface
aliases: [TRE-REQ-022, content-sized LayerWindow, size content, auto size layer surface]
type: engine-request
status: accepted
owner: phil
created: 2026-11-17
updated: 2026-11-17
tags: [engine-request, spec/surface, needs-verification]
---

# TRE-REQ-022: A Layer Surface Sized to Its Content, Padding Included, Kept in Step as the Content Changes

> [!NOTE]
> A `LayerWindow` takes a fixed `size`. The shell works around this by measuring the content once in a headless window before the surface exists and fixing that size; when the content changes while the surface is open (the Launcher's result list as the user types) the size cannot follow. The request: tre sizes a layer surface to its content on either axis, includes the root node's padding in that size, and re-requests the size as the content changes, in the same frame as the redraw and without flicker. Written on 2026-11-17 at the maintainer's request ("I want these built"), from the code session's report and the maintainer's own description; the vault session sent it to tre on the maintainer's standing order (2026-11-17), and tre begins work on receipt.

## Shell Need

The Launcher is a fixed 480 by 400 Panel, so a short result list leaves empty space ([Applications Module](../40%20Specifications/Modules/Applications%20Module.md)). The same holds for any Panel or OSD whose content changes size. The shell's Panel spec already allows `Width: AUTO` and `Height: AUTO` and fits the content once at creation, the way a Popup does ([Panel](../40%20Specifications/Surfaces/Panel.md), [Popup](../40%20Specifications/Surfaces/Popup.md)); what is missing is following the content while the surface is open.

The maintainer's condition (2026-11-17): the size must take the padding into account. A Panel can resize to its content and the space inside it, its `Padding`, must stay: a Panel with `Padding: 16` around 200 by 80 of content is 232 by 112.

## What Tre Does Today

Read in tre's documentation (`docs/api/python.md` and `docs/design/layer-window.md` in the tre repository, 0.6.9, 2026-11-17) and the code session's report:

| Fact | Source |
|---|---|
| `LayerWindow(..., size: tuple[int, int] \| None)` takes pixels; `0` on an axis stretches between two opposite anchors | The constructor signature and the design page ("0 stretches between opposite anchors") |
| `set(size=...)` changes the size later | The `set` row of the LayerWindow table |
| A `configure` event reports the size the compositor gave the surface | The window events table |
| Sizing to content means measuring the laid-out size in Python and calling `set(size=...)` again: a second layout, a configure round trip, and a frame that can be drawn at the old size | The code session's report; reasoning from the API |
| A headless measuring pass works without a display: `get("layout_width")` and `get("layout_height")` read the laid-out size | [Popup](../40%20Specifications/Surfaces/Popup.md), throwaway test on tre 0.5.8, 2026-10-28 |

#needs-verification: whether `layout_width` includes the root node's padding, and what tre does when `size` changes between a commit and its configure.

## Proposed Change

tre implements this; the form is tre's choice, and the shell would use it like this:

- `size` accepts `"content"` for either axis, alone or mixed with a fixed value: `("content", "content")` or `(480, "content")`.
- The requested size on a `"content"` axis is the root node's measured outer size, **including the root node's own padding and border**. So a root with padding 16 and 200 by 80 of content gives a surface of 232 by 112.
- `min_size` and `max_size`, each `(w, h)` in pixels (`None` for no limit), clamp the result. Content larger than `max_size` is clamped; the content scrolls inside it (the application's scroll view, as for a Popup, [Popup](../40%20Specifications/Surfaces/Popup.md)).
- tre re-measures when the content's layout changes (a node added, removed, resized or re-laid-out) and requests a new size from the compositor at most once per frame. The frame that shows the new content is committed at the new size together with the new buffer, so no frame is drawn at the old size when the surface grows, and none is stretched when it shrinks.
- The edge the surface is anchored to stays where it is; an unanchored surface stays centred on its output (a bottom-anchored panel grows upward).
- `get("size")` returns the pair last requested (with `"content"` kept as the word) and a `configure` event gives the size the compositor set, as today. A new event, or a read of the measured size, is welcome but not needed.
- Sizes are whole logical pixels, rounded up, so a fractional scale never clips content.
- Changing `size` to `"content"` or back by `set(...)` works while the surface is open.

## Alternatives

None. The shell can keep measuring and calling `set(size=...)` itself, which is the workaround that exists today: it needs a layout pass of its own, costs a frame of lag and draws a frame at the wrong size on a change.

## If Declined

The Launcher keeps its fixed 480 by 400, and a Panel that wants to follow its content measures and re-sizes by hand with the flicker described above.

## Acceptance

On a private sway, with a Wayland protocol trace:

- A layer window with `size=("content", "content")` holding 3 rows ends at the size of 3 rows; adding rows up to 10 makes the surface follow, with one size request per content change, and no frame in a screenshot sequence shows the new content at the old size.
- With root padding 16, the surface is the content plus 32 on each axis.
- `max_size=(480, 400)` clamps; content beyond scrolls.
- A bottom-anchored surface grows upward and its anchored edge does not move; an unanchored one stays centred.
- No resize loop: a steady content produces no further size requests (a trace over 5 seconds shows none).
- `(480, "content")` keeps the width and follows the height.

## Links

[Panel](../40%20Specifications/Surfaces/Panel.md) · [Popup](../40%20Specifications/Surfaces/Popup.md) · [Applications Module](../40%20Specifications/Modules/Applications%20Module.md) · [TRE-REQ-020 Layer Window Update Before the Surface Exists](TRE-REQ-020%20Layer%20Window%20Update%20Before%20the%20Surface%20Exists.md) · [M7 Brief](../00%20Home/M7%20Brief.md) · [80 Requests](80%20Requests.md)
