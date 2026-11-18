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
