---
title: TRE-REQ-026 Lost Connection Signal and Layer Shell Re-Probe
aliases: [TRE-REQ-026, wayland connection lost, supports layer_shell re-probe]
type: engine-request
status: draft
owner: phil
created: 2026-11-17
updated: 2026-11-17
tags: [engine-request, quality, needs-verification]
---

# TRE-REQ-026: Tell the Application That the Wayland Connection Was Lost, and Let `supports('layer_shell')` Re-Probe

> [!NOTE]
> When the compositor goes away, the shell finds out only because tre's windows close and the loop ends. Two small additions would let it recover cleanly: a signal that the Wayland connection was lost, and a `supports('layer_shell')` that asks again instead of keeping its first answer. Drafted on 2026-11-17 from the code session's report of the M7b work (`tess-shell` PR #67) and offered to the maintainer to carry; not sent to tre.

## Shell Need

After a lost compositor the shell stops its modules, saves the registry and exits with code 69, and the session unit restarts it ([Crash Recovery and Watchdog](../60%20Quality/Crash%20Recovery%20and%20Watchdog.md)). If the compositor is not back within the unit's restart delay of 2 seconds, the restarted shell exits 2 (no layer shell) and the unit stays down. A signal for "the connection was lost" would let the shell tell a lost compositor from other endings of the loop without inference, and a `supports('layer_shell')` that re-probes would let a restarted shell wait for the compositor instead of failing at once.

## What Tre Does Today

| Fact | Source |
|---|---|
| The shell treats the end of the loop with its windows closed as a lost compositor | The code session's report, 2026-11-17 |
| `supports('layer_shell')` caches its first answer | The code session's report. #needs-verification: the vault has not read the engine's code or documentation for this |
| There is no signal for a lost connection | The code session's report; the vault found none in the API page. #needs-verification |

## Proposed Change

tre implements both: (1) an `App` event or callback such as `connection_lost` fired once when the Wayland connection breaks, before the windows are closed; (2) `supports('layer_shell')` that probes again when asked (or takes a `refresh=True` argument), so a caller can poll until the compositor is back.

## Alternatives

None needed beyond the shell's own inference, which it already has.

## If Declined

The shell keeps inferring a lost compositor from the loop ending, and a restarted shell that finds no compositor exits 2.

## Acceptance

On a private sway killed while a window is open: the callback fires once, with the application still running; after a new sway starts, `supports('layer_shell')` with the refresh returns true.

## Links

[Crash Recovery and Watchdog](../60%20Quality/Crash%20Recovery%20and%20Watchdog.md) · [M7 Brief](../00%20Home/M7%20Brief.md) · [80 Requests](80%20Requests.md)
