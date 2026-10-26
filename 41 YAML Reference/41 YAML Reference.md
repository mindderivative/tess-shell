---
title: 41 YAML Reference
aliases: [YAML Reference]
type: moc
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-26
tags: [moc, yaml-ref]
related: ["[[Index]]", "[[AGENTS]]"]
depends_on: []
---

# 41 YAML Reference

The keys and forms of every shell YAML file. Decisions are in [[ADR-0007 Shell UI Layer]] and the notes it links; these notes collect them for a file author and mark what is still proposed.

| Note | Purpose | Status |
|---|---|---|
| [[Common Keys and Conventions]] | Keys every file has, `type`/`kind`/`widget`, names, value forms, errors | draft |
| [[Shell File]] | The shell file: root, monitor, surfaces and their keys | draft |
| [[Module File]] | The module file: layout, params, data in the layout, using a module | draft |
| [[Style, Theme and Stylesheet Files]] | Style format from the Label example; theme and stylesheet to design | draft |

Expressions are TEL's ([[Expression Language Requirements]]); their grammar is worked out in the TEL project. Not started: a per-widget property reference, the surface-kind keys, the event and action keys, the Theme and Stylesheet shapes, and a JSON Schema for editor support.
