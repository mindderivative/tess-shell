---
title: 41 TDL Reference
aliases: [41 YAML Reference, YAML Reference, TDL Reference]
type: moc
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-30
tags: [moc, tdl-ref]
related: ["[[Index]]", "[[AGENTS]]"]
depends_on: []
---

# 41 TDL Reference

The keys and forms of every shell file, written in TDL (Tesserae Data Language, `.tdl`; [[ADR-0014 Shell File Language]]). The folder is `41 TDL Reference` and the note type is `tdl-ref` (D13 in [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]). Decisions are in [[ADR-0007 Shell UI Layer]], [[ADR-0014 Shell File Language]] and the notes they link; these notes collect them for a file author and mark what is still open.

| Note                                    | Purpose                                                                                                      | Status |
|-----------------------------------------|--------------------------------------------------------------------------------------------------------------|--------|
| [[TDL Language]] | The language itself: file header, punctuation, case rules, name registry, monitors, structure words      | draft  |
| [[Common Keys and Conventions]] | Keys every file has, what says what a thing is, names, value forms, errors                                      | draft  |
| [[Shell File]] | The shell file: root, monitor, surfaces and their keys                                                       | draft  |
| [[Module File]] | The module file: layout, params, data in the layout, using a module                                          | draft  |
| [[Style, Theme and Stylesheet Files]] | Style format from the Label example; theme and stylesheet to design                                          | draft  |
| [[Settings File]] | The config directory layout and `settings.tdl`: directories, main shell, global settings (keys proposed)    | draft  |
| [[JSON Schema and Editor Support]] | JSON Schema files that validate the parsed TDL tree at load and reload; the `tesserae-shell schema` command; no editor part in v1 (D12) | draft  |
| [[Style Schema]] | Proposed shell-owned style keys, theme tokens, shadow keys and stylesheet `Rule` blocks                          | draft  |

Expressions are TEL's ([[Expression Language Requirements]]); their grammar is worked out in the TEL project. Not started: a per-widget property reference, the surface-kind keys, the event and action keys, and the JSON Schema files themselves (the design is in [[JSON Schema and Editor Support]]; the Theme and Stylesheet shapes are proposed in [[Style Schema]]; the key names of the style schema are still a proposal).
