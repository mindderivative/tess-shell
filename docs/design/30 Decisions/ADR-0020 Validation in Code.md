---
title: ADR-0020 Validation in Code
aliases: [ADR-0020, No jsonschema at Runtime, In-Code Validation]
type: adr
status: accepted
owner: phil
created: 2026-11-03
updated: 2026-11-03
tags: [adr, runtime, dependencies]
---

# ADR-0020: Validation in Code

> [!NOTE]
> The shell checks a parsed TDL file in its own `schema` package, in code, as it builds the typed tree. It does not run the `jsonschema` library at run time. If editor tools want JSON Schema files later, the shell emits them as plain JSON from the same declarations, with no validator library. Accepted by the maintainer in chat on 2026-11-03 ("Lets go with your recommendation").

## Context

[ADR-0011 JSON Schema for Shell Files](ADR-0011%20JSON%20Schema%20for%20Shell%20Files.md) (accepted 2026-10-27, for YAML) had the shell validate each file against JSON Schema files generated from the block and module declarations, using `jsonschema` at load and on hot reload. The shell's files are now TDL ([ADR-0014 Shell File Language](ADR-0014%20Shell%20File%20Language.md)), and:

- the editor use of the schemas was dropped (no language server in v1, D12), so run-time validation was the schemas' only use;
- the `schema` package has to check keys and types in code anyway, to build the typed tree for the binder, report `file:line:column`, and suggest the nearest key names ([M1 Brief](../00%20Home/M1%20Brief.md), T5);
- a 2026-10-27 spike found that `jsonschema` reports a choice between branches (`oneOf`) as one vague error and `best_match` picked an unrelated one, so the schema had to be hand-shaped around the library, and it gives paths, not positions;
- `jsonschema` brings `attrs`, `referencing`, `jsonschema-specifications` and the compiled `rpds-py`, and about 43 ms of import time, which the shell worked around with a lazy import and a cache ([JSON Schema and Editor Support > The `jsonschema` Dependency: Runtime, Not Only Development](../41%20TDL%20Reference/JSON%20Schema%20and%20Editor%20Support.md#the-jsonschema-dependency-runtime-not-only-development));
- [ADR-0019 Dependency Policy](ADR-0019%20Dependency%20Policy.md) asks for a library only where building the same would be a project of its own, and these checks are not.

The maintainer asked whether there is any reason for `jsonschema` to run at run time; none was found.

## Options

### Option A — Validate in Code; Emit JSON Schema Later as Plain JSON (Chosen)

- **For:** one pass builds the typed tree and the errors with their positions; messages are ours; four fewer packages and no compiled one; no 43 ms import; no cache; module `Params` become validators built from the module's declarations.
- **Against:** we write and test the checks (they are table-driven, and the declarations are the same ones the Block Reference test compares).

### Option B — Keep `jsonschema` at Run Time (ADR-0011 as it stood)

- **Against:** the costs above, for a use that code does anyway.

## Decision

Accepted 2026-11-03 by the maintainer in chat: **Option A**.

## Consequences

- [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md) drops `jsonschema`. The `tesserae-shell schema` command, if wanted, writes JSON Schema as plain JSON from the declarations; it needs no validator library.
- The `Validation.Enabled` setting stays. The validation cache is no longer needed: in-code checks take microseconds to milliseconds ([Settings File](../41%20TDL%20Reference/Settings%20File.md)). A cache returns only if a measurement shows a need.
- [ADR-0011 JSON Schema for Shell Files](ADR-0011%20JSON%20Schema%20for%20Shell%20Files.md) carries a dated update: run-time validation by `jsonschema` is replaced by this ADR; the other parts (schemas generated from declarations, if produced) stand.
- [Validation and Errors](../40%20Specifications/Runtime/Validation%20and%20Errors.md) stage 4 is "the `schema` package checks in code". The error record, positions and nearest-name hints are unchanged.
- [Risk Register](../00%20Home/Risk%20Register.md) R-13 no longer lists `jsonschema`.
- The code session writes the checks as part of M1 T5; the tests compare the declarations with [Block Reference](../41%20TDL%20Reference/Block%20Reference.md).

## Links

- [ADR-0011 JSON Schema for Shell Files](ADR-0011%20JSON%20Schema%20for%20Shell%20Files.md) · [ADR-0019 Dependency Policy](ADR-0019%20Dependency%20Policy.md) · [Validation and Errors](../40%20Specifications/Runtime/Validation%20and%20Errors.md) · [JSON Schema and Editor Support](../41%20TDL%20Reference/JSON%20Schema%20and%20Editor%20Support.md) · [Shell Package Layout](../20%20Architecture/Shell%20Package%20Layout.md) · [30 Decisions](30%20Decisions.md)
