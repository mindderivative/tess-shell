---
title: Validation and Errors
aliases: [Error Reporting, Validation Pipeline, file:line:column]
type: spec
status: review
owner: phil
created: 2026-10-28
updated: 2026-10-30
tags: [spec/runtime, needs-verification]
related: ["[[Runtime]]", "[[Common Keys and Conventions]]", "[[JSON Schema and Editor Support]]", "[[ADR-0011 JSON Schema for Shell Files]]", "[[Config Discovery and Registry]]", "[[Hot Reload]]", "[[Shell Start and Stop]]", "[[Expression Language Requirements]]"]
depends_on: ["[[ADR-0011 JSON Schema for Shell Files]]", "[[Common Keys and Conventions]]"]
---

# Validation and Errors

> [!summary]
> Every problem the shell finds in a file is reported with the file, line and column, says what is wrong and what to write, and goes to the console and the log. Checking runs in stages, from the file's bytes to a running module. At start any error stops the shell; on a reload any error keeps the old state ([[Process Model and Threading#Lifecycle (proposed)]]). Decided: `file:line:column` ([[AGENTS#3. Layering principle]]), JSON Schema for structure ([[ADR-0011 JSON Schema for Shell Files]]), the schema cache ([[JSON Schema and Editor Support]]), a bad `settings.tdl` stops the shell ([[Settings File]]). Everything else is proposed with a recommendation.

## Purpose and Scope

- One pipeline and one error format for all five file types, the settings file and the Python modules.
- Not in this note: what the keys mean (the TDL reference, folder [[41 TDL Reference]]), the JSON Schema files themselves ([[JSON Schema and Editor Support]]), and TEL's own grammar ([[Expression Language Requirements]]).

## Behaviour

### The Pipeline

```mermaid
flowchart LR
    a[1 Read] --> b[2 Parse]
    b --> c[3 Header]
    c --> d[4 Schema]
    d --> e[5 Semantic checks]
    e --> f[6 Expressions]
    f --> g[7 Modules]
    g --> h[8 Run time]
```

| Stage          | Checks                                                                                   | Tool                                                             | Position comes from                                                   |
|----------------|------------------------------------------------------------------------------------------|------------------------------------------------------------------|-----------------------------------------------------------------------|
| 1. Read        | The file opens and is UTF-8 (a byte-order mark is allowed and dropped)                   | Standard library                                                 | The file, line 1                                                      |
| 2. Parse       | TDL syntax; the tree is an ordered list of entries (head, properties, children) that keeps repeated names (D12); it holds only blocks, properties, lists and literal values; `{{ }}` slots are kept as text for stage 6 | The shell's TDL parser ([[ADR-0014 Shell File Language]])        | The parser's own positions                                            |
| 3. Header      | The loader reads the metadata block first, because the file-type key picks the schema (D12). The metadata block is present; `TDL:` is present with a known version; exactly one file-type key (`Shell:`, `Module:`, `Style:`, `Stylesheet:`, `Theme:`) with a known version; the key agrees with the suffix; `UID:` well formed | The shell                                                        | The key's node                                                        |
| 4. Schema      | The schema picked at stage 3 validates the metadata part and the block part (D12). Types, enums, required keys, unknown keys (the metadata block's other keys are kept and ignored), value forms (colour, four-sided, size) | `jsonschema`, draft-07 ([[ADR-0011 JSON Schema for Shell Files]]) | The tree node at the error's path                                       |
| 5. Semantic    | Rules a schema cannot say (below)                                                        | The shell                                                        | The node at the offending key or value                                |
| 6. Expressions | TEL compiles; every name it reads is known                                               | TEL                                                              | The slot's `Origin` (file, line, column) from the parser              |
| 7. Modules     | The `.py` imports; it holds one `Module` class; `validate_use` accepts each use          | Python                                                           | The traceback line for the `.py`; the use's node for a rejected param |
| 8. Run time    | An expression that fails to evaluate; a module callback that raises; a tre error         | The shell                                                        | The node or module that ran                                           |

- Unknown keys are errors, not warnings, to catch typos (decided 2026-10-28). The exception is the metadata block, where other keys are allowed and the shell ignores them ([[TDL Language#The Metadata Block]]).
- **Stage 3 errors** name the file and say which rule failed: no metadata block, no `TDL:`, not exactly one file-type key, or the key and the suffix disagree (the error names both; the key is authoritative, [[ADR-0014 Shell File Language#Layout Rules]]).
- **A file that fails stage 2 or 3 is not checked further,** because later stages need its data; other files continue. Stage 5 runs only when every file has passed stage 4, because it compares across files (decided 2026-10-28).
- **Stages 1 to 7 run before anything is shown** at start, and before anything is applied on a reload ([[Hot Reload]]). Stage 8 happens while running.

### Parsing

- The parser is the shell's own, in a module that imports nothing from the shell ([[ADR-0014 Shell File Language#What TDL Is (Decided)]], item 9). Its syntax errors carry `file:line:column` directly. There is no third-party parser, so no marks to translate.
- The same block name may repeat in one `Children { }`, ordered by position, so a repeated module call is not an error ([[Module File#Using a module]]). A property key repeated in one block is an error naming both places (D9, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]); the stage 5 rule is in the table below.
- The tree holds structure and literal values only. A file cannot run code: TDL has no statements, variables or tags, and every `{{ }}` slot is handed to TEL, which is sandboxed ([[Expression Language Requirements]]).
- The tree is lossless: it keeps comments and layout, and every node knows its line and column, so any path in the data maps to a position. This replaces the earlier YAML design, which kept PyYAML's `compose` node marks beside the data (spike of 2026-10-27, [[JSON Schema and Editor Support#Findings from a spike (2026-10-27)]]).
- Columns are 1-based and count characters, as editors do.
- No language server in v1, so these printed errors are the author's main feedback ([[ADR-0014 Shell File Language#What TDL Is (Decided)]], item 10). A small TextMate grammar gives highlighting only.
- `true`, `false` and `null` are lowercase bare words, and `[]` is the empty list. The parser keeps a bare word as a string, so stage 4 sees `Hidden: true` as the string `true` and the key's declared type in the schema turns it into a boolean, number or null (D2, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]).

### Semantic Checks

Rules a schema cannot say, with the note that owns each:

| Rule                                                                                                                       | Owner                                                                                                                     |
|----------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| A property key appears once in a block; a repeat is an error naming both places (D9; repeated block names are allowed) | [[TDL Language#Punctuation]] |
| A name is registered once (one registry for blocks, surface types and modules; a user module overrides a shipped one); a name used as a reference exists | [[Config Discovery and Registry#Names]], [[Common Keys and Conventions#Names and references]]                                          |
| No import cycle; every imported file exists                                                                                | [[Config Discovery and Registry#Discovery]]                                                                                   |
| A block head names a registered block, surface type or module; a module's params have the declared types; `validate_use` accepts them | [[Module File]], [[Module Contract]]                                          |
| A token `$group.name` exists in the active theme                                                                           | [[Style Schema#Theme tokens]]                                                                                   |
| `Exclusive_Zone` only on `Layer: top`; a Bar has no margin that breaks its zone; thickness forms are valid                 | [[Surface Types#Layers per kind]], [[Bar]], [[Frame]] |
| `Attach_To` and `Anchor_To` resolve; a Panel's target is a surface, a module or a Panel                                    | [[Panel]], [[Popup]]                                          |
| `Auto_Hide` and `Reveal_Key` are consistent                                                                                | [[Bar#Auto-hide (decided 2026-10-27)]]                                                                                   |
| The Python for a module exists, next to its TDL                                                                           | [[Module File]]                                                                                   |
| Two `Monitor` blocks do not name the same monitor; a `Monitor` with no selector is ignored (not an error); the files agree on the monitor rules | [[Shell File#Monitors]]                                                                                   |

A rule belongs to one stage. An unknown key is found by the schema (stage 4), not again by stage 5.

### The Error Record

Every finding has the same fields:

| Field            | Meaning                                                                                                                           |
|------------------|-----------------------------------------------------------------------------------------------------------------------------------|
| `file`           | The path, relative to the config directory when inside it                                                                         |
| `line`, `column` | 1-based; `0` only for a problem with the whole file                                                                               |
| `severity`       | `error`, `warning` or `info`                                                                                                      |
| `rule`           | A short stable slug such as `unknown-key` or `name-duplicate`; used in logs and tests, not shown as a number (decided 2026-10-28) |
| `message`        | What is wrong and what to write                                                                                                   |
| `hint`           | Optional: the nearest valid names, an example, a link to a note                                                                   |

Printed form, as a compiler prints it, with the offending line and a caret under the column:

```
Shells/Main_Shell.tdl:12:9: error: unknown style key 'Colour' on bar 'top_bar'
    12 |         Colour: red
       |         ^
    hint: did you mean 'Border_Color'?
```

- **Nearest names** come from `difflib.get_close_matches` in the standard library. A test on 2026-10-28 gave `border_color` for the typo `colour` and for `border_colour` (lowercase, run before keys were Capitalised; the match is the same on `Colour` and `Border_Colour`, to re-run).
- **Say what to write.** A message names the wrong thing, then the right form: `a colour is "#RRGGBB", "#RRGGBBAA" or rgba(r g b a)` ([[Common Keys and Conventions#Errors]]).
- **Severity.** An `error` refuses the file or the load. A `warning` never stops anything (a target that disappeared, a rebuilt registry record, a stale cache). An `info` is a note (an ignored file, a configured directory overriding the default).

### How Many Errors, and in what Order

- Every error from a stage is reported, sorted by file and line, not only the first, so a user fixes a file in one pass. A cap of 50 per run, then a line saying how many more were found (decided 2026-10-28).
- Errors from different files at the same stage are all reported. Stages after a failed stage are not run for the files they depend on.

### Where it Goes

| Place                  | What                                                                                                                          | When                                                                                                                      |
|------------------------|-------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| Console (stderr)       | The printed form, in colour when it is a terminal                                                                             | Always                                                                                                                    |
| The log file           | One record per finding, with `file`, `line`, `column`, `rule`, `severity` as fields ([[Settings File#Log files]]) | Always                                                                                                                    |
| A desktop notification | A short summary and the first error                                                                                           | A failure that stops the shell, or a failed reload; opt-out (decided 2026-10-28, [[Shell Start and Stop#Accessibility]]) |
| The command `check`    | The same output, no shell started, exit code 1 on any error                                                                   | On demand (the IPC and CLI note, to write)                                                                                |

### What a Failure Does

| When                   | Error                                                                                        | Warning                        |
|------------------------|----------------------------------------------------------------------------------------------|--------------------------------|
| Start                  | The shell stops with exit code 1 ([[Shell Start and Stop#Exit codes]])                   | Printed; the shell continues   |
| Reload                 | The old state is kept and the error is reported ([[Hot Reload]])    | Printed; the new state applies |
| Stage 8, while running | Logged with the node or module; the node shows its fallback, the rest of the shell continues | Logged                         |

A bad `settings.tdl` always stops the shell at start (decided 2026-10-27) and keeps the running settings on a reload.

## Configuration

`settings.tdl`: `Validation` with `Enabled` (default true) and the cache location ([[Settings File]]). Proposed additions: `Max_Errors` (default 50) and `Notify` (default true) in the `Validation` block. No other key.

## Python Contract

A module reports a rejected param by raising `ValueError` in `validate_use` ([[Module Contract]]); the shell turns it into a stage 7 error at the use's node. A module's runtime exceptions are caught by the shell, logged with the module name and UID, and do not stop others ([[Process Model and Threading#Failure and recovery]]). A module can log through `ctx.log` ([[Module Context]]) but does not format shell errors.

## Integration

- `jsonschema` (lazy, with a pass cache keyed by content hash and schema version; it validates the tree the TDL parser produces, and [[ADR-0011 JSON Schema for Shell Files]] is being rethought for TDL), the TDL parser, `difflib`, Loguru ([[JSON Schema and Editor Support]], [[Logging with Loguru]]).
- Threads: stages 1 to 7 run on the config watcher thread or before the loop at start; the loop only receives a finished result or a finished report ([[Process Model and Threading#Threads]]).
- TEL: the parser tells TEL where each `{{ }}` slot starts as an `Origin` (file, line, column, 1-based), so TEL errors point into the file and the shell adds no offset itself. A slot is on one line, so no indentation arithmetic is needed. This is the proposed requirement T17 in [[Expression Language Requirements]], not yet sent to the TEL project. #needs-verification

## Design

The printed form is plain text and works without colour. No icons, and no emoji ([[AGENTS#10. Writing style]]).

## Accessibility

A plain-text error is readable by a screen reader in a terminal. An error that stops the shell is also sent as a notification so a user who launched it from a menu sees it ([[Shell Start and Stop]]).

## Performance Budget

- A cached file costs a hash. A changed file costs a parse and a validation; a few milliseconds per hundred entries on this machine ([[JSON Schema and Editor Support#The `jsonschema` Dependency: Runtime, Not Only Development]]).
- Collecting up to 50 errors adds nothing the user feels; the cap protects the log.

## Failure Modes and Recovery

| Failure                                                     | Result                                                                                                                                       |
|-------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------|
| The validator itself fails (a schema that does not compile) | A shell error naming the schema; the shell falls back to its own checks of required keys and types ([[JSON Schema and Editor Support#Failure modes and recovery]]) |
| A file is huge or binary                                    | Stage 1 error naming the size or the encoding; the size limit is 1 MiB per TDL file (decided 2026-10-28, written for YAML files)                                    |
| An error cannot be mapped to a node                         | Reported at the nearest parent's line, with the path in the message                                                                          |
| Logging is not available                                    | The console still gets the error                                                                                                             |

## Open Questions

All seven were answered on 2026-10-28, as recommended.

1. [x] **Unknown keys are errors.**
2. [x] **Rule slugs in logs, no numeric codes.**
3. [x] **Stop at 50 errors.**
4. [x] **A notification for a failed start or reload,** opt-out.
5. [x] A `check` command (it needs the IPC and CLI note).
6. [x] **A size limit of 1 MiB per TDL file.**
7. [x] **Stage 5 only after every file passes stage 4.**

Raised by the move to TDL ([[ADR-0014 Shell File Language]]), not yet asked:

> [!question] Open for the maintainer
> - [ ] The TDL error list (rule slugs for syntax errors such as an unclosed brace or a `}}` written for two closing braces) is part of the TDL reference, once written.

Answered on 2026-10-30 ("Do all as you would recommend", [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]):

- [x] A property key repeated inside one block is an error naming both places (D9).
- [x] Boolean and null literals, and how unquoted words become numbers, for stage 4 types: the key's declared type decides (D2).
- [x] Stage 3 reads the metadata block first, then `TDL:`, then the file-type key, which picks the schema (D12). The error text for each rule is part of the TDL error list above.

## Acceptance Criteria

- [ ] A file with a TDL syntax error is reported with `file:line:column`, and no later stage runs for it.
- [ ] A file with no metadata block, no `TDL:`, or not exactly one file-type key is refused at stage 3 with an error naming the file; a file-type key that disagrees with the suffix is an error naming both.
- [ ] Two blocks with the same name in one `Children { }` load, in positional order (the YAML-era rule that rejected duplicate keys no longer applies).
- [ ] An unknown style key reports its line and column and offers the nearest key.
- [ ] A wrong-typed value reports the types allowed and what to write.
- [ ] A property key repeated in one block is reported as an error naming both places.
- [ ] A file with six deliberate mistakes yields six errors, each at the right line and column ([[JSON Schema and Editor Support#Acceptance criteria]]).
- [ ] A module key that names nothing registered reports the nearest names.
- [ ] A TEL error reports the file line and the column inside the expression.
- [ ] At start any error stops the shell with code 1 and nothing opens; on a reload the old state keeps running.
- [ ] A warning never stops the shell.
- [ ] The log record of each finding carries `file`, `line`, `column`, `rule` and `severity`.
- [ ] No error is reported twice by two stages.
- [ ] A `{{ }}` slot with an error in its expression reports the file line and the column of the error inside the slot, using the `Origin` the parser gave TEL.

## Links

- [[Runtime]] · [[Common Keys and Conventions]] · [[JSON Schema and Editor Support]] · [[Config Discovery and Registry]] · [[Hot Reload]] · [[Shell Start and Stop]]
