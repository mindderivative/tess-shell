---
title: Settings File
aliases: [settings.tdl, settings.yaml, Shell Settings, Config Directory Layout]
type: tdl-ref
status: draft
owner: phil
created: 2026-10-27
updated: 2026-10-31
tags: [tdl-ref, runtime]
---

# Settings File

> [!NOTE]
> The config directory, `$HOME/.config/tesserae-shell/`, holds the shell's files in fixed folders. One file at its root, `settings.tdl`, holds settings that are not tied to a single shell: where to look for files when the user wants a different layout, which shell file to start, and global behaviour. The folder layout and the file are the maintainer's (2026-10-27); the key names were accepted by the maintainer on 2026-10-29, and the name `settings.tdl` is confirmed (D20; its file-type key `Settings: v1` was replaced by the root block `Settings { }`, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)).

## The Config Directory

```
$HOME/.config/tesserae-shell/
    settings.tdl
    registry.json    default place; `settings.tdl` can move it
    Shells/          Main_Shell.tdl, <Name>_Shell.tdl
    Modules/         <module_name>/<Name>_Module.tdl and .py
    Styles/          <Name>_Style.tdl
    Themes/          <Name>_Theme.tdl
    Stylesheets/     <Name>_Stylesheet.tdl
    Icons/           SVG and PNG icons (searched third, [[Block Reference#Icons (R7)]])
    schemas/         generated, ignored by version control
    logs/            log files (default)
```

- Shell files live in `Shells/` (decided 2026-10-27). The folder names and the other four are from [ADR-0007 Shell UI Layer > Modules, styles, themes and stylesheets live in the config directory (2026-10-27)](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md#modules-styles-themes-and-stylesheets-live-in-the-config-directory-2026-10-27).
- `settings.tdl` can point to absolute directories for any of these types, for a user who wants a different layout (decided 2026-10-27). With no `settings.tdl`, or no key for a type, the folders above are used.
- `settings.tdl` is the home for settings that are not project based (decided 2026-10-27).
- **Where the config directory is** (decided 2026-10-27, "whichever is safer for the operating system"): `$XDG_CONFIG_HOME/tesserae-shell/` when `XDG_CONFIG_HOME` is set, non-empty and an absolute path; otherwise `$HOME/.config/tesserae-shell/`. This follows the XDG base directory specification: an unset or empty variable means `$HOME/.config`, and a relative value is invalid and ignored ([spec](https://specifications.freedesktop.org/basedir/latest/)). The cache directory follows the same rule with `XDG_CACHE_HOME` and `$HOME/.cache`. Every note that writes `$HOME/.config/tesserae-shell/` means this directory at its default.

## File Header

```
---
TDL: 0.1
Name: Settings
---
```

The metadata block of every shell file is defined in [TDL Language > The Metadata Block](TDL%20Language.md#the-metadata-block); the file type is named by the root block, `Settings { }` (D20, [TDL Language > The Root Block](TDL%20Language.md#the-root-block)), and holds all the keys below. The file is a sixth file type, beside the five of [ADR-0014 Shell File Language > Layout Rules](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#layout-rules); the name is fixed (`settings.tdl`, not `<Name>_Settings.tdl`) because there is one per config directory. `Name:` is required (D39). Proposed: it carries no `UID` and is not entered in the registry. AGENTS > 9. Naming in the designed system lists the file suffixes and types; adding `Settings` there is the maintainer's edit.

## Keys (Proposed)

| Key           | Meaning                              | Value                                                                                                                                                                                |
|---------------|--------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `Directories` | Where to look for each file type     | A block with the keys `Shells`, `Modules`, `Styles`, `Themes`, `Stylesheets`, `Icons` to an absolute directory or a list of them. `Icons` lists extra locations searched after the config `Icons/` folder (decided 2026-11-01, [Block Reference > Icons (R7)](Block%20Reference.md#icons-r7))                                                                     |
| `Main_Shell`  | The shell file the shell starts from | A file name in the shells directory; default `Main_Shell.tdl`                                                                                                                       |
| `Registry`    | Where the registry file lives        | An absolute path to a `registry.json` file; default `$HOME/.config/tesserae-shell/registry.json`. Same path rules as `Directories`                                                   |
| `Logging`     | Global log settings                  | `Level`, `Directory` (default `logs/` in the config directory, same path rules) and `Retention` (optional, days); naming and rotation are in [Log files](#log-files) |
| `Validation`  | Schema validation settings           | `Enabled` (default true); the cache location is [JSON Schema and Editor Support > The `jsonschema` Dependency: Runtime, Not Only Development](JSON%20Schema%20and%20Editor%20Support.md#the-jsonschema-dependency-runtime-not-only-development)                                                                                              |

Keys are Capitalised like every key in a shell file ([TDL Language > Names and the Registry](TDL%20Language.md#names-and-the-registry)). The key names are the agent's Capitalisation of the 2026-10-29 names; `Level`, `Directory`, `Retention` and `Enabled` follow the same rule.

Enum values of settings keys are full upper case, like every enum value (D58):

| Key                | Values                                                                 |
|--------------------|------------------------------------------------------------------------|
| `Logging.Level`    | `TRACE`, `DEBUG`, `INFO`, `SUCCESS`, `WARNING`, `ERROR`, `CRITICAL` (Loguru's level names) |
| `Logging.Format`   | `TEXT`, `JSON`                                                         |
| `KWin.Script`      | `RUNTIME`, `PERSISTENT`, `OFF`                                         |

```
---
TDL: 0.1
Name: Settings
---

Settings {
    Directories {
        Modules: ["~/Projects/shell/Modules", "~/.config/tesserae-shell/Modules"]
        Themes: ~/Projects/shell/Themes
    }

    Main_Shell: Main_Shell.tdl

    Logging {
        Level: INFO
    }
}
```

Settings keys are nested blocks, as the example shows (`Logging { Level: INFO }`). `Logging.Level` in the prose below is only a shorthand for that path (D20). The metadata block and the brace blocks follow [TDL Language](TDL%20Language.md); the paths in the list are quoted to keep the example safe, and whether bare paths are fine in a list is not stated there.

- A value in `Directories` is a path or a list of paths, searched in order (decided 2026-10-27).
- **Fallback to the default.** The default folder for the type, inside the config directory, is searched after the configured ones (decided 2026-10-27, read as "fallback to defaults"). A name found in a configured directory is used and the default is not consulted for it; a name found only in the default folder is used from there. When the same name exists in both, the configured one wins and the shell logs a notice at info level naming both files (proposed). The maintainer confirmed this reading on 2026-10-27.
- **Paths.** `~` and environment variables are allowed (decided 2026-10-27). The shell expands them, and the result must be an absolute path. If a variable is unset or the path does not resolve, that is an error naming the key, the text written and what failed. There is no silent empty value. A path that resolves to a directory that does not exist is an error too. A relative path after expansion is an error: it would depend on the working directory.
- A name found twice in the same tier (two configured directories) is an error naming both files, as a duplicate unique name is ([Common Keys and Conventions > Names and references](Common%20Keys%20and%20Conventions.md#names-and-references)).
- Files found through a configured directory are registered like any other. How such files are associated with a schema depends on the schema set: the loader picks the schema from the root block and the suffix, so no association is needed ([JSON Schema and Editor Support > Associating a Schema with a File](JSON%20Schema%20and%20Editor%20Support.md#associating-a-schema-with-a-file)).

## Log Files

Decided 2026-10-27; the details marked below were settled by adopting the recommendations the same day.

- **Name.** `log_yyyy-mm-dd`, with a `.log` extension: `log_2026-10-27.log`. The extension lets editors and log tools recognise the file.
- **Rotation.** A new day is a new log file. The day changes at local midnight (Loguru's timestamps are local time, [Loguru API](https://loguru.readthedocs.io/en/stable/api/logger.html)). A shell that runs across midnight writes the next file from then. A restart on the same day appends to that day's file.
- **Retention.** Up to the user: by default the shell deletes nothing. An optional `Logging.Retention` key holds a number of days; when set, the shell deletes only files in the log directory that match `log_yyyy-mm-dd.log` and are older than that many days, checked at start and at each midnight. Any other file in the folder is left alone.
- **How it is built.** The shell computes the file name from the local date and swaps the Loguru sink at midnight (add the new day's sink, then remove the old one). It does not use Loguru's own rotation. A test with Loguru 0.7.3 on this machine (2026-10-27) showed why: a path `log_{time:YYYY-MM-DD}.log` is accepted and gives `log_2026-10-27.log`, and a restart appends to it, but a rotation renames the finished file with a timestamp suffix (`log_2026-10-27.2026-10-27_20-50-15_081151.log`), so the files would not be named `log_yyyy-mm-dd` after a rotation. The swap keeps the names exact. Loguru's own retention option is not used either. A real midnight crossing was not tested. #needs-verification

## Start Order

Decided 2026-10-27: `settings.tdl` is read first, before the registry, because it can move the registry to a custom location. Proposed order: expand paths and read `settings.tdl`; start logging with its `Logging` keys (or the default log directory if the file failed); open the registry at the configured path; then find and load shell files, modules, styles, themes and stylesheets. The `settings.tdl` file itself is found only at `$HOME/.config/tesserae-shell/settings.tdl` (the fixed point everything else is relative to); the directory spelling is still open in [ADR-0007 Shell UI Layer > Open items](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md#open-items).

## Reload

Decided 2026-10-27: `settings.tdl` is read at start and watched like any other file. A change to `Logging` applies at once; a change to `Directories` or `Main_Shell` takes effect on a shell restart, because it changes what is loaded. A reload that produces an invalid `settings.tdl` keeps the running settings and reports the error; only a start stops.

## A Bad Settings File Stops the Shell

Decided 2026-10-27: if `settings.tdl` cannot be read or fails validation, the shell does not start. It prints the error to the console and writes it to the log file, with `file:line:column`. It does not fall back to defaults, because a shell that starts with other settings than the user wrote hides the mistake and looks like a bug.

- The settings file configures logging, so a failure cannot use the file's own `Logging` keys. The error goes to the console and to the default log directory, `$HOME/.config/tesserae-shell/logs/` (decided 2026-10-27).
- A missing `settings.tdl` is not a failure: the defaults apply (see Acceptance criteria).
- The same stop-and-report rule is proposed for every path or directory error below.

## Errors Specific to This File

- A directory that does not exist, or a path with an unset variable or one that does not resolve: error with the key, the text written and what failed.
- A relative path in `Directories`: error with the key.
- A `Main_Shell` that is not in the shells directory: error naming the directories searched.
- An unknown key: error with the closest names, as in every file ([Common Keys and Conventions > Errors](Common%20Keys%20and%20Conventions.md#errors)).

## Open

- [x] The keys above are the starting set. Which other global settings belong here is deferred to building and testing the shell (maintainer, 2026-10-27); new keys are added to this note as they are found.
- [x] A configured directory list is searched first and the default folder is the fallback (decided 2026-10-27; reading confirmed by the maintainer the same day).
- [x] `~` and environment variables are allowed; an unresolved path is an error (decided 2026-10-27).
- [x] A bad `settings.tdl` stops the shell with an error on the console and in the log, in `$HOME/.config/tesserae-shell/logs/` (decided 2026-10-27).
- [x] `settings.tdl` is read before the registry, because it can move the registry (decided 2026-10-27).
- [x] Reload: `Logging` applies at once; `Directories` and `Main_Shell` need a restart (accepted as proposed, 2026-10-27).
- [x] Log file naming `log_yyyy-mm-dd.log`, a new file each local day, no deletion unless `Logging.Retention` is set (decided 2026-10-27). Open: a real midnight crossing, tested at the testing phase.
- [x] If the configured registry path has no registry, the shell creates an empty one (decided 2026-10-27). Moving the registry by hand: the user moves the file and sets `Registry` in `settings.tdl`; the shell uses the file at the new path. If files already carry UIDs and the registry is new or empty, the shell logs a warning and rebuilds each entry's registry record from the UID in its file rather than issuing new UIDs (recommendation adopted and confirmed by the maintainer, 2026-10-27; the rebuild rules belong to [ADR-0007 Shell UI Layer > UIDs and the registry (2026-10-25)](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md#uids-and-the-registry-2026-10-25) and are open there).
- [x] Per-monitor settings belong in the shell file's `Monitor` block, not here ([Shell File](Shell%20File.md), [TDL Language > Monitors (Shell Schema)](TDL%20Language.md#monitors-shell-schema)) (recommendation adopted 2026-10-27).
- [x] The name `settings.tdl` is confirmed (D20, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)).
- [x] The metadata form of `settings.tdl`: the root block `Settings { }` with a required `Name:` (D20 as revised by D26 and D39).
- [x] The Settings entry in the schema set: `settings.schema.json` ([JSON Schema and Editor Support > Files](JSON%20Schema%20and%20Editor%20Support.md#files)).

## Acceptance Criteria

- [ ] With no `settings.tdl`, the shell loads from the five folders, keeps the registry at `registry.json` and logs to `logs/`.
- [ ] A `Registry` path in `settings.tdl` makes the shell read and write the registry there, and not at the default path.
- [ ] A `Directories.Modules` entry makes the shell load modules from that path first; a module not found there is loaded from `Modules/`.
- [ ] `~/shell/Modules` and `$HOME/shell/Modules` resolve and load; an unset variable fails at start with the key and the text written.
- [ ] A settings file with an error stops the shell: the error is on the console and in the log, and no surface opens.
- [ ] A relative path in `Directories` fails at load with `file:line:column`.
- [ ] The same module name twice in the configured directories fails naming both files; the same name in a configured and the default folder uses the configured one and logs a notice.
- [ ] A `settings.tdl` with an unknown key fails with the nearest key names.

## Links

- [41 TDL Reference](41%20TDL%20Reference.md) · [Common Keys and Conventions](Common%20Keys%20and%20Conventions.md) · [Shell File](Shell%20File.md) · [JSON Schema and Editor Support](JSON%20Schema%20and%20Editor%20Support.md) · [ADR-0007 Shell UI Layer](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md)
