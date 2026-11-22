# Your first Bar

A Bar is a strip along one edge of a monitor. It keeps its space free of windows, like a panel. This page writes the smallest shell file that shows one, then adds a clock.

## The smallest shell

Create `~/.config/tesserae-shell/Shells/Main_Shell.tdl` (`Main_Shell.tdl` is the file the shell looks for first) with this content:

<!-- BEGIN generated: example-set:03-first-bar/minimal -->
File `Shells/Main_Shell.tdl`:

```tdl
---
TDL: 0.2
Name: Main_Shell
---
# One Bar along the top of every monitor, with one line of text in it.
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
                Style { Background: "#1b222b" }
                Children {
                    Text { Text: "Hello, shell", Foreground: "#e4eaf1", Margin: [12, 8, 0, 0] }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:03-first-bar/minimal -->

Line by line:

* `---` ... `---` is the metadata block every file starts with. `TDL: 0.2` is the language version and `Name: Main_Shell` the file's name ([The configuration folder](configuration-folder.md#what-a-file-starts-with)).
* A line that starts with `#` is a comment.
* `Shell { ... }` is the root block of a shell file. It holds `Monitor` blocks.
* `Monitor { ... }` is one monitor's share of the shell. `Name: Main` is the block's own name (every `Monitor`, surface and named block has a unique `Name`). `Index: default` says "every monitor that no other `Monitor` block asks for": with only one `Monitor` block, every monitor gets a Bar. To pick monitors, see [Surfaces](surfaces.md#monitor).
* `Children { ... }` holds what is on that monitor: Bars, Panels, Popups and Frames.
* `Bar { ... }` is the Bar. `Name: Top_Bar` names it; `Edge: TOP` puts it along the top edge; `Width: EXPAND` makes it run edge to edge along that edge; `Height: 32` is its thickness in pixels.
* `Style { Background: "#1b222b" }` gives it a background colour. A colour is a quoted `"#RRGGBB"` (also `#RRGGBBAA`, `#RGB` and `#RGBA`) or `rgba(r g b a)`.
* `Children { Text { ... } }` is what is inside the Bar. `Text { Text: "Hello, shell" }` is a line of text; `Foreground` is its colour and `Margin: [12, 8, 0, 0]` moves it 12 pixels from the left and 8 from the top (a list of four is left, top, right, bottom).

Before you start it, ask `check` (it needs no compositor):

```sh
tesserae-shell check
```

```text
ok: 1 files checked
```

A mistake is reported with its place, the line and a hint (see [hot reload](configuration-folder.md#hot-reload)); `check` then exits with code 1. It counts only your own files, not the ones the shell ships.

Start the shell with `tesserae-shell run`. You should get a 32-pixel strip along the top of each monitor with your text in it, and the windows of your applications should start below it. Stop it with `Ctrl+C`.

> The descriptions of what a page looks like are taken from the design notes and the module sources. `check` proves the file is valid, not that it looks as you imagine.

## Adding a clock

The shell ships a `Clock` module. A shell file uses a module by writing its name as a block, with its parameters as keys:

<!-- BEGIN generated: example-set:03-first-bar/clock -->
File `settings.tdl`:

```tdl
---
TDL: 0.2
Name: Settings
---
Settings {
    Appearance { Stylesheets: [Default] }
}
```

File `Shells/Main_Shell.tdl`:

```tdl
---
TDL: 0.2
Name: Main_Shell
---
# One Bar along the top of every monitor, with the time at its right end.
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

<!-- END generated: example-set:03-first-bar/clock -->

What is new:

* `Style { Background: $color.surface }`: `$color.surface` is a **token**, a named value from the theme. The Bar takes the theme's surface colour, so it follows light and dark mode with the desktop. [Styling and themes](styling.md) lists the tokens.
* `FlexBox { ... }` lays its children out in a row (`Flex: HORIZONTAL`), centred vertically (`Align_Items: CENTER`), with 12 pixels of space at each end (`Padding: [12, 0, 12, 0]`). `Width: EXPAND` makes it as wide as the Bar.
* `Spacer { }` takes all the free space between the blocks around it, which pushes the clock to the right end.
* `Clock { format: "%H:%M" }` is the module. `format` is a `strftime` pattern; the other [Clock parameters](modules.md#clock) are `locale`, `hour_cycle`, `timezone` and `tooltip_format`. The Clock shows the date as a tooltip when the pointer rests on it.
* `settings.tdl` names the `Default` stylesheet. A stylesheet holds the rules that give blocks their colours and type; the shell's `Default` one gives text the theme's text colour and the standard modules their look. Name it in every configuration you write ([Settings](settings.md#appearance)).

While the shell runs, change `Height: 32` to `Height: 40` or the `Background` and save: the Bar changes in place after a moment. If you make a mistake the shell keeps what it shows and prints the error.

## The blocks you can put in a Bar

A Bar (or a Panel, Popup or Frame strip) holds **blocks**. The shipped modules are blocks too, written the same way; they are on [Modules](modules.md). These are the plain ones:

<!-- BEGIN generated: blocks -->
| Block | What it is | Style keys |
|---|---|---|
| `Box` | A plain container; its children are placed by their own keys. | `Transition`, `Duration`, `Easing`, `Background`, `Border_Width`, `Border_Color`, `Corner_Radius`, `Padding`, `Margin`, `Opacity`, `Elevation`, `Shadows`, `Hover_Layer`, `Pressed_Layer`, `Focus_Layer`, `Outline_Width`, `Outline_Offset`, `Outline_Color` |
| `FlexBox` | A container that lays its children out in a row or a column. | `Transition`, `Duration`, `Easing`, `Background`, `Border_Width`, `Border_Color`, `Corner_Radius`, `Padding`, `Margin`, `Opacity`, `Elevation`, `Shadows`, `Hover_Layer`, `Pressed_Layer`, `Focus_Layer`, `Outline_Width`, `Outline_Offset`, `Outline_Color`, `Spacing` |
| `Text` | Text in one style. | `Transition`, `Duration`, `Easing`, `Foreground`, `Font_Family`, `Font_Size`, `Font_Weight`, `Line_Height`, `Text_Align`, `Overflow`, `Padding`, `Margin`, `Opacity` |
| `Rectangle` | A filled rectangle with an optional border and rounded corners. | `Transition`, `Duration`, `Easing`, `Fill`, `Border_Width`, `Border_Color`, `Corner_Radius`, `Margin`, `Opacity`, `Elevation`, `Shadows`, `Outline_Width`, `Outline_Offset`, `Outline_Color` |
| `ScrollBox` | A clipped viewport that scrolls its one content child. | `Transition`, `Duration`, `Easing`, `Opacity`, `Elevation`, `Shadows`, `Outline_Width`, `Outline_Offset`, `Outline_Color` |
| `Spacer` | Takes the free space between its siblings in a flex container. | none |
| `SVG` | An SVG image from a file or an icon set; it takes the Foreground colour. | `Transition`, `Duration`, `Easing`, `Foreground`, `Opacity` |
| `Bitmap` | A raster image from a file. | `Transition`, `Duration`, `Easing`, `Opacity` |
| `Circle` | A filled circle sized by its Diameter. | `Transition`, `Duration`, `Easing`, `Fill`, `Border_Width`, `Border_Color`, `Margin`, `Opacity` |
| `Ring` | A circle drawn as a border only; Border_Width is its thickness. | `Transition`, `Duration`, `Easing`, `Border_Width`, `Border_Color`, `Margin`, `Opacity` |
| `Path` | A vector path in SVG path syntax. | `Transition`, `Duration`, `Easing`, `Fill`, `Border_Width`, `Border_Color`, `Margin`, `Opacity` |
| `Marquee` | A line of text that scrolls when it is wider than its box. | `Foreground`, `Font_Family`, `Font_Size`, `Font_Weight`, `Line_Height`, `Margin`, `Opacity`, `Transition`, `Duration`, `Easing` |
| `TextField` | An editable text field, single line or multi-line. | `Transition`, `Duration`, `Easing`, `Background`, `Border_Width`, `Border_Color`, `Corner_Radius`, `Padding`, `Margin`, `Opacity`, `Elevation`, `Shadows`, `Hover_Layer`, `Pressed_Layer`, `Focus_Layer`, `Outline_Width`, `Outline_Offset`, `Outline_Color`, `Foreground`, `Font_Family`, `Font_Size`, `Font_Weight`, `Overflow`, `Placeholder_Foreground` |

<!-- END generated: blocks -->

A few rules that hold everywhere:

* A key is written `Key: value`, one to a line or separated by commas. A block with children is `Type { keys, Children { ... } }`.
* Words such as `TOP`, `EXPAND` and `HORIZONTAL` are upper case; `true` and `false` are lower case. Text is in double quotes.
* A list is written in brackets, `[12, 0, 12, 0]`.
* A `<| ... |>` slot is an expression that a **module's layout** uses to show a value the module sends. You do not write slots in a shell file; the modules that ship already have them.
* An unknown key is an error with a hint naming the nearest keys, so a typo is caught by `check`.

Next: [surfaces](surfaces.md).
