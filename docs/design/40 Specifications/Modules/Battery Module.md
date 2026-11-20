---
title: Battery Module
aliases: [Battery, Battery_Module]
type: spec
status: draft
owner: phil
created: 2026-11-05
updated: 2026-11-14
tags: [spec/module, integration/dbus, needs-verification]
---

# Battery Module

> [!NOTE]
> The Battery shows the charge of the machine's battery: an icon, a percentage, and a tooltip with the state and the time left. It reads UPower's aggregate "display device" on the system bus and watches `PropertiesChanged`; it never polls. On a machine with no battery (a desktop) it hides itself. It is the first service module and sets the pattern for the others ([M5 Brief](../../00%20Home/M5%20Brief.md)): the `available` value, the hooks for a service that leaves, and a test on a fake service. All names and TDL below are proposals built on [Clock Module](Clock%20Module.md), [Module File](../../41%20TDL%20Reference/Module%20File.md) and [Module Context](../../42%20Python%20API/Module%20Context.md); nothing is final. The UPower members were read on the maintainer's machine on 2026-11-05 (read-only `busctl` calls; UPower 1.91.5, a desktop with no battery) and checked against the [UPower Device documentation](https://upower.freedesktop.org/docs/Device.html).

## Purpose and Scope

- Show the charge level, the charging state and the time to empty or full, for the machine's battery as UPower aggregates it.
- Warn at the levels the desktop sets (UPower's `WarningLevel`), not at levels the shell invents.
- v1: read-only. Not in v1: per-device lists (mouse, keyboard, phone batteries), history graphs, charge thresholds, switching the power profile ([Open Questions](#open-questions)).

## Files

```
Modules/Battery/
    Battery_Module.tdl     the layout and its params
    Battery_Style.tdl      the look
    Battery_Module.py      the logic
```

## Behaviour

### What It Reads

The shell talks to one object, the display device. UPower builds it from every battery in the machine, so a laptop with two batteries shows one level ([UPower Device](https://upower.freedesktop.org/docs/Device.html)).

| Item | Value | Read on 2026-11-05 |
|---|---|---|
| Bus | system | n/a |
| Name | `org.freedesktop.UPower` | Present |
| Path | `/org/freedesktop/UPower/devices/DisplayDevice` | Present (`GetDisplayDevice` on `/org/freedesktop/UPower` returns an object path) |
| Interface | `org.freedesktop.UPower.Device` | Present |

| Property | Type | Use | Notes |
|---|---|---|---|
| `IsPresent` | boolean | Decides `available` | False on this desktop |
| `Type` | uint32 | Checked: 2 is a battery | Read as 0 here (no battery), so the module trusts `IsPresent`, not `Type` alone |
| `Percentage` | double, 0 to 100 | The number and the icon step | Valid only when `Type` is a battery |
| `State` | uint32 | The icon and the tooltip | 0 unknown, 1 charging, 2 discharging, 3 empty, 4 fully charged, 5 pending charge, 6 pending discharge |
| `TimeToEmpty`, `TimeToFull` | int64, seconds | The tooltip | 0 means unknown |
| `WarningLevel` | uint32 | `low` and `critical` | 0 unknown, 1 none, 2 discharging (UPS only), 3 low, 4 critical, 5 action |
| `IconName` | string | Not used (see below) | `battery-missing-symbolic` here |

All of these were seen with the flag `emits-change`, so `PropertiesChanged` carries them. `/org/freedesktop/UPower` also has `OnBattery` and `LidIsPresent`; v1 does not use them.

### Values Sent

The Python sends these keys to every use of the module (`ctx.send(key, value)`, [Module Context > Sending values](../../42%20Python%20API/Module%20Context.md#sending-values)):

| Key | Type | Meaning |
|---|---|---|
| `available` | boolean | True when UPower is on the bus and `IsPresent` is true. The layout hides itself on false ([M5 Brief](../../00%20Home/M5%20Brief.md), G2) |
| `percent` | number | `Percentage` rounded to a whole number |
| `state` | string | `CHARGING`, `DISCHARGING`, `FULL`, `EMPTY` or `UNKNOWN`; pending states map to the state they are about to leave (`PENDING_CHARGE` is `FULL` if the level is 100, else `UNKNOWN`) |
| `icon` | string | The name of an `mdi` icon chosen from `percent` and `state` ([Icon](#icon)) |
| `low`, `critical` | boolean | True from `WarningLevel` 3, and from 4 or 5 (`critical`) |
| `tooltip` | string | For example `82 %, discharging, 2 h 14 min left` |

A value is sent only when it changes. The value store coalesces repeated sends in one loop turn ([Module Context > Sending values](../../42%20Python%20API/Module%20Context.md#sending-values)).

### Icon

UPower gives `IconName`, an icon-theme name. The shell resolves no system icon theme before the Tray part of M5 ([M5 Brief](../../00%20Home/M5%20Brief.md), G8), so the module does not use it. It picks from the `mdi` set the shell ships:

| `state` | `percent` | Icon |
|---|---|---|
| `DISCHARGING` or `UNKNOWN` | rounded down to 10, 20 to 90 | `battery-10` to `battery-90`; below 10 and above 90 the unnumbered `battery-alert` and `battery` |
| `CHARGING` | same steps | `battery-charging-10` to `battery-charging-90`; at 100 `battery-charging-100` |
| `FULL` | 100 | `battery-charging-100` on mains, `battery` otherwise: v1 uses `battery` |
| `EMPTY` | 0 | `battery-alert-variant-outline` |
| `UNKNOWN` with no reading | none | `battery-unknown` |

#needs-verification: each name against the `mdi` set the package ships ([Risk Register](../../00%20Home/Risk%20Register.md) R-23). The table is a proposal until the names are checked in the set; a missing name is a build-time test failure, not a runtime surprise.

### Hiding

`available` is false when:

- UPower is not on the system bus (`NameHasNoOwner`, `ServiceUnknown`, the system bus is unreachable), or
- `IsPresent` is false.

The module's layout wraps its children in `If <| available |>` ([M5 Brief](../../00%20Home/M5%20Brief.md), G2), so the Bar's layout closes up. The module does not show a "no battery" placeholder. When UPower returns, or a battery is plugged in (`IsPresent` becomes true, as with a hot-swappable bay), the module re-reads and shows itself.

### Layout (`Battery_Module.tdl`)

```
---
TDL: 0.2
TEL: 0.1
TRE: 0.5.9
Shell: 0.1
Name: Battery
---

Module {
    Style: Battery_Style.tdl
    Params {
        # show the number next to the icon
        show_percent { Type: boolean, Default: true }
    }

    If <| available |> {
        FlexBox {
            Flex: HORIZONTAL
            Children {
                Icon {
                    Icon: <| icon |>
                    Class: battery_icon
                }
                If <| show_percent |> {
                    Text {
                        Text: <| percent |> %
                        Class: battery_text
                    }
                }
            }
        }
    }
}
```

A sketch. The `Icon` module's key for a named icon, the slot form inside a text, and `If` around a block follow [Module File](../../41%20TDL%20Reference/Module%20File.md), [Block Reference](../../41%20TDL%20Reference/Block%20Reference.md) and [TDL Language](../../41%20TDL%20Reference/TDL%20Language.md); none is re-decided here. `low` and `critical` select a class in the style file (`battery_low`, `battery_critical`), which the theme colours with the warning and error tokens ([Style Schema](../../41%20TDL%20Reference/Style%20Schema.md)). How a block takes a class from a value is an open question shared with [Workspaces Module > Open Questions](Workspaces%20Module.md#open-questions) (item 7).

## Configuration

| Param | Type | Default | Meaning |
|---|---|---|---|
| `show_percent` | boolean | true | The number next to the icon |

There is no threshold param: the desktop's `WarningLevel` decides `low` and `critical`. A user who wants their own levels uses the `percent` value in a TEL condition in their own layout.

## Python Contract

The class follows [Module Contract](../../42%20Python%20API/Module%20Contract.md) and the additions in [D-Bus Service Layer > Python Contract](../Integration/D-Bus%20Service%20Layer.md#python-contract).

```python
from tess_shell import Module

DEVICE = "/org/freedesktop/UPower/devices/DisplayDevice"

class Battery(Module):
    def start(self):
        bus = self.ctx.dbus.system()
        self.dev = bus.proxy("org.freedesktop.UPower", DEVICE)
        self.dev.on_property_changed(self.changed)      # on the dbus thread, short
        self.refresh()                                  # GetAll once, then signals only

    def on_service_lost(self, name):
        self.ctx.send("available", False)

    def on_service_found(self, name):
        self.refresh()
```

An illustration of the shape, not tested code. What it shows:

- One instance, one proxy, for every use. There is no per-use state, so it never sends with `use=`.
- `refresh` reads the properties once with `GetAll`; after that only `PropertiesChanged` moves values. No timer ([D-Bus Service Layer > Calling a Service](../Integration/D-Bus%20Service%20Layer.md#calling-a-service), rule 4).
- The callback only reads the changed properties, derives the keys and calls `ctx.send`, which crosses to the loop. It does no other work ([D-Bus Service Layer > The Service Thread](../Integration/D-Bus%20Service%20Layer.md#the-service-thread)).
- `on_service_lost` and `on_service_found` are the hooks of [Module Contract](../../42%20Python%20API/Module%20Contract.md) (decided 2026-11-12, [D-Bus Service Layer](../Integration/D-Bus%20Service%20Layer.md)).

## Integration

- Service: UPower on the system bus, the display device above. UPower is activatable: the name is owned when the daemon runs, and a first call starts it ([D-Bus Service Layer > Activation](../Integration/D-Bus%20Service%20Layer.md#activation)).
- Threads: callbacks on the `dbus` thread; `ctx.send` crosses to the loop; no worker thread ([Process Model and Threading](../../20%20Architecture/Process%20Model%20and%20Threading.md)).
- Plasma: plasmashell shows its own battery applet from the same service. Both read; neither writes ([Plasma Coexistence](../Integration/Plasma%20Coexistence.md)).
- No file, no network, no subprocess.

## Design

An `Icon` and a `Text`, a style class per warning level. The look comes from the theme; the colours for `low` and `critical` are tokens ([Style Schema](../../41%20TDL%20Reference/Style%20Schema.md), [50 Design System](../../50%20Design%20System/50%20Design%20System.md)).

## Accessibility

- The group exposes a name that includes the level and the state, for example `Battery 82 percent, discharging`, not only the icon ([D-Bus Service Layer > Accessibility](../Integration/D-Bus%20Service%20Layer.md#accessibility), [Building Blocks](../../50%20Design%20System/Building%20Blocks.md)).
- State is never colour only: the icon changes shape with the level and the charging bolt.
- A change of `percent` is not announced. A change to `critical` is announced once (proposed). #needs-verification against how tre publishes live regions ([TRE-REQ-001 Layer Surface Window > Delivered (tre #195 closed)](../../80%20Requests/TRE-REQ-001%20Layer%20Surface%20Window.md#delivered-tre-195-closed)).
- The tooltip text is the description.

## Performance Budget

- Idle: no timer. Wake-ups follow UPower's signals; the module sends a value only when it changed, so a refresh that changes nothing costs no frame ([Performance Budgets](../../60%20Quality/Performance%20Budgets.md)).
- Per signal: under 1 ms of the module's own work on the `dbus` thread (the layer's callback budget, proposed in [D-Bus Service Layer](../Integration/D-Bus%20Service%20Layer.md)).
- UPower can emit `TimeToEmpty` changes often while discharging. The module sends `tooltip` only when its text changes, which is at most once a minute because the text shows minutes. #needs-verification: how often UPower emits on a real laptop; this machine has no battery, so it is measured by the maintainer on one, or not at all (the maintainer chose the fake service for tests, 2026-11-05).

## Failure Modes and Recovery

| Failure | Result |
|---|---|
| UPower is not on the bus at start | `available` false; the module hides; recovers on `on_service_found` |
| UPower restarts | `on_service_lost` hides the module; `on_service_found` re-reads and shows it |
| `IsPresent` is false (a desktop) | `available` false; the module is hidden and logs nothing |
| The system bus is unreachable | `available` false; one warning logged by the layer; the shell runs |
| A call times out | `ServiceTimeout` is logged once per service per minute; the last values stay |
| A property has an unexpected type or value | The key keeps its last value and one warning names the property |
| An `mdi` name in the icon table is not in the set | Caught by the build-time test; at run time the module sends `battery-unknown` |
| The callback raises | Caught, logged with the module name; the module keeps running ([Module Contract](../../42%20Python%20API/Module%20Contract.md)) |

## Built in M5b (code session's report, 2026-11-12, not run in the vault)

- The module is `shipped/Battery/`. It sends `present` and the layer owns `available`; the module's root is `Visible: <| available and present |>`, so a hidden Battery takes no Bar Spacing.
- The icon is chosen at run time through the icon slot (`Icon: <| expr |>`), which removed the 24 `If` branches; the icon takes the level colour. Low and critical colour the text and a dot (there is no `Class` from a value yet).
- Pending states 5 and 6 map to `FULL` at 100 % and otherwise `UNKNOWN`; charging below 10 % is `battery-charging-outline` and 91 to 99 % is `battery-charging-90`.
- `profile` is sent and read-only; nothing reads it until the Menu that switches profiles.
- A service that leaves logs one WARNING a minute.
- Measured on fake services: per-signal work p50 6.9 us, p99 36 us; idle 60 s with both M5b modules 0 wakes on the `dbus` thread. No real battery was read; the maintainer's KWin check with a fake battery on a private bus passes (2026-11-13).

## Open Questions

1. [ ] Should v1 read the power profile only, or also change it? Context: the power-profile service exists on this machine (read 2026-11-05: bus name and interface `org.freedesktop.UPower.PowerProfiles`, path `/org/freedesktop/UPower/PowerProfiles`, `ActiveProfile` read as `performance` and writable, `Profiles` listing `power-saver`, `balanced` and `performance`). The UPower documentation page for it was not found (404), so only the machine read supports this. #needs-verification. Recommendation: v1 sends a read-only `profile` value and does not change it; switching needs a `Menu` and a state-changing call, and waits until after M5.
2. [ ] In which language is the tooltip? Context: the text is built in Python (`82 %, discharging, 2 h 14 min left`). Recommendation: English in v1, with the wording in one table so a later locale param can swap it, as the Clock does with `locale` ([Clock Module](Clock%20Module.md)).
3. [ ] Does `FULL` on mains show `battery-charging-100` (a bolt) or `battery`? Context: `OnBattery` on `/org/freedesktop/UPower` would tell mains from battery and is not read. Recommendation: `battery` in v1.
4. [ ] Should the module cover other devices (a mouse or a headset battery)? Context: they are separate devices on UPower. Recommendation: not in v1; a later `Devices` module using `EnumerateDevices`, not this module.

## Questions After Testing

Answered by: a check of every `mdi` name in the icon table against the shipped icon set.

5. [ ] Do all the `mdi` names in the icon table exist in the shipped set? Context: a missing name shows no icon. Recommendation: run the check before M5 starts this module and rename any that fail. #needs-verification

## Acceptance Criteria

- [ ] On this desktop (`IsPresent` false) the module is hidden and logs nothing.
- [ ] On a fake UPower service on a private bus, setting `IsPresent` true with `Percentage` 82 and `State` 2 shows the icon `battery-80`, the text `82 %` and the tooltip with the state and the time left.
- [ ] Changing `State` to 1 (charging) changes the icon to `battery-charging-80` within one loop turn after the signal.
- [ ] `WarningLevel` 3 sets `low`, 4 sets `critical`; the style class changes.
- [ ] Removing the fake service hides the module and logs one warning; bringing it back shows the module again, with no shell restart.
- [ ] `TimeToEmpty` 0 leaves the time out of the tooltip.
- [ ] With no signal traffic, the module causes no wake-ups over 60 seconds (measured in the layer's test, [D-Bus Service Layer > Acceptance Criteria](../Integration/D-Bus%20Service%20Layer.md#acceptance-criteria)).
- [ ] The Python never blocks the loop and starts no thread.
- [ ] Every icon name in the table exists in the shipped `mdi` set (a test).

## Links

- [Modules](Modules.md) · [Clock Module](Clock%20Module.md) · [D-Bus Service Layer](../Integration/D-Bus%20Service%20Layer.md) · [Module Contract](../../42%20Python%20API/Module%20Contract.md) · [Module Context](../../42%20Python%20API/Module%20Context.md) · [M5 Brief](../../00%20Home/M5%20Brief.md) · [V1 Scope](../../10%20Vision/V1%20Scope.md)
