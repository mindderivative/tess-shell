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
    registry.json
    Shells/          Main_Shell.yaml, <Name>_Shell.yaml
    Modules/         <module_name>/<Name>_Module.yaml and .py
    Styles/          <Name>_Style.yaml
    Themes/          <Name>_Theme.yaml
    Stylesheets/     <Name>_Stylesheet.yaml
    schemas/         generated, ignored by version control
```

- Shell files live in `Shells/` (decided 2026-10-27). The folder names and the other four are from [[ADR-0007 Shell UI Layer#Modules, styles, themes and stylesheets live in the config directory (2026-10-27)]].
- `settings.yaml` can point to absolute directories for any of these types, for a user who wants a different layout (decided 2026-10-27). With no `settings.yaml`, or no key for a type, the folders above are used.
- `settings.yaml` is the home for settings that are not project based (decided 2026-10-27).
- The directory spelling (`$HOME/.config` against `$XDG_CONFIG_HOME`) is an open item in [[ADR-0007 Shell UI Layer#Open items]].

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
| `logging` | Global log settings | Level and file location; keys set by [[Logging with Loguru]] |
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

- A value in `directories` is a path or a list of paths, searched in order. A relative path is an error: it would depend on the working directory. Whether `~` and environment variables are allowed is open.
- A configured list replaces the default folder for that type; the user adds the default explicitly if they want both. This is a recommendation; the alternative is to search the default last.
- A name found in two directories is an error naming both, as a duplicate unique name is ([[Common Keys and Conventions#Names and references]]).
- Files found through a configured directory are registered like any other. Their editor modelines cannot always be relative to the config directory, so the shell writes an absolute path for them ([[JSON Schema and Editor Support#Where the schemas live]]).

## Reload

Proposed: `settings.yaml` is read at start and watched like any other file. A change to `logging` applies at once; a change to `directories` or `main_shell` takes effect on a shell restart, because it changes what is loaded. Open.

## Errors specific to this file

- A directory that does not exist: error with the key and the path.
- A relative path in `directories`: error with the key.
- A `main_shell` that is not in the shells directory: error naming the directories searched.
- An unknown key: error with the closest names, as in every file ([[Common Keys and Conventions#Errors]]).

## Open

- [ ] The keys above (accept or change them), and which other global settings belong here.
- [ ] A configured directory list replacing the default, or searched after it.
- [ ] `~` and environment variables in paths.
- [ ] Whether `settings.yaml` is read before the registry, and whether a bad file stops the shell or falls back to defaults.
- [ ] Reload behaviour for each key.
- [ ] Per-monitor settings: they belong in the shell file's `root`, not here ([[Shell File]]).
- [ ] The Settings entry in the schema set ([[JSON Schema and Editor Support#Files]]).

## Acceptance criteria

- [ ] With no `settings.yaml`, the shell loads from the five folders and starts `Main_Shell.yaml`.
- [ ] A `directories.modules` entry makes the shell load modules from that path and not from `Modules/`.
- [ ] A relative path in `directories` fails at load with `file:line:column`.
- [ ] The same module name in two directories fails naming both files.
- [ ] A `settings.yaml` with an unknown key fails with the nearest key names.

## Links

- [[41 YAML Reference]] · [[Common Keys and Conventions]] · [[Shell File]] · [[JSON Schema and Editor Support]] · [[ADR-0007 Shell UI Layer]]
