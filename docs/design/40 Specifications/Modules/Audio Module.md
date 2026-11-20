---
title: Audio Module
aliases: [Audio, Audio_Module, Volume Module]
type: spec
status: accepted
owner: phil
created: 2026-11-13
updated: 2026-11-14
tags: [spec/module, integration/audio, needs-verification]
---

# Audio Module

> [!NOTE]
> The Audio module shows and sets the volume of the default sound output: an icon for the kind of output and the level, a mute toggle on click, a volume change on scroll, an optional slider, and a menu of outputs to switch between. It talks to the sound server through the shell's own client for the PulseAudio native protocol ([ADR-0021 Audio Access](../../30%20Decisions/ADR-0021%20Audio%20Access.md)), follows the server's events and never polls. It hides when there is no sound server. Written and decided by the orchestrator under the [Tesserae Shell Directive](../../00%20Home/Tesserae%20Shell%20Directive.md); M5e builds it ([M5 Brief](../../00%20Home/M5%20Brief.md)). The device facts were read on the maintainer's machine on 2026-11-13 with a read-only `pactl list sinks`.

## Purpose and Scope

- Show the default output's volume and mute, and change them.
- Show whether the default microphone is muted, when asked.
- Switch the default output from a menu.
- Not in v1: per-application volume, input volume, balance controls, device profiles, over-amplification above 100 %.

## Files

```
Modules/Audio/
    Audio_Module.tdl     the layout and its params
    Audio_Style.tdl      the look
    Audio_Module.py      the logic
```

The protocol client is not part of the module: it is `tess_shell/services/pulse_native.py`, reached through the module context ([Needs from the Shell](#needs-from-the-shell)).

## Behaviour

### What It Reads

The sound server's native-protocol socket in the user's runtime folder (`pulse/native`). On the maintainer's machine the server is PipeWire 1.6.11 with its PulseAudio server (`pactl info`, 2026-11-13).

| Item | Use |
|---|---|
| Server info: the default sink and the default source names | Which devices the module shows |
| Sink info: description, volume per channel, mute, `device.form_factor`, `device.bus`, the active port and its type | The level, the icon, the tooltip, the menu |
| Source info: mute | The microphone mark |
| Subscription events for sinks, sources and the server | Every change, with no timer |

The three outputs read on 2026-11-13:

| Output | `device.form_factor` | `device.bus` | Active port and its type |
|---|---|---|---|
| The mainboard's analogue output | none | `pci` | `analog-output-speaker`, Speaker (a second port: `analog-output-headphones`, Headphones) |
| The Razer Leviathan V2 X (the default) | none | `usb` | `analog-output`, Analog |
| The graphics card's HDMI output | none | `pci` | `hdmi-output-0`, HDMI |

No output on this machine sets `device.form_factor`, so the port type decides the kind here.

### Values Sent

| Key | Type | Meaning |
|---|---|---|
| `ready` | boolean | True after the first read. The root is `Visible: <\| ready \|>`; false when there is no server |
| `volume` | number | The default output's volume in percent, the mean of its channels, rounded; a value above 100 is sent as it is |
| `muted` | boolean | The default output's mute |
| `kind` | string | `SPEAKER`, `HEADPHONES`, `HDMI`, `BLUETOOTH` or `OTHER` ([Kind and Icon](#kind-and-icon)) |
| `name` | string | The output's description |
| `mic_muted` | boolean | The default input's mute; false when there is no input |
| `has_mic` | boolean | Whether a default input exists |
| `outputs` | list | One entry per output: `id` (the sink name), `name`, `kind`, `icon`, `current` |
| `icon` | string | The `mdi` icon from `kind`, `volume` and `muted` |
| `tooltip`, `label` | string | For example `Razer Leviathan V2 X, 45 %`, or `..., muted` |

A value is sent only when it changes.

### Kind and Icon

The kind is taken in this order: `device.form_factor` when set (`headphone`, `headset`: `HEADPHONES`; `speaker`, `internal`: `SPEAKER`; `tv`, `hdmi`: `HDMI`); else the active port's type (Headphones, Headset: `HEADPHONES`; HDMI: `HDMI`; Speaker, Analog, Line: `SPEAKER`); else `device.bus` (`bluetooth`: `BLUETOOTH`); else `SPEAKER`. A Bluetooth bus makes the kind `BLUETOOTH` whatever the form factor says, so the icon shows it.

| State | Icon |
|---|---|
| Muted, any kind | `volume-off` (`headphones-off` for `HEADPHONES`) |
| `SPEAKER`, `HDMI`, `OTHER`: 0 % | `volume-mute` |
| 1 to 33 % | `volume-low` |
| 34 to 66 % | `volume-medium` |
| 67 % and above | `volume-high` |
| `HEADPHONES`, not muted | `headphones` |
| `BLUETOOTH`, not muted | `bluetooth-audio` |
| An output in the menu | `speaker`, `headphones`, `hdmi-port` or `bluetooth-audio` by its kind |
| The microphone mark | `microphone-off`, shown only while `mic_muted` and `show_mic` |

Every name was checked in the shipped `mdi` set on 2026-11-13.

### Actions

| Action | Effect |
|---|---|
| `toggle_mute` | Sets the default output's mute to the opposite |
| `set_volume(percent)` | Sets every channel of the default output; the value is clamped to 0 to 100; a balance between channels is kept by scaling when the output has one |
| `step(delta)` | `set_volume` of the current volume plus `delta`; used by scroll, `delta` is the `step` param times the scroll direction |
| `set_output(id)` | Makes that output the default |
| `toggle_mic` | Toggles the default input's mute |

A call runs on the `dbus` thread and returns at once. The module does not predict the result: the values change when the server's event arrives (median 1.5 ms in the spike). While the user drags the slider, `On_Changed` calls `set_volume` at most once every 50 ms and `On_Released` sends the final value.

### Hiding

The module is hidden while no sound server is reachable. It shows again when the socket appears; the shell watches the socket's folder and uses no timer ([ADR-0021 Audio Access](../../30%20Decisions/ADR-0021%20Audio%20Access.md)).

### Layout (`Audio_Module.tdl`)

```
---
TDL: 0.2
TEL: 0.1
TRE: 0.6.7
Shell: 0.1
Name: Audio
---

Module {
    Style: Audio_Style.tdl
    Visible: <| ready |>
    Params {
        show_percent { Type: boolean, Default: false }
        show_slider { Type: boolean, Default: false }
        show_mic { Type: boolean, Default: true }
        step { Type: number, Default: 5 }
    }

    FlexBox {
        Flex: HORIZONTAL
        On_Scroll { Action: step, delta: <| event.delta * step |> }
        Children {
            Button { Icon: <| icon |>, On_Click: toggle_mute, On_Secondary_Click { Action: Show, Target: Audio_Outputs } }
            If <| show_percent |> { Text { Text: <| volume |> % } }
            If <| show_slider |> {
                Slider { Value: <| volume |>, Max: 100, On_Changed { Action: set_volume, percent: <| event.value |> }, On_Released { Action: set_volume, percent: <| event.value |> } }
            }
            If <| show_mic and mic_muted |> { Icon { Icon: microphone-off } }
        }
    }
}
```

A sketch; the code session aligns key spellings with what is built. `Audio_Outputs` is a Popup holding a `Menu` with a `For` over `outputs`, each `MenuItem` calling `set_output` with its `id` (the module call in a `For` inside a Popup, built in M5).

## Configuration

| Param | Type | Default | Meaning |
|---|---|---|---|
| `show_percent` | boolean | false | The number next to the icon |
| `show_slider` | boolean | false | A volume slider on the Bar |
| `show_mic` | boolean | true | A mark while the microphone is muted |
| `step` | number | 5 | Percent per scroll step |

## Needs from the Shell

Both are inside `tess-shell` (Tier 1):

| Need | Shape |
|---|---|
| The protocol client | `services/pulse_native.py`, per [ADR-0021 Audio Access](../../30%20Decisions/ADR-0021%20Audio%20Access.md): connect, authenticate, negotiate the version, subscribe, get server info, sink and source info, set sink volume and mute, set source mute, set the default sink; reconnect by watching the socket's folder |
| A way for a module to use it | `self.ctx.audio`, with `on_changed(callback)`, the readers and setters above as coroutines, and `available`; the callbacks run on the `dbus` thread like D-Bus callbacks. It is a second service object beside `ctx.dbus` ([Module Context](../../42%20Python%20API/Module%20Context.md)) |
| A scroll event on a block | `On_Scroll` with `event.delta` (+1 or -1 per step) is one of the twelve event keys ([Events and Actions](../../42%20Python%20API/Events%20and%20Actions.md)); built in this part if it is not yet |

## Python Contract

One instance for every use. `start` subscribes; the callback reads what changed, derives the keys and sends them. Setters are called through the context and never block the loop. No timer, no thread, no subprocess.

## Integration

- Service: the sound server's socket; no D-Bus. Plasma's volume applet uses the same server; both read and both may set.
- Threads: the client's socket is on the `dbus` thread's loop; `ctx.send` crosses to the loop thread.
- Tests run only against a private sound stack inside the sandbox wrapper built for the spike ([Orchestration Log](../../00%20Home/Orchestration%20Log.md) D-025, D-026). No test may reach the real sound server.

## Design

A Button with the icon, an optional Text, Slider and Icon, and a Menu of outputs; all standard modules. Muted uses the muted colour token.

## Accessibility

- The group's name is `label`: the output, the level and "muted" when muted.
- The Button's name is "Mute" or "Unmute"; the Slider's is "Volume" with the percent.
- State is never colour only: the icon changes with level and mute.
- Keyboard operation is M6 ([Standard Modules > Keyboard Operation (M6)](../../50%20Design%20System/Standard%20Modules.md#keyboard-operation-m6)).

## Performance Budget

- Idle: 0 wake-ups (measured 0 in the spike for the chosen route).
- A change to the value in Python: under 5 ms (measured median 1.5 ms, worst 1.9 ms).
- Per event: under 1 ms of the module's own work.
- A slider drag sends at most 20 volume calls a second.

## Failure Modes and Recovery

| Failure | Result |
|---|---|
| No sound server at start | Hidden; shows when the socket appears |
| The server restarts | Hidden for the gap; values re-read on reconnect; no shell restart |
| The default output disappears (a USB or Bluetooth device unplugged) | The server names a new default; the module follows it |
| No output at all | `ready` true, `outputs` empty, the icon `volume-off`, the tooltip "No output" |
| The server's protocol version is below 34 | Port types are absent; the kind comes from the form factor and the bus |
| A setter fails | Logged once a minute; nothing changes |
| The volume is above 100 % (set elsewhere) | Shown as it is; the module's own setters still clamp to 100 |
| The callback raises | Caught and logged with the module name ([Module Contract](../../42%20Python%20API/Module%20Contract.md)) |

## Built in M5e (code session's report, 2026-11-13, not run in the vault)

- Merged to `main` as `65b2e5d` (`feat/m5e-audio`). Normal suite 3989 passed, 1 skipped, 20 deselected. The normal suite never reaches a sound server: it uses an in-process fake, and the test setup removes the sound-server variables. The real-protocol tests run only inside the sandbox on the private stack: 12 passed, including a restart of `pipewire-pulse` and of `pipewire`.
- Built: `services/pulse_native.py` (standard library only, protocol versions 13 to 35, port types from 34), `services/audio.py` and `ctx.audio` (reconnect by a watch on the folder, no timer), the shipped modules `Audio` and `Audio_Outputs`, and the events `On_Secondary_Click` and `On_Scroll` (`event.delta`).
- Measured on the private stack: latency median 0.87 ms, worst 1.32 ms; callbacks p99 18.6 microseconds; idle 0 wake-ups.
- Departures, accepted by the orchestrator on 2026-11-13 (Tier 1): the outputs menu is a second shipped module `Audio_Outputs`, shown in a Popup the user writes in the shell file, opened by the action `show_outputs` (a module cannot declare a Popup; without the Popup the click logs one warning); the mute control is a `FlexBox` with the role of a button and two icons, because the Button module cannot colour its glyph for the muted state; a key `volume_text` carries the number as text; the slider's `On_Changed` calls a throttled `drag` action and `On_Released` calls `set_volume`; `event.delta` is +1 for a step down, so the layout negates it; `set_volume` scales the channels so their mean is the target and none exceeds 100 %; a port type of Bluetooth gives `BLUETOOTH` and TV gives `HDMI`; a default source that is a sink's monitor is not a microphone; the current output is marked by a dot and by ", current" in its accessible name; `toggle_mic` exists as an action with no control in the layout.
- Not verified: a real PulseAudio server and its cookie; port types on real hardware through the client; a real compositor's wheel reaching a block in a layer window; a touchpad's many small scroll steps.

## Open Questions

Decided by the orchestrator on 2026-11-13 ([Tesserae Shell Directive](../../00%20Home/Tesserae%20Shell%20Directive.md) rule 7, Tier 1).

1. [x] Which route? The shell's own native-protocol client ([ADR-0021 Audio Access](../../30%20Decisions/ADR-0021%20Audio%20Access.md)).
2. [x] Volume above 100 %? Shown when the server reports it; never set by the module.
3. [x] Balance? Kept by scaling the channels; there is no balance control.
4. [x] What does a click do? Toggles mute; a secondary click opens the outputs menu; scroll changes the volume.
5. [x] Is the slider on the Bar by default? No.
6. [x] The kind lookup order? Form factor, then port type, then bus, then speaker; Bluetooth by bus wins.

## Questions After Testing

1. [ ] Do port types and a Bluetooth output arrive as the spec assumes on real hardware? Context: the spike's null sinks have no ports; the three real outputs were read with `pactl`, not through the client. Recommendation: keep the lookup and correct it from a hand run. Answered by: the maintainer running the module on his machine with headphones, HDMI and a Bluetooth device.
3. [ ] Does a touchpad's stream of small scroll steps change the volume too fast? Context: `On_Scroll` raises one event per wheel event, and each steps the volume by `step` percent. Recommendation: keep one event per wheel event and add an accumulator only if a hand check shows it is too fast. Answered by: a hand run on a touchpad.
2. [ ] Does the client recover when `pipewire` itself restarts, not only `pipewire-pulse`? Context: not measured in the spike. Recommendation: test it in the sandbox in M5e. Answered by: a sandbox test that restarts the private `pipewire`.

## Acceptance Criteria

All against a private sound stack in the sandbox.

- [ ] With no server the module is hidden and takes no Bar space; starting the server shows it with no shell restart.
- [ ] A volume change made by another client arrives and changes `volume` and the icon step within 5 ms; a mute change changes `muted` and the icon.
- [ ] `toggle_mute`, `set_volume`, `step`, `set_output` and `toggle_mic` change the private server's state, read back with `pactl` in the sandbox; `set_volume(150)` sets 100.
- [ ] Adding and removing a sink changes `outputs`; changing the default sink changes `name`, `kind` and the `current` mark.
- [ ] The kind lookup gives `HEADPHONES` for a headphone form factor, `HDMI` for an HDMI port type, `BLUETOOTH` for a Bluetooth bus and `SPEAKER` otherwise (private sinks with those properties).
- [ ] A slider drag sends at most 20 calls a second and one final call on release.
- [ ] Killing and starting the private `pipewire-pulse`, and the private `pipewire`, hides and shows the module.
- [ ] With no change, the module and the client cause no wake-ups over 60 seconds.
- [ ] Every test of the client and the module refuses to run outside the sandbox (the guard and the canary).
- [ ] Every icon name in the tables exists in the shipped `mdi` set (a test).

## Links

- [Modules](Modules.md) · [ADR-0021 Audio Access](../../30%20Decisions/ADR-0021%20Audio%20Access.md) · [Audio Access Spike](../../90%20Research/Audio%20Access%20Spike.md) · [Media Module](Media%20Module.md) · [Module Contract](../../42%20Python%20API/Module%20Contract.md) · [Module Context](../../42%20Python%20API/Module%20Context.md) · [Standard Modules](../../50%20Design%20System/Standard%20Modules.md) · [M5 Brief](../../00%20Home/M5%20Brief.md) · [Tesserae Shell Directive](../../00%20Home/Tesserae%20Shell%20Directive.md)
