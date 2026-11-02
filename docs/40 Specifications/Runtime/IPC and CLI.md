---
title: IPC and CLI
aliases: [Control Interface, Command Line, tesserae-shell CLI, Shell D-Bus Interface]
type: spec
status: review
owner: phil
created: 2026-10-28
updated: 2026-10-30
tags: [spec/runtime, integration/dbus, needs-verification]
---

# IPC and CLI

> [!NOTE]
> How the outside world controls a running shell, and the command line that does it. The shell owns one session-bus name and exports one small D-Bus interface; the `tesserae-shell` command is a thin client of it, and a few subcommands run without a shell at all (`check`, `schema`, the KWin helpers). The KWin script that reports fullscreen windows ([ADR-0012 Keeping the Shell Above Plasma Panels](../../30%20Decisions/ADR-0012%20Keeping%20the%20Shell%20Above%20Plasma%20Panels.md)) calls the same interface. Decided by [ADR-0013 Control Interface](../../30%20Decisions/ADR-0013%20Control%20Interface.md) (accepted 2026-10-28, Option B). The commands and names below were accepted by the maintainer (2026-10-28 and 2026-10-29).

## Purpose and Scope

- Define the commands, the D-Bus interface, the command line, and the security and failure rules.
- Not in this note: what each action does to a surface ([Surfaces](../Surfaces/Surfaces.md)), how a module action is written ([Module Contract](../../42%20Python%20API/Module%20Contract.md)), and how the shell registers global shortcuts itself ([ADR-0005 Global Shortcuts](../../30%20Decisions/ADR-0005%20Global%20Shortcuts.md), the Integration notes, to write).

## Behaviour

### Who Calls the Shell

| Caller                  | Uses                                                                                                                          | Example                                                                                    |
|-------------------------|-------------------------------------------------------------------------------------------------------------------------------|--------------------------------------------------------------------------------------------|
| The user, in a terminal | The `tesserae-shell` command                                                                                                  | `tesserae-shell reload`                                                                    |
| A keyboard shortcut     | A KDE custom shortcut that runs a command, or a shortcut the shell registers itself ([ADR-0005 Global Shortcuts](../../30%20Decisions/ADR-0005%20Global%20Shortcuts.md)) | `tesserae-shell toggle launcher`                                                           |
| The KWin script         | `callDBus` on the interface                                                                                                   | Reporting which outputs have a fullscreen window ([ADR-0012 Keeping the Shell Above Plasma Panels](../../30%20Decisions/ADR-0012%20Keeping%20the%20Shell%20Above%20Plasma%20Panels.md)) |
| Desktop tools           | `busctl`, `qdbus`, KRunner or a launcher script                                                                               | `busctl --user call ...`                                                                   |
| systemd                 | Signals and `sd_notify`, not this interface ([Shell Start and Stop > Telling systemd (decided 2026-10-28)](Shell%20Start%20and%20Stop.md#telling-systemd-decided-2026-10-28))                                         | n/a                                                                                        |

On a compositor without KDE's shortcut service the launcher still opens from the command or a shortcut the user binds in the compositor ([ADR-0005 Global Shortcuts](../../30%20Decisions/ADR-0005%20Global%20Shortcuts.md)); this interface is what that command calls.

### The Bus Name

- The shell requests one name on the session bus and exports one object, at start, once the model is built ([Shell Start and Stop](Shell%20Start%20and%20Stop.md)).
- Decided names, 2026-10-28 (nothing is registered or checked for clashes): service `io.github.mindderivative.TesseraeShell`, object path `/io/github/mindderivative/TesseraeShell`, interface `io.github.mindderivative.TesseraeShell1`. A reverse-domain name needs a domain the project owns; the repositories of tre and Tesserae are under `github.com/mindderivative`, so the `io.github.<account>` form is used. The `1` in the interface name is the interface version: a breaking change makes `2`. 
- The name is requested without queueing. A name that is already owned means another shell is running; the shell exits with code 4 ([Shell Start and Stop > Exit codes](Shell%20Start%20and%20Stop.md#exit-codes)). The lock file remains the first guard ([Shell Start and Stop > Process rules](Shell%20Start%20and%20Stop.md#process-rules)).

### The Interface

Proposed methods. Names are `CamelCase` as D-Bus convention; every method that changes the shell returns a success flag and a message as two values (signature `bs`, not a struct), or raises a D-Bus error. The test below showed `dbus-fast` returning two values from a method annotated `bs`.

| Method                   | Arguments                    | Result              | What it does                                                                                                                                                                                |
| ------------------------ | ---------------------------- | ------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Reload`                 | none                         | `(b ok, s message)` | Reloads everything now, as `SIGHUP` does ([Hot Reload](Hot%20Reload.md)); returns after the apply, with the errors if it failed                                                                            |
| `Quit`                   | none                         | none                | Starts the stop sequence ([Shell Start and Stop > Stop sequence](Shell%20Start%20and%20Stop.md#stop-sequence))                                                                                                                           |
| `Status`                 | none                         | `s` (JSON)          | The state, versions, monitors, surfaces, modules and the last errors                                                                                                                        |
| `Show`, `Hide`, `Toggle` | `s name`                     | `(b ok, s message)` | Show, hide or toggle a Bar, Panel or Frame by its unique name ([Panel > States](../Surfaces/Panel.md#states))                                                                                                            |
| `ClosePopup`             | none                         | none                | Closes the open Popup, if any                                                                                                                                                               |
| `Call`                   | `s module, s action, s args` | `s` (JSON)          | Calls an `@action` method of a module; `args` is a JSON array                                                                                                                               |
| `SetLogLevel`            | `s level`                    | none                | Changes the log level until the next reload of `settings.tdl` ([Settings File > Log files](../../41%20TDL%20Reference/Settings%20File.md#log-files))                                                                                                |
| `FullscreenState`        | `s outputs`                  | none                | For the KWin script: the outputs that now have an active fullscreen window; the shell hides its surfaces on those ([Surface Types > Fullscreen and maximised windows (decided 2026-10-27)](../Surfaces/Surface%20Types.md#fullscreen-and-maximised-windows-decided-2026-10-27)) |

Properties: `State` (`starting`, `running`, `stopping`), `Version`, `ApiVersion`. Signals: `Reloaded(b ok, s summary)`, `ErrorReported(s rule, s file, i line, s message)`, `SurfaceChanged(s name, s state)`.

- **No method opens a Popup.** A focused Popup needs a user action for its grab, which a bus call is not; a menu or launcher opened from a command is a Panel ([Popup > Focus and dismissal (decided)](../Surfaces/Popup.md#focus-and-dismissal-decided), decided 2026-10-28). `ClosePopup` is allowed.
- **Names are unique names.** `Show`, `Hide` and `Toggle` take the unique `Name:` of a surface and look it up in the registry; an unknown name is an error with the nearest names ([Validation and Errors > The error record](Validation%20and%20Errors.md#the-error-record)).
- **Idempotent state changes.** `Show` on a shown surface succeeds and does nothing.
- `FullscreenState` takes its list as one string holding a JSON array (for example `["DP-1"]`), because a KWin script cannot send a D-Bus `as`: a test on 2026-10-29 showed `callDBus` sends a JavaScript array as `av`, and a method declared `as` was never called ([KWin Integration > What a script inside KWin showed (test of 2026-10-29)](../Integration/KWin%20Integration.md#what-a-script-inside-kwin-showed-test-of-2026-10-29)). It is a full state, not an event. The script sends the complete list each time; the shell diffs it. A lost message is corrected by the next one. Decided 2026-10-28.
- The method list is the minimum for v1; more are added as modules need them.

### Threading

The shell's D-Bus service thread (a shared asyncio loop, [ADR-0009 D-Bus Client Library](../../30%20Decisions/ADR-0009%20D-Bus%20Client%20Library.md)) receives each call. The handler never touches a node: it queues the command for the loop with `call_soon` and awaits the result with a timeout of 5 seconds, then replies ([Process Model and Threading > Handing a value to the loop (proposed)](../../20%20Architecture/Process%20Model%20and%20Threading.md#handing-a-value-to-the-loop-proposed)). The loop applies the command between frames. If the loop is stuck, the call times out with an error; `Quit` also asks tre to stop from the service thread through `LoopHandle.stop()`, which any thread may call ([TRE-REQ-005 Keep-Alive and Loop Stop](../../80%20Engine%20Requests/TRE-REQ-005%20Keep-Alive%20and%20Loop%20Stop.md)).

### The Command Line

One executable, `tesserae-shell` (name decided 2026-10-28), also `python -m tesserae_shell`.

| Subcommand                                | Needs a shell | What it does                                                                                                                                             |
|-------------------------------------------|---------------|----------------------------------------------------------------------------------------------------------------------------------------------------------|
| `run`                                     | no            | Starts the shell; the default when no subcommand is given; what systemd runs ([Shell Start and Stop](Shell%20Start%20and%20Stop.md))                                   |
| `check [--json]`                          | no            | Validates settings and files without starting: the same pipeline and errors as start ([Validation and Errors](Validation%20and%20Errors.md)); exit code 1 on any error |
| `schema [--out DIR]`                      | no            | Writes or refreshes the JSON schemas ([ADR-0011 JSON Schema for Shell Files](../../30%20Decisions/ADR-0011%20JSON%20Schema%20for%20Shell%20Files.md), [JSON Schema and Editor Support > Where the schemas live](../../41%20TDL%20Reference/JSON%20Schema%20and%20Editor%20Support.md#where-the-schemas-live))                                  |
| `reload`                                  | yes           | Calls `Reload`                                                                                                                                           |
| `quit`                                    | yes           | Calls `Quit`                                                                                                                                             |
| `status [--json]`                         | yes           | Calls `Status` and prints it                                                                                                                             |
| `show NAME`, `hide NAME`, `toggle NAME`   | yes           | Calls the method of the same name                                                                                                                        |
| `call MODULE ACTION [ARG ...]`            | yes           | Calls a module action; each `ARG` is a JSON value, or plain text if it is not valid JSON                                                                 |
| `log-level LEVEL`                         | yes           | Calls `SetLogLevel`                                                                                                                                      |
| `events`                                  | yes           | Streams the interface's signals until interrupted. Not in v1: later (decided 2026-10-28); until then `busctl --user monitor` shows them                  |
| `kwin script install`, `remove`, `status` | no            | Installs or removes the KWin fullscreen script ([ADR-0012 Keeping the Shell Above Plasma Panels](../../30%20Decisions/ADR-0012%20Keeping%20the%20Shell%20Above%20Plasma%20Panels.md))                                                                 |
| `kwin rule show`, `install`, `remove`     | no            | Shows, writes or removes the one KWin window rule group the shell owns; `install` shows the rule and asks, or needs `--yes`                              |
| `version`                                 | no            | Prints the shell, tre and Python versions                                                                                                                |

Global options: `--config-dir PATH` (overrides the config directory, for tests), `--json`, `--timeout SECONDS` (default 5), `--quiet`.

- **Fast to start.** A command from a shortcut must start quickly. The client path imports only the standard library and the D-Bus client; it never imports tre, Loguru, `jsonschema`, the TDL parser or TEL. Measured on this machine: a `jeepney` client making one call takes about 21 ms ([ADR-0013 Control Interface > Context](../../30%20Decisions/ADR-0013%20Control%20Interface.md#context)). Heavy imports happen inside `run`, `check` and `schema` only.
- The framework is `argparse` (standard library, nothing to install, the lowest start-up cost). Decided 2026-10-28; `click` is installed here (8.5.0) but is a dependency.
- The D-Bus client is `jeepney` (blocking, pure Python, the named fallback in [ADR-0009 D-Bus Client Library](../../30%20Decisions/ADR-0009%20D-Bus%20Client%20Library.md)). Decided 2026-10-28, backed by a measurement: a `jeepney` client making one call took 21.0 ms, a `dbus-fast` client 53.2 ms (its asyncio import dominates), and `busctl --user call` 1.5 ms. A shortcut can call `busctl` directly and skip Python altogether.
- **Output.** Plain text for people, one result per line; `--json` for scripts, as one JSON object. Errors go to stderr in the printed form of [Validation and Errors > The error record](Validation%20and%20Errors.md#the-error-record).

### Exit Codes of the Client

The shell's own codes are in [Shell Start and Stop > Exit codes](Shell%20Start%20and%20Stop.md#exit-codes). The client uses the same numbers where they apply, and adds two:

| Code | Meaning                                                                                 |
|------|-----------------------------------------------------------------------------------------|
| 0    | The command succeeded                                                                   |
| 1    | The command ran and failed (a `check` found errors, an unknown name, a rejected action) |
| 2    | Environment error: no session bus, no config directory                                  |
| 3    | No shell is running: the bus name has no owner                                          |
| 4    | `run` only: another shell is already running                                            |
| 5    | The call timed out                                                                      |

Decided 2026-10-28; codes 3 and 5 were free in the shell's table.

### Security

- Only processes of the same user can reach the session bus; the bus enforces it. The shell adds no authentication of its own. A sandboxed application with session-bus access could call the interface; narrowing that belongs to the security model in `60 Quality/` (to write).
- **No method evaluates code, reads a file or runs a command.** `Call` reaches only methods a module marked `@action`, the same rule as a shell file ([Module Contract](../../42%20Python%20API/Module%20Contract.md), decided 2026-10-26). `Reload` reads only the files the shell already watches.
- `Status` must not return secrets: it lists names (including module names, decided 2026-10-28), states and counts, and never param values or log contents.
- The KWin helpers write to the user's desktop configuration; they show what they will write and need consent ([ADR-0012 Keeping the Shell Above Plasma Panels](../../30%20Decisions/ADR-0012%20Keeping%20the%20Shell%20Above%20Plasma%20Panels.md)).

## Configuration

One `settings.tdl` key (decided 2026-10-28): `Control`, default true; `Control: false` runs the shell without exporting the interface, and the KWin script then cannot report fullscreen windows. The rest of the global settings list is deferred ([Settings File](../../41%20TDL%20Reference/Settings%20File.md)).

## Python Contract

None. A module's `@action` methods are reachable through `Call`, and a module never talks to the interface ([Module Context](../../42%20Python%20API/Module%20Context.md)).

## Integration

- D-Bus: `dbus-fast` on the shared service thread, exporting the object ([ADR-0009 D-Bus Client Library](../../30%20Decisions/ADR-0009%20D-Bus%20Client%20Library.md)). Exporting was listed there as later work and is v1 work ([ADR-0013 Control Interface](../../30%20Decisions/ADR-0013%20Control%20Interface.md), accepted 2026-10-28). Verified on 2026-10-28 with `dbus-fast` 5.2.0 (a scratch install, not on the system): a service exported a method returning `bs`, a method that raises a named D-Bus error, a method taking `as`, a read-only property with change notification, and a signal, under a name requested on the session bus; `busctl introspect`, `busctl call` and `busctl monitor` all worked, and a second `DO_NOT_QUEUE` request for the name got `EXISTS` ([ADR-0013 Control Interface > Context](../../30%20Decisions/ADR-0013%20Control%20Interface.md#context)).
- KWin script: calls `callDBus(service, path, interface, "FullscreenState", outputs, callback)`; the call is asynchronous ([KWin scripting API](https://develop.kde.org/docs/plasma/kwin/api/), read 2026-10-28). How the script finds the shell's name and what it does when the shell is not running (the call fails, the callback ignores it) is specified with the script in the Integration notes.
- Plasma coexistence: the shell owns only its own name, so nothing here claims a name plasmashell uses ([ADR-0004 Plasma Coexistence](../../30%20Decisions/ADR-0004%20Plasma%20Coexistence.md)).

## Design

None. Command output is plain text and works without colour.

## Accessibility

Plain text and exit codes are readable by a screen reader and a script. `--json` gives a stable shape.

## Performance Budget

- A control command costs the client about 20 ms plus the shell's work; target under 100 ms end to end for `toggle` on this machine (proposed; measured in testing).
- On the loop a command is one `call_soon` callback that does a lookup and one tre call; it stays under a millisecond.
- An idle shell receives no calls and wakes for none.

## Failure Modes and Recovery

| Failure                            | Result                                                                                                                               |
|------------------------------------|--------------------------------------------------------------------------------------------------------------------------------------|
| No session bus                     | The client exits with code 2 naming `DBUS_SESSION_BUS_ADDRESS`; the shell cannot own a name and exits with code 2 if `Control` is on |
| The name has no owner              | The client exits with code 3: "no shell is running"                                                                                  |
| A call times out                   | The client exits with code 5; the shell's loop is probably busy or stuck                                                             |
| An unknown surface name            | Error with the nearest names; exit code 1                                                                                            |
| The shell is starting or stopping  | The method returns an error saying so                                                                                                |
| The client is newer than the shell | A missing method returns `UnknownMethod`; the client says the running shell is older and prints both versions                        |
| A module action raises             | The error is returned with the module name; the shell continues                                                                      |
| A second `run`                     | The name is taken: exit code 4                                                                                                       |

## Open Questions

- [x] **The channel:** one D-Bus interface, no socket ([ADR-0013 Control Interface](../../30%20Decisions/ADR-0013%20Control%20Interface.md), maintainer, 2026-10-28).
- [x] **The bus name** `io.github.mindderivative.TesseraeShell` (maintainer, 2026-10-28).
- [x] **The command name** `tesserae-shell` (maintainer, 2026-10-28).
- [x] `argparse` for the CLI (maintainer, 2026-10-28, as recommended).
- [x] `jeepney` as the CLI's D-Bus client (as recommended).
- [x] A `call` command that reaches module `@action` methods (as recommended).
- [x] An `events` subcommand: later, not v1 (as recommended).
- [x] A `log-level` command (as recommended).
- [x] The KWin helper commands under `kwin`, with consent (as recommended).
- [x] Client exit codes 3 and 5 (maintainer: "That is fine").
- [x] `FullscreenState` as a full list of outputs (as recommended).
- [x] Shell completion scripts: later (maintainer: "Later is fine").
- [x] A `settings.tdl` key `Control` to turn the interface off, and `Status` may list module names (maintainer, 2026-10-28).

## Acceptance Criteria

- [ ] With the shell running, `tesserae-shell reload` returns after the apply and prints the result; with a bad file it prints the errors and exits with code 1.
- [ ] `tesserae-shell toggle launcher` shows and hides the Panel and returns in under 100 ms.
- [ ] `tesserae-shell status --json` prints state, versions, monitors, surfaces and modules, with no param values.
- [ ] With no shell running, `tesserae-shell reload` exits with code 3 and says so.
- [ ] `tesserae-shell check` validates without starting and exits with 1 on any error, using the same messages as start.
- [ ] `tesserae-shell call Volume set_volume 40` calls an `@action` method; a method not marked `@action` is refused.
- [ ] No D-Bus method evaluates code or reads a file.
- [ ] The KWin script's `FullscreenState` call makes the shell hide its surfaces on that output and show them again when the list no longer names it.
- [ ] `busctl --user introspect` lists the methods, properties and signals above.
- [ ] A second `tesserae-shell run` exits with code 4.
- [ ] The client path does not import tre, Loguru, `jsonschema` or the TDL parser (checked by listing the imported modules of `reload`).

## Links

- [Runtime](Runtime.md) · [ADR-0013 Control Interface](../../30%20Decisions/ADR-0013%20Control%20Interface.md) · [Shell Start and Stop](Shell%20Start%20and%20Stop.md) · [Validation and Errors](Validation%20and%20Errors.md) · [Hot Reload](Hot%20Reload.md) · [ADR-0012 Keeping the Shell Above Plasma Panels](../../30%20Decisions/ADR-0012%20Keeping%20the%20Shell%20Above%20Plasma%20Panels.md)
