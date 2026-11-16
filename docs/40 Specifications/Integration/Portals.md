---
title: Portals
aliases: [XDG Desktop Portals, Desktop Portals, Appearance Portal]
type: spec
status: accepted
owner: phil
created: 2026-11-02
updated: 2026-11-16
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
- The package must install `io.github.mindderivative.TesseraeShell.desktop`. This is a delivery requirement, specified in [Packaging and Session Start > The Desktop File](../../70%20Delivery/Packaging%20and%20Session%20Start.md#the-desktop-file) (2026-11-13).
- Reading the Settings portal may not need the registration (reads are not tied to an app); that was not tested. Registering is cheap, and the id is what portals use to tell apps apart (the Registry documentation); whether `BindShortcuts` requires it is untested. #needs-verification
- On `NameOwnerChanged` of `org.freedesktop.portal.Desktop` the shell calls `Register` again, then re-reads the settings.
- **Order at start.** The service thread starts at step 10, so the portal `Register` and the single `ReadAll` run at the start of step 11, before the surfaces open ([Shell Start and Stop > Start Sequence](../Runtime/Shell%20Start%20and%20Stop.md#start-sequence)). The first theme resolve waits for the answer for at most 200 ms (proposed), then uses the defaults and re-resolves when the answer arrives, so a slow portal never delays the surfaces.
- If `Register` fails (portal absent, id already registered), the shell logs one warning and keeps reading settings. The maintainer chose to keep the warning until the package ships the `.desktop` file (D43, 2026-11-05).

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

## Settings Read in M5h (Decided 2026-11-13)

Read on the maintainer's machine on 2026-11-13 with read-only `ReadOne` calls on `org.freedesktop.portal.Settings`:

| Namespace and key | Value read | Use |
|---|---|---|
| `org.gnome.desktop.interface` `icon-theme` | `breeze-dark` (the same as `org.kde.kdeglobals.Icons` `Theme`) | The icon service's theme, before `kdeglobals` ([Tray Module > Icons (G8)](../Modules/Tray%20Module.md#icons-g8)) |
| `org.gnome.desktop.interface` `font-name` | `Hack Nerd Font  10` | The desktop's UI font, offered to themes as the token `type.system.font_family`; the shipped theme does not use it unless the user says so |
| `org.gnome.desktop.interface` `enable-animations` | true | False is treated as reduced motion |
| `org.gnome.desktop.interface` `cursor-theme` | `Oxygen 18 White` | Not used: the compositor draws the cursor |

## As Built in M5h (code session's report, 2026-11-14, not run in the vault)

Merged as `ce89ad5` (task T-044, PR #9; its suite 5010 passed, 1 skipped, 25 deselected, 1 expected failure).

| Part | Built |
|---|---|
| Reading | One `ReadAll` over `org.freedesktop.appearance` and `org.gnome.desktop.interface`; `SettingChanged` is followed for `icon-theme`, `font-name` and `enable-animations` |
| Icon theme | The icon service's order is: a theme set in code (the constructor or `set_theme`), then the portal's `icon-theme`, then `kdeglobals`, then `hicolor`. A portal change empties the icon cache and calls the listeners of `ctx.icons.on_theme_changed`; the shipped Tray resolves its icons again ([Tray Module > Icons (G8)](../Modules/Tray%20Module.md#icons-g8)) |
| Font | The token `type.system.font_family` holds the family of `font-name`: the first family of a list, with the style, weight and stretch words and the size taken off the end. The size is not offered |
| Motion | The combined flag `Appearance.motion_reduced` is true when `reduced-motion` is 1 or `enable-animations` is false; every user of reduced motion reads it. `Appearance.reduced_motion` still holds only the `reduced-motion` key |
| Not built | The Tasks module's icons (no Tasks module yet; it will use the same `ctx.icons.on_theme_changed`). The cursor theme is not used |

Gaps in this note that the build met, each now answered below: what the font token holds when the desktop names no font (question 3) and that the token is not in the schema export's token list (question 10). Follow-ups from the answers of 2026-11-16, for the code session: the font token falls back to the shipped default family and not `sans-serif` (3); one public reduced-motion flag, the combined one (6); the token in the export as a separate list (10); an open Tray menu refreshes its icons on a theme change (11).

## Open Questions

1. [x] Should the shell ship a `.desktop` file and which application id should it use for `Register` and delivery? Context: the portal Registry needs an id that matches the basename of a `.desktop` file (see the registry paragraph above); the Delivery notes must record it. Recommendation: use the shell's own D-Bus name as the id and ship the matching `.desktop` file in the package; the exact id is fixed in the Delivery notes. #needs-verification Decided by the orchestrator on 2026-11-13 (directive rule 7): as recommended.
2. [x] Is the GlobalShortcuts portal worth building for any v1 target? Context: v1 registers shortcuts through the KDE shortcut service ([Global Shortcuts](Global%20Shortcuts.md)) and commands cover other compositors. Recommendation: no. Decided by the orchestrator on 2026-11-13 (directive rule 7): as recommended.
3. [x] What does `type.system.font_family` hold when the desktop names no font? Context: the spec did not say. As built the token is always defined and holds `sans-serif`, so `check` does not report a bad token for a layout that uses it; whether tre accepts the generic name `sans-serif` is untested. Recommendation: keep it, and confirm the generic name against tre before the note is `stable`. #needs-verification Answered by the maintainer on 2026-11-16: it holds the default font family that `tess-shell` ships. This replaces the built `sans-serif`. The shipped `Default_Theme.tdl` sets no `Font_Family` today, so the code session names which family the shell uses when nothing is set and the token takes that.
4. [x] Does a theme that sets `type.system.font_family` itself keep its value over the desktop's font? Context: as built, yes. Recommendation: yes; a theme's own value is the author's choice, like a fixed accent. Answered by the maintainer on 2026-11-16: yes, a theme's own value wins over the desktop's font.
5. [x] Is the font's size offered too? Context: `font-name` carries a size (`Hack Nerd Font  10` on this machine); as built only the family is offered. Recommendation: family only for now; a size token can follow if a theme needs it. Answered by the maintainer on 2026-11-16: as recommended, family only.
6. [x] Keep two names for reduced motion: `Appearance.reduced_motion` for the portal key alone and `motion_reduced` for the combined flag? Context: the two names differ only in word order and are easy to confuse. Recommendation: keep one public flag, the combined one, and make the single key private. Answered by the maintainer on 2026-11-16: as recommended. One public flag, the combined one; the single `reduced-motion` key becomes private. This changes the built names, so it is a follow-up for the code session.
7. [x] Does an icon theme set in code beat the portal's? Context: as built, yes; the shell's tests rely on it, and no shell file key sets a theme today. Recommendation: yes. Answered by the maintainer on 2026-11-16: as recommended, yes: an icon theme set in code beats the portal's.
8. [x] May a portal icon-theme change notify listeners without comparing it to `kdeglobals`? Context: comparing would read a file on the loop thread; the cost of not comparing is one redundant icon refresh. Recommendation: yes, as built. Answered by the maintainer on 2026-11-16: as recommended, yes: notify without comparing to `kdeglobals`.
9. [x] Is a wrong-typed portal key logged at debug only? Context: [Failure Modes and Recovery](#failure-modes-and-recovery) says the key uses its default; the one warning is kept for the portal being unavailable. Recommendation: yes, as built. Answered by the maintainer on 2026-11-16: as recommended, yes: a wrong-typed key is logged at debug only.
10. [x] Should the schema export list `type.system.font_family`, so the configuration application can offer it? Context: it is documented only in the repository's README today; a test requires the export's token list to equal the shipped theme's tokens. Recommendation: yes, as a separate list of tokens the shell supplies, so that test keeps its meaning. Answered by the maintainer on 2026-11-16: as recommended: the schema export lists `type.system.font_family` in a separate list of tokens the shell supplies, so the test that the main list equals the shipped theme keeps its meaning. A follow-up for the code session.
11. [x] Should an open Tray menu also refresh its icons on a theme change? Context: as built only the item icons refresh; an open menu keeps the old icons until it is opened again. Recommendation: leave it; a theme change while a menu is open is rare and the menu is short-lived. Answered by the maintainer on 2026-11-16: yes, an open Tray menu refreshes its icons on a theme change. This differs from the recommendation and from what was built (only item icons refresh), so it is a follow-up for the code session.

## Questions After Testing

1. [ ] Does `ReadAll` need a registered app id? Context: the Registry says an unsandboxed app registers before any other portal call; whether reads work without it is unknown. Recommendation: always call `Register` first (as the acceptance criteria say) unless the test shows reads fail or break with it. Answered by: calling `ReadAll` on `org.freedesktop.appearance` with and without `Register` on this machine.
2. [ ] Does the KDE backend emit `SettingChanged` for the accent colour and the colour scheme at once, and for a custom colour scheme? Context: the theme re-resolve is coalesced to one per frame ([Failure Modes and Recovery](#failure-modes-and-recovery)). Recommendation: re-resolve on either signal and read all keys again, so the order of signals does not matter. Answered by: changing scheme, accent and a custom scheme in System Settings while `busctl --user monitor` watches the portal.
3. [ ] Does tre have a reduced-motion switch for the shell to set, or does the shell apply it alone? Context: acceptance requires no animation with `reduced-motion` 1. Recommendation: the shell applies it alone (it already does for Panels, D49) and uses a tre switch only if one exists. Answered by: checking tre's window and animation reference and a spike with an animated surface.
4. [ ] Is the 100 ms budget from signal to screen met on a loaded machine? Context: the code session saw `test_a_scheme_change_on_the_bus_reaches_the_bar_within_100_ms` take 1076 ms once in 6 runs of a CI shard, unexplained, one sample. Recommendation: keep the budget and read it on an idle machine; look again if it repeats. Answered by: repeating the test on an idle machine and on CI. Update, 2026-11-15 (code session's report, `tess-shell` PR #19): the same unexplained wait of about 650 ms before the portal reader saw a signal happened in 2 of 36 CI runs of one shard, while applying the look itself always took 0 to 1 ms. The test is now the best of five runs with a 3 s hang guard, so the 100 ms budget is checked on the shell's own work and the signal's arrival is not. Where the wait comes from is still unknown (the bus, the runner or the reader thread).

## Acceptance Criteria

- [ ] At start the shell reads `org.freedesktop.appearance` once and logs the four values at debug level.
- [ ] Changing the colour scheme in System Settings changes the shell's theme variant within 100 ms of the signal, with no restart.
- [ ] With `Appearance.Follow_Desktop` false, the portal is not called.
- [ ] With the portal service absent, the shell starts with the default variant and one warning.
- [ ] With `reduced-motion` 1, no shell animation runs and no looping icon animates.
- [ ] The shell calls `Register` before any other portal method, and the package ships the matching `.desktop` file.

## Links

- [Integration](Integration.md) · [ADR-0005 Global Shortcuts](../../30%20Decisions/ADR-0005%20Global%20Shortcuts.md) · [Global Shortcuts](Global%20Shortcuts.md) · [D-Bus Service Layer](D-Bus%20Service%20Layer.md) · [Plasma Coexistence](Plasma%20Coexistence.md) · [Style Schema](../../41%20TDL%20Reference/Style%20Schema.md)
