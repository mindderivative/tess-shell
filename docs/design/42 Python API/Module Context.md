---
title: Module Context
aliases: [ctx, Module ctx API]
type: api
status: review
owner: phil
created: 2026-10-26
updated: 2026-11-17
tags: [api, needs-verification]
---

# Module Context

> [!NOTE]
> The context (`self.ctx`) is a module's whole view of the shell. It gives the module its configuration, its identity, a logger, the entry point that sends values, helpers for threads, timers and D-Bus, and a read-only view of TDL files ([ADR-0014 Shell File Language](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md)). A module touches nothing else in the shell. Members marked **decided** come from the ADRs; the rest are proposed. Names are not final.

## Members

| Member                                             | Does                                                                                                                                                              | Status                                                                                                     |
|----------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------|
| `ctx.name`                                         | The module's `Name:` from the metadata block of its TDL file (required; the word a use is called by and the root of the file's path; [TDL Language > Names and the Registry](../41%20TDL%20Reference/TDL%20Language.md#names-and-the-registry))                                                                                                                     | Decided ([ADR-0007 Shell UI Layer > Config directory and registry (2026-10-25)](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md#config-directory-and-registry-2026-10-25))                                                          |
| `ctx.uid`                                          | The module file's UID (UUIDv7)                                                                                                                                    | Decided                                                                                                    |
| `ctx.config`                                       | The module's TDL keys and values, read-only, including any extra metadata keys the author added to the metadata block (the shell ignores them; [ADR-0014 Shell File Language > Layout Rules](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#layout-rules), item 14) | Decided ("its YAML values", now TDL)                                                                                |
| `ctx.tdl(ref=None)`                                | A read-only view of a TDL file by file name, unique name or UID; default is the module's own, metadata included. Lets the Python read the rest of the file's keys, tokens and so on. Was `ctx.yaml` before D14 ([ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)) | Decided ([ADR-0007 Shell UI Layer > Modules (2026-10-25)](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md#modules-2026-10-25), D14); shape of the view open ([Open Questions](#open-questions)) |
| `ctx.log`                                          | A logger bound with the module's name and UID                                                                                                                     | Decided that a logger is given; the library is open ([Logging with Loguru](../90%20Research/Logging%20with%20Loguru.md))              |
| `ctx.send(key, value, use=None)`                   | Send a value to the shell. Thread-safe, coalesced, never blocks                                                                                                   | Decided that an entry point exists; signature proposed                                                     |
| `ctx.uses`                                         | The places this module is used, keyed `<Module>@<uid>` (for example `Clock@<uid>`); each record has the use's `Name:`, monitor, UID and `params`                  | Key form decided ([ADR-0014 Shell File Language > Layout Rules](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#layout-rules), item 12); Python always gets and passes back this key (D23, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)); record shape proposed |
| `ctx.dbus`                                         | A helper over the shared `dbus-fast` service thread                                                                                                               | Decided that it exists ([ADR-0009 D-Bus Client Library](../30%20Decisions/ADR-0009%20D-Bus%20Client%20Library.md)); shape proposed                           |
| `ctx.announce(text, *, politeness='polite', use=None)` | Say one message to a screen reader through `Window.announce` ([TRE-REQ-021 Announce Without a Node](../80%20Requests/TRE-REQ-021%20Announce%20Without%20a%20Node.md)), on the window of the use; with no `use` it is said for the module's first use on an open window, so a module on two Bars is read once. Thread safe (it hops to the loop); the same text twice running is said twice; works for a hidden block; empty text or a politeness other than `polite` or `assertive` raises `ValueError`. Built in `tess-shell` PR #56 (code session's report, 2026-11-17) | Built |
| `ctx.thread(fn, ...)`                              | Start a thread that catches and logs its exceptions and is joined on `stop`                                                                                       | Proposed                                                                                                   |
| `ctx.every(seconds, fn)`, `ctx.after(seconds, fn)` | Timers that run `fn` on the loop thread                                                                                                                           | Proposed                                                                                                   |
| `ctx.on_tick(unit, fn)`                            | Subscribe to the shell's shared time source (`second` or `minute`)                                                                                                | Decided that a shared source exists (2026-10-27); shape proposed ([A shared time source](#a-shared-time-source)) |
| `ctx.data_dir`                                     | The module's folder, `Modules/<module_name>/`                                                                                                                     | Proposed                                                                                                   |
| `ctx.state_dir`                                    | A writable folder for the module's own state, under the shell's config directory                                                                                  | Proposed                                                                                                   |

## Sending Values

```python
self.ctx.send("time", "14:05")                       # to every use
self.ctx.send("text", "Hello", use=self.ctx.uses[use_key])       # to one use; use_key is "Label@<uid>" (the code also takes the key string itself, as built in M2a)
```

- **Keys** are strings. A view reads them as `<module name>.<key>` in an expression ([Module Contract > Integration](Module%20Contract.md#integration)).
- **Values** are plain Python values ([Value Types and Conversion](Value%20Types%20and%20Conversion.md)).
- **Coalescing.** Sending the same key many times keeps only the latest value; the loop applies it once per turn ([Process Model and Threading > Handing a value to the loop (proposed)](../20%20Architecture/Process%20Model%20and%20Threading.md#handing-a-value-to-the-loop-proposed)).
- **One call, one key, one value.** `ctx.send(key, value, use=None)` takes a single key and a single value. It is not a list of values for the uses: to give three uses three different values, call it three times, once per use.
- **Per use.** One module instance serves every use. When uses must differ, as in the maintainer's `Label_Module` example, the module decides what each use shows and sends it with `use=`. The values it receives from each use are its `params`. A `use` is one of `ctx.uses`. Sending with no `use` reaches every use.
- **Order.** Values from one module keep their order per key; the flush applies the keys of one turn together.

## Uses

A use is a place where the module is referenced in a shell file: a block with the module's name as its head, such as `Label { Name: Top_Label }` ([TDL Language > Names and the Registry](../41%20TDL%20Reference/TDL%20Language.md#names-and-the-registry)). It is not a copy of the module: there is one module instance for all its uses.

`ctx.uses` is a read-only mapping from each use's instance key to a use record. The key is the module name and the use's UID, `Label@<uid>` ([ADR-0014 Shell File Language > Layout Rules](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#layout-rules), item 12). The shell keeps the UID in the registry; it writes `UID:` into the use in the file only when the user asks for stable identity across reordering. A use record has the use's `name` (its `Name:`), its `uid`, the `monitor` it is on, and its `params` (the values written in that use for the module's declared `Params`). The shell calls optional hooks when uses change:

```python
def use_added(self, use): ...      # a surface showing this module appeared
def use_removed(self, use): ...    # a surface went away (monitor unplugged, file edited)
```

This lets a module follow monitors coming and going ([Data Flow > Monitor hot-plug](../20%20Architecture/Data%20Flow.md#monitor-hot-plug)) without polling. #needs-verification: whether hooks or an event stream is the better shape.

## Example: the Label Module

The maintainer's example (2026-10-26), which replaced an earlier example of mine that treated a module as a data source for widgets in a bar. A module has three parts: a layout TDL file, a style TDL file and a Python file ([ADR-0007 Shell UI Layer > What a module is (2026-10-26)](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md#what-a-module-is-2026-10-26)). The files are reproduced as the maintainer gave them in YAML, converted to TDL on 2026-10-29 and revised on 2026-10-30 to the header without a file-type key and a root block that names the file type (`Module { }`, `Style { }`, `Shell { }`; [ADR-0014 Shell File Language > Second-Sketch Decisions (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#second-sketch-decisions-2026-10-30)) without changing what they say. The maintainer notes it is only an example and may not work exactly like this.

`Modules/Label/Label_Module.tdl`: the layout and the data positioning

```
---
TDL: 0.2
TEL: 0.1
TRE: 0.5.9
Shell: 0.1
Name: Label        # the call name: a use is written Label { }
---

Module {
    Style: Label_Style.tdl
    Params {
        text { Type: string }
    }

    FlexBox {
        Name: Label_Module_FlexBox
        Alignment: HORIZONTAL
        Width: 120
        Height: 34
        Align_Content: CENTER
        Justify_Content: MIDDLE
        Children {
            Icon {
                Name: Monitor_Icon   # Optional
                Icon: monitor.svg
            }
            Text {
                Name: Label_Text
                Class: text_style
            }
        }
    }
}
```

`Modules/Label/Label_Style.tdl` (named `Label_Style.py` in the message; its content is a style file): the look and feel

```
---
TDL: 0.2
TEL: 0.1
TRE: 0.5.9
Shell: 0.1
Name: Label_Style
---

Style {
    Classes {
        text_style {
            Kind: Text
            Font_Size: 16
            Font_Weight: 500
            Foreground: "#ffffff"   # or "#fffffff0" or rgba(255 255 255 1.0)
        }
    }

    Icon {
        Foreground: "#ffffff"       # or "#fffffff0" or rgba(255 255 255 1.0)
        Fill: "#00000000"           # or rgba(255 255 255 0.0)
    }

    FlexBox {
        Background: "#000000"       # or "#000000f0" or rgba(0 0 0 1.0)
        Border_Width: [2, 2, 2, 2]
        Border_Color: "#ffffff"
        Corner_Radius: [8, 8, 8, 8]
    }

    Text {
        Font_Family: ["Hack Nerd Font Mono", "JetBrains Mono"]
    }
}
```

The maintainer's four-sided and font-list shorthand `{2, 2, 2, 2}` and `{"Hack Nerd Font Mono", "JetBrains Mono"}` is written as lists here, because `{ }` is a block in TDL ([ADR-0014 Shell File Language > What TDL Is (Decided)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#what-tdl-is-decided), item 15). The colours use the TDL forms, quoted hex or space-separated `rgba(...)` ([Value Types and Conversion > Colour and Length Literals in TDL](Value%20Types%20and%20Conversion.md#colour-and-length-literals-in-tdl)). The `"#fffffff0"` in the comment is as the maintainer wrote it (nine digits). The brace shorthand is not defined in TDL; a four-sided value is one number, a list of four or a block of named sides (D7, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)).

`Modules/Label/Label_Module.py`: the logic

```python
import json
from tess_shell import Module, action

# The example opened and parsed its own layout file here with a YAML loader.
# The shell already holds the parsed tree, so the Python asks the context
# (self.ctx.tdl(), see Members) instead of opening the file.
text_name = "Label_Text"   # the Name: of the Text block in Label_Module.tdl

class Label(Module):
    def start(self):
        for use in self.ctx.uses.values():
            self.show(use)

    def use_added(self, use):          # a bar showing this module appeared
        self.show(use)

    def use_removed(self, use):        # a bar went away (monitor unplugged, file edited)
        pass

    def show(self, use):
        # Three places the text can come from, tried in order.
        text = (use.options.get("top_label")      # 1. the "top_label:" written in this use in the shell file
                or self.saved().get(use.name)     # 2. the module's own file, keyed by the use's Name:
                or f"Screen {use.monitor}")       # 3. a default the module computes
                or f"${text_name}"                # 4. get text widget param by name
        self.ctx.send("text", text, use=use)      # the key is always "text"; only this use gets this value

    @action
    def rename(self, use_key, text):              # a shell-file event can call this (key names: 41 TDL Reference)
        use = self.ctx.uses[use_key]               # use_key is the "Label@<uid>" key from ctx.uses (D23)
        saved = self.saved()
        saved[use.name] = text                     # e.g. {"Side_Label": "Mail"}
        (self.ctx.state_dir / "labels.json").write_text(json.dumps(saved))
        self.show(use)                             # send the new text to that one use

    def saved(self):
        path = self.ctx.state_dir / "labels.json"
        return json.loads(path.read_text()) if path.exists() else {}
```

`RootShell_Shell.tdl`: a surface places the module and passes params

```
---
TDL: 0.2
TEL: 0.1
TRE: 0.5.9
Shell: 0.1
Name: RootShell        # the root of the path: RootShell.DP1.Top_Bar
---

Shell {
    Monitor {
        Name: DP1          # an identifier; the connector is a value below
        Connector: DP-1
        Children {
            Bar {
                Name: Top_Bar
                Edge: TOP
                Width: EXPAND
                Height: 34
                Children {
                    Label {
                        Name: Top_Label
                        text: "Work"            # param name as the module declared it (D18)
                    }
                    # the head Label is the module's Name:; the use's own unique name is its Name:
                }
            }
            Bar {
                Name: Side_Bar
                Edge: LEFT
                Width: 120
                Height: EXPAND
                Children {
                    Label {
                        Name: Side_Label
                        text: <| "label.text" |>
                    }
                }
            }
        }
    }
}
```

The bar geometry (`Edge`, `Width`, `Height`) was not in the maintainer's example; it is added so the file is a complete shell ([Bar](../40%20Specifications/Surfaces/Bar.md)). The paths of the two uses are `RootShell.DP1.Top_Bar.Top_Label` and `RootShell.DP1.Side_Bar.Side_Label` ([TDL Language > The Metadata Block](../41%20TDL%20Reference/TDL%20Language.md#the-metadata-block)).

### How the Pieces Fit (My Reading, for the Maintainer to Correct)

1. A surface lists modules under `Children`, each a block headed by the module's `Name:` (`Label`) with its own unique `Name:` (`Top_Label`, `Side_Label`) and the params it passes (`text: "Work"`).
2. The shell finds the module's TDL file through the registry and checks the passed params against its `Params` declaration (`text` is a string). Param names are written as the module declared them (D18, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)).
3. The shell builds the module's widgets (a `FlexBox` holding an `Icon` and a `Text`) inside the surface, and applies the style file named by `Style:`. The `Class: text_style` on the `Text` picks up the `text_style` class.
4. The Python class is created once. For each use it gets a `use` record, keyed `Label@<uid>`: the use's `Name:`, its monitor and its params.
5. The Python sends values (`ctx.send("text", ..., use=use)`). The module's expressions, written in its layout TDL file, place those values into widgets.

### Points the Example Raises

| Point                      | Note                                                                                                                                                                                                                                                                                                                                                              |
|----------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Reading the module's TDL file | The example opened `Label_Module.yaml` itself with a YAML loader and indexed into it. `ctx.tdl()` ([Members](#members)) exists for this: the shell already knows the path and the parsed tree, so the Python needs neither `open` nor a working directory. The index `data["FlexBox"][8]...` was the example's shorthand for "find the widget whose `Name:` is `Label_Text`"; how a view of the TDL tree finds a block by `Name:` is open ([Open Questions](#open-questions)) |
| Options or params          | **Decided:** `use.params` ("params matches the file", said of YAML before ADR-0014). The example's `use.options.get("top_label")` reads the entry's value for the param, which is `use.params["text"]`                                                                                                                                                                                          |
| The fourth source          | `f"${text_name}"` asks for the text widget's name, so the module can address a widget by `Name:`                                                                                                                                                                                                                                                                  |
| The text in the widget     | The `Text` widget has no `text:` expression in the example. How the sent value or the param reaches it is the first open item in [ADR-0007 Shell UI Layer > Open items](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md#open-items)                                                                                                                                                                                          |
| `text: <\| "label.text" \|>` | In the `Side_Label` use, a param bound to the module's own sent value. What `label.text` resolves to for that use is part of the same open item                                                                                                                                                                                                                 |
| `Children` entries         | **Decided:** the block head is the type (`Text { Name: Label_Text }`), with no `Block:` or `widget:` key ([ADR-0014 Shell File Language > Layout Rules](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#layout-rules), item 6). The same block or module name may repeat in one `Children { }`, ordered by position (`Text_1`, `Text_2`; [TDL Language > Names and the Registry](../41%20TDL%20Reference/TDL%20Language.md#names-and-the-registry))                                                |
| Style syntax               | `{2, 2, 2, 2}` is the maintainer's list shorthand for four sides. PyYAML read it as `{2: None}` (2026-10-26), and in TDL `{ }` is a block, so the examples write `[2, 2, 2, 2]`. No brace shorthand is defined (D7, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)). The colour forms are in [Value Types and Conversion](Value%20Types%20and%20Conversion.md)                          |
| File type                  | **Decided (D26):** the root block names it (`Module { }`, `Style { }`, `Shell { }`); the metadata block has no file-type key. The root block must agree with the suffix                                                                                                                                                                                                              |

## Calling a Popup

A module can call a popup ("Calls" in the flow diagram, [Shell Structure](../20%20Architecture/Shell%20Structure.md)). The popup is a `Popup { Name: ... }` block in the shell file; the module asks the shell to open it. Decided (2026-10-26): many modules can call one popup, and the popup must know what called it so its data fits the caller.

The maintainer's suggested shape passes `self`:

```python
@action
def open_menu(self, popup_name, anchor):
    self.ctx.popup(self, popup_name).open(anchor_rect=anchor)
```

A problem with `self` alone. One module instance serves every use. `self` says *which module* called but not *which use* (which surface, which monitor, which params). The popup's parent is the surface that holds the calling use, and it must open on that monitor. So the caller also has to carry the use. Options:

| Option                                      | Shape                                                                                                                                                        | Notes                                                                                                                    |
|---------------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------------|
| A. The shell supplies the use to the action | An action called from a widget receives the calling `use` (as `use` or on `self.ctx.caller`) automatically, because the shell knows which widget was clicked | The module writes `self.ctx.popup(popup_name)` and the shell fills in the caller. Least code in the module (recommended) |
| B. The module passes the use                | `self.ctx.popup(popup_name, caller=use)`                                                                                                                     | Explicit; the module must keep the `use`                                                                                 |
| C. The maintainer's form                    | `self.ctx.popup(self, popup_name)`                                                                                                                           | Identifies the module only; works for a module with a single use                                                         |

What the popup sees: a `caller` record: the calling module's name and UID, the use (name, monitor, params), the anchor rectangle, and an optional `data` mapping the module passes (for example which tray item). Expressions in the popup read `caller.<field>`; the popup's own modules receive it as params.

- The popup's parent is the surface that holds the calling use, so it opens on that monitor only ([Surface Types > Open questions](../40%20Specifications/Surfaces/Surface%20Types.md#open-questions)).
- The caller passes the anchor rectangle (the clicked icon), in its surface's coordinates.
- Focus is a setting on the popup entry, not a call argument. It is on by default (decided 2026-10-26); tooltip-like popups opt out.
- Decided (maintainer, 2026-10-26): option A. The shell supplies the calling use to the action automatically, so the module writes `self.ctx.popup(popup_name)`. Open: whether the call is a method on the context or an action the shell file can declare directly.

## D-Bus Helper

Over `dbus-fast` on the shared asyncio service thread ([ADR-0009 D-Bus Client Library](../30%20Decisions/ADR-0009%20D-Bus%20Client%20Library.md)). As built in M5a (the code session's report, 2026-11-12, not run in the vault; the code is `tess_shell.services`):

```python
bus = self.ctx.dbus.session()            # or .system(); nothing connects until first use
proxy = bus.proxy("org.freedesktop.UPower", "/org/freedesktop/UPower/devices/DisplayDevice",
                  "org.freedesktop.UPower.Device")          # interface optional here, or per call
# on the loop thread, return at once (the work is posted to the dbus thread):
sub = proxy.on_property_changed(cb, initial=True)   # cb(changed: Mapping[str, Any]) on the dbus thread
sub = proxy.on_signal("Changed", cb)                # cb(*body) on the dbus thread; sub.cancel()
# coroutines on the dbus thread:
await proxy.get("Percentage", fresh=False)          # the cache; fresh=True asks the service
await proxy.call("SetProfile", ["balanced"], "s", timeout=5.0)   # reply: value, None or tuple
# from anywhere:
fut = bus.run(proxy.call(...))                      # a concurrent.futures.Future, never blocks
bus.run_blocking(proxy.call(...), timeout=None)     # BlockingCallError on the loop thread and the dbus thread
bus.state("org.freedesktop.UPower")                 # a ServiceState
self.ctx.dbus.available                             # bool: every service of this module is present
def on_service_lost(self, name): ...                # loop thread
def on_service_found(self, name): ...               # loop thread
```

- `on_property_changed` first calls back with every property (unless `initial=False`), then with what `PropertiesChanged` reports; when a service returns after leaving, the callback gets every property again, before `on_service_found`.
- Callbacks run on the service thread, are short, never block, and call `ctx.send`, which crosses to the loop. A callback over 50 ms is logged with the module name.
- A call takes the D-Bus signature of its arguments (no introspection). A call to a service with no owner raises `ServiceUnavailable` (maintainer, 2026-11-12, as recommended).
- The errors are `ServiceTimeout`, `ServiceUnavailable` and `ServiceError`; they and `ServiceState` and `BlockingCallError` are exported from `tess_shell`.
- `available` is sent with `ctx.send("available", bool)` to every use when the AND over the module's services changes. A module that needs more (Battery `IsPresent`) sends a key of its own and combines it in its layout, and does not send `available` itself.
- `bus.watch_prefix(prefix, on_added, on_removed)` follows every bus name that starts with a prefix (one `ListNames` and one `NameOwnerChanged` rule by namespace, shared, listed again after a reconnect); the callbacks run on the dbus thread. `bus.forget(name)` stops watching a name the module no longer needs, so names that come and go (a browser's player per instance) do not pile up. Built in M5d for the Media module (code session's report, 2026-11-13).
- No call takes a bus name, exports an object or owns anything.
- `ctx.thread` does not exist yet; `bus.run` from an `@action`, or a thread of the module's own, serves until it does.
- A module may use another D-Bus library on its own thread; the helper is a recommendation.

## Timers and Threads

- `ctx.every` and `ctx.after` run on the loop thread; use them only for short work. They use tre's timers (`window.after`, `window.every`), which do not wake the loop without a reason ([Process Model and Threading > Performance notes](../20%20Architecture/Process%20Model%20and%20Threading.md#performance-notes)).
- `ctx.thread(fn)` is for blocking work. An exception is logged with the module's name. The shell joins it on `stop` with a timeout.

## A Shared Time Source

Decided 2026-10-27: the shell offers a shared time source, so modules that show or use the time tick together instead of each running its own timer ([Clock Module](../40%20Specifications/Modules/Clock%20Module.md)). Shape proposed:

```python
handle = self.ctx.on_tick("minute", self.tick)   # "second" or "minute"
handle.cancel()                                  # the shell also cancels it on stop
```

- The callback runs on the loop thread, at the start of each second or minute of the wall clock, for every subscriber in one batch.
- The shell computes the next boundary from the wall clock each time, so a sleep, a resume or a manual time change corrects itself within one tick.
- A shell with no module subscribed to `second` runs no one-second timer.
- The unit is a closed set (`second`, `minute`); finer timing uses `ctx.every`.

## What the Context Does Not Give

- tre nodes, windows or surfaces.
- Other modules' data (a module that needs another's values reads its own source).
- The registry or the config loader.
- A way to call TEL directly (expressions are written in shell files).
- The TDL parser. The context gives a parsed, read-only view, not the means to parse or write a shell file.

## Open Questions

- [x] M2: `ctx.send(key, value)` takes one key and one value (G4); a dict form can come later.
- [x] `ctx.uses` is a mapping from `<Module>@<uid>` to the use, as in the example (G4).
- [ ] Can a module send to a specific monitor? Context: deferred past M2; no M2 module needs it. Recommendation: not before a module needs it.
- [ ] Is `ctx.state_dir` needed, or is `ctx.data_dir` enough? Context: deferred past M2; the Clock needs neither. Recommendation: offer only `ctx.data_dir` until a module needs a separate state directory.
- [ ] What does `ctx.tdl()` return for imported files and for values that are TEL expressions: the raw text or the evaluated value? Context: a module reads data, not syntax. Recommendation: the evaluated value, with the raw text reachable through the tree view.
- [x] The name `ctx.yaml` is renamed `ctx.tdl` (D14, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)).
- [ ] What shape does the read-only view of the TDL tree have: does it support lookup by `Name:`, and does it expose comments? Context: D12 ([ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)) fixes the tree as an ordered list of entries (head, properties, children) that keeps repeated names, with the metadata block read first. Recommendation: offer lookup by `Name:` and do not expose comments.
- [x] The brace shorthand `{2, 2, 2, 2}` is not defined; the three forms of D7 stand ([ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)).
- [x] M2: ticks come from one shared wall-clock source scheduled to the next second or minute boundary; a module's tick subscriptions end on `stop()` and on a replacement of its instance (G4).
- [x] Param names written on a use stay as the module declared them (D18, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)).
- [x] An action names a use by the `Label@<uid>` key from `ctx.uses` (D23, [ADR-0014 Shell File Language > Decisions on the Open Items (2026-10-30)](../30%20Decisions/ADR-0014%20Shell%20File%20Language.md#decisions-on-the-open-items-2026-10-30)).

## Acceptance Criteria

- [ ] A module reads its own keys through `ctx.config` and another file through `ctx.tdl(ref)` by name, UID and file name, and reaches each of its uses by `<Module>@<uid>`.
- [ ] `ctx.send` from a thread reaches the loop in one turn and coalesces repeated sends.
- [ ] A module sends different text to two uses of the same module file.
- [ ] A module is told when a use appears and when it goes away.
- [ ] A D-Bus signal handled through `ctx.dbus` reaches a view without blocking the loop.
- [ ] An exception in a `ctx.thread` function is logged with the module's name.

## Links

- [42 Python API](42%20Python%20API.md) · [Module Contract](Module%20Contract.md) · [Value Types and Conversion](Value%20Types%20and%20Conversion.md) · [ADR-0007 Shell UI Layer](../30%20Decisions/ADR-0007%20Shell%20UI%20Layer.md)
