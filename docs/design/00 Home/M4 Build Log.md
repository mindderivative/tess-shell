---
title: M4 Build Log
aliases: [M4 Log]
type: moc
status: draft
owner: phil
created: 2026-11-10
updated: 2026-11-11
tags: [moc, build-log]
---

# M4 Build Log

> [!NOTE]
> The log of milestone M4, widgets (M4a input and states, then the later parts of [M4 Brief](M4%20Brief.md)). The `tess-shell` code session owns this note ([Build Logs](Build%20Logs.md)). The vault session created it empty on 2026-11-10 when the code session started M4a; the code session fills it in.

## Tasks

M4a, M4b and M4c are built (code session, 2026-11-10 and 2026-11-11). tesserae-engine 0.6.6 (TRE-REQ-016 wrap and overflow on `text_input`, pinned `27860e1`), tess_utils 0.2.0 carried from a LOCAL build (not yet released). Tests 3261 pass, 1 skipped; `ruff` and `mypy` clean. KWin checks are the maintainer's and are not done yet.

| Task | State | Commit | Note |
|---|---|---|---|
| W0 inventory | Done | none | `/tmp/m4-w0-inventory.md`, sent to the vault session |
| A1 `Enabled`, `:disabled`, `::part` | Built | 565aafd | Shell-enforced (tre `disabled` is the a11y state only). `Part: name` key in a module layout; `Module::part[:state]` selectors |
| A3 `Call`, `caller.data` | Built | 565aafd | `On_Click { Action: Call, Target: "Module.action", ...args }`, args in `event.args`, slot args allowed; `caller.data` readable in popup content |
| A2 TextField, TextInput, TextEditor | Built | 9ddbf2e | On tre 0.6.6 properties, no workaround: `Wrap WORD\|NONE`, `Overflow SCROLL\|ELLIPSIS\|CLIP` always set on a single line; `Read_Only`, `Max_Length`, `Password`; `On_Changed`, `On_Submit`, `On_Text_Commit`; a surface with a field gets `keyboard on_demand` automatically |
| A4 gallery | Built | 565aafd, 9ddbf2e | `tests/kwin/prepare_m4a_gallery.py`, `/tmp/tess-kwin-m4a`, 20 rows |
| B1 Label, TextBox, Badge, Marquee text, ProgressBar | Built | 35e101a | Marquee scrolls only when the text is wider than its box, engine-animated |
| B2 Bitmap, Image, decoding | Built | 35e101a | `tess_utils.image.decode_image` (png, jpeg, gif first frame, webp; Pillow lazy, outside the .so); the shell lists Pillow and never imports it; 4096 limit, cache, error image; decoding is synchronous |
| B3 Circle, Ring, Path, Icon | Built | 35e101a | |
| B4 Expander, Tooltip | Partly | 35e101a | Expander with the content fade; string `Tooltip: "text"`. No separate Tooltip module file; Expander `On_Changed` not built |
| B5 gallery | Built | 35e101a | `/tmp/tess-kwin-m4b` |
| C1 Button, Toggle, Checkbox | Built | 1b664a1 | `:checked`, `:selected` states; `Transition` eases state changes |
| C2 Slider | Built | 1b664a1 | Drag with pointer capture, `track` and `handle` parts, steps, vertical |
| C3 ScrollBox, List | Built | 1b664a1 | `Selection: SINGLE\|NONE`; entries identified by `Key` |
| C4 Menu, MenuItem, submenus | Built | 1b664a1 | Popup-in-popup works on the private sway (three levels); tre does not close a submenu when its parent closes, so the shell closes the innermost first |
| C5/C6 gallery | Built | 1b664a1 | `tests/kwin/prepare_m4c_gallery.py`, `/tmp/tess-kwin-m4c-widgets`, 10 rows |
| `Handle_Opacity`, `Content_Fade` on peeks | **Not built** | | Accepted in Frame.md; the B builder ran out of budget; still owed |

## KWin Results (2026-11-11)

Reported by the maintainer on `/tmp/tess-kwin-m4a`, `m4b` and `m4c-widgets`:

All three checklists are now passed (M4a row 14, the input-method check, was not performed). tre 0.6.7 (TRE-REQ-017: row keys, word keys, overwrite, word and string selection) was pinned afterwards and is not checked on KWin; the M4a gallery checklist row 19 lists the new keys.

| Checklist | Result |
|---|---|
| M4a (20 rows) | Pass, except row 14 (the input-method check), which the maintainer did not perform: 'not performing and do not care about this part'. Input methods are untested on a real compositor |
| M4b (12 rows) | Pass, except row 5: no tooltip opened over the DISABLED Marquee text. Cause: the spec says a tooltip never opens over a disabled block 'unless the block says so' but names no key, and M4a decision 4 had made 'none' absolute. Fixed (commit after 1b664a1): a common block key `Tooltip_When_Disabled` (default false) lets a disabled block's tooltip open; the shipped `Marquee_Text` sets it; and a second bug, `Tooltip: "{{ params.Text }}"` was literal text, is fixed. Row 5 re-run: **Pass** (maintainer, 2026-11-11) |
| M4c (10 rows) | Pass |

**Decision to confirm (D-M4-1):** `Tooltip_When_Disabled` is my key name; only Marquee_Text sets it. Label with an ellipsis, TextBox with `Max_Lines` and a TextInput with `Overflow: ELLIPSIS` have no tooltip at all, so their cut text is never shown whole: the vault should say whether they get one.

## Measurements

Private sway (software rendering), idle and active frame counts, from `tests/kwin/measure_m4b.py` and `measure_m4c.py`: M4b idle with Marquees that fit and an Expander at rest 0 frames in 3 s; the Expander opening over 0.4 s 26 frames, then 0 at rest; a scrolling Marquee about 61 frames a second while it moves (0 while paused or fitting). M4c: 0 frames in 3 s at rest with the controls and a List on screen, and with the File menu and two submenus open. KWin figures: not taken yet.

## Differences from the Specs

- **Where the spec was silent and the code decided** (full lists with the alternatives in `/tmp/frame-review/M4A.md`, `TEXTFIELD.md`, `M4B.md`, `M4C.md`; the main ones): a part is declared with `Part: name` (`.class::part` and `#name::part` not built); `Call`'s `Target` is the module's `Name` and its arguments are not checked against the action's signature (no note declares action parameters); a click on a disabled block is swallowed there but `pointer_down`/`pointer_up` still bubble; `caller.use.uid` is the use's uid, not a module uid; a module call takes the common block keys and forwards them to its root; `Content { }` marks where a call's `Children { }` go; module rule keys pass down the first-child chain (a deviation from D40 'roots only'); `Transition`, `Duration`, `Easing` are style keys on every block; Toggle, Checkbox, Slider and List keep their state in the binder through behaviour keys (`Toggles`, `Slides`, `Selection_Mode`, `Chosen`, `Key`, `Menu_Item`, `Opens`); `:checked` and `:selected` are new states; a submenu is a named Popup (`Submenu: Share_Menu`), the inline `MenuItem { Children { Menu } }` form is not built; a submenu's `caller.data` is empty; a single-line TextField with no `Width` is 200 px (tre lays an unset width out at 0); an explicit `Keyboard: NONE` is overridden by the automatic `on_demand` on a surface that holds a field.
- **Existing bug found, not fixed:** a module-root stylesheet rule loses to a type rule on the same key (the spec puts module above type).

## Owed Changes After the Maintainer's Answers (2026-11-13)

M4 Brief questions 12 to 24 answered as recommended. Built 694f1e6 (suite 3449 passed, 1 skipped, 2 deselected; the count fell from 3466 because removing the `Tooltip_When_Disabled` key took 34 parametrised cases of `test_every_key_row_builds_a_node` with it). Report `/tmp/frame-review/M4-OWED.md`.

- Q22: a submenu opened with no `Data` gets a copy of the opening Popup's `caller.data`, read-only, at every level.
- Q20: `On_Text_Commit` is dropped when the text is unchanged after the commit (Max_Length refused the edit); a tre node takes one listener per event type, so the `change` listener is always registered and also calls `On_Changed`.
- Q24: a disabled Marquee text opens its own whole-text tooltip only while the text is cut with an ellipsis; nothing else disabled opens one. The general `Tooltip_When_Disabled` key (3ecb168) is REMOVED (clean cutover). New live test `tests/test_marquee_tooltip_live.py`.
- Q17: `Keyboard: NONE` written on a Panel or Frame holding a text field is overridden to `on_demand` with one load warning naming the surface and the field.
- Q16: `Enabled` on a module use disables the module's root and all under it (already so; pinned by a test).
- Q18: every loop-thread image decode is timed (`IMAGES.timings`); over 8 ms logs a debug line naming the file. Measured: icons and thumbnails up to 512 px under 5 ms; a 1080p JPEG about 10 ms; a 1080p PNG about 18 ms; the shipped icons are SVG and never decoded; the only shipped raster `error.png` 0.04 ms.
- Q14 NOT built: every action is `def x(self, event)` and reads `event.args`, so reading names from the signature would make Workspaces' `Id` a load error. Proposed rule for the maintainer: parameters after `event` are the arguments, checked at load with the nearest name, required ones enforced, passed as keywords; an action with only `event` or `**kwargs` stays unchecked.

Answered by the maintainer on 2026-11-13: Q14 as proposed, `Tooltip_When_Disabled` KEEP, off-thread decode as recommended (M5/M6 list). Built 15b23a8 (suite 3488 passed, 1 skipped, 2 deselected; report `/tmp/frame-review/M4-OWED2.md`): the `Tooltip_When_Disabled` key is RESTORED (the line above that says it was removed is superseded), beside the automatic exception (a disabled Marquee whose text is cut always opens its whole-text tooltip; one whose text fits opens none even with the key; no other disabled block opens one without the key). Q14: the parameters after `event` are an action's arguments; at load an unknown argument gives `unknown-argument` at the handler with the nearest parameter name, a missing required one `missing-argument`; a `{ }` argument is checked by name only; the declared arguments reach the action as keywords and `event.args` stays fully filled; an action with only `event` (every shipped action) is unchecked and free-form; an action with `**kwargs` takes any names but its required parameters are enforced (my choice where the rule left room); applies to `Call` in shell files, Popup content, module layouts and `For` entries and to a bare action name in a module's layout; one finding per handler however many uses.

Former decisions needed (now answered): Q14 rule as proposed? Removing `Tooltip_When_Disabled` right (D-M4-1 never answered)? A 1080p photo is not typical on a Bar, so off-thread decode goes on the M5/M6 list?

## Handle_Opacity and Content_Fade (2026-11-13, dd2af58)

Built from the stable [Frame](../40%20Specifications/Surfaces/Frame.md) spec (accepted 2026-11-08); suite 3612 passed, 1 skipped, 3 deselected; report `/tmp/frame-review/FADE.md`; pushed through `feat/frame-fade`, merged to `main` under the directive.

- `Peek { Handle_Opacity }`: 0 to 1, default 0.6; hover raises the handle to full; a reload changes it in place; outside 0 to 1 is a load error.
- Content fade: the content's opacity is the slide's progress, same duration and easing as the contour; during a drag it is written in one `set` with the content's position in the same call as `Join.seek`; under both `Frame_Blend` settings; peek slide and drag, plain show/hide of a Panel without a `Peek`, strip children with their strip; the tab shows no content. `Content_Fade: false` on a melded `Panel` and on an `Edges` entry; none under reduced motion. The Expander already had `Content_Fade` as a module parameter.
- Measured: headless opacity equals the progress to 1e-6 in a drag; live drag on the private sway (real pointer, continuous grim) within 0.18 at every sample between 0.3 and 0.9, SRGB and LINEAR; 0 idle frames after the slide.
- Differences: a Panel in its own window already fades its whole surface, so `Content_Fade` on one is a load warning; no Bar slides today (a Bar melded to a Frame is not built); tre delivers pointer events to nodes at opacity 0 (collapsed content is hidden at rest; during a slide faint content can still be clicked, as before).
- Questions (my recommendations): a window Panel with `Content_Fade: false` keeps its content opaque? no, the warning stands (`Animation { Type: NONE }` is the opt-out). Faint content refuses clicks during a slide? no until a mis-mapped click is seen. `Handle_Opacity` unchanged while the handle travels? leave.

## Slider On_Released (T-023, 2026-11-13, 9fc42a7)

Suite 3671 passed, 1 skipped, 7 deselected (includes T-025's 3 guard tests); report `/tmp/frame-review/SLIDER-RELEASED.md`; merged to `main` through `feat/slider-released`.

- `On_Released` fires once when a press ends, with `event.value` (and `event.new`) the final value and `event.old` the value at the press; `On_Changed` unchanged. The slider already captures the pointer with tre's `capture_pointer()`, so the release arrives even outside the slider (no new engine API). Also fires on `pointer_cancel` (the press taken for a window move) and when the slider is disabled while held, so a module can always reset its holding state. Only a block with `Slides` can raise it (others get the usual does-not-raise error); the Call argument check works for its handlers.
- Media: `On_Released { Action: release, position: {{ event.value }} }`; `SetPosition` is sent once at release with the final position, nothing during the drag; a touch that moves nothing seeks nowhere; the live position display waits while the handle is held.
- Tests: 7 headless slider tests, Media seek tests, a live test with a real virtual pointer on the private sway (press, drag out of the Bar, nothing sent while held, one seek on release outside; passed 3 of 3).
- Questions: a keyboard step (M6, the Slider has no key handling yet): recommend `On_Changed` then `On_Released` immediately with `old` the value before the step. Cancel and disable also fire the event (alternative leaves Media's drag state stuck): recommend keep. A no-change press fires with old equal new (Media decides by whether the drag moved): recommend keep.

## Expander On_Changed (2026-11-13, 8d183c1)

Built from Standard Modules > Expander ('`On_Changed` fires when an opening or a closing finishes, with `value`'); suite 4138 passed, 1 skipped, 22 deselected; report `/tmp/frame-review/M4-OWED3.md`; merged to `main` through `feat/m4-owed-2`. The Expander root writes `Reveals: {{ "OPEN" if params.Expanded else "CLOSED" }}`, a new module-layout-only key (`NONE | OPEN | CLOSED`, no tre property, like `Slides`); a new `Expand` control remembers the state it started in (no event for that) and on a change either waits for tre's `animation_end` of the eased size and raises `On_Changed` then, or raises it at once when nothing eases (reduced motion, Duration 0, size already there); `event.value` is the new open state (`old`/`new` too); a reversal half-way gives one event. Schema export fixture regenerated; KWin kit line 13 added. The separate Tooltip module file is NOT built: the spec's Tooltip section gives the module no params or layout and describes exactly the built `Tooltip` key; question sent to the vault session (A: the built key IS the standard module, amend the spec; B: delays on the string form; C: a child-block module registering on its parent, not recommended).

## Facts About tre, TEL and tess_dl

- tre 0.6.5: `text_input` refused `wrap` and `overflow`, and its default single-line input wrapped by word while `multiline=True` did not wrap at all. 0.6.6 fixes it (TRE-REQ-016); with `overflow` unset a single line still wraps, so the shell sets it on every field.
- tre `disabled` only sets the accessibility state; it does not stop focus, clicks or keys.
- `On_Text_Commit` is tre's `input`, so it still fires when `Max_Length` rejects an edit; `On_Changed` does not.
- In a wrapped multi-line input the arrow keys and Home/End move by logical line (tre's known limit).
- Popup in popup works on the private sway; tre does not close a submenu when its parent closes.
- tre has no `Fit: NONE` for an image (the shell uses the natural pixel size).
- A headless tre has no clipboard service; an early probe run WITH the desktop's `WAYLAND_DISPLAY` set wrote text to the maintainer's real clipboard (my fault: the brief said tests, not probes). Every probe now runs with `env -u WAYLAND_DISPLAY -u DISPLAY`.

## Decisions Needed

The numbered decisions are in the four reports above (A: 12, textfield: 11, B: 12, C: 16). The ones that change behaviour a user can see: (1) an explicit `Keyboard: NONE` is overridden on a surface with a text field; (2) image decoding is synchronous (the spec says off the loop thread, 'appears when ready'); (3) module rule keys pass down the first-child chain, deviating from D40; (4) `Call` arguments are not validated; (5) `On_Text_Commit` fires on a rejected `Max_Length` edit; (6) the submenu is declared as a named Popup.

## For the Vault Session

- Write `Part:` and the part selectors into Block Reference and Standard Modules, and the disabled-block behaviour into Accessibility (M4 Brief q12 and q13 recommend yes).
- `tess_utils` 0.2.0 (`decode_image`) is built and committed locally in the tess-utils repo and carried in the shell; the push, the tag and the GitHub release wait for the maintainer.
- Owed to code: `Handle_Opacity` and `Content_Fade` for peeks (accepted), the Expander `On_Changed`, a separate Tooltip module file, off-thread image decoding, `Content_Fade` on an Expander is built.
- Owed to the vault: a decision on `.class::part` and `#name::part`, on inline submenus (`MenuItem { Children { Menu } }`), and on `caller.data` for a submenu.

## Links

- [Build Logs](Build%20Logs.md) · [M4 Brief](M4%20Brief.md) · [M3 Build Log](M3%20Build%20Log.md)
