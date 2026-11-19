# Writing a module

A module of your own is a layout in TDL and a Python file beside it. The layout says what is drawn; the Python says what is true: it keeps the state, reacts to a click and sends the values the layout shows. You use the module in a shell file the way you use the ones the shell ships ([Modules](modules.md)).

This page builds one small module, `Tally`, a counter. A click adds to it, a click with the secondary button sets it back to 0. Every name the page uses is described exactly in the [module API reference](../api/module-api.md).

> A module's Python runs inside the shell, as you, with your rights, and the shell does not sandbox it. See [Trust](#what-the-shell-does-with-your-python) below and [Security](security.md).

## The folder

A module lives in `Modules/` of your [configuration folder](configuration-folder.md), in a folder of its own named like the module:

```text
Modules/
  Tally/
    Tally_Module.tdl      the layout: the name, the params, the block tree
    Tally_Module.py       the Python: one class that extends Module
```

The Python file has the name of the layout file with `.py` in place of `.tdl`, and sits next to it. A layout with no Python file beside it is an error (`module-no-python`, naming both files). A module that has no behaviour still needs the file; the shipped `Toggle` has a class with `pass` in it.

A module that has a look of its own can name a style file in its layout (`Style: Tally_Style.tdl`, as the shipped modules do); this page uses the theme's colours and does not need one.

## The layout

The metadata block names the module (`Name: Tally`, which is what a shell file writes to use it), then one `Module { }` block holds the params and the block tree:

```tdl
---
TDL: 0.2
Name: Tally
---
Module {
    Params {
        step { Type: number, Default: 1 }
    }
    FlexBox {
        Name: Root
        Role: BUTTON
        Label: <| text |>
        Padding: [10, 4, 10, 4]
        On_Click { Action: bump, amount: <| params.step |> }
        On_Secondary_Click: reset
        Children {
            Text {
                Name: Face
                Text: <| text |>
            }
        }
    }
}
```

* **`Params`** lists what a use may set: here `Tally { step: 5 }`. A param has a `Type` (`string`, `number`, `boolean`, `path` or `icon`) and an optional `Default`; one with no default must be given. An unknown param in a use is an error with the nearest names as a hint.
* **The block tree** is built from the [blocks the shell has](first-bar.md#the-blocks-you-can-put-in-a-bar). A use of the module also takes the common keys of every module use (`Width`, `Margin`, `Label` and the rest, [Modules](modules.md#using-a-module)).
* **A `<| ... |>` slot** is an expression whose value the block shows and keeps up to date. It reads two things: `params.step`, a param of this use, and a name the Python sent, like `text`. When the Python sends a new value, only the blocks that read it change.
* **The type of the key decides what a slot may give.** `Text:` takes a string, a number key takes a number, a colour key takes a colour string such as `"#8fd3b6"`, an enum key one of its upper-case words. A slot that gives something else is logged as a warning with the key and the value, and the block keeps what it had. The [reference](../api/module-api.md#values) lists every kind.
* **Events and handlers.** `On_Click { Action: bump, amount: <| params.step |> }` calls the module's own `@action` named `bump`; `amount` is an argument, a plain value or a slot that is evaluated when the click happens. `On_Secondary_Click: reset` is the short form, a bare action name with no arguments. The events a block can raise are in [Surfaces](surfaces.md#showing-hiding-and-toggling) and on each block's page.

Send every value the layout reads as early as you can, in `start()` as `Tally` does: the shell keeps what is sent before a surface exists, and a surface that is drawn then shows it.

## The Python

```python
"""Tally: a counter. The class name is the module's Name."""

from __future__ import annotations

from tess_shell import Event, Module, action
from tess_shell.modules.context import UseRecord


class Tally(Module):
    def start(self) -> None:
        # one instance serves every use, so the counts are kept by use key
        self.counts: dict[str, int] = {}
        for use in self.ctx.uses.values():
            self.show(use.key)

    def validate_use(self, use: UseRecord) -> None:
        step = use.params.get("step", 1)
        if step < 1 or step != int(step):
            raise ValueError(f"step must be a whole number of 1 or more, not {step}")

    def use_added(self, use: UseRecord) -> None:
        self.show(use.key)

    def use_removed(self, use: UseRecord) -> None:
        self.counts.pop(use.key, None)

    @action
    def bump(self, event: Event, amount: float = 1) -> None:
        key = event.use
        self.counts[key] = self.counts.get(key, 0) + int(amount)
        self.show(key)

    @action
    def reset(self, event: Event) -> None:
        # a click on the module's own block names its use; a Call from another block names that
        # block's use, so then every use of the module is reset
        keys = [event.use] if event.use in self.ctx.uses else list(self.ctx.uses)
        for key in keys:
            self.counts[key] = 0
            self.show(key)
        self.ctx.announce("Tally reset")

    def show(self, key: str) -> None:
        count = self.counts.get(key, 0)
        self.ctx.send("count", count, use=key)
        self.ctx.send("text", f"Tally: {count}", use=key)
```

The pieces:

* **One class.** The file must hold exactly one class that extends `Module` (imported from `tess_shell`). None, or two, is an error (`module-classes`) naming the file. By convention it is named like the module. It takes no constructor arguments: the shell creates it, sets `self.ctx` and then calls `__init__()` with none, so `self.ctx` is already there in an `__init__` you write.
* **One instance serves every use.** `Tally { step: 1 }` and `Tally { step: 5 }` in the example are two uses of one object. `self.ctx.uses` maps each use's key to a `UseRecord` (its `key`, `name`, `uid`, `monitor` and `params`). The key, `Tally@<uid>`, is what you keep state under and pass back to name a use.
* **`start()`** runs once, on the shell's loop thread, after the files are read. Return quickly: while a callback runs, nothing else on the screen moves. Slow work goes to a thread ([below](#slow-work-and-threads)).
* **`self.ctx.send(key, value, use=...)`** sends a value to the layout. With `use=` it goes to that use; with no `use` it goes to every use of the module. It may be called from any thread and never blocks: the shell takes the value on its next turn and keeps the latest one for each use and key. A value must be a string, a number, a boolean, or a list or dict of those. `None`, a `datetime` or any object is refused with an error in the log and the old value stays.
* **`@action`** marks a method that a layout, a shortcut or `tesserae-shell call` may run. Nothing else in the class can be called from a file. Its first parameter is the `Event` (its `use` is the key of the use whose block raised it); the parameters after it are the handler's arguments by name, so `On_Click { Action: bump, amount: 5 }` runs `bump(event, amount=5)`. `check` reads the handlers, not the Python, so a wrong argument name is found when the shell starts or reloads: the finding is `unknown-argument` (with the nearest name), and a required argument that no handler gives is `missing-argument`.
* **`validate_use(use)`** is called for each use when it is loaded and when its params change. Raise `ValueError` with a message to reject it: it is reported as `module-use` with the message, naming the file. Only `ValueError` is handled.
* **`use_added` / `use_removed`** tell the module that a use came or went: a surface that shows the module appeared or went away, for example after a reload that added or removed a use.
* **`self.ctx.announce(text)`** says a text through assistive technology, once, so a screen reader reads it. Nothing happens when none is connected.

## Using it

A shell file uses the module by its name, with the params as keys. A `Call` handler elsewhere can run its actions as `Module.action`:

```tdl
Tally { step: 5 }
Button { Text: "Reset all", On_Click { Action: Call, Target: "Tally.reset" } }
```

The whole folder, which is also tested to pass `check`:

<!-- BEGIN generated: example-set:12-modules/tally -->
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
# The module Tally is in Modules/Tally/. It is used like any other: its name, and its params as keys.
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
                            Tally { step: 1 }
                            Tally { step: 5, Tooltip: "Counts in fives" }
                            Spacer { }
                            Button { Text: "Reset all", On_Click { Action: Call, Target: "Tally.reset" } }
                            Clock { }
                        }
                    }
                }
            }
        }
    }
}
```

File `Modules/Tally/Tally_Module.py`:

```python
"""Tally: a counter. The class name is the module's Name."""

from __future__ import annotations

from tess_shell import Event, Module, action
from tess_shell.modules.context import UseRecord


class Tally(Module):
    def start(self) -> None:
        # one instance serves every use, so the counts are kept by use key
        self.counts: dict[str, int] = {}
        for use in self.ctx.uses.values():
            self.show(use.key)

    def validate_use(self, use: UseRecord) -> None:
        step = use.params.get("step", 1)
        if step < 1 or step != int(step):
            raise ValueError(f"step must be a whole number of 1 or more, not {step}")

    def use_added(self, use: UseRecord) -> None:
        self.show(use.key)

    def use_removed(self, use: UseRecord) -> None:
        self.counts.pop(use.key, None)

    @action
    def bump(self, event: Event, amount: float = 1) -> None:
        key = event.use
        self.counts[key] = self.counts.get(key, 0) + int(amount)
        self.show(key)

    @action
    def reset(self, event: Event) -> None:
        # a click on the module's own block names its use; a Call from another block names that
        # block's use, so then every use of the module is reset
        keys = [event.use] if event.use in self.ctx.uses else list(self.ctx.uses)
        for key in keys:
            self.counts[key] = 0
            self.show(key)
        self.ctx.announce("Tally reset")

    def show(self, key: str) -> None:
        count = self.counts.get(key, 0)
        self.ctx.send("count", count, use=key)
        self.ctx.send("text", f"Tally: {count}", use=key)
```

File `Modules/Tally/Tally_Module.tdl`:

```tdl
---
TDL: 0.2
Name: Tally
---
# A counter. A click adds `step`, a secondary click (right button) takes it back to 0. The Python
# sends `count` and `text`; the layout shows `text` and says it again as the accessible name.
Module {
    Params {
        step { Type: number, Default: 1 }
    }
    FlexBox {
        Name: Root
        Role: BUTTON
        Label: <| text |>
        Padding: [10, 4, 10, 4]
        On_Click { Action: bump, amount: <| params.step |> }
        On_Secondary_Click: reset
        Children {
            Text {
                Name: Face
                Text: <| text |>
            }
        }
    }
}
```

<!-- END generated: example-set:12-modules/tally -->

An action may also be run from outside, by the command line: `tesserae-shell call Tally bump 3` passes `3` as the first parameter after the event (`amount`), and prints what the action returns (`None` prints nothing special). A control call has no use: `event.use` is the empty string, which is why `reset` above treats "no use of mine" as "all of them". See [The command line](command-line.md).

## Testing it

```console
$ tesserae-shell check --config-dir ~/.config/tesserae-shell
ok: 2 files checked
```

`check` reads every TDL file as the shell does: your layout must parse, a use may name only the params the layout declares, and every key and enum word must exist. It does **not** run your Python, so it cannot tell you that the file has a syntax error, that a handler names an action the class lacks, or that a handler's arguments do not fit the method. Those are found when the shell loads the module, at start or at a reload, and come back as findings that name the Python file and the line.

So the loop is: edit, save, look at the log.

* A hand test: `tesserae-shell run` in a terminal, with the module in a Bar, and the log beside it. `self.ctx.log` is a [loguru](https://loguru.readthedocs.io/) logger bound to the module (`self.ctx.log.info("started")`). Raise the level with `tesserae-shell log-level DEBUG`.
* `tesserae-shell call Tally bump 3` runs an action without a click.

## Changing it while the shell runs

The shell watches the folder ([hot reload](configuration-folder.md#hot-reload)). What it does when you save:

* **The layout (`Tally_Module.tdl`) changed:** the module keeps running, its instance is kept, and `reload()` is called, if you wrote one. The layout is read again; the values you sent stay.
* **The Python (`Tally_Module.py`) changed:** the shell reads the new file first. If it fails to import, or has no class, or has two, the old instance **keeps running** and the error is reported. If it loads, the old instance's `stop()` is called, its timers and subscriptions are cancelled, and a new instance is created and started. The values the old one sent stay until the new one sends. Your own state in the old object is gone, so keep what must survive a reload in a file.
* **Any file has an error:** nothing is applied; the shell shows what it showed.

The shell calls `stop()` when it quits, before a code reload and when the module has no use left. It stops the module's `on_tick` subscriptions and its service subscriptions, but it does **not** stop a thread you started: stop your own threads and close your own files and connections in `stop()`.

## Slow work and threads

Everything the shell calls on a module (`start`, an action, a tick) runs on the one loop thread that also draws and answers the pointer. A callback that is slow holds up the whole screen:

* over 4 ms is a debug line with the module's name; more than 100 of those in a minute is the warning `slow-module`;
* an action over 50 ms is logged as a warning (`took N ms on the loop`).

Do slow work (a network call, a big file) in a thread you start, and send the result with `self.ctx.send`, which is safe from a thread. If the result must touch something that is for the loop thread only (open a Popup, say), hand a function to the loop with `self.ctx.call_soon(fn)`. A thread's exception is yours to catch: the shell does not see it. More than 16 live threads that run your file's code give the warning `many-threads`.

```python
import threading
import urllib.request

from tess_shell import Module, action


class Weather(Module):
    @action
    def refresh(self, event):
        threading.Thread(target=self.fetch, daemon=True).start()

    def fetch(self):                      # a thread of its own: it may block
        try:
            with urllib.request.urlopen("https://example.org/temperature", timeout=5) as r:
                text = r.read().decode().strip()
        except OSError as exc:
            self.ctx.log.warning(f"fetch failed: {exc}")
            return
        self.ctx.send("temperature", text)   # safe from any thread
```

For timers the shell has one shared clock: `self.ctx.on_tick("second", fn)` or `("minute", fn)` calls `fn` at the start of each second or minute, on the loop thread, and costs nothing while nobody has subscribed. There is no other timer in the context; use `threading.Timer` or a thread with a wait for anything else, and send from it.

The context also reaches D-Bus, the sound server, icons, the tray, the window list, the application index, Popups, surfaces and shortcut mode; they are in the [reference](../api/module-api.md#the-context).

## What the shell does with your Python

* **It raises in `start`, `use_added`, `use_removed` or `reload`:** that module alone is marked failed, with its name and UID in the log and the line in your file. The others keep running and its surfaces keep their last values. The shell starts it again, from the file as it then is, after 1, 2, 4, 8 and 16 seconds (never more than 60 in one wait, at most five tries); a module that fails every time stays failed until a reload, and a reload gives it five new tries.
* **An `@action`, a tick callback or a `call_soon` callback raises:** logged with the module's name, the event and the block's position; the module is **not** failed and the event is not repeated.
* **It hangs** (an action that loops, a `time.sleep` in a callback): the loop is blocked, and a thread that watches it names the culprit. After 2 seconds the log has `loop stalled for 2 s: module Tally, entry point bump, running for N s`, with the traceback of every thread, again every 5 seconds. After 10 seconds, under the `systemd` unit `install-session` writes, the shell is restarted; by hand, nothing can restart it and the log says so. After three unclean starts in a row the next start is a **safe start** that does not run the Python of your modules (it names them) until you fix the file and run `tesserae-shell reload`. All of this is in [When the shell hangs or crashes](troubleshooting.md#when-the-shell-hangs-or-crashes).
* **It runs as you.** A module's Python is not isolated from the shell or from your files: it can read what you can read and start what you can start. Write modules yourself or read them before you add them, and keep the folder writable by you only; the shell warns (`insecure-permissions`) when it is not. A file named in a module's layout (a `Style:`, an image) must be inside your configuration folder. The shell loads a module's `.py` by its path and does not put your folder or the module's folder on `sys.path`, so a helper file beside it is not importable by name; keep the module in one file, or read a neighbour through `Path(__file__).parent`. [Security](security.md) has the whole model.

Next: the [module API reference](../api/module-api.md).
