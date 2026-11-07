# TRE-REQ-014 (draft): an input region for a PopupWindow

Draft by the tess-shell code session, 2026-11-07. Not sent to tre: the maintainer decides whether to send it.

## What the shell sees

tesserae-engine 0.6.3 added `PopupWindow(geometry=)`, so the compositor places, flips and slides the popup's
body and ignores the transparent shadow margin around it. The shell uses it (a popup draws its shadow).
Maintainer's KWin 6.8.2 retest, 2026-11-07: placement is right (gap, left and right edges, flip), but **a
click in the shadow area, about 30 to 40 px around the card, is taken by the popup** instead of reaching the
window below. `geometry` is the placement rectangle, not an input region; a layer window has `input_region=`
and a `PopupWindow` has none (`PopupWindow.set` raises for it).

## Ask

`PopupWindow(..., input_region=None | [] | [(x, y, w, h), ...])` and `popup.set(input_region=...)`, with the
meaning a `LayerWindow` has (`None`: the whole surface, `[]`: nothing, rectangles in the popup's own logical
pixels, at most 256), sent as `wl_surface.set_input_region`. An `input_region` given with a `geometry`
defaults to that geometry when the caller passes the string `"geometry"` (a convenience; rectangles are
enough for the shell).

## Acceptance

A popup with a 20 px shadow margin and `input_region=[(20, 20, w, h)]`: a click in the margin reaches the
window below, a click on the body reaches the popup, on sway (pointer by virtual device) and on KWin. With
`grab=True`, a click in the margin still dismisses the popup (it is outside the body).

## Workaround meanwhile

None that keeps the shadow: the shell either draws the shadow and accepts a dead area of the margin's size
(the shadow's reach, 30 to 40 px at a 40 % elevation), or draws no shadow (D63, before 0.6.3).
