---
title: Config Discovery and Registry
aliases: [Config Loader, Discovery, Registry, UID Write]
type: spec
status: review
owner: phil
created: 2026-10-28
updated: 2026-10-29
tags: [spec/runtime, needs-verification]
related: ["[[Runtime]]", "[[Settings File]]", "[[Shell File]]", "[[Module File]]", "[[Common Keys and Conventions]]", "[[Validation and Errors]]", "[[Hot Reload]]", "[[Shell Start and Stop]]", "[[ADR-0007 Shell UI Layer]]"]
depends_on: ["[[Settings File]]", "[[ADR-0007 Shell UI Layer]]"]
---

# Config Discovery and Registry

> [!summary]
> How the shell finds its files, decides which are loaded, gives each a stable identity, and keeps that identity in `registry.json`. Decided already: the config directory layout, the search order and fallback, `settings.tdl` before the registry (the name `settings.tdl` is an assumption pending maintainer confirmation, [[ADR-0014 Shell File Language#Open Items]]), UIDs made with `uuid.uuid7()`, the registry as a JSON file, the UID written into the file below `shell:`, reference errors at load, and rebuilding the registry from file UIDs ([[ADR-0007 Shell UI Layer#Config directory and registry (2026-10-25)]], [[Settings File]]). This note adds the rules that make those work, as proposals with recommendations.

## Purpose and Scope

- Define discovery, file recognition, name uniqueness, the registry file and its operations, the UID write, and reference resolution.
- Not in this note: what a shell, module, style, theme or stylesheet file contains (the TDL reference, folder [[41 YAML Reference]], rename pending), how errors are reported ([[Validation and Errors]]), watching for changes ([[Hot Reload]]), and the order of start-up ([[Shell Start and Stop]]).

## Behaviour

### Where Files Are

The folders and `settings.tdl` are in [[Settings File#The config directory]]: `Shells/`, `Modules/<module_name>/`, `Styles/`, `Themes/`, `Stylesheets/` and `schemas/` under the config directory. A configured directory in `settings.tdl` is searched first and the default folder is the fallback ([[Settings File]], decided 2026-10-27). Shipped modules come from the package and are registry-only; a user module of the same name overrides one ([[ADR-0007 Shell UI Layer#Modules, styles, themes and stylesheets live in the config directory (2026-10-27)]]).

### Discovery

```mermaid
flowchart TD
    a[Read the directory list for each file type] --> b[Scan each directory]
    b --> c[Recognise files by suffix, then by shell and type keys]
    c --> d[Load main_shell and follow import:]
    d --> e[Register every recognised file]
    e --> f[Check names are unique]
    f --> g[Resolve references]
```

- **What is scanned.** Each directory is scanned recursively for files that end in a shell suffix (`_Shell.tdl`, `_Module.tdl`, `_Style.tdl`, `_Theme.tdl`, `_Stylesheet.tdl`). Dot files, `schemas/`, `logs/` and editor temporary files (names starting with a dot or ending in `~`, `.swp`, `.tmp` or `.bak`) are skipped. Recursive, not one level, so a user can sort Styles into folders; a module is still one folder `Modules/<module_name>/` ([[AGENTS#9. Naming in the designed system]]). Decided 2026-10-28.
- **What is a shell file.** A file is recognised by its suffix and by a top-level `shell:` key, and its `type:` must agree with the suffix ([[ADR-0007 Shell UI Layer#Recognising a shell file and importing (2026-10-25)]], [[Common Keys and Conventions#Keys every file has]]). A file with a shell suffix and no `shell:` key is refused with an error naming it. A file with another name is ignored, and a note is logged at info level.
- **What is loaded.** The top-level shell file is `main_shell` from `settings.tdl` (default `Main_Shell.tdl`) in the shells directory, and every file reachable through `import:` from it ([[Shell File]]). A `_Shell.tdl` in `Shells/` that nothing imports is not loaded and is logged at info level (decided 2026-10-28). Modules, styles, themes and stylesheets are all registered, whether used or not, so that a name used as a key resolves.
- **Imports** are paths relative to the importing file and nest ([[Common Keys and Conventions#Structure keys]]). A cycle is an error naming the chain; a missing file is an error with the paths tried.
- **Parsing** uses the shell's own TDL parser ([[ADR-0014 Shell File Language]]). The same module or block name may appear many times in one `children { }`, ordered by position, and each is named from its position (`Clock_1`, `Clock_2`), so a repeated name is not an error. A property key repeated inside one block (two `text:` lines) is not decided in ADR-0014; see Open Questions. Parse errors carry `file:line:column` from the parser ([[Validation and Errors#Parsing]]). (Earlier, with YAML, a loader had to reject duplicate keys because PyYAML keeps the last of two equal keys silently; a test on 2026-10-28 loaded two `Clock:` entries and got one.)

### Names

- A `name` is unique across the shell, in every file ([[Common Keys and Conventions#Keys every file has]], decided 2026-10-26). A repeated use of one definition gets a path name (proposed).
- A name found twice in one tier is an error naming both files. The same name in a configured directory and in the default folder uses the configured one, with an info notice ([[Settings File]]). A user module overrides a shipped one of the same name.
- A module is called by its name as the key ([[Module File#Using a module]]). The name is looked up in the registry; an unknown key that is neither a block name nor a registered module is an error with the nearest names ([[Validation and Errors#Semantic checks]]).

### Identity and UIDs

- A UID is a `uuid.uuid7()` ([[ADR-0007 Shell UI Layer#UIDs and the registry (2026-10-25)]]). A file carries its own UID in the file, as `UID:` directly below `shell:` in the file's header; it travels with the file when the file is moved or renamed.
- Named entries inside a file (a surface, a module use, a popup) get registry-only UIDs, keyed by the file's UID and the entry's name path. The files themselves are not edited for these. Decided 2026-10-28; the earlier text says anything with a unique name gets a UID and the file holds its own.
- Shipped modules have stable, registry-only UIDs (decided 2026-10-26).
- **Identity** compares the entry's values other than the UID, with `name` and `location`. If they agree, the entry is the same; a mismatch means a new entry and the old one is treated as removed ([[ADR-0007 Shell UI Layer#UIDs and the registry (2026-10-25)]]).
- **A copied file.** Two files that carry the same UID is an error naming both: the user removed the `UID:` line from neither copy. The shell does not choose one (decided 2026-10-28). Giving the later file a new UID was rejected because it can silently change which copy keeps state.

### The Registry File

`registry.json` is at the configured path, default `registry.json` in the config directory ([[Settings File]]). A JSON file, not a database (decided 2026-10-25). Proposed shape:

```json
{
  "registry": 1,
  "entries": {
    "0192f4a0-7c3e-7000-8a1b-3f2c9d4e5a60": {
      "type": "Module",
      "name": "Clock",
      "file": "Modules/Clock/Clock_Module.tdl",
      "state": {}
    },
    "0192f4a0-8d11-7000-9c2d-1b4e6f7a8c91": {
      "kind": "panel",
      "name": "clock_widget",
      "file": "Shells/Main_Shell.tdl",
      "owner": "0192f4a0-7c3e-7000-8a1b-3f2c9d4e5a60",
      "state": {"margin": [40, 0, 0, 40]}
    }
  }
}
```

| Field            | Meaning                                                                                                                          |
|------------------|----------------------------------------------------------------------------------------------------------------------------------|
| `registry`       | The format version of the file; a newer version than the shell knows is an error                                                 |
| `type` or `kind` | A file's type, or a surface's kind                                                                                               |
| `name`           | The unique name                                                                                                                  |
| `file`           | Relative to the config directory when inside it, otherwise absolute                                                              |
| `owner`          | For a named entry inside a file, the file's UID                                                                                  |
| `state`          | What the shell saves: a floating Panel's position ([[Panel#Position and attachment]]); other state is added as it is found |

- **Reading.** At start, on the main thread before the loop runs ([[Shell Start and Stop]]). A file that is not valid JSON is an error and stops the shell; the shell does not overwrite it. A missing file is created empty (decided 2026-10-27).
- **Writing.** A single writer thread collects changes and writes at most once every 500 ms, and once at stop. It writes to a temporary file in the same directory, flushes it, and replaces the registry atomically (`os.replace`), so a crash leaves the old file whole. Recommendation; this settles the open question about registry I/O on the loop ([[ADR-0007 Shell UI Layer#Open items]]).
- **A moved or empty registry.** If the registry is new, empty or moved and the files already carry UIDs, the shell logs a warning and rebuilds each record from the UID in its file instead of issuing new ones (decided 2026-10-27, [[Settings File]]). What a rebuilt record holds is name, kind or type, and file, found by scanning; the saved `state` is lost (decided 2026-10-28).
- **Removed entries.** When a file or entry is gone, its record is kept for 30 days and then dropped (decided 2026-10-28), so that renaming a file and back does not lose a Panel's position.

### Writing the UID into a File

The shell edits a file the user wrote, so it is careful (risk R-06 in the [[Risk Register]]).

1. Before the first write to a file, copy it to a backups folder under the config directory (`backups/`, ignored by version control like `schemas/`; decided 2026-10-28).
2. Insert the line `UID: <uuid7>` directly below the `shell:` line in the parser's lossless tree, which keeps comments and layout, then write the tree back out; there is no separate comment-keeping writer ([[ADR-0014 Shell File Language#What TDL Is (Decided)]], item 13). Comments, order and quoting survive. Keep the file's line endings. How the tree is written back (edit the text at the node's position, or print the tree) is not decided; see Open Questions.
3. Check that the file did not change since it was read (content hash); if it did, skip and retry on the next load.
4. Write a temporary file in the same directory, then replace the original atomically; keep the file's permissions.
5. Tell the watcher this write is the shell's own, so the change does not trigger a reload ([[Hot Reload#The shell's own writes]]).
6. If the file cannot be written (read-only, not owned), log a warning and keep its identity in the registry only.

### References

- A reference is by name: `attach_to`, `anchor_to`, a module call key, `import:` paths for files. The registry resolves it ([[Common Keys and Conventions#Names and references]]).
- An unresolved reference is an error at load naming the file, the entry and the name. A target that disappears while running is a warning and the referring surface stays hidden until it returns ([[ADR-0007 Shell UI Layer#Config directory and registry (2026-10-25)]], [[Panel#Failure modes and recovery]]).
- Python reaches a file's parsed TDL tree by file name, unique name or UID through `ctx.yaml(ref)` ([[Module Context]]; the method name keeps `yaml` until that note is rewritten); the registry resolves it.

## Configuration

`settings.tdl` keys: `directories`, `registry`, `main_shell` ([[Settings File]]). Proposed addition: `registry_retention` (days an orphaned record is kept, default 30; the 30 days are decided). No other key.

## Python Contract

A module receives its own UID and name in the context and can read other TDL files through the registry ([[Module Context]]). It never reads or writes the registry.

## Integration

- Files: read through the standard library; shell files through the TDL parser (a module in the shell package, [[ADR-0014 Shell File Language]]); JSON through the standard library.
- Threads: discovery and parsing may run on the config watcher thread; the registry and the model are updated on the loop with a finished result ([[Process Model and Threading#Threads]]). One writer thread for the registry.
- Platform: `os.replace` is atomic on one filesystem; the temporary file is in the registry's own directory for that reason.

## Design

None.

## Accessibility

None directly. Error messages follow [[Validation and Errors]].

## Performance Budget

- Discovery scans a few dozen files; parsing dominates. With the validation cache an unchanged file is not re-validated ([[JSON Schema and Editor Support#The `jsonschema` dependency runtime, not only development]]).
- A registry write is off the loop and bounded by one write per 500 ms.
- Budgets are set in `60 Quality/`.

## Failure Modes and Recovery

| Failure                                         | Result                                                                      |
|-------------------------------------------------|-----------------------------------------------------------------------------|
| `registry.json` is not valid JSON               | Error naming the file; the shell stops and does not overwrite it            |
| The registry is newer than the shell knows      | Error naming the version; the shell stops                                   |
| Two files carry the same UID                    | Error naming both                                                           |
| A name defined twice                            | Error naming both files and lines                                           |
| A shell-suffix file with no `shell:` key        | Error naming the file                                                       |
| A configured directory is missing or unreadable | Error naming the key and the path ([[Settings File#Errors specific to this file]]) |
| The UID write fails                             | Warning; the file keeps a registry-only identity                            |
| A file changes during the UID write             | The write is skipped and retried                                            |
| The registry write fails (disk full)            | Logged; the old file stays whole; retried at the next change and at stop    |

## Open Questions

All seven were answered on 2026-10-28, as recommended.

1. [x] **Scan depth:** recursive for all types.
2. [x] **A copied file with a duplicate UID:** an error naming both.
3. [x] **Retention of removed records:** 30 days.
4. [x] **What a rebuilt record holds:** name, kind or type and file from the scan; saved state is lost.
5. [x] **Named entries:** registry-only UIDs for entries inside a file.
6. [x] A `backups/` folder under the config directory for the first UID write.
7. [x] **Unimported shell files:** a `_Shell.tdl` in `Shells/` that nothing imports is ignored with an info notice.
- [ ] The registry writer: one thread, one write per 500 ms (proposed, not asked).
- [ ] The UID write with TDL: whether the shell patches the text at the lossless tree's position or prints the tree back out. Either keeps comments (ADR-0014 item 13); the choice is not made.
- [ ] A property key repeated inside one block: an error, or last wins. ADR-0014 allows repeated block names only.

## Acceptance Criteria

- [ ] With the default folders and no `settings.tdl`, the shell finds `Shells/Main_Shell.tdl` and registers every module, style, theme and stylesheet.
- [ ] A `directories.modules` path is searched before `Modules/`; a module found only in `Modules/` still loads.
- [ ] Two entries with the same name fail the load and the error names both files and lines.
- [ ] Two `Clock { }` blocks in one `children { }` load, in positional order, named `Clock_1` and `Clock_2`.
- [ ] A `.tdl` syntax error is reported with `file:line:column` from the TDL parser.
- [ ] A shell-suffix file with no `shell:` key is refused by name.
- [ ] The first load writes `UID:` below `shell:` in each file, keeping comments and line endings, and a backup exists first.
- [ ] A file moved to another folder keeps its UID and its saved state.
- [ ] Deleting `registry.json` and starting rebuilds records from the files' UIDs with a warning, and creates the file.
- [ ] A crash during a registry write leaves the previous registry readable.
- [ ] A reference to a missing name fails the load; removing a target while running hides its Panel and logs a warning.

## Links

- [[Runtime]] · [[Settings File]] · [[Shell File]] · [[Common Keys and Conventions]] · [[Validation and Errors]] · [[Hot Reload]] · [[Shell Start and Stop]]
