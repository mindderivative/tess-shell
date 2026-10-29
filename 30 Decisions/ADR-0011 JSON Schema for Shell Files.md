---
title: ADR-0011 JSON Schema for Shell Files
aliases: [ADR-0011, Shell YAML Schema Decision]
type: adr
status: accepted
owner: phil
created: 2026-10-27
updated: 2026-10-27
tags: [adr, tooling, needs-verification]
related: ["[[JSON Schema and Editor Support]]", "[[Style Schema]]", "[[ADR-0007 Shell UI Layer]]", "[[Common Keys and Conventions]]"]
depends_on: ["[[ADR-0007 Shell UI Layer]]"]
---

# ADR-0011: JSON Schema for Shell Files

> [!summary]
> Define the shell's YAML with JSON Schema files, generated from the block and module declarations. Editors use them for completion, hover and validation; the shell uses them to validate at load and on hot reload. Accepted 2026-10-27 on the maintainer's idea.

## Context

The shell has five YAML file types and many keys ([[Common Keys and Conventions]], [[Style Schema]]). Authors write them by hand. Without a schema an author gets no completion or hover text, and the only validation is whatever the shell codes by hand. The maintainer proposed JSON Schema with the Red Hat YAML extension.

## Options

### Option A — JSON Schema, Generated from the Declarations (Recommended)

- **For:** one source of truth with the Python declarations; works in editors that use the YAML language server; the shell reuses the same files; the schema language is standard and documented. A spike found that `if`/`then` dispatch gives precise errors with `file:line:column` ([[JSON Schema and Editor Support#Findings from a spike (2026-10-27)]]).
- **Against:** user modules need a generated project schema; the schema cannot express cross-file rules, so the shell still needs semantic checks; adds a dependency (`jsonschema`); draft support differs between the extension and the server (draft-07 keywords avoid it).

### Option B — Hand-coded Validation in the Shell Only

- **For:** no dependency; full control of messages.
- **Against:** no editor support; the reference, the code and the checks can disagree; every block needs its own checks written.

### Option C — Hand-written Schemas

- **For:** editor support without a generator.
- **Against:** drifts from the code; large files that nobody maintains.

## Decision

Option A (maintainer, 2026-10-27). Decided the same day: draft-07 keywords; the schemas live in the config directory, `$HOME/.config/tesserae-shell/schemas/`, ignored by version control; `jsonschema` is imported lazily and a validation cache skips unchanged files. Validation runs at start and on reload, not per frame. Open items are in [[JSON Schema and Editor Support#Open]].

## Consequences

- Blocks and modules must declare their properties with a doc line each; the doc becomes the hover text ([[Building Blocks#Properties, parts and states]]).
- A schema generation step and a `tesserae-shell schema` command are part of the runtime and delivery design.
- Semantic checks stay in the shell, after the schema passes.
- The format version in `shell:` selects the schema folder.

## Links

[[JSON Schema and Editor Support]] · [[Style Schema]] · [[Common Keys and Conventions]] · [[30 Decisions]]
