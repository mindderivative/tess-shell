---
title: Audio Access Spike
aliases: [Audio Spike, M5e Spike]
type: research
status: research
owner: phil
created: 2026-11-13
updated: 2026-11-13
tags: [research, integration/audio, needs-verification]
---

# Audio Access Spike

> [!NOTE]
> The brief for the spike that opens M5e (gap G3 of [M5 Brief](../00%20Home/M5%20Brief.md)): how the Audio module reads and sets volume and mute and follows changes without polling. PipeWire has no D-Bus interface for volume, so the D-Bus layer of M5a does not reach it. The code session runs the spike (task T-018 in [Orchestration Log](../00%20Home/Orchestration%20Log.md)); its result becomes an ADR and then the Audio spec, which are different notes from this one.

## What Was Read on the Maintainer's Machine (2026-11-13, Read-Only)

| Fact | Source |
|---|---|
| The sound server is PipeWire 1.6.11 with its PulseAudio server (`pactl info`: "PulseAudio (on PipeWire 1.6.11)", protocol version 15.0.0) | `pactl info` |
| `wpctl`, `pactl`, `pw-dump` and `pw-cli` are installed | `which` |
| The Python package `pulsectl` is not installed | `import pulsectl` fails |
| `pipewire`, `wireplumber` and `pipewire-pulse` are on the session bus; the names seen are `org.pulseaudio.Server`, `org.pipewire.Telephony` and `org.freedesktop.ReserveDevice1.Audio0` to `Audio2`, none of which is a volume interface | `busctl --user list` |

## Candidates

| # | Route | Events without polling | Dependency | To find out |
|---|---|---|---|---|
| A | The PulseAudio native protocol on the `pipewire-pulse` socket, spoken by the shell itself (a small client: subscribe, sink and source info, set volume and mute) | Yes, the protocol's subscribe | None, but the client is written by us; the policy allows a library only where building it is a project of its own ([ADR-0019 Dependency Policy](../30%20Decisions/ADR-0019%20Dependency%20Policy.md)) | How large a client for five commands is; whether it is a few hundred lines or a project |
| B | A Python library over the same protocol (`pulsectl` with its event loop, or `pulsectl-asyncio`) | Yes | One or two packages, and `libpulse` through `ctypes` | Whether it runs on the `dbus` asyncio thread; its idle cost; its licence and upkeep |
| C | A subprocess that follows events (`pactl subscribe`) with `pactl` or `wpctl` for reads and writes | Yes, by reading the subprocess's output | None in Python; needs the tools installed | Process cost at idle; latency of a read after an event; behaviour when the server restarts |
| D | A PipeWire binding or `pw-dump --monitor` (JSON) | Yes | A subprocess or a binding | Whether volume is readable and settable for the default sink this way without WirePlumber's own API |

## What the Spike Measures

Corrected on 2026-11-13 after incident I-003 ([Orchestration Log > Incidents](../00%20Home/Orchestration%20Log.md#incidents)): the spike runs only against a private PipeWire and `pipewire-pulse` instance started by the spike in its own runtime folder under `/tmp`, with a null sink inside that instance. It makes no connection to the maintainer's real sound server, for reads or writes. Every script carries a guard that aborts unless its server socket and runtime folder are under `/tmp`, builds its environment from scratch, and is read by the lead session before it first runs. The earlier wording here ("a null sink the spike creates") was wrong, because it did not name a private server.

For each candidate that works at all:

1. Does a volume or mute change, or a change of the default sink, arrive as an event, with no timer?
2. Idle cost over 60 seconds with no change: wake-ups and CPU time of every process and thread the route adds.
3. Latency from a change to the value in Python (median and worst of 50).
4. What it adds: packages, lines of our own code, a required system tool.
5. What happens when `pipewire-pulse` restarts: does the route recover without a shell restart?

## What the Audio Module Needs (for the Comparison)

The default output: volume in percent, mute, the device's name and kind (speaker, headphones, HDMI, Bluetooth) for the icon; the default input's mute; a list of outputs to switch between (a Menu, as [V1 Widgets](../50%20Design%20System/V1%20Widgets.md) lists); set volume, toggle mute, set the default output. All of it without polling, and hidden or empty when there is no sound server.

## Output

A report with the five measurements per candidate and a recommendation. The orchestrator writes the ADR from it (Tier 1 unless a new dependency is shared with another project), then the Audio spec.

## Links

- [M5 Brief](../00%20Home/M5%20Brief.md) · [D-Bus Service Layer](../40%20Specifications/Integration/D-Bus%20Service%20Layer.md) · [ADR-0019 Dependency Policy](../30%20Decisions/ADR-0019%20Dependency%20Policy.md) · [D-Bus Libraries for Python](D-Bus%20Libraries%20for%20Python.md) · [Orchestration Log](../00%20Home/Orchestration%20Log.md)
