# tess-shell

Tesserae Shell is a tool for building desktop shells (bars, panels, docks, launchers, OSDs and widgets) that run alongside an installed desktop environment, with KDE Plasma on Wayland as the first target. It is built on the [tre](https://github.com/mindderivative/tre) rendering engine, with Python for logic and its own data language, TDL, for describing shells.

## Status

Milestones M0 (the skeleton), M1 (a static Bar) and M2 (live and modular) are built, and M3a (the look: themes, stylesheets, the desktop's light/dark setting, shadows) is built; the KWin checklists, which the maintainer runs by hand, are the open part. `run` opens a `Bar` from `Main_Shell.tdl` on the matched monitor through `tess_dl`, the schema, the binder and tre, reserves its space, and stops cleanly on SIGTERM or SIGINT. On top of that:

- **Modules:** a `<Name>_Module.tdl` plus `<Name>_Module.py` in `Modules/<Name>/`; a use is written `Clock { format: "%H:%M" }` or `Import: <path>_Module.tdl`. The Python sends values with `ctx.send`; a `{{ }}` slot in the layout reads them, and only the node properties that changed are set. The shell ships a Clock (`format`, `hour_cycle`, `timezone`); a module of the same name in your `Modules/` folder overrides it.
- **Structure and look:** `If`/`Else` and `For` (keyed lists) in a module's layout, style files (`Style: <Name>_Style.tdl` with `Classes`) and `SVG { Icon: "mdi:account" }`: the `mdi` set ships in the package, and Iconify-style JSON sets in the `Icons` folder come first.
- **Hot reload:** saving a shell, module, style or icon file updates the running shell about 200 ms later, once; a file with an error changes nothing and is reported as `file:line:column`. `SIGHUP` reloads everything. `settings.tdl` keys: `Hot_Reload` (default true), `Reload_Debounce` (milliseconds, default 200); `Logging` applies at once, `Directories`, `Registry` and `Main_Shell` need a restart.
- **Identity:** the first time the shell registers one of your files it adds a `UID:` line to its metadata, after copying the file to `$XDG_STATE_HOME/tesserae-shell/backups`.

- **Look:** a `Theme` file holds colour, type, shape, space, elevation and motion tokens, with `Light`, `Dark`, `High_Contrast` and `Reduced_Motion` modes; a style value `$color.surface` reads one. A `Stylesheet` holds `Rule { Selector: "Text" | ".class" | "#name", ... }` blocks. The shell ships a `Default` theme and stylesheet; `Appearance { Theme: ..., Stylesheets: [...], Follow_Desktop: true }` in `settings.tdl` names the ones in use, and the desktop's colour scheme, accent, contrast and reduced-motion settings (the Settings portal) pick the mode live. `Elevation: 20%` or `Shadows { Shadow { ... } }` on a Bar draws its shadow in a transparent margin; the reserved space does not change.

- **Events:** `On_Click: open_it` (or `On_Click { Action: pick, Which: "b" }`) on a box, `Rectangle`, `Spacer` or `SVG` in a module's layout calls the module's `@action` method with an `Event`; the other events and the shell's own actions come with the Panel.

- **Panels:** `Panel { Name: Volume_OSD, Layer: OVERLAY, Anchor: [BOTTOM], Inset: [0, 0, 0, 80], Width: 260, Height: 60, Input_Region: [], Hide_After: 1500 }` opens an anchored or centred surface; `Visible: false` starts it hidden, `On_Click { Action: Toggle, Target: Volume_OSD }` on a block shows and hides it, and Escape hides one that takes the keyboard. `Attach_To: Top_Bar, Attach: BOTTOM, Gap: 8, Alignment: START` places a Panel against a Bar, another Panel or a module used in a Bar (`Name: Clock_One`). Moving, sliding and saved positions are not built yet.

Not built yet: popups, frames, panel attachment, most events and actions, `:state` and `::part` selectors, services, shortcuts. The design is in `docs/`.

## Commands

```sh
tesserae-shell version   # versions of the shell, tess_re, tess_el, tess_dl and Python
tesserae-shell check     # validate settings.tdl and every shell file (syntax, header, schema)
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
