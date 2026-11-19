---
title: TRE-REQ-028 App Drops Closed Windows
aliases: [TRE-REQ-028, App.remove_window, closed windows retained]
type: engine-request
status: draft
owner: phil
created: 2026-11-19
updated: 2026-11-19
tags: [engine-request, quality/performance, bug, needs-verification]
---

# TRE-REQ-028: `App` Must Drop a Window Once It Is Closed

> [!NOTE]
> tre's `App.add_window` only ever pushes onto `App.windows` and never removes a closed window, so a long-running shell grows with every Panel it closes and opens again. The shell's fix ([SHELL-REQ-001 Reload Memory Retention](SHELL-REQ-001%20Reload%20Memory%20Retention.md)) frees what it holds on a closed window, but the window objects themselves stay in tre. This request asks tre to release them. Written 2026-11-19 from the code session's report (`tess-shell` PR #83); not sent. The maintainer decides whether to carry it, and whether it joins 0.6.10.

## Need

A shell that reloads or hides and shows surfaces opens and closes windows all day. A closed window should leave `App.windows` and free its tree, its handler wrappers and its pending timers.

## What Tre Does Today (code session's finding; the vault did not run it)

| Observation | Source |
|---|---|
| `App.add_window` pushes onto `App.windows` and nothing removes a closed window | `crates/engine-py/src/app.rs`, per the code session |
| Per cycle of nine Panels away and back, nine `LayerWindow` objects stay, about 7 KiB heap and 0.3 to 0.45 MiB resident | After the shell's own fix; before it, about 5.8 MiB resident per cycle |
| Closed Popups: 100 open and close cycles keep 100 `OpenPopup` and 100 `PopupWindow`, about 5.7 KiB each | The shell's retention, not fixed yet; tre's share not separated |
| `window.after` timers still pending on a closed Panel are not cancelled; tre gives no list of them | The code session |
| 4 Python blocks per closed headless Popup, tre's handler wrappers (about 20 per open) | M7c, [Performance Budgets](../60%20Quality/Performance%20Budgets.md) |

## Proposed Change

tre implements this: when a window is closed, `App` drops it from `App.windows`, cancels its pending `after` timers and releases its tree and handler wrappers. If automatic dropping is unsafe for code that still holds the window object, offer `App.remove_window(window)` and document it; the shell would call it after its own cleanup.

## Alternatives

- The shell keeps its own listeners off closed windows (built, PR #83) and accepts about 7 KiB and 0.4 MiB per closed Panel. At nine Panels per reload and 100 reloads that is about 40 MiB resident, which is slow but unbounded.

## If Declined

The shell lives with it. The test of PR #83 marks tre's window objects as a strict expected failure and turns red the day tre fixes it.

## Acceptance

A test that opens and closes 100 windows on one `App` and finds `len(App.windows)` back at its starting value, the heap flat after the first few cycles, and no pending timer left on a closed window.

## Links

[SHELL-REQ-001 Reload Memory Retention](SHELL-REQ-001%20Reload%20Memory%20Retention.md) · [Performance Budgets](../60%20Quality/Performance%20Budgets.md) · [80 Requests](80%20Requests.md)
