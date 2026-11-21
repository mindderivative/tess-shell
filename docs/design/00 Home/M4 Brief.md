---
title: M4 Brief
aliases: [M4, Widgets Brief, Shell M4]
type: moc
status: draft
owner: phil
created: 2026-11-05
updated: 2026-11-13
tags: [moc, roadmap, brief]
---

# M4 Brief

> [!NOTE]
> The scope of milestone M4, "widgets": every block and every standard module of [V1 Widgets](../50%20Design%20System/V1%20Widgets.md) is built and checked, operated by the pointer, before the shell reads any desktop service. The maintainer set this on 2026-11-08: "I want the basic widgets completed first. I want M4 to cover all of the V1 Widgets/Modules", moved the D-Bus service layer and the service modules to [M5 Brief](M5%20Brief.md), and made focus and keyboard its own milestone, [M6 Brief](M6%20Brief.md). M4 follows [M3 Brief](M3%20Brief.md) (the look, Panel and Popup, Frame and monitors; confirmed completed by the maintainer on 2026-11-08). It also builds what the widgets need: text input, menus with submenus, the `Call` action and the widget states `Enabled`, `:disabled` and `::part`. This is a plan for the maintainer, written to keep the design ahead of the build ([ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md)). It starts when the maintainer says go.

## State of the Shell at the Start of M4 (2026-11-08)

M0 to M3 are built and KWin-checked. The code session reports tesserae-engine 0.6.5, 1609 tests passing (1 skipped), `ruff` and `mypy` clean ([M3 Build Log](M3%20Build%20Log.md), "M3 Closed"); the vault has not run them.

| Widget | State |
|---|---|
| Box, FlexBox, Text, Rectangle, Spacer, SVG (with the `Icon` key and the icon lookup) | Built in M1 to M3 |
| Popup, Panel, Frame, tooltips, state selectors `:hovered` and `:pressed`, events and actions | Built in M3 |
| ScrollBox, TextField (single and multi-line), Bitmap, Circle, Ring, Path | Not built; confirmed by the W0 inventory (tre has the nodes: `scroll_view`, `text_input`, `image`, `path`) |
| Label, TextBox, TextInput, TextEditor, Icon, Image, Button, Toggle, Checkbox, Slider, ProgressBar, Badge, Tooltip (standard module), List, Menu, MenuItem, Marquee text, Expander | Not built; only Clock is built. Tooltip: the hover hook is built through `Popup` and the Clock declares an inline Tooltip |
| `Enabled`, `:disabled`, `::part` | Not built (D53). tre's `disabled` only sets the accessibility state and does not stop focus, clicks or keys, so the shell must stop events itself (hit testing off, or handlers swallowed) and set `disabled` |
| `Call` and a text-input block, popup submenus, `caller.data` | Not built, waiting on specs ([M3 Build Log](M3%20Build%20Log.md), "M3 Closed") |
| Shell accessibility today | `Label` and `A11y_Hidden` only: no role, state or live-region keys, though tre has `role`, `label`, `focusable`, `disabled`, `checked`, `selected`, `expanded` ([Accessibility](../60%20Quality/Accessibility.md)) |
| Events on blocks today | `On_Click` only, on Box, FlexBox, Rectangle, Spacer and SVG; `On_Changed`, `On_Focus`, pointer and wheel events are not built |
| Dependencies | Pillow is not a dependency (`tesserae-engine`, `tesserae-el`, `tesserae-dl`, `loguru`, `inotify-simple`, `dbus-fast`); W5 needs [ADR-0019 Dependency Policy](../30%20Decisions/ADR-0019%20Dependency%20Policy.md) sign-off |

Decided since M3 and relevant here: handle opacity and the content fade are accepted and not built yet (the code session builds them, [Frame > M3 Final Pass: Peek Findings (maintainer, 2026-11-08)](../40%20Specifications/Surfaces/Frame.md#m3-final-pass-peek-findings-maintainer-2026-11-08)); the fade also applies to an Expander's content (decided 2026-11-08, W8). Specs still owed and not needed by M4: a Bar melded to a Frame, strip expand and contract.

## Goal and Definition of Done

M4 is done when:

- Every block under "Blocks Needed for V1" in [V1 Widgets](../50%20Design%20System/V1%20Widgets.md) works as [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) says: Box, FlexBox, ScrollBox, Text, TextField (single-line and multi-line), Bitmap, SVG and the shapes (Rectangle, Circle, Ring, Path), with their properties, states, events and accessibility defaults.
- Every module under "Standard Modules Needed for V1" works by the pointer: Label, TextBox, TextInput, TextEditor, Icon, Image, Button, Toggle, Checkbox, Slider, ProgressBar, Badge, Tooltip, List, Menu, MenuItem, Marquee text, Spacer and Expander ([Building Blocks > The Modules Built from Them (The Maintainer's List)](../50%20Design%20System/Building%20Blocks.md#the-modules-built-from-them-the-maintainers-list)). All of them are V1 by the maintainer's decisions of 2026-11-08.
- A widget can be disabled (`Enabled`, `:disabled`) and a style can address a widget's parts (`::part`, a Slider's `track` and `handle`).
- A text field takes the keyboard when it is clicked and reports typed text through `On_Changed`; nothing more of the keyboard is in M4 (focus traversal, the focus ring and keyboard operation are [M6 Brief](M6%20Brief.md)).
- `Call`, popup submenus and `caller.data` are built (named in M3's closing note as waiting on specs).
- A widgets gallery shell shows every widget in each of its states; the maintainer checks it on KWin, one look each. Every widget has headless tests (`window.simulate`, [Testing Strategy](../60%20Quality/Testing%20Strategy.md)) and sets its accessibility role, name and state.
- No widget wakes the loop at idle; an animation runs only while it animates ([Performance Budgets](../60%20Quality/Performance%20Budgets.md)).

Not in M4: the D-Bus service layer and the service modules (M5, [M5 Brief](M5%20Brief.md)); Tab and arrow-key focus, the focus ring, `:focused`, keyboard operation of widgets, global shortcuts and the keyboard-only way into a surface (M6, [M6 Brief](M6%20Brief.md)); Grid, Terminal, Canvas and VirtualList (no v1 use).

## Proposed Split

Each half ends with something the maintainer can look at on KWin. Order by dependence: input and the widget states first, because the interactive widgets need them.

| Half | Content | Done when |
|---|---|---|
| M4a: input and states | `Enabled`, `:disabled` and `::part`; TextField in its single-line and multi-line forms (W3); `Call` (W4); the widgets gallery skeleton and its KWin checklist | In the gallery a clicked TextField takes typed text in each form and reports it through `On_Changed`; a disabled block shows its state |
| M4b: display widgets | Label, TextBox, Icon, Image (with Bitmap and image decoding, W5), Circle, Ring and Path, ProgressBar, Badge, Marquee text, Spacer checked, Expander, Tooltip | The gallery shows each, in each state; an Expander opens and closes with its animation and fade and idles at 0 frames; Marquee text scrolls only while it needs to and idles at 0 frames otherwise |
| M4c: interactive widgets | Button (all states), Toggle, Checkbox, Slider (drag), ScrollBox and List, TextInput and TextEditor, Menu and MenuItem with popup submenus and `caller.data` (W4) | The gallery's Button, Toggle, Checkbox, Slider, List, TextInput, TextEditor and a Menu with a submenu work by the pointer |

Recommendation: build in that order.

## Design Needed First

| # | Gap | State | Recommendation |
|---|---|---|---|
| W1 | The standard modules have no spec. Only [Clock Module](../40%20Specifications/Modules/Clock%20Module.md) exists, and [Building Blocks](../50%20Design%20System/Building%20Blocks.md) lists the modules with a sentence each. Each needs properties, parts a style can address (a Slider's `track` and `handle`), states, events, accessibility, a tooltip rule where it applies, a budget and acceptance criteria | None written | One note, `Standard Modules`, with a section per module (Label, TextBox, TextInput, TextEditor, Icon, Image, Button, Toggle, Checkbox, Slider, ProgressBar, Badge, Tooltip, List, Menu, MenuItem, Marquee text, Spacer, Expander), at `review` before M4a, split if it grows. It is a spec under `50 Design System`, linked from [V1 Widgets](../50%20Design%20System/V1%20Widgets.md) and [Modules](../40%20Specifications/Modules/Modules.md). Keyboard operation of each widget is left to [M6 Brief](M6%20Brief.md) and named there |
| W2 | Moved to [M6 Brief](M6%20Brief.md): the focus model and keyboard operation (the number is not reused) | | |
| W3 | Text input. Decided by the maintainer on 2026-11-08: single-line and multi-line, each with the wrapping it can sensibly have. A wrap on a single-line field "makes no sense", so a single-line field has horizontal scroll or ellipsis, and a multi-line field wraps by word or does not. `Wrap` means word wrapping for now; character wrapping comes later. TextInput is the single-line module and TextEditor the multi-line one. Composition and input methods work on layer surfaces in tre 0.5.8, but no real input method was tested | Keys decided (2026-11-08, as recommended); tre's `text_input` options were not read | Specified in [Standard Modules](../50%20Design%20System/Standard%20Modules.md) and [Block Reference > TextField](../41%20TDL%20Reference/Block%20Reference.md#textfield). Keys with no new name: multi-line uses the block key `Wrap: WORD \| NONE` that `Text` already has (`NONE` scrolls horizontally; `CHAR` is added later); single-line uses the existing style key `Overflow` ([Style Schema > Style Keys](../41%20TDL%20Reference/Style%20Schema.md#style-keys)) extended with `SCROLL` for a TextField, default `SCROLL`; the ellipsis shows while the field is not edited and the text scrolls to keep the caret visible while it is. Whether tre's `text_input` supports each behaviour was not read: a gap goes to a `TRE-REQ`. #needs-verification. Input methods tested once on KWin in M4a |
| W4 | `Call`, popup submenus, `caller.data`, and the Menu content. `Call` and `caller.data` were deferred in M3 (D59, D60), popup submenus are not built, `Menu` and `MenuItem` are `draft`. The slot in a `For` argument that [Workspaces Module](../40%20Specifications/Modules/Workspaces%20Module.md) needs (a service module, M5) is the same question as `caller.data` | Specified 2026-11-10 (maintainer: "As recommended") in [Events and Actions > Call, caller.data and Submenus (Decided 2026-11-10)](../42%20Python%20API/Events%20and%20Actions.md#call-callerdata-and-submenus-decided-2026-11-10) and [Standard Modules > Menu and MenuItem](../50%20Design%20System/Standard%20Modules.md#menu-and-menuitem), `draft` until reviewed | `Call` runs a module's `@action` with arguments, a Menu is a Popup whose content is MenuItems, a submenu is a Popup parented to its MenuItem, and `caller.data` is the data the opening block passes. At `review` before M4c |
| W5 | Image decoding and where images come from. Decided 2026-11-01 (R8): the shell decodes images with Pillow and gives tre pixels; the shared converters package is planned ([ADR-0017 Shared Utilities](../30%20Decisions/ADR-0017%20Shared%20Utilities.md), [tess-utils Brief](tess-utils%20Brief.md)); icons come from the shipped set, the freedesktop theme, the config `Icons` folder and the settings list ([Block Reference > Icons (R7)](../41%20TDL%20Reference/Block%20Reference.md#icons-r7)) | The `Icon` key on SVG is built; Image, Bitmap and decoding are not | Write the Image spec in `Standard Modules`: the formats (png, jpeg, gif, webp), caching, an error image, size limits. Pillow is the one new dependency ([ADR-0019 Dependency Policy](../30%20Decisions/ADR-0019%20Dependency%20Policy.md)); confirm it there |
| W6 | The widgets gallery. A shell file that shows every widget in each state is the test fixture, the KWin checklist and the documentation in one | Not written | The code session generates it, as it does the demo configs; the vault session writes the checklist lines in the milestone's build log. One look per widget |
| W7 | Accessibility for v1. [Development Readiness](Development%20Readiness.md) design item 5 ("a short accessibility note": roles and names are in [Block Reference](../41%20TDL%20Reference/Block%20Reference.md); keyboard reach, contrast and reduced motion come from [Portals](../40%20Specifications/Integration/Portals.md)) was never written | Not written | Write it before M4a for roles, names, states, contrast and reduced motion; the keyboard part is written in [M6 Brief](M6%20Brief.md) |
| W8 | Expander and the content fade. Decided by the maintainer on 2026-11-08: the surface content fade applies to an Expander's content too (this replaces my recommendation that it should not) | Decided | The Expander animates its children's size and fades their content with the same progress and easing, with the same `Content_Fade: false` opt-out as a surface ([Frame > M3 Final Pass: Peek Findings (maintainer, 2026-11-08)](../40%20Specifications/Surfaces/Frame.md#m3-final-pass-peek-findings-maintainer-2026-11-08)); reduced motion switches at once |

Notes that must be at `review` before a half starts, with their status on 2026-11-10: the maintainer answered every open question of [Standard Modules](../50%20Design%20System/Standard%20Modules.md) and [Accessibility](../60%20Quality/Accessibility.md) on 2026-11-10 and they are at `review`, so the gate for M4a is cleared; M4b needs `Standard Modules` and [V1 Widgets](../50%20Design%20System/V1%20Widgets.md) (`draft`, to settle); M4c needs `Standard Modules`, [Events and Actions](../42%20Python%20API/Events%20and%20Actions.md) (the W4 section is `draft`) and [Popup](../40%20Specifications/Surfaces/Popup.md) (`stable`). The vault session lists each half's notes and their status before the half starts, and the maintainer waives or accepts any that is not at `review`.

## Tasks

### M4a: Input and States

| # | Task | Done when |
|---|---|---|
| W0 | Inventory: list which blocks and modules of [V1 Widgets](../50%20Design%20System/V1%20Widgets.md) exist in the code, with their properties, and hand the list to the vault session | Done 2026-11-08 by the code session (`/tmp/m4-w0-inventory.md`, main at b6dea30, tesserae-engine 0.6.5); the state table above is corrected from it |
| A1 | `Enabled`, `:disabled` and `::part` on the blocks that need them | A disabled block shows its state and takes no pointer events; a style addresses a Slider's `track` and `handle` |
| A2 | TextField in both forms (W3): caret, selection, paste, `On_Changed`; multi-line `Wrap` word or none; single-line scroll or ellipsis | Typed and pasted text arrives in `On_Changed` in each form; one input-method check on KWin |
| A3 | `Call` (W4) | An action with arguments runs from a block's `On_Click` |
| A4 | The widgets gallery skeleton and its checklist | The gallery starts on KWin and shows a TextField in each form |

### M4b: Display Widgets

| # | Task | Done when |
|---|---|---|
| B1 | Label, TextBox, Spacer (checked), ProgressBar, Badge, Marquee text | Each shows in the gallery in each state; ProgressBar follows a value; Marquee text scrolls only when the text is wider than its box |
| B2 | Bitmap, Image and decoding (W5) | A png, a jpeg, a gif and a webp show; a bad file shows the error image |
| B3 | Circle, Ring, Path; Icon (SVG and bitmap) | The shapes and an icon from each source show; the hit shape is `painted` ([Building Blocks > Open](../50%20Design%20System/Building%20Blocks.md#open)) |
| B4 | Expander with its content fade (W8); the standard Tooltip over the built tooltip hook | It opens and closes with its animation and fade and idles at 0 frames; a Tooltip opens after its delay |
| B5 | A KWin check of the gallery, tests, a measurement | Reported |

### M4c: Interactive Widgets

| # | Task | Done when |
|---|---|---|
| C1 | Button, Toggle and Checkbox: hover, pressed, disabled, and for the last two checked and unchecked; a Button with an icon and a label | The pointer operates them; states show |
| C2 | Slider: drag, `track` and `handle` parts, `On_Changed` | A drag changes the value; the handle follows |
| C3 | ScrollBox and List | A long list scrolls by wheel; the selected entry has a state |
| C4 | TextInput and TextEditor (the modules over TextField) | They edit, show a placeholder and report changes; a TextEditor wraps by word or scrolls by its `Wrap` |
| C5 | Menu and MenuItem, popup submenus, `caller.data` (W4) | A menu with a submenu opens from a Button and works by the pointer |
| C6 | A KWin check of the whole gallery, one look each; tests; a measurement | Reported |

## Dependencies

`tess_re` (`Window.apply`, images, text input, pointer events), `tess_dl`, `tess_el`, `tess_utils` (colour, sides, and the planned image converters); Pillow for decoding (W5, to confirm against [ADR-0019 Dependency Policy](../30%20Decisions/ADR-0019%20Dependency%20Policy.md)); the Popup of M3 for menus. No D-Bus. Nothing here needs tre changes known today; a gap found goes to a `TRE-REQ` through the maintainer ([Vault Reference > Requests between projects](Vault%20Reference.md#requests-between-projects)).

## Risks

- Text input is the likeliest to grow: input methods, selection and paste on a layer surface are only partly tested, and the behaviours (scroll, ellipsis, word wrap or none) are unread in tre's `text_input` (W3).
- A text field is the only widget with the keyboard in M4. If a widget's pointer behaviour has to be reworked for focus in [M6 Brief](M6%20Brief.md), the gallery covers each widget alone so the change is small.
- A module that composes other modules inherits their states; a mistake in Button repeats in every module that uses it. The gallery covers each widget alone before any service module uses it.
- The gallery is large. One look per widget in a single run is about 50 lines; M4a to M4c each have their own run.

## Questions for the Maintainer

1. [x] Scope: TextBox, TextEditor, Badge, Tooltip, Toggle, Marquee text and Checkbox are all V1 (maintainer, 2026-11-08), so M4 builds them with the rest.
2. [x] M5 stays one milestone, broken into smaller parts ([M5 Brief](M5%20Brief.md)); release is M7 and focus and keyboard is M6 ([M6 Brief](M6%20Brief.md)) (maintainer, 2026-11-08).
3. [x] W1 and W7: the vault session writes `Standard Modules` and the v1 accessibility note before M4a (maintainer, 2026-11-08, as recommended). Written, and on 2026-11-10 the maintainer answered all their open questions ([Standard Modules](../50%20Design%20System/Standard%20Modules.md), [Accessibility](../60%20Quality/Accessibility.md)), so both are at `review`.
4. [x] W3 and the wrap: `Wrap` is word wrapping now, character wrapping later; a single-line field has horizontal scroll or ellipsis, a multi-line field wraps by word or does not (maintainer, 2026-11-08).
5. [x] W3: the ellipsis shows while a single-line field is not edited and the text scrolls to keep the caret visible; the keys are the block key `Wrap: WORD \| NONE` for multi-line and the style key `Overflow` extended with `SCROLL` for single-line, default `SCROLL` (maintainer, 2026-11-08, as recommended).
6. [x] W8: the surface content fade applies to an Expander (maintainer, 2026-11-08).
7. [x] The boundary with M6: M4 widgets work by the pointer and a clicked text field takes typed text; Tab and arrow-key focus, the focus ring, `:focused` and keyboard operation of every widget are M6 (maintainer, 2026-11-08, as recommended).
9. [x] W3 and tre: the maintainer chose (a) with (b) meanwhile (2026-11-08, "As you recommend"): he carries [TRE-REQ-016 Text Input Wrap and Overflow](../80%20Requests/TRE-REQ-016%20Text%20Input%20Wrap%20and%20Overflow.md) to tre, and the shell builds a workaround for the single line (fixed height, scroll through `selection` and tre's `caret_move`, ellipsis at rest). A multi-line TextEditor has no word wrap until tre supports it (no shell-side route): it ships with `Wrap: NONE` behaviour or waits, and [Standard Modules > TextEditor](../50%20Design%20System/Standard%20Modules.md#texteditor) says so.
10. [x] W5: Pillow lives in `tess_utils`, imported lazily by `tess_utils.image`, outside the compiled `.so` (maintainer, 2026-11-08; [tess-utils Brief](tess-utils%20Brief.md), [ADR-0017 Shared Utilities](../30%20Decisions/ADR-0017%20Shared%20Utilities.md)). The shell lists Pillow in its own `pyproject.toml` and never imports it directly. The `image` module is built when M4b needs Bitmap and Image.
11. [x] The shell side of `Enabled`: the shell stops the widget's events itself, since tre only sets the accessibility state (maintainer, 2026-11-08, as recommended).
12. [x] Is `Part: <name>` the key that declares a part of a module (a block in its layout), with `Module::part` and `Module::part:hovered|pressed|disabled` as the only selector forms for now? Context: the code session reports (not confirmed here) that the spec was silent and it built `Part:`; `.class::part` and `#name::part` give a "not built" warning; a part rule weighs between class and name. Recommendation: yes; the vault writes `Part` into [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) and the part selectors into [Style Schema](../41%20TDL%20Reference/Style%20Schema.md). Maintainer, 2026-11-13: as recommended.
13. [x] Is this the right behaviour for a disabled block? Context (code session's report): the block and all its descendants take no hover, press or click; a click is swallowed at the block; `pointer_down` and `pointer_up` still bubble, so a press on a disabled block still dismisses a Popup; no tooltip opens over it; re-enabling under the pointer restores hover at the next pointer event. Recommendation: yes; the vault writes it into [Standard Modules](../50%20Design%20System/Standard%20Modules.md) and [Accessibility](../60%20Quality/Accessibility.md). Maintainer, 2026-11-13: as recommended.
14. [x] Should `Call` check its arguments against the action's Python signature at load? Context: the spec says an unknown argument is a load error, but no note declares an action's parameters, so the code session built only the checks that the target module and action exist (reported, not confirmed). `Target` is the module's `Name`, as in `Clock.cycle_format`; the arguments arrive unordered in `event.args`. Recommendation: yes, read the parameter names from the `@action` method's signature, so a module declares nothing extra; the vault amends [Events and Actions](../42%20Python%20API/Events%20and%20Actions.md). Maintainer, 2026-11-13: as recommended.
15. [x] Does `caller.uid` stay the uid of the use of the module that opened the Popup, not a module uid? Context: the Popup note says "module name and UID", but a Popup cannot reach a module UID (reported). Recommendation: yes; the vault corrects the Popup note. Maintainer, 2026-11-13: as recommended.
16. [x] Does `Enabled` on a use of a module disable that module's root block and so its whole subtree? Context: [Standard Modules](../50%20Design%20System/Standard%20Modules.md) says modules take the common keys; the first report said a module call took only its own parameters. The code session now reports (build log, not confirmed here) that a module call takes the common block keys and forwards them to its root, which is the recommendation. Recommendation: yes; the vault writes it into [Standard Modules](../50%20Design%20System/Standard%20Modules.md). Maintainer, 2026-11-13: as recommended.
17. [x] When a surface holds a text field, may the shell override an explicit `Keyboard: NONE` with `ON_DEMAND`? Context (reported): a field needs the keyboard to take typing, and the code session overrides the written value silently. Recommendation: yes, with one warning at load naming the surface and the field, so the override is not silent. Maintainer, 2026-11-13: as recommended.
18. [x] Is synchronous image decoding acceptable for M4? Context (reported): the spec says decoding runs off the loop thread and the image "appears when ready"; the code session decodes on the loop thread, and has not measured a decode against a frame. Recommendation: yes for M4; build the off-thread path when a measured decode of a typical icon or photo exceeds 8 ms, and record the measurement in [M4 Build Log](M4%20Build%20Log.md). Maintainer, 2026-11-13: as recommended.
19. [x] Should module rule keys pass down the chain of first children of a module's layout, instead of styling the module's root block only (D40)? Context (reported): a module whose root is a wrapper then lets a stylesheet rule such as `Clock { Background: ... }` reach the visible block. Recommendation: yes, and the vault amends the D40 wording in [Style Schema](../41%20TDL%20Reference/Style%20Schema.md) to the first-child chain. Maintainer, 2026-11-13: as recommended.
20. [x] Should `On_Text_Commit` stay silent when `Max_Length` rejects an edit? Context (reported): tre fires `input` even then, so the shell's `On_Text_Commit` fires although the text did not change, while `On_Changed` does not. Recommendation: yes, the shell ignores a commit whose text equals the previous text. Maintainer, 2026-11-13: as recommended.
21. [x] Is a submenu declared only as a named Popup (`Submenu: Share_Menu`), with the inline `MenuItem { Children { Menu } }` form left out of v1? Context (reported): only the named form is built; two spellings of one thing would break one-spelling-per-key. Recommendation: yes; the vault amends [Events and Actions](../42%20Python%20API/Events%20and%20Actions.md) to the named form. Maintainer, 2026-11-13: as recommended.
22. [x] Should a submenu get the `caller.data` of the Menu that opened it? Context (reported): today a submenu's `caller.data` is empty, so a submenu item cannot act on the item of the parent menu. Recommendation: yes, read-only and inherited from the Menu that opened it. Maintainer, 2026-11-13: as recommended.
23. [x] Are `.class::part` and `#name::part` left out of v1? Context (reported): only `Module::part` is built; the others warn "not built". Recommendation: yes; part rules are written under the module name (M4 Brief question 12). Maintainer, 2026-11-13: as recommended.
24. [x] Should a disabled Marquee text that is cut with an ellipsis still show a tooltip with its whole text? Context: on KWin (maintainer, 2026-11-11) no tooltip showed over the disabled Marquee however long the pointer stayed; the checklist and [Standard Modules > Marquee text](../50%20Design%20System/Standard%20Modules.md#marquee-text) expect the whole text in a tooltip. The cause is probably the rule of question 13 that no tooltip opens over a disabled block (reported decision 4, not confirmed); without the tooltip a disabled cut text cannot be read. Recommendation: yes; the rule of question 13 gets one exception, the automatic whole-text tooltip of cut text, and the code session fixes it. Maintainer, 2026-11-13: as recommended.
25. [x] Is the one input-method check on KWin (task A2) needed before M4 is done? No: the maintainer did not perform it and does not care about that part (2026-11-11). The input-method behaviour of text fields stays untested ([V1 Widgets](../50%20Design%20System/V1%20Widgets.md), Questions After Testing).

## KWin Results (maintainer, 2026-11-11)

| Checklist | Result |
|---|---|
| M4a, 20 rows (`/tmp/tess-kwin-m4a`) | Rows 1 to 13 and 15 to 20 pass; row 14, the input-method check, not performed (question 25) |
| M4b, 12 rows (`/tmp/tess-kwin-m4b`) | Rows 1 to 4 and 6 to 12 pass; row 5 (Marquee text) passes except the tooltip over the disabled one, which never appears (question 24) |
| M4c, 10 rows (`/tmp/tess-kwin-m4c-widgets`) | All 10 pass |

The Frame look items owed by M4 (`Handle_Opacity`, `Content_Fade` on peeks, Expander `On_Changed`) are not in these checklists and are not built ([M4 Build Log](M4%20Build%20Log.md)).

## Acceptance Criteria

- [ ] Every line of "Goal and Definition of Done" is true, with a KWin check of the gallery.
- [ ] Each task has a test or a recorded measurement.
- [ ] The notes listed under "Design Needed First" are at `review` before the half that needs them starts, or the maintainer has waived one.
- [ ] Design gaps found are handed back to the vault session.

## Links

- [M4 Build Log](M4%20Build%20Log.md) · [Development Readiness](Development%20Readiness.md) · [M3 Brief](M3%20Brief.md) · [M5 Brief](M5%20Brief.md) · [M6 Brief](M6%20Brief.md) · [V1 Widgets](../50%20Design%20System/V1%20Widgets.md) · [Building Blocks](../50%20Design%20System/Building%20Blocks.md) · [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) · [Events and Actions](../42%20Python%20API/Events%20and%20Actions.md) · [Popup](../40%20Specifications/Surfaces/Popup.md) · [Testing Strategy](../60%20Quality/Testing%20Strategy.md) · [Performance Budgets](../60%20Quality/Performance%20Budgets.md)
