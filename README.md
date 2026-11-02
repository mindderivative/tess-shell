# tess-shell

Tesserae Shell is a tool for building desktop shells (bars, panels, docks, launchers, OSDs and widgets) that run alongside an installed desktop environment, with KDE Plasma on Wayland as the first target. It is built on the [tre](https://github.com/mindderivative/tre) rendering engine, with Python for logic and its own data language, TDL, for describing shells.

## Status

The project is in its design phase. No product code exists yet. The complete design is being written first.

## Documentation

The design documentation is in [`docs/`](docs/README.md). Start at [Home](docs/00%20Home/Home.md) for the current status, decisions and open questions.

`docs/` is generated from the maintainer's design notes (an Obsidian vault) by [`tools/sync_docs.py`](tools/sync_docs.py). Edits made in `docs/` are overwritten the next time the tool runs.
