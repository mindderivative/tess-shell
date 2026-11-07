# tess-shell

Tesserae Shell is a tool for building desktop shells (bars, panels, docks, launchers, OSDs and widgets) that run alongside an installed desktop environment, with KDE Plasma on Wayland as the first target. It is built on the [tre](https://github.com/mindderivative/tre) rendering engine, with Python for logic and its own data language, TDL, for describing shells.

## Status

Milestones M0 (the skeleton), M1 (a static Bar) and M2 (live and modular) are built, and M3a (the look: themes, stylesheets, the desktop's light/dark setting, shadows) is built; the KWin checklists, which the maintainer runs by hand, are the open part. `run` opens a `Bar` from `Main_Shell.tdl` on the matched monitor through `tess_dl`, the schema, the binder and tre, reserves its space, and stops cleanly on SIGTERM or SIGINT. On top of that:

- **Modules:** a `<Name>_Module.tdl` plus `<Name>_Module.py` in `Modules/<Name>/`; a use is written `Clock { format: "%H:%M" }` or `Import: <path>_Module.tdl`. The Python sends values with `ctx.send`; a `{{ }}` slot in the layout reads them, and only the node properties that changed are set. The shell ships a Clock (`format`, `locale`, `hour_cycle`, `timezone`, `tooltip_format`); a module of the same name in your `Modules/` folder overrides it.
- **Structure and look:** `If`/`Else` and `For` (keyed lists) in a module's layout, style files (`Style: <Name>_Style.tdl` with `Classes`) and `SVG { Icon: "mdi:account" }`: the `mdi` set ships in the package, and Iconify-style JSON sets in the `Icons` folder come first.
- **Hot reload:** saving a shell, module, style or icon file updates the running shell about 200 ms later, once; a file with an error changes nothing and is reported as `file:line:column`. `SIGHUP` reloads everything. `settings.tdl` keys: `Hot_Reload` (default true), `Reload_Debounce` (milliseconds, default 200); `Logging` applies at once, `Directories`, `Registry` and `Main_Shell` need a restart.
- **Identity:** the first time the shell registers one of your files it adds a `UID:` line to its metadata, after copying the file to `$XDG_STATE_HOME/tesserae-shell/backups`.

- **Look:** a `Theme` file holds colour, type, shape, space, elevation and motion tokens, with `Light`, `Dark`, `High_Contrast` and `Reduced_Motion` modes; a style value `$color.surface` reads one. A `Stylesheet` holds `Rule { Selector: "Text" | ".class" | "#name", ... }` blocks, each with an optional `:hovered` or `:pressed` state. The shell ships a `Default` theme and stylesheet; `Appearance { Theme: ..., Stylesheets: [...], Follow_Desktop: true }` in `settings.tdl` names the ones in use, and the desktop's colour scheme, accent, contrast and reduced-motion settings (the Settings portal) pick the mode live. `Elevation: 20%` or `Shadows { Shadow { ... } }` on a Bar draws its shadow in a transparent margin; the reserved space does not change.

- **Events:** `On_Click: open_it` (or `On_Click { Action: pick, Which: "b" }`) on a box, `Rectangle`, `Spacer` or `SVG` in a module's layout calls the module's `@action` method with an `Event`; the other events and the shell's own actions come with the Panel.

- **Panels:** `Panel { Name: Volume_OSD, Layer: OVERLAY, Anchor: [BOTTOM], Inset: [0, 0, 0, 80], Width: 260, Height: 60, Input_Region: [], Hide_After: 1500 }` opens an anchored or centred surface; `Visible: false` starts it hidden, `On_Click { Action: Toggle, Target: Volume_OSD }` on a block shows and hides it, and Escape hides one that takes the keyboard. `Attach_To: Top_Bar, Attach: BOTTOM, Gap: 8, Alignment: START` places a Panel against a Bar, another Panel or a module used in a Bar (`Name: Clock_One`). `Animation { Type: SLIDE, Duration: 300 }` slides or fades it in and out, `Movable: true` lets the pointer move it and remembers where, and `On_Open`, `On_Visible`, `On_Close` and `On_Hidden` run shell actions around it.
- **Popups and tooltips:** `Popup { Name: Menu, Gap: 4, Children { ... } }` is opened by a module with `self.ctx.popup("Menu")` from an `@action` (a click on its block), beside that block, upward under a bottom Bar; `On_Click: Close` inside it closes it, an outside click or Escape dismisses it. `Tooltip: true` on a Popup, with `Tooltip: Name` or an inline `Tooltip { Children { ... } }` on a block or module use, opens it after `Enter_Delay` of hovering. The Clock shows its date as a tooltip (`tooltip_format`, `locale`).
- **Monitor hot-plug:** plugging an output in opens only the surfaces of the `Monitor` blocks that match it (`Connector`, `Description`, `Index`, `Index: default`), unplugging one closes only its surfaces, and an output whose size or scale changes gets its surfaces' geometry set live. The other monitors' windows are never recreated. A Panel that comes back is a new window at the position saved for `<Monitor>@<output>`, clamped to the output; the modules follow the uses that came or went as a hot reload does. `Index` is evaluated again on every change.

- **Frame:** `Frame { Name: Screen_Frame, Thickness: [10, 20, 30, 40], Margin: 5, Corner_Radius: 0, Inner_Radius: 14, Inner_Border { Width: 2, Color: "#89b4fa" }, Outer_Border { ... }, Style { Background: "#1e1e2e" } }` in a `Monitor` draws a ring around the output (one painter window, with the opening taking no clicks) and reserves each side's thickness plus borders plus margin (four thin reserver windows, one per side with a thickness; a side of 0 has none). `Thickness` and `Margin` are a number, four sides (left, top, right, bottom) or named sides; the radii are one number or four corners clockwise from the top-left, and one too large for the ring is reduced with a warning. A reload changes zones, radii and colours without opening the painter again; tokens (`$color.surface`) follow the theme; `Visible: false` starts it hidden and `Show`, `Hide` and `Toggle` with `Target: <Frame name>` act on it. `tests/kwin/measure_frame.py` measures its cost.
- **Frame strips and melded Panels:** `Edges { Top { Thickness: 34, Padding: 4, Children { ... } }, Left { ... } }` makes a side a strip: its `Children` (blocks and module uses, with live values, reload and hot-plug like a Bar's, Popups and tooltips included) are laid out in a box in that side's band inside the Frame's painter; the top and bottom strips own the corners and run the full width, the left and right strips run between them and lay their children out vertically, text is not rotated. `Padding` (on the Frame for every strip, or on an edge) is the space between a strip's children and its sides; an edge's `Thickness` replaces the Frame's for that side. `Panel { Name: Dock, Meld: true, Attach_To: Screen_Frame, Attach: BOTTOM, Alignment: CENTER, Length: 320, Depth: 56, Style { Corner_Radius: 12 } }` is drawn inside the Frame's surface as a body grown from that side into the opening, in the Frame's colour and border, as part of the ring's one contour with a fillet (the Frame's `Inner_Radius`) at each join; `Show`, `Hide` and `Toggle` with `Target: Dock` take it out of the contour and put it back, with `Animation { Type: SLIDE | FADE | NONE, Duration: 300 }` (the body slides out of the Frame's edge, or fades; instant with reduced motion), `Hide_After` and the Panel events (`On_Open`, `On_Close`, `On_Visible`, `On_Hidden`, `On_Toggle`, `On_Anim_Start`, `On_Anim_End`); a `Margin`, `Movable`, `Keyboard` or `Input_Region` on it is an error. `Keyboard: NONE | ON_DEMAND` on the Frame sets the painter's keyboard mode (default `NONE`). `tests/kwin/prepare_m3c_strips.py` writes a KWin check.

Not built yet: strip expand, contract and peek, a Bar or a window-Panel melded to the Frame, gradients, popup submenus, most events and actions, the `:focused` and `:disabled` states and `::part` selectors, services, shortcuts. The design is in `docs/`.

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
