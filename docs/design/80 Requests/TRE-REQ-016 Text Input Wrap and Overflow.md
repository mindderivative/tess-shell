---
title: TRE-REQ-016 Text Input Wrap and Overflow
aliases: [TRE-REQ-016, text_input wrap, text_input overflow]
type: engine-request
status: stable
owner: phil
created: 2026-11-08
updated: 2026-11-11
tags: [engine-request, design/widgets, needs-verification]
---

# TRE-REQ-016: Text Input Wrap and Overflow

> [!NOTE]
> Let tre's `text_input` node choose how a long line is shown: a `wrap` (word wrapping or none) and, for a single-line input, an `overflow` (scroll, ellipsis or clip). Found by the code session's W0 inventory for [M4 Brief](../00%20Home/M4%20Brief.md) on 2026-11-08. The maintainer decided the behaviour the shell needs, chose to send this request to tre and to build the single-line workaround meanwhile, and on 2026-11-10 reported that he carried it to tre for work to begin. Not filed from this vault (AGENTS section 6).

## Shell Need

The maintainer decided on 2026-11-08 ([Standard Modules > TextInput](../50%20Design%20System/Standard%20Modules.md#textinput), [Standard Modules > TextEditor](../50%20Design%20System/Standard%20Modules.md#texteditor)): a single-line text field scrolls horizontally or shows an ellipsis (a wrapped single line "makes no sense"), and a multi-line field wraps by word or does not wrap. `Wrap` means word wrapping now; character wrapping comes later.

## What Tre Does Today (code session, tre 0.6.5, headless probe; not checked in the vault)

| Fact | Detail |
|---|---|
| `text_input` has `placeholder`, `multiline`, `selection`, `obscured`, `read_only`, `max_length`, `caret_*`, `input_mode` and the events `input`, `change`, `submit`, `compose_*`, `caret_move` | The probe's list |
| `wrap` and `overflow` are refused on a `text_input` | The error: "node property `wrap` applies only to a text node" |
| A default (single-line) `text_input` wraps by word onto several lines and grows | 60 characters in a 100 px field gave 5 lines; render `/tmp/m4_textinput_probe3.png` |
| `multiline=True` does not wrap: one clipped line | The inverse of what the maintainer's decision assumes |

So neither a single-line scroll or ellipsis nor a multi-line word wrap or no-wrap can be chosen by a property today.

### What Tesserae UI does (read by the vault session in the local clone, 2026-11-08)

The maintainer remembered that Tesserae UI built its own wrapping and scrolling for input. The clone at `~/Projects/pyDev/projects/tesserae` (the `tess_ui` package) shows no such thing:

- Its `TextField` is "a single-line text input in a box" (`docs/yaml.md`) over tre's `text_input`; `wrap` and `overflow` are documented "Not for a TextField" in its YAML and widget schemas.
- `TextInput` and `TextField` take `placeholder`, `multiline`, `obscured`, `max_length`, `read_only`, `mask` and the `typing_effect` and `caret_effect` drawn from tre's `caret_move` and `text_rects` (`composed.py`, `docs/changelog.md`). Nothing sets a wrap, a horizontal scroll or an ellipsis on the input.
- It does enforce `max_length` and `read_only` itself, with a `change` listener that puts the text right ("which the engine's input does not have", `composed.py` `_enforce_input`). That comment disagrees with the code session's probe, which found `read_only` and `max_length` accepted by tre 0.6.5; the clone may predate tre's support, so the two readings differ and neither was run by the vault. #needs-verification

So Tesserae UI is no precedent for a shell-side wrap or scroll, though its use of `caret_move` and `text_rects` is the route the single-line workaround below would take. Another place the maintainer remembers it (a different branch, or the earlier Fabric shell in `myShell`) was not searched.

### Could this be a tess-utils helper? (the maintainer's suggestion, 2026-11-08)

[ADR-0017 Shared Utilities](../30%20Decisions/ADR-0017%20Shared%20Utilities.md) lets a function into `tess_utils` when at least two Tesserae projects use it, it needs no `tess_re` import and has no UI meaning. Against the single-line scroll that fits in part: a pure function that takes the caret position from tre's `caret_move`, the field's width and the current offset and returns the new scroll offset has no tre import. It fails the two-users rule today: Tesserae UI sets no scroll on its input (read above), so only the shell would use it. Recommendation: write it as a pure function in the shell's `binder` or widget code, in the form that can move, and move it to `tess_utils` when Tesserae UI adopts it, as ADR-0017 Option B describes. It does not help the multi-line word wrap: tre draws the text of a `text_input` itself, so no helper outside tre can change how it wraps, and that part still needs this request. The `tess-utils` repository directory at `~/Projects/pyDev/projects/tess-utils` was empty when checked, so the package is not built yet (the vault does not know whether the shell vendors a copy).

## Proposed Change

- `wrap` on a `text_input`: `"word"` or `"none"`, with the same meaning as on a text node. For a multi-line input the default is `"word"`; `"none"` scrolls horizontally.
- `overflow` on a single-line `text_input`: `"scroll"` (keeps the caret in view), `"ellipsis"` (while not edited) or `"clip"`.
- A single-line input never wraps, whatever `wrap` says, and does not grow in height.
- Later: `"char"` for `wrap` (the maintainer wants character wrapping added later).

## Alternatives

| Option | Effect |
|---|---|
| A shell-side workaround for a single line: a fixed height and a scroll managed through `selection` and the `caret_move` event | Gives the single-line scroll; costs shell code and may flicker; an ellipsis at rest would be a second node over the input |
| A shell-side workaround for multi-line word wrap | None: the code session found no shell-side route |
| Change the decision: a multi-line field that does not wrap, and a single-line field that grows | Needs the maintainer's say; contradicts 2026-11-08 |

## If Declined, and Meanwhile

The single-line field uses the workaround (fixed height, shell-managed scroll, an ellipsis at rest) from the start, whatever tre answers; it is replaced by the property when tre ships it (maintainer, 2026-11-08). The multi-line field cannot wrap by word until tre supports it, so TextEditor ships without word wrap and [Standard Modules > TextEditor](../50%20Design%20System/Standard%20Modules.md#texteditor) says so.

## Acceptance

A `text_input` with 60 characters in a 100 px field: with `wrap="word"` and `multiline=True` it shows several lines; with `wrap="none"` it scrolls horizontally; a single-line input with `overflow="scroll"` keeps the caret visible and stays one line high; `overflow="ellipsis"` shows an ellipsis when it is not edited. The defaults for an unset property are unchanged from tre 0.6.5.

## Links

[Standard Modules](../50%20Design%20System/Standard%20Modules.md) · [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) · [M4 Brief](../00%20Home/M4%20Brief.md) · [V1 Widgets](../50%20Design%20System/V1%20Widgets.md) · [80 Requests](80%20Requests.md)
