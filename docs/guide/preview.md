# The preview model

A tool that edits your configuration (the configuration app) can show a mockup of what the shell will give you, before you save. It does not read the files itself: the shell has a function that returns what it would show, as plain data, with the same rules it uses when it runs. The tool only draws it.

```python
from pathlib import Path
from tess_shell.preview import VirtualOutput, preview

model = preview(
    Path("~/.config/tesserae-shell").expanduser(),
    overrides={Path("~/.config/tesserae-shell/Shells/Main_Shell.tdl").expanduser(): text},
    outputs=[VirtualOutput("DP-1", 1920, 1080)],
)
data = model.to_dict()   # dicts, lists, strings, numbers, booleans and None
```

Nothing opens a window and nothing touches the compositor. The shell does not import a toolkit for this: the module is `tess_shell.preview`, and it is safe to call on every keystroke (the example takes a few tens of milliseconds; the shell's own files are read once).

## The arguments

* `config`: the configuration folder.
* `overrides`: path to text. The text an editor holds for a file is read instead of the disk's, for a file that does not exist yet as well. The disk is not touched.
* `outputs`: the outputs to preview on, each a name (what a `Monitor` selects with `Connector`), a size in logical pixels and a scale. The default is one 1920 by 1080 output.
* `appearance`: the light or dark scheme and the accent to preview with; the default follows the theme's default.

## What you get

| Key | What it holds |
|---|---|
| `preview_version` | The version of this shape (`"1"`). A key is added without a bump; a key that is changed or removed bumps it. |
| `findings` | What `tesserae-shell check` prints: `file`, `line`, `column`, `severity`, `rule`, `message`, `hint`. |
| `outputs` | The outputs given: `name`, `width`, `height`, `scale`, `description`. |
| `appearance` | `scheme`, `density`, `theme` (a name or `null`), `stylesheets`. |
| `tokens` | The theme's tokens by dotted path: colours as `#RRGGBB`, numbers, words. |
| `shell` | `name` and `file` of the main shell, or `null` when there is none. |
| `monitors` | Each `Monitor` block: `name`, `index`, `connector`, `description`, the `outputs` it lands on and its `status`. |
| `surfaces` | Every Bar, Panel and Frame, one per `Monitor` and output (below). |
| `popups` | Each Popup of a `Monitor` as a static card: where it opens relative to its caller, its size and its blocks. |
| `desktop` | Per output, the rectangle windows get after the exclusive zones of the Bars and the Frame: `output`, `x`, `y`, `width`, `height`. |

A surface has `kind` (`bar`, `panel` or `frame`), `name`, `monitor`, `output`, `status`, `visible`, `layer`, `style` and `blocks`. A Bar and a Panel also have `anchor`, `size`, `margin`, `exclusive_zone` and `rect`, the body's rectangle on the output in logical pixels, worked out by the same placement the shell opens its windows from (`content_sized` says which axis the content decides: that size is a stand-in). A Frame has `thickness`, `margin`, `outer_radius`, `inner_radius`, `inner_border`, `outer_border`, its `edges` (with their blocks) and the names of the Panels melded into it.

`status` is `ok`, or `skipped: ` and the reason (a Panel attached to a Panel that the content sizes, a size of zero). A skipped surface has no placement.

## Blocks

`blocks` is the tree of what a surface holds. Each entry has a `type`:

* `block`: `kind`, `name`, `classes`, `props`, `style` and `children`. The stylesheets' rules are already in `style`.
* `module`: the call of a module: `module`, `name`, `label` (a placeholder: its `Label`, `Text` or `Format` when that is plain text, else its name), `params` (what the module declares as default, with what the call writes over it) and `children`. There is **no live data**: a clock shows no time, a tray no icons.
* `if` and `for`: the condition or the list as the text written, and the blocks of the body. Which branch or how many entries is known only to the running shell.

A value is plain data: a length is a number of pixels, `auto`, `expand` and the words of a key are lower-case text, a percentage is text (`"50%"`), a colour is `#RRGGBB` or `#RRGGBBAA`, a token reference is `{"token": "color.surface", "value": "#12171D"}` and a slot (`<| ... |>`) is `{"slot": "text"}`.

## A configuration with errors

The preview never fails on a configuration error. `findings` has everything `check` would say. The surfaces that resolve are still in the model; a file the shell cannot read at all (a syntax error in the main shell file) gives no surfaces, so a tool that wants to keep drawing while you type keeps the last good model underneath and shows the findings over it. A `settings.tdl` that does not read gives the findings and nothing else.

## What it is not

It is a structural mockup: placement, sizes, colours and what is in each slot. It does not measure content (an `AUTO` size is a flag, not a number), does not run modules, and does not draw shadows, animations or the Frame's blended joins as the shell does. The shape is also in the [schema export](../reference/schema.md) under `preview`.
