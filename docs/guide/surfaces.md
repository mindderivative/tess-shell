# Surfaces

A **surface** is a window the shell draws on the screen. There are four kinds, and a `Monitor` block says which monitors they are on.

| Surface | What it is | Typical use |
|---|---|---|
| [Bar](#bar) | A strip along a screen edge that reserves its space. | The top or bottom bar. |
| [Panel](#panel) | A surface placed by anchors, or against another surface; it can start hidden and be shown and hidden. | A launcher, a notes drawer, an on-screen display, a dock. |
| [Popup](#popup) and [tooltip](#tooltip) | A surface that opens beside a block of another surface. | A menu, a tooltip. |
| [Frame](#frame) | A ring around the whole screen, with strips along its sides and Panels grown out of it. | A screen border that holds a clock, a dock and widgets. |

Every key below is listed with what it accepts. A key marked *required* must be written. The tables come from the shell's schema, so they list exactly the keys the loader accepts and say which are **not built yet**: writing one of those is reported by `check`.

## How values are written

<!-- BEGIN generated: kinds -->
| Value | How it is written |
|---|---|
| text | Text, in double quotes (a single word may be written without). |
| text or number | A number or text. |
| name | Letters, digits and `_`, starting with a letter. |
| name of a surface | The `Name` of another block or surface of the shell, written exactly. |
| true or false | `true` or `false`, in lower case. |
| true or false | `true` or `false`; `false` disables the block (the key is `Enabled`, not `Disabled`). |
| number | A number. |
| whole number | A whole number. |
| percentage | A percentage such as `20%`, within the range the key allows. |
| length | Pixels (a whole number), a percentage such as `50%`, or `AUTO` (fit the content); `EXPAND` (take the free space) only where a table allows it. |
| sides | One number for all four sides, a list of four `[left, top, right, bottom]`, or a block of named sides (`Left`, `Top`, `Right`, `Bottom`; a side not named is 0). |
| radius | One number for all corners, or a list of four corners clockwise from the top left. |
| colour | A quoted colour in one of these forms: `"#RRGGBB"`, `"#RRGGBBAA"`, `"#RGB"`, `"#RGBA"`, `rgba(r g b a)`, or `rgba(r g b a)` with alpha from 0.0 to 1.0. Where a table lists theme tokens, a token such as `$color.surface` also works ([Styling and themes](styling.md#tokens)). |
| word | One upper-case word of the choices the table lists. |
| list | A list written `[a, b]`. Where a table says one value is also accepted, a single item may be written without brackets. |
| font | A font family name, or a list of names in the order of fallback. |
| milliseconds | A time in milliseconds. |
| path | A file or folder path. In a shell file a relative path is relative to that file; in `settings.tdl` a path starts with `/` or `~`. |
| icon | An icon name such as `mdi:account`; the prefix selects an icon set. |
| shadows | A block of `Shadow` blocks, the first on top, or `$elevation.max`. |
| `[]` or `AUTO` | `[]` (nothing takes the pointer) or `AUTO` (only the drawn shapes do). |
| tooltip | A Popup's `Name`, a short quoted text, or an inline `Tooltip` block. |
| number or `default` | A whole number from 0, or the word `default`. |
| key | A key press: modifiers and one key joined by `+`, such as `"Ctrl+Shift+F1"` ([Keyboard and shortcuts](keyboard.md#key-names)). |
| token | `$group.name`, a theme token ([Styling and themes](styling.md#tokens)). |
| slot | `<\| ... \|>`, an expression that a module's layout uses to show a value. |

<!-- END generated: kinds -->

A word key lists its choices in the table (`TOP` `BOTTOM` ...). `Name` is a letter followed by letters, digits and `_`; every surface has a unique one, and it is what `Show`, `Hide`, `Toggle`, `Attach_To` and the commands refer to.

## Monitor

A `Monitor` block holds the surfaces of one monitor, chosen by a selector.

<!-- BEGIN generated: surface:Monitor -->
One monitor, chosen by Connector, Description or Index, and the surfaces on it.

| Key | Value | Default | Required | What it does |
|---|---|---|---|---|
| `Name` | name | none | yes | The unique name of this block in the shell: letters, digits and _, starting with a letter. Actions and Attach_To refer to it. |
| `Index` | number or `default` | none |  | The position of the monitor (0, 1, ...) or default for the ones nothing else names. |
| `Connector` | text | none |  | The connector of the monitor, such as DP-1. |
| `Description` | text | none |  | The description of the monitor, as the compositor reports it. |

Inside it: `Bar`, `Panel`, `Popup`, `Frame`.

<!-- END generated: surface:Monitor -->

* `Index: 0` is the first monitor in the compositor's list, `1` the second. `Index: default` applies to every monitor that no other `Monitor` block names. `Index` is not stable: the order can change after unplugging, sleeping or rebooting, so prefer `Connector` (`DP-1`, `eDP-1`) or `Description` for a particular screen.
* With several selectors in one block, the shell tries `Connector`, then `Description`, then `Index`.
* A `Monitor` with no selector is ignored. If two blocks name the same monitor, the first wins and the shell logs a warning (`Monitor X names DP-1, which Monitor Y already took; Y wins and X opens nothing`).
* To see the names the shell gives your monitors, run `tesserae-shell status` while it runs: its `monitors:` line lists each `Monitor` block's name and the output it got, such as `Laptop (eDP-1)`.
* Plugging a monitor in opens the surfaces of the `Monitor` blocks that match it; unplugging closes only its surfaces; a change of size or scale updates the surfaces on that monitor in place. Other monitors' windows are not recreated.

<!-- BEGIN generated: example-set:04-surfaces/monitors -->
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
# The laptop's own screen gets a slim Bar, picked by its connector name; every other monitor gets
# a taller one with the time. Index: default is "every monitor no other block names".
Shell {
    Monitor {
        Name: Laptop
        Connector: "eDP-1"
        Children {
            Bar {
                Name: Laptop_Bar
                Edge: TOP
                Width: EXPAND
                Height: 28
                Style { Background: $color.surface }
            }
        }
    }
    Monitor {
        Name: Others
        Index: default
        Children {
            Bar {
                Name: Big_Bar
                Edge: TOP
                Width: EXPAND
                Height: 40
                Style { Background: $color.surface }
                Children {
                    FlexBox {
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Align_Items: CENTER
                        Padding: [12, 0, 12, 0]
                        Children {
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

<!-- END generated: example-set:04-surfaces/monitors -->

### A shell in several files

A shell file can import another, so a large shell is not one long file. The file that imports is the one `Main_Shell` names, or any other with `Monitor` blocks. The imported file holds surface blocks and no `Monitor`; it is a `_Shell.tdl` with `Shell { }` as its root, and its surfaces come in on the `Monitor` that writes the `Import:`.

* **Where.** `Import: Parts/Dock_Shell.tdl` (one file, or a list `Import: [A_Shell.tdl, B_Shell.tdl]`) goes among the `Children` of a `Monitor`. The path is relative to the file that writes it and must end inside your configuration folder (or a folder of `Directories`) after `..` and symbolic links are resolved; anything else is `path-outside-config`. The file may lie in `Shells/`, in a folder below it, or anywhere else in the folder.
* **Order.** The surfaces of the imported file come in at the place of the `Import:`, in the order they are written, as if they were written there. A `Panel` of one file may `Attach_To` a `Bar` of the other: the names are those of one `Monitor`.
* **Names.** A `Name` is unique across the whole shell, files included. A name used in both files is `name-duplicate`, reported in the file that uses it second, with the position of the first. For the same reason a file is imported once into a shell; a second `Import:` of it (under another `Monitor`, or through another imported file) is `import-twice`, with the position of the first.
* **Nesting.** An imported file may import further files, written the same way, in its own root: `Shell { Bar { ... } Import: More_Shell.tdl }`. A circle (`A` imports `B` imports `A`, or a file importing itself) is `import-cycle`, and the message prints the chain of files.
* **Errors.** A mistake in an imported file is reported at that file's own path, line and column, and the `Import:` that brought it in is reported as `import-failed`. A file that does not exist is `import-not-found`, with the path that was looked at. A `Monitor` block in an imported file is `import-monitor`. A file with only surfaces cannot be `Main_Shell` (`main-shell-surfaces`: it would show nothing). A shell file named in a surface's `Children`, or a module file named in a `Monitor`'s, is `import-misplaced`.
* **Reload.** Saving an imported file reloads the shell, wherever in the configuration folder it is (the shell watches each file it imports). A file with no `Import:` that names it, in `Shells/`, is checked by itself and not shown.
* **UIDs.** Each imported file gets a `UID:` line in its metadata, like every shell file ([The configuration folder](configuration-folder.md#identifiers-and-backups)).

<!-- BEGIN generated: example-set:04-surfaces/split -->
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
# One Monitor. The top Bar is written here; the dock at the bottom is in its own file, and the
# Import brings its surfaces in at that position, on this Monitor.
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
                            Clock { }
                        }
                    }
                }
            }
            Import: Parts/Dock_Shell.tdl
        }
    }
}
```

File `Shells/Parts/Dock_Shell.tdl`:

```tdl
---
TDL: 0.2
Name: Dock_Shell
---
# A file to import: surface blocks and no Monitor. It could import more files; a path is relative
# to the file that writes it. Its names (Dock) are unique across the whole shell.
Shell {
    Bar {
        Name: Dock
        Edge: BOTTOM
        Width: 480
        Height: 40
        Gap: 8
        Style { Background: $color.surface }
        Children {
            FlexBox {
                Width: EXPAND
                Flex: HORIZONTAL
                Align_Items: CENTER
                Padding: [12, 0, 12, 0]
                Children { Text { Text: "A dock, from its own file" } }
            }
        }
    }
}
```

<!-- END generated: example-set:04-surfaces/split -->

## Bar

A Bar is along one edge, as wide as the edge (`Width: EXPAND`) or shorter, and it keeps its space free: windows do not cover it. It is drawn in the layer you choose.

<!-- BEGIN generated: surface:Bar -->
A strip along a screen edge that reserves its space.

| Key | Value | Default | Required | What it does |
|---|---|---|---|---|
| `Name` | name | none | yes | The unique name of the Bar; required. |
| `Edge` | `TOP` `BOTTOM` `LEFT` `RIGHT` | none | yes | The screen edge the Bar attaches to. |
| `Width` | length | none | yes | The Bar's width: pixels, a percentage, AUTO or EXPAND (edge to edge along the Edge). |
| `Height` | length | none | yes | The Bar's height: pixels, a percentage, AUTO or EXPAND (edge to edge along the Edge). |
| `Layer` | `BOTTOM` `TOP` `OVERLAY` | `TOP` |  | The layer the Bar is drawn in: BOTTOM, TOP or OVERLAY. |
| `Alignment` | `START` `CENTER` `END` | none |  | Where a Bar shorter than the edge sits along it: START, CENTER or END; no effect on an EXPAND axis. |
| `Offset` | number | none |  | Moves the Bar along its edge, in pixels, forward or back. |
| `Gap` | number | `0` |  | The space between the screen edge and the Bar, in pixels; the reserved space includes it. |
| `Reserve` | true or false | `true` |  | Whether the Bar keeps its space free of windows (its size across the edge plus the Gap). |
| `Min_Width` | length | none |  | The least width of the Bar, in pixels. |
| `Min_Height` | length | none |  | The least height of the Bar, in pixels. |
| `Max_Width` | length | none |  | The greatest width of the Bar, in pixels. |
| `Max_Height` | length | none |  | The greatest height of the Bar, in pixels. |
| `Keyboard` | `NONE` `ON_DEMAND` | `NONE` |  | Whether the Bar takes the keyboard: NONE never (Tab does nothing in it), ON_DEMAND on a click. |
| `Tab_Index` | whole number | none |  | The place of a block, or of a surface, in the order Tab (and Shift+Tab) follows: a whole number from 0 to 2147483647. Ascending; equal numbers keep document order; items with no number come after all the others. A surface holds one order for its blocks and the shell holds one for its surfaces. |
| `Shortcut_Mode` | true or false | `false` |  | Whether this surface is the one in shortcut mode: the shell's keyboard mode, entered with Enter_Shortcut_Mode, in which the shortcut keys act on the surfaces (Next_Focus, Previous_Focus, Set_Shortcut_Mode, Exit_Shortcut_Mode). At most one surface is true at a time: setting one true sets every other false, and writing it false on the one that is true leaves the mode. Written true on a surface it makes the shell start in the mode on that surface; two surfaces written true are a warning and the first keeps it. |

Not built yet (the loader says so if you write them): `Exclusive_Zone`, `Input_Region`, `Auto_Hide`, `Auto_Hide_Delay`, `Visible`, `Attach_To`, `Meld`, `Animation`, `Text_Rotation`, `Padding`, `Class`.

A `Style { }` block of a Bar takes: `Background`, `Fill`, `Opacity`, `Elevation`, `Shadows`, `Shadow_Bleed`.

Inside it: any block (see the table of blocks on page 3).

<!-- END generated: surface:Bar -->

* **Size and place.** For a top or bottom Bar `Width` runs along the edge and `Height` is the thickness; for a left or right Bar it is the other way round. `EXPAND` runs edge to edge. A Bar shorter than its edge sits at `Alignment` (`START`, `CENTER`, `END`) and `Offset` moves it along the edge.
* **Floating.** `Gap: 8` leaves 8 pixels between the screen edge and the Bar, and the reserved space includes the gap. `Elevation: 20%` or a `Shadows { Shadow { ... } }` block draws a shadow in a transparent margin of the surface; the reserved space does not change.
* **Space.** `Reserve: true` (the default) keeps windows out of the Bar's space; `Reserve: false` lets them go under it.
* **Keyboard.** A Bar takes no keyboard (`NONE`) unless you write `ON_DEMAND`. A Bar that holds a text field takes it on demand whatever it says, and the shell logs a warning if you wrote `NONE` ([troubleshooting](troubleshooting.md)).
* A Bar cannot be hidden by a command or a shortcut; `Visible` and `Auto_Hide` are not built.
* Text in a left or right Bar is not rotated (`Text_Rotation` is not built).

An example with a bar across the top and a short floating one at the bottom:

<!-- BEGIN generated: example-set:04-surfaces/bars -->
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
# A bar across the top that keeps its space free, and a short floating bar in the middle of the
# bottom edge that lies above the windows' space by Gap pixels.
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
                            Workspaces { }
                            Spacer { }
                            Clock { }
                        }
                    }
                }
            }
            Bar {
                Name: Dock_Bar
                Edge: BOTTOM
                Width: 360
                Height: 44
                Alignment: CENTER
                Gap: 8
                Style { Background: $color.surface_raised, Elevation: 20% }
                Children {
                    FlexBox {
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Align_Items: CENTER
                        Justify_Content: CENTER
                        Spacing: 12
                        Children {
                            Icon { Icon: "mdi:firefox", Size: 28, Label: "Browser" }
                            Icon { Icon: "mdi:folder", Size: 28, Label: "Files" }
                            Icon { Icon: "mdi:console", Size: 28, Label: "Terminal" }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:04-surfaces/bars -->

## Panel

A Panel is a surface you place with anchors or against another surface. It can start hidden, be shown and hidden by actions, commands and keys, animate, take the keyboard and be moved by the pointer.

<!-- BEGIN generated: surface:Panel -->
A surface placed by anchors or against a target; a launcher, an OSD, a dock. Width and Height size it, or Depth and Length with Meld: true.

| Key | Value | Default | Required | What it does |
|---|---|---|---|---|
| `Name` | name | none | yes | The unique name of the Panel; Show, Hide, Toggle and Attach_To use it. |
| `Layer` | `BOTTOM` `TOP` `OVERLAY` | `TOP` |  | The layer the Panel is drawn in: BOTTOM, TOP or OVERLAY. |
| `Anchor` | list of `TOP` `BOTTOM` `LEFT` `RIGHT` | none |  | The screen edges the Panel is anchored to: one or a list; none is a floating Panel centred by the compositor. |
| `Inset` | sides | `0` |  | The distance from the anchored edges: one number, four (left, top, right, bottom) or named sides. |
| `Width` | length | none | one of | The Panel's width in pixels or a percentage; AUTO and EXPAND are not built. 0 stretches between two opposite anchors. |
| `Height` | length | none | one of | The Panel's height in pixels or a percentage; AUTO and EXPAND are not built. 0 stretches between two opposite anchors. |
| `Keyboard` | `NONE` `ON_DEMAND` `EXCLUSIVE` | `NONE` |  | Whether the Panel takes the keyboard: NONE never, ON_DEMAND on a click, EXCLUSIVE all keys. |
| `Input_Region` | `AUTO` | none |  | Which part of the Panel takes the pointer: [] none, AUTO the drawn shapes; leaving it out is the whole Panel. |
| `Visible` | true or false | `true` |  | Starts the Panel shown (true) or hidden (false). |
| `Hide_After` | number | none |  | Hides the Panel after this many milliseconds; showing it again restarts the time. |
| `Attach` | `LEFT` `RIGHT` `TOP` `BOTTOM` | none |  | The edge of the target the Panel meets (needs Attach_To). |
| `Gap` | number | `0` |  | The space between the Panel and its target, in pixels (with Attach_To). |
| `Alignment` | `START` `CENTER` `END` | `CENTER` |  | How the Panel lines up along the edge it shares with its target: START, CENTER or END (with Attach_To). |
| `Movable` | true or false | `false` |  | Lets the pointer move the Panel; its position is saved. |
| `Meld` | true or false | `false` |  | True draws the Panel inside the Frame it is attached to; needs Attach_To a Frame. |
| `Content_Fade` | true or false | `true` |  | Whether the content's opacity follows the slide of the Panel. |
| `Depth` | length | none | one of | The extent of a Panel with Meld: true away from the Frame's edge. |
| `Length` | length | none | one of | The extent of a Panel with Meld: true along the Frame's edge. |
| `Shortcut` | key | none |  | The global key that toggles the Panel or Frame, written as Meta+Space; the same as Toggle_&lt;Name> in Shortcuts. The Shortcuts entry wins when both are written. |
| `Tab_Index` | whole number | none |  | The place of a block, or of a surface, in the order Tab (and Shift+Tab) follows: a whole number from 0 to 2147483647. Ascending; equal numbers keep document order; items with no number come after all the others. A surface holds one order for its blocks and the shell holds one for its surfaces. |
| `Shortcut_Mode` | true or false | `false` |  | Whether this surface is the one in shortcut mode: the shell's keyboard mode, entered with Enter_Shortcut_Mode, in which the shortcut keys act on the surfaces (Next_Focus, Previous_Focus, Set_Shortcut_Mode, Exit_Shortcut_Mode). At most one surface is true at a time: setting one true sets every other false, and writing it false on the one that is true leaves the mode. Written true on a surface it makes the shell start in the mode on that surface; two surfaces written true are a warning and the first keeps it. |
| `Attach_To` | name of a surface | none |  | The Name of the Bar, Panel or Frame this Panel is placed against. |
| `Animation` | block | none |  | How the Panel comes and goes: an Animation block with Type and Duration. |
| `Peek` | block | none |  | Makes a melded Panel rest as a tab of Size pixels that comes out when asked. |

Not built yet (the loader says so if you write them): `Open_With_Target`, `Exclusive_Zone`, `Margin`, `Padding`, `Class`.

A `Style { }` block of a Panel takes: `Background`, `Fill`, `Opacity`, `Elevation`, `Shadows`, `Shadow_Bleed`, `Corner_Radius`, `Border_Width`, `Border_Color`.

Events it raises: `On_Open`, `On_Close`, `On_Visible`, `On_Hidden`, `On_Toggle`, `On_Anim_Start`, `On_Anim_End`.

Inside it: any block (see the table of blocks on page 3).

<!-- END generated: surface:Panel -->

* **Anchors.** `Anchor: [TOP, LEFT]` anchors the Panel to those edges and `Inset: [left, top, right, bottom]` is the distance from them. A `Width` or `Height` of `0` stretches the Panel between two opposite anchors. With no `Anchor` the Panel floats, centred by the compositor.
* **Against a target.** `Attach_To: Top_Bar` places the Panel against a Bar, another Panel, or a module used in a Bar (give the use a `Name`, `Clock { Name: Clock_One }`); `Attach` is the edge of the target it meets, `Gap` the space between, `Alignment` how it lines up along that edge. A Panel whose target is hidden stays hidden.
* **Start and stop.** `Visible: false` starts it hidden. `Hide_After: 1500` hides it 1.5 seconds after it is shown (showing it again restarts the time): an on-screen display.
* **Pointer.** `Input_Region: []` makes the whole Panel click-through; `AUTO` takes only the drawn shapes; leaving the key out is the whole Panel. `Movable: true` lets the pointer move it, and the shell remembers where (in `registry.json`, as `<Monitor>@<output>`).
* **Keyboard.** `NONE` (the default), `ON_DEMAND` (after a click) or `EXCLUSIVE` (it takes every key while shown). **Escape** hides a Panel that takes the keyboard.
* **Layer.** `BOTTOM`, `TOP` or `OVERLAY`, the layer-shell layers.
* **Animation.** `Animation { Type: SLIDE, Duration: 200 }` slides or fades it in and out (`NONE` is instant). With the desktop's reduced-motion setting it is instant.
* **Events.** `On_Open`, `On_Close`, `On_Visible`, `On_Hidden`, `On_Toggle`, `On_Anim_Start` and `On_Anim_End` run shell actions around it (`On_Open { Action: Hide, Target: Other_Panel }`).
* **Frame.** `Meld: true` with `Attach_To: <a Frame>` grows the Panel out of the Frame; see [Frame](#frame).
* A Panel can be hidden in two ways, set in `settings.tdl` under `Debug { Panel_Hide }`: `KEEP` (the default) leaves its window mapped and draws nothing, so it keeps its state; `CLOSE` destroys the window and makes a new one when it is shown.

<!-- BEGIN generated: surface:Animation -->
How a Panel comes and goes.

| Key | Value | Default | Required | What it does |
|---|---|---|---|---|
| `Type` | `SLIDE` `FADE` `NONE` | `SLIDE` |  | How the Panel comes and goes: SLIDE, FADE or NONE. |
| `Duration` | milliseconds | `200` |  | How long it takes, in milliseconds; 0 is no animation. |

<!-- END generated: surface:Animation -->

A Panel and its button. The Bar's button shows and hides `Notes`; `Volume_OSD` is an on-screen display that a command or shortcut shows and that hides itself:

<!-- BEGIN generated: example-set:04-surfaces/panels -->
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
# A button in the Bar shows and hides the Panel Notes; Volume_OSD is a small overlay that hides
# itself 1.5 seconds after it is shown (a command or a shortcut shows it).
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
                                Text: "Notes"
                                On_Click { Action: Toggle, Target: Notes }
                            }
                        }
                    }
                }
            }
            Panel {
                Name: Notes
                Layer: TOP
                Anchor: [TOP, LEFT]
                Inset: [12, 44, 0, 0]
                Width: 280
                Height: 160
                Visible: false
                Animation { Type: SLIDE, Duration: 200 }
                Style { Background: $color.surface_raised, Corner_Radius: 8, Elevation: 30% }
                Children {
                    FlexBox {
                        Flex: VERTICAL
                        Padding: 12
                        Spacing: 8
                        Children {
                            Label { Text: "Notes" }
                            Button { Text: "Close", On_Click { Action: Hide, Target: Notes } }
                        }
                    }
                }
            }
            Panel {
                Name: Volume_OSD
                Layer: OVERLAY
                Anchor: [BOTTOM]
                Inset: [0, 0, 0, 80]
                Width: 260
                Height: 60
                Visible: false
                Input_Region: []
                Hide_After: 1500
                Style { Background: $color.surface_raised, Corner_Radius: 12 }
                Children {
                    FlexBox {
                        Flex: HORIZONTAL
                        Align_Items: CENTER
                        Padding: 16
                        Spacing: 12
                        Children {
                            Icon { Icon: "mdi:volume-high", Size: 24 }
                            ProgressBar { Value: 70, Width: 180, Label: "Volume" }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:04-surfaces/panels -->

On a monitor you would see a thin Bar across the top with a `Notes` button; pressing it slides a rounded, raised card in under the Bar at the left, and `Close` slides it away. `Volume_OSD` starts hidden: `tesserae-shell show Volume_OSD` shows a small rounded card with a speaker icon and a bar near the bottom of the screen, which hides itself after 1.5 seconds. Because of `Input_Region: []` clicks pass through it.

An attached Panel:

<!-- BEGIN generated: example-set:04-surfaces/attached-panel -->
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
# A Panel placed against another surface: it sits under Top_Bar, 8 pixels away, at its right end.
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
                            Button { Text: "Menu", On_Click { Action: Toggle, Target: Drawer } }
                            Spacer { }
                            Clock { }
                        }
                    }
                }
            }
            Panel {
                Name: Drawer
                Layer: TOP
                Attach_To: Top_Bar
                Attach: BOTTOM
                Gap: 8
                Alignment: START
                Width: 240
                Height: 120
                Visible: false
                Style { Background: $color.surface_raised, Corner_Radius: 8 }
                Children { Label { Text: "Attached to the Bar", Margin: 12 } }
            }
        }
    }
}
```

<!-- END generated: example-set:04-surfaces/attached-panel -->

## Popup

A Popup opens beside a block of another surface, and closes when you click outside it or press Escape. It is what a menu is made of. A button opens it with `On_Click { Action: Show, Target: Info }`, or `Toggle` to open and close. Inside the Popup, a block with `On_Click { Action: Close }` closes it.

<!-- BEGIN generated: surface:Popup -->
A surface that opens from a block: a menu or a tooltip.

| Key | Value | Default | Required | What it does |
|---|---|---|---|---|
| `Name` | name | none | yes | The unique name of the Popup; Show, Toggle and Tooltip use it. |
| `Attach` | `LEFT` `RIGHT` `TOP` `BOTTOM` | `BOTTOM` |  | The edge of the block it opens from that the Popup meets. |
| `Alignment` | `START` `CENTER` `END` | `START` |  | How the Popup lines up along the edge it shares with the block: START, CENTER or END. |
| `Gap` | number | `0` |  | The space between the block and the Popup, in pixels. |
| `Adjust` | list of `FLIP_X` `FLIP_Y` `SLIDE_X` `SLIDE_Y` `RESIZE_X` `RESIZE_Y` | `[FLIP_Y, SLIDE_X]` |  | What the compositor may do to keep the popup on screen: one or a list of FLIP_X, FLIP_Y, SLIDE_X, SLIDE_Y, RESIZE_X, RESIZE_Y; [] asks for nothing. |
| `Width` | length | none |  | The Popup's width in pixels or AUTO. |
| `Height` | length | none |  | The Popup's height in pixels or AUTO. |
| `Max_Width` | length | `300` |  | The greatest width of the Popup, in pixels. |
| `Max_Height` | length | `400` |  | The greatest height of the Popup, in pixels, or a percentage (above 0, at most 100) of the output's height; a taller content scrolls. |
| `Focus` | true or false | `true` |  | Takes the keyboard and the pointer while open. |
| `Tooltip` | true or false | `false` |  | Makes the Popup a tooltip: it takes no focus, opens when the pointer enters the block and closes when it leaves. |
| `Open_On_Enter` | true or false | `false` |  | Opens when the pointer enters the block it is the tooltip of. |
| `Enter_Delay` | number | `500` |  | How long the pointer rests before it opens, in milliseconds. |
| `Close_On_Exit` | true or false | `false` |  | Closes when the pointer leaves. |
| `Exit_Delay` | number | `200` |  | How long the pointer is away before it closes, in milliseconds. |

Not built yet (the loader says so if you write them): `Attach_To`, `Animation`.

A `Style { }` block of a Popup takes: `Background`, `Fill`, `Opacity`, `Elevation`, `Shadows`, `Shadow_Bleed`, `Corner_Radius`, `Border_Width`, `Border_Color`.

Inside it: any block (see the table of blocks on page 3).

<!-- END generated: surface:Popup -->

* **Place.** `Attach` is the edge of the block that the Popup meets (default `BOTTOM`: under it), `Alignment` how it lines up along that edge, `Gap` the space between. The compositor may move the Popup to keep it on screen, as `Adjust` allows (by default `FLIP_Y` and `SLIDE_X`: it flips above the block instead of running off the bottom). A Popup under a bottom Bar therefore opens upward.
* **Size.** The Popup is as large as its content, up to `Max_Width` (default 300) and `Max_Height` (default 400, or a percentage of the output's height); content taller than that scrolls.
* **Data.** `On_Click { Action: Show, Target: File_Menu, Data { Id: 7 } }` hands values to the Popup, which reads them as `<| caller.data.Id |>` in a module's layout. This is how the Menu in [Modules](modules.md#menu) knows what it was opened for.
* A command never opens a Popup (it needs the pointer or key press that opened it): `tesserae-shell show Info` says `Info is a Popup: no command opens a Popup ...` and exits 1.
* **Menus.** The [Menu and MenuItem](modules.md#menu) modules are the content of a Popup, with submenus (up to three levels), a keyboard way in and a separator.

<!-- BEGIN generated: example-set:04-surfaces/popups -->
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
# A Button opens the Popup Info under itself; the Popup's own button closes it again. A click
# outside the Popup or Escape closes it too.
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
                            Button { Text: "Info", On_Click { Action: Show, Target: Info } }
                        }
                    }
                }
            }
            Popup {
                Name: Info
                Attach: BOTTOM
                Alignment: START
                Gap: 4
                Max_Width: 260
                Style { Background: $color.surface_raised, Corner_Radius: 8, Elevation: 20% }
                Children {
                    FlexBox {
                        Flex: VERTICAL
                        Padding: 12
                        Spacing: 8
                        Children {
                            TextBox { Text: "A Popup opens beside the block that opened it.", Width: 220 }
                            Button { Text: "Close", On_Click { Action: Close } }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:04-surfaces/popups -->

The shell also adds some Popups itself when a module needs them (the Tray's menus and the Audio output list). You can write one of the same name on a Monitor to replace it whole:

<!-- BEGIN generated: shipped-popups -->
Added to every Monitor with a Bar, Panel or Frame that shows the module in shown_by, on each output it opens on, unless that Monitor writes a Popup of the same name (which replaces it whole).

| Popup | Used by | Holds | Max height | What it is |
|---|---|---|---|---|
| `Tray_Menu` | Tray | Tray_Menu | 60 % | The menu of a tray item: its entries, below the clicked icon. |
| `Tray_Menu_2` | Tray | Tray_Menu | 60 % | The submenu of a row of Tray_Menu. |
| `Tray_Menu_3` | Tray | Tray_Menu | 60 % | The submenu of a row of Tray_Menu_2. |
| `Audio_Outputs` | Audio | Audio_Outputs | 400 px | The list of sound outputs the Audio module's secondary click opens. |

<!-- END generated: shipped-popups -->

## Tooltip

A tooltip is a Popup that takes no focus: it opens when the pointer has rested on a block for `Enter_Delay` milliseconds (default 500) and closes when the pointer leaves, `Exit_Delay` (default 200) later. There are three ways to write one, all in this example:

<!-- BEGIN generated: example-set:04-surfaces/tooltips -->
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
# Three ways to a tooltip: the short form, an inline Tooltip block, and a Popup with Tooltip: true
# that blocks name.
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
                            Icon { Icon: "mdi:information-outline", Tooltip: "The short form", Label: "Information" }
                            FlexBox {
                                Padding: 8
                                Tooltip {
                                    Gap: 4
                                    Enter_Delay: 300
                                    Style { Background: $color.surface_raised, Corner_Radius: 6 }
                                    Children { Label { Text: "A Tooltip block", Margin: 8 } }
                                }
                                Children { Label { Text: "Hover me" } }
                            }
                            FlexBox {
                                Padding: 8
                                Tooltip: Shared_Tip
                                Children { Label { Text: "Or me" } }
                            }
                        }
                    }
                }
            }
            Popup {
                Name: Shared_Tip
                Tooltip: true
                Gap: 4
                Style { Background: $color.surface_raised, Corner_Radius: 6 }
                Children { Label { Text: "A Popup that is a tooltip", Margin: 8 } }
            }
        }
    }
}
```

<!-- END generated: example-set:04-surfaces/tooltips -->

* `Tooltip: "The short form"` on a block or module use is a one-line text.
* An inline `Tooltip { ... Children { ... } }` block holds any content, with the Popup's placement and size keys below.
* `Tooltip: Shared_Tip` names a `Popup` with `Tooltip: true`, so several blocks can share one.
* A disabled block opens no tooltip unless it has `Tooltip_When_Disabled: true`.

The keys of an inline `Tooltip` block (the ones a Popup has, all optional):

<!-- BEGIN generated: surface:Tooltip -->
An inline Popup that is a tooltip, written inside a block or a module call.

| Key | Value | Default | Required | What it does |
|---|---|---|---|---|
| `Attach` | `LEFT` `RIGHT` `TOP` `BOTTOM` | none |  | The edge of the target the surface meets: LEFT, RIGHT, TOP or BOTTOM. |
| `Alignment` | `START` `CENTER` `END` | none |  | Where the surface sits along the edge it shares: START, CENTER or END. |
| `Gap` | number | none |  | The space between the surface and what it is placed against, in pixels. |
| `Adjust` | list of `FLIP_X` `FLIP_Y` `SLIDE_X` `SLIDE_Y` `RESIZE_X` `RESIZE_Y` | none |  | What the compositor may do to keep the popup on screen: one or a list of FLIP_X, FLIP_Y, SLIDE_X, SLIDE_Y, RESIZE_X, RESIZE_Y; [] asks for nothing. |
| `Width` | length | none |  | The width: pixels, a percentage, AUTO (fit the content) or EXPAND (take the free space). |
| `Height` | length | none |  | The height: pixels, a percentage, AUTO (fit the content) or EXPAND (take the free space). |
| `Max_Width` | length | none |  | The greatest width the block may resolve to, in pixels or a percentage. |
| `Max_Height` | length | none |  | The greatest height the block may resolve to, in pixels or a percentage. |
| `Focus` | true or false | none |  | Takes the keyboard and the pointer while open. |
| `Open_On_Enter` | true or false | none |  | Opens when the pointer enters the block it is the tooltip of. |
| `Enter_Delay` | number | none |  | How long the pointer rests before it opens, in milliseconds. |
| `Close_On_Exit` | true or false | none |  | Closes when the pointer leaves. |
| `Exit_Delay` | number | none |  | How long the pointer is away before it closes, in milliseconds. |

Not built yet (the loader says so if you write them): `Attach_To`, `Animation`.

A `Style { }` block of a Tooltip takes: `Background`, `Fill`, `Opacity`, `Elevation`, `Shadows`, `Shadow_Bleed`, `Corner_Radius`, `Border_Width`, `Border_Color`.

Inside it: any block (see the table of blocks on page 3).

<!-- END generated: surface:Tooltip -->

## Frame

A Frame is a ring around a monitor. It has a thickness on each side, which it reserves, so windows stay inside it; the opening in the middle takes no clicks. Along its sides it can have **strips** that hold blocks and modules, and **melded Panels** that grow out of it like part of the ring. It is drawn by one window, with four thin windows that reserve the space.

<!-- BEGIN generated: surface:Frame -->
A ring around the output, with strips along its sides that hold blocks.

| Key | Value | Default | Required | What it does |
|---|---|---|---|---|
| `Name` | name | none | yes | The unique name of the Frame; Attach_To of a melded Panel uses it. |
| `Layer` | `TOP` | none |  | The layer the Frame is drawn in; only TOP is built. |
| `Thickness` | sides | none | yes | The thickness of the Frame's ring: one number, four (left, top, right, bottom) or named sides. |
| `Margin` | sides | `0` |  | Space around the Frame's ring: one number, four or named sides. |
| `Corner_Radius` | radius | `0` |  | The radius of the outer corners of the ring: one number or four from the top-left clockwise. |
| `Inner_Radius` | radius | `0` |  | The radius of the corners of the opening inside the ring: one number or four from the top-left clockwise. |
| `Visible` | true or false | `true` |  | Starts the Frame shown (true) or hidden (false). |
| `Padding` | sides | `0` |  | Space between a strip's children and its sides, for every strip. |
| `Keyboard` | `NONE` `ON_DEMAND` | `NONE` |  | Whether the Frame's surface takes the keyboard: NONE or ON_DEMAND. |
| `Tab_Index` | whole number | none |  | The place of a block, or of a surface, in the order Tab (and Shift+Tab) follows: a whole number from 0 to 2147483647. Ascending; equal numbers keep document order; items with no number come after all the others. A surface holds one order for its blocks and the shell holds one for its surfaces. |
| `Shortcut` | key | none |  | The global key that toggles the Panel or Frame, written as Meta+Space; the same as Toggle_&lt;Name> in Shortcuts. The Shortcuts entry wins when both are written. |
| `Shortcut_Mode` | true or false | `false` |  | Whether this surface is the one in shortcut mode: the shell's keyboard mode, entered with Enter_Shortcut_Mode, in which the shortcut keys act on the surfaces (Next_Focus, Previous_Focus, Set_Shortcut_Mode, Exit_Shortcut_Mode). At most one surface is true at a time: setting one true sets every other false, and writing it false on the one that is true leaves the mode. Written true on a surface it makes the shell start in the mode on that surface; two surfaces written true are a warning and the first keeps it. |
| `Inner_Border` | block | none |  | A line along the inside of the ring: a block with Width and Color. |
| `Outer_Border` | block | none |  | A line along the outside of the ring: a block with Width and Color. |
| `Edges` | block | none |  | The sides of the Frame that have their own thickness or are strips: a block with Left, Top, Right and Bottom. |

Not built yet (the loader says so if you write them): `Children`, `Border_Tile`, `Meld`, `Exclusive_Zone`, `Input_Region`, `Class`.

A `Style { }` block of a Frame takes: `Background`, `Border_Width`, `Border_Color`, `Opacity`, `Elevation`, `Shadows`, `Shadow_Bleed`.

<!-- END generated: surface:Frame -->

* **Thickness and margin.** `Thickness` and `Margin` are one number, four sides `[left, top, right, bottom]`, or named sides (`Thickness { Top: 34, Left: 6 }`; an unnamed side is 0). A side of 0 reserves nothing. The reserved space of a side is its thickness plus the borders plus the margin.
* **Radii.** `Corner_Radius` rounds the outer corners and `Inner_Radius` the corners of the opening: one number, or four corners clockwise from the top left. A radius that is too large for the ring is reduced, with a warning.
* **Colour and borders.** `Style { Background: ... }` is the ring's colour (a token such as `$color.surface` follows the theme). `Inner_Border` and `Outer_Border` are lines along the opening and the outside.
* **Hide and show.** `Visible: false` starts it hidden; `Show`, `Hide` and `Toggle` with `Target: <the Frame's name>` act on it.
* **Keyboard.** `Keyboard: NONE` (the default) or `ON_DEMAND`. A Frame with a strip that holds a text field takes the keyboard on demand, with a warning if you wrote `NONE`.
* Not built yet: a Bar or a window Panel melded into the Frame, strips that expand and contract (changing the reserved space), gradients.

<!-- BEGIN generated: surface:Border -->
A line around the Frame's opening or outside: a width and a colour.

| Key | Value | Default | Required | What it does |
|---|---|---|---|---|
| `Width` | number | none | yes | The width of the border line, in pixels, 0 or more. |
| `Color` | colour | none | yes | The colour of the border line, a colour or a theme token. |

<!-- END generated: surface:Border -->

### Strips

`Edges { Top { ... }, Left { ... } }` makes a side a strip. Its `Children` are laid out in that side's band inside the Frame; the top and bottom strips own the corners and run the full width, and the left and right strips run between them and lay their children out vertically (text is not rotated). Blocks and module uses in a strip behave as they do in a Bar, including popups and tooltips.

<!-- BEGIN generated: surface:Edge -->
One side of a Frame: its thickness, padding and, with Children, a strip.

| Key | Value | Default | Required | What it does |
|---|---|---|---|---|
| `Name` | name | none |  | The target of Show, Hide and Toggle; only a strip with a Peek has one. |
| `Thickness` | number | none |  | The thickness of this side's strip in pixels, replacing the Frame's for this side (the full extent of a strip with a Peek). |
| `Padding` | sides | none |  | Space between the strip's children and its sides, replacing the Frame's. |
| `Content_Fade` | true or false | `true` |  | Whether the strip's children fade with its slide. |
| `Tab_Index` | whole number | none |  | The place of a block, or of a surface, in the order Tab (and Shift+Tab) follows: a whole number from 0 to 2147483647. Ascending; equal numbers keep document order; items with no number come after all the others. A surface holds one order for its blocks and the shell holds one for its surfaces. |
| `Shortcut_Mode` | true or false | `false` |  | Whether this surface is the one in shortcut mode: the shell's keyboard mode, entered with Enter_Shortcut_Mode, in which the shortcut keys act on the surfaces (Next_Focus, Previous_Focus, Set_Shortcut_Mode, Exit_Shortcut_Mode). At most one surface is true at a time: setting one true sets every other false, and writing it false on the one that is true leaves the mode. Written true on a surface it makes the shell start in the mode on that surface; two surfaces written true are a warning and the first keeps it. |
| `Peek` | block | none |  | Makes the strip rest as a sliver of Size pixels that comes out when asked; needs Children. |

Inside it: any block (see the table of blocks on page 3).

<!-- END generated: surface:Edge -->

### Melded Panels

A Panel with `Meld: true` and `Attach_To: <Frame>` is drawn inside the Frame's window as a body that grows from that side of the ring into the opening, in the Frame's colour and border, joined to the ring by a rounded fillet (the Frame's `Inner_Radius`). Size it with `Depth` (away from the edge) and `Length` (along it), not `Width` and `Height`. `Show`, `Hide` and `Toggle` with `Target: Dock` take it out of the ring and put it back, with its `Animation`. A `Margin`, `Movable`, `Keyboard` or `Input_Region` on a melded Panel is an error. How the join is drawn while the body slides is a [`Debug` setting](settings.md#debug) (`Frame_Join`, `Frame_Blend`).

### Peek

`Peek` in a melded Panel, or in an `Edges` entry, makes it rest as a thin tab or sliver and come out when asked. The tab is `Size` pixels of the body standing out of the ring's edge, with no content shown. `Trigger: HOVER` (the default) brings the whole body out when the pointer has stayed on the tab for `Enter_Delay` milliseconds, and sends it back when the pointer has left for `Exit_Delay`. `Trigger: CLICK` opens it with a click on the tab, and closes it with another. `Trigger: DRAG` lets you pull it out with the pointer: the body follows, and it finishes opening if you let go at halfway or more. `Handle` draws a small icon on the tab (`DOTS`, `BAR`, `CHEVRON`, or `AUTO`, which picks one for the trigger); it is dim (`Handle_Opacity`) until the pointer is on the tab. `Slide_From` is for a Panel in a Frame corner: the edge it slides out of. `Show`, `Hide` and `Toggle` bring a peeking surface fully out or back to the tab; a strip with a `Peek` needs a `Name` to be a target. The content of a melded Panel or strip fades with the slide (`Content_Fade: false` keeps it opaque).

For a melded Panel:

<!-- BEGIN generated: surface:Peek -->
Makes a melded Panel rest as a tab that comes out when asked.

| Key | Value | Default | Required | What it does |
|---|---|---|---|---|
| `Size` | number | `24` |  | How many pixels of the Panel show at rest, 1 or more and below its Depth. |
| `Enter_Delay` | milliseconds | `150` |  | How long the pointer rests before it opens, in milliseconds. |
| `Exit_Delay` | milliseconds | `300` |  | How long the pointer is away before it closes, in milliseconds. |
| `Trigger` | `HOVER` `CLICK` `DRAG` | `HOVER` |  | What opens it: HOVER, CLICK or DRAG. |
| `Handle` | `AUTO` `NONE` `DOTS` `BAR` `CHEVRON` | `AUTO` |  | The icon on its tab: AUTO, NONE, DOTS, BAR or CHEVRON. |
| `Handle_Opacity` | number | `0.6` |  | How bright the handle is at rest, from 0 to 1; hover raises it. |
| `Slide_From` | `TOP` `RIGHT` `BOTTOM` `LEFT` | none |  | For a Panel in a Frame corner: the edge it slides out of. |

<!-- END generated: surface:Peek -->

For a strip (an `Edges` entry):

<!-- BEGIN generated: surface:Edge_Peek -->
Makes a strip rest as a sliver that comes out when asked.

| Key | Value | Default | Required | What it does |
|---|---|---|---|---|
| `Size` | number | `24` |  | How many pixels of the strip show at rest, 1 or more and below the strip's thickness. |
| `Enter_Delay` | milliseconds | `150` |  | How long the pointer rests before it opens, in milliseconds. |
| `Exit_Delay` | milliseconds | `300` |  | How long the pointer is away before it closes, in milliseconds. |
| `Trigger` | `HOVER` `CLICK` `DRAG` | `HOVER` |  | What opens it: HOVER, CLICK or DRAG. |
| `Handle` | `AUTO` `NONE` `DOTS` `BAR` `CHEVRON` | `AUTO` |  | The icon on its tab: AUTO, NONE, DOTS, BAR or CHEVRON. |
| `Handle_Opacity` | number | `0.6` |  | How bright the handle is at rest, from 0 to 1; hover raises it. |

<!-- END generated: surface:Edge_Peek -->

A Frame with a top strip, an inner border and a melded dock that rests as a tab:

<!-- BEGIN generated: example-set:04-surfaces/frame -->
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
# A Frame: a ring around the screen. The top side is a strip that holds a Clock, the bottom side
# is a thin line, and a Panel is melded into the bottom edge as a dock that rests as a tab.
Shell {
    Monitor {
        Name: Main
        Index: default
        Children {
            Frame {
                Name: Screen_Frame
                Thickness: [6, 34, 6, 6]
                Margin: 4
                Corner_Radius: 0
                Inner_Radius: 14
                Inner_Border { Width: 2, Color: "#4682b4" }
                Style { Background: "#12171d" }
                Edges {
                    Top {
                        Thickness: 34
                        Padding: [12, 0, 12, 0]
                        Children {
                            FlexBox {
                                Width: EXPAND
                                Flex: HORIZONTAL
                                Align_Items: CENTER
                                Children {
                                    Spacer { }
                                    Clock { }
                                }
                            }
                        }
                    }
                }
            }
            Panel {
                Name: Dock
                Meld: true
                Attach_To: Screen_Frame
                Attach: BOTTOM
                Alignment: CENTER
                Length: 320
                Depth: 56
                Peek { Size: 12, Enter_Delay: 150, Exit_Delay: 300 }
                Animation { Type: SLIDE, Duration: 250 }
                Style { Corner_Radius: 12 }
                Children {
                    FlexBox {
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Align_Items: CENTER
                        Justify_Content: CENTER
                        Spacing: 16
                        Children {
                            Icon { Icon: "mdi:folder", Size: 28, Label: "Files" }
                            Icon { Icon: "mdi:console", Size: 28, Label: "Terminal" }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:04-surfaces/frame -->

> The Frame, its strips, melded Panels and peek were checked on KWin when they were built. How the ring's colours blend (`Debug { Frame_Blend }`) and the several ways to draw the join (`Frame_Join`) exist so they can be compared; the defaults are the maintainer's choice.

## Showing, hiding and toggling

A Panel, a Frame, a melded Panel and a strip that has a `Name` and a `Peek` can be shown and hidden by name, in three ways that do the same thing:

* **From a block**, with an action: `On_Click { Action: Toggle, Target: Notes }` on a button or any block that takes clicks. The actions are:

<!-- BEGIN generated: actions -->
| Action | Arguments | What it does |
|---|---|---|
| `Show` | `Target` (required), `Data` | Shows the Panel or strip named by Target; Data is given to a Popup as caller.data. |
| `Hide` | `Target` (required) | Hides the Panel or strip named by Target. |
| `Toggle` | `Target` (required), `Data` | Shows the Panel or strip named by Target if it is hidden, else hides it. |
| `Close` | none | Closes the Popup that holds the block. |
| `Call` | `Target` (required) | Runs a module's @action: Target is Module.action, the other keys are its arguments. |

<!-- END generated: actions -->

* **From the command line**: `tesserae-shell show Notes`, `tesserae-shell hide Notes`, `tesserae-shell toggle Notes`. They answer `Notes is shown` or `Notes is hidden`. An unknown name is an error with the nearest names (`no surface named Notez (did you mean Notes?)`); a Bar answers `Top_Bar is a Bar and is always shown` to `show` and an error to `hide` and `toggle`; showing a Panel whose `Attach_To` target is hidden answers `... stays hidden: see the log`.
* **From a key**: `Toggle_Notes: "Meta+N"` in `Shortcuts` or `Shortcut: "Meta+N"` on the Panel; see [Keyboard and shortcuts](keyboard.md).

Showing something already shown, or hiding something already hidden, succeeds and does nothing.

Blocks raise events when something happens to them. The ones a handler may be written for are:

<!-- BEGIN generated: events -->
| Event | Raised by | What it is |
|---|---|---|
| `On_Open` | Panel | A Panel is about to show. |
| `On_Close` | Panel | A Panel is about to hide. |
| `On_Visible` | Panel | A Panel has shown. |
| `On_Hidden` | Panel | A Panel has hidden. |
| `On_Focus` | nothing yet | The block took keyboard focus. Not raised yet. |
| `On_Unfocus` | nothing yet | The block lost keyboard focus. Not raised yet. |
| `On_Toggle` | Panel | A Panel was toggled. |
| `On_Click` | 12 block types | A click: the mouse, Space or Enter on a focused block, or assistive activation. A pointer event (this, On_Secondary_Click, On_Middle_Click, On_Scroll) gives a module's action event.rect: the block's (x, y, width, height) on the output, None inside a Popup. |
| `On_Secondary_Click` | 12 block types | A click with the secondary (right) button; event.button is "secondary". It does not run On_Click. |
| `On_Middle_Click` | 12 block types | A click with the middle button (a press and a release on the block); event.button is "middle". It does not run On_Click. |
| `On_Scroll` | 12 block types | One step of the mouse wheel over the block (the nearest block with the handler takes it); event.delta is +1 for a step down and -1 for a step up. |
| `On_Anim_Start` | Panel | A Panel's animation started. |
| `On_Anim_End` | Panel | A Panel's animation ended. |
| `On_Changed` | 5 block types | A control's value changed by the user: a toggle flipped (a click, or Space), an entry chosen (a click, or an arrow key), a slider moved (for each new value while the pointer moves, and for each key step). A TextField raises it for each change of its text. An Expander raises it when an opening or a closing has finished (event.value is whether it is open), whoever set the new state. |
| `On_Released` | Box, FlexBox, Rectangle, ScrollBox | A slider's press ended, once, with the final value; a key step (an arrow, Page Up or Down, Home or End) raises it at once after its On_Changed. |
| `On_Change` | nothing yet | Reserved: the old spelling of On_Changed. |
| `On_Submit` | TextField | Enter in a single-line TextField. |
| `On_Text_Commit` | TextField | Committed text in a TextField, such as an input-method composition. |
| `On_Key_Down` | TextField | A key went down in a TextField (event.key, event.ctrl, event.shift, event.alt, event.meta, event.repeat), before the field acts on it; the field acts whatever the handler does, and event.stop() keeps the surface above from hearing the key (a Panel's Escape). |

<!-- END generated: events -->

A handler is written inside the block: `On_Click: name` or `On_Click { Action: ... }`. `Show`, `Hide`, `Toggle` and `Close` are the shell's own actions; `Call` runs a module's `@action` (`Target: "Audio.set_volume"`, with the other keys as arguments). Most events are raised by modules' blocks, so on [Modules](modules.md) each module lists the ones it takes.

## The shipped Panel

The shell can add one Panel to your shell by itself, when you name it and write none of that name:

<!-- BEGIN generated: shipped-panels -->
The shell adds them to the main shell's first Monitor when added to the main shell's first Monitor when a Shortcuts entry or a handler names it and no Panel of the same name is written.

| Panel | Holds | Layer | Keyboard | Shown at start | What it is |
|---|---|---|---|---|---|
| `Launcher` | Applications | OVERLAY | EXCLUSIVE | no | The launcher: the Applications module in a hidden Panel. Open it with Toggle_Launcher in Shortcuts or a Toggle of Launcher. |

<!-- END generated: shipped-panels -->

The [Launcher](keyboard.md#the-launcher) is described with the keyboard (it was added after 0.1.1).

Next: [modules](modules.md).
