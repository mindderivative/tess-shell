---
title: V1 Scope
aliases: [v1, Version 1 Scope, Scope of v1]
type: vision
status: stable
owner: phil
created: 2026-10-25
updated: 2026-10-25
tags: [vision]
related: ["[[10 Vision]]", "[[Goals and Non-Goals]]", "[[Personas and Use Cases]]", "[[ADR-0001 Shell Surface Strategy]]"]
depends_on: ["[[ADR-0001 Shell Surface Strategy]]"]
---

# v1 scope

> [!summary]
> Recommendation: v1 is a working bar, popups, OSDs, a launcher and movable desktop widgets, on KDE Plasma 6 Wayland (KWin), with wlroots compositors best effort. Any monitor can host the shell, each configured separately in one configuration, with all, some or none of the surfaces ([[#Multi-monitor]]). It ships a default shell built from eight modules. Notification centre, screen frame and the Tesserae Shell package manager are after v1. Confirmed by the maintainer on 2026-10-25, including the multi-monitor rules ([[#Multi-monitor]]).

## Target environment

| Item | v1 | Basis |
|---|---|---|
| Desktop | KDE Plasma on Wayland | [[AGENTS#1. What Tesserae Shell is]] |
| Compositor | KWin first. wlroots compositors (sway tested by tre) best effort, not a release gate. | tre tested KWin 6.8.1 and sway 1.12 ([[TRE-REQ-001 Layer Surface Window#Delivered (tre #195 closed)]]) |
| Engine | `tesserae-engine` 0.5.8 or later | PyPI, 2026-10-25 |
| Not supported | X11, GNOME, Windows, macOS | `LayerWindow` raises `UnsupportedPlatform`; GNOME decision deferred to testing ([[ADR-0001 Shell Surface Strategy#Open items]]) |

## Surfaces

The shell has four surface types: Bar, Frame, Panel and Popup ([[Surface Types]], [[ADR-0007 Shell UI Layer#Surface types (2026-10-25)]]). The rows below are uses; the surface type for each is in the Note column.

| Surface | In v1 | Use case | Note |
|---|---|---|---|
| Bar | Yes | UC1, UC11 | Type Bar. On each monitor that lists it; reserves an exclusive zone. A dock or side bar is a Bar. |
| Popup (menu, flyout) | Yes | UC2 | Type Popup. `PopupWindow`. Escape dismissal is untested in tre; the spec names it as a gap. |
| OSD (on-screen display: a small overlay that appears briefly to confirm an action, such as a volume bar when a volume key is pressed, then disappears) | Yes | UC3 | Type Panel (decided 2026-10-25), click-through, on its configured monitor. |
| Launcher | Yes | UC4 | Panel on the `overlay` layer with exclusive keyboard (decided 2026-10-25). Shortcut through KDE's global-accel service ([[ADR-0005 Global Shortcuts]]); opens on its configured monitor. |
| Desktop widget | Yes | UC5 | Type Panel (decided 2026-10-25). Movable, position saved from `moved`. |
| Panel (slide-in) | Yes | UC6 | Type Panel. Margin animation. |
| Wallpaper | Later | none | `background` layer; no use case written. |
| Screen frame | Yes | UC7 | Type Frame, in v1 (decided 2026-10-25). The four-reserver plus painter layout was not tested together by tre; concave corners and join hit testing are asked of tre ([[Surface Types#Open questions]]). |

## Multi-monitor

Maintainer requirement (2026-10-25): any monitor can host the shell, each monitor is configured separately, and each monitor can have all, some or none of the surfaces. Separate configuration does not mean separate files: one configuration holds a section per monitor.

| Rule | Meaning |
|---|---|
| Equal monitors | No monitor is special to the tool. "Primary" is a configuration choice, not a built-in role. |
| Per-monitor surface set | Each monitor lists the surfaces it shows (bar, OSD, widgets and so on), their position and their modules. |
| All, some or none | A monitor may show every surface, a chosen subset, or nothing. A monitor with none gets no `LayerWindow` at all. |
| Hot-plug | Adding a monitor opens its configured surfaces. Removing one closes them, and the shell creates new windows on return because a closed `LayerWindow` is dead ([[TRE-REQ-001 Layer Surface Window#Lifecycle and events]]). |
| Identity | A monitor is matched by the connector name tre reports (`Output.name`, for example `DP-1`) ([[TRE-REQ-001 Layer Surface Window#Outputs]]). |

Every `LayerWindow` is bound to an explicit `Output`, never `output=None` ([[TRE-REQ-001 Layer Surface Window#Delivered (tre #195 closed)]]).

Decided by the maintainer in chat, 2026-10-25:

- [x] **Naming a monitor.** A configuration section matches a monitor by connector name, with an optional match on the display description, so one profile can follow a particular display. Connector names can change between ports and docks.
- [x] **Unnamed monitors.** A monitor no section names gets a configurable default section, which may itself be "none".
- [x] **Sharing.** A surface is defined once and referenced from several monitors, so the definition lives once ([[AGENTS#2. Hard rules]], rule 4).
- [x] **How `monitor` is written.** Decided 2026-10-25 ([[ADR-0007 Shell UI Layer#Monitors (2026-10-25)]]): connector name, then display description; `monitor: default` for monitors no root names; a root with no `monitor` is ignored. This is the same as the first three points above.
- [x] **Single-place surfaces (launcher, OSD).** Each names its monitor in its own configuration: a configured monitor, not the focused or pointer's one.

- [x] **Mirrored outputs and output changes (`output_updated`).** Accepted by the maintainer, 2026-10-25, as recommended: (1) treat every `Output` tre reports as one monitor, so mirrored screens that appear as two outputs are configured as two, and a mirror that appears as one output is one monitor; (2) on `output_updated`, keep the surfaces and re-evaluate only the match rules, recreating a surface set only when the match result changes (for example a description rule that no longer matches); (3) test mirroring on KWin in the testing phase and record what it reports. Basis: `output_updated` fires when a screen's position, size, scale or rotation changes, and tre follows the new scale itself ([Outputs](https://mindderivative.github.io/tre/reference/outputs/)). How the compositor presents mirrored screens to a client is not documented there. #needs-verification, deferred to the testing phase.

## Modules in the default shell

The eight modules, confirmed. Every module is available on any monitor's surfaces. Each becomes a spec under `40 Specifications/Modules/`.

| Module | Needs | Open decision |
|---|---|---|
| Clock | Time source | none |
| Workspaces | KWin virtual desktops | Which protocol or D-Bus API; #needs-verification |
| Tasks (window list) | Foreign-toplevel or KWin interface | Same; #needs-verification |
| System tray | StatusNotifierItem | Who owns `StatusNotifierWatcher` when plasmashell runs: coexist, replace or proxy |
| Audio | PipeWire | none known |
| Network | NetworkManager D-Bus | none known |
| Battery | UPower D-Bus | none known |
| Media | MPRIS D-Bus | none known |

## After v1

| Item | Why it waits |
|---|---|
| Notification centre | Owns the `org.freedesktop.Notifications` name; coexistence with plasmashell is undecided. |
| Screen frame | Depends on an untested surface layout. |
| Wallpaper | No use case yet. |
| Other compositors, X11 | Out of scope until testing ([[Goals and Non-Goals]] N3). |
| Package manager for shared shells | A delivery question for `70 Delivery`. |

## Decisions to take

All four were taken by the maintainer on 2026-10-25 and are recorded as ADRs. One was reversed the same day: the Tesserae relationship. The shell's own view layer is `proposed` in [[ADR-0007 Shell UI Layer]].

| Decision | Outcome | ADR |
|---|---|---|
| Relationship to Tesserae UI | Separate project on tre; no `tesserae-ui` dependency. Replaces ADR-0002. | [[ADR-0006 Shell Independent of Tesserae UI]] |
| Process model | One process owning all surfaces and one event loop. | [[ADR-0003 Process Model]] |
| Plasma coexistence per service | Coexist by default; replace only after a per-service ADR. | [[ADR-0004 Plasma Coexistence]] |
| Global shortcuts | KDE's global-accel service. | [[ADR-0005 Global Shortcuts]] |

## Acceptance criteria

- [x] The maintainer confirmed the target environment, surface list, module list and after-v1 list (2026-10-25).
- [x] Multi-monitor rules confirmed, including mirrored outputs and `output_updated`. How KWin presents a mirrored pair is checked in the testing phase.
- [ ] Every surface in the table has a matching use case in [[Personas and Use Cases]].
- [ ] Every module row has a decision recorded or a `#needs-verification` tag.
- [x] Each "Decisions to take" row has an ADR, accepted by the maintainer.

## Links

- [[10 Vision]] · [[Problem Statement]] · [[Goals and Non-Goals]] · [[Personas and Use Cases]]
- [[ADR-0001 Shell Surface Strategy]] · [[TRE-REQ-001 Layer Surface Window]]
