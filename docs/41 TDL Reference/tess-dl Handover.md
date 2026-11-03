---
title: tess-dl Handover
aliases: [TDL Source of Truth, Moving TDL to tess-dl]
type: tdl-ref
status: draft
owner: phil
created: 2026-11-02
updated: 2026-11-02
tags: [tdl-ref, tdl]
---

# tess-dl Handover

> [!NOTE]
> The `tess-dl` project becomes the source of truth for the TDL language (maintainer, 2026-11-02, [ADR-0014 Shell File Language > Ninth-Round Decisions (2026-11-02)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#ninth-round-decisions-2026-11-02) D66). This note says which parts of [TDL Language](TDL%20Language.md) move to `tess-dl`, which stay in this vault as the shell's schema, and how the move happens without a gap. Done on 2026-11-02 (D66, D92): the library API and the first-slice brief moved to `tess-dl/docs/` (`api.md`, `first-slice.md`), the vault keeps pointers, and the syntax and lexical parts of [TDL Language](TDL%20Language.md) are replaced by pointers to `tess-dl`'s `docs/language.md`. Still in the vault: the shell's schema and the decisions.

## What Moves and What Stays

| Section of [TDL Language](TDL%20Language.md) | Goes to `tess-dl` (language) | Stays in this vault (shell schema) |
|---|---|---|
| Two Layers | The table's first row; the statement that other projects add their own blocks | The shell and Tesserae UI rows |
| A File, the sample | The file shape with a neutral sample (no bars) | The shell sample, moved into [Shell File](Shell%20File.md) |
| The Metadata Block | `---` block, `TDL:` and `Name:` rules, `UID:` placement (D10), unknown keys kept, versions are strings | Which pins a shell requires (`TEL`, `TRE`, `Shell`), the meaning of minimum versions (D37) |
| The Root Block | Exactly one root block; the block's word is its type | The table of root blocks and suffixes; the suffix check |
| Punctuation | All of it | Nothing |
| Values (lexical kinds) | Word, string, number, percent, call, list, slot, template, escapes, comments, the bare-hash rule | Length, colour, enum, boolean, four-sided: typing and defaults |
| Names and the Registry | Name characters, dotted paths, reserved structure words, repeats | The built-in name registry, modules, Kind, instances |
| Structure Words | `Children`, `Import`, `If`, `Else`, `For`, `In`, `Key` | How the shell resolves `Import` and `Key` |
| Monitors, Sizes (Shell Schema) | Nothing | All of it |
| Errors | The language-level codes (D52) | Schema and load errors, including `shell-root-suffix` (D91) |
| Editor Support | The TextMate grammar (lives next to the parser) | The JSON Schema ([JSON Schema and Editor Support](JSON%20Schema%20and%20Editor%20Support.md)) |
| Acceptance Criteria | The language-level ones, as the conformance corpus | The schema-level ones |

## How the Move Happens

1. First slice in `tess-dl`. The `tess-dl` session writes the language reference (`docs/language.md`) and the conformance corpus from [TDL Language](TDL%20Language.md) and [TDL Library API](../42%20Python%20API/TDL%20Library%20API.md). The sources are the vault notes; the text is rewritten for readers from other UI frameworks ([ADR-0014 Shell File Language > Ninth-Round Decisions (2026-11-02)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#ninth-round-decisions-2026-11-02) D68).
2. Differences are `TDL-REQ-###`. When the `tess-dl` text must differ from the vault, or a rule is unclear, it becomes a `TDL-REQ-###` in `80 Requests`, carried by the maintainer (AGENTS > 6. Requests Between Projects).
3. **Hand over, section by section.** When a section is in `tess-dl` and its corpus passes, the matching section here becomes a short summary with a link to the `tess-dl` page, so there is one source of truth (rule 4). The vault keeps the shell's schema and the decisions that explain it.
4. **The ADR stays.** [ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md) records why the language is as it is; the decision history is not moved.
5. **Until then,** the vault note is the working text and `tess-dl` may read it.
6. **All TDL documentation moves.** The maintainer plans to move all of the TDL documentation into `tess-dl/docs/` eventually (2026-11-02, D92). This note lists the first sections; the rest follow, and the vault keeps only the shell's schema and the decisions.
7. **The test corpus belongs to `tess-dl`.** The shell proposes cases through `TDL-REQ-###` and does not edit the corpus ([tess-dl First Slice](tess-dl%20First%20Slice.md)).

## Open Questions

1. [ ] Whether `tess-dl` publishes its docs as a site (the tre and Tesserae projects do) or keeps Markdown in the repository.
2. [ ] Who edits the language text when a shell need changes it: the `tess-dl` session after a `TDL-REQ-###` (recommended), or the shell session directly.

## Acceptance Criteria

- [ ] Every row above has a single owner after the move.
- [ ] No rule of the language is stated in both places.
- [ ] Every language-level acceptance case in [TDL Language](TDL%20Language.md) appears in the conformance corpus.

## Links

- [TDL Language](TDL%20Language.md) · [TDL Library API](../42%20Python%20API/TDL%20Library%20API.md) · [ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md) · [41 TDL Reference](41%20TDL%20Reference.md)
