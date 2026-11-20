---
title: Version Policy and Migration
aliases: [Version Policy, Versioning, Migrate, tesserae-shell migrate, M7d]
type: delivery
status: accepted
owner: phil
created: 2026-11-17
updated: 2026-11-17
tags: [delivery, process, needs-verification]
---

# Version Policy and Migration

> [!NOTE]
> **Accepted by the maintainer on 2026-11-17**
> Sent to `tess-shell` by the vault session the same day, on the maintainer's standing order; accepted by him afterwards. Open questions below are answered as recommended unless a line says otherwise.

> [!NOTE]
> What each version number of Tesserae Shell promises, how a file says which shell it needs, and a command, `tesserae-shell migrate`, that brings a user's files from an older format to the current one. The 0.1 to 0.2 slot change (`{{ }}` to `<| |>`, 2026-11-14) was done by hand with a script from the `tess-dl` repository; this note makes that a supported step. M7d of [M7 Brief](../00%20Home/M7%20Brief.md). The release this policy first governs is 0.2.0, the end of M7; versioning, tagging and publishing stay the maintainer's.

## Purpose and scope

- In: the numbers and what they cover, the pre-1.0 and post-1.0 promises, deprecation, the `Shell:` pin, `migrate`, the release checklist items that follow from it.
- Out: how a release is built and published ([Packaging and Session Start](Packaging%20and%20Session%20Start.md)); the language rules of TDL, owned by `tess-dl` ([TDL Language](../41%20TDL%20Reference/TDL%20Language.md)).

## The Version Numbers

| Number | Where it is written | Covers |
|---|---|---|
| Shell release | `__version__`, `pyproject.toml`, the changelog, the tag `vX.Y.Z` | The package as a whole |
| TDL language version | `TDL:` in a file's metadata block (major.minor, a string) | The punctuation and structure of a file; owned by `tess-dl` |
| TEL language version | `TEL:` in the block, and `tess_el.LANGUAGE` | What an expression may say |
| Schema export version | `schema_version` in `tesserae-shell schema --json` (1.9 at the time of writing) | The keys, blocks, kinds, tokens and modules the shell knows; the configuration application reads it |
| Module contract | The shell release; `Shell:` in a module file | `Module`, `ctx`, `@action`, events |
| Registry format | `"registry": 1` in `registry.json` | The shell's own file; the user does not edit it |
| Control interface | The bus name `io.github.mindderivative.TesseraeShell` and its interface version | The D-Bus methods and properties |

## What a Release Promises

| | Before 1.0 (0.x) | From 1.0 |
|---|---|---|
| A patch (0.x.Y) | Fixes only; no file, command or API change | Same |
| A minor (0.X.0) | May change anything below, each change listed under "Changed" or "Removed" in the changelog, with a `migrate` step when it touches a user's files | New features and additions; nothing removed or renamed; a deprecation may start |
| A major | Not used | May remove what was deprecated for at least two minors, each with a `migrate` step |
| Command line | May change in a minor | A command, option, exit code or `--json` shape never changes in a minor |
| Schema export | Version bumps minor for an addition, major for a change or a removal | Same; the configuration application checks the major |
| A user's TDL files | A key rename or a language change comes with `migrate` | A file valid for 1.X stays valid for 1.Y |
| Module contract | May change in a minor, with `migrate` where code can be rewritten | Additions only within 1.x |

The rules are decided here so that the 0.2.0 changelog already follows them. The maintainer decides what goes into a minor; this note decides how it is told.

## Deprecation

- A renamed or replaced key, block, parameter or command keeps working under its old name for one minor before 1.0 and two minors after, with the warning `deprecated-key` (or `deprecated-command` on the command line) naming the replacement and the release that removes it.
- The schema export marks it (`deprecated: {since, removed_in, use}`) so the configuration application can show it.
- `migrate` rewrites the old name to the new one wherever it can do so without losing meaning.

## The `Shell:` Pin

`Shell:` in a file's metadata block is the minimum shell release the file needs ([TDL Language > The Metadata Block](../41%20TDL%20Reference/TDL%20Language.md#the-metadata-block)). The shell compares it with its own release (major.minor):

- A pin newer than the shell is an error with `file:line:column`: `shell-too-old`, hint "install tesserae-shell X.Y or later". The file is refused, as any file with an error.
- A `TDL:` version the installed `tess-dl` does not read is the library's own version error, with its hint.
- A file for an older language version (today `TDL: 0.1`) is refused with a hint that says "run `tesserae-shell migrate`". By the code session's report (commit `e30bfe3`, 2026-11-14) the shell already refuses older files; the exact error code was not read. #needs-verification

## The `migrate` Command

```
tesserae-shell migrate [--config-dir DIR] [--check] [--json]
```

| Behaviour | Rule |
|---|---|
| What it reads | Every `.tdl` file under the configuration directories and `settings.tdl`, never the registry |
| Steps | An ordered list of numbered steps. Each has a `from` and a `to` (a language or shell version) and rewrites text only; a step is idempotent (a file already at `to` is left alone) |
| First step | `0001`: TDL 0.1 to 0.2: the slot delimiters become `<| |>` and `TDL: 0.1` becomes `TDL: 0.2`; no other byte changes (comments, layout, line endings, quoted text that looks like a slot). A slot that holds `|>` outside a quote cannot be rewritten and is reported, not touched |
| Check | `--check` changes nothing and exits 1 if any file would change |
| Backup | Before writing, the originals are copied to `<config>/.migrate-backup/<timestamp>/` with their relative paths; nothing is deleted |
| Result | Prints each file changed, the step applied, and a summary; `--json` gives `{ok, steps: [{step, files: [{path, state}]}], skipped: [...]}` with the shape of the other commands ([IPC and CLI](../40%20Specifications/Runtime/IPC%20and%20CLI.md)) |
| Exit codes | 0 nothing to do or done; 1 `--check` found work; 2 a file could not be migrated; the shell's usual codes for a bad configuration directory |
| Safety | It writes only inside the configuration directories, never runs a shell, and refuses to run while a shell holds the lock unless `--force` |
| After | `tesserae-shell check` is run on the result and its verdict is printed |

### Where the 0.1 to 0.2 step comes from

The script that did the change by hand, `tools/migrate_slots.py` in the `tess-dl` repository, needs the old reader (`tesserae-dl` 0.1.1) to find the slots. The shell depends on `tesserae-dl` 0.2.0 or later, which cannot read the old form, so `migrate` cannot call the script without installing a second library version at run time, which needs a network and `uv` and is not acceptable for a command a user runs on their own files. The step therefore needs the rewrite inside the library, which is the request [TDL-REQ-001 Slot Migration in the Library](../80%20Requests/TDL-REQ-001%20Slot%20Migration%20in%20the%20Library.md). If `tess-dl` declines, the shell carries its own small scanner for the 0.1 slot rules (the rules are in `tess-dl`'s language reference) and the vault records it.

## What the Release Checklist Gains

From 0.2.0, a release is not named until:

1. The changelog has a section for the version with "Changed" and "Removed" entries where they apply, each with its `migrate` step.
2. The schema version is bumped by the rule above and the recorded fixture is regenerated.
3. The guide's generated pages are regenerated (`python -m tests.guide_tables`).
4. A configuration folder of the previous minor passes `migrate --check` and `check` after `migrate`.
5. The dependency ranges follow the next section.

## Dependency Ranges

- A floor is raised only when the shell needs something the older version lacks, and the change says which.
- The upper bound is the next minor of a 0.x dependency (`tesserae-engine>=0.6.9,<0.7`, `tesserae-el>=0.2.0,<0.3`, `tesserae-dl>=0.2.0,<0.3`) and the next major of a 1.x one, so a breaking release of a dependency never reaches a user without a shell release that has been tested against it.
- Moving an upper bound is its own pull request with the full suite on the new version.

## Python Contract

A module author sees nothing new except `deprecated-*` warnings and, for a contract change, a `migrate` step where code can be rewritten. `tesserae-shell migrate` is a command, not an API.

## Integration

- `tess-dl` owns the language and the slot rewrite ([TDL-REQ-001 Slot Migration in the Library](../80%20Requests/TDL-REQ-001%20Slot%20Migration%20in%20the%20Library.md)).
- The configuration application (`tess-ui`) reads `schema_version` and `deprecated` from the schema export and can offer to run `migrate --check` and show its result in its Files area.
- `install-session --print` and `status` print the release; `status` also prints the schema version.

## Failure modes and recovery

| Failure | Result |
|---|---|
| A file is read-only or in a read-only folder | Exit 2 for that file, others still migrated, the report names the file |
| A slot cannot be rewritten | Reported and left unchanged; the rest of the file is migrated only if it is safe to do so; otherwise the whole file is left unchanged |
| The shell is running | Refuses unless `--force`, because a reload would read half-migrated files |
| A migration is interrupted | The backup holds every original; a second run is idempotent |
| A newer config than the shell | `shell-too-old` for each such file, nothing migrated backwards |

## Open Questions

1. [x] How long does a deprecated name keep working? Context: the table says one minor before 1.0 and two after. Recommendation: as written; before 1.0 the shell has one user and the cost of carrying aliases is real. Accepted as recommended by the maintainer on 2026-11-17, with his acceptance of the note.
2. [x] Does `migrate` also rewrite a renamed key in a user's module Python? Context: Python source cannot be rewritten safely by text. Recommendation: no; the changelog lists the contract change and the warning names the replacement. Accepted as recommended by the maintainer on 2026-11-17, with his acceptance of the note.
3. [x] Is a refusal of `TDL: 0.1` files at start the right behaviour, or should the shell read them and warn until `migrate` is run? Context: the shell refuses them today (by report). Recommendation: keep the refusal; a file that parses differently from what its author wrote is worse than a clear stop with the command to run. Accepted as recommended by the maintainer on 2026-11-17, with his acceptance of the note.

## As Built (code session's report of `tess-shell` PR #61, merged 2026-11-17, CI green; not run in the vault)

- `tesserae-shell migrate [--check] [--json] [--force] [--config-dir]`. Step 0001 is the TDL 0.1 to 0.2 slot rewrite with the shell's own scanner behind one function (`migrate/slots.py`: `rewrite_slots(text, *, path)`), verified against `tesserae-dl` 0.1.1 on 213 generated valid files, so it can be swapped for `tess_dl`'s function later ([TDL-REQ-001 Slot Migration in the Library](../80%20Requests/TDL-REQ-001%20Slot%20Migration%20in%20the%20Library.md) stays unsent). Step 0002 is the deprecated renames; its table is empty in 0.2.0, so it is machinery only.
- A backup goes to `.migrate-backup/<timestamp>` (files outside the config folder go under the same stamp with the absolute path stripped of the root). Writes use a temporary file and a rename. It refuses while a shell runs (the lock) unless `--force`. `--check` changes nothing and exits 1 if any file would change; `--json` is available; it is idempotent; the post-migration `check` verdict is printed.
- A shell file that asks for a newer shell (the `Shell:` pin) is the error `shell-too-old`; it compares major.minor, so a pin of 0.2.9 is not too new for 0.2.0. `tdl-old-version` carries a `migrate` hint, also for a 0.1 file with slots. `deprecated-key` and `deprecated-command` findings and a `deprecated` mark in the schema export appear only when a row exists (none in 0.2.0, so M7d bumps no schema version).
- The version policy text is in `guide/09` and the README as this note gives it.
- CI found two things: a real regression in the first push (the thin reload client imported `tess_dl` through `schema/deprecations.py`; fixed with lazy imports; the toggle end to end is 59 ms median), and a latent race in `test_kill_strays` (`Popen` returns slightly before the kernel fills `/proc/PID/environ`; 0 of 40 failures locally under load, 2 in CI on one shard; the test now waits).

### Decisions from the build (code session's list; the report is cut off after the fourth)

1. Exit 2 serves both "a file could not be migrated" and "missing config directory". Recommendation: as built.
2. A refusal because a shell runs uses exit 4 (`ALREADY_RUNNING`); this note named no code. Recommendation: as built.
3. The exit stays 0 after a successful rewrite even if the post-migration `check` fails; the verdict is printed and in the JSON result; only `--check` uses exit 1. Recommendation: as built.
4. Discovery is the config folder tree plus the `Directories` folders of the settings (the rest of this item was cut off in what the vault read; it ends with a reference to the note's answer 3, module Python).

## Acceptance criteria

- [ ] `tesserae-shell migrate --check` on a 0.1-era configuration folder exits 1 and lists the files; `migrate` rewrites them, writes the backup, and the result passes `check`.
- [ ] A second `migrate` changes nothing and exits 0.
- [ ] A file with a `Shell:` pin newer than the shell is `shell-too-old` with its position and the hint.
- [ ] A file with `TDL: 0.1` is refused with the hint to run `migrate`.
- [ ] A renamed key used in an old file gives `deprecated-key` naming the replacement and `migrate` rewrites it.
- [ ] `migrate` refuses while a shell runs, and works with `--force`.
- [ ] The 0.2.0 changelog follows the rules above and the release checklist items 1 to 5 are done before the release is named.
- [ ] The dependency ranges in `pyproject.toml` follow the rule.

## Links

[M7 Brief](../00%20Home/M7%20Brief.md) · [Packaging and Session Start](Packaging%20and%20Session%20Start.md) · [TDL Language](../41%20TDL%20Reference/TDL%20Language.md) · [TDL-REQ-001 Slot Migration in the Library](../80%20Requests/TDL-REQ-001%20Slot%20Migration%20in%20the%20Library.md) · [IPC and CLI](../40%20Specifications/Runtime/IPC%20and%20CLI.md) · [Settings File](../41%20TDL%20Reference/Settings%20File.md) · [Validation and Errors](../40%20Specifications/Runtime/Validation%20and%20Errors.md) · [70 Delivery](70%20Delivery.md)
