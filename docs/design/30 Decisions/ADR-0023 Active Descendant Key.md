---
title: ADR-0023 Active Descendant Key
aliases: [ADR-0023, Active Descendant Naming, TextInput Active_Descendant]
type: adr
status: accepted
owner: phil
created: 2026-11-21
updated: 2026-11-21
tags: [adr, a11y]
---

# ADR-0023: How a Layout Names the List a Text Field Follows

## Context

tre 0.6.10 sets `node.set(active_descendant=<node>)`: a focused text field names the selected row of a list for a screen reader and focus does not move ([TRE-REQ-023 Active Descendant](../80%20Requests/TRE-REQ-023%20Active%20Descendant.md)). The Launcher needs it ([Applications Module > Accessibility](../40%20Specifications/Modules/Applications%20Module.md#accessibility)); until it is released the selection is a polite announcement. The question is how a TDL layout asks the shell to set the relation. This ADR is written from `tess-shell`'s M7j proposal, relayed by the Orchestrator; nothing was built or run in the vault.

Existing convention: no spec names this relation. [Block Reference > Accessibility](../41%20TDL%20Reference/Block%20Reference.md#accessibility) has `Role`, `Label`, `Live` and `A11y_Hidden`, each named after tre's property; a key that points at another block by name is written like `Attach_To` (the name of the surface, [Shell File](../41%20TDL%20Reference/Shell%20File.md)). tre also has a separate `controls` relation (ARIA `aria-controls`), so `Controls` would name the wrong relation.

## Options

### Option A: an optional key on `TextInput` naming a List in the same layout (recommended)

The key is `Active_Descendant: <List name>`, named like tre's property and valued like `Attach_To`. The shell keeps the field's `active_descendant` on that List's selected entry, updates it when `Selected` or the entries change, and clears it when none. `check` errors if the name is not a List of the same layout (with the nearest names). Two fields may name one List. Schema 1.15.

- Pro: declarative; any module author gets it, not only the Launcher; checkable.
- Con: a schema key and a validation rule. The name is the one the tess-shell proposal changes from `Controls`.

### Option B: a module call `ctx.surface.set_active_descendant(field_name, row_name)`

- Pro: no schema change.
- Con: only Python modules get it; a layout author cannot; more code in each module and a contract addition.

### Option C: hard-wired for the Launcher

- Pro: smallest.
- Con: a combobox or any other text field with a list gets nothing; an exception to remember.

## Decision

Option A, accepted by the maintainer on 2026-11-21 (relayed by the Orchestrator, item 18): the optional `TextInput` key `Active_Descendant: <List name>`. The polite announcement stays as the fallback.

## Consequences

A: [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) gains the key; the schema export moves to 1.15; the Launcher layout names its List; `check` gains an error. B: a module-contract addition. C: none beyond the Launcher.

## As Built (`tess-shell` PR #117, code session's report, 2026-11-21; not run in the vault)

- `TextInput` module param `Active_Descendant` (string, default empty) maps to a `TextField` block key `Active_Descendant`; the Launcher layout writes `Active_Descendant: results`.
- The List is resolved by name among the sibling calls of the same layout; a missing or non-List name is a bind error with the nearest names. The field's active descendant follows the chosen entry and is cleared when none is chosen.
- Limit: only within one static layout; a List and field inside a `For` body are not linked.
- The polite announcement stays. Schema 1.15.
- `ctx.announce` goes through one window: the Frame painter, else the first Bar, else any open surface.
- Not tested live: the accessibility tree on sway, and Orca.

## Links

[TRE-REQ-023 Active Descendant](../80%20Requests/TRE-REQ-023%20Active%20Descendant.md) · [Accessibility](../60%20Quality/Accessibility.md) · [Applications Module](../40%20Specifications/Modules/Applications%20Module.md) · [Block Reference](../41%20TDL%20Reference/Block%20Reference.md) · [M7 Brief](../00%20Home/M7%20Brief.md)
