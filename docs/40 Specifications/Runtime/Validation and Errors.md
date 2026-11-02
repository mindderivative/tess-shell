---
title: Validation and Errors
aliases: [Error Reporting, Validation Pipeline, file:line:column]
type: spec
status: review
owner: phil
created: 2026-10-28
updated: 2026-10-30
tags: [spec/runtime, needs-verification]
---

# Validation and Errors

> [!NOTE]
> Every problem the shell finds in a file is reported with the file, line and column, says what is wrong and what to write, and goes to the console and the log. Checking runs in stages, from the file's bytes to a running module. At start any error stops the shell; on a reload any error keeps the old state ([Process Model and Threading > Lifecycle (proposed)](../../20%20Architecture/Process%20Model%20and%20Threading.md#lifecycle-proposed)). Decided: `file:line:column` (AGENTS > 3. Layering principle), JSON Schema for structure ([ADR-0011 JSON Schema for Shell Files](../../30%20Decisions/ADR-0011%20JSON%20Schema%20for%20Shell%20Files.md)), the schema cache ([JSON Schema and Editor Support](../../41%20TDL%20Reference/JSON%20Schema%20and%20Editor%20Support.md)), a bad `settings.tdl` stops the shell ([Settings File](../../41%20TDL%20Reference/Settings%20File.md)). Everything else is proposed with a recommendation.

## Purpose and Scope

- One pipeline and one error format for all five file types, the settings file and the Python modules.
- Not in this note: what the keys mean (the TDL reference, folder [41 TDL Reference](../../41%20TDL%20Reference/41%20TDL%20Reference.md)), the JSON Schema files themselves ([JSON Schema and Editor Support](../../41%20TDL%20Reference/JSON%20Schema%20and%20Editor%20Support.md)), and TEL's own grammar ([Expression Language Requirements](Expression%20Language%20Requirements.md)).

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
| 2. Parse       | TDL syntax; the tree is an ordered list of entries (head, properties, children) that keeps repeated names (D12); it holds only blocks, properties, lists and literal values; `{{ }}` slots are kept as text for stage 6 | The shell's TDL parser ([ADR-0014 Shell File Language](../../30%20Decisions/ADR-0014%20Shell%20File%20Language.md))        | The parser's own positions                                            |
| 3. Header      | The loader reads the metadata block first, then the root block, which picks the schema (D12). The metadata block is present; `TDL:` is present with a known version; `Name:` is present and follows the name rules (letters, digits and `_`, starting with a letter); the minimum version pins (`TEL:`, `TRE:`, `Shell:`) are met; exactly one root block (`Shell`, `Module`, `Style`, `Stylesheet`, `Theme`); the root block agrees with the suffix; `UID:` well formed | The shell                                                        | The key's or the root block's node                                    |
| 4. Schema      | The schema picked at stage 3 validates the metadata part and the block part (D12). Types, enums (upper case: `Edge: top` is refused with a hint to write `TOP`), required keys, unknown keys (the metadata block's other keys are kept and ignored), value forms (colour, four-sided in the order left, top, right, bottom, size) | `jsonschema`, draft-07 ([ADR-0011 JSON Schema for Shell Files](../../30%20Decisions/ADR-0011%20JSON%20Schema%20for%20Shell%20Files.md)) | The tree node at the error's path                                       |
| 5. Semantic    | Rules a schema cannot say (below)                                                        | The shell                                                        | The node at the offending key or value                                |
| 6. Expressions | TEL compiles; every name it reads is known                                               | TEL                                                              | The slot's `Origin` (file, line, column) from the parser              |
| 7. Modules     | The `.py` imports; it holds one `Module` class; `validate_use` accepts each use          | Python                                                           | The traceback line for the `.py`; the use's node for a rejected param |
| 8. Run time    | An expression that fails to evaluate; a module callback that raises; a tre error         | The shell                                                        | The node or module that ran                                           |

- Unknown keys are errors, not warnings, to catch typos (decided 2026-10-28). The exception is the metadata block, where other keys are allowed and the shell ignores them ([TDL Language > The Metadata Block](../../41%20TDL%20Reference/TDL%20Language.md#the-metadata-block)).
- **Stage 3 errors** name the file and say which rule failed: no metadata block, no `TDL:`, no `Name:`, a bad `Name:`, no root block or more than one, or the root block and the suffix disagree (the error names both; the root block is authoritative, [TDL Language > The Root Block](../../41%20TDL%20Reference/TDL%20Language.md#the-root-block)). The proposed codes and hints (`tdl-no-metadata`, `tdl-no-version`, `tdl-no-name`, `tdl-bad-name`, `tdl-no-root`, `tdl-many-roots`, `tdl-root-suffix` and the others) are in [TDL Language > Errors](../../41%20TDL%20Reference/TDL%20Language.md#errors); this note does not copy them.
- **A file that fails stage 2 or 3 is not checked further,** because later stages need its data; other files continue. Stage 5 runs only when every file has passed stage 4, because it compares across files (decided 2026-10-28).
- **Stages 1 to 7 run before anything is shown** at start, and before anything is applied on a reload ([Hot Reload](Hot%20Reload.md)). Stage 8 happens while running.

### Parsing

- The parser is the shell's own, in a module that imports nothing from the shell ([ADR-0014 Shell File Language > What TDL Is (Decided)](../../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#what-tdl-is-decided), item 9). Its syntax errors carry `file:line:column` directly. There is no third-party parser, so no marks to translate.
- The same block name may repeat in one `Children { }`, ordered by position, so a repeated module call is not an error ([Module File > Using a module](../../41%20TDL%20Reference/Module%20File.md#using-a-module)). A property key repeated in one block is an error naming both places (D9, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)); the stage 5 rule is in the table below.
- The tree holds structure and literal values only. A file cannot run code: TDL has no statements, variables or tags, and every `{{ }}` slot is handed to TEL, which is sandboxed ([Expression Language Requirements](Expression%20Language%20Requirements.md)).
- The tree is lossless: it keeps comments and layout, and every node knows its line and column, so any path in the data maps to a position. This replaces the earlier YAML design, which kept PyYAML's `compose` node marks beside the data (spike of 2026-10-27, [JSON Schema and Editor Support > Findings from a spike (2026-10-27)](../../41%20TDL%20Reference/JSON%20Schema%20and%20Editor%20Support.md#findings-from-a-spike-2026-10-27)).
- Columns are 1-based and count characters, as editors do.
- No language server in v1, so these printed errors are the author's main feedback ([ADR-0014 Shell File Language > What TDL Is (Decided)](../../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#what-tdl-is-decided), item 10). A small TextMate grammar gives highlighting only.
- `true`, `false` and `null` are lowercase bare words, and `[]` is the empty list. The parser keeps a bare word as a string, so stage 4 sees `Hidden: true` as the string `true` and the key's declared type in the schema turns it into a boolean, number or null (D2, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)).

### Semantic Checks

Rules a schema cannot say, with the note that owns each:

| Rule                                                                                                                       | Owner                                                                                                                     |
|----------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| A property key appears once in a block; a repeat is an error naming both places (D9; repeated block names are allowed) | [TDL Language > Punctuation](../../41%20TDL%20Reference/TDL%20Language.md#punctuation) |
| A name is registered once (one registry for blocks, surface types and modules; a user module overrides a shipped one); a name used as a reference exists | [Config Discovery and Registry > Names](Config%20Discovery%20and%20Registry.md#names), [Common Keys and Conventions > Names and references](../../41%20TDL%20Reference/Common%20Keys%20and%20Conventions.md#names-and-references)                                          |
| No import cycle; every imported file exists                                                                                | [Config Discovery and Registry > Discovery](Config%20Discovery%20and%20Registry.md#discovery)                                                                                   |
| A block head names a registered block, surface type or module; a module's params have the declared types; `validate_use` accepts them | [Module File](../../41%20TDL%20Reference/Module%20File.md), [Module Contract](../../42%20Python%20API/Module%20Contract.md)                                          |
| A token `$group.name` exists in the active theme                                                                           | [Style Schema > Theme tokens](../../41%20TDL%20Reference/Style%20Schema.md#theme-tokens)                                                                                   |
| `Exclusive_Zone` only on `Layer: TOP`; a Bar resolves to a size above 0 on the axis it is attached along (a Bar that resolves to 0, for example a top Bar with `Height: EXPAND` and no `Max_Height` or `Min_Height`, is not created: a warning names the Bar and says to set `Min_Height`; the check is at creation and never stops hide, peek, expand or contract of a Bar or Frame strip); a Frame or Panel `Margin` agrees with the meld rule (a Panel attached to a Frame with a `Margin` on the sides facing the Frame does not meld, with none it melds; a Frame's `Margin` adds to its total size) | [Surface Types > Layers per kind](../Surfaces/Surface%20Types.md#layers-per-kind), [Bar](../Surfaces/Bar.md), [Frame](../Surfaces/Frame.md), [Panel](../Surfaces/Panel.md) |
| Names follow the rules (letters, digits and `_`, starting with a letter); enum values are upper case; the root block agrees with the suffix | [TDL Language > Names and the Registry](../../41%20TDL%20Reference/TDL%20Language.md#names-and-the-registry), [TDL Language > The Root Block](../../41%20TDL%20Reference/TDL%20Language.md#the-root-block) |
| `Attach_To` and `Anchor_To` resolve; a Panel's target is a surface, a module or a Panel                                    | [Panel](../Surfaces/Panel.md), [Popup](../Surfaces/Popup.md)                                          |
| `Auto_Hide` and `Reveal_Key` are consistent                                                                                | [Bar > Auto-hide (decided 2026-10-27)](../Surfaces/Bar.md#auto-hide-decided-2026-10-27)                                                                                   |
| The Python for a module exists, next to its TDL                                                                           | [Module File](../../41%20TDL%20Reference/Module%20File.md)                                                                                   |
| Two `Monitor` blocks do not name the same monitor; a `Monitor` with no selector is ignored (not an error); the files agree on the monitor rules | [Shell File > Monitors](../../41%20TDL%20Reference/Shell%20File.md#monitors)                                                                                   |

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
- **Say what to write.** A message names the wrong thing, then the right form: `a colour is "#RRGGBB", "#RRGGBBAA" or rgba(r g b a)` ([Common Keys and Conventions > Errors](../../41%20TDL%20Reference/Common%20Keys%20and%20Conventions.md#errors)).
- **Severity.** An `error` refuses the file or the load. A `warning` never stops anything (a target that disappeared, a rebuilt registry record, a stale cache). An `info` is a note (an ignored file, a configured directory overriding the default).

### How Many Errors, and in what Order

- Every error from a stage is reported, sorted by file and line, not only the first, so a user fixes a file in one pass. A cap of 50 per run, then a line saying how many more were found (decided 2026-10-28).
- Errors from different files at the same stage are all reported. Stages after a failed stage are not run for the files they depend on.

### Where it Goes

| Place                  | What                                                                                                                          | When                                                                                                                      |
|------------------------|-------------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| Console (stderr)       | The printed form, in colour when it is a terminal                                                                             | Always                                                                                                                    |
| The log file           | One record per finding, with `file`, `line`, `column`, `rule`, `severity` as fields ([Settings File > Log files](../../41%20TDL%20Reference/Settings%20File.md#log-files)) | Always                                                                                                                    |
| A desktop notification | A short summary and the first error                                                                                           | A failure that stops the shell, or a failed reload; opt-out (decided 2026-10-28, [Shell Start and Stop > Accessibility](Shell%20Start%20and%20Stop.md#accessibility)) |
| The command `check`    | The same output, no shell started, exit code 1 on any error                                                                   | On demand (the IPC and CLI note, to write)                                                                                |

### What a Failure Does

| When                   | Error                                                                                        | Warning                        |
|------------------------|----------------------------------------------------------------------------------------------|--------------------------------|
| Start                  | The shell stops with exit code 1 ([Shell Start and Stop > Exit codes](Shell%20Start%20and%20Stop.md#exit-codes))                   | Printed; the shell continues   |
| Reload                 | The old state is kept and the error is reported ([Hot Reload](Hot%20Reload.md))    | Printed; the new state applies |
| Stage 8, while running | Logged with the node or module; the node shows its fallback, the rest of the shell continues | Logged                         |

A bad `settings.tdl` always stops the shell at start (decided 2026-10-27) and keeps the running settings on a reload.

## Configuration

`settings.tdl`: `Validation` with `Enabled` (default true) and the cache location ([Settings File](../../41%20TDL%20Reference/Settings%20File.md)). Proposed additions: `Max_Errors` (default 50) and `Notify` (default true) in the `Validation` block. No other key.

## Python Contract

A module reports a rejected param by raising `ValueError` in `validate_use` ([Module Contract](../../42%20Python%20API/Module%20Contract.md)); the shell turns it into a stage 7 error at the use's node. A module's runtime exceptions are caught by the shell, logged with the module name and UID, and do not stop others ([Process Model and Threading > Failure and recovery](../../20%20Architecture/Process%20Model%20and%20Threading.md#failure-and-recovery)). A module can log through `ctx.log` ([Module Context](../../42%20Python%20API/Module%20Context.md)) but does not format shell errors.

## Integration

- `jsonschema` (lazy, with a pass cache keyed by content hash and schema version; it validates the tree the TDL parser produces, and [ADR-0011 JSON Schema for Shell Files](../../30%20Decisions/ADR-0011%20JSON%20Schema%20for%20Shell%20Files.md) is being rethought for TDL), the TDL parser, `difflib`, Loguru ([JSON Schema and Editor Support](../../41%20TDL%20Reference/JSON%20Schema%20and%20Editor%20Support.md), [Logging with Loguru](../../90%20Research/Logging%20with%20Loguru.md)).
- Threads: stages 1 to 7 run on the config watcher thread or before the loop at start; the loop only receives a finished result or a finished report ([Process Model and Threading > Threads](../../20%20Architecture/Process%20Model%20and%20Threading.md#threads)).
- TEL: the parser tells TEL where each `{{ }}` slot starts as an `Origin` (file, line, column, 1-based), so TEL errors point into the file and the shell adds no offset itself. A slot is on one line, so no indentation arithmetic is needed. This is the proposed requirement T17 in [Expression Language Requirements](Expression%20Language%20Requirements.md), not yet sent to the TEL project. #needs-verification

## Design

The printed form is plain text and works without colour. No icons, and no emoji (AGENTS > 10. Writing style).

## Accessibility

A plain-text error is readable by a screen reader in a terminal. An error that stops the shell is also sent as a notification so a user who launched it from a menu sees it ([Shell Start and Stop](Shell%20Start%20and%20Stop.md)).

## Performance Budget

- A cached file costs a hash. A changed file costs a parse and a validation; a few milliseconds per hundred entries on this machine ([JSON Schema and Editor Support > The `jsonschema` Dependency: Runtime, Not Only Development](../../41%20TDL%20Reference/JSON%20Schema%20and%20Editor%20Support.md#the-jsonschema-dependency-runtime-not-only-development)).
- Collecting up to 50 errors adds nothing the user feels; the cap protects the log.

## Failure Modes and Recovery

| Failure                                                     | Result                                                                                                                                       |
|-------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------|
| The validator itself fails (a schema that does not compile) | A shell error naming the schema; the shell falls back to its own checks of required keys and types ([JSON Schema and Editor Support > Failure modes and recovery](../../41%20TDL%20Reference/JSON%20Schema%20and%20Editor%20Support.md#failure-modes-and-recovery)) |
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

Raised by the move to TDL ([ADR-0014 Shell File Language](../../30%20Decisions/ADR-0014%20Shell%20File%20Language.md)), not yet asked:

> [!NOTE]
> **Open for the maintainer**
> - [ ] The TDL error list (rule slugs for syntax errors such as an unclosed brace or a `}}` written for two closing braces) is a proposal in [TDL Language > Errors](../../41%20TDL%20Reference/TDL%20Language.md#errors); the maintainer has not decided it.

Answered on 2026-10-30 ("Do all as you would recommend", [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)):

- [x] A property key repeated inside one block is an error naming both places (D9).
- [x] Boolean and null literals, and how unquoted words become numbers, for stage 4 types: the key's declared type decides (D2).
- [x] Stage 3 reads the metadata block first, then `TDL:`, then the root block, which picks the schema (D12, with the file-type key replaced by the root block). The error text for each rule is part of the TDL error list in [TDL Language > Errors](../../41%20TDL%20Reference/TDL%20Language.md#errors).

## Acceptance Criteria

- [ ] A file with a TDL syntax error is reported with `file:line:column`, and no later stage runs for it.
- [ ] A file with no metadata block, no `TDL:`, no `Name:`, or not exactly one root block is refused at stage 3 with an error naming the file; a root block that disagrees with the suffix is an error naming both.
- [ ] A `Name:` with a `-` or a leading digit is refused with an error that says which characters are allowed.
- [ ] `Edge: top` is refused with an error that says enum values are upper case.
- [ ] A Bar that resolves to size 0 on its attached axis is not created and the warning names the Bar and says to set `Min_Height`; hiding and revealing a Bar is not stopped by this check.
- [ ] Two blocks with the same name in one `Children { }` load, in positional order (the YAML-era rule that rejected duplicate keys no longer applies).
- [ ] An unknown style key reports its line and column and offers the nearest key.
- [ ] A wrong-typed value reports the types allowed and what to write.
- [ ] A property key repeated in one block is reported as an error naming both places.
- [ ] A file with six deliberate mistakes yields six errors, each at the right line and column ([JSON Schema and Editor Support > Acceptance criteria](../../41%20TDL%20Reference/JSON%20Schema%20and%20Editor%20Support.md#acceptance-criteria)).
- [ ] A module key that names nothing registered reports the nearest names.
- [ ] A TEL error reports the file line and the column inside the expression.
- [ ] At start any error stops the shell with code 1 and nothing opens; on a reload the old state keeps running.
- [ ] A warning never stops the shell.
- [ ] The log record of each finding carries `file`, `line`, `column`, `rule` and `severity`.
- [ ] No error is reported twice by two stages.
- [ ] A `{{ }}` slot with an error in its expression reports the file line and the column of the error inside the slot, using the `Origin` the parser gave TEL.

## Links

- [Runtime](Runtime.md) · [Common Keys and Conventions](../../41%20TDL%20Reference/Common%20Keys%20and%20Conventions.md) · [JSON Schema and Editor Support](../../41%20TDL%20Reference/JSON%20Schema%20and%20Editor%20Support.md) · [Config Discovery and Registry](Config%20Discovery%20and%20Registry.md) · [Hot Reload](Hot%20Reload.md) · [Shell Start and Stop](Shell%20Start%20and%20Stop.md)
