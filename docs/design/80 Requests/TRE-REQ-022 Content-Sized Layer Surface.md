---
title: TRE-REQ-022 Content-Sized Layer Surface
aliases: [TRE-REQ-022, content-sized LayerWindow, size content, auto size layer surface]
type: engine-request
status: accepted
owner: phil
created: 2026-11-17
updated: 2026-11-19
tags: [engine-request, spec/surface, needs-verification]
---

# TRE-REQ-022: A Layer Surface Sized to Its Content, Padding Included, Kept in Step as the Content Changes

> [!NOTE]
> **The maintainer said on 2026-11-19 that it ships in tre 0.6.10.**
> A `LayerWindow` takes a fixed `size`. The shell works around this by measuring the content once in a headless window before the surface exists and fixing that size; when the content changes while the surface is open (the Launcher's result list as the user types) the size cannot follow. The request: tre sizes a layer surface to its content on either axis, includes the root node's padding in that size, and re-requests the size as the content changes, in the same frame as the redraw and without flicker. Written on 2026-11-17 at the maintainer's request ("I want these built"), from the code session's report and the maintainer's own description; the vault session sent it to tre on the maintainer's standing order (2026-11-17), and tre begins work on receipt.

## Built by tre, not yet released (tre's report, 2026-11-17)

The `tess-re` session reports the request built and committed on its local branch `feat/req-022` (`a33341a2`, stacked on `feat/req-023`), not pushed, merged or released (the maintainer's word is needed); it ships in the release after 0.6.9. The vault has not read the code.

- **API:** `LayerWindow(size=(w, h), min_size=None, max_size=None)`. Each axis of `size` is a number of logical pixels or the string `'content'`: `('content', 'content')`, `(480, 'content')` and `('content', 300)` all work. `min_size` and `max_size` are `None` or `(w, h)` with `None` or an int of at least 1 per axis (a minimum above the maximum raises `ValueError`). All three can be changed with `set()` while the surface is open, in either direction (content to fixed and back). `get('size')` returns what was given with `'content'` kept as the word.
- **Padding:** the size on a content axis is the root node's outer size including its padding. Checked: a root with padding 16 around 200 by 80 lays out at 232 by 112. A protocol trace in a private sway with 3 rows of 24 and padding 16 gave 232 by 104, then 128, 152, 176 and 200 as rows 4 to 7 were added. The root is laid out unconstrained on a content axis (or up to `max_size`), so the root must be given no size of its own there.
- **Rounding and requests:** whole logical pixels, rounded up (with a small allowance for float noise), then clamped. tre asks the compositor for the new size once per change, with a new platform command `LayerController::set_size` that touches only the size (a margin animation is untouched). It holds the frame that shows the new content until the compositor's `configure` arrives (a 500 ms deadline for a silent compositor): the first buffer attached is 232 by 104 after `configure(232,104)`, and no buffer of a new size is attached before its configure. Steady content asks for nothing: there was no further `set_size` over the idle seconds after the last change, so there is no resize loop.
- **Other behaviour:** `max_size` clamps (once clamped, more rows ask for nothing more); `min_size` is a floor; a bottom-anchored surface grows upward with its bottom edge fixed; an unanchored surface stays centred. Before the first layout the surface is a 1 by 1 placeholder (or `min_size`) and nothing is drawn. Headless, `root.get('layout_width')` reads the content size.
- **One thing to know** (compositor behaviour, not tre): wlroots lays the surface out at the requested size on the commit that carries `set_size`, one frame before the new-size buffer can be attached (a client cannot send the new-size buffer before the configure). For that one frame the old content sits where the new size puts it: a centred surface's old content is half a step off centre, a bottom-anchored one's is one step high. A screenshot sequence caught it once, 12 px off centre, which is half of a 24 px row. Settled frames are exact. tre's docs say so. The flicker-free wording of this request is therefore met except for that one transitional frame on wlroots.
- Not built: a separate event for the measured size (`get('size')` and the configure event give it). Verified by tre: 5 headless tests, 5 live tests (protocol trace and pixel checks on screenshots taken while rows were added), `cargo test --workspace` 856 passed, full pytest in a private sway 1608 passed, 13 skipped, 0 failed, fmt and clippy clean. Not verified: KWin, a real GPU, a fractional scale (rounded up by construction, not run), macOS and Windows.
- This note stays `accepted` until it is released and the maintainer has seen it on KWin; then `stable`.

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
