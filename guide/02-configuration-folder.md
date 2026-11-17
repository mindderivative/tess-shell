# 2. The configuration folder

Everything you write lives in one folder. The shell reads it at start and again whenever a file in it changes.

## Where it is

The shell uses, in this order:

1. the folder named by `--config-dir PATH`, if the command has it;
2. `$XDG_CONFIG_HOME/tesserae-shell`, if `XDG_CONFIG_HOME` is set to an absolute path;
3. `~/.config/tesserae-shell`.

`tesserae-shell version --json` prints the one it would use (`config_dir`). `run` creates the folder and the six folders below on first start; `check` never creates anything and exits with code 2 if the folder does not exist.

## What is in it

```text
~/.config/tesserae-shell/
  settings.tdl        the shell's own settings (optional)
  registry.json       made by the shell: identifiers and saved Panel positions
  logs/               made by the shell: one log file for each day
  Shells/             *_Shell.tdl       what is on the screen: Monitors, Bars, Panels, ...
  Modules/            *_Module.tdl      your own modules (a layout, with a .py beside it)
  Styles/             *_Style.tdl       style files that a module of yours names
  Themes/             *_Theme.tdl       colours, type and other tokens
  Stylesheets/        *_Stylesheet.tdl  rules that give blocks their look
  Icons/              *.json            icon sets of your own
```

How the shell finds a file:

* **By its ending.** A file in `Shells/` is a shell file only if its name ends in `_Shell.tdl`; the other folders work the same way with their own ending. Other files (`notes.tdl`, `Main_Shell.tdl.bak`, an editor's `~` and `.swp` files, anything that starts with a dot) are ignored. Sub-folders are searched too, except `schemas`, `logs` and `backups` and any folder that starts with a dot.
* **The shell's own files come last.** The shell ships its modules (the ones in [page 5](05-modules.md)), a `Default` theme, a `Default` stylesheet and the `mdi` icon set. A file of yours with the same name overrides the shipped one; this is how you change a module's look or behaviour. Two files of your own with the same `Name` in their metadata are an error (`name-duplicate`).
* **The main shell.** The shell that is shown is the file named by `Main_Shell` in [`settings.tdl`](07-settings.md); it is `Main_Shell.tdl` if you write nothing. Every other `*_Shell.tdl` is still checked, but not shown.
* **More folders.** `Directories { Shells: ..., Modules: ... }` in `settings.tdl` adds folders to search for each kind of file (an absolute path or one starting with `~`, which must exist); the folder in the configuration folder is always searched as well.

`Styles/` is for the style files that a module names with a `Style:` line (the shipped modules do this); a shell file does not import one. A shell file takes its look from the stylesheets named in `settings.tdl`; see [Styling and themes](06-styling.md).

## What a file starts with

Every file begins with a metadata block between two `---` lines, then one root block whose name matches the file's ending (`Shell { }` in a `_Shell.tdl`, `Module { }` in a `_Module.tdl`, `Theme { }`, `Stylesheet { }`, `Style { }`; `settings.tdl` holds `Settings { }`):

```tdl
---
TDL: 0.2
Name: Main_Shell
---
Shell {
}
```

* `TDL: 0.2` is the version of the language. The shell reads TDL 0.2 only. A file that says `TDL: 0.1` is refused with `tdl-old-version` ("this file is written for TDL 0.1; the shell reads TDL 0.2") and a hint on how to migrate it; one that says a newer version is refused with `version-pin`.
* `Name:` is the file's name. For a theme or a stylesheet it is what `settings.tdl` refers to (`Theme: Dusk`), and for a module it is the name you use it by. Letters, digits and `_`, starting with a letter.
* `Shell: 0.1` (optional) is a minimum-version pin: the shell refuses the file if it is older than that.
* `UID:` is written by the shell, as described below.
* A root block that does not match the ending (a `Theme { }` in a `_Shell.tdl`) is an error, `shell-root-suffix`.

A `#` starts a comment that runs to the end of the line.

## Identifiers and backups

The first time the shell registers one of your shell files or module files, it adds a `UID:` line to the file's metadata block. The line holds a unique identifier that the shell uses to recognise the file after you rename or move things. It changes nothing else in the file, byte for byte, and it never touches the files the shell ships. Themes, stylesheets and `settings.tdl` get none.

Before the shell edits a file it copies it to its state folder, `$XDG_STATE_HOME/tesserae-shell/backups` (`~/.local/state/tesserae-shell/backups` by default), as `<path inside the configuration folder>.<YYYYMMDDTHHMMSS>`. The backup is outside your configuration folder on purpose, so it is never read as a shell file. If the write fails (a read-only file, say) the shell logs a `uid-write` warning, keeps the identifier in `registry.json` and leaves your file as it was. The shell's own write does not cause a reload.

The state folder also holds `launcher-counts.json`, how many times you started each application from the [Launcher](08-keyboard.md#the-launcher).

`registry.json` (in the configuration folder, or where `Registry` in `settings.tdl` says) holds the identifiers of the things the shell has met and the saved position of every Panel with `Movable: true`. The shell writes it; leave it alone while the shell runs.

## A configuration folder with a module of your own

The shell finds a module in `Modules/` by its `Name`, and a shell file uses it like a shipped one. A module is a layout in a `_Module.tdl` file and, if it has any behaviour, a Python file of the same name beside it. This one greets you by the time of day:

<!-- BEGIN generated: example-set:02-config-folder/my-config -->
File `settings.tdl`:

```tdl
---
TDL: 0.2
Name: Settings
---
# settings.tdl: the shell's own settings. Every key is optional; a missing file means defaults.
Settings {
    Main_Shell: "Main_Shell.tdl"
    Hot_Reload: true
    Reload_Debounce: 200
    Logging { Level: INFO, Retention: 14 }
    Appearance { Stylesheets: [Default], Follow_Desktop: true }
}
```

File `Shells/Main_Shell.tdl`:

```tdl
---
TDL: 0.2
Name: Main_Shell
---
# A shell file may use any module found in Modules/, next to the ones the shell ships.
Shell {
    Monitor {
        Name: Main
        Index: default
        Children {
            Bar {
                Name: Top_Bar
                Edge: TOP
                Width: EXPAND
                Height: 32
                Style { Background: $color.surface }
                Children {
                    FlexBox {
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Align_Items: CENTER
                        Padding: [12, 0, 12, 0]
                        Children {
                            Greeting { name: "Ada" }
                            Spacer { }
                            Clock { }
                        }
                    }
                }
            }
        }
    }
}
```

File `Modules/Greeting/Greeting_Module.py`:

```python
"""Greeting: a module of your own. The class name is the module's Name."""

from __future__ import annotations

from datetime import datetime

from tess_shell import Module


class Greeting(Module):
    def start(self) -> None:
        self.tick()
        self.ctx.on_tick("minute", self.tick)

    def tick(self) -> None:
        hour = datetime.now().hour
        text = "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening"
        self.ctx.send("greeting", text)  # every use of the module gets it
```

File `Modules/Greeting/Greeting_Module.tdl`:

```tdl
---
TDL: 0.2
Name: Greeting
---
# The layout of a module of your own: params, and a block tree that reads what the Python sends
# with <| ... |>. This one greets by the time of day.
Module {
    Params {
        name { Type: string, Default: "there" }
    }
    Text {
        Text: <| greeting + ", " + params.name |>
        Label: <| greeting + ", " + params.name |>
    }
}
```

<!-- END generated: example-set:02-config-folder/my-config -->

* The `Params` block lists what a use may set (`Greeting { name: "Ada" }`). A param has a `Type` (`string`, `number`, `boolean`, `path` or `icon`) and an optional `Default`; a param with no default must be given.
* A `<| ... |>` is a slot: an expression whose value the layout shows and keeps up to date. `params.name` is a param; `greeting` is a value the Python sent.
* In the Python file the class has the module's name, `start` runs once, and `self.ctx.send("greeting", text)` sends a value to every use. `self.ctx.on_tick("minute", fn)` calls `fn` at the start of every minute. The module's `@action` methods are what `On_Click { Action: Call, Target: "Module.action" }` and `tesserae-shell call` run.

This guide stops at the shape of a module. Writing one is covered by the design notes ([Module File](../docs/41%20TDL%20Reference/Module%20File.md) and the Python API notes in `docs/`).

You can also use a module by file path instead of by name: `Import: ../Modules/Greeting/Greeting_Module.tdl` in place of the `Greeting { }` line, with a path relative to the shell file. `Import:` of another shell file is not built yet.

## Hot reload

While the shell runs it watches `settings.tdl` and the folders above (including the ones named in `Directories`). When you save a file, about 200 milliseconds after the last change the shell:

1. reads and checks every file in the folder, exactly as it does at start;
2. if everything is valid, applies what changed: your new Bars, Panels and modules appear, changed ones are updated in place, removed ones close. Windows of surfaces that did not change are not recreated;
3. if any file has an error, changes **nothing**: the shell keeps showing what it showed, prints the errors and logs them.

An error is reported with the file, the line and the column, the line itself with a caret under the place, and a hint where there is one:

```text
Shells/Main_Shell.tdl:5:7: error: This block is never closed.
  5 |  Shell {
    |        ^
    hint: Add the missing }
```

Fix the file and save again; the next reload starts from the files as they then are. An editor that saves by writing a temporary file and renaming it is fine.

Other ways to reload:

* `tesserae-shell reload` checks everything and applies it, and answers after the apply: `reloaded (...) in 120 ms`, or the errors and exit code 1.
* `SIGHUP` to the shell process reloads everything: `kill -HUP $(pgrep -f 'tesserae-shell run')`.

Hot reload is switched off with `Hot_Reload: false` in `settings.tdl`; `reload` and `SIGHUP` still work then. `Reload_Debounce` (milliseconds, default 200) sets how long the files must be quiet first; the shell reads it when it starts.

What a reload does not apply: `Directories`, `Registry`, `Main_Shell`, the `Debug` block and `Appearance.Follow_Desktop` need a restart, and the shell logs a warning naming the one you changed (`settings.tdl: Debug applies after a restart`). `Control` and the `KWin` block need a restart too. What it does apply at once: the shell files, modules (a module's Python file too), themes, stylesheets, icons, `Logging`, `Appearance.Theme` and `Appearance.Stylesheets`, and the `Shortcuts` and `Global_Shortcuts` settings.

Next: [your first Bar](03-first-bar.md).
