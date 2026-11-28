# Install and start

<!-- BEGIN generated: version-info -->
This guide describes tesserae-shell 0.2.0 (schema version 1.47, the one `tesserae-shell schema --json` prints).

<!-- END generated: version-info -->

<!-- BEGIN generated: release-state -->
The code this guide describes is a little **ahead of the 0.2.0 release** on PyPI: the CHANGELOG lists the difference under *Unreleased*. The pages mark what was added after 0.2.0; a package installed from PyPI at 0.2.0 does not have it until the next release.

<!-- END generated: release-state -->

## What you need

* A KDE Plasma desktop on Wayland (KWin). The shell draws its bars and panels as layer-shell surfaces, so it needs a Wayland compositor that offers the layer-shell protocol. KWin does. If the shell finds none it stops with `no Wayland compositor with layer-shell` and exit code 2.
* Python 3.14 or newer. An older Python stops with `tesserae-shell needs Python 3.14 or newer`.
* A session bus (every desktop session has one). Without it the shell still runs but the control commands and the desktop services do not work; see [troubleshooting](troubleshooting.md).

The shell runs beside Plasma. It does not replace `plasmashell`, take its D-Bus names or touch its panels: your Plasma panel stays where it is until you remove it in Plasma itself.

## Install

The package is pure Python (one `py3-none-any` wheel). It depends on these packages, which `pip` installs for you:

<!-- BEGIN generated: dependencies -->
Python `>=3.14` is required.

| Package | Version | What it is for |
|---|---|---|
| `tesserae-engine` | `>=0.6.13,<0.7` | the rendering engine (imported as `tess_re`) |
| `tesserae-el` | `>=0.2.0,<0.3` | the expression language of the `<\| \|>` slots (imported as `tess_el`) |
| `tesserae-dl` | `>=0.2.0,<0.3` | the reader of TDL files (imported as `tess_dl`) |
| `loguru` | `>=0.7.3,<0.8` | the log |
| `inotify-simple` | `>=2.0.1,<3` | notices a saved file, for hot reload |
| `dbus-fast` | `>=2.24,<4` | the shell's own D-Bus connection |
| `tesserae-utils[image]` | `>=0.2.1,<0.3` | shared helpers (imported as `tess_utils`) |
| `pillow` | `>=11,<14` | decodes the pictures of `Image` |
| `jeepney` | `>=0.9,<0.10` | a light D-Bus client that the control commands use |

<!-- END generated: dependencies -->

Install it into its own environment so it does not disturb your system Python. With `uv`:

```sh
uv tool install --python 3.14 tesserae-shell
```

With `pipx`:

```sh
pipx install --python python3.14 tesserae-shell
```

Or with `pip`, in a virtual environment of your own:

```sh
python3.14 -m venv ~/.local/share/tesserae-shell-venv
~/.local/share/tesserae-shell-venv/bin/pip install tesserae-shell
```

Each of these puts a `tesserae-shell` command in a folder (`~/.local/bin`, or the environment's `bin`) that must be on your `PATH` for the plain command to work. `python -m tess_shell` is the same command.

Check the installation:

```sh
tesserae-shell version
```

It prints one line each for the shell, `tess_re` (the engine), `tess_el`, `tess_dl` and Python:

```text
tesserae-shell <version>
tess_re <version>
tess_el <version>
tess_dl <version>
python <version>
```

`tesserae-shell version --json` prints the same as one JSON object, and adds `config_dir`, the folder the shell would read.

## What needs a recent release

These parts of the guide describe features added after the 0.1.1 package (the CHANGELOG has the details; the Volume_OSD module needs 0.2.0, the rest 0.1.2 or later). A package from PyPI at 0.1.1 does not have them:

* the `tesserae-shell install-session` command ([below](#starting-with-your-session));
* the `tesserae-shell kwin ...` commands, the `KWin` block of `settings.tdl`, and the [Tasks](modules.md#tasks) and [Volume_OSD](modules.md#volume_osd) modules;
* the [Applications](modules.md#applications) module and the shipped `Launcher` Panel ([the Launcher](keyboard.md#the-launcher));
* the accessibility additions: `Value_Text` of Slider, `Label` of TextInput and TextEditor, and `announce` of Media, Audio and Tasks.

If a command or key from this guide is "unknown" to your installation, you probably have an old package: upgrade it (`uv tool upgrade tesserae-shell`). To run the current code instead, install from the repository (it needs `git`):

```sh
uv tool install --python 3.14 git+https://github.com/mindderivative/tess-shell
```

## The first run

```sh
tesserae-shell run
```

(`run` is the default: `tesserae-shell` with no command does the same.) The shell stays in the foreground and logs to the terminal. On the first run it creates its [configuration folder](configuration-folder.md), `~/.config/tesserae-shell`, with empty folders for your files, and a `registry.json` there. With no shell file yet it logs `no Main_Shell.tdl found; nothing to show` and shows nothing: a shell file is what puts a bar on the screen. [Your first Bar](first-bar.md) writes one.

To stop it, press `Ctrl+C` in its terminal, or run `tesserae-shell quit` from another. The first signal stops it cleanly; a second one makes it leave at once (exit code 130).

Before you start it with a file you have just written, ask `check` whether the files are valid. It creates nothing and does not need a compositor:

```sh
tesserae-shell check
```

To try a configuration without touching your own, point both commands at another folder with `--config-dir`:

```sh
tesserae-shell check --config-dir ~/try-shell
tesserae-shell run --config-dir ~/try-shell
```

Only one shell runs at a time per session. A second `run` stops with `another tesserae-shell is already running` and exit code 4.

## Starting with your session

A terminal is fine for trying things out. To have the shell start when you log in, the desktop and `systemd` need two small files. The wheel carries them as package data, but `pip`, `uv tool` and `pipx` put package data inside the environment, where neither the desktop nor `systemd` looks. So a command writes them where they are read (this command was added after 0.1.1; see [above](#what-needs-a-recent-release)):

```sh
tesserae-shell install-session --print    # show both files and their paths; write nothing
tesserae-shell install-session            # write both files; enable and start nothing
tesserae-shell install-session --enable   # also run: systemctl --user enable tesserae-shell.service
tesserae-shell install-session --remove   # disable the unit if it is enabled, and remove both files
```

Run `--print` first: it shows what would be written and where, and changes nothing. The two files are:

* `~/.local/share/applications/io.github.mindderivative.TesseraeShell.desktop`, which gives the shell its application id. It is marked `NoDisplay=true`, so it does not appear in your application menu. The desktop's Settings portal wants a desktop file with the id the shell registers; without it the shell may log a warning about the portal (see [troubleshooting](troubleshooting.md)) and still works.
* `~/.config/systemd/user/tesserae-shell.service`, a user unit that runs `tesserae-shell run` as part of `graphical-session.target`. It is `Type=notify` (the shell tells `systemd` when it is ready and when it is stopping), has `WatchdogSec=15` (the shell pings `systemd` while its loop runs; a loop that stops for 15 seconds, or that the shell reports as stuck after 10, is ended with `SIGABRT` and restarted), restarts after a failure two seconds later (at most five starts in 60 seconds) and does not restart after exit code 1 (the files have errors), 2 (the machine cannot run it) or 4 (another shell is running). A lost Wayland connection ends the shell with exit code 69, which does restart it.

Both files name the absolute path of the `tesserae-shell` command that wrote them, so run `install-session` from the installation you want the session to use. If you move or reinstall the shell, run it again with `--force`; `tesserae-shell status` warns when the unit points at a path that no longer exists. `--config-dir PATH`, if given, is written into both files.

Details of how the command behaves:

* A file that exists with other content is left alone: the command names it, changes nothing and exits 1. `--force` replaces it. A file that already has exactly the content is reported as `unchanged`, so running the command twice is safe.
* `--enable` only enables the unit, so the shell starts at your next login. To start it now, run `systemctl --user start tesserae-shell.service`.
* `--remove` leaves `~/.config/tesserae-shell` alone and does not stop a running shell; `tesserae-shell quit` does.
* `--json` prints one JSON object (`ok`, `action`, `files`, `enabled`, `exec_start`, `notes`); an error is `{"ok": false, "error": "...", "exit": N}`.
* Exit codes: 0 done, 1 a differing file kept or a file that cannot be written, 2 `systemctl` missing or refusing (the files are still written and listed).

After `--enable`, log out and in again (or start the unit as above). The shell then starts with your session and its log goes to the journal as well as to the log file: `journalctl --user -u tesserae-shell`.

> **Not yet checked on KWin.** `install-session` is covered by tests that write into temporary folders and use a recording stand-in for `systemctl`. Starting the shell from the unit on a real Plasma session has not been confirmed by the maintainer's hand checks yet. Try `--print` first, and keep your Plasma panel until you have seen the shell start from the unit.

## What has been checked on KWin

The design notes record which parts the maintainer has confirmed by hand on a real KWin session and which only the automated tests have seen. It affects how much to trust a page of this guide:

* Confirmed on KWin: Bars, Panels, Popups and tooltips, the Frame (strips, melded Panels, peek), monitor hot-plug, the Clock and hot reload.
* Built and tested on a private compositor, with some hand checks done and others still open: the other modules (Battery, Workspaces, Network, Media, Audio, Tray, Tasks, the interactive widgets), focus and the keyboard.
* Not yet checked on KWin: the exact way global shortcuts register with `kglobalaccel`, shortcut mode's keyboard (`Debug { Mode_Keyboard }`), the Launcher's keyboard and application start, the KWin script and the window rule (`tesserae-shell kwin ...`), and `install-session`.

Each of these is repeated where it matters.

Next: [the configuration folder](configuration-folder.md).
