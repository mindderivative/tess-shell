---
title: 41 YAML Reference
aliases: [YAML Reference, TDL Reference]
type: moc
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-29
tags: [moc, yaml-ref]
related: ["[[Index]]", "[[AGENTS]]"]
depends_on: []
---

# 41 YAML Reference

The keys and forms of every shell file, written in TDL (Tesserae Data Language, `.tdl`; [[ADR-0014 Shell File Language]]). This folder keeps the name `41 YAML Reference` and the note type `yaml-ref` until the maintainer decides a rename. Decisions are in [[ADR-0007 Shell UI Layer]] and the notes it links; these notes collect them for a file author and mark what is still proposed.

| Note                                    | Purpose                                                                                                      | Status |
|-----------------------------------------|--------------------------------------------------------------------------------------------------------------|--------|
| [[Common Keys and Conventions]] | Keys every file has, `type`/`kind`/`widget`, names, value forms, errors                                      | draft  |
| [[Shell File]] | The shell file: root, monitor, surfaces and their keys                                                       | draft  |
| [[Module File]] | The module file: layout, params, data in the layout, using a module                                          | draft  |
| [[Style, Theme and Stylesheet Files]] | Style format from the Label example; theme and stylesheet to design                                          | draft  |
| [[Settings File]] | The config directory layout and `settings.tdl`: directories, main shell, global settings (proposed keys)    | draft  |
| [[JSON Schema and Editor Support]] | JSON Schema files to validate the parsed TDL tree at load; editor completion and hover need a rethink after ADR-0014 (proposed) | draft  |
| [[Style Schema]] | Proposed shell-owned style keys, theme tokens, shadow keys and stylesheet selectors                          | draft  |

Expressions are TEL's ([[Expression Language Requirements]]); their grammar is worked out in the TEL project. Not started: a per-widget property reference, the surface-kind keys, the event and action keys, and the JSON Schema files themselves (the design is in [[JSON Schema and Editor Support]]; the Theme and Stylesheet shapes are proposed in [[Style Schema]]).
