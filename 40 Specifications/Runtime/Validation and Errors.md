---
title: Validation and Errors
aliases: [Error Reporting, Validation Pipeline, file:line:column]
type: spec
status: review
owner: phil
created: 2026-10-28
updated: 2026-10-28
tags: [spec/runtime, needs-verification]
related: ["[[Runtime]]", "[[Common Keys and Conventions]]", "[[JSON Schema and Editor Support]]", "[[ADR-0011 JSON Schema for Shell Files]]", "[[Config Discovery and Registry]]", "[[Hot Reload]]", "[[Shell Start and Stop]]", "[[Expression Language Requirements]]"]
depends_on: ["[[ADR-0011 JSON Schema for Shell Files]]", "[[Common Keys and Conventions]]"]
---

# Validation and Errors

> [!summary]
> Every problem the shell finds in a file is reported with the file, line and column, says what is wrong and what to write, and goes to the console and the log. Checking runs in stages, from the file's bytes to a running module. At start any error stops the shell; on a reload any error keeps the old state ([[Process Model and Threading#Lifecycle (proposed)]]). Decided: `file:line:column` ([[AGENTS#3. Layering principle]]), JSON Schema for structure ([[ADR-0011 JSON Schema for Shell Files]]), the schema cache ([[JSON Schema and Editor Support]]), a bad `settings.yaml` stops the shell ([[Settings File]]). Everything else is proposed with a recommendation.

## Purpose and Scope

- One pipeline and one error format for all five file types, the settings file and the Python modules.
- Not in this note: what the keys mean ([[41 YAML Reference]]), the JSON Schema files themselves ([[JSON Schema and Editor Support]]), and TEL's own grammar ([[Expression Language Requirements]]).

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
| 2. Parse       | YAML syntax; no duplicate keys; only plain data (no tags that build objects)             | PyYAML's safe loader with a strict mapping rule                  | The YAML node marks                                                   |
| 3. Header      | `shell:` present and a known version; `type:` agrees with the suffix; `UID:` well formed | The shell                                                        | The key's node                                                        |
| 4. Schema      | Types, enums, required keys, unknown keys, value forms (colour, four-sided, size)        | `jsonschema`, draft-07 ([[ADR-0011 JSON Schema for Shell Files]]) | The node at the error's path                                          |
| 5. Semantic    | Rules a schema cannot say (below)                                                        | The shell                                                        | The node at the offending key or value                                |
| 6. Expressions | TEL compiles; every name it reads is known                                               | TEL                                                              | The expression's position inside the YAML string                      |
| 7. Modules     | The `.py` imports; it holds one `Module` class; `validate_use` accepts each use          | Python                                                           | The traceback line for the `.py`; the use's node for a rejected param |
| 8. Run time    | An expression that fails to evaluate; a module callback that raises; a tre error         | The shell                                                        | The node or module that ran                                           |

- Unknown keys are errors, not warnings, to catch typos (decided 2026-10-28).
- **A file that fails stage 2 or 3 is not checked further,** because later stages need its data; other files continue. Stage 5 runs only when every file has passed stage 4, because it compares across files (decided 2026-10-28).
- **Stages 1 to 7 run before anything is shown** at start, and before anything is applied on a reload ([[Hot Reload]]). Stage 8 happens while running.

### Parsing

- PyYAML keeps the last of two equal keys silently. A test on 2026-10-28 loaded `children:` with two `Clock:` keys and got one. The shell's loader raises on a duplicate and names both lines (`duplicate key 'Clock' (first at line 2)`, at line 4). This matters because a module is called by its name as the key ([[Module File#Using a module]]).
- The loader builds only plain data: mappings, lists, strings, numbers, booleans and null. It never constructs objects from tags, so a file cannot run code. Recommendation; it is the safe-loader rule.
- The loader keeps the node tree beside the data, so any path in the data maps to a line and column. A spike on 2026-10-27 did this with PyYAML's `compose` marks and got errors at the right place ([[JSON Schema and Editor Support#Findings from a spike (2026-10-27)]]).
- Columns are 1-based and count characters, as editors do.

### Semantic Checks

Rules a schema cannot say, with the note that owns each:

| Rule                                                                                                                       | Owner                                                                                                                     |
|----------------------------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------|
| A name is unique across the shell; a name used as a reference exists                                                       | [[Config Discovery and Registry#Names]], [[Common Keys and Conventions#Names and references]]                                          |
| No import cycle; every imported file exists                                                                                | [[Config Discovery and Registry#Discovery]]                                                                                   |
| A module key names a registered module, or a block; a module's params have the declared types; `validate_use` accepts them | [[Module File]], [[Module Contract]]                                          |
| A token `$group.name` exists in the active theme                                                                           | [[Style Schema#Theme tokens]]                                                                                   |
| `exclusive_zone` only on `layer: top`; a Bar has no margin that breaks its zone; thickness forms are valid                 | [[Surface Types#Layers per kind]], [[Bar]], [[Frame]] |
| `attach_to` and `anchor_to` resolve; a Panel's target is a surface, a module or a Panel                                    | [[Panel]], [[Popup]]                                          |
| `auto_hide` and `reveal_key` are consistent                                                                                | [[Bar#Auto-hide (decided 2026-10-27)]]                                                                                   |
| The Python for a module exists, next to its YAML                                                                           | [[Module File]]                                                                                   |
| A file in `Shells/` and its imports agree on the monitor rule                                                              | [[Shell File#Monitors]]                                                                                   |

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
Shells/Main_Shell.yaml:12:9: error: unknown style key 'colour' on bar 'top_bar'
    12 |         colour: red
       |         ^
    hint: did you mean 'border_color'?
```

- **Nearest names** come from `difflib.get_close_matches` in the standard library. A test on 2026-10-28 gave `border_color` for the typo `colour` and for `border_colour`.
- **Say what to write.** A message names the wrong thing, then the right form: `a colour is "#RRGGBB", "#RRGGBBAA" or RGBA(r, g, b, a)` ([[Common Keys and Conventions#Errors]]).
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

A bad `settings.yaml` always stops the shell at start (decided 2026-10-27) and keeps the running settings on a reload.

## Configuration

`settings.yaml`: `validation` with `enabled` (default true) and the cache location ([[Settings File]]). Proposed additions: `validation.max_errors` (default 50) and `validation.notify` (default true). No other key.

## Python Contract

A module reports a rejected param by raising `ValueError` in `validate_use` ([[Module Contract]]); the shell turns it into a stage 7 error at the use's node. A module's runtime exceptions are caught by the shell, logged with the module name and UID, and do not stop others ([[Process Model and Threading#Failure and recovery]]). A module can log through `ctx.log` ([[Module Context]]) but does not format shell errors.

## Integration

- `jsonschema` (lazy, with a pass cache keyed by content hash and schema version), PyYAML, `difflib`, Loguru ([[JSON Schema and Editor Support]], [[Logging with Loguru]]).
- Threads: stages 1 to 7 run on the config watcher thread or before the loop at start; the loop only receives a finished result or a finished report ([[Process Model and Threading#Threads]]).
- TEL: errors arrive with a line and column inside the expression string; the shell adds the string's position ([[Expression Language Requirements]]). For a multi-line string the offset needs the node's start mark and indentation. #needs-verification

## Design

The printed form is plain text and works without colour. No icons, and no emoji ([[AGENTS#10. Writing style]]).

## Accessibility

A plain-text error is readable by a screen reader in a terminal. An error that stops the shell is also sent as a notification so a user who launched it from a menu sees it ([[Shell Start and Stop]]).

## Performance Budget

- A cached file costs a hash. A changed file costs a parse and a validation; a few milliseconds per hundred entries on this machine ([[JSON Schema and Editor Support#The `jsonschema` dependency runtime, not only development]]).
- Collecting up to 50 errors adds nothing the user feels; the cap protects the log.

## Failure Modes and Recovery

| Failure                                                     | Result                                                                                                                                       |
|-------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------|
| The validator itself fails (a schema that does not compile) | A shell error naming the schema; the shell falls back to its own checks of required keys and types ([[JSON Schema and Editor Support#Failure modes and recovery]]) |
| A file is huge or binary                                    | Stage 1 error naming the size or the encoding; the size limit is 1 MiB per YAML file (decided 2026-10-28)                                    |
| An error cannot be mapped to a node                         | Reported at the nearest parent's line, with the path in the message                                                                          |
| Logging is not available                                    | The console still gets the error                                                                                                             |

## Open Questions

All seven were answered on 2026-10-28, as recommended.

1. [x] **Unknown keys are errors.**
2. [x] **Rule slugs in logs, no numeric codes.**
3. [x] **Stop at 50 errors.**
4. [x] **A notification for a failed start or reload,** opt-out.
5. [x] A `check` command (it needs the IPC and CLI note).
6. [x] **A size limit of 1 MiB per YAML file.**
7. [x] **Stage 5 only after every file passes stage 4.**

## Acceptance Criteria

- [ ] A file with a YAML syntax error is reported with `file:line:column`, and no later stage runs for it.
- [ ] A `children:` mapping with two equal keys is rejected with both lines named.
- [ ] An unknown style key reports its line and column and offers the nearest key.
- [ ] A wrong-typed value reports the types allowed and what to write.
- [ ] A file with six deliberate mistakes yields six errors, each at the right line and column ([[JSON Schema and Editor Support#Acceptance criteria]]).
- [ ] A module key that names nothing registered reports the nearest names.
- [ ] A TEL error reports the file line and the column inside the expression.
- [ ] At start any error stops the shell with code 1 and nothing opens; on a reload the old state keeps running.
- [ ] A warning never stops the shell.
- [ ] The log record of each finding carries `file`, `line`, `column`, `rule` and `severity`.
- [ ] No error is reported twice by two stages.

## Links

- [[Runtime]] · [[Common Keys and Conventions]] · [[JSON Schema and Editor Support]] · [[Config Discovery and Registry]] · [[Hot Reload]] · [[Shell Start and Stop]]
