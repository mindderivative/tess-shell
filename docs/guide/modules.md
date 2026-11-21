# Modules

A **module** is a ready-made piece of a Bar, Panel or Popup: a clock, a battery indicator, a button, a launcher. The shell ships the ones on this page. You use one by writing its name as a block, with its parameters as keys:

```tdl
Clock { format: "%H:%M", timezone: "Europe/Berlin" }
```

Each section below says what the module shows, lists its parameters (generated from the shell's schema, with their defaults), and gives a configuration folder that you can copy.

<!-- BEGIN generated: module-index -->
| Module | What it is |
|---|---|
| [Applications](#applications) | The launcher: |
| [Audio](#audio) | The default sound output: |
| [Audio_Outputs](#audio_outputs) | The content of the Audio module's outputs Popup: |
| [Badge](#badge) | A pill with a count, or a dot, in the error colour |
| [Battery](#battery) | The battery's charge as an icon and a number, with a tooltip; |
| [Button](#button) | A pressable control with an optional icon and text |
| [Checkbox](#checkbox) | A box that is checked or not, with an optional text beside it |
| [Clock](#clock) | The time, with a tooltip that shows the date |
| [Expander](#expander) | A block that shows or hides its content with an animation |
| [Icon](#icon) | An icon from an icon set or a file, sized by one number |
| [Image](#image) | A picture from a file, with a placeholder while it loads |
| [Label](#label) | A line of text in the theme's body type |
| [List](#list) | A list of entries of which one can be chosen |
| [Marquee_Text](#marquee_text) | A line of text that scrolls when it is wider than its box |
| [Media](#media) | What a media player plays, with previous, play or pause and next buttons |
| [Menu](#menu) | The content of a Popup: |
| [MenuItem](#menuitem) | A row of a menu: |
| [Network](#network) | How the machine is connected, as NetworkManager reports it |
| [ProgressBar](#progressbar) | A bar that shows a value between a minimum and a maximum |
| [Slider](#slider) | A control that sets a value between a minimum and a maximum by dragging |
| [Task_Item](#task_item) | One button of the Tasks row: |
| [Tasks](#tasks) | The open windows as a row of buttons, from the shell's KWin script; |
| [TextBox](#textbox) | Several lines of text that can wrap, be cut and be selected |
| [TextEditor](#texteditor) | A multi-line text field |
| [TextInput](#textinput) | A single-line text field |
| [Toggle](#toggle) | A switch that is on or off |
| [Tray](#tray) | The system tray: |
| [Tray_Item](#tray_item) | One icon of the Tray, with a tooltip |
| [Tray_Menu](#tray_menu) | The content of the Popups that draw a tray item's menu, one level of it |
| [Volume_OSD](#volume_osd) | The volume on-screen display: |
| [Workspaces](#workspaces) | The virtual desktops as buttons: |

<!-- END generated: module-index -->

## Using a module

* **Parameters** are written as keys. The names are case-sensitive, and the display modules use two styles: lower case (`show_percent`) for the ones that read a service, and capitalised (`Text`, `Value`) for the widgets. An unknown parameter is an error, with a hint naming the nearest ones. A parameter with no default must be given.
* **Common keys.** Every module use also takes the keys listed below the list: they size, place and describe it.
* **Events.** A module use may handle the events listed in its section, written inside it: `On_Click { Action: Toggle, Target: Notes }`, `On_Changed { Action: Call, Target: "Module.action", name: value }`. See [Surfaces](surfaces.md#showing-hiding-and-toggling) for the actions. In a handler's arguments a `<| event.value |>` slot is replaced by the value when the event fires.
* **Modules that depend on a service hide themselves** when the service is not there: Battery without a battery or UPower, Workspaces without KWin, Network without NetworkManager, Media without a player, Audio without a sound server, Tray without a StatusNotifier watcher or items, Tasks without KWin's script or windows. A hidden module takes no space in the Bar, not even the `Spacing` beside it, and shows no placeholder. It returns when the service does.
* **Look.** The modules are styled by the `Default` stylesheet (name it in `settings.tdl`, as the examples do) and the theme's tokens, so they follow light and dark. A stylesheet rule addresses a module by name (`Button`), a part of it (`Slider::handle`) and a state (`Button:hovered`); see [Styling and themes](styling.md). A module of your own with the same name in your `Modules/` folder replaces the shipped one.
* **Accessibility.** The modules name themselves and carry their state for assistive technology (a Toggle says whether it is checked, a Slider its value). `Media`, `Audio` and `Tasks` can also make polite spoken announcements with `announce: true`; `Network`, `Battery` and `Applications` announce without a parameter.
* **Added after 0.1.1** (not in the package on PyPI at 0.1.1; Volume_OSD needs 0.2.0): the [Tasks](#tasks), [Applications](#applications) and [Volume_OSD](#volume_osd) modules, the `announce` parameters, `Value_Text` of the Slider and the `Label` of TextInput and TextEditor ([Install and start](install.md#what-needs-a-recent-release)).

The common keys of every module use are:

<!-- BEGIN generated: module-common-keys -->
`Key`, `Visible`, `Enabled`, `Width`, `Height`, `Min_Width`, `Min_Height`, `Max_Width`, `Max_Height`, `Aspect_Ratio`, `Margin`, `Flex_Grow`, `Flex_Shrink`, `Align_Self`, `Z_Index`, `Label`, `Tooltip_When_Disabled`, `A11y_Hidden`, `Opacity`, `Position`, `Left`, `Top`, `Right`, `Bottom`, `Translate_X`, `Translate_Y`, `Scale`, `Rotation`, `Clip_Children`, `Role`, `Description`, `Live`, `Focusable`, `Tab_Index`

<!-- END generated: module-common-keys -->

`Width`, `Height`, `Margin`, `Flex_Grow`, `Position` and the like size and place the module among its siblings (a `Label { Width: 120 }` is 120 pixels wide). `Label` here is the accessible name that assistive technology reads; it is not the `Label` module. `Key` names a list entry. `Tooltip: "text"` also works on a module use.

## Clock

The time, with a tooltip that shows the date. With no `format` the shell uses `%H:%M`, or `%I:%M %p` when `hour_cycle` is `12`; `desktop` (the default) follows the locale: 12 hours when the time format of the Clock's locale counts to 12 (`en_US` does, `de_DE` and `en_GB` do not), else 24. The locale is the `locale` param, or, when that is empty, the one the environment names (`LC_ALL`, then `LC_TIME`, then `LANG`); with none set, `C` or one the system lacks, it is 24 hours. The shell reads no 12/24-hour switch of System Settings (the Settings portal values it follows are appearance ones: colour scheme, accent, fonts, icon theme, animations). A `locale` the system lacks is warned about once and ignored (see `locale -a` for the ones you have). A format with seconds (`%S`) makes it update every second, otherwise once a minute.

<!-- BEGIN generated: module:Clock -->
The time, with a tooltip that shows the date.

| Param | Type | Default | What it does |
|---|---|---|---|
| `format` | string | `""` | A strftime pattern; empty is chosen by hour_cycle. |
| `locale` | string | `""` | A locale name such as de_DE for month and day names; empty is the process's own. The system must have it; a missing one is warned about and ignored. |
| `hour_cycle` | string | `"desktop"` | desktop, 12 or 24. desktop is 12 hours when the time format of the locale (the locale param, else LC_ALL, LC_TIME or LANG) counts to 12, as en_US does, and 24 otherwise or when no locale is set. |
| `timezone` | string | `""` | An IANA zone such as Europe/Berlin; empty is the local zone. |
| `tooltip_format` | string | `"%A, %d %B %Y"` | A strftime pattern for the text of the tooltip the pointer opens on the clock. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

<!-- END generated: module:Clock -->

<!-- BEGIN generated: example-set:05-modules/clock -->
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
# The Clock twice: the local time with the date as its tooltip, and the time in Tokyo.
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            Spacer { }
                            Clock { format: "%a %d %b  %H:%M", tooltip_format: "%A, %d %B %Y" }
                            Clock { timezone: "Asia/Tokyo", format: "Tokyo %H:%M" }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/clock -->

## Label

One line of text in the theme's body type, not editable. A text wider than the Label is cut; give it a `Width` to make it narrower than its text. The text is its accessible name. `Label:disabled` styles it while `Enabled: false`.

<!-- BEGIN generated: module:Label -->
A line of text in the theme's body type.

| Param | Type | Default | What it does |
|---|---|---|---|
| `Text` | string | `""` | The words. |

Events a use may handle: .

<!-- END generated: module:Label -->

<!-- BEGIN generated: example-set:05-modules/label -->
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            Label { Text: "Hello from a Label" }
                            Label { Text: "A long text that is cut at the width of the Label", Width: 120 }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/label -->

## Icon

An icon, sized by one number. `Icon` is a name (`mdi:home`, from the shell's `mdi` set, then the desktop's icon theme, then your `Icons/` folder) or a file written relative to the file that names it: an `.svg` (it takes the text colour) or a `.png`, `.jpg`, `.gif` or `.webp` (drawn as it is). A name that no set has shows the broken-image icon, with one warning in the log. An icon is decoration and hidden from assistive technology unless the use has a `Label`. See [Styling and themes](styling.md#icons).

<!-- BEGIN generated: module:Icon -->
An icon from an icon set or a file, sized by one number.

| Param | Type | Default | What it does |
|---|---|---|---|
| `Icon` | icon | `""` | An icon name such as mdi:account, or a file path relative to the file. |
| `Size` | number | `16` | The width and the height, in pixels. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

<!-- END generated: module:Icon -->

<!-- BEGIN generated: example-set:05-modules/icon -->
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            Icon { Icon: "mdi:home", Size: 20 }
                            Icon { Icon: "mdi:wifi", Size: 20, Label: "Wi-Fi" }
                            Icon { Icon: "mdi:battery-charging-80", Size: 24, Label: "Battery charging" }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/icon -->

## Image

A picture from a `.png`, `.jpg`, `.gif` or `.webp` file (the first frame of a gif). The shell decodes it and caches it by path and modification time. A file larger than 4096 by 4096 pixels, or one that cannot be read, shows an error picture and logs one warning. The box is 96 by 96 pixels unless the use writes a `Width` or `Height`. `Fit` is `CONTAIN` (all of it, inside the box), `COVER` (the box is full, the picture cropped), `FILL` (stretched) or `NONE` (its own size). `Placeholder` shows while there is no `Source`: a colour such as `"#334455"` or an icon name.

<!-- BEGIN generated: module:Image -->
A picture from a file, with a placeholder while it loads.

| Param | Type | Default | What it does |
|---|---|---|---|
| `Source` | path | `""` | The file to show, relative to the file that names it. |
| `Fit` | string | `"CONTAIN"` | How the picture fits its box: CONTAIN, COVER, FILL or NONE. |
| `Placeholder` | icon | `""` | A colour or an icon shown while the picture loads or fails. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

<!-- END generated: module:Image -->

<!-- BEGIN generated: example-set:05-modules/image -->
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
# logo.png sits beside this file; the second Image has no Source and shows its Placeholder colour.
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            Image { Source: "logo.png", Width: 32, Height: 32 }
                            Image { Placeholder: "#334455", Width: 32, Height: 32 }
                        }
                    }
                }
            }
        }
    }
}
```

The folder also holds `Shells/logo.png`, which are not shown.

<!-- END generated: example-set:05-modules/image -->

## Badge

A count, or a dot, in the error colour, to sit on the corner of something else. `Count` shows nothing when it is 0 (unless `Show_Zero`), and a count above `Max` reads `99+`. Place it with the common keys: `Position: ABSOLUTE, Right: 0, Top: 0` inside a box. A Badge is decoration, hidden from assistive technology: put the information in the name of the thing it sits on (`Label: "Mail, 3 unread"`). Parts: `Badge::dot`.

<!-- BEGIN generated: module:Badge -->
A pill with a count, or a dot, in the error colour.

| Param | Type | Default | What it does |
|---|---|---|---|
| `Count` | number | `0` | The number shown; 0 shows nothing unless Show_Zero is true. |
| `Show_Zero` | boolean | `false` | Shows the badge for a count of 0. |
| `Max` | number | `99` | The largest number shown; above it the badge reads that number and a plus. |
| `Dot` | boolean | `false` | Shows a dot with no number. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

<!-- END generated: module:Badge -->

<!-- BEGIN generated: example-set:05-modules/badge -->
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            Box {
                                Width: 28
                                Height: 24
                                Children {
                                    Icon { Icon: "mdi:email-outline", Size: 24, Label: "Mail, 3 unread" }
                                    Badge { Count: 3, Position: ABSOLUTE, Right: 0, Top: 0 }
                                }
                            }
                            Box {
                                Width: 28
                                Height: 24
                                Children {
                                    Icon { Icon: "mdi:bell-outline", Size: 24, Label: "Notifications" }
                                    Badge { Dot: true, Position: ABSOLUTE, Right: 2, Top: 0 }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/badge -->

## Button

A pressable control with an optional icon and text. A press that starts on the button and ends outside it is not a click. Enter and Space press a focused button. `Enabled: false` dims it and makes it ignore the pointer. An icon-only button needs a `Label`, its accessible name: the shell warns at load when it has none. A button that controls an [Expander](#expander) says so with `Expandable: true, Expanded: ...`. Parts: `Button::icon`, `Button::label`; states `:hovered`, `:pressed`, `:disabled`, `:focused`.

<!-- BEGIN generated: module:Button -->
A pressable control with an optional icon and text.

| Param | Type | Default | What it does |
|---|---|---|---|
| `Text` | string | `""` | The words on the button. |
| `Icon` | icon | `""` | An icon name such as mdi:home, or a file path, shown beside the text. |
| `Icon_Position` | string | `"START"` | Where the icon sits: START (before the text) or END (after it). |
| `Label` | string | `""` | The name assistive technology reads aloud; the text when it is empty. |
| `Expandable` | boolean | `false` | True when the button controls an Expander: it then carries the accessibility state expanded, with the value of Expanded. |
| `Expanded` | boolean | `false` | Whether the Expander the button controls is open; read only when Expandable is true. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

<!-- END generated: module:Button -->

<!-- BEGIN generated: example-set:05-modules/button -->
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            Button { Text: "Open", Icon: "mdi:folder-open-outline" }
                            Button { Icon: "mdi:cog", Label: "Settings" }
                            Button { Text: "Disabled", Enabled: false }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/button -->

## Checkbox

A box with a check mark and, if `Text` is written, a label beside it; a click on the label flips it too. A click flips it and raises `On_Changed` once, with `event.old`, `event.new` and `event.value` (true or false). Setting `Checked` from outside raises nothing. There is no mixed state. Space flips a focused checkbox; Enter does nothing. Parts: `Checkbox::box`, `Checkbox::mark`, `Checkbox::label`; states `:checked`, `:hovered`, `:pressed`, `:disabled`.

<!-- BEGIN generated: module:Checkbox -->
A box that is checked or not, with an optional text beside it.

| Param | Type | Default | What it does |
|---|---|---|---|
| `Checked` | boolean | `false` | Whether the box is checked; set from outside. |
| `Text` | string | `""` | A label beside the box; a click on it flips the checkbox too. |
| `Label` | string | `""` | The name assistive technology reads aloud; the text when it is empty. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Changed`, `On_Key_Down`.

<!-- END generated: module:Checkbox -->

<!-- BEGIN generated: example-set:05-modules/checkbox -->
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            Checkbox { Text: "Remember me" }
                            Checkbox { Text: "Already checked", Checked: true }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/checkbox -->

## Toggle

A switch that is on or off, with a thumb that slides. It works like a Checkbox: a click or Space flips it and raises `On_Changed` once. Give it a `Label` to name it. Parts: `Toggle::track`, `Toggle::thumb`; states `:checked`, `:hovered`, `:pressed`, `:disabled`. It is 40 by 22 pixels.

<!-- BEGIN generated: module:Toggle -->
A switch that is on or off.

| Param | Type | Default | What it does |
|---|---|---|---|
| `Checked` | boolean | `false` | Whether the switch is on; set from outside. |
| `Label` | string | `""` | The name assistive technology reads aloud for the switch. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Changed`, `On_Key_Down`.

<!-- END generated: module:Toggle -->

<!-- BEGIN generated: example-set:05-modules/toggle -->
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            Toggle { Label: "Do not disturb" }
                            Toggle { Label: "Night light", Checked: true }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/toggle -->

## Slider

A value between `Min` and `Max`, set by dragging. A press on the track jumps the handle there and a drag moves it in steps of `Step`, also when the pointer leaves the slider sideways. `On_Changed` fires for each new value the user makes; `On_Released` fires once when the press ends, with the final value in `event.value`: use it for something that must happen once, such as a seek. A value the module sets from outside raises neither. It is 160 by 20 pixels (20 by 160 when `Orientation: VERTICAL`, with `Max` at the top) unless you write a `Width` or `Height`. Keys: Left and Down take a step off, Right and Up put one on, Page Up and Page Down ten steps, Home and End go to `Min` and `Max`. Give it a `Label`, and a `Value_Text` to have the value said in words. Parts: `Slider::track`, `Slider::fill`, `Slider::handle`.

<!-- BEGIN generated: module:Slider -->
A control that sets a value between a minimum and a maximum by dragging.

| Param | Type | Default | What it does |
|---|---|---|---|
| `Value` | number | `0` | The value, set from outside. |
| `Min` | number | `0` | The least value. |
| `Max` | number | `100` | The greatest value. |
| `Step` | number | `1` | The increment; a drag snaps to it. |
| `Orientation` | string | `"HORIZONTAL"` | The direction: HORIZONTAL or VERTICAL. |
| `Label` | string | `""` | The name assistive technology reads aloud for the slider. |
| `Value_Text` | string | `""` | The value in words for assistive technology ('45 percent'); without one it reads the number. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Changed`, `On_Released`, `On_Key_Down`.

<!-- END generated: module:Slider -->

<!-- BEGIN generated: example-set:05-modules/slider -->
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
# The first Slider sets the sound volume, once, when you let go of it: On_Released calls the Audio module's set_volume action.
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            Slider {
                                Label: "Volume"
                                Value: 30
                                Width: 140
                                On_Released { Action: Call, Target: "Audio.set_volume", percent: <| event.value |> }
                            }
                            Audio { show_percent: true }
                            Slider { Label: "Steps of ten", Value: 50, Step: 10, Min: 0, Max: 100, Value_Text: "50 percent" }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/slider -->

## ProgressBar

A read-only bar whose fill is as wide as the value is far from `Min` to `Max`. A change of `Value` eases the fill (instantly with reduced motion). It is 160 by 8 pixels unless you write a `Width` or `Height`. Give it a `Label`. Parts: `ProgressBar::track`, `ProgressBar::fill`.

<!-- BEGIN generated: module:ProgressBar -->
A bar that shows a value between a minimum and a maximum.

| Param | Type | Default | What it does |
|---|---|---|---|
| `Value` | number | `0` | The progress, between Min and Max. |
| `Min` | number | `0` | The value at which the bar is empty. |
| `Max` | number | `100` | The value at which the bar is full. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

<!-- END generated: module:ProgressBar -->

<!-- BEGIN generated: example-set:05-modules/progressbar -->
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            ProgressBar { Value: 65, Label: "Download" }
                            ProgressBar { Value: 12, Min: 0, Max: 20, Width: 80, Label: "Disk quota" }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/progressbar -->

## List

A scrolling list of entries, one of which can be chosen. The entries are the use's children; each has a `Key`, and a `For` over your own data makes them from a module. The wheel scrolls it; it is 240 by 200 pixels unless you write a size. A click chooses an entry (`Selection: SINGLE`) and raises `On_Changed` with the old and new keys; with `Selection: NONE` it chooses nothing. `Selected` marks an entry from outside and raises nothing. The chosen entry takes the style state `:selected`: give the entries a class and style `.list_item:selected`, as the `Default` stylesheet does for the class `list_item`. Keys: one Tab stop, then Up and Down move the choice, Page Up and Page Down by a page, Home and End to the ends, and letters typed jump to the next entry starting with them.

<!-- BEGIN generated: module:List -->
A list of entries of which one can be chosen.

| Param | Type | Default | What it does |
|---|---|---|---|
| `Selected` | string | `""` | The Key of the chosen entry, set from outside; empty is none. |
| `Selection` | string | `"SINGLE"` | SINGLE lets one entry be chosen; NONE does not. |
| `Label` | string | `""` | The name assistive technology reads aloud for the list. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Changed`.

<!-- END generated: module:List -->

<!-- BEGIN generated: example-set:05-modules/list -->
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
# A Panel holds the List: a list is taller than a Bar.
Shell {
    Monitor {
        Name: Main
        Index: default
        Children {
            Panel {
                Name: Pick_One
                Layer: TOP
                Anchor: [TOP, LEFT]
                Inset: [24, 24, 0, 0]
                Width: 260
                Height: 160
                Style { Background: $color.surface, Corner_Radius: 8 }
                Children {
                    List {
                        Label: "Colours"
                        Selected: "green"
                        Width: 240
                        Height: 140
                        Margin: 10
                        Children {
                            FlexBox { Class: list_item, Key: red, Height: 28, Align_Items: CENTER, Padding: [8, 0, 8, 0], Children { Text { Text: "Red" } } }
                            FlexBox { Class: list_item, Key: green, Height: 28, Align_Items: CENTER, Padding: [8, 0, 8, 0], Children { Text { Text: "Green" } } }
                            FlexBox { Class: list_item, Key: blue, Height: 28, Align_Items: CENTER, Padding: [8, 0, 8, 0], Children { Text { Text: "Blue" } } }
                            FlexBox { Class: list_item, Key: amber, Height: 28, Align_Items: CENTER, Padding: [8, 0, 8, 0], Children { Text { Text: "Amber" } } }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/list -->

## Menu

The content of a [Popup](surfaces.md#popup): a column of `MenuItem`s. A button opens the Popup (`On_Click { Action: Toggle, Target: File_Menu }`). A click on an item runs its handler and closes the whole menu. Keys: a menu opened from the keyboard takes the focus; Up and Down move the lit row (round the ends, over disabled rows), Home and End go to the ends, Enter and Space run the row, Right opens the submenu of the lit row, Left closes a submenu, and Escape closes the innermost level (Escape on the first menu closes it and gives the focus back to the block it was opened from). A Menu is at least 160 pixels wide.

<!-- BEGIN generated: module:Menu -->
The content of a Popup: a column of menu items.

| Param | Type | Default | What it does |
|---|---|---|---|
| `Label` | string | `""` | The name assistive technology reads aloud for the menu. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

<!-- END generated: module:Menu -->

### MenuItem

One row of a Menu: an icon, the text, a key hint at the end (`Shortcut_Text`, display only), an arrow when it opens a submenu, or a rule between groups (`Separator: true`, which takes no events). `Submenu` is the `Name` of a Popup that opens to the right of the row (to the left when there is no room) when the pointer rests on the row for a quarter of a second, or at a click; one submenu is open at a time, up to three levels deep. Parts: `MenuItem::icon`, `::label`, `::shortcut`, `::arrow`, `::rule`.

<!-- BEGIN generated: module:MenuItem -->
A row of a menu: text, an icon, a key hint, a rule or a submenu.

| Param | Type | Default | What it does |
|---|---|---|---|
| `Text` | string | `""` | The words of the row. |
| `Icon` | icon | `""` | An icon name or a file path shown before the text. |
| `Shortcut_Text` | string | `""` | A key hint shown at the end of the row; display only. |
| `Separator` | boolean | `false` | Makes the row a rule between groups; it takes no events. |
| `Submenu` | string | `""` | The Name of the Popup that opens beside the row as its submenu; empty has none. |
| `Label` | string | `""` | The name assistive technology reads aloud; the text when it is empty. |
| `Id` | string | `""` | A text the row carries for the code that built the menu; shown nowhere. A submenu reads it as caller.use.params.Id. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

<!-- END generated: module:MenuItem -->

<!-- BEGIN generated: example-set:05-modules/menu -->
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
# A Button in the Bar opens the Popup File_Menu; the Menu is the Popup's content.
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
                        Padding: [12, 0, 12, 0]
                        Children {
                            Button {
                                Text: "File"
                                Icon: "mdi:menu-down"
                                Icon_Position: END
                                On_Click { Action: Toggle, Target: File_Menu }
                            }
                        }
                    }
                }
            }
            Popup {
                Name: File_Menu
                Gap: 4
                Style { Background: $color.surface_raised, Corner_Radius: 8, Elevation: 20% }
                Children {
                    Menu {
                        Label: "File"
                        Children {
                            MenuItem { Text: "New", Icon: "mdi:file-plus-outline", Shortcut_Text: "Ctrl+N" }
                            MenuItem { Text: "Open", Shortcut_Text: "Ctrl+O" }
                            MenuItem { Separator: true }
                            MenuItem { Text: "Share", Submenu: Share_Menu }
                            MenuItem { Text: "Print", Enabled: false }
                        }
                    }
                }
            }
            Popup {
                Name: Share_Menu
                Gap: 4
                Style { Background: $color.surface_raised, Corner_Radius: 8, Elevation: 20% }
                Children {
                    Menu {
                        Children {
                            MenuItem { Text: "Mail" }
                            MenuItem { Text: "Chat" }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/menu -->

## TextInput

A single-line text field. It is a field of the engine, so it follows the theme. Typing, the arrows, Home and End, Shift to select, Ctrl+A, Ctrl+C, Ctrl+X and Ctrl+V work as usual; Enter raises `On_Submit`; Tab leaves the field. Every edit raises `On_Changed` (`event.old`, `event.new`); a typed, pasted or input-method character raises `On_Text_Commit` (`event.text`) first. `On_Key_Down` reports a key before the field acts on it. `Text` is data in: setting it raises nothing. The field's accessible name is its `Label`, else its `Placeholder`: give it one. A Bar or Panel that holds a text field takes the keyboard on demand, so a click on the field gives it the keyboard.

<!-- BEGIN generated: module:TextInput -->
A single-line text field.

| Param | Type | Default | What it does |
|---|---|---|---|
| `Text` | string | `""` | The value, set from outside; edits come out through On_Changed. |
| `Placeholder` | string | `""` | The text shown while the field is empty. |
| `Label` | string | `""` | The name assistive technology reads aloud for the field; without one it is the Placeholder. |
| `Read_Only` | boolean | `false` | The text can be selected and copied but not changed. |
| `Max_Length` | number | `0` | The most characters the field takes; 0 is no limit. |
| `Password` | boolean | `false` | Shows dots instead of the text and blocks copy and cut. |
| `Enabled` | boolean | `true` | False disables the field. |
| `Width` | number | `240` | The width in pixels. |
| `Active_Descendant` | string | `""` | The Name of a List called in the same layout: a screen reader reads that List's chosen entry as the current item of the field while the keyboard stays in it. Empty: none. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Changed`, `On_Submit`, `On_Text_Commit`, `On_Key_Down`.

<!-- END generated: module:TextInput -->

<!-- BEGIN generated: example-set:05-modules/textinput -->
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
# A Bar that holds a text field takes the keyboard when the field is clicked.
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            TextInput { Placeholder: "Search", Width: 200 }
                            TextInput { Label: "Password", Placeholder: "Password", Password: true, Width: 160 }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/textinput -->

## TextEditor

A multi-line text field: it works like TextInput, but Enter adds a line and there is no `On_Submit`. `Wrap: WORD` wraps at the width, `NONE` keeps each line whole and scrolls sideways; `Lines` is the height in lines when you write no `Height`. Tab and Shift+Tab leave the field (the shell sets the engine's `tab_navigates`), so a tab character cannot be typed.

<!-- BEGIN generated: module:TextEditor -->
A multi-line text field.

| Param | Type | Default | What it does |
|---|---|---|---|
| `Text` | string | `""` | The value, set from outside; edits come out through On_Changed. |
| `Placeholder` | string | `""` | The text shown while the editor is empty. |
| `Label` | string | `""` | The name assistive technology reads aloud for the editor; without one it is the Placeholder. |
| `Read_Only` | boolean | `false` | The text can be selected and copied but not changed. |
| `Max_Length` | number | `0` | The most characters the editor takes; 0 is no limit. |
| `Wrap` | string | `"WORD"` | WORD wraps at the width by word; NONE does not wrap and scrolls sideways. |
| `Lines` | number | `4` | The height in lines, when the height is AUTO. |
| `Enabled` | boolean | `true` | False disables the editor. |
| `Width` | number | `320` | The width in pixels. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Changed`, `On_Submit`, `On_Text_Commit`, `On_Key_Down`.

<!-- END generated: module:TextEditor -->

<!-- BEGIN generated: example-set:05-modules/texteditor -->
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
# The Panel asks for the keyboard when it is clicked, so the editor can be typed into.
Shell {
    Monitor {
        Name: Main
        Index: default
        Children {
            Panel {
                Name: Notes
                Layer: TOP
                Anchor: [TOP, RIGHT]
                Inset: [0, 48, 24, 0]
                Width: 360
                Height: 160
                Keyboard: ON_DEMAND
                Style { Background: $color.surface, Corner_Radius: 8 }
                Children {
                    TextEditor {
                        Label: "Notes"
                        Placeholder: "Write a note"
                        Width: 340
                        Lines: 6
                        Margin: 10
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/texteditor -->

## TextBox

Several lines of text that wrap by word at the width, are not editable, and can be selected. Give it a `Width`, or put it in a column that has one. `Wrap: NONE` keeps each line as written and cuts it at the box; `Max_Lines` shows at most that many lines.

<!-- BEGIN generated: module:TextBox -->
Several lines of text that can wrap, be cut and be selected.

| Param | Type | Default | What it does |
|---|---|---|---|
| `Text` | string | `""` | The words. |
| `Wrap` | string | `"WORD"` | WORD wraps at word ends; NONE keeps the lines as written. |
| `Max_Lines` | number | `0` | Cuts the text after this many lines; 0 is no limit. |
| `Selectable` | boolean | `false` | Lets the user select the text. |

Events a use may handle: .

<!-- END generated: module:TextBox -->

<!-- BEGIN generated: example-set:05-modules/textbox -->
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            TextBox { Text: "TextBox wraps at word ends when it has a width and stops after Max_Lines lines, however long the text is.", Width: 220, Max_Lines: 2 }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/textbox -->

## Marquee_Text

A long text that scrolls in a small space. It scrolls only while the text is wider than its box (160 pixels unless you write a `Width`), at `Speed` pixels a second, waiting `Pause` milliseconds at each end; the engine does the moving, with no work in Python for each frame. `Loop: RESTART` jumps back to the start, `BOUNCE` scrolls back. When it is disabled, or with the desktop's reduced-motion setting, it does not scroll: a text that does not fit ends with an ellipsis and the tooltip shows the whole text. The whole text is its accessible name.

<!-- BEGIN generated: module:Marquee_Text -->
A line of text that scrolls when it is wider than its box.

| Param | Type | Default | What it does |
|---|---|---|---|
| `Text` | string | `""` | The words; they scroll when wider than the box. |
| `Speed` | number | `30` | How fast the text scrolls, in pixels a second. |
| `Pause` | number | `1500` | How long the text waits at each end, in milliseconds. |
| `Direction` | string | `"LEFT"` | The way the text moves: LEFT or RIGHT. |
| `Loop` | string | `"RESTART"` | RESTART jumps back to the start; BOUNCE scrolls back. |
| `tooltip` | boolean | `true` | False turns off the tooltip with the whole cut text: write it when the Marquee is inside a control that has its own tooltip. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`.

<!-- END generated: module:Marquee_Text -->

<!-- BEGIN generated: example-set:05-modules/marquee-text -->
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            Marquee_Text { Text: "A long title that does not fit in its box and so scrolls to the left", Width: 160, Speed: 40, Loop: BOUNCE }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/marquee-text -->

## Expander

Shows or hides its children with an animation. `Direction` is the edge the content grows from: `DOWN` (the default) and `UP` size its height, `LEFT` and `RIGHT` its width. A change of `Expanded` eases the size and the opacity of the content together over `Duration` milliseconds (`-1` takes the theme's medium duration; nothing eases with reduced motion), and an animation that is interrupted turns round from where it is. A use may write `On_Changed`, raised when an opening or closing has finished (`event.value` true when open). It has no keys of its own: Enter and Space on the [Button](#button) that controls it toggle it. In a shell file `Expanded` is a fixed value; a module of your own can drive it from a slot.

<!-- BEGIN generated: module:Expander -->
A block that shows or hides its content with an animation.

| Param | Type | Default | What it does |
|---|---|---|---|
| `Expanded` | boolean | `false` | Whether the content is shown; set from outside. |
| `Direction` | string | `"DOWN"` | The edge the content grows from: DOWN, UP, LEFT or RIGHT. |
| `Duration` | number | `-1` | The animation time in milliseconds; -1 takes the theme's. |
| `Content_Fade` | boolean | `true` | Whether the content's opacity follows the animation. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Changed`, `On_Key_Down`.

<!-- END generated: module:Expander -->

<!-- BEGIN generated: example-set:05-modules/expander -->
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
# An Expander shows its children while Expanded is true, with a slide and a fade.
Shell {
    Monitor {
        Name: Main
        Index: default
        Children {
            Panel {
                Name: Details
                Layer: TOP
                Anchor: [TOP, LEFT]
                Inset: [24, 48, 0, 0]
                Width: 260
                Height: 120
                Style { Background: $color.surface, Corner_Radius: 8 }
                Children {
                    FlexBox {
                        Flex: VERTICAL
                        Padding: 12
                        Spacing: 8
                        Children {
                            Label { Text: "Details" }
                            Expander {
                                Expanded: true
                                Direction: DOWN
                                Children {
                                    Label { Text: "These lines are the Expander's content." }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/expander -->

## Battery

The charge of the machine's battery: an icon, an optional number (`82 %`) and a tooltip with the state and the time left. It reads UPower's display device on the system bus, with no timer. At UPower's own low and critical warning levels the icon, a dot beside it and the number take the theme's warning and error colours, and the icon changes shape (colour is never the only sign). It hides itself when there is no battery or no UPower, so on a desktop machine both Batteries in the example are hidden.

<!-- BEGIN generated: module:Battery -->
The battery's charge as an icon and a number, with a tooltip; hides without one.

| Param | Type | Default | What it does |
|---|---|---|---|
| `show_percent` | boolean | `true` | Shows the charge as a number next to the icon. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

<!-- END generated: module:Battery -->

<!-- BEGIN generated: example-set:05-modules/battery -->
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
# Both are hidden on a machine with no battery.
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            Spacer { }
                            Battery { }
                            Battery { show_percent: false }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/battery -->

> The low and critical look was restructured after a problem seen on the maintainer's KWin, where the icon was not drawn; it has not been checked on KWin again yet.

## Workspaces

KWin's virtual desktops as a row of buttons. The current desktop's button is marked (the style state `:selected`, which the `Default` stylesheet colours with the theme's primary colour) and a click on another switches to it. `label: name` shows each desktop's name (its number when it has none), `label: number` shows 1, 2, 3. It follows KWin's own signals, with no timer, and hides itself when KWin is not on the session bus. **A click really switches your desktop.**

<!-- BEGIN generated: module:Workspaces -->
The virtual desktops as buttons: the current one is marked, a click switches.

| Param | Type | Default | What it does |
|---|---|---|---|
| `label` | string | `"name"` | name shows each desktop's name (its number when it has none); number shows 1, 2, 3. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

Actions a `Call` may run:

| Action | What it does |
|---|---|
| `Workspaces.switch()` | A click on a desktop's button: set KWin's `current` to its id. The call runs on the `dbus` thread; the mark moves when KWin's `PropertiesChanged` says so. |

<!-- END generated: module:Workspaces -->

<!-- BEGIN generated: example-set:05-modules/workspaces -->
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            Workspaces { }
                            Workspaces { label: number }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/workspaces -->

## Network

How the machine is connected, as NetworkManager reports it, read only, from the system bus. An icon for the kind of connection (Ethernet, Wi-Fi with four signal steps, mobile, Bluetooth, other) and its state, a second icon while a VPN is up, an optional connection name, and a tooltip such as `Home-WiFi, Wi-Fi 70 %, connected`. A connection with no internet or one that wants a sign-in takes the theme's warning colour; disconnected or networking off takes the muted colour, and the icon changes shape too. It stays visible when disconnected and hides only when NetworkManager is absent. It announces a change between connected and not connected.

<!-- BEGIN generated: module:Network -->
How the machine is connected, as NetworkManager reports it.

| Param | Type | Default | What it does |
|---|---|---|---|
| `show_name` | boolean | `false` | Shows the connection's name (or the Wi-Fi network's) next to the icon. |
| `show_vpn` | boolean | `true` | Shows a second icon while a VPN is up. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

<!-- END generated: module:Network -->

<!-- BEGIN generated: example-set:05-modules/network -->
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            Spacer { }
                            Network { show_name: true, show_vpn: true }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/network -->

## Media

What an MPRIS media player (a browser, Elisa, VLC, mpv and the like) plays: previous, play or pause and next as buttons, the title in a scrolling text, optionally the cover and a position slider, and a tooltip with the title, artist, player and state. One player is shown: the one that plays, else the one shown last, else the paused one that changed last; a browser's integration player counts once. With no player the module hides. **The buttons and the slider act on the real player**; the icon changes only when the player says so. The cover is shown only from a `file://` address; a web address is never fetched. `show_position` adds a slider and, while the player plays, a one-second tick.

<!-- BEGIN generated: module:Media -->
What a media player plays, with previous, play or pause and next buttons.

| Param | Type | Default | What it does |
|---|---|---|---|
| `show_art` | boolean | `false` | Shows the artwork, 24 px (a file:// URL of the player's; a placeholder icon otherwise). |
| `show_title` | boolean | `true` | Shows the title, scrolling when it is wider than max_width. |
| `show_controls` | boolean | `true` | Shows the previous, play or pause and next buttons. |
| `show_position` | boolean | `false` | Shows the seek slider; it turns on the one-second tick while the player plays. |
| `max_width` | number | `240` | The title's width in pixels. |
| `announce` | boolean | `false` | Says aloud, politely, a new track after one that was shown (off by default). |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

Actions a `Call` may run:

| Action | What it does |
|---|---|
| `Media.drag(position)` | The slider's handle moved by the user: nothing goes to the player until the release. |
| `Media.next()` |  |
| `Media.play_pause()` |  |
| `Media.previous()` |  |
| `Media.release(position)` | The press on the slider ended (`On_Released`, `position` is its final value): ask the player for that position and wait for its `Seeked` (the module moves nothing itself). A press that moved nothing (a touch on the handle) seeks nowhere. |
| `Media.seek(position)` | Ask the player to go to `position` seconds. |

<!-- END generated: module:Media -->

<!-- BEGIN generated: example-set:05-modules/media -->
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            Media { show_title: true, show_controls: true, show_position: false, max_width: 220 }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/media -->

## Audio

The default sound output, through the shell's own client of the PulseAudio protocol (`pipewire-pulse` or PulseAudio): an icon for the kind of output (speaker, headphones, HDMI, Bluetooth) and the level, in the muted colour and shape when muted, and a crossed microphone while the input is muted. A **click mutes**, the **wheel** changes the volume by `step` percent (up for a scroll up), and a **secondary click** opens a menu of outputs, the [Popup `Audio_Outputs`](#audio_outputs). The slider writes at most 20 times a second while you drag. Hidden when there is no sound server, back when it starts. Its actions are what the [volume shortcuts](keyboard.md#global-shortcuts) call.

<!-- BEGIN generated: module:Audio -->
The default sound output: an icon for its kind and level, mute on a click, the volume on the wheel, an optional percent and slider, and a menu of outputs.

| Param | Type | Default | What it does |
|---|---|---|---|
| `show_percent` | boolean | `false` | Shows the volume as a number next to the icon. |
| `show_slider` | boolean | `false` | Shows a volume slider. |
| `show_mic` | boolean | `true` | Shows a microphone mark while the default input is muted. |
| `step` | number | `5` | The percent one wheel step changes the volume by. |
| `announce` | boolean | `false` | Says aloud, politely, mute and unmute and a new volume once it has settled (off by default). |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

Actions a `Call` may run:

| Action | What it does |
|---|---|
| `Audio.drag(percent)` | The slider's handle moved by the user: write at most every 50 ms; the release writes the final value. |
| `Audio.key(step)` | A key on the focused mute button: Up and Down change the volume by one step, Menu or Shift+F10 opens the list of outputs (the keyboard twins of the wheel and the secondary click). |
| `Audio.set_output(id)` |  |
| `Audio.set_volume(percent)` | Set the volume (clamped to 0 to 100); a slider's release sends its final value here. |
| `Audio.show_outputs()` | Open the Popup `Audio_Outputs` with the outputs as they are now. |
| `Audio.step(delta)` | Change the volume by `delta` percent (the layout gives `step` times the way). |
| `Audio.toggle_mic()` |  |
| `Audio.toggle_mute()` |  |

<!-- END generated: module:Audio -->

<!-- BEGIN generated: example-set:05-modules/audio -->
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
# The secondary-click menu of outputs is the Popup Audio_Outputs, which the shell provides.
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            Spacer { }
                            Audio { show_percent: true, show_slider: false, step: 5 }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/audio -->

### Audio_Outputs

The content of the Popup that the Audio module's secondary click opens: one row for each output, with the icon of its kind and a dot on the default one; a click makes it the default and closes the menu. The shell provides the Popup `Audio_Outputs` (see [Popups](surfaces.md#popup)); write one of that name to change its look.

<!-- BEGIN generated: module:Audio_Outputs -->
The content of the Audio module's outputs Popup: one row per output.

This module has no params of its own.

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

Actions a `Call` may run:

| Action | What it does |
|---|---|
| `Audio_Outputs.pick(id)` |  |

<!-- END generated: module:Audio_Outputs -->

<!-- BEGIN generated: example-set:05-modules/audio-outputs -->
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
# The shell provides the Popup Audio_Outputs by itself. Write one of the same name on a Monitor
# to change how it looks: it replaces the shipped one whole.
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
                        Padding: [12, 0, 12, 0]
                        Children {
                            Spacer { }
                            Audio { }
                        }
                    }
                }
            }
            Popup {
                Name: Audio_Outputs
                Attach: BOTTOM
                Alignment: END
                Gap: 6
                Style { Background: $color.surface_raised, Corner_Radius: 12, Elevation: 30% }
                Children { Audio_Outputs { } }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/audio-outputs -->

## Volume_OSD

The volume on-screen display: when the default output's **volume or mute changes**, a small card appears for a moment with an icon, the output's name, a bar and the percent (or the word *Muted*), and goes away by itself. It reads the sound server itself, so it shows what changed the volume (a volume key, the Audio module's wheel, `pavucontrol`, another program) and needs no Audio module beside it. It shows **nothing at start**, for the first reading of the server, when the default output is switched (the new output's volume is the starting point) or when the microphone or the list of outputs changes. Muted is told by the word, by the icon's shape (a crossed speaker) and by the dimmed bar, never by colour alone.

The module goes in a **Panel** that you write: `Visible: false` (it starts hidden), `Input_Region: []` (clicks pass through it) and `Keyboard: NONE` (it never takes the keyboard), on `Layer: OVERLAY` so it shows over other windows. The module shows that Panel when something changes and hides it `duration` milliseconds after the last change (a change in that time starts the time again); this `duration` replaces the Panel's own `Hide_After`. The Panel gives the size, the place and the card (`Style`); the module fills it. A `Volume_OSD` in a Bar has no Panel to show: the shell says so once in its log. In a Panel that does not start hidden the card is on screen from the start until the first change and the time after it.

The module **says nothing aloud**, so a screen reader is not told twice: set `announce: true` on an [Audio](#audio) module if you want the changes spoken. To assistive technology the card is a group named for example "Volume, Razer Leviathan V2 X, 45 %" (or "..., muted") that holds one progress bar named "Volume"; the icon and the two texts are hidden from it because the name already says them. Brightness is not part of it: the shell has no brightness service.

<!-- BEGIN generated: module:Volume_OSD -->
The volume on-screen display: the output, a bar and the percent (or Muted) for a moment when the default output's volume or mute changes; it goes in a click-through Panel.

| Param | Type | Default | What it does |
|---|---|---|---|
| `duration` | number | `1500` | Milliseconds the Panel stays after the last change of the volume or mute (more than 0, at most 60000). |
| `show_name` | boolean | `true` | Shows the output's name above the bar. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

<!-- END generated: module:Volume_OSD -->

<!-- BEGIN generated: example-set:05-modules/volume-osd -->
File `settings.tdl`:

```tdl
---
TDL: 0.2
Name: Settings
---
# The volume keys change the volume through the Audio module in the Bar; the on-screen display
# shows for a moment each time the volume or the mute changes, whatever changed it.
Settings {
    Appearance { Stylesheets: [Default] }
    Shortcuts {
        Volume_Up { Keys: "AudioRaiseVolume", Action: Call, Target: "Audio.step", delta: 5 }
        Volume_Down { Keys: "AudioLowerVolume", Action: Call, Target: "Audio.step", delta: -5 }
        Mute { Keys: "AudioMute", Action: Call, Target: "Audio.toggle_mute" }
    }
}
```

File `Shells/Main_Shell.tdl`:

```tdl
---
TDL: 0.2
Name: Main_Shell
---
# Volume_OSD goes in a Panel that starts hidden (Visible: false), takes no pointer (Input_Region: [])
# and no keyboard (Keyboard: NONE) and sits on the overlay layer. The module shows the Panel when the
# volume or mute changes and the Panel hides itself after `duration` milliseconds.
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
                        Padding: [12, 0, 12, 0]
                        Children {
                            Spacer { }
                            Audio { }
                        }
                    }
                }
            }
            Panel {
                Name: Volume_Panel
                Layer: OVERLAY
                Keyboard: NONE
                Input_Region: []
                Visible: false
                Anchor: [BOTTOM]
                Inset: [0, 0, 0, 80]
                Width: 300
                Height: 64
                Style { Background: $color.surface_raised, Corner_Radius: 12, Elevation: 20% }
                Children {
                    Volume_OSD { duration: 1500, show_name: true }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/volume-osd -->

## Tray

The system tray: one icon for each application that registers a StatusNotifierItem, with its tooltip. A click calls the application's `Activate`, a middle click and the wheel are passed on, and a secondary click opens the application's own menu, drawn by the shell. The shell is a **second tray host** beside Plasma's: it never starts a watcher and does not touch Plasma's tray, so the same icons can show in both; hide one of them if that bothers you. Icons come from the desktop's icon theme (the Settings portal's `icon-theme`), the item's own folder, or its picture. The menus are the Popups `Tray_Menu`, `Tray_Menu_2` and `Tray_Menu_3`, which the shell provides (a menu shows three levels and scrolls at 60 % of the output's height); write one of the same name to replace it. The module hides when there is no watcher or no item. **A click calls the real application and a menu entry runs in it.**

<!-- BEGIN generated: module:Tray -->
The system tray: one icon per StatusNotifier application, with its tooltip, clicks and menu; the shell is a second tray host beside Plasma's.

| Param | Type | Default | What it does |
|---|---|---|---|
| `icon_size` | number | `18` | The size of each icon in pixels. |
| `show_passive` | boolean | `false` | Shows the items whose status is Passive. |
| `spacing` | number | `6` | The space between two items in pixels. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

Actions a `Call` may run:

| Action | What it does |
|---|---|
| `Tray.activate(id)` |  |
| `Tray.key(id)` | A key on a focused item: Menu, or Shift+F10, opens its menu (Keyboard Navigation). |
| `Tray.menu(id)` | The item's menu, drawn by the shell; `ContextMenu` when the item has none. |
| `Tray.scroll(id, delta?)` | One wheel step (`delta` +1 for a step down): `Scroll(delta, "vertical")` in Qt's units, up positive. |
| `Tray.secondary(id)` |  |

<!-- END generated: module:Tray -->

<!-- BEGIN generated: example-set:05-modules/tray -->
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            Spacer { }
                            Tray { icon_size: 18, spacing: 6 }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/tray -->

### Tray_Item

The Tray draws each icon with `Tray_Item`; you do not use it yourself.

<!-- BEGIN generated: module:Tray_Item -->
One icon of the Tray, with a tooltip.

| Param | Type | Default | What it does |
|---|---|---|---|
| `icon` | icon | `""` | The icon: an SVG document or pixels the shell holds (the Tray sends it). |
| `size` | number | `18` | The icon's size in pixels. |
| `tooltip_title` | string | `""` | The first line of the tooltip. |
| `tooltip_text` | string | `""` | The second line of the tooltip; empty shows none. |
| `label` | string | `""` | The name assistive technology reads aloud. |
| `description` | string | `""` | The description assistive technology reads after the name. |
| `attention` | boolean | `false` | The item needs attention: the block takes the :selected look. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

<!-- END generated: module:Tray_Item -->

### Tray_Menu

Each level of a tray item's menu is drawn with `Tray_Menu`, as the content of the Popups `Tray_Menu`, `Tray_Menu_2` and `Tray_Menu_3` that the shell provides; you use it only to replace one of them.

<!-- BEGIN generated: module:Tray_Menu -->
The content of the Popups that draw a tray item's menu, one level of it.

| Param | Type | Default | What it does |
|---|---|---|---|
| `Level` | number | `1` | 1 is the menu itself; 2 and 3 are the submenus of the row that opened the Popup. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

Actions a `Call` may run:

| Action | What it does |
|---|---|
| `Tray_Menu.pick(id, service, path, submenu?)` | A row was clicked: tell the application (`Event` with `clicked`); the menu closes. A row that opens a submenu (`submenu` is its Popup) is only opened by the click. |

<!-- END generated: module:Tray_Menu -->

## Tasks

The open windows as a row of buttons, one for each window with its application's icon and, with `show_title`, its title. A click on a window that is not active activates it (un-minimising it); a click on the active window minimises it; a middle click asks it to close; the wheel over the row activates the next or previous window. The list comes from the shell's own **KWin script** (KWin has no call that lists windows), so `Tasks` needs `KWin { Script: RUNTIME }` (the default) or `PERSISTENT`; with `OFF` it stays hidden, and it is hidden too with no KWin or no window. The active window takes the `:selected` look, a minimised one is dimmed, and one that wants attention shows a small mark in the warning colour.

<!-- BEGIN generated: module:Tasks -->
The open windows as a row of buttons, from the shell's KWin script; a click activates, minimises or closes a window.

| Param | Type | Default | What it does |
|---|---|---|---|
| `show_title` | boolean | `true` | Shows each window's title beside its icon. |
| `max_width` | number | `180` | The widest a button gets, in pixels. |
| `icon_size` | number | `18` | The size of each icon in pixels. |
| `monitor` | string | `"THIS"` | THIS shows the windows on the module's own monitor, ALL those on every monitor. |
| `desktop` | string | `"CURRENT"` | CURRENT shows the windows on the current virtual desktop (and those on all desktops), ALL those on every desktop. |
| `show_empty` | boolean | `false` | Keeps the module's space when there is no window. |
| `announce` | boolean | `false` | Says aloud, politely, a window of the row that opens, closes or wants attention, once for a change (off by default). |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

Actions a `Call` may run:

| Action | What it does |
|---|---|
| `Tasks.activate(id)` | A click on a button: the active window is minimised, any other is activated (un-minimising it). The row changes when KWin has acted and the script reports. |
| `Tasks.close(id)` | A middle click: ask the window to close. |
| `Tasks.cycle(delta?)` | The wheel over a row: activate the next (`delta` > 0, a step down) or the previous window of that row, wrapping round. |
| `Tasks.key(id)` | A key on a focused task: Delete closes its window (the middle click's keyboard twin). |

<!-- END generated: module:Tasks -->

<!-- BEGIN generated: example-set:05-modules/tasks -->
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
                        Spacing: 16
                        Padding: [12, 0, 12, 0]
                        Children {
                            Tasks { show_title: true, max_width: 180, monitor: THIS, desktop: CURRENT }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:05-modules/tasks -->

> **Not yet checked on KWin:** the KWin script that Tasks and fullscreen hiding depend on has been built and tested with fakes; loading it into a real KWin has not been confirmed by hand.

### Task_Item

The button of one window in the Tasks row.

<!-- BEGIN generated: module:Task_Item -->
One button of the Tasks row: an application's icon and a window's title.

| Param | Type | Default | What it does |
|---|---|---|---|
| `icon` | icon | `""` | The icon: an SVG document or pixels the shell holds (Tasks sends it). |
| `title` | string | `""` | The window's title, scrolled when it is longer than the button. |
| `label` | string | `""` | The name assistive technology reads aloud: the title and the application, with the state in words. |
| `show_title` | boolean | `true` | Shows the title beside the icon. |
| `max_width` | number | `180` | The button's width when it shows a title, in pixels. |
| `icon_size` | number | `18` | The icon's size in pixels. |
| `active` | boolean | `false` | The window is the active one: the block takes the :selected look. |
| `minimized` | boolean | `false` | The window is minimised: the button is drawn dimmed. |
| `attention` | boolean | `false` | The window wants attention: a small mark in the warning colour. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

<!-- END generated: module:Task_Item -->

## Applications

The launcher: a text field over a list of the installed applications that narrows as you type. Down and Up move the selection; Enter or a click starts it; Escape clears the field and then hides the Panel. It is meant to sit in a Panel: the shell ships a hidden Panel called `Launcher` that holds it, which one line of `settings.tdl` opens with a key. That is described in [Keyboard and shortcuts](keyboard.md#the-launcher).

<!-- BEGIN generated: module:Applications -->
The launcher: a text field over a list of the installed applications that narrows as you type; Down and Up move the selection, Enter or a click starts it, Escape clears the field and then hides the Panel. The shipped Panel Launcher holds it.

| Param | Type | Default | What it does |
|---|---|---|---|
| `max_results` | number | `8` | The most rows shown; Page Down and Page Up move by them. |
| `show_comment` | boolean | `true` | Shows the generic name, else the comment, under each name. |
| `icon_size` | number | `24` | The size of each application icon in pixels. |
| `placeholder` | string | `"Search applications"` | The hint the empty text field shows. |

Events a use may handle: `On_Click`, `On_Secondary_Click`, `On_Middle_Click`, `On_Scroll`, `On_Key_Down`.

Actions a `Call` may run:

| Action | What it does |
|---|---|
| `Applications.key()` | `On_Key_Down` of the field (it comes before the field acts, which it does whatever this does): the list's keys are moved from it, and Escape is the module's (clear, then hide). A key this module uses goes no further, so the Panel's own Escape does not also hide a Panel that was only cleared. |
| `Applications.launch(id)` | A click on a row: start that application. |
| `Applications.launch_selected()` | Enter in the field: start the selected row. |
| `Applications.search(text?)` | Typing in the field: the list narrows and the first row is selected. |

<!-- END generated: module:Applications -->

<!-- BEGIN generated: example-set:08-keyboard/launcher -->
File `settings.tdl`:

```tdl
---
TDL: 0.2
Name: Settings
---
# One line gives a launcher: the shell adds the Panel Launcher to the first monitor because this
# file names it and writes no Panel of that name.
Settings {
    Appearance { Stylesheets: [Default] }
    Shortcuts { Toggle_Launcher: "Meta+Space" }
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
                Height: 32
                Style { Background: $color.surface }
                Children {
                    FlexBox {
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Align_Items: CENTER
                        Padding: [12, 0, 12, 0]
                        Children {
                            Button { Icon: "mdi:magnify", Label: "Applications", On_Click { Action: Toggle, Target: Launcher } }
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

<!-- END generated: example-set:08-keyboard/launcher -->

## Your own modules and the process they run in

A module of your own is a `<Name>_Module.tdl` and a `<Name>_Module.py` in `Modules/<Name>/` of your configuration folder. Its Python is one class that extends `Module` (`from tess_shell import Module, action`), and it runs in **a process of its own**, started with the shell, one process per module file however many times the module is used. The modules on this page are the shell's own and run inside it.

What that means for you:

* A callback that hangs does not freeze the bars. A callback that runs for 2 seconds is named in the log; one that runs for 5 seconds gets the process killed and the module starts again after 1, 2, 4, 8 and 16 seconds (five tries; a save of the file gives it five new ones). `tesserae-shell status` lists each process with its state.
* `ctx` is the same: `ctx.send`, `ctx.uses`, `ctx.popup`, `ctx.dbus`, `ctx.audio`, `ctx.windows`, `ctx.apps`, `ctx.icons`, `ctx.tray`, `ctx.surface`, `ctx.focus`, `ctx.announce`, `ctx.on_tick`, `ctx.call_soon` and `ctx.log`. The services stay in the shell (the module has no connection of its own to open); a member whose contract says it answers at once on the loop (`ctx.is_popup_open`, `ctx.update_popup`, `ctx.apps.search`, `ctx.icons.theme_icon`, `ctx.surface.hide`, `ctx.focus.set_mode` ...) now waits for the shell for a moment, and raises `ShellCallTimeout`, naming the module and the call, if the shell does not answer within 2 seconds. "The loop" is the process's main thread: every callback of the module still runs one at a time.
* Everything that crosses to the shell is plain data (strings, numbers, booleans, lists, dictionaries with string keys; a tuple stays a tuple). A value you send in `start()` can appear a moment after the bar's first paint.
* `Event.stop()` has no effect (the shell's handler has returned before your action runs); one warning in the log says so. An `@action` that returns something returns it to `tesserae-shell call` when it has run.
* Write each action as a method marked `@action` in the class body of the file: the shell reads the file's text (it does not import it) to know which actions exist and what arguments they take, so a `Call` that names one can be checked before anything runs. An action added another way is found when the process imports the file and reported as `module-actions`.
* `ctx.log` lines come out of the shell's log under the module's name, at most 200 a second; `print` and the process's standard error go where the shell's go (the journal, under systemd).
* `tesserae-shell check` reads your module's Python without running it; `tesserae-shell check --import-modules` imports it in a throwaway process.
* A process costs about 20 MB. It is fault containment, **not a sandbox**: it runs as you. `Debug { User_Modules_In_Process: true }` in `settings.tdl` keeps your modules in the shell's own process ([Settings](settings.md)).

Next: [styling and themes](styling.md).
