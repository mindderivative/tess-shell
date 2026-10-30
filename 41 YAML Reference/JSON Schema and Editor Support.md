---
title: JSON Schema and Editor Support
aliases: [Shell JSON Schema, YAML Schema Files, TDL Schema Files, Editor Support]
type: yaml-ref
status: draft
owner: phil
created: 2026-10-27
updated: 2026-10-29
tags: [yaml-ref, tooling, needs-verification]
related: ["[[41 YAML Reference]]", "[[Style Schema]]", "[[Common Keys and Conventions]]", "[[Module File]]", "[[Shell File]]", "[[Building Blocks]]", "[[ADR-0011 JSON Schema for Shell Files]]", "[[ADR-0014 Shell File Language]]"]
depends_on: ["[[ADR-0011 JSON Schema for Shell Files]]"]
---

# JSON Schema and Editor Support

> [!summary]
> The shell publishes JSON Schema files for its shell files. The shell validates the parsed tree against them at load and on hot reload. The schemas are generated from the block and module declarations, so the reference and the code cannot drift. [[ADR-0011 JSON Schema for Shell Files]] (accepted 2026-10-27) also relied on the YAML language server for completion and hover in editors; shell files are now TDL ([[ADR-0014 Shell File Language]]), so that part no longer applies. There is no language server in v1, and a small TextMate grammar (syntax highlighting) ships with v1. The details below are proposed.

> [!important] Revised for TDL, 2026-10-29
> What still holds: schemas generated from block and module declarations; the shell validates the parsed tree at load and on reload; semantic checks stay in the shell; the `jsonschema` cost and cache. What no longer applies: the Red Hat YAML extension, modelines, `yaml.schemas` globs and the language server's completion, hover and diagnostics. [[ADR-0011 JSON Schema for Shell Files]] is being revisited by the maintainer (the agent does not edit ADRs). Everything about editor feedback beyond highlighting is an open item in [[#Open]]. The spike findings below were measured on YAML, 2026-10-27, and are kept as dated findings.

## What the Editor and the Shell Each Get

| Consumer                | Uses the schema for                                                                                                  | Notes                                                                                                                                                                                                                                      |
|-------------------------|----------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Editor                  | Syntax highlighting from a small TextMate grammar in v1. No completion, hover or schema diagnostics in v1            | ADR-0014 decides: no language server in v1, TextMate grammar in v1 ([[ADR-0014 Shell File Language#What TDL Is (Decided)]]). The grammar's content comes from the TDL reference, once written. Whether any editor feature ever reads the JSON Schema is open |
| Shell                   | Structural validation of the parsed tree at load and hot reload: types, enums, required keys, unknown keys           | The TDL parser is the shell's own, so errors carry `file:line:column` from that parser ([[AGENTS#3. Layering principle]], [[ADR-0014 Shell File Language]])                                                                                  |
| Not the schema's job    | Unique names across the shell, registry references, import cycles, token existence, expression syntax                | Semantic checks run after the schema passes ([[Common Keys and Conventions#Errors]]). An expression slot is a plain string to the schema; TEL checks it                                                                                      |

## Associating a Schema with a File

This section described the YAML language server: a `# yaml-language-server: $schema=...` modeline, `yaml.schemas` globs and a `$schema` key. All three are specific to that server and a TDL file has no such mechanism, so they are dropped (measured on YAML and read from the server's README on 2026-10-27, [README](https://github.com/redhat-developer/yaml-language-server)).

The shell itself picks the schema from the file-type key in the file's metadata block (`Shell:`, `Module:`, `Style:`, `Stylesheet:` or `Theme:`, [[TDL Language#The Metadata Block]]), so it needs no association. For an editor the question is open ([[#Open]]): with no language server in v1 there is nothing to associate. The `*_Shell.tdl`, `*_Module.tdl`, `*_Style.tdl`, `*_Theme.tdl` and `*_Stylesheet.tdl` suffixes still give clean globs for any later tool.

Draft decided 2026-10-27: draft-07 keywords (`definitions`, `if`/`then`/`else`, `enum`, `const`, `patternProperties`) and the shell validates with the same draft. The reason given then was that any editor version works; with no editor consumer in v1 the choice stands for the shell's own validator, and is open to revisit with ADR-0011.

## Where the Schemas Live

Decided 2026-10-27 (replacing the project-root `.shell/schemas/` of earlier the same day): the shell's config directory, `$HOME/.config/tesserae-shell/schemas/` ([[ADR-0007 Shell UI Layer#Config directory and registry (2026-10-25)]]). The generator writes every schema the shell uses into that folder: copies of the shipped ones (pinned to the shell version that wrote them) and the generated project schema. The decision was made so a YAML modeline could point at that folder; with no modeline, whether the folder is still needed on disk is open ([[#Open]]).

- **Ignored by version control** (decided 2026-10-27): the folder is generated, so the shell writes a `.gitignore` containing `*` inside it. A user who keeps the config directory in git then never commits the schemas.
- **Modeline path.** Dropped with the modeline (it was a YAML language server feature). Files that `settings.tdl` places outside the config directory ([[Settings File]]) need no schema path.

## Files

| Schema                                                             | For                                                                                                   | Shipped or generated                                                            |
|--------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------|---------------------------------------------------------------------------------|
| `shell.schema.json`                                                | Files with the `Shell:` key: monitors, surfaces, children                                             | Shipped, per format version (`Shell: v1` maps to a `v1` folder and `$id`)       |
| `module.schema.json`                                               | Files with the `Module:` key: params, layout, style                                                   | Shipped                                                                         |
| `settings.schema.json`                                             | The config directory's `settings.tdl` ([[Settings File]]); its file-type key is not decided         | Shipped                                                                         |
| `style.schema.json`, `theme.schema.json`, `stylesheet.schema.json` | The three look files ([[Style Schema]])                                        | Shipped; the theme token enums are filled in by generation                      |
| `definitions.schema.json`                                          | Shared definitions: colour, four-sided values, size, token reference, shadow, each block's properties | Generated from the block declarations ([[Building Blocks#Properties, parts and states]]) |
| `project.schema.json`                                              | One config directory: which module names exist and their `params`                                     | Generated from the module files in the config directory and the registry        |

The six file-type schemas are told apart by which file-type key the metadata block has. The parsed tree has two parts: a metadata part (the keys between the `---` lines, including `TDL:`, the file-type key, `UID:` and any user keys) and a block part (the blocks that follow). Each file-type schema requires its own key in the metadata part (`required: [Shell]` for `shell.schema.json`, and so on) and exactly one of the five, then validates the block part with its `if`/`then` branches; unknown metadata keys are allowed ([[ADR-0014 Shell File Language#Layout Rules]], items 1, 2 and 14). The suffix check (a mismatch with the file-type key is a load error) is the loader's, not the schema's. Whether the metadata part is validated by the schema or by the loader is open ([[#Open]]).

## Why a Generated Project Schema

A module is called by its name as the block head, with params beneath ([[Module File#Using a module]]). A static schema cannot know which names a user's shell defines. The generated project schema lists each module name as an allowed head in `Children` with that module's `Params` as its value schema, so the schema checks each module call's params. Block entries (a built-in block name as the head, such as `Text`) fall through to the block branches; both kinds of name come from the one registry ([[TDL Language#Names and the Registry]]). This was written for YAML mappings; in TDL the same name may repeat in one `Children { }`, ordered by position, so the shape of the parsed tree and of `Children` in the schema is open ([[#Open]]). Completion of module names is an editor feature and is not in v1. The shell regenerates the project schema when the registry changes ([[ADR-0007 Shell UI Layer#Config directory and registry (2026-10-25)]]); the command is proposed as `tesserae-shell schema`.

## Findings from a Spike (2026-10-27)

Measured on YAML, 2026-10-27. These are dated findings from before ADR-0014; the shell now parses TDL with its own parser, so the position step below is replaced and the rest needs a re-check on a TDL tree.

A throwaway script in /tmp (not in the vault) validated a sample shell file with Python `jsonschema` 4.26.0 and located each error in the file with PyYAML's `compose` marks (PyYAML 6.0.3, Python 3.14.8).

- **Line and column work.** An error's path maps to a node mark; output looked like `bad.yaml:6:16: children/bar_top/style: Additional properties are not allowed ('colour' was unexpected)`. The library gives paths, not positions, so the shell must keep the composed node tree next to the data. With TDL the parser's lossless tree is that node tree ([[ADR-0014 Shell File Language#What TDL Is (Decided)]], item 13); the mapping from a schema path to a position in it is still to be built.
- **A choice between branches hides the real error.** With each entry as a `oneOf` of "block entry" or "module call", a typo deep in one entry produced a single error at the entry ("not valid under any of the given schemas") and `best_match` chose an unrelated deeper error. Recommendation: dispatch with `if`/`then` on the key that names the branch (`block` equal to `Text`, and so on, in the YAML sample; in TDL the block head names the branch) instead of `oneOf`. The same sample then gave six errors, each at the right line and column: an unknown `txt` key, an unknown block `Hexagon`, a wrong type, an out-of-range `elevation`, an unknown `colour` style key and a four-sided value of the wrong length. The language server's own diagnostics for `oneOf` were not tested, and no longer matter in v1. #needs-verification
- `additionalProperties: false` is only correct inside an `if`/`then` branch that lists every allowed property; the generation step must emit complete property lists, including shared keys such as `Style` and `Children`.

## Generation

- Every block and module declares its properties (type, default, choices, doc), parts and states in Python; the generator turns them into the property schemas, with the doc line as `description` ([[Style Schema#Principles]]).
- The theme token groups become `enum` lists in the reference form `$group.name` for completion; token existence is also checked by the shell after loading ([[Style Schema#Theme tokens]]).
- Schemas are build artefacts. They ship in the package and regenerate for a config directory; nobody edits them by hand.
- The schemas validate the parsed tree at load. A file that passes the schema can still fail the semantic checks above.

## The `jsonschema` Dependency: Runtime, Not Only Development

Validation runs at runtime: at shell start and on every hot reload, because the shell validates files at load ([[#What the Editor and the Shell Each Get]]). It never runs per frame, and Python stays out of layout and paint ([[AGENTS#3. Layering principle]]). So the cost is start-up and reload latency, which is small. Measured on this machine (2026-10-27, Python 3.14.8, `jsonschema` 4.26.0, draft-07 validator, a throwaway script in /tmp):

| Measure                                                         | Result                                                   |
|-----------------------------------------------------------------|----------------------------------------------------------|
| Import of `jsonschema`                                          | about 43 ms cumulative, 29 ms of it in its format checks |
| Compile one schema                                              | 0.5 ms                                                   |
| Validate 50, 500, 5000 entries                                  | 2 ms, 21 ms, 208 ms (about 0.4 ms per entry)             |
| PyYAML `compose` of the same files (node tree for line numbers), measured on YAML | 9 ms, 93 ms, 1048 ms: about five times the validation    |

A realistic shell is tens to a few hundred entries, so validation costs a few milliseconds to about 25 ms. The parsing figure is for PyYAML; the TDL parser's cost is not measured and is open ([[#Open]]). Decided 2026-10-27 to keep the steady state free:

- **Lazy import.** `jsonschema` is imported on the first file that needs validation, not at start.
- **Validation cache.** After a file validates, the shell stores its content hash and the schema version. At start it skips files whose hash and schema version are unchanged; hot reload validates only the changed file. A schema change (a shell upgrade, or a new module that changes the project schema) invalidates the entries that depend on it. With a warm cache and no changes, `jsonschema` is never imported.
- The cache lives at `$HOME/.cache/tesserae-shell/validation.json` (decided 2026-10-27), because it is disposable and the XDG cache folder is the place for that. Deleting it only costs one full validation. The cache holds hashes, not file contents.
- Validation stays on in normal runs; a switch to turn it off is not planned.

These numbers are one machine and synthetic files. Re-measure with real shell files in the testing phase.

## Failure Modes and Recovery

- Schema missing or stale: the shell regenerates it (the cache entries that depended on it are invalid); if it cannot, it validates with the shipped schema and warns that module params are unchecked.
- A corrupt or unreadable validation cache: ignored and rebuilt; a warning names the file.
- A schema that fails to compile: a shell bug, reported with the schema path; the shell falls back to its own checks of required keys and types.
- A newer file-type version than the shell knows (`Shell: v2` on a shell that supports `v1`): refused with the supported versions ([[Common Keys and Conventions#Errors]]).

## Open

- [x] Accept [[ADR-0011 JSON Schema for Shell Files]] (2026-10-27).
- [x] Draft: draft-07 keywords (decided 2026-10-27).
- [x] Location: `$HOME/.config/tesserae-shell/schemas/`, ignored by version control (decided 2026-10-27). The modeline part of that decision (relative for files in the config directory, absolute for others) died with the YAML language server.
- [x] `jsonschema` cost: lazy import, a validation cache, and its location `$HOME/.cache/tesserae-shell/` (decided 2026-10-27). Open: `jsonschema`'s own dependencies on the target Python. #needs-verification
- [x] Editor support in v1: no language server; a small TextMate grammar ships (maintainer, 2026-10-29, [[ADR-0014 Shell File Language]]).
- [ ] An Obsidian view of the schemas is out of scope; the maintainer's editor is the target.

Redesign questions for the maintainer, after [[ADR-0014 Shell File Language]] (the agent has not answered them):

> [!question] Redesign of ADR-0011
> - [ ] Does [[ADR-0011 JSON Schema for Shell Files]] stand for load-time validation only, or is it superseded?
> - [ ] After v1, which editor feedback is wanted (completion, hover, diagnostics), and by what route: a TDL language server, an editor plugin that reads these schemas, or none?
> - [ ] Is the schema folder `schemas/` still written to disk, or built in memory or in the cache, now that no modeline points at it?
> - [ ] What is the shape of the block part the schema validates, given repeated names in one `Children { }`: an ordered list of entries rather than a mapping? The `Children` and project-schema design above depend on it.
> - [ ] The parsed tree has a metadata part that holds `TDL:` (ADR-0014 Layout Rules item 1). Does the schema validate that part, or does the loader check `TDL:` and the file-type key before the schema runs?
> - [ ] What does the TDL parser cost on 50, 500 and 5000 entries? Re-measure with the validation numbers above.
> - [ ] Do the schema-path-to-position mapping and the oneOf versus if/then findings hold on a TDL tree?
> - [ ] What does the TextMate grammar cover beyond highlighting (nothing else is planned)?

## Acceptance Criteria

- [ ] The shell rejects an unknown key in a `_Shell.tdl` at load with `file:line:column` from the TDL parser. (Editor completion, hover and squiggles are not in v1.)
- [ ] An editor with the shell's TextMate grammar highlights a `.tdl` file.
- [ ] A user module's params validate in a file that calls it, after the project schema is generated.
- [ ] A file with six deliberate mistakes yields six shell errors, each with the right `file:line:column`.
- [ ] A property added to a block's Python declaration appears in the schema without a manual edit.
- [ ] A file that passes the schema can still fail a semantic check with its own message, never a schema error.

## Links

- [[41 YAML Reference]] · [[Style Schema]] · [[Common Keys and Conventions]] · [[Module File]] · [[Shell File]] · [[Building Blocks]] · [[ADR-0011 JSON Schema for Shell Files]]
