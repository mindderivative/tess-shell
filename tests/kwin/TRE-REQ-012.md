# TRE-REQ-012: Draw a Window Whose Node Was Changed in Another Window's Callback

> Reported by the `tess-shell` code session on the maintainer's instruction (2026-11-06); not filed upstream by the code session. Evidence from tess_re 0.6.1 (`tesserae-engine` 0.6.1), Python 3.14.9, on KWin 6.8.2 (the maintainer's session) and on a private headless sway. The repro, the probe and the shell's log are in the `tess-shell` repository under `tests/kwin/`.

## Summary

A node property set in window B during a callback of window A (a timer, an event listener) is not drawn until something else wakes the event loop. In a shell with several windows (a bar and panels), a click on the bar that changes a panel leaves the panel showing what it showed before: a hidden panel stays on screen, a shown panel stays empty. A queued `LoopHandle.call_soon(lambda: None)` after the change makes B draw in 1 to 3 ms, so the shell works around it, but the engine should not need the caller to wake it.

## Shell Need

`tess-shell` has one `App` with several `LayerWindow`s: a Bar and Panels. A click on a block in the Bar can show, hide or toggle a Panel, a theme change touches every window, and a module's value may feed a node in a Panel. All of these change a window other than the one whose callback is running. The change must reach the screen without the shell waking the loop by another route.

## What tre Does Today

`tests/kwin/repro_cross_window_redraw.py` uses only `tess_re`. It opens a bar A and a card B (two `LayerWindow`s). A timer of A sets B's card fill (between two opaque colours) once every 1.5 s, six times with a plain `set`, then six times with `set` followed by `handle.call_soon(lambda: None)`; B's `frame` events are timestamped. Milliseconds from each change to B's next frame, on a private sway (three runs):

| Variant | Run 1 | Run 2 | Run 3 |
|---|---|---|---|
| `set` | 1501, 1, 1, 2, 1, 2 | 3001, 1501, 1500, 1500, 1499, 1501 | 3001, 1501, 1500, 1500, 1501, 1499 |
| `set` then `call_soon` | 2, 2, 2, 2, 1, 1 | 1, 1, 1, 1, 1, 1 | 1, 1, 1, 1, 1, 1 |

A change followed by no wake is drawn when the loop next wakes for an unrelated reason (here A's next timer, 1.5 s later; 3001 ms means two wakes were missed). It sometimes draws at once (run 1), so the behaviour is inconsistent as well as late.

`tests/kwin/probe_hide.py` (six buttons, six cards, toggles made from the buttons' click handlers, so a different window's callback) on KWin 6.8.2, the maintainer's machine, time to the card's first frame:

| Change made to the card | hide | show |
|---|---|---|
| root node `visible` only | **no frame in 500 ms** | **no frame** |
| fill to 1/255 alpha and back | **no frame** | **no frame** |
| root `visible`, then `call_soon(noop)` | (not tried on hide) | 1 ms |
| fill to 1/255 alpha, then `call_soon(noop)` | 1 ms | 1 ms |
| the same change made inside a `call_soon` callback | 1 ms | 1 ms |
| surface resized to 1 by 1 and back | 3 ms | 3 ms |
| window closed and a new one made | n/a | 5 ms |

The same pattern shows in `tess-shell`'s own log: with a hidden Panel kept mapped (root not visible), the 2026-11-05 KWin log had `a frame 1 ms after it was hidden` on every hide and **no frame after a show** until the shell's own 250 ms debug timer woke the loop; with a `call_soon` wake added after each change (2026-11-06) every one of about 60 toggles drew in 1 to 2 ms.

Two observations that may help: a window that has its own recurring timer (`b.every(5000, ...)`) draws promptly after the change, while one with a single pending `after` does not; and changing alpha sometimes draws at once where changing an opaque colour does not. So what draws B depends on what else keeps the loop awake.

## Why It Belongs in the Engine

Which window's frame runs a callback, and whether a window requested a frame after a property changed, are decided inside the loop. tre's own documentation says a surface draws when something changed and costs nothing when idle ("Idle costs nothing"); a caller cannot tell from outside whether a change made in another window's callback requested a frame. `LoopHandle.call_soon` is documented as the cross-thread wake, not as something to call after every `set`.

## Proposed Change

When a node property of window B changes (or `LayerWindow.set` changes a layer setting) outside B's own frame, request a frame for B exactly as a change made in B's own callback does, including when the loop is otherwise idle and when the change comes from the callback of another window. No API change.

Possible cause, from the 0.5.10 occlusion notes (`design/occlusion.md`): a layer surface is drawn only after the frame callback for its last frame, with `ControlFlow::Wait`. If a change made in another window's callback marks B dirty without waking the loop or requesting B's frame, B waits for the next unrelated wake. This is a guess; tre knows.

## Alternatives

| Option | Against |
|---|---|
| Callers call `call_soon(noop)` after every cross-window change (the shell's workaround today) | A wake the engine should not need; every multi-window app has to discover it |
| A documented rule that a change in B needs a wake | The rule is surprising (a single window works) and inconsistent as measured above |
| Callers make every change inside a `call_soon` callback | Same, and slower to write |

## If Declined

The shell keeps its wake after every change it makes to its windows (`SurfaceManager.wake`), with a test that fails without it. The request stays recorded as the reason.

## Open Questions

1. [ ] Whether tre treats this as a bug or as documented behaviour.
2. [ ] Whether the same happens for `Window` (xdg toplevel) windows as for layer surfaces (the shell has layer surfaces only).
3. [ ] Why a window with a recurring timer draws promptly after such a change and one without does not.

## Acceptance Criteria

- [ ] In `repro_cross_window_redraw.py`, B's next frame follows every plain `set` within a few milliseconds, in all runs.
- [ ] `probe_hide.py` shows a frame within a few milliseconds for every change on KWin and sway, with no `call_soon`.
- [ ] A hidden-then-shown layer surface (root `visible` False then True) is drawn after a show made from another window's click listener, with no wake.
