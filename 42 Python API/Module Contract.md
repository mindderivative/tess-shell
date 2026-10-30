---
title: Module Contract
aliases: [Module API, Module Base Class]
type: api
status: draft
owner: phil
created: 2026-10-26
updated: 2026-10-30
tags: [api, needs-verification]
related: ["[[42 Python API]]", "[[Module Context]]", "[[Value Types and Conversion]]", "[[ADR-0007 Shell UI Layer]]", "[[ADR-0014 Shell File Language]]", "[[Process Model and Threading]]"]
depends_on: ["[[ADR-0007 Shell UI Layer]]", "[[ADR-0009 D-Bus Client Library]]"]
---

# Module Contract

> [!summary]
> A module has three parts: a layout TDL file (`<Name>_Module.tdl`: a metadata block with `Module: v1` and `Name:`, then widgets, expressions and `Params`; [[ADR-0014 Shell File Language]]), a style TDL file, and a Python file (`<Name>_Module.py`) next to them, in a `Modules/<module_name>/` folder ([[ADR-0007 Shell UI Layer#What a module is (2026-10-26)]]). This note is about the Python part: the logic. The Python file holds one class that extends the shell's `Module` base. The shell creates it once, gives it a context, and calls `start`, `stop` and, for a changed configuration, `reload`. The module owns its data and its threads; it sends finished values to the shell, which renders them. **Decided** parts come from [[ADR-0007 Shell UI Layer]] and [[ADR-0009 D-Bus Client Library]]; names and signatures below are **proposed**. Short snippets are illustrations, not code to build.

## What is Decided

| Decision                                                                                                                                                | Source                                                                           |
|---------------------------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------|
| A module is `<Name>_Module.tdl` plus a required matching `<Name>_Module.py`, next to each other, in `Modules/<module_name>/` with all supporting files | [[ADR-0007 Shell UI Layer#Modules (2026-10-25)]]                                          |
| The shell imports the file, finds the class that extends a shell `Module` base, creates it once, and calls `start`, `stop` and an optional `reload`     | [[ADR-0007 Shell UI Layer#Module Python (2026-10-25)]]                                          |
| The module receives a context with its TDL values, its name (the `Name:` in its metadata block) and UID, a logger and the send entry point                                                 | same                                                                             |
| One instance per module file, shared by every use; per-use differences are the module's job. The Python reaches each use by the key `<Module>@<uid>`, which it receives from `ctx.uses` and passes back to name a use in an action (D23, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]; [[Module Context#Uses]])                                                             | [[ADR-0007 Shell UI Layer#Modules (2026-10-25)]]                                          |
| The module's Python reaches its TDL file by file name, unique name or UID                                                                                   | same                                                                             |
| Modules send values to shell entry points; the shell converts what it can                                                                               | [[ADR-0007 Shell UI Layer#Module data reaches the view through shell entry points (2026-10-25)]]                                          |
| A module's Python can be reloaded at runtime                                                                                                            | [[ADR-0007 Shell UI Layer#Events and module reload (2026-10-26)]]                                          |
| Blocking work runs off the loop; D-Bus goes through the shared `dbus-fast` service thread                                                               | [[Process Model and Threading]], [[ADR-0009 D-Bus Client Library]] |

## The Class (Proposed)

```python
# Modules/Clock/Clock_Module.py   (illustration; the import path is not decided)
from tesserae_shell import Module

class Clock(Module):
    def start(self):
        self.ctx.every(1.0, self.tick)          # a timer the shell runs
        self.tick()

    def tick(self):
        self.ctx.send("time", "14:05")          # a plain value

    def stop(self):
        pass                                    # timers are cancelled by the shell
```

- **One class.** The file holds exactly one class extending `Module`. None or more than one is a load error naming the file ([[ADR-0007 Shell UI Layer#Monitors, names and errors (2026-10-25)]]).
- **No constructor arguments.** The base class sets `self.ctx` before `start()` is called.
- **Methods.** `start()`, `stop()`, an optional `reload()` and an optional `validate_use(use)`; the base class provides empty versions. `validate_use` is called when a use is loaded, before it is shown; it raises `ValueError` with a message to reject a param, and the shell reports it as an error naming the file, the use and the param ([[Clock Module]], decided 2026-10-27 that the Clock validates its format on use loaded; the hook and its name are proposed).
- **Actions.** A shell file can call a module method from an event (the shell, not TEL, maps events: [[ADR-0007 Shell UI Layer#Events and module reload (2026-10-26)]]). Decided (maintainer, 2026-10-26): only methods marked with an `@action` decorator can be called from a shell file, and a shell file cannot call anything else. Slow work in an action goes to a thread and the method returns at once.

## Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Created: shell imports the file and creates the class
    Created --> Running: start() returns
    Created --> Failed: start() raises
    Running --> Running: reload() for a changed TDL file
    Running --> Stopping: stop() on quit or code reload
    Stopping --> Created: new code imported, new instance made
    Stopping --> [*]: threads joined, instance dropped
    Running --> Failed: a callback or thread raises past the helpers
    Failed --> Created: code reload
```

| Method              | Runs on     | Called when                                                              | Must                                                                                                               |
|---------------------|-------------|--------------------------------------------------------------------------|--------------------------------------------------------------------------------------------------------------------|
| `start()`           | Loop thread | After the shell model is built ([[Process Model and Threading#Lifecycle (proposed)]]) | Return quickly. Start threads or timers for anything slow. Values sent before a surface exists are kept            |
| `stop()`            | Loop thread | On quit, or before a code reload                                         | Stop its own threads and close connections, within a timeout. The shell joins threads started through `ctx.thread` |
| `validate_use(use)` | Loop thread | A use of the module is loaded or its params change                       | Check `use.params` and raise `ValueError` on a bad value. Quick, no I/O (proposed)                                 |
| `reload()`          | Loop thread | The module's TDL file changed and the Python did not                         | Re-read `self.ctx.config`. No restart                                                                              |

Code reload ([[ADR-0007 Shell UI Layer#Events and module reload (2026-10-26)]], mechanics proposed): the shell imports the new code first and checks it for the class; only then does it call `stop()` on the old instance, join its threads, purge the module's own modules from `sys.modules`, create the new instance and call `start()`. If the new code fails to import, the old instance keeps running and the error is logged with `file:line:column`. The value store keeps the last values until the new instance sends. #needs-verification: `importlib` with live threads, and supporting files in the module folder.

## Rules for the Module Author

1. **Never touch tre nodes.** Send values; the shell renders ([[Layers and Components#Dependency rules]]).
2. **Never block the loop.** `start`, `stop`, `reload` and actions return fast; blocking work uses `ctx.thread`, `ctx.dbus` or its own threads ([[Process Model and Threading#The rules]]).
3. **Own your data.** Read from your sources, keep your own files, JSON or database. The shell stores only the values you send, not your data.
4. **Catch your own thread errors**, or start threads through `ctx.thread`, which catches and logs them with the module's name.
5. **No heavy computation on the shared service thread.** D-Bus callbacks are short and never block, or they delay every D-Bus module ([[ADR-0009 D-Bus Client Library]]).
6. **Heavy CPU work leaves the process** (a subprocess or native code); the GIL is shared with the loop ([[Process Model and Threading#Performance notes]]).

## Integration

- **Threads.** Methods on the loop; module work on `ctx.thread`s; D-Bus callbacks on the shared service thread; values cross to the loop with `call_soon` through `ctx.send`.
- **Names.** The expressions that place values into widgets are written in the module's own layout TDL file, not in the surface. Which names they read (the use's `params`, the values the Python sends) is open ([[ADR-0007 Shell UI Layer#Open items]]). #needs-verification
- **D-Bus.** `ctx.dbus` ([[Module Context]]).

## Failure Modes and Recovery

| Failure                                               | Result                                                                                                        |
|-------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| No class, or more than one                            | Load error naming the file                                                                                    |
| `<Name>_Module.py` missing                            | Load error naming both files                                                                                  |
| `start()` raises                                      | Module marked failed; logged with name and UID; other modules continue; surfaces keep last values or defaults |
| An exception in a `ctx.thread` or `ctx.dbus` callback | Caught, logged with the module name; the module keeps running                                                 |
| A bad code reload                                     | Old instance keeps running; error logged                                                                      |
| `stop()` does not return within the timeout           | Logged; the shell continues shutdown                                                                          |

## Open Questions

- [ ] Constructor versus `self.ctx` set by the base class (proposed above).
- [x] Only `@action`-marked methods are callable from a shell file (maintainer, 2026-10-26).
- [ ] The decorator's final name, and whether actions can return values.
- [x] How a module used several times is named: a use's `Name:` is for the file, references and expressions, and Python uses the `<Module>@<uid>` key (D23, [[ADR-0014 Shell File Language#Decisions on the Open Items (2026-10-30)]]; the head word is the module name, [[ADR-0014 Shell File Language#Layout Rules]], items 6 and 7). Which names an expression reads (`params`, sent values) stays open under Integration.
- [ ] The shell's package name and import path.
- [ ] Which timer helpers `ctx` offers (`every`, `after`) and which clock they use.
- [ ] Whether `reload()` is passed the changed keys.

## Acceptance Criteria

- [ ] A module with one `Module` subclass and its matching TDL file loads, starts and sends a value that a view shows.
- [ ] A missing `.py`, no class, or two classes each fail with a message naming the files.
- [ ] A module whose `start()` raises is marked failed and the other modules keep running.
- [ ] Editing the module's `.py` reloads it without restarting the shell; a bad edit keeps the old instance.
- [ ] Editing only its TDL file calls `reload()`.
- [ ] `stop()` is called on quit, and its threads are joined within the timeout.
- [ ] A callback exception on `ctx.thread` or `ctx.dbus` is logged with the module name and does not stop the shell.

## Links

- [[42 Python API]] · [[Module Context]] · [[Value Types and Conversion]] · [[Process Model and Threading]] · [[ADR-0007 Shell UI Layer]]
