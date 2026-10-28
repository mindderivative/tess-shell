---
title: ADR-0012 Keeping the Shell Above Plasma Panels
aliases: [ADR-0012, Plasma Panel Stacking]
type: adr
status: accepted
owner: phil
created: 2026-10-27
updated: 2026-10-27
tags: [adr, integration/kwin, needs-verification]
related: ["[[Surface Types#Fullscreen and maximised windows (decided 2026-10-27)]]", "[[Bar]]", "[[Frame]]", "[[ADR-0004 Plasma Coexistence]]", "[[ADR-0001 Shell Surface Strategy]]"]
depends_on: ["[[ADR-0004 Plasma Coexistence]]"]
---

# ADR-0012: Keeping the shell above Plasma panels

> [!summary]
> The maintainer wants a Bar to win over a Plasma panel on the same edge, unless that panel is always on top or a window is fullscreen. A `top` layer-shell surface and a Plasma panel share KWin's Above layer, so layer order does not settle it. This ADR compares the five ways the maintainer named (2026-10-27) and recommends one combination. Accepted 2026-10-27 as recommended; the facts come from KWin's source and one check on this machine, with no live test of any option.

## Context

- KWin's layers, lowest to highest: Desktop, Below, Normal, Above, Notification, Active, Popup, CriticalNotification, OnScreenDisplay, Overlay ([`globals.h`](https://invent.kde.org/plasma/kwin/-/raw/master/src/effect/globals.h)). A layer-shell `top` surface is in Above; `overlay` is in Overlay; a dock window (a Plasma panel) is in Above too ([`window.cpp`](https://invent.kde.org/plasma/kwin/-/raw/master/src/window.cpp)). See [[Surface Types#Fullscreen and maximised windows (decided 2026-10-27)]].
- Our rule: only `top` surfaces reserve space ([[Surface Types#Layers per kind]]). Required behaviour: a fullscreen window covers every shell element.
- The shell is a Python process on tre windows, with no Qt ([[ADR-0003 Process Model]]).

## Options

### Option 1 — KWin window rules (the Layer rule)
KWin's rule set has a Layer rule that overrides a window's stacking layer, and `Window::layer()` passes through it ([`rules.h`](https://invent.kde.org/plasma/kwin/-/raw/master/src/rules.h), [`window.cpp`](https://invent.kde.org/plasma/kwin/-/raw/master/src/window.cpp)). A rule can lower the Plasma panel's layer, or raise a shell surface's.
- **For:** the compositor does the stacking, so it is reliable once it applies; it does not touch our surfaces; a panel's strut is separate from its layer, so reserved space is unchanged. #needs-verification
- **Against:** it changes the user's KWin settings; matching a layer-shell surface or a panel needs checking (a rule can match on window type, class and title, and the files read do not show a layer-shell surface's class); the rule type is recent (it came from [MR 4953](https://invent.kde.org/plasma/kwin/-/merge_requests/4953), 2024), so older KWin lacks it.

### Option 2 — Put our surfaces in layers above Normal
`top` is already above Normal (it is Above); `overlay` is above everything.
- **For:** nothing to install.
- **Against:** `top` ties with panels, so it does not settle the order. `overlay` cannot reserve space under our rule, sits above fullscreen windows, and above Plasma's own OSDs and critical notifications (Overlay is the top layer). Splitting a Bar into an invisible reserver on `top` and a painter on `overlay` works but doubles the surfaces and covers notifications.

### Option 3 — A persistent KWin script
KWin's scripting API has `Window.keepAbove` and `keepBelow` (read-write), `layer` and `dock` (read-only), `fullScreen`, the signals `windowAdded` and `windowActivated`, and `workspace.raiseWindow(window)` ([scripting API](https://develop.kde.org/docs/plasma/kwin/api/)). A script cannot set `layer`. For a dock, `keepBelow` has no effect, because `belongsToLayer` returns Above for docks before it looks at `keepBelow`; for a layer-shell window the layer comes from the protocol layer. So a script cannot lower a panel, but it can raise a window with `raiseWindow` (within the same layer) and watch `fullScreen`. #needs-verification whether `raiseWindow` reorders a layer-shell window.
- **For:** a script can tell the shell about fullscreen windows (a D-Bus call from the script), which the shell needs for the fullscreen rule whatever else is chosen; it is the way scripts such as the `kzones` one already on this machine work.
- **Against:** a QML or JS file in the shell's package and a user-level install and enable step; it cannot change layers.

### Option 4 — PyGObject with KWindowSystem
- **For:** it would keep the shell in Python.
- **Against:** KWindowSystem is a Qt framework, not a GObject library. On this machine PyGObject 3.50.0 has no typelib for it (`gi.require_version("KWindowSystem", ...)` reports the namespace unavailable; the KF6 headers are installed but no GIR), and PySide6 is not installed. A Python binding for it was not found. On Wayland it is also not shown to reorder other windows. #needs-verification Not viable as stated.

### Option 5 — Writing the rules into `~/.config/kwinrulesrc`
This is the delivery of Option 1, not a different effect. Rules are INI groups; people write them with `kwriteconfig6` and ask KWin to reload, and reports on reliability differ (one thread says a reconfigure did not apply the rule until plasmashell had run; a KDE patch sent a reload signal to KWin) ([discussion](https://discuss.kde.org/t/applying-window-rule-via-command-line/37452)). The file exists on this machine and was not read.
- **Against:** the shell would write to a file that is the user's and shared with the Rules KCM; it must append its own group only, never rewrite others', and remove it on uninstall.

## Recommendation (proposed)

- **Do not rely on stacking for v1 correctness.** Default: `top`, coexist ([[ADR-0004 Plasma Coexistence]]); put the Bar on an edge or monitor the Plasma panel does not use, or hide the Plasma panel there, as the maintainer's Edge Shell does with its per-monitor mode (shell, Plasma, both, none).
- **Ship Option 3 for fullscreen detection** (needed anyway): a small KWin script reports fullscreen windows to the shell, which hides its surfaces on that monitor.
- **Offer Options 1 and 5 as an opt-in, explicit step** for a user who wants the Bar to win: a shell command writes one clearly named rule group (lowering the Plasma panel's layer) after showing it to the user, and a second command removes it. Never automatic.
- **Reject Options 2 and 4** as the answer: 2 does not settle the order or covers notifications, 4 has no binding.

## Decision

The maintainer accepted the recommendation as written (2026-10-27): v1 does not rely on stacking; a KWin script reports fullscreen windows; KWin window rules (written to `kwinrulesrc`) are an opt-in step with consent and an undo; layers above Normal and PyGObject with KWindowSystem are rejected.

## Consequences

- The fullscreen rule needs a KWin script; the install path and enable step are a delivery item ([[Surface Types#Fullscreen and maximised windows (decided 2026-10-27)]]).
- A KWin rule is a change to the user's desktop, so it needs consent and an undo.
- Testing phase: on KWin 6.8.1, with a temporary rule and then a removal, check that a Layer rule matches a Plasma panel and a layer-shell surface, that a maximised window still stops at the panel's strut, and that an active fullscreen window covers `top` surfaces and not `overlay` ones.

## Links

[[Surface Types]] · [[Bar]] · [[Frame]] · [[ADR-0004 Plasma Coexistence]] · [[30 Decisions]]
