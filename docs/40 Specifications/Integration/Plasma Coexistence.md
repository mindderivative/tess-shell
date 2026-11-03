---
title: Plasma Coexistence
aliases: [Coexistence, Plasmashell Coexistence Spec]
type: spec
status: draft
owner: phil
created: 2026-11-02
updated: 2026-11-02
tags: [spec/integration, integration/dbus, integration/plasma, needs-verification]
---

# Plasma Coexistence

> [!NOTE]
> The per-service rule that [ADR-0004 Plasma Coexistence](../../30%20Decisions/ADR-0004%20Plasma%20Coexistence.md) (accepted) asks every integration spec to carry: who owns each name or role on a Plasma session today, what mode the shell uses (coexist, proxy or replace), and what happens when the shell starts before, after or without plasmashell. In v1 every row is `coexist`: the shell takes no name that plasmashell, `kded6` or KWin holds. The owners were read on the maintainer's machine on 2026-11-02 (Plasma 6.8.2, KWin 6.8.2; KWin was 6.8.1 on 2026-10-26 and 2026-10-29); other distributions and versions may differ.

## Purpose and Scope

- Give the owner, mode and start-order behaviour for each shared service, so no other spec has to argue it.
- State what the shell does to plasmashell's visible parts: panels, wallpaper, desktop widgets.
- Not in this note: stacking against Plasma panels ([ADR-0012 Keeping the Shell Above Plasma Panels](../../30%20Decisions/ADR-0012%20Keeping%20the%20Shell%20Above%20Plasma%20Panels.md), [KWin Integration](KWin%20Integration.md)), the D-Bus rules themselves ([D-Bus Service Layer](D-Bus%20Service%20Layer.md)), and a notification centre, which is after v1 ([V1 Scope > After v1](../../10%20Vision/V1%20Scope.md#after-v1)).

## Behaviour

### The Three Modes

| Mode | Meaning | Allowed in v1 |
|---|---|---|
| coexist | The shell is a client or a second host. It takes no name the other process holds, and stopping the shell leaves nothing to restore | Yes, every row |
| proxy | The shell forwards to the other process's service | Not used |
| replace | The shell owns the name | No: needs its own ADR ([ADR-0004 Plasma Coexistence > Options](../../30%20Decisions/ADR-0004%20Plasma%20Coexistence.md#options)) |

### Services and Owners

Owners read with `busctl --user list` on 2026-11-02; the last row is on the system bus (`busctl --system list`), and no media player was running that day, so the players are from 2026-10-26.

| Service | Owner today | Mode | Shell behaviour | Before or after plasmashell |
|---|---|---|---|---|
| `org.freedesktop.Notifications` | plasmashell | coexist (none) | The shell neither serves nor posts notifications in v1 | n/a. A later notification centre needs a replace ADR, and plasmashell must stop serving first |
| `org.kde.StatusNotifierWatcher` | `kded6` (not plasmashell) | coexist | The Tray module is a second host ([Tray](#tray)) | The watcher outlives plasmashell, so order does not matter while `kded6` runs |
| `org.kde.StatusNotifierHost-<pid>` | plasmashell (`-1458` here) | coexist | The shell registers its own host name next to it | Independent |
| `org.kde.kglobalaccel` | `kwin_wayland` | coexist | The shell registers its own component ([Global Shortcuts](Global%20Shortcuts.md)) | Independent of plasmashell; needs KWin |
| `org.kde.JobViewServer`, `org.kde.kuiserver` | plasmashell | coexist (none) | Not used | n/a |
| `org.kde.plasmashell`, `org.kde.klipper` | plasmashell | coexist (none) | Not used. Klipper (clipboard history) is a possible later source | n/a |
| `org.freedesktop.impl.portal.desktop.plasmanotify` | plasmashell | coexist (none) | Not used | n/a |
| `org.kde.KWin`, `org.freedesktop.ScreenSaver` | `kwin_wayland` | coexist | Read as in [KWin Integration](KWin%20Integration.md) | n/a |
| `org.freedesktop.portal.Desktop` | xdg-desktop-portal | coexist | Client only ([Portals](Portals.md)) | Independent |
| `org.freedesktop.PowerManagement`, `org.kde.Solid.PowerManagement` | `org_kde_powerde` (PowerDevil) | coexist (none) | Not used in v1; the Battery module reads UPower directly ([D-Bus Service Layer > The Service Catalogue](D-Bus%20Service%20Layer.md#the-service-catalogue)) | n/a |
| `org.mpris.MediaPlayer2.*`, `org.freedesktop.NetworkManager`, `org.freedesktop.UPower` | the players, NetworkManager, upowerd | coexist (read only) | Clients | n/a |

> [!WARNING]
> **Unverified on other machines**
> The table is one session. Whether `kded6` owns the watcher, and whether `kwin_wayland` owns `org.kde.kglobalaccel`, is a property of this Plasma version; a different Plasma version or distribution may differ. The shell must not hard-code an owner: it uses the name only ([D-Bus Service Layer > Listening and Name Owners](D-Bus%20Service%20Layer.md#listening-and-name-owners)).

### Tray

- The Tray module registers as a host: it owns a name `org.kde.StatusNotifierHost-<pid>` (the shell's pid, with a suffix if the name is taken) and calls `RegisterStatusNotifierHost` on the watcher. The method and the name pattern are present on this machine; the full protocol text is the StatusNotifierItem specification ([KDE StatusNotifierItem](https://www.freedesktop.org/wiki/Specifications/StatusNotifierItem/), read as a reference, not re-read on 2026-11-02). #needs-verification
- Both hosts see every item. Apps that fall back to a window tray when no host exists will not, because plasmashell is already a host.
- Two trays showing the same items is a user choice: the user either hides the Plasma tray or does not use the shell's Tray module. The shell does not touch plasmashell's tray.
- If the watcher is absent (a session without `kded6`'s watcher module, or not Plasma), the module shows nothing and logs one warning. The shell does not start its own watcher in v1 (replace needs an ADR).

### Panels, Wallpaper and Desktop Widgets

- Plasma panels keep running. The shell's Bar and Frame reserve their own exclusive zones next to them ([Surface Types](../Surfaces/Surface%20Types.md), [Bar](../Surfaces/Bar.md)); two reservers on one edge stack, which [Wayland Protocols](Wayland%20Protocols.md) covers.
- Where a Plasma panel and a shell surface overlap in stacking, [ADR-0012 Keeping the Shell Above Plasma Panels](../../30%20Decisions/ADR-0012%20Keeping%20the%20Shell%20Above%20Plasma%20Panels.md) applies: the shell does not rely on stacking in v1.
- The wallpaper belongs to plasmashell (two `plasmashell` windows of type desktop, one per output, on the layer below normal windows; [KWin Integration > What a script inside KWin showed (test of 2026-10-29)](KWin%20Integration.md#what-a-script-inside-kwin-showed-test-of-2026-10-29)). A shell wallpaper surface is not in v1.
- The shell never closes, moves or configures a plasmashell window or setting. The only file of the user's Plasma setup it may write is the opt-in window rule ([KWin Integration > Window rules](KWin%20Integration.md#window-rules)).

### Start Order

| Case | Behaviour |
|---|---|
| Shell starts after plasmashell | Normal. Tray finds the watcher; shortcuts register; the shell reads `NameOwnerChanged` for the rest |
| Shell starts before plasmashell | The shell does not wait for it. Services that plasmashell serves are not used in v1, so nothing is missing. The Tray module's host registers with the watcher whether or not plasmashell is up |
| plasmashell restarts while the shell runs | The shell is unaffected. The tray host and shortcut component are not plasmashell's. A module that uses a plasmashell name gets `on_service_lost`, then `on_service_found` ([D-Bus Service Layer > Listening and Name Owners](D-Bus%20Service%20Layer.md#listening-and-name-owners)) |
| Session without plasmashell (another desktop, or plasmashell stopped on purpose) | The shell runs; modules that need a Plasma service show `UNAVAILABLE`. Support for this is not a v1 goal ([Goals and Non-Goals](../../10%20Vision/Goals%20and%20Non-Goals.md)) |
| The shell stops | It drops its tray host name and sets its shortcut actions inactive; the shortcut component and the user's keys stay ([Global Shortcuts > Cleaning Up](Global%20Shortcuts.md#cleaning-up), [Shell Start and Stop > Stop Sequence](../Runtime/Shell%20Start%20and%20Stop.md#stop-sequence)). It leaves no bus name and no rule that plasmashell must clean up |

### What Needs a Later ADR

| Wanted | Why it is a replace | Blocker |
|---|---|---|
| A notification centre | Only one process may own `org.freedesktop.Notifications` | plasmashell holds it; no stop-and-take path is designed |
| A tray watcher | Only one `org.kde.StatusNotifierWatcher` | `kded6` holds it |
| Job progress (`org.kde.JobViewServer`) | Held by plasmashell | Not in v1 |

## Configuration

None. No setting enables a replace mode in v1. If a setting ever does, it is one per service with the default `COEXIST`, and its ADR is linked here.

## Python Contract

A module reads a service through `ctx.dbus` and gets `UNAVAILABLE` when the owner is missing ([D-Bus Service Layer](D-Bus%20Service%20Layer.md)). No module may request a name that appears in the table above ([D-Bus Service Layer > Own Names and Objects](D-Bus%20Service%20Layer.md#own-names-and-objects)).

## Integration

- Threads and libraries: [D-Bus Service Layer](D-Bus%20Service%20Layer.md).
- Names, versions and the observed owners: [System Context > Observed D-Bus names](../../20%20Architecture/System%20Context.md#observed-d-bus-names).

## Design

None.

## Accessibility

Two trays showing the same items doubles the controls a screen reader meets. The Tray module's accessible name says which tray it is ("Tesserae Shell tray") so the user can tell them apart (proposed).

## Performance Budget

Coexistence adds no work: the shell owns one name of its own plus the tray host name, and listens to `NameOwnerChanged` for the names its modules use.

## Failure Modes and Recovery

| Failure | Result |
|---|---|
| The tray host name is taken | The module requests `-<pid>-<n>` with the next `n`; after 3 tries it logs and shows nothing |
| `RegisterStatusNotifierHost` fails | One warning; the Tray module is empty |
| `kded6` restarts | The helper sees `NameOwnerChanged` for `org.kde.StatusNotifierWatcher`; the Tray module calls `RegisterStatusNotifierHost` again and re-reads `RegisteredStatusNotifierItems`. A new watcher knows no hosts until one registers. #needs-verification |
| Another distribution has no watcher | As above: empty tray, one warning |
| The user starts a second shell | Prevented by the lock and the single bus name ([Shell Start and Stop > Process rules](../Runtime/Shell%20Start%20and%20Stop.md#process-rules)) |

## Open Questions

1. [ ] Whether a second tray host sees items that register before it joins: the watcher's `RegisteredStatusNotifierItems` property lists them, so the host reads it at registration (proposed; test).
2. [ ] The behaviour of an app that checks `IsStatusNotifierHostRegistered` when only the shell's host is present (test with plasmashell stopped, in a throwaway session).
3. [ ] Whether the same owners hold on Plasma versions before 6.8 and on Fedora, KDE neon and Arch.
4. [ ] Whether the shell should offer a `tesserae-shell doctor` command that prints the owners table for a bug report (recommended, post-v1).

## Acceptance Criteria

- [ ] On a Plasma session, starting the shell changes no name owner in `busctl --user list` except the shell's own name and its tray host.
- [ ] After a normal stop, both names are gone, the shell's shortcut actions are inactive, and plasmashell has no new state.
- [ ] The Tray module shows the items listed in `RegisteredStatusNotifierItems` at start.
- [ ] With plasmashell stopped and started again, the shell keeps running and its tray host remains registered.
- [ ] With no watcher on the bus, the Tray module is empty, logs one warning, and the shell runs.
- [ ] Nothing in the shell requests `org.freedesktop.Notifications`, `org.kde.StatusNotifierWatcher` or `org.kde.kglobalaccel`.

## Links

- [Integration](Integration.md) · [ADR-0004 Plasma Coexistence](../../30%20Decisions/ADR-0004%20Plasma%20Coexistence.md) · [ADR-0012 Keeping the Shell Above Plasma Panels](../../30%20Decisions/ADR-0012%20Keeping%20the%20Shell%20Above%20Plasma%20Panels.md) · [D-Bus Service Layer](D-Bus%20Service%20Layer.md) · [Global Shortcuts](Global%20Shortcuts.md) · [Portals](Portals.md) · [System Context](../../20%20Architecture/System%20Context.md)
