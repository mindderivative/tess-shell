# Examples

Every example in the guide is a real configuration folder, kept in the repository under `docs/guide/examples/<page>/<set>/`. A test runs each one through `tesserae-shell check`, so an example that stops being valid fails the build. This page lists them all, with the guide page that explains each.

Each set is a folder you can use as it is: copy it, then check it, and run it if you like.

```sh
cp -r docs/guide/examples/03-first-bar/clock /tmp/try
tesserae-shell check --config-dir /tmp/try
tesserae-shell run --config-dir /tmp/try
```

The files of a set are shown in full on the page that explains it. The paths below are relative to the repository's `docs/guide/examples/` folder. A set holds `settings.tdl` and `Shells/Main_Shell.tdl` unless the table lists other files.

## The configuration folder and the first Bar

Explained in [The configuration folder](guide/configuration-folder.md) and [Your first Bar](guide/first-bar.md).

| Set | What it shows | Other files |
|---|---|---|
| `02-config-folder/my-config` | A folder with a module of your own, `Greeting`, used from the main shell | `Modules/Greeting/Greeting_Module.tdl`, `Greeting_Module.py` |
| `03-first-bar/minimal` | The smallest shell: one Bar with one line of text (no `settings.tdl`) | |
| `03-first-bar/clock` | One Bar along the top of every monitor with the time at its right end | |

## Tutorial

The five steps of the [tutorial](guide/tutorial.md); each builds on the last.

| Set | What it shows | Other files |
|---|---|---|
| `11-tutorial/step-1-bar` | One Bar with the time at its right end | |
| `11-tutorial/step-2-launcher` | A button in the Bar and a Panel named `Launcher` | |
| `11-tutorial/step-3-popup` | A Tray in the Bar and a Popup of your own | |
| `11-tutorial/step-4-style` | The clock in a chip, with a theme and a stylesheet of your own | `Themes/Mine_Theme.tdl`, `Stylesheets/Mine_Stylesheet.tdl` |
| `11-tutorial/step-5-module` | A module of your own, `Uptime`, beside the clock | `Modules/Uptime/Uptime_Module.tdl`, `Uptime_Module.py`, `Styles/Uptime_Style.tdl`, the theme and stylesheet |

## Writing a module

Explained in [Writing a module](guide/writing-a-module.md).

| Set | What it shows | Other files |
|---|---|---|
| `12-modules/tally` | A counter module: a click adds a step, a secondary click resets; the Python sends the count and the layout shows it | `Modules/Tally/Tally_Module.tdl`, `Tally_Module.py` |

## Surfaces

Explained in [Surfaces](guide/surfaces.md).

| Set | What it shows | Other files |
|---|---|---|
| `04-surfaces/bars` | A Bar across the top that keeps its space free, and a short floating Bar at the bottom that lies above the windows' space by `Gap` | |
| `04-surfaces/monitors` | A slim Bar on the laptop screen picked by its connector, a taller one with the time on every other monitor (`Index: default`) | |
| `04-surfaces/panels` | A button in the Bar that shows and hides a Panel; `Volume_OSD`, an overlay that hides itself | |
| `04-surfaces/popups` | A Button that opens a Popup under itself, closed by its own button, a click outside or Escape | |
| `04-surfaces/attached-panel` | A Panel placed against another surface with `Attach_To`: under the Bar, 8 pixels away, at its right end | |
| `04-surfaces/frame` | A Frame, a ring around the screen: a strip that holds a Clock, a thin line, and a Panel melded into the bottom edge as a dock that rests as a tab | |
| `04-surfaces/split` | A shell in several files: the dock is in its own file, brought in with `Import` on this Monitor | `Shells/Parts/Dock_Shell.tdl` |
| `04-surfaces/tooltips` | Three ways to a tooltip: the short form, an inline `Tooltip` block, and a Popup with `Tooltip: true` | |

## Modules

Explained in [Modules](guide/modules.md), one set for each module the shell ships. The set has the same name as the module's section; each uses the module with its parameters, in a Bar, a Panel or a Popup as the module needs.

| Set | The module |
|---|---|
| `05-modules/clock` | [Clock](guide/modules.md#clock): the local time with the date as its tooltip, and the time in Tokyo |
| `05-modules/label` | [Label](guide/modules.md#label) |
| `05-modules/icon` | [Icon](guide/modules.md#icon) |
| `05-modules/image` | [Image](guide/modules.md#image): a file beside the shell file (`Shells/logo.png`), and one with only a `Placeholder` colour |
| `05-modules/badge` | [Badge](guide/modules.md#badge) |
| `05-modules/button` | [Button](guide/modules.md#button) |
| `05-modules/checkbox` | [Checkbox](guide/modules.md#checkbox) |
| `05-modules/toggle` | [Toggle](guide/modules.md#toggle) |
| `05-modules/slider` | [Slider](guide/modules.md#slider): the first sets the sound volume once, when you let go, through the Audio module's `set_volume` action |
| `05-modules/progressbar` | [ProgressBar](guide/modules.md#progressbar) |
| `05-modules/list` | [List](guide/modules.md#list): in a Panel, because a list is taller than a Bar |
| `05-modules/menu` | [Menu](guide/modules.md#menu): a Button in the Bar opens the Popup `File_Menu`, whose content is the Menu |
| `05-modules/textinput` | [TextInput](guide/modules.md#textinput): a Bar that holds a text field takes the keyboard when it is clicked |
| `05-modules/texteditor` | [TextEditor](guide/modules.md#texteditor): in a Panel that asks for the keyboard when clicked |
| `05-modules/textbox` | [TextBox](guide/modules.md#textbox) |
| `05-modules/marquee-text` | [Marquee_Text](guide/modules.md#marquee_text) |
| `05-modules/expander` | [Expander](guide/modules.md#expander): shows its children while `Expanded` is true, with a slide and a fade |
| `05-modules/battery` | [Battery](guide/modules.md#battery): hidden on a machine with no battery |
| `05-modules/workspaces` | [Workspaces](guide/modules.md#workspaces) |
| `05-modules/network` | [Network](guide/modules.md#network) |
| `05-modules/media` | [Media](guide/modules.md#media) |
| `05-modules/audio` | [Audio](guide/modules.md#audio): its secondary-click menu is the Popup `Audio_Outputs`, which the shell provides |
| `05-modules/audio-outputs` | [Audio_Outputs](guide/modules.md#audio_outputs): a Popup of the same name written on a Monitor replaces the shipped one whole |
| `05-modules/volume-osd` | [Volume_OSD](guide/modules.md#volume_osd): in a Panel that starts hidden, takes no pointer and no keyboard, on the overlay layer |
| `05-modules/tray` | [Tray](guide/modules.md#tray) |
| `05-modules/tasks` | [Tasks](guide/modules.md#tasks) |

## Styling

Explained in [Styling and themes](guide/styling.md).

| Set | What it shows | Other files |
|---|---|---|
| `06-styling/dusk` | A theme of your own and a stylesheet that uses its tokens | `Themes/Dusk_Theme.tdl`, `Stylesheets/Mine_Stylesheet.tdl` |
| `06-styling/effects` | Shadows, and a change that is animated: a tile's fill eases when the pointer comes and goes (instant with reduced motion) | `Stylesheets/Tiles_Stylesheet.tdl` |
| `06-styling/icons` | Icons: a name from the shipped `mdi` set, a name from a set of your own, and a plain SVG file | `Icons/mine.json`, `Shells/dot.svg` |

## Settings

Explained in [`settings.tdl`](guide/settings.md).

| Set | What it shows |
|---|---|
| `07-settings/every-key` | A `settings.tdl` that writes every key, with the shell file it names |

## Keyboard

Explained in [Keyboard and shortcuts](guide/keyboard.md).

| Set | What it shows |
|---|---|
| `08-keyboard/focus` | Tab and Shift+Tab through the focusable blocks of a surface: `Tab_Index`, `Focusable` and `Enabled` |
| `08-keyboard/shortcuts` | The surfaces that global shortcuts name, and a surface that carries its own key |
| `08-keyboard/shortcut-mode` | Shortcut mode, which walks the surfaces with the keyboard |
| `08-keyboard/launcher` | The Launcher the shell provides, and the shortcut that opens it |
| `08-keyboard/custom-launcher` | A Panel written as `Launcher`, which replaces the shipped one whole |

## Keeping the list true

New sets are added with the page that explains them, and `tests/test_guide_examples.py` checks that every set passes `tesserae-shell check`. The pages that explain a set show it between `<!-- BEGIN generated: example-set:<page>/<set> -->` markers, written by `tests/guide_tables.py` ([Contributing](contributing.md#the-documentation)).
