---
title: M2 Brief
aliases: [M2, Live and Modular Brief, Shell M2]
type: moc
status: draft
owner: phil
created: 2026-11-03
updated: 2026-11-04
tags: [moc, roadmap, brief]
---

# M2 Brief

> [!NOTE]
> M2 is under way in `tess-shell` (maintainer, 2026-11-04) while the M1 KWin check (T11) waits. The scope of milestone M2, "live and modular": values that change on screen. A `{{ }}` slot in a file reads a value that a Python module sends, TEL re-evaluates only what changed, and the binder updates only the linked properties. The Clock is the first module; saving a file updates the running shell. It follows [M1 Brief](M1%20Brief.md) (a static Bar, in progress in `tess-shell`). This is a plan for the maintainer, written so the design is ready before M1 ends ([ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md)); M2 starts when M1 is done and the maintainer says so.

## Progress (Reported by `tess-shell`, 2026-11-04)

M2a and M2b are built (A1 to A7, B1 to B6; last commit `a27c950`; 663 tests pass, checked by the vault session on 2026-11-04). Details, measurements and decisions D19 to D31 are in [M2 Build Log](M2%20Build%20Log.md); the maintainer accepted D19 to D31 on 2026-11-04 and confirmed it to the vault session. The KWin checks of the Clock and of the reload cases are the maintainer's.

## Goal and Definition of Done

M2 is done when:

- A `Clock` module, called from the Bar's `Children`, shows the time and changes at the start of each minute (each second when the format has `%S`), driven by its Python through `ctx.send`.
- A `{{ }}` slot in `Text` reads that value; when the value changes only that node's property is set, through `Window.apply`.
- A module and its `Params` load from a `<Name>_Module.tdl` with its `<Name>_Module.py`, and a bad module (missing `.py`, no class, two classes, a `start()` that raises) fails with a message naming the files while the other modules keep running.
- `If`/`Else` and `For` work with TEL conditions and keyed lists.
- Saving a changed shell, module or style file updates the running shell within about 300 ms, once, and a file with an error leaves the shell unchanged and reports `file:line:column`.
- Idle between ticks costs no frames and no wake-ups ([Clock Module > Performance Budget](../40%20Specifications/Modules/Clock%20Module.md#performance-budget)).

Not in M2: `Panel`, `Popup`, `Frame`, services, shortcuts, events (`On_Click`), theme tokens, the other shipped modules.

## Proposed Split

M2 is large, so the plan has two halves, each with its own done point. Recommendation: build them in this order.

| Half | Content | Done when |
|---|---|---|
| M2a: live values | Module file and `Import`; module host; value store and `ctx.send`; TEL slots and tracked links; `view.update`; the Clock; the file UID write | The Clock ticks on the Bar and idles between ticks |
| M2b: structure and reload | `If`/`Else`, `For` with keyed entries; hot reload with the keyed diff; module style files; icon sets for `SVG` by name | Saving a file updates the shell in about 300 ms and a `For` list follows a module's list |

## Design Needed First

Most of what M2 needs is written but at `draft`. These are the gaps, each with a recommendation. Answers are asked under "Questions for the Maintainer".

| # | Gap | Where it is open | Recommendation |
|---|---|---|---|
| G1 | The TEL integration: how the shell builds the scope (the file's name tree, module values, `Params`), compiles templates and expressions with their `Origin`, evaluates on the loop thread, and turns tracked reads into links | Spread across [Expression Language Requirements](../40%20Specifications/Runtime/Expression%20Language%20Requirements.md), [Layers and Components](../20%20Architecture/Layers%20and%20Components.md) and [Render Binder Design](../20%20Architecture/Render%20Binder%20Design.md); no note of its own | Write one note, "TEL Integration" in `20 Architecture`, before M2a |
| G2 | The value store: keys, one writer (the loop), coalescing of repeated sends in one turn, what a link reads | [Layers and Components](../20%20Architecture/Layers%20and%20Components.md) names it; [Module Context](../42%20Python%20API/Module%20Context.md) lists coalescing | Fold into the TEL Integration note |
| G3 | The module contract: `self.ctx` set by the base class before `start()` (not a constructor argument); `reload()` takes no arguments (the module re-reads `ctx.config`); `from tess_shell import Module, action` | [Module Contract](../42%20Python%20API/Module%20Contract.md) open items | Accept as proposed in the note |
| G4 | The context API for M2: `ctx.send(key, value)` (one key), `ctx.config`, `ctx.log`, `ctx.uses`, `ctx.on_tick("second" or "minute")`; no `ctx.every` or `ctx.after` yet | [Module Context](../42%20Python%20API/Module%20Context.md) open items | Build only what the Clock needs; add the rest when a module needs it |
| G5 | Value types: strings, numbers, booleans, lists and dicts of those; an unconvertible value names the module and key and keeps the last value; colours and images later | [Value Types and Conversion](../42%20Python%20API/Value%20Types%20and%20Conversion.md) | Accept as proposed |
| G6 | The `Module` file: root is `Module { Params { ... } Children { ... } }`; `Params` types `string`, `number`, `boolean`, with defaults | [Module File](../41%20TDL%20Reference/Module%20File.md) open items | Accept; defaults are in v1 because the Clock needs them |
| G7 | The Clock scope: the full spec has `format`, `locale`, `hour_cycle`, `timezone`, `tooltip_format` | [Clock Module](../40%20Specifications/Modules/Clock%20Module.md) | M2: `format`, `hour_cycle` and `timezone`; `locale` and the tooltip with Popups in M3 |
| G8 | The file UID write: `with_metadata("UID", ...)` on first registration, with a backup first (R-06) | [Config Discovery and Registry](../40%20Specifications/Runtime/Config%20Discovery%20and%20Registry.md), [Risk Register](Risk%20Register.md) R-06 | M2a, with a backup copy outside the config folder before the first write |
| G9 | The keyed diff (written 2026-11-04 as [Render Binder Design > The Keyed Diff (Proposed, for M2b)](../20%20Architecture/Render%20Binder%20Design.md#the-keyed-diff-proposed-for-m2b)): identity is the `Name:`, else block word plus position; `For` entries use TEL's `<name>_0001` names; what is kept, added, moved, removed | [Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md), [Render Binder Design > The View and the Later Operations](../20%20Architecture/Render%20Binder%20Design.md#the-view-and-the-later-operations) | Write the algorithm as a section of Render Binder Design before M2b |
| G10 | Theme tokens and style files | Deferred by [ADR-0016 Staged Development](../30%20Decisions/ADR-0016%20Staged%20Development.md) to M1 and M2 | M2 has inline `Style` and module style files with literal values; tokens and themes go to M3 |
| G11 | The shipped-module list | [V1 Widgets](../50%20Design%20System/V1%20Widgets.md) | Only the Clock is needed for M2; the list is needed before M4 |
| G12 | Events and actions (`On_Click`, `@action`) | [Module File](../41%20TDL%20Reference/Module%20File.md), [Module Contract](../42%20Python%20API/Module%20Contract.md) | Not in M2 (the Clock has none); design with the first interactive module |

Notes that must be at `review` before M2a starts: [Module Contract](../42%20Python%20API/Module%20Contract.md), [Module Context](../42%20Python%20API/Module%20Context.md), [Value Types and Conversion](../42%20Python%20API/Value%20Types%20and%20Conversion.md), [Module File](../41%20TDL%20Reference/Module%20File.md), [Clock Module](../40%20Specifications/Modules/Clock%20Module.md), and the new TEL Integration note.

## Tasks

### M2a: Live Values

| # | Task | Done when | Spec |
|---|---|---|---|
| A1 | `files/`: the `Module` root, `Params` and `Children`, `Import` of module files (relative paths, nesting, cycle error), module calls by `Name:` through the registry | A shell that imports a module file loads; a cycle names the chain | [Module File](../41%20TDL%20Reference/Module%20File.md), [Config Discovery and Registry](../40%20Specifications/Runtime/Config%20Discovery%20and%20Registry.md) |
| A2 | The file UID write with a backup, keyed registry entries (`Clock@<uid>`) | A first load adds `UID:` to the metadata and changes no other byte; a backup exists | [Config Discovery and Registry > Identity and UIDs](../40%20Specifications/Runtime/Config%20Discovery%20and%20Registry.md#identity-and-uids), [TDL Library API](../42%20Python%20API/TDL%20Library%20API.md) |
| A3 | `modules/`: the host imports `<Name>_Module.py`, finds one `Module` subclass, builds `ctx`, calls `start()` and `stop()`, isolates failures | The bad-module cases in [Module Contract](../42%20Python%20API/Module%20Contract.md) pass | [Module Contract](../42%20Python%20API/Module%20Contract.md), [Module Context](../42%20Python%20API/Module%20Context.md) |
| A4 | The value store and `ctx.send`: thread-safe entry through `call_soon`, coalescing, type check | Sends from two threads in one turn leave the latest value per key | [Value Types and Conversion](../42%20Python%20API/Value%20Types%20and%20Conversion.md) |
| A5 | `model/`: the TEL scope and compilation of slots with `Origin`, tracked reads, the link table | A slot reading `clock.text` re-evaluates only when that key changes; an error names `file:line:column` | the TEL Integration note |
| A6 | `binder/`: `SlotValue` in the typed tree, `View.update` through `Window.apply` | One value change makes one `apply` and no other call | [Render Binder Design](../20%20Architecture/Render%20Binder%20Design.md) |
| A7 | The Clock module with `ctx.on_tick` | The text changes at the minute (the second with `%S`) without drift | [Clock Module](../40%20Specifications/Modules/Clock%20Module.md) |
| A8 | Tests, a manual KWin check, and an idle measurement with the Clock running | Between ticks: no frames, no wake-ups | [Testing Strategy](../60%20Quality/Testing%20Strategy.md), [Performance Budgets](../60%20Quality/Performance%20Budgets.md) |

### M2b: Structure and Reload

| # | Task | Done when | Spec |
|---|---|---|---|
| B1 | `If`/`Else` and `For` in the binder, TEL `select`, `compile_repeater_parts` and `Repeater.reconcile`, entry scopes | A `For` over a module's list shows one entry per item, reordered without rebuilding the others | [ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md) D64, D65 |
| B2 | The file watcher (`inotify_simple`, a thread, `call_soon`), the 200 ms debounce, atomic-save handling | One reload per save | [Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md) |
| B3 | `view.rebuild` by keyed diff; a module `.tdl` change calls `reload()` and keeps the instance; a `.py` change replaces it | The acceptance cases in [Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md) pass | [Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md), [Render Binder Design](../20%20Architecture/Render%20Binder%20Design.md) |
| B4 | Module style files `<Name>_Style.tdl` and inline `Style` in modules | A module's look is a file next to it | [Style, Theme and Stylesheet Files](../41%20TDL%20Reference/Style%2C%20Theme%20and%20Stylesheet%20Files.md) |
| B5 | Icon sets: read the `mdi` JSON from the configured folder, `SVG` by name, `Color` | An icon shows by name and takes the foreground colour | [Block Reference > Icons (R7)](../41%20TDL%20Reference/Block%20Reference.md#icons-r7) |
| B6 | Tests, a KWin check of the reload cases, and a measurement of the reload time | Reload within about 300 ms | [Testing Strategy](../60%20Quality/Testing%20Strategy.md) |

## Dependencies

`tess_el` (`tesserae-el` 0.1.2 or later in the range), `tess_utils` for colour and sides, `inotify_simple` for B2 ([ADR-0019 Dependency Policy](../30%20Decisions/ADR-0019%20Dependency%20Policy.md)), and the packages already in use. `tess_dl` 0.1 has no `Block.properties`, `Block.get` or `Document.imports`; the shell's helpers cover them, or a `TDL-REQ-###` asks for them.

## Questions for the Maintainer

All seven were answered on 2026-11-04 ("1. yes ... 6. yes, 7. M2b").

1. [x] M2 is split into M2a and M2b, in that order.
2. [x] Design first: the TEL Integration note is written while M1 is built ([TEL Integration](../20%20Architecture/TEL%20Integration.md)).
3. [x] G3, G4, G5 and G6 are accepted as recommended (module contract, context API, value types, module file).
4. [x] G7: the Clock in M2 has `format`, `hour_cycle` and `timezone`; `locale` and the tooltip wait for M3.
5. [x] G8: the file UID write is in M2a, with a backup outside the config folder.
6. [x] G10: tokens and themes move to M3; M2 uses literal values.
7. [x] B5: icon sets are in M2b.

## Acceptance Criteria

- [x] Every line of "Goal and Definition of Done" is true, with a KWin check of the Clock and the reload.
- [x] Each task has a test or a recorded measurement.
- [ ] The notes listed under "Design Needed First" are at `review` before the half that needs them starts.
- [ ] Design gaps found are handed back to the vault session.

## Links

- [Development Readiness](Development%20Readiness.md) · [M1 Brief](M1%20Brief.md) · [Render Binder Design](../20%20Architecture/Render%20Binder%20Design.md) · [Module Contract](../42%20Python%20API/Module%20Contract.md) · [Module Context](../42%20Python%20API/Module%20Context.md) · [Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md) · [Clock Module](../40%20Specifications/Modules/Clock%20Module.md)
