---
title: Module Context
aliases: [ctx, Module ctx API]
type: api
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-26
tags: [api, needs-verification]
related: ["[[42 Python API]]", "[[Module Contract]]", "[[Value Types and Conversion]]", "[[ADR-0009 D-Bus Client Library]]"]
depends_on: ["[[Module Contract]]"]
---

# Module context

> [!summary]
> The context (`self.ctx`) is a module's whole view of the shell. It gives the module its configuration, its identity, a logger, the entry point that sends values, helpers for threads, timers and D-Bus, and a read-only view of YAML files. A module touches nothing else in the shell. Members marked **decided** come from the ADRs; the rest are proposed. Names are not final.

## Members

| Member | Does | Status |
|---|---|---|
| `ctx.name` | The module's `name:` from its YAML (required) | Decided ([[ADR-0007 Shell UI Layer#Config directory and registry (2026-10-25)]]) |
| `ctx.uid` | The module file's UID (UUIDv7) | Decided |
| `ctx.config` | The module's YAML keys and values, read-only | Decided ("its YAML values") |
| `ctx.yaml(ref=None)` | A read-only view of a YAML file by file name, unique name or UID; default is the module's own. Lets the Python read the rest of the file's keys, tokens and so on | Decided ([[ADR-0007 Shell UI Layer#Modules (2026-10-25)]]); shape proposed |
| `ctx.log` | A logger bound with the module's name and UID | Decided that a logger is given; the library is open ([[Logging with Loguru]]) |
| `ctx.send(key, value, use=None)` | Send a value to the shell. Thread-safe, coalesced, never blocks | Decided that an entry point exists; signature proposed |
| `ctx.uses` | The places this module is used: each with the entry's unique name, monitor, UID and `params` | Proposed |
| `ctx.dbus` | A helper over the shared `dbus-fast` service thread | Decided that it exists ([[ADR-0009 D-Bus Client Library]]); shape proposed |
| `ctx.thread(fn, ...)` | Start a thread that catches and logs its exceptions and is joined on `stop` | Proposed |
| `ctx.every(seconds, fn)`, `ctx.after(seconds, fn)` | Timers that run `fn` on the loop thread | Proposed |
| `ctx.data_dir` | The module's folder, `Modules/<module_name>/` | Proposed |
| `ctx.state_dir` | A writable folder for the module's own state, under the shell's config directory | Proposed |

## Sending values

```python
self.ctx.send("time", "14:05")                       # to every use
self.ctx.send("text", "Hello", use=self.ctx.uses["bar_label"])   # to one use
```

- **Keys** are strings. A view reads them as `<module name>.<key>` in an expression ([[Module Contract#Integration]]).
- **Values** are plain Python values ([[Value Types and Conversion]]).
- **Coalescing.** Sending the same key many times keeps only the latest value; the loop applies it once per turn ([[Process Model and Threading#Handing a value to the loop (proposed)]]).
- **One call, one key, one value.** `ctx.send(key, value, use=None)` takes a single key and a single value. It is not a list of values for the uses: to give three uses three different values, call it three times, once per use.
- **Per use.** One module instance serves every use. When uses must differ, as in the maintainer's `Label_Module` example, the module decides what each use shows and sends it with `use=`. The values it receives from each use are its `params`. A `use` is one of `ctx.uses`. Sending with no `use` reaches every use.
- **Order.** Values from one module keep their order per key; the flush applies the keys of one turn together.

## Uses

A use is a place where the module is referenced in a shell file (an entry such as `top_label`). It is not a copy of the module: there is one module instance for all its uses.

`ctx.uses` is a read-only mapping from each entry's unique name to a use record. A use record has the entry's `name`, its `uid`, the `monitor` it is on, and its `params` (the values written in that entry for the module's declared `params:`). The shell calls optional hooks when uses change:

```python
def use_added(self, use): ...      # a surface showing this module appeared
def use_removed(self, use): ...    # a surface went away (monitor unplugged, file edited)
```

This lets a module follow monitors coming and going ([[Data Flow#Monitor hot-plug]]) without polling. #needs-verification: whether hooks or an event stream is the better shape.

## Example: the Label module

The maintainer's example (2026-10-26), which replaced an earlier example of mine that treated a module as a data source for widgets in a bar. A module has three parts: a layout YAML, a style YAML and a Python file ([[ADR-0007 Shell UI Layer#What a module is (2026-10-26)]]). The files are reproduced as given. The maintainer notes it is only an example and may not work exactly like this.

**`Modules/Label/Label_Module.yaml`**: the layout and the data positioning

```yaml
shell: v1
type: Module
name: label
style: Label_Style.yaml
params:
    text: {type: string}

FlexBox:
    name: Label_Module_FlexBox
    alignment: horizontal
    width: 120
    height: 34
    align_content: center
    justify_content: middle
    children:
        Icon:
            name: Monitor_Icon   # Optional
            icon: monitor.svg
        Text:
            name: Label_Text
            class: text_style
```

**`Modules/Label/Label_Style.yaml`** (named `Label_Style.py` in the message; its content is YAML): the look and feel

```yaml
shell: v1
type: Style

classes:
    text_style:
        kind: Text
        size: 16
        weight: 500
        foreground: "#ffffff" # or | "#fffffff0" | RGBA(255, 255, 255, 1.0)

Icon:
    foreground: "#ffffff" # or | "#fffffff0" | RGBA(255, 255, 255, 1.0)
    fill: "#00000000" # or RGBA(255, 255, 255, 0.0)

FlexBox:
    background: "#000000" # or | "#000000f0" | RGBA(0, 0, 0, 1.0)
    border: true
    border_thickness: {2, 2, 2, 2}
    border_color: "#ffffff"
    corner_radius: {8, 8, 8, 8}

Text:
    font_family: {"Hack Nerd Font Mono", "JetBrains Mono"}
```

**`Modules/Label/Label_Module.py`**: the logic

```python
import json, yaml
from tesserae_shell import Module, action

with open('Label_Module.yaml', 'r') as file:
    data = yaml.safe_load(file)

module_name = data.get("name")  # for reference or passing to shell
text_name = data["FlexBox"][8]["Text"][0]["name"]

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
        text = (use.options.get("top_label")      # 1. the "top_label:" written in this use's entry in the shell file
                or self.saved().get(use.name)     # 2. the module's own file, keyed by the entry's unique name
                or f"Screen {use.monitor}")       # 3. a default the module computes
                or f"${text_name}"                # 4. get text widget param by name
        self.ctx.send("text", text, use=use)      # the key is always "text"; only this use gets this value

    @action
    def rename(self, use_name, text):             # a shell-file event can call this (key names: 41 YAML Reference)
        saved = self.saved()
        saved[use_name] = text                     # e.g. {"side_label": "Mail"}
        (self.ctx.state_dir / "labels.json").write_text(json.dumps(saved))
        self.show(self.ctx.uses[use_name])         # send the new text to that one use

    def saved(self):
        path = self.ctx.state_dir / "labels.json"
        return json.loads(path.read_text()) if path.exists() else {}
```

**`DP1_Shell.yaml`**: a surface places the module and passes params

```yaml
shell: v1
type: Shell

root:
    name: dp1_root
    monitor: DP-1
    children:
        top_bar:
            kind: bar
            modules:
                top_label:
                    module: Label_Module.yaml
                    text: "Work"
        side_bar:
            kind: bar
            modules:
                side_label:
                    module: Label_Module.yaml
                    text: {{ "label.text" }}
```

### How the pieces fit (my reading, for the maintainer to correct)

1. A surface lists modules under `modules:`, each with a unique name (`top_label`, `side_label`) and the `params` it passes (`text: "Work"`).
2. The shell loads the module YAML and checks the passed params against its `params:` declaration (`text` is a string).
3. The shell builds the module's widgets (a `FlexBox` holding an `Icon` and a `Text`) inside the surface, and applies the style file named by `style:`. The `class: text_style` on the `Text` picks up the `text_style` class.
4. The Python class is created once. For each use it gets a `use` record: the entry's name, its monitor and its params.
5. The Python sends values (`ctx.send("text", ..., use=use)`). The module's expressions, written in its layout YAML, place those values into widgets.

### Points the example raises

| Point | Note |
|---|---|
| Reading the module's YAML | The example opens `Label_Module.yaml` itself and indexes into it. `ctx.yaml()` ([[#Members]]) exists for this: the shell already knows the path and the parsed tree, so the Python needs neither `open` nor a working directory. The index `data["FlexBox"][8]...` is the example's shorthand for "find the widget named `Label_Text`" |
| Options or params | **Decided:** `use.params` ("params matches the YAML"). The example's `use.options.get("top_label")` reads the entry's value for the param, which is `use.params["text"]` |
| The fourth source | `f"${text_name}"` asks for the text widget's name, so the module can address a widget by `name:` |
| The text in the widget | The `Text` widget has no `text:` expression in the example. How the sent value or the param reaches it is the first open item in [[ADR-0007 Shell UI Layer#Open items]] |
| `text: {{ "label.text" }}` | In the `side_label` entry, a param bound to the module's own sent value. What `label.text` resolves to for that use is part of the same open item |
| `children:` keys | **Decided:** `Text:` and `widget: Text` mean the same; where a type repeats, a unique-name key with `widget: Text` inside |
| Style syntax | `{2, 2, 2, 2}` is the maintainer's list shorthand for four sides. A standard YAML parser reads it as `{2: None}`, so the shell needs a defined form ([[ADR-0007 Shell UI Layer#Open items]]). The colour forms are in [[Value Types and Conversion]] |
| Style file type | **Decided:** `type: Style` |

## Calling a popup

A module can call a popup ("Calls" in the flow diagram, [[Shell Structure]]). The popup is a `kind: popup` entry in the shell file; the module asks the shell to open it. Decided (2026-10-26): many modules can call one popup, and the popup must know what called it so its data fits the caller.

The maintainer's suggested shape passes `self`:

```python
@action
def open_menu(self, popup_name, anchor):
    self.ctx.popup(self, popup_name).open(anchor_rect=anchor)
```

**A problem with `self` alone.** One module instance serves every use. `self` says *which module* called but not *which use* (which surface, which monitor, which params). The popup's parent is the surface that holds the calling use, and it must open on that monitor. So the caller also has to carry the use. Options:

| Option | Shape | Notes |
|---|---|---|
| A. The shell supplies the use to the action | An action called from a widget receives the calling `use` (as `use` or on `self.ctx.caller`) automatically, because the shell knows which widget was clicked | The module writes `self.ctx.popup(popup_name)` and the shell fills in the caller. Least code in the module (recommended) |
| B. The module passes the use | `self.ctx.popup(popup_name, caller=use)` | Explicit; the module must keep the `use` |
| C. The maintainer's form | `self.ctx.popup(self, popup_name)` | Identifies the module only; works for a module with a single use |

What the popup sees: a `caller` record: the calling module's name and UID, the use (name, monitor, params), the anchor rectangle, and an optional `data` mapping the module passes (for example which tray item). Expressions in the popup read `caller.<field>`; the popup's own modules receive it as params.

- The popup's parent is the surface that holds the calling use, so it opens on that monitor only ([[Surface Types#Open questions]]).
- The caller passes the anchor rectangle (the clicked icon), in its surface's coordinates.
- Focus is opt-in on the popup entry, not a call argument.
- Open: option A, B or C; and whether the call is a method on the context or an action the shell file can declare directly.

## D-Bus helper

Over `dbus-fast` on the shared asyncio service thread ([[ADR-0009 D-Bus Client Library]]). Proposed shape:

```python
bus = self.ctx.dbus.system()              # or .session()
proxy = bus.proxy("org.freedesktop.UPower", "/org/freedesktop/UPower/devices/DisplayDevice")
proxy.on_property_changed(self.on_battery)      # called on the service thread, short, never blocks
level = proxy.get("Percentage")                  # may be awaited off the loop thread
```

- Callbacks run on the service thread and call `ctx.send`, which crosses to the loop.
- Reads and calls are asynchronous; a module author does not use them from the loop thread.
- A module may use another D-Bus library on its own thread; the helper is a recommendation.
- #needs-verification: the exact `dbus-fast` calls, after the spike in [[ADR-0009 D-Bus Client Library#Consequences]].

## Timers and threads

- `ctx.every` and `ctx.after` run on the loop thread; use them only for short work. They use tre's timers (`window.after`, `window.every`), which do not wake the loop without a reason ([[Process Model and Threading#Performance notes]]).
- `ctx.thread(fn)` is for blocking work. An exception is logged with the module's name. The shell joins it on `stop` with a timeout.

## What the context does not give

- tre nodes, windows or surfaces.
- Other modules' data (a module that needs another's values reads its own source).
- The registry or the config loader.
- A way to call TEL directly (expressions are written in shell files).

## Open questions

- [ ] Whether `ctx.send` accepts a dict of several keys at once.
- [ ] Whether `ctx.uses` is a mapping (as in the example), a list or an event stream. The example above is for the maintainer to judge the use cases (2026-10-26).
- [ ] Whether a module can send to a specific monitor.
- [ ] Whether `ctx.state_dir` is needed or `ctx.data_dir` is enough.
- [ ] What `ctx.yaml()` returns for imported files and for values that are TEL expressions (the raw text or the evaluated value).
- [ ] The timer clock and what happens to timers on reload.

## Acceptance criteria

- [ ] A module reads its own keys through `ctx.config` and another file through `ctx.yaml(ref)` by name, UID and file name.
- [ ] `ctx.send` from a thread reaches the loop in one turn and coalesces repeated sends.
- [ ] A module sends different text to two uses of the same module file.
- [ ] A module is told when a use appears and when it goes away.
- [ ] A D-Bus signal handled through `ctx.dbus` reaches a view without blocking the loop.
- [ ] An exception in a `ctx.thread` function is logged with the module's name.

## Links

- [[42 Python API]] · [[Module Contract]] · [[Value Types and Conversion]] · [[ADR-0007 Shell UI Layer]]
