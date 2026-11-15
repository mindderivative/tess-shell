---
title: M6 Build Log
aliases: [M6 Log]
type: moc
status: draft
owner: phil
created: 2026-11-13
updated: 2026-11-13
tags: [moc, build-log]
---

# M6 Build Log

> [!NOTE]
> The log of milestone M6, focus and keyboard (parts M6a to M6d of [M6 Brief](M6%20Brief.md)). The `tess-shell` code sessions own this note ([Build Logs](Build%20Logs.md)). The vault session created it empty on 2026-11-13; the entry for T-047 (M6c, shortcuts) is in the [M5 Build Log](M5%20Build%20Log.md) because this note did not exist yet, and its owner may move it here. Several sessions write here: each entry says which session wrote it ([Task Owners](Task%20Owners.md)).

## Tasks

Written by the session `keys` (it made `../tess-shell-t047`).

| Task | State | Commit | Note |
|---|---|---|---|
| T-047 M6c shortcuts (C1) | Merged | 974596d | Full entry in [M5 Build Log](M5%20Build%20Log.md) (written before this log existed). 4600 passed, 1 skipped, 25 deselected |
| T-053 `fix/shortcuts-followups` | Merged | a3083ca | The fake kglobalaccel signatures are the real ones; `isGlobalShortcutAvailable` before the taken warning; a `Call` shortcut loads its module. 4628 passed, 1 skipped, 25 deselected; the session pushed `fix/shortcuts-followups:main` itself |

## Measurements

T-053 (2026-11-13 22:50, `keys`): full suite 4628 passed, 1 skipped, 25 deselected, `ruff` and `mypy` clean; report `/tmp/frame-review/T053.md`. The new tests: 15 signature checks (a right-signature call and a deliberately wrong one for each member of the real interface, plus answer, signal and property shapes), the availability cases (cleared by the user, held by the desktop, held by another component, no call when the key was set, a failing call; exactly one availability call per empty chord), and 5 live tests of a `Call` shortcut whose module no surface uses (loaded and started once with no use, a press calls the action with its argument, removing the entry at reload stops the module, a surface that later uses it shares the one instance, a missing action still a finding).

## Differences from the Specs

T-053 against [Global Shortcuts](../40%20Specifications/Integration/Global%20Shortcuts.md): the client already sent the real signatures, so only the fake changed (`unregister` answers `b`, `allShortcutInfos` is `a(ssssssaiai)` with real rows, `setShortcut` and `globalShortcutAvailable` added). The fake cannot export `allShortcutInfos` with the optional `s` argument, because dbus-fast allows one handler per method name; the shell never calls it. The return type of `invokeShortcut` was not in the introspection table: the fake returns `b`, the real one may be void; the shell never calls it. When the availability call fails, the taken warning reads 'could not be checked' after the usual text.

## Facts About tre, TEL and tess_dl

A live test that asserts `"ERROR" not in stderr` flakes: tre's GPU layer logs `wgpu_hal::vulkan::swapchain::native: get_physical_device_surface_capabilities: ERROR_SURFACE_LOST_KHR` when a window is created or torn down on a headless sway under load (2 failures in 72 loaded runs). Match the shell's own level with `"| ERROR "` instead. It is harmless and tre's.

## Decisions Needed

## For the Vault Session

## Links

- [Build Logs](Build%20Logs.md) · [M6 Brief](M6%20Brief.md) · [M5 Build Log](M5%20Build%20Log.md) · [Task Owners](Task%20Owners.md)
