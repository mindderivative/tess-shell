---
title: ADR-0011 JSON Schema for Shell Files
aliases: [ADR-0011, Shell YAML Schema Decision]
type: adr
status: proposed
owner: phil
created: 2026-10-27
updated: 2026-10-27
tags: [adr, tooling, needs-verification]
related: ["[[JSON Schema and Editor Support]]", "[[Style Schema]]", "[[ADR-0007 Shell UI Layer]]", "[[Common Keys and Conventions]]"]
depends_on: ["[[ADR-0007 Shell UI Layer]]"]
---

# ADR-0011: JSON Schema for shell files

> [!summary]
> Define the shell's YAML with JSON Schema files, generated from the block and module declarations. Editors use them for completion, hover and validation; the shell uses them to validate at load and on hot reload. Proposed on the maintainer's idea (2026-10-27).

## Context

The shell has five YAML file types and many keys ([[Common Keys and Conventions]], [[Style Schema]]). Authors write them by hand. Without a schema an author gets no completion or hover text, and the only validation is whatever the shell codes by hand. The maintainer proposed JSON Schema with the Red Hat YAML extension.

## Options

### Option A — JSON Schema, generated from the declarations (recommended)
- **For:** one source of truth with the Python declarations; works in editors that use the YAML language server; the shell reuses the same files; the schema language is standard and documented. A spike found that `if`/`then` dispatch gives precise errors with `file:line:column` ([[JSON Schema and Editor Support#Findings from a spike (2026-10-27)]]).
- **Against:** user modules need a generated project schema; the schema cannot express cross-file rules, so the shell still needs semantic checks; adds a dependency (`jsonschema`); draft support differs between the extension and the server (draft-07 keywords avoid it).

### Option B — Hand-coded validation in the shell only
- **For:** no dependency; full control of messages.
- **Against:** no editor support; the reference, the code and the checks can disagree; every block needs its own checks written.

### Option C — Hand-written schemas
- **For:** editor support without a generator.
- **Against:** drifts from the code; large files that nobody maintains.

## Decision

Blank until the maintainer accepts.

## Consequences

- Blocks and modules must declare their properties with a doc line each; the doc becomes the hover text ([[Building Blocks#Properties, parts and states]]).
- A schema generation step and a `tesserae-shell schema` command are part of the runtime and delivery design.
- Semantic checks stay in the shell, after the schema passes.
- The format version in `shell:` selects the schema folder.

## Links

[[JSON Schema and Editor Support]] · [[Style Schema]] · [[Common Keys and Conventions]] · [[30 Decisions]]
