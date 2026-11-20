# tess-shell

Tesserae Shell is a tool for building desktop shells (bars, panels, docks, launchers, on-screen displays and widgets) that run alongside an installed desktop environment, with KDE Plasma on Wayland as the first target. You describe a shell in TDL files, add Python where you want logic, and the [tre](https://github.com/mindderivative/tre) rendering engine draws it.

**Documentation: https://mindderivative.github.io/tess-shell/**: installation, a tutorial, the user guide, the reference, the module API and the design record.

> Pre-alpha software. Keep a way back to your usual Plasma panel.

## Install

You need a KDE Plasma desktop on Wayland and Python 3.14 or newer.

```sh
uv tool install --python 3.14 tesserae-shell      # or: pipx install --python python3.14 tesserae-shell
```

## Try it

Save this as `~/.config/tesserae-shell/Shells/Main_Shell.tdl`:

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
                            Spacer { }
                            Clock { format: "%H:%M" }
                        }
                    }
                }
            }
        }
    }
}
```

```sh
tesserae-shell check    # validate every file; needs no compositor
tesserae-shell run      # start the shell
```

A bar with a clock appears along the top of every monitor, and saving the file changes it about 200 ms later. The [documentation](https://mindderivative.github.io/tess-shell/) goes on from there.

## Commands

```sh
tesserae-shell version   # versions of the shell, tess_re, tess_el, tess_dl and Python
tesserae-shell check     # validate settings.tdl and every shell file
tesserae-shell run       # start the shell (needs a Wayland compositor with layer-shell)
tesserae-shell schema --json [--out FILE]  # the shell's schema as JSON, for configuration tools
tesserae-shell migrate [--check] [--json] [--force]  # bring your files to the current format (backup first)
tesserae-shell install-session [--print|--enable|--remove] [--force]  # the desktop file and the systemd user unit
```

The [command line page](https://mindderivative.github.io/tess-shell/guide/command-line/) lists every command, option and exit code.

## Security

A module is Python that runs with your rights. The modules that ship with the shell run inside it; a module you write or add runs in a process of its own, so a module that hangs or crashes does not freeze your bars. That is not a sandbox: it can still read your files and start programs. Write modules yourself or read them before you add them. TDL files cannot run code. Keep your configuration folder writable by you only: the shell warns if it is not.

## Development

```sh
export UV_PROJECT_ENVIRONMENT=$HOME/Projects/pyDev/pyEnvs/tess-shell
uv sync
uv run pytest
```

`docs/` is the documentation site (MkDocs); `docs/design/` is generated from the maintainer's design notes by [`tools/sync_docs.py`](tools/sync_docs.py). The [contributing page](https://mindderivative.github.io/tess-shell/contributing/) has the rest. To build the site locally: `uv sync --only-group docs && uv run --no-sync mkdocs serve`.

## Licence and third-party notices

The shell is MIT licensed ([`LICENSE`](LICENSE)). The assets it ships follow that unless they say otherwise: the three peek handle icons (`shipped/Handles/`) and the fallback image `shipped/Images/error.png` were made for Tesserae Shell and are MIT; the icon set `shipped/Icons/mdi.json` is Material Design Icons by Pictogrammers, under Apache-2.0 (with the licence text, `MDI-LICENSE.txt`, next to it). The package ships no font; text is drawn with the fonts bundled in `tesserae-engine` (Roboto, Noto Sans Arabic and Hack Nerd Font Mono). [`NOTICE`](NOTICE) lists every shipped or required third-party asset and runtime dependency with its licence and source; it is in the wheel (`dist-info/licenses/NOTICE`) and the sdist, and `tests/test_notice.py` fails when an asset or a dependency is added without a line in it. When you add a dependency or an asset, add its line to `NOTICE` in the same change.
