---
title: SHELL-REQ-001 Reload Memory Retention
aliases: [SHELL-REQ-001, reload leak, 7 MiB per reload]
type: engine-request
status: accepted
owner: phil
created: 2026-11-19
updated: 2026-11-19
tags: [engine-request, quality/performance, bug]
---

# SHELL-REQ-001: Find and Fix the Memory Kept by a Reload

> [!NOTE]
> The M7c reading found that a reload which removes and re-adds nine Panels leaves about 7 MiB more in Python objects after each cycle. If that holds over many reloads, a shell that is edited all day grows without limit. The code session reported it as a possible leak that needs a separate look. This request asks `tess-shell` to reproduce it, find what holds the memory, fix it, and add a test that fails while it leaks. The sender is the vault session on the maintainer's instruction (2026-11-19). Drafted by the vault; sent to `tess-shell` on the maintainer's standing order for work of this kind. Nothing here was run in the vault.

## Built (code session's report of `tess-shell` PR #83, merged 2026-11-19, CI green; not run in the vault)

It was a real, steady, linear leak, and only when Panels close and open; a reload that changes nothing or only a style never leaks. The 7 MiB was a Python heap reading (`tracemalloc`) per cycle of nine Panels away and back (two reloads).

- **Before the fix:** +5.0 MiB heap, +13,000 `gc` objects (exactly linear), +9 each of Surface, View, LiveTree and LayerWindow, +142 tre Node wrappers, about +5.8 MiB resident of the real shell on a private sway. The first three reloads add about 12 MiB once (a warming cache, not the leak).
- **Why M7c missed it:** the stub app the tests and probes use ignores `add_window`, so nothing grew. The fix's tests use a real `tess_re.App`.
- **Cause:** tre's `App.add_window` only pushes onto `App.windows` and never removes a closed window. The shell's listeners on each closed Panel's window (App to LayerWindow to the `_panel_events.on_key` closure to the Surface and View) held the whole Surface, View and tree.
- **Fix:** `free_window` in `surfaces/manager.py` takes the shell's listeners off a closed window and destroys the root's children once both tre has closed it and the manager has dropped it, in either order. A window a live surface still names is never touched.
- **After:** Surface, View and LiveTree constant, about 6 KiB heap per cycle; the real shell over 40 reloads keeps Surface at 10, View at 10, Node at 285, and about 0.26 MiB resident per cycle after reload 20 (5.8 before).
- **What stays is tre's:** 9 `LayerWindow` objects per cycle, about 7 KiB heap and 0.3 to 0.45 MiB resident. Drafted as [TRE-REQ-028 App Drops Closed Windows](TRE-REQ-028%20App%20Drops%20Closed%20Windows.md).
- **Tests:** `tests/test_reload_leak.py` (30 reloads, 12 s, no sway) fails without the fix (Surface 37 to 145, heap +60,494 KiB) and passes with it. A strict expected failure marks tre's window objects and turns red the day tre fixes it. B16 now has the reload case beside the Popup case.

Decisions from the build: see [Performance Budgets](../60%20Quality/Performance%20Budgets.md).

## What Is Known

| Fact | Source |
|---|---|
| A reload that removes and re-adds nine Panels retains about 7 MiB per cycle in Python objects | The code session's M7c report, 2026-11-19 (the figure is not in `tests/perf/budget-results.md`; the harness's own run holds the detail) |
| A closed Popup holds nothing over 200 open and close cycles: no growth in threads, descriptors, Bar nodes, open Popups, Popup windows or live trees | `budget-results.md`, B16 part, headless |
| One thing is held per closed headless Popup: 4 Python blocks per cycle, tre's handler wrappers of a closed headless window (about 20 per open) | Same file, "Python blocks left per cycle", recorded |
| The reload itself is fast: 41 ms median for a Bar and 9 shown Panels, 243 ms from the save with the debounce | B06 |

> [!WARNING]
> **Unconfirmed**
> The code session answered on 2026-11-19 that it cannot say which reading the figure was or whether it grows each cycle. It came only from the M7c builder's final summary ("in Python objects; tre alone does not"); the builder's report file is gone with the reboot, the real reading does not contain it, and the one test that touches it reads RSS over 12 reloads against a 40 MiB bound, which cannot show 7 MiB per cycle. Most likely a Python block count, not RSS. Treat it as a suspect, not a finding. The code session reproduces it after the M7a2 full measurement, because anything run now would spoil that run.

Two readings of "7 MiB per cycle" are possible and the report does not say which: Python heap growth measured with `tracemalloc` or `gc`, or resident memory. The first job is to find out which one it was, and whether it is steady growth per cycle or a one-off rise that levels off after the first reload (a cache warming up is not a leak).

## Where to Look

The reload path is `Reloader._apply_now` in `src/tess_shell/reloader.py`. It replaces `self.scan` and `self.file_uids` with the new scan, builds `look`, calls `host.sync`, calls `store.add_use` for every use, then `manager.apply`, which closes and opens the surfaces. Suspects, in the order I would check them:

1. **Surfaces removed by `manager.apply`.** Does every closed Panel's window, tree, bound `Signal` or `Computed`, `Effect`, event handler and module `Context` become unreachable? A handler or `Effect` kept in a list or a dict keyed by the old surface keeps the whole tree alive. Compare with the Popup path, which is clean.
2. **`store.add_use(module, key)`.** It runs for every use on every reload. If a use is added and never removed when its surface closes, the store grows by nine entries per cycle, and what each holds with it.
3. **`host.sync` and `host.dynamic`.** Module instances, their `start` results and callbacks that are replaced by a new set on each reload but not stopped or dropped. `modules/host.py` has `stop_all`, which suggests a per-module counterpart exists; check that reload calls it for what it replaces.
4. **The previous `scan` result and `look`.** Each reload keeps `self.scan` (the full parse with its trees) and builds a new `look` from it. A reference from the new objects back to the old (a closure over the previous scan, a log record) chains them.
5. **tre's handler wrappers.** The 4 blocks per closed Popup show tre keeps some wrappers of a closed window. If a closed Panel keeps its wrappers as well, that is tre's to fix: collect the numbers, then write the request to tre (the vault will draft it, TRE-REQ number to follow).
6. **`self.reloads`, the `Outcome` and the log.** Small, but check that no list of outcomes or findings grows without limit.

## Method

1. Reproduce headless first: the example shell with a Bar and nine shown Panels, as in B06, on a private sway. Touch a file nine to fifty times in a row.
2. Measure three ways after each reload, after a forced `gc.collect()`: `len(gc.get_objects())`, `tracemalloc` current size with a snapshot taken after reload 3 and compared with a snapshot after reload 33 (`compare_to(..., "lineno")`), and PSS. Steady growth per cycle in all three is a leak; growth in PSS alone is allocator behaviour or tre.
3. Count instances per type with `gc.get_objects()` before and after a run of 30 reloads, for the shell's own classes (Panel, surface, tree, `Signal`, `Effect`, module context and instances, `Use`) and for tre's window and handler wrapper classes. The type whose count grows by a multiple of nine per cycle is the owner of the leak.
4. For the type that grows, `gc.get_referrers` on one stale instance, walked up until a long-lived object (the `Reloader`, `store`, `host`, `manager`, `app`, or a tre object) holds it. That chain is the fix.
5. Repeat with a reload that changes nothing, and with one that only changes a style, to see if the leak needs the Panels to close and open or happens on every reload.

## Acceptance

- The code session reports what held the memory and where, with the type counts before and after.
- A test that runs 30 reloads of a shell with a Bar and nine Panels and fails if the live count of the grown type or the `tracemalloc` size grows by more than a fixed small amount between reload 5 and reload 30 (a threshold, not zero, since Python's own caches settle).
- The fix, or a plain statement that the growth is tre's wrappers with the numbers, so the vault can draft the request to tre.
- B16 gets the reload case beside the Popup case, so the budget covers it from now on.

## If Declined

The risk stays recorded in [Performance Budgets](../60%20Quality/Performance%20Budgets.md) and a reload-heavy session is restarted by hand; a shell started by `install-session` restarts at login anyway.

## Links

[Performance Budgets](../60%20Quality/Performance%20Budgets.md) · [Hot Reload](../40%20Specifications/Runtime/Hot%20Reload.md) · [M7 Brief](../00%20Home/M7%20Brief.md) · [80 Requests](80%20Requests.md)
