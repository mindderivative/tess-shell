---
title: TRE-REQ-007 Popup Body Geometry
aliases: [TRE-REQ-007, tre Popup Geometry, Popup Window Geometry]
type: engine-request
status: draft
owner: phil
created: 2026-10-28
updated: 2026-10-28
tags: [engine-request, integration/wayland, needs-verification]
related: ["[[Popup]]", "[[ADR-0010 Surface Shadows]]", "[[TRE-REQ-001 Layer Surface Window]]", "[[80 Engine Requests]]"]
depends_on: []
---

# TRE-REQ-007: Popup body geometry

> [!summary]
> Let a `PopupWindow` say which rectangle of its surface is the popup proper, so the compositor places and constrains that rectangle and ignores a transparent margin around it (a shadow margin). Written for the future; the shell has a workaround, so nothing is blocked. The maintainer will carry it to tre when it is wanted.

> [!info] Not to be filed now
> Written 2026-10-28 after the maintainer decided that a popup's placement uses its visual shape. Not filed from this vault, and the `tre` session has not been told ([[AGENTS#6. Engine requests (tre / Tesserae)]]).

## Shell need

A popup with a shadow draws the shadow in a transparent margin inside its own surface, because a surface cannot draw outside itself ([[ADR-0010 Surface Shadows]]). The maintainer decided (2026-10-28, [[Popup]]) that the compositor places the visual shape (the border and the body), and that the transparent margin is ignored and not counted in the popup's size.

## What tre does today

| Fact | Source |
|---|---|
| A `PopupWindow` creates an `xdg_popup` with a positioner (anchor rectangle, anchor, gravity, adjustment, offset) | [layer-window reference](https://mindderivative.github.io/tre/reference/layer-window/#popupwindow) |
| tre sets the popup's window geometry to the whole surface: `set_window_geometry(0, 0, width, height)` | `crates/engine-platform/src/layer.rs`, line 921 (read 2026-10-28) |
| A popup's size is fixed for its life and its settings cannot change after it is made | [layer-window reference](https://mindderivative.github.io/tre/reference/layer-window/#popupwindow) |
| tre passes the last input serial it saw to the grab | `layer.rs`, `popup.xdg_popup().grab(&seat, self.last_serial)` |

The xdg-shell protocol places and constrains the window geometry, not the whole surface, so a shadow margin inside the surface moves the visible body and can make the compositor flip a popup that would fit. #needs-verification against xdg-shell's `set_window_geometry` text.

## Why it belongs in the engine

The window geometry is a Wayland request on the popup's own `xdg_surface`; the shell has no access to it. It is mechanism: which part of a surface the compositor treats as the window.

## Proposed API

> [!danger] Proposal, not existing API
> Names are mine and tre may choose others.

```python
PopupWindow(parent, size=(w + 2 * m, h + 2 * m), geometry=(m, m, w, h), ...)
```

- `geometry` is `(x, y, width, height)` in the popup's own pixels. Default: the whole surface, which is today's behaviour.
- The anchor rectangle, gravity and `offset` then refer to the body, and `configure` reports the body's position.
- It must lie inside the surface; otherwise `ValueError`.
- Optional: the same for `LayerWindow`, which does not need it (a layer surface is placed by anchor and margin, and the margin is the shell's to compute).

## Alternatives

| Alternative | Verdict |
|---|---|
| The shell compensates: it shifts `offset` by the margin so the body lands where the whole surface would have put it | The workaround. It works for placement; the compositor's flip and slide still use the whole surface, so a popup near a screen edge can flip a margin early |
| No shadow margin on popups | Loses elevation on menus |
| The shell ignores the question | The body lands a margin off where `attach` and `gap` say |

## If declined

The shell uses the workaround: it computes the margin from the shadow ([[Style Schema#Shadow keys]]), enlarges the popup by it, and shifts `offset`. Flip and slide decisions use the larger rectangle, so a popup with a shadow can flip up to one margin early.

## Size

Small by reading the code: one argument, and the `set_window_geometry` call takes it instead of `(0, 0, width, height)`. Not measured.

## Links

[[Popup]] · [[ADR-0010 Surface Shadows]] · [[80 Engine Requests]]
