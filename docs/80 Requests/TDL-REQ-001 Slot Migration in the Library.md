---
title: TDL-REQ-001 Slot Migration in the Library
aliases: [TDL-REQ-001, tess_dl migrate, slot migration]
type: engine-request
status: draft
owner: phil
created: 2026-11-17
updated: 2026-11-17
tags: [engine-request, tdl]
---

# TDL-REQ-001: Ship the Slot Migration Inside `tess_dl`

> [!NOTE]
> The step that rewrites a TDL 0.1 file (slots written `{{ }}`) to 0.2 (`<| |>`) lives in `tools/migrate_slots.py` in the `tess-dl` repository, and it needs `tesserae-dl` 0.1.1 installed to read the old form. A program that depends on `tesserae-dl` 0.2.0 or later, as Tesserae Shell does, cannot call it. The request: `tess_dl` ships the rewrite as a library function that needs no old reader, so a program can migrate a user's files itself. Written on 2026-11-17 from the design of [Version Policy and Migration](../70%20Delivery/Version%20Policy%20and%20Migration.md); the maintainer carries it to `tess-dl`.

## Need

`tesserae-shell migrate` ([Version Policy and Migration > The `migrate` Command](../70%20Delivery/Version%20Policy%20and%20Migration.md#the-migrate-command)) must bring a user's 0.1 files to 0.2 on the user's machine. Raised by Tesserae Shell; `tess-ui`'s configuration application may want the same for the files it edits.

## Why It Belongs in `tess-dl`

The rules for where a 0.1 slot starts and ends (the first `}}` outside a quoted string, quote and escape rules) are the language's. Two programs writing their own scanner would drift from the language reference. The library owns the language, and the migration is a statement about the language's history.

## Facts

Read from the `tess-dl` repository on 2026-11-17 and its session's reports:

| Fact | Source |
|---|---|
| `tools/migrate_slots.py` rewrites the two delimiters of every slot and `TDL: 0.1` to `TDL: 0.2`, and changes no other byte; it is run with `uv run --no-project --with tesserae-dl==0.1.1 python tools/migrate_slots.py [--check] PATHS` | The script's own header |
| A slot whose text holds `|>` outside a quote cannot be migrated by rewriting the delimiters; the file is reported and left | The same header |
| Exit status: 0 done or nothing to do, 1 `--check` found work, 2 a file could not be migrated | The same header |
| `tesserae-dl` 0.2.0 reads slots as `<| |>` and refuses `{{ }}` with `tdl-unexpected-text` | The `tess-dl` session's report, 2026-11-14 |

## Proposed Change

`tess-dl` adds, to a release after 0.2.0, a function such as `tess_dl.migrate.slots_0_1_to_0_2(text: str) -> MigrationResult`, with the behaviour of the script: a scan that implements the 0.1 slot rules itself (so it needs no 0.1 reader), the rewritten text, the number of slots changed, and the list of slots it could not rewrite with their positions. The script becomes a thin command over it. The same module is where later steps go (`0.2 to 0.3` and so on), each a pure text-to-text function.

## Alternatives

None that does not cost the program something: running the script needs a second library version, a network and `uv` at run time; copying the script into the shell duplicates the language rules. If `tess-dl` declines, Tesserae Shell carries its own small scanner and the vault records it ([Version Policy and Migration](../70%20Delivery/Version%20Policy%20and%20Migration.md)).

## If Declined

The shell carries its own scanner of the 0.1 slot rules for the one `migrate` step.

## Acceptance

On the `tess-dl` conformance corpus, `slots_0_1_to_0_2` gives the same output as `tools/migrate_slots.py` run with 0.1.1 for every 0.1 file; a file already at 0.2 is returned unchanged; a slot with `|>` outside a quote is reported with its position and left alone; the function raises nothing for any input.

## Links

[Version Policy and Migration](../70%20Delivery/Version%20Policy%20and%20Migration.md) · [TDL Language](../41%20TDL%20Reference/TDL%20Language.md) · [80 Requests](80%20Requests.md)
