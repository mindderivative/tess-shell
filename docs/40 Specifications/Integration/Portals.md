---
title: Portals
aliases: [XDG Desktop Portals, Desktop Portals, Appearance Portal]
type: spec
status: draft
owner: phil
created: 2026-11-02
updated: 2026-11-02
tags: [spec/integration, integration/dbus, integration/portal, needs-verification]
---

# Portals

> [!NOTE]
> Which XDG desktop portals the shell uses, and for what. v1 uses one for certain: the Settings portal, to follow the desktop's colour scheme, accent colour, contrast and reduced-motion preference. The GlobalShortcuts portal is the named fallback of [ADR-0005 Global Shortcuts](../../30%20Decisions/ADR-0005%20Global%20Shortcuts.md) and is not built in v1. Everything else is listed so a later need has a place to start. The portal interfaces and values were read on the maintainer's machine on 2026-11-02 (xdg-desktop-portal 1.22.1, xdg-desktop-portal-kde 6.8.2), and the interface text comes from the [portal documentation](https://flatpak.github.io/xdg-desktop-portal/docs/) read the same day.

## Purpose and Scope

- Name each portal the shell may call, say whether v1 uses it, and give the identity rule for an unsandboxed caller.
- Specify the Settings portal read in full, because the design system's "follow the desktop theme" depends on it.
- Not in this note: the KDE shortcut path ([Global Shortcuts](Global%20Shortcuts.md)), or how tokens are built from the values (the design system, [Style Schema](../../41%20TDL%20Reference/Style%20Schema.md)).

## Behaviour

### Portals on the Observed Session

`org.freedesktop.portal.Desktop` at `/org/freedesktop/portal/desktop` offers 28 interfaces on this machine, among them `Settings` (version 2), `GlobalShortcuts` (2), `Inhibit` (3), `Notification` (1), `OpenURI` (5), `Background` (2), `ScreenCast`, `Screenshot`, `Clipboard`, `RemoteDesktop`, `InputCapture`, `Wallpaper`, `Trash` and `Usb`. Backends: `org.freedesktop.impl.portal.desktop.kde`, `.gtk` and `.kwallet` are on the bus, and `.plasmanotify` belongs to plasmashell ([Plasma Coexistence](Plasma%20Coexistence.md)).

| Portal | Use for the shell | v1 |
|---|---|---|
| Settings | Colour scheme, accent colour, contrast, reduced motion | Yes ([The Settings Portal](#the-settings-portal)) |
| GlobalShortcuts | Fallback to KDE's service, with `BindShortcuts` every start | No: named fallback ([Global Shortcuts Portal](#global-shortcuts-portal)) |
| OpenURI | Open a link from a tray menu or the launcher | No: the launcher uses desktop entries; revisit when the launcher is written |
| Inhibit | Hold off idle or suspend while a surface needs it | No |
| Notification | Post a notification | No: the shell posts none in v1 |
| Background | Ask to be autostarted | No: autostart is a delivery item for the session (a systemd user unit or an autostart file, [Shell Start and Stop > Telling Systemd (Decided 2026-10-28)](../Runtime/Shell%20Start%20and%20Stop.md#telling-systemd-decided-2026-10-28)) |
| Screenshot, ScreenCast | A screenshot or a recording | Post-v1 |
| Wallpaper | Set a wallpaper | Not needed: the wallpaper is plasmashell's ([Plasma Coexistence](Plasma%20Coexistence.md)) |

### Identity of an Unsandboxed Caller

Portals identify the caller by an application id. A Flatpak or Snap app has one from its sandbox; a normal install does not. The host portal Registry exists for this: `org.freedesktop.host.portal.Registry.Register(s app_id, a{sv} options)` is on the same object on this machine (version 1). Per the documentation, an unsandboxed app registers its D-Bus connection once, before any other portal call; registering after a portal call is an error; and the id must match the basename of a `.desktop` file that describes the app ([Registry](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.host.portal.Registry.html)).

- The shell registers the id `io.github.mindderivative.TesseraeShell` first, before it reads any setting. The id matches the bus name in [IPC and CLI > The Bus Name](../Runtime/IPC%20and%20CLI.md#the-bus-name).
- The package must install `io.github.mindderivative.TesseraeShell.desktop`. This is a **delivery requirement**; the Delivery notes are not written, so it is recorded here and in [Open Questions](../../00%20Home/Open%20Questions.md).
- Reading the Settings portal may not need the registration (reads are not tied to an app); that was not tested. Registering is cheap, and the id is what portals use to tell apps apart (the Registry documentation); whether `BindShortcuts` requires it is untested. #needs-verification
- On `NameOwnerChanged` of `org.freedesktop.portal.Desktop` the shell calls `Register` again, then re-reads the settings.
- **Order at start.** The service thread starts at step 10, so the portal `Register` and the single `ReadAll` run at the start of step 11, before the surfaces open ([Shell Start and Stop > Start Sequence](../Runtime/Shell%20Start%20and%20Stop.md#start-sequence)). The first theme resolve waits for the answer for at most 200 ms (proposed), then uses the defaults and re-resolves when the answer arrives, so a slow portal never delays the surfaces.
- If `Register` fails (portal absent, id already registered), the shell logs one warning and keeps reading settings.

### The Settings Portal

Interface `org.freedesktop.portal.Settings`, version 2 here. Methods: `ReadAll(as namespaces)` returning `a{sa{sv}}`, `ReadOne`, and the deprecated `Read`; signal `SettingChanged(s namespace, s key, v value)`. `ReadAll` with `org.freedesktop.appearance` was called on 2026-11-02 and returned four keys:

| Key | Type | Meaning (from the documentation) | Value on this machine |
|---|---|---|---|
| `color-scheme` | `u` | 0 no preference, 1 prefer dark, 2 prefer light | 1 (dark) |
| `accent-color` | `(ddd)` | sRGB, each in 0 to 1; out of range means unset | 0.239, 0.682, 0.914 (a light blue) |
| `contrast` | `u` | 0 no preference, 1 higher contrast | 0 |
| `reduced-motion` | `u` | 0 no preference, 1 reduced motion | 0 |

An unknown value for the three `u` keys counts as 0 ([documentation](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Settings.html), read 2026-11-02).

How the shell uses them:

| Value | Effect (proposed; the token side belongs to the design system) |
|---|---|
| `color-scheme` | Picks the light or dark theme variant when the active theme offers both ([Style Schema](../../41%20TDL%20Reference/Style%20Schema.md)). A theme with one variant ignores it |
| `accent-color` | Fills the `accent` token when the theme asks to follow the desktop; a theme with a fixed accent ignores it |
| `contrast` | Selects the high-contrast variant; a theme with none gets the shell's built-in high-contrast adjustments |
| `reduced-motion` | Sets reduced motion for all shell animation: durations go to 0 and looping icons stop. It also feeds tre's own reduced-motion setting if tre has one #needs-verification |

- **When it is read.** Once at start (see the order above), with a single `ReadAll`, then from `SettingChanged` only. No polling. The signal arrives on the service thread and is handed to the loop, which re-resolves the theme tokens and repaints ([D-Bus Service Layer > The Service Thread](D-Bus%20Service%20Layer.md#the-service-thread), [Hot Reload](../Runtime/Hot%20Reload.md)).
- **Order of precedence.** A value the user sets in the shell's `settings.tdl` wins over the portal (proposed key: `Appearance.Follow_Desktop`, default `true`, [Settings File](../../41%20TDL%20Reference/Settings%20File.md)). With it `false` the portal is not read.
- **Fallback.** No portal, a failed read, or an unknown key: `color-scheme` 0 (the theme's default variant), no accent, contrast 0, reduced motion 0. One warning, no retry loop; the shell tries again on `NameOwnerChanged` of `org.freedesktop.portal.Desktop`.
- **Latency.** The change must reach the screen within 100 ms of the signal (proposed budget, measured in testing).
- Plasma writes these values from its own appearance settings; whether a change in System Settings emits `SettingChanged` at once, and whether a colour scheme change that is not a light/dark switch does, is untested. #needs-verification

### Global Shortcuts Portal

Interface `org.freedesktop.portal.GlobalShortcuts`, version 2 here: `CreateSession(a{sv})`, `BindShortcuts(o session, a(sa{sv}) shortcuts, s parent_window, a{sv} options)`, `ListShortcuts`, `ConfigureShortcuts` (added in version 2), and signals `Activated`, `Deactivated`, `ShortcutsChanged` (all read 2026-11-02). Per the documentation, every shortcut belongs to a session that belongs to the app that created it; a shortcut has a `description` and an optional `preferred_trigger`; the app can bind only once per session; and `Activated` carries the shortcut id, a millisecond timestamp and an optional `activation_token` ([documentation](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.GlobalShortcuts.html)).

- **Status in v1: not built.** [ADR-0005 Global Shortcuts](../../30%20Decisions/ADR-0005%20Global%20Shortcuts.md) chose KDE's service and kept this as the fallback. The portal also works where `kglobalaccel` is absent but a portal backend implements it, which may include other compositors; that list is not checked.
- **Cost if built.** A session per start, a `BindShortcuts` call on every start (since xdg-desktop-portal-kde 6.7.4 a shortcut is active only after the app calls it in the current session, [ADR-0005 Global Shortcuts > Context](../../30%20Decisions/ADR-0005%20Global%20Shortcuts.md#context)), the id registration above, and a user-facing dialog on first bind that a KDE-service registration does not show (to be tested).
- **Recommendation.** Do not build it in v1: the commands cover non-KDE desktops ([Global Shortcuts > Fallbacks](Global%20Shortcuts.md#fallbacks)). Reopen it if a second compositor becomes a goal ([Goals and Non-Goals](../../10%20Vision/Goals%20and%20Non-Goals.md)).

### Not Used in v1

The portals that open a file chooser, print, read the camera, or share the screen are not used. A module that wants one later declares it in its own spec and goes through this note's identity rule.

## Configuration

| Key | Meaning | Default |
|---|---|---|
| `Appearance.Follow_Desktop` | Read the Settings portal and follow it (proposed; the settings list is deferred, [Settings File](../../41%20TDL%20Reference/Settings%20File.md)) | `true` |

## Python Contract

The shell reads the portal, not modules. A module gets the resolved values as theme tokens and a `reduced_motion` flag in its context (proposed, [Module Context](../../42%20Python%20API/Module%20Context.md)); it does not call the portal.

## Integration

- D-Bus: `org.freedesktop.portal.Desktop` on the session bus, through the shared service thread ([D-Bus Service Layer](D-Bus%20Service%20Layer.md)).
- Threads: `SettingChanged` runs on the service thread and crosses to the loop with `call_soon`.
- Related decisions: [ADR-0004 Plasma Coexistence](../../30%20Decisions/ADR-0004%20Plasma%20Coexistence.md) (the portal backends are not the shell's to own), [ADR-0005 Global Shortcuts](../../30%20Decisions/ADR-0005%20Global%20Shortcuts.md).

## Design

The portal supplies three tokens' sources: scheme, accent, contrast, and the motion flag. The token names and the mapping are for [Style Schema](../../41%20TDL%20Reference/Style%20Schema.md) and `50 Design System`.

## Accessibility

`contrast` and `reduced-motion` are the accessibility preferences the desktop already holds, so following them is the default, not an option the user must find. A user who sets `Follow_Desktop` to `false` also loses them; the setting's description says so.

## Performance Budget

- One `ReadAll` at start, under 20 ms of service-thread time (proposed; measured in testing).
- Idle: no timer; changes by signal only.

## Failure Modes and Recovery

| Failure | Result |
|---|---|
| Portal service absent | Defaults, one warning, retry on `NameOwnerChanged` |
| `Register` fails | One warning; reads continue |
| A key is missing or has an unexpected type | That key uses its default; the others apply |
| A burst of `SettingChanged` | The loop coalesces to one theme re-resolve per frame |
| Backend swaps (KDE to GTK) | The shell reads whichever answers on the portal name |

## Open Questions

1. [ ] Whether `ReadAll` needs a registered app id (test with and without `Register`).
2. [ ] Whether the KDE backend emits `SettingChanged` for the accent colour and scheme at once, and for a custom colour scheme.
3. [ ] Whether tre has a reduced-motion switch to set, or the shell applies it alone.
4. [ ] The `.desktop` file and the id for delivery; recorded for the Delivery notes.
5. [ ] Whether the GlobalShortcuts portal is worth building for any v1 target (recommendation: no).

## Acceptance Criteria

- [ ] At start the shell reads `org.freedesktop.appearance` once and logs the four values at debug level.
- [ ] Changing the colour scheme in System Settings changes the shell's theme variant within 100 ms of the signal, with no restart.
- [ ] With `Appearance.Follow_Desktop` false, the portal is not called.
- [ ] With the portal service absent, the shell starts with the default variant and one warning.
- [ ] With `reduced-motion` 1, no shell animation runs and no looping icon animates.
- [ ] The shell calls `Register` before any other portal method, and the package ships the matching `.desktop` file.

## Links

- [Integration](Integration.md) · [ADR-0005 Global Shortcuts](../../30%20Decisions/ADR-0005%20Global%20Shortcuts.md) · [Global Shortcuts](Global%20Shortcuts.md) · [D-Bus Service Layer](D-Bus%20Service%20Layer.md) · [Plasma Coexistence](Plasma%20Coexistence.md) · [Style Schema](../../41%20TDL%20Reference/Style%20Schema.md)
