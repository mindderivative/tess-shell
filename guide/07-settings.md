# 7. `settings.tdl`

`settings.tdl` in the [configuration folder](02-configuration-folder.md) holds the shell's own settings, as opposed to what is on the screen. It is optional: with no file every setting has its default. Its root block is `Settings { }`.

A key the shell does not know is an error with a hint naming the nearest keys, and a `settings.tdl` with an error stops `run` before anything is shown (exit code 1) and refuses a reload. The tables below are generated from the schema, so they list every key that exists.

This file shows every key once, with its default or a typical value:

<!-- BEGIN generated: example-set:07-settings/every-key -->
File `settings.tdl`:

```tdl
---
TDL: 0.2
Name: Settings
---
# Every key of settings.tdl once, with its default or a typical value.
Settings {
    Main_Shell: "Main_Shell.tdl"
    Hot_Reload: true
    Reload_Debounce: 200
    Control: true
    Global_Shortcuts: true

    Logging {
        Level: INFO
        Directory: "~/.local/state/tesserae-shell/logs"
        Retention: 14
        Format: TEXT
        Diagnose: false
        Console: true
    }

    Validation { Enabled: true }

    Appearance {
        Theme: Default
        Stylesheets: [Default]
        Follow_Desktop: true
    }

    KWin {
        Script: RUNTIME
        Hide_On_Fullscreen: true
    }

    Shortcuts {
        Toggle_Launcher: "Meta+Space"
    }

    Debug {
        Panel_Hide: KEEP
        Frame_Blend: LINEAR
        Mode_Keyboard: EXCLUSIVE
        User_Modules_In_Process: false
    }
}
```

File `Shells/Main_Shell.tdl`:

```tdl
---
TDL: 0.2
Name: Main_Shell
---
Shell {
    Monitor {
        Name: Main
        Index: default
        Children {
            Bar { Name: Top_Bar, Edge: TOP, Width: EXPAND, Height: 28 }
        }
    }
}
```

<!-- END generated: example-set:07-settings/every-key -->

Booleans are `true` and `false` in lower case, and words such as `INFO` are upper case. A path is a quoted string that starts with `/` or `~` (a `$VAR` is expanded; one that is not set is an error).

## Settings

The keys of the `Settings` block itself:

<!-- BEGIN generated: settings:Settings -->
| Key | Value | Default | What it does |
|---|---|---|---|
| `Main_Shell` | path | `"Main_Shell.tdl"` | The shell file to start, looked up in the Shells directories. |
| `Registry` | path | none | The registry file that remembers UIDs and positions; an absolute path. |
| `Directories` | block | none | Extra folders to search for each kind of file. |
| `Logging` | block | none | Where and how the shell logs. |
| `Validation` | block | none | Whether files are validated at load. |
| `Hot_Reload` | true or false | `true` | Applies a saved file to the running shell. |
| `Reload_Debounce` | number | `200` | How long files must be quiet before a reload, in milliseconds. |
| `Appearance` | block | none | The theme and the stylesheets in use. |
| `Debug` | block | none | Switches for finding a fault. |
| `Control` | true or false | `true` | Whether the shell exports its control interface on the session bus (the tesserae-shell commands); a restart applies it. |
| `Shortcuts` | block | none | The shell's global keys, one Name: "keys" entry for each action; a hot reload applies it. |
| `Global_Shortcuts` | true or false | `true` | Whether the shell registers its keys with the desktop's shortcut service; false makes no call to it at all. A hot reload applies it. |
| `KWin` | block | none | What the shell does with KWin: its script and fullscreen hiding. |

<!-- END generated: settings:Settings -->

* `Main_Shell` is the shell file that is shown. It is looked up in the `Shells` folders. If you write it and no such file exists it is an error (`main-shell-not-found`); if you write nothing and there is no `Main_Shell.tdl`, the shell starts and shows nothing.
* `Registry` must be an absolute path whose folder exists. Moving the file by hand and setting `Registry` is how you move it.
* `Hot_Reload: false` stops the watcher; `reload` and `SIGHUP` still reload. See [hot reload](02-configuration-folder.md#hot-reload).
* `Control: false` makes the shell export no bus name, so no `tesserae-shell` control command can reach it (they exit with code 3); `run` and `check` still work. A restart applies it.
* `Global_Shortcuts: false` makes no call to the desktop's shortcut service at all. A hot reload applies it. See [Keyboard and shortcuts](08-keyboard.md#global-shortcuts).
* Changes to `Directories`, `Registry` and `Main_Shell` apply after a restart; the other keys apply on reload as the schema's descriptions say.

## Directories

Extra folders to search for each kind of file, each an absolute path (or `~/...`) of a folder that exists; a list is written `[a, b]`. The folder of that name in the configuration folder is always searched as well.

<!-- BEGIN generated: settings:Directories -->
| Key | Value | Default | What it does |
|---|---|---|---|
| `Shells` | path | none | Folders searched for shell files. |
| `Modules` | path | none | Folders searched for module files. |
| `Styles` | path | none | Folders searched for style files. |
| `Themes` | path | none | Folders searched for theme files. |
| `Stylesheets` | path | none | Folders searched for stylesheet files. |
| `Icons` | path | none | Folders searched for icon sets. |

<!-- END generated: settings:Directories -->

For a folder named here the order is: the folders you list, in order, then the one in the configuration folder, then (for modules, themes and stylesheets) the shell's own. For `Icons` the one in the configuration folder comes first. A path that is not a folder is an error (`missing-directory`).

## Logging

<!-- BEGIN generated: settings:Logging -->
| Key | Value | Default | What it does |
|---|---|---|---|
| `Level` | `TRACE` `DEBUG` `INFO` `SUCCESS` `WARNING` `ERROR` `CRITICAL` | `INFO` | The least severe message that is logged. |
| `Directory` | path | none | The folder of the log files; the default is logs in the config directory. |
| `Retention` | whole number | none | How many days of log files are kept; leaving it out keeps them all. |
| `Format` | `TEXT` `JSON` | `TEXT` | TEXT for lines a person reads, JSON for lines a program reads. |
| `Diagnose` | true or false | `false` | Adds the values of variables to a logged traceback. |
| `Console` | true or false | `true` | Also logs to the terminal. |
| `Capture_Stderr` | true or false | `true` | Routes the standard error stream into the log. |

<!-- END generated: settings:Logging -->

* The log is a text file for each day, `log_YYYY-MM-DD.log`, in the `Directory` (by default `logs/` in the configuration folder), created readable by you only; a new file starts at local midnight. `Retention: 14` deletes the log files older than 14 days when the shell starts and at each midnight; it touches nothing but `log_*.log` files. Leaving `Retention` out keeps them all.
* A line is `time | LEVEL | source | location | message`; with `Format: JSON` each line is a JSON object instead.
* `Console: true` also writes to the terminal (to the journal when started by `systemd`). `tesserae-shell run --quiet` limits the terminal to warnings and errors. If the log folder cannot be written, the shell says so once and logs to the terminal only.
* `Level` applies at once on a reload. `tesserae-shell log-level DEBUG` changes the level for the running shell until the next reload of `settings.tdl`.
* `Capture_Stderr` is accepted and stored but does nothing yet: Python's own `logging` and `warnings` output is not routed into the log.
* `Diagnose: true` adds the values of variables to a logged traceback; leave it off unless you are reporting a bug (the values can be private).

## Validation

<!-- BEGIN generated: settings:Validation -->
| Key | Value | Default | What it does |
|---|---|---|---|
| `Enabled` | true or false | `true` | Whether files are checked against the schema at load. |

<!-- END generated: settings:Validation -->

`Enabled` is accepted and stored but does nothing yet: the shell checks every file whatever it says.

## Appearance

<!-- BEGIN generated: settings:Appearance -->
| Key | Value | Default | What it does |
|---|---|---|---|
| `Theme` | text | none | The Name of the theme to use; the shell's Default theme when left out. |
| `Stylesheets` | list of text | none | The Name of a stylesheet or a list of them, lowest priority first. |
| `Follow_Desktop` | true or false | `true` | Follows the desktop's colour scheme, accent, contrast and reduced-motion settings. |

<!-- END generated: settings:Appearance -->

See [Styling and themes](06-styling.md). `Theme` and `Stylesheets` apply on reload; `Follow_Desktop` needs a restart.

## Shortcuts

The shell's keys. This block has one entry for each action (`Toggle_Launcher: "Meta+Space"`), plus the five fixed actions of shortcut mode:

<!-- BEGIN generated: settings:Shortcuts -->
| Key | Value | Default | What it does |
|---|---|---|---|
| `Enter_Shortcut_Mode` | key | none | The key that puts the shell in shortcut mode: the one global key of the mode, registered with the desktop. |
| `Exit_Shortcut_Mode` | key | none | The key that leaves shortcut mode. It acts inside the mode only (a key event on the surface that has the keyboard); it is not registered with the desktop. |
| `Set_Shortcut_Mode` | key | none | The key that turns shortcut mode on or off for the focused surface. It acts inside the mode only; it is not registered with the desktop. |
| `Next_Focus` | key | none | The key that moves focus to the next surface in shortcut mode. It acts inside the mode only; it is not registered with the desktop. |
| `Previous_Focus` | key | none | The key that moves focus to the previous surface in shortcut mode. It acts inside the mode only; it is not registered with the desktop. |

<!-- END generated: settings:Shortcuts -->

The other entries (`Toggle_<Name>`, `Show_<Name>`, `Hide_<Name>` and blocks with `Keys` and `Action`) are described in [Keyboard and shortcuts](08-keyboard.md#global-shortcuts). A hot reload applies changes with no restart.

## KWin

What the shell does with KWin:

<!-- BEGIN generated: settings:KWin -->
| Key | Value | Default | What it does |
|---|---|---|---|
| `Script` | `RUNTIME` `PERSISTENT` `OFF` | `RUNTIME` | How the shell's KWin script runs: RUNTIME loads it into KWin when the shell starts and unloads it at stop, PERSISTENT leaves it to the one installed by tesserae-shell kwin script install, OFF loads nothing (no fullscreen hiding, no window list). A restart applies it. |
| `Hide_On_Fullscreen` | true or false | `true` | Hides the shell's surfaces on an output while a fullscreen window is active there, and shows them again when it leaves. A restart applies it. |

<!-- END generated: settings:KWin -->

The shell loads a small **KWin script** when it starts (`Script: RUNTIME`) and unloads it when it stops. The script reports which monitors have an active fullscreen window, on which the shell hides its Bars, Panels, Frame and Popups (`Hide_On_Fullscreen`), and, only while a [Tasks](05-modules.md#tasks) module is in use, the list of open windows. `PERSISTENT` leaves loading to the script that `tesserae-shell kwin script install` puts in KWin's scripts folder, so KWin runs it from login; `OFF` loads nothing, so there is no fullscreen hiding and no window list. A restart applies the setting. See [the command line](09-command-line.md#the-kwin-commands) for the install commands.

The `KWin` block and the script it controls were added after 0.1.1 ([Install and start](01-install.md#what-is-newer-than-the-011-release)).

> **Not yet checked on KWin:** loading the script into a real KWin, its fullscreen reports and the `kwin script` commands have been built and tested against fakes; the maintainer's hand check of them is still open. If KWin is not found the shell logs `kwin: org.kde.KWin is not on the session bus ...` at INFO and runs on without them.

## Debug

Switches for finding a fault, and a few choices that were left open so they could be compared. A restart applies all of them (a reload warns that it did not).

<!-- BEGIN generated: settings:Debug -->
| Key | Value | Default | What it does |
|---|---|---|---|
| `Panel_Hide` | `CLOSE` `KEEP` | `KEEP` | How a Panel is hidden: KEEP leaves the surface mapped and draws nothing, CLOSE destroys the window. |
| `Frame_Join` | `SMIL` `CONCAVE` `SHADER` `STRUCTURE` `PARAM` | `PARAM` | How the join of a melded Panel animates: PARAM, SMIL, CONCAVE, SHADER or STRUCTURE. A restart applies it. |
| `Frame_Blend` | `SRGB` `LINEAR` | `LINEAR` | How the Frame's ring is blended: LINEAR in linear light or SRGB. A restart applies it. |
| `Mode_Keyboard` | `EXCLUSIVE` `ON_DEMAND` | `EXCLUSIVE` | The keyboard mode the surface that has the focus takes while the shell is in shortcut mode: EXCLUSIVE (the one way a layer surface takes the keyboard without a click) or ON_DEMAND (for a compositor that hands focus over after a global key). A restart applies it. |
| `User_Modules_In_Process` | true or false | `false` | Keeps the Python of your own modules in the shell's process instead of a process each (the default, false): a module that hangs or crashes then freezes or ends the shell, and Event.stop() works. A restart applies it. |

<!-- END generated: settings:Debug -->

* `Panel_Hide`: `KEEP` leaves a hidden Panel's window mapped and draws nothing, so it keeps its state; `CLOSE` destroys the window and makes a new one when it is shown.
* `Frame_Join` and `Frame_Blend` choose how a melded Panel's join with the Frame, and the Frame's ring, are drawn. `Frame_Blend: LINEAR` (the default) draws the ring in one shader that blends in linear light, so a light border is as wide on a curve as on a straight; the shell falls back to drawing with paths, with one warning saying why, for a Frame the shader cannot draw (a translucent colour, an `Opacity` below 1, a Panel with `FADE`, more than eight melded bodies). `SRGB` draws paths throughout.
* `Mode_Keyboard` is the keyboard mode the surface in shortcut mode asks the compositor for: `EXCLUSIVE` (the default; on Wayland a layer surface cannot take the keyboard without a click or an exclusive request) or `ON_DEMAND`, for a compositor that hands focus over after a global key. **Not yet checked on KWin:** which of the two KWin needs. If shortcut mode's keys do not arrive, try the other.

* `User_Modules_In_Process` (default `false`): your own modules' Python (a module file in your configuration folder, not one that ships with the shell) runs in a process of its own, so a module that hangs or crashes does not freeze the bars ([page 2](02-configuration-folder.md#trust-and-security)). `true` keeps it in the shell's own process, as before: for a module that needs `Event.stop()`, or to find out whether the process is the cause of a problem. A restart applies it.

Next: [keyboard and shortcuts](08-keyboard.md).
