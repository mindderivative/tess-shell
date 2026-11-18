---
title: TRE-REQ-021 Announce Without a Node
aliases: [TRE-REQ-021, Window.announce, screen reader announcement]
type: engine-request
status: accepted
owner: phil
created: 2026-11-16
updated: 2026-11-17
tags: [engine-request, quality/accessibility, needs-verification]
---

# TRE-REQ-021: Announce Text to a Screen Reader Without a Node

> [!NOTE]
> tre 0.6.8 can announce only through a live node: a node announces when its name changes or when it enters the tree. The shell therefore announces through a 1x1 absolute Box per module. The request: `Window.announce(text, politeness)` (and the same on `LayerWindow` and `PopupWindow`) that raises one live announcement for that window through AccessKit, with no node. Drafted on 2026-11-16 from the code session's report, at the maintainer's request; the maintainer carries it to tre.

## Built by tre 0.6.9 (tre's report, 2026-11-17)

The `tess-re` session reports `Window.announce(text, politeness='polite')` in 0.6.9, with politeness `polite` or `assertive`, also on `LayerWindow` and `PopupWindow`. Each call is exactly one announcement and needs no node, so it works for a hidden module and a repeated identical message with no zero-width-space toggle; removing duplicates is the caller's job. An empty text or another politeness raises `ValueError`. AccessKit 0.25 has no announce call, so tre adds an internal live Group node under the window root for one accessibility update and removes it in the next; it is raised with the next frame the window draws, and nothing is heard unless a screen reader is connected. tre verified real AT-SPI `Announcement` signals on a private bus, including with a hidden module present. Not verified: Orca, NVDA, VoiceOver, KWin. The three candidates listed under "Not part of this request" were not built. `tess-shell` PR #56 (merged 2026-11-17, by the code session's report) moved every module to `ctx.announce`, which calls `Window.announce`, and tested the announcements through a real AT-SPI bus on a private sway. Not Orca. This note stays `accepted` until the maintainer has heard it with Orca and confirms it; then it becomes `stable`.

## Shell Need

[Accessibility](../60%20Quality/Accessibility.md) asks modules to announce state changes (a network connecting or dropping, a battery going critical, the launcher's selected row, a window opening or closing). Three cases a node cannot serve:

- A module that is hidden is out of the accessibility tree, so the Tasks module cannot announce that the last window closed or that the window list became unavailable.
- Two uses of one module on two Bars each hold a node and each announce, so a screen reader says the message twice.
- A repeated identical message does not change the node's name, so it is not announced again; the shell works around it with a zero-width-space toggle.

## What Tre Does Today

| Fact | Source |
|---|---|
| `live="polite"` or `"assertive"` makes a node a live region: a screen reader announces changes to it | tre's guide, Accessibility, "Announcing and hiding" (`docs/guide/accessibility.md`, read in the tre repository at `94e5e2ab`, 0.6.8, 2026-11-16) |
| The page does not mention an announce call; the guide says the support "has not been tried with NVDA, VoiceOver or Orca" | The same page |
| tre 0.6.8 has `role`, `label`, `description`, `value_text`, `states`, `a11y_hidden` and a `live` flag, but no announce call and no active-descendant; a live node announces only when its name changes or when it enters the tree (`accesskit_atspi_common` emits `object:announcement`) | The code session's report on `tess-shell` PR #37 |
| The shell announces through a 1x1 absolute `Box` (role `GROUP`, live `POLITE`) labelled with the module key `announcement`, not tried with a screen reader | The code session's report |

## Proposed Change

`Window.announce(text: str, politeness: 'polite' | 'assertive' = 'polite')`, and the same method on `LayerWindow` and `PopupWindow`: raises one live announcement through AccessKit for that window. It has no node, so it works for a hidden module and a repeated message. Removing duplicates is the caller's job.

## Alternatives

None that is better: the node workaround is what the shell already does, and it fails in the three cases above.

## If Declined

The shell keeps the node-per-module workaround, the Tasks module cannot announce the last window closing, and a repeated message needs the zero-width-space toggle.

## Acceptance

A test through the accessibility tree or the AT-SPI announcement event: `window.announce("Connected", "polite")` produces one announcement with that text and politeness; two calls with the same text produce two announcements; a call on a window whose modules are hidden still announces.

## Not part of this request

Candidates the code session listed and the vault does not file yet, until a need is shown: a content-sized (AUTO) layer surface for a Panel (the Launcher is a fixed 480x400, so a short result list leaves empty space); an active-descendant for a focused text field with a list (the Launcher announces the selection with polite messages instead); an outside-press or keyboard-leave signal for `EXCLUSIVE` surfaces (probably impossible by protocol).

## Links

[Accessibility](../60%20Quality/Accessibility.md) · [Tasks Module](../40%20Specifications/Modules/Tasks%20Module.md) · [Applications Module](../40%20Specifications/Modules/Applications%20Module.md) · [M5 Build Log](../00%20Home/M5%20Build%20Log.md) · [80 Requests](80%20Requests.md)
