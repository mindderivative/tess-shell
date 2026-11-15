---
title: ADR-0021 Audio Access
aliases: [ADR-0021, Audio Access Path, PulseAudio Protocol Client]
type: adr
status: accepted
owner: phil
created: 2026-11-13
updated: 2026-11-13
tags: [adr, integration/audio]
---

# ADR-0021: Audio Access

## Context

The Audio module must read and set volume and mute, follow changes without polling, and list and switch outputs. PipeWire has no D-Bus interface for volume, so the service layer of M5a does not reach it (gap G3 of [M5 Brief](../00%20Home/M5%20Brief.md)). The code session measured four routes in a sandbox against a private PipeWire 1.6.11 stack on 2026-11-13 (task T-018, brief in [Audio Access Spike](../90%20Research/Audio%20Access%20Spike.md), report `/tmp/frame-review/T018.md`, scripts in `tests/spikes/audio/` of `tess-shell`). The numbers below are its report; the vault did not run them.

## Options

| | A. Own client for the PulseAudio native protocol | B. `pulsectl-asyncio` | C. `pactl subscribe` and `pactl` | D. `pw-dump --monitor` and `wpctl` |
|---|---|---|---|---|
| Events with no timer | Yes | Yes | Yes | Yes |
| Idle wake-ups in 60 s | 0 | 0 | 0 | 0 |
| Latency of a volume change, median and worst | 1.5 and 1.9 ms | 2.4 and 4.0 ms | 6.7 and 7.6 ms | 1.5 and 2.3 ms |
| Own code | 231 lines of protocol and 121 of glue | 86 lines | 123 lines | 132 lines |
| Adds | Nothing | Two packages (`pulsectl` 24.12.0, last release 2024-12-26; `pulsectl-asyncio` 1.3.2) and `libpulse` through `ctypes` | The tool `pactl` at run time; a process per refresh and per write | The tools `pw-dump` and `wpctl`; a large JSON graph parsed on each change |
| `pipewire-pulse` restarts | Back after 0.5 s | Back after 0.5 s | Back at once | Unaffected |
| Not proven | Port type parsing (null sinks have no ports); version negotiation; a restart of `pipewire` itself | The same server-side points | The same | The volume path on real hardware (the mixer is in the device's `Route` param, which it does not read) |

### Option A — Own client for the PulseAudio native protocol (chosen)

A socket on the `dbus` thread's asyncio loop, five commands and one subscription. It adds no package and no tool, is the fastest, and its callback has the shape of a D-Bus callback. The cost is that the shell owns a wire format; it has been stable since PulseAudio 15.

### Option C — `pactl subscribe` (the fallback)

No protocol code, a tool that must be installed, several times slower. Kept as the documented fallback if the protocol client meets a server it cannot speak to.

### Options B and D

B adds two packages and `libpulse` for the same five commands. D is unproven for hardware volume.

## Decision

Decided by the orchestrator on 2026-11-13 under the [Tesserae Shell Directive](../00%20Home/Tesserae%20Shell%20Directive.md) (rule 7, Tier 1: the choice is inside `tess-shell` and adds no shared dependency), on the code session's recommendation:

1. Option A. [ADR-0019 Dependency Policy](ADR-0019%20Dependency%20Policy.md) is met: five commands and a notification are a few hundred lines of our own code, not a project of their own.
2. Option C is the fallback, not built unless A fails on a real server.
3. Reconnecting uses a watch on the socket's folder (inotify, a dependency the shell already has), so there is no timer while the server is gone and recovery is immediate.
4. The client negotiates the protocol version from the server's reply and works without port types on a server below version 34.
5. A future spike against a system service runs under the same sandbox wrapper, with a temporary home folder ([Orchestration Log](../00%20Home/Orchestration%20Log.md) D-026).

## Consequences

- The shell gains a small protocol module (`services/pulse_native.py`), with tests against a private server in the sandbox.
- The Audio module needs no new package. The policy's count of dependencies is unchanged.
- A real PulseAudio server (not PipeWire's) wants the user's cookie file; the client reads it when the zero cookie is refused. #needs-verification, since only `pipewire-pulse` was tested.
- Not proven and carried into the Audio part's tests: port types on hardware, a restart of `pipewire` itself, Bluetooth outputs.

## Links

- [Audio Access Spike](../90%20Research/Audio%20Access%20Spike.md) · [Audio Module](../40%20Specifications/Modules/Audio%20Module.md) · [ADR-0019 Dependency Policy](ADR-0019%20Dependency%20Policy.md) · [D-Bus Service Layer](../40%20Specifications/Integration/D-Bus%20Service%20Layer.md) · [M5 Brief](../00%20Home/M5%20Brief.md) · [Orchestration Log](../00%20Home/Orchestration%20Log.md)
