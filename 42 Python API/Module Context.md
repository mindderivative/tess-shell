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
| `ctx.uses` | The places this module is used: each with the entry's unique name, monitor, UID and options | Proposed |
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
- **Per use.** One module instance serves every use. When uses must differ, as in the maintainer's `Label_Module` example, the module decides what each use shows and sends it with `use=`. A `use` is one of `ctx.uses`. Sending with no `use` reaches every use.
- **Order.** Values from one module keep their order per key; the flush applies the keys of one turn together.

## Uses

`ctx.uses` is a read-only mapping from each entry's unique name to a use record. A use record has the entry's `name`, its `uid`, the `monitor` it is on, and its options (the keys written in that entry). The shell calls optional hooks when uses change:

```python
def use_added(self, use): ...      # a surface showing this module appeared
def use_removed(self, use): ...    # a surface went away (monitor unplugged, file edited)
```

This lets a module follow monitors coming and going ([[Data Flow#Monitor hot-plug]]) without polling. #needs-verification: whether hooks or an event stream is the better shape.

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
- [ ] Whether `ctx.uses` is a mapping, a list or an event stream.
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
