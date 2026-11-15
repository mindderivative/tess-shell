---
title: Network Module
aliases: [Network, Network_Module, NetworkManager Module]
type: spec
status: accepted
owner: phil
created: 2026-11-13
updated: 2026-11-14
tags: [spec/module, integration/dbus, needs-verification]
---

# Network Module

> [!NOTE]
> The Network module shows how the machine is connected: an icon for the kind of connection (wired, Wi-Fi, mobile, Bluetooth, other), the state (connected, no internet, connecting, disconnected, networking off), the Wi-Fi signal strength in steps, a second icon when a VPN is up, and a tooltip with the connection name and the details. It reads NetworkManager on the system bus, follows `PropertiesChanged` on the manager, the primary connection, its device and its access point, and never polls. It is read-only in v1. It follows the pattern of [Battery Module](Battery%20Module.md) and [Workspaces Module](Workspaces%20Module.md): the layer owns `available`, the module sends `ready`, a hook for a service that leaves, a test on a fake service. All names and TDL below are proposals; the NetworkManager members were read on the maintainer's machine on 2026-11-13 (read-only `busctl` calls; NetworkManager 1.58.1) and checked against the [NetworkManager D-Bus reference](https://networkmanager.dev/docs/api/latest/).

## Purpose and Scope

- Show whether the machine is online, by which kind of connection, and how strong the Wi-Fi signal is.
- Show the state NetworkManager reports, not a state the shell works out from pings ([What It Reads](#what-it-reads)).
- v1: read-only. Not in v1: switching Wi-Fi on or off, listing or joining networks, entering passwords, VPN control, per-device lists, speeds and data counters ([Open Questions](#open-questions) question 1).

## Files

```
Modules/Network/
    Network_Module.tdl     the layout and its params
    Network_Style.tdl      the look
    Network_Module.py      the logic
```

## Behaviour

### What It Reads

Everything is on the system bus, bus name `org.freedesktop.NetworkManager`. One service, so the layer's `available` is one state ([D-Bus Service Layer > Open Questions](../Integration/D-Bus%20Service%20Layer.md#open-questions), 2026-11-12: AND over the module's services).

| Object | Interface | Properties used | Read on 2026-11-13 |
|---|---|---|---|
| `/org/freedesktop/NetworkManager` | `org.freedesktop.NetworkManager` | `State` (u), `Connectivity` (u), `PrimaryConnection` (o), `ActiveConnections` (ao), `WirelessEnabled` (b), `WirelessHardwareEnabled` (b), `NetworkingEnabled` (b) | `State` 70, `Connectivity` 4, `PrimaryConnection` `.../ActiveConnection/3`, `WirelessEnabled` false, `WirelessHardwareEnabled` true, `NetworkingEnabled` true; NetworkManager 1.58.1 |
| The primary active connection | `org.freedesktop.NetworkManager.Connection.Active` | `Id` (s), `Type` (s), `State` (u), `Vpn` (b), `Default` (b), `Devices` (ao) | `Id` "Wired connection 1", `Type` "802-3-ethernet", `State` 2, `Vpn` false, `Default` true, one device |
| That connection's first device | `org.freedesktop.NetworkManager.Device` | `DeviceType` (u), `Interface` (s), `State` (u) | `DeviceType` 1 (ethernet), `Interface` `enp195s0`, `State` 100 |
| A Wi-Fi device | `org.freedesktop.NetworkManager.Device.Wireless` | `ActiveAccessPoint` (o) | `wlan0` is a Wi-Fi device (`DeviceType` 2) in state 20 (unavailable, Wi-Fi switched off): `ActiveAccessPoint` is `/` |
| The active access point | `org.freedesktop.NetworkManager.AccessPoint` | `Ssid` (ay), `Strength` (y, percent) | Not read: Wi-Fi was off on 2026-11-13. From the reference: `Strength` "the current signal quality of the access point, in percent", `Ssid` a byte array. #needs-verification on a live Wi-Fi connection |

All of the manager properties above were seen with the flag `emits-change`, so `PropertiesChanged` carries them. The other devices on this machine (`lo`, a second ethernet port in state 20, a `virbr0` bridge) are not the primary connection and the module ignores them.

Values from the reference ([NetworkManager D-Bus types](https://networkmanager.dev/docs/api/latest/nm-dbus-types.html)):

| Property | Values |
|---|---|
| `State` | 0 unknown, 10 disabled, 20 disconnected, 30 disconnecting, 40 connecting, 50 connected local, 60 connected site, 70 connected global |
| `Connectivity` | 0 unknown, 1 none, 2 portal, 3 limited, 4 full |
| `DeviceType` | 1 ethernet, 2 Wi-Fi, 5 Bluetooth, 8 modem, 29 WireGuard (and others) |
| Active connection `State` | 0 unknown, 1 activating, 2 activated (read on this machine), 3 deactivating, 4 deactivated |

### Values Sent

The Python sends these keys to every use of the module (`ctx.send(key, value)`, [Module Context > Sending values](../../42%20Python%20API/Module%20Context.md#sending-values)):

| Key | Type | Meaning |
|---|---|---|
| `ready` | boolean | True after the first read of the manager. The layout shows only when `available` and `ready` ([Battery Module > Built in M5b (code session's report, 2026-11-12, not run in the vault)](Battery%20Module.md#built-in-m5b-code-sessions-report-2026-11-12-not-run-in-the-vault)) |
| `state` | string | `CONNECTED`, `LIMITED`, `PORTAL`, `CONNECTING`, `DISCONNECTED`, `DISABLED` or `UNKNOWN` ([State and Kind](#state-and-kind)) |
| `kind` | string | `ETHERNET`, `WIFI`, `MOBILE`, `BLUETOOTH`, `OTHER` or `NONE`: the kind of the primary connection |
| `name` | string | The connection's `Id`, or the access point's `Ssid` for Wi-Fi; empty when there is none |
| `strength` | number | The Wi-Fi signal in percent, rounded to a whole number; -1 when the primary connection is not Wi-Fi |
| `vpn` | boolean | True when any active connection is a VPN (`Vpn` true, or `Type` `vpn` or `wireguard`) |
| `icon` | string | The name of an `mdi` icon from `kind`, `state` and `strength` ([Icon](#icon)) |
| `tooltip` | string | For example `Home-WiFi, Wi-Fi 70 %, connected` |

A value is sent only when it changes. `strength` is sent only when the icon step or the rounded tooltip value changes ([Performance Budget](#performance-budget)).

### State and Kind

`state` comes from the manager, with the portal case from `Connectivity`:

| NetworkManager | `state` |
|---|---|
| `Connectivity` 2 (portal) | `PORTAL` |
| `State` 70 and `Connectivity` not 2 or 3 | `CONNECTED` |
| `State` 60, or 70 with `Connectivity` 3 | `LIMITED` (connected, no confirmed internet) |
| `State` 50 (local only) | `LIMITED` (proposed: [Open Questions](#open-questions) question 5) |
| `State` 40, or the primary connection's `State` 1 | `CONNECTING` |
| `State` 20 or 30 | `DISCONNECTED` |
| `State` 10 or `NetworkingEnabled` false | `DISABLED` |
| `State` 0 | `UNKNOWN` |

`kind` comes from the type of the primary connection's first device: 1 `ETHERNET`, 2 `WIFI`, 8 `MOBILE`, 5 `BLUETOOTH`, anything else `OTHER`; with no primary connection `NONE`. A VPN is never the `kind`: it is its own value, so a VPN over Wi-Fi still shows the Wi-Fi.

### Following the Primary Connection

The primary connection, its device and its access point are other objects on the same service, and they change. The module keeps one subscription for each and replaces it when the object changes:

1. At start, `GetAll` on the manager, then `on_property_changed` on it.
2. When `PrimaryConnection` changes, cancel the subscriptions on the old active connection, device and access point, read the new ones (`GetAll`), and subscribe to their `PropertiesChanged`.
3. For a Wi-Fi device, `ActiveAccessPoint` changes when the machine roams: replace the access-point subscription the same way.
4. When `PrimaryConnection` is `/`, there is no primary connection: `kind` is `NONE`, `name` is empty, `strength` is -1.

The match rules are shared by the layer, one per object path and interface, and removed with the last subscriber ([D-Bus Service Layer > Listening and Name Owners](../Integration/D-Bus%20Service%20Layer.md#listening-and-name-owners)).

### Icon

The shell resolves no system icon theme before the Tray part ([M5 Brief](../../00%20Home/M5%20Brief.md), G8), so the module uses the `mdi` set the shell ships. Every name below was checked against the shipped `mdi.json` (7447 icons) on 2026-11-13.

| `kind` | `state` | Icon |
|---|---|---|
| `WIFI` | `CONNECTED` | `wifi-strength-1` for 0 to 24 %, `wifi-strength-2` for 25 to 49 %, `wifi-strength-3` for 50 to 74 %, `wifi-strength-4` for 75 to 100 % |
| `WIFI` | `LIMITED` or `PORTAL` | `wifi-alert` |
| `WIFI` | `CONNECTING` | `wifi-sync` |
| `ETHERNET` | `CONNECTED` | `ethernet` |
| `ETHERNET` | `LIMITED` or `PORTAL` | `lan-disconnect` |
| `ETHERNET`, `MOBILE`, `BLUETOOTH`, `OTHER` | `CONNECTING` | `lan-pending` |
| `MOBILE` | `CONNECTED`, `LIMITED`, `PORTAL` | `cellphone-wireless` |
| `BLUETOOTH` | `CONNECTED`, `LIMITED`, `PORTAL` | `bluetooth` |
| `OTHER` | `CONNECTED`, `LIMITED`, `PORTAL` | `network` |
| `NONE` | `DISCONNECTED` | `network-off` |
| `NONE` | `DISABLED` | `wifi-off` |
| any | `UNKNOWN` | `network-outline` |

Rows added from the M5c build (orchestrator, 2026-11-13, [M5 Brief](../../00%20Home/M5%20Brief.md) question 24): `NONE` with `CONNECTED`, `LIMITED` or `PORTAL` (a link with no primary connection) is `network`; `NONE` with `CONNECTING` is `lan-pending`; any kind with `DISCONNECTED` is `network-off` and with `DISABLED` is `wifi-off`; `WIFI` with no access point read is step 1; `MOBILE` and `BLUETOOTH` keep their kind icon when `LIMITED` or `PORTAL`.

When a VPN is the primary connection it is still never the kind: the icon describes the connection under it (the first non-VPN active connection that is `Default`), and the tooltip adds `VPN <connection name>` ([M5 Brief](../../00%20Home/M5%20Brief.md) question 25).

A VPN adds a second icon, `vpn`, shown while `vpn` is true ([Layout (Network_Module.tdl)](#layout-network_moduletdl)). Proposed: the table is a proposal until the maintainer sees it on KWin; a missing name is a build-time test failure ([Acceptance Criteria](#acceptance-criteria)).

### Hiding

`available` is false when NetworkManager is not on the system bus (`NameHasNoOwner`, `ServiceUnknown`, the system bus is unreachable). The module hides itself then, the way [Battery Module > Hiding](Battery%20Module.md#hiding) does. It does not hide for a disconnected machine: `DISCONNECTED` and `DISABLED` are states a user wants to see, shown with `network-off` and `wifi-off` ([Open Questions](#open-questions) question 2).

### Layout (`Network_Module.tdl`)

```
---
TDL: 0.2
TEL: 0.1
TRE: 0.6.7
Shell: 0.1
Name: Network
---

Module {
    Style: Network_Style.tdl
    Visible: <| available and ready |>
    Params {
        # show the connection name next to the icon
        show_name { Type: boolean, Default: false }
        # show the second VPN icon while a VPN is up
        show_vpn { Type: boolean, Default: true }
    }

    FlexBox {
        Flex: HORIZONTAL
        Children {
            Icon { Icon: <| icon |> }
            If <| show_vpn and vpn |> {
                Icon { Icon: vpn }
            }
            If <| show_name |> {
                Text { Text: <| name |> }
            }
        }
    }
}
```

A sketch. The forms follow [Block Reference](../../41%20TDL%20Reference/Block%20Reference.md), [Module File](../../41%20TDL%20Reference/Module%20File.md) and the icon slot decided in M5b ([M5 Build Log](../../00%20Home/M5%20Build%20Log.md)); none is re-decided here. A tooltip is registered by the shell from the `tooltip` value ([Standard Modules > Tooltip](../../50%20Design%20System/Standard%20Modules.md#tooltip)).

## Configuration

| Param | Type | Default | Meaning |
|---|---|---|---|
| `show_name` | boolean | false | The connection name or the Wi-Fi name next to the icon |
| `show_vpn` | boolean | true | A second icon while a VPN is up |

There is no strength threshold: the four steps in [Icon](#icon) are fixed. A user who wants other steps uses the `strength` value in a TEL condition in their own layout.

## Python Contract

The class follows [Module Contract](../../42%20Python%20API/Module%20Contract.md) and [Module Context > D-Bus Helper](../../42%20Python%20API/Module%20Context.md#d-bus-helper).

```python
from tess_shell import Module

NM = "org.freedesktop.NetworkManager"

class Network(Module):
    def start(self):
        bus = self.ctx.dbus.system()
        self.nm = bus.proxy(NM, "/org/freedesktop/NetworkManager", NM)
        self.sub = self.nm.on_property_changed(self.manager_changed)   # on the dbus thread, short
        self.active = self.device = self.ap = None                      # per-object subscriptions

    def on_service_lost(self, name):
        self.ctx.send("ready", False)

    def on_service_found(self, name):
        self.rebuild()      # read the manager again; follow the primary connection
```

An illustration of the shape, not tested code. What it shows:

- One instance, one manager proxy, for every use; it never sends with `use=`.
- The callbacks read only what changed, derive the keys and call `ctx.send`, which crosses to the loop. They do no other work.
- Replacing the active-connection, device and access-point subscriptions on a change of `PrimaryConnection` is the module's own logic, with `sub.cancel()` ([Following the Primary Connection](#following-the-primary-connection)).
- The module does not send `available`; the layer owns it ([Module Context > D-Bus Helper](../../42%20Python%20API/Module%20Context.md#d-bus-helper)).

## Integration

- Service: NetworkManager on the system bus; activatable. The system bus opens lazily on the first proxy ([D-Bus Service Layer > Open Questions](../Integration/D-Bus%20Service%20Layer.md#open-questions), 2026-11-12).
- Threads: callbacks on the `dbus` thread; `ctx.send` crosses to the loop; no worker thread ([Process Model and Threading](../../20%20Architecture/Process%20Model%20and%20Threading.md)).
- Plasma: plasmashell's network applet reads the same service. Both read; this module never writes ([Plasma Coexistence](../Integration/Plasma%20Coexistence.md)).
- No file, no network request, no subprocess. The module never calls `CheckConnectivity`.

## Design

An `Icon`, an optional second `Icon` for the VPN and an optional `Text`. The look comes from the theme: the state colours (`LIMITED` and `PORTAL` use the warning token, `DISCONNECTED` and `DISABLED` the muted one) are tokens ([Style Schema](../../41%20TDL%20Reference/Style%20Schema.md), [50 Design System](../../50%20Design%20System/50%20Design%20System.md)).

## Accessibility

- The group's name includes the kind and the state, for example `Network, Wi-Fi Home-WiFi, 70 percent, connected`, not only the icon ([Accessibility](../../60%20Quality/Accessibility.md)).
- State is never colour only: the icon changes shape with the kind, the signal step and the alert.
- A change of `strength` is not announced. A change of `state` to or from `CONNECTED` is announced once, politely ([Accessibility](../../60%20Quality/Accessibility.md) rule 6); it is built in the M6 accessibility pass with the other announcements, not in M5c ([M5 Brief](../../00%20Home/M5%20Brief.md) question 26). #needs-verification against how tre publishes live regions.
- The tooltip text is the description.

## Performance Budget

- Idle: no timer. Wake-ups follow NetworkManager's signals ([Performance Budgets](../../60%20Quality/Performance%20Budgets.md)).
- Per signal: under 1 ms of the module's own work on the `dbus` thread ([D-Bus Service Layer](../Integration/D-Bus%20Service%20Layer.md), measured p99 25 microseconds for a `ctx.send` callback in M5a).
- `Strength` can change several times a second on a live Wi-Fi link. The module sends `strength` and `icon` only when the icon step changes, and `tooltip` only when its text changes, which is when the percent rounded down in fives changes (72 and 73 both show 70; [M5 Brief](../../00%20Home/M5%20Brief.md) question 23) ([Open Questions](#open-questions) question 4). #needs-verification: how often NetworkManager emits `Strength` on a real Wi-Fi link ([Questions After Testing](#questions-after-testing)).

## Failure Modes and Recovery

| Failure | Result |
|---|---|
| NetworkManager is not on the bus at start | `available` false; the module hides; recovers on `on_service_found` |
| NetworkManager restarts | `on_service_lost` hides the module; `on_service_found` reads the manager again and follows the new primary connection |
| The system bus is unreachable | `available` false; one warning logged by the layer; the shell runs |
| `PrimaryConnection` is `/` | `kind` `NONE`, empty `name`, `strength` -1; `state` from the manager |
| The primary connection or its device disappears between two reads | The read raises `ServiceUnavailable` for that object; the module keeps the last values and rebuilds on the next `PrimaryConnection` change |
| A Wi-Fi device has no active access point | `strength` -1 and the Wi-Fi name is empty; `state` from the manager |
| `Ssid` is not valid UTF-8 | Decoded with replacement characters; the connection `Id` is used when `Ssid` is empty |
| A property has an unexpected type or value | The key keeps its last value and one warning names the property |
| A call times out | `ServiceTimeout` is logged once per service per minute; the last values stay |
| An `mdi` name in the icon table is not in the set | Caught by the build-time test; at run time the module sends `network-outline` |
| The callback raises | Caught, logged with the module name; the module keeps running ([Module Contract](../../42%20Python%20API/Module%20Contract.md)) |

## Built in M5c (code session's report, 2026-11-13, not run in the vault)

- The module is `shipped/Network/` (commit 01dc853), with a fake NetworkManager for tests and a KWin kit in `/tmp/tess-kwin-m5c`. Suite 3576 passed.
- Measured on the fake service: callbacks p50 8 to 11 us, p99 36 to 58 us, max 63 to 96 us; idle 0 loop iterations, 0 timeslices and 0 voluntary context switches over 5 s and over one 60 s run.
- Departures from this spec, put to the maintainer in [M5 Brief](../../00%20Home/M5%20Brief.md) questions 23 to 26: the percent is rounded down in fives (72 and 73 both 70) where the spec said "rounded to 5"; rows the icon table lacks were filled (for example no known kind but connected shows `network`); with a VPN as the primary connection the icon describes the link under it and the tooltip adds `VPN <name>`; the module does not use `on_service_lost` and `on_service_found`, because they raced with the layer's redelivery and a full manager read resets what the module follows; the live-region announcement is not built.
- Not checked: the Wi-Fi `Strength` rate on a live link and a real captive portal (Questions After Testing below).
- A layer bug was found and fixed in the M5a code (`services/layer.py`): a `PropertiesChanged` arriving during the first `GetAll` of an interface could be lost, in about 1 run in 12 when a module changed two properties right after start; Battery and Workspaces had the same exposure. A test models the race.

## Open Questions

1. [x] Is the module read-only in v1, with no Wi-Fi switch, no network list and no joining a network? Context: [V1 Widgets](../../50%20Design%20System/V1%20Widgets.md) lists a Network menu (a network list), but joining a network needs secrets and an authorisation prompt through NetworkManager's agent, which the shell would have to implement; switching Wi-Fi writes `WirelessEnabled`. [M5 Brief](../../00%20Home/M5%20Brief.md) C1 only asks that unplugging a cable or turning Wi-Fi off changes the Bar. Recommendation: yes, read-only; a click does nothing in v1, and a later Network menu is its own spec. Maintainer, 2026-11-13: as recommended.
2. [x] Should the module stay visible when disconnected, and hide only when NetworkManager is absent? Context: a user wants to see "no network"; Battery hides on `IsPresent` false because there is nothing to show, which is a different case. Recommendation: yes, stay visible with `network-off` or `wifi-off`. Maintainer, 2026-11-13: as recommended.
3. [x] Should a VPN show as a second `vpn` icon next to the connection icon, controlled by the param `show_vpn` (default true)? Context: a VPN rides on another connection, so the kind icon and the VPN are two facts. Recommendation: yes. Maintainer, 2026-11-13: as recommended.
4. [x] Should the tooltip be English in v1, with the Wi-Fi percent rounded to 5? Context: the text is built in Python, as in [Battery Module](Battery%20Module.md) question 2, with the wording in one table; rounding stops the tooltip changing on every signal wobble. Recommendation: yes, English, percent rounded to 5, wording in one table. Maintainer, 2026-11-13: as recommended.
5. [x] Should NetworkManager's `State` 50 (connected, local only) show as `LIMITED` with the alert icon? Context: the reference says a shell should indicate no connectivity for 50, and "limited connectivity" for 60. Recommendation: yes, `LIMITED` for both, so a user sees there is a link but no internet. Maintainer, 2026-11-13: as recommended.
6. [x] Are the four Wi-Fi steps (0 to 24, 25 to 49, 50 to 74, 75 to 100 percent) the right split? Context: the `mdi` set has four strength icons, `wifi-strength-1` to `wifi-strength-4`. Recommendation: yes, equal quarters. Maintainer, 2026-11-13: as recommended.
7. [x] Should the connection show a metered mark (NetworkManager's `Metered` property) in v1? Context: `Metered` is read as 4 (guess: not metered) on this machine; a mark needs a new icon and a rule for the four values. Recommendation: no, not in v1. Maintainer, 2026-11-13: as recommended.

## Questions After Testing

Answered by: a Wi-Fi connection on the maintainer's machine, with Wi-Fi switched on (it was off on 2026-11-13, so no access point was read), and a fake NetworkManager on a private bus for the rest. The two items below need a real network.

1. [ ] How often does NetworkManager emit `PropertiesChanged` for `Strength` on a live Wi-Fi link, and does `ActiveAccessPoint` change on a roam? Context: the budget above assumes a few per second at most and sends only on a step change. Recommendation: keep the rule and set the rounding from the measured rate. Answered by: the Wi-Fi test with the module's per-signal timing.
2. [ ] Does a captive portal on a real network give `Connectivity` 2, and a network without internet give 3? Context: the mapping to `PORTAL` and `LIMITED` follows the reference. Recommendation: keep the mapping; correct it if a real network differs. Answered by: a test on a portal network, or the fake service only if none is at hand.

## Acceptance Criteria

- [ ] On this desktop (wired, `State` 70, `Connectivity` 4) the module shows the `ethernet` icon, no second icon, and the tooltip `Wired connection 1, ethernet, connected`.
- [ ] Unplugging the cable (`State` 20, no primary connection) changes the icon to `network-off` and the tooltip to `Disconnected` within one loop turn after the signal.
- [ ] On a fake NetworkManager on a private bus with a Wi-Fi primary connection at `Strength` 72, the icon is `wifi-strength-3` and the tooltip shows `Wi-Fi 70 %`; changing `Strength` to 80 changes the icon to `wifi-strength-4`; changing it from 72 to 73 changes nothing sent.
- [ ] Setting `Connectivity` 2 shows `wifi-alert` for Wi-Fi and `lan-disconnect` for ethernet, and `state` `PORTAL`.
- [ ] Setting `WirelessEnabled` false while no connection is primary shows `wifi-off` only when NetworkManager reports `State` 10; otherwise `network-off`.
- [ ] A change of `PrimaryConnection` replaces the subscriptions on the active connection, device and access point; the old paths no longer produce callbacks (checked on the fake service's monitor, [D-Bus Service Layer > Acceptance Criteria](../Integration/D-Bus%20Service%20Layer.md#acceptance-criteria)).
- [ ] A VPN active connection shows the `vpn` icon while `show_vpn` is true; `show_vpn: false` hides it.
- [ ] Removing the fake service hides the module and logs one warning; bringing it back shows it again with the current state, with no shell restart.
- [ ] With no signal traffic, the module causes no wake-ups over 60 seconds.
- [ ] The Python never blocks the loop and starts no thread.
- [ ] Every icon name in the table exists in the shipped `mdi` set (a test).
- [ ] The maintainer's KWin check passes with the cable unplugged and plugged back in, and with Wi-Fi switched off and on.

## Links

- [Modules](Modules.md) · [Battery Module](Battery%20Module.md) · [Workspaces Module](Workspaces%20Module.md) · [D-Bus Service Layer](../Integration/D-Bus%20Service%20Layer.md) · [Module Contract](../../42%20Python%20API/Module%20Contract.md) · [Module Context](../../42%20Python%20API/Module%20Context.md) · [Plasma Coexistence](../Integration/Plasma%20Coexistence.md) · [M5 Brief](../../00%20Home/M5%20Brief.md) · [V1 Scope](../../10%20Vision/V1%20Scope.md)
