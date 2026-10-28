---
title: Settings File
aliases: [settings.yaml, Shell Settings, Config Directory Layout]
type: yaml-ref
status: draft
owner: phil
created: 2026-10-27
updated: 2026-10-27
tags: [yaml-ref, runtime]
related: ["[[41 YAML Reference]]", "[[Common Keys and Conventions]]", "[[Shell File]]", "[[Module File]]", "[[Style, Theme and Stylesheet Files]]", "[[JSON Schema and Editor Support]]", "[[ADR-0007 Shell UI Layer]]", "[[Logging with Loguru]]"]
depends_on: ["[[ADR-0007 Shell UI Layer]]"]
---

# Settings file

> [!summary]
> The config directory, `$HOME/.config/tesserae-shell/`, holds the shell's files in fixed folders. One file at its root, `settings.yaml`, holds settings that are not tied to a single shell: where to look for files when the user wants a different layout, which shell file to start, and global behaviour. The folder layout and the file are the maintainer's (2026-10-27); the keys below are proposed.

## The config directory

```text
$HOME/.config/tesserae-shell/
    settings.yaml
    registry.json    default place; `settings.yaml` can move it
    Shells/          Main_Shell.yaml, <Name>_Shell.yaml
    Modules/         <module_name>/<Name>_Module.yaml and .py
    Styles/          <Name>_Style.yaml
    Themes/          <Name>_Theme.yaml
    Stylesheets/     <Name>_Stylesheet.yaml
    schemas/         generated, ignored by version control
    logs/            log files (default)
```

- Shell files live in `Shells/` (decided 2026-10-27). The folder names and the other four are from [[ADR-0007 Shell UI Layer#Modules, styles, themes and stylesheets live in the config directory (2026-10-27)]].
- `settings.yaml` can point to absolute directories for any of these types, for a user who wants a different layout (decided 2026-10-27). With no `settings.yaml`, or no key for a type, the folders above are used.
- `settings.yaml` is the home for settings that are not project based (decided 2026-10-27).
- **Where the config directory is** (decided 2026-10-27, "whichever is safer for the operating system"): `$XDG_CONFIG_HOME/tesserae-shell/` when `XDG_CONFIG_HOME` is set, non-empty and an absolute path; otherwise `$HOME/.config/tesserae-shell/`. This follows the XDG base directory specification: an unset or empty variable means `$HOME/.config`, and a relative value is invalid and ignored ([spec](https://specifications.freedesktop.org/basedir/latest/)). The cache directory follows the same rule with `XDG_CACHE_HOME` and `$HOME/.cache`. Every note that writes `$HOME/.config/tesserae-shell/` means this directory at its default.

## File header

```yaml
shell: v1
type: Settings
```

`type: Settings` is a sixth file type; the name is fixed (`settings.yaml`, not `<Name>_Settings.yaml`) because there is one per config directory. Proposed: it carries no `name` and no `UID`, and is not entered in the registry. [[AGENTS#9. Naming in the designed system]] lists the file suffixes and types; adding `Settings` there is the maintainer's edit.

## Keys (proposed)

| Key | Meaning | Value |
|---|---|---|
| `directories` | Where to look for each file type | A mapping from `shells`, `modules`, `styles`, `themes`, `stylesheets` to an absolute directory or a list of them |
| `main_shell` | The shell file the shell starts from | A file name in the shells directory; default `Main_Shell.yaml` |
| `registry` | Where the registry file lives | An absolute path to a `registry.json` file; default `$HOME/.config/tesserae-shell/registry.json`. Same path rules as `directories` |
| `logging` | Global log settings | `level`, `directory` (default `logs/` in the config directory, same path rules) and `retention` (optional, days); naming and rotation are in [[#Log files]] |
| `validation` | Schema validation settings | `enabled` (default true); the cache location is [[JSON Schema and Editor Support#The `jsonschema` dependency runtime, not only development]] |

```yaml
shell: v1
type: Settings

directories:
    modules:
        - /home/phil/Projects/shell/Modules
        - /home/phil/.config/tesserae-shell/Modules
    themes: /home/phil/Projects/shell/Themes

main_shell: Main_Shell.yaml

logging:
    level: info
```

- A value in `directories` is a path or a list of paths, searched in order (decided 2026-10-27).
- **Fallback to the default.** The default folder for the type, inside the config directory, is searched after the configured ones (decided 2026-10-27, read as "fallback to defaults"). A name found in a configured directory is used and the default is not consulted for it; a name found only in the default folder is used from there. When the same name exists in both, the configured one wins and the shell logs a notice at info level naming both files (proposed). The maintainer confirmed this reading on 2026-10-27.
- **Paths.** `~` and environment variables are allowed (decided 2026-10-27). The shell expands them, and the result must be an absolute path. If a variable is unset or the path does not resolve, that is an error naming the key, the text written and what failed. There is no silent empty value. A path that resolves to a directory that does not exist is an error too. A relative path after expansion is an error: it would depend on the working directory.
- A name found twice in the same tier (two configured directories) is an error naming both files, as a duplicate unique name is ([[Common Keys and Conventions#Names and references]]).
- Files found through a configured directory are registered like any other. Their editor modelines cannot always be relative to the config directory, so the shell writes the expanded, absolute path for them (never `~` or a variable) ([[JSON Schema and Editor Support#Where the schemas live]]).

## Log files

Decided 2026-10-27; the details marked below were settled by adopting the recommendations the same day.

- **Name.** `log_yyyy-mm-dd`, with a `.log` extension: `log_2026-10-27.log`. The extension lets editors and log tools recognise the file.
- **Rotation.** A new day is a new log file. The day changes at local midnight (Loguru's timestamps are local time, [Loguru API](https://loguru.readthedocs.io/en/stable/api/logger.html)). A shell that runs across midnight writes the next file from then. A restart on the same day appends to that day's file.
- **Retention.** Up to the user: by default the shell deletes nothing. An optional `logging.retention` key holds a number of days; when set, the shell deletes only files in the log directory that match `log_yyyy-mm-dd.log` and are older than that many days, checked at start and at each midnight. Any other file in the folder is left alone.
- **How it is built.** The shell computes the file name from the local date and swaps the Loguru sink at midnight (add the new day's sink, then remove the old one). It does not use Loguru's own rotation. A test with Loguru 0.7.3 on this machine (2026-10-27) showed why: a path `log_{time:YYYY-MM-DD}.log` is accepted and gives `log_2026-10-27.log`, and a restart appends to it, but a rotation renames the finished file with a timestamp suffix (`log_2026-10-27.2026-10-27_20-50-15_081151.log`), so the files would not be named `log_yyyy-mm-dd` after a rotation. The swap keeps the names exact. Loguru's own retention option is not used either. A real midnight crossing was not tested. #needs-verification

## Start order

Decided 2026-10-27: `settings.yaml` is read first, before the registry, because it can move the registry to a custom location. Proposed order: expand paths and read `settings.yaml`; start logging with its `logging` keys (or the default log directory if the file failed); open the registry at the configured path; then find and load shell files, modules, styles, themes and stylesheets. The `settings.yaml` file itself is found only at `$HOME/.config/tesserae-shell/settings.yaml` (the fixed point everything else is relative to); the directory spelling is still open in [[ADR-0007 Shell UI Layer#Open items]].

## Reload

Decided 2026-10-27: `settings.yaml` is read at start and watched like any other file. A change to `logging` applies at once; a change to `directories` or `main_shell` takes effect on a shell restart, because it changes what is loaded. A reload that produces an invalid `settings.yaml` keeps the running settings and reports the error; only a start stops.

## A bad settings file stops the shell

Decided 2026-10-27: if `settings.yaml` cannot be read or fails validation, the shell does not start. It prints the error to the console and writes it to the log file, with `file:line:column`. It does not fall back to defaults, because a shell that starts with other settings than the user wrote hides the mistake and looks like a bug.

- The settings file configures logging, so a failure cannot use the file's own `logging` keys. The error goes to the console and to the default log directory, `$HOME/.config/tesserae-shell/logs/` (decided 2026-10-27).
- A missing `settings.yaml` is not a failure: the defaults apply (see Acceptance criteria).
- The same stop-and-report rule is proposed for every path or directory error below.

## Errors specific to this file

- A directory that does not exist, or a path with an unset variable or one that does not resolve: error with the key, the text written and what failed.
- A relative path in `directories`: error with the key.
- A `main_shell` that is not in the shells directory: error naming the directories searched.
- An unknown key: error with the closest names, as in every file ([[Common Keys and Conventions#Errors]]).

## Open

- [x] The keys above are the starting set. Which other global settings belong here is deferred to building and testing the shell (maintainer, 2026-10-27); new keys are added to this note as they are found.
- [x] A configured directory list is searched first and the default folder is the fallback (decided 2026-10-27; reading confirmed by the maintainer the same day).
- [x] `~` and environment variables are allowed; an unresolved path is an error (decided 2026-10-27).
- [x] A bad `settings.yaml` stops the shell with an error on the console and in the log, in `$HOME/.config/tesserae-shell/logs/` (decided 2026-10-27).
- [x] `settings.yaml` is read before the registry, because it can move the registry (decided 2026-10-27).
- [x] Reload: `logging` applies at once; `directories` and `main_shell` need a restart (accepted as proposed, 2026-10-27).
- [x] Log file naming `log_yyyy-mm-dd.log`, a new file each local day, no deletion unless `logging.retention` is set (decided 2026-10-27). Open: a real midnight crossing, tested at the testing phase.
- [x] If the configured registry path has no registry, the shell creates an empty one (decided 2026-10-27). Moving the registry by hand: the user moves the file and sets `registry` in `settings.yaml`; the shell uses the file at the new path. If files already carry UIDs and the registry is new or empty, the shell logs a warning and rebuilds each entry's registry record from the UID in its file rather than issuing new UIDs (recommendation adopted and confirmed by the maintainer, 2026-10-27; the rebuild rules belong to [[ADR-0007 Shell UI Layer#UIDs and the registry (2026-10-25)]] and are open there).
- [x] Per-monitor settings belong in the shell file's `root`, not here ([[Shell File]]) (recommendation adopted 2026-10-27).
- [x] The Settings entry in the schema set: `settings.schema.json` ([[JSON Schema and Editor Support#Files]]).

## Acceptance criteria

- [ ] With no `settings.yaml`, the shell loads from the five folders, keeps the registry at `registry.json` and logs to `logs/`.
- [ ] A `registry` path in `settings.yaml` makes the shell read and write the registry there, and not at the default path.
- [ ] A `directories.modules` entry makes the shell load modules from that path first; a module not found there is loaded from `Modules/`.
- [ ] `~/shell/Modules` and `$HOME/shell/Modules` resolve and load; an unset variable fails at start with the key and the text written.
- [ ] A settings file with an error stops the shell: the error is on the console and in the log, and no surface opens.
- [ ] A relative path in `directories` fails at load with `file:line:column`.
- [ ] The same module name twice in the configured directories fails naming both files; the same name in a configured and the default folder uses the configured one and logs a notice.
- [ ] A `settings.yaml` with an unknown key fails with the nearest key names.

## Links

- [[41 YAML Reference]] · [[Common Keys and Conventions]] · [[Shell File]] · [[JSON Schema and Editor Support]] · [[ADR-0007 Shell UI Layer]]
