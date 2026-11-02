---
title: 41 TDL Reference
aliases: [41 YAML Reference, YAML Reference, TDL Reference]
type: moc
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-30
tags: [moc, tdl-ref]
---

# 41 TDL Reference

The keys and forms of every shell file, written in TDL (Tesserae Data Language, `.tdl`; [ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md)). The folder is `41 TDL Reference` and the note type is `tdl-ref` (D13 in [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)). Decisions are in [ADR-0007 Shell UI Layer](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md), [ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md) and the notes they link; these notes collect them for a file author and mark what is still open.

| Note                                    | Purpose                                                                                                      | Status |
|-----------------------------------------|--------------------------------------------------------------------------------------------------------------|--------|
| [TDL Language](TDL%20Language.md) | The language itself: metadata block, root block, punctuation, case rules, name registry, monitors, sizes, structure words      | draft  |
| [Block Reference](Block%20Reference.md) | The properties, events, accessibility defaults and tre mapping of every building block (proposed) | draft  |
| [Common Keys and Conventions](Common%20Keys%20and%20Conventions.md) | Keys every file has, what says what a thing is, names, value forms, errors                                      | draft  |
| [Shell File](Shell%20File.md) | The shell file: root, monitor, surfaces and their keys                                                       | draft  |
| [Module File](Module%20File.md) | The module file: layout, params, data in the layout, using a module                                          | draft  |
| [Style, Theme and Stylesheet Files](Style%2C%20Theme%20and%20Stylesheet%20Files.md) | Style, theme and stylesheet files: metadata block and root block (`Style { }`, `Theme { }`, `Stylesheet { }`); style format from the Label example                                          | draft  |
| [Settings File](Settings%20File.md) | The config directory layout and `settings.tdl` (root block `Settings { }`): directories, main shell, global settings (keys proposed)    | draft  |
| [JSON Schema and Editor Support](JSON%20Schema%20and%20Editor%20Support.md) | JSON Schema files, chosen by the root block and suffix, that validate the parsed TDL tree at load and reload; the `tesserae-shell schema` command; no editor part in v1 (D12) | draft  |
| [Style Schema](Style%20Schema.md) | Proposed shell-owned style keys, theme tokens, shadow keys and stylesheet `Rule` blocks                          | draft  |

Expressions are TEL's ([Expression Language Requirements](../40%20Specifications/Runtime/Expression%20Language%20Requirements.md)); their grammar is worked out in the TEL project. Not started: the surface-kind keys, the event and action keys, and the JSON Schema files themselves (the design is in [JSON Schema and Editor Support](JSON%20Schema%20and%20Editor%20Support.md); the Theme and Stylesheet shapes are proposed in [Style Schema](Style%20Schema.md); the key names of the style schema are still a proposal).
