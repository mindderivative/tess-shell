# Multiple monitors

The shell treats every monitor alike: a `Monitor` block says which screen its surfaces are for, and the shell opens them there. [Surfaces](surfaces.md#monitor) lists the keys of a `Monitor` block. This page goes further: how the choice is made, how to write a shell for a laptop and a changing set of screens, and what happens when you plug a screen in or pull one out.

## How a monitor is chosen

The shell asks the compositor for its list of outputs and matches each `Monitor` block to them:

1. A block with `Connector` takes the output of that name (`eDP-1`, `DP-1`, `HDMI-A-1`). With `Description` it takes the output the compositor describes that way. With a number `Index` it takes the output at that position, counted from 0. A block with several of these tries them in that order: `Connector`, then `Description`, then `Index`, and the first that finds an output wins.
2. A block that names an output another block already took gets nothing: the first block wins, and the shell logs `Monitor X names DP-1, which Monitor Y already took; Y wins and X opens nothing`.
3. A block with `Index: default` and no other selector takes every output that no other block took.
4. A block with no selector at all is ignored.

A block that matches no output (the screen is not plugged in) opens nothing and logs `monitor NAME matches no output; its surfaces are not opened` at info level. That is not an error: the block waits, and opens its surfaces when its screen appears.

To see the names the shell gives your outputs, run `tesserae-shell status` while it runs. The `monitors:` line lists each block that found an output and the output it got (`Laptop (eDP-1)`), and the `surfaces:` list ends each line with the output the surface is on. The shell logs the outputs it sees each time they change (`output DP-1 added: outputs now eDP-1, DP-1`).

`Index` is the position in the compositor's list, top to bottom and then left to right, and the shell works it out again on every change. A block with `Index: 1` follows whichever screen is second now: when the order changes, its surfaces close on one screen and open on the other. `Connector` and `Description` do not move. For anything that must stay on a particular screen, use `Connector` or `Description`.

## One definition on several monitors

An `Index: default` block is one definition shown on every monitor it matches. Its surfaces are real, separate windows, one per output, each with its own size, so a `Width: EXPAND` Bar is as wide as the screen it is on.

```tdl
---
TDL: 0.2
Name: Main_Shell
---
Shell {
    # The laptop screen, by connector: a slim Bar and a Panel that only this screen has.
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
            Panel {
                Name: Notes
                Layer: TOP
                Anchor: [TOP, RIGHT]
                Inset: [0, 36, 12, 0]
                Width: 240
                Height: 120
                Visible: false
                Style { Background: $color.surface_raised, Corner_Radius: 8 }
                Children {
                    Label { Text: "Only on the laptop" }
                }
            }
        }
    }
    # Every other monitor, however many there are and whatever they are called.
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
            }
        }
    }
}
```

This file passes `tesserae-shell check`. With the laptop alone, only `Laptop` opens. Plug in a screen and `Others` opens a Bar on it; the laptop's Bar is not touched. If the laptop's own screen is the only one that goes away (a docked laptop with the lid closed), `Others` still covers the screens that are left.

Things that follow from "one window per output":

* Every surface name is unique in the shell, so the same `Bar` block on three screens is three windows with one name. The shell tells them apart by the output.
* `Show`, `Hide` and `Toggle` on a Panel's name, from a block or from `tesserae-shell show NAME`, `hide` or `toggle`, reach the Panel on every monitor that has it. To show a Panel on one monitor only, put it in a `Monitor` block that names that monitor, as `Notes` is above. See [Showing, hiding and toggling](surfaces.md#showing-hiding-and-toggling).
* A Popup is tied to the monitor of the surface that opened it. It opens there and never anchors to a surface on another monitor.
* A module a `Monitor` block uses gets one use per monitor it is shown on, so a module can be shown by a Bar on each screen at once. [Modules](modules.md) describes how a module's values reach each use.
* A floating Panel you moved is remembered per block and output (`Laptop@eDP-1`), so it comes back where you left it on that screen and nowhere else. The position is kept inside the output.

## Differences between monitors

Write one `Monitor` block per screen that should look different, each chosen by `Connector` or `Description`, and one `Index: default` block for the rest. Anything a Bar, Panel, Popup or Frame can have may differ: the height, the edge, the modules, the style. A Frame (the ring around a monitor) is per monitor as well; each `Monitor` that writes one gets its own.

The shell does not scale one definition by itself. If a Bar should be taller on a 4K screen, say so in a block of its own for that screen. A change of the output's size or scale is followed, though: see below.

## When monitors come and go

The shell listens to the compositor for outputs added, removed and changed. On each event it plans the whole shell again against the new list, with the same rules as at start, and compares the plan with what is running by each surface's name and output:

| What happened | What the shell does |
|---|---|
| A monitor is plugged in | The surfaces of the blocks that now match it are opened, in new windows. Every other monitor's windows are not recreated or redrawn. `Index: default` blocks pick it up. |
| A monitor is unplugged, or switched off so that the compositor drops it | The surfaces on it close: `Bar Big_Bar on DP-1 closed: output DP-1 was removed`. The modules that were used only there are stopped, and a module used elsewhere keeps running. Other monitors are not touched. |
| A monitor changes size, scale or rotation | The surfaces on it get their new geometry in place, with no new window, and are logged (`output DP-1 is now 1920x1080 at scale 1.0`). A Popup that was open on that output closes. |
| A monitor comes back | New windows open, since a closed window is gone for good, at the positions the registry saved for that block and output. |
| The `Index` order changes | Blocks chosen by `Index` follow the new order: their surfaces close on one screen and open on another. |

The surfaces of the other monitors stay exactly as they were. What is lost with a closed window is its state: an open Popup, a Panel that was shown (a Panel starts again as its file says, `Visible`). The files and the registry are untouched.

If the compositor reports no output at start, the shell logs `no outputs: no surface was opened` and keeps running. If the compositor itself goes away (KWin restarted or crashed), that is a different case: the shell stops what it runs and exits with code 69, and the systemd unit from [Start with your session](session.md) starts it again.

## When an output goes away

If a screen was unplugged and you want your surfaces somewhere else, you have two choices:

* Nothing. The surfaces of that screen are closed and will be back when it is. This is the right choice for a laptop that is docked now and then.
* Write an `Index: default` block, so that any screen gets a Bar. This is the choice for a laptop that goes to changing places, where the screens' names are not yours to know. Add a block with `Connector` for each screen that should look different.

If a Bar you expect is missing, run `tesserae-shell status`: the `monitors:` line shows which block found which output, and `surfaces:` which surface is where. The shell's log has the lines quoted on this page, at the default level. [Troubleshooting](troubleshooting.md) lists the messages.

> Monitor hot-plug is one of the parts confirmed by hand on a real KWin session (see [Install and start](install.md#what-has-been-checked-on-kwin)). The design notes record the monitor rules and the cases not yet tried.

Next: [hot reload](hot-reload.md), or the design of the surfaces in [Surface Types](../design/40%20Specifications/Surfaces/Surface%20Types.md) and the monitor flow in [Data Flow](../design/20%20Architecture/Data%20Flow.md).
