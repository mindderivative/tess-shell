---
title: TRE-REQ-023 Active Descendant
aliases: [TRE-REQ-023, active_descendant, listbox active descendant, ActiveDescendantChanged]
type: engine-request
status: accepted
owner: phil
created: 2026-11-17
updated: 2026-11-17
tags: [engine-request, quality/accessibility, needs-verification]
---

# TRE-REQ-023: An Active Descendant Relation

> [!NOTE]
> A focused text field with a list under it (the Launcher's search field and its results, any combobox or autocomplete) should tell a screen reader which row is selected without moving keyboard focus out of the field. The request: a node property `active_descendant` that names one node, carried through tre's accessibility tree to AccessKit and, on Linux, to AT-SPI's `ActiveDescendantChanged`. Written on 2026-11-17 at the maintainer's request ("I want these built"); the maintainer's description of the cost is that it is small. The maintainer carries it to tre.

## Shell Need

In the Launcher the text field keeps the keyboard and Up and Down move a selection in the list below it ([Applications Module](../40%20Specifications/Modules/Applications%20Module.md)). A screen reader reads the field, not the row the user selected. Today the shell announces the selected row with a polite message ("Name, 2 of 8"), which works but is not the relation the platform expects and is spoken as a notification, not as the control's state ([Accessibility](../60%20Quality/Accessibility.md); built in `tess-shell` PR #37, by the code session's report). With `Window.announce` in tre 0.6.9 ([TRE-REQ-021 Announce Without a Node](TRE-REQ-021%20Announce%20Without%20a%20Node.md)) the workaround is easier, and still a workaround.

## What Tre Does Today

| Fact | Source |
|---|---|
| tre supports the relations `describedby` and `controls` (0.5.6): each takes the nodes that describe this one or that it controls | tre's guide, Accessibility (`docs/guide/accessibility.md`, tre 0.6.9, read 2026-11-17) |
| The guide and the API page list no `active_descendant` | The same page and `docs/api/python.md` |
| AccessKit has the relation (`active_descendant`) and AT-SPI emits `ActiveDescendantChanged` for it | The maintainer's description of 2026-11-17, from the `tess-re` session's assessment. #needs-verification: the vault has not read AccessKit or AT-SPI |

## Proposed Change

tre implements this: a node property `active_descendant`, a `Node` or `None`, readable and settable with `get` and `set` like `controls`, mapped to AccessKit's active-descendant of that node. When it changes, a screen reader hears the target's name and state as the active item of the focused node, and AT-SPI emits `ActiveDescendantChanged`. Notes:

- The target is a node in the same window, normally a descendant or a node the field `controls` (the list). It need not be focusable.
- The target being destroyed or hidden clears the property.
- It works with the target's `role` (`LIST_ITEM`, `OPTION`) and `selected` state as set today.
- Setting it does not move focus and does not fire `focus` or `unfocus`.

## Alternatives

None needed. The polite announcement stays as the fallback on platforms where the relation is not delivered.

## If Declined

The Launcher and any list with a text field keep announcing the selection with polite messages.

## Acceptance

Through the accessibility tree: with a text input focused and a list below it, `input.set(active_descendant=row2)` makes `get("active_descendant")` return `row2`, the accessibility tree reports it as the active descendant, and a real AT-SPI `ActiveDescendantChanged` signal arrives on a private bus, as tre already checks for announcements; changing it again sends one more; destroying `row2` clears it; focus stays in the field throughout.

## Links

[Accessibility](../60%20Quality/Accessibility.md) · [Applications Module](../40%20Specifications/Modules/Applications%20Module.md) · [TRE-REQ-021 Announce Without a Node](TRE-REQ-021%20Announce%20Without%20a%20Node.md) · [M7 Brief](../00%20Home/M7%20Brief.md) · [80 Requests](80%20Requests.md)
