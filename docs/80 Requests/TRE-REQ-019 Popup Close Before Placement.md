---
title: TRE-REQ-019 Popup Close Before Placement
aliases: [TRE-REQ-019, PopupWindow close before placement, silent popup close]
type: engine-request
status: accepted
owner: phil
created: 2026-11-15
updated: 2026-11-17
tags: [engine-request, spec/surface, needs-verification]
---

# TRE-REQ-019: A Popup Closed Before the Compositor Places It Must Close

> [!NOTE]
> `PopupWindow.close()` called before the compositor has placed the popup does nothing and reports nothing, so the popup appears a moment later and stays on screen with no owner. The request: tre remembers the close and carries it out when the popup is placed, with the same events as any other close. Written on 2026-11-15 at the maintainer's request, from the code session's report; the maintainer reviewed it and carried it to tre on 2026-11-15. It stays `accepted` until tre has built it and the maintainer confirms it.

## Built by tre 0.6.8 (tre's migration notes, 2026-11-15)

The migration notes of `tesserae-engine` 0.6.8 (read by the vault session in the tre repository) say: a popup or layer window closed before it is placed now closes. `close()` called in the same loop turn as `App.add_window`, before the compositor's first configure, was ignored, and neither `close_requested` nor `closed` came. The close is now remembered and made when the surface exists, with the same events (`closed`, reason `"app"`) (tre's task T-019). Code that guarded its own close can drop the guard: the shell did (`tess-shell` PR #16, by the code session's report). The request's note about a `LayerWindow` is covered too. The vault has not run tre. This note stays `accepted` until the maintainer has tested it and confirms it; then it becomes `stable`. `tess-re` confirms (2026-11-17) that it first reproduced the gap (a 120x80 popup left 9,600 pixels of its fill in a screenshot, and 0 after) and that `close()` on a `PopupWindow` or `LayerWindow` before placement is remembered and made when the surface exists, with `close_requested` then `closed` with reason `"app"`; a second `close()` is harmless. Not verified by tre on KWin.

## Shell Need

A [Popup](../40%20Specifications/Surfaces/Popup.md) is opened and closed by user actions that can follow each other within one frame: a pointer that enters and leaves a tray icon, a menu opened and dismissed by a key, a tooltip whose trigger goes away. The shell calls `close()` as soon as the reason to show the popup is gone. When that happens before placement, the popup must not appear at all, or must go away at once. A popup that stays cannot be dismissed by the user, because the shell has already dropped it.

## What Tre Does Today

| Fact | Source |
|---|---|
| `PopupWindow.close()` is documented as: "Closes the popup on the loop's next turn: `close_requested` first, then `closed` with reason `"app"`". Nothing is said about a popup that is not placed yet | tre's Python API page, the `PopupWindow` table (read in the tre repository, `docs/api/python.md`, 2026-11-15) |
| With `tesserae-engine` 0.6.7, `close()` before the compositor's first configure of the popup is ignored: no event, no error, and the popup is shown when the configure arrives. The popup has no window id until then | The `tess-shell` code session's report (found by its CI, 2026-11-14; fix `6d24108`, test `tests/test_popup_close.py`). The vault has not run tre. #needs-verification |

## Proposed Change

tre implements this: a `close()` on a popup that is not placed yet is kept and carried out when the popup is placed (or the popup is never mapped), and the popup's owner gets `close_requested` and then `closed` with reason `"app"`, the same as for a placed popup. A second `close()` stays harmless. The same holds for a `LayerWindow` closed before its first configure, if it has the same gap.

## Alternatives

None that needs less of tre. If a deferred close is not possible, `close()` before placement raises or returns a value that says the close did not happen, so that a caller cannot miss it.

## If Declined

The shell keeps its own guard (built in `6d24108`): it marks a popup closed before placement and closes it when the configure arrives. Every other user of tre has to find the gap the same way.

## Acceptance

Open a popup and call `close()` in the same loop turn, before any configure: the popup is never visible in a screenshot taken after the next frames, and its `closed` event arrives with reason `"app"`. The shell's `tests/test_popup_close.py` passes with the shell's guard removed.

## Links

[Popup](../40%20Specifications/Surfaces/Popup.md) · [TRE-REQ-014 Popup Input Region](TRE-REQ-014%20Popup%20Input%20Region.md) · [M5 Build Log](../00%20Home/M5%20Build%20Log.md) · [80 Requests](80%20Requests.md)
