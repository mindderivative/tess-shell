# 9. The command line

`tesserae-shell` is one command with sub-commands. With no sub-command it runs the shell (`run`). `python -m tess_shell` is the same command.

```text
tesserae-shell [OPTIONS] COMMAND [ARGUMENTS]
```

The commands fall into three groups:

* **Files and installation**, which need no running shell: `run`, `check`, `version`, `schema`, `install-session`, and the `kwin` commands.
* **Control commands**, which talk to a running shell over the session bus: `reload`, `quit`, `status`, `show`, `hide`, `toggle`, `call` and `log-level`. They import only the standard library and a small D-Bus client, so they start fast enough to be bound to a key.
* `run` itself, the shell.

## Options and commands

These options are accepted by every command, before or after its name:

<!-- BEGIN generated: cli-global-options -->
| Option | What it does |
|---|---|
| `--config-dir PATH` | configuration directory |
| `--json` | machine readable output |
| `--quiet` | only warnings and errors |
| `--timeout SECONDS` | how long a control command waits for the shell (default 5) |

<!-- END generated: cli-global-options -->

The commands, with the arguments and options each adds:

<!-- BEGIN generated: cli-commands -->
| Command | Its own arguments and options | What it does |
|---|---|---|
| `tesserae-shell run` | none | start the shell (default) |
| `tesserae-shell check` | `--strict` | validate settings and shell files |
| `tesserae-shell version` | none | print versions |
| `tesserae-shell schema` | `--out FILE` | print the schema of the shell's files as JSON (with --json) |
| `tesserae-shell install-session` | `--print` `--enable` `--remove` `--force` | write the desktop file and the systemd user unit (--enable, --remove, --print) |
| `tesserae-shell reload` | none | reload the running shell and report the errors |
| `tesserae-shell quit` | none | stop the running shell |
| `tesserae-shell status` | none | show the running shell's state (--json: the shell's own JSON) |
| `tesserae-shell show` | `name` | show a Panel or a Frame by its Name |
| `tesserae-shell hide` | `name` | hide a Panel or a Frame by its Name |
| `tesserae-shell toggle` | `name` | toggle a Panel or a Frame by its Name |
| `tesserae-shell call` | `module` `action` `[args ...]` | call a module's @action (each ARG a JSON value, or text) |
| `tesserae-shell log-level` | `level` | change the log level until the next reload of settings.tdl |
| `tesserae-shell kwin` | a group | KWin helpers: the script and the window rule (no shell needs to run) |
| `tesserae-shell kwin script` | a group | the shell's KWin script, installed for KWin to run from login (mode P) |
| `tesserae-shell kwin script install` | `--kwinrc PATH` `--scripts-dir PATH` `--no-reload` | copy the script to KWin's scripts folder and enable it in kwinrc |
| `tesserae-shell kwin script remove` | `--kwinrc PATH` `--scripts-dir PATH` `--no-reload` | take the script and its kwinrc switch away |
| `tesserae-shell kwin script status` | `--kwinrc PATH` `--scripts-dir PATH` | report the package, the kwinrc switch and whether KWin has it loaded |
| `tesserae-shell kwin rule` | a group | the one window rule that keeps the shell's surfaces above Plasma panels (opt-in) |
| `tesserae-shell kwin rule show` | `--rules-file PATH` | print the rule group the shell would write to kwinrulesrc |
| `tesserae-shell kwin rule install` | `--rules-file PATH` `--no-reload` `--yes` | write that group (shows it and asks first, or takes --yes) |
| `tesserae-shell kwin rule remove` | `--rules-file PATH` `--no-reload` | take exactly that group out of kwinrulesrc |

<!-- END generated: cli-commands -->

The full `--help` of the program and of each command are at the end of this page.

## The commands in detail

### `run`

Starts the shell and keeps running in the foreground. It stops cleanly on `SIGTERM` or `SIGINT` (`Ctrl+C`) or on `tesserae-shell quit`; a second signal makes it leave at once with exit code 130. It needs a Wayland compositor with layer-shell and a usable `XDG_RUNTIME_DIR`. Under `systemd` it tells the manager when it is ready and when it is stopping. See [Install and start](01-install.md#the-first-run).

### `check`

Validates `settings.tdl` and every shell, module, style, theme and stylesheet file in the configuration folder, without a compositor, and creates nothing:

```text
ok: 3 files checked
```

or, for each finding, the file, line and column, the severity, the message, the offending line with a caret and a hint (see [hot reload](02-configuration-folder.md#hot-reload) for an example). It counts only your own files. A finding is an **error** (exit code 1) or a **warning**, which is printed but does not fail the check. At most 50 findings are printed, then `... and N more`. `--quiet` leaves out the `ok:` line.

`--strict` makes a warning fail the check too: the warnings are printed and the exit code is 1 (for a script or a git hook that wants a folder with no `insecure-permissions` or `image-not-found`).

If `settings.tdl` has an error, `check` stops there and reports only that.

With `--json` it prints one object:

```json
{"ok": true, "config_dir": "...", "files": 3, "errors": [], "omitted": 0}
```

Each entry of `errors` (warnings are in the list too) has `file`, `line`, `column`, `severity`, `rule`, `message` and `hint`. Exit codes: 0 no errors, 1 errors (or, with `--strict`, warnings), 2 the configuration folder does not exist.

`check` proves a file is valid, which includes that every key, module parameter and theme token named in it exists. It does not run modules or contact the desktop, so it cannot tell you that a `Call` names an action a module lacks (that is reported when the shell starts or reloads) or that a monitor name exists.

### `version`

Prints the versions of the shell, `tess_re`, `tess_el`, `tess_dl` and Python. `--json` prints them as one object with the folder the shell would read as `config_dir`.

### `schema`

`tesserae-shell schema --json` prints everything the loader accepts, as JSON: every block, surface, key, kind, choice, default, event, action, theme token and `settings.tdl` key, each with a line of documentation, so a configuration tool can build its forms. `--out FILE` writes it to a file instead. It is the data this guide's tables are generated from. Without `--json` the command answers `schema writes JSON only; add --json` and exits 1.

### `install-session`

Writes the desktop file and the `systemd` user unit that start the shell with your session. See [Install and start](01-install.md#starting-with-your-session).

### Control commands

A control command asks the running shell, which owns the session bus name `io.github.mindderivative.TesseraeShell`, to do something and prints the answer. With no shell running it says `no shell is running (nobody owns the bus name)` and exits 3.

| Command | What it does |
|---|---|
| `tesserae-shell reload` | Checks every file and applies it, and answers after the apply: `reloaded (...) in N ms`, or the errors and exit 1. |
| `tesserae-shell quit` | Stops the shell (`stopping`; exit 0 once it has been asked). |
| `tesserae-shell status` | Shows the state, the versions, the monitors, the surfaces, the modules and the last errors. `--json` prints the shell's own JSON. |
| `tesserae-shell show NAME`, `hide NAME`, `toggle NAME` | Shows, hides or toggles a Panel, a Frame, a melded Panel or a strip by its `Name`. See [Surfaces](04-surfaces.md#showing-hiding-and-toggling) for what it answers. |
| `tesserae-shell call MODULE ACTION [ARG ...]` | Runs an `@action` of a module. Each `ARG` is a JSON value (`40`, `true`, `"text"`) or, if it is not valid JSON, the text itself. The answer is printed. |
| `tesserae-shell log-level LEVEL` | Changes the log level of the running shell, `TRACE` to `CRITICAL`, until the next reload of `settings.tdl`. |

`status` prints something like:

```text
state: running
tesserae-shell <version> (tess_re <version>, python <version>)
monitors: Main (eDP-1)
surfaces:
  Launcher  panel  hidden  eDP-1
  Top_Bar  bar  shown  eDP-1
modules: Clock
last errors: none
```

It never lists a parameter's value or a line of the log. It also warns on standard error when the installed `systemd` unit points at a command that no longer exists, or at another installation than the one you ran `status` from, even when no shell is running.

`call` reaches only methods that a module marked as an `@action`; the actions of each shipped module are in its table on [page 5](05-modules.md). For example, with an `Audio` module in your shell:

```sh
tesserae-shell call Audio set_volume 40
tesserae-shell call Audio toggle_mute
```

No control command opens a Popup. `Settings { Control: false }` exports nothing, so every control command exits 3.

`--timeout SECONDS` (default 5) bounds the wait for the shell; after that the command says `the shell did not answer within 5 s (its loop is busy or stuck)` and exits 5. A running shell older than the command (after an upgrade you have not restarted) says `the running shell (version ...) does not know '...'; this client is version ...`.

### The `kwin` commands

These help the shell work with KWin. None needs a running shell.

* `tesserae-shell kwin script install | remove | status`: installs the shell's KWin script so that KWin runs it from login (the `PERSISTENT` mode of `KWin { Script }`). `install` copies the script's package into KWin's scripts folder, switches it on in `kwinrc` and asks KWin to reload; `remove` undoes exactly that; `status` reports the package, the `kwinrc` switch and whether KWin has the script loaded now. Options: `--kwinrc PATH`, `--scripts-dir PATH` to point at other files, `--no-reload`.
* `tesserae-shell kwin rule show | install | remove`: an **opt-in** window rule that keeps the shell's surfaces above Plasma's panels. `show` prints the rule group the shell would write to `kwinrulesrc`; `install` shows it, asks first (or takes `--yes`) and writes that group; `remove` takes exactly that group out. No other group is ever touched. If KWin cannot be asked to reload after a write, the file is put back as it was. Options: `--rules-file PATH`, `--no-reload`, `--yes`.

The `kwin` commands, like `install-session`, were added after 0.1.1 ([Install and start](01-install.md#what-is-newer-than-the-011-release)).

> **Not yet checked on KWin:** both the KWin script and the window rule are built and tested with temporary files and a fake KWin, but have not been confirmed on a real KWin by the maintainer's hand checks. Use `kwin rule show` first and read what it would write. You never need either for the shell to run: with the default `KWin { Script: RUNTIME }` the shell loads its script itself while it runs.

## Exit codes

<!-- BEGIN generated: exit-codes -->
| Code | Name | Meaning |
|---|---|---|
| 0 | `OK` | Done. |
| 1 | `CONFIG` | The files have errors (`check`, `run`, `reload`), a control command ran and failed (an unknown name, an action that raised), or `install-session` kept a file that differs. |
| 2 | `ENVIRONMENT` | The machine cannot run it: no Wayland compositor with layer-shell, no session bus, `XDG_RUNTIME_DIR` unusable, the config folder missing (`check`), or `systemctl` missing or refusing (`install-session`). |
| 3 | `NOT_RUNNING` | A control command found no running shell. |
| 4 | `ALREADY_RUNNING` | A second `run`: another shell holds the instance lock. |
| 5 | `TIMEOUT` | A control command got no answer within `--timeout` seconds. |
| 70 | `INTERNAL` | An unexpected error inside the shell (it is in the log). |
| 130 | `FORCED` | A second signal made the shell leave at once. |

<!-- END generated: exit-codes -->

With `--json` an error is also one object on standard output, `{"ok": false, "error": "...", "exit": 3}`, so a program that drives the command reads one stream. Which of these a command can return is listed with it above.

## `--help`

<!-- BEGIN generated: cli-help -->
```text
usage: tesserae-shell [-h] [--config-dir PATH] [--json] [--quiet]
                      [--timeout SECONDS]
                      COMMAND ...

positional arguments:
  COMMAND
    run              start the shell (default)
    check            validate settings and shell files
    version          print versions
    schema           print the schema of the shell's files as JSON (with
                     --json)
    install-session  write the desktop file and the systemd user unit
                     (--enable, --remove, --print)
    reload           reload the running shell and report the errors
    quit             stop the running shell
    status           show the running shell's state (--json: the shell's own
                     JSON)
    show             show a Panel or a Frame by its Name
    hide             hide a Panel or a Frame by its Name
    toggle           toggle a Panel or a Frame by its Name
    call             call a module's @action (each ARG a JSON value, or text)
    log-level        change the log level until the next reload of
                     settings.tdl
    kwin             KWin helpers: the script and the window rule (no shell
                     needs to run)

options:
  -h, --help         show this help message and exit
  --config-dir PATH  configuration directory
  --json             machine readable output
  --quiet            only warnings and errors
  --timeout SECONDS  how long a control command waits for the shell (default
                     5)
```

<!-- END generated: cli-help -->

Every command's own `--help`:

<!-- BEGIN generated: cli-command-help -->
#### tesserae-shell run --help

```text
usage: tesserae-shell run [-h] [--config-dir PATH] [--json] [--quiet]
                          [--timeout SECONDS]

options:
  -h, --help         show this help message and exit
  --config-dir PATH  configuration directory
  --json             machine readable output
  --quiet            only warnings and errors
  --timeout SECONDS  how long a control command waits for the shell (default
                     5)
```

#### tesserae-shell check --help

```text
usage: tesserae-shell check [-h] [--config-dir PATH] [--json] [--quiet]
                            [--timeout SECONDS] [--strict]

options:
  -h, --help         show this help message and exit
  --config-dir PATH  configuration directory
  --json             machine readable output
  --quiet            only warnings and errors
  --timeout SECONDS  how long a control command waits for the shell (default
                     5)
  --strict           a warning fails the check too (exit code 1)
```

#### tesserae-shell version --help

```text
usage: tesserae-shell version [-h] [--config-dir PATH] [--json] [--quiet]
                              [--timeout SECONDS]

options:
  -h, --help         show this help message and exit
  --config-dir PATH  configuration directory
  --json             machine readable output
  --quiet            only warnings and errors
  --timeout SECONDS  how long a control command waits for the shell (default
                     5)
```

#### tesserae-shell schema --help

```text
usage: tesserae-shell schema [-h] [--config-dir PATH] [--json] [--quiet]
                             [--timeout SECONDS] [--out FILE]

options:
  -h, --help         show this help message and exit
  --config-dir PATH  configuration directory
  --json             machine readable output
  --quiet            only warnings and errors
  --timeout SECONDS  how long a control command waits for the shell (default
                     5)
  --out FILE         write the JSON to FILE, not to standard output
```

#### tesserae-shell install-session --help

```text
usage: tesserae-shell install-session [-h] [--config-dir PATH] [--json]
                                      [--quiet] [--timeout SECONDS] [--print |
                                      --enable | --remove] [--force]

options:
  -h, --help         show this help message and exit
  --config-dir PATH  configuration directory
  --json             machine readable output
  --quiet            only warnings and errors
  --timeout SECONDS  how long a control command waits for the shell (default
                     5)
  --print            show both files and their paths, write nothing
  --enable           also run systemctl --user enable tesserae-shell.service
  --remove           disable the unit if it is enabled and remove both files
  --force            replace an existing file that has other content
```

#### tesserae-shell reload --help

```text
usage: tesserae-shell reload [-h] [--config-dir PATH] [--json] [--quiet]
                             [--timeout SECONDS]

options:
  -h, --help         show this help message and exit
  --config-dir PATH  configuration directory
  --json             machine readable output
  --quiet            only warnings and errors
  --timeout SECONDS  how long a control command waits for the shell (default
                     5)
```

#### tesserae-shell quit --help

```text
usage: tesserae-shell quit [-h] [--config-dir PATH] [--json] [--quiet]
                           [--timeout SECONDS]

options:
  -h, --help         show this help message and exit
  --config-dir PATH  configuration directory
  --json             machine readable output
  --quiet            only warnings and errors
  --timeout SECONDS  how long a control command waits for the shell (default
                     5)
```

#### tesserae-shell status --help

```text
usage: tesserae-shell status [-h] [--config-dir PATH] [--json] [--quiet]
                             [--timeout SECONDS]

options:
  -h, --help         show this help message and exit
  --config-dir PATH  configuration directory
  --json             machine readable output
  --quiet            only warnings and errors
  --timeout SECONDS  how long a control command waits for the shell (default
                     5)
```

#### tesserae-shell show --help

```text
usage: tesserae-shell show [-h] [--config-dir PATH] [--json] [--quiet]
                           [--timeout SECONDS]
                           name

positional arguments:
  name

options:
  -h, --help         show this help message and exit
  --config-dir PATH  configuration directory
  --json             machine readable output
  --quiet            only warnings and errors
  --timeout SECONDS  how long a control command waits for the shell (default
                     5)
```

#### tesserae-shell hide --help

```text
usage: tesserae-shell hide [-h] [--config-dir PATH] [--json] [--quiet]
                           [--timeout SECONDS]
                           name

positional arguments:
  name

options:
  -h, --help         show this help message and exit
  --config-dir PATH  configuration directory
  --json             machine readable output
  --quiet            only warnings and errors
  --timeout SECONDS  how long a control command waits for the shell (default
                     5)
```

#### tesserae-shell toggle --help

```text
usage: tesserae-shell toggle [-h] [--config-dir PATH] [--json] [--quiet]
                             [--timeout SECONDS]
                             name

positional arguments:
  name

options:
  -h, --help         show this help message and exit
  --config-dir PATH  configuration directory
  --json             machine readable output
  --quiet            only warnings and errors
  --timeout SECONDS  how long a control command waits for the shell (default
                     5)
```

#### tesserae-shell call --help

```text
usage: tesserae-shell call [-h] [--config-dir PATH] [--json] [--quiet]
                           [--timeout SECONDS]
                           module action [args ...]

positional arguments:
  module
  action
  args

options:
  -h, --help         show this help message and exit
  --config-dir PATH  configuration directory
  --json             machine readable output
  --quiet            only warnings and errors
  --timeout SECONDS  how long a control command waits for the shell (default
                     5)
```

#### tesserae-shell log-level --help

```text
usage: tesserae-shell log-level [-h] [--config-dir PATH] [--json] [--quiet]
                                [--timeout SECONDS]
                                level

positional arguments:
  level

options:
  -h, --help         show this help message and exit
  --config-dir PATH  configuration directory
  --json             machine readable output
  --quiet            only warnings and errors
  --timeout SECONDS  how long a control command waits for the shell (default
                     5)
```

#### tesserae-shell kwin --help

```text
usage: tesserae-shell kwin [-h] [--config-dir PATH] [--json] [--quiet]
                           [--timeout SECONDS]
                           GROUP ...

positional arguments:
  GROUP
    script           the shell's KWin script, installed for KWin to run from
                     login (mode P)
    rule             the one window rule that keeps the shell's surfaces above
                     Plasma panels (opt-in)

options:
  -h, --help         show this help message and exit
  --config-dir PATH  configuration directory
  --json             machine readable output
  --quiet            only warnings and errors
  --timeout SECONDS  how long a control command waits for the shell (default
                     5)
```

#### tesserae-shell kwin script --help

```text
usage: tesserae-shell kwin script [-h] ACTION ...

positional arguments:
  ACTION
    install   copy the script to KWin's scripts folder and enable it in kwinrc
    remove    take the script and its kwinrc switch away
    status    report the package, the kwinrc switch and whether KWin has it
              loaded

options:
  -h, --help  show this help message and exit
```

#### tesserae-shell kwin script install --help

```text
usage: tesserae-shell kwin script install [-h] [--config-dir PATH] [--json]
                                          [--quiet] [--timeout SECONDS]
                                          [--kwinrc PATH] [--scripts-dir PATH]
                                          [--no-reload]

options:
  -h, --help          show this help message and exit
  --config-dir PATH   configuration directory
  --json              machine readable output
  --quiet             only warnings and errors
  --timeout SECONDS   how long a control command waits for the shell (default
                      5)
  --kwinrc PATH       KWin's kwinrc
  --scripts-dir PATH  KWin's scripts folder
  --no-reload         do not ask KWin to reload afterwards
```

#### tesserae-shell kwin script remove --help

```text
usage: tesserae-shell kwin script remove [-h] [--config-dir PATH] [--json]
                                         [--quiet] [--timeout SECONDS]
                                         [--kwinrc PATH] [--scripts-dir PATH]
                                         [--no-reload]

options:
  -h, --help          show this help message and exit
  --config-dir PATH   configuration directory
  --json              machine readable output
  --quiet             only warnings and errors
  --timeout SECONDS   how long a control command waits for the shell (default
                      5)
  --kwinrc PATH       KWin's kwinrc
  --scripts-dir PATH  KWin's scripts folder
  --no-reload         do not ask KWin to reload afterwards
```

#### tesserae-shell kwin script status --help

```text
usage: tesserae-shell kwin script status [-h] [--config-dir PATH] [--json]
                                         [--quiet] [--timeout SECONDS]
                                         [--kwinrc PATH] [--scripts-dir PATH]

options:
  -h, --help          show this help message and exit
  --config-dir PATH   configuration directory
  --json              machine readable output
  --quiet             only warnings and errors
  --timeout SECONDS   how long a control command waits for the shell (default
                      5)
  --kwinrc PATH       KWin's kwinrc
  --scripts-dir PATH  KWin's scripts folder
```

#### tesserae-shell kwin rule --help

```text
usage: tesserae-shell kwin rule [-h] ACTION ...

positional arguments:
  ACTION
    show      print the rule group the shell would write to kwinrulesrc
    install   write that group (shows it and asks first, or takes --yes)
    remove    take exactly that group out of kwinrulesrc

options:
  -h, --help  show this help message and exit
```

#### tesserae-shell kwin rule show --help

```text
usage: tesserae-shell kwin rule show [-h] [--config-dir PATH] [--json]
                                     [--quiet] [--timeout SECONDS]
                                     [--rules-file PATH]

options:
  -h, --help         show this help message and exit
  --config-dir PATH  configuration directory
  --json             machine readable output
  --quiet            only warnings and errors
  --timeout SECONDS  how long a control command waits for the shell (default
                     5)
  --rules-file PATH  the rule file (kwinrulesrc)
```

#### tesserae-shell kwin rule install --help

```text
usage: tesserae-shell kwin rule install [-h] [--config-dir PATH] [--json]
                                        [--quiet] [--timeout SECONDS]
                                        [--rules-file PATH] [--no-reload]
                                        [--yes]

options:
  -h, --help         show this help message and exit
  --config-dir PATH  configuration directory
  --json             machine readable output
  --quiet            only warnings and errors
  --timeout SECONDS  how long a control command waits for the shell (default
                     5)
  --rules-file PATH  the rule file (kwinrulesrc)
  --no-reload        do not ask KWin to reload afterwards
  --yes              write without asking
```

#### tesserae-shell kwin rule remove --help

```text
usage: tesserae-shell kwin rule remove [-h] [--config-dir PATH] [--json]
                                       [--quiet] [--timeout SECONDS]
                                       [--rules-file PATH] [--no-reload]

options:
  -h, --help         show this help message and exit
  --config-dir PATH  configuration directory
  --json             machine readable output
  --quiet            only warnings and errors
  --timeout SECONDS  how long a control command waits for the shell (default
                     5)
  --rules-file PATH  the rule file (kwinrulesrc)
  --no-reload        do not ask KWin to reload afterwards
```

<!-- END generated: cli-command-help -->

Next: [troubleshooting](10-troubleshooting.md).
