---
title: TRE-REQ-024 Outside Press and Keyboard Leave on Layer Surfaces
aliases: [TRE-REQ-024, outside press, keyboard leave, dismiss on outside click, exclusive layer surface dismissal]
type: engine-request
status: accepted
owner: phil
created: 2026-11-17
updated: 2026-11-17
tags: [engine-request, spec/surface, needs-verification]
---

# TRE-REQ-024: Tell the Application When a Press Lands Outside a Layer Surface, or When the Keyboard Leaves It (Either One)

> [!NOTE]
> A Panel that holds the keyboard exclusively (the Launcher) cannot learn that the user clicked elsewhere, so it cannot hide itself the way a menu does. The request: tre gives the application **one of two signals, whichever it can deliver**: that a pointer press landed outside the `LayerWindow` (`outside_press`), or that keyboard focus left it (`keyboard_leave`). The maintainer said on 2026-11-17 that the two are alternatives and that both sound technically difficult, so the request asks for the one tre can build reliably and a written reason for the other. Written at the maintainer's request ("I want these built"); the vault session sent it to tre on the maintainer's standing order (2026-11-17), and tre begins work on receipt.

## Answered by tre (tre's report, 2026-11-17)

The `tess-re` session reports the request done as: `keyboard_leave` delivered, `outside_press` not built as a tre option, with written reasons and a working recipe. Committed on its local branch `feat/req-024` (`b342ea34`, stacked on 022 and 023), not pushed, merged or released. No new API and no new engine code: docs and tests only, so the recipe works with `tesserae-engine` 0.6.9 today. The vault has not read the code.

1. **Keyboard leave.** A `LayerWindow`'s `active` event (`window.on('active', lambda e: ... e.active ...)`) is the compositor's `wl_keyboard` enter and leave; it already existed and is now tested and documented. Verified in a private sway with a virtual keyboard: a first exclusive surface gets `active` true; a second exclusive surface opens, first `active=False`, second `True`; the second closes, the first is `True` again. It is not fired by a click elsewhere while the surface holds the keyboard exclusively (the compositor does not take the keyboard for a click); with `keyboard='on_demand'` a click on another window does move focus away and it fires. So it covers the keyboard-taken row of the table above, not the click-away.
2. **Outside press, by a recipe.** tre tested it in a private sway: a transparent 1 by 1 `PopupWindow(launcher, size=(1, 1), anchor_rect=(0, 0, 1, 1), grab=True)` hung off an exclusive-keyboard panel is dismissed by a click on another application's window or on the empty desktop; its `closed` event arrives with reason `'dismissed'`, and the panel keeps the keyboard. Use: `catcher.on('closed', lambda e: hide() if e.reason == 'dismissed' else None)` and `app.add_window(catcher)` from a handler with the panel open. No prior input to the panel was needed for sway to accept the grab.
3. **Why not a tre option** (tre's written reasons): (a) Wayland gives a client no way to see a press on another client's surface without taking it, so any catcher, this popup grab or a full-output transparent layer surface, swallows the click and the user clicks again; the request's "observed, not swallowed" cannot be met by any mechanism tre knows of, so an option could only wrap the recipe; (b) the grab is one-shot: after a dismissal it is gone and a new popup is needed; (c) a click on another surface of the same application is delivered normally and does not dismiss the catcher (the grab belongs to the client), so the shell's own windows, such as its Bar, will not trigger it; (d) compositors differ on whether they accept a grab without a recent input serial from the panel: sway did, KWin is not verified; (e) the transparent full-output surface was not tested, since (a) rules it out for the observe-not-swallow goal.
4. **Verified:** 2 tests (the `active` sequence true, false, true; the click dismisses the catcher with reason `dismissed` and the panel still gets a later key), using `wtype` and the virtual pointer helper, never `/dev/uinput`. Not verified: KWin for both signals. If the maintainer wants the recipe wrapped as an `outside_press` event anyway, tre will build it on top of the popup grab.

## Shell Need

The Launcher opens as an exclusive-keyboard Panel on the overlay layer. It closes on Escape, on starting an application and on its shortcut toggle; a click outside does not close it, and nothing is built for that ([Applications Module](../40%20Specifications/Modules/Applications%20Module.md), maintainer's decision of 2026-11-16). Users expect a launcher to close when they click away, and the same holds for any shown Panel with exclusive keyboard.

## What Tre Does Today

| Fact | Source |
|---|---|
| A `Window` has an `active` event ("gained or lost focus") | tre's API page, window events (`docs/api/python.md`, tre 0.6.9, 2026-11-17). #needs-verification: whether a `LayerWindow` receives it from the compositor's keyboard enter and leave |
| `show_layer(..., dismissible=True)` closes a layer on a press outside it, for layers inside one window (a menu) | tre's guide, Layers |
| A popup has a grab, so a press outside it is delivered to it | The shell's Popup work, [Popup](../40%20Specifications/Surfaces/Popup.md) |
| The layer-shell protocol sends a layer surface the pointer events that land on it and none for a press on another surface; with exclusive keyboard interactivity the compositor owns keyboard focus until the surface goes | The maintainer's description of 2026-11-17 and the code session's report. #needs-verification |

## Proposed Change

tre implements at least one of these, as far as the platform allows, and says in its reply which, and why not the other:

1. **Outside press.** A `LayerWindow` option such as `dismiss_on_outside_press=True` that makes tre emit an `outside_press` event when a pointer press lands outside the surface on the same output. How is tre's choice. One way that works on any compositor is an input-only, fully transparent layer surface that tre owns, sized to the output and stacked just below the window, created and destroyed with it; its stacking is untested (the code session's note). A compositor-specific route (a popup grab or a KWin interface) is acceptable where it is better. This one closes the Launcher on a click on the desktop or another window, which is what a user expects.
2. **Keyboard enter and leave.** A `LayerWindow` reports when keyboard focus enters it and leaves it (the compositor's keyboard enter and leave events), as `active` or `keyboard_enter` and `keyboard_leave`, with a reason where the protocol gives one. This is plain protocol: a client is told when it loses the keyboard. It covers a compositor taking the keyboard away (another exclusive surface, a lock screen, a switch of the active window).

What each gives the shell, so that the choice is made with the facts:

| Signal | A click on the desktop or another window | The keyboard taken by something else |
|---|---|---|
| `outside_press` | Closes the Launcher | Not seen |
| `keyboard_leave` | Not seen while the Launcher holds the keyboard exclusively; it would be seen if the Launcher used `ON_DEMAND`, where a click elsewhere moves focus away (the Launcher uses `EXCLUSIVE` by the maintainer's decision of 2026-11-16, because `ON_DEMAND` gave no keys without a click on sway and was never tried on KWin) | Closes the Launcher |

Either signal is useful; `outside_press` is the one that matches the user's expectation, and `keyboard_leave` is the one that is plain protocol. If tre can do only `keyboard_leave`, the shell uses it for the second row and the click-away stays unbuilt.

## Alternatives

The two signals are alternatives of each other (above). If tre finds that neither can be delivered reliably on KWin and sway, the shell builds the click-catcher itself (the code session's idea of a transparent full-output Panel under the Launcher), with the stacking risk on the shell's side.

## If Declined

The Launcher stays closable by Escape, a launch and its shortcut only.

## Acceptance

On a private sway (and KWin where it can be driven), for the signal tre builds:

- `keyboard_leave`: a `LayerWindow` with exclusive keyboard emits `keyboard_leave` when a second exclusive surface takes the keyboard, and `keyboard_enter` when it returns.
- `outside_press`: with `dismiss_on_outside_press=True`, a pointer press on another window or on empty desktop on the same output emits one `outside_press` with the press position; a press inside the surface emits none; a press on the surface's transparent input margin follows the surface's input region.
- Either way: no surface is left behind when the window closes, no wake-ups are added while idle, and what clicks reach the windows below is unchanged (the press is observed, not swallowed, unless the application asks for it).

## Links

[Applications Module](../40%20Specifications/Modules/Applications%20Module.md) · [Panel](../40%20Specifications/Surfaces/Panel.md) · [Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md) · [TRE-REQ-022 Content-Sized Layer Surface](TRE-REQ-022%20Content-Sized%20Layer%20Surface.md) · [M7 Brief](../00%20Home/M7%20Brief.md) · [80 Requests](80%20Requests.md)
