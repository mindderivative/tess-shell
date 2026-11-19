---
title: TRE-REQ-018 Tab Leaves a Multi-Line Text Input
aliases: [TRE-REQ-018, TextEditor Tab, tab_navigates, multiline text_input Tab]
type: engine-request
status: accepted
owner: phil
created: 2026-11-15
updated: 2026-11-17
tags: [engine-request, design/widgets, needs-verification]
---

# TRE-REQ-018: Tab Leaves a Multi-Line Text Input

> [!NOTE]
> A focused multi-line `text_input` takes Tab as a tab character, and nothing lets Tab move focus out of it. A keyboard user is held in the field. The request: a way for the shell to make Tab and Shift+Tab move focus from a multi-line input, as they do from a single-line one. Drafted on 2026-11-15 at the maintainer's request (confirmed in chat), from the facts of the code session's work on widget keys (T-048, `tess-shell` `main` `b2812d3`); the maintainer carries it to tre.

## Built by tre 0.6.8 (tre's migration notes, 2026-11-15)

`tesserae-engine` 0.6.8 is on PyPI (read from PyPI's JSON page on 2026-11-15) and its migration notes (`docs/migrating-0.6.md` in the tre repository, read by the vault session) say: a new property `tab_navigates` on a multiline `text_input` makes Tab and Shift+Tab move focus out of the input instead of typing a tab character, as from a single-line input. It is off by default, so every existing multiline input behaves as before (tre's task T-018). The shell sets it on every multi-line `TextEditor` (`tess-shell` PR #16, by the code session's report, whose strict expected-failure test now passes). The property was chosen from the two options the request offered. The vault has not run tre or the shell. This note stays `accepted` until the maintainer has tested it and confirms it; then it becomes `stable`. `tess-re` confirms (2026-11-17) that it first reproduced the gap on 0.6.7 (a multi-line input typed the tab and kept focus, a single-line input let Tab leave) and built `tab_navigates` as option 1: default `False`, settable and readable while the input lives, a single-line input is unchanged, and any other node kind raises `ValueError`.

## Shell Need

The shell's key table says Tab leaves a `TextEditor` like every other widget ([Standard Modules > TextEditor](../50%20Design%20System/Standard%20Modules.md#texteditor), [Focus and Keyboard > Tab Order: `Tab_Index`](../40%20Specifications/Integration/Focus%20and%20Keyboard.md#tab-order-tab_index)). A field that keeps Tab is a focus trap: Escape is the only way out, and a user who works by keyboard alone cannot reach what comes after the field ([Accessibility](../60%20Quality/Accessibility.md)). The shell builds every `TextEditor` itself, so it can set a property on each one.

## What Tre Does Today

| Fact | Source |
|---|---|
| Tab and Shift+Tab move through focusable nodes in tree order, and `tab_index` changes the order | tre's guide, Events and Input, "Focus and the keyboard" (read in the tre repository, `docs/guide/events-and-input.md`, 2026-11-15) |
| A focused `text_input` handles its own editing keys; a text input or terminal "take every key" where Enter and Space are concerned. The page does not say what Tab does in a text input | The same page, "Focus and the keyboard" and "Text input" |
| `multiline` is described as: Enter inserts a newline. No property concerns Tab | tre's guide, Text, the text input table |
| With `tesserae-engine` 0.6.7 on a headless `Window`: with a multi-line `text_input` focused, `Window.simulate` of the Tab key types a tab character into the text and focus stays in the field. A single-line input lets Tab leave. No property or event makes Tab move focus | The `tess-shell` code session's report (T-048). The vault has not run tre. #needs-verification |

## Proposed Change

tre implements one of these, at its choice:

1. A per-node property on a `text_input`, for example `tab_navigates` (default as today): when set, Tab on the focused input moves focus to the next focusable node and Shift+Tab to the previous one, and neither types anything.
2. Tab always leaves a text input, and a tab character is typed by Ctrl+Tab or only when a property asks for it.

The shell sets the property on every `TextEditor` it builds, or relies on the new default.

## Alternatives

None in the shell that is sound: catching Tab in a `key_down` handler on the input and moving focus from Python would have to undo the typed character and repeat tre's own focus order.

## If Declined

A `TextEditor` stays a place Tab cannot leave. The shell documents Escape as the way out and the accessibility criterion for a full keyboard path stays unmet for layouts with a `TextEditor`.

## Acceptance

With the property set (or under the new default), Tab on a focused multi-line input moves focus to the next focusable node and types nothing; Shift+Tab goes back. On the shell's side `tests/test_keys.py::test_texteditor_tab_leaves_the_field` is a strict expected failure today: it turns into a failure the day tre changes this, which is the signal to remove the marker and set the property.

## Links

[Focus and Keyboard](../40%20Specifications/Integration/Focus%20and%20Keyboard.md) · [Standard Modules](../50%20Design%20System/Standard%20Modules.md) · [Accessibility](../60%20Quality/Accessibility.md) · [80 Requests](80%20Requests.md)
