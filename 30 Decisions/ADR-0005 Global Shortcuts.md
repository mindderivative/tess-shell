---
title: ADR-0005 Global Shortcuts
aliases: [ADR-0005, Global Shortcut Service]
type: adr
status: accepted
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [adr, integration/dbus, needs-verification]
related: ["[[V1 Scope]]", "[[ADR-0004 Plasma Coexistence]]"]
depends_on: []
---

# ADR-0005: Global Shortcuts

> [!summary]
> The shell registers global shortcuts (launcher, OSD triggers) through KDE's global-accel service. The XDG GlobalShortcuts portal is the fallback to evaluate. Both are unverified on a live session and wait for the testing phase.

## Context

The launcher ([[Personas and Use Cases]] UC4) opens from a keyboard shortcut that works while no shell surface has focus. Under Wayland the client cannot grab keys itself; the compositor or its service must.

What the search found (2026-10-25, not tested):

- KDE's `kglobalacceld` exposes the `org.kde.KGlobalAccel` D-Bus interface; its `doRegister` and `setShortcut` calls are described by KDE developers as public API. Each action needs an object name, and one component registers a shortcut ([KGlobalAccel source](https://lxr.kde.org/source/frameworks/kglobalaccel/src/kglobalaccel.cpp), [kglobalacceld.h](https://lxr.kde.org/source/plasma/kglobalacceld/src/kglobalacceld.h), [forum thread](https://forum.kde.org/viewtopic.php%3Ff=43&t=109524.html)).
- The `org.freedesktop.portal.GlobalShortcuts` portal exists and KDE is reported to implement it. Since xdg-desktop-portal-kde 6.7.4, a shortcut is active only when the app calls `BindShortcuts` in the current session ([KDE bug 523063](https://bugs.kde.org/show_bug.cgi?id=523063), [1Password report](https://www.1password.community/developers-69/linux-kde-wayland-global-shortcut-ctrl-shift-space-does-not-work-after-1password-restarts-25707)).
- Observed on the maintainer's session (2026-10-26): `org.kde.kglobalaccel` is held by the `kwin_wayland` process ([[System Context#Observed D-Bus names]]).
- Not found: how `org.kde.KGlobalAccel` behaves for a non-KDE client on a Wayland session, and how a component is identified. #needs-verification

## Options

### Option A — KDE Global-accel Service (Chosen)

- **For:** the native KDE path; shortcuts appear in System Settings, where the user can change them.
- **Against:** KDE only. No shortcuts on wlroots compositors in v1.

### Option B — XDG GlobalShortcuts Portal

- **For:** works across desktops that implement it.
- **Against:** needs `BindShortcuts` on every start on recent Plasma; portal support differs by desktop. Kept as the fallback.

## Decision

Accepted 2026-10-25 by the maintainer in chat ("as recommended"): **Option A**, KDE's global-accel service.

## Consequences

- A global-shortcut spec under `40 Specifications/Integration/` documents the component name, action IDs and re-registration at start.
- On a compositor without the service (wlroots, in v1) the launcher still opens from the CLI or IPC command, and from a shortcut the user binds in the compositor itself.
- Verify in the testing phase: registration from Python over D-Bus on Plasma 6 Wayland, and what the user sees in System Settings.

## Links

- [[ADR-0004 Plasma Coexistence]] · [[V1 Scope#Decisions to take]]
