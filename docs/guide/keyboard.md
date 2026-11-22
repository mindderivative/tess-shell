# Keyboard and shortcuts

Everything on this page is about the keyboard: moving focus between widgets, the keys the widgets take, keys that work anywhere on the desktop (**global shortcuts**), a keyboard mode for walking from surface to surface, and the launcher.

## Focus

`Tab` and `Shift+Tab` walk the focusable blocks of a surface that **takes the keyboard**. A surface takes it only if you say so, because on Wayland a surface that grabs the keyboard unasked would steal it from your windows:

* a Bar: `Keyboard: NONE` (the default) or `ON_DEMAND`;
* a Panel: `NONE`, `ON_DEMAND` or `EXCLUSIVE` (it takes every key while shown);
* a Frame: `NONE` or `ON_DEMAND`;
* a surface that holds a text field takes `ON_DEMAND` whatever it says, and the log has a warning if you wrote `NONE`.

`ON_DEMAND` means the keyboard goes to the surface after you click it. Then:

* every interactive module (Button, Toggle, Checkbox, Slider, List, Menu, TextInput, TextEditor) is **one Tab stop**; a List and a Menu are one stop each and take the arrow keys inside. A disabled block, a block that is not visible and the content of a closed Expander are none;
* The order is the order of the file: nothing reorders the stops (`Tab_Index` above 0 is an error; `tesserae-shell migrate` rewrites a file that has one). `Focusable: true` puts a plain block in the order; `Enabled: false` takes one out;
* `:focused` styles the ring that keyboard focus shows. A click focuses a block without the ring. The ring is an outline drawn outside the block (`Outline_Width` 3, `Outline_Offset` 2, `Outline_Color` `color.primary`, from the theme's `space.focus_ring_width` and `space.focus_ring_offset`), so it shifts nothing and a block's own `Shadows` are untouched; a `:focused` rule can change it with the `Outline_*` keys. Only blocks that take those keys show it, so put `Focusable` on a `Box`, `FlexBox`, `Rectangle`, `ScrollBox` or `TextField`;
* a reload keeps focus on a block that is still there; when it is gone nothing is focused and Tab starts again at the first stop. A Popup gives focus back to the block it was opened from.

<!-- BEGIN generated: example-set:08-keyboard/focus -->
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
# Tab and Shift+Tab walk the focusable blocks of a surface that takes the keyboard, in the order
# of the file ("Save" before "Name"); Focusable puts a plain box in the order, and Enabled: false
# takes a button out of it.
Shell {
    Monitor {
        Name: Main
        Index: default
        Children {
            Panel {
                Name: Form
                Layer: TOP
                Anchor: [TOP, LEFT]
                Inset: [24, 24, 0, 0]
                Width: 320
                Height: 200
                Keyboard: ON_DEMAND
                Style { Background: $color.surface, Corner_Radius: 8 }
                Children {
                    FlexBox {
                        Flex: VERTICAL
                        Padding: 12
                        Spacing: 8
                        Children {
                            Button { Text: "Save" }
                            TextInput { Placeholder: "Name" }
                            Button { Text: "Not now", Enabled: false }
                            FlexBox {
                                Focusable: true
                                Padding: 8
                                Children { Label { Text: "A focusable box" } }
                            }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:08-keyboard/focus -->

Set `Logging { Level: DEBUG }` to see `focus:` lines in the log.

### Keys of the widgets

A key with Ctrl, Alt or Meta belongs to you, not to a widget, except the Ctrl keys a text field takes itself.

| Widget | Keys |
|---|---|
| Button | Enter and Space press it: `On_Click` runs, and the pressed look shows while the key is held. |
| Toggle, Checkbox | Space flips it and raises `On_Changed` once (a held key does not repeat the flip). Enter does nothing. |
| Slider | Left and Down take a step off, Right and Up put one on, Page Up and Page Down ten steps, Home and End go to `Min` and `Max`. Each key that moves the value raises `On_Changed` and then `On_Released`; a key at an end raises nothing. |
| List | Up and Down move the chosen entry (the first Down chooses the first entry, the first Up the last), Page Up and Page Down by a page, Home and End to the ends; Enter and Space choose the first entry when none is chosen; letters typed jump to the next entry that starts with them. Each move is a choice and raises `On_Changed`. |
| Menu | Up and Down move the lit row (round the ends, over disabled rows), Home and End go to the ends, Enter and Space run a row, Right opens a submenu, Left closes it, Escape closes the innermost level. |
| TextInput | Typing, the arrows, Home and End, Shift selects, Ctrl+A, Ctrl+C, Ctrl+X, Ctrl+V; Enter raises `On_Submit`; Tab leaves the field. |
| TextEditor | As TextInput; Enter inserts a newline; Tab and Shift+Tab leave the field. |
| Expander | No keys of its own; Enter and Space on the Button that controls it toggle it. |

A focused widget that takes keys keeps them: the arrow keys do not scroll a scrolling box around a focused Button, Toggle, Checkbox, Slider or List.

## Global shortcuts

A global shortcut works while no shell surface has focus. The shell registers its keys with KDE's shortcut service (`org.kde.kglobalaccel`) as one component named `tesserae-shell`, so they appear in System Settings under Shortcuts, where you can change or clear them.

You write them in the `Shortcuts` block of [`settings.tdl`](settings.md#shortcuts), one entry for each action:

<!-- BEGIN generated: shortcut-forms -->
| Entry in `Shortcuts { }` | What it does |
|---|---|
| `Toggle_<Name>` | Toggle_&lt;Name>: "keys" toggles the Panel, Bar or Frame called &lt;Name>. |
| `Show_<Name>` | Show_&lt;Name>: "keys" shows the Panel, Bar or Frame called &lt;Name>. |
| `Hide_<Name>` | Hide_&lt;Name>: "keys" hides the Panel, Bar or Frame called &lt;Name>. |
| `<Any_Name> { Keys, Action }` | &lt;Any_Name> { Keys: "keys", Action: ... } runs a handler of Events and Actions (Show, Hide, Toggle or Call, with its arguments) when the key is pressed; its name is what the desktop's shortcut settings show. |

The five fixed actions are `Enter_Shortcut_Mode`, `Exit_Shortcut_Mode`, `Set_Shortcut_Mode`, `Next_Focus`, `Previous_Focus`.

| Surface | Key | Meaning |
|---|---|---|
| `Panel` | `Shortcut` | the same as `Toggle_<Name>` |
| `Frame` | `Shortcut` | the same as `Toggle_<Name>` |

A surface's own key and a Shortcuts entry for the same action: the entry wins, with one warning. Two actions with the same key (any case, order or alias) are both left without it, with one warning. A name that matches no surface is a warning and the shortcut is not registered.

<!-- END generated: shortcut-forms -->

<!-- BEGIN generated: example-set:08-keyboard/shortcuts -->
File `settings.tdl`:

```tdl
---
TDL: 0.2
Name: Settings
---
Settings {
    Appearance { Stylesheets: [Default] }
    Shortcuts {
        Toggle_Launcher: "Meta+Space"
        Toggle_Notes: "Meta+N"
        Hide_Notes: "Meta+Shift+N"
        Volume_Up { Keys: "AudioRaiseVolume", Action: Call, Target: "Audio.step", delta: 5 }
        Volume_Down { Keys: "AudioLowerVolume", Action: Call, Target: "Audio.step", delta: -5 }
        Mute { Keys: "AudioMute", Action: Call, Target: "Audio.toggle_mute" }
        Play_Pause { Keys: "AudioPlay", Action: Call, Target: "Media.play_pause" }
    }
}
```

File `Shells/Main_Shell.tdl`:

```tdl
---
TDL: 0.2
Name: Main_Shell
---
# The surfaces the shortcuts name. Toggle_Launcher names the Launcher, which the shell adds
# itself because this file writes no Panel of that name. A surface may also carry its own key:
# Shortcut on a Panel or a Frame, as Scratch does (the same as Toggle_<Name>).
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
                            Audio { }
                            Spacer { }
                            Clock { }
                        }
                    }
                }
            }
            Panel {
                Name: Notes
                Layer: TOP
                Anchor: [TOP, RIGHT]
                Inset: [0, 40, 12, 0]
                Width: 280
                Height: 160
                Visible: false
                Style { Background: $color.surface_raised, Corner_Radius: 8 }
                Children { Label { Text: "Notes", Margin: 12 } }
            }
            Panel {
                Name: Scratch
                Layer: TOP
                Anchor: [BOTTOM, LEFT]
                Inset: [12, 0, 0, 12]
                Width: 220
                Height: 100
                Visible: false
                Shortcut: "Meta+S"
                Style { Background: $color.surface_raised, Corner_Radius: 8 }
                Children { Label { Text: "Opened by its own Shortcut key", Margin: 12 } }
            }
        }
    }
}
```

<!-- END generated: example-set:08-keyboard/shortcuts -->

In this example `Toggle_Notes` and `Hide_Notes` toggle and hide the Panel `Notes`; `Toggle_Launcher` names the shipped Launcher ([below](#the-launcher)); `Volume_Up`, `Volume_Down`, `Mute` and `Play_Pause` are handlers of your own that call actions of the Audio and Media modules (each module's actions are listed on [Modules](modules.md)); and the Panel `Scratch` carries its own `Shortcut` key, which is the same as `Toggle_Scratch`. A Bar has no key of its own: it is always shown (`Auto_Hide` is not built), so the old `Reveal_Key` was removed and a Bar that still writes it is an error naming the key. `Show_<Name>` for a Bar has nothing to do yet, and `Hide_<Name>` takes a Panel or a Frame, not a Bar. A handler entry's name is what System Settings shows for the action. A `Call` handler loads its module even when no Bar or Panel uses it.

How a key is chosen:

* **The desktop wins.** A key the desktop already uses is not taken: the action is registered with no key and the log has one warning (`shortcuts: Toggle_Launcher: the key Meta+Space is taken by the desktop or another application: the action is registered with no key (choose one in System Settings)`). Choose a free key in System Settings. A key you cleared there is not a taken key and gives no warning.
* **System Settings wins over the file.** The file gives a *default*. A key you changed in System Settings is kept across restarts and wins; the log then says so at INFO level (`the file writes ... but the service uses ...`).
* **Two actions with the same key** (in any case, order or spelling) both lose it, with one warning naming both. An entry that names no surface is a warning and is not registered.
* A hot reload applies changed shortcuts without a restart. `Settings { Global_Shortcuts: false }` makes no call to the service at all.
* If there is no `org.kde.kglobalaccel` on the session bus the shell starts, warns once (`shortcuts: no org.kde.kglobalaccel on the session bus: no global keys; the shell runs and tesserae-shell toggle <name> still works`) and the commands keep working: `tesserae-shell toggle Notes` does what the key would.

> **Not yet checked on KWin:** the registration details with the real `kglobalaccel`. The maintainer's hand check passed most of its lines on KWin; how KDE stores, reports and changes the keys in every case has not been confirmed, and the shell's behaviour is built from the documented behaviour of the service and tests against a fake. If a key does nothing, look at the log for the lines above and at System Settings, Shortcuts.

### Key names

<!-- BEGIN generated: key-names -->
A key is the modifiers `Ctrl`, `Alt`, `Shift`, `Meta` and one key, joined by `+`, for example `Ctrl+Shift+F1`. Case and order do not matter. These are the key names:

| Group | Names |
|---|---|
| Letters | `A`, `B`, `C`, `D`, `E`, `F`, `G`, `H`, `I`, `J`, `K`, `L`, `M`, `N`, `O`, `P`, `Q`, `R`, `S`, `T`, `U`, `V`, `W`, `X`, `Y`, `Z` |
| Digits | `0`, `1`, `2`, `3`, `4`, `5`, `6`, `7`, `8`, `9` |
| Function | `F1`, `F2`, `F3`, `F4`, `F5`, `F6`, `F7`, `F8`, `F9`, `F10`, `F11`, `F12`, `F13`, `F14`, `F15`, `F16`, `F17`, `F18`, `F19`, `F20`, `F21`, `F22`, `F23`, `F24` |
| Named | `Enter`, `Escape`, `Tab`, `Space`, `Backspace`, `Delete`, `Insert`, `Home`, `End`, `Left`, `Up`, `Right`, `Down`, `PageUp`, `PageDown`, `Plus`, `Print`, `Pause`, `Menu` |
| Hardware | `AudioRaiseVolume`, `AudioLowerVolume`, `AudioMute`, `AudioMicMute`, `AudioPlay`, `AudioPause`, `AudioStop`, `AudioNext`, `AudioPrev`, `AudioRecord`, `AudioRewind`, `AudioForward`, `AudioMedia`, `MonBrightnessUp`, `MonBrightnessDown`, `KbdLightOnOff`, `KbdBrightnessUp`, `KbdBrightnessDown`, `PowerOff`, `WakeUp`, `Eject`, `ScreenSaver`, `WWW`, `Sleep`, `Suspend`, `Hibernate`, `Standby`, `HomePage`, `Favorites`, `Search`, `Mail`, `Calculator`, `Calendar`, `Explorer`, `Documents`, `Tools`, `Music`, `Video`, `Display`, `Battery`, `Bluetooth`, `WLAN`, `TouchpadToggle`, `ZoomIn`, `ZoomOut`, `Back`, `Forward`, `Refresh`, `Launch0`, `Launch1`, `Launch2`, `Launch3`, `Launch4`, `Launch5`, `Launch6`, `Launch7`, `Launch8`, `Launch9`, `LaunchA`, `LaunchB`, `LaunchC`, `LaunchD`, `LaunchE`, `LaunchF` |

Other spellings that are read:

| Written | Read as |
|---|---|
| `Return` | `Enter` |
| `Esc` | `Escape` |
| `Del` | `Delete` |
| `Ins` | `Insert` |
| `PgUp` | `PageUp` |
| `PgDown` | `PageDown` |

Every key of the hardware group may also be written with the `XF86` prefix of its X name.

<!-- END generated: key-names -->

Write `Plus` for the plus key. Media and hardware keys are written by their X names without `XF86`: `AudioRaiseVolume`, `MonBrightnessUp`.

## Shortcut mode

A keyboard mode of the whole shell, for reaching the surfaces without the pointer. Name the one global key in `settings.tdl`, and the keys of the mode beside it (use a key the desktop does not use; `Ctrl+Alt+Shift+F9` is rare):

<!-- BEGIN generated: example-set:08-keyboard/shortcut-mode -->
File `settings.tdl`:

```tdl
---
TDL: 0.2
Name: Settings
---
Settings {
    Appearance { Stylesheets: [Default] }
    Shortcuts {
        Enter_Shortcut_Mode: "Ctrl+Alt+Shift+F9"
        Exit_Shortcut_Mode: "Ctrl+Q"
        Set_Shortcut_Mode: "Ctrl+Enter"
        Next_Focus: "Tab"
        Previous_Focus: "Shift+Tab"
    }
}
```

File `Shells/Main_Shell.tdl`:

```tdl
---
TDL: 0.2
Name: Main_Shell
---
# Shortcut mode walks the surfaces with the keyboard. Each surface that holds something to focus
# takes the keyboard on demand; Focus_Order says which one shortcut mode visits first.
Shell {
    Focus_Order: [Top_Bar, Notes]
    Monitor {
        Name: Main
        Index: default
        Children {
            Bar {
                Name: Top_Bar
                Edge: TOP
                Width: EXPAND
                Height: 36
                Keyboard: ON_DEMAND
                Style { Background: $color.surface }
                Children {
                    FlexBox {
                        Width: EXPAND
                        Flex: HORIZONTAL
                        Align_Items: CENTER
                        Spacing: 8
                        Padding: [12, 0, 12, 0]
                        Children {
                            Button { Text: "One" }
                            Button { Text: "Two" }
                        }
                    }
                }
            }
            Panel {
                Name: Notes
                Layer: TOP
                Anchor: [TOP, RIGHT]
                Inset: [0, 48, 12, 0]
                Width: 280
                Height: 120
                Keyboard: ON_DEMAND
                Style { Background: $color.surface_raised, Corner_Radius: 8 }
                Children {
                    FlexBox {
                        Flex: VERTICAL
                        Padding: 12
                        Spacing: 8
                        Children {
                            Checkbox { Text: "Remind me" }
                            Button { Text: "Done" }
                        }
                    }
                }
            }
        }
    }
}
```

<!-- END generated: example-set:08-keyboard/shortcut-mode -->

* **Enter.** `Enter_Shortcut_Mode` puts the Frame (or, with no Frame, the first surface in the order below) in the mode, gives it the focus and shows every peek of the Frame at once. The surface that has the focus asks the compositor for the keyboard for the length of the mode (`Debug { Mode_Keyboard }`). **While the mode is on, your other windows get no typing:** Escape leaves it.
* **Only the Enter key is a global key.** The other four are declared with no key (System Settings lists them, and a key you give one there runs it), and the keys you wrote for them arrive as key events on the surface that has the keyboard.
* **`Next_Focus` and `Previous_Focus`** move the focus through the surfaces in the shell's order (`Focus_Order` first, then the order of the file; Bars, Panels, the Frame; a strip as `<Frame>.<side>`), going round and skipping a hidden Panel. The ring shows on the first Tab stop of the surface that has the focus.
* **`Focus_Order`** is a key of the `Shell` block: `Shell { Focus_Order: [Screen_Frame, Notes, Top_Bar] Monitor { ... } }`. The surfaces it names come first, in that order; the others follow in the order of the file. A name no surface has is a warning (`focus-order-unknown`) with the nearest names. An older file that ordered surfaces with `Tab_Index` is rewritten by `tesserae-shell migrate` (step 0003).
* **F6 and Shift+F6** move between the surfaces from one that has the keyboard (a Bar you clicked, a Panel that takes it): the first press enters the mode and steps to the next surface in the order above, then each press steps on (Shift goes back); Escape leaves. F6 with Ctrl, Alt or Meta is not the shell's. It needs a shell surface to have the keyboard already; from another window the key that enters the mode (`Enter_Shortcut_Mode`) is the way in.
* **`Set_Shortcut_Mode`** toggles the mode of the focused surface: turned on for a Panel it moves the mode to that Panel (the Frame's peeks go back to rest, the Panel's own keys apply); turned off it ends the whole mode (press the Enter key again to start over). **`Exit_Shortcut_Mode`** ends it.
* **`Shortcut_Mode: true`** on a Bar, Panel, Frame or strip (`Edges { Top { Shortcut_Mode: true } }`) starts the shell in the mode on that surface. At most one surface may say it: two give one load warning naming both, and the first wins.
* Entering and leaving the mode, and each move, set a polite status text on the window that has the focus. At `Logging { Level: DEBUG }` the log says `shortcut mode: ...`.

> **Not yet checked on KWin:** shortcut mode's keyboard. Which of `EXCLUSIVE` and `ON_DEMAND` KWin needs for the mode's keys to arrive is an open question; the default is `EXCLUSIVE`. If after entering the mode the log says `shortcut mode: the compositor did not give <surface> the keyboard (...) within ... ms, so the keys of the mode do not arrive`, set `Debug { Mode_Keyboard: ON_DEMAND }` and restart.

## The Launcher

A text field over the installed applications, opened by a key and operated from the keyboard alone. The module is [Applications](modules.md#applications); the shell ships a Panel named `Launcher` that holds it, so one line in `settings.tdl` gives you a launcher:

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

The shell adds the Panel to the first Monitor of the main shell when a `Shortcuts` entry (`Toggle_`, `Show_` or `Hide_Launcher`) or a `Show`, `Hide` or `Toggle` handler names `Launcher` and your file writes no Panel of that name. A shell that never names it gets no extra surface. The shipped Panel is a floating 480 by 400 Panel on the overlay layer with `Keyboard: EXCLUSIVE`, hidden until shown (the table of shipped Panels is on [Surfaces](surfaces.md#the-shipped-panel)). A Panel you write called `Launcher` replaces it whole:

<!-- BEGIN generated: example-set:08-keyboard/custom-launcher -->
File `settings.tdl`:

```tdl
---
TDL: 0.2
Name: Settings
---
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
# A Panel written as Launcher replaces the shipped one whole: here a taller one near the top.
Shell {
    Monitor {
        Name: Main
        Index: default
        Children {
            Panel {
                Name: Launcher
                Layer: OVERLAY
                Anchor: [TOP]
                Inset: [0, 80, 0, 0]
                Width: 520
                Height: 460
                Keyboard: EXCLUSIVE
                Visible: false
                Style { Background: $color.surface_raised, Corner_Radius: 12, Elevation: 30% }
                Children { Applications { max_results: 10, show_comment: false, icon_size: 28, placeholder: "Run..." } }
            }
        }
    }
}
```

<!-- END generated: example-set:08-keyboard/custom-launcher -->

* **Opening.** The field takes the keyboard focus and its text is selected, so typing starts a new search.
* **Typing** narrows the list at once. Every word of the query must match, without case or accents. Best rank first: the start of the name, the start of a word of the name, anywhere in the name, the start of a word of the generic name or a keyword, then anywhere in the generic name, a keyword or the comment. Equal ranks are ordered by how often you started the application, then by name. An empty query lists the most started first, then the rest by name.
* **Keys.** Down and Up move the selection and wrap; Page Down and Page Up move by the rows shown and stop at the ends; Enter starts the selected row; **Escape** clears the field and, with the field empty, hides the Panel. A click on a row starts it. A click on the desktop or on another application's window hides the Panel when it is on the OVERLAY layer, as the shipped one is (the click itself is taken by the Panel's closing, so click again to use it), and so does another Panel of the shell taking the keyboard from it. A click on another surface of the shell, such as its Bar, does not hide it: use Escape or the key.
* **Starting.** The application is started detached, so it outlives the shell: in a transient user scope named `app-<id>-<random>.scope` when `systemd-run --user --scope` works, otherwise as a plain process in a session of its own. Its working folder is the entry's `Path` (else your home) and its environment is the shell's without the shell's own variables. The shell asks the compositor for an activation token inside the Enter or click, so the new window can take focus. `Exec` follows the Desktop Entry Specification (`%f %F %u %U` removed, `%i` as `--icon <Icon>`, `%c` the name, `%k` the file's path); `Terminal=true` runs through `xdg-terminal-exec`, and if that is not on your path the shell warns once and starts nothing. A program that is not there, or an entry without `Exec`, keeps the Panel open with `Could not start <name>`. After a start the field is empty and the Panel hidden.
* **The list** is built from the desktop entries in `XDG_DATA_HOME` and `XDG_DATA_DIRS` on first use and follows changes with inotify: an application you install appears with no restart.
* **Not in this version:** files, a calculator, web search, desktop actions of an entry, categories, a grid, pinned favourites.

The Launcher and the Applications module were added in 0.1.2 ([Install and start](install.md#what-needs-a-recent-release)).

> **Not yet checked on KWin:** the Launcher's keyboard when it opens from a global key (it asks for `EXCLUSIVE` keyboard for that reason), and a real start of an application with focus after it. The shell never starts a process during its tests; a kit for the hand check exists but has not been reported yet.

Next: [the command line](command-line.md).
