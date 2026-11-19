# Tesserae Shell: user guide

This guide is for a person who has installed `tesserae-shell` and wants a bar, a launcher or a few widgets on a KDE Plasma desktop. It does not explain how the shell is built; the design notes in [`docs/`](../docs/README.md) do that.

<!-- BEGIN generated: version-info -->
This guide describes tesserae-shell 0.1.2 (schema version 1.12, the one `tesserae-shell schema --json` prints).

<!-- END generated: version-info -->

<!-- BEGIN generated: release-state -->
The code this guide describes is a little **ahead of the 0.1.2 release** on PyPI: the CHANGELOG lists the difference under *Unreleased*. The pages mark what was added after 0.1.2; a package installed from PyPI at 0.1.2 does not have it until the next release.

<!-- END generated: release-state -->

Everything here is what the code does today. Where something is built but has not been tried on a real KWin session yet, the page says **not yet checked on KWin**, and where a feature is not built it says so instead of describing it. The shell is pre-alpha software: expect rough edges and keep a way back to your usual Plasma panel.

## Pages

1. [Install and start](01-install.md): the package, the first run, and starting with your session.
2. [The configuration folder](02-configuration-folder.md): where your files live, the `UID:` line and backups, and hot reload.
3. [Your first Bar](03-first-bar.md): a minimal shell file and a clock, line by line, and `check`.
4. [Surfaces](04-surfaces.md): Bar, Panel, Popup, Frame and Monitor, with every key.
5. [Modules](05-modules.md): every module the shell ships, with its parameters.
6. [Styling and themes](06-styling.md): tokens, light and dark, stylesheets, icons, shadows and motion.
7. [`settings.tdl`](07-settings.md): every setting.
8. [Keyboard and shortcuts](08-keyboard.md): focus, global shortcuts, shortcut mode and the launcher.
9. [The command line](09-command-line.md): every command and its exit codes.
10. [Troubleshooting](10-troubleshooting.md): the messages the shell prints and what to do.

## How the guide is kept true

* Every example in the guide is a real configuration folder under [`examples/`](examples/). A test runs each one through `tesserae-shell check` (the same code, in process, on a temporary folder), so an example that stops being valid fails the test suite.
* Every table of keys, defaults, tokens, settings and commands is generated from the shell's own schema (`tesserae-shell schema --json`) and its command-line parser, and written into the pages between a pair of HTML comments that start with `BEGIN generated` and `END generated`. A test generates them again and compares; after a change in the code, run

  ```sh
  env -u WAYLAND_DISPLAY -u DISPLAY uv run python -m tests.guide_tables
  ```

  from a checkout to bring the pages up to date. Do not edit between the comments.
* `check` proves that a file is valid, not that it looks as you want: the examples are checked, and the descriptions of what they look like are taken from the design notes and the module sources, not from screenshots.
