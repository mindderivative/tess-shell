---
title: Tasks Module
aliases: [Tasks, Tasks_Module, Window List, Task Bar]
type: spec
status: accepted
owner: phil
created: 2026-11-13
updated: 2026-11-14
tags: [spec/module, integration/kwin, needs-verification]
---

# Tasks Module

> [!NOTE]
> The Tasks module shows the open windows as a row of buttons, each with the application's icon and optionally its title, marks the active one, and activates, minimises or closes a window on a click. KWin has no D-Bus call that lists windows ([KWin Integration > What KWin offers over D-Bus (introspected on 2026-10-29)](../Integration/KWin%20Integration.md#what-kwin-offers-over-d-bus-introspected-on-2026-10-29)), so the list comes from the shell's KWin script, which already reports fullscreen outputs. This note also carries the window-list design the script needs, which is part M5g of [M5 Brief](../../00%20Home/M5%20Brief.md) with the script's first build. Written and decided by the orchestrator under the [Tesserae Shell Directive](../../00%20Home/Tesserae%20Shell%20Directive.md). Facts about KWin's scripting API come from [KWin Integration](../Integration/KWin%20Integration.md) (a read-only script run on KWin 6.8.1 on 2026-10-29); what was not seen there is marked.

## Purpose and Scope

- Show the windows of the current virtual desktop (or of all), on the module's own monitor (or on all), and act on them.
- v1: KWin only. On another compositor the module is hidden. Not in v1: window previews, grouping by application, pinned launchers, drag to reorder, moving a window between desktops, a per-window menu beyond close.

## Change to an Earlier Decision

[KWin Integration](../Integration/KWin%20Integration.md) says the script "sends nothing else in v1: no titles, no classes, no window ids", and has an acceptance criterion for it. That was written for fullscreen hiding alone. A window list needs each window's id, title and application. Decided by the orchestrator on 2026-11-13 (Tier 1, inside `tess-shell`; [Orchestration Log](../../00%20Home/Orchestration%20Log.md) D-043): the script sends the window list only while at least one Tasks module is in use, and never otherwise; with no Tasks module the script behaves exactly as before, and the old criterion holds for that case. Titles stay inside the shell's process: they are sent to no log above debug level and to no file.

## The Window List (the Script's Second Report)

### What the script sends

One call, `WindowsState(s windows)`, on the shell's interface ([IPC and CLI](../Runtime/IPC%20and%20CLI.md)): the full list, as one string holding a JSON array, because a script cannot send an array of structures ([KWin Integration > What a script inside KWin showed (test of 2026-10-29)](../Integration/KWin%20Integration.md#what-a-script-inside-kwin-showed-test-of-2026-10-29)). Each entry:

| Field | From the script's window object | Seen on 2026-10-29 |
|---|---|---|
| `id` | `internalId` (the window's uuid, as a string) | The uuid exists (`getWindowInfo(uuid)`); the property name in a script is from KDE's API page #needs-verification |
| `title` | `caption` | `caption` is among `getWindowInfo`'s properties |
| `app` | `desktopFileName`, else `resourceClass` | `desktopFile` and `resourceClass` are among `getWindowInfo`'s properties |
| `active` | The window equals `workspace.activeWindow` | Present |
| `minimized` | `minimized` | #needs-verification |
| `desktops` | The ids of the window's virtual desktops; empty means all | #needs-verification |
| `output` | `output.name` | Present |
| `attention` | `demandsAttention` | #needs-verification |

Windows that are left out: `skipTaskbar` true (this removes every shell surface, seen as true for a layer-shell surface), `windowType` other than normal and dialog (docks and the desktop), and special windows.

The order is the order in which windows were opened (the script keeps its own list); it does not change when a window is activated.

### When it sends

Only while enabled ([Turning it on and off](#turning-it-on-and-off)). It sends the full list at enable, and after any of: a window added or removed, the active window changing, and per window a change of caption, minimised state, desktops, output or attention. Changes within one turn of KWin's event loop are sent as one call. The signals seen on 2026-10-29 are `windowActivated` and `windowRemoved` on `workspace`, and `outputChanged` per window; `windowAdded`, `captionChanged`, `minimizedChanged`, `desktopsChanged` and `demandsAttentionChanged` are from KDE's API page. #needs-verification

### Turning it on and off

The script starts with the window list off. The shell turns it on when the first Tasks use appears and off when the last goes. A script cannot receive a D-Bus call, so the shell does it by the reply to a call the script already makes: the reply of `FullscreenState` and of `WindowsState` is a small JSON string, `{"windows": true}` or `{"windows": false}`, and the script reads it in its callback (a callback receives the method's return value, seen on 2026-10-29). To make a change take effect at once, the shell reloads the script when the wanted state changes (unload, load, start; the script's first call gets the new reply).

### Acting on a window

A script cannot be called, so an action is a short one-shot script the shell loads through `/Scripting` (`loadScript` of a file in the shell's runtime folder, `start`, then `unloadScript`): it finds the window by `internalId` and sets `workspace.activeWindow`, or `minimized`, or calls `closeWindow()`. `loadScript` of a path outside KWin's folders, with `start` and `unloadScript`, was seen working on 2026-10-29; the three actions inside a script are from KDE's API page. #needs-verification

- The file is written once per action kind and takes the uuid from its name or a second file, so no script text is built from a window's title.
- If a one-shot script proves too slow or unreliable in the test, the fallback is the script asking for commands in the reply to `WindowsState` after a short `Ping` call the shell cannot trigger, which adds latency; the code session reports before choosing it.

## Behaviour

### Values Sent

| Key | Type | Meaning |
|---|---|---|
| `ready` | boolean | The first `WindowsState` has arrived. The root is `Visible: <\| ready and has_windows \|>` unless `show_empty` |
| `windows` | list | One entry per shown window, per use (the filter depends on the use's monitor): `id`, `title`, `app`, `icon`, `active`, `minimized`, `attention` |
| `has_windows` | boolean | The list is not empty |

The module filters the script's list for each use: by the use's monitor when `monitor` is `THIS`, and by the current virtual desktop when `desktop` is `CURRENT` (the current desktop comes from the same source as [Workspaces Module](Workspaces%20Module.md)). So the values are sent per use (`ctx.send(use=)`).

### Icons

`app` is a desktop file's name. The icon is looked up by the shell's icon service: the desktop entry's `Icon=` name through `ctx.icons.theme_icon` ([Tray Module > Icons (G8)](Tray%20Module.md#icons-g8)); when no desktop entry is found, `app` itself as an icon name; else the shipped `application-outline`. Finding the desktop entry reads the `applications` folders of `XDG_DATA_HOME` and `XDG_DATA_DIRS` once and caches the names; the launcher of M6 uses the same index ([M6 Brief](../../00%20Home/M6%20Brief.md), K5).

### Clicks

| Input | Action |
|---|---|
| Primary click on a window that is not active | Activate it (un-minimising it) |
| Primary click on the active window | Minimise it |
| Middle click | Close it |
| Scroll over the row | Activate the next or previous window in the row |

The module does not predict the result: the row changes when the next `WindowsState` arrives.

### Layout (`Tasks_Module.tdl`)

```
Module {
    Style: Tasks_Style.tdl
    Params {
        show_title { Type: boolean, Default: true }
        max_width { Type: number, Default: 180 }
        icon_size { Type: number, Default: 18 }
        monitor { Type: enum, Values: [THIS, ALL], Default: THIS }
        desktop { Type: enum, Values: [CURRENT, ALL], Default: CURRENT }
        show_empty { Type: boolean, Default: false }
    }

    FlexBox {
        Flex: HORIZONTAL
        On_Scroll { Action: cycle, delta: <| event.delta |> }
        Children {
            For w In <| windows |> Key <| w.id |> {
                Task_Item {
                    icon: <| w.icon |>
                    title: <| w.title |>
                    Selected: <| w.active |>
                    On_Click { Action: activate, id: <| w.id |> }
                    On_Middle_Click { Action: close, id: <| w.id |> }
                }
            }
        }
    }
}
```

A sketch; the code session aligns spellings with what is built. `Task_Item` is a small module in the same folder: an Icon and, when `show_title`, a Marquee text capped at `max_width`; a minimised window is drawn dimmed and one that wants attention uses the warning token.

## Configuration

| Param | Type | Default | Meaning |
|---|---|---|---|
| `show_title` | boolean | true | The window's title beside the icon |
| `max_width` | number | 180 | The widest a button gets, in pixels |
| `icon_size` | number | 18 | The icon's size |
| `monitor` | `THIS`, `ALL` | `THIS` | Windows on the module's own monitor, or on all |
| `desktop` | `CURRENT`, `ALL` | `CURRENT` | Windows on the current virtual desktop, or on all |
| `show_empty` | boolean | false | Keep the module's space when there is no window |

## Needs from the Shell

All inside `tess-shell`:

| Need | Shape |
|---|---|
| The KWin script, first build | The package of [KWin Integration > The KWin script](../Integration/KWin%20Integration.md#the-kwin-script) with both reports; loaded at run time (mode R) |
| The interface methods | `FullscreenState(s) -> s` and `WindowsState(s) -> s` on the shell's interface, each returning the small JSON reply; added to [IPC and CLI](../Runtime/IPC%20and%20CLI.md) |
| A window service | `ctx.windows`: `on_changed(callback)`, `list()`, `activate(id)`, `minimize(id)`, `close(id)`, `available`; the shell counts the uses that want the list and enables it |
| The desktop-entry index | `ctx.icons.app_icon(app, size)` over the cached index |

## Python Contract

One instance. It subscribes to `ctx.windows`, filters per use and sends. The actions call the service and return at once. No timer, no thread, no subprocess.

## Integration

- KWin: the script and `/Scripting`, on the service thread; the incoming call is handed to the loop with `call_soon`.
- Tests: KWin cannot be started inside the code session's private sway, and nothing may be loaded into the maintainer's real KWin ([Orchestration Log](../../00%20Home/Orchestration%20Log.md) D-019). So: a fake `/Scripting` service and a fake script (a test client that calls `WindowsState` with recorded lists) on a private bus prove the shell side; the script's own logic is tested by running `main.js` under a JavaScript engine with a stub `workspace` if one is installed, and otherwise by a nested `kwin_wayland --virtual` inside the sandbox if that starts. What neither reaches is listed as a hand check.

## Accessibility

Each button's name is the window's title and application, with "active", "minimised" or "wants attention" said in words. The row is a list. Keyboard operation is M6.

## Performance Budget

- Idle: nothing is sent and nothing wakes while no window changes.
- A `WindowsState` of 50 windows to the row updated: under 16 ms of the shell's work.
- An action: the window reacts within 100 ms of the click (the one-shot script's load is the cost; measured by hand on KWin).
- A title that changes many times a second (a terminal, a browser tab) causes at most one update per frame for that button.

## Failure Modes and Recovery

| Failure | Result |
|---|---|
| Not KWin, or the script fails to load | The module is hidden; one warning from the script loader ([KWin Integration > Failure modes and recovery](../Integration/KWin%20Integration.md#failure-modes-and-recovery)) |
| The script is silent after enable (5 s) | One warning; hidden |
| A malformed `WindowsState` string | Ignored, with one warning; the last list stays |
| An action's script fails to load | One warning; nothing changes |
| A window closes between the list and a click | The action finds no window and does nothing |
| No icon for an application | `application-outline` |
| The shell stops | The script is unloaded |

## Open Questions

Decided by the orchestrator on 2026-11-13 ([Tesserae Shell Directive](../../00%20Home/Tesserae%20Shell%20Directive.md) rule 7, Tier 1).

1. [x] Where does the window list come from? The shell's KWin script; not the `org_kde_plasma_window_management` protocol, which tre does not expose.
2. [x] May the script send titles and ids? Only while a Tasks module is in use (see the change above).
3. [x] How does the shell act on a window? A one-shot script per action.
4. [x] Are windows grouped by application? Not in v1.
5. [x] What does a click on the active window do? Minimises it.

## Questions After Testing

1. [ ] Do the scripting properties and signals named above exist with those names on KWin 6.8.1, and does a one-shot script activate, minimise and close a window? Context: several names are from KDE's API page, not from the 2026-10-29 run. Recommendation: build to the page, and correct from the first real run. Answered by: a hand run on the maintainer's KWin, or a nested KWin if the code session can start one in the sandbox.
2. [ ] How long does a one-shot script take from the click to the window reacting? Context: the budget is 100 ms. Recommendation: keep one-shot scripts if under 100 ms. Answered by: the same run, timed.

## Acceptance Criteria

- [ ] With no Tasks module in use the shell replies `{"windows": false}` and no `WindowsState` call is expected; a test proves the shell ignores one that arrives anyway and logs no title.
- [ ] With a Tasks use, the fake script's list appears as buttons in the script's order; the active window is marked; a minimised one is dimmed.
- [ ] `monitor: THIS` shows only windows whose `output` is the use's monitor; `desktop: CURRENT` only windows on the current desktop or on all desktops; two uses on two monitors show different rows.
- [ ] A new list with one title changed updates one button and creates no node.
- [ ] A primary click on an inactive window asks the fake `/Scripting` to load the activate script for that id; on the active window, the minimise script; a middle click, the close script.
- [ ] A malformed string leaves the row as it was and logs one warning without the string's content.
- [ ] The shell's surfaces never appear in the row (a list containing a `skipTaskbar` entry is a script fault; the shell also drops entries whose `app` starts with `tesserae-shell.`).
- [ ] With no window change, no wake-ups over 60 seconds.
- [ ] No test loads a script into a real KWin or reaches the real session bus.

## Links

- [Modules](Modules.md) · [KWin Integration](../Integration/KWin%20Integration.md) · [IPC and CLI](../Runtime/IPC%20and%20CLI.md) · [Tray Module](Tray%20Module.md) · [Workspaces Module](Workspaces%20Module.md) · [Module Context](../../42%20Python%20API/Module%20Context.md) · [M5 Brief](../../00%20Home/M5%20Brief.md) · [Tesserae Shell Directive](../../00%20Home/Tesserae%20Shell%20Directive.md)
