# tess-shell

Tesserae Shell is a tool for building desktop shells (bars, panels, docks, launchers, OSDs and widgets) that run alongside an installed desktop environment, with KDE Plasma on Wayland as the first target. It is built on the [tre](https://github.com/mindderivative/tre) rendering engine, with Python for logic and its own data language, TDL, for describing shells.

## Status

Milestone M0 (the skeleton) is in progress: the package, the command line and tooling exist. The design is in `docs/`.

## Commands

```sh
tesserae-shell version   # versions of the shell, tess_re, tess_el, tess_dl and Python
tesserae-shell check     # validate settings.tdl and the syntax of every shell file
tesserae-shell run       # start the shell (needs a Wayland compositor with layer-shell)
```

Global options: `--config-dir PATH`, `--json`, `--quiet`. Other subcommands named in the design
report that they are not implemented yet.

## Development

```sh
export UV_PROJECT_ENVIRONMENT=$HOME/Projects/pyDev/pyEnvs/tess-shell
uv sync
uv run pytest
```

## Documentation

The design documentation is in [`docs/`](docs/README.md). Start at [Home](docs/00%20Home/Home.md) for the current status, decisions and open questions.

`docs/` is generated from the maintainer's design notes (an Obsidian vault) by [`tools/sync_docs.py`](tools/sync_docs.py). Edits made in `docs/` are overwritten the next time the tool runs.
