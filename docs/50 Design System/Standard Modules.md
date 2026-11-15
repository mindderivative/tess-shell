---
title: Standard Modules
aliases: [Standard Widgets, Shipped Modules, V1 Standard Modules]
type: design
status: accepted
owner: phil
created: 2026-11-08
updated: 2026-11-13
tags: [design, spec/widget, needs-verification]
---

# Standard Modules

> [!NOTE]
> The spec of the standard modules that ship with the shell and that [M4 Brief](../00%20Home/M4%20Brief.md) builds: Label, TextBox, TextInput, TextEditor, Icon, Image, Button, Toggle, Checkbox, Slider, ProgressBar, Badge, Tooltip, List, Menu, MenuItem, Marquee text, Spacer and Expander. Every one is V1 (maintainer, 2026-11-08). A module is composed in TDL from the blocks of [Block Reference](../41%20TDL%20Reference/Block%20Reference.md), called by name, with Python only where it needs it ([Building Blocks](Building%20Blocks.md)). This note gives each module's job, the blocks it is built from, its keys, parts, states, events, accessibility and acceptance. **Everything below is a proposal for the maintainer unless it says decided**: no widget was built when this was written, and the vault session wrote the key names from the existing key vocabulary. Keyboard operation is not here: it is [M6 Brief](../00%20Home/M6%20Brief.md); M4 operates every widget by the pointer.

## Purpose and Scope

- One place for the properties of the standard modules, so [V1 Widgets](V1%20Widgets.md) stays a list and [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) stays about blocks.
- Out of scope: the keyboard behaviour of each widget and the focus model ([M6 Brief](../00%20Home/M6%20Brief.md)); the service modules ([M5 Brief](../00%20Home/M5%20Brief.md)); Checkbox's and Toggle's look beyond the parts named here (the theme and stylesheets decide it, [Style Schema](../41%20TDL%20Reference/Style%20Schema.md)).

## Rules That Hold for Every Module

| Rule | Source |
|---|---|
| Keys are Capitalised, enum values are full upper case, a four-sided value runs left, top, right, bottom | [TDL Language](../41%20TDL%20Reference/TDL%20Language.md), D32 |
| A module takes the common block keys: `Name`, `Class`, `Style`, `Tooltip`, `Visible`, `Enabled`, the size keys, the child keys and the accessibility keys | [Block Reference > Common Properties](../41%20TDL%20Reference/Block%20Reference.md#common-properties) |
| A module with `Enabled: false` takes the style state `Disabled`, sets the accessibility state `disabled` and ignores input; tre does not do this, the shell does | [Block Reference > State](../41%20TDL%20Reference/Block%20Reference.md#state) |
| Data goes in through a key and edits come out through an event; there is no two-way binding | R6, [Block Reference > Decisions of 2026-11-01](../41%20TDL%20Reference/Block%20Reference.md#decisions-of-2026-11-01) |
| An event key is `On_` plus the event name, and runs an action | [Events and Actions](../42%20Python%20API/Events%20and%20Actions.md) |
| A style addresses a part of a module with `::part`; the parts of each module are listed below and built in M4a | [Building Blocks > Properties, Parts and States](Building%20Blocks.md#properties-parts-and-states) |
| A module animates only while it animates; at rest it draws no frames | [Performance Budgets](../60%20Quality/Performance%20Budgets.md) |
| A module with an animation honours reduced motion: it switches state at once | [Goals and Non-Goals](../10%20Vision/Goals%20and%20Non-Goals.md) G7 |
| A user module with the same name overrides a shipped one; a name registered twice otherwise is a load error | [ADR-0014 Shell File Language > File Layout (Decided 2026-10-29)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#file-layout-decided-2026-10-29) |

## Text and Display

### Label

A single line of text, no wrap, not editable. Built from `Text`.

| Key | Values | Default | Meaning |
|---|---|---|---|
| `Text` | A string; may hold slots | empty | The words |
| `Overflow` (style) | `CLIP`, `ELLIPSIS` | `CLIP` | What happens when the text is wider than the Label |

Accessibility: no role; the Label carries the text as its `Label` unless it labels another block. Events: the common ones. Acceptance: a longer text clips or shows an ellipsis; a slot updates the text without a rebuild.

### TextBox

Multi-line text, not editable (clarified 2026-10-26). Built from `Text`.

| Key | Values | Default | Meaning |
|---|---|---|---|
| `Text` | A string | empty | The words |
| `Wrap` | `WORD`, `NONE` | `WORD` | `NONE` keeps lines as written and scrolls horizontally |
| `Max_Lines` | A whole number | none | Truncates after this many lines |
| `Selectable` | true, false | false | Lets the user select the text |

Part: none. Accessibility: role none; a TextBox that holds the main content takes `Role: TEXTBOX` and `Label` from the author. Acceptance: a long text wraps by word at the width; `Wrap: NONE` scrolls; `Max_Lines` truncates.

### Marquee text

A long text scrolling in a small space. Built from `Text` with an animated `Translate_X`.

| Key | Values | Default | Meaning |
|---|---|---|---|
| `Text` | A string | empty | The words |
| `Speed` | Pixels per second | 30 | The scroll speed |
| `Pause` | Milliseconds | 1500 | The wait at each end before the scroll turns or restarts |
| `Direction` | `LEFT`, `RIGHT` | `LEFT` | The direction of the scroll |
| `Loop` | `RESTART`, `BOUNCE` | `RESTART` | Jump back to the start, or scroll back |

Behaviour: the text scrolls only when it is wider than its box; if it fits it is a Label and draws nothing animated. The scroll runs only while the Marquee is visible; a hidden or off-screen Marquee stops. Reduced motion: no scroll; the text shows with an ellipsis and the whole text is in the tooltip. Accessibility: the full text is the `Label`, so assistive technology does not read a moving fragment. Acceptance: 0 frames at idle when the text fits; the animation stops when the block is hidden; reduced motion shows the ellipsis.

### Badge

A count or a dot on an icon. Built from `Circle` and `Text`.

| Key | Values | Default | Meaning |
|---|---|---|---|
| `Count` | A whole number | none | The number shown; `0` or none shows nothing unless `Show_Zero` |
| `Show_Zero` | true, false | false | Show a badge for a count of 0 |
| `Max` | A whole number | 99 | Above this the badge reads `99+` |
| `Dot` | true, false | false | A dot with no number |

Part: `::dot`. Placement: the Badge is an absolute child at a corner of its parent (`Position: ABSOLUTE`, `Right`, `Top`). Accessibility: the Badge sets the `Label` of its parent text, for example "3 notifications", and is itself `A11y_Hidden`. Acceptance: counts, `99+`, the dot and the hidden zero.

### Icon

A named or file icon. Built from `SVG` and `Bitmap`. The lookup order is decided: the shipped set, the freedesktop theme, the config `Icons` folder, the settings list ([Block Reference > Icons (R7)](../41%20TDL%20Reference/Block%20Reference.md#icons-r7)). The `Icon` key on `SVG` is built (M2).

| Key | Values | Default | Meaning |
|---|---|---|---|
| `Icon` | A name, or a file path relative to the file that names it | none | The icon |
| `Size` | A length | 16 | Width and height |
| `Color` (style `Foreground`) | A colour | the text colour | The icon's colour; an SVG with `currentColor` follows it |

Accessibility: `A11y_Hidden` true unless `Label` is set. Failure: a missing icon shows the `image-missing` icon and one warning per name. Acceptance: one icon from each source shows; the colour follows `Foreground`.

### Image

An image from png, jpeg, gif or webp, decoded by the shell (R8, Pillow; the decoding helper lives in `tess_utils`). Built from `Bitmap`.

| Key | Values | Default | Meaning |
|---|---|---|---|
| `Source` | A file path, relative to the file that names it | none | The image |
| `Fit` | `CONTAIN`, `COVER`, `FILL`, `NONE` | `CONTAIN` | How it fits its box ([Block Reference > Bitmap](../41%20TDL%20Reference/Block%20Reference.md#bitmap)) |
| `Placeholder` | A colour or an icon name | none | Shown while it loads and when it fails |

Behaviour: decoding runs off the loop thread and the image appears when ready; the decoded pixels are cached by path and modification time; a file larger than 4096 by 4096 pixels is refused with one warning (proposed limit); an animated gif shows its first frame in v1 (R8). Failure: a bad file shows the error image and one warning. Accessibility: `A11y_Hidden` true unless `Label` is set. Acceptance: a png, a jpeg, a gif and a webp show; a bad file shows the error image.

### Spacer

Flexible empty space; built from `Box`. Built in M1 ([M4 Brief](../00%20Home/M4%20Brief.md) checks it). `Width`, `Height` and `Flex_Grow` work as on any block; a Spacer has no event handlers of its own and takes no pointer events unless `On_Click` is set on it. Acceptance: in a Bar, left, centre and right groups separated by Spacers keep their places when the Bar is resized.

## Pointer and Input Controls

### Button

A pressable control with states. Built from `Box`, `Text` and `Icon`.

| Key | Values | Default | Meaning |
|---|---|---|---|
| `Text` | A string | none | The label |
| `Icon` | An icon name | none | An icon before the text |
| `Icon_Position` | `START`, `END` | `START` | Where the icon sits |
| `On_Click` | event | none | A press and release on the Button |

States: `Hovered`, `Pressed`, `Disabled` ([Style Schema](../41%20TDL%20Reference/Style%20Schema.md); `Focused` is [M6 Brief](../00%20Home/M6%20Brief.md)). Parts: `::icon`, `::label`. Role `BUTTON`. A Button with only an icon needs a `Label`; without one the shell warns at load. A press that starts on the Button and ends outside it cancels with no click. Acceptance: the states show; a click runs the action; a disabled Button ignores the pointer.

### Toggle

A switch. Built from `Box` and `Circle`.

| Key | Values | Default | Meaning |
|---|---|---|---|
| `Checked` | true, false | false | The state, set from outside |
| `On_Changed` | event | none | Fires when the user flips it, with `value` (true or false); it does not fire when the module sets `Checked` |

Parts: `::track`, `::thumb`. Role `SWITCH`, state `checked`. The thumb slides in the theme's motion duration; reduced motion switches at once. Acceptance: a click flips it and fires the event once; setting `Checked` moves it without the event.

### Checkbox

A check box, separate from Toggle (maintainer, 2026-10-27): a box with a check mark. Built from `Box` and `Path`.

| Key | Values | Default | Meaning |
|---|---|---|---|
| `Checked` | true, false | false | The state |
| `Text` | A string | none | A label beside the box; a click on it flips the Checkbox too |
| `On_Changed` | event | none | As for Toggle |

Parts: `::box`, `::mark`. Role `CHECKBOX`, state `checked`. A mixed state is not in v1. Acceptance: as for Toggle; the label's click flips it.

### Slider

A draggable value. Built from `Box` and shapes.

| Key | Values | Default | Meaning |
|---|---|---|---|
| `Value` | A number | `Min` | The value, set from outside |
| `Min`, `Max` | Numbers | 0, 100 | The range |
| `Step` | A number | 1 | The increment; a drag snaps to it |
| `Orientation` | `HORIZONTAL`, `VERTICAL` | `HORIZONTAL` | The direction |
| `On_Changed` | event | none | Fires while the user drags and on a click on the track, with `value` |

Parts: `::track`, `::fill`, `::handle`. Role `SLIDER`, with `value`, `value_min`, `value_max`, `value_step` and the actions `increment`, `decrement` and `set_value` ([Block Reference > Accessibility Defaults](../41%20TDL%20Reference/Block%20Reference.md#accessibility-defaults)). The drag uses `pointer_down`, `pointer_move` with pointer capture and `pointer_up`; there is no drag event in tre ([Block Reference > Events](../41%20TDL%20Reference/Block%20Reference.md#events)). Events during a drag are coalesced to one per frame. Acceptance: a drag changes the value and the handle follows; a click on the track jumps; the value stays inside the range.

Decided 2026-11-13 (orchestrator, Tier 1, from the Media build): the Slider has an `On_Released` event, raised once when a drag or a click on the track ends, with the final value in `event.value`. `On_Changed` keeps firing while the value moves. A module that must act once, such as a seek, uses `On_Released`. As built (code session's report, `9fc42a7`, not run in the vault): it fires once per press, also when the pointer is released outside the slider, on a cancelled press and when the slider is disabled mid-press, and also when the value did not change; `event.value` holds the final value. In M6 a keyboard step raises `On_Changed` and then `On_Released` (orchestrator, 2026-11-13).

### ProgressBar

A read-only bar. Built from `Box`.

| Key | Values | Default | Meaning |
|---|---|---|---|
| `Value` | A number | 0 | The progress |
| `Min`, `Max` | Numbers | 0, 100 | The range |

Parts: `::track`, `::fill`. Role `PROGRESSBAR` (tre's page lists more roles than the Block Reference does; whether `PROGRESSBAR` is among them is not read) with `value`, `value_min`, `value_max`. A change of `Value` animates the fill in the theme's motion duration. An indeterminate bar is not in v1. #needs-verification. Acceptance: the fill follows the value and stays inside the track.

### TextInput

A single-line text field, editable. Built from `TextField`. Decided (maintainer, 2026-11-08, as recommended): a single-line field does not wrap; it scrolls horizontally or shows an ellipsis.

| Key | Values | Default | Meaning |
|---|---|---|---|
| `Text` | A string | empty | The value, set from outside |
| `Placeholder` | A string | none | Shown while the field is empty |
| `Overflow` (style) | `SCROLL`, `ELLIPSIS`, `CLIP` | `SCROLL` | `SCROLL` keeps the caret in view as the user types. `ELLIPSIS` shows an ellipsis while the field is not being edited and scrolls while it is |
| `On_Changed` | event | none | Every change the user makes (keystroke, paste, deletion), with `old_value` and `new_value`; not when the module sets `Text` |
| `On_Submit` | event | none | Enter |
| `Read_Only` | true, false | false | The text can be selected and copied but not changed (tre's `read_only`; maintainer, 2026-11-10, as recommended) |
| `Max_Length` | A whole number | 0 | The most characters the field takes; 0 is no limit (tre's `max_length`) |
| `Password` | true, false | false | Shows dots instead of the text and blocks copy and cut (tre's `obscured`) |

Behaviour: a click puts the caret in the field and gives it the keyboard (the surface needs `Keyboard: ON_DEMAND` or `EXCLUSIVE`, [Surface Types](../40%20Specifications/Surfaces/Surface%20Types.md)); selection, copy and paste work; committed text from an input method arrives through `On_Text_Commit` ([Block Reference > TextField](../41%20TDL%20Reference/Block%20Reference.md#textfield)). Role `TEXTBOX`. Part: `::placeholder`. Acceptance: typed and pasted text arrives in `On_Changed`; `SCROLL` keeps the caret visible; an ellipsis shows at rest and not while editing; one input-method check on KWin.

> [!CAUTION]
> **tre 0.6.5 cannot select these behaviours (code session's W0 probe, 2026-11-08; not checked in the vault)**
> tre's `text_input` refuses `wrap` and `overflow` ("applies only to a text node"), and its observed behaviour is the inverse of the decision: a default single-line input wraps by word onto several lines and grows, and `multiline=True` does not wrap. A single-line scroll or ellipsis and a multi-line word wrap cannot be chosen by a property today. Decided (maintainer, 2026-11-08): the maintainer sends [TRE-REQ-016 Text Input Wrap and Overflow](../80%20Requests/TRE-REQ-016%20Text%20Input%20Wrap%20and%20Overflow.md) to tre, the shell builds the single-line workaround meanwhile (fixed height, scroll through `selection` and `caret_move`, ellipsis at rest), and a TextEditor has no word wrap until tre supports it ([M4 Brief](../00%20Home/M4%20Brief.md), question 9).
>
> The same probe found that tre 0.6.5 has `read_only`, `max_length` and `obscured` (password masking) on `text_input`. An earlier version of this note and of [Block Reference > TextField](../41%20TDL%20Reference/Block%20Reference.md#textfield) said tre has none, from tre's documentation page; that was wrong for 0.6.5. They are offered as the keys `Read_Only`, `Max_Length` and `Password` (maintainer, 2026-11-10, as recommended); `Password` is on TextInput only. #needs-verification

### TextEditor

A multi-line text field, editable. Built from `TextField` with `Multiline: true`.

| Key | Values | Default | Meaning |
|---|---|---|---|
| `Text`, `Placeholder`, `On_Changed` | as for TextInput | | |
| `Read_Only`, `Max_Length` | as for TextInput | | `Password` is not offered on a TextEditor |
| `Wrap` | `WORD`, `NONE` | `WORD` | `WORD` wraps at the width by word. `NONE` does not wrap and scrolls horizontally. Character wrapping (`CHAR`) comes later (maintainer, 2026-11-08) |
| `Lines` | A whole number | none | A height in lines, when `Height` is `AUTO` |

Behaviour: Enter inserts a newline (there is no `On_Submit`); the field scrolls vertically; selection, copy and paste work. Role `TEXTBOX`. Acceptance: a long line wraps by word or scrolls by `Wrap`; Enter adds a line; a long text scrolls vertically.

Until tre supports a word wrap on `text_input` ([TRE-REQ-016 Text Input Wrap and Overflow](../80%20Requests/TRE-REQ-016%20Text%20Input%20Wrap%20and%20Overflow.md), decided 2026-11-08), a TextEditor has no word wrap: it behaves as `Wrap: NONE`, and `Wrap: WORD` is accepted with one warning and no effect, so a shell file written for the final behaviour loads. The `WORD` default above is the target and not what 0.6.5 does.

## Lists and Menus

### List

A scrolling list, the usual target of a repeater. Built from `ScrollBox`, `FlexBox`.

| Key | Values | Default | Meaning |
|---|---|---|---|
| `Selected` | An entry key, or none | none | The chosen entry, set from outside |
| `Selection` | `NONE`, `SINGLE` | `SINGLE` | Whether an entry can be chosen |
| `On_Changed` | event | none | The user chose an entry, with `value` (its key) |

Behaviour: the entries are children, usually a `For` repeater keyed by an id (TEL reconciles by key, [ADR-0008 Tesserae Expression Language](../30%20Decisions/ADR-0008%20Tesserae%20Expression%20Language.md)); the List scrolls by the wheel; a chosen entry takes the style state `Selected`. A List of more entries than a ScrollBox can build is the case `VirtualList` waits for (R3). Role `LIST`, entries `LISTITEM`, `selected` on the chosen one. Acceptance: a list longer than its box scrolls; a click chooses an entry; setting `Selected` marks it without the event.

### Menu and MenuItem

Menu content for a Popup. A Menu is a Popup whose content is MenuItems; a MenuItem is a Button-like row.

| Module | Key | Values | Meaning |
|---|---|---|---|
| Menu | none of its own | | The content of a `Popup`; it takes the Popup's keys for placement ([Popup](../40%20Specifications/Surfaces/Popup.md)) |
| MenuItem | `Text`, `Icon` | | The row |
| MenuItem | `Shortcut_Text` | A string | A key hint shown at the end (display only) |
| MenuItem | `Separator` | true, false | A rule between groups; takes no events |
| MenuItem | `On_Click` | event | Runs the action, then the menu closes |
| MenuItem | a child `Menu` | | A submenu: opens beside the item on a pointer rest and on a click |

A submenu is a Popup parented to its MenuItem's Popup. It is built in M4c with `caller.data` and `Call`, specified in [Events and Actions > Call, caller.data and Submenus (Decided 2026-11-10)](../42%20Python%20API/Events%20and%20Actions.md#call-callerdata-and-submenus-decided-2026-11-10) (maintainer: "As recommended", 2026-11-10): the opening rules, the one-at-a-time rule, the depth of three levels and the open point whether tre can parent a popup to a popup are there. Roles `MENU` and `MENUITEM`, with `expanded` on an item that has a submenu. Parts: `::icon`, `::label`, `::shortcut`, `::arrow`. States: `Hovered`, `Pressed`, `Disabled`. Acceptance: a menu opens from a Button; a click on an item runs its action and closes the menu; a submenu opens beside its item and closes with its parent.

## Reveal and Hover

### Expander

Shows or hides children with an animation. A must have (maintainer, 2026-10-26; renamed from Revealer 2026-11-01). Built from `Box`.

| Key | Values | Default | Meaning |
|---|---|---|---|
| `Expanded` | true, false | false | The state, set from outside |
| `Direction` | `DOWN`, `UP`, `LEFT`, `RIGHT` | `DOWN` | The edge the content grows from |
| `Duration` | Milliseconds | the theme's | The animation time |
| `Content_Fade` | true, false | true | The content's opacity follows the animation (decided 2026-11-08: the surface content fade applies to an Expander too, [Frame > M3 Final Pass: Peek Findings (maintainer, 2026-11-08)](../40%20Specifications/Surfaces/Frame.md#m3-final-pass-peek-findings-maintainer-2026-11-08)); `false` opts out |
| `On_Changed` | event | none | Fires when an opening or a closing finishes, with `value` |

Behaviour: the size and the content opacity follow the same progress and easing; an interrupted animation turns round from where it is. At rest it draws no frames. Reduced motion switches at once. Role none; the controlling Button carries `expanded`. Acceptance: it opens and closes with its animation and fade and idles at 0 frames.

### Tooltip

Hover text. The hover popup is built through `Popup` and the `Tooltip` key on every block (M3: `Tooltip: true` on a Popup, `Enter_Delay` 500 ms and `Exit_Delay` 200 ms, [Popup > Tooltips (decided 2026-10-28)](../40%20Specifications/Surfaces/Popup.md#tooltips-decided-2026-10-28)). The standard module is the short form for the common case: a block names its tooltip text and does not write a Popup.

| Key | Values | Default | Meaning |
|---|---|---|---|
| `Tooltip` (on any block) | A Popup, or a string | none | A string is shorthand for a one-line tooltip Popup with the text (decided 2026-11-10, as recommended; [Popup > Tooltips (Decided 2026-10-28)](../40%20Specifications/Surfaces/Popup.md#tooltips-decided-2026-10-28) has the Popup form and notes the shorthand) |
| `Enter_Delay`, `Exit_Delay` | Milliseconds | 500, 200 | As built |

A tooltip is not focusable, opens with no keyboard focus and never opens over a disabled block unless the block says so. It reads the block's `Label` when no text is given. Acceptance: a string opens a one-line tooltip after the delay and closes after the exit delay; the pointer moving onto the tooltip keeps it open (as built).

Decided 2026-11-13 (orchestrator, Tier 1): there is no separate Tooltip module file. A tooltip is the `Tooltip` key on a block or a module call: a string, or a Popup block that carries its own `Enter_Delay` and `Exit_Delay`. The Expander's `On_Changed` is built: it fires when an opening or a closing finishes, with the new state in `event.value`.

## Keyboard Operation (M6)

Written for [M6 Brief](../00%20Home/M6%20Brief.md) gap K2 ("As recommended, in `Standard Modules`", maintainer, 2026-11-10), so each widget's keys are in the note that defines the widget. M4 builds none of it: the widgets are operated by the pointer. The focus model, the Tab order and the shortcut mode are in [Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md). Keys follow the common patterns; the code session and the gallery check them in M6b. #needs-verification

| Widget | Takes focus | Keys while focused | Accessible state |
|---|---|---|---|
| Label, TextBox, Badge, Icon, Image, ProgressBar, Spacer, Marquee text | No (a TextBox with `Selectable` can) | None | Read only |
| Button | Yes | Enter and Space press it (`On_Click`, as [Block Reference > Accessibility Defaults](../41%20TDL%20Reference/Block%20Reference.md#accessibility-defaults) says) | `pressed` while held |
| Toggle, Checkbox | Yes | Space flips it and fires `On_Changed`; Enter does nothing | `checked` |
| Slider | Yes | Left and Down decrease, Right and Up increase by `Step`; Page Up and Page Down by ten steps; Home and End go to `Min` and `Max` | `value`, `value_min`, `value_max`, `value_step` |
| TextInput | Yes | Typing, arrows, Home and End, Shift selects, Ctrl+A, Ctrl+C, Ctrl+X, Ctrl+V; Enter fires `On_Submit`; Tab leaves the field | none beyond `TEXTBOX` |
| TextEditor | Yes | As TextInput; Enter inserts a newline; Tab leaves the field | none beyond `TEXTBOX` |
| List | Yes (one stop; entries are reached by arrows) | Up and Down move the chosen entry; Home and End; Enter or Space chooses; type-ahead jumps to an entry | `selected` on the entry |
| Menu, MenuItem | Yes (the opened Menu) | Up and Down move; Enter or Space runs the item; Right opens a submenu and Left or Escape closes the innermost level; Escape on the root closes the menu and returns focus to its opener | `expanded` on an item with a submenu |
| Expander | The controlling Button | Enter and Space on that Button toggle it | `expanded` on the Button |
| Tooltip | No | None; it never takes focus | none |

A disabled widget takes no focus and no key. A widget's key handling does not reach the shell's own keys: in shortcut mode the mode's keys win ([Focus and Keyboard > Shortcut Mode (the maintainer's design, 2026-11-10)](../40%20Specifications/Integration/Focus%20and%20Keyboard.md#shortcut-mode-the-maintainers-design-2026-11-10)).

## As Built in M4 and Decided 2026-11-13

All as recommended by the maintainer on 2026-11-13, from the code session's M4 report (not run in the vault):

- Disabled block: the block and all its descendants take no hover, press or click; a click is swallowed at the block; `pointer_down` and `pointer_up` still bubble, so a press on a disabled block still dismisses a Popup; no tooltip opens over it, with one exception (next item); re-enabling under the pointer restores hover at the next pointer event ([M4 Brief](../00%20Home/M4%20Brief.md) question 13).
- A block may opt in to a tooltip while disabled with the key `Tooltip_When_Disabled` (the code session's name; kept by the maintainer, 2026-11-13). Without the key no disabled block opens a tooltip, except the automatic exception in the next item. The key is the "unless the block says so" of [M4 Brief](../00%20Home/M4%20Brief.md) question 13.
- A disabled Marquee text that is cut with an ellipsis still shows the whole text in its tooltip: the automatic whole-text tooltip of cut text is the one exception to "no tooltip over a disabled block". On KWin no tooltip showed there, so the code session fixes it ([M4 Brief](../00%20Home/M4%20Brief.md) question 24).
- `Enabled` on a use of a module applies to the module's root block and so to its subtree; a module author writes nothing. A module call takes the common block keys and forwards them to its root ([M4 Brief](../00%20Home/M4%20Brief.md) question 16).
- A surface that holds a text field takes the keyboard `ON_DEMAND` automatically, overriding an explicit `Keyboard: NONE`, with one warning at load naming the surface and the field ([M4 Brief](../00%20Home/M4%20Brief.md) question 17).
- Image decoding is synchronous for M4; the off-thread path is built when a measured decode of a typical icon or photo exceeds 8 ms, and the measurement is recorded in [M4 Build Log](../00%20Home/M4%20Build%20Log.md) ([M4 Brief](../00%20Home/M4%20Brief.md) question 18). Measured by the code session on 2026-11-13: icons and thumbnails up to 512 px under 5 ms; a 1080p JPEG about 10 ms; a 1080p PNG about 18 ms; the shipped icons are SVG and are never decoded. A 1080p photo is not typical on a Bar, so the code session put off-thread decoding on the M5/M6 list, which the maintainer approved (2026-11-13).
- `Part: name` and the part selectors, and the first-child rule keys: [Style Schema > Parts and Module Rules (Decided 2026-11-13)](../41%20TDL%20Reference/Style%20Schema.md#parts-and-module-rules-decided-2026-11-13).

## Open Questions

1. [x] The keys above are the M4 default; adjust after the first look at the gallery (maintainer, 2026-11-10, as recommended).
2. [x] Not a question (maintainer, 2026-11-10): `PROGRESSBAR` as a role is a fact to check, not a decision. It stays tagged `#needs-verification` on the ProgressBar section, and the code session reads tre's role list when it builds it.
3. [x] Image: the size limit (4096 by 4096), the cache key and the error image as written (maintainer, 2026-11-10, as recommended).
4. [x] Marquee defaults (30 px a second, a 1500 ms pause), tuned on KWin (maintainer, 2026-11-10, as recommended).
5. [x] List `Selection: MULTIPLE` is not in v1 (maintainer, 2026-11-10, as recommended).
6. [x] A string shorthand for `Tooltip` (maintainer, 2026-11-10, as recommended).
7. [x] `Read_Only` and `Max_Length` on TextInput and TextEditor, `Password` on TextInput only (maintainer, 2026-11-10, as recommended).
8. [x] Pillow: decoding in `tess_utils`; the shell lists Pillow in its own `pyproject.toml` (maintainer, 2026-11-10, as recommended).

## Acceptance Criteria

- [ ] Every module of this note exists in the gallery of [M4 Brief](../00%20Home/M4%20Brief.md) in each of its states, and the maintainer has looked at each on KWin.
- [ ] Every module sets its role, name and state as [Accessibility](../60%20Quality/Accessibility.md) says.
- [ ] No module draws a frame at idle.
- [ ] Reduced motion switches Toggle, Expander, Marquee text and ProgressBar at once.
- [ ] `Enabled: false` gives every interactive module the `Disabled` state and no pointer input.

## Links

- [V1 Widgets](V1%20Widgets.md) · [Building Blocks](Building%20Blocks.md) · [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) · [Style Schema](../41%20TDL%20Reference/Style%20Schema.md) · [Events and Actions](../42%20Python%20API/Events%20and%20Actions.md) · [Popup](../40%20Specifications/Surfaces/Popup.md) · [Accessibility](../60%20Quality/Accessibility.md) · [M4 Brief](../00%20Home/M4%20Brief.md) · [M6 Brief](../00%20Home/M6%20Brief.md) · [50 Design System](50%20Design%20System.md)
