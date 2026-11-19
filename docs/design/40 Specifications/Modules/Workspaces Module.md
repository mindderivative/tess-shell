---
title: Workspaces Module
aliases: [Workspaces, Workspaces_Module, Virtual Desktops Module]
type: spec
status: draft
owner: phil
created: 2026-11-06
updated: 2026-11-14
tags: [spec/module, integration/dbus, needs-verification]
---

# Workspaces Module

> [!NOTE]
> The Workspaces module shows KWin's virtual desktops as a row of buttons, marks the current one, and switches desktop on a click. It reads `org.kde.KWin` on the session bus (`/VirtualDesktopManager`), follows its change signals, and never polls. It uses the empty-state rule from [Battery Module](Battery%20Module.md) (`available` plus `If`) and is the first module with a click action that carries an argument. All names and TDL below are proposals built on [Battery Module](Battery%20Module.md), [Module File](../../41%20TDL%20Reference/Module%20File.md) and [Events and Actions](../../42%20Python%20API/Events%20and%20Actions.md). The KWin members were read on the maintainer's machine on 2026-11-06 (read-only `busctl` calls, KWin 6.8.2, two desktops named `Main` and `Code`); no method that changes state was called, so switching is unverified.

## Purpose and Scope

- Show the virtual desktops in order, mark the current one, and switch on a click.
- v1: a flat list in the order KWin gives. Not in v1: the desktop grid (`rows`) as a grid, a per-desktop window count or an "occupied" mark (that needs the window list, M5g with Tasks, [M5 Brief](../../00%20Home/M5%20Brief.md) G1), creating, renaming or removing desktops, scroll to switch ([Open Questions](#open-questions)).

## Files

```
Modules/Workspaces/
    Workspaces_Module.tdl
    Workspaces_Style.tdl
    Workspaces_Module.py
```

## Behaviour

### What It Reads

| Item | Value | Read on 2026-11-06 |
|---|---|---|
| Bus | session | n/a |
| Name | `org.kde.KWin` | Present (KWin 6.8.2) |
| Path | `/VirtualDesktopManager` | Present |
| Interface | `org.kde.KWin.VirtualDesktopManager` | Present |

| Member | Type | Use | Read |
|---|---|---|---|
| `desktops` | array of (number, id, name), `emits-change` | The list, in KWin's order | `(0, "58d47c1b-e24b-489d-a2da-7897636d1cbf", "Main")` and `(1, "c261655f-27dc-408d-9e26-bf3834652409", "Code")` |
| `current` | string (a desktop id), `emits-change`, writable | The current desktop; the switch target | `58d47c1b-e24b-489d-a2da-7897636d1cbf` |
| `count` | uint32, `emits-change` | Not used (the list has it) | 2 |
| `rows` | uint32, `emits-change`, writable | Not used in v1 | 1 |
| `navigationWrappingAround` | boolean, writable | Not used | true |
| `currentChanged(s)` | signal | Redundant with the property change; either may be used | Seen on 2026-10-26 ([System Context > Observed D-Bus names](../../20%20Architecture/System%20Context.md#observed-d-bus-names)) |
| `desktopCreated`, `desktopRemoved`, `desktopDataChanged` | signals | The list changed | Listed in the interface, not seen firing |
| `setDesktopName`, `createDesktop`, `removeDesktop` | methods | Not used in v1 | Listed |

The `/KWin` object has `currentDesktop` (read as 1, the current desktop's number counted from 1), `setCurrentDesktop(int)` returning a boolean, `nextDesktop` and `previousDesktop` ([KWin Integration](../Integration/KWin%20Integration.md)).

> [!WARNING]
> **A signature that disagrees**
> `busctl introspect` printed the type of `desktops` as `a(iss)`, but `get-property` printed `a(uss)` (an unsigned number first, then two strings), and the numbers read were `0` and `1`. The module reads the value as it arrives and treats the first field as an integer. A test pins the shape on the fake service. #needs-verification: against KWin's source or a second KWin version.

The number in `desktops` counts from 0 here, and `currentDesktop` counts from 1. The module never shows the raw field as a label: `number` below is the list position plus 1.

### Values Sent

The Python sends these keys to every use (`ctx.send(key, value)`):

| Key | Type | Meaning |
|---|---|---|
| `available` | boolean | True when KWin is on the bus and `desktops` was read. False when KWin is not the compositor or has left the bus ([M5 Brief](../../00%20Home/M5%20Brief.md), G2) |
| `desktops` | list of records | One record per desktop, in KWin's order: `id` (string), `number` (1-based), `name` (string), `label` (the text to show), `current` (boolean) |
| `current` | string | The current desktop's id |

A `For` over `desktops` keys each entry by `id`, so a desktop that is renamed or reordered keeps its node and only its text or class changes ([TDL Language > Structure Words](../../41%20TDL%20Reference/TDL%20Language.md#structure-words), [Render Binder Design](../../20%20Architecture/Render%20Binder%20Design.md)). The list value changes when the current desktop changes (the `current` flags move), so the keyed diff updates two buttons and no more.

`label` follows the param `label`: the desktop's `name` when `name`, or `number` as text when `number`. A desktop with an empty name shows its number.

### Layout (`Workspaces_Module.tdl`)

```
---
TDL: 0.2
TEL: 0.1
TRE: 0.5.9
Shell: 0.1
Name: Workspaces
---

Module {
    Style: Workspaces_Style.tdl
    Params {
        # name or number
        label { Type: string, Default: name }
    }

    If <| available |> {
        FlexBox {
            Flex: HORIZONTAL
            Children {
                For desktop In <| desktops |> Key <| desktop.id |> {
                    FlexBox {
                        Class: workspace
                        On_Click { Action: switch, Id: <| desktop.id |> }
                        Children {
                            Text {
                                Text: <| desktop.label |>
                                Class: workspace_text
                            }
                        }
                    }
                }
            }
        }
    }
}
```

A sketch. The `For` form is in [TDL Language > Structure Words](../../41%20TDL%20Reference/TDL%20Language.md#structure-words) and the handler form `On_Click { Action: name, Arg: value }` is built for module layouts ([M3 Build Log](../../00%20Home/M3%20Build%20Log.md), B1). Two things it relies on are not confirmed:

- The handler goes on the box around the `Text`, because a `Text` takes no listener ([Building Blocks](../../50%20Design%20System/Building%20Blocks.md), tre's design).
- The `<| desktop.id |>` slot inside a handler's argument, in a `For` entry. B1 built plain argument values; a slot that reads the loop variable is not confirmed, and D59 refused a slot in a shell-file block for `ctx.popup` data. If it is not built, M5b builds it first (a small addition to [Events and Actions](../../42%20Python%20API/Events%20and%20Actions.md), proposed): see [Open Questions](#open-questions).

The current desktop's button needs the class `workspace_current` on top of `workspace`; the style gives it the primary colour from the theme tokens ([Style Schema](../../41%20TDL%20Reference/Style%20Schema.md)), and the hover and pressed states come from the stylesheet rules M3b built. How a block takes a class that depends on a value is not confirmed: `Class` takes a name or a list ([Block Reference](../../41%20TDL%20Reference/Block%20Reference.md)), and whether it takes a `<| |>` slot (for example `Class: <| desktop.current ? [workspace, workspace_current] : [workspace] |>`) is open ([Open Questions](#open-questions), 7). The alternative is a `current` flag that a style state reads.

## Configuration

| Param | Type | Default | Meaning |
|---|---|---|---|
| `label` | string | `name` | `name` shows each desktop's name, `number` shows 1, 2, 3 |

## Python Contract

```python
from tess_shell import Module, action

class Workspaces(Module):
    def start(self):
        bus = self.ctx.dbus.session()
        self.vdm = bus.proxy("org.kde.KWin", "/VirtualDesktopManager")
        self.vdm.on_property_changed(self.changed)    # dbus thread, short
        self.refresh()                                # GetAll once, then signals only

    def on_service_lost(self, name):
        self.ctx.send("available", False)

    def on_service_found(self, name):
        self.refresh()

    @action
    def switch(self, event):
        # a call on the dbus thread; the module does not wait on the loop thread
        self.vdm.set("current", event.args["Id"])
```

An illustration of the shape, not tested code. What it shows:

- One instance, one proxy, for every use. The list is the same on every monitor, because KWin's virtual desktops belong to the session, not to an output.
- `refresh` reads `desktops` and `current` once with `GetAll`, builds the records and sends `desktops`, `current` and `available`. After that, `PropertiesChanged` moves them. The `desktopCreated`, `desktopRemoved` and `desktopDataChanged` signals trigger the same `refresh`.
- `switch` sets the `current` property. This is the first call in the shell that changes the desktop's state, so it was not run while writing this note. The fallback is `/KWin setCurrentDesktop(int)` with the 1-based number. #needs-verification which of the two a KDE 6 session accepts from a client that is not plasmashell.
- Coalescing: a burst of signals (creating a desktop emits several) is one `refresh` per loop turn, and the value store sends only a changed list ([Module Context > Sending values](../../42%20Python%20API/Module%20Context.md#sending-values)).

## Integration

- Service: KWin on the session bus. It is not activatable. When the compositor is not KWin the name has no owner and the module is hidden ([D-Bus Service Layer > Calling a Service](../Integration/D-Bus%20Service%20Layer.md#calling-a-service)). This is the expected state on sway.
- Threads: callbacks on the `dbus` thread; `ctx.send` crosses to the loop; the click action runs on the loop thread and starts the call on the `dbus` thread ([Process Model and Threading](../../20%20Architecture/Process%20Model%20and%20Threading.md)).
- Plasma: plasmashell's own pager reads the same service. Both read; the shell writes only on a click ([Plasma Coexistence](../Integration/Plasma%20Coexistence.md)).
- No file, no subprocess.

## Design

A row of boxes with a text each; the current one has the primary colour. The look comes from the theme ([Style Schema](../../41%20TDL%20Reference/Style%20Schema.md), [50 Design System](../../50%20Design%20System/50%20Design%20System.md)). A desktop name can be long: the style gives a button a maximum width. How an over-long text is cut (an ellipsis or a clip) is not defined in [Block Reference](../../41%20TDL%20Reference/Block%20Reference.md) and is left to the design system.

## Accessibility

- Each button is a `BUTTON` with the accessible name `Desktop 2, Code` (number and name) and a state that says it is the current one, not only a colour ([Block Reference](../../41%20TDL%20Reference/Block%20Reference.md), [Building Blocks](../../50%20Design%20System/Building%20Blocks.md)).
- The row is a group named `Workspaces`. Enter and Space activate a focused button like a click ([Block Reference](../../41%20TDL%20Reference/Block%20Reference.md)).
- A change of the current desktop is not announced by the module; the desktop's own switcher does that.

## Performance Budget

- Idle: no timer. Wake-ups follow KWin's signals ([D-Bus Service Layer > Performance Budget](../Integration/D-Bus%20Service%20Layer.md#performance-budget)).
- A switch updates two buttons through the keyed diff (a class change on each), not the whole row.
- Per signal: under 1 ms of the module's own work on the `dbus` thread. Measured on a real session by the maintainer (switch ten times; log the time from signal to `ctx.send`).

## Failure Modes and Recovery

| Failure | Result |
|---|---|
| KWin is not the compositor (sway, a session without KWin) | `available` false; the module is hidden; one info line in the log |
| KWin restarts | `on_service_lost` hides the module; `on_service_found` re-reads and shows it |
| `desktops` is empty or has an unexpected shape | The key keeps its last value and one warning names the property; with no value yet the module stays hidden |
| `switch` is called with an id that is not in the list | The call is refused by the module and logged once; nothing changes |
| The call to set `current` fails or times out | `ServiceTimeout` or the bus error is logged once per minute; the buttons keep showing the current desktop, which did not change |
| A desktop is removed while the module holds its id | The next `refresh` drops it; a click that was already on its way is refused as above |
| The callback raises | Caught and logged with the module name; the module keeps running ([Module Contract](../../42%20Python%20API/Module%20Contract.md)) |

## Built in M5b (code session's report, 2026-11-12, not run in the vault)

- The module is `shipped/Workspaces/`. It sends `ready` and the layer owns `available`; the root is `Visible: <| available and ready |>`.
- A click sets KWin's `current` on the `dbus` thread; the entry id reaches the action through an argument slot. `label` (`name` or `number`) is applied in the layout; both `a(uss)` and `a(iss)` desktop lists are accepted.
- The current desktop is shown with `Selected: <| desktop.current |>` and the `:selected` state, because a `Class` from a value is not built.
- Per-signal work p50 15 us, p99 36 to 58 us on a fake KWin; the checklist `/tmp/tess-kwin-m5b` has a run whose click switches the real desktop. The maintainer's KWin run on 2026-11-13 passes after one fix (the current-desktop marker).

## Open Questions

1. [ ] How does the click pass the id of the clicked entry to the action? Context: the click needs the desktop id; the alternative (the action maps the entry's block name back to an id) breaks when entries are reordered. Recommendation: `On_Click { Action: switch, Id: <| desktop.id |> }` with a `For` variable allowed in an argument slot, and `event.args` carrying the evaluated value. If that is not built, M5b adds it before this module.
2. [ ] Should scroll on the row switch desktops (`On_Scroll`)? Context: it is a common pager gesture, but v1 has no other scroll use. Recommendation: after v1, with the other scroll uses.
3. [ ] How should the module treat a desktop grid? Context: with `rows` greater than 1, KWin lays desktops in a grid. Recommendation: v1 shows one row in KWin's order and ignores `rows`.
4. [ ] Should each desktop show an occupied or window-count mark? Context: it needs the window list, which arrives with Tasks in M5g ([M5 Brief](../../00%20Home/M5%20Brief.md), G1). Recommendation: not in v1; add it after M5g.
5. [ ] Should a class that depends on a value (the current button) use a `<| |>` slot in `Class`, or a state key? Context: a module needs it for every on/off look (Battery's `low` and `critical` have the same need, [Battery Module](Battery%20Module.md)). Recommendation: allow the slot.

## Questions After Testing

Answered by: the first test on a real KWin session, and a D-Bus read of the desktop list.

6. [ ] Which call switches desktops: setting `current` or `/KWin setCurrentDesktop(int)`? Context: `current` names the desktop by id; the KWin call uses a number and can race a reorder. Read-only checks cannot answer it. Recommendation: set `current`.
7. [ ] Is the type of `desktops` `a(iss)` or `a(uss)`? Context: see the warning above; the wrong signature fails the call. Recommendation: read the property on a real session and use what it returns. #needs-verification

## Acceptance Criteria

- [ ] On KWin with two desktops, the module shows two buttons labelled with the names, and the first is marked current.
- [ ] Switching desktop with the keyboard or the desktop's own switcher moves the mark within one loop turn after the signal.
- [ ] A click on the second button makes it the current desktop, and the mark follows.
- [ ] Creating or removing a desktop in System Settings adds or removes a button, and the other buttons keep their nodes (the keyed diff).
- [ ] Renaming a desktop changes only that button's text.
- [ ] `label: number` shows 1, 2, 3; an empty name shows the number.
- [ ] On sway (no KWin) the module is hidden and logs one info line.
- [ ] Restarting KWin hides the module, then shows it again, with no shell restart (fake service in the test; the real restart is the maintainer's check).
- [ ] With no signal traffic the module causes no wake-ups over 60 seconds.
- [ ] The Python never blocks the loop and starts no thread.
- [ ] On a fake service on a private bus: every case above except the real click on KWin passes.

## Links

- [Modules](Modules.md) · [Battery Module](Battery%20Module.md) · [Clock Module](Clock%20Module.md) · [D-Bus Service Layer](../Integration/D-Bus%20Service%20Layer.md) · [KWin Integration](../Integration/KWin%20Integration.md) · [Events and Actions](../../42%20Python%20API/Events%20and%20Actions.md) · [Module Contract](../../42%20Python%20API/Module%20Contract.md) · [Module Context](../../42%20Python%20API/Module%20Context.md) · [M5 Brief](../../00%20Home/M5%20Brief.md) · [V1 Scope](../../10%20Vision/V1%20Scope.md)
