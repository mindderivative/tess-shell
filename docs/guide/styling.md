# Styling and themes

The look of a shell comes from four things, from the most general to the most particular:

1. a **theme**: named values (colours, type sizes, corner radii, spacing, shadows, motion), called **tokens**;
2. the desktop: its colour scheme, accent colour, contrast and reduced-motion settings pick a **mode** of the theme, live;
3. **stylesheets**: rules that give blocks their look from tokens;
4. the **keys on a block**: `Style { Background: $color.surface }`, `Foreground: "#ffffff"`.

All of it is chosen in [`settings.tdl`](settings.md#appearance):

```tdl
Settings {
    Appearance {
        Theme: Dusk
        Stylesheets: [Default, Mine]
        Follow_Desktop: true
    }
}
```

`Theme` names a theme file by its `Name` (the shipped theme is `Default`, which is also what you get if you write nothing). `Stylesheets` lists stylesheets by `Name`, lowest priority first: a rule of yours that comes later wins over one of the same weight. **The `Default` stylesheet applies unless you write `Stylesheets: []`**: it gives text the theme's colour and size, and the standard modules their look, so `Stylesheets: [Default]` can be left out, and you name it only to add your own after it (`Stylesheets: [Default, Mine]`). With an empty list a TextField or List has the engine's black text, and `tesserae-shell check` says so in a note (`appearance-no-stylesheet`). A theme or stylesheet that does not exist is an error naming the nearest names.

## Tokens

A token is written `$group.name` where a colour, size or duration is expected: `Background: $color.surface`, `Corner_Radius: $shape.medium`, `Font_Size: $type.body.font_size`. A key accepts the tokens of the groups its table lists (the *Theme tokens* column below). A token the theme does not hold is an error found by `check`.

Inside a theme file the same tokens are written as nested blocks with capitalised names (`Color { Surface_Raised: "#262036" }` is `$color.surface_raised`).

<!-- BEGIN generated: tokens -->
### Color

| Token | Value | Default | The built-in modes change it in | What it is |
|---|---|---|---|---|
| `$color.surface` | colour | `"#12171D"` | light, high contrast | The ground of bars and panels. |
| `$color.surface_raised` | colour | `"#1B222B"` | light, high contrast | A surface above the ground: popups, buttons, tooltips. |
| `$color.on_surface` | colour | `"#E4EAF1"` | light, high contrast | Text and icons on a surface. |
| `$color.on_surface_muted` | colour | `"#9FAEBF"` | light, high contrast | Secondary text and icons on a surface, and a disabled state. |
| `$color.primary` | colour | `"#5B97C9"` | light, high contrast | The main colour of controls: a filled slider, a checked toggle. |
| `$color.on_primary` | colour | `"#08121C"` | light, high contrast | Text and icons on the primary colour. |
| `$color.accent` | colour | `"#4682B4"` | high contrast | The accent colour; DESKTOP follows the desktop's accent. |
| `$color.error` | colour | `"#F2958C"` | light | An error or a critical state. |
| `$color.warning` | colour | `"#E6BB6A"` | light | A warning or a low state. |
| `$color.success` | colour | `"#8CCB9A"` | light | A success state. |
| `$color.outline` | colour | `"#55657A"` | light, high contrast | Borders, dividers and tracks. |
| `$color.scrim` | colour | `"#000000"` | never | The colour laid over what a modal surface covers. |

### Type

| Token | Value | Default | The built-in modes change it in | What it is |
|---|---|---|---|---|
| `$type.caption.font_size` | number | `12` | never | The size of caption type. |
| `$type.caption.font_weight` | whole number | `400` | never | The weight of caption type. |
| `$type.caption.line_height` | number | `16` | never | The line height of caption type. |
| `$type.label.font_size` | number | `13` | never | The size of label type. |
| `$type.label.font_weight` | whole number | `500` | never | The weight of label type. |
| `$type.label.line_height` | number | `18` | never | The line height of label type. |
| `$type.body.font_size` | number | `14` | never | The size of body type. |
| `$type.body.font_weight` | whole number | `400` | never | The weight of body type. |
| `$type.body.line_height` | number | `20` | never | The line height of body type. |
| `$type.title.font_size` | number | `18` | never | The size of title type. |
| `$type.title.font_weight` | whole number | `500` | never | The weight of title type. |
| `$type.title.line_height` | number | `24` | never | The line height of title type. |
| `$type.display.font_size` | number | `28` | never | The size of display type. |
| `$type.display.font_weight` | whole number | `400` | never | The weight of display type. |
| `$type.display.line_height` | number | `36` | never | The line height of display type. |

### Shape

| Token | Value | Default | The built-in modes change it in | What it is |
|---|---|---|---|---|
| `$shape.none` | number | `0` | never | No rounding. |
| `$shape.small` | number | `4` | never | Slightly rounded corners. |
| `$shape.medium` | number | `8` | never | Rounded corners. |
| `$shape.medium_large` | number | `12` | never | Between medium and large rounding: a rich tooltip or a card (12). |
| `$shape.large` | number | `16` | never | Strongly rounded corners. |
| `$shape.extra_large` | number | `28` | never | Very strongly rounded corners: a dialog (28). |
| `$shape.full` | number | `999` | never | Fully rounded: a pill or a circle. |

### Space

| Token | Value | Default | The built-in modes change it in | What it is |
|---|---|---|---|---|
| `$space.step_1` | number | `2` | never | The smallest step of spacing. |
| `$space.step_2` | number | `4` | never | A small step of spacing. |
| `$space.step_3` | number | `8` | never | A step of spacing between small things. |
| `$space.step_4` | number | `12` | never | A step of spacing inside controls. |
| `$space.step_5` | number | `16` | never | A step of spacing between controls. |
| `$space.step_6` | number | `24` | never | A step of spacing between groups. |
| `$space.step_7` | number | `32` | never | A large step of spacing. |
| `$space.step_8` | number | `48` | never | The largest step of spacing. |

### Density

| Token | Value | Default | The built-in modes change it in | What it is |
|---|---|---|---|---|
| `$density.control_height` | number | `40` | compact, dense | The height of a button, a text field, a switch row and an icon button: 40, 32 or 28 at the default, compact and dense levels. |
| `$density.row_height` | number | `40` | compact, dense | The height of a one-line list or tree row: 40, 32 or 24. |
| `$density.menu_item_height` | number | `40` | compact, dense | The height of a menu item: 40, 32 or 28. |
| `$density.icon_size` | number | `24` | compact, dense | The painted size of an icon in an icon button: 24, 20 or 20. |
| `$density.row_padding_x` | number | `12` | compact, dense | The side padding of a list row, a tree row and a menu item: 12, 8 or 4. |
| `$density.icon_label_gap` | number | `8` | compact, dense | The gap between an icon and its label: 8, 8 or 4. |
| `$density.field_padding_x` | number | `12` | compact, dense | The side padding of a text field: 12, 8 or 8. |
| `$density.tree_indent` | number | `20` | compact, dense | The indent of one tree level: 20, 16 or 12. |
| `$density.chevron_box` | number | `24` | compact, dense | The size of a tree's chevron box: 24, 20 or 16. |

### Elevation

| Token | Value | Default | The built-in modes change it in | What it is |
|---|---|---|---|---|
| `$elevation.reach` | number | `64` | never | How far the largest shadow reaches, in pixels. |
| `$elevation.max` | shadows | `Max { Shadows { Shadow { Color: "#00000066", X: 0, Y: 16, Blur: 48, Spread: 0 } } }` | never | The shadow list at 100% elevation; a smaller Elevation scales it. |
| `$elevation.level_1` | shadows | `Level_1 { Shadows { Shadow { Color: "#0000004D", X: 0, Y: 1, Blur: 2, Spread: 0 }, Shadow { Color: "#00000026", X: 0, Y: 1, Blur: 3, Spread: 1 } } }` | never | The shadows of Elevation: LEVEL_1 (1 dp): a key and an ambient shadow. |
| `$elevation.level_2` | shadows | `Level_2 { Shadows { Shadow { Color: "#0000004D", X: 0, Y: 1, Blur: 2, Spread: 0 }, Shadow { Color: "#00000026", X: 0, Y: 2, Blur: 6, Spread: 2 } } }` | never | The shadows of Elevation: LEVEL_2 (3 dp): a menu, a tooltip, a popup. |
| `$elevation.level_3` | shadows | `Level_3 { Shadows { Shadow { Color: "#0000004D", X: 0, Y: 1, Blur: 3, Spread: 0 }, Shadow { Color: "#00000026", X: 0, Y: 4, Blur: 8, Spread: 3 } } }` | never | The shadows of Elevation: LEVEL_3 (6 dp): a dialog. |
| `$elevation.level_4` | shadows | `Level_4 { Shadows { Shadow { Color: "#0000004D", X: 0, Y: 2, Blur: 3, Spread: 0 }, Shadow { Color: "#00000026", X: 0, Y: 6, Blur: 10, Spread: 4 } } }` | never | The shadows of Elevation: LEVEL_4 (8 dp). |
| `$elevation.level_5` | shadows | `Level_5 { Shadows { Shadow { Color: "#0000004D", X: 0, Y: 4, Blur: 4, Spread: 0 }, Shadow { Color: "#00000026", X: 0, Y: 8, Blur: 12, Spread: 6 } } }` | never | The shadows of Elevation: LEVEL_5 (12 dp). |

### Motion

| Token | Value | Default | The built-in modes change it in | What it is |
|---|---|---|---|---|
| `$motion.duration.short` | number | `100` | reduced motion | A short animation, in milliseconds. |
| `$motion.duration.medium` | number | `200` | reduced motion | A medium animation, in milliseconds. |
| `$motion.duration.long` | number | `400` | reduced motion | A long animation, in milliseconds. |
| `$motion.easing.standard` | number | `standard` | never | The standard curve. |
| `$motion.easing.emphasized` | number | `emphasized` | never | The emphasised curve. |

<!-- END generated: tokens -->

### The desktop's font

One more token comes from the desktop rather than from a theme:

<!-- BEGIN generated: system-tokens -->
| Token | Value | Default | What it is |
|---|---|---|---|
| `$type.system.font_family` | font | `Roboto` | The family of the desktop's UI font (the family of the Settings portal's font-name, without its style and size), for a Font_Family: $type.system.font_family. While the desktop names no font it holds the family the shell uses for text that sets none (the default, Roboto, which the shell's renderer bundles). A theme that sets this token itself keeps its own value over the desktop's. |

<!-- END generated: system-tokens -->

Use it as `Font_Family: $type.system.font_family`. No shipped theme or stylesheet uses it; it is there for you. A theme that sets this token itself keeps its own value.

## Light, dark, high contrast and reduced motion

A theme file holds the dark look as its base values and overrides what differs in `Modes`:

```tdl
Theme {
    Color { Surface: "#1a1626" }
    Modes {
        Light { Color { Surface: "#f6f2ff" } }
        High_Contrast { Color { Surface: "#000000" } }
        Reduced_Motion { }
    }
}
```

The modes apply in this order, each over the last: the colour scheme (`Light` or `Dark`), then `High_Contrast`, then `Reduced_Motion`, which also sets every `motion.duration` token to 0. A desktop that states no colour-scheme preference gets the base values. A token a theme leaves out comes from the `Default` theme, token by token, so a theme can be as short as the colours you change. `Accent: DESKTOP` makes the accent colour follow the desktop's own accent colour (and the primary colour when the desktop has none).

### Following the desktop

With `Follow_Desktop: true` (the default) the shell reads the desktop's **Settings portal** (`org.freedesktop.portal.Desktop`) once at start, then listens for changes, with no polling:

| The desktop says | What the shell does |
|---|---|
| colour scheme (`org.freedesktop.appearance` `color-scheme`) | applies the theme's `Light` or `Dark` mode |
| accent colour (`accent-color`) | gives `Accent: DESKTOP` its colour |
| contrast (`contrast`) | applies `High_Contrast` |
| reduced motion (`reduced-motion`), or animations off (`org.gnome.desktop.interface` `enable-animations: false`, which KDE also serves) | applies `Reduced_Motion`: no animations; either one is enough |
| icon theme (`icon-theme`) | the icon theme the [Tray](modules.md#tray) uses, then the `kdeglobals` one, then `hicolor` |
| UI font (`font-name`) | the family in `$type.system.font_family` |

A change is followed live: switch Plasma between light and dark and the shell follows. A portal that does not answer within a moment makes the shell start on the defaults (it never delays your bar) and apply the answer when it arrives; one that is missing gives one warning, `portal: ... using the default appearance`, in the log. `Follow_Desktop: false` does not read the portal: you get the theme's base look. Changing `Follow_Desktop` needs a restart.

## Density

The sizes of controls come in three levels: `DEFAULT` (a 40 pixel button), `COMPACT` (32, the shell's default) and `DENSE` (28). `Appearance { Density: DENSE }` in `settings.tdl` picks the level for the whole shell, and a Bar or Panel can write its own `Density: DEFAULT` (a touch panel on a desktop bar, say). The sizes are the `density.*` tokens of [Density](#density); the base values of the theme are the `DEFAULT` level, and its `Modes { Compact { Density { ... } } }` and `Dense` blocks replace them, as `Light` replaces colours. The standard Button, Toggle, Checkbox, MenuItem and the Applications list take their heights from them.

A module reads the tokens of its surface's level in a slot, as `<| density.control_height |>`; write the same in your own modules to follow the level. The setting applies on reload. A theme that lacks the group falls back to the Default theme's values.

## Stylesheets

A stylesheet is a `_Stylesheet.tdl` file in `Stylesheets/` with `Rule` blocks. Each has a `Selector` and the style keys to apply. A rule can use any style key from the table at the end of this page.

<!-- BEGIN generated: example-set:06-styling/dusk -->
File `settings.tdl`:

```tdl
---
TDL: 0.2
Name: Settings
---
Settings {
    Appearance {
        Theme: Dusk
        Stylesheets: [Default, Mine]
        Follow_Desktop: true
    }
}
```

File `Shells/Main_Shell.tdl`:

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
                Height: 36
                Style { Background: $color.surface }
                Children {
                    FlexBox {
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Align_Items: CENTER
                        Spacing: 12
                        Padding: [12, 0, 12, 0]
                        Children {
                            Text { Text: "Battery low", Class: warn }
                            FlexBox {
                                Class: chip
                                Padding: [10, 4, 10, 4]
                                Children { Text { Text: "A chip", Font_Family: $type.system.font_family } }
                            }
                            Spacer { }
                            Clock { }
                        }
                    }
                }
            }
        }
    }
}
```

File `Themes/Dusk_Theme.tdl`:

```tdl
---
TDL: 0.2
Name: Dusk
---
# A theme need only hold what differs from the Default theme; a token it leaves out comes from
# there. The base values are the dark look; Modes change them for light, high contrast and
# reduced motion.
Theme {
    Color {
        Surface: "#1a1626"
        Surface_Raised: "#262036"
        Primary: "#b392f0"
        Accent: DESKTOP
    }
    Modes {
        Light {
            Color {
                Surface: "#f6f2ff"
                Surface_Raised: "#ffffff"
                On_Surface: "#1d1830"
                Primary: "#5b3fa6"
            }
        }
    }
}
```

File `Stylesheets/Mine_Stylesheet.tdl`:

```tdl
---
TDL: 0.2
Name: Mine
---
# Rules pick blocks by type ("Text"), by class (".warn"), by name ("#Face") or by a module's
# part ("Button::label"), each with an optional state (":hovered", ":pressed", ":disabled").
Stylesheet {
    Rule { Selector: ".warn", Foreground: $color.warning, Font_Weight: 700 }
    Rule { Selector: ".chip", Background: $color.surface_raised, Corner_Radius: $shape.medium }
    Rule { Selector: ".chip:hovered", Background: $color.primary }
}
```

<!-- END generated: example-set:06-styling/dusk -->

A selector is one of:

| Selector | Picks |
|---|---|
| `"Text"` | every block of that type (`Text`, `FlexBox`, `Rectangle`, ...) |
| `"Clock"`, `"Button"` | a module's root block, at every use of the module |
| `".warn"` | every block with `Class: warn` |
| `"#Face"` | the block with `Name: Face` |
| `"Slider::handle"` | a part of a module (the parts are listed per module on [Modules](modules.md)) |

and may end in a **state**: `:hovered`, `:pressed`, `:checked`, `:selected`, `:focused` or `:disabled`. A state adds to the base rule; `:disabled` wins over `:hovered` and `:pressed`. A part rule beats a class or type rule on the same block. A selector that names a part the module does not have is an error naming the nearest parts; a part after a class (`".warn::part"`) is not built.

A block takes a class with `Class: warn` (several are written as a list). A module's own look is in its `_Style.tdl` file, which the module names with a `Style:` line, with `Classes { clock_text { Kind: Text, Font_Size: 14 } }`; your stylesheet rules override it because they come later.

`:focused` is the ring that **keyboard** focus shows (a click focuses without it); a block shows it only if it takes `Shadows`, so a `Focusable` block should be a `Box`, `FlexBox`, `Rectangle`, `ScrollBox` or `TextField`. See [Keyboard and shortcuts](keyboard.md#focus).

### Style keys

These are the keys a `Style { }` block, a style key written directly on a block, or a `Rule` may hold. Each block type takes the ones listed for it in [Your first Bar](first-bar.md#the-blocks-you-can-put-in-a-bar).

<!-- BEGIN generated: style-keys -->
| Style key | Value | Used by | Theme tokens | What it does |
|---|---|---|---|---|
| `Transition` | list of text | 12 block types | motion | The keys whose change animates, a key name or a list of them. |
| `Duration` | milliseconds | 12 block types | motion.duration.* | How long a change of a Transition key takes, in milliseconds. |
| `Easing` | `STANDARD` `EMPHASIZED` `LINEAR` | 12 block types |  | The curve of the animation: STANDARD, EMPHASIZED or LINEAR. |
| `Background` | colour | Box, FlexBox, TextField | color | The fill behind the block's content, a colour or a theme token. |
| `Border_Width` | number | 7 block types | type, shape, space, density, elevation, motion | The width of the border line; 0 draws none. |
| `Border_Color` | colour | 7 block types | color | The colour of the border line, a colour or a theme token. |
| `Corner_Radius` | radius | Box, FlexBox, Rectangle, TextField | shape | The radius of the corners: one number, or four from the top-left corner clockwise. |
| `Padding` | sides | Box, FlexBox, Text, TextField | space | Space between the content and the four sides: one number or four (left, top, right, bottom). |
| `Margin` | sides | 9 block types | space | Transparent space around the block: one number or four (left, top, right, bottom). |
| `Opacity` | number | 12 block types | type, shape, space, density, elevation, motion | How opaque the block and what it holds is painted, from 0 (invisible) to 1. |
| `Elevation` | percentage | Box, FlexBox, Rectangle, ScrollBox, TextField |  | How high the block floats: a percentage of the theme's largest shadow (0% is no shadow) or a level, LEVEL_0 to LEVEL_5, whose two shadows the theme holds (a menu is LEVEL_2, a dialog LEVEL_3). |
| `Shadows` | shadows | Box, FlexBox, Rectangle, ScrollBox, TextField | elevation.max | A list of Shadow blocks, the first on top; it replaces Elevation when both are written. |
| `Spacing` | number | FlexBox | space | The space between the children, in pixels. |
| `Foreground` | colour | Text, SVG, Marquee, TextField | color | The colour of the text or of the icon, a colour or a theme token. |
| `Font_Family` | font | Text, Marquee, TextField | color, motion | A font family name, or a list of them in the order of fallback. |
| `Font_Size` | number | Text, Marquee, TextField | type.*.font_size | The size of the type, above 0. |
| `Font_Weight` | whole number | Text, Marquee, TextField | type.*.font_weight | The weight of the type as a whole number, 400 regular, 700 bold. |
| `Line_Height` | number | Text, Marquee | type.*.line_height | The height of one line, above 0. |
| `Text_Align` | `START` `CENTER` `END` | Text |  | How a line sits in the text's box: START, CENTER or END. |
| `Overflow` | `CLIP` `ELLIPSIS` | Text, TextField |  | What happens to text that does not fit: CLIP cuts it, ELLIPSIS ends it with dots (a TextField also has SCROLL). |
| `Fill` | colour | Rectangle, Circle, Path | color | The fill of the shape, a colour or a theme token. |
| `Placeholder_Foreground` | colour | TextField | color | The colour of the placeholder text. |

<!-- END generated: style-keys -->

## Icons

An icon is an `SVG` block with `Icon` (a name) or `Source` (a file), or the [Icon](modules.md#icon) module. The shell ships the **`mdi`** set (Material Design Icons, over 7000 icons; its licence is in the package). A name is `mdi:account`; browse the names on the set's website. A name with `+dot` on the end (`mdi:battery-10+dot`) is that icon with a dot of the same colour drawn to its right.

* An icon from a file: `Source: "dot.svg"`, a path relative to the shell file. An SVG that draws with `currentColor` takes the block's `Foreground`, so it follows the theme.
* Your own set: a file `Icons/mine.json` in Iconify's JSON format, with a `prefix`, `icons` (each name with an SVG `body`) and optionally `width` and `height` (24 by default). Its icons are used as `mine:star`. A set of the same prefix in your `Icons/` folder wins over the shipped one; a name with no prefix is looked up in `mdi` first, then in the other sets. An unreadable set is skipped, with a warning.
* A name that no set has shows a broken-image icon and logs one warning.
* The colour of an icon is `Foreground` (`Style { Foreground: $color.primary }`); a stylesheet rule `Selector: "SVG"` sets it for all.

<!-- BEGIN generated: example-set:06-styling/icons -->
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
# Icons: a name from the shipped mdi set, a name from a set of your own in the Icons folder
# (mine:star, from Icons/mine.json), and a plain SVG file beside this one.
Shell {
    Monitor {
        Name: Main
        Index: default
        Children {
            Bar {
                Name: Top_Bar
                Edge: TOP
                Width: EXPAND
                Height: 36
                Style { Background: $color.surface }
                Children {
                    FlexBox {
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Align_Items: CENTER
                        Spacing: 12
                        Padding: [12, 0, 12, 0]
                        Children {
                            SVG { Icon: "mdi:account", Width: 20, Height: 20, Style { Foreground: $color.on_surface } }
                            SVG { Icon: "mine:star", Width: 20, Height: 20, Style { Foreground: $color.warning } }
                            SVG { Source: "dot.svg", Width: 12, Height: 12, Style { Foreground: $color.primary } }
                        }
                    }
                }
            }
        }
    }
}
```

File `Icons/mine.json`:

```json
{
  "prefix": "mine",
  "width": 24,
  "height": 24,
  "icons": {
    "star": {
      "body": "<path fill=\"currentColor\" d=\"M12 2l2.9 6.9 7.1.6-5.4 4.7 1.6 7.1L12 17.6 5.8 21.3l1.6-7.1L2 9.5l7.1-.6z\"/>"
    }
  }
}
```

The folder also holds `Shells/dot.svg`, which are not shown.

<!-- END generated: example-set:06-styling/icons -->

## Shadows

`Elevation: 20%` on a Bar, Panel, Popup, Rectangle or Box floats it above what is behind: it is a percentage of the theme's largest shadow (`$elevation.max`), and `0%` is none. For full control write `Shadows { Shadow { Color: "#00000055", X: 0, Y: 2, Blur: 6, Spread: 0 } }`; the first shadow is on top. A surface cannot draw outside its own window, so a Bar or Panel with a shadow is a slightly larger transparent window: the shadow is drawn in that margin and the reserved space does not change.

## Transitions and reduced motion

A block can ease a change instead of making it at once: `Transition: [Fill, Opacity]` names the keys that animate, `Duration` is the time in milliseconds (200 if you write none; `$motion.duration.short`, `medium` and `long` are the theme's durations) and `Easing` the curve, `STANDARD`, `EMPHASIZED` or `LINEAR`. The effects example shows a tile that eases its fill when the pointer arrives:

<!-- BEGIN generated: example-set:06-styling/effects -->
File `settings.tdl`:

```tdl
---
TDL: 0.2
Name: Settings
---
Settings {
    Appearance { Stylesheets: [Default, Tiles] }
}
```

File `Shells/Main_Shell.tdl`:

```tdl
---
TDL: 0.2
Name: Main_Shell
---
# Shadows, and a change that is animated: the tile's Fill eases over 200 ms when the pointer
# comes (the :hovered rule of the stylesheet below) and goes. With reduced motion it is instant.
Shell {
    Monitor {
        Name: Main
        Index: default
        Children {
            Bar {
                Name: Top_Bar
                Edge: TOP
                Width: EXPAND
                Height: 36
                Style { Background: $color.surface, Elevation: 20% }
                Children {
                    FlexBox {
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Align_Items: CENTER
                        Padding: [12, 0, 12, 0]
                        Children {
                            Rectangle {
                                Class: tile
                                Width: 80
                                Height: 24
                                Corner_Radius: 6
                                Transition: [Fill]
                                Duration: 200
                                Easing: STANDARD
                                Shadows { Shadow { Color: "#00000055", X: 0, Y: 2, Blur: 6, Spread: 0 } }
                            }
                        }
                    }
                }
            }
        }
    }
}
```

File `Stylesheets/Tiles_Stylesheet.tdl`:

```tdl
---
TDL: 0.2
Name: Tiles
---
Stylesheet {
    Rule { Selector: ".tile", Fill: $color.surface_raised }
    Rule { Selector: ".tile:hovered", Fill: $color.primary }
}
```

<!-- END generated: example-set:06-styling/effects -->

With the desktop's reduced-motion setting everything is instant: the `Reduced_Motion` mode sets every duration to 0, Panel animations are skipped, a Marquee does not scroll and an Expander does not ease. A theme can also use the mode to turn other things off.

Next: [`settings.tdl`](settings.md).
