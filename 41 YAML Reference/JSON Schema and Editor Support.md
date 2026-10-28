---
title: JSON Schema and Editor Support
aliases: [Shell JSON Schema, YAML Schema Files, Editor Support]
type: yaml-ref
status: draft
owner: phil
created: 2026-10-27
updated: 2026-10-27
tags: [yaml-ref, tooling, needs-verification]
related: ["[[41 YAML Reference]]", "[[Style Schema]]", "[[Common Keys and Conventions]]", "[[Module File]]", "[[Shell File]]", "[[Building Blocks]]", "[[ADR-0011 JSON Schema for Shell Files]]"]
depends_on: ["[[ADR-0011 JSON Schema for Shell Files]]"]
---

# JSON Schema and editor support

> [!summary]
> The shell publishes JSON Schema files for its YAML. An editor with the Red Hat YAML extension (the YAML language server) uses them for auto-completion, hover descriptions and syntax validation; the shell uses the same files to validate at load and on hot reload. The schemas are generated from the block and module declarations, so the reference and the code cannot drift. Proposal from the maintainer's idea (2026-10-27); every detail below is proposed.

## What the editor and the shell each get

| Consumer | Uses the schema for | Notes |
|---|---|---|
| Editor (Red Hat YAML extension, any client of the YAML language server) | Completion of keys and values, hover text from `description`, diagnostics for wrong types, unknown keys and bad enum values | Verified from the server's README: keys, values and structure completion, hover from schema descriptions, diagnostics ([README](https://github.com/redhat-developer/yaml-language-server)). Whether `markdownDescription` and `defaultSnippets` work was not confirmed. #needs-verification |
| Shell | Structural validation at load and hot reload: types, enums, required keys, unknown keys | Errors are reported as `file:line:column` ([[AGENTS#3. Layering principle]]) |
| Not the schema's job | Unique names across the shell, registry references, import cycles, token existence, expression syntax | Semantic checks run after the schema passes ([[Common Keys and Conventions#Errors]]). Expressions are plain strings to the schema; TEL checks them |

## Associating a schema with a file

The language server resolves a schema from, in priority order: a modeline comment, a top-level `$schema` key, a custom provider, `yaml.schemas` settings, then SchemaStore ([README](https://github.com/redhat-developer/yaml-language-server)).

| Method | Form | Recommendation |
|---|---|---|
| Modeline | First line of the file: `# yaml-language-server: $schema=<path or URL>`; relative paths resolve from the file | Yes. The shell writes it when it creates or registers a file, as it writes the UID ([[Common Keys and Conventions#Keys every file has]]). A comment, so the "unknown key is an error" rule is untouched |
| `yaml.schemas` with globs | The editor setting maps a schema to patterns | Yes, as the zero-edit route: the suffixes give clean globs (`*_Shell.yaml`, `*_Module.yaml`, `*_Style.yaml`, `*_Theme.yaml`, `*_Stylesheet.yaml`) |
| `$schema` as a key | A top-level key | No. It would need the shell to ignore a key it otherwise rejects |

Draft support is stated differently by two sources: the server lists draft-04, draft-07, 2019-09 and 2020-12, while the extension's page mentions Draft 7 ([vscode-yaml](https://github.com/redhat-developer/vscode-yaml)). Recommendation: write to the draft-07 keyword set (`definitions`, `if`/`then`/`else`, `enum`, `const`, `patternProperties`) so any editor version works, and have the shell validate with the same draft. #needs-verification in the installed extension.

## Files

| Schema | For | Shipped or generated |
|---|---|---|
| `shell.schema.json` | `type: Shell` files: roots, monitors, surfaces, children | Shipped, per format version (`shell: v1` maps to a `v1` folder and `$id`) |
| `module.schema.json` | `type: Module` files: params, layout, style | Shipped |
| `style.schema.json`, `theme.schema.json`, `stylesheet.schema.json` | The three look files ([[Style Schema]]) | Shipped; the theme token enums are filled in by generation |
| `definitions.schema.json` | Shared definitions: colour, four-sided values, size, token reference, shadow, each block's properties | Generated from the block declarations ([[Building Blocks#Properties, parts and states]]) |
| `project.schema.json` | One config directory: which module names exist and their `params` | Generated from the module files in the config directory and the registry |

The five file-type schemas are told apart by the required `type:` key; each starts with a `required: [shell, type]` check, then branches with `if`/`then` on `type`.

## Why a generated project schema

A module is called by its unique name as the key, with params beneath ([[Module File#Using a module]]). A static schema cannot know which names a user's shell defines. The generated project schema lists each module name as a property of `children` with that module's `params` as its value schema, so completion offers the user's modules and checks their params. Block entries (their own key, with `block:`) fall through to the block branches. The shell regenerates the project schema when the registry changes ([[ADR-0007 Shell UI Layer#Config directory and registry (2026-10-25)]]); the command is proposed as `tesserae-shell schema`.

## Findings from a spike (2026-10-27)

A throwaway script in /tmp (not in the vault) validated a sample shell file with Python `jsonschema` 4.26.0 and located each error in the file with PyYAML's `compose` marks (PyYAML 6.0.3, Python 3.14.8).

- **Line and column work.** An error's path maps to a node mark; output looked like `bad.yaml:6:16: children/bar_top/style: Additional properties are not allowed ('colour' was unexpected)`. The library gives paths, not positions, so the shell must keep the composed node tree next to the data.
- **A choice between branches hides the real error.** With each entry as a `oneOf` of "block entry" or "module call", a typo deep in one entry produced a single error at the entry ("not valid under any of the given schemas") and `best_match` chose an unrelated deeper error. Recommendation: dispatch with `if`/`then` on the key that names the branch (`block` equal to `Text`, and so on) instead of `oneOf`. The same sample then gave six errors, each at the right line and column: an unknown `txt` key, an unknown block `Hexagon`, a wrong type, an out-of-range `elevation`, an unknown `colour` style key and a four-sided value of the wrong length. The language server's own diagnostics for `oneOf` were not tested. #needs-verification
- `additionalProperties: false` is only correct inside an `if`/`then` branch that lists every allowed property; the generation step must emit complete property lists, including shared keys such as `style` and `children`.

## Generation

- Every block and module declares its properties (type, default, choices, doc), parts and states in Python; the generator turns them into the property schemas, with the doc line as `description` ([[Style Schema#Principles]]).
- The theme token groups become `enum` lists in the reference form `$group.name` for completion; token existence is also checked by the shell after loading ([[Style Schema#Theme tokens]]).
- Schemas are build artefacts. They ship in the package and regenerate for a config directory; nobody edits them by hand.
- The shell and the editor read the same files, so a file that passes in the editor passes at load, except for the semantic checks above.

## Failure modes and recovery

- Schema missing or stale: the shell regenerates it; if it cannot, it validates with the shipped schema and warns that module params are unchecked.
- A schema that fails to compile: a shell bug, reported with the schema path; the shell falls back to its own checks of required keys and types.
- A newer `shell:` version than the shell knows: refused with the supported versions ([[Common Keys and Conventions#Errors]]).

## Open

- [ ] Accept [[ADR-0011 JSON Schema for Shell Files]].
- [ ] Draft: draft-07 keywords (recommended) or 2020-12.
- [ ] Where the generated project schema lives and how the modeline points to it.
- [ ] `jsonschema` as a dependency, and its cost: load time at hot reload, and its own dependencies on the target Python. #needs-verification
- [ ] Whether `markdownDescription` and `defaultSnippets` are usable in the extension.
- [ ] An Obsidian view of the schemas is out of scope; the maintainer's editor is the target.

## Acceptance criteria

- [ ] In an editor with the YAML extension, a `_Shell.yaml` with the modeline offers block names after `block:`, hover text on every style key, and a squiggle on an unknown key.
- [ ] A user module's params complete and validate in a file that calls it, after the project schema is generated.
- [ ] A file with six deliberate mistakes yields six shell errors, each with the right `file:line:column`.
- [ ] A property added to a block's Python declaration appears in the schema without a manual edit.
- [ ] A file that passes the schema can still fail a semantic check with its own message, never a schema error.

## Links

- [[41 YAML Reference]] · [[Style Schema]] · [[Common Keys and Conventions]] · [[Module File]] · [[Shell File]] · [[Building Blocks]] · [[ADR-0011 JSON Schema for Shell Files]]
