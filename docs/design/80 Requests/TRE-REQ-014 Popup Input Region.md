---
title: TRE-REQ-014 Popup Input Region
aliases: [TRE-REQ-014, PopupWindow input_region, Popup Shadow Click-Through]
type: engine-request
status: stable
owner: phil
created: 2026-11-07
updated: 2026-11-07
tags: [engine-request, integration/wayland, needs-verification]
---

# TRE-REQ-014: Popup Input Region

> [!NOTE]
> Give `PopupWindow` an `input_region`, as a `LayerWindow` has, so the transparent shadow margin of a popup lets clicks through to the window below. Drafted by the code session (`tests/kwin/TRE-REQ-014-draft.md` in the tess-shell repository, 2026-11-07); the maintainer directed the `tre` session to work on it (2026-11-07). Raised by the failed KWin retest of popup shadows ([Popup > Found on KWin (maintainer, 2026-11-06)](../40%20Specifications/Surfaces/Popup.md#found-on-kwin-maintainer-2026-11-06), [Risk Register](../00%20Home/Risk%20Register.md) R-30).

> [!NOTE]
> **Not filed from this vault**
> The maintainer carried the request to tre himself (requests go to tre only through the maintainer, AGENTS section 6). The vault records it so the design has one place to read it from.

> [!TIP]
> **Released and confirmed (2026-11-07)**
> tre 0.6.5 brings `PopupWindow(input_region=)` (the code session's [M3 Build Log](../00%20Home/M3%20Build%20Log.md) D99; not read from tre's `LOG.md` here). A shadowed popup sets `input_region="geometry"`, so only the body takes the pointer. The maintainer's KWin retest passes: "shadows have click through now and works well." [Risk Register](../00%20Home/Risk%20Register.md) R-30 is closed.

## Shell Need

[TRE-REQ-007 Popup Body Geometry](TRE-REQ-007%20Popup%20Body%20Geometry.md) is released in tre 0.6.3: `PopupWindow(geometry=)` makes the compositor place, flip and slide the popup body and ignore the transparent shadow margin. The shell uses it, so a popup draws its shadow again (M3 Build Log D93). On KWin 6.8.2 (maintainer, 2026-11-07) placement is right (gap, left and right edges, flip), but a click in the shadow area, about 30 to 40 px around the card, is taken by the popup instead of reaching the window below.

## What Tre Does Today

| Fact | Source |
|---|---|
| `geometry` is the placement rectangle, not an input region | The code session's draft, from the 0.6.3 behaviour on KWin |
| A `LayerWindow` has `input_region=`; a `PopupWindow` has none, and `PopupWindow.set` raises for it | The code session's draft |

Both rows come from the code session and are not checked against tre's source or docs here. #needs-verification

## Proposed Change

`PopupWindow(..., input_region=None | [] | [(x, y, w, h), ...])` and `popup.set(input_region=...)`, with the meaning a `LayerWindow` has: `None` is the whole surface, `[]` is nothing, rectangles are in the popup's own logical pixels, at most 256, sent as `wl_surface.set_input_region`. As a convenience, the string `"geometry"` means the popup's `geometry` rectangle; the shell does not need it.

## Alternatives

None that keeps the shadow. Until the request lands the shell either draws the shadow and accepts a dead area the size of the shadow's reach (30 to 40 px at a 40 % elevation), or draws no shadow (D63, before tre 0.6.3). The maintainer chooses which meanwhile ([Home](../00%20Home/Home.md), Waiting on you).

## If Declined

Popups draw no shadow, or the dead margin stays. [ADR-0010 Surface Shadows](../30%20Decisions/ADR-0010%20Surface%20Shadows.md) route A (a compositor-drawn shadow) is the other way, outside this request.

## Acceptance

A popup with a 20 px shadow margin and `input_region=[(20, 20, w, h)]`: a click in the margin reaches the window below, a click on the body reaches the popup, on sway (pointer by virtual device) and on KWin. With `grab=True`, a click in the margin still dismisses the popup, since it is outside the body.

## Links

[Popup](../40%20Specifications/Surfaces/Popup.md) · [TRE-REQ-007 Popup Body Geometry](TRE-REQ-007%20Popup%20Body%20Geometry.md) · [Risk Register](../00%20Home/Risk%20Register.md) · [80 Requests](80%20Requests.md)
