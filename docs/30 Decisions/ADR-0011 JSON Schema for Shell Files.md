---
title: ADR-0011 JSON Schema for Shell Files
aliases: [ADR-0011, Shell YAML Schema Decision]
type: adr
status: accepted
owner: phil
created: 2026-10-27
updated: 2026-11-03
tags: [adr, tooling, needs-verification]
---

# ADR-0011: JSON Schema for Shell Files

> [!NOTE]
> Define the shell's YAML with JSON Schema files, generated from the block and module declarations. Editors use them for completion, hover and validation; the shell uses them to validate at load and on hot reload. Accepted 2026-10-27 on the maintainer's idea.

> [!WARNING]
> **Amended after ADR-0014 (2026-10-29, decided 2026-10-30)**
> The shell's files are now TDL, not YAML ([ADR-0014 Shell File Language](ADR-0014%20Shell%20File%20Language.md)). What still holds: JSON Schema files generated from the block and module declarations can validate the tree the TDL parser produces, at load and on reload, and semantic checks stay in the shell. What no longer applies: completion, hover and validation in editors through the YAML language server and the Red Hat YAML extension, and the spike's results on YAML (kept as dated findings). There is no language server in v1; a small TextMate grammar gives highlighting only. The text below is the 2026-10-27 decision as made. Decided 2026-10-30 ([ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30), D12): the ADR stands for load-time and reload validation of the parsed tree, and the editor part is dropped. The `schemas/` folder is still generated, for the `tesserae-shell schema` command and a future language server. The loader reads the metadata block first, because the file-type key picks the schema, and the schema then validates both the metadata part and the block part. The parsed tree is an ordered list of entries (head, properties, children) that keeps repeated names. See [JSON Schema and Editor Support](../41%20TDL%20Reference/JSON%20Schema%20and%20Editor%20Support.md).

## Context

The shell has five YAML file types and many keys ([Common Keys and Conventions](../41%20TDL%20Reference/Common%20Keys%20and%20Conventions.md), [Style Schema](../41%20TDL%20Reference/Style%20Schema.md)). Authors write them by hand. Without a schema an author gets no completion or hover text, and the only validation is whatever the shell codes by hand. The maintainer proposed JSON Schema with the Red Hat YAML extension.

## Options

### Option A — JSON Schema, Generated from the Declarations (Recommended)

- **For:** one source of truth with the Python declarations; works in editors that use the YAML language server; the shell reuses the same files; the schema language is standard and documented. A spike found that `if`/`then` dispatch gives precise errors with `file:line:column` ([JSON Schema and Editor Support > Findings from a spike (2026-10-27)](../41%20TDL%20Reference/JSON%20Schema%20and%20Editor%20Support.md#findings-from-a-spike-2026-10-27)).
- **Against:** user modules need a generated project schema; the schema cannot express cross-file rules, so the shell still needs semantic checks; adds a dependency (`jsonschema`); draft support differs between the extension and the server (draft-07 keywords avoid it).

### Option B — Hand-coded Validation in the Shell Only

- **For:** no dependency; full control of messages.
- **Against:** no editor support; the reference, the code and the checks can disagree; every block needs its own checks written.

### Option C — Hand-written Schemas

- **For:** editor support without a generator.
- **Against:** drifts from the code; large files that nobody maintains.

## Decision

Option A (maintainer, 2026-10-27). Decided the same day: draft-07 keywords; the schemas live in the config directory, `$HOME/.config/tesserae-shell/schemas/`, ignored by version control; `jsonschema` is imported lazily and a validation cache skips unchanged files. Validation runs at start and on reload, not per frame. Open items are in [JSON Schema and Editor Support > Open](../41%20TDL%20Reference/JSON%20Schema%20and%20Editor%20Support.md#open).

## Consequences

- Blocks and modules must declare their properties with a doc line each; the doc becomes the hover text ([Building Blocks > Properties, parts and states](../50%20Design%20System/Building%20Blocks.md#properties-parts-and-states)).
- A schema generation step and a `tesserae-shell schema` command are part of the runtime and delivery design.
- Semantic checks stay in the shell, after the schema passes.
- The format version in `shell:` selects the schema folder.

## Update 2026-11-03

Run-time validation with `jsonschema` is replaced by validation in code ([ADR-0020 Validation in Code](ADR-0020%20Validation%20in%20Code.md), accepted 2026-11-03). Schemas generated from the declarations, if produced for tools, are emitted as plain JSON; the shell does not load a validator library.

## Links

[JSON Schema and Editor Support](../41%20TDL%20Reference/JSON%20Schema%20and%20Editor%20Support.md) · [Style Schema](../41%20TDL%20Reference/Style%20Schema.md) · [Common Keys and Conventions](../41%20TDL%20Reference/Common%20Keys%20and%20Conventions.md) · [30 Decisions](30%20Decisions.md)
