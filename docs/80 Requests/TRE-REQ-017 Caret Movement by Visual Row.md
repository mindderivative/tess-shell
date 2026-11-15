---
title: TRE-REQ-017 Caret Movement by Visual Row
aliases: [TRE-REQ-017, caret up down wrapped rows, text_input visual rows, text_input editing keys]
type: engine-request
status: accepted
owner: phil
created: 2026-11-11
updated: 2026-11-13
tags: [engine-request, design/widgets, needs-verification]
---

# TRE-REQ-017: Caret Movement by Visual Row, and the Normal Editing Keys

> [!NOTE]
> In a multi-line `text_input` that wraps long lines, the caret keys should work on the rows the user sees: Up and Down move one wrapped row, Home and End go to the start and end of the row, Page Up and Page Down move by a screenful of rows. Today they move by logical line, so in a long paragraph that wraps over five rows one press jumps over all of them. While tre is in there, the maintainer asked that the normal editing keys be complete: Backspace and Delete remove the character before and after the caret, Insert toggles between insert and overwrite mode (a bar caret and a block caret), and double-click and triple-click select a word and a space-separated string. Found by the code session while building TextEditor on tre 0.6.6 ([M4 Build Log](../00%20Home/M4%20Build%20Log.md), "tre's known limit"); scope set by the maintainer on 2026-11-11. The maintainer reviewed and accepted it on 2026-11-11 and is passing it to tre himself; it is not filed from this vault (AGENTS section 6).

## Built by tre 0.6.7 (tre's report, 2026-11-11)

The maintainer confirmed on 2026-11-13 that tre 0.6.7 is released and on PyPI. tre reports that `tesserae-engine` 0.6.7 is on PyPI with this request built (tag `v0.6.7`, #288, clean-venv install checked on Linux, headless). The vault read tre's migration page for 0.6.7 ([Upgrading to 0.6.x](https://mindderivative.github.io/tess-re/migrating-0.6/)), which says the same; it has not run 0.6.7. A real compositor and an input method are not checked, and they are the maintainer's to test ([Open Questions](#open-questions) is empty).

| Asked for | Built, with the differences from the request |
|---|---|
| Up, Down, Home, End, Page Up, Page Down by visual row, goal column, Shift to select | Yes, for a multi-line input with a `wrap` set (`"word"` or `"none"`). Up on the first row goes to the start of the text and Down on the last row to its end. End stops before the spaces a wrap fell on, because a caret has no affinity. With no `wrap` set a multi-line input keeps its 0.6.6 keys, by logical line, so the shell must set `wrap` on every TextEditor. A single-line input has one row |
| Shift with those keys, shrink and cross the anchor | Yes: the selection grows from its fixed end, shrinks when the direction reverses and selects on the other side past the anchor |
| Ctrl+Left and Ctrl+Right by word, Ctrl+Backspace and Ctrl+Delete by word | Yes, in every text input. tre's word for these is letters, digits and underscore, then a run of punctuation, then the spaces after it; this differs from the double-click word below. Shift does not change the deletes |
| Ctrl+Home and Ctrl+End, Shift with them | Yes: the start and end of the whole text; Ctrl+Shift+Home and End select to there. Plain Shift+Home and Shift+End select to the start or end of the visual row (the whole text in a single-line input) |
| Backspace and Delete at row edges | Yes: they remove one character or the selection; at a row start or a line break they remove the wrap space or join the lines; at the very start or end of the text they do nothing |
| Insert toggles overwrite | Yes: `node.get("overwrite")`, `node.set(overwrite=True)` and the event `overwrite_change` (`old_value`, `new_value`), fired by the key and not by `set()`. Off by default. A typed, space or IME-committed character replaces the one after the caret and the caret moves on; at the end of the text or before a line break it is added; typing over a selection replaces only the selection; a paste is always inserted; `max_length` lets a replacement through. Shift+Insert and Ctrl+Insert are untouched |
| Block caret in overwrite | Yes, automatically: the default bar caret is drawn as a block while overwrite is on, and a `caret_shape` of `"block"` or `"underline"` stays as set, so the shell need not switch the shape |
| Double-click and triple-click | Yes: double-click selects the word under the pointer (letters, digits and underscore, Unicode included; on a space or punctuation it selects that run); triple-click selects the string up to the spaces, special characters included. Both stop at the edge of the visual row and neither starts a drag; click, hold and drag is unchanged |

Not built: `wrap="char"` (character wrapping, still to come).

Behaviour changes in every text input, which the shell's code and tests must allow for: Ctrl+Left, Ctrl+Right, Ctrl+Backspace and Ctrl+Delete used to act on one character; Ctrl+Home and Ctrl+End in a multi-line input used to go to the line start or end; two quick clicks on an input now select a word, so a headless test that clicks one input twice needs `window.advance(1000)` between the clicks. tre's 0.6.6 known limit, arrow keys by logical line in a wrapped input, is gone.

This note stays `accepted` until the maintainer has tested it on KWin, with an input method, and confirms it; then it becomes `stable`.

## Shell Need

[Standard Modules > TextEditor](../50%20Design%20System/Standard%20Modules.md#texteditor) is a multi-line field with `Wrap: WORD`, which [TRE-REQ-016 Text Input Wrap and Overflow](TRE-REQ-016%20Text%20Input%20Wrap%20and%20Overflow.md) made possible in tre 0.6.6. With word wrap on, a paragraph is shown as several rows, but the caret keys treat the paragraph as one line. A user who wants to move to the row above must use the pointer or the Left key. A keyboard-only user ([Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md), [Accessibility](../60%20Quality/Accessibility.md)) has no efficient way to move through a wrapped paragraph. The maintainer wants the whole set of normal editor behaviour, with no reason to leave part of it out.

## What Tre Does Today

Read by the vault session on 2026-11-11 from tre's own documentation ([Text](https://mindderivative.github.io/tess-re/guide/text/), [Events and Input](https://mindderivative.github.io/tess-re/guide/events-and-input/), tre 0.6.6); the code session's report is marked as such. The vault has not run tre.

| Fact | Source |
|---|---|
| A focused `text_input` handles typing, the arrow keys, Home and End (with Shift to select), Backspace, Delete, Enter in a multi-line input, and Ctrl+C, Ctrl+X, Ctrl+V and Ctrl+A | Events and Input, "Text input" |
| Page Up and Page Down are left alone by a text input, to scroll the view around it | Events and Input, "Text input" |
| In a wrapped multi-line input the arrow keys, Home and End move by logical line (between newlines), not by wrapped line; clicking, typing and the caret itself follow the wrapped text | Text, "Long lines in a text input (0.6.6)"; same in the code session's report ([M4 Build Log](../00%20Home/M4%20Build%20Log.md)) |
| `caret_shape` is `"bar"`, `"block"` or `"underline"`, with `caret_width`, `caret_color`, `caret_blink` and `caret_visible` (0.5.6) | Text, the text input table |
| `caret_rect()` and `text_rects()` read the geometry; `selection_start` and `selection_end` give the ends in order; the `caret_move` event exists | Text; [TRE-REQ-016 Text Input Wrap and Overflow > What Tesserae UI does (read by the vault session in the local clone, 2026-11-08)](TRE-REQ-016%20Text%20Input%20Wrap%20and%20Overflow.md#what-tesserae-ui-does-read-by-the-vault-session-in-the-local-clone-2026-11-08) |
| An insert and overwrite mode (the Insert key) is not mentioned | Neither page |
| Static selectable text (a `text` node with `selectable=True`) already has: double-click selects a word, triple-click a line, Ctrl+Shift+Left and Right by word (a run of letters and digits, a run of punctuation, then the spaces after it), Shift+Up and Shift+Down by line keeping the column, Shift+Home and Shift+End | Text, "Rich text and selectable text" |
| Shift+Left and Shift+Right select a character at a time, and Shift+Up and Shift+Down select by logical line, in a text input | The maintainer, 2026-11-11 (his statement; the vault did not run it) |
| Whether a `text_input` has double-click, triple-click, Ctrl+Left and Ctrl+Right by word, Ctrl+Backspace, Ctrl+Delete or Ctrl+Home and Ctrl+End | Not documented for a text input. #needs-verification |

So the caret keys the maintainer asked for mostly exist, by logical line; what is missing, as far as the documentation and the maintainer say, is the row-aware movement (including Shift+Up and Shift+Down by row), Page Up and Page Down, the overwrite mode, and possibly the pointer and word selection in a text input.

## Proposed Change

All of it applies to a `text_input` and follows the rows the user sees. With `wrap="none"` a row is a logical line and nothing changes; a single-line input has one row.

### Moving the caret

- Up moves the caret to the row above and Down to the row below, to the character nearest the column where the caret was. The column is remembered across consecutive Up and Down presses, so moving through a short row does not lose it (the goal column of an editor).
- Up on the first row moves the caret to the start of the text; Down on the last row moves it to the end (maintainer, 2026-11-11).
- Home moves the caret to the start of the visual row and End to its end, not to the start and end of the logical line (maintainer, 2026-11-11). Ctrl+Home and Ctrl+End keep the usual meaning, the start and the end of the whole text.
- Page Up and Page Down move the caret by as many rows as the field shows, keeping the goal column, and scroll the field with it (maintainer, 2026-11-11).
- Shift+Left and Shift+Right extend the selection by one character at a time as the caret moves, and against the direction of the selection they shrink it, one character at a time, as in a normal editor (maintainer, 2026-11-11). tre supports this (maintainer, 2026-11-11); the request asks tre only to keep it working with the changes below.
- Shift+Up and Shift+Down select every character from the selection's fixed end (the anchor) to where the caret lands on the row above or below, with deselection when the direction reverses and a selection that crosses the anchor selecting on the other side (maintainer, 2026-11-11). tre supports them by logical line (maintainer, 2026-11-11); the request asks for them by visual row, with the same goal-column rule as Up and Down.
- Shift with Home, End, Page Up and Page Down, and with Ctrl+Left, Ctrl+Right, Ctrl+Home and Ctrl+End, extends the selection to where the caret lands, with the same anchor rule.

### Deleting

- Backspace removes the character before the caret and Delete removes the character after it (maintainer, 2026-11-11). tre documents both for a text input; the request asks tre to confirm that with a selection either removes the selection.
- At the edge of a row the same rule holds (maintainer, 2026-11-11): Backspace at the beginning of a row removes the character, space, newline or carriage return before it, which is the last character of the row above; Delete at the end of a row removes the character, space, newline or carriage return after it, which is the first character of the row below. At a wrap this removes the space or character the wrap fell on, and at a logical line break it removes the line break and joins the two lines. Backspace at the beginning of the first row and Delete at the end of the last row of the whole field do nothing (maintainer, 2026-11-11).

### Insert and overwrite

- The Insert key toggles the mode (maintainer, 2026-11-11, as he understands the normal behaviour). Insert on: typed characters are added at the caret. Insert off (overwrite): each typed character replaces the character after the caret, and the caret moves to the start of the next character, as in insert mode. Overwrite is off by default, so typing inserts until Insert is pressed (maintainer, 2026-11-11, [Open Questions](#open-questions) question 6).
- Typing over a selection replaces the selection in both modes. At the end of the text, and in front of a line break, an overwrite typed character is added and does not consume the line break.
- The mode is a property of the `text_input` that the shell can read and set, and a change raises an event (maintainer, 2026-11-11: yes). tre already has `caret_shape`, so the shell sets `"block"` while overwrite is on and `"bar"` while it is off from that event; tre needs to draw nothing new. If tre prefers to switch the shape itself, with an explicit `caret_shape` winning, the shell accepts that.
- The caret is a bar in insert mode and a block in overwrite mode (maintainer, 2026-11-11).
- A composed character from an input method follows the same rule as a typed character.

### Selecting with the pointer

The rules, as the maintainer gave them on 2026-11-11:

| Click | Selects | The string ends at |
|---|---|---|
| Double-click | The string of characters under the pointer | A special character, a space, a line break (newline or carriage return), the beginning of the line or the end of the line |
| Triple-click | The string of characters under the pointer, special characters included | A space, a line break (newline or carriage return), the beginning of the line or the end of the line |
| Click, hold and drag | The characters from the press to the pointer | Already works in tre and must stay as it is (maintainer, 2026-11-11) |

So in `well-known` a double-click on `well` selects `well`, and a triple-click selects `well-known`; neither selects the whole row. "Line" means the visual row, not the logical line (maintainer, 2026-11-11), the same row the caret keys use above; at a wrap, the row's edge ends the string. A special character is any character that is not a letter, a digit or the underscore, Unicode letters and digits included ([Open Questions](#open-questions) question 7). For comparison, tre's own word for Ctrl+Shift+Left and Right in static text is a run of letters and digits, then a run of punctuation, then the spaces after it, and its triple-click in static text selects a line; a text input needs the rules above.

- The request changes nothing about a plain click, hold and drag. It does not ask for a drag that follows a double-click or a triple-click to extend by words or strings; if tre already does something there, it stays as it is.

## Alternatives (Not Accepted Unless tre Shows It Cannot Be Built)

> [!IMPORTANT]
> **The maintainer's position (2026-11-11)**
> tre implements this request. An alternative is taken only if tre gives a really good reason that this cannot be done, and the reason must be technical: something that cannot be built in Rust at all. Effort, size, scope, a preference for the shell to do it, or "it belongs in a framework" are not reasons. If tre declines, it names the technical limit, and the maintainer decides.

The alternatives below are listed only so a declined item has a named fallback; none of them is chosen.

| Option | Effect |
|---|---|
| A shell-side workaround for row movement: on Up or Down the shell reads `text_rects`, finds the row and column, and sets `selection` | Possible in principle with the properties named above; it must stop tre's own handling of the key, keep a goal column, and handle selection, scrolling and IME. More shell code and a likelier source of flicker; not tried |
| A shell-side overwrite mode: on a typed character the shell extends the selection by one and lets tre replace it | Possible in principle with `selection` and `input`; it collides with `max_length` and with input methods. The block caret itself is already available through `caret_shape` |
| Leave the behaviour as it is and document it | Not accepted: the maintainer's own report calls it a gap; a keyboard-only user is left without row movement |
| Disable word wrap in TextEditor | Contradicts the maintainer's decision of 2026-11-08 |

## If tre Declines an Item

tre states the technical reason, item by item, in writing to the maintainer. Until he decides, the TextEditor ships with the movement tre has today, as built, and [Standard Modules > TextEditor](../50%20Design%20System/Standard%20Modules.md#texteditor) says so. A shell-side workaround is built only if the maintainer asks for it, one item at a time.

## Acceptance

A multi-line `text_input` with `wrap="word"` and one paragraph that wraps over three rows, in a field 100 px wide:

| Step | Expected |
|---|---|
| Caret in the middle of row 2, press Down | The caret is on row 3 at the nearest column |
| Press Up twice | The caret is on row 1 at the column it started from; moving across a short row returns to the original column |
| Press Home, then End | The caret goes to the start, then to the end, of the visual row |
| Press Up on row 1, then Down on the last row | The caret goes to the start of the text, then to its end |
| Press Page Down in a field taller than its rows | The caret moves by the number of rows shown and the view follows |
| Press Shift+Right three times, then Shift+Left once | Three characters are selected, then two |
| Press Shift+Down from the middle of row 1 | Every character from the start point to where the caret lands on row 2 is selected |
| Press Shift+Down again, then Shift+Up twice | The selection grows to row 3, shrinks back to row 2, then to row 1, and stops at the anchor; one more Shift+Up selects on the other side of it |
| Press Backspace, then Delete in the middle of a word | One character before the caret goes, then one character after it |
| Press Insert, type three characters over four existing ones | Three characters are replaced and the caret is in front of the fourth; the caret is a block while overwrite is on and a bar after Insert is pressed again; the next typed character is then added |
| Double-click on `well` in `well-known` | `well` is selected, not `well-known` |
| Triple-click on `well` in `well-known` | The whole string `well-known` is selected, up to the spaces around it; not the whole row |
| Triple-click on a string at the start or end of a visual row | The selection stops at the row's edge |
| With `wrap="none"` and in a single-line input | Behaviour is unchanged from tre 0.6.6, except that Insert, Delete and Backspace work as above |

## Open Questions

1. [x] Should Home and End also move to the start and end of the visual row? Yes (maintainer, 2026-11-11); asked for in this request.
2. [x] Should Up on the first row move the caret to the start of the text, and Down on the last row to the end? Yes (maintainer, 2026-11-11).
3. [x] Should Page Up and Page Down be in this request? Yes; the maintainer wants all of the normal behaviour now, including Backspace, Delete and Insert (2026-11-11).
4. [x] Should the overwrite mode be a property of the `text_input` that the shell can read and set, with a change event, and should tre draw the caret differently while it is on? Yes (maintainer, 2026-11-11): the caret is a bar in insert mode and a block in overwrite mode.
5. [x] Should this request also ask for Ctrl+Left and Ctrl+Right by word, Ctrl+Backspace and Ctrl+Delete by word, and Ctrl+Home and Ctrl+End? Yes (maintainer, 2026-11-11), and also double-click to select a word and triple-click to select a space-separated string, above.
6. [x] Is overwrite mode off by default, so typing inserts until Insert is pressed? Yes (maintainer, 2026-11-11); he had already said so in his first directions ("Default is off").
7. [x] Which characters count as "special" and separate words for the double-click? A word is letters, digits and the underscore (Unicode letters and digits included); every other character separates words, so `well-known`, `a.b` and `foo(bar)` split at `-`, `.` and the brackets (maintainer, 2026-11-11, as recommended).

## Links

[TRE-REQ-016 Text Input Wrap and Overflow](TRE-REQ-016%20Text%20Input%20Wrap%20and%20Overflow.md) · [Standard Modules](../50%20Design%20System/Standard%20Modules.md) · [M4 Build Log](../00%20Home/M4%20Build%20Log.md) · [Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md) · [Accessibility](../60%20Quality/Accessibility.md) · [80 Requests](80%20Requests.md)
