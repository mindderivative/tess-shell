---
title: D-Bus Service Layer
aliases: [D-Bus Services, Service Layer, ctx.dbus]
type: spec
status: draft
owner: phil
created: 2026-11-02
updated: 2026-11-02
tags: [spec/integration, integration/dbus, needs-verification]
---

# D-Bus Service Layer

> [!NOTE]
> The one place the shell talks D-Bus: a shared asyncio service thread with one session-bus and one system-bus connection, the rules every caller follows (names, timeouts, missing services, name owners that change, threads), and the catalogue of services the v1 modules read. It turns [ADR-0009 D-Bus Client Library](../../30%20Decisions/ADR-0009%20D-Bus%20Client%20Library.md) (accepted) into rules. The interface names and properties in the catalogue were read on the maintainer's machine on 2026-11-02 (read-only `busctl` calls; plasmashell, KWin and kglobalacceld 6.8.2, xdg-desktop-portal 1.22.1); every row says what was read and what was not.

## Purpose and Scope

- Specify the service thread, the connections, the helper that modules use (`ctx.dbus`, [Module Context > D-Bus Helper](../../42%20Python%20API/Module%20Context.md#d-bus-helper)), the rules for calling and listening, and the failure behaviour when a service is missing or leaves the bus.
- Not in this note: the shell's own exported interface ([IPC and CLI > The Interface](../Runtime/IPC%20and%20CLI.md#the-interface)), the KWin objects ([KWin Integration](KWin%20Integration.md)), the shortcut service ([Global Shortcuts](Global%20Shortcuts.md)), the portals ([Portals](Portals.md)), and the meaning of each service to its module (the module specs, which wait).

## Behaviour

### The Service Thread

| Item | Rule | Source |
|---|---|---|
| Thread | One thread named `dbus`, running one asyncio loop, started at step 10 of the start sequence, because the shell must own its bus name before modules start, and joined after the last module stops ([Shell Start and Stop > Start Sequence](../Runtime/Shell%20Start%20and%20Stop.md#start-sequence)) | [ADR-0009 D-Bus Client Library](../../30%20Decisions/ADR-0009%20D-Bus%20Client%20Library.md), [Process Model and Threading > Threads](../../20%20Architecture/Process%20Model%20and%20Threading.md#threads) |
| Connections | One session-bus connection and one system-bus connection, opened on first use; the system bus is not opened if no module asks for it | Proposed |
| Library | `dbus-fast`; `jeepney` is the fallback ([D-Bus Libraries for Python](../../90%20Research/D-Bus%20Libraries%20for%20Python.md)) | [ADR-0009 D-Bus Client Library](../../30%20Decisions/ADR-0009%20D-Bus%20Client%20Library.md) |
| Crossing to the loop | A callback on this thread never touches a node. It calls the module's `ctx.send`, which crosses to the loop with `call_soon` | [Process Model and Threading > Handing a value to the loop (proposed)](../../20%20Architecture/Process%20Model%20and%20Threading.md#handing-a-value-to-the-loop-proposed) |
| Callback budget | A callback returns in under 1 ms of its own work; anything longer is handed to `ctx.thread` (proposed, measured in testing) | Proposed |
| Name and path of the helper | `ctx.dbus` with `.session()` and `.system()`, each returning a bus object with `proxy(name, path)`; the shape is in [Module Context > D-Bus Helper](../../42%20Python%20API/Module%20Context.md#d-bus-helper) | Proposed |

### Calling a Service

1. **Every call has a timeout.** The default is 5 seconds, the same as the control interface ([IPC and CLI > Threading](../Runtime/IPC%20and%20CLI.md#threading)). A module may pass a shorter one. A call that times out raises one `ServiceTimeout` error in the module and is logged once per service per minute.
2. **A missing service is a state, not a crash.** `ServiceUnknown`, `NameHasNoOwner` and `NoReply` map to a service state `UNAVAILABLE`. The helper returns it to the module, which shows its empty or hidden state (the module specs decide what that looks like). The shell keeps running ([Goals and Non-Goals](../../10%20Vision/Goals%20and%20Non-Goals.md) G3).
3. **No call from the loop thread.** A module that awaits a D-Bus call from a loop callback is a defect; the helper's blocking forms raise when called on the loop thread (proposed).
4. **No polling when a signal exists.** A module that needs a value watches `PropertiesChanged` (the idle-CPU budget in AGENTS > 12. Design Completeness Checklist applies; the `60 Quality` budgets are not written).

### Listening and Name Owners

- A subscription is a match rule on the bus. The helper adds the rule once per (bus, sender, path, interface, member) however many modules ask, and removes it when the last subscriber stops.
- The helper watches `NameOwnerChanged` for every well-known name a module uses. When the owner goes away it marks the service `UNAVAILABLE` and calls the module's `on_service_lost`; when a new owner appears it re-reads the module's properties and calls `on_service_found`. The helper hands both calls to the loop with `call_soon`, so they run on the loop thread like every other hook. This is how a module survives `plasmashell` or `upowerd` restarting. The two hook names are proposed additions to the hook table in [Module Contract](../../42%20Python%20API/Module%20Contract.md); they do not exist there yet.
- Property reads are cached per (service, path, interface) and updated from `PropertiesChanged`. A service that does not emit `PropertiesChanged` for a property (the catalogue says which) is read on a timer the module chooses, not by the helper.
- `GetAll` is used once at subscription, then signals only.

### Own Names and Objects

The shell owns exactly one name on the session bus, `io.github.mindderivative.TesseraeShell`, and exports one object ([IPC and CLI > The Bus Name](../Runtime/IPC%20and%20CLI.md#the-bus-name)). It takes no other name in v1, and in particular none that plasmashell holds ([Plasma Coexistence](Plasma%20Coexistence.md)). A module must not request a bus name; the helper has no call for it.

### Activation

A well-known name that is only activatable (listed with no owner, for example `org.kde.krunner`) starts its service on the first call. The helper treats activation as a normal call with the call's timeout, and a service that is slow to start is not an error until the timeout.

## The Service Catalogue

Read on 2026-11-02 on one machine (Plasma 6.8.2, KWin 6.8.2, a desktop with no battery). "Read" means the interface and the stated members exist; no method that changes state was called. Other distributions and versions may differ. #needs-verification elsewhere.

| Service | Bus | Name, path, interface | What was read | Module | Missing means |
|---|---|---|---|---|---|
| Virtual desktops | session | `org.kde.KWin`, `/VirtualDesktopManager` | `current` returned a UUID string; `desktops`, `currentChanged` seen on 2026-10-26 ([System Context > Observed D-Bus names](../../20%20Architecture/System%20Context.md#observed-d-bus-names)) | Workspaces | Not KWin: the module is empty |
| Tray watcher | session | `org.kde.StatusNotifierWatcher`, `/StatusNotifierWatcher` | Held by `kded6`; `IsStatusNotifierHostRegistered` true, `ProtocolVersion` 0, `RegisteredStatusNotifierItems` lists one item; methods `RegisterStatusNotifierHost`, `RegisterStatusNotifierItem`; signals `StatusNotifierItemRegistered`, `StatusNotifierItemUnregistered`, `StatusNotifierHostRegistered`, `StatusNotifierHostUnregistered` | Tray | No watcher: the module shows nothing and logs a warning ([Plasma Coexistence > Tray](Plasma%20Coexistence.md#tray)) |
| Notifications | session | `org.freedesktop.Notifications`, `/org/freedesktop/Notifications` | Held by plasmashell; `GetServerInformation` returned `Plasma`, `KDE`, `6.8.2`, `1.2`; 13 capabilities including `actions`, `body-markup`, `inline-reply`, `persistence`; property `Inhibited` false | None in v1 | A notification centre is outside v1 ([V1 Scope > After v1](../../10%20Vision/V1%20Scope.md#after-v1)) |
| Battery | system | `org.freedesktop.UPower`, `/org/freedesktop/UPower/devices/DisplayDevice`, `org.freedesktop.UPower.Device` | `Percentage`, `State`, `IsPresent`, `IconName`, `TimeToEmpty`, `TimeToFull`, `Energy` exist, all with change signals. On this desktop `IsPresent` is false and `IconName` is `battery-missing-symbolic` | Battery | `IsPresent` false: the module hides itself (the check is part of this note, [Acceptance Criteria](#acceptance-criteria)) |
| Power profile | system | `org.freedesktop.UPower.PowerProfiles`, `/org/freedesktop/UPower/PowerProfiles` | `ActiveProfile` (writable) read as `performance`; `ActiveProfileHolds` exists | Battery (optional) | Profile control hidden |
| Network | system | `org.freedesktop.NetworkManager`, `/org/freedesktop/NetworkManager` | `State` read as 70 (connected globally) and `Connectivity` as 4 (full) | Network | Module empty |
| Media | session | `org.mpris.MediaPlayer2.<player>`, `/org/mpris/MediaPlayer2` | On 2026-11-02 no player was running, so none was read; names were present on 2026-10-26 | Media | No player: the module hides itself |
| Audio | not D-Bus | PipeWire through `wpctl` or a library | Not read | Audio | The access path is open ([D-Bus Libraries for Python > Open](../../90%20Research/D-Bus%20Libraries%20for%20Python.md#open)) |
| Shortcuts | session | `org.kde.kglobalaccel`, `/kglobalaccel`, `org.kde.KGlobalAccel` | See [Global Shortcuts](Global%20Shortcuts.md) | the shell | See [Global Shortcuts](Global%20Shortcuts.md) |
| Portals | session | `org.freedesktop.portal.Desktop`, `/org/freedesktop/portal/desktop` | See [Portals](Portals.md) | the shell | See [Portals](Portals.md) |
| Screen saver and idle | session | `org.freedesktop.ScreenSaver` | Held by `kwin_wayland` | none in v1 | n/a |

> [!NOTE]
> **Applications and the launcher**
> The launcher reads desktop entries from the files, not from a D-Bus service, so it is not in this table. The Applications source is open (#needs-verification in [System Context > Services for the V1 Modules](../../20%20Architecture/System%20Context.md#services-for-the-v1-modules)); `org.kde.krunner` is activatable on this machine and is a possible search backend, not chosen.

## Configuration

None in v1. The shell asks for no bus address option: it uses `DBUS_SESSION_BUS_ADDRESS` and the system bus socket as they are. `--config-dir` for tests does not change the bus ([IPC and CLI > The Command Line](../Runtime/IPC%20and%20CLI.md#the-command-line)).

## Python Contract

The helper's methods, hooks and error types are listed in [Module Context > D-Bus Helper](../../42%20Python%20API/Module%20Context.md#d-bus-helper) and [Module Contract](../../42%20Python%20API/Module%20Contract.md). The additions this note proposes: `ServiceTimeout` and `ServiceUnavailable` error types, the hooks `on_service_lost(name)` and `on_service_found(name)`, a blocking-call guard on the loop thread, and a state value `UNAVAILABLE`.

## Integration

- Threads: the `dbus` service thread is the only thread that touches a bus connection. The control interface's incoming calls arrive on it too and are handed to the loop ([IPC and CLI > Threading](../Runtime/IPC%20and%20CLI.md#threading)).
- Plasma: no name that plasmashell holds is taken ([Plasma Coexistence](Plasma%20Coexistence.md)).
- The incoming `FullscreenState` call from the KWin script arrives here ([KWin Integration](KWin%20Integration.md)).

## Design

None.

## Accessibility

The layer carries no UI. A module that shows a service as unavailable must also expose the state to assistive technology, not only by colour ([Building Blocks](../../50%20Design%20System/Building%20Blocks.md)).

## Performance Budget

- Idle: no timer in the layer; subscriptions are signals only. Target: 0 wake-ups per second with no signal traffic (measured in testing).
- One connection per bus, however many modules; a spike on Python 3.14 measures the battery read, a `PropertiesChanged` signal, the `/VirtualDesktopManager` read and the idle cost ([ADR-0009 D-Bus Client Library > Consequences](../../30%20Decisions/ADR-0009%20D-Bus%20Client%20Library.md#consequences)).

## Failure Modes and Recovery

| Failure | Result |
|---|---|
| The session bus is not reachable at start | The shell exits with a clear error: its own interface cannot be owned ([Shell Start and Stop > Exit codes](../Runtime/Shell%20Start%20and%20Stop.md#exit-codes)) |
| The system bus is not reachable | Modules that need it show `UNAVAILABLE`; the shell runs |
| A service leaves the bus | Its modules get `on_service_lost`, show their empty state, and recover on `on_service_found` |
| A callback is slow | It delays every D-Bus module ([ADR-0009 D-Bus Client Library > Options](../../30%20Decisions/ADR-0009%20D-Bus%20Client%20Library.md#options)); the layer logs a callback over 50 ms with the module name (proposed) |
| A callback raises | Caught, logged with the module name, the module keeps running ([Module Contract](../../42%20Python%20API/Module%20Contract.md)) |
| Cython wheels fail to install | The pure-Python build is the escape hatch; if both fail, `jeepney` ([ADR-0009 D-Bus Client Library > Consequences](../../30%20Decisions/ADR-0009%20D-Bus%20Client%20Library.md#consequences)) |
| The bus daemon restarts | Connections close; the layer reconnects with a back-off of 1, 2, 4, 8 seconds, capped at 30 (proposed), re-adds its match rules, and re-requests the shell's own name |

## Open Questions

1. [ ] The 1 ms and 50 ms callback numbers are proposals; measure in the spike.
2. [ ] Whether the hooks `on_service_lost` and `on_service_found` belong to the module contract or to the helper's subscription call (recommendation: the contract, so every module handles a service the same way).
3. [ ] Whether the system bus connection is opened lazily (recommended) or at start.
4. [ ] The Applications source for the launcher ([Roadmap](../../00%20Home/Roadmap.md)).

## Acceptance Criteria

- [ ] One thread named `dbus` exists after start, and `ctx.dbus` calls from any module run on it.
- [ ] A call to a name with no owner returns `UNAVAILABLE` within the call timeout and logs one warning.
- [ ] When plasmashell or `upowerd` is restarted, the module that uses it shows its empty state and then recovers without a shell restart.
- [ ] A blocking helper call made on the loop thread raises.
- [ ] Two modules subscribing to the same signal add one match rule.
- [ ] On a machine with `IsPresent` false, the Battery module hides itself.
- [ ] With no signal traffic, the layer causes no wake-ups over 60 seconds.
- [ ] No module can request a bus name through the helper.

## Links

- [Integration](Integration.md) · [ADR-0009 D-Bus Client Library](../../30%20Decisions/ADR-0009%20D-Bus%20Client%20Library.md) · [Plasma Coexistence](Plasma%20Coexistence.md) · [Global Shortcuts](Global%20Shortcuts.md) · [Portals](Portals.md) · [Module Context](../../42%20Python%20API/Module%20Context.md) · [Process Model and Threading](../../20%20Architecture/Process%20Model%20and%20Threading.md) · [System Context](../../20%20Architecture/System%20Context.md)
