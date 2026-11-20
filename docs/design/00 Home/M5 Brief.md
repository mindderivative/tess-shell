---
title: M5 Brief
aliases: [M5, Services Brief, Shell M5]
type: moc
status: draft
owner: phil
created: 2026-11-08
updated: 2026-11-13
tags: [moc, roadmap, brief]
---

# M5 Brief

> [!NOTE]
> The scope of milestone M5, "services and desktop integration": the shell stops showing only its own values and shows the desktop's. It grows the service thread that M3a started for the portal reader into the full [D-Bus Service Layer](../40%20Specifications/Integration/D-Bus%20Service%20Layer.md), adds the modules that read a desktop service (Battery, Workspaces, Network, Media, Audio and Tray), then the KWin integration (the KWin script, fullscreen hiding and Tasks) and the portal settings. The maintainer moved the service layer and the modules here from M4 on 2026-11-08 ("I want the basic widgets completed first"): [M4 Brief](M4%20Brief.md) builds every V1 widget and M5 starts after it. On the same day he decided that M5 stays one milestone, broken into smaller parts like the others, that focus and keyboard is its own milestone ([M6 Brief](M6%20Brief.md): global shortcuts and the launcher moved there) and that release is M7. This note keeps the service plan written for M4 on 2026-11-05, renamed and split further; its answered questions stay as history. It starts when M4 is done and the maintainer says so.

## What Changed from the M4 Plan

- The service layer, the six service modules and the empty-state convention were [M4 Brief](M4%20Brief.md) on 2026-11-05. They are M5a to M5f here, with Battery and Workspaces together, and Network, Media, Audio and Tray each on their own.
- The old M5 desktop integration joins as M5g (the KWin script, fullscreen hiding, Tasks) and M5h (portal settings). Global shortcuts and the launcher moved to [M6 Brief](M6%20Brief.md): they belong with focus and keyboard.
- Gap G11 of the old plan (popup submenus, `caller.data`, `Menu` and `MenuItem`) moved to M4.
- By the time M5 starts, M4 will have built the standard modules a service module is composed from (Label, Icon, Button, Slider, ProgressBar, List, Menu): Battery, Workspaces and the rest use them and no longer wait for them.

## Goal and Definition of Done

M5 is done when:

- `ctx.dbus` gives a module a session or a system bus, a proxy with `get`, `call` and `on_property_changed`, and every call has a timeout and runs off the loop thread ([D-Bus Service Layer > Calling a Service](../40%20Specifications/Integration/D-Bus%20Service%20Layer.md#calling-a-service)).
- A service that is missing is a state: the module shows its empty or hidden state, and recovers without a shell restart when the service returns (`on_service_lost`, `on_service_found`).
- Each of the six modules shows live values on the Bar, and each has a fake-service test on a private bus and a KWin check by the maintainer.
- No module polls where a signal exists; with no signal traffic the layer wakes the process zero times in 60 seconds.
- Restarting `plasmashell` or `upowerd` does not stop the shell ([Plasma Coexistence](../40%20Specifications/Integration/Plasma%20Coexistence.md)).
- The KWin integration and the portal settings work as their own checklists say (written when M5g and M5h are planned).

Not in M5: global shortcuts and the launcher ([M6 Brief](M6%20Brief.md)), the notification centre (after v1), packaging (M7).

## Proposed Split

Each part ends with something the maintainer can look at on KWin. Order by risk: the layer first, then the modules whose service was read on this machine and whose behaviour is simple, then the ones with an unsettled access path, then the integration.

| Part | Content | Done when |
|---|---|---|
| M5a: the layer | The full service layer on the `dbus` thread (session and system bus, proxy, `PropertiesChanged`, `NameOwnerChanged`, reconnect), the hooks `on_service_lost` and `on_service_found`, the fake-service test harness, the empty-state convention (G2) | A test module reads a fake service, loses it, and gets it back; the layer's acceptance criteria that need no module pass |
| M5b: Battery and Workspaces | The two modules whose services are read and simple | Each shows live values on the Bar and hides or empties itself when its service is missing |
| M5c: Network | NetworkManager: connectivity, the primary connection, Wi-Fi strength | Unplugging a cable or turning Wi-Fi off changes the Bar |
| M5d: Media | MPRIS: the active player, controls, artwork, position (G7) | The Media module follows a running player; no player: hidden |
| M5e: Audio | The audio spike (G3) and its ADR, then volume, mute and the default sink | Changing the volume in System Settings updates the Bar and the Bar's slider changes the volume |
| M5f: Tray | The StatusNotifierItem host, item icons and the menu | An application's tray icon shows on the Bar, a click activates it, and its menu opens |
| M5g: KWin integration | The KWin script and fullscreen hiding ([KWin Integration](../40%20Specifications/Integration/KWin%20Integration.md)), the window list and Tasks | A fullscreen window hides the shell as designed; Tasks lists windows |
| M5h: portal settings | The portal settings beyond the M3a reader: contrast, motion, anything the maintainer names ([Portals](../40%20Specifications/Integration/Portals.md)) | Written when M5h is planned |

Recommendation: build in that order. Tray is a project of its own (the item protocol, the menu protocol, icon pixmaps and icon names), so it goes last of the services and may be split further.

## Design Needed First

| # | Gap | State | Recommendation |
|---|---|---|---|
| G1 | Where Tasks and the launcher belong. Decided 2026-11-05: M5 with the KWin script and the shortcuts. Changed 2026-11-08: Tasks stay in M5 (M5g), because they need the window list from the KWin script; the launcher moves to [M6 Brief](M6%20Brief.md), because it needs a shortcut key, a TextInput and a List | Decided as stated; the shortcut design is written ([Global Shortcuts](../40%20Specifications/Integration/Global%20Shortcuts.md)), the action names are undecided | Write Tasks into [Development Readiness](Development%20Readiness.md) and [Modules](../40%20Specifications/Modules/Modules.md) under M5g and the launcher under M6 |
| G2 | The empty state: what "the module hides itself" means in a file. A module is a block the shell builds; a module that hides itself needs a rule that the Bar's layout understands | [D-Bus Service Layer](../40%20Specifications/Integration/D-Bus%20Service%20Layer.md) says "hides itself" per module; no note defines the mechanism | One convention: every service module sends `available` (boolean) and the module's `Children` wrap in `If: available`. The layer sets `available` false on `UNAVAILABLE`. Write it in [Module Context](../42%20Python%20API/Module%20Context.md) and each module spec |
| G3 | The audio access path. PipeWire has no D-Bus interface for volume. Candidates: a library over the PulseAudio compatibility protocol, a subprocess that follows events (`pactl subscribe`) with `wpctl` for reads and writes, or a PipeWire binding | Open since 2026-10 ([D-Bus Libraries for Python > Open](../90%20Research/D-Bus%20Libraries%20for%20Python.md#open), [System Context](../20%20Architecture/System%20Context.md)); nothing was read | A spike at the start of M5e compares them on this machine: events without polling, idle cost, a dependency count that fits [ADR-0019 Dependency Policy](../30%20Decisions/ADR-0019%20Dependency%20Policy.md). The result goes in an ADR (`proposed`) before the Audio module is built |
| G4 | Module specs. Only [Clock Module](../40%20Specifications/Modules/Clock%20Module.md), [Battery Module](../40%20Specifications/Modules/Battery%20Module.md) and [Workspaces Module](../40%20Specifications/Modules/Workspaces%20Module.md) exist (the last two are `draft`). Network, Media, Audio and Tray each need a spec from the template (values sent, Params, actions, empty state, tooltip, accessibility, budget, acceptance criteria) | Network written and accepted 2026-11-13; Media written and accepted 2026-11-13; Audio and Tray not written | Write them one at a time, each at `review` before its part starts; Battery and Workspaces first |
| G5 | The layer's open questions: callback numbers (1 ms, 50 ms), whether the two hooks belong to the contract (recommended) or to the subscription call, lazy system bus (recommended) | [D-Bus Service Layer > Open Questions](../40%20Specifications/Integration/D-Bus%20Service%20Layer.md#open-questions) | Measure in M5a and settle; add the hooks to [Module Contract](../42%20Python%20API/Module%20Contract.md) |
| G6 | Workspaces: reading is verified (`current`, `desktops`, `currentChanged` on `/VirtualDesktopManager`); switching a desktop was not called, and a rename or a reorder signal was not seen | [D-Bus Service Layer > The Service Catalogue](../40%20Specifications/Integration/D-Bus%20Service%20Layer.md#the-service-catalogue) | Read the switch call and the change signals read-only, then settle the module spec |
| G7 | Media position. MPRIS emits `Seeked` but no signal while a track plays, so a progress bar cannot follow a position without a timer | Not in the catalogue | Compute the position from the last read, the rate and the time, and re-read on `Seeked`, `PlaybackStatus` and `Metadata` changes; a module timer ticks only while a Slider is visible and playing. Write it in the Media spec |
| G8 | Icons from the system. Tray items and Tasks give an icon name or pixmap data, not a path; the shell ships only `mdi` | [Block Reference > Icons (R7)](../41%20TDL%20Reference/Block%20Reference.md#icons-r7) decides the lookup order: the shipped set, the freedesktop icon theme, the config `Icons` folder, the settings list. M4 builds the widget side | Decide in the Tray spec how a name resolves through the freedesktop icon-theme directories (files read by the shell, decoded pixels to tre; AGENTS > 3. Layering Principle) and how pixmap data is used; `mdi` is the fallback. Needs a small spike |
| G9 | The tray menu. The menu protocol is `com.canonical.dbusmenu`; the menu opens as a `Popup` and uses `Menu` and `MenuItem` (built in [M4 Brief](M4%20Brief.md)), and the item's own `ContextMenu` call is the fallback | Not read on this machine | Read the menu interface read-only on one item before writing the Tray spec; build the menu from the items, not from the item's own window |
| G10 | The fake-service harness. The portal reader already has a fake portal on a private bus ([M3 Build Log](M3%20Build%20Log.md), `tests/test_portal_live.py`) | Built for one service | Generalise it to a small helper that exports a fake interface with settable properties and signals; every module test uses it ([Testing Strategy](../60%20Quality/Testing%20Strategy.md)) |
| G12 | Content fade and a module that hides itself. The accepted fade (not built when this was written) applies to a surface's slide, peek, show and hide, and to an Expander's content. A service module hides by `available` plus `If` (G2), which is not a surface motion | The accepted fade rule does not say | Recommended: the fade does not apply to `If`; only a surface's own motion and an Expander fade. Write it in [Module Context](../42%20Python%20API/Module%20Context.md) with G2. Maintainer to confirm (question 8) |

(G11 of the old plan moved to [M4 Brief](M4%20Brief.md) as W4; the number is not reused.)

Notes that must be at `review` before a part starts, with their status on 2026-11-08: M5a needs [D-Bus Service Layer](../40%20Specifications/Integration/D-Bus%20Service%20Layer.md) (`draft`), [Module Context](../42%20Python%20API/Module%20Context.md) and [Module Contract](../42%20Python%20API/Module%20Contract.md) (edited for G2 and G5; both `review`); M5b needs the Battery and Workspaces specs (both `draft`); M5c needs the [Network Module](../40%20Specifications/Modules/Network%20Module.md) spec (written 2026-11-13, accepted the same day: all seven questions answered); M5d needs the [Media Module](../40%20Specifications/Modules/Media%20Module.md) spec (written and accepted 2026-11-13 by the orchestrator); M5e needs the [Audio Module](../40%20Specifications/Modules/Audio%20Module.md) spec and [ADR-0021 Audio Access](../30%20Decisions/ADR-0021%20Audio%20Access.md) (both written and accepted 2026-11-13); M5f needs the [Tray Module](../40%20Specifications/Modules/Tray%20Module.md) spec (written and accepted 2026-11-13; it settles G8 and G9) and [Plasma Coexistence](../40%20Specifications/Integration/Plasma%20Coexistence.md) (`draft`); M5g needs [KWin Integration](../40%20Specifications/Integration/KWin%20Integration.md) (`review`) and the [Tasks Module](../40%20Specifications/Modules/Tasks%20Module.md) spec (written and accepted 2026-11-13); M5h needs [Portals](../40%20Specifications/Integration/Portals.md) (`draft`). The vault session lists each part's notes and their status before that part starts, and the maintainer waives or accepts any that is not at `review` (the M3 Brief closed with one such waiver open).

## Tasks

### M5a: the Layer

| # | Task | Done when |
|---|---|---|
| A1 | Extend `services/bus.py`: a system-bus connection on first use, a reconnect with back-off 1, 2, 4, 8 s capped at 30, the shell's own name re-requested | Killing and restarting the bus daemon in a test brings the layer back |
| A2 | `ctx.dbus.session()` and `.system()`, `proxy(name, path)`, `get`, `call` with a timeout (default 5 s), `on_property_changed`; a blocking form on the loop thread raises | The layer's acceptance criteria on threads and timeouts pass |
| A3 | One match rule per (bus, sender, path, interface, member) however many modules subscribe; removed with the last subscriber | Two modules, one rule, in a test |
| A4 | `NameOwnerChanged`: `UNAVAILABLE`, `on_service_lost`, `on_service_found`, re-read | A fake service that leaves and returns drives the hooks |
| A5 | The empty-state convention (G2): `available` sent by the layer on a state change | A test module hides and shows through `If` |
| A6 | The fake-service helper (G10); the callback-time guard (log over 50 ms with the module name) | Reported with the measured callback times |
| A7 | Tests, a measurement of idle wake-ups over 60 s | Reported against [Performance Budgets](../60%20Quality/Performance%20Budgets.md) |

### M5b: Battery and Workspaces

| # | Task | Done when |
|---|---|---|
| B1 | Battery (UPower `DisplayDevice`): percentage, state, icon, time to empty or full; hidden when `IsPresent` is false; power profile optional | A fake UPower service drives the Bar through charge, discharge and absent; on this desktop the module is hidden |
| B2 | Workspaces (`/VirtualDesktopManager`): the list, the current one, a click switches | Switching a desktop in KWin updates the Bar; a click on a name switches |
| B3 | A KWin check, tests on the fake services, a measurement | Reported |

### M5c: Network

| # | Task | Done when |
|---|---|---|
| C1 | Network (NetworkManager): connectivity, the primary connection's type and name, Wi-Fi strength if present | Unplugging a cable or turning Wi-Fi off changes the Bar |
| C2 | A KWin check, tests on the fake service, a measurement | Reported |

### M5d: Media

| # | Task | Done when |
|---|---|---|
| D1 | Media (MPRIS): finds the active player among `org.mpris.MediaPlayer2.*`, title, artist, status, controls, artwork read by the shell from the file URL | A running player shows and its play and next buttons work; no player: hidden |
| D2 | Media position and the seek Slider (G7) | The slider follows playback and a seek sets the position |
| D3 | A KWin check, tests, a measurement | Reported |

### M5e: Audio

| # | Task | Done when |
|---|---|---|
| E1 | The audio spike (G3) and its `proposed` ADR | The maintainer picks the path |
| E2 | Audio: volume, mute, the default sink's name; a slider and a mute button | Changing the volume in System Settings updates the Bar and the Bar's slider changes the volume |
| E3 | A KWin check, tests, a measurement | Reported |

### M5f: Tray

| # | Task | Done when |
|---|---|---|
| F1 | The host: the name `org.kde.StatusNotifierHost-<pid>`, `RegisterStatusNotifierHost`, the item list from the watcher and its two signals | An existing item appears; a started application's item appears |
| F2 | Item properties and icons: `IconName`, `IconPixmap`, `Title`, `Status`, the icon lookup (G8) | The icons match the application's; a `Passive` item is hidden |
| F3 | Activate, secondary activate and scroll; `ContextMenu` | A left click activates the application |
| F4 | The item's menu through `com.canonical.dbusmenu` as a `Popup` (G9) | A right click opens the menu and a click on an entry runs it |
| F5 | No watcher: the module is empty and one warning is logged; the shell never starts its own ([Plasma Coexistence > Tray](../40%20Specifications/Integration/Plasma%20Coexistence.md#tray)) | A test with no watcher passes |
| F6 | A KWin check beside plasmashell's tray, tests, a measurement | Reported |

### M5g and M5h: KWin Integration and Portal Settings

Written by the orchestrator on 2026-11-13.

| # | Task | Done when |
|---|---|---|
| G1 | The KWin script package and its run-time load (mode R), the KWin version check, `FullscreenState` and hiding the shell's surfaces on an output with an active fullscreen window ([KWin Integration](../40%20Specifications/Integration/KWin%20Integration.md)) | The acceptance criteria of [KWin Integration](../40%20Specifications/Integration/KWin%20Integration.md) that need no real KWin pass on a fake `/Scripting` and a fake script |
| G2 | The window list: `WindowsState`, the enable reply, `ctx.windows`, the one-shot action scripts ([Tasks Module](../40%20Specifications/Modules/Tasks%20Module.md)) | The shell-side criteria of [Tasks Module](../40%20Specifications/Modules/Tasks%20Module.md) pass |
| G3 | The desktop-entry index and `ctx.icons.app_icon` | An application's icon is found from its desktop file name in a temporary data folder |
| G4 | The Tasks module and `Task_Item` | The module's criteria pass |
| G5 | The `kwin script` and `kwin rule` commands | `status` reports; `rule show` prints; `install` and `remove` are tested on a temporary copy of the rule file, never the real one |
| H1 | Portal settings ([Portals](../40%20Specifications/Integration/Portals.md)): the icon theme and the UI font from the Settings portal (`org.gnome.desktop.interface` `icon-theme` and `font-name`, read on this machine on 2026-11-13 as `breeze-dark` and `Hack Nerd Font  10`), following `SettingChanged`; the icon service uses the portal's theme before `kdeglobals` | A fake portal changing `icon-theme` re-resolves the Tray's and Tasks' icons; the font is offered to themes as a token `type.system.font_family` |
| H2 | `enable-animations` false from the portal is treated as reduced motion, with the `reduced-motion` key | A fake portal setting either gives no animation |

## Dependencies

`dbus-fast` (already in at M3a), `tess_utils` (colour, sides), `tess_re` (`Window.apply`, images), the packages in use; the widgets of [M4 Brief](M4%20Brief.md) (Label, Icon, Button, Slider, ProgressBar, List, Menu); the icon-theme lookup (G8) for the Tray; the audio path (G3) may add one dependency or none. Nothing here needs tre changes known today; a gap found goes to a `TRE-REQ` through the maintainer (AGENTS > 6. Requests Between Projects).

## Risks

- A service the code session cannot reach from a headless sway (UPower, NetworkManager, MPRIS) is tested on fake services only; the real behaviour is the maintainer's KWin check. This desktop has no battery, so Battery is checked by a fake service and by its hidden state here.
- Tray items differ widely in what they send (pixmap only, name only, a theme name in `IconThemePath`); the Tray is the most likely to grow. R-19 (user Python in the process) matters more once modules call services.
- A slow callback delays every D-Bus module ([ADR-0009 D-Bus Client Library > Options](../30%20Decisions/ADR-0009%20D-Bus%20Client%20Library.md#options)); A6 measures it before the modules rely on it.
- M5 is one milestone with eight parts; the parts are what the maintainer checks, so a long M5 is a series of small checks.

### M5i: the Control Interface (Added 2026-11-13)

Added by the orchestrator on 2026-11-13 ([Orchestration Log](Orchestration%20Log.md) D-036): the control interface was in no part of M5 or M6, and the command line's control commands are stubs from M0.

| # | Task | Done when |
|---|---|---|
| I1 | The shell owns its bus name and exports the control interface of [ADR-0013 Control Interface](../30%20Decisions/ADR-0013%20Control%20Interface.md); `status`, `reload`, `quit`, `show`, `hide`, `toggle`, `call` and `log-level` work from the command line as [IPC and CLI](../40%20Specifications/Runtime/IPC%20and%20CLI.md) says; the name is requested again after a bus restart | Each command works against a shell on a private bus and compositor in a test; `status --json` has a recorded fixture; a second shell started in the same session exits with the error the spec names |

## Questions for the Maintainer

Questions 1 to 7 were answered on 2026-11-05 for this plan when it was M4 (1 to 5 and 7 as recommended; 6 as stated). Question 8 is open; 9 was answered on 2026-11-08.

1. [x] G1: move Tasks and the launcher to M5 with the KWin script and the shortcuts? Recommendation: yes. (Changed 2026-11-08: Tasks stay in M5, the launcher moves to M6.)
2. [x] G2: the empty-state convention, `available` plus `If`. Recommendation: yes; one rule for every module.
3. [x] G3: run the audio spike at the start of the Audio part and decide by ADR (asked as M4c). Recommendation: yes.
4. [x] The split of the services in that order (asked as M4a to M4d), with Tray movable. Recommendation: yes. (Split further on 2026-11-08: M5a to M5h.)
5. [x] G4: write the module specs in the order Battery, Workspaces, Network, Media, Audio, Tray, each at `review` before its part. Recommendation: yes; the vault session writes them.
6. [x] Battery is tested on the fake service only; there is no laptop check. The Battery KWin check is therefore the hidden state on this desktop (`IsPresent` false) plus the fake service.
7. [x] Decided: all six, in that order. Does the default shell show all six at once on the Bar, or is the default Bar a smaller set? This changes the shipped `Main_Shell.tdl`, not the modules. Recommendation: all six, in the order Workspaces, Media, Network, Audio, Battery, Tray, Clock.
8. [x] G12: should the content fade skip a module that appears or disappears through `If`, so that only a surface's own motion and an Expander fade? Context: a fade on every `If` change would make the empty-state convention (G2) flicker as services come and go. Recommendation: yes. Yes: the content fade skips a module that appears or disappears through `If`; only a surface's own motion and an Expander fade (maintainer, 2026-11-12, as recommended).
9. [x] M5 stays one milestone, broken into smaller parts (maintainer, 2026-11-08), with focus and keyboard as M6 and release as M7.
10. [x] Should a call to a service with no owner raise `ServiceUnavailable` (with `.state`), rather than return `UNAVAILABLE` as [D-Bus Service Layer > Calling a Service](../40%20Specifications/Integration/D-Bus%20Service%20Layer.md#calling-a-service) says? Context (code session's M5a report, not confirmed here): a return value would make every call site compare against a sentinel; the state is also on `bus.state(name)` and in `available`. Recommendation: raise, and the vault rewrites the spec line to match. Maintainer, 2026-11-12: as recommended.
11. [x] Is "an unread service counts as unavailable" right, so `available` is false right after `proxy()` and turns true when the service is read, a few milliseconds later? Context (reported): a module with two services may get `false, true`. Recommendation: yes; the module is hidden until its service is read. Maintainer, 2026-11-12: as recommended.
12. [x] Should a module hear `on_service_lost` for a service that was absent from the start? Context (reported): nothing was lost; the module sees `available: false` and gets `on_service_found` when the service appears. Recommendation: no. Maintainer, 2026-11-12: as recommended.
13. [x] When the IPC interface is built, who re-requests the shell's own bus name after a bus restart? Context: the layer has `Bus.on_reconnect(hook)`; the shell owns no bus name yet. Recommendation: the IPC module, through `Bus.on_reconnect` and once at start. Maintainer, 2026-11-12: as recommended.
14. [x] Is the AND rule right for `available` when a module uses several services (all present)? Context (reported): Tray (watcher plus an item) and Media (several players) use more than one. Recommendation: yes; a module that needs "any" (Media) makes one proxy per player after it finds them and reads `bus.state(name)`. Maintainer, 2026-11-12: as recommended.
15. [x] Should a one-shot `proxy.get` leave a `PropertiesChanged` rule on the bus for the life of the module? Context (reported): `get` is cached and subscribes the first time; `fresh=True` asks the service directly. Recommendation: accept; `fresh=True` covers the rare one-off read. Maintainer, 2026-11-12: as recommended.
16. [x] Keep the identity scheme for a module call inside `If` and `For` (parent use, the `For`'s place in the layout, the entry's TEL name, and the call's place, with no source line)? Context (code session's report of d47f5d4, not confirmed here): a first version used the source line, and the shell's own `UID:` write shifted every key on the first hot reload; a live test caught it. Recommendation: yes. Maintainer, 2026-11-13: yes.
17. [x] Should a module call inside an `If` stay one static use, so only its blocks come and go and `start` and `stop` do not run on a flip? Context (reported): in a `For` each entry is its own use with `use_added` and `use_removed`. Recommendation: yes. Maintainer, 2026-11-13: yes.
18. [x] Should the next piece of work be a module call in a `For` inside a Popup? Context (reported): the Tray menus need it, and the uses end when the Popup closes; today it is an error naming the call. Recommendation: yes, as separate work before the Tray part. Maintainer, 2026-11-13: yes.

Reported by the code session, not confirmed here (peer messages, 2026-11-12): the maintainer answered the M5b decisions in its session: a `{{ }}` slot in an icon param, yes; a hidden module takes no Bar Spacing, fix now; keep the warning when a service leaves; leave `profile` unused until the Menu that switches profiles; a `TRE-REQ` for the tre `visible: false` layout-space quirk, not filed because the shell handles it; an unknown runtime icon shows the broken-image icon; a module call inside `If` and `For`, as separate work. These are recorded in [M5 Build Log](M5%20Build%20Log.md), and the specs below follow them.

19. [x] Should the code session fix the Workspaces current-desktop marker now? Context: it is the M5b KWin failure of 2026-11-13 (see KWin Results below): the marker does not follow a desktop change, and clicks stop working after the first switch. Recommendation: yes, before M5c; the code session finds the cause (reported: the module reads KWin's `current`, and a fake KWin passes), and a test that changes `current` on a second real property signal is added. Done without waiting for an answer: the code session reports the fix in aab71a4 (a click compared against a stale own copy of `current`: certain; the module did not listen to KWin's `currentChanged` and `countChanged`: inferred, not seen on your KWin). The maintainer re-tested it on KWin and it works (2026-11-13).
20. [x] Inside an entry of a `For` call, should `ctx.caller` stay as built: for a handler written on the call it is the holder of the call, and for the entry's own layout it is the entry's use? Context (code session's report of 36fa502, not confirmed here; it is question 19 in the M5 Build Log). Recommendation: keep. Maintainer, 2026-11-13: keep.
21. [x] Should `caller.data` stay a copy made when the Popup opens? Context (reported; build log question 20). Recommendation: keep. Maintainer, 2026-11-13: keep.
22. [x] Is a shell-file `If` or `For` written directly in a Popup's content left out for now? Context (reported; build log question 21): it is still refused; module layouts inside a Popup can use them (the Tray menus). Recommendation: yes, not now. Maintainer, 2026-11-13: yes.
23. [x] Should the Network tooltip's Wi-Fi percent round down in fives (72 and 73 both show 70), or to the nearest five (72 shows 70, 73 shows 75)? Context (code session's M5c report, 01dc853, not confirmed here; its question 22): your answer to the Network spec was "rounded to 5", and the spec's own acceptance bullet (72 to 73 changes nothing sent) only fits round-down; the code session built round-down. Recommendation: keep round-down, and the spec says "rounded down in fives". Decided by the orchestrator on 2026-11-13 (directive rule 7, Tier 1): as recommended.
24. [x] Should the icon rows that the Network spec's table lacks, which the code session filled (for example connected with no known kind shows `network`), be folded into the spec's table? Context (reported; its question 23). Recommendation: yes; the vault copies them from the build log into the table. Decided by the orchestrator on 2026-11-13 (directive rule 7, Tier 1): as recommended.
25. [x] When a VPN is the primary connection, should the icon describe the link under it and the tooltip add `VPN <name>`? Context (reported; its question 24): the spec said a VPN is never the kind, but it did not say what to show when NetworkManager reports the VPN as primary. Recommendation: yes. Decided by the orchestrator on 2026-11-13 (directive rule 7, Tier 1): as recommended.
26. [x] Should the Network state-change announcement to assistive technology be left to the M6 accessibility pass? Context (reported; its question 25): the spec proposed one polite announcement when the state changes to or from connected; it is not built. Recommendation: yes, M6 builds every announcement together. Decided by the orchestrator on 2026-11-13 (directive rule 7, Tier 1): as recommended.

## KWin Results (maintainer, 2026-11-13)

M5b checklist, part 1, real buses (`/tmp/tess-kwin-m5b`):

| Row | Result |
|---|---|
| 1 Battery hidden, no gap | Pass |
| 2 Workspaces names, current marked | Pass |
| 3 Workspaces numbers, current marked | Pass |
| 4 Ctrl+F2 or the pager moves the mark | Fail: the marker does not move with the workspace change using Ctrl+F2 |
| 5 Click a desktop, KWin switches and the mark follows | Fail: the workspace switches but the marker does not change; once moved, clicking on the previous one does not work; only the first click of the second named or second numbered workspace works, with no marker change |
| 6 Hover look | Pass |
| 7 Rename, add, remove a desktop | Pass |
| 8 Arrow cursor over the buttons | Pass |
| 9 Log has no ERROR | Pass |
| 10 Restart KWin (optional) | Skipped |

Rows 4 and 5 were re-tested after the fix (aab71a4) and pass (maintainer, 2026-11-13). Part 2 (fake battery, rows 11 and on) was re-checked and all rows pass (maintainer, 2026-11-13). So the M5b KWin checklist passes: Battery and Workspaces are confirmed on KWin.

## Acceptance Criteria

- [ ] Every line of "Goal and Definition of Done" is true, with a KWin check of each module.
- [ ] Each task has a test or a recorded measurement.
- [ ] The notes listed under "Design Needed First" are at `review` before the part that needs them starts, or the maintainer has waived one.
- [ ] Design gaps found are handed back to the vault session.

## Links

- [Development Readiness](Development%20Readiness.md) · [M4 Brief](M4%20Brief.md) · [M6 Brief](M6%20Brief.md) · [D-Bus Service Layer](../40%20Specifications/Integration/D-Bus%20Service%20Layer.md) · [Module Context](../42%20Python%20API/Module%20Context.md) · [Module Contract](../42%20Python%20API/Module%20Contract.md) · [Plasma Coexistence](../40%20Specifications/Integration/Plasma%20Coexistence.md) · [V1 Widgets](../50%20Design%20System/V1%20Widgets.md) · [V1 Scope](../10%20Vision/V1%20Scope.md) · [Performance Budgets](../60%20Quality/Performance%20Budgets.md) · [Testing Strategy](../60%20Quality/Testing%20Strategy.md) · [KWin Integration](../40%20Specifications/Integration/KWin%20Integration.md) · [Portals](../40%20Specifications/Integration/Portals.md)
